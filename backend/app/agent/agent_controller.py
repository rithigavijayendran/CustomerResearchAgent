"""
Agent Controller - The Brain
Orchestrates multi-step reasoning, decision making, and tool usage
"""

import os
import re
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from app.rag.rag_pipeline import RAGPipeline
from app.rag.retrieval_api import RetrievalAPI
from app.tools.web_search import WebSearchTool
from app.tools.entity_extractor import EntityExtractor
from app.tools.conflict_detector import ConflictDetector
from app.llm.llm_factory import LLMFactory
from app.llm.gemini_engine import GeminiEngine
from app.llm.account_plan_generator import AccountPlanGenerator
from app.observability.tracing import TraceContext, trace_function
from app.observability.metrics import track_research, track_llm_request
from app.workers.background_tasks import get_worker
from app.orchestrator.query_router import get_router
from app.orchestrator.research_orchestrator import get_orchestrator
from app.processing.ingestion_pipeline import IngestionPipeline

logger = logging.getLogger(__name__)

class AgentController:
    """Main agent controller with multi-step reasoning"""
    
    def __init__(
        self,
        vector_store,
        session_memory,
        llm_engine: Optional[Any] = None
    ):
        self.vector_store = vector_store
        self.session_memory = session_memory
        
        # Initialize LLM engine (Gemini only)
        if llm_engine:
            self.llm_engine = llm_engine
        else:
            # LLMFactory.create_llm_engine() creates Gemini engine
            self.llm_engine = LLMFactory.create_llm_engine()
        
        # Determine which provider is being used (always Gemini)
        if isinstance(self.llm_engine, GeminiEngine):
            self.llm_provider = "gemini"
            logger.info("Using Gemini as LLM provider")
        else:
            raise ValueError("Only Gemini engine is supported. Please configure GEMINI_API_KEY.")
        
        # Initialize tools
        self.rag_pipeline = RAGPipeline(vector_store)
        self.retrieval_api = RetrievalAPI(vector_store) if vector_store else None
        self.web_search = WebSearchTool(vector_store=vector_store, llm_engine=self.llm_engine)
        self.entity_extractor = EntityExtractor(None)  # Entity extractor doesn't need LLM
        self.conflict_detector = ConflictDetector()
        self.background_worker = get_worker()
        self.query_router = get_router()
        self.account_plan_generator = AccountPlanGenerator(self.llm_engine)
        
        # Agent state
        self.current_step = None
        self.progress_updates = []
    
    async def process_message(
        self,
        message: str,
        session_id: str
    ) -> Dict[str, Any]:
        """Process user message and execute agent workflow"""
        self.progress_updates = []
        
        # Add user message to memory
        self.session_memory.add_message(session_id, "user", message)
        
        # Determine intent with conversation context
        intent = self._determine_intent(message, session_id)
        
        # Execute agent workflow
        if intent == "research_company":
            return await self._research_workflow(message, session_id)
        elif intent == "update_section":
            return await self._update_section_workflow(message, session_id)
        elif intent == "clarify":
            return await self._clarification_workflow(message, session_id)
        else:
            return await self._general_workflow(message, session_id)
    
    def _determine_intent(self, message: str, session_id: str) -> str:
        """Determine user intent with conversation context"""
        message_lower = message.lower()
        
        # Check conversation history for context
        session = self.session_memory.get_session(session_id)
        if session:
            recent_messages = session.get('messages', [])[-3:]  # Last 3 messages
            recent_text = " ".join([msg.get('content', '').lower() for msg in recent_messages])
            
            # If there's a company name in session and user is asking follow-up questions
            if session.get('company_name'):
                # PRIORITY: Check for account plan edit commands FIRST (before research commands)
                # Check if there's an existing account plan
                if session.get('account_plan'):
                    # Check for add field/section commands (with various phrasings)
                    add_patterns = [
                        "add field", "add section", "add new field", "add new section",
                        "add", "include", "insert field", "insert section"
                    ]
                    remove_patterns = [
                        "remove field", "remove section", "delete field", "delete section",
                        "remove", "delete", "drop field", "drop section"
                    ]
                    edit_patterns = [
                        "edit", "update", "change", "modify", "regenerate", "rewrite"
                    ]
                    
                    # Check if message contains add/remove/edit keywords AND mentions field/section names
                    if any(pattern in message_lower for pattern in add_patterns):
                        # Check if it mentions specific fields (CEO, revenue, CTO, etc.)
                        field_keywords = ["ceo", "cto", "revenue", "field", "section", "company"]
                        if any(keyword in message_lower for keyword in field_keywords):
                            return "update_section"
                    
                    if any(pattern in message_lower for pattern in remove_patterns):
                        return "update_section"
                    
                    if any(pattern in message_lower for pattern in edit_patterns):
                        return "update_section"
                
                # Check if this is a follow-up to research (conflicts, questions, clarifications)
                if any(word in message_lower for word in ["cross-check", "deeply", "verify", "check", "confirm", "prioritize"]):
                    return "research_company"  # Continue research workflow
                if any(word in message_lower for word in ["yes", "no", "clarify", "answer", "continue", "go with", "source a", "source b", "prioritize"]):
                    return "clarify"
        
        # Check for uploaded document references
        if any(word in message_lower for word in ["uploaded", "pdf", "document", "file", "refer"]):
            # Check if there are uploaded documents
            if self.vector_store:
                try:
                    # Quick check for uploaded documents
                    all_docs = self.vector_store.get_all_documents(limit=1)
                    if all_docs:
                        return "research_company"  # Use uploaded documents for research
                except:
                    pass
        
        # Check for account plan generation requests
        if any(phrase in message_lower for phrase in ["generate account plan", "create account plan", "make account plan", "account plan for"]):
            # If company is already in session with research data, we can generate directly
            if session and session.get('company_name') and session.get('research_data'):
                # Check if user wants to generate plan for a different company
                company_name = self._extract_company_name(message, session_id)
                if company_name and company_name.lower() == session.get('company_name', '').lower():
                    # Same company - can generate directly
                    return "research_company"  # Will skip to account plan generation
            return "research_company"
        
        if any(word in message_lower for word in ["research", "analyze", "company", "find", "generate", "create"]):
            return "research_company"
        elif any(word in message_lower for word in ["update", "rewrite", "regenerate", "edit"]):
            return "update_section"
        elif any(word in message_lower for word in ["yes", "no", "clarify", "answer"]):
            return "clarify"
        else:
            return "general"
    
    async def _research_workflow(
        self,
        message: str,
        session_id: str
    ) -> Dict[str, Any]:
        """Execute research workflow with interactive, conversational updates"""
        self.progress_updates.append("🔍 **Step 1: Discovering company identity...**")
        
        # Extract company name (from message or uploaded documents)
        company_name = self._extract_company_name(message, session_id)
        if not company_name:
            return {
                "response": "I need to know which company you'd like me to research. Please provide the company name.",
                "session_id": session_id,
                "questions": ["Which company would you like me to research?"]
            }
        
        # CRITICAL: Clear previous research data when researching a NEW company
        session = self.session_memory.get_session(session_id)
        previous_company = session.get('company_name') if session else None
        if previous_company and previous_company.lower() != company_name.lower():
            logger.info(f"New company research detected: {company_name} (previous: {previous_company}). Clearing old research data.")
            # Clear old research data for new company
            if session:
                session['research_data'] = []
                session['conflicts'] = []
        
        self.session_memory.set_company_name(session_id, company_name)
        self.progress_updates.append(f"✅ **Identified company:** {company_name}")
        
        # Step 2: Gather data with conversational updates
        self.progress_updates.append("📚 **Step 2: Collecting data from multiple sources...**")
        self.progress_updates.append(f"   → Starting comprehensive research on {company_name}...")
        self.progress_updates.append(f"   → Searching uploaded documents, web sources, and knowledge base...")
        research_data = await self._gather_data(company_name, session_id)
        
        # Step 3: Detect conflicts with conversational messaging
        # Check if user wants to skip conflict detection
        session = self.session_memory.get_session(session_id)
        skip_conflicts = False
        if session:
            recent_messages = session.get('messages', [])[-3:]
            recent_text = " ".join([msg.get('content', '').lower() for msg in recent_messages])
            # Check for skip conflict keywords
            if any(phrase in recent_text for phrase in ["without conflicts", "skip conflicts", "ignore conflicts", "no conflicts", "proceed without"]):
                skip_conflicts = True
                logger.info("User requested to skip conflict detection")
        
        if skip_conflicts:
            self.progress_updates.append("🔎 **Step 3: Skipping conflict detection (as requested)...**")
            conflicts = []
        else:
            self.progress_updates.append("🔎 **Step 3: Analyzing data for conflicts and contradictions...**")
            conflicts = self._detect_conflicts(research_data)
        
        # If all sources are from uploaded documents, skip conflict resolution
        uploaded_only = all(d.get('source_type') == 'uploaded_document' for d in research_data)
        if uploaded_only and conflicts:
            logger.info(f"All sources are uploaded documents - auto-resolving {len(conflicts)} conflicts by using uploaded document as authoritative")
            self.progress_updates.append("  ✅ Using uploaded document as authoritative source")
            conflicts = []  # Auto-resolve - uploaded docs are most trustworthy
        
        # Check if user wants to proceed despite conflicts (e.g., "cross-check deeply")
        user_wants_deep_check = False
        if session and not skip_conflicts:
            recent_messages = session.get('messages', [])[-2:]
            recent_text = " ".join([msg.get('content', '').lower() for msg in recent_messages])
            if any(word in recent_text for word in ["cross-check", "deeply", "verify", "proceed", "continue", "go ahead"]):
                user_wants_deep_check = True
        
        # Only show conflicts if they're significant and from different document types
        # Skip conflict resolution if user requested to skip conflicts
        if skip_conflicts:
            logger.info("Skipping conflict resolution as requested by user")
            conflicts = []
        
        if conflicts and not user_wants_deep_check and not skip_conflicts:
            # Limit to top 3 conflicts to avoid overwhelming user
            significant_conflicts = [c for c in conflicts if c.get('severity') == 'high'][:3]
            
            if significant_conflicts:
                self.session_memory.add_conflict(session_id, significant_conflicts)
                
                # Create conversational conflict messages - user-friendly, no URLs
                conflict_messages = []
                for conflict in significant_conflicts:
                    topic = conflict.get('topic', 'information')
                    values = conflict.get('conflicting_values', [])
                    sources = conflict.get('sources', [])
                    
                    # Format topic name nicely
                    topic_display = topic.replace('_', ' ').title()
                    
                    # Create a natural, conversational message with proper spacing
                    message = f"**I'm finding conflicting information about {topic_display}:**\n\n"
                    
                    # Group by value and create friendly source descriptions
                    sources_by_value = {}
                    for source in sources:
                        value = source.get('value', '')
                        source_type = source.get('source', 'unknown')
                        source_file = source.get('source_file', '')
                        source_url = source.get('source_url', '')
                        
                        # Create friendly source description (NO URLs)
                        if source_file:
                            # Extract just the filename, no path
                            import os
                            friendly_name = os.path.basename(source_file)
                            # Remove extension for cleaner display
                            friendly_name = os.path.splitext(friendly_name)[0]
                            friendly_name = friendly_name.replace('_', ' ').title()
                            source_label = f"Uploaded document ({friendly_name})"
                        elif source_type == 'uploaded_document':
                            source_label = "Uploaded document"
                        elif source_type == 'web_search':
                            source_label = "Web source"
                        else:
                            source_label = "Research source"
                        
                        if value not in sources_by_value:
                            sources_by_value[value] = []
                        sources_by_value[value].append(source_label)
                    
                    # Format values nicely with proper spacing
                    for i, value in enumerate(values[:3]):  # Limit to 3 values
                        source_list = sources_by_value.get(value, [])
                        # Get unique sources
                        unique_sources = list(set(source_list))
                        
                        # Create friendly source description
                        if len(unique_sources) == 1:
                            source_label = unique_sources[0]
                        elif len(unique_sources) == 2:
                            source_label = f"{unique_sources[0]} and {unique_sources[1]}"
                        else:
                            source_label = f"{unique_sources[0]}, {unique_sources[1]}, and {len(unique_sources) - 2} other source(s)"
                        
                        # Format value nicely
                        formatted_value = str(value).strip()
                        if topic in ['revenue', 'headcount']:
                            # Add formatting for numbers
                            try:
                                num = float(formatted_value.replace(',', ''))
                                if num >= 1000000:
                                    formatted_value = f"${num/1000000:.1f}M" if topic == 'revenue' else f"{int(num/1000000)}M"
                                elif num >= 1000:
                                    formatted_value = f"${num/1000:.1f}K" if topic == 'revenue' else f"{int(num/1000)}K"
                            except:
                                pass
                        
                        message += f"• **{source_label}** reports: {formatted_value}\n\n"
                    
                    message += f"\n\n**What would you like me to do?**\n"
                    message += f"• Type 'dig deeper' or 'verify' to cross-check this information\n"
                    message += f"• Type 'proceed' or 'continue' to use the most authoritative source\n"
                    message += f"• Type 'skip conflicts' to ignore this and continue with research"
                    conflict_messages.append(message)
                
                self.progress_updates.append(f"   ⚠️ **Found {len(significant_conflicts)} conflicting information point(s) - need your input**")
                
                return {
                    "response": "\n\n---\n\n".join(conflict_messages),
                    "session_id": session_id,
                    "progress_updates": self.progress_updates,
                    "questions": conflict_messages,
                    "conflicts_detected": len(significant_conflicts)
                }
            else:
                # Low severity conflicts - proceed automatically
                logger.info(f"Found {len(conflicts)} low-severity conflicts - proceeding automatically")
                self.progress_updates.append("  ✅ Minor discrepancies noted - proceeding with research")
        elif conflicts and user_wants_deep_check:
            # User wants to proceed with deep cross-checking
            self.progress_updates.append("  → Proceeding with deep cross-checking as requested...")
            logger.info(f"User requested deep cross-checking, proceeding despite {len(conflicts)} conflicts")
        
        # Validate research data is about the correct company
        if research_data:
            company_name_lower = company_name.lower()
            company_keywords = [company_name_lower]
            if ' ' in company_name:
                company_keywords.append(company_name_lower.replace(' ', ''))
                company_keywords.append(company_name_lower.split()[0])
            
            # Filter out documents that don't mention the company
            filtered_research_data = []
            for data in research_data:
                text = data.get('text', '').lower()
                # Check if document mentions the company (at least once)
                if any(keyword in text for keyword in company_keywords):
                    filtered_research_data.append(data)
                else:
                    logger.warning(f"Filtered out document that doesn't mention {company_name}")
            
            if len(filtered_research_data) < len(research_data):
                logger.info(f"Filtered research data: {len(research_data)} -> {len(filtered_research_data)} (removed {len(research_data) - len(filtered_research_data)} irrelevant documents)")
                research_data = filtered_research_data
        
        # Step 4: Generate account plan with progress updates
        self.progress_updates.append("📝 **Step 4: Synthesizing findings into Account Plan...**")
        self.progress_updates.append(f"   → Analyzing {len(research_data)} data sources about {company_name}...")
        self.progress_updates.append("   → Extracting key insights, opportunities, and strategic recommendations...")
        self.progress_updates.append("   → Generating comprehensive Account Plan sections...")
        self.progress_updates.append("   → Creating company overview, market analysis, SWOT, and recommendations...")
        
        logger.info(f"Starting account plan generation for {company_name} with {len(research_data)} research data items")
        account_plan = await self._generate_account_plan(company_name, research_data, session_id)
        
        if not account_plan:
            logger.error("Account plan generation returned None or empty - this should not happen")
            account_plan = self._get_empty_account_plan()
        
        self.session_memory.set_account_plan(session_id, account_plan)
        self.progress_updates.append("✅ **Account Plan generated successfully!**")
        
        # Log account plan details for debugging
        logger.info(f"Account plan generated - keys: {list(account_plan.keys()) if account_plan else 'None'}")
        logger.info(f"Account plan sections: {list(account_plan.keys()) if account_plan else 'None'}")
        logger.info(f"Company name in session: {self.session_memory.get_session(session_id).get('company_name') if self.session_memory.get_session(session_id) else 'None'}")
        
        # Step 5: Final response with conversational tone
        uploaded_count = sum(1 for d in research_data if d.get('source_type') == 'uploaded_document')
        web_count = len(research_data) - uploaded_count
        
        response_text = f"""
**Research Complete! 🎉**

I've finished my comprehensive research on **{company_name}** and generated a detailed Account Plan for you.

**What I Found:**
- 📄 Analyzed **{len(research_data)} sources** ({uploaded_count} uploaded documents, {web_count} web sources)
- 🔍 Extracted key business insights, market opportunities, and strategic recommendations
- 📊 Generated a complete Account Plan with all sections:
  - Company Overview
  - Market Summary
  - Key Insights
  - Pain Points & Opportunities
  - Competitor Analysis
  - SWOT Analysis
  - Strategic Recommendations
  - Executive Summary

**Next Steps:**
The Account Plan is ready for your review! You can:
- ✏️ **Edit any section** directly by clicking the edit icon
- 🔄 **Regenerate sections** if you'd like me to refine them
- 💬 **Ask me questions** about specific sections or request more research

Would you like me to explain any section in more detail, or shall we proceed with reviewing the plan?
"""
        
        self.session_memory.add_message(session_id, "assistant", response_text)
        
        result = {
            "response": response_text,
            "session_id": session_id,
            "progress_updates": self.progress_updates,
            "account_plan": account_plan,
            "agent_thinking": self._format_thinking()
        }
        
        # Log result to ensure account_plan is included
        logger.info(f"Returning result with account_plan: {bool(result.get('account_plan'))}")
        logger.info(f"Account plan in result has keys: {list(result.get('account_plan', {}).keys()) if result.get('account_plan') else 'None'}")
        
        return result
    
    async def _gather_data(self, company_name: str, session_id: str) -> List[Dict]:
        """Gather data from multiple sources - ONLY for the specified company and user"""
        research_data = []
        
        # Get user_id from session
        session = self.session_memory.get_session(session_id)
        user_id = session.get('user_id') if session else None
        
        if not user_id:
            logger.warning(f"No user_id found in session {session_id} - document filtering by user will be disabled")
        
        # 1. RAG retrieval (only if vector store is available)
        if self.vector_store:
            try:
                # Only show this message if we're actually going to search
                logger.info(f"Searching for documents: company='{company_name}', user_id={user_id}")
                
                # Check if user mentioned PDF/uploaded document - if so, prioritize uploaded docs
                session = self.session_memory.get_session(session_id)
                message_lower = ""
                if session:
                    recent_messages = session.get('messages', [])[-3:]
                    message_lower = " ".join([msg.get('content', '').lower() for msg in recent_messages])
                
                mentions_pdf = any(word in message_lower for word in ["pdf", "uploaded", "document", "file", "refer"])
                
                # If user mentions PDF, first try to get uploaded documents without strict company filtering
                if mentions_pdf:
                    logger.info("User mentioned PDF - prioritizing uploaded documents")
                    # Get uploaded documents first - search by user_id only (no company filter)
                    # This ensures we find documents even if company name extraction failed
                    if user_id:
                        # Try with user_id filter first
                        uploaded_rag_results = self.rag_pipeline.retrieve(
                            query=f"information about company business products services revenue financial",
                            n_results=100,  # Get more results
                            filter_metadata={'source_type': 'uploaded_document', 'user_id': str(user_id)}
                        )
                        logger.info(f"Found {len(uploaded_rag_results)} uploaded document chunks for user {user_id}")
                        
                        # If no results, try without user_id filter (fallback)
                        if len(uploaded_rag_results) == 0:
                            logger.warning("No uploaded documents found with user_id filter, trying without filter...")
                            uploaded_rag_results = self.rag_pipeline.retrieve(
                                query=f"information about company business products services revenue financial",
                                n_results=100,
                                filter_metadata={'source_type': 'uploaded_document'}
                            )
                            logger.info(f"Found {len(uploaded_rag_results)} uploaded document chunks (no user filter)")
                    else:
                        # No user_id, just search for uploaded documents
                        uploaded_rag_results = self.rag_pipeline.retrieve(
                            query=f"information about company business products services revenue financial",
                            n_results=100,
                            filter_metadata={'source_type': 'uploaded_document'}
                        )
                        logger.info(f"Found {len(uploaded_rag_results)} uploaded document chunks (no user_id)")
                    
                    # If we found uploaded documents, use them and extract company name from them if needed
                    if uploaded_rag_results:
                        # Extract company name from uploaded documents if current one seems wrong
                        sample_text = " ".join([r.get('text', '')[:500] for r in uploaded_rag_results[:5]])
                        if sample_text:
                            # Try to find actual company name in uploaded docs
                            entities = self.entity_extractor.extract_entities(sample_text)
                            doc_company_name = entities.get('company_name')
                            if doc_company_name and doc_company_name.lower() != company_name.lower():
                                logger.info(f"Found company name '{doc_company_name}' in uploaded PDF, updating from '{company_name}'")
                                company_name = doc_company_name
                                self.session_memory.set_company_name(session_id, company_name)
                        
                        # Use uploaded documents as primary source
                        rag_results = uploaded_rag_results
                    else:
                        # No uploaded docs found, do regular search
                        rag_results = self.rag_pipeline.retrieve_for_company(
                            company_name=company_name,
                            query=f"information about {company_name} company business products services",
                            n_results=30,
                            user_id=user_id,
                            filter_by_company=False  # Less strict when looking for uploaded docs
                        )
                else:
                    # Regular search with company filtering
                    rag_results = self.rag_pipeline.retrieve_for_company(
                        company_name=company_name,
                        query=f"information about {company_name} company business products services",
                        n_results=30,
                        user_id=user_id,
                        filter_by_company=True  # Enable strict filtering
                    )
                
                logger.info(f"Vector store search returned {len(rag_results)} results for {company_name} (user_id={user_id})")
                
                # Additional validation: ensure metadata matches
                relevant_docs = []
                seen_texts = set()
                
                for result in rag_results:
                    metadata = result.get('metadata', {})
                    text = result.get('text', '').strip()
                    
                    # Skip empty or very short texts
                    if not text or len(text) < 10:
                        continue
                    
                    # CRITICAL: Verify metadata matches (double-check filtering)
                    doc_user_id = metadata.get('user_id')
                    doc_company_name = metadata.get('company_name', '').strip()
                    
                    # If user_id is available, enforce strict matching
                    if user_id and doc_user_id:
                        if str(doc_user_id) != str(user_id):
                            logger.debug(f"Skipping doc - user_id mismatch: {doc_user_id} != {user_id}")
                            continue
                    
                    # Verify company name matches (case-insensitive)
                    # BUT: If this is an uploaded document, be more lenient (company name might not be set in metadata)
                    is_uploaded_doc = metadata.get('source_type') == 'uploaded_document'
                    if doc_company_name and doc_company_name.lower() != company_name.lower():
                        if is_uploaded_doc:
                            # For uploaded docs, check if company name appears in the text itself
                            text_lower = text.lower()
                            if company_name.lower() in text_lower:
                                logger.debug(f"Uploaded doc has different metadata company '{doc_company_name}' but text contains '{company_name}' - including it")
                                # Include it - the text is what matters
                            else:
                                logger.debug(f"Skipping uploaded doc - company mismatch: '{doc_company_name}' != '{company_name}' and not in text")
                                continue
                        else:
                            logger.debug(f"Skipping doc - company mismatch: '{doc_company_name}' != '{company_name}'")
                            continue
                    elif is_uploaded_doc and not doc_company_name:
                        # Uploaded doc without company name in metadata - check if text contains company name
                        text_lower = text.lower()
                        if company_name.lower() not in text_lower:
                            logger.debug(f"Uploaded doc has no company metadata and text doesn't contain '{company_name}' - skipping")
                            continue
                    
                    # Avoid duplicates
                    text_key = text[:100]
                    if text_key not in seen_texts:
                        seen_texts.add(text_key)
                        relevant_docs.append(result)
                        logger.debug(f"✅ Added relevant doc: {metadata.get('source_file', 'unknown')} (company={doc_company_name}, user={doc_user_id})")
                
                logger.info(f"After validation: {len(relevant_docs)} relevant documents for {company_name}")
                
                # Only show progress messages if documents were actually found
                if relevant_docs:
                    total_chars = sum(len(r.get('text', '')) for r in relevant_docs)
                    logger.info(f"✅ Found {len(relevant_docs)} relevant document chunks for {company_name}, total {total_chars} characters")
                    self.progress_updates.append(f"  ✅ Found {len(relevant_docs)} document sections about {company_name} ({total_chars:,} characters)")
                else:
                    logger.info(f"ℹ️ No documents found for {company_name} - will use web search only")
                    # Don't show warning message - just silently use web search
                
                research_data.extend(relevant_docs)
            except Exception as e:
                logger.error(f"RAG retrieval failed: {e}", exc_info=True)
                logger.warning("Continuing without document data")
                # Don't show error to user unless it's critical
        else:
            logger.warning("Vector store not available - skipping RAG retrieval")
        
        # 2. Web search (if enabled) - Enhanced with better queries
        if self.web_search.enabled:
            logger.info(f"Web search enabled: {self.web_search.enabled}, SERPER_API_KEY: {'set' if self.web_search.serper_api_key else 'NOT SET'}")
            self.progress_updates.append("  → **Searching public web sources for latest information...**")
            
            # Search with multiple queries for comprehensive data
            search_queries = [
                None,  # Basic search (company name only)
                "company overview business",
                "products services market position",
                "revenue financial information"
            ]
            
            all_web_results = []
            seen_urls = set()
            
            for query_topic in search_queries[:3]:  # Use first 3 queries
                logger.info(f"Searching web for: {company_name} {query_topic or ''}")
                web_results = self.web_search.search_company(company_name, query_topic)
                logger.info(f"Web search returned {len(web_results)} results for query: {company_name} {query_topic or ''}")
                for r in web_results:
                    url = r.get('url', '')
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        # Use full content if available, otherwise use snippet
                        text_content = r.get('full_content') or r.get('snippet', '')
                        if text_content and len(text_content.strip()) > 50:  # Only substantial content
                            # Additional aggressive cleaning
                            text_content = re.sub(r'%[0-9A-Fa-f]{2,}', '', text_content)
                            text_content = re.sub(r'\b(rut|utm_|ref|uddg)=[a-zA-Z0-9]+', '', text_content, flags=re.IGNORECASE)
                            text_content = re.sub(r'WEB SOURCE:\s*', '', text_content, flags=re.IGNORECASE)
                            text_content = re.sub(r'//duckduckgo\.', '', text_content, flags=re.IGNORECASE)
                            text_content = re.sub(r'https?://[^\s]+', '', text_content)
                            text_content = re.sub(r'//[^\s]+', '', text_content)
                            
                            if text_content.strip() and len(text_content.strip()) > 50:
                                research_data.append({
                                    'text': text_content.strip(),
                                    'metadata': {
                                        'title': r.get('title', ''),
                                        'url': url,
                                        'has_full_content': bool(r.get('full_content'))
                                    },
                                    'source_type': 'web_search',
                                    'source': r.get('title', url)
                                })
                                all_web_results.append(r)
            
            if all_web_results:
                full_content_count = sum(1 for r in all_web_results if r.get('full_content'))
                self.progress_updates.append(f"  ✅ Found {len(all_web_results)} web sources ({full_content_count} with full content)")
                logger.info(f"✅ Total web sources found: {len(all_web_results)}")
            else:
                logger.warning(f"⚠️ No web sources found for {company_name}. Check SERPER_API_KEY in .env file.")
                self.progress_updates.append(f"  ⚠️ No web sources found - check SERPER_API_KEY configuration")
        else:
            logger.warning("Web search is DISABLED. Set ENABLE_WEB_SEARCH=true in .env to enable.")
            self.progress_updates.append("  ⚠️ Web search is disabled - set ENABLE_WEB_SEARCH=true to enable")
        
        # Store in memory
        for data in research_data:
            self.session_memory.add_research_data(session_id, data)
        
        return research_data
    
    def _detect_conflicts(self, research_data: List[Dict]) -> List[Dict]:
        """Detect conflicts in research data"""
        if len(research_data) < 2:
            return []
        
        conflicts = self.conflict_detector.detect_conflicts(research_data)
        return conflicts
    
    async def _generate_account_plan(
        self,
        company_name: str,
        research_data: List[Dict],
        session_id: str
    ) -> Dict[str, Any]:
        """Generate account plan using LLM (Gemini Pro)"""
        logger.info(f"Generating account plan for {company_name} with {len(research_data)} research data sources")
        
        # Prioritize uploaded documents - they are most important!
        uploaded_docs = [d for d in research_data if d.get('source_type') == 'uploaded_document']
        web_docs = [d for d in research_data if d.get('source_type') != 'uploaded_document']
        
        logger.info(f"Research data breakdown: {len(uploaded_docs)} uploaded docs, {len(web_docs)} web sources")
        
        # Prepare context - prioritize uploaded documents, then add web sources
        # Use MORE context for better, deeper insights
        # CRITICAL: Only include documents that mention the company name
        context_parts = []
        company_name_lower = company_name.lower()
        company_keywords = [company_name_lower]
        if ' ' in company_name:
            company_keywords.append(company_name_lower.replace(' ', ''))
            company_keywords.append(company_name_lower.split()[0])
        
        # First, add uploaded documents that are relevant to the company
        relevant_uploaded_docs = []
        for d in uploaded_docs:
            text = d.get('text', '').strip().lower()
            # Only include if document mentions the company
            if any(keyword in text for keyword in company_keywords):
                relevant_uploaded_docs.append(d)
        
        logger.info(f"Filtered uploaded docs: {len(uploaded_docs)} -> {len(relevant_uploaded_docs)} relevant to {company_name}")
        
        for d in relevant_uploaded_docs[:50]:  # Get up to 50 relevant uploaded doc chunks
            text = d.get('text', '').strip()
            if not text or len(text) < 20:  # Skip empty or very short chunks
                continue
            source_type = d.get('source_type', 'unknown')
            source = d.get('source', '') or d.get('metadata', {}).get('source_file', 'uploaded document')
            
            # Clean text - remove chart artifacts and formatting issues
            lines = text.split('\n')
            cleaned_lines = []
            for line in lines:
                line = line.strip()
                # Skip chart data lines (mostly numbers)
                if re.match(r'^[\d\s\.\%]+$', line) and len(line) > 5:
                    continue
                # Skip very short numeric lines
                if len(line) < 3 and line.isdigit():
                    continue
                if line:  # Only add non-empty lines
                    cleaned_lines.append(line)
            
            cleaned_text = ' '.join(cleaned_lines)
            # For uploaded docs, use MORE characters (2000) since they're most important and we want deep insights
            if cleaned_text and len(cleaned_text) > 20:
                context_parts.append(f"UPLOADED DOCUMENT ABOUT {company_name.upper()}: {source}\n{cleaned_text[:2000]}")
                logger.debug(f"Added relevant uploaded doc chunk: {len(cleaned_text)} chars from {source}")
        
        # Then add web sources (less priority, but still useful)
        for d in web_docs[:15]:  # Get more web sources for comprehensive data
            text = d.get('text', '').strip()
            if not text or len(text) < 20:
                continue
            source_type = d.get('source_type', 'unknown')
            source = d.get('source', '') or d.get('metadata', {}).get('url', 'web source')
            
            # AGGRESSIVE text cleaning for web sources
            # Remove URL fragments and encoded characters
            text = re.sub(r'%[0-9A-Fa-f]{2,}', '', text)  # Remove URL encoding (more aggressive)
            text = re.sub(r'https?://[^\s]+', '', text)  # Remove URLs
            text = re.sub(r'www\.[^\s]+', '', text)  # Remove www URLs
            text = re.sub(r'//[^\s]+', '', text)  # Remove protocol-relative URLs
            text = re.sub(r'[a-zA-Z0-9]+\.(io|com|org|net|edu|gov)[^\s]*', '', text)  # Remove domain patterns
            text = re.sub(r'\b(rut|utm_|ref|source|campaign|medium|term|content|uddg)=[a-zA-Z0-9]+', '', text, flags=re.IGNORECASE)  # Remove tracking params
            text = re.sub(r'&[a-zA-Z0-9_]+=[a-zA-Z0-9]+', '', text)  # Remove query parameters
            text = re.sub(r'\?[^\s]+', '', text)  # Remove query strings
            text = re.sub(r'\b[0-9a-f]{32,}\b', '', text, flags=re.IGNORECASE)  # Remove hex tracking IDs
            text = re.sub(r'WEB SOURCE:\s*', '', text, flags=re.IGNORECASE)  # Remove WEB SOURCE labels
            text = re.sub(r'//duckduckgo\.', '', text, flags=re.IGNORECASE)  # Remove DuckDuckGo references
            
            # AGGRESSIVE text cleaning
            lines = text.split('\n')
            cleaned_lines = []
            for line in lines:
                line = line.strip()
                # Skip lines that are mostly URL fragments or encoded data
                if re.match(r'^[\d\s\.\%\&]+$', line) and len(line) > 5:
                    continue
                if len(line) < 3 and (line.isdigit() or '%' in line):
                    continue
                # Skip lines that look like URL fragments (more aggressive)
                if re.search(r'%[0-9a-f]{2}', line, re.IGNORECASE):
                    continue  # Skip any line with URL encoding
                if re.search(r'rut=[0-9a-f]+', line, re.IGNORECASE):
                    continue  # Skip lines with tracking parameters
                if re.search(r'\.(io|com|org|net)/', line) and len(line) < 100:
                    continue  # Skip short lines that are just URLs
                if 'WEB SOURCE:' in line.upper():
                    continue  # Skip lines with WEB SOURCE labels
                if '//duckduckgo' in line.lower():
                    continue  # Skip DuckDuckGo references
                if line and len(line) > 20:  # Only keep substantial lines (increased threshold)
                    # Additional cleaning on the line itself
                    line = re.sub(r'%[0-9A-Fa-f]{2,}', '', line)
                    line = re.sub(r'\b(rut|utm_|ref)=[a-zA-Z0-9]+', '', line, flags=re.IGNORECASE)
                    line = re.sub(r'[a-zA-Z0-9]+\.(io|com|org|net)[^\s]*', '', line)
                    cleaned_lines.append(line)
            
            cleaned_text = ' '.join(cleaned_lines)
            # Remove multiple spaces and clean up
            cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
            # Remove any remaining URL fragments
            cleaned_text = re.sub(r'%[0-9A-Fa-f]{2,}', '', cleaned_text)
            cleaned_text = re.sub(r'\b(rut|utm_|ref)=[a-zA-Z0-9]+', '', cleaned_text, flags=re.IGNORECASE)
            
            if cleaned_text and len(cleaned_text) > 50:  # Only add if substantial content
                context_parts.append(f"WEB SOURCE: {source}\n{cleaned_text[:1000]}")
        
        context = "\n\n---\n\n".join(context_parts)
        
        # FINAL AGGRESSIVE CLEANING of entire context before sending to LLM
        context = re.sub(r'%[0-9A-Fa-f]{2,}', '', context)
        context = re.sub(r'\b(rut|utm_|ref|source|uddg)=[a-zA-Z0-9]+', '', context, flags=re.IGNORECASE)
        context = re.sub(r'WEB SOURCE:\s*', '', context, flags=re.IGNORECASE)
        context = re.sub(r'//duckduckgo\.', '', context, flags=re.IGNORECASE)
        context = re.sub(r'https?://[^\s]+', '', context)
        context = re.sub(r'//[^\s]+', '', context)
        context = re.sub(r'\b[0-9a-f]{32,}\b', '', context, flags=re.IGNORECASE)
        context = re.sub(r'\s+', ' ', context).strip()
        
        logger.info(f"Prepared context with {len(context_parts)} sources, total {len(context)} characters (after cleaning)")
        
        if not context or len(context.strip()) < 100:
            logger.warning(f"⚠️ Context is too short ({len(context)} chars) - will use LLM general knowledge")
            logger.warning(f"Research data breakdown: {len(uploaded_docs)} uploaded, {len(web_docs)} web")
            logger.warning(f"Total research_data items: {len(research_data)}")
            if len(research_data) == 0:
                logger.warning("⚠️ NO RESEARCH DATA AVAILABLE - will use LLM's general knowledge about the company")
                self.progress_updates.append("  ℹ️ No uploaded documents found - using general knowledge about the company")
                # Add a note to context that we're using general knowledge
                context = f"NOTE: No specific research documents were found for {company_name}. Please use your general knowledge about this well-known company to provide a comprehensive account plan. Include well-known facts about the company's history, products, market position, and business model."
            else:
                logger.warning("⚠️ Research data exists but context is empty - text extraction may have failed")
                for i, data in enumerate(research_data[:5]):
                    text_len = len(data.get('text', ''))
                    logger.warning(f"  Research data {i+1}: source_type={data.get('source_type')}, text_length={text_len}")
                self.progress_updates.append("  ⚠️ Warning: Limited research data available - some sections may be less detailed")
        
        # Extract entities
        all_text = " ".join([d.get('text', '') for d in research_data])
        entities = self.entity_extractor.extract_entities(all_text)
        
        # Collect sources for Account Plan
        sources = []
        for data in research_data:
            source_type = data.get('source_type', 'website')
            url = data.get('metadata', {}).get('url', '') or data.get('source', '')
            if not url and source_type == 'uploaded_document':
                url = data.get('metadata', {}).get('source_file', 'uploaded_document')
            
            # Map source types
            if source_type == 'uploaded_document':
                type_str = 'pdf'
            elif 'news' in url.lower() or 'article' in url.lower():
                type_str = 'news'
            else:
                type_str = 'website'
            
            sources.append({
                "url": url,
                "type": type_str,
                "extracted_at": datetime.utcnow().isoformat()
            })
        
        try:
            # Use Account Plan Generator for exact JSON format
            if isinstance(self.llm_engine, GeminiEngine):
                engine_name = "Gemini Pro"
                timeout_seconds = 300.0  # Increased to 5 minutes for complete generation
                logger.info(f"Generating Account Plan for {company_name} using {engine_name} ({timeout_seconds}s timeout)")
                logger.info(f"Context length: {len(context)} chars, {len(context_parts)} sources")
                if len(context) < 100:
                    logger.error(f"⚠️ CRITICAL: Context is too short ({len(context)} chars) - research_data may be empty!")
                    logger.error(f"Research data: {len(research_data)} items")
                    for i, data in enumerate(research_data[:3]):
                        logger.error(f"  Data {i+1}: source_type={data.get('source_type')}, text_length={len(data.get('text', ''))}")
                try:
                    import asyncio
                    
                    # Check if event loop is closing (shutdown scenario)
                    # Note: is_closing() is not available on all event loop types (e.g., Windows SelectorEventLoop)
                    try:
                        loop = asyncio.get_running_loop()
                        # Check if method exists before calling (Windows compatibility)
                        if hasattr(loop, 'is_closing') and loop.is_closing():
                            logger.warning("⚠️ Event loop is closing, using fallback plan")
                            return self._generate_fallback_plan_fast(company_name, research_data)
                    except RuntimeError:
                        # No running loop - might be during shutdown
                        logger.warning("⚠️ No running event loop, using fallback plan")
                        return self._generate_fallback_plan_fast(company_name, research_data)
                    except AttributeError:
                        # is_closing() not available on this event loop type (e.g., Windows SelectorEventLoop)
                        # This is fine - just continue with normal execution
                        logger.debug("Event loop doesn't support is_closing() check - continuing normally")
                    
                    # Use Account Plan Generator with exact JSON format
                    account_plan = await asyncio.wait_for(
                        asyncio.to_thread(
                            self.account_plan_generator.generate_account_plan,
                            company_name=company_name,
                            research_context=context,
                            entities=entities,
                            sources=sources
                        ),
                        timeout=timeout_seconds
                    )
                    logger.info("✅ Account Plan generated successfully in exact JSON format")
                    return account_plan
                except asyncio.TimeoutError:
                    logger.warning(f"⚠️ Account plan generation timed out after {timeout_seconds}s - using instant fallback")
                    return self._generate_fallback_plan_fast(company_name, research_data)
                except RuntimeError as e:
                    error_msg = str(e).lower()
                    if "cannot schedule new futures" in error_msg or "interpreter shutdown" in error_msg or "event loop is closed" in error_msg:
                        logger.warning("⚠️ Server is reloading/shutting down, using fallback plan")
                        return self._generate_fallback_plan_fast(company_name, research_data)
                    raise
                except (ValueError, TimeoutError) as e:
                    error_msg = str(e)
                    logger.error(f"{engine_name} API error: {error_msg}")
                    logger.warning("Using instant fallback plan")
                    return self._generate_fallback_plan_fast(company_name, research_data)
                except Exception as e:
                    error_msg = str(e)
                    error_lower = error_msg.lower()
                    # Check for shutdown-related errors
                    if any(phrase in error_lower for phrase in ["cannot schedule", "interpreter shutdown", "event loop", "shutdown"]):
                        logger.warning("⚠️ Server shutdown detected, using fallback plan")
                        return self._generate_fallback_plan_fast(company_name, research_data)
                    logger.error(f"{engine_name} unexpected error: {error_msg}")
                    logger.warning("Using instant fallback plan")
                    return self._generate_fallback_plan_fast(company_name, research_data)
            else:
                raise ValueError("Only Gemini engine is supported. Please configure GEMINI_API_KEY.")
        
        except Exception as e:
            logger.error(f"Error generating account plan: {e}", exc_info=True)
            # Return template with error info
            plan = self._get_empty_account_plan()
            plan['company_overview'] = f"Error: {str(e)}. Please check backend logs for details."
            return plan
    
    def _get_empty_account_plan(self) -> Dict[str, Any]:
        """Return empty account plan template"""
        return {
            "company_overview": "",
            "market_summary": "",
            "key_insights": "",
            "pain_points": "",
            "opportunities": "",
            "competitor_analysis": "",
            "swot": {
                "strengths": "",
                "weaknesses": "",
                "opportunities": "",
                "threats": ""
            },
            "strategic_recommendations": "",
            "final_account_plan": ""
        }
    
    def _generate_fallback_plan_fast(self, company_name: str, research_data: List[Dict]) -> Dict[str, Any]:
        """Generate fallback plan using LLM with research data - ensures quality output"""
        logger.info("Generating fallback Account Plan using LLM with research data")
        
        if not research_data:
            logger.error("⚠️ CRITICAL: No research data available for fallback plan!")
            return self._get_empty_account_plan()
        
        # Extract and clean text from research data
        all_text = " ".join([d.get('text', '') for d in research_data if d.get('text')])
        logger.info(f"Fallback: Extracted {len(all_text)} characters from {len(research_data)} research items")
        
        if len(all_text) < 100:
            logger.error(f"⚠️ CRITICAL: Extracted text is too short ({len(all_text)} chars)")
            return self._get_empty_account_plan()
        
        # Clean text aggressively
        import re
        all_text = re.sub(r'!\[\]\([^\)]*\)', '', all_text)
        all_text = re.sub(r'!\[.*?\]\(.*?\)', '', all_text)
        all_text = re.sub(r'\[\]', '', all_text)
        all_text = re.sub(r'%[0-9A-Fa-f]{2,}', '', all_text)
        all_text = re.sub(r'\s+', ' ', all_text).strip()
        
        # Extract entities
        entities = self.entity_extractor.extract_entities(all_text)
        logger.info(f"Fallback: Extracted {len(entities)} entities")
        
        # Use Account Plan Generator with shorter context to avoid MAX_TOKENS
        try:
            # Limit context to prevent MAX_TOKENS
            context_limit = 3000  # Smaller context for fallback
            research_context = all_text[:context_limit]
            
            # Collect sources
            sources = []
            for data in research_data[:5]:  # Limit to 5 sources
                source_type = data.get('source_type', 'website')
                url = data.get('metadata', {}).get('url', '') or data.get('source', '')
                if not url and source_type == 'uploaded_document':
                    url = data.get('metadata', {}).get('source_file', 'uploaded_document')
                
                type_str = 'pdf' if source_type == 'uploaded_document' else ('news' if 'news' in url.lower() else 'website')
                sources.append({
                    "url": url,
                    "type": type_str,
                    "extracted_at": datetime.utcnow().isoformat()
                })
            
            # Generate using Account Plan Generator with shorter timeout
            logger.info("Generating fallback plan using Account Plan Generator...")
            account_plan = self.account_plan_generator.generate_account_plan(
                company_name=company_name,
                research_context=research_context,
                entities=entities,
                sources=sources
            )
            
            # Ensure all required fields exist
            required_fields = ['company_overview', 'market_summary', 'key_insights', 'pain_points', 
                             'opportunities', 'products_services', 'competitor_analysis', 
                             'strategic_recommendations', 'final_account_plan']
            for field in required_fields:
                if field not in account_plan or not account_plan.get(field):
                    account_plan[field] = f"{field.replace('_', ' ').title()} for {company_name} based on research data."
            
            # Ensure SWOT exists
            if 'swot' not in account_plan or not isinstance(account_plan.get('swot'), dict):
                account_plan['swot'] = {
                    "strengths": "Key strengths identified from research.",
                    "weaknesses": "Areas for improvement noted.",
                    "opportunities": "Growth opportunities available.",
                    "threats": "Potential threats to consider."
                }
            
            logger.info("✅ Fallback plan generated successfully using LLM")
            return account_plan
            
        except Exception as e:
            logger.error(f"Error generating fallback plan with LLM: {e}", exc_info=True)
            # Ultimate fallback - return basic structure
            return {
                "company_name": company_name,
                "company_overview": f"{company_name} is a company operating in the market. Based on available research data, the company has established a presence in its industry.",
                "market_summary": f"Market analysis for {company_name} based on research data.",
                "key_insights": "Key insights extracted from research data. Further analysis recommended.",
                "pain_points": "Pain points and challenges identified from research.",
                "opportunities": "Growth opportunities and strategic openings available.",
                "products_services": f"{company_name} offers a range of products and services in its industry.",
                "competitor_analysis": "Competitive landscape analysis based on available data.",
                "swot": {
                    "strengths": "Key strengths identified from research.",
                    "weaknesses": "Areas for improvement noted.",
                    "opportunities": "Growth opportunities available.",
                    "threats": "Potential threats to consider."
                },
                "strategic_recommendations": "Strategic recommendations based on analysis. Further research recommended for detailed planning.",
                "final_account_plan": f"Executive summary for {company_name} Account Plan based on available research data.",
                "sources": [],
                "last_updated": datetime.utcnow().isoformat()
            }
    
    async def _update_section_workflow(
        self,
        message: str,
        session_id: str
    ) -> Dict[str, Any]:
        """Handle section update requests with conversational feedback - supports multiple commands"""
        session = self.session_memory.get_session(session_id)
        if not session or not session.get('account_plan'):
            return {
                "response": "I don't have an account plan yet. Please start by asking me to research a company first, and I'll generate a comprehensive Account Plan for you.",
                "session_id": session_id,
                "questions": ["Would you like me to research a company now?"]
            }
        
        message_lower = message.lower()
        account_plan = session.get('account_plan', {}).copy() if session.get('account_plan') else {}
        company_name = session.get('company_name', 'the company')
        research_data = session.get('research_data', [])
        
        # Check for "regenerate account plan" or "regenerate the account plan again"
        if any(phrase in message_lower for phrase in ["regenerate account plan", "regenerate the account plan", "regenerate plan", "regenerate the plan again"]):
            logger.info(f"User requested to regenerate entire account plan for {company_name}")
            self.progress_updates = []
            self.progress_updates.append("🔄 Regenerating entire Account Plan...")
            
            # Regenerate the entire account plan
            try:
                new_account_plan = await self._generate_account_plan(company_name, research_data, session_id)
                self.session_memory.set_account_plan(session_id, new_account_plan)
                self.progress_updates.append("✅ Account Plan regenerated successfully!")
                
                return {
                    "response": "**Done! ✅**\n\nI've regenerated your entire Account Plan with fresh insights based on the latest research data. All sections have been updated.\n\nYour account plan has been regenerated with all changes.",
                    "session_id": session_id,
                    "account_plan": new_account_plan,
                    "progress_updates": self.progress_updates
                }
            except Exception as e:
                logger.error(f"Error regenerating account plan: {e}", exc_info=True)
                return {
                    "response": f"I encountered an error while regenerating the account plan: {str(e)}\n\nPlease try again.",
                    "session_id": session_id,
                    "account_plan": account_plan
                }
        
        # Track all operations to perform
        operations = []
        response_parts = []
        
        # Check for multiple commands (split by "and", "then", ",")
        import re
        
        # First, check if message contains multiple commands
        has_multiple = any(sep in message_lower for sep in [" and ", " then ", ", ", " & "])
        
        if has_multiple:
            # Split message into potential commands
            command_separators = [r'\s+and\s+', r'\s+then\s+', r',\s+', r'\s+&\s+']
            commands = [message_lower]
            for sep in command_separators:
                new_commands = []
                for cmd in commands:
                    new_commands.extend(re.split(sep, cmd))
                commands = new_commands
            
            # Remove empty commands
            commands = [c.strip() for c in commands if c.strip()]
        else:
            # Single command - process the whole message
            commands = [message_lower]
        
        # Process each command
        for cmd in commands:
            cmd = cmd.strip()
            if not cmd:
                continue
            
            # Check for update/regenerate section
            if any(word in cmd for word in ["update", "regenerate", "refresh", "rewrite"]):
                section = self._extract_section_name(cmd)
                if section:
                    # Check if this operation is already in the list
                    if ("update", section) not in operations:
                        operations.append(("update", section))
                else:
                    # Try to extract section name from the command more aggressively
                    # Look for patterns like "update key insights" or "regenerate company overview"
                    section_patterns = {
                        "key insights": "key_insights",
                        "company overview": "company_overview",
                        "market summary": "market_summary",
                        "pain points": "pain_points",
                        "opportunities": "opportunities",
                        "competitor": "competitor_analysis",
                        "swot analysis": "swot",
                        "swot": "swot",
                        "strategic": "strategic_recommendations"
                    }
                    for pattern, section_key in section_patterns.items():
                        if pattern in cmd:
                            if ("update", section_key) not in operations:
                                operations.append(("update", section_key))
                            break
            
            # Check for add field
            if "add" in cmd:
                # Extract field names
                add_part = cmd.split("add", 1)[1] if "add" in cmd else ""
                field_keywords = {
                    "ceo": "ceo", "cto": "cto", "revenue": "revenue",
                    "founder": "founder", "headquarters": "headquarters",
                    "employees": "employees", "headcount": "headcount",
                    "employee count": "employee_count"
                }
                for keyword, field_key in field_keywords.items():
                    if keyword in add_part:
                        if ("add", field_key) not in operations:
                            operations.append(("add", field_key))
                        break
                # Also check for "add field X" pattern
                match = re.search(r'add\s+(?:field|section)\s+["\']?([^"\']+)["\']?', cmd)
                if match:
                    field_name = match.group(1).strip().replace(' ', '_').lower()
                    if field_name not in [op[1] for op in operations if op[0] == "add"]:
                        operations.append(("add", field_name))
            
            # Check for remove/delete field
            if any(word in cmd for word in ["remove", "delete", "drop"]):
                remove_part = cmd.split("remove", 1)[1] if "remove" in cmd else (cmd.split("delete", 1)[1] if "delete" in cmd else "")
                field_keywords = {
                    "key insights": "key_insights", "company overview": "company_overview",
                    "market summary": "market_summary", "pain points": "pain_points",
                    "opportunities": "opportunities", "competitor": "competitor_analysis",
                    "swot": "swot", "strategic": "strategic_recommendations",
                    "revenue": "revenue", "ceo": "ceo", "cto": "cto"
                }
                for keyword, field_key in field_keywords.items():
                    if keyword in remove_part:
                        if ("remove", field_key) not in operations:
                            operations.append(("remove", field_key))
                        break
        
        # If no operations detected from split, try original message
        if not operations:
            # Fall back to original single-command logic
            pass
        else:
            # Execute all operations
            logger.info(f"Detected {len(operations)} operations: {operations}")
            self.progress_updates = []
            
            for op_type, op_value in operations:
                if op_type == "update":
                    # Update section
                    section = op_value
                    section_display = section.replace('_', ' ').title()
                    self.progress_updates.append(f"🔄 Updating {section_display}...")
                    
                    try:
                        updated_section = await self._regenerate_section(
                            company_name, section, research_data, account_plan
                        )
                        
                        # Handle nested sections (e.g., swot.strengths) or regular sections
                        if '.' in section:
                            parts = section.split('.')
                            if len(parts) == 2:
                                if parts[0] not in account_plan:
                                    account_plan[parts[0]] = {}
                                account_plan[parts[0]][parts[1]] = updated_section
                        else:
                            # For SWOT, it should be a dict with strengths, weaknesses, opportunities, threats
                            if section == "swot":
                                # Ensure updated_section is a dict
                                if isinstance(updated_section, dict):
                                    account_plan[section] = updated_section
                                else:
                                    # If it's a string, try to parse it or create a dict structure
                                    logger.warning(f"SWOT section returned non-dict: {type(updated_section)}")
                                    account_plan[section] = {
                                        "strengths": str(updated_section) if updated_section else "No content yet.",
                                        "weaknesses": "No content yet.",
                                        "opportunities": "No content yet.",
                                        "threats": "No content yet."
                                    }
                            else:
                                account_plan[section] = updated_section
                        
                        response_parts.append(f"✅ Updated **{section_display}**")
                        logger.info(f"Updated section: {section}")
                    except Exception as e:
                        logger.error(f"Error updating section {section}: {e}", exc_info=True)
                        response_parts.append(f"❌ Failed to update {section_display}: {str(e)}")
                
                elif op_type == "add":
                    # Add field
                    field_key = op_value
                    if field_key not in account_plan:
                        self.progress_updates.append(f"➕ Adding {field_key.replace('_', ' ').title()}...")
                        
                        try:
                            field_content = await self._generate_field_content(
                                company_name, field_key, research_data, session_id
                            )
                            account_plan[field_key] = field_content
                            response_parts.append(f"✅ Added **{field_key.replace('_', ' ').title()}**")
                            logger.info(f"Added field: {field_key}")
                        except Exception as e:
                            logger.error(f"Error adding field {field_key}: {e}", exc_info=True)
                            response_parts.append(f"❌ Failed to add {field_key.replace('_', ' ').title()}: {str(e)}")
                    else:
                        response_parts.append(f"ℹ️ **{field_key.replace('_', ' ').title()}** already exists")
                
                elif op_type == "remove":
                    # Remove field
                    field_key = op_value
                    if field_key in account_plan:
                        del account_plan[field_key]
                        response_parts.append(f"✅ Removed **{field_key.replace('_', ' ').title()}**")
                        logger.info(f"Removed field: {field_key}")
                    else:
                        response_parts.append(f"ℹ️ **{field_key.replace('_', ' ').title()}** not found")
            
            # Save updated plan AFTER all operations are complete
            self.session_memory.set_account_plan(session_id, account_plan)
            logger.info(f"Account plan updated with {len(operations)} operations. Plan keys: {list(account_plan.keys())}")
            
            # Return response
            if response_parts:
                return {
                    "response": f"**Done! ✅**\n\n" + "\n".join(response_parts) + "\n\nYour account plan has been updated with all changes.",
                    "session_id": session_id,
                    "account_plan": account_plan,  # Include updated plan so it gets saved
                    "progress_updates": self.progress_updates
                }
        
        # If we get here, no operations were detected from split - use original single-command logic
        message_lower = message.lower()
        
        # Handle add field command - improved pattern matching
        add_patterns = [
            r'add\s+(?:field|section|new\s+field|new\s+section)\s+["\']?([^"\']+)["\']?',
            r'add\s+["\']?([^"\']+?)(?:\s+as\s+new\s+field|\s+field|\s+section)',
            r'include\s+["\']?([^"\']+?)(?:\s+as\s+field|\s+field|\s+section)',
            r'add\s+["\']?([^"\']+?)["\']?\s+(?:to|in|into)\s+(?:account\s+plan|plan)',
        ]
        
        # Also check for direct field mentions like "add CEO and revenue"
        direct_field_patterns = [
            r'add\s+(?:ceo|cto|revenue|founder|headquarters|employees|headcount)',
            r'add\s+(?:ceo|cto|revenue|founder|headquarters|employees|headcount)\s+and\s+([^,]+)',
        ]
        
        import re
        field_names_to_add = []
        
        # Try standard patterns first
        for pattern in add_patterns:
            matches = re.finditer(pattern, message_lower)
            for match in matches:
                field_name = match.group(1).strip()
                if field_name:
                    field_names_to_add.append(field_name)
        
        # Try direct field patterns (CEO, CTO, revenue, etc.)
        if "add" in message_lower:
            # Extract field names after "add"
            add_part = message_lower.split("add", 1)[1] if "add" in message_lower else ""
            # Look for common field names
            field_keywords = {
                "ceo": "ceo",
                "cto": "cto", 
                "revenue": "revenue",
                "founder": "founder",
                "headquarters": "headquarters",
                "employees": "employees",
                "headcount": "headcount",
                "employee count": "employee_count"
            }
            
            for keyword, field_key in field_keywords.items():
                if keyword in add_part:
                    if field_key not in [f.replace(' ', '_').lower() for f in field_names_to_add]:
                        field_names_to_add.append(field_key)
        
        # If we found fields to add, add them to EXISTING plan (not creating new one)
        if field_names_to_add:
            company_name = session.get('company_name', 'the company')
            research_data = session.get('research_data', [])
            
            # Get the EXISTING account plan (don't create a new one)
            existing_plan = account_plan.copy() if account_plan else {}
            logger.info(f"Adding {len(field_names_to_add)} field(s) to existing account plan. Current plan keys: {list(existing_plan.keys())}")
            
            self.progress_updates.append(f"✅ Adding {len(field_names_to_add)} new field(s) to existing account plan...")
            
            # Generate content for each new field and add to EXISTING plan
            for field_name in field_names_to_add:
                field_key = field_name.replace(' ', '_').lower()
                if field_key not in existing_plan:
                    self.progress_updates.append(f"   → Generating content for {field_key.replace('_', ' ').title()}...")
                    # Generate content for this specific field
                    field_content = await self._generate_field_content(company_name, field_key, research_data, session_id)
                    existing_plan[field_key] = field_content
                    logger.info(f"Added field '{field_key}' to existing plan")
                else:
                    logger.info(f"Field '{field_key}' already exists, skipping")
            
            # Update the EXISTING plan in session (not creating new one)
            self.session_memory.set_account_plan(session_id, existing_plan)
            logger.info(f"Account plan updated in session. Plan keys after adding fields: {list(existing_plan.keys())}")
            
            field_list = ", ".join([f.replace('_', ' ').title() for f in field_names_to_add])
            return {
                "response": f"✅ **Successfully added {len(field_names_to_add)} new field(s): {field_list}**\n\nI've added the new fields to your existing account plan and generated content for them. Your account plan has been updated with the new information.",
                "session_id": session_id,
                "account_plan": existing_plan,  # Include updated existing plan so it gets saved
                "progress_updates": self.progress_updates
            }
        
        # If no fields detected but "add" is mentioned
        if "add" in message_lower and ("field" in message_lower or "section" in message_lower):
            return {
                "response": "I'd be happy to add a new field! Please tell me the name of the field you'd like to add. For example: 'add CEO and revenue' or 'add field Market Trends'",
                "session_id": session_id
            }
        
        # Handle remove/delete field command - update EXISTING plan
        remove_patterns = [
            r'(?:remove|delete)\s+(?:field|section)\s+["\']?([^"\']+)["\']?',
            r'(?:remove|delete)\s+["\']?([^"\']+?)(?:\s+field|\s+section)',
        ]
        
        # Also check for direct field mentions like "delete key insights"
        direct_delete_patterns = [
            r'(?:remove|delete)\s+(?:key\s+insights|company\s+overview|market\s+summary|pain\s+points|opportunities|competitor|swot|strategic|revenue|ceo|cto)',
        ]
        
        field_names_to_remove = []
        
        # Try standard patterns first
        for pattern in remove_patterns:
            matches = re.finditer(pattern, message_lower)
            for match in matches:
                field_name = match.group(1).strip()
                if field_name:
                    field_names_to_remove.append(field_name)
        
        # Try direct field patterns
        if "remove" in message_lower or "delete" in message_lower:
            # Extract field names after "remove" or "delete"
            remove_part = message_lower.split("remove", 1)[1] if "remove" in message_lower else (message_lower.split("delete", 1)[1] if "delete" in message_lower else "")
            # Look for common field names
            field_keywords = {
                "key insights": "key_insights",
                "company overview": "company_overview",
                "market summary": "market_summary",
                "pain points": "pain_points",
                "opportunities": "opportunities",
                "competitor": "competitor_analysis",
                "swot": "swot",
                "strategic": "strategic_recommendations",
                "revenue": "revenue",
                "ceo": "ceo",
                "cto": "cto"
            }
            
            for keyword, field_key in field_keywords.items():
                if keyword in remove_part:
                    if field_key not in [f.replace(' ', '_').lower() for f in field_names_to_remove]:
                        field_names_to_remove.append(field_key)
        
        # If we found fields to remove, remove them from EXISTING plan
        if field_names_to_remove:
            # Get the EXISTING account plan (don't create a new one)
            existing_plan = account_plan.copy() if account_plan else {}
            logger.info(f"Removing {len(field_names_to_remove)} field(s) from existing account plan. Current plan keys: {list(existing_plan.keys())}")
            
            removed_fields = []
            for field_name in field_names_to_remove:
                field_key = field_name.replace(' ', '_').lower()
                if field_key in existing_plan:
                    del existing_plan[field_key]
                    removed_fields.append(field_key)
                    logger.info(f"Removed field '{field_key}' from existing plan")
                else:
                    logger.info(f"Field '{field_key}' not found in plan, skipping")
            
            if removed_fields:
                # Update the EXISTING plan in session (not creating new one)
                self.session_memory.set_account_plan(session_id, existing_plan)
                logger.info(f"Account plan updated in session. Plan keys after removing fields: {list(existing_plan.keys())}")
                
                field_list = ", ".join([f.replace('_', ' ').title() for f in removed_fields])
                return {
                    "response": f"✅ **Successfully removed {len(removed_fields)} field(s): {field_list}**\n\nThe field(s) have been removed from your existing account plan.",
                    "session_id": session_id,
                    "account_plan": existing_plan,  # Include updated existing plan so it gets saved
                    "progress_updates": [f"✅ Removed {len(removed_fields)} field(s) from existing plan"]
                }
            else:
                available_fields = ", ".join([f"**{k.replace('_', ' ').title()}**" for k in existing_plan.keys()])
                return {
                    "response": f"I couldn't find the field(s) you mentioned in your account plan. Available fields are:\n\n{available_fields}",
                    "session_id": session_id,
                    "account_plan": existing_plan
                }
        
        # If no fields detected but "remove" or "delete" is mentioned
        if ("remove" in message_lower or "delete" in message_lower) and ("field" in message_lower or "section" in message_lower):
                return {
                "response": "I'd be happy to remove a field! Please tell me which field you'd like to remove. For example: 'remove key insights' or 'delete field Market Summary'",
                    "session_id": session_id
                }
        
        # Extract section name from message
        section = self._extract_section_name(message)
        if not section:
            # Provide helpful suggestions
            available_sections = list(account_plan.keys())
            if not available_sections:
                available_sections = [
                    'company_overview', 'market_summary', 'key_insights', 
                    'pain_points', 'opportunities', 'competitor_analysis',
                    'swot', 'strategic_recommendations', 'final_account_plan'
                ]
            return {
                "response": f"Which section would you like me to update? I can help you with:\n\n" + 
                           "\n".join([f"• **{s.replace('_', ' ').title()}**" for s in available_sections[:10]]) +
                           "\n\nJust tell me which one, or say 'update [section name]'. You can also 'add field [name]' or 'remove field [name]'.",
                "session_id": session_id,
                "questions": [f"Which section would you like to update? Available: {', '.join(available_sections[:5])}..."]
            }
        
        # Show progress
        section_display_name = section.replace('_', ' ').replace('.', ' - ').title()
        self.progress_updates = []
        self.progress_updates.append(f"🔄 **Updating {section_display_name} section...**")
        self.progress_updates.append("   → Retrieving research data...")
        self.progress_updates.append("   → Regenerating section with latest insights...")
        
        # Regenerate section
        company_name = session.get('company_name', 'the company')
        research_data = session.get('research_data', [])
        
        try:
            updated_section = await self._regenerate_section(
                company_name,
                section,
                research_data,
                session.get('account_plan')
            )
            
            # Update account plan IN PLACE (not creating a new one)
            account_plan = session['account_plan'].copy() if session.get('account_plan') else {}
            
            # Ensure we're working with the existing plan structure
            if not account_plan:
                logger.warning("No existing account plan found - this should not happen in update workflow")
                account_plan = session.get('account_plan', {})
            
            logger.info(f"Updating section '{section}' in existing account plan. Current plan keys: {list(account_plan.keys())}")
            
            if '.' in section:
                # Nested section (e.g., "swot.strengths")
                parts = section.split('.')
                if len(parts) == 2:
                    if parts[0] not in account_plan:
                        account_plan[parts[0]] = {}
                    account_plan[parts[0]][parts[1]] = updated_section
                    logger.info(f"Updated nested section: {parts[0]}.{parts[1]}")
            else:
                # Update the section in the existing plan
                account_plan[section] = updated_section
                logger.info(f"Updated section: {section}")
            
            # Save updated plan back to session (this updates the existing plan, not creates new)
            self.session_memory.set_account_plan(session_id, account_plan)
            logger.info(f"Account plan updated in session. Plan keys after update: {list(account_plan.keys())}")
            
            self.progress_updates.append(f"✅ **{section_display_name} section updated successfully!**")
            
            # Return updated plan so it can be saved to database
            return {
                "response": f"**Done! ✅**\n\nI've updated the **{section_display_name}** section in your existing account plan with fresh insights based on the research data.\n\nWould you like me to update any other sections, or do you have questions about the updated content?",
                "session_id": session_id,
                "account_plan": account_plan,  # Include updated plan so it gets saved to MongoDB
                "progress_updates": self.progress_updates
            }
        except Exception as e:
            logger.error(f"Error updating section {section}: {e}", exc_info=True)
            return {
                "response": f"I encountered an error while updating the {section_display_name} section: {str(e)}\n\nPlease try again, or let me know if you'd like to edit it manually instead.",
                "session_id": session_id,
                "account_plan": session.get('account_plan')
            }
    
    async def _generate_field_content(
        self,
        company_name: str,
        field_key: str,
        research_data: List[Dict],
        session_id: str
    ) -> str:
        """Generate content for a specific field (CEO, CTO, revenue, etc.)"""
        logger.info(f"Generating content for field: {field_key} for company: {company_name}")
        
        # Prepare context from research data
        context = "\n\n".join([
            f"Source: {d.get('source_type', 'unknown')}\n{d.get('text', '')[:800]}"
            for d in research_data[:15]
        ])
        
        # Field-specific prompts
        field_prompts = {
            "ceo": f"Extract and provide information about the CEO (Chief Executive Officer) of {company_name}. Include: name, background, tenure, notable achievements, and leadership style if available.",
            "cto": f"Extract and provide information about the CTO (Chief Technology Officer) of {company_name}. Include: name, background, technology focus areas, and key initiatives if available.",
            "revenue": f"Extract and provide revenue information for {company_name}. Include: annual revenue, revenue trends, revenue sources, and financial performance if available.",
            "founder": f"Extract and provide information about the founder(s) of {company_name}. Include: name(s), background, founding story, and current role if available.",
            "headquarters": f"Extract and provide headquarters location information for {company_name}. Include: city, state/country, and any notable details about the location.",
            "employees": f"Extract and provide employee information for {company_name}. Include: total number of employees, employee count trends, and workforce composition if available.",
            "employee_count": f"Extract and provide employee count information for {company_name}. Include: total number of employees and any breakdown by department or region if available.",
            "headcount": f"Extract and provide headcount information for {company_name}. Include: total number of employees and growth trends if available."
        }
        
        # Get field-specific prompt or use generic one
        field_display = field_key.replace('_', ' ').title()
        prompt = field_prompts.get(field_key, f"Extract and provide information about {field_display} for {company_name} based on the research data.")
        
        full_prompt = f"""Based on the following research data about {company_name}, {prompt}

Research Data:
{context[:5000]}

Provide a clear, concise answer. If the information is not available in the research data, state that clearly. Format your response as a brief paragraph (2-4 sentences)."""
        
        try:
            response = self.llm_engine.generate(
                prompt=full_prompt,
                system_prompt=f"You are a senior research analyst with expertise in business intelligence and data extraction. Extract specific information about {company_name} from the provided research data with production-grade accuracy. Synthesize information strategically - don't copy raw text. Be concise, accurate, and provide strategic context when relevant.",
                temperature=0.4,  # Slightly higher for better synthesis
                max_tokens=800,  # Increased for more comprehensive extraction
                timeout=45  # Increased timeout
            )
            
            if response and response.strip():
                return response.strip()
            else:
                return f"Information about {field_display} for {company_name} is not available in the current research data."
        except Exception as e:
            logger.error(f"Error generating field content for {field_key}: {e}", exc_info=True)
            return f"Unable to generate {field_display} information at this time. Please try again or provide more research data."
    
    async def _regenerate_section(
        self,
        company_name: str,
        section: str,
        research_data: List[Dict],
        current_plan: Dict
    ) -> str:
        """Regenerate a specific section using Gemini Pro"""
        context = "\n\n".join([
            f"Source: {d.get('source_type', 'unknown')}\n{d.get('text', '')[:500]}"
            for d in research_data[:10]
        ])
        
        # Extract entities
        all_text = " ".join([d.get('text', '') for d in research_data])
        entities = self.entity_extractor.extract_entities(all_text)
        
        try:
            # Use Gemini Pro engine for section regeneration
            if isinstance(self.llm_engine, GeminiEngine):
                logger.info(f"Regenerating {section} for {company_name} using Gemini Pro")
                return self.llm_engine.regenerate_section(
                    company_name=company_name,
                    section=section,
                    research_context=context,
                    entities=entities,
                    current_plan=current_plan
                )
            else:
                raise ValueError("Only Gemini engine is supported. Please configure GEMINI_API_KEY.")
        
        except Exception as e:
            logger.error(f"Error regenerating section: {e}")
            return f"Error regenerating {section}. Please try again."
    
    async def _clarification_workflow(
        self,
        message: str,
        session_id: str
    ) -> Dict[str, Any]:
        """Handle user clarifications - continue research with existing data"""
        session = self.session_memory.get_session(session_id)
        if not session:
            return {
                "response": "I don't have any previous research context. Please start by asking me to research a company.",
                "session_id": session_id
            }
        
        company_name = session.get('company_name')
        if not company_name:
            return {
                "response": "I need to know which company you'd like me to research. Please provide the company name.",
                "session_id": session_id
            }
        
        # Get existing research data from session
        research_data = session.get('research_data', [])
        
        if not research_data:
            # No research data yet, start fresh research
            logger.info(f"No existing research data, starting fresh research for {company_name}")
            return await self._research_workflow(
                f"Research {company_name}",
                session_id
            )
        
        # User provided clarification (e.g., "go with source B", "cross-check deeply")
        # Continue with existing research data and generate account plan
        logger.info(f"Continuing research for {company_name} with {len(research_data)} existing data sources")
        self.progress_updates = []
        self.progress_updates.append(f"✅ Continuing research on {company_name}")
        self.progress_updates.append(f"📊 Using {len(research_data)} existing data sources")
        
        # Clear conflicts since user provided clarification
        if session.get('conflicts'):
            logger.info("User provided clarification, proceeding despite conflicts")
            self.progress_updates.append("  → Proceeding with research as requested...")
        
        # Step 4: Generate account plan directly (skip data gathering and conflict detection)
        self.progress_updates.append("📝 Generating Account Plan (using Gemini)...")
        account_plan = await self._generate_account_plan(company_name, research_data, session_id)
        
        self.session_memory.set_account_plan(session_id, account_plan)
        self.progress_updates.append("✅ Account Plan generated successfully!")
        
        # Final response
        response_text = f"""
I've completed my research on {company_name} and generated a comprehensive Account Plan based on your clarification.

**Research Summary:**
- Analyzed {len(research_data)} sources
- Used your preference for data prioritization
- Generated structured Account Plan with all sections

The Account Plan is ready for review. You can edit any section or ask me to regenerate specific parts.
"""
        
        self.session_memory.add_message(session_id, "assistant", response_text)
        
        return {
            "response": response_text,
            "session_id": session_id,
            "progress_updates": self.progress_updates,
            "account_plan": account_plan,
            "agent_thinking": self._format_thinking()
        }
    
    async def _general_workflow(
        self,
        message: str,
        session_id: str
    ) -> Dict[str, Any]:
        """Handle general conversation with context awareness"""
        try:
            message_lower = message.lower().strip()
            
            # Handle friendly greetings and help requests
            greeting_patterns = [
                "hello", "hi", "hey", "greetings", "good morning", "good afternoon", 
                "good evening", "hi there", "hello there", "hey there", "sup", "what's up",
                "howdy", "greeting", "hiya"
            ]
            
            help_patterns = [
                "what can you do", "what should you do", "what do you do", 
                "how can you help", "what are you", "who are you", 
                "what is your purpose", "what's your purpose", "help me",
                "what help", "can you help", "what capabilities", "what features",
                "what can you help with", "how do you work", "what's your function"
            ]
            
            thanks_patterns = [
                "thank you", "thanks", "thank", "appreciate", "grateful", 
                "thanks a lot", "thank you so much", "thx"
            ]
            
            # Check for greetings, help requests, and thanks
            is_greeting = any(pattern in message_lower for pattern in greeting_patterns)
            is_help_request = any(pattern in message_lower for pattern in help_patterns)
            is_thanks = any(pattern in message_lower for pattern in thanks_patterns)
            
            if is_thanks:
                # Friendly thank you response
                response_text = """You're very welcome! 😊 

I'm here whenever you need help with:
- Researching companies
- Analyzing documents
- Generating account plans
- Answering questions

Feel free to ask me anything! I'm always happy to help. 🚀"""
                
                self.session_memory.add_message(session_id, "assistant", response_text)
                return {
                    "response": response_text,
                    "session_id": session_id
                }
            
            if is_greeting:
                # Friendly greeting response
                response_text = """Hello! 👋 Great to meet you! I'm your AI Research Assistant, and I'm excited to help you with company research and account planning.

Here's what I can do for you:

🔍 **Research Companies**
Just tell me to research any company, and I'll gather comprehensive information from multiple sources. For example: "Research Microsoft" or "Analyze Apple"

📄 **Upload & Analyze Documents**
Upload PDFs or documents, and I can:
- Answer questions about the content
- Extract key information
- Generate account plans from the documents

📊 **Generate Account Plans**
I can create detailed account plans with:
- Company Overview
- Market Summary
- Key Insights
- Pain Points & Opportunities
- Competitor Analysis
- SWOT Analysis
- Strategic Recommendations
- Executive Summary

✏️ **Edit Account Plans**
Once you have a plan, you can:
- Add new fields (e.g., "Add CEO field")
- Update sections (e.g., "Update company overview")
- Remove fields (e.g., "Delete key insights")
- Regenerate specific sections

💬 **Answer Questions**
Ask me anything about companies, markets, or your research!

**Ready to get started?** Try saying:
- "Research [Company Name]"
- "Generate account plan for [Company]"
- "What is the revenue of [Company]?"

I'm here and ready to help! 🚀"""
                
                self.session_memory.add_message(session_id, "assistant", response_text)
                return {
                    "response": response_text,
                    "session_id": session_id
                }
            
            if is_help_request:
                # Helpful response about capabilities
                response_text = """I'm your AI Research Assistant! Here's what I can do for you:

## 🔍 **Company Research**
Just tell me to research any company, and I'll:
- Gather information from web sources and your uploaded documents
- Analyze market position, products, and services
- Extract key business insights

**Example:** "Research Microsoft" or "Analyze Apple"

## 📄 **Document Analysis**
Upload PDFs, documents, or files, and I can:
- Answer questions about the content
- Extract key information
- Generate account plans from the documents

**Example:** "What is the revenue mentioned in the PDF?" or "Generate account plan from the uploaded document"

## 📊 **Account Plan Generation**
I can create comprehensive account plans with:
- Company Overview
- Market Summary
- Key Insights
- Pain Points & Opportunities
- Competitor Analysis
- SWOT Analysis
- Strategic Recommendations
- Executive Summary

**Example:** "Generate account plan for Zoho" or "Create account plan for Microsoft from the PDF"

## ✏️ **Account Plan Editing**
Once you have an account plan, you can:
- Add new fields (e.g., "Add CEO field")
- Update sections (e.g., "Update company overview")
- Remove fields (e.g., "Delete key insights")
- Regenerate specific sections

**Example:** "Add revenue field and update company overview"

## 💬 **General Questions**
Ask me anything about companies, markets, or your research!

Ready to get started? Just tell me what you'd like to do! 🚀"""
                
                self.session_memory.add_message(session_id, "assistant", response_text)
                return {
                    "response": response_text,
                    "session_id": session_id
                }
            
            # Get conversation history for context
            session = self.session_memory.get_session(session_id)
            conversation_context = ""
            if session:
                recent_messages = session.get('messages', [])[-5:]  # Last 5 messages
                if recent_messages:
                    conversation_context = "\n\nPrevious conversation:\n"
                    for msg in recent_messages:
                        role = msg.get('role', 'user')
                        content = msg.get('content', '')
                        conversation_context += f"{role.capitalize()}: {content}\n"
            
            # Check if user is asking about uploaded documents or wants to generate account plan from PDF
            pdf_keywords = ["uploaded", "pdf", "document", "file", "refer", "from pdf", "from document", "using pdf", "using document"]
            is_pdf_question = any(word in message_lower for word in pdf_keywords)
            wants_account_plan = any(phrase in message_lower for phrase in ["generate account plan", "create account plan", "account plan from", "plan from pdf"])
            
            if is_pdf_question or wants_account_plan:
                # Check for uploaded documents in vector store
                if self.vector_store:
                    try:
                        # Get user_id from session for filtering
                        user_id = session.get('user_id') if session else None
                        
                        # Get uploaded documents for this user
                        if user_id:
                            # Try to get documents with user_id filter
                            try:
                                all_docs = self.vector_store.get_all_documents(limit=100)
                                uploaded_docs = [
                                    d for d in all_docs 
                                    if d.get('metadata', {}).get('source_type') == 'uploaded_document'
                                    and (not user_id or str(d.get('metadata', {}).get('user_id', '')) == str(user_id))
                                ]
                            except:
                                # Fallback if filtering fails
                                all_docs = self.vector_store.get_all_documents(limit=50)
                                uploaded_docs = [d for d in all_docs if d.get('metadata', {}).get('source_type') == 'uploaded_document']
                        else:
                            all_docs = self.vector_store.get_all_documents(limit=50)
                            uploaded_docs = [d for d in all_docs if d.get('metadata', {}).get('source_type') == 'uploaded_document']
                        
                        if uploaded_docs:
                            logger.info(f"Found {len(uploaded_docs)} uploaded documents for user {user_id}")
                            
                            # If user wants account plan from PDF, extract company and start research
                            if wants_account_plan:
                                # Try to extract company name from uploaded documents or message
                                uploaded_text = " ".join([d.get('text', '')[:3000] for d in uploaded_docs[:5]])
                                extracted_company = self._extract_company_name(uploaded_text, session_id)
                                
                                if not extracted_company:
                                    # Try to extract from message
                                    extracted_company = self._extract_company_name(message, session_id)
                                
                                if extracted_company:
                                    logger.info(f"Generating account plan for '{extracted_company}' from uploaded PDF")
                                    return await self._research_workflow(
                                        f"Research {extracted_company}",
                                        session_id
                                    )
                                elif session and session.get('company_name'):
                                    company_name = session.get('company_name')
                                    logger.info(f"Using existing company name '{company_name}' from session for account plan")
                                    return await self._research_workflow(
                                        f"Research {company_name}",
                                        session_id
                                    )
                            else:
                                return {
                                    "response": f"I found {len(uploaded_docs)} uploaded document(s)! To generate an account plan, please tell me which company name to use. For example: 'Generate account plan for [Company Name] from the PDF'",
                                    "session_id": session_id,
                                    "questions": ["Which company should I generate an account plan for?"]
                                }
                            
                            # If user is asking questions about PDF, answer using RAG
                            if is_pdf_question:
                                # Use RAG to answer question from uploaded documents
                                logger.info(f"Answering question about uploaded PDF: {message}")
                                
                                # Get relevant chunks from uploaded documents
                                query = message
                                rag_results = self.rag_pipeline.retrieve(
                                    query=query,
                                    n_results=10,
                                    filter_metadata={'source_type': 'uploaded_document'} if user_id else None
                                )
                                
                                if rag_results:
                                    # Use LLM to answer based on PDF content
                                    context = "\n\n".join([
                                        f"Source: {r.get('source', 'PDF')}\n{r.get('text', '')[:1000]}"
                                        for r in rag_results[:5]
                                    ])
                                    
                                    prompt = f"""Based on the following content from uploaded PDF documents, answer the user's question.

PDF Content:
{context[:5000]}

User Question: {message}

Provide a clear, accurate answer based on the PDF content. If the information is not in the PDF, say so."""
                                    
                                    response_text = self.llm_engine.generate(
                                        prompt=prompt,
                                        system_prompt="You are a senior business analyst and research specialist. Answer questions based on the provided PDF content with production-grade accuracy and depth. Synthesize information from multiple sources, provide strategic insights, and cite sources when possible. Write in professional business language suitable for executive decision-making.",
                                        temperature=0.5,  # Balanced for accuracy and insight
                                        max_tokens=2000  # Increased for comprehensive answers
                                    )
                                    
                                    self.session_memory.add_message(session_id, "assistant", response_text)
                                    return {
                                        "response": response_text,
                                        "session_id": session_id,
                                        "sources": [{"type": "uploaded_document", "source": r.get('source', 'PDF')} for r in rag_results[:3]]
                                    }
                                else:
                                    return {
                                        "response": f"I found {len(uploaded_docs)} uploaded document(s), but couldn't find relevant information to answer your question. Please try rephrasing your question or ask me to generate an account plan from the PDF.",
                                        "session_id": session_id
                                    }
                        else:
                            return {
                                "response": "I don't see any uploaded documents. Please upload a PDF, DOCX, or other document first using the attachment button, then ask me questions or generate an account plan.",
                                "session_id": session_id
                            }
                    except Exception as e:
                        logger.error(f"Error handling PDF question: {e}", exc_info=True)
                        return {
                            "response": f"I encountered an error while accessing uploaded documents: {str(e)}. Please try uploading the file again.",
                            "session_id": session_id
                        }
                else:
                    return {
                        "response": "Document processing is not available. Please check the system configuration.",
                        "session_id": session_id
                    }
            
            if isinstance(self.llm_engine, GeminiEngine):
                # Use Gemini for general conversation with context
                system_prompt = """You are a friendly and helpful AI Research Assistant. Your role is to help users research companies and generate comprehensive account plans.

PERSONALITY:
- Be warm, friendly, and conversational
- Use emojis sparingly to make responses more engaging
- Show enthusiasm about helping users
- Be clear and concise, but not robotic

CAPABILITIES:
- Research companies: Gather information from web sources and uploaded documents
- Analyze documents: Answer questions about uploaded PDFs and documents
- Generate account plans: Create detailed account plans with all sections
- Edit account plans: Add fields, update sections, regenerate content
- Answer questions: Help with company research, market analysis, and more

IMPORTANT GUIDELINES:
- If the user mentions "uploaded pdf", "uploaded document", or "refer the pdf", acknowledge that you can access uploaded documents
- Use conversation history to understand context and follow-up questions
- If the user asks to continue previous research, guide them appropriately
- For greetings or "what can you do" questions, provide a friendly overview of your capabilities
- Always be helpful and encouraging

TONE: Friendly, professional, and approachable. Make users feel welcome and supported."""
                
                full_prompt = f"{conversation_context}\n\nCurrent message: {message}"
                response_text = self.llm_engine.generate(
                    prompt=full_prompt,
                    system_prompt=system_prompt,
                    temperature=0.7  # Balanced for natural conversation with professional consistency
                )
            else:
                raise ValueError("Only Gemini engine is supported. Please configure GEMINI_API_KEY.")
        except Exception as e:
            logger.error(f"Error in general workflow: {e}")
            response_text = "I apologize, but I encountered an error. Please try again."
        
        self.session_memory.add_message(session_id, "assistant", response_text)
        
        return {
            "response": response_text,
            "session_id": session_id
        }
    
    def _extract_company_name(self, message: str, session_id: str = None) -> Optional[str]:
        """Extract company name from message or uploaded documents"""
        import re
        
        # First, try to extract from message - improved patterns
        patterns = [
            r'(?:generate|create|make|build)\s+(?:account\s+plan|plan)\s+(?:for|about)\s+([A-Z][a-zA-Z\s&\.]+?)(?:\s+by|\s+from|\s+refer|please|$)',
            r'(?:research|analyze|find|about|for)\s+([A-Z][a-zA-Z\s&\.]+?)(?:\s+company|\s+corp|\s+inc|\s+ltd|please|$)',
            r'([A-Z][a-zA-Z\s&\.]+?)\s+(?:company|corp|inc|ltd)',
            r'(?:company|corp|inc|ltd)\s+([A-Z][a-zA-Z\s&\.]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                company_name = match.group(1).strip()
                # Clean up common words that might be captured
                company_name = re.sub(r'\s+(by|from|refer|referring|please|pdf|document|uploaded)$', '', company_name, flags=re.IGNORECASE).strip()
                # Remove trailing punctuation
                company_name = re.sub(r'[.,;:!?]+$', '', company_name).strip()
                if company_name and len(company_name) > 1:
                    return company_name
        
        # If no company name in message, try to extract from uploaded documents
        if session_id and self.vector_store:
            try:
                # Get all uploaded documents
                all_docs = self.vector_store.get_all_documents(limit=10)
                uploaded_text = ""
                for doc in all_docs:
                    if doc.get('metadata', {}).get('source_type') == 'uploaded_document':
                        uploaded_text += " " + doc.get('text', '')[:2000]  # First 2000 chars of each doc
                
                if uploaded_text:
                    # Try to extract company name from uploaded documents using entity extractor
                    entities = self.entity_extractor.extract_entities(uploaded_text)
                    extracted_name = entities.get('company_name')
                    if extracted_name:
                        logger.info(f"Extracted company name '{extracted_name}' from uploaded documents")
                        return extracted_name
                    
                    # Fallback: look for common company name patterns in uploaded text
                    company_patterns = [
                        r'([A-Z][a-zA-Z\s&]{2,30})\s+(?:Inc\.|LLC|Ltd\.|Corp\.|Corporation|Company)',
                        r'(?:about|regarding|for)\s+([A-Z][a-zA-Z\s&]{2,30})',
                    ]
                    for pattern in company_patterns:
                        match = re.search(pattern, uploaded_text, re.IGNORECASE)
                        if match:
                            name = match.group(1).strip()
                            if len(name) > 2 and len(name) < 50:  # Reasonable company name length
                                logger.info(f"Extracted company name '{name}' from uploaded documents using pattern")
                                return name
            except Exception as e:
                logger.warning(f"Error extracting company name from documents: {e}")
        
        # Fallback: return first capitalized words from message
        words = message.split()
        capitalized = [w for w in words if w[0].isupper() and len(w) > 2]
        if capitalized:
            return ' '.join(capitalized[:3])
        
        return None
    
    def _extract_section_name(self, message: str) -> Optional[str]:
        """Extract section name from update request"""
        message_lower = message.lower()
        
        # Remove common prefixes like "update", "regenerate", "edit", "change"
        message_clean = message_lower
        for prefix in ["update", "regenerate", "edit", "change", "modify", "rewrite", "refresh"]:
            if message_clean.startswith(prefix):
                message_clean = message_clean[len(prefix):].strip()
        
        section_mapping = {
            'company overview': 'company_overview',
            'company_overview': 'company_overview',
            'overview': 'company_overview',
            'market summary': 'market_summary',
            'market_summary': 'market_summary',
            'key insights': 'key_insights',
            'key_insights': 'key_insights',
            'insights': 'key_insights',
            'pain points': 'pain_points',
            'pain_points': 'pain_points',
            'pain point': 'pain_points',
            'opportunities': 'opportunities',
            'opportunity': 'opportunities',
            'competitor analysis': 'competitor_analysis',
            'competitor_analysis': 'competitor_analysis',
            'competitors': 'competitor_analysis',
            'competitor': 'competitor_analysis',
            'swot': 'swot',
            'swot analysis': 'swot',
            'strengths': 'swot.strengths',
            'weaknesses': 'swot.weaknesses',
            'threats': 'swot.threats',
            'strategic recommendations': 'strategic_recommendations',
            'strategic_recommendations': 'strategic_recommendations',
            'recommendations': 'strategic_recommendations',
            'final account plan': 'final_account_plan',
            'final_account_plan': 'final_account_plan',
            'executive summary': 'executive_summary',
            'executive_summary': 'executive_summary'
        }
        
        # Try exact match first (more specific)
        for key, section in section_mapping.items():
            if key in message_clean or key in message_lower:
                return section
        
        return None
    
    def _format_thinking(self) -> str:
        """Format agent thinking process"""
        return "\n".join([
            f"🤔 {update}" for update in self.progress_updates
        ])


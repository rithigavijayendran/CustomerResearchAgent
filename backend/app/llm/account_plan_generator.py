"""
Account Plan Generator
Generates Account Plans in the exact JSON format specified in the architecture
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class AccountPlanGenerator:
    """
    Generates Account Plans matching the exact JSON schema:
    {
      "company_name": "string",
      "company_overview": "string",
      "financial_summary": {
        "revenue": {"value": "string", "source": ["..."], "confidence": 0.92},
        "profit": {"value": "string", "source": ["..."], "confidence": 0.88}
      },
      "products_services": "string",
      "key_people": [{"name":"", "title":"", "source":""}],
      "swot": {"strengths":"", "weaknesses":"", "opportunities":"", "threats":""},
      "competitors": [{"name":"", "reason":"", "source":""}],
      "recommended_strategy": "string",
      "sources": [{"url":"", "type":"news|pdf|website", "extracted_at":"ISO"}],
      "last_updated": "ISO"
    }
    """
    
    def __init__(self, llm_engine):
        """
        Initialize Account Plan Generator
        
        Args:
            llm_engine: LLM engine instance (GeminiEngine)
        """
        self.llm_engine = llm_engine
    
    def generate_account_plan(
        self,
        company_name: str,
        research_context: str,
        entities: Dict[str, Any],
        sources: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate Account Plan in exact JSON format
        
        Args:
            company_name: Company name
            research_context: Research data context
            entities: Extracted entities (revenue, products, competitors, etc.)
            sources: List of source references with URLs and types
            
        Returns:
            Account Plan dictionary matching exact schema
        """
        logger.info(f"Generating Account Plan for {company_name} in exact JSON format")
        
        sources = sources or []
        
        # Extract financial data from entities
        revenue_value = self._extract_financial_value(entities.get('revenue', []))
        profit_value = self._extract_financial_value(entities.get('profit', []))
        employees_value = self._extract_financial_value(entities.get('employees', []))
        market_cap_value = self._extract_financial_value(entities.get('market_cap', []))
        
        # Build financial summary
        financial_summary = {}
        if revenue_value:
            financial_summary["revenue"] = {
                "value": revenue_value,
                "source": self._get_sources_for_field("revenue", sources),
                "confidence": 0.85
            }
        if profit_value:
            financial_summary["profit"] = {
                "value": profit_value,
                "source": self._get_sources_for_field("profit", sources),
                "confidence": 0.80
            }
        if employees_value:
            financial_summary["employees"] = {
                "value": employees_value,
                "source": self._get_sources_for_field("employees", sources),
                "confidence": 0.75
            }
        if market_cap_value:
            financial_summary["market_cap"] = {
                "value": market_cap_value,
                "source": self._get_sources_for_field("market_cap", sources),
                "confidence": 0.80
            }
        
        # Generate all sections using LLM with individual error handling
        # This ensures all sections are generated even if some fail
        logger.info(f"Generating all sections for {company_name}...")
        
        def safe_generate(generator_func, *args, fallback_text="", **kwargs):
            """Safely generate a section with fallback"""
            try:
                result = generator_func(*args, **kwargs)
                if result and len(str(result).strip()) > 20:
                    return result
                return fallback_text
            except Exception as e:
                logger.error(f"Error generating section {generator_func.__name__}: {e}")
                return fallback_text
        
        company_overview = safe_generate(
            self._generate_company_overview, company_name, research_context, entities,
            fallback_text=f"{company_name} is a company operating in the market. Based on available research data, the company has established a presence in its industry."
        )
        
        market_summary = safe_generate(
            self._generate_market_summary, company_name, research_context, entities,
            fallback_text=f"Market analysis for {company_name} based on research data."
        )
        
        key_insights = safe_generate(
            self._generate_key_insights, company_name, research_context, entities,
            fallback_text=f"Key insights extracted from research data for {company_name}."
        )
        
        pain_points = safe_generate(
            self._generate_pain_points, company_name, research_context, entities,
            fallback_text=f"Pain points and challenges identified from research for {company_name}."
        )
        
        opportunities = safe_generate(
            self._generate_opportunities, company_name, research_context, entities,
            fallback_text=f"Growth opportunities identified from research for {company_name}."
        )
        
        products_services = safe_generate(
            self._generate_products_services, company_name, research_context, entities,
            fallback_text=f"{company_name} offers a range of products and services in its industry."
        )
        
        competitor_analysis = safe_generate(
            self._generate_competitor_analysis, company_name, research_context, entities,
            fallback_text=f"Competitive landscape analysis for {company_name} based on research data."
        )
        
        key_people = safe_generate(
            self._generate_key_people, company_name, research_context, entities, sources,
            fallback_text=[]
        )
        
        swot = safe_generate(
            self._generate_swot, company_name, research_context, entities,
            fallback_text={
                "strengths": "Key strengths identified from research.",
                "weaknesses": "Areas for improvement noted.",
                "opportunities": "Growth opportunities available.",
                "threats": "Potential threats to consider."
            }
        )
        
        competitors = safe_generate(
            self._generate_competitors, company_name, research_context, entities, sources,
            fallback_text=[]
        )
        
        recommended_strategy = safe_generate(
            self._generate_recommended_strategy, company_name, research_context, entities,
            fallback_text=f"Strategic recommendations for engaging with {company_name} based on research analysis."
        )
        
        final_account_plan = safe_generate(
            self._generate_final_account_plan, company_name, company_overview, key_insights, opportunities,
            fallback_text=f"Executive summary for {company_name} Account Plan based on comprehensive research and analysis."
        )
        
        # Format sources
        formatted_sources = self._format_sources(sources)
        
        # Build account plan with all sections
        account_plan = {
            "company_name": company_name,
            "company_overview": company_overview,
            "market_summary": market_summary,
            "key_insights": key_insights,
            "pain_points": pain_points,
            "opportunities": opportunities,
            "financial_summary": financial_summary if financial_summary else None,
            "products_services": products_services,
            "competitor_analysis": competitor_analysis,
            "key_people": key_people,
            "swot": swot,
            "competitors": competitors,
            "strategic_recommendations": recommended_strategy,
            "recommended_strategy": recommended_strategy,  # Keep for compatibility
            "final_account_plan": final_account_plan,
            "sources": formatted_sources,
            "last_updated": datetime.utcnow().isoformat()
        }
        
        logger.info(f"✅ Account Plan generated for {company_name}")
        return account_plan
    
    def _parse_json_array(self, response: str) -> List[Dict]:
        """
        Robustly parse JSON array from LLM response
        Extracts only the first valid JSON array, ignoring extra text
        """
        try:
            # Remove markdown code blocks
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            
            if not response or len(response.strip()) == 0:
                return []
            
            # Find first '[' that starts JSON array
            first_bracket = response.find('[')
            if first_bracket == -1:
                return []
            
            json_candidate = response[first_bracket:]
            
            # Find matching closing ']' by tracking bracket depth
            bracket_depth = 0
            in_string = False
            escape_next = False
            json_end = -1
            
            for i, char in enumerate(json_candidate):
                if escape_next:
                    escape_next = False
                    continue
                
                if char == '\\':
                    escape_next = True
                    continue
                
                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue
                
                if not in_string:
                    if char == '[':
                        bracket_depth += 1
                    elif char == ']':
                        bracket_depth -= 1
                        if bracket_depth == 0:
                            json_end = i + 1
                            break
            
            if json_end > 0:
                json_candidate = json_candidate[:json_end]
            
            # Try to parse
            return json.loads(json_candidate)
        except:
            return []
    
    def _parse_json_object(self, response: str) -> Dict:
        """
        Robustly parse JSON object from LLM response
        Extracts only the first valid JSON object, ignoring extra text
        """
        try:
            # Remove markdown code blocks
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            
            if not response or len(response.strip()) == 0:
                return {}
            
            # Find first '{' that starts JSON object
            first_brace = response.find('{')
            if first_brace == -1:
                return {}
            
            json_candidate = response[first_brace:]
            
            # Find matching closing '}' by tracking brace depth
            brace_depth = 0
            in_string = False
            escape_next = False
            json_end = -1
            
            for i, char in enumerate(json_candidate):
                if escape_next:
                    escape_next = False
                    continue
                
                if char == '\\':
                    escape_next = True
                    continue
                
                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue
                
                if not in_string:
                    if char == '{':
                        brace_depth += 1
                    elif char == '}':
                        brace_depth -= 1
                        if brace_depth == 0:
                            json_end = i + 1
                            break
            
            if json_end > 0:
                json_candidate = json_candidate[:json_end]
            
            # Try to parse
            return json.loads(json_candidate)
        except:
            return {}
    
    def _clean_text(self, text: str) -> str:
        """Aggressively clean text to remove artifacts"""
        if not text:
            return ""
        
        # Remove markdown images and artifacts
        text = re.sub(r'!\[\]\([^\)]*\)', '', text)
        text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
        text = re.sub(r'\[\]', '', text)
        text = re.sub(r'!\[\]', '', text)
        
        # Remove URL fragments
        text = re.sub(r'%[0-9A-Fa-f]{2,}', '', text)
        text = re.sub(r'https?://[^\s]+', '', text)
        text = re.sub(r'www\.[^\s]+', '', text)
        
        # Remove tracking parameters
        text = re.sub(r'\b(rut|utm_|ref|source)=[a-zA-Z0-9]+', '', text, flags=re.IGNORECASE)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    def _extract_financial_value(self, values: List[str]) -> Optional[str]:
        """Extract most recent/relevant financial value"""
        if not values:
            return None
        # Return first value (most relevant)
        return values[0] if isinstance(values[0], str) else str(values[0])
    
    def _get_sources_for_field(self, field: str, sources: List[Dict[str, Any]]) -> List[str]:
        """Get source URLs for a specific field"""
        # Return top 2-3 source URLs
        relevant_sources = [s.get("url", "") for s in sources[:3] if s.get("url")]
        return relevant_sources
    
    def _generate_company_overview(
        self,
        company_name: str,
        research_context: str,
        entities: Dict[str, Any]
    ) -> str:
        """Generate company overview with retry logic"""
        # Reduce context size to prevent MAX_TOKENS issues
        context_limit = 2000  # Reduced from 3000
        entities_limit = 500  # Reduced from 1000
        
        prompt = f"""You are a senior business analyst generating a production-grade company overview for {company_name}.

Research Context (PRIORITIZE UPLOADED DOCUMENTS):
{research_context[:context_limit]}

Extracted Entities:
{json.dumps(entities, indent=2)[:entities_limit]}

Generate a comprehensive, executive-ready company overview (250-350 words) that demonstrates deep understanding:

STRUCTURE:
1. Company History & Founding - When and how the company was established, key milestones
2. Core Business Model - How the company creates value, revenue streams, business approach
3. Current Market Position - Industry standing, market share, competitive positioning
4. Key Products/Services - Primary offerings, unique value propositions, key differentiators
5. Recent Developments - Recent strategic moves, expansions, partnerships, innovations

QUALITY STANDARDS:
- Executive-level business writing suitable for C-suite presentations
- Strategic depth with actionable insights
- Data-driven analysis backed by research
- Clear, concise, and professional language
- Synthesize information - don't copy raw text chunks

Write in professional business English. Return ONLY the overview text, no JSON, no markdown, no artifacts."""
        
        # Retry with smaller context if MAX_TOKENS error
        for attempt in range(2):
            try:
                response = self.llm_engine.generate(
                    prompt=prompt,
                    system_prompt="You are a senior business analyst with 15+ years of experience in strategic consulting. Generate production-grade, executive-ready company overviews suitable for C-suite presentations. Synthesize information from research data - never copy raw text chunks. Write in professional business language with strategic depth. Return ONLY clean text, no markdown, no images, no artifacts.",
                    temperature=0.6,  # Lower for more consistent professional output
                    max_tokens=8000,
                    timeout=120
                )
                if response and len(response.strip()) > 50:
                    cleaned = self._clean_text(response.strip())
                    if len(cleaned) > 50:
                        return cleaned
            except ValueError as e:
                error_msg = str(e).lower()
                if "max_tokens" in error_msg or "truncation" in error_msg:
                    if attempt == 0:
                        # Retry with smaller context
                        logger.warning(f"MAX_TOKENS error on attempt {attempt+1}, retrying with smaller context")
                        context_limit = 1500
                        entities_limit = 300
                        prompt = f"""Generate a comprehensive company overview for {company_name} based on the research data below.

Research Context:
{research_context[:context_limit]}

Generate a detailed company overview (200-300 words) covering company history, business model, market position, products/services, and recent developments.

Write in professional business English. Return ONLY the overview text, no JSON, no markdown."""
                        continue
                raise
            except Exception as e:
                logger.error(f"Error generating company overview: {e}")
                if attempt == 1:  # Last attempt
                    break
        
        return f"{company_name} is a company operating in the market. Based on available research data, the company has established a presence in its industry."
    
    def _generate_products_services(
        self,
        company_name: str,
        research_context: str,
        entities: Dict[str, Any]
    ) -> str:
        """Generate products/services section with retry logic"""
        products = entities.get('products', [])
        products_text = ", ".join(products[:10]) if products else "Various products and services"
        context_limit = 1500  # Reduced to prevent MAX_TOKENS
        
        prompt = f"""Generate a products and services description for {company_name}.

Research Context:
{research_context[:context_limit]}

Known Products/Services: {products_text}

Generate a detailed products and services section (150-250 words) covering:
- Main product/service offerings
- Key features and capabilities
- Target markets
- Service delivery model

Return ONLY the text, no JSON, no markdown."""
        
        for attempt in range(2):
            try:
                response = self.llm_engine.generate(
                    prompt=prompt,
                    system_prompt="You are a senior business analyst with expertise in product strategy and market analysis. Generate production-grade, executive-ready product/service descriptions suitable for strategic planning. Synthesize information from research data - never copy raw text. Write in professional business language with strategic depth. Return ONLY clean text, no markdown, no images, no artifacts.",
                    temperature=0.7,
                max_tokens=8000,  # Significantly increased
                timeout=120
                )
                if response and len(response.strip()) > 50:
                    cleaned = self._clean_text(response.strip())
                    if len(cleaned) > 50:
                        return cleaned
            except ValueError as e:
                error_msg = str(e).lower()
                if "max_tokens" in error_msg or "truncation" in error_msg:
                    if attempt == 0:
                        context_limit = 1000
                        prompt = f"""Generate a products and services description for {company_name}.

Research Context:
{research_context[:context_limit]}

Known Products/Services: {products_text}

Generate a detailed products and services section (150-250 words). Return ONLY the text, no JSON, no markdown."""
                        continue
                raise
            except Exception as e:
                logger.error(f"Error generating products/services: {e}")
                if attempt == 1:
                    break
        
        return f"{company_name} offers a range of products and services in its industry."
    
    def _generate_key_people(
        self,
        company_name: str,
        research_context: str,
        entities: Dict[str, Any],
        sources: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Generate key people list"""
        # Extract from entities
        people = entities.get('people', [])
        
        if not people:
            # Try to extract from research context using LLM
            prompt = f"""Extract key people (executives, leaders) for {company_name} from the research data below.

Research Context:
{research_context[:2000]}

Return a JSON array of key people in this format:
[
  {{"name": "John Doe", "title": "CEO", "source": "url1"}},
  {{"name": "Jane Smith", "title": "CTO", "source": "url2"}}
]

Return ONLY the JSON array, no markdown, no explanations."""
            
            try:
                response = self.llm_engine.generate(
                    prompt=prompt,
                    system_prompt="You are a senior business analyst specializing in executive intelligence and organizational analysis. Extract key people information with high accuracy. Return ONLY valid JSON array with proper formatting. Ensure all fields are complete and accurate.",
                    temperature=0.5,
                    max_tokens=8000,  # Significantly increased  # Increased
                    timeout=120
                )
                
                # Parse JSON with robust extraction (same as web_search.py)
                people_list = self._parse_json_array(response)
                if isinstance(people_list, list):
                    # Limit to top 5
                    return people_list[:5]
            except Exception as e:
                logger.error(f"Error extracting key people: {e}")
        
        # Fallback: format from entities
        formatted_people = []
        source_url = sources[0].get("url", "") if sources else ""
        
        for person in people[:5]:
            if isinstance(person, dict):
                formatted_people.append({
                    "name": person.get("name", ""),
                    "title": person.get("title", ""),
                    "source": person.get("source", source_url)
                })
            elif isinstance(person, str):
                # Try to parse "Name, Title" format
                parts = person.split(",")
                if len(parts) >= 2:
                    formatted_people.append({
                        "name": parts[0].strip(),
                        "title": parts[1].strip(),
                        "source": source_url
                    })
        
        return formatted_people[:5]
    
    def _generate_swot(
        self,
        company_name: str,
        research_context: str,
        entities: Dict[str, Any]
    ) -> Dict[str, str]:
        """Generate SWOT analysis with retry logic"""
        context_limit = 2000  # Reduced to prevent MAX_TOKENS
        
        prompt = f"""Generate a SWOT analysis for {company_name} based on the research data below.

Research Context:
{research_context[:context_limit]}

Return a JSON object with SWOT analysis:
{{
  "strengths": "4-5 key strengths, each as a complete sentence or bullet point",
  "weaknesses": "4-5 weaknesses, each as a complete sentence or bullet point",
  "opportunities": "4-5 opportunities, each as a complete sentence or bullet point",
  "threats": "4-5 threats, each as a complete sentence or bullet point"
}}

Return ONLY the JSON object, no markdown, no explanations."""
        
        for attempt in range(2):
            try:
                response = self.llm_engine.generate(
                    prompt=prompt,
                    system_prompt="You are a strategic analyst. Generate SWOT analysis. Return ONLY valid JSON object, no markdown, no explanations, no extra text after JSON.",
                    temperature=0.7,
                    max_tokens=8000,  # Significantly increased
                    timeout=120
                )
                
                if not response or len(response.strip()) < 10:
                    if attempt == 0:
                        context_limit = 1500
                        prompt = f"""Generate a SWOT analysis for {company_name} based on the research data below.

Research Context:
{research_context[:context_limit]}

Return a JSON object with SWOT analysis. Return ONLY the JSON object, no markdown."""
                        continue
                    break
                
                # Parse JSON with robust extraction
                swot = self._parse_json_object(response)
                if swot:
                    return {
                        "strengths": self._clean_text(str(swot.get("strengths", ""))),
                        "weaknesses": self._clean_text(str(swot.get("weaknesses", ""))),
                        "opportunities": self._clean_text(str(swot.get("opportunities", ""))),
                        "threats": self._clean_text(str(swot.get("threats", "")))
                    }
            except ValueError as e:
                error_msg = str(e).lower()
                if "max_tokens" in error_msg or "truncation" in error_msg:
                    if attempt == 0:
                        logger.warning(f"MAX_TOKENS error in SWOT, retrying with smaller context")
                        context_limit = 1500
                        prompt = f"""Generate a SWOT analysis for {company_name} based on the research data below.

Research Context:
{research_context[:context_limit]}

Return a JSON object with SWOT analysis. Return ONLY the JSON object, no markdown."""
                        continue
                raise
            except Exception as e:
                logger.error(f"Error generating SWOT: {e}")
                if attempt == 1:
                    break
        
        return {
            "strengths": "Key strengths identified from research.",
            "weaknesses": "Areas for improvement noted.",
            "opportunities": "Growth opportunities available.",
            "threats": "Potential threats to consider."
        }
    
    def _generate_competitors(
        self,
        company_name: str,
        research_context: str,
        entities: Dict[str, Any],
        sources: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Generate competitors list"""
        competitors = entities.get('competitors', [])
        source_url = sources[0].get("url", "") if sources else ""
        
        formatted_competitors = []
        
        for competitor in competitors[:5]:
            if isinstance(competitor, dict):
                formatted_competitors.append({
                    "name": competitor.get("name", ""),
                    "reason": competitor.get("reason", "Competitor in the same market"),
                    "source": competitor.get("source", source_url)
                })
            elif isinstance(competitor, str):
                formatted_competitors.append({
                    "name": competitor,
                    "reason": "Competitor in the same market",
                    "source": source_url
                })
        
        return formatted_competitors[:5]
    
    def _generate_recommended_strategy(
        self,
        company_name: str,
        research_context: str,
        entities: Dict[str, Any]
    ) -> str:
        """Generate recommended strategy with retry logic"""
        context_limit = 2000  # Reduced to prevent MAX_TOKENS
        
        prompt = f"""Generate strategic recommendations for engaging with {company_name} based on the research data below.

Research Context:
{research_context[:context_limit]}

Generate 4-6 actionable strategic recommendations (250-350 words) covering:
- Key engagement opportunities
- Strategic partnership areas
- Solution positioning
- Implementation approach

Return ONLY the text, no JSON, no markdown."""
        
        for attempt in range(2):
            try:
                response = self.llm_engine.generate(
                    prompt=prompt,
                    system_prompt="You are a strategic consultant. Generate actionable strategic recommendations. Return ONLY clean text, no markdown, no images, no artifacts.",
                    temperature=0.8,
                    max_tokens=8000,  # Significantly increased
                    timeout=120
                )
                if response and len(response.strip()) > 50:
                    cleaned = self._clean_text(response.strip())
                    if len(cleaned) > 50:
                        return cleaned
            except ValueError as e:
                error_msg = str(e).lower()
                if "max_tokens" in error_msg or "truncation" in error_msg:
                    if attempt == 0:
                        logger.warning(f"MAX_TOKENS error in recommended strategy, retrying with smaller context")
                        context_limit = 1500
                        prompt = f"""Generate strategic recommendations for engaging with {company_name} based on the research data below.

Research Context:
{research_context[:context_limit]}

Generate 4-6 actionable strategic recommendations (250-350 words). Return ONLY the text, no JSON, no markdown."""
                        continue
                raise
            except Exception as e:
                logger.error(f"Error generating recommended strategy: {e}")
                if attempt == 1:
                    break
        
        return "Strategic recommendations based on analysis. Further research recommended for detailed planning."
    
    def _generate_market_summary(
        self,
        company_name: str,
        research_context: str,
        entities: Dict[str, Any]
    ) -> str:
        """Generate market summary with retry logic"""
        context_limit = 2000
        
        prompt = f"""Generate a market summary for {company_name} based on the research data below.

Research Context:
{research_context[:context_limit]}

Generate a detailed market summary (200-300 words) covering:
- Industry classification
- Market size and growth trends
- Market position and competitive landscape
- Key market segments
- Geographic presence

Return ONLY the text, no JSON, no markdown."""
        
        for attempt in range(2):
            try:
                response = self.llm_engine.generate(
                    prompt=prompt,
                    system_prompt="You are a market analyst. Generate professional market summaries. Return ONLY clean text, no markdown, no images, no artifacts.",
                    temperature=0.7,
                    max_tokens=8000,  # Significantly increased
                    timeout=120
                )
                if response and len(response.strip()) > 50:
                    cleaned = self._clean_text(response.strip())
                    if len(cleaned) > 50:
                        return cleaned
            except ValueError as e:
                error_msg = str(e).lower()
                if "max_tokens" in error_msg or "truncation" in error_msg:
                    if attempt == 0:
                        context_limit = 1500
                        prompt = f"""Generate a market summary for {company_name} based on the research data below.

Research Context:
{research_context[:context_limit]}

Generate a detailed market summary (200-300 words). Return ONLY the text, no JSON, no markdown."""
                        continue
                raise
            except Exception as e:
                logger.error(f"Error generating market summary: {e}")
                if attempt == 1:
                    break
        
        return f"Market analysis for {company_name} based on research data."
    
    def _generate_key_insights(
        self,
        company_name: str,
        research_context: str,
        entities: Dict[str, Any]
    ) -> str:
        """Generate key insights with retry logic"""
        context_limit = 2000
        
        prompt = f"""Generate key insights for {company_name} based on the research data below.

Research Context:
{research_context[:context_limit]}

Generate 5-7 key insights (250-350 words) covering:
- Strategic implications
- Market dynamics
- Competitive advantages
- Business model insights
- Recent developments

Return ONLY the text, no JSON, no markdown."""
        
        for attempt in range(2):
            try:
                response = self.llm_engine.generate(
                    prompt=prompt,
                    system_prompt="You are a strategic analyst. Generate key business insights. Return ONLY clean text, no markdown, no images, no artifacts.",
                    temperature=0.7,
                    max_tokens=8000,  # Significantly increased
                    timeout=120
                )
                if response and len(response.strip()) > 50:
                    cleaned = self._clean_text(response.strip())
                    if len(cleaned) > 50:
                        return cleaned
            except ValueError as e:
                error_msg = str(e).lower()
                if "max_tokens" in error_msg or "truncation" in error_msg:
                    if attempt == 0:
                        context_limit = 1500
                        prompt = f"""Generate key insights for {company_name} based on the research data below.

Research Context:
{research_context[:context_limit]}

Generate 5-7 key insights (250-350 words). Return ONLY the text, no JSON, no markdown."""
                        continue
                raise
            except Exception as e:
                logger.error(f"Error generating key insights: {e}")
                if attempt == 1:
                    break
        
        return f"Key insights extracted from research data for {company_name}."
    
    def _generate_pain_points(
        self,
        company_name: str,
        research_context: str,
        entities: Dict[str, Any]
    ) -> str:
        """Generate pain points with retry logic"""
        context_limit = 2000
        
        prompt = f"""Generate pain points and challenges for {company_name} based on the research data below.

Research Context:
{research_context[:context_limit]}

Generate 4-6 major pain points (200-300 words) covering:
- Operational challenges
- Market pressures
- Competitive threats
- Technology gaps
- Financial constraints

Return ONLY the text, no JSON, no markdown."""
        
        for attempt in range(2):
            try:
                response = self.llm_engine.generate(
                    prompt=prompt,
                    system_prompt="You are a business consultant. Identify key pain points and challenges. Return ONLY clean text, no markdown, no images, no artifacts.",
                    temperature=0.7,
                    max_tokens=8000,  # Significantly increased
                    timeout=120
                )
                if response and len(response.strip()) > 50:
                    cleaned = self._clean_text(response.strip())
                    if len(cleaned) > 50:
                        return cleaned
            except ValueError as e:
                error_msg = str(e).lower()
                if "max_tokens" in error_msg or "truncation" in error_msg:
                    if attempt == 0:
                        context_limit = 1500
                        prompt = f"""Generate pain points for {company_name} based on the research data below.

Research Context:
{research_context[:context_limit]}

Generate 4-6 major pain points (200-300 words). Return ONLY the text, no JSON, no markdown."""
                        continue
                raise
            except Exception as e:
                logger.error(f"Error generating pain points: {e}")
                if attempt == 1:
                    break
        
        return f"Pain points and challenges identified from research for {company_name}."
    
    def _generate_opportunities(
        self,
        company_name: str,
        research_context: str,
        entities: Dict[str, Any]
    ) -> str:
        """Generate opportunities with retry logic"""
        context_limit = 2000
        
        prompt = f"""Generate growth opportunities for {company_name} based on the research data below.

Research Context:
{research_context[:context_limit]}

Generate 4-6 key opportunities (200-300 words) covering:
- Market expansion opportunities
- Product development areas
- Strategic partnerships
- Emerging trends
- Untapped markets

Return ONLY the text, no JSON, no markdown."""
        
        for attempt in range(2):
            try:
                response = self.llm_engine.generate(
                    prompt=prompt,
                    system_prompt="You are a senior growth strategist with 15+ years of experience in market expansion and strategic planning. Identify growth opportunities with production-grade strategic depth. Synthesize information from research data - never copy raw text. Write in professional business language with actionable insights. Return ONLY clean text, no markdown, no images, no artifacts.",
                    temperature=0.8,
                    max_tokens=8000,  # Significantly increased
                    timeout=120
                )
                if response and len(response.strip()) > 50:
                    cleaned = self._clean_text(response.strip())
                    if len(cleaned) > 50:
                        return cleaned
            except ValueError as e:
                error_msg = str(e).lower()
                if "max_tokens" in error_msg or "truncation" in error_msg:
                    if attempt == 0:
                        context_limit = 1500
                        prompt = f"""Generate opportunities for {company_name} based on the research data below.

Research Context:
{research_context[:context_limit]}

Generate 4-6 key opportunities (200-300 words). Return ONLY the text, no JSON, no markdown."""
                        continue
                raise
            except Exception as e:
                logger.error(f"Error generating opportunities: {e}")
                if attempt == 1:
                    break
        
        return f"Growth opportunities identified from research for {company_name}."
    
    def _generate_competitor_analysis(
        self,
        company_name: str,
        research_context: str,
        entities: Dict[str, Any]
    ) -> str:
        """Generate competitor analysis with retry logic"""
        context_limit = 2000
        competitors = entities.get('competitors', [])
        competitors_text = ", ".join(competitors[:5]) if competitors else "Various competitors"
        
        prompt = f"""Generate competitor analysis for {company_name} based on the research data below.

Research Context:
{research_context[:context_limit]}

Known Competitors: {competitors_text}

Generate a detailed competitor analysis (250-350 words) covering:
- Main competitors and their market positions
- Competitive advantages and disadvantages
- Market share comparisons
- Product/service differentiation

Return ONLY the text, no JSON, no markdown."""
        
        for attempt in range(2):
            try:
                response = self.llm_engine.generate(
                    prompt=prompt,
                    system_prompt="You are a competitive intelligence analyst. Generate competitor analysis. Return ONLY clean text, no markdown, no images, no artifacts.",
                    temperature=0.7,
                    max_tokens=8000,  # Significantly increased
                    timeout=120
                )
                if response and len(response.strip()) > 50:
                    cleaned = self._clean_text(response.strip())
                    if len(cleaned) > 50:
                        return cleaned
            except ValueError as e:
                error_msg = str(e).lower()
                if "max_tokens" in error_msg or "truncation" in error_msg:
                    if attempt == 0:
                        context_limit = 1500
                        prompt = f"""Generate competitor analysis for {company_name} based on the research data below.

Research Context:
{research_context[:context_limit]}

Known Competitors: {competitors_text}

Generate a detailed competitor analysis (250-350 words). Return ONLY the text, no JSON, no markdown."""
                        continue
                raise
            except Exception as e:
                logger.error(f"Error generating competitor analysis: {e}")
                if attempt == 1:
                    break
        
        return f"Competitive landscape analysis for {company_name} based on research data."
    
    def _generate_final_account_plan(
        self,
        company_name: str,
        company_overview: str,
        key_insights: str,
        opportunities: str
    ) -> str:
        """Generate final account plan (executive summary)"""
        prompt = f"""Create an executive summary for {company_name} Account Plan based on the following sections:

Company Overview: {company_overview[:300]}

Key Insights: {key_insights[:300]}

Opportunities: {opportunities[:300]}

Generate a comprehensive executive summary (300-400 words) that synthesizes all key findings into a cohesive narrative. Include company positioning, market opportunity, and strategic priorities.

Return ONLY the text, no JSON, no markdown."""
        
        try:
            response = self.llm_engine.generate(
                prompt=prompt,
                system_prompt="You are a senior executive strategist with 15+ years of experience in C-suite consulting and strategic planning. Generate production-grade, executive-ready summaries suitable for board presentations. Synthesize all sections into a cohesive strategic narrative with actionable insights. Write in professional business language with strategic depth. Return ONLY clean text, no markdown, no images, no artifacts.",
                temperature=0.7,
                max_tokens=8000,  # Significantly increased
                timeout=120
            )
            if response and len(response.strip()) > 50:
                cleaned = self._clean_text(response.strip())
                if len(cleaned) > 50:
                    return cleaned
        except Exception as e:
            logger.error(f"Error generating final account plan: {e}")
        
        return f"Executive summary for {company_name} Account Plan based on comprehensive research and analysis."
    
    def _format_sources(self, sources: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Format sources to match schema"""
        formatted = []
        for source in sources:
            formatted.append({
                "url": source.get("url", ""),
                "type": source.get("type", "website"),  # "news", "pdf", "website"
                "extracted_at": source.get("extracted_at", datetime.utcnow().isoformat())
            })
        return formatted


"""
Retrieval API / Grounding Layer
Exposes retrieval helpers to Agent Controller and LLM
Provides: retrieve_relevant_chunks, retrieve_by_section, filter_by_date
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta

from app.rag.vector_store import VectorStore

logger = logging.getLogger(__name__)


class RetrievalAPI:
    """
    Retrieval API for RAG operations
    Provides grounding layer for LLM responses
    """
    
    def __init__(self, vector_store: Optional[VectorStore] = None):
        self.vector_store = vector_store
    
    def retrieve_relevant_chunks(
        self,
        query: str,
        company: Optional[str] = None,
        top_k: int = 10,
        user_id: Optional[str] = None,
        min_score: float = 0.5,
        source_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant chunks for a query
        
        Args:
            query: Search query
            company: Optional company name filter
            top_k: Number of results to return
            user_id: Optional user ID filter
            min_score: Minimum similarity score
            source_types: Optional list of source types to filter
            
        Returns:
            List of relevant chunks with metadata
        """
        if not self.vector_store:
            logger.warning("No vector store available")
            return []
        
        try:
            # Build filter
            filter_dict = {}
            if company:
                filter_dict["company_name"] = company
            if user_id:
                filter_dict["user_id"] = user_id
            if source_types:
                filter_dict["source"] = {"$in": source_types}
            
            # Retrieve from vector store
            results = self.vector_store.search(
                query=query,
                top_k=top_k,
                filter=filter_dict if filter_dict else None
            )
            
            # Filter by minimum score
            filtered_results = [
                r for r in results
                if r.get("score", 0.0) >= min_score
            ]
            
            # Enhance with metadata
            enhanced_results = []
            for result in filtered_results[:top_k]:
                enhanced = {
                    "text": result.get("text", ""),
                    "chunk_id": result.get("chunk_id", ""),
                    "score": result.get("score", 0.0),
                    "metadata": result.get("metadata", {}),
                    "source": result.get("metadata", {}).get("source", "unknown"),
                    "url": result.get("metadata", {}).get("url", ""),
                    "title": result.get("metadata", {}).get("title", ""),
                    "confidence": result.get("metadata", {}).get("confidence", 0.5),
                    "llm_summary": result.get("metadata", {}).get("llm_summary", ""),
                    "key_facts": result.get("metadata", {}).get("key_facts", []),
                    "retrieved_at": result.get("metadata", {}).get("retrieved_at", ""),
                    "stored_at": result.get("metadata", {}).get("stored_at", "")
                }
                enhanced_results.append(enhanced)
            
            logger.info(f"Retrieved {len(enhanced_results)} chunks for query: {query[:50]}")
            return enhanced_results
            
        except Exception as e:
            logger.error(f"Error retrieving chunks: {e}", exc_info=True)
            return []
    
    def retrieve_by_section(
        self,
        company: str,
        section_key: str,
        top_k: int = 5,
        user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve chunks relevant to a specific account plan section
        
        Args:
            company: Company name
            section_key: Section key (e.g., "opportunities", "pain_points")
            top_k: Number of results
            user_id: Optional user ID filter
            
        Returns:
            List of relevant chunks
        """
        # Map section keys to relevant queries
        section_queries = {
            "company_overview": f"{company} overview company information",
            "market_summary": f"{company} market analysis industry",
            "key_insights": f"{company} insights trends",
            "pain_points": f"{company} challenges problems pain points",
            "opportunities": f"{company} opportunities growth potential",
            "competitor_analysis": f"{company} competitors competitive analysis",
            "swot": f"{company} SWOT analysis strengths weaknesses",
            "strategic_recommendations": f"{company} recommendations strategy",
            "final_account_plan": f"{company} account plan strategy"
        }
        
        query = section_queries.get(section_key, f"{company} {section_key}")
        
        return self.retrieve_relevant_chunks(
            query=query,
            company=company,
            top_k=top_k,
            user_id=user_id,
            min_score=0.4  # Lower threshold for section-specific retrieval
        )
    
    def filter_by_date(
        self,
        chunks: List[Dict[str, Any]],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Filter chunks by date range
        
        Args:
            chunks: List of chunks to filter
            start_date: Optional start date
            end_date: Optional end date
            
        Returns:
            Filtered list of chunks
        """
        if not start_date and not end_date:
            return chunks
        
        filtered = []
        for chunk in chunks:
            # Try to get date from metadata
            retrieved_at = chunk.get("metadata", {}).get("retrieved_at")
            stored_at = chunk.get("metadata", {}).get("stored_at")
            
            chunk_date = None
            if retrieved_at:
                try:
                    chunk_date = datetime.fromisoformat(retrieved_at.replace('Z', '+00:00'))
                except:
                    pass
            elif stored_at:
                try:
                    chunk_date = datetime.fromisoformat(stored_at.replace('Z', '+00:00'))
                except:
                    pass
            
            if chunk_date:
                if start_date and chunk_date < start_date:
                    continue
                if end_date and chunk_date > end_date:
                    continue
            
            filtered.append(chunk)
        
        return filtered
    
    def apply_grounding_filter(
        self,
        chunks: List[Dict[str, Any]],
        min_confidence: float = 0.6,
        require_sources: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Apply grounding filter to chunks
        Filters by confidence and source requirements
        
        Args:
            chunks: List of chunks to filter
            min_confidence: Minimum confidence score
            require_sources: Whether to require source URLs
            
        Returns:
            Filtered and sorted chunks
        """
        filtered = []
        for chunk in chunks:
            # Check confidence
            confidence = chunk.get("confidence", 0.5)
            if confidence < min_confidence:
                continue
            
            # Check source requirement
            if require_sources:
                url = chunk.get("url") or chunk.get("metadata", {}).get("url")
                if not url:
                    continue
            
            filtered.append(chunk)
        
        # Sort by score (descending)
        filtered.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        
        return filtered
    
    def get_top_sources(
        self,
        chunks: List[Dict[str, Any]],
        top_n: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Extract top sources from chunks
        
        Args:
            chunks: List of chunks
            top_n: Number of top sources to return
            
        Returns:
            List of unique sources with metadata
        """
        sources_map = {}
        
        for chunk in chunks:
            url = chunk.get("url") or chunk.get("metadata", {}).get("url")
            if not url:
                continue
            
            if url not in sources_map:
                sources_map[url] = {
                    "url": url,
                    "title": chunk.get("title") or chunk.get("metadata", {}).get("title", ""),
                    "source": chunk.get("source") or chunk.get("metadata", {}).get("source", "unknown"),
                    "confidence": chunk.get("confidence", 0.5),
                    "chunk_count": 0,
                    "max_score": 0.0
                }
            
            sources_map[url]["chunk_count"] += 1
            sources_map[url]["max_score"] = max(
                sources_map[url]["max_score"],
                chunk.get("score", 0.0)
            )
        
        # Sort by max_score and chunk_count
        sorted_sources = sorted(
            sources_map.values(),
            key=lambda x: (x["max_score"], x["chunk_count"]),
            reverse=True
        )
        
        return sorted_sources[:top_n]

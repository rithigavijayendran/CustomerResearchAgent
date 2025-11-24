"""
Query Router / Orchestrator
Validates queries, checks cache, deduplicates jobs, routes to workers, and handles tracing
"""

import os
import hashlib
import logging
import uuid
import asyncio
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
from fastapi import Request

from app.orchestrator.cache_manager import CacheManager
from app.observability.tracing import TraceContext, trace_function
from app.workers.background_tasks import get_worker

logger = logging.getLogger(__name__)


class QueryRouter:
    """
    Orchestrator that handles:
    - Request validation
    - Cache checking (SERP responses, embeddings)
    - Job deduplication
    - Request tracing
    - Worker job routing
    """
    
    def __init__(self):
        self.cache_manager = CacheManager()
        self.worker = get_worker()
        self.active_jobs: Dict[str, Dict[str, Any]] = {}  # Track active jobs by query hash
        
    @trace_function
    async def route_query(
        self,
        query: str,
        user_id: str,
        company_name: Optional[str] = None,
        request: Optional[Request] = None
    ) -> Dict[str, Any]:
        """
        Main routing method - validates, checks cache, deduplicates, and routes query
        
        Args:
            query: User query string
            user_id: User ID for tracking
            company_name: Optional company name for context
            request: FastAPI request object for tracing
            
        Returns:
            Dictionary with routing result, cache status, job_id, etc.
        """
        # Generate request ID for tracing
        request_id = str(uuid.uuid4())
        
        # Create trace context
        trace_context = TraceContext(request_id=request_id)
        trace_context.start_span("query_router.route_query")
        
        try:
            # Step 1: Validate query
            validation_result = self._validate_query(query, company_name)
            if not validation_result["valid"]:
                trace_context.end_span()
                return {
                    "request_id": request_id,
                    "valid": False,
                    "error": validation_result["error"],
                    "cached": False
                }
            
            # Step 2: Generate query hash for deduplication
            query_hash = self._generate_query_hash(query, company_name, user_id)
            
            # Step 3: Check for duplicate active job
            if query_hash in self.active_jobs:
                active_job = self.active_jobs[query_hash]
                logger.info(f"Duplicate query detected, returning existing job_id: {active_job['job_id']}")
                trace_context.end_span()
                return {
                    "request_id": request_id,
                    "valid": True,
                    "cached": False,
                    "duplicate": True,
                    "job_id": active_job["job_id"],
                    "existing_job": active_job
                }
            
            # Step 4: Check cache (SERP responses cached for 1-6 hours)
            cache_key = f"serp:{query_hash}"
            cached_result = await self.cache_manager.get(cache_key)
            
            if cached_result:
                logger.info(f"Cache hit for query: {query[:50]}...")
                trace_context.end_span()
                return {
                    "request_id": request_id,
                    "valid": True,
                    "cached": True,
                    "cache_key": cache_key,
                    "result": cached_result,
                    "job_id": None
                }
            
            # Step 5: Create new job
            job_id = str(uuid.uuid4())
            job_info = {
                "job_id": job_id,
                "query": query,
                "company_name": company_name,
                "user_id": user_id,
                "query_hash": query_hash,
                "created_at": datetime.utcnow(),
                "status": "queued"
            }
            
            self.active_jobs[query_hash] = job_info
            
            trace_context.end_span()
            
            return {
                "request_id": request_id,
                "valid": True,
                "cached": False,
                "duplicate": False,
                "job_id": job_id,
                "job_info": job_info
            }
            
        except Exception as e:
            logger.error(f"Query routing error: {e}", exc_info=True)
            trace_context.end_span()
            return {
                "request_id": request_id,
                "valid": False,
                "error": str(e),
                "cached": False
            }
    
    def _validate_query(self, query: str, company_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate query input
        
        Args:
            query: Query string
            company_name: Optional company name
            
        Returns:
            Validation result dictionary
        """
        if not query or len(query.strip()) == 0:
            return {"valid": False, "error": "Query cannot be empty"}
        
        if len(query) > 1000:
            return {"valid": False, "error": "Query too long (max 1000 characters)"}
        
        # Check for suspicious patterns (basic security)
        suspicious_patterns = ["<script", "javascript:", "onerror=", "onload="]
        query_lower = query.lower()
        for pattern in suspicious_patterns:
            if pattern in query_lower:
                return {"valid": False, "error": "Query contains invalid characters"}
        
        return {"valid": True}
    
    def _generate_query_hash(self, query: str, company_name: Optional[str], user_id: str) -> str:
        """
        Generate hash for query deduplication
        
        Args:
            query: Query string
            company_name: Optional company name
            user_id: User ID
            
        Returns:
            SHA256 hash string
        """
        # Normalize query
        normalized = query.strip().lower()
        if company_name:
            normalized += f":{company_name.strip().lower()}"
        normalized += f":{user_id}"
        
        return hashlib.sha256(normalized.encode()).hexdigest()
    
    def mark_job_complete(self, query_hash: str, result: Dict[str, Any]):
        """
        Mark job as complete and cache result
        
        Args:
            query_hash: Query hash
            result: Job result to cache
        """
        if query_hash in self.active_jobs:
            job_info = self.active_jobs[query_hash]
            job_info["status"] = "completed"
            job_info["completed_at"] = datetime.utcnow()
            job_info["result"] = result
            
            # Cache SERP results for 1-6 hours (configurable)
            cache_ttl = int(os.getenv("SERP_CACHE_TTL_HOURS", "3"))  # Default 3 hours
            cache_key = f"serp:{query_hash}"
            asyncio.create_task(self.cache_manager.set(cache_key, result, ttl_seconds=cache_ttl * 3600))
            
            # Remove from active jobs after a delay (keep for 1 hour)
            # In production, use a background task for cleanup
            logger.info(f"Job {job_info['job_id']} completed and cached")
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job status by job_id
        
        Args:
            job_id: Job ID
            
        Returns:
            Job info dictionary or None
        """
        for job_info in self.active_jobs.values():
            if job_info["job_id"] == job_id:
                return job_info
        return None
    
    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """
        Clean up old completed jobs
        
        Args:
            max_age_hours: Maximum age in hours for completed jobs
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        jobs_to_remove = []
        for query_hash, job_info in self.active_jobs.items():
            if job_info.get("status") == "completed":
                completed_at = job_info.get("completed_at")
                if completed_at and completed_at < cutoff_time:
                    jobs_to_remove.append(query_hash)
        
        for query_hash in jobs_to_remove:
            del self.active_jobs[query_hash]
        
        if jobs_to_remove:
            logger.info(f"Cleaned up {len(jobs_to_remove)} old jobs")


# Global router instance
_router_instance = None

def get_router() -> QueryRouter:
    """Get or create global router instance"""
    global _router_instance
    if _router_instance is None:
        _router_instance = QueryRouter()
    return _router_instance


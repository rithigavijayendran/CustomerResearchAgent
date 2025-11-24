"""
Research Orchestrator - Central Coordinator
Handles request validation, caching, job dispatch, and progress tracking
"""

import os
import logging
import hashlib
import json
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

from app.workers.background_tasks import get_worker
from app.orchestrator.cache_manager import CacheManager
from app.observability.tracing import TraceContext, trace_function

logger = logging.getLogger(__name__)


@dataclass
class ResearchJob:
    """Research job metadata"""
    job_id: str
    user_id: str
    company_name: str
    query: str
    status: str  # pending, processing, completed, failed
    created_at: datetime
    updated_at: datetime
    progress: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ResearchOrchestrator:
    """
    Central orchestrator for research requests
    - Validates input
    - Checks cache
    - Creates jobs
    - Dispatches to background worker
    - Tracks progress
    - Handles retries
    """
    
    def __init__(self, cache_manager: Optional[CacheManager] = None, worker=None):
        self.cache_manager = cache_manager or CacheManager()
        self.worker = worker or get_worker()
        self.active_jobs: Dict[str, ResearchJob] = {}
        self.circuit_breaker_threshold = 5
        self.circuit_breaker_failures = 0
        
    @trace_function
    async def process_research_request(
        self,
        user_id: str,
        company_name: str,
        query: str,
        session_id: str,
        trace_context: Optional[TraceContext] = None
    ) -> Dict[str, Any]:
        """
        Main entry point for research requests
        
        Args:
            user_id: User ID
            company_name: Company to research
            query: Research query
            session_id: Session ID for context
            trace_context: Tracing context
            
        Returns:
            Dict with job_id, status, and initial response
        """
        with TraceContext("research_orchestrator", trace_context) as ctx:
            # Step 1: Validate input
            validation_result = self._validate_request(company_name, query)
            if not validation_result["valid"]:
                return {
                    "job_id": None,
                    "status": "validation_failed",
                    "error": validation_result["error"],
                    "trace_id": ctx.trace_id
                }
            
            # Step 2: Check cache
            cache_key = self._generate_cache_key(company_name, query)
            cached_result = await self.cache_manager.get(cache_key)
            
            if cached_result:
                logger.info(f"Cache hit for {company_name} - {query}")
                return {
                    "job_id": f"cached_{cache_key[:8]}",
                    "status": "completed",
                    "result": cached_result,
                    "cached": True,
                    "trace_id": ctx.trace_id
                }
            
            # Step 3: Create job
            job_id = self._generate_job_id(user_id, company_name, query)
            job = ResearchJob(
                job_id=job_id,
                user_id=user_id,
                company_name=company_name,
                query=query,
                status="pending",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                progress={"step": "initializing", "message": "Creating research job..."}
            )
            
            self.active_jobs[job_id] = job
            
            # Step 4: Dispatch to background worker
            try:
                if self.worker and hasattr(self.worker, 'dispatch_async'):
                    # Dispatch asynchronously
                    task_result = await self.worker.dispatch_async(
                        "crawl_and_index",
                        {
                            "job_id": job_id,
                            "user_id": user_id,
                            "company_name": company_name,
                            "query": query,
                            "session_id": session_id,
                            "trace_id": ctx.trace_id
                        }
                    )
                    job.status = "processing"
                    job.progress = {"step": "dispatched", "message": "Research job queued"}
                else:
                    # Fallback: mark as processing (will be handled by agent)
                    job.status = "processing"
                    job.progress = {"step": "processing", "message": "Starting research..."}
                
                self.active_jobs[job_id] = job
                self.circuit_breaker_failures = 0  # Reset on success
                
                return {
                    "job_id": job_id,
                    "status": job.status,
                    "progress": job.progress,
                    "trace_id": ctx.trace_id
                }
                
            except Exception as e:
                logger.error(f"Error dispatching job {job_id}: {e}", exc_info=True)
                self.circuit_breaker_failures += 1
                job.status = "failed"
                job.error = str(e)
                
                if self.circuit_breaker_failures >= self.circuit_breaker_threshold:
                    logger.error("Circuit breaker triggered - too many failures")
                
                return {
                    "job_id": job_id,
                    "status": "failed",
                    "error": str(e),
                    "trace_id": ctx.trace_id
                }
    
    def _validate_request(self, company_name: str, query: str) -> Dict[str, Any]:
        """Validate research request"""
        if not company_name or len(company_name.strip()) < 2:
            return {"valid": False, "error": "Company name must be at least 2 characters"}
        
        if not query or len(query.strip()) < 3:
            return {"valid": False, "error": "Query must be at least 3 characters"}
        
        # Check for malicious input
        if any(char in company_name for char in ['<', '>', '{', '}', '[', ']']):
            return {"valid": False, "error": "Invalid characters in company name"}
        
        return {"valid": True}
    
    def _generate_cache_key(self, company_name: str, query: str) -> str:
        """Generate cache key for research request"""
        key_string = f"{company_name.lower().strip()}:{query.lower().strip()}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _generate_job_id(self, user_id: str, company_name: str, query: str) -> str:
        """Generate unique job ID"""
        timestamp = datetime.utcnow().isoformat()
        key_string = f"{user_id}:{company_name}:{query}:{timestamp}"
        return hashlib.sha256(key_string.encode()).hexdigest()[:16]
    
    def get_job_status(self, job_id: str) -> Optional[ResearchJob]:
        """Get job status"""
        return self.active_jobs.get(job_id)
    
    def update_job_progress(
        self,
        job_id: str,
        step: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ):
        """Update job progress"""
        if job_id in self.active_jobs:
            job = self.active_jobs[job_id]
            job.updated_at = datetime.utcnow()
            job.progress = {
                "step": step,
                "message": message,
                "data": data or {}
            }
            self.active_jobs[job_id] = job
    
    def complete_job(
        self,
        job_id: str,
        result: Dict[str, Any],
        cache_ttl: int = 3600
    ):
        """Mark job as completed and cache result"""
        if job_id in self.active_jobs:
            job = self.active_jobs[job_id]
            job.status = "completed"
            job.result = result
            job.updated_at = datetime.utcnow()
            self.active_jobs[job_id] = job
            
            # Cache result (use asyncio if in async context, otherwise sync)
            cache_key = self._generate_cache_key(job.company_name, job.query)
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.cache_manager.set(cache_key, result, ttl=cache_ttl))
                else:
                    loop.run_until_complete(self.cache_manager.set(cache_key, result, ttl=cache_ttl))
            except:
                # Fallback: try sync cache if available
                if hasattr(self.cache_manager, 'set_sync'):
                    self.cache_manager.set_sync(cache_key, result, ttl=cache_ttl)
            
            logger.info(f"Job {job_id} completed successfully")
    
    def fail_job(self, job_id: str, error: str):
        """Mark job as failed"""
        if job_id in self.active_jobs:
            job = self.active_jobs[job_id]
            job.status = "failed"
            job.error = error
            job.updated_at = datetime.utcnow()
            self.active_jobs[job_id] = job
            logger.error(f"Job {job_id} failed: {error}")


# Global orchestrator instance
_orchestrator: Optional[ResearchOrchestrator] = None


def get_orchestrator() -> ResearchOrchestrator:
    """Get global orchestrator instance"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ResearchOrchestrator()
    return _orchestrator


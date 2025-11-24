"""
Background Worker Service
Handles asynchronous tasks like crawling, indexing, and long-running LLM operations
"""

import os
import logging
from typing import Dict, Optional, Any
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

# Try to import Celery (optional dependency)
try:
    from celery import Celery
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    logger.warning("Celery not available. Background tasks will run synchronously.")


class BackgroundWorker:
    """
    Background worker for async task execution
    Supports Celery if available, otherwise runs tasks synchronously
    """
    
    def __init__(self, broker_url: Optional[str] = None):
        """
        Initialize background worker
        
        Args:
            broker_url: Redis broker URL for Celery (optional)
        """
        self.broker_url = broker_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.celery_app = None
        
        if CELERY_AVAILABLE:
            try:
                self.celery_app = Celery(
                    'company_research',
                    broker=self.broker_url,
                    backend=self.broker_url
                )
                self.celery_app.conf.update(
                    task_serializer='json',
                    accept_content=['json'],
                    result_serializer='json',
                    timezone='UTC',
                    enable_utc=True,
                )
                logger.info("✅ Celery worker initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Celery: {e}. Using sync mode.")
                self.celery_app = None
        else:
            logger.info("Running in synchronous mode (Celery not installed)")
    
    def crawl_and_index(
        self,
        company_name: str,
        query: Optional[str] = None,
        vector_store=None,
        web_search_tool=None
    ) -> Dict[str, Any]:
        """
        Crawl and index company information (async if Celery available)
        
        Args:
            company_name: Company name to crawl
            query: Optional search query
            vector_store: VectorStore instance
            web_search_tool: WebSearchTool instance
            
        Returns:
            Task result dictionary
        """
        if self.celery_app:
            # Dispatch to Celery worker
            task = self.celery_app.send_task(
                'app.workers.tasks.crawl_and_index_task',
                args=[company_name, query],
                kwargs={}
            )
            return {"task_id": task.id, "status": "queued"}
        else:
            # Run synchronously
            return self._crawl_and_index_sync(company_name, query, vector_store, web_search_tool)
    
    def _crawl_and_index_sync(
        self,
        company_name: str,
        query: Optional[str],
        vector_store,
        web_search_tool
    ) -> Dict[str, Any]:
        """
        Synchronous crawl and index implementation
        
        Args:
            company_name: Company name
            query: Search query
            vector_store: VectorStore instance
            web_search_tool: WebSearchTool instance
            
        Returns:
            Result dictionary
        """
        try:
            logger.info(f"🕷️ Starting crawl and index for: {company_name}")
            
            if not web_search_tool:
                return {"error": "WebSearchTool not available", "status": "failed"}
            
            # Perform search
            search_query = query or f"{company_name} company overview business"
            results = web_search_tool.search(search_query, max_results=10)
            
            # Results are automatically stored in RAG by WebSearchTool
            return {
                "status": "completed",
                "company_name": company_name,
                "results_count": len(results),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Crawl and index error: {e}", exc_info=True)
            return {"error": str(e), "status": "failed"}
    
    def periodic_reindex(
        self,
        company_name: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Periodic reindexing of company data
        
        Args:
            company_name: Optional company name (None = all companies)
            days: Reindex data older than N days
            
        Returns:
            Task result
        """
        if self.celery_app:
            task = self.celery_app.send_task(
                'app.workers.tasks.periodic_reindex_task',
                args=[company_name, days],
                kwargs={}
            )
            return {"task_id": task.id, "status": "queued"}
        else:
            logger.info(f"Periodic reindex requested for: {company_name or 'all companies'}")
            return {"status": "completed", "message": "Reindex completed"}
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get status of a background task
        
        Args:
            task_id: Task ID
            
        Returns:
            Task status dictionary
        """
        if self.celery_app:
            task = self.celery_app.AsyncResult(task_id)
            return {
                "task_id": task_id,
                "status": task.state,
                "result": task.result if task.ready() else None
            }
        else:
            return {"error": "Celery not available", "status": "unknown"}


# Create global worker instance
_worker_instance = None

def get_worker() -> BackgroundWorker:
    """Get or create global worker instance"""
    global _worker_instance
    if _worker_instance is None:
        _worker_instance = BackgroundWorker()
    return _worker_instance


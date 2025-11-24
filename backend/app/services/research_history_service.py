"""
Service for managing research history logs in MongoDB
"""

from typing import List, Dict, Any
from datetime import datetime
from bson import ObjectId
import logging

from app.database import get_database

logger = logging.getLogger(__name__)

class ResearchHistoryService:
    """Service for research history operations"""
    
    @staticmethod
    async def add_log(
        user_id: str,
        company_name: str,
        log_entry: Dict[str, Any]
    ):
        """Add a log entry to research history"""
        db = get_database()
        if db is None:
            logger.warning("Database not available, skipping log save")
            return
        
        # Find or create research history
        history = await db.research_history.find_one({
            "user_id": ObjectId(user_id),
            "company_name": company_name
        })
        
        log_entry_with_timestamp = {
            **log_entry,
            "timestamp": datetime.utcnow()
        }
        
        if history:
            # Append to existing logs
            await db.research_history.update_one(
                {"_id": history["_id"]},
                {"$push": {"logs": log_entry_with_timestamp}}
            )
        else:
            # Create new history
            await db.research_history.insert_one({
                "user_id": ObjectId(user_id),
                "company_name": company_name,
                "logs": [log_entry_with_timestamp],
                "created_at": datetime.utcnow()
            })
    
    @staticmethod
    async def get_research_history(
        user_id: str,
        company_name: str
    ) -> List[Dict[str, Any]]:
        """Get research history for a company"""
        db = get_database()
        if db is None:
            return []
        
        history = await db.research_history.find_one({
            "user_id": ObjectId(user_id),
            "company_name": company_name
        })
        
        if history:
            return history.get("logs", [])
        return []


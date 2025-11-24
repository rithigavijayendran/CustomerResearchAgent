"""
Service for managing RAG chunks in MongoDB
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from bson import ObjectId
import logging

from app.database import get_database

logger = logging.getLogger(__name__)

class RAGChunkService:
    """Service for RAG chunk operations"""
    
    @staticmethod
    async def save_chunk(
        user_id: str,
        company_name: str,
        text_chunk: str,
        embedding: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Save a RAG chunk"""
        db = get_database()
        if db is None:
            raise ValueError("Database not available")
        
        result = await db.rag_chunks.insert_one({
            "user_id": ObjectId(user_id),
            "company_name": company_name,
            "text_chunk": text_chunk,
            "embedding": embedding,
            "metadata": metadata or {},
            "created_at": datetime.utcnow()
        })
        
        return str(result.inserted_id)
    
    @staticmethod
    async def get_chunks_for_company(
        user_id: str,
        company_name: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get RAG chunks for a company"""
        db = get_database()
        if db is None:
            return []
        
        chunks = []
        async for chunk in db.rag_chunks.find({
            "user_id": ObjectId(user_id),
            "company_name": company_name
        }).limit(limit):
            chunks.append({
                "id": str(chunk["_id"]),
                "text_chunk": chunk["text_chunk"],
                "embedding": chunk.get("embedding"),
                "metadata": chunk.get("metadata", {})
            })
        
        return chunks
    
    @staticmethod
    async def delete_chunks_for_company(
        user_id: str,
        company_name: str
    ):
        """Delete all RAG chunks for a company"""
        db = get_database()
        if db is None:
            return
        
        await db.rag_chunks.delete_many({
            "user_id": ObjectId(user_id),
            "company_name": company_name
        })


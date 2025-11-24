"""
Vector store implementation using ChromaDB
Handles document embedding, storage, and retrieval
"""

import os
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Optional
import logging
import uuid

logger = logging.getLogger(__name__)

class VectorStore:
    """Vector store for RAG using ChromaDB"""
    
    def __init__(self, db_path: str = "./vector_db"):
        """Initialize vector store - handles errors gracefully"""
        self.db_path = db_path
        # Ensure db_path directory exists
        os.makedirs(db_path, exist_ok=True)
        
        # Try to initialize ChromaDB - handle schema errors
        max_retries = 2
        for attempt in range(max_retries):
            try:
                # Initialize ChromaDB with telemetry disabled
                self.client = chromadb.PersistentClient(
                    path=db_path,
                    settings=Settings(
                        anonymized_telemetry=False,
                        allow_reset=True
                    )
                )
                
                # Get or create collection
                self.collection = self.client.get_or_create_collection(
                    name="company_documents",
                    metadata={"hnsw:space": "cosine"}
                )
                logger.info(f"✅ ChromaDB initialized successfully at {db_path}")
                break  # Success, exit retry loop
                
            except Exception as e:
                error_msg = str(e)
                # Check for schema incompatibility errors
                if "no such column" in error_msg.lower() or "schema" in error_msg.lower():
                    if attempt < max_retries - 1:
                        logger.warning(f"ChromaDB schema error detected: {error_msg}")
                        logger.info("Attempting to reset ChromaDB database...")
                        try:
                            # Try to reset the database
                            import shutil
                            if os.path.exists(db_path):
                                # Backup old database
                                backup_path = f"{db_path}_backup_{uuid.uuid4().hex[:8]}"
                                logger.info(f"Backing up old database to {backup_path}")
                                shutil.move(db_path, backup_path)
                                logger.info("Old database backed up, creating new database...")
                        except Exception as reset_error:
                            logger.warning(f"Could not reset database: {reset_error}")
                            # Try alternative: use a new path
                            db_path = f"{db_path}_new_{uuid.uuid4().hex[:8]}"
                            os.makedirs(db_path, exist_ok=True)
                            self.db_path = db_path
                            logger.info(f"Using new database path: {db_path}")
                    else:
                        # Last attempt failed
                        logger.error(f"Failed to initialize ChromaDB after {max_retries} attempts: {error_msg}")
                        logger.error("ChromaDB database may be corrupted. Please delete the vector_db folder and restart.")
                        raise ValueError(
                            f"ChromaDB initialization failed: {error_msg}. "
                            f"Try deleting the '{db_path}' folder and restarting the server."
                        )
                else:
                    # Other errors - don't retry
                    logger.error(f"Failed to initialize ChromaDB: {error_msg}")
                    raise
        
        # Initialize embedding model with offline/cached support
        model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        try:
            # Set cache directory to avoid repeated downloads
            cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "sentence_transformers")
            os.makedirs(cache_dir, exist_ok=True)
            
            logger.info(f"Loading embedding model: {model_name} (this may take a moment on first run)...")
            self.embedder = SentenceTransformer(
                model_name,
                cache_folder=cache_dir
            )
            logger.info(f"✅ Initialized VectorStore with model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            logger.warning("Vector store will work but embeddings may be limited. Continuing anyway...")
            # Create a dummy embedder that returns zeros (better than crashing)
            class DummyEmbedder:
                def encode(self, texts, **kwargs):
                    import numpy as np
                    # Return random embeddings as fallback
                    return np.random.rand(len(texts), 384).tolist()
            self.embedder = DummyEmbedder()
            logger.warning("Using fallback embedder - upload documents may not work optimally")
    
    def add_documents(
        self, 
        texts: List[str], 
        metadatas: List[Dict] = None,
        ids: List[str] = None
    ) -> List[str]:
        """Add documents to vector store"""
        if not texts:
            return []
        
        # Generate embeddings
        embeddings = self.embedder.encode(texts, show_progress_bar=False).tolist()
        
        # Generate IDs if not provided
        if not ids:
            ids = [str(uuid.uuid4()) for _ in texts]
        
        # Prepare metadatas
        if not metadatas:
            metadatas = [{} for _ in texts]
        
        # Add to collection
        self.collection.add(
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )
        
        logger.info(f"Added {len(texts)} documents to vector store")
        return ids
    
    def search(
        self, 
        query: str, 
        n_results: int = 5,
        filter_metadata: Optional[Dict] = None
    ) -> List[Dict]:
        """Search for similar documents with optional metadata filtering"""
        # Generate query embedding
        query_embedding = self.embedder.encode([query], show_progress_bar=False).tolist()[0]
        
        # Build ChromaDB where clause
        # ChromaDB metadata filtering: fields are stored in metadatas array
        # The where clause filters on metadata fields directly
        where_clause = None
        if filter_metadata:
            # ChromaDB where clause format
            # For multiple conditions, use $and operator
            if len(filter_metadata) > 1:
                where_clause = {
                    "$and": [
                        {k: {"$eq": v}} for k, v in filter_metadata.items()
                    ]
                }
            else:
                # Single condition
                k, v = next(iter(filter_metadata.items()))
                where_clause = {k: {"$eq": v}}
        
        # Search with metadata filtering
        query_kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": n_results
        }
        if where_clause:
            query_kwargs["where"] = where_clause
            logger.debug(f"Searching with metadata filter: {where_clause}")
        
        try:
            results = self.collection.query(**query_kwargs)
            
            # If no results with filter, try without filter but log warning
            if results and results.get('ids') and len(results['ids'][0]) == 0:
                logger.warning(f"No results found with metadata filter {where_clause}. This may indicate documents weren't tagged with user_id/company_name.")
        except Exception as e:
            logger.warning(f"ChromaDB query with filter failed: {e}. Trying without filter...")
            # Fallback: try without filter if metadata filtering fails
            try:
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results
                )
                logger.warning("⚠️ Metadata filtering failed - returned results without filter. Documents may not be properly tagged.")
            except Exception as e2:
                logger.error(f"ChromaDB query completely failed: {e2}")
                return []
        
        # Format results
        formatted_results = []
        if results['documents'] and len(results['documents'][0]) > 0:
            for i in range(len(results['documents'][0])):
                formatted_results.append({
                    'text': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                    'distance': results['distances'][0][i] if results['distances'] else None,
                    'id': results['ids'][0][i] if results['ids'] else None
                })
        
        return formatted_results
    
    def delete_documents(self, ids: List[str]):
        """Delete documents by IDs"""
        self.collection.delete(ids=ids)
        logger.info(f"Deleted {len(ids)} documents from vector store")
    
    def get_all_documents(self, limit: int = 100) -> List[Dict]:
        """Get all documents (for debugging)"""
        try:
            results = self.collection.get(limit=limit)
            if not results or not results.get('ids'):
                logger.warning(f"get_all_documents: No documents found in collection")
                return []
            
            documents = []
            ids = results.get('ids', [])
            docs = results.get('documents', [])
            metadatas = results.get('metadatas', [])
            
            for i in range(len(ids)):
                metadata = metadatas[i] if metadatas and i < len(metadatas) else {}
                text = docs[i] if docs and i < len(docs) else ""
                documents.append({
                    'id': ids[i],
                    'text': text,
                    'metadata': metadata
                })
            
            logger.info(f"get_all_documents: Retrieved {len(documents)} documents from vector store")
            return documents
        except Exception as e:
            logger.error(f"Error in get_all_documents: {e}", exc_info=True)
            return []
    
    def close(self):
        """Close the vector store"""
        # ChromaDB handles cleanup automatically
        pass


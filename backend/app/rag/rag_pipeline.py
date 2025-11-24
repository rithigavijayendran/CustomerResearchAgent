"""
Complete RAG pipeline orchestrator
Coordinates document processing, embedding, storage, and retrieval
"""

import os
from typing import List, Dict, Optional
import logging
from pathlib import Path

from app.rag.document_processor import DocumentProcessor
from app.rag.vector_store import VectorStore

logger = logging.getLogger(__name__)

class RAGPipeline:
    """Complete RAG pipeline"""
    
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
        self.processor = DocumentProcessor()
        self.chunk_size = int(os.getenv("MAX_CHUNK_SIZE", "1000"))
        self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "200"))
    
    def ingest_document(
        self, 
        file_path: str, 
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Ingest a document into the RAG system"""
        try:
            # Extract text
            logger.info(f"Extracting text from {file_path}")
            raw_text = self.processor.extract_text(file_path)
            
            # Clean text
            cleaned_text = self.processor.clean_text(raw_text)
            
            # Chunk text
            chunks = self.processor.chunk_text(
                cleaned_text, 
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap
            )
            
            # Prepare metadata
            file_metadata = metadata or {}
            file_metadata.update({
                'source_file': Path(file_path).name,
                'source_type': 'uploaded_document'
            })
            
            # Add chunks to vector store
            texts = [chunk['text'] for chunk in chunks]
            metadatas = [
                {**file_metadata, 'chunk_index': i, 'total_chunks': len(chunks)}
                for i in range(len(chunks))
            ]
            
            chunk_ids = self.vector_store.add_documents(
                texts=texts,
                metadatas=metadatas
            )
            
            return {
                'status': 'success',
                'chunks_processed': len(chunks),
                'chunk_ids': chunk_ids,
                'file_name': Path(file_path).name
            }
        
        except Exception as e:
            logger.error(f"Error ingesting document {file_path}: {e}")
            raise
    
    def retrieve(
        self, 
        query: str, 
        n_results: int = 5,
        filter_metadata: Optional[Dict] = None
    ) -> List[Dict]:
        """Retrieve relevant documents for a query"""
        results = self.vector_store.search(
            query=query,
            n_results=n_results,
            filter_metadata=filter_metadata
        )
        
        # Format results with relevance scores
        formatted = []
        for result in results:
            formatted.append({
                'text': result['text'],
                'metadata': result['metadata'],
                'relevance_score': 1 - result['distance'] if result['distance'] else 0.0,
                'source': result['metadata'].get('source_file', 'unknown'),
                'source_type': result['metadata'].get('source_type', 'unknown')
            })
        
        return formatted
    
    def retrieve_for_company(
        self, 
        company_name: str, 
        query: str, 
        n_results: int = 5,
        user_id: str = None,
        filter_by_company: bool = True
    ) -> List[Dict]:
        """Retrieve documents specifically for a company and user"""
        try:
            # Combine company name with query for better context
            enhanced_query = f"{company_name} {query}"
            
            # Build metadata filter
            filter_metadata = None
            if filter_by_company and user_id:
                # CRITICAL: Only get documents uploaded by this user for this company
                filter_metadata = {
                    'user_id': user_id,
                    'company_name': company_name
                }
                logger.info(f"Filtering documents: user_id={user_id}, company_name={company_name}")
            elif filter_by_company:
                # Filter by company only (if user_id not available)
                filter_metadata = {
                    'company_name': company_name
                }
                logger.info(f"Filtering documents by company_name={company_name}")
            
            return self.retrieve(enhanced_query, n_results=n_results, filter_metadata=filter_metadata)
        except Exception as e:
            logger.warning(f"RAG retrieval failed: {e} - returning empty results")
            return []  # Return empty list instead of crashing


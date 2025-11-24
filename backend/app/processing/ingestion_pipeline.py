"""
Complete Ingestion Pipeline
Orchestrates: Preprocessing → Chunking → Scoring → Embedding → Storage
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime

from app.processing.preprocessor import DocumentPreprocessor
from app.processing.chunker import DocumentChunker
from app.processing.scorer import DocumentScorer
from app.rag.vector_store import VectorStore
from app.llm.llm_factory import LLMFactory

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """
    Complete ingestion pipeline following the architecture:
    1. Preprocessing & Normalization
    2. Document Chunking
    3. Document Scoring
    4. Post-Processing LLM Layer (Gemini Pro)
    5. Embedding & Vector Storage
    """
    
    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        llm_engine=None,
        chunk_size: int = 800,
        chunk_overlap: int = 100
    ):
        self.vector_store = vector_store
        self.llm_engine = llm_engine or LLMFactory.create_llm_engine()
        
        # Pipeline components
        self.preprocessor = DocumentPreprocessor()
        self.chunker = DocumentChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.scorer = DocumentScorer()
        
    async def ingest_documents(
        self,
        documents: List[Dict[str, Any]],
        user_id: str,
        company_name: str,
        query: Optional[str] = None,
        source_type: str = "web_search"
    ) -> List[Dict[str, Any]]:
        """
        Complete ingestion pipeline
        
        Args:
            documents: List of raw documents with url, content, etc.
            user_id: User ID for metadata
            company_name: Company name for metadata
            query: Original query for context
            source_type: Type of source (web_search, uploaded_document, etc.)
            
        Returns:
            List of processed chunks with embeddings and metadata
        """
        processed_chunks = []
        
        for doc_idx, doc in enumerate(documents):
            try:
                # Step 1: Preprocessing & Normalization
                logger.debug(f"Preprocessing document {doc_idx + 1}/{len(documents)}")
                preprocessed = self.preprocessor.preprocess(
                    content=doc.get("content", ""),
                    url=doc.get("url", ""),
                    title=doc.get("title", "")
                )
                
                if not preprocessed.get("text"):
                    logger.warning(f"Skipping document {doc_idx} - no content after preprocessing")
                    continue
                
                # Step 2: Document Chunking
                logger.debug(f"Chunking document {doc_idx + 1}")
                chunks = self.chunker.chunk(
                    text=preprocessed["text"],
                    metadata={
                        "url": doc.get("url", ""),
                        "title": preprocessed.get("title", ""),
                        "source": doc.get("source", source_type),
                        "query": query,
                        "company": company_name,
                        "user_id": user_id,
                        "retrieved_at": datetime.utcnow().isoformat()
                    }
                )
                
                # Step 3: Document Scoring
                logger.debug(f"Scoring {len(chunks)} chunks from document {doc_idx + 1}")
                scored_chunks = []
                for chunk in chunks:
                    score = self.scorer.score(
                        chunk=chunk,
                        query=query,
                        company=company_name,
                        source_type=source_type
                    )
                    chunk["score"] = score
                    chunk["metadata"]["score"] = score
                    scored_chunks.append(chunk)
                
                # Step 4: Post-Processing LLM Layer (Gemini Pro)
                logger.debug(f"Post-processing {len(scored_chunks)} chunks with LLM")
                llm_processed = await self._post_process_with_llm(
                    chunks=scored_chunks,
                    company=company_name,
                    query=query
                )
                
                # Step 5: Embedding & Vector Storage
                logger.debug(f"Storing {len(llm_processed)} processed chunks in vector store")
                stored_chunks = await self._store_in_vector_db(
                    chunks=llm_processed,
                    user_id=user_id,
                    company_name=company_name
                )
                
                processed_chunks.extend(stored_chunks)
                
            except Exception as e:
                logger.error(f"Error processing document {doc_idx}: {e}", exc_info=True)
                continue
        
        logger.info(f"✅ Ingestion complete: {len(processed_chunks)} chunks processed")
        return processed_chunks
    
    async def _post_process_with_llm(
        self,
        chunks: List[Dict[str, Any]],
        company: str,
        query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Post-process chunks with Gemini Pro:
        - Summarization (2-3 sentences)
        - Deduplication
        - Fact extraction
        - Confidence scoring
        - Source attribution
        """
        processed = []
        
        # Process in batches to avoid token limits
        batch_size = 5
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            
            try:
                # Create prompt for LLM post-processing
                prompt = self._create_post_processing_prompt(batch, company, query)
                
                # Call Gemini Pro
                response = await self.llm_engine.generate_structured(
                    prompt=prompt,
                    schema={
                        "type": "object",
                        "properties": {
                            "summaries": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "chunk_id": {"type": "string"},
                                        "summary": {"type": "string"},
                                        "key_facts": {"type": "array", "items": {"type": "string"}},
                                        "confidence": {"type": "number"},
                                        "sources": {"type": "array", "items": {"type": "string"}}
                                    }
                                }
                            }
                        }
                    }
                )
                
                # Merge LLM results back into chunks
                if response and "summaries" in response:
                    for llm_result in response["summaries"]:
                        chunk_id = llm_result.get("chunk_id")
                        matching_chunk = next(
                            (c for c in batch if c.get("chunk_id") == chunk_id),
                            None
                        )
                        if matching_chunk:
                            matching_chunk["llm_summary"] = llm_result.get("summary", "")
                            matching_chunk["key_facts"] = llm_result.get("key_facts", [])
                            matching_chunk["confidence"] = llm_result.get("confidence", 0.5)
                            matching_chunk["metadata"]["llm_processed"] = True
                            matching_chunk["metadata"]["llm_confidence"] = llm_result.get("confidence", 0.5)
                            processed.append(matching_chunk)
                        else:
                            # Fallback: use original chunk
                            processed.append(matching_chunk)
                else:
                    # Fallback: use original chunks
                    processed.extend(batch)
                    
            except Exception as e:
                logger.error(f"Error in LLM post-processing: {e}", exc_info=True)
                # Fallback: use original chunks
                processed.extend(batch)
        
        return processed
    
    def _create_post_processing_prompt(
        self,
        chunks: List[Dict[str, Any]],
        company: str,
        query: Optional[str] = None
    ) -> str:
        """Create prompt for LLM post-processing"""
        chunks_text = "\n\n".join([
            f"Chunk {i+1} (ID: {chunk.get('chunk_id', 'unknown')}):\n{chunk.get('text', '')}"
            for i, chunk in enumerate(chunks)
        ])
        
        prompt = f"""You are a research assistant processing information about {company}.

Process the following text chunks and provide:
1. A 2-3 sentence summary for each chunk
2. Key facts extracted (revenue, CEO, location, products, etc.)
3. Confidence score (0.0-1.0) based on source credibility and information clarity
4. Source attribution

Chunks to process:
{chunks_text}

{f"Original query: {query}" if query else ""}

Return structured JSON with summaries, key_facts, confidence, and sources for each chunk."""
        
        return prompt
    
    async def _store_in_vector_db(
        self,
        chunks: List[Dict[str, Any]],
        user_id: str,
        company_name: str
    ) -> List[Dict[str, Any]]:
        """Store processed chunks in vector database"""
        if not self.vector_store:
            logger.warning("No vector store available - skipping storage")
            return chunks
        
        stored = []
        for chunk in chunks:
            try:
                # Prepare metadata
                metadata = {
                    **chunk.get("metadata", {}),
                    "user_id": user_id,
                    "company_name": company_name,
                    "chunk_id": chunk.get("chunk_id", ""),
                    "score": chunk.get("score", 0.0),
                    "confidence": chunk.get("confidence", chunk.get("metadata", {}).get("llm_confidence", 0.5)),
                    "llm_summary": chunk.get("llm_summary", ""),
                    "key_facts": chunk.get("key_facts", []),
                    "stored_at": datetime.utcnow().isoformat()
                }
                
                # Use LLM summary if available, otherwise use original text
                text_to_embed = chunk.get("llm_summary") or chunk.get("text", "")
                
                # Store in vector database
                chunk_id = self.vector_store.add_document(
                    text=text_to_embed,
                    metadata=metadata,
                    document_id=chunk.get("chunk_id")
                )
                
                chunk["stored_chunk_id"] = chunk_id
                stored.append(chunk)
                
            except Exception as e:
                logger.error(f"Error storing chunk: {e}", exc_info=True)
                continue
        
        return stored


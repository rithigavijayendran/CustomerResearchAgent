"""
Document Chunker Module
Breaks cleaned text into semantic chunks optimized for embeddings
"""

import re
import logging
from typing import List, Dict, Optional
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class DocumentChunker:
    """
    Chunks documents into optimal sizes for embeddings
    Uses overlap strategy and preserves semantic boundaries
    """
    
    def __init__(
        self,
        chunk_size: int = 800,
        chunk_overlap: int = 100,
        min_chunk_size: int = 200
    ):
        """
        Initialize chunker
        
        Args:
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks in characters
            min_chunk_size: Minimum chunk size to keep
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
    
    def chunk(
        self,
        text: str,
        metadata: Optional[Dict] = None,
        url: Optional[str] = None,
        query: Optional[str] = None
    ) -> List[Dict]:
        """
        Chunk text into semantic pieces
        
        Args:
            text: Text to chunk
            metadata: Optional metadata to attach to chunks
            url: Source URL
            query: Original query that led to this content
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        if not text or len(text.strip()) < self.min_chunk_size:
            logger.debug("Text too short to chunk")
            return []
        
        try:
            # Strategy 1: Try to chunk by paragraphs (best for semantic boundaries)
            chunks = self._chunk_by_paragraphs(text, metadata, url, query)
            
            # Strategy 2: If paragraph chunking produces too large chunks, use sentence-based
            if chunks and any(len(chunk['text']) > self.chunk_size * 1.5 for chunk in chunks):
                logger.debug("Some chunks too large, using sentence-based chunking")
                chunks = self._chunk_by_sentences(text, metadata, url, query)
            
            # Strategy 3: If still too large, use character-based with overlap
            if chunks and any(len(chunk['text']) > self.chunk_size * 2 for chunk in chunks):
                logger.debug("Using character-based chunking with overlap")
                chunks = self._chunk_with_overlap(text, metadata, url, query)
            
            # Filter out chunks that are too small
            chunks = [chunk for chunk in chunks if len(chunk['text']) >= self.min_chunk_size]
            
            logger.info(f"Created {len(chunks)} chunks from text ({len(text)} chars)")
            return chunks
            
        except Exception as e:
            logger.error(f"Chunking error: {e}", exc_info=True)
            return []
    
    def _chunk_by_paragraphs(
        self,
        text: str,
        metadata: Optional[Dict],
        url: Optional[str],
        query: Optional[str]
    ) -> List[Dict]:
        """
        Chunk by paragraphs (preserves semantic boundaries)
        
        Args:
            text: Text to chunk
            metadata: Metadata
            url: Source URL
            query: Query
            
        Returns:
            List of chunks
        """
        # Split by double newlines (paragraphs)
        paragraphs = re.split(r'\n\s*\n', text)
        
        chunks = []
        current_chunk = ""
        chunk_index = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # If adding this paragraph would exceed chunk size, save current chunk
            if current_chunk and len(current_chunk) + len(para) > self.chunk_size:
                if len(current_chunk) >= self.min_chunk_size:
                    chunks.append(self._create_chunk(
                        current_chunk,
                        chunk_index,
                        metadata,
                        url,
                        query,
                        len(chunks)
                    ))
                    chunk_index += 1
                
                # Start new chunk with overlap
                if self.chunk_overlap > 0 and current_chunk:
                    overlap_text = current_chunk[-self.chunk_overlap:]
                    current_chunk = overlap_text + "\n\n" + para
                else:
                    current_chunk = para
            else:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
        
        # Add final chunk
        if current_chunk and len(current_chunk) >= self.min_chunk_size:
            chunks.append(self._create_chunk(
                current_chunk,
                chunk_index,
                metadata,
                url,
                query,
                len(chunks)
            ))
        
        return chunks
    
    def _chunk_by_sentences(
        self,
        text: str,
        metadata: Optional[Dict],
        url: Optional[str],
        query: Optional[str]
    ) -> List[Dict]:
        """
        Chunk by sentences (fallback when paragraphs are too large)
        
        Args:
            text: Text to chunk
            metadata: Metadata
            url: Source URL
            query: Query
            
        Returns:
            List of chunks
        """
        # Split by sentence endings
        sentences = re.split(r'([.!?]\s+)', text)
        
        # Recombine sentences with their punctuation
        sentences = [sentences[i] + (sentences[i+1] if i+1 < len(sentences) else '') 
                     for i in range(0, len(sentences), 2)]
        
        chunks = []
        current_chunk = ""
        chunk_index = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            if current_chunk and len(current_chunk) + len(sentence) > self.chunk_size:
                if len(current_chunk) >= self.min_chunk_size:
                    chunks.append(self._create_chunk(
                        current_chunk,
                        chunk_index,
                        metadata,
                        url,
                        query,
                        len(chunks)
                    ))
                    chunk_index += 1
                
                # Start new chunk with overlap
                if self.chunk_overlap > 0 and current_chunk:
                    overlap_text = current_chunk[-self.chunk_overlap:]
                    current_chunk = overlap_text + " " + sentence
                else:
                    current_chunk = sentence
            else:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
        
        # Add final chunk
        if current_chunk and len(current_chunk) >= self.min_chunk_size:
            chunks.append(self._create_chunk(
                current_chunk,
                chunk_index,
                metadata,
                url,
                query,
                len(chunks)
            ))
        
        return chunks
    
    def _chunk_with_overlap(
        self,
        text: str,
        metadata: Optional[Dict],
        url: Optional[str],
        query: Optional[str]
    ) -> List[Dict]:
        """
        Character-based chunking with overlap (last resort)
        
        Args:
            text: Text to chunk
            metadata: Metadata
            url: Source URL
            query: Query
            
        Returns:
            List of chunks
        """
        chunks = []
        start = 0
        chunk_index = 0
        
        while start < len(text):
            end = start + self.chunk_size
            
            # Try to break at word boundary
            if end < len(text):
                # Look for last space or newline before end
                last_space = text.rfind(' ', start, end)
                last_newline = text.rfind('\n', start, end)
                break_point = max(last_space, last_newline)
                
                if break_point > start:
                    end = break_point
            
            chunk_text = text[start:end].strip()
            
            if len(chunk_text) >= self.min_chunk_size:
                chunks.append(self._create_chunk(
                    chunk_text,
                    chunk_index,
                    metadata,
                    url,
                    query,
                    len(chunks)
                ))
                chunk_index += 1
            
            # Move start with overlap
            start = end - self.chunk_overlap if self.chunk_overlap > 0 else end
        
        return chunks
    
    def _create_chunk(
        self,
        text: str,
        chunk_index: int,
        metadata: Optional[Dict],
        url: Optional[str],
        query: Optional[str],
        total_chunks: int
    ) -> Dict:
        """
        Create a chunk dictionary with metadata
        
        Args:
            text: Chunk text
            chunk_index: Index of this chunk
            metadata: Source metadata
            url: Source URL
            query: Query
            total_chunks: Total number of chunks
            
        Returns:
            Chunk dictionary
        """
        chunk_metadata = {
            "chunk_id": str(uuid.uuid4()),
            "chunk_index": chunk_index,
            "total_chunks": total_chunks + 1,
            "url": url,
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "char_count": len(text),
            "word_count": len(text.split())
        }
        
        # Merge with source metadata
        if metadata:
            chunk_metadata.update(metadata)
        
        return {
            "text": text,
            "metadata": chunk_metadata
        }


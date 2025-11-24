"""
Preprocessing & Normalization Module
Cleans raw HTML/text into usable chunks with boilerplate removal, language detection, and normalization
"""

import re
import logging
from typing import Dict, Optional, List
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Try to import trafilatura (optional dependency)
try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError as e:
    TRAFILATURA_AVAILABLE = False
    logger.warning(f"trafilatura not available: {e}. Will use BeautifulSoup fallback.")


class DocumentPreprocessor:
    """
    Preprocessing pipeline for web content and documents
    Handles HTML->text conversion, boilerplate removal, language detection, and normalization
    """
    
    def __init__(self):
        """Initialize preprocessor"""
        self.min_text_length = 100  # Minimum text length to consider valid
        self.max_text_length = 50000  # Maximum text length to process
    
    def preprocess(self, content: str, content_type: str = "html", url: Optional[str] = None) -> Dict:
        """
        Main preprocessing method
        
        Args:
            content: Raw content (HTML, text, markdown)
            content_type: Type of content ("html", "text", "markdown")
            url: Optional URL for metadata
            
        Returns:
            Dictionary with cleaned text and metadata
        """
        try:
            # Step 1: Extract text based on content type
            if content_type == "html":
                extracted_text = self._extract_from_html(content, url)
            elif content_type == "markdown":
                extracted_text = self._extract_from_markdown(content)
            else:
                extracted_text = self._extract_from_text(content)
            
            if not extracted_text or len(extracted_text.strip()) < self.min_text_length:
                logger.warning(f"Extracted text too short: {len(extracted_text) if extracted_text else 0} chars")
                return {
                    "text": "",
                    "metadata": {
                        "url": url,
                        "language": "unknown",
                        "word_count": 0,
                        "processed_at": datetime.now().isoformat()
                    }
                }
            
            # Step 2: Normalize text
            normalized_text = self._normalize_text(extracted_text)
            
            # Step 3: Detect language
            language = self._detect_language(normalized_text)
            
            # Step 4: Extract metadata
            metadata = self._extract_metadata(normalized_text, url, language)
            
            # Step 5: Remove duplicates and low-quality content
            cleaned_text = self._remove_low_quality_content(normalized_text)
            
            return {
                "text": cleaned_text[:self.max_text_length],  # Limit length
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Preprocessing error: {e}", exc_info=True)
            return {
                "text": "",
                "metadata": {
                    "url": url,
                    "language": "unknown",
                    "error": str(e),
                    "processed_at": datetime.now().isoformat()
                }
            }
    
    def _extract_from_html(self, html: str, url: Optional[str] = None) -> str:
        """
        Extract clean text from HTML using multiple strategies
        
        Args:
            html: Raw HTML content
            url: Optional URL for context
            
        Returns:
            Clean extracted text
        """
        # Strategy 1: Use trafilatura (best for readability extraction)
        if TRAFILATURA_AVAILABLE:
            try:
                extracted = trafilatura.extract(html, include_comments=False, include_tables=True)
                if extracted and len(extracted) > self.min_text_length:
                    return extracted
            except Exception as e:
                logger.debug(f"Trafilatura extraction failed: {e}")
        
        # Strategy 2: Use BeautifulSoup with semantic extraction
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'advertisement']):
                element.decompose()
            
            # Try to find main content
            main_content = (
                soup.find('main') or
                soup.find('article') or
                soup.find('div', class_=lambda x: x and ('content' in x.lower() or 'main' in x.lower() or 'article' in x.lower())) or
                soup.find('body')
            )
            
            if main_content:
                text = main_content.get_text(separator=' ', strip=True)
                if len(text) > self.min_text_length:
                    return text
        except Exception as e:
            logger.debug(f"BeautifulSoup extraction failed: {e}")
        
        # Strategy 3: Fallback - extract all text
        try:
            soup = BeautifulSoup(html, 'html.parser')
            for element in soup(['script', 'style']):
                element.decompose()
            text = soup.get_text(separator=' ', strip=True)
            return text
        except Exception as e:
            logger.debug(f"Fallback extraction failed: {e}")
            return ""
    
    def _extract_from_markdown(self, markdown: str) -> str:
        """
        Extract text from markdown
        
        Args:
            markdown: Markdown content
            
        Returns:
            Clean text
        """
        # Remove markdown syntax but keep content
        text = re.sub(r'#{1,6}\s+', '', markdown)  # Remove headers
        text = re.sub(r'\*\*([^\*]+)\*\*', r'\1', text)  # Remove bold
        text = re.sub(r'\*([^\*]+)\*', r'\1', text)  # Remove italic
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)  # Remove links
        text = re.sub(r'`([^`]+)`', r'\1', text)  # Remove code
        text = re.sub(r'```[^`]+```', '', text, flags=re.DOTALL)  # Remove code blocks
        
        return text.strip()
    
    def _extract_from_text(self, text: str) -> str:
        """
        Clean plain text
        
        Args:
            text: Raw text
            
        Returns:
            Cleaned text
        """
        return text.strip()
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text: whitespace, encoding, special characters
        
        Args:
            text: Raw text
            
        Returns:
            Normalized text
        """
        # Remove URL-encoded fragments
        text = re.sub(r'%[0-9A-Fa-f]{2}', '', text)
        
        # Remove URLs
        text = re.sub(r'https?://[^\s]+', '', text)
        text = re.sub(r'www\.[^\s]+', '', text)
        
        # Remove tracking parameters
        text = re.sub(r'\b(rut|utm_|ref|source|campaign|medium|term|content)=[a-zA-Z0-9]+', '', text, flags=re.IGNORECASE)
        text = re.sub(r'&[a-zA-Z0-9_]+=[a-zA-Z0-9]+', '', text)
        
        # Remove hex tracking IDs
        text = re.sub(r'\b[0-9a-f]{32,}\b', '', text, flags=re.IGNORECASE)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)  # Normalize paragraph breaks
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def _detect_language(self, text: str) -> str:
        """
        Detect language of text (simple heuristic-based)
        
        Args:
            text: Text to analyze
            
        Returns:
            Language code (e.g., "en", "es", "fr")
        """
        # Simple heuristic: check for common English words
        # In production, use langdetect library
        try:
            from langdetect import detect
            return detect(text)
        except:
            # Fallback: check for common patterns
            text_lower = text.lower()
            english_indicators = ['the', 'and', 'is', 'are', 'was', 'were', 'this', 'that']
            if any(word in text_lower for word in english_indicators):
                return "en"
            return "unknown"
    
    def _extract_metadata(self, text: str, url: Optional[str], language: str) -> Dict:
        """
        Extract metadata from processed text
        
        Args:
            text: Processed text
            url: Source URL
            language: Detected language
            
        Returns:
            Metadata dictionary
        """
        word_count = len(text.split())
        char_count = len(text)
        
        # Extract domain from URL
        domain = None
        if url:
            try:
                parsed = urlparse(url)
                domain = parsed.netloc
            except:
                pass
        
        return {
            "url": url,
            "domain": domain,
            "language": language,
            "word_count": word_count,
            "char_count": char_count,
            "processed_at": datetime.now().isoformat()
        }
    
    def _remove_low_quality_content(self, text: str) -> str:
        """
        Remove low-quality content (repetitive, too short, etc.)
        
        Args:
            text: Text to clean
            
        Returns:
            Cleaned text
        """
        # Remove lines that are mostly whitespace or punctuation
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Skip lines that are too short
            if len(line) < 10:
                continue
            
            # Skip lines that are mostly special characters
            if len(re.sub(r'[^\w\s]', '', line)) < len(line) * 0.3:
                continue
            
            # Skip lines that are repetitive (same character repeated)
            if len(set(line)) < 3:
                continue
            
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def extract_structured_data(self, text: str) -> Dict:
        """
        Extract structured data from text (dates, numbers, entities)
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary with extracted structured data
        """
        structured = {
            "dates": [],
            "numbers": [],
            "percentages": [],
            "currencies": []
        }
        
        # Extract dates (simple pattern)
        date_pattern = r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b'
        structured["dates"] = re.findall(date_pattern, text)
        
        # Extract numbers
        number_pattern = r'\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b'
        structured["numbers"] = re.findall(number_pattern, text)
        
        # Extract percentages
        percent_pattern = r'\d+\.?\d*\s*%'
        structured["percentages"] = re.findall(percent_pattern, text)
        
        # Extract currencies (simple pattern)
        currency_pattern = r'\$[\d,]+(?:\.\d{2})?'
        structured["currencies"] = re.findall(currency_pattern, text)
        
        return structured


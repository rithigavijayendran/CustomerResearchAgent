"""
Document Scoring Module
Pre-LLM ranking of chunks by quality, freshness, credibility, and relevance
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class DocumentScorer:
    """
    Scores documents/chunks for quality, freshness, credibility, and relevance
    Used to filter and rank content before LLM processing
    """
    
    def __init__(self):
        """Initialize scorer"""
        # Credible domains (news, official, academic)
        self.credible_domains = {
            'reuters.com', 'bloomberg.com', 'wsj.com', 'ft.com', 'economist.com',
            'nytimes.com', 'washingtonpost.com', 'theguardian.com',
            'forbes.com', 'techcrunch.com', 'wired.com',
            'gov', 'edu', 'org', 'wikipedia.org',
            'linkedin.com', 'crunchbase.com', 'sec.gov'
        }
        
        # Low-quality indicators
        self.low_quality_patterns = [
            r'click here', r'buy now', r'sign up', r'subscribe',
            r'advertisement', r'sponsored', r'promoted',
            r'cookie policy', r'privacy policy', r'terms of service'
        ]
    
    def score(
        self,
        text: str,
        metadata: Dict,
        query: Optional[str] = None
    ) -> Dict:
        """
        Calculate comprehensive score for a document/chunk
        
        Args:
            text: Text content
            metadata: Document metadata (url, timestamp, source, etc.)
            query: Optional query for relevance scoring
            
        Returns:
            Dictionary with scores and total score
        """
        scores = {
            "freshness": self._score_freshness(metadata),
            "credibility": self._score_credibility(metadata),
            "quality": self._score_quality(text, metadata),
            "relevance": self._score_relevance(text, query) if query else 0.5,
            "readability": self._score_readability(text)
        }
        
        # Weighted total score
        weights = {
            "freshness": 0.15,
            "credibility": 0.25,
            "quality": 0.20,
            "relevance": 0.30,
            "readability": 0.10
        }
        
        total_score = sum(scores[key] * weights[key] for key in scores)
        
        return {
            "scores": scores,
            "total_score": round(total_score, 3),
            "scored_at": datetime.now().isoformat()
        }
    
    def _score_freshness(self, metadata: Dict) -> float:
        """
        Score based on how recent the content is
        
        Args:
            metadata: Document metadata
            
        Returns:
            Freshness score (0.0-1.0)
        """
        timestamp = metadata.get("timestamp") or metadata.get("processed_at")
        if not timestamp:
            return 0.5  # Unknown age = medium score
        
        try:
            if isinstance(timestamp, str):
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            else:
                dt = timestamp
            
            age_days = (datetime.now(dt.tzinfo) - dt).days if dt.tzinfo else (datetime.now() - dt.replace(tzinfo=None)).days
            
            # Score based on age
            if age_days < 7:
                return 1.0  # Very fresh
            elif age_days < 30:
                return 0.8  # Recent
            elif age_days < 90:
                return 0.6  # Somewhat recent
            elif age_days < 365:
                return 0.4  # Older
            else:
                return 0.2  # Very old
        except:
            return 0.5
    
    def _score_credibility(self, metadata: Dict) -> float:
        """
        Score based on source credibility
        
        Args:
            metadata: Document metadata
            
        Returns:
            Credibility score (0.0-1.0)
        """
        url = metadata.get("url") or metadata.get("source_url", "")
        domain = metadata.get("domain")
        
        if not domain and url:
            try:
                parsed = urlparse(url)
                domain = parsed.netloc.lower()
            except:
                pass
        
        if not domain:
            return 0.5  # Unknown source
        
        domain_lower = domain.lower()
        
        # Check for credible domains
        for credible in self.credible_domains:
            if credible in domain_lower:
                return 1.0
        
        # Check for low-credibility indicators
        low_cred_patterns = ['blogspot', 'wordpress', 'tumblr', 'medium.com']
        if any(pattern in domain_lower for pattern in low_cred_patterns):
            return 0.3
        
        # Check TLD
        if domain_lower.endswith('.gov') or domain_lower.endswith('.edu'):
            return 0.9
        elif domain_lower.endswith('.org'):
            return 0.7
        elif domain_lower.endswith('.com') or domain_lower.endswith('.net'):
            return 0.6
        else:
            return 0.5
    
    def _score_quality(self, text: str, metadata: Dict) -> float:
        """
        Score based on content quality indicators
        
        Args:
            text: Text content
            metadata: Document metadata
            
        Returns:
            Quality score (0.0-1.0)
        """
        if not text:
            return 0.0
        
        score = 1.0
        
        # Penalize low-quality patterns
        text_lower = text.lower()
        for pattern in self.low_quality_patterns:
            if re.search(pattern, text_lower):
                score -= 0.1
        
        # Penalize very short content
        word_count = len(text.split())
        if word_count < 50:
            score -= 0.3
        elif word_count < 100:
            score -= 0.1
        
        # Penalize very long content (might be noise)
        if len(text) > 50000:
            score -= 0.2
        
        # Reward structured content (lists, paragraphs)
        if text.count('\n\n') > 3:
            score += 0.1
        
        # Penalize excessive repetition
        words = text.split()
        if len(words) > 0:
            unique_ratio = len(set(words)) / len(words)
            if unique_ratio < 0.3:
                score -= 0.3
        
        return max(0.0, min(1.0, score))
    
    def _score_relevance(self, text: str, query: Optional[str]) -> float:
        """
        Score based on relevance to query (simple keyword matching)
        
        Args:
            text: Text content
            query: Search query
            
        Returns:
            Relevance score (0.0-1.0)
        """
        if not query:
            return 0.5
        
        text_lower = text.lower()
        query_lower = query.lower()
        
        # Extract keywords from query
        query_words = set(re.findall(r'\b\w+\b', query_lower))
        query_words = {w for w in query_words if len(w) > 3}  # Filter short words
        
        if not query_words:
            return 0.5
        
        # Count matches
        matches = sum(1 for word in query_words if word in text_lower)
        match_ratio = matches / len(query_words)
        
        return min(1.0, match_ratio * 1.2)  # Boost slightly
    
    def _score_readability(self, text: str) -> float:
        """
        Score based on readability (simple heuristics)
        
        Args:
            text: Text content
            
        Returns:
            Readability score (0.0-1.0)
        """
        if not text:
            return 0.0
        
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return 0.0
        
        # Average sentence length
        avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences)
        
        # Score based on sentence length (optimal: 15-20 words)
        if 10 <= avg_sentence_length <= 25:
            readability = 1.0
        elif 5 <= avg_sentence_length < 10 or 25 < avg_sentence_length <= 35:
            readability = 0.7
        else:
            readability = 0.4
        
        # Check for proper punctuation
        proper_punctuation = sum(1 for s in sentences if s and s[-1] in '.!?')
        punctuation_ratio = proper_punctuation / len(sentences) if sentences else 0
        
        return (readability + punctuation_ratio) / 2
    
    def filter_by_score(self, items: List[Dict], min_score: float = 0.3) -> List[Dict]:
        """
        Filter items by minimum score
        
        Args:
            items: List of items with scores
            min_score: Minimum total score to keep
            
        Returns:
            Filtered and sorted list (highest score first)
        """
        filtered = [
            item for item in items
            if item.get("score", {}).get("total_score", 0) >= min_score
        ]
        
        # Sort by score (highest first)
        filtered.sort(key=lambda x: x.get("score", {}).get("total_score", 0), reverse=True)
        
        return filtered


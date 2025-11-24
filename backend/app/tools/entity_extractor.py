"""
Entity extraction tool
Extracts structured information from text
"""

import re
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class EntityExtractor:
    """Extract entities from text using patterns and LLM"""
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
    
    def extract_entities(self, text: str) -> Dict:
        """Extract entities from text"""
        entities = {
            'company_name': self._extract_company_name(text),
            'revenue': self._extract_revenue(text),
            'headcount': self._extract_headcount(text),
            'products': self._extract_products(text),
            'services': self._extract_services(text),
            'markets': self._extract_markets(text),
            'competitors': self._extract_competitors(text),
            'locations': self._extract_locations(text)
        }
        return entities
    
    def _extract_company_name(self, text: str) -> Optional[str]:
        """Extract company name (simple pattern matching)"""
        # Look for patterns like "Company Name Inc.", "Company Name Ltd."
        patterns = [
            r'([A-Z][a-zA-Z\s&]+)\s+(Inc\.|LLC|Ltd\.|Corp\.|Corporation|Company)',
            r'([A-Z][a-zA-Z\s&]+)\s+is\s+(?:a|an)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None
    
    def _extract_revenue(self, text: str) -> List[str]:
        """Extract revenue mentions"""
        patterns = [
            r'revenue\s+(?:of|is|was)\s+[\$]?([\d,]+\.?\d*)\s*(?:million|billion|M|B)?',
            r'[\$]([\d,]+\.?\d*)\s*(?:million|billion|M|B)?\s+(?:in\s+)?revenue',
        ]
        revenues = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            revenues.extend(matches)
        return list(set(revenues))
    
    def _extract_headcount(self, text: str) -> List[str]:
        """Extract employee count"""
        patterns = [
            r'(\d{1,3}(?:,\d{3})*)\s+employees?',
            r'employs?\s+(\d{1,3}(?:,\d{3})*)',
            r'workforce\s+of\s+(\d{1,3}(?:,\d{3})*)',
        ]
        headcounts = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            headcounts.extend(matches)
        return list(set(headcounts))
    
    def _extract_products(self, text: str) -> List[str]:
        """Extract product mentions"""
        # Simple extraction - in production, use NER or LLM
        products = []
        product_keywords = ['product', 'offers', 'provides', 'sells']
        sentences = re.split(r'[.!?]', text)
        for sentence in sentences:
            if any(keyword in sentence.lower() for keyword in product_keywords):
                # Extract noun phrases (simplified)
                words = sentence.split()
                if len(words) > 2:
                    products.append(' '.join(words[:5]))
        return products[:10]  # Limit results
    
    def _extract_services(self, text: str) -> List[str]:
        """Extract service mentions"""
        services = []
        service_keywords = ['service', 'solutions', 'consulting', 'support']
        sentences = re.split(r'[.!?]', text)
        for sentence in sentences:
            if any(keyword in sentence.lower() for keyword in service_keywords):
                words = sentence.split()
                if len(words) > 2:
                    services.append(' '.join(words[:5]))
        return services[:10]
    
    def _extract_markets(self, text: str) -> List[str]:
        """Extract market/industry mentions"""
        markets = []
        market_keywords = ['market', 'industry', 'sector', 'vertical']
        sentences = re.split(r'[.!?]', text)
        for sentence in sentences:
            if any(keyword in sentence.lower() for keyword in market_keywords):
                words = sentence.split()
                if len(words) > 2:
                    markets.append(' '.join(words[:5]))
        return markets[:10]
    
    def _extract_competitors(self, text: str) -> List[str]:
        """Extract competitor mentions"""
        competitors = []
        competitor_keywords = ['competitor', 'competes with', 'rival', 'vs.', 'versus']
        sentences = re.split(r'[.!?]', text)
        for sentence in sentences:
            if any(keyword in sentence.lower() for keyword in competitor_keywords):
                words = sentence.split()
                if len(words) > 2:
                    competitors.append(' '.join(words[:5]))
        return competitors[:10]
    
    def _extract_locations(self, text: str) -> List[str]:
        """Extract location mentions"""
        # Simple pattern for cities/countries
        patterns = [
            r'(?:in|at|from)\s+([A-Z][a-zA-Z\s]+(?:,\s*[A-Z][a-zA-Z]+)?)',
        ]
        locations = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            locations.extend(matches)
        return list(set(locations))[:10]


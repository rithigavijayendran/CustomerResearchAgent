"""
Conflict detection module
Detects contradictions in gathered information
"""

from typing import List, Dict, Any, Optional
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

class ConflictDetector:
    """Detect conflicts and contradictions in research data"""
    
    def __init__(self):
        self.conflict_keywords = {
            'revenue': ['revenue', 'sales', 'income', 'earnings'],
            'headcount': ['employees', 'headcount', 'workforce', 'staff'],
            'founded': ['founded', 'established', 'started', 'incorporated'],
            'location': ['headquarters', 'based in', 'located in', 'HQ'],
            'products': ['product', 'offers', 'provides'],
            'market': ['market', 'industry', 'sector']
        }
    
    def detect_conflicts(self, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect conflicts across multiple sources - only between DIFFERENT documents"""
        conflicts = []
        
        # Group sources by document/file to avoid false conflicts from same document
        sources_by_document = defaultdict(list)
        for i, source in enumerate(sources):
            metadata = source.get('metadata', {})
            source_file = metadata.get('source_file', '')
            source_url = source.get('source', '') or metadata.get('url', '')
            
            # Create a unique document identifier
            doc_id = source_file if source_file else source_url if source_url else f"source_{i}"
            sources_by_document[doc_id].append(source)
        
        # If all sources are from the same document, skip conflict detection
        if len(sources_by_document) == 1:
            logger.info("All sources from same document - skipping conflict detection")
            return []
        
        # Group by topic, but track which document each value comes from
        topic_data = defaultdict(list)
        
        for doc_id, doc_sources in sources_by_document.items():
            # For each document, extract the best value for each topic
            doc_text = ' '.join([s.get('text', '') for s in doc_sources]).lower()
            metadata = doc_sources[0].get('metadata', {})
            source_type = doc_sources[0].get('source_type', 'unknown')
            source_file = metadata.get('source_file', '')
            source_url = source_file or metadata.get('url', '') or doc_id
            
            # Check each topic
            for topic, keywords in self.conflict_keywords.items():
                if any(keyword in doc_text for keyword in keywords):
                    # Extract value for this topic from the combined document text
                    value = self._extract_value(doc_text, topic)
                    if value and value.strip():
                        topic_data[topic].append({
                            'value': value,
                            'source': source_type,
                            'document_id': doc_id,
                            'source_file': source_file,
                            'source_url': source_url,
                            'metadata': metadata
                        })
        
        # Detect conflicts for each topic - only if values come from DIFFERENT documents
        for topic, values in topic_data.items():
            if len(values) < 2:
                continue
            
            # Group by document to get unique values per document
            values_by_doc = defaultdict(set)
            for v in values:
                values_by_doc[v['document_id']].add(v['value'])
            
            # Only flag conflicts if we have different values from different documents
            if len(values_by_doc) > 1:
                # Get unique values across all documents
                all_unique_values = set()
                for doc_values in values_by_doc.values():
                    all_unique_values.update(doc_values)
                
                # Only create conflict if there are genuinely different values
                if len(all_unique_values) > 1:
                    # For numeric topics, check if values are significantly different
                    if topic in ['revenue', 'headcount', 'founded']:
                        if not self._are_values_significantly_different(topic, all_unique_values):
                            continue  # Skip - values are similar enough
                    
                    conflict = {
                        'topic': topic,
                        'conflicting_values': list(all_unique_values),
                        'sources': values,
                        'severity': self._calculate_severity(topic, all_unique_values)
                    }
                    conflicts.append(conflict)
                    logger.info(f"Detected conflict for {topic}: {len(all_unique_values)} different values from {len(values_by_doc)} documents")
        
        return conflicts
    
    def _extract_value(self, text: str, topic: str) -> Optional[str]:
        """Extract value for a specific topic - improved accuracy"""
        import re
        
        if topic == 'revenue':
            # Look for revenue numbers - be more specific
            patterns = [
                r'(?:revenue|sales|income)[:\s]+(?:of|is|was|were|are)\s+[\$]?([\d,]+\.?\d*)\s*(?:million|billion|M|B|trillion)?',
                r'[\$]([\d,]+\.?\d*)\s*(?:million|billion|M|B|trillion)?\s+(?:in\s+)?(?:annual\s+)?(?:revenue|sales)',
                r'(?:annual\s+)?revenue\s+(?:of\s+)?[\$]?([\d,]+\.?\d*)\s*(?:million|billion|M|B|trillion)?'
            ]
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    # Return the largest/most recent value (usually the most accurate)
                    return matches[-1] if matches else None
        
        elif topic == 'headcount':
            # Look for employee counts - be more specific
            patterns = [
                r'(\d{1,3}(?:,\d{3})*)\s+employees?',
                r'employs?\s+(\d{1,3}(?:,\d{3})*)\s+(?:people|employees|staff)',
                r'workforce\s+(?:of\s+)?(\d{1,3}(?:,\d{3})*)',
                r'approximately\s+(\d{1,3}(?:,\d{3})*)\s+employees?'
            ]
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    # Return the most common or largest value
                    return matches[-1] if matches else None
        
        elif topic == 'founded':
            # Look for founding year
            patterns = [
                r'founded\s+in\s+(\d{4})',
                r'established\s+in\s+(\d{4})',
                r'started\s+in\s+(\d{4})',
                r'incorporated\s+in\s+(\d{4})',
                r'(\d{4})\s+(?:was\s+)?(?:the\s+)?year\s+(?:we\s+)?(?:were\s+)?founded'
            ]
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    # Return the earliest year (most likely founding year)
                    years = [int(m) for m in matches if 1800 <= int(m) <= 2100]
                    if years:
                        return str(min(years))
        
        elif topic == 'location':
            # Extract headquarters location
            patterns = [
                r'headquarters[:\s]+(?:in|at|is\s+in|are\s+in|located\s+in)\s+([A-Z][a-zA-Z\s,]+(?:,\s*[A-Z][a-zA-Z]+)?)',
                r'based\s+in\s+([A-Z][a-zA-Z\s,]+(?:,\s*[A-Z][a-zA-Z]+)?)',
                r'headquartered\s+in\s+([A-Z][a-zA-Z\s,]+(?:,\s*[A-Z][a-zA-Z]+)?)'
            ]
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    loc = match.group(1).strip()
                    # Clean up common false positives
                    if len(loc) > 3 and not any(word in loc.lower() for word in ['the', 'company', 'corporation']):
                        return loc[:50]  # Limit length
        
        # For other topics (products, market), don't extract - too ambiguous
        # Only detect conflicts for factual, verifiable data
        return None
    
    def _are_values_significantly_different(self, topic: str, values: set) -> bool:
        """Check if values are significantly different (not just formatting differences)"""
        import re
        
        if topic == 'revenue':
            # Normalize values and compare
            normalized = []
            for v in values:
                # Remove commas, convert to number
                num_str = re.sub(r'[,\s]', '', str(v))
                try:
                    num = float(num_str)
                    normalized.append(num)
                except:
                    continue
            
            if len(normalized) < 2:
                return True  # Can't compare, assume different
            
            # Check if values differ by more than 10%
            min_val = min(normalized)
            max_val = max(normalized)
            if min_val > 0:
                diff_percent = ((max_val - min_val) / min_val) * 100
                return diff_percent > 10  # More than 10% difference = significant
        
        elif topic == 'headcount':
            # Similar logic for headcount
            normalized = []
            for v in values:
                num_str = re.sub(r'[,\s]', '', str(v))
                try:
                    num = int(num_str)
                    normalized.append(num)
                except:
                    continue
            
            if len(normalized) < 2:
                return True
            
            min_val = min(normalized)
            max_val = max(normalized)
            if min_val > 0:
                diff_percent = ((max_val - min_val) / min_val) * 100
                return diff_percent > 15  # More than 15% difference = significant
        
        elif topic == 'founded':
            # Years should be exact match or very close (within 1-2 years)
            years = []
            for v in values:
                year_str = re.sub(r'[^\d]', '', str(v))
                if year_str and len(year_str) == 4:
                    try:
                        year = int(year_str)
                        if 1800 <= year <= 2100:
                            years.append(year)
                    except:
                        continue
            
            if len(years) < 2:
                return True
            
            # If years differ by more than 2, it's significant
            return (max(years) - min(years)) > 2
        
        return True  # Default: assume different
    
    def _calculate_severity(self, topic: str, values: set) -> str:
        """Calculate conflict severity"""
        if topic in ['revenue', 'headcount', 'founded', 'location']:
            # Factual conflicts are high severity
            return 'high'
        else:
            return 'medium'
    
    def format_conflict_message(self, conflict: Dict[str, Any]) -> str:
        """Format conflict as a user-friendly message - NO URLs, clean formatting"""
        import os
        
        topic = conflict['topic']
        values = conflict['conflicting_values']
        sources = conflict['sources']
        
        # Format topic name nicely
        topic_display = topic.replace('_', ' ').title()
        
        # Group sources by value
        sources_by_value = defaultdict(list)
        for source in sources:
            value = source['value']
            sources_by_value[value].append(source)
        
        message = f"**I'm finding conflicting information about {topic_display}:**\n\n"
        
        for i, value in enumerate(values):
            source_list = sources_by_value[value]
            
            # Create friendly source descriptions (NO URLs)
            friendly_sources = []
            for s in source_list:
                source_file = s.get('source_file', '')
                source_type = s.get('source', 'unknown')
                
                if source_file:
                    # Extract just filename, no path or extension
                    filename = os.path.basename(source_file)
                    filename = os.path.splitext(filename)[0]
                    filename = filename.replace('_', ' ').title()
                    friendly_sources.append(f"Uploaded document ({filename})")
                elif source_type == 'uploaded_document':
                    friendly_sources.append("Uploaded document")
                elif source_type == 'web_search':
                    friendly_sources.append("Web research source")
                else:
                    friendly_sources.append("Research source")
            
            # Get unique friendly sources
            unique_sources = list(set(friendly_sources))
            
            # Create source label
            if len(unique_sources) == 1:
                source_label = unique_sources[0]
            elif len(unique_sources) == 2:
                source_label = f"{unique_sources[0]} and {unique_sources[1]}"
            else:
                source_label = f"{unique_sources[0]}, {unique_sources[1]}, and {len(unique_sources) - 2} other source(s)"
            
            # Format value nicely
            formatted_value = str(value).strip()
            if topic in ['revenue', 'headcount']:
                try:
                    num = float(formatted_value.replace(',', ''))
                    if num >= 1000000:
                        formatted_value = f"${num/1000000:.1f}M" if topic == 'revenue' else f"{int(num/1000000)}M employees"
                    elif num >= 1000:
                        formatted_value = f"${num/1000:.1f}K" if topic == 'revenue' else f"{int(num/1000)}K employees"
                except:
                    pass
            
            message += f"• **{source_label}** reports: {formatted_value}\n\n"
        
        message += "**Should I dig deeper to verify this information, or would you like me to proceed with the most authoritative source?**"
        
        return message


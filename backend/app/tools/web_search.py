"""
Advanced Web Search Tool - Hybrid Search Pipeline
Combines Serper.dev (Google Search), Firecrawl.dev (Deep Scraping), and LLM Intelligence
"""

import os
import json
import time
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.llm.llm_factory import LLMFactory
from app.processing.preprocessor import DocumentPreprocessor
from app.processing.chunker import DocumentChunker
from app.processing.scorer import DocumentScorer

logger = logging.getLogger(__name__)


class WebSearchTool:
    """
    Advanced web search tool with hybrid architecture:
    1. Serper.dev for Google Search API (accurate SERP results)
    2. Firecrawl.dev for deep scraping and readability extraction
    3. LLM post-processing for summarization, deduplication, ranking, and fact extraction
    4. RAG integration for vector storage
    """
    
    def __init__(self, vector_store=None, llm_engine=None):
        """
        Initialize WebSearchTool with API keys and dependencies
        
        Args:
            vector_store: Optional VectorStore instance for RAG integration
            llm_engine: Optional LLM engine instance (defaults to Gemini)
        """
        # API Configuration
        self.serper_api_key = os.getenv("SERPER_API_KEY", "")
        self.firecrawl_api_key = os.getenv("FIRECRAWL_API_KEY", "")
        self.enabled = os.getenv("ENABLE_WEB_SEARCH", "true").lower() == "true"
        
        # API Endpoints
        self.serper_url = "https://google.serper.dev/search"
        self.firecrawl_url = "https://api.firecrawl.dev/v1/scrape"
        
        # Configuration
        self.max_results = 10
        self.top_urls_to_scrape = 5  # Number of top URLs to scrape with Firecrawl
        self.request_timeout = 30  # Timeout for API requests
        self.max_retries = 3  # Maximum retry attempts
        
        # Dependencies
        self.vector_store = vector_store
        self.llm_engine = llm_engine
        if not self.llm_engine:
            try:
                self.llm_engine = LLMFactory.create_llm_engine()
                logger.info("✅ LLM engine initialized for WebSearchTool")
            except Exception as e:
                logger.warning(f"⚠️ Could not initialize LLM engine: {e}. LLM post-processing will be disabled.")
                self.llm_engine = None
        
        # LLM failure tracking (circuit breaker pattern)
        self.llm_failure_count = 0
        self.llm_failure_threshold = 3  # Disable LLM after 3 consecutive failures
        self.llm_disabled = False
        
        # Processing pipeline components
        self.preprocessor = DocumentPreprocessor()
        self.chunker = DocumentChunker(chunk_size=800, chunk_overlap=100)
        self.scorer = DocumentScorer()
        
        # Validate API keys
        if self.enabled:
            if not self.serper_api_key:
                logger.error("❌ SERPER_API_KEY not found. Web search will NOT work. Please set SERPER_API_KEY in .env file.")
                logger.error("   Get a free key from: https://serper.dev")
                # Don't disable completely - allow fallback
            else:
                logger.info("✅ SERPER_API_KEY found - Google Search enabled")
            
            if not self.firecrawl_api_key:
                logger.warning("⚠️ FIRECRAWL_API_KEY not found. Deep scraping will be disabled (will use snippets only).")
                logger.warning("   Get a free key from: https://firecrawl.dev")
            else:
                logger.info("✅ FIRECRAWL_API_KEY found - Deep scraping enabled")
        else:
            logger.warning("⚠️ Web search is DISABLED. Set ENABLE_WEB_SEARCH=true in .env to enable.")
    
    def search(self, query: str, max_results: int = 5) -> List[Dict]:
        """
        Main search method - orchestrates the hybrid search pipeline
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            
        Returns:
            List of search result dictionaries with enhanced data
        """
        if not self.enabled:
            logger.warning("Web search is disabled")
            return []
        
        try:
            logger.info(f"🔍 Starting hybrid search for: {query}")
            
            # Step 1: Search Layer - Get SERP results from Serper
            serp_results = self._search_with_serper(query, max_results)
            
            if not serp_results:
                logger.warning(f"No SERP results found for query: {query}")
                return []
            
            # Step 2: Crawling Layer - Scrape top URLs with Firecrawl
            enriched_results = self._enrich_with_firecrawl(serp_results, query)
            
            # Step 3: Intelligence Layer - LLM post-processing
            processed_results = self._process_with_llm(enriched_results, query)
            
            # Ensure we have results - if LLM processing failed, use enriched results
            if not processed_results or len(processed_results) == 0:
                logger.warning("LLM processing returned no results, using enriched results")
                processed_results = enriched_results
            
            # Step 4: RAG Integration - Store in vector database
            self._store_in_rag(processed_results, query)
            
            logger.info(f"✅ Search completed: {len(processed_results)} results for '{query}'")
            return processed_results
            
        except Exception as e:
            logger.error(f"❌ Web search error for query '{query}': {e}", exc_info=True)
            # Try to return enriched results if available, otherwise return empty
            try:
                if 'enriched_results' in locals() and enriched_results:
                    logger.info(f"Returning {len(enriched_results)} enriched results despite error")
                    return enriched_results
            except:
                pass
            return []
    
    def search_company(self, company_name: str, topic: str = None) -> List[Dict]:
        """
        Search for specific company information
        
        Args:
            company_name: Name of the company to search for
            topic: Optional topic to narrow the search
            
        Returns:
            List of search results related to the company
        """
        if topic:
            query = f"{company_name} {topic}"
        else:
            # Enhanced query for better results
            query = f"{company_name} company overview business products services"
        
        results = self.search(query, max_results=self.max_results)
        
        # Post-process to ensure clean text
        cleaned_results = []
        for result in results:
            cleaned_result = {
                'title': self._clean_text(result.get('title', '')),
                'url': result.get('url', ''),
                'snippet': self._clean_text(result.get('snippet', '')),
                'full_content': self._clean_text(result.get('full_content', '')),
                'source': result.get('source', 'serper + firecrawl'),
                'confidence': result.get('confidence', 0.8),
                'source_type': 'web_search'
            }
            cleaned_results.append(cleaned_result)
        
        return cleaned_results
    
    def fetch_full_content(self, url: str) -> Optional[str]:
        """
        Fetch full content from a URL using Firecrawl
        
        Args:
            url: URL to fetch content from
            
        Returns:
            Full text content of the page, or None if failed
        """
        if not self.firecrawl_api_key:
            logger.warning("FIRECRAWL_API_KEY not available. Cannot fetch full content.")
            return None
        
        try:
            logger.info(f"📥 Fetching full content from: {url}")
            content = self._scrape_with_firecrawl(url)
            return content
        except Exception as e:
            logger.error(f"Failed to fetch content from {url}: {e}")
            return None
    
    # ==================== Search Layer (Serper) ====================
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.exceptions.RequestException, TimeoutError))
    )
    def _search_with_serper(self, query: str, max_results: int) -> List[Dict]:
        """
        Search using Serper.dev Google Search API
        
        Args:
            query: Search query
            max_results: Maximum number of results
            
        Returns:
            List of SERP results with title, snippet, url, source
        """
        if not self.serper_api_key:
            logger.warning("SERPER_API_KEY not available. Using fallback search.")
            return self._fallback_search(query, max_results)
        
        try:
            headers = {
                "X-API-KEY": self.serper_api_key,
                "Content-Type": "application/json"
            }
            
            payload = {
                "q": query,
                "num": max_results
            }
            
            logger.debug(f"🔎 Calling Serper API for: {query}")
            response = requests.post(
                self.serper_url,
                headers=headers,
                json=payload,
                timeout=self.request_timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Extract organic results
            results = []
            organic_results = data.get("organic", [])
            
            for item in organic_results[:max_results]:
                result = {
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "source": item.get("source", "serper"),
                    "position": item.get("position", 0)
                }
                results.append(result)
            
            logger.info(f"✅ Serper returned {len(results)} results")
            return results
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Serper API error: {e}")
            return self._fallback_search(query, max_results)
        except Exception as e:
            logger.error(f"Unexpected error in Serper search: {e}")
            return []
    
    # ==================== Crawling Layer (Firecrawl) ====================
    
    def _enrich_with_firecrawl(self, serp_results: List[Dict], query: str) -> List[Dict]:
        """
        Enrich SERP results by scraping top URLs with Firecrawl
        
        Args:
            serp_results: List of SERP results from Serper
            query: Original search query
            
        Returns:
            Enriched results with full_content from Firecrawl
        """
        if not self.firecrawl_api_key:
            logger.warning("⚠️ FIRECRAWL_API_KEY not available. Skipping deep scraping - using snippets only.")
            logger.warning("   To enable Firecrawl, set FIRECRAWL_API_KEY in your .env file")
            logger.warning("   Get a free key from: https://firecrawl.dev")
            # Return results with snippet as full_content
            for result in serp_results:
                result["full_content"] = result.get("snippet", "")
                result["source"] = "serper"
            return serp_results
        
        logger.info(f"🕷️ Enriching {len(serp_results)} SERP results with Firecrawl (scraping top {self.top_urls_to_scrape} URLs)")
        enriched_results = []
        
        # Scrape top N URLs
        urls_to_scrape = serp_results[:self.top_urls_to_scrape]
        successful_scrapes = 0
        failed_scrapes = 0
        
        for i, result in enumerate(serp_results):
            url = result.get("url", "")
            
            # Scrape top URLs with Firecrawl
            if i < len(urls_to_scrape) and url:
                try:
                    logger.info(f"🕷️ Scraping {i+1}/{len(urls_to_scrape)} with Firecrawl: {url}")
                    full_content = self._scrape_with_firecrawl(url)
                    
                    if full_content and len(full_content.strip()) > 100:
                        result["full_content"] = full_content
                        result["source"] = "serper + firecrawl"
                        successful_scrapes += 1
                        logger.info(f"✅ Successfully scraped {url} ({len(full_content)} chars)")
                    else:
                        result["full_content"] = result.get("snippet", "")
                        result["source"] = "serper"
                        failed_scrapes += 1
                        logger.warning(f"⚠️ Firecrawl returned insufficient content for {url}, using snippet")
                except Exception as e:
                    logger.warning(f"Error scraping {url} with Firecrawl: {e}")
                    result["full_content"] = result.get("snippet", "")
                    result["source"] = "serper"
                    failed_scrapes += 1
            else:
                # For non-top URLs, use snippet as full_content
                result["full_content"] = result.get("snippet", "")
                result["source"] = "serper"
            
            enriched_results.append(result)
        
        logger.info(f"✅ Firecrawl enrichment complete: {successful_scrapes} successful, {failed_scrapes} failed out of {len(urls_to_scrape)} attempts")
        return enriched_results
    
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type((requests.exceptions.RequestException, TimeoutError))
    )
    def _scrape_with_firecrawl(self, url: str) -> Optional[str]:
        """
        Scrape URL using Firecrawl.dev API with preprocessing pipeline
        
        Args:
            url: URL to scrape
            
        Returns:
            Clean text content of the page, or None if failed
        """
        if not self.firecrawl_api_key:
            logger.debug(f"FIRECRAWL_API_KEY not available. Cannot scrape {url}")
            return None
        
        try:
            headers = {
                "Authorization": f"Bearer {self.firecrawl_api_key}",
                "Content-Type": "application/json"
            }
            
            # Updated payload structure for Firecrawl API v1
            payload = {
                "url": url,
                "formats": ["markdown", "html"],
                "onlyMainContent": True
            }
            
            logger.debug(f"🕷️ Calling Firecrawl API for: {url}")
            response = requests.post(
                self.firecrawl_url,
                headers=headers,
                json=payload,
                timeout=self.request_timeout
            )
            
            # Log response status for debugging
            logger.debug(f"Firecrawl API response status: {response.status_code}")
            
            response.raise_for_status()
            
            data = response.json()
            
            # Log response structure for debugging
            logger.debug(f"Firecrawl API response keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
            
            # Handle different response structures
            # Firecrawl v1 can return data directly or wrapped in success/data structure
            result = None
            raw_content = None
            
            if isinstance(data, dict):
                # Check for success/data structure
                if data.get("success") is True:
                    result = data.get("data", {})
                    if isinstance(result, dict):
                        # Prefer markdown, fallback to html
                        raw_content = result.get("markdown") or result.get("html", "") or result.get("content", "")
                # Check if data is directly in response (alternative structure)
                elif "markdown" in data or "html" in data or "content" in data:
                    result = data
                    raw_content = result.get("markdown") or result.get("html", "") or result.get("content", "")
                # Check for error structure
                elif "error" in data:
                    error_msg = data.get("error", "Unknown error")
                    logger.warning(f"Firecrawl API returned error for {url}: {error_msg}")
                    return None
            
            if not raw_content:
                logger.debug(f"No content extracted from Firecrawl response for {url}")
                return None
            
            logger.debug(f"✅ Extracted {len(raw_content)} chars from Firecrawl for {url}")
            
            # Use preprocessing pipeline for clean extraction
            content_type = "markdown" if result and result.get("markdown") else "html"
            try:
                processed = self.preprocessor.preprocess(
                    content=raw_content,
                    content_type=content_type,
                    url=url
                )
                
                cleaned_text = processed.get("text", "") if isinstance(processed, dict) else str(processed)
                if cleaned_text and len(cleaned_text.strip()) > 50:
                    return cleaned_text[:10000]  # Limit to 10k chars
                else:
                    logger.debug(f"Preprocessed content too short for {url}: {len(cleaned_text)} chars")
                    # Fallback: use raw content if preprocessing fails
                    return raw_content[:10000]
            except Exception as preprocess_error:
                logger.warning(f"Preprocessing failed for {url}, using raw content: {preprocess_error}")
                # Fallback: use raw content if preprocessing fails
                return raw_content[:10000]
            
        except requests.exceptions.HTTPError as e:
            error_detail = ""
            try:
                error_response = e.response.json()
                error_detail = error_response.get("error", {}).get("message", str(e))
            except:
                error_detail = str(e)
            logger.warning(f"Firecrawl API HTTP error for {url}: {error_detail} (Status: {e.response.status_code})")
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"Firecrawl API request error for {url}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"Firecrawl API returned invalid JSON for {url}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error scraping {url} with Firecrawl: {e}", exc_info=True)
            return None
    
    # ==================== Intelligence Layer (LLM) ====================
    
    def _process_with_llm(self, results: List[Dict], query: str) -> List[Dict]:
        """
        Post-process results with LLM for:
        - Summarization
        - Deduplication
        - Relevance ranking
        - Fact extraction
        
        Args:
            results: List of enriched search results
            query: Original search query
            
        Returns:
            Processed and ranked results (always returns at least the original results)
        """
        # Check if LLM is disabled due to repeated failures
        if self.llm_disabled:
            logger.debug("LLM processing disabled due to repeated failures - using basic results")
            return self._create_basic_results(results)
        
        if not self.llm_engine or not results:
            # If no LLM, return results with basic confidence scores
            return self._create_basic_results(results)
        
        # Always prepare fallback results first
        fallback_results = []
        for result in results:
            fallback_results.append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "snippet": result.get("snippet", ""),
                "full_content": result.get("full_content", ""),
                "source": result.get("source", "serper + firecrawl"),
                "source_type": "web_search",
                "confidence": 0.8,
                "key_facts": []
            })
        
        try:
            logger.debug(f"🧠 Processing {len(results)} results with LLM")
            
            # Process in smaller batches to avoid MAX_TOKENS truncation
            # Limit to 3 results per batch to keep prompt size very small
            BATCH_SIZE = 3
            MAX_CONTENT_LENGTH = 150  # Very short to prevent truncation
            MAX_SNIPPET_LENGTH = 100  # Very short
            
            all_processed_results = []
            
            # Process results in batches
            for batch_start in range(0, len(results), BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE, len(results))
                batch_results = results[batch_start:batch_end]
                
                logger.debug(f"Processing batch {batch_start//BATCH_SIZE + 1}: results {batch_start}-{batch_end-1}")
                
                # Prepare context for LLM - use much shorter content
                results_context = []
                for i, result in enumerate(batch_results):
                    # Use only essential information to keep prompt short
                    snippet = result.get("snippet", "")[:MAX_SNIPPET_LENGTH]
                    full_content = result.get("full_content", "")
                    # Take first paragraph or first 300 chars, whichever is shorter
                    if full_content:
                        # Get first sentence or first 300 chars
                        first_sentence = full_content.split('.')[0][:MAX_CONTENT_LENGTH]
                        content_preview = first_sentence if len(first_sentence) < MAX_CONTENT_LENGTH else full_content[:MAX_CONTENT_LENGTH]
                    else:
                        content_preview = snippet[:MAX_CONTENT_LENGTH]
                    
                    results_context.append({
                        "index": batch_start + i,  # Keep original index
                        "title": result.get("title", "")[:100],  # Limit title length
                        "snippet": snippet,
                        "preview": content_preview  # Much shorter preview
                    })
                
                # Create simplified, more reliable prompt
                # Build a simpler context string
                results_text = ""
                for i, ctx in enumerate(results_context):
                    results_text += f"\nResult {i}:\nTitle: {ctx.get('title', '')}\nSnippet: {ctx.get('snippet', '')}\n"
                
                prompt = f"""Analyze these {len(batch_results)} search results for the query: "{query}"

{results_text}

For each result, provide:
- A relevance confidence score (0.0 to 1.0)
- A brief 2-3 sentence summary
- 2-3 key facts

Return ONLY a valid JSON array in this exact format:
[
  {{"index": 0, "confidence": 0.95, "summary": "Brief summary here", "key_facts": ["fact1", "fact2"]}},
  {{"index": 1, "confidence": 0.90, "summary": "Brief summary here", "key_facts": ["fact1", "fact2"]}}
]

Important: Return ONLY the JSON array, no markdown code blocks, no explanations, no text before or after."""
                
                # Skip LLM processing if batch is too large - just use original results
                # This prevents MAX_TOKENS issues
                if len(batch_results) > BATCH_SIZE:
                    logger.warning(f"Batch too large, skipping LLM processing for batch {batch_start//BATCH_SIZE + 1}")
                    raise ValueError("Batch too large")
                
                # Try with optimized prompt and higher token limit
                try:
                    logger.debug(f"Calling LLM for batch {batch_start//BATCH_SIZE + 1} with prompt length: {len(prompt)}")
                    response = self.llm_engine.generate(
                        prompt=prompt,
                        system_prompt="You are a helpful assistant. Return ONLY valid JSON array, no markdown, no explanations.",
                        temperature=0.3,
                        max_tokens=4000,  # Increased to prevent truncation
                        timeout=30
                    )
                    
                    if not response or len(response.strip()) == 0:
                        logger.warning(f"Empty response from LLM for batch {batch_start//BATCH_SIZE + 1}")
                        raise ValueError("Empty response from LLM")
                    
                    logger.debug(f"LLM response length: {len(response)}, preview: {response[:200]}")
                    
                    # Parse LLM response for this batch
                    batch_analysis = self._parse_llm_response(response)
                    
                    if not batch_analysis:
                        logger.warning(f"Failed to parse LLM response for batch {batch_start//BATCH_SIZE + 1}, using original results")
                        raise ValueError("Failed to parse LLM response")
                    
                    # Reset failure count on success
                    self.llm_failure_count = 0
                    
                    # Merge batch analysis with results
                    for i, result in enumerate(batch_results):
                        original_index = batch_start + i
                        analysis = batch_analysis.get(original_index, {})
                        
                        processed_result = {
                            "title": result.get("title", ""),
                            "url": result.get("url", ""),
                            "snippet": analysis.get("summary", result.get("snippet", "")),
                            "full_content": result.get("full_content", ""),
                            "source": result.get("source", "serper + firecrawl"),
                            "source_type": "web_search",
                            "confidence": analysis.get("confidence", 0.8),
                            "key_facts": analysis.get("key_facts", [])
                        }
                        
                        all_processed_results.append(processed_result)
                        
                except ValueError as e:
                    error_msg = str(e)
                    self.llm_failure_count += 1
                    logger.warning(f"LLM error for batch {batch_start//BATCH_SIZE + 1}: {error_msg} (failure count: {self.llm_failure_count})")
                    
                    # Check if we should disable LLM
                    if self.llm_failure_count >= self.llm_failure_threshold:
                        logger.error(f"⚠️ LLM failed {self.llm_failure_count} times consecutively. Disabling LLM processing for this session.")
                        self.llm_disabled = True
                    
                    # Add batch results without LLM enhancement
                    for result in batch_results:
                        all_processed_results.append({
                            "title": result.get("title", ""),
                            "url": result.get("url", ""),
                            "snippet": result.get("snippet", ""),
                            "full_content": result.get("full_content", ""),
                            "source": result.get("source", "serper + firecrawl"),
                            "source_type": "web_search",
                            "confidence": 0.8,
                            "key_facts": []
                        })
                        
                except Exception as batch_error:
                    self.llm_failure_count += 1
                    logger.error(f"Unexpected error processing batch {batch_start//BATCH_SIZE + 1}: {batch_error}", exc_info=True)
                    
                    # Check if we should disable LLM
                    if self.llm_failure_count >= self.llm_failure_threshold:
                        logger.error(f"⚠️ LLM failed {self.llm_failure_count} times consecutively. Disabling LLM processing for this session.")
                        self.llm_disabled = True
                    
                    # Add batch results without LLM enhancement
                    for result in batch_results:
                        all_processed_results.append({
                            "title": result.get("title", ""),
                            "url": result.get("url", ""),
                            "snippet": result.get("snippet", ""),
                            "full_content": result.get("full_content", ""),
                            "source": result.get("source", "serper + firecrawl"),
                            "source_type": "web_search",
                            "confidence": 0.8,
                            "key_facts": []
                        })
            
            # Deduplicate across all batches
            seen_content = set()
            processed_results = []
            for result in all_processed_results:
                # Use URL as deduplication key if content is empty
                content_key = result.get("full_content", "")[:200].lower() or result.get("url", "").lower()
                if content_key and content_key in seen_content:
                    continue
                seen_content.add(content_key)
                processed_results.append(result)
            
            # Ensure we have results - if LLM processing failed completely, use fallback
            if not processed_results or len(processed_results) == 0:
                logger.warning("LLM processing returned 0 results, using fallback")
                # Make sure fallback_results has all original results
                if not fallback_results or len(fallback_results) == 0:
                    # Create fallback from original results if needed
                    for result in results:
                        fallback_results.append({
                            "title": result.get("title", ""),
                            "url": result.get("url", ""),
                            "snippet": result.get("snippet", ""),
                            "full_content": result.get("full_content", ""),
                            "source": result.get("source", "serper + firecrawl"),
                            "source_type": "web_search",
                            "confidence": 0.8,
                            "key_facts": []
                        })
                return fallback_results
            
            # Sort by confidence (highest first)
            processed_results.sort(key=lambda x: x.get("confidence", 0), reverse=True)
            
            logger.info(f"✅ LLM processed {len(processed_results)} results in {(len(results)-1)//BATCH_SIZE + 1} batches")
            return processed_results
            
        except Exception as e:
            self.llm_failure_count += 1
            logger.error(f"LLM processing failed completely: {e}", exc_info=True)
            
            # Check if we should disable LLM
            if self.llm_failure_count >= self.llm_failure_threshold:
                logger.error(f"⚠️ LLM failed {self.llm_failure_count} times consecutively. Disabling LLM processing for this session.")
                self.llm_disabled = True
            
            # Always return fallback results - never return empty list
            return fallback_results
    
    def _create_basic_results(self, results: List[Dict]) -> List[Dict]:
        """Create basic result structure without LLM enhancement"""
        processed = []
        for result in results:
            processed.append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "snippet": result.get("snippet", ""),
                "full_content": result.get("full_content", ""),
                "source": result.get("source", "serper + firecrawl"),
                "source_type": "web_search",
                "confidence": 0.8,
                "key_facts": []
            })
        return processed
    
    def _parse_llm_response(self, response: str) -> Dict[int, Dict]:
        """
        Parse LLM JSON response into structured format
        Robustly extracts the first valid JSON array, ignoring extra text after it
        
        Args:
            response: LLM response string
            
        Returns:
            Dictionary mapping result index to analysis data
        """
        try:
            # Remove markdown code blocks if present
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            
            # Check if response is empty
            if not response or len(response.strip()) == 0:
                logger.warning("Empty LLM response received - cannot parse JSON")
                return {}
            
            # CRITICAL FIX: Extract only the first valid JSON array
            # The LLM often returns valid JSON followed by extra text like "} ]."
            # We need to find the first '[' and its matching ']' and extract only that
            
            # Find the first '[' that starts a JSON array
            first_bracket = response.find('[')
            if first_bracket == -1:
                logger.warning("No JSON array found in response")
                return {}
            
            # Extract from first bracket onwards
            json_candidate = response[first_bracket:]
            
            # Find the matching closing ']' by tracking bracket depth
            bracket_depth = 0
            in_string = False
            escape_next = False
            json_end = -1
            
            for i, char in enumerate(json_candidate):
                if escape_next:
                    escape_next = False
                    continue
                
                if char == '\\':
                    escape_next = True
                    continue
                
                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue
                
                if not in_string:
                    if char == '[':
                        bracket_depth += 1
                    elif char == ']':
                        bracket_depth -= 1
                        if bracket_depth == 0:
                            json_end = i + 1
                            break
            
            # If we found a complete array, extract it
            if json_end > 0:
                json_candidate = json_candidate[:json_end]
            else:
                # Fallback: try to find the last ']' before any extra text
                # Look for patterns like "] } ]." or "] }."
                last_bracket = json_candidate.rfind(']')
                if last_bracket > 0:
                    # Check if there's extra text after the last ']'
                    after_bracket = json_candidate[last_bracket+1:].strip()
                    if after_bracket and not after_bracket.startswith(','):
                        # There's extra text, extract up to the last ']'
                        json_candidate = json_candidate[:last_bracket+1]
            
            # Clean up the JSON candidate
            json_candidate = json_candidate.strip()
            
            # Try to parse the extracted JSON
            try:
                analysis_list = json.loads(json_candidate)
            except json.JSONDecodeError as json_err:
                # If still failing, try more aggressive extraction
                logger.debug(f"First parse attempt failed at position {json_err.pos}, trying fallback extraction")
                
                # Fallback: try to extract each object individually
                # Find all { ... } objects and reconstruct array
                objects = []
                i = 0
                while i < len(json_candidate):
                    if json_candidate[i] == '{':
                        # Find matching closing brace
                        brace_depth = 0
                        in_str = False
                        escape = False
                        obj_start = i
                        obj_end = -1
                        
                        for j in range(i, len(json_candidate)):
                            if escape:
                                escape = False
                                continue
                            if json_candidate[j] == '\\':
                                escape = True
                                continue
                            if json_candidate[j] == '"' and not escape:
                                in_str = not in_str
                                continue
                            if not in_str:
                                if json_candidate[j] == '{':
                                    brace_depth += 1
                                elif json_candidate[j] == '}':
                                    brace_depth -= 1
                                    if brace_depth == 0:
                                        obj_end = j + 1
                                        break
                        
                        if obj_end > 0:
                            obj_str = json_candidate[obj_start:obj_end]
                            try:
                                obj = json.loads(obj_str)
                                objects.append(obj)
                            except:
                                pass
                            i = obj_end
                        else:
                            i += 1
                    else:
                        i += 1
                
                if objects:
                    analysis_list = objects
                    logger.debug(f"Extracted {len(objects)} objects using fallback method")
                else:
                    logger.error(f"JSON decode error at position {json_err.pos}: {json_err.msg}")
                    logger.error(f"Response around error: {json_candidate[max(0, json_err.pos-50):json_err.pos+50]}")
                    return {}
            
            # Ensure it's a list
            if not isinstance(analysis_list, list):
                analysis_list = [analysis_list] if analysis_list else []
            
            # Convert to dictionary indexed by result index
            analysis_dict = {}
            for item in analysis_list:
                if not isinstance(item, dict):
                    logger.warning(f"Skipping non-dict item in LLM response: {type(item)}")
                    continue
                index = item.get("index", len(analysis_dict))
                # Validate and sanitize values
                confidence = item.get("confidence", 0.8)
                if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
                    confidence = 0.8
                    logger.warning(f"Invalid confidence value, using default: {item.get('confidence')}")
                
                analysis_dict[index] = {
                    "confidence": float(confidence),
                    "summary": str(item.get("summary", "")).strip(),
                    "is_duplicate": bool(item.get("is_duplicate", False)),
                    "key_facts": item.get("key_facts", []) if isinstance(item.get("key_facts"), list) else []
                }
            
            logger.debug(f"✅ Successfully parsed {len(analysis_dict)} analysis items from LLM response")
            return analysis_dict
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response preview: {response[:500]}...")
            return {}
        except Exception as e:
            logger.warning(f"Error parsing LLM response: {e}")
            return {}
    
    # ==================== RAG Integration ====================
    
    def _store_in_rag(self, results: List[Dict], query: str) -> None:
        """
        Store search results in vector database for RAG with preprocessing pipeline
        
        Args:
            results: List of processed search results
            query: Original search query
        """
        if not self.vector_store:
            logger.debug("Vector store not available. Skipping RAG storage.")
            return
        
        try:
            all_chunks = []
            all_metadatas = []
            
            for result in results:
                # Get full content
                full_content = result.get('full_content', '')
                title = result.get('title', '')
                url = result.get('url', '')
                
                if not full_content:
                    continue
                
                # Combine title and content
                combined_text = f"{title}\n\n{full_content}" if title else full_content
                
                # Chunk the content
                chunks = self.chunker.chunk(
                    text=combined_text,
                    metadata={
                        "source": "web_search",
                        "url": url,
                        "query": query,
                        "title": title,
                        "confidence": result.get("confidence", 0.8),
                        "key_facts": result.get("key_facts", [])
                    },
                    url=url,
                    query=query
                )
                
                # Score each chunk
                scored_chunks = []
                for chunk in chunks:
                    score_result = self.scorer.score(
                        text=chunk['text'],
                        metadata=chunk['metadata'],
                        query=query
                    )
                    
                    # Only keep high-quality chunks
                    if score_result['total_score'] >= 0.3:
                        chunk['metadata']['score'] = score_result
                        scored_chunks.append(chunk)
                
                # Filter by score
                scored_chunks = self.scorer.filter_by_score(
                    [{"text": c['text'], "metadata": c['metadata'], "score": c['metadata']['score']} 
                     for c in scored_chunks],
                    min_score=0.3
                )
                
                # Add to batch
                for chunk_data in scored_chunks:
                    all_chunks.append(chunk_data['text'])
                    # Sanitize metadata for ChromaDB (convert lists/dicts to JSON strings)
                    sanitized_metadata = self._sanitize_metadata(chunk_data['metadata'])
                    all_metadatas.append(sanitized_metadata)
            
            # Store all chunks in batch
            if all_chunks:
                self.vector_store.add_documents(
                    texts=all_chunks,
                    metadatas=all_metadatas
                )
                logger.info(f"✅ Stored {len(all_chunks)} processed chunks in vector database")
            
        except Exception as e:
            logger.warning(f"Failed to store results in RAG: {e}", exc_info=True)
    
    # ==================== Fallback & Utilities ====================
    
    def _fallback_search(self, query: str, max_results: int) -> List[Dict]:
        """
        Fallback search method when Serper is unavailable
        Uses basic web scraping as last resort
        
        Args:
            query: Search query
            max_results: Maximum number of results
            
        Returns:
            List of basic search results
        """
        logger.error(f"❌ SERPER_API_KEY is required for web search. Cannot search for: {query}")
        logger.error("Please set SERPER_API_KEY in your .env file. Get a free key from https://serper.dev")
        # Return empty results - user should configure API keys
        return []
    
    def _sanitize_metadata(self, metadata: Dict) -> Dict:
        """
        Sanitize metadata for ChromaDB compatibility
        ChromaDB only accepts: str, int, float, bool, None
        Converts lists and dicts to JSON strings
        
        Args:
            metadata: Metadata dictionary
            
        Returns:
            Sanitized metadata dictionary
        """
        sanitized = {}
        
        for key, value in metadata.items():
            if value is None:
                sanitized[key] = None
            elif isinstance(value, (str, int, float, bool)):
                sanitized[key] = value
            elif isinstance(value, list):
                # Convert list to JSON string
                sanitized[key] = json.dumps(value) if value else ""
            elif isinstance(value, dict):
                # Convert dict to JSON string
                sanitized[key] = json.dumps(value) if value else "{}"
            else:
                # Convert other types to string
                sanitized[key] = str(value)
        
        return sanitized
    
    def _clean_text(self, text: str) -> str:
        """
        Clean text by removing artifacts, URL fragments, and tracking parameters
        
        Args:
            text: Raw text to clean
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        import re
        from urllib.parse import unquote
        
        # Remove URL-encoded fragments
        text = re.sub(r'%[0-9A-Fa-f]{2}', '', text)
        
        # Remove URLs
        text = re.sub(r'https?://[^\s]+', '', text)
        text = re.sub(r'www\.[^\s]+', '', text)
        text = re.sub(r'[a-zA-Z0-9]+\.(io|com|org|net|edu|gov)[^\s]*', '', text)
        
        # Remove tracking parameters
        text = re.sub(r'\b(rut|utm_|ref|source|campaign|medium|term|content)=[a-zA-Z0-9]+', '', text, flags=re.IGNORECASE)
        text = re.sub(r'&[a-zA-Z0-9_]+=[a-zA-Z0-9]+', '', text)
        
        # Remove hex tracking IDs
        text = re.sub(r'\b[0-9a-f]{32,}\b', '', text, flags=re.IGNORECASE)
        
        # Decode URL-encoded characters
        text = unquote(text, errors='ignore')
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text

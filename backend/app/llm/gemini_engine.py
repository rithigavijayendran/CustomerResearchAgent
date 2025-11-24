"""
Gemini Pro LLM Engine
Handles all LLM operations using Google's Gemini Pro
"""

import os
import json
import re
import time
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
# Removed ThreadPoolExecutor - using direct API calls to avoid shutdown issues

# Load .env file
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

logger = logging.getLogger(__name__)

class GeminiEngine:
    """Gemini Pro LLM Engine for Account Plan generation"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Gemini Pro engine"""
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        
        genai.configure(api_key=self.api_key)
        
        # First, try to get available models from the API
        available_model_names = []
        try:
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            # Extract just the model name (e.g., "gemini-2.5-flash" from "models/gemini-2.5-flash")
            available_model_names = [m.split('/')[-1] for m in available_models]
            logger.info(f"Found {len(available_models)} available Gemini models")
        except Exception as e:
            logger.debug(f"Could not list available models: {e}")
            available_model_names = []
        
        # Build model list: prioritize available models, then fallback to common names
        models_to_try = []
        
        # First, add available models (prioritize flash models for speed, exclude small models)
        if available_model_names:
            # Filter out small/limited models (gemma, nano, etc.) - they're too small for account plans
            excluded_patterns = ['gemma', 'nano', 'lite', '1b', '2b', '7b']
            suitable_models = [
                m for m in available_model_names 
                if not any(pattern in m.lower() for pattern in excluded_patterns)
            ]
            
            # Sort: flash models first, then pro models
            flash_models = [m for m in suitable_models if 'flash' in m.lower()]
            pro_models = [m for m in suitable_models if 'pro' in m.lower() and 'flash' not in m.lower()]
            other_models = [m for m in suitable_models if 'flash' not in m.lower() and 'pro' not in m.lower()]
            models_to_try.extend(flash_models)
            models_to_try.extend(pro_models)
            models_to_try.extend(other_models)
        
        # Add fallback models (newer models first)
        fallback_models = [
            'gemini-2.5-flash',
            'gemini-2.5-pro',
            'gemini-1.5-flash-latest',
            'gemini-1.5-flash-001',
            'gemini-1.5-flash',
            'gemini-1.5-pro-latest',
            'gemini-1.5-pro-001',
            'gemini-1.5-pro',
            'gemini-pro'
        ]
        
        # Add fallbacks that aren't already in the list
        for fallback in fallback_models:
            if fallback not in models_to_try:
                models_to_try.append(fallback)
        
        model_initialized = False
        for model_name in models_to_try:
            try:
                self.model = genai.GenerativeModel(model_name)
                # Don't test the model here - just initialize it to save quota
                # The first actual use will test if it works
                logger.info(f"Gemini engine initialized with model: {model_name}")
                model_initialized = True
                break
            except Exception as e:
                error_str = str(e)
                # Skip models with quota errors (429) immediately
                if "429" in error_str or "quota" in error_str.lower():
                    logger.debug(f"Model {model_name} quota exceeded, skipping")
                    continue
                if "404" not in error_str and "not found" not in error_str.lower():
                    # If it's not a 404, it might be a different issue, but try next anyway
                    logger.debug(f"Model {model_name} failed: {error_str[:100]}")
                continue
        
        if not model_initialized:
            # Check if all models failed due to quota
            quota_errors = []
            for model_name in models_to_try[:5]:  # Check first 5 models
                try:
                    test_model = genai.GenerativeModel(model_name)
                    test_model.generate_content("test")
                except Exception as e:
                    if "429" in str(e) or "quota" in str(e).lower():
                        quota_errors.append(model_name)
            
            if quota_errors:
                raise ValueError(
                    f"All available Gemini models have exceeded their quota. "
                    f"Please check your Google Cloud billing and API quotas. "
                    f"Alternatively, set OPENAI_API_KEY in backend/.env and use LLM_PROVIDER=openai"
                )
            else:
                raise ValueError(
                    "Failed to initialize any Gemini model. "
                    "Please check your API key and try updating the package: "
                    "pip install --upgrade google-generativeai"
                )
    
    def _ensure_complete_response(self, text: str) -> str:
        """Ensure response ends properly and is not truncated"""
        if not text or len(text.strip()) < 10:
            return text
        
        text = text.strip()
        
        # Check if it ends with proper punctuation
        if not any(text.endswith(p) for p in ['.', '!', '?', ':', ';']):
            # Add period if it doesn't end properly
            text = text + '.'
        
        # Check for common truncation patterns and remove incomplete endings
        truncation_patterns = [
            r'\s+relev$', r'\s+focu$', r'\s+into re$', r'\s+ant to$',
            r'\s+private$', r'\s+forecast$', r'\s+launche$'
        ]
        import re
        for pattern in truncation_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                # Remove the incomplete word
                text = re.sub(pattern, '', text, flags=re.IGNORECASE).strip()
                if text and not any(text.endswith(p) for p in ['.', '!', '?']):
                    text = text + '.'
                break
        
        return text
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout: int = 60,  # Increased default timeout for complex operations
        max_retries: int = 3  # Retry for quota/rate limit errors
    ) -> str:
        """Generate text using Gemini Pro with timeout and retry logic"""
        import time
        
        # Verify API key is loaded
        current_key = os.getenv("GEMINI_API_KEY", "")
        if not current_key:
            raise ValueError("GEMINI_API_KEY not found in environment. Please check backend/.env file.")
        
        # Log API key status (without exposing the key)
        key_preview = current_key[:8] + "..." + current_key[-4:] if len(current_key) > 12 else "***"
        logger.debug(f"Using Gemini API key: {key_preview}")
        
        # Reconfigure genai if API key changed
        if current_key != self.api_key:
            logger.info("API key changed, reconfiguring Gemini...")
            self.api_key = current_key
            genai.configure(api_key=self.api_key)
            # Reinitialize model with new key
            try:
                model_name = getattr(self.model, '_model_name', 'gemini-1.5-flash') if hasattr(self, 'model') else 'gemini-1.5-flash'
                self.model = genai.GenerativeModel(model_name)
            except:
                # Fallback to default
                self.model = genai.GenerativeModel('gemini-1.5-flash')
        
        last_error = None
        for attempt in range(max_retries):
            # Combine system and user prompts
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            
            # Configure generation - use dict format for compatibility
            generation_config_dict = {
                "temperature": temperature,
            }
            # Set max_output_tokens - use provided value or default to 8192 (max for most Gemini models)
            # This prevents truncation issues
            if max_tokens:
                # Ensure max_tokens is reasonable (not too low)
                if max_tokens < 500:
                    logger.warning(f"max_tokens ({max_tokens}) is very low, increasing to 2000 to prevent truncation")
                    generation_config_dict["max_output_tokens"] = 2000
                else:
                    generation_config_dict["max_output_tokens"] = max_tokens
            else:
                # Default to 8192 tokens (maximum for most Gemini models) to prevent truncation
                generation_config_dict["max_output_tokens"] = 8192
            
            # Configure safety settings to be less restrictive for business content
            # Use genai types for safety settings
            try:
                    safety_settings = [
                        {
                            "category": genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                            "threshold": genai.types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
                        },
                        {
                            "category": genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                            "threshold": genai.types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
                        },
                        {
                            "category": genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                            "threshold": genai.types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
                        },
                        {
                            "category": genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                            "threshold": genai.types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
                        }
                    ]
            except AttributeError:
                # Fallback if types are not available (older API version)
                safety_settings = None
                logger.debug("Using default safety settings (types not available)")
            
            # Call Gemini API directly - it's already synchronous and handles its own timeouts
            # Using ThreadPoolExecutor was causing "cannot schedule new futures" errors during hot reload
            try:
                if safety_settings:
                    response = self.model.generate_content(
                        full_prompt,  # Positional argument
                        generation_config=generation_config_dict,
                        safety_settings=safety_settings
                    )
                else:
                    response = self.model.generate_content(
                        full_prompt,  # Positional argument
                        generation_config=generation_config_dict
                    )
                    
                if not response:
                    raise ValueError("Empty response from Gemini API")
                
                # Check for safety filters blocking content
                if hasattr(response, 'prompt_feedback'):
                    feedback = response.prompt_feedback
                    if hasattr(feedback, 'block_reason') and feedback.block_reason:
                        reason = feedback.block_reason
                        logger.warning(f"⚠️ Content blocked by safety filters: {reason}")
                        # Try to continue with a modified prompt or return a fallback
                        raise ValueError(f"Content blocked by safety filters: {reason}")
                
                # Extract full text from response - handle different response formats
                response_text = ""
                
                # Check if response was truncated (finish_reason)
                if hasattr(response, 'candidates') and response.candidates:
                        candidate = response.candidates[0]
                        
                        # Check for safety ratings FIRST (more reliable than finish_reason)
                        safety_blocked = False
                        blocked_categories = []
                        if hasattr(candidate, 'safety_ratings'):
                            for rating in candidate.safety_ratings:
                                # Check both 'blocked' attribute and 'probability' for different API versions
                                is_blocked = False
                                if hasattr(rating, 'blocked'):
                                    is_blocked = rating.blocked
                                elif hasattr(rating, 'probability'):
                                    # Some API versions use probability instead of blocked
                                    prob = rating.probability
                                    if hasattr(prob, 'name'):
                                        # HIGH or MEDIUM probability might indicate blocking
                                        is_blocked = prob.name in ['HIGH', 'MEDIUM']
                                
                                if is_blocked:
                                    safety_blocked = True
                                    category = getattr(rating, 'category', 'UNKNOWN')
                                    if hasattr(category, 'name'):
                                        category = category.name
                                    blocked_categories.append(str(category))
                                    logger.warning(f"⚠️ Content blocked by safety rating: {category}")
                        
                        if safety_blocked:
                            raise ValueError(f"Content blocked by safety filters: {', '.join(blocked_categories) if blocked_categories else 'unknown category'}")
                        
                        # Check finish reason - handle both string and integer/enum values
                        finish_reason = getattr(candidate, 'finish_reason', None)
                        
                        # Convert finish_reason to string for comparison (handles enum, int, and string)
                        finish_reason_str = str(finish_reason) if finish_reason is not None else None
                        finish_reason_int = None
                        
                        # Try to get integer value if it's an enum or int
                        try:
                            if hasattr(finish_reason, 'value'):
                                finish_reason_int = finish_reason.value
                            elif isinstance(finish_reason, int):
                                finish_reason_int = finish_reason
                        except (AttributeError, TypeError):
                            pass
                        
                        # Check for MAX_TOKENS (2 or 'MAX_TOKENS')
                        if finish_reason_int == 2 or finish_reason_str == 'MAX_TOKENS' or (hasattr(genai.types, 'FinishReason') and finish_reason == genai.types.FinishReason.MAX_TOKENS):
                            # MAX_TOKENS is a warning, not an error - response was truncated but we can still use it
                            # Only log warning if response is actually empty or very short
                            if not response_text or len(response_text.strip()) < 50:
                                logger.warning("⚠️ Response was truncated due to MAX_TOKENS limit and is empty/too short")
                                logger.warning("⚠️ Consider increasing max_tokens or splitting the request into smaller parts")
                            else:
                                logger.debug("⚠️ Response was truncated due to MAX_TOKENS limit but has usable content")
                        # Check for SAFETY (3 or 'SAFETY') - this blocks the response
                        elif finish_reason_int == 3 or finish_reason_str == 'SAFETY' or (hasattr(genai.types, 'FinishReason') and finish_reason == genai.types.FinishReason.SAFETY):
                            logger.error("⚠️ Response blocked by safety filters")
                            raise ValueError("Response blocked by safety filters")
                        # Check for RECITATION (4 or 'RECITATION')
                        elif finish_reason_int == 4 or finish_reason_str == 'RECITATION' or (hasattr(genai.types, 'FinishReason') and finish_reason == genai.types.FinishReason.RECITATION):
                            logger.error("⚠️ Response blocked due to recitation")
                            raise ValueError("Response blocked due to recitation")
                        # Check for STOP (1 or 'STOP') - normal completion
                        elif finish_reason_int == 1 or finish_reason_str == 'STOP' or (hasattr(genai.types, 'FinishReason') and finish_reason == genai.types.FinishReason.STOP):
                            logger.debug("Response completed normally")
                        elif finish_reason:
                            logger.debug(f"Finish reason: {finish_reason} (type: {type(finish_reason)})")
                        
                        # Extract text from parts (more reliable than response.text)
                        if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                            parts = candidate.content.parts
                            response_text = ''.join([part.text for part in parts if hasattr(part, 'text')])
                        elif hasattr(response, 'text'):
                            response_text = response.text
                        else:
                            response_text = str(response)
                elif hasattr(response, 'text'):
                    response_text = response.text
                else:
                    response_text = str(response)
                
                if not response_text or len(response_text.strip()) == 0:
                        # Log detailed information for debugging
                        logger.error("Empty response text from Gemini API")
                        error_details = []
                        is_max_tokens = False
                        
                        if hasattr(response, 'candidates'):
                            logger.error(f"Number of candidates: {len(response.candidates) if response.candidates else 0}")
                            if response.candidates:
                                candidate = response.candidates[0]
                                finish_reason = getattr(candidate, 'finish_reason', None)
                                finish_reason_str = str(finish_reason) if finish_reason is not None else 'unknown'
                                
                                # Try to get integer value
                                finish_reason_int = None
                                try:
                                    if hasattr(finish_reason, 'value'):
                                        finish_reason_int = finish_reason.value
                                    elif isinstance(finish_reason, int):
                                        finish_reason_int = finish_reason
                                except (AttributeError, TypeError):
                                    pass
                                
                                logger.error(f"Finish reason: {finish_reason_str} (int: {finish_reason_int})")
                                
                                # Determine the specific issue
                                # According to Gemini API: 1=STOP, 2=MAX_TOKENS, 3=SAFETY, 4=RECITATION
                                # finish_reason 2 is MAX_TOKENS (truncation), not SAFETY
                                if finish_reason_int == 2 or finish_reason_str == 'MAX_TOKENS':
                                    # MAX_TOKENS means response was truncated - handle gracefully
                                    is_max_tokens = True
                                    error_details.append("Response truncated due to MAX_TOKENS limit (empty response)")
                                    logger.warning("⚠️ Empty response with MAX_TOKENS - likely truncation issue, not safety filter")
                                elif finish_reason_int == 3 or finish_reason_str == 'SAFETY':
                                    error_details.append("Response blocked by safety filters")
                                elif finish_reason_int == 4 or finish_reason_str == 'RECITATION':
                                    error_details.append("Response blocked due to recitation")
                                elif finish_reason_int == 1 or finish_reason_str == 'STOP':
                                    # STOP with empty response is unusual - might be a different issue
                                    error_details.append("Response completed but empty (unusual)")
                                else:
                                    # Unknown finish_reason - log it but don't assume it's a safety filter
                                    error_details.append(f"Unknown finish_reason: {finish_reason_str} (int: {finish_reason_int})")
                                
                                if hasattr(candidate, 'safety_ratings'):
                                    safety_ratings = candidate.safety_ratings
                                    logger.error(f"Safety ratings: {safety_ratings}")
                                    if safety_ratings:
                                        blocked_ratings = [r for r in safety_ratings if hasattr(r, 'blocked') and r.blocked]
                                        if blocked_ratings:
                                            error_details.append(f"Blocked by safety ratings: {[getattr(r, 'category', 'UNKNOWN') for r in blocked_ratings]}")
                        
                        # Build error message
                        if error_details:
                            error_msg = "Empty response text from Gemini API - " + "; ".join(error_details)
                        else:
                            error_msg = "Empty response text from Gemini API - possible safety filter or API issue"
                        
                        # For MAX_TOKENS with empty response, try to retry with a shorter prompt
                        # If that's not possible, raise a more informative error
                        if is_max_tokens:
                            logger.warning("⚠️ Empty response with MAX_TOKENS truncation - prompt may be too long")
                            # Instead of returning empty string, raise error with retry suggestion
                            raise ValueError(
                                "Empty response due to MAX_TOKENS truncation. "
                                "The prompt may be too long. Consider splitting the request or reducing context size."
                            )
                        
                        # For other cases (SAFETY, RECITATION, etc.), raise error
                        raise ValueError(error_msg)
                    
                # Log response length for debugging
                logger.debug(f"Generated response length: {len(response_text)} characters")
                if len(response_text) > 100:
                    logger.debug(f"Response preview (first 100 chars): {response_text[:100]}...")
                    logger.debug(f"Response preview (last 100 chars): ...{response_text[-100:]}")
                
                # Ensure response is complete (not truncated)
                response_text = self._ensure_complete_response(response_text)
                
                return response_text
            except RuntimeError as e:
                error_msg = str(e).lower()
                if "cannot schedule new futures" in error_msg or "interpreter shutdown" in error_msg:
                    raise RuntimeError("Server is shutting down or reloading. Please wait and retry your request.")
                raise
            except Exception as api_error:
                # Handle API errors with retry logic
                error_msg = str(api_error)
                error_lower = error_msg.lower()
                
                # Check for quota/rate limit errors (429)
                is_quota_error = "429" in error_msg or "quota" in error_lower or "rate limit" in error_lower
                
                if is_quota_error:
                    last_error = api_error
                    if attempt < max_retries - 1:
                        # Exponential backoff: 2s, 4s, 8s
                        wait_time = 2 ** (attempt + 1)
                        logger.warning(f"⚠️ Gemini API quota/rate limit error (attempt {attempt + 1}/{max_retries}). Waiting {wait_time}s before retry...")
                        logger.warning(f"Error: {error_msg[:200]}")
                        time.sleep(wait_time)
                        continue
                    else:
                        # Last attempt failed
                        logger.error(f"❌ Gemini API quota exceeded after {max_retries} attempts")
                        raise ValueError(
                            f"Gemini API quota exceeded after {max_retries} retries. "
                            f"Please check your Google Cloud billing and API quotas at: "
                            f"https://ai.dev/usage?tab=rate-limit. "
                            f"Error: {error_msg[:200]}"
                        )
                
                # Check for invalid API key
                if "API_KEY_INVALID" in error_msg or "401" in error_msg:
                    raise ValueError(
                        f"Invalid Gemini API key. Please check your GEMINI_API_KEY in backend/.env file. "
                        f"Make sure you've restarted the server after changing the API key. "
                        f"Error: {error_msg[:200]}"
                    )
                
                # Check for timeout
                if "timeout" in error_lower:
                    if attempt < max_retries - 1:
                        wait_time = 2 ** (attempt + 1)
                        logger.warning(f"⚠️ Gemini API timeout (attempt {attempt + 1}/{max_retries}). Retrying after {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    raise TimeoutError(f"Gemini API call timed out after {timeout} seconds: {error_msg}")
                
                # Other errors - raise immediately
                raise
    
    def generate_account_plan(
        self,
        company_name: str,
        research_context: str,
        entities: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate complete Account Plan - uses section-by-section generation to prevent truncation"""
        logger.info(f"Generating Account Plan for {company_name} using Gemini Pro")
        
        # Generate sections individually to prevent truncation
        # This is more reliable than single request which can truncate
        logger.info("Generating Account Plan section-by-section to ensure completeness...")
        return self._generate_account_plan_section_by_section(company_name, research_context, entities)
    
    def _generate_section_with_retry(self, generator_func, *args, max_retries=2, **kwargs):
        """
        Generate a section with retry logic for empty responses and timeouts
        
        Args:
            generator_func: Function to call for generation
            *args: Positional arguments
            max_retries: Maximum retry attempts
            **kwargs: Keyword arguments
            
        Returns:
            Generated content or fallback text
        """
        for attempt in range(max_retries + 1):
            try:
                result = generator_func(*args, **kwargs)
                if result and len(result.strip()) > 10:
                    return result
                else:
                    logger.warning(f"Empty or too short response on attempt {attempt + 1}")
            except (ValueError, TimeoutError) as e:
                error_msg = str(e)
                is_timeout = isinstance(e, TimeoutError) or "timeout" in error_msg.lower()
                is_empty = "Empty response" in error_msg
                is_blocked = "blocked" in error_msg.lower()
                is_max_tokens = "MAX_TOKENS" in error_msg or "truncation" in error_msg.lower()
                is_shutdown = "cannot schedule" in error_msg.lower() or "interpreter shutdown" in error_msg.lower()
                
                # Don't retry on shutdown errors - use fallback immediately
                if is_shutdown:
                    logger.warning("Server shutdown detected, using fallback")
                    return self._get_fallback_content(generator_func.__name__)
                
                if is_timeout or is_empty or is_blocked or is_max_tokens:
                    if attempt < max_retries:
                        retry_delay = 2 * (attempt + 1)  # Exponential backoff: 2s, 4s, 6s
                        logger.warning(f"Retrying section generation (attempt {attempt + 2}/{max_retries + 1}) after {retry_delay}s...")
                        logger.warning(f"Error: {error_msg}")
                        time.sleep(retry_delay)
                        continue
                    else:
                        logger.error(f"Failed after {max_retries + 1} attempts: {error_msg}")
                        # Return fallback content
                        return self._get_fallback_content(generator_func.__name__)
                else:
                    raise
            except RuntimeError as e:
                error_msg = str(e).lower()
                if "cannot schedule" in error_msg or "interpreter shutdown" in error_msg or "event loop" in error_msg:
                    logger.warning("Server shutdown detected, using fallback")
                    return self._get_fallback_content(generator_func.__name__)
                raise
            except Exception as e:
                error_msg = str(e)
                error_lower = error_msg.lower()
                # Check for shutdown-related errors
                if any(phrase in error_lower for phrase in ["cannot schedule", "interpreter shutdown", "event loop", "shutdown"]):
                    logger.warning("Server shutdown detected, using fallback")
                    return self._get_fallback_content(generator_func.__name__)
                if attempt < max_retries:
                    retry_delay = 2 * (attempt + 1)
                    logger.warning(f"Error on attempt {attempt + 1}, retrying after {retry_delay}s: {error_msg}")
                    time.sleep(retry_delay)
                    continue
                else:
                    raise
        
        return self._get_fallback_content(generator_func.__name__)
    
    def _get_fallback_content(self, section_name: str) -> str:
        """Get fallback content for a section"""
        fallbacks = {
            "_generate_company_overview": "Company overview information is being processed. Please try again in a moment.",
            "_generate_market_summary": "Market analysis is being processed. Please try again in a moment.",
            "_generate_key_insights": "Key insights are being processed. Please try again in a moment.",
            "_generate_pain_points": "Pain points analysis is being processed. Please try again in a moment.",
            "_generate_opportunities": "Opportunities analysis is being processed. Please try again in a moment.",
            "_generate_competitor_analysis": "Competitor analysis is being processed. Please try again in a moment.",
            "_generate_strategic_recommendations": "Strategic recommendations are being processed. Please try again in a moment.",
            "_generate_final_account_plan": "Final account plan is being processed. Please try again in a moment."
        }
        return fallbacks.get(section_name, "Content generation is temporarily unavailable. Please try again.")
    
    def _generate_account_plan_section_by_section(
        self,
        company_name: str,
        research_context: str,
        entities: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate account plan section by section to prevent truncation"""
        account_plan = {}
        
        # Check if we have meaningful research context
        has_research = research_context and len(research_context.strip()) > 100
        
        if not has_research:
            logger.warning(f"⚠️ No research data available for {company_name} - will use LLM general knowledge")
            logger.warning("This may result in less specific account plans. Consider uploading company documents.")
        
        try:
            # Generate each section individually with enhanced prompts and retry logic
            logger.info("Generating company_overview...")
            account_plan['company_overview'] = self._generate_section_with_retry(
                self._generate_company_overview, company_name, research_context, entities
            )
            
            logger.info("Generating market_summary...")
            account_plan['market_summary'] = self._generate_section_with_retry(
                self._generate_market_summary, company_name, research_context, entities
            )
            
            logger.info("Generating key_insights...")
            account_plan['key_insights'] = self._generate_section_with_retry(
                self._generate_key_insights, company_name, research_context, entities
            )
            
            logger.info("Generating pain_points...")
            account_plan['pain_points'] = self._generate_section_with_retry(
                self._generate_pain_points, company_name, research_context, entities
            )
            
            logger.info("Generating opportunities...")
            account_plan['opportunities'] = self._generate_section_with_retry(
                self._generate_opportunities, company_name, research_context, entities
            )
            
            logger.info("Generating competitor_analysis...")
            account_plan['competitor_analysis'] = self._generate_section_with_retry(
                self._generate_competitor_analysis, company_name, research_context, entities
            )
            
            logger.info("Generating SWOT analysis...")
            account_plan['swot'] = self._generate_swot(company_name, research_context, entities)
            
            logger.info("Generating strategic_recommendations...")
            account_plan['strategic_recommendations'] = self._generate_section_with_retry(
                lambda cn, rc, e: self._generate_strategic_recommendations(cn, rc, e, account_plan),
                company_name, research_context, entities
            )
            
            logger.info("Generating final_account_plan...")
            account_plan['final_account_plan'] = self._generate_section_with_retry(
                lambda cn, rc, e: self._generate_final_account_plan(cn, account_plan),
                company_name, None, None
            )
            
            logger.info("✅ All sections generated successfully")
            
            # AGGRESSIVE post-processing: Clean all fields in the account plan MULTIPLE TIMES
            for _ in range(2):  # Clean twice to catch any remaining fragments
                for key, value in account_plan.items():
                    if isinstance(value, str):
                        account_plan[key] = self._clean_llm_response(value)
                    elif isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            if isinstance(sub_value, str):
                                account_plan[key][sub_key] = self._clean_llm_response(sub_value)
            
            return account_plan
            
        except Exception as e:
            logger.error(f"Error generating account plan section-by-section: {e}")
            # Fallback to basic plan
            return self._generate_fallback_plan(company_name, research_context, entities)
    
    def _generate_account_plan_single_request(
        self,
        company_name: str,
        research_context: str,
        entities: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate Account Plan in single request (faster but can truncate) - DEPRECATED"""
        logger.info(f"Generating Account Plan for {company_name} using Gemini Pro (Single Request Mode)")
        
        account_plan = {}
        
        # Use a single comprehensive prompt to generate all sections at once (MUCH FASTER)
        try:
            logger.info("Generating Account Plan in single request (fast mode)...")
            comprehensive_prompt = f"""You are a senior business analyst and strategic consultant with 15+ years of experience in enterprise account planning, market research, and strategic consulting. You work for a top-tier consulting firm and are generating a production-grade Account Plan for {company_name}.

PROFESSIONAL STANDARDS:
- Industry-level analysis quality comparable to McKinsey, BCG, or Deloitte
- Strategic depth with actionable insights
- Data-driven recommendations backed by research
- Executive-ready content suitable for C-suite presentations
- Clear, concise, and professional business writing

CRITICAL INSTRUCTIONS:
1. **PRIORITIZE UPLOADED DOCUMENTS** - The "UPLOADED DOCUMENT" sections contain the most important, first-hand information from user-uploaded PDFs. These are PRIMARY sources - use them extensively and cite them appropriately.
2. **ANALYZE AND SYNTHESIZE** - Do NOT copy raw text chunks. Analyze patterns, extract insights, and synthesize information into professional business content.
3. **STRATEGIC FOCUS** - Extract key business insights, market dynamics, competitive positioning, and strategic implications - not just raw data.
4. **PROFESSIONAL LANGUAGE** - Write in executive-level business language suitable for board presentations and strategic planning documents.
5. **ACTIONABLE INSIGHTS** - Focus on strategic value, actionable recommendations, and business implications that drive decision-making.
6. **DATA QUALITY** - Remove chart data, formatting artifacts, or raw numbers that don't make sense. Clean and validate all information.
7. **COHERENT STRUCTURE** - Create coherent, well-structured content with logical flow, clear arguments, and professional formatting.
8. **SOURCE PRIORITIZATION** - UPLOADED DOCUMENTS are PRIMARY sources. Web sources are SECONDARY. Always prioritize uploaded document information when available.

Research Data (UPLOADED DOCUMENTS are most important):
{research_context[:8000]}

Extracted Key Information:
{json.dumps(entities, indent=2)[:2000]}

Generate a comprehensive, production-grade Account Plan by ANALYZING and SYNTHESIZING the research data above. Write professional, strategic content that demonstrates deep understanding of the company, market, and competitive landscape.

CRITICAL REQUIREMENTS:
1. **COMPLETENESS** - Complete ALL fields fully. Do NOT truncate text mid-sentence. Each section must be comprehensive and complete.
2. **QUALITY** - Each field must be a complete, well-formed paragraph or structured list with proper formatting.
3. **PUNCTUATION** - All sentences must end with proper punctuation. No incomplete thoughts or fragments.
4. **JSON VALIDITY** - Ensure JSON is valid, complete, and properly formatted before returning.
5. **STRATEGIC DEPTH** - Provide strategic analysis, not surface-level information. Show understanding of business dynamics, market forces, and competitive positioning.
6. **ACTIONABILITY** - Include specific, actionable recommendations that can drive business decisions.
7. **ACCURACY** - Base all statements on the provided research data. If information is uncertain, indicate confidence levels or note limitations.

Return ONLY valid JSON in this exact format (complete all fields fully):
{{
  "company_overview": "Professional company overview synthesizing key information about {company_name} - history, business model, current market position (150-200 words). Write in complete sentences, not raw data. MUST END WITH A COMPLETE SENTENCE.",
  "market_summary": "Market analysis - industry classification, market size, competitive position, market trends (150-200 words). Synthesize the information professionally. MUST END WITH A COMPLETE SENTENCE.",
  "key_insights": "3-5 most important strategic insights about {company_name} based on the research (200-250 words). Focus on business implications. MUST END WITH A COMPLETE SENTENCE.",
  "pain_points": "3-5 major business challenges or pain points facing {company_name} (150-200 words). Write as strategic analysis, not raw data. MUST END WITH A COMPLETE SENTENCE.",
  "opportunities": "4-6 key growth opportunities or strategic openings for {company_name} (200-250 words). Be specific and actionable. MUST END WITH A COMPLETE SENTENCE.",
  "competitor_analysis": "Competitive landscape analysis - main competitors, market positioning, competitive advantages (250-300 words). MUST END WITH A COMPLETE SENTENCE.",
  "swot": {{
    "strengths": "4-5 key strengths of {company_name}, each as a complete sentence or bullet point ending with proper punctuation",
    "weaknesses": "4-5 areas for improvement or weaknesses, each as a complete sentence or bullet point ending with proper punctuation",
    "opportunities": "4-5 market opportunities, each as a complete sentence or bullet point ending with proper punctuation",
    "threats": "4-5 potential threats or risks, each as a complete sentence or bullet point ending with proper punctuation"
  }},
  "strategic_recommendations": "4-6 actionable strategic recommendations for engaging with {company_name} (250-300 words). Be specific and business-focused. MUST END WITH A COMPLETE SENTENCE.",
  "final_account_plan": "Executive summary synthesizing all sections into a cohesive account plan (300-350 words). Write as a professional business document. MUST END WITH A COMPLETE SENTENCE."
}}

IMPORTANT: 
- ANALYZE the data, don't copy raw text
- Write professional business content
- Remove any chart data or formatting artifacts
- COMPLETE ALL FIELDS FULLY - no truncated sentences
- Return ONLY valid JSON, no markdown, no code blocks, no explanations
- Ensure every text field ends with proper punctuation"""
            
            # Single API call instead of 9 separate calls - MUCH FASTER
            # Production-grade system prompt for industry-level quality
            system_prompt = """You are a senior business analyst and strategic consultant with 15+ years of experience in enterprise account planning, market research, and strategic consulting. You work for a top-tier consulting firm (McKinsey, BCG, Deloitte level).

YOUR ROLE:
- Generate production-grade Account Plans suitable for C-suite presentations
- Provide strategic analysis with actionable insights
- Synthesize complex information into clear, executive-ready content
- Maintain industry-level quality standards

CRITICAL GUIDELINES:
1. **PRIORITIZE UPLOADED DOCUMENTS** - Information from "UPLOADED DOCUMENT" sections is PRIMARY and most reliable. Use it extensively.
2. **ANALYZE, DON'T COPY** - Never copy raw text chunks. Always analyze, synthesize, and create original professional content.
3. **STRATEGIC DEPTH** - Provide deep strategic insights, not surface-level information. Show understanding of business dynamics.
4. **COMPLETENESS** - Complete ALL fields fully. Never truncate text mid-sentence. Each section must be comprehensive.
5. **PROFESSIONAL QUALITY** - Write in executive-level business language suitable for board presentations.
6. **ACTIONABILITY** - Include specific, actionable recommendations that drive business decisions.
7. **ACCURACY** - Base all statements on provided research data. Indicate confidence levels when uncertain.

OUTPUT REQUIREMENTS:
- Valid JSON only (no markdown, no code blocks, no explanations)
- All text fields must end with proper punctuation
- Complete sentences and paragraphs (no fragments)
- Professional business writing throughout"""
            
            response_text = self.generate(
                prompt=comprehensive_prompt,
                system_prompt=system_prompt,
                temperature=0.6,  # Lower temperature for more consistent, professional output
                max_tokens=32000,  # Maximum supported by Gemini to prevent truncation
                timeout=120  # Increased timeout for comprehensive generation
            )
            
            # Parse JSON response
            import json
            import re
            
            # Remove markdown code blocks if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            # Try to fix incomplete JSON (common issue: text cut off mid-sentence)
            response_text = response_text.strip()
            
            # Check if JSON looks incomplete (ends with incomplete string)
            if response_text.count('"') % 2 != 0:
                logger.warning("JSON appears incomplete - attempting to fix")
                # Try to close the last string
                last_quote = response_text.rfind('"')
                if last_quote > 0:
                    # Check if we're in the middle of a string
                    before_quote = response_text[:last_quote]
                    if before_quote.count('"') % 2 != 0:
                        # We're in a string, close it
                        response_text = response_text[:last_quote+1] + '"'
            
            # Try to close incomplete JSON objects
            open_braces = response_text.count('{')
            close_braces = response_text.count('}')
            if open_braces > close_braces:
                response_text += '}' * (open_braces - close_braces)
            
            try:
                account_plan = json.loads(response_text)
                
                # Validate that all fields are complete (not truncated)
                truncated_fields = []
                for key, value in account_plan.items():
                    if isinstance(value, str):
                        if not value or len(value.strip()) < 10:
                            continue
                        
                        # Check for incomplete words at the end (e.g., "relev" instead of "relevant")
                        last_word = value.strip().split()[-1] if value.strip().split() else ""
                        # If last word is very short (< 4 chars) and doesn't end with punctuation, might be truncated
                        incomplete_word = len(last_word) < 4 and not any(last_word.endswith(p) for p in ['.', '!', '?', ',', ';', ':'])
                        
                        # Check if text ends mid-sentence (common truncation pattern)
                        last_chars = value[-50:].strip()  # Check last 50 chars for better detection
                        # Check if it ends with proper punctuation
                        ends_properly = any(last_chars.endswith(p) for p in ['.', '!', '?', '"', '}', ')', ']'])
                        
                        # Check if it's very short (likely truncated)
                        is_very_short = len(value) < 50 and key in ['company_overview', 'market_summary', 'key_insights', 'pain_points', 'opportunities']
                        
                        # Check if last word looks incomplete (common truncation: "relev", "focu", etc.)
                        # Check for words cut in half at the end
                        last_words = value.strip().split()[-3:] if len(value.strip().split()) >= 3 else value.strip().split()
                        last_text = ' '.join(last_words).lower()
                        common_incomplete_patterns = [
                            'relev', 'focu', 'into re', 'ant to', 'private', 'forecast',
                            'stay relev', 'translate it into re', 'bank, are', 'launche',
                            'with a focu', 'operational excellence, with a focu'
                        ]
                        has_incomplete_pattern = any(pattern in last_text for pattern in common_incomplete_patterns)
                        
                        # Also check if last word is suspiciously short and doesn't look complete
                        if last_words:
                            last_word_lower = last_words[-1].lower().rstrip('.,!?;:')
                            # Common incomplete words
                            incomplete_words = ['relev', 'focu', 're', 'ant', 'priv']
                            if last_word_lower in incomplete_words or (len(last_word_lower) < 5 and not ends_properly):
                                has_incomplete_pattern = True
                        
                        if not ends_properly or is_very_short or incomplete_word or has_incomplete_pattern:
                            truncated_fields.append(key)
                            logger.warning(f"Field '{key}' appears truncated - length: {len(value)}, last 50 chars: '{value[-50:]}'")
                
                if truncated_fields:
                    logger.warning(f"⚠️ Detected {len(truncated_fields)} truncated fields: {truncated_fields}")
                    # Regenerate ALL truncated sections individually to ensure completeness
                    logger.info("Regenerating truncated sections individually to ensure completeness...")
                    account_plan = self._regenerate_truncated_sections(
                        company_name, research_context, entities, account_plan, truncated_fields
                    )
                
                logger.info("✅ Account Plan generated successfully")
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error: {e}")
                logger.error(f"Response text length: {len(response_text)} characters")
                logger.error(f"Response text (first 500 chars): {response_text[:500]}")
                logger.error(f"Response text (last 500 chars): {response_text[-500:]}")
                
                # Check if response was truncated
                if len(response_text) > 15000:
                    logger.error("⚠️ Response is very long - might have been truncated by API")
                elif len(response_text) < 500:
                    logger.error("⚠️ Response is very short - might be incomplete")
                
                raise  # Re-raise to trigger fallback
            
        except (json.JSONDecodeError, TimeoutError, ValueError) as e:
            logger.error(f"Account plan generation error: {e}")
            logger.warning("Using fast fallback plan - will still return results")
            # Fallback: generate minimal plan immediately
            account_plan = self._generate_fallback_plan(company_name, research_context, entities)
        except Exception as e:
            logger.error(f"Unexpected error generating account plan: {e}")
            # Fallback: generate minimal plan
            account_plan = self._generate_fallback_plan(company_name, research_context, entities)
        
        # Ensure all required fields exist
        if 'swot' not in account_plan or not isinstance(account_plan['swot'], dict):
            account_plan['swot'] = {
                "strengths": account_plan.get('swot', {}).get('strengths', 'Key strengths identified.') if isinstance(account_plan.get('swot'), dict) else 'Key strengths identified.',
                "weaknesses": account_plan.get('swot', {}).get('weaknesses', 'Areas for improvement.') if isinstance(account_plan.get('swot'), dict) else 'Areas for improvement.',
                "opportunities": account_plan.get('swot', {}).get('opportunities', 'Growth opportunities.') if isinstance(account_plan.get('swot'), dict) else 'Growth opportunities.',
                "threats": account_plan.get('swot', {}).get('threats', 'Potential threats.') if isinstance(account_plan.get('swot'), dict) else 'Potential threats.'
            }
        
        # Fill missing fields with defaults
        required_fields = ['company_overview', 'market_summary', 'key_insights', 'pain_points', 
                          'opportunities', 'competitor_analysis', 'strategic_recommendations', 'final_account_plan']
        for field in required_fields:
            if field not in account_plan or not account_plan[field]:
                account_plan[field] = f"{field.replace('_', ' ').title()} for {company_name}."
        
        logger.info("Account Plan generation completed")
        return account_plan
    
    def _regenerate_truncated_sections(
        self,
        company_name: str,
        research_context: str,
        entities: Dict[str, Any],
        account_plan: Dict[str, Any],
        truncated_fields: List[str]
    ) -> Dict[str, Any]:
        """Regenerate truncated sections individually to ensure completeness"""
        logger.info(f"Regenerating {len(truncated_fields)} truncated sections: {truncated_fields}")
        
        # Map of field names to generation methods
        section_generators = {
            'company_overview': self._generate_company_overview,
            'market_summary': self._generate_market_summary,
            'key_insights': self._generate_key_insights,
            'pain_points': self._generate_pain_points,
            'opportunities': self._generate_opportunities,
            'competitor_analysis': self._generate_competitor_analysis,
            'strategic_recommendations': self._generate_strategic_recommendations,
            'final_account_plan': self._generate_final_account_plan
        }
        
        # Regenerate each truncated section
        for field in truncated_fields:
            if field in section_generators:
                try:
                    logger.info(f"Regenerating {field}...")
                    new_content = section_generators[field](company_name, research_context, entities)
                    # Clean and validate the new content
                    if new_content and len(new_content.strip()) > 20:
                        # Ensure it ends properly
                        cleaned = new_content.strip()
                        if not any(cleaned.endswith(p) for p in ['.', '!', '?']):
                            cleaned = cleaned + '.'
                        account_plan[field] = cleaned
                        logger.info(f"✅ {field} regenerated successfully ({len(cleaned)} chars)")
                    else:
                        logger.warning(f"⚠️ {field} regeneration produced short/invalid content")
                except Exception as e:
                    logger.error(f"Error regenerating {field}: {e}")
                    # Keep the truncated version rather than failing completely
            elif field == 'swot':
                # Handle SWOT separately
                try:
                    logger.info("Regenerating SWOT analysis...")
                    swot = self._generate_swot(company_name, research_context, entities)
                    if swot and isinstance(swot, dict):
                        account_plan['swot'] = swot
                        logger.info("✅ SWOT regenerated successfully")
                except Exception as e:
                    logger.error(f"Error regenerating SWOT: {e}")
        
        return account_plan
    
    def _generate_fallback_plan(
        self,
        company_name: str,
        research_context: str,
        entities: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate a detailed fallback plan using actual research data"""
        logger.warning("Using enhanced fallback plan generation with research data")
        
        # Extract meaningful content from research context
        if not research_context or len(research_context.strip()) < 100:
            logger.warning("Research context is too short, using basic fallback")
            return self._get_basic_fallback(company_name)
        
        # Try to generate using LLM even in fallback mode (with shorter timeout)
        try:
            logger.info("Attempting quick LLM generation for fallback plan...")
            quick_prompt = f"""You are a senior business analyst with 15+ years of experience in enterprise account planning and strategic consulting. Generate a production-grade, executive-ready Account Plan for {company_name} based on the research data below, suitable for C-suite presentations.

CRITICAL INSTRUCTIONS - READ CAREFULLY:
- SYNTHESIZE and ANALYZE the research data - DO NOT copy raw text chunks
- Write in clear, professional business English - NO URL fragments, NO encoded characters
- ABSOLUTELY DO NOT include: %2F, rut=, io%2F, com%2F, WEB SOURCE:, //duckduckgo, or any URL fragments
- Extract SPECIFIC facts and write them in professional language
- If you see "WEB SOURCE:" or URL fragments in the data, IGNORE them and extract only the meaningful content
- Write complete, grammatically correct sentences in professional business English
- Your output must be 100% clean - no technical artifacts, no URL fragments, no tracking parameters

Research Data:
{research_context[:8000]}

Extracted Entities:
{json.dumps(entities, indent=2)[:2000]}

Generate a comprehensive Account Plan with detailed, specific information extracted from the research data. SYNTHESIZE the information into professional business language - do not copy raw text.

Return ONLY valid JSON in this format:
{{
  "company_overview": "Detailed company overview (200-300 words) with specific facts from research",
  "market_summary": "Detailed market analysis (200-300 words) with specific market data",
  "key_insights": "3-5 key insights (250-350 words) with specific examples from research",
  "pain_points": "3-5 pain points (200-300 words) with specific challenges mentioned in research",
  "opportunities": "4-6 opportunities (250-350 words) with specific growth areas",
  "competitor_analysis": "Detailed competitor analysis (300-400 words) with specific competitors mentioned",
  "swot": {{
    "strengths": "4-5 specific strengths from research, each as a complete sentence",
    "weaknesses": "4-5 specific weaknesses from research, each as a complete sentence",
    "opportunities": "4-5 specific opportunities from research, each as a complete sentence",
    "threats": "4-5 specific threats from research, each as a complete sentence"
  }},
  "strategic_recommendations": "4-6 strategic recommendations (300-400 words) with specific actions",
  "final_account_plan": "Executive summary (350-450 words) synthesizing all findings"
}}"""
            
            response = self.generate(
                prompt=quick_prompt,
                system_prompt="You are a senior business analyst. CRITICAL: Your output must be 100% clean professional business English. ABSOLUTELY NO URL fragments (%2F, rut=, etc.), NO encoded characters, NO tracking parameters, NO 'WEB SOURCE:' labels. Synthesize information - never copy raw text. Write production-ready content.",
                temperature=0.7,
                max_tokens=10000,
                timeout=60  # Increased timeout for better quality
            )
            
            # Parse JSON
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            
            account_plan = json.loads(response)
            
            # AGGRESSIVE post-processing: Clean all fields in the account plan MULTIPLE TIMES
            for _ in range(2):  # Clean twice to catch any remaining fragments
                for key, value in account_plan.items():
                    if isinstance(value, str):
                        account_plan[key] = self._clean_llm_response(value)
                    elif isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            if isinstance(sub_value, str):
                                account_plan[key][sub_key] = self._clean_llm_response(sub_value)
            
            logger.info("✅ Fallback plan generated successfully using LLM")
            return account_plan
            
        except Exception as e:
            logger.warning(f"Quick LLM generation failed: {e}, using data extraction fallback")
            return self._extract_detailed_plan_from_research(company_name, research_context, entities)
    
    def _get_basic_fallback(self, company_name: str) -> Dict[str, Any]:
        """Basic fallback when no research data available"""
        return {
            "company_overview": f"{company_name} is a company operating in the market. Based on available research data, the company has established a presence in its industry.",
            "market_summary": f"Market analysis for {company_name} based on research data.",
            "key_insights": "Key insights extracted from research data. Further analysis recommended.",
            "pain_points": "Pain points and challenges identified from research.",
            "opportunities": "Growth opportunities and strategic openings available.",
            "competitor_analysis": "Competitive landscape analysis based on available data.",
            "swot": {
                "strengths": "Key strengths identified from research.",
                "weaknesses": "Areas for improvement noted.",
                "opportunities": "Growth opportunities available.",
                "threats": "Potential threats to consider."
            },
            "strategic_recommendations": "Strategic recommendations based on analysis. Further research recommended for detailed planning.",
            "final_account_plan": f"Executive summary for {company_name} Account Plan based on available research data."
        }
    
    def _extract_detailed_plan_from_research(
        self,
        company_name: str,
        research_context: str,
        entities: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract detailed plan directly from research data"""
        logger.info("Extracting detailed plan from research data")
        
        # Split research context into meaningful sections
        context_parts = research_context.split("---")
        
        # Extract key information
        all_text = research_context[:10000]  # Use first 10k chars
        
        # Extract specific information
        revenue_info = ", ".join(entities.get('revenue', [])[:3]) if entities.get('revenue') else ""
        products_info = ", ".join(entities.get('products', [])[:5]) if entities.get('products') else ""
        competitors_info = ", ".join(entities.get('competitors', [])[:5]) if entities.get('competitors') else ""
        locations_info = ", ".join(entities.get('locations', [])[:3]) if entities.get('locations') else ""
        
        # Create detailed sections from research data
        company_overview = self._extract_company_overview_from_text(company_name, all_text, entities)
        market_summary = self._extract_market_summary_from_text(all_text, entities)
        key_insights = self._extract_key_insights_from_text(all_text, entities)
        pain_points = self._extract_pain_points_from_text(all_text)
        opportunities = self._extract_opportunities_from_text(all_text, entities)
        competitor_analysis = self._extract_competitor_analysis_from_text(all_text, competitors_info)
        swot = self._extract_swot_from_text(all_text, entities)
        strategic_recommendations = self._extract_recommendations_from_text(all_text, entities)
        final_plan = self._create_executive_summary(company_name, company_overview, key_insights, opportunities)
        
        return {
            "company_overview": company_overview,
            "market_summary": market_summary,
            "key_insights": key_insights,
            "pain_points": pain_points,
            "opportunities": opportunities,
            "competitor_analysis": competitor_analysis,
            "swot": swot,
            "strategic_recommendations": strategic_recommendations,
            "final_account_plan": final_plan
        }
    
    def _extract_company_overview_from_text(self, company_name: str, text: str, entities: Dict) -> str:
        """Extract company overview from research text with aggressive cleaning"""
        # Clean text first
        text = self._clean_llm_response(text)
        
        # Find sentences about the company
        sentences = text.split('.')
        company_sentences = []
        for s in sentences:
            s_clean = s.strip()
            # Skip sentences with URL fragments
            if re.search(r'%[0-9a-f]{2}|rut=|WEB SOURCE:', s_clean, re.IGNORECASE):
                continue
            if company_name.lower() in s_clean.lower() or any(word in s_clean.lower() for word in ['company', 'corporation', 'founded', 'established', 'headquarters', 'leader', 'provides', 'offers']):
                if len(s_clean) > 30:  # Only substantial sentences
                    company_sentences.append(s_clean)
        
        # Combine with entity information
        overview_parts = []
        if company_sentences:
            overview_parts.append('. '.join(company_sentences[:8]) + '.')  # More sentences
        
        if entities.get('revenue'):
            overview_parts.append(f"Revenue information indicates {', '.join(entities['revenue'][:2])}.")
        
        if entities.get('products'):
            overview_parts.append(f"Key products/services include: {', '.join(entities['products'][:5])}.")
        
        if entities.get('locations'):
            overview_parts.append(f"Operates in: {', '.join(entities['locations'][:3])}.")
        
        result = ' '.join(overview_parts) if overview_parts else f"{company_name} is a company operating in the market. Based on available research data, the company has established a presence in its industry."
        # Final cleaning
        return self._clean_llm_response(result)
    
    def _extract_market_summary_from_text(self, text: str, entities: Dict) -> str:
        """Extract market summary from research text"""
        market_keywords = ['market', 'industry', 'sector', 'growth', 'revenue', 'customers', 'clients']
        market_sentences = []
        for sentence in text.split('.'):
            if any(keyword in sentence.lower() for keyword in market_keywords):
                market_sentences.append(sentence.strip())
        
        if market_sentences:
            return '. '.join(market_sentences[:8]) + '.'
        return "Market analysis based on research data indicates significant opportunities in the industry."
    
    def _extract_key_insights_from_text(self, text: str, entities: Dict) -> str:
        """Extract key insights from research text with cleaning"""
        # Clean text first
        text = self._clean_llm_response(text)
        
        insight_keywords = ['insight', 'trend', 'opportunity', 'growth', 'strategy', 'innovation', 'digital', 'transformation', 'leading', 'leader', 'expertise', 'capability']
        insights = []
        for sentence in text.split('.'):
            s_clean = sentence.strip()
            # Skip sentences with URL fragments
            if re.search(r'%[0-9a-f]{2}|rut=|WEB SOURCE:', s_clean, re.IGNORECASE):
                continue
            if any(keyword in s_clean.lower() for keyword in insight_keywords) and len(s_clean) > 40:
                insights.append(s_clean)
        
        if insights:
            result = '\n\n'.join([f"• {insight}." for insight in insights[:7]])  # More insights
            return self._clean_llm_response(result)
        return "Key insights extracted from research data indicate several strategic opportunities and market trends."
    
    def _extract_pain_points_from_text(self, text: str) -> str:
        """Extract pain points from research text with cleaning"""
        # Clean text first
        text = self._clean_llm_response(text)
        
        pain_keywords = ['challenge', 'problem', 'issue', 'risk', 'threat', 'difficulty', 'concern', 'barrier', 'vulnerability', 'weakness']
        pain_points = []
        for sentence in text.split('.'):
            s_clean = sentence.strip()
            # Skip sentences with URL fragments
            if re.search(r'%[0-9a-f]{2}|rut=|WEB SOURCE:', s_clean, re.IGNORECASE):
                continue
            if any(keyword in s_clean.lower() for keyword in pain_keywords) and len(s_clean) > 40:
                pain_points.append(s_clean)
        
        if pain_points:
            result = '\n\n'.join([f"• {point}." for point in pain_points[:6]])  # More pain points
            return self._clean_llm_response(result)
        return "Pain points and challenges identified from research include operational efficiency, market competition, and technology adoption."
    
    def _extract_opportunities_from_text(self, text: str, entities: Dict) -> str:
        """Extract opportunities from research text with cleaning"""
        # Clean text first
        text = self._clean_llm_response(text)
        
        opp_keywords = ['opportunity', 'growth', 'expansion', 'potential', 'emerging', 'new market', 'innovation', 'market opportunity', 'strategic', 'partnership']
        opportunities = []
        for sentence in text.split('.'):
            s_clean = sentence.strip()
            # Skip sentences with URL fragments
            if re.search(r'%[0-9a-f]{2}|rut=|WEB SOURCE:', s_clean, re.IGNORECASE):
                continue
            if any(keyword in s_clean.lower() for keyword in opp_keywords) and len(s_clean) > 40:
                opportunities.append(s_clean)
        
        if opportunities:
            result = '\n\n'.join([f"• {opp}." for opp in opportunities[:7]])  # More opportunities
            return self._clean_llm_response(result)
        return "Growth opportunities identified include market expansion, digital transformation, and strategic partnerships."
    
    def _extract_competitor_analysis_from_text(self, text: str, competitors_info: str) -> str:
        """Extract competitor analysis from research text"""
        comp_keywords = ['competitor', 'competition', 'rival', 'market share', 'competitive']
        comp_sentences = []
        for sentence in text.split('.'):
            if any(keyword in sentence.lower() for keyword in comp_keywords):
                comp_sentences.append(sentence.strip())
        
        analysis = '. '.join(comp_sentences[:6]) + '.' if comp_sentences else ""
        if competitors_info:
            analysis = f"Key competitors include: {competitors_info}. " + analysis
        
        return analysis if analysis else "Competitive landscape analysis based on available data shows a dynamic market with multiple players."
    
    def _extract_swot_from_text(self, text: str, entities: Dict) -> Dict[str, str]:
        """Extract SWOT analysis from research text with cleaning"""
        # Clean text first
        text = self._clean_llm_response(text)
        
        strengths = []
        weaknesses = []
        opportunities = []
        threats = []
        
        for sentence in text.split('.'):
            s_clean = sentence.strip()
            s = s_clean.lower()
            # Skip sentences with URL fragments
            if re.search(r'%[0-9a-f]{2}|rut=|WEB SOURCE:', s_clean, re.IGNORECASE):
                continue
            if any(word in s for word in ['strength', 'advantage', 'strong', 'leading', 'expertise', 'leader', 'capability']):
                if len(s_clean) > 30:
                    strengths.append(s_clean)
            elif any(word in s for word in ['weakness', 'challenge', 'limitation', 'gap', 'lack', 'vulnerability']):
                if len(s_clean) > 30:
                    weaknesses.append(s_clean)
            elif any(word in s for word in ['opportunity', 'growth', 'potential', 'emerging', 'market opportunity']):
                if len(s_clean) > 30:
                    opportunities.append(s_clean)
            elif any(word in s for word in ['threat', 'risk', 'competition', 'challenge', 'cyber threat']):
                if len(s_clean) > 30:
                    threats.append(s_clean)
        
        return {
            "strengths": self._clean_llm_response('\n'.join([f"• {s}." for s in strengths[:6]])) if strengths else "Key strengths identified from research.",
            "weaknesses": self._clean_llm_response('\n'.join([f"• {w}." for w in weaknesses[:6]])) if weaknesses else "Areas for improvement noted.",
            "opportunities": self._clean_llm_response('\n'.join([f"• {o}." for o in opportunities[:6]])) if opportunities else "Growth opportunities available.",
            "threats": self._clean_llm_response('\n'.join([f"• {t}." for t in threats[:6]])) if threats else "Potential threats to consider."
        }
    
    def _extract_recommendations_from_text(self, text: str, entities: Dict) -> str:
        """Extract strategic recommendations from research text"""
        rec_keywords = ['recommend', 'suggest', 'should', 'strategy', 'action', 'approach', 'focus']
        recommendations = []
        for sentence in text.split('.'):
            if any(keyword in sentence.lower() for keyword in rec_keywords) and len(sentence.strip()) > 40:
                recommendations.append(sentence.strip())
        
        if recommendations:
            return '\n\n'.join([f"• {rec}." for rec in recommendations[:6]])
        return "Strategic recommendations based on analysis include focusing on digital transformation, expanding market presence, and strengthening customer relationships."
    
    def _create_executive_summary(self, company_name: str, overview: str, insights: str, opportunities: str) -> str:
        """Create executive summary from extracted sections"""
        summary = f"Executive Summary for {company_name} Account Plan\n\n"
        summary += f"Company Overview: {overview[:200]}...\n\n"
        summary += f"Key Insights: {insights[:200]}...\n\n"
        summary += f"Opportunities: {opportunities[:200]}...\n\n"
        summary += "This account plan provides a comprehensive analysis based on available research data and identifies strategic opportunities for engagement."
        return summary
    
    def _clean_llm_response(self, response: str) -> str:
        """Clean LLM response to remove URL fragments and encoded characters - AGGRESSIVE CLEANING"""
        if not response:
            return response
        
        # Remove URL-encoded fragments (more aggressive)
        response = re.sub(r'%[0-9A-Fa-f]{2,}', '', response)
        
        # Remove tracking parameters and query strings
        response = re.sub(r'\b(rut|utm_|ref|source|campaign|medium|term|content|uddg)=[a-zA-Z0-9]+', '', response, flags=re.IGNORECASE)
        response = re.sub(r'&[a-zA-Z0-9_]+=[a-zA-Z0-9]+', '', response)
        response = re.sub(r'\?[^\s]+', '', response)  # Remove query strings
        
        # Remove domain patterns and URLs (more aggressive)
        response = re.sub(r'https?://[^\s]+', '', response)
        response = re.sub(r'www\.[^\s]+', '', response)
        response = re.sub(r'[a-zA-Z0-9]+\.(io|com|org|net|edu|gov)[^\s]*', '', response)
        response = re.sub(r'//[^\s]+', '', response)  # Remove protocol-relative URLs
        
        # Remove "WEB SOURCE:" labels
        response = re.sub(r'WEB SOURCE:\s*', '', response, flags=re.IGNORECASE)
        response = re.sub(r'//duckduckgo\.', '', response, flags=re.IGNORECASE)
        
        # Remove hex tracking IDs (32+ character hex strings)
        response = re.sub(r'\b[0-9a-f]{32,}\b', '', response, flags=re.IGNORECASE)
        
        # Remove lines that are mostly URL fragments
        lines = response.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            # Skip lines that are mostly URL fragments or encoded characters
            if re.search(r'%[0-9a-f]{2}', line, re.IGNORECASE) and len(re.findall(r'%[0-9a-f]{2}', line)) > 3:
                continue  # Skip lines with many encoded chars
            if re.search(r'rut=[0-9a-f]+', line, re.IGNORECASE):
                continue  # Skip lines with tracking parameters
            if re.search(r'\.(io|com|org|net)/', line) and len(line) < 100:
                continue  # Skip short lines that are just URLs
            if 'WEB SOURCE:' in line.upper():
                continue  # Skip lines with WEB SOURCE labels
            if '//duckduckgo' in line.lower():
                continue  # Skip DuckDuckGo references
            if line:
                cleaned_lines.append(line)
        
        response = '\n'.join(cleaned_lines)
        
        # Final cleanup
        response = re.sub(r'\s+', ' ', response).strip()
        response = re.sub(r'\s+([\.\,\;\:])', r'\1', response)  # Remove spaces before punctuation
        
        # Ensure response ends properly
        if response and not any(response.rstrip().endswith(p) for p in ['.', '!', '?']):
            response = response.rstrip() + '.'
        
        return response
    
    def _generate_company_overview(
        self,
        company_name: str,
        research_context: str,
        entities: Dict[str, Any]
    ) -> str:
        """Generate Company Overview section with deep insights"""
        
        # Check if we have research context
        has_research = research_context and len(research_context.strip()) > 100
        
        if has_research:
            context_section = f"""
Research Context (PRIORITIZE THIS DATA - it's from uploaded documents and web research):
IMPORTANT: If you see any URL fragments like "%2F", "rut=", "WEB SOURCE:", or "//duckduckgo" in the data below, IGNORE them completely. Extract only the meaningful business content.

{research_context[:5000]}

Extracted Entities:
{json.dumps(entities, indent=2)}
"""
            data_instruction = "- SYNTHESIZE and ANALYZE the research data above - DO NOT copy raw text chunks\n- Extract SPECIFIC facts from the research data and write them professionally\n- USE ACTUAL DATA from research but WRITE IT PROFESSIONALLY"
        else:
            context_section = """
NOTE: Limited research data available. Use your general knowledge about this company to provide a comprehensive overview.
"""
            data_instruction = "- Use your general knowledge about this company to provide detailed, factual information\n- Include well-known facts about the company's history, products, and market position\n- Be specific and factual based on publicly available information"
        
        prompt = f"""You are a senior business analyst with 15+ years of experience in strategic consulting and enterprise account planning. Generate a production-grade, executive-ready Company Overview for {company_name} suitable for C-suite presentations.

{context_section}

CRITICAL REQUIREMENTS - MUST FOLLOW EXACTLY:
- Provide a DETAILED, comprehensive overview (400-600 words) - NOT generic, be SPECIFIC
{data_instruction}
- Write in clear, professional English - ABSOLUTELY NO URL fragments, encoded characters, or tracking parameters
- Your output must be production-ready business English with NO technical artifacts whatsoever
- Include DETAILED: company history, founding year, core business model, current status, key milestones, recent developments, market position
- Mention SPECIFIC: revenue figures, headcount numbers, geographic presence, office locations, customer base (if known)
- Include DETAILED: products/services, key partnerships, acquisitions, strategic initiatives, technology stack
- Be factual, data-driven, and professional
- Focus on what makes this company unique in its industry - provide SPECIFIC examples
- DO NOT use generic phrases like "operating in the market" or "based on available research data" - use SPECIFIC details
- DO NOT include URL fragments, encoded characters (%2F, rut=, etc.), or tracking parameters - ZERO TOLERANCE
- Write complete, grammatically correct sentences in professional business English
- If revenue is mentioned, include it. If headcount is mentioned, include it. If locations are mentioned, include them.
- Provide DEEP insights - not surface-level information

Generate a DETAILED Company Overview section using SPECIFIC information from the research data, written in clear professional English:"""
        
        response = self.generate(
            prompt,
            system_prompt="You are a market research analyst. Synthesize research data into professional business English. Remove all URL fragments, encoded characters, and tracking parameters. Write clear, grammatically correct sentences. Do not copy raw text - analyze and synthesize the information.",
            temperature=0.6, 
            max_tokens=4000,  # Increased to prevent truncation
            timeout=60
        )
        return self._clean_llm_response(response)
    
    def _generate_market_summary(
        self,
        company_name: str,
        research_context: str,
        entities: Dict[str, Any]
    ) -> str:
        """Generate Market Summary section with deep analysis"""
        prompt = f"""You are a senior market research analyst with 15+ years of experience in industry analysis and strategic market intelligence. Generate a production-grade, executive-ready Market Summary for {company_name} with strategic depth suitable for C-suite decision-making.

Research Context (USE THIS DATA - extract specific market information):
IMPORTANT: If you see any URL fragments like "%2F", "rut=", "WEB SOURCE:", or "//duckduckgo" in the data below, IGNORE them completely. Extract only the meaningful business content.

{research_context[:5000]}

Extracted Entities:
{json.dumps(entities, indent=2)}

CRITICAL REQUIREMENTS:
- Analyze the industry and market position in DETAIL (250-400 words) - NOT generic
- Extract SPECIFIC market data from research: market size, growth rates, market share numbers
- Include: SPECIFIC industry classification, market size figures, growth trends mentioned in research
- Describe: SPECIFIC market position, market share percentages (if mentioned), competitive positioning details
- Mention: SPECIFIC key market segments, geographic markets served, customer segments
- Include: market dynamics, trends, regulatory environment mentioned in research
- Be analytical and data-driven - USE ACTUAL NUMBERS and FACTS from research
- Use market research terminology appropriately
- DO NOT use generic phrases - use SPECIFIC market data from research

Generate a DETAILED Market Summary with SPECIFIC market information extracted from research:"""
        
        response = self.generate(
            prompt,
            system_prompt="You are a market research analyst. Synthesize research data into professional business English. Remove all URL fragments, encoded characters, and tracking parameters. Write clear, grammatically correct sentences. Do not copy raw text - analyze and synthesize the information.",
            temperature=0.6, 
            max_tokens=4000,  # Increased to prevent truncation 
            timeout=60
        )
        return self._clean_llm_response(response)
    
    def _generate_key_insights(
        self,
        company_name: str,
        research_context: str,
        entities: Dict[str, Any]
    ) -> str:
        """Generate Key Insights section with deep analysis"""
        prompt = f"""You are a senior strategic analyst with 15+ years of experience in business intelligence and strategic consulting. Extract and synthesize the most critical, production-grade Key Insights about {company_name} with strategic depth suitable for executive decision-making.

Research Context (USE THIS DATA - it contains specific information):
IMPORTANT: If you see any URL fragments like "%2F", "rut=", "WEB SOURCE:", or "//duckduckgo" in the data below, IGNORE them completely. Extract only the meaningful business content.

{research_context[:5000]}

Extracted Entities:
{json.dumps(entities, indent=2)}

CRITICAL REQUIREMENTS:
- Identify 5-7 most important insights (300-450 words) - BE SPECIFIC
- SYNTHESIZE and ANALYZE the research data - DO NOT copy raw text chunks
- Write in clear, professional English - remove any URL fragments, encoded characters, or tracking parameters
- Extract ACTUAL insights from the research data - not generic statements
- Focus on: strategic implications, market dynamics, competitive advantages, business model insights
- Include: SPECIFIC recent developments, trends, strategic moves mentioned in research
- Mention: financial performance, growth patterns, market position, technology adoption
- Prioritize: actionable insights with SPECIFIC examples from research
- Format: Use detailed bullet points with explanations
- Be specific and cite ACTUAL patterns, numbers, and facts from the research
- DO NOT use generic phrases - use SPECIFIC details from the research data
- DO NOT include URL fragments, encoded characters, or tracking parameters
- Write complete, grammatically correct sentences in professional business English

Generate DETAILED Key Insights section with SPECIFIC information extracted from research, written in clear professional English:"""
        
        response = self.generate(
            prompt,
            system_prompt="You are a strategic analyst. Synthesize research data into professional business English. Remove all URL fragments, encoded characters, and tracking parameters. Write clear, grammatically correct sentences. Do not copy raw text - analyze and synthesize the information.",
            temperature=0.7, 
            max_tokens=4000,  # Increased to prevent truncation
            timeout=60
        )
        # Clean response
        response = re.sub(r'%[0-9A-Fa-f]{2}', '', response)
        response = re.sub(r'\b(rut|utm_|ref)=[a-zA-Z0-9]+', '', response, flags=re.IGNORECASE)
        response = re.sub(r'[a-zA-Z0-9]+\.(io|com|org|net)[^\s]*', '', response)
        # Ensure response ends properly
        if response and not any(response.rstrip().endswith(p) for p in ['.', '!', '?']):
            response = response.rstrip() + '.'
        return response
    
    def _generate_pain_points(
        self,
        company_name: str,
        research_context: str,
        entities: Dict[str, Any]
    ) -> str:
        """Generate Pain Points section with specific challenges"""
        prompt = f"""You are a business consultant. Identify the key Pain Points and challenges facing {company_name}.

Research Context (EXTRACT SPECIFIC CHALLENGES from this data):
{research_context[:4000]}

Extracted Entities:
{json.dumps(entities, indent=2)}

CRITICAL REQUIREMENTS:
- Identify 4-6 major pain points (250-350 words) - BE SPECIFIC
- Extract ACTUAL challenges mentioned in the research data - not generic problems
- Focus on: SPECIFIC operational challenges, market pressures, competitive threats mentioned
- Include: SPECIFIC financial constraints, technology gaps, market challenges from research
- Be specific: mention CONCRETE issues with examples from research, not generic problems
- Prioritize: pain points that present opportunities for solutions
- Format: Clear, structured list with detailed explanations
- DO NOT use generic phrases - use SPECIFIC challenges mentioned in research

Generate DETAILED Pain Points section with SPECIFIC challenges extracted from research:"""
        
        response = self.generate(
            prompt,
            system_prompt="You are a strategic analyst. Synthesize research data into professional business English. Remove all URL fragments, encoded characters, and tracking parameters. Write clear, grammatically correct sentences. Do not copy raw text - analyze and synthesize the information.",
            temperature=0.7, 
            max_tokens=4000,  # Increased to prevent truncation
            timeout=60
        )
        # Clean response
        response = re.sub(r'%[0-9A-Fa-f]{2}', '', response)
        response = re.sub(r'\b(rut|utm_|ref)=[a-zA-Z0-9]+', '', response, flags=re.IGNORECASE)
        response = re.sub(r'[a-zA-Z0-9]+\.(io|com|org|net)[^\s]*', '', response)
        # Ensure response ends properly
        if response and not any(response.rstrip().endswith(p) for p in ['.', '!', '?']):
            response = response.rstrip() + '.'
        return response
    
    def _generate_opportunities(
        self,
        company_name: str,
        research_context: str,
        entities: Dict[str, Any]
    ) -> str:
        """Generate Opportunities section"""
        prompt = f"""You are a senior growth strategist with 15+ years of experience in market expansion and strategic planning. Identify production-grade growth Opportunities for {company_name} with actionable strategic depth suitable for C-suite strategic planning.

Research Context:
IMPORTANT: If you see any URL fragments like "%2F", "rut=", "WEB SOURCE:", or "//duckduckgo" in the data below, IGNORE them completely. Extract only the meaningful business content.

{research_context[:3000]}

Extracted Entities:
{json.dumps(entities, indent=2)}

Requirements:
- Identify 4-6 key opportunities (200-300 words)
- Focus on: market expansion, product development, strategic partnerships
- Include: emerging trends, untapped markets, technology opportunities
- Be specific: quantify opportunities where possible (market size, growth rate)
- Prioritize: high-impact, actionable opportunities
- Format: Structured list with opportunity descriptions and potential impact

Generate the Opportunities section:"""
        
        response = self.generate(
            prompt,
            system_prompt="You are a business consultant. Synthesize research data into professional business English. Remove all URL fragments, encoded characters, and tracking parameters. Write clear, grammatically correct sentences. Do not copy raw text - analyze and synthesize the information.",
            temperature=0.8, 
            max_tokens=4000,  # Increased to prevent truncation 
            timeout=60
        )
        return self._clean_llm_response(response)
    
    def _generate_competitor_analysis(
        self,
        company_name: str,
        research_context: str,
        entities: Dict[str, Any]
    ) -> str:
        """Generate Competitor Analysis section"""
        prompt = f"""You are a senior competitive intelligence analyst with 15+ years of experience in competitive analysis and market positioning. Create a production-grade, executive-ready Competitor Analysis for {company_name} with strategic depth suitable for board-level strategic planning.

Research Context:
IMPORTANT: If you see any URL fragments like "%2F", "rut=", "WEB SOURCE:", or "//duckduckgo" in the data below, IGNORE them completely. Extract only the meaningful business content.

{research_context[:3000]}

Extracted Entities:
{json.dumps(entities, indent=2)}

Requirements:
- Identify 3-5 main competitors (250-350 words)
- For each competitor: name, market position, key strengths, weaknesses
- Compare: competitive positioning, market share, product/service differentiation
- Analyze: competitive threats and advantages
- Include: competitive landscape overview
- Be analytical: focus on strategic implications
- Format: Structured analysis with clear comparisons

Generate the Competitor Analysis section:"""
        
        response = self.generate(
            prompt,
            system_prompt="You are a competitive intelligence analyst. Synthesize research data into professional business English. Remove all URL fragments, encoded characters, and tracking parameters. Write clear, grammatically correct sentences. Do not copy raw text - analyze and synthesize the information.",
            temperature=0.7, 
            max_tokens=4000,  # Increased to prevent truncation
            timeout=60
        )
        return self._clean_llm_response(response)
    
    def _generate_swot(
        self,
        company_name: str,
        research_context: str,
        entities: Dict[str, Any]
    ) -> Dict[str, str]:
        """Generate SWOT Analysis"""
        prompt = f"""You are a senior strategic planning analyst with 15+ years of experience in strategic consulting and competitive analysis. Create a production-grade, executive-ready SWOT Analysis for {company_name} with strategic depth suitable for board-level strategic planning.

Research Context:
IMPORTANT: If you see any URL fragments like "%2F", "rut=", "WEB SOURCE:", or "//duckduckgo" in the data below, IGNORE them completely. Extract only the meaningful business content.

{research_context[:3000]}

Extracted Entities:
{json.dumps(entities, indent=2)}

Requirements:
Generate a SWOT analysis with 4-5 items for each category:

STRENGTHS:
- Internal capabilities, competitive advantages, resources
- What the company does well, unique assets

WEAKNESSES:
- Internal limitations, resource constraints, areas for improvement
- What holds the company back

OPPORTUNITIES:
- External factors, market trends, growth potential
- Favorable conditions the company can leverage

THREATS:
- External risks, competitive pressures, market challenges
- Factors that could negatively impact the company

Format your response as JSON:
{{
  "strengths": "List 4-5 strengths, each on a new line with brief explanation",
  "weaknesses": "List 4-5 weaknesses, each on a new line with brief explanation",
  "opportunities": "List 4-5 opportunities, each on a new line with brief explanation",
  "threats": "List 4-5 threats, each on a new line with brief explanation"
}}

Return ONLY valid JSON, no markdown formatting."""
        
        response = self.generate(prompt, temperature=0.7, max_tokens=4000, timeout=60)  # Increased to prevent truncation
        
        # Parse JSON response
        try:
            # Remove markdown code blocks if present
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            
            swot = json.loads(response)
            return {
                "strengths": swot.get("strengths", ""),
                "weaknesses": swot.get("weaknesses", ""),
                "opportunities": swot.get("opportunities", ""),
                "threats": swot.get("threats", "")
            }
        except json.JSONDecodeError:
            logger.warning("Failed to parse SWOT JSON, using fallback")
            # Fallback: split response into sections
            return {
                "strengths": "Analysis in progress",
                "weaknesses": "Analysis in progress",
                "opportunities": "Analysis in progress",
                "threats": "Analysis in progress"
            }
    
    def _generate_strategic_recommendations(
        self,
        company_name: str,
        research_context: str,
        entities: Dict[str, Any],
        account_plan: Dict[str, Any]
    ) -> str:
        """Generate Strategic Recommendations section"""
        prompt = f"""You are a senior strategy consultant. Create actionable Strategic Recommendations for {company_name}.

Research Context:
IMPORTANT: If you see any URL fragments like "%2F", "rut=", "WEB SOURCE:", or "//duckduckgo" in the data below, IGNORE them completely. Extract only the meaningful business content.

{research_context[:3000]}

Current Account Plan Summary:
- Pain Points: {account_plan.get('pain_points', '')[:500]}
- Opportunities: {account_plan.get('opportunities', '')[:500]}
- SWOT: {json.dumps(account_plan.get('swot', {}), indent=2)}

Requirements:
- Provide 4-6 strategic recommendations (250-350 words)
- Each recommendation should be:
  * Specific and actionable
  * Aligned with identified opportunities
  * Address key pain points
  * Leverage strengths and mitigate weaknesses
- Include: priority level, expected impact, implementation considerations
- Format: Numbered list with clear recommendations and rationale
- Be strategic: focus on high-impact initiatives

Generate the Strategic Recommendations section:"""
        
        response = self.generate(
            prompt,
            system_prompt="You are a senior strategy consultant. Synthesize research data into professional business English. Remove all URL fragments, encoded characters, and tracking parameters. Write clear, grammatically correct sentences. Do not copy raw text - analyze and synthesize the information.",
            temperature=0.8, 
            max_tokens=4000,  # Increased to prevent truncation
            timeout=60
        )
        return self._clean_llm_response(response)
    
    def _generate_final_account_plan(
        self,
        company_name: str,
        account_plan: Dict[str, Any]
    ) -> str:
        """Generate Final Account Plan (Executive Summary)"""
        prompt = f"""You are a senior executive strategist with 15+ years of experience in C-suite consulting and strategic planning. Create a production-grade, executive-ready Final Account Plan (Executive Summary) for {company_name} suitable for board presentations and strategic decision-making.

Account Plan Sections:
- Company Overview: {account_plan.get('company_overview', '')[:300]}
- Market Summary: {account_plan.get('market_summary', '')[:300]}
- Key Insights: {account_plan.get('key_insights', '')[:300]}
- Pain Points: {account_plan.get('pain_points', '')[:300]}
- Opportunities: {account_plan.get('opportunities', '')[:300]}
- Competitor Analysis: {account_plan.get('competitor_analysis', '')[:300]}
- Strategic Recommendations: {account_plan.get('strategic_recommendations', '')[:300]}

Requirements:
- Create an executive summary (300-400 words)
- Synthesize all key findings into a cohesive narrative
- Include: company positioning, market opportunity, strategic priorities
- Highlight: most critical insights, top opportunities, key recommendations
- Format: Professional executive summary style
- Be concise but comprehensive
- Focus on strategic implications and next steps

Generate the Final Account Plan (Executive Summary):"""
        
        response = self.generate(
            prompt,
            system_prompt="You are an executive strategist. Synthesize research data into professional business English. Remove all URL fragments, encoded characters, and tracking parameters. Write clear, grammatically correct sentences. Do not copy raw text - analyze and synthesize the information.",
            temperature=0.7, 
            max_tokens=4000,  # Increased to prevent truncation
            timeout=60
        )
        return self._clean_llm_response(response)
    
    def regenerate_section(
        self,
        company_name: str,
        section: str,
        research_context: str,
        entities: Dict[str, Any],
        current_plan: Dict[str, Any]
    ) -> str:
        """Regenerate a specific section of the Account Plan"""
        logger.info(f"Regenerating {section} for {company_name}")
        
        # Map section names to generation methods
        section_generators = {
            'company_overview': self._generate_company_overview,
            'market_summary': self._generate_market_summary,
            'key_insights': self._generate_key_insights,
            'pain_points': self._generate_pain_points,
            'opportunities': self._generate_opportunities,
            'competitor_analysis': self._generate_competitor_analysis,
            'strategic_recommendations': lambda cn, rc, e: self._generate_strategic_recommendations(cn, rc, e, current_plan),
            'final_account_plan': lambda cn, rc, e: self._generate_final_account_plan(cn, current_plan)
        }
        
        # Handle SWOT section (can be dict or nested)
        if section == 'swot':
            # Regenerate entire SWOT as a dict
            swot = self._generate_swot(company_name, research_context, entities)
            return swot  # Return the dict directly
        
        # Handle nested sections (e.g., swot.strengths)
        if '.' in section:
            parts = section.split('.')
            if parts[0] == 'swot' and len(parts) == 2:
                # Regenerate entire SWOT and return specific part
                swot = self._generate_swot(company_name, research_context, entities)
                return swot.get(parts[1], "")
        
        # Generate the section
        generator = section_generators.get(section)
        if generator:
            result = generator(company_name, research_context, entities)
            return result
        else:
            logger.warning(f"Unknown section: {section}")
            return "Section regeneration not available for this section."


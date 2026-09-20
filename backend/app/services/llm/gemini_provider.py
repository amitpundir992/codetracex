"""
Gemini LLM Provider implementation.

Uses Google's Gemini API for text generation with proper error handling,
timeouts, and production-ready configuration.
"""
import logging
import time
from typing import Optional

try:
    import google.generativeai as genai
    from google.api_core import exceptions as google_exceptions
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from app.services.llm.provider import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    LLMProviderError,
    LLMTimeoutError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMMalformedResponseError,
)

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """
    Google Gemini LLM provider.
    
    Implements the LLM provider interface using Google's Gemini API.
    
    Configuration:
        - api_key: Google AI API key
        - model: Model name (e.g., "gemini-1.5-flash", "gemini-1.5-pro")
        
    Usage:
        provider = GeminiProvider(api_key="...", model="gemini-1.5-flash")
        response = provider.generate(request)
    """
    
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        """
        Initialize Gemini provider.
        
        Args:
            api_key: Google AI API key
            model: Model name to use
            
        Raises:
            LLMProviderError: If Gemini SDK is not available
        """
        if not GEMINI_AVAILABLE:
            raise LLMProviderError(
                "google-generativeai package not installed. "
                "Install it with: pip install google-generativeai"
            )
        
        if not api_key:
            raise LLMProviderError("Gemini API key is required")
        
        self.api_key = api_key
        self.model_name = model
        
        # Configure API
        genai.configure(api_key=self.api_key)
        
        # Initialize model
        try:
            self.model = genai.GenerativeModel(self.model_name)
            logger.info(f"Initialized Gemini provider with model: {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini model: {e}")
            raise LLMProviderError(f"Failed to initialize Gemini model: {e}")
    
    def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Generate text using Gemini API.
        
        Args:
            request: LLM request with prompts and parameters
            
        Returns:
            LLM response with generated content
            
        Raises:
            LLMTimeoutError: Request timed out
            LLMAuthenticationError: Authentication failed
            LLMRateLimitError: Rate limit exceeded
            LLMMalformedResponseError: Response was malformed
            LLMProviderError: Other provider errors
        """
        # Combine system and user prompts
        # Gemini doesn't have a separate system prompt, so we prepend it
        full_prompt = f"{request.system_prompt}\n\n{request.user_prompt}"
        
        # Configure generation parameters
        generation_config = genai.GenerationConfig(
            temperature=request.temperature,
            max_output_tokens=request.max_tokens,
        )
        
        # Safety settings - allow all content since we're processing code
        safety_settings = [
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_NONE",
            },
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_NONE",
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_NONE",
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_NONE",
            },
        ]
        
        try:
            # Track timing for timeout
            start_time = time.time()
            
            # Generate content
            response = self.model.generate_content(
                full_prompt,
                generation_config=generation_config,
                safety_settings=safety_settings,
            )
            
            elapsed = time.time() - start_time
            
            # Check timeout (soft check, since SDK may not enforce it exactly)
            if elapsed > request.timeout_seconds:
                logger.warning(
                    f"Gemini request exceeded timeout: {elapsed:.2f}s > {request.timeout_seconds}s"
                )
                raise LLMTimeoutError(
                    f"Request exceeded timeout: {elapsed:.2f}s > {request.timeout_seconds}s"
                )
            
            # Extract text from response
            if not response.text:
                logger.warning("Gemini returned empty response")
                raise LLMMalformedResponseError("Gemini returned empty response")
            
            # Get finish reason if available
            finish_reason = None
            if hasattr(response, 'candidates') and response.candidates:
                finish_reason = str(response.candidates[0].finish_reason)
            
            logger.info(
                f"Gemini generation completed in {elapsed:.2f}s, "
                f"finish_reason: {finish_reason}"
            )
            
            return LLMResponse(
                content=response.text,
                model=self.model_name,
                finish_reason=finish_reason,
            )
            
        except google_exceptions.Unauthenticated as e:
            logger.error(f"Gemini authentication failed: {e}")
            raise LLMAuthenticationError(f"Gemini authentication failed: {e}")
        
        except google_exceptions.ResourceExhausted as e:
            logger.error(f"Gemini rate limit exceeded: {e}")
            raise LLMRateLimitError(f"Gemini rate limit exceeded: {e}")
        
        except google_exceptions.DeadlineExceeded as e:
            logger.error(f"Gemini request timed out: {e}")
            raise LLMTimeoutError(f"Gemini request timed out: {e}")
        
        except (LLMTimeoutError, LLMAuthenticationError, LLMRateLimitError, LLMMalformedResponseError):
            # Re-raise our custom exceptions
            raise
        
        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            raise LLMProviderError(f"Gemini generation failed: {e}")
    
    def get_model_name(self) -> str:
        """Get the model name being used."""
        return self.model_name

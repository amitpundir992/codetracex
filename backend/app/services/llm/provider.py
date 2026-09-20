"""
LLM Provider abstraction for Phase 12: LLM Reasoning & Grounded Explanations.

This module defines the abstract interface for LLM providers and implements
concrete providers (e.g., Gemini).

Design Principles:

1. PROVIDER ABSTRACTION
   - Clean interface for generate()
   - No provider-specific logic in service layer
   - Easy to add new providers

2. PRODUCTION-ORIENTED
   - Safe timeouts
   - Structured error handling
   - No API key exposure

3. TESTABILITY
   - Easy to mock for tests
   - Clear failure modes
"""
from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class LLMRequest:
    """
    Request to LLM provider.
    
    Encapsulates all parameters needed for generation.
    """
    system_prompt: str
    user_prompt: str
    temperature: float = 0.1  # Low temperature for deterministic, grounded answers
    max_tokens: Optional[int] = 4096
    timeout_seconds: int = 60


@dataclass
class LLMResponse:
    """
    Response from LLM provider.
    
    Encapsulates generated content and metadata.
    """
    content: str
    model: str
    finish_reason: Optional[str] = None
    
    @property
    def is_empty(self) -> bool:
        """Check if response content is empty."""
        return not self.content or not self.content.strip()


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""
    pass


class LLMTimeoutError(LLMProviderError):
    """LLM request timed out."""
    pass


class LLMAuthenticationError(LLMProviderError):
    """LLM authentication failed (API key invalid, etc.)."""
    pass


class LLMRateLimitError(LLMProviderError):
    """LLM rate limit exceeded."""
    pass


class LLMMalformedResponseError(LLMProviderError):
    """LLM returned malformed response."""
    pass


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    All providers must implement the generate() method.
    """
    
    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Generate text from the LLM.
        
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
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """Get the model name being used."""
        pass

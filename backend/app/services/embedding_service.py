"""
Embedding service for generating semantic embeddings.

Phase 9: Embeddings + pgvector

This service provides an abstraction over embedding providers,
allowing the embedding model to be changed without affecting
the rest of the codebase.

Architecture:
    
    EmbeddingService (interface)
        ↓
    Provider-specific implementation
        ↓
    Embedding model (sentence-transformers, OpenAI, etc.)

Supported Providers:
    - sentence-transformers: Local embedding models (default)
    - openai: OpenAI embeddings API (future)

Design Principles:
    - Provider abstraction: Easy to swap models
    - Batch support: Efficient embedding generation
    - Error handling: Graceful failures
    - Configuration: Environment-driven
    - No secrets in code: API keys from environment only

Content Processing:
    - Content is truncated to MAX_EMBEDDING_CONTENT_LENGTH
    - Empty content returns None (no embedding)
    - Batch processing for efficiency
"""
import logging
from typing import List, Optional
from abc import ABC, abstractmethod

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """
    Abstract base class for embedding providers.
    
    All embedding providers must implement this interface.
    """
    
    @abstractmethod
    def embed_one(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Input text to embed
            
        Returns:
            Embedding vector as list of floats, or None if failed
        """
        pass
    
    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of input texts to embed
            
        Returns:
            List of embedding vectors (or None for failures)
        """
        pass


class SentenceTransformerProvider(EmbeddingProvider):
    """
    Embedding provider using sentence-transformers library.
    
    This provider uses local transformer models for embedding generation.
    No external API calls required.
    
    Benefits:
    - No API costs
    - No rate limits
    - Works offline
    - Fast for small batches
    
    Drawbacks:
    - Requires local compute
    - Model downloads on first use
    - Less powerful than large commercial models
    
    Popular models:
    - all-MiniLM-L6-v2: 384 dimensions, fast, good quality (default)
    - all-mpnet-base-v2: 768 dimensions, slower, better quality
    - multi-qa-mpnet-base-dot-v1: Optimized for Q&A
    """
    
    def __init__(self, model_name: str):
        """
        Initialize sentence-transformers provider.
        
        Args:
            model_name: Name of sentence-transformers model
        """
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)
            self.model_name = model_name
            logger.info(f"Loaded sentence-transformers model: {model_name}")
        except ImportError:
            logger.error("sentence-transformers not installed")
            raise ImportError(
                "sentence-transformers is required. "
                "Install with: pip install sentence-transformers"
            )
        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            raise
    
    def embed_one(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Input text to embed
            
        Returns:
            Embedding vector as list of floats, or None if failed
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return None
        
        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None
    
    def embed_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of input texts to embed
            
        Returns:
            List of embedding vectors (or None for failures)
        """
        if not texts:
            return []
        
        # Filter out empty texts but preserve positions
        valid_texts = []
        valid_indices = []
        for i, text in enumerate(texts):
            if text and text.strip():
                valid_texts.append(text)
                valid_indices.append(i)
        
        if not valid_texts:
            logger.warning("No valid texts in batch")
            return [None] * len(texts)
        
        try:
            embeddings = self.model.encode(valid_texts, convert_to_numpy=True, show_progress_bar=False)
            
            # Reconstruct results with None for invalid texts
            results = [None] * len(texts)
            for i, embedding in enumerate(embeddings):
                original_index = valid_indices[i]
                results[original_index] = embedding.tolist()
            
            return results
        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            return [None] * len(texts)


class EmbeddingService:
    """
    Main embedding service with provider abstraction.
    
    This service handles:
    - Provider selection based on configuration
    - Content truncation
    - Batch processing
    - Error handling
    
    Usage:
        service = EmbeddingService()
        embedding = service.embed("def hello(): pass")
        
        embeddings = service.embed_batch([
            "def foo(): pass",
            "class Bar: pass",
            "def baz(): pass"
        ])
    """
    
    def __init__(self):
        """Initialize embedding service with configured provider."""
        settings = get_settings()
        
        self.provider_name = settings.EMBEDDING_PROVIDER
        self.model_name = settings.EMBEDDING_MODEL
        self.dimension = settings.EMBEDDING_DIMENSION
        self.max_length = settings.MAX_EMBEDDING_CONTENT_LENGTH
        self.batch_size = settings.EMBEDDING_BATCH_SIZE
        
        # Initialize provider
        if self.provider_name == "sentence-transformers":
            self.provider = SentenceTransformerProvider(self.model_name)
        else:
            raise ValueError(f"Unsupported embedding provider: {self.provider_name}")
        
        logger.info(
            f"EmbeddingService initialized: provider={self.provider_name}, "
            f"model={self.model_name}, dimension={self.dimension}"
        )
    
    def _truncate_content(self, text: str) -> str:
        """
        Truncate content to maximum length.
        
        Args:
            text: Input text
            
        Returns:
            Truncated text
        """
        if len(text) > self.max_length:
            logger.debug(f"Truncating content from {len(text)} to {self.max_length} chars")
            return text[:self.max_length]
        return text
    
    def embed(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Input text to embed
            
        Returns:
            Embedding vector as list of floats, or None if failed
        """
        if not text or not text.strip():
            return None
        
        truncated = self._truncate_content(text)
        return self.provider.embed_one(truncated)
    
    def embed_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts in batches.
        
        This method processes texts in configurable batch sizes
        to avoid memory issues with large lists.
        
        Args:
            texts: List of input texts to embed
            
        Returns:
            List of embedding vectors (or None for failures)
        """
        if not texts:
            return []
        
        # Truncate all texts
        truncated_texts = [self._truncate_content(text) if text else "" for text in texts]
        
        # Process in batches
        all_embeddings = []
        for i in range(0, len(truncated_texts), self.batch_size):
            batch = truncated_texts[i:i + self.batch_size]
            batch_embeddings = self.provider.embed_batch(batch)
            all_embeddings.extend(batch_embeddings)
        
        return all_embeddings

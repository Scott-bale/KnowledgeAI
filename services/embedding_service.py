import os
import logging
import numpy as np
from typing import List, Union
import json

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None

logger = logging.getLogger(__name__)

class EmbeddingService:
    """Service for generating text embeddings using sentence-transformers (default) or OpenAI if configured."""
    
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None
        self.openai_client = None
        self.embedding_dimension = 384
        
        # Initialize the embedding model
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize the embedding model."""
        # Prefer local sentence-transformers if available
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.model = SentenceTransformer(self.model_name)
                logger.info(f"Loaded sentence-transformer model: {self.model_name}")
                
                # Get actual embedding dimension
                test_embedding = self.model.encode(["test"])
                self.embedding_dimension = test_embedding.shape[1]
                return
                
            except Exception as e:
                logger.warning(f"Failed to load sentence-transformer model: {str(e)}")
        
        # Optionally support OpenAI if user configures it
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        if openai_api_key:
            try:
                from openai import OpenAI  # lazy import
                self.openai_client = OpenAI(api_key=openai_api_key)
                self.embedding_dimension = 1536  # text-embedding-ada-002
                logger.info("Using OpenAI embeddings as fallback service")
                return
            except Exception as openai_error:
                logger.warning(f"Failed to initialize OpenAI client: {str(openai_error)}")

        # If both fail, raise error
        raise Exception("No embedding service available - sentence-transformers not installed and no OpenAI API key configured")
    
    def generate_embeddings(self, texts: Union[str, List[str]]) -> np.ndarray:
        """
        Generate embeddings for text(s).
        
        Args:
            texts: Single text string or list of text strings
            
        Returns:
            NumPy array of embeddings
        """
        if isinstance(texts, str):
            texts = [texts]
        
        try:
            if self.openai_client is not None:
                # Use OpenAI embeddings (primary)
                return self._generate_openai_embeddings(texts)
            
            elif self.model is not None:
                # Use sentence-transformers (fallback)
                embeddings = self.model.encode(texts)
                return np.array(embeddings)
            
            else:
                raise Exception("No embedding model available")
                
        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            raise
    
    def _generate_openai_embeddings(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings using OpenAI API."""
        embeddings = []
        
        # Process in batches to avoid API limits
        batch_size = 100
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            try:
                response = self.openai_client.embeddings.create(
                    model="text-embedding-ada-002",
                    input=batch
                )
                
                batch_embeddings = [item.embedding for item in response.data]
                embeddings.extend(batch_embeddings)
                
            except Exception as e:
                logger.error(f"Error generating OpenAI embeddings for batch {i}: {str(e)}")
                raise
        
        return np.array(embeddings)
    
    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings produced by this service."""
        return self.embedding_dimension
    
    def compute_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Compute cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Cosine similarity score between -1 and 1
        """
        try:
            # Normalize the embeddings
            norm1 = np.linalg.norm(embedding1)
            norm2 = np.linalg.norm(embedding2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            # Compute cosine similarity
            similarity = np.dot(embedding1, embedding2) / (norm1 * norm2)
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Error computing similarity: {str(e)}")
            return 0.0

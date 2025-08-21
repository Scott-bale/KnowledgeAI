import os
import pickle
import logging
import numpy as np
import faiss
from typing import List, Dict, Tuple, Optional
from config import Config

logger = logging.getLogger(__name__)

class VectorStore:
    """FAISS-based vector store for efficient similarity search."""
    
    def __init__(self, dimension: int = Config.EMBEDDING_DIMENSION):
        self.dimension = dimension
        self.index = None
        self.document_chunks = []  # Store chunk metadata
        self.index_path = Config.FAISS_INDEX_PATH
        self.metadata_path = f"{self.index_path}.metadata"
        
        # Create index directory if it doesn't exist
        os.makedirs(os.path.dirname(self.index_path) if os.path.dirname(self.index_path) else '.', exist_ok=True)
        
        # Initialize or load the index
        self._initialize_index()
    
    def _initialize_index(self):
        """Initialize FAISS index or load existing one."""
        try:
            # Try to load existing index
            if os.path.exists(f"{self.index_path}.index") and os.path.exists(self.metadata_path):
                self._load_index()
                logger.info(f"Loaded existing FAISS index with {self.index.ntotal} vectors")
            else:
                # Create new index
                self._create_new_index()
                logger.info("Created new FAISS index")
                
        except Exception as e:
            logger.error(f"Error initializing FAISS index: {str(e)}")
            # Create new index as fallback
            self._create_new_index()
    
    def _create_new_index(self):
        """Create a new FAISS index."""
        # Use IndexFlatIP for inner product (cosine similarity with normalized vectors)
        self.index = faiss.IndexFlatIP(self.dimension)
        self.document_chunks = []
    
    def _load_index(self):
        """Load existing FAISS index and metadata."""
        try:
            # Load FAISS index
            self.index = faiss.read_index(f"{self.index_path}.index")
            
            # Load metadata
            with open(self.metadata_path, 'rb') as f:
                self.document_chunks = pickle.load(f)
                
        except Exception as e:
            logger.error(f"Error loading FAISS index: {str(e)}")
            raise
    
    def _save_index(self):
        """Save FAISS index and metadata to disk."""
        try:
            # Save FAISS index
            faiss.write_index(self.index, f"{self.index_path}.index")
            
            # Save metadata
            with open(self.metadata_path, 'wb') as f:
                pickle.dump(self.document_chunks, f)
                
            logger.info(f"Saved FAISS index with {self.index.ntotal} vectors")
            
        except Exception as e:
            logger.error(f"Error saving FAISS index: {str(e)}")
            raise
    
    def add_embeddings(self, embeddings: np.ndarray, chunk_metadata: List[Dict]):
        """
        Add embeddings to the vector store.
        
        Args:
            embeddings: NumPy array of embeddings (shape: [n_chunks, dimension])
            chunk_metadata: List of metadata dictionaries for each chunk
        """
        try:
            # Normalize embeddings for cosine similarity
            embeddings_normalized = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
            
            # Add to FAISS index
            self.index.add(embeddings_normalized.astype('float32'))
            
            # Store metadata
            self.document_chunks.extend(chunk_metadata)
            
            # Save to disk
            self._save_index()
            
            logger.info(f"Added {len(embeddings)} embeddings to vector store")
            
        except Exception as e:
            logger.error(f"Error adding embeddings to vector store: {str(e)}")
            raise
    
    def search(self, query_embedding: np.ndarray, k: int = 10, threshold: float = 0.3) -> List[Dict]:
        """
        Search for similar embeddings.
        
        Args:
            query_embedding: Query embedding vector
            k: Number of results to return
            threshold: Minimum similarity threshold
            
        Returns:
            List of search results with metadata and similarity scores
        """
        try:
            if self.index.ntotal == 0:
                return []
            
            # Normalize query embedding
            query_normalized = query_embedding / np.linalg.norm(query_embedding)
            query_normalized = query_normalized.reshape(1, -1).astype('float32')
            
            # Search FAISS index
            similarities, indices = self.index.search(query_normalized, k)
            
            results = []
            for i, (similarity, idx) in enumerate(zip(similarities[0], indices[0])):
                if idx == -1 or similarity < threshold:
                    continue
                
                # Get chunk metadata
                chunk_metadata = self.document_chunks[idx].copy()
                chunk_metadata['similarity'] = float(similarity)
                chunk_metadata['rank'] = i + 1
                
                results.append(chunk_metadata)
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching vector store: {str(e)}")
            return []
    
    def get_stats(self) -> Dict:
        """Get statistics about the vector store."""
        return {
            'total_vectors': self.index.ntotal if self.index else 0,
            'dimension': self.dimension,
            'total_chunks': len(self.document_chunks)
        }
    
    def remove_document_embeddings(self, document_id: int):
        """
        Remove all embeddings for a specific document.
        Note: This is a simplified implementation. For production,
        consider using IndexIDMap for efficient deletion.
        """
        try:
            # Filter out chunks for the specified document
            remaining_chunks = [chunk for chunk in self.document_chunks 
                              if chunk.get('document_id') != document_id]
            
            if len(remaining_chunks) == len(self.document_chunks):
                logger.warning(f"No chunks found for document {document_id}")
                return
            
            # Rebuild index with remaining chunks
            if remaining_chunks:
                # This is inefficient but simple - rebuild entire index
                logger.info(f"Rebuilding index after removing document {document_id}")
                # For now, log the action but don't implement full rebuild
                # In production, use IndexIDMap for efficient deletion
                logger.warning("Document deletion not fully implemented - requires index rebuild")
            else:
                # All chunks removed, create empty index
                self._create_new_index()
                self._save_index()
                
        except Exception as e:
            logger.error(f"Error removing document embeddings: {str(e)}")
            raise

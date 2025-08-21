import re
import logging
from typing import List, Tuple
from config import Config

logger = logging.getLogger(__name__)

class TextChunker:
    """Utility class for chunking text into smaller segments for embedding."""
    
    def __init__(self, chunk_size: int = Config.MAX_CHUNK_SIZE, overlap: int = Config.CHUNK_OVERLAP):
        self.chunk_size = chunk_size
        self.overlap = overlap
    
    def chunk_text(self, text: str, preserve_sentences: bool = True) -> List[Tuple[str, int, int]]:
        """
        Split text into chunks with optional sentence preservation.
        
        Args:
            text: Input text to chunk
            preserve_sentences: Whether to try to preserve sentence boundaries
            
        Returns:
            List of tuples (chunk_text, start_position, end_position)
        """
        if not text or len(text.strip()) == 0:
            return []
        
        try:
            if preserve_sentences:
                return self._chunk_by_sentences(text)
            else:
                return self._chunk_by_characters(text)
                
        except Exception as e:
            logger.error(f"Error chunking text: {str(e)}")
            # Fallback to character-based chunking
            return self._chunk_by_characters(text)
    
    def _chunk_by_sentences(self, text: str) -> List[Tuple[str, int, int]]:
        """Chunk text while preserving sentence boundaries."""
        # Split text into sentences using regex
        sentence_pattern = r'(?<=[.!?])\s+'
        sentences = re.split(sentence_pattern, text)
        
        chunks = []
        current_chunk = ""
        current_start = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Check if adding this sentence would exceed chunk size
            potential_chunk = current_chunk + " " + sentence if current_chunk else sentence
            
            if len(potential_chunk) <= self.chunk_size:
                # Add sentence to current chunk
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
                    current_start = text.find(sentence, current_start)
            else:
                # Current chunk is full, save it and start new one
                if current_chunk:
                    chunk_end = current_start + len(current_chunk)
                    chunks.append((current_chunk, current_start, chunk_end))
                    
                    # Start new chunk with overlap
                    current_start = max(0, chunk_end - self.overlap)
                    current_chunk = sentence
                else:
                    # Single sentence is too long, split it
                    sentence_chunks = self._chunk_by_characters(sentence)
                    chunks.extend(sentence_chunks)
                    current_chunk = ""
                    current_start = text.find(sentence, current_start) + len(sentence)
        
        # Add the last chunk if it exists
        if current_chunk:
            chunk_end = current_start + len(current_chunk)
            chunks.append((current_chunk, current_start, chunk_end))
        
        return chunks
    
    def _chunk_by_characters(self, text: str) -> List[Tuple[str, int, int]]:
        """Chunk text by character count with overlap."""
        chunks = []
        start = 0
        
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            
            # Try to end at a word boundary if possible
            if end < len(text):
                # Look for the last space within the chunk
                last_space = text.rfind(' ', start, end)
                if last_space > start:
                    end = last_space
            
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append((chunk_text, start, end))
            
            # Move start position considering overlap
            start = max(start + 1, end - self.overlap)
        
        return chunks
    
    def get_chunk_metadata(self, chunk_text: str, chunk_index: int, start_pos: int, 
                          end_pos: int, document_id: int, filename: str) -> dict:
        """
        Create metadata dictionary for a text chunk.
        
        Args:
            chunk_text: The text content of the chunk
            chunk_index: Index of the chunk within the document
            start_pos: Starting position in the original document
            end_pos: Ending position in the original document
            document_id: ID of the source document
            filename: Name of the source file
            
        Returns:
            Metadata dictionary for the chunk
        """
        return {
            'document_id': document_id,
            'chunk_index': chunk_index,
            'content': chunk_text,
            'start_position': start_pos,
            'end_position': end_pos,
            'filename': filename,
            'chunk_length': len(chunk_text),
            'word_count': len(chunk_text.split())
        }

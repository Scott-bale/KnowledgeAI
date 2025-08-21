import os
import logging
import fitz  
from docx import Document as DocxDocument
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """Handles document text extraction from various file formats."""
    
    @staticmethod
    def extract_text(file_path: str, file_type: str) -> Optional[str]:
        """
        Extract text content from a document file.
        
        Args:
            file_path: Path to the document file
            file_type: Type of the file (pdf, txt, docx)
            
        Returns:
            Extracted text content or None if extraction fails
        """
        try:
            if file_type.lower() == 'txt':
                return DocumentProcessor._extract_text_from_txt(file_path)
            elif file_type.lower() == 'pdf':
                return DocumentProcessor._extract_text_from_pdf(file_path)
            elif file_type.lower() == 'docx':
                return DocumentProcessor._extract_text_from_docx(file_path)
            else:
                logger.error(f"Unsupported file type: {file_type}")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {str(e)}")
            return None
    
    @staticmethod
    def _extract_text_from_txt(file_path: str) -> str:
        """Extract text from a TXT file."""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
            return file.read()
    
    @staticmethod
    def _extract_text_from_pdf(file_path: str) -> str:
        """Extract text from a PDF file using PyMuPDF."""
        text = ""
        try:
            with fitz.open(file_path) as pdf_document:
                for page_num in range(pdf_document.page_count):
                    page = pdf_document[page_num]
                    page_text = (page.get_text("text") or "").strip()
                    if not page_text:
                        try:
                            blocks = page.get_text("blocks") or []
                            block_texts = [b[4] for b in blocks if isinstance(b, (list, tuple)) and len(b) > 4 and isinstance(b[4], str)]
                            page_text = "\n".join(t.strip() for t in block_texts if t and t.strip())
                        except Exception:
                            page_text = ""
                    if not page_text:
                        try:
                            words = page.get_text("words") or []
                            words_sorted = sorted(words, key=lambda w: (w[1], w[0]))
                            page_text = " ".join(w[4] for w in words_sorted if isinstance(w, (list, tuple)) and len(w) > 4 and isinstance(w[4], str))
                        except Exception:
                            page_text = ""

                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            logger.error(f"Error processing PDF {file_path}: {str(e)}")
            raise
        return text
    
    @staticmethod
    def _extract_text_from_docx(file_path: str) -> str:
        """Extract text from a DOCX file."""
        text = ""
        try:
            doc = DocxDocument(file_path)
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
        except Exception as e:
            logger.error(f"Error processing DOCX {file_path}: {str(e)}")
            raise
        return text
    
    @staticmethod
    def get_document_info(file_path: str) -> Dict[str, Any]:
        """
        Get basic information about a document.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Dictionary containing document information
        """
        try:
            file_stats = os.stat(file_path)
            file_extension = os.path.splitext(file_path)[1].lower()
            
            return {
                'file_size': file_stats.st_size,
                'file_type': file_extension[1:] if file_extension else 'unknown',
                'filename': os.path.basename(file_path)
            }
        except Exception as e:
            logger.error(f"Error getting document info for {file_path}: {str(e)}")
            return {}

import os
import json
import logging
from typing import List, Dict, Optional
from groq import Groq

logger = logging.getLogger(__name__)

class QAService:
    """Service for question answering using retrieved context and Groq."""
    
    def __init__(self):
        self.groq_client = None
        self._initialize_groq()
    
    def _initialize_groq(self):
        """Initialize Groq client."""
        groq_api_key = os.environ.get("GROQ_API_KEY")
        if not Groq:
            logger.warning("groq package not installed - Q&A service disabled")
            return
        if groq_api_key:
            try:
                self.groq_client = Groq(api_key=groq_api_key)
                logger.info("Groq client initialized for Q&A service")
            except Exception as e:
                logger.error(f"Failed to initialize Groq client: {str(e)}")
        else:
            logger.warning("No GROQ_API_KEY provided - Q&A service disabled")
    
    def answer_question(self, question: str, context_chunks: List[Dict], max_context_length: int = 3000) -> Dict:
        """
        Generate an answer to a question using retrieved context.
        
        Args:
            question: The question to answer
            context_chunks: List of relevant document chunks
            max_context_length: Maximum length of context to include
            
        Returns:
            Dictionary containing answer and metadata
        """
        if not self.groq_client:
            return {
                'answer': 'Q&A service is not available. Groq API key not configured.',
                'confidence': 0.0,
                'sources': [],
                'context_used': False
            }
        
        try:
            # Prepare context from chunks
            context = self._prepare_context(context_chunks, max_context_length)
            
            # Generate answer using Groq
            response = self._generate_answer_with_groq(question, context)
            
            # Extract sources
            sources = self._extract_sources(context_chunks)
            
            return {
                'answer': response.get('answer', 'Sorry, I could not generate an answer.'),
                'confidence': response.get('confidence', 0.0),
                'sources': sources,
                'context_used': len(context.strip()) > 0,
                'num_sources': len(context_chunks)
            }
            
        except Exception as e:
            logger.error(f"Error generating answer: {str(e)}")
            return {
                'answer': f'Error generating answer: {str(e)}',
                'confidence': 0.0,
                'sources': [],
                'context_used': False
            }
    
    def _prepare_context(self, context_chunks: List[Dict], max_length: int) -> str:
        """Prepare context text from document chunks."""
        context_parts = []
        current_length = 0
        
        # Sort chunks by similarity score (highest first)
        sorted_chunks = sorted(context_chunks, key=lambda x: x.get('similarity', 0), reverse=True)
        
        for chunk in sorted_chunks:
            chunk_text = chunk.get('content', '')
            chunk_length = len(chunk_text)
            
            if current_length + chunk_length > max_length:
                # Take partial chunk if it fits
                remaining_space = max_length - current_length
                if remaining_space > 100:  # Only if meaningful amount of space left
                    context_parts.append(chunk_text[:remaining_space] + "...")
                break
            
            context_parts.append(chunk_text)
            current_length += chunk_length
        
        return "\n\n".join(context_parts)
    
    def _generate_answer_with_groq(self, question: str, context: str) -> Dict:
        """Generate answer using Groq API."""
        try:
            system_prompt = """You are a helpful assistant that answers questions based on the provided context. 
            Follow these guidelines:
            1. Base your answer primarily on the provided context
            2. If the context doesn't contain enough information, say so clearly
            3. Provide a confidence score from 0.0 to 1.0 based on how well the context supports your answer
            4. Be concise but comprehensive
            5. Respond ONLY with valid JSON in this exact format: {"answer": "your answer text here", "confidence": 0.8}
            6. Do not include any text before or after the JSON response
            7. Do not include markdown formatting or code blocks"""
            
            user_prompt = f"""Context:
{context}

Question: {question}

Respond with ONLY a JSON object in this format: {{"answer": "your answer here", "confidence": 0.8}}"""
            
            # Default Groq model; configurable via env GROQ_QA_MODEL
            model = os.environ.get("GROQ_QA_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
            response = self.groq_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=1000,
                stream=False
            )

            content = response.choices[0].message.content
            logger.debug(f"Raw Groq response: {content}")
            try:
                result = json.loads(content)
            except Exception as e:
                logger.warning(f"Failed to parse JSON response: {e}")
                logger.debug(f"Raw content: {content}")
                # If model didn't strictly return JSON, try to extract answer from text
                if '"answer":' in content and '"confidence":' in content:
                    # Try to extract JSON-like content
                    try:
                        # Find JSON-like structure in the response
                        start_idx = content.find('{')
                        end_idx = content.rfind('}') + 1
                        if start_idx != -1 and end_idx != 0:
                            json_str = content[start_idx:end_idx]
                            result = json.loads(json_str)
                        else:
                            result = {"answer": content, "confidence": 0.5}
                    except Exception:
                        result = {"answer": content, "confidence": 0.5}
                else:
                    result = {"answer": content, "confidence": 0.5}
            
            # Validate response
            if 'answer' not in result:
                result['answer'] = content
            if 'confidence' not in result:
                result['confidence'] = 0.5
            
            # Clean up answer if it contains JSON formatting
            if isinstance(result['answer'], str):
                # Remove any markdown code blocks
                answer = result['answer']
                if answer.startswith('```') and answer.endswith('```'):
                    answer = answer[3:-3].strip()
                if answer.startswith('{') and answer.endswith('}'):
                    try:
                        # If answer is just JSON, extract the actual answer
                        json_answer = json.loads(answer)
                        if 'answer' in json_answer:
                            answer = json_answer['answer']
                    except Exception:
                        pass
                result['answer'] = answer
            
            # Ensure confidence is between 0 and 1
            result['confidence'] = max(0.0, min(1.0, float(result['confidence'])))
            
            return result
            
        except Exception as e:
            logger.error(f"Error calling Groq API: {str(e)}")
            raise
    
    def _extract_sources(self, context_chunks: List[Dict]) -> List[Dict]:
        """Extract source information from context chunks."""
        sources = []
        seen_documents = set()
        
        for chunk in context_chunks:
            doc_id = chunk.get('document_id')
            filename = chunk.get('filename', 'Unknown')
            
            if doc_id not in seen_documents:
                sources.append({
                    'document_id': doc_id,
                    'filename': filename,
                    'similarity': chunk.get('similarity', 0.0)
                })
                seen_documents.add(doc_id)
        
        # Sort by similarity
        sources.sort(key=lambda x: x['similarity'], reverse=True)
        
        return sources
    
    def check_document_completeness(self, document_content: str, document_metadata: Dict) -> Dict:
        """
        Check the completeness and quality of a document.
        
        Args:
            document_content: Full text content of the document
            document_metadata: Document metadata
            
        Returns:
            Dictionary containing completeness analysis
        """
        if not self.groq_client:
            return {
                'completeness_score': 0.0,
                'analysis': 'Document completeness check is not available. OpenAI API key not configured.',
                'suggestions': []
            }
        
        try:
            system_prompt = """You are an expert document analyst. Analyze the provided document for completeness and quality.
            Evaluate:
            1. Structure and organization
            2. Content depth and coverage
            3. Missing information or sections
            4. Overall quality
            
            Provide a completeness score from 0.0 to 1.0 and actionable suggestions for improvement.
            Respond in JSON format with 'completeness_score', 'analysis', and 'suggestions' fields."""
            
            # Truncate content if too long
            max_content_length = 4000
            content_preview = document_content[:max_content_length]
            if len(document_content) > max_content_length:
                content_preview += "\n[Content truncated...]"
            
            user_prompt = f"""Document Metadata:
Filename: {document_metadata.get('filename', 'Unknown')}
File Type: {document_metadata.get('file_type', 'Unknown')}
File Size: {document_metadata.get('file_size', 0)} bytes

Document Content:
{content_preview}

Please analyze this document for completeness and quality."""
            response = self.groq_client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_completion_tokens=1024,
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Validate response
            if 'completeness_score' not in result:
                result['completeness_score'] = 0.5
            if 'analysis' not in result:
                result['analysis'] = 'Analysis not available'
            if 'suggestions' not in result:
                result['suggestions'] = []
            
            # Ensure score is between 0 and 1
            result['completeness_score'] = max(0.0, min(1.0, float(result['completeness_score'])))
            
            return result
            
        except Exception as e:
            logger.error(f"Error checking document completeness: {str(e)}")
            return {
                'completeness_score': 0.0,
                'analysis': f'Error analyzing document: {str(e)}',
                'suggestions': []
            }

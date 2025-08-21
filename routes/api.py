import os
import time
import logging
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from extensions import db
from models import Document, DocumentChunk, SearchQuery
from services.document_processor import DocumentProcessor
from services.embedding_service import EmbeddingService
from services.vector_store import VectorStore
from services.qa_service import QAService
from utils.text_chunker import TextChunker
from config import Config

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)

# Lazy singleton services to avoid import-time initialization failures
_embedding_service = None
_vector_store = None
_qa_service = None
_text_chunker = None

def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service

def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        # Use configured dimension to avoid forcing embedding service initialization
        from config import Config as _Cfg
        _vector_store = VectorStore(dimension=_Cfg.EMBEDDING_DIMENSION)
    return _vector_store

def get_qa_service() -> QAService:
    global _qa_service
    if _qa_service is None:
        _qa_service = QAService()
    return _qa_service

def get_text_chunker() -> TextChunker:
    global _text_chunker
    if _text_chunker is None:
        _text_chunker = TextChunker()
    return _text_chunker

def allowed_file(filename):
    """Check if file has allowed extension."""
    if '.' not in filename:
        return False
    extension = '.' + filename.rsplit('.', 1)[1].lower()
    return extension in Config.SUPPORTED_EXTENSIONS

@api_bp.route('/upload', methods=['POST'])
def upload_document():
    """Upload and process a document."""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': f'File type not supported. Allowed types: {Config.SUPPORTED_EXTENSIONS}'}), 400
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        try:
            # Extract text from document
            file_type = filename.rsplit('.', 1)[1].lower()
            text_content = DocumentProcessor.extract_text(file_path, file_type)
            
            if not text_content:
                os.remove(file_path)  # Clean up
                return jsonify({'error': 'Could not extract text from document'}), 400
            
            file_info = DocumentProcessor.get_document_info(file_path)
            
            # Create document record
            document = Document(
                filename=filename,
                file_type=file_type,
                content=text_content,
                file_size=file_info.get('file_size', 0),
                embedding_status='processing'
            )
            db.session.add(document)
            db.session.commit()
            
            success = process_document_embeddings(document, text_content)
            
            if success:
                document.embedding_status = 'completed'
            else:
                document.embedding_status = 'failed'
            
            db.session.commit()
            
            # Clean up uploaded file
            os.remove(file_path)
            
            return jsonify({
                'message': 'Document uploaded and processed successfully',
                'document': document.to_dict()
            }), 201
            
        except Exception as e:
            # Clean up on error
            if os.path.exists(file_path):
                os.remove(file_path)
            db.session.rollback()
            logger.error(f"Error processing document: {str(e)}")
            return jsonify({'error': f'Error processing document: {str(e)}'}), 500
            
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        return jsonify({'error': f'Error uploading document: {str(e)}'}), 500

def process_document_embeddings(document: Document, text_content: str) -> bool:
    """Process document embeddings and store in vector database."""
    try:
        # Chunk the text
        chunks = get_text_chunker().chunk_text(text_content)
        
        if not chunks:
            logger.warning(f"No chunks generated for document {document.id}")
            return False
        
        # Store chunks in database
        chunk_records = []
        chunk_texts = []
        chunk_metadata = []
        
        for i, (chunk_text, start_pos, end_pos) in enumerate(chunks):
            # Create chunk record
            chunk_record = DocumentChunk(
                document_id=document.id,
                chunk_index=i,
                content=chunk_text,
                start_position=start_pos,
                end_position=end_pos
            )
            chunk_records.append(chunk_record)
            chunk_texts.append(chunk_text)
            
            # Create metadata for vector store
            metadata = get_text_chunker().get_chunk_metadata(
                chunk_text, i, start_pos, end_pos, document.id, document.filename
            )
            chunk_metadata.append(metadata)
        
        # Save chunks to database
        db.session.add_all(chunk_records)
        db.session.commit()
        
        # Generate embeddings
        embeddings = get_embedding_service().generate_embeddings(chunk_texts)

        # Add to vector store
        get_vector_store().add_embeddings(embeddings, chunk_metadata)
        
        # Update document
        document.chunk_count = len(chunks)
        db.session.commit()
        
        logger.info(f"Successfully processed {len(chunks)} chunks for document {document.id}")
        return True
        
    except Exception as e:
        logger.error(f"Error processing embeddings for document {document.id}: {str(e)}")
        db.session.rollback()
        return False

@api_bp.route('/search', methods=['POST'])
def search_documents():
    """Search documents using semantic similarity."""
    try:
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({'error': 'Query text is required'}), 400
        
        query_text = data['query'].strip()
        if not query_text:
            return jsonify({'error': 'Query text cannot be empty'}), 400
        
        max_results = min(data.get('max_results', 10), Config.MAX_SEARCH_RESULTS)
        threshold = data.get('threshold', Config.SIMILARITY_THRESHOLD)
        
        start_time = time.time()
        
        # Generate query embedding
        query_embedding = get_embedding_service().generate_embeddings([query_text])[0]

        # Search vector store
        results = get_vector_store().search(query_embedding, k=max_results, threshold=threshold)
        
        response_time = (time.time() - start_time) * 1000
        
        # Log search query
        search_query = SearchQuery(
            query_text=query_text,
            results_count=len(results),
            response_time_ms=response_time
        )
        db.session.add(search_query)
        db.session.commit()
        
        return jsonify({
            'query': query_text,
            'results': results,
            'total_results': len(results),
            'response_time_ms': response_time,
            'threshold': threshold
        }), 200
        
    except Exception as e:
        logger.error(f"Error searching documents: {str(e)}")
        return jsonify({'error': f'Error searching documents: {str(e)}'}), 500

@api_bp.route('/ask', methods=['POST'])
def ask_question():
    """Answer a question using retrieved documents."""
    try:
        data = request.get_json()
        if not data or 'question' not in data:
            return jsonify({'error': 'Question is required'}), 400
        
        question = data['question'].strip()
        if not question:
            return jsonify({'error': 'Question cannot be empty'}), 400
        
        max_results = min(data.get('max_results', 5), 10)
        threshold = data.get('threshold', Config.SIMILARITY_THRESHOLD)
        
        start_time = time.time()
        
        # Search for relevant chunks
        query_embedding = get_embedding_service().generate_embeddings([question])[0]
        context_chunks = get_vector_store().search(query_embedding, k=max_results, threshold=threshold)
        
        if not context_chunks:
            return jsonify({
                'question': question,
                'answer': 'I could not find relevant information to answer your question. Please try rephrasing or asking about something else.',
                'confidence': 0.0,
                'sources': [],
                'context_used': False
            }), 200
        
        # Generate answer using Q&A service
        qa_result = get_qa_service().answer_question(question, context_chunks)
        
        response_time = (time.time() - start_time) * 1000
        
        # Log search query
        search_query = SearchQuery(
            query_text=question,
            results_count=len(context_chunks),
            response_time_ms=response_time
        )
        db.session.add(search_query)
        db.session.commit()
        
        return jsonify({
            'question': question,
            'answer': qa_result['answer'],
            'confidence': qa_result['confidence'],
            'sources': qa_result['sources'],
            'context_used': qa_result['context_used'],
            'num_context_chunks': qa_result['num_sources'],
            'response_time_ms': response_time
        }), 200
        
    except Exception as e:
        logger.error(f"Error answering question: {str(e)}")
        return jsonify({'error': f'Error answering question: {str(e)}'}), 500

@api_bp.route('/documents', methods=['GET'])
def list_documents():
    """List all uploaded documents."""
    try:
        documents = Document.query.order_by(Document.upload_time.desc()).all()
        return jsonify({
            'documents': [doc.to_dict() for doc in documents],
            'total_count': len(documents)
        }), 200
        
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        return jsonify({'error': f'Error listing documents: {str(e)}'}), 500

@api_bp.route('/documents/<int:document_id>', methods=['GET'])
def get_document(document_id):
    """Get details of a specific document."""
    try:
        document = Document.query.get_or_404(document_id)
        return jsonify(document.to_dict()), 200
        
    except Exception as e:
        logger.error(f"Error getting document {document_id}: {str(e)}")
        return jsonify({'error': f'Error getting document: {str(e)}'}), 500

@api_bp.route('/documents/<int:document_id>/completeness', methods=['POST'])
def check_document_completeness(document_id):
    """Check the completeness of a document."""
    try:
        document = Document.query.get_or_404(document_id)
        # Run completeness check
        completeness_result = get_qa_service().check_document_completeness(
            document.content, 
            document.to_dict()
        )
        
        return jsonify({
            'document_id': document_id,
            'filename': document.filename,
            'completeness_score': completeness_result['completeness_score'],
            'analysis': completeness_result['analysis'],
            'suggestions': completeness_result['suggestions']
        }), 200
        
    except Exception as e:
        logger.error(f"Error checking document completeness: {str(e)}")
        return jsonify({'error': f'Error checking document completeness: {str(e)}'}), 500

@api_bp.route('/stats', methods=['GET'])
def get_system_stats():
    """Get system statistics."""
    try:
        # Get database stats
        total_documents = Document.query.count()
        total_chunks = DocumentChunk.query.count()
        total_searches = SearchQuery.query.count()
        
        # Get vector store stats
        vector_stats = get_vector_store().get_stats()
        
        # Get recent activity
        recent_documents = Document.query.order_by(Document.upload_time.desc()).limit(5).all()
        recent_searches = SearchQuery.query.order_by(SearchQuery.query_time.desc()).limit(5).all()
        
        return jsonify({
            'database_stats': {
                'total_documents': total_documents,
                'total_chunks': total_chunks,
                'total_searches': total_searches
            },
            'vector_store_stats': vector_stats,
            'recent_documents': [doc.to_dict() for doc in recent_documents],
            'recent_searches': [search.to_dict() for search in recent_searches]
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting system stats: {str(e)}")
        return jsonify({'error': f'Error getting system stats: {str(e)}'}), 500

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from extensions import db
from models import Document, SearchQuery
import logging

logger = logging.getLogger(__name__)

web_bp = Blueprint('web', __name__)

@web_bp.route('/')
def index():
    """Main dashboard page."""
    try:
        # Get recent documents and searches for dashboard
        recent_documents = Document.query.order_by(Document.upload_time.desc()).limit(5).all()
        recent_searches = SearchQuery.query.order_by(SearchQuery.query_time.desc()).limit(5).all()
        
        # Get basic stats
        total_documents = Document.query.count()
        total_searches = SearchQuery.query.count()
        
        return render_template('index.html', 
                             recent_documents=recent_documents,
                             recent_searches=recent_searches,
                             total_documents=total_documents,
                             total_searches=total_searches)
    except Exception as e:
        logger.error(f"Error loading dashboard: {str(e)}")
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return render_template('index.html', 
                             recent_documents=[],
                             recent_searches=[],
                             total_documents=0,
                             total_searches=0)

@web_bp.route('/upload')
def upload_page():
    """Document upload page."""
    return render_template('upload.html')

@web_bp.route('/search')
def search_page():
    """Search interface page."""
    return render_template('search.html')

@web_bp.route('/documents')
def documents_page():
    """List all documents page."""
    try:
        documents = Document.query.order_by(Document.upload_time.desc()).all()
        return render_template('index.html', documents=documents, page='documents')
    except Exception as e:
        logger.error(f"Error loading documents: {str(e)}")
        flash(f'Error loading documents: {str(e)}', 'error')
        return render_template('index.html', documents=[], page='documents')

@web_bp.route('/document/<int:document_id>')
def document_detail(document_id):
    """Document detail page."""
    try:
        document = Document.query.get_or_404(document_id)
        chunks = document.chunks[:10]
        return render_template('index.html', document=document, chunks=chunks, page='document_detail')
    except Exception as e:
        logger.error(f"Error loading document {document_id}: {str(e)}")
        flash(f'Error loading document: {str(e)}', 'error')
        return redirect(url_for('web.index'))

@web_bp.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors."""
    return render_template('index.html', error='Page not found'), 404

@web_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    db.session.rollback()
    return render_template('index.html', error='Internal server error'), 500

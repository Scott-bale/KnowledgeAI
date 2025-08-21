from extensions import db
from datetime import datetime

class Document(db.Model):
    __tablename__ = 'documents'

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(10), nullable=False)
    content = db.Column(db.Text, nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    upload_time = db.Column(db.DateTime, default=datetime.utcnow)
    chunk_count = db.Column(db.Integer, default=0)
    embedding_status = db.Column(db.String(20), default='pending')
    
    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'file_type': self.file_type,
            'file_size': self.file_size,
            'upload_time': self.upload_time.isoformat() if self.upload_time else None,
            'chunk_count': self.chunk_count,
            'embedding_status': self.embedding_status
        }

class DocumentChunk(db.Model):
    __tablename__ = 'document_chunks'

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    chunk_index = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    start_position = db.Column(db.Integer, nullable=False)
    end_position = db.Column(db.Integer, nullable=False)
    
    document = db.relationship('Document', backref=db.backref('chunks', lazy=True, cascade='all, delete-orphan'))
    
    def to_dict(self):
        return {
            'id': self.id,
            'document_id': self.document_id,
            'chunk_index': self.chunk_index,
            'content': self.content,
            'start_position': self.start_position,
            'end_position': self.end_position
        }

class SearchQuery(db.Model):
    __tablename__ = 'search_queries'

    id = db.Column(db.Integer, primary_key=True)
    query_text = db.Column(db.Text, nullable=False)
    query_time = db.Column(db.DateTime, default=datetime.utcnow)
    results_count = db.Column(db.Integer, default=0)
    response_time_ms = db.Column(db.Float, default=0.0)
    
    def to_dict(self):
        return {
            'id': self.id,
            'query_text': self.query_text,
            'query_time': self.query_time.isoformat() if self.query_time else None,
            'results_count': self.results_count,
            'response_time_ms': self.response_time_ms
        }
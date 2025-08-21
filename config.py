import os

class Config:
    
    # Embedding Configuration
    EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION = 384  
    
    # FAISS Configuration
    FAISS_INDEX_PATH = "faiss_index"
    
    # Document Processing Configuration
    MAX_CHUNK_SIZE = 512  
    CHUNK_OVERLAP = 50 
    
    # Search Configuration
    MAX_SEARCH_RESULTS = 10
    SIMILARITY_THRESHOLD = 0.3
    
    # Supported file types
    SUPPORTED_EXTENSIONS = {'.txt', '.pdf', '.docx'}

    # Groq configuration
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
    GROQ_QA_MODEL = os.environ.get(
        "GROQ_QA_MODEL",
        "meta-llama/llama-4-scout-17b-16e-instruct"
    )

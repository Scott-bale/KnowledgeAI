// Main JavaScript file for the AI Knowledge Base application

// Global variables
let uploadInProgress = false;
let searchInProgress = false;

// Utility functions
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDate(dateString) {
    if (!dateString) return 'Unknown';
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

function showToast(message, type = 'info') {
    // Create toast container if it doesn't exist
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
        toastContainer.style.zIndex = '1055';
        document.body.appendChild(toastContainer);
    }
    
    // Create toast element
    const toastId = 'toast-' + Date.now();
    const toastHtml = `
        <div id="${toastId}" class="toast align-items-center text-white bg-${type}" role="alert">
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;
    
    toastContainer.insertAdjacentHTML('beforeend', toastHtml);
    
    // Initialize and show toast
    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, {
        autohide: true,
        delay: type === 'danger' ? 5000 : 3000
    });
    toast.show();
    
    // Remove toast element after it's hidden
    toastElement.addEventListener('hidden.bs.toast', function() {
        toastElement.remove();
    });
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function() {
        showToast('Copied to clipboard!', 'success');
    }).catch(function(err) {
        console.error('Could not copy text: ', err);
        showToast('Failed to copy to clipboard', 'danger');
    });
}

// API helper functions
async function apiCall(url, options = {}) {
    try {
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API call failed:', error);
        throw error;
    }
}

// Document management functions
async function deleteDocument(documentId) {
    if (!confirm('Are you sure you want to delete this document? This action cannot be undone.')) {
        return;
    }
    
    try {
        await apiCall(`/api/documents/${documentId}`, {
            method: 'DELETE'
        });
        
        showToast('Document deleted successfully', 'success');
        
        // Refresh the page or update the UI
        if (typeof loadDocuments === 'function') {
            loadDocuments();
        } else {
            location.reload();
        }
    } catch (error) {
        showToast('Failed to delete document: ' + error.message, 'danger');
    }
}

async function checkDocumentCompleteness(documentId) {
    try {
        showToast('Checking document completeness...', 'info');
        
        const result = await apiCall(`/api/documents/${documentId}/completeness`, {
            method: 'POST'
        });
        
        // Show completeness results in a modal or dedicated area
        showCompletenessResults(result);
        
    } catch (error) {
        showToast('Failed to check document completeness: ' + error.message, 'danger');
    }
}

function showCompletenessResults(result) {
    const modalHtml = `
        <div class="modal fade" id="completeness-modal" tabindex="-1">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="fas fa-check-circle me-2"></i>Document Completeness Analysis
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <h6>Document: ${result.filename}</h6>
                        <hr>
                        
                        <div class="mb-3">
                            <label class="form-label">Completeness Score:</label>
                            <div class="progress mb-2">
                                <div class="progress-bar bg-${result.completeness_score > 0.7 ? 'success' : result.completeness_score > 0.4 ? 'warning' : 'danger'}" 
                                     style="width: ${result.completeness_score * 100}%">
                                    ${(result.completeness_score * 100).toFixed(1)}%
                                </div>
                            </div>
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">Analysis:</label>
                            <div class="border rounded p-3 bg-light">
                                ${result.analysis}
                            </div>
                        </div>
                        
                        ${result.suggestions && result.suggestions.length > 0 ? `
                            <div class="mb-3">
                                <label class="form-label">Suggestions for Improvement:</label>
                                <ul class="list-group">
                                    ${result.suggestions.map(suggestion => `
                                        <li class="list-group-item">
                                            <i class="fas fa-lightbulb me-2 text-warning"></i>${suggestion}
                                        </li>
                                    `).join('')}
                                </ul>
                            </div>
                        ` : ''}
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Remove existing modal if present
    const existingModal = document.getElementById('completeness-modal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // Add modal to page
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('completeness-modal'));
    modal.show();
    
    // Clean up when modal is hidden
    document.getElementById('completeness-modal').addEventListener('hidden.bs.modal', function() {
        this.remove();
    });
}

// Search and Q&A helper functions
function highlightSearchTerms(text, query) {
    if (!query || !text) return text;
    
    const words = query.toLowerCase().split(/\s+/).filter(word => word.length > 2);
    let highlighted = text;
    
    words.forEach(word => {
        const regex = new RegExp(`\\b${escapeRegex(word)}\\b`, 'gi');
        highlighted = highlighted.replace(regex, '<mark>$&</mark>');
    });
    
    return highlighted;
}

function escapeRegex(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function truncateText(text, maxLength = 200) {
    if (!text || text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}

// File upload helpers
function validateFile(file) {
    const allowedTypes = ['application/pdf', 'text/plain', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
    const allowedExtensions = ['.pdf', '.txt', '.docx'];
    const maxSize = 50 * 1024 * 1024; // 50MB
    
    // Check file type
    const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
    if (!allowedExtensions.includes(fileExtension)) {
        throw new Error(`File type not supported. Allowed types: ${allowedExtensions.join(', ')}`);
    }
    
    // Check file size
    if (file.size > maxSize) {
        throw new Error(`File too large. Maximum size is ${formatFileSize(maxSize)}`);
    }
    
    return true;
}

// Initialize tooltips and popovers
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize Bootstrap popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });
});

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Ctrl/Cmd + K for search
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        const searchInput = document.getElementById('search-input') || document.getElementById('question-input');
        if (searchInput) {
            searchInput.focus();
        }
    }
    
    // Escape to clear search
    if (e.key === 'Escape') {
        const activeElement = document.activeElement;
        if (activeElement && (activeElement.id === 'search-input' || activeElement.id === 'question-input')) {
            activeElement.value = '';
            activeElement.blur();
        }
    }
});

// Export utility functions for use in other scripts
window.KnowledgeBase = {
    formatFileSize,
    formatDate,
    showToast,
    copyToClipboard,
    apiCall,
    deleteDocument,
    checkDocumentCompleteness,
    highlightSearchTerms,
    truncateText,
    validateFile
};

// Service worker registration for offline functionality (optional)
if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
        // Register service worker if available
        // navigator.serviceWorker.register('/sw.js');
    });
}

console.log('AI Knowledge Base - Main JavaScript loaded successfully');

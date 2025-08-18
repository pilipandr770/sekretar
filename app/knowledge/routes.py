"""Knowledge management API endpoints."""
from functools import wraps
from flask import request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_current_user
from app.knowledge import knowledge_bp
from app.services.knowledge_service import KnowledgeService
from app.utils.response import success_response, error_response, paginated_response
from app.utils.exceptions import ValidationError, ProcessingError
def validate_json_data(request, required_fields=None):
    """Validate JSON request data."""
    if not request.is_json:
        raise ValidationError("Request must be JSON")
    
    data = request.get_json()
    if data is None:
        raise ValidationError("Invalid JSON data")
    
    if required_fields:
        for field in required_fields:
            if field not in data:
                raise ValidationError(f"Missing required field: {field}")
    
    return data


def tenant_required(f):
    """Decorator to require tenant context and pass tenant_id to function."""
    @wraps(f)
    @jwt_required()
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user or not user.tenant_id:
            return error_response(
                error_code="AUTHORIZATION_ERROR",
                message="Tenant context required",
                status_code=403
            )
        return f(user.tenant_id, *args, **kwargs)
    return decorated_function


@knowledge_bp.route('/sources', methods=['GET'])
@jwt_required()
@tenant_required
def get_knowledge_sources(tenant_id):
    """Get knowledge sources for tenant."""
    try:
        status = request.args.get('status')
        sources = KnowledgeService.get_sources(tenant_id, status=status)
        
        return success_response(
            message="Knowledge sources retrieved successfully",
            data={
                'sources': [source.to_dict() for source in sources],
                'total': len(sources)
            }
        )
        
    except Exception as e:
        current_app.logger.error(f"Failed to get knowledge sources: {str(e)}")
        return error_response(
            error_code="KNOWLEDGE_SOURCES_FETCH_FAILED",
            message="Failed to retrieve knowledge sources",
            status_code=500,
            details=str(e)
        )


@knowledge_bp.route('/sources', methods=['POST'])
@jwt_required()
@tenant_required
def create_knowledge_source(tenant_id):
    """Create a new knowledge source."""
    try:
        data = validate_json_data(request, required_fields=['name', 'source_type'])
        
        name = data['name']
        source_type = data['source_type']
        description = data.get('description')
        tags = data.get('tags', [])
        
        if source_type == 'document':
            source = KnowledgeService.create_document_source(
                tenant_id=tenant_id,
                name=name,
                description=description,
                tags=tags
            )
        elif source_type == 'url':
            url = data.get('url')
            if not url:
                return error_response(
                    error_code="VALIDATION_ERROR",
                    message="URL is required for URL sources",
                    status_code=400
                )
            
            crawl_frequency = data.get('crawl_frequency', 'manual')
            max_depth = data.get('max_depth', 1)
            
            source = KnowledgeService.create_url_source(
                tenant_id=tenant_id,
                name=name,
                url=url,
                description=description,
                tags=tags,
                crawl_frequency=crawl_frequency,
                max_depth=max_depth
            )
        else:
            return error_response(
                error_code="VALIDATION_ERROR",
                message="Invalid source type. Must be 'document' or 'url'",
                status_code=400
            )
        
        return success_response(
            message="Knowledge source created successfully",
            data={'source': source.to_dict()},
            status_code=201
        )
        
    except ValidationError as e:
        return error_response(
            error_code="VALIDATION_ERROR",
            message=str(e),
            status_code=400
        )
    except ProcessingError as e:
        return error_response(
            error_code="PROCESSING_ERROR",
            message=str(e),
            status_code=500
        )
    except Exception as e:
        current_app.logger.error(f"Failed to create knowledge source: {str(e)}")
        return error_response(
            error_code="KNOWLEDGE_SOURCE_CREATE_FAILED",
            message="Failed to create knowledge source",
            status_code=500,
            details=str(e)
        )


@knowledge_bp.route('/sources/<int:source_id>', methods=['GET'])
@jwt_required()
@tenant_required
def get_knowledge_source(tenant_id, source_id):
    """Get a specific knowledge source."""
    try:
        from app.models.knowledge import KnowledgeSource
        
        source = KnowledgeSource.get_by_id(source_id)
        if not source or source.tenant_id != tenant_id:
            return error_response(
                error_code="NOT_FOUND",
                message="Knowledge source not found",
                status_code=404
            )
        
        return success_response(
            message="Knowledge source retrieved successfully",
            data={'source': source.to_dict()}
        )
        
    except Exception as e:
        current_app.logger.error(f"Failed to get knowledge source: {str(e)}")
        return error_response(
            error_code="KNOWLEDGE_SOURCE_FETCH_FAILED",
            message="Failed to retrieve knowledge source",
            status_code=500,
            details=str(e)
        )


@knowledge_bp.route('/sources/<int:source_id>', methods=['DELETE'])
@jwt_required()
@tenant_required
def delete_knowledge_source(tenant_id, source_id):
    """Delete a knowledge source."""
    try:
        success = KnowledgeService.delete_source(tenant_id, source_id)
        
        if success:
            return success_response(
                message="Knowledge source deleted successfully",
                data={'deleted': True}
            )
        else:
            return error_response(
                error_code="DELETE_FAILED",
                message="Failed to delete knowledge source",
                status_code=500
            )
        
    except ValidationError as e:
        return error_response(
            error_code="NOT_FOUND",
            message=str(e),
            status_code=404
        )
    except ProcessingError as e:
        return error_response(
            error_code="PROCESSING_ERROR",
            message=str(e),
            status_code=500
        )
    except Exception as e:
        current_app.logger.error(f"Failed to delete knowledge source: {str(e)}")
        return error_response(
            error_code="KNOWLEDGE_SOURCE_DELETE_FAILED",
            message="Failed to delete knowledge source",
            status_code=500,
            details=str(e)
        )


@knowledge_bp.route('/sources/<int:source_id>/documents', methods=['GET'])
@jwt_required()
@tenant_required
def get_source_documents(tenant_id, source_id):
    """Get documents for a knowledge source."""
    try:
        documents = KnowledgeService.get_source_documents(tenant_id, source_id)
        
        return success_response(
            message="Source documents retrieved successfully",
            data={
                'documents': [doc.to_dict() for doc in documents],
                'total': len(documents)
            }
        )
        
    except ValidationError as e:
        return error_response(
            error_code="NOT_FOUND",
            message=str(e),
            status_code=404
        )
    except ProcessingError as e:
        return error_response(
            error_code="PROCESSING_ERROR",
            message=str(e),
            status_code=500
        )
    except Exception as e:
        current_app.logger.error(f"Failed to get source documents: {str(e)}")
        return error_response(
            error_code="SOURCE_DOCUMENTS_FETCH_FAILED",
            message="Failed to retrieve source documents",
            status_code=500,
            details=str(e)
        )


@knowledge_bp.route('/sources/<int:source_id>/upload', methods=['POST'])
@jwt_required()
@tenant_required
def upload_document(tenant_id, source_id):
    """Upload a document to a knowledge source."""
    try:
        if 'file' not in request.files:
            return error_response(
                error_code="VALIDATION_ERROR",
                message="No file provided",
                status_code=400
            )
        
        file = request.files['file']
        title = request.form.get('title')
        
        document = KnowledgeService.upload_document(
            tenant_id=tenant_id,
            source_id=source_id,
            file=file,
            title=title
        )
        
        return success_response(
            message="Document uploaded successfully",
            data={'document': document.to_dict()},
            status_code=201
        )
        
    except ValidationError as e:
        return error_response(
            error_code="VALIDATION_ERROR",
            message=str(e),
            status_code=400
        )
    except ProcessingError as e:
        return error_response(
            error_code="PROCESSING_ERROR",
            message=str(e),
            status_code=500
        )
    except Exception as e:
        current_app.logger.error(f"Failed to upload document: {str(e)}")
        return error_response(
            error_code="DOCUMENT_UPLOAD_FAILED",
            message="Failed to upload document",
            status_code=500,
            details=str(e)
        )


@knowledge_bp.route('/sources/<int:source_id>/crawl', methods=['POST'])
@jwt_required()
@tenant_required
def crawl_url_source(tenant_id, source_id):
    """Crawl URL for a knowledge source."""
    try:
        data = request.get_json() or {}
        url = data.get('url')  # Optional - will use source URL if not provided
        
        documents = KnowledgeService.crawl_url(
            tenant_id=tenant_id,
            source_id=source_id,
            url=url
        )
        
        return success_response(
            message="URL crawled successfully",
            data={
                'documents': [doc.to_dict() for doc in documents],
                'total': len(documents)
            }
        )
        
    except ValidationError as e:
        return error_response(
            error_code="VALIDATION_ERROR",
            message=str(e),
            status_code=400
        )
    except ProcessingError as e:
        return error_response(
            error_code="PROCESSING_ERROR",
            message=str(e),
            status_code=500
        )
    except Exception as e:
        current_app.logger.error(f"Failed to crawl URL: {str(e)}")
        return error_response(
            error_code="URL_CRAWL_FAILED",
            message="Failed to crawl URL",
            status_code=500,
            details=str(e)
        )


@knowledge_bp.route('/documents/<int:document_id>', methods=['GET'])
@jwt_required()
@tenant_required
def get_document(tenant_id, document_id):
    """Get a specific document."""
    try:
        from app.models.knowledge import Document
        
        document = Document.get_by_id(document_id)
        if not document or document.tenant_id != tenant_id:
            return error_response(
                error_code="NOT_FOUND",
                message="Document not found",
                status_code=404
            )
        
        # Include full content for individual document view
        doc_data = document.to_dict()
        doc_data['content'] = document.content
        
        return success_response(
            message="Document retrieved successfully",
            data={'document': doc_data}
        )
        
    except Exception as e:
        current_app.logger.error(f"Failed to get document: {str(e)}")
        return error_response(
            error_code="DOCUMENT_FETCH_FAILED",
            message="Failed to retrieve document",
            status_code=500,
            details=str(e)
        )


@knowledge_bp.route('/documents/<int:document_id>', methods=['DELETE'])
@jwt_required()
@tenant_required
def delete_document(tenant_id, document_id):
    """Delete a document."""
    try:
        success = KnowledgeService.delete_document(tenant_id, document_id)
        
        if success:
            return success_response(
                message="Document deleted successfully",
                data={'deleted': True}
            )
        else:
            return error_response(
                error_code="DELETE_FAILED",
                message="Failed to delete document",
                status_code=500
            )
        
    except ValidationError as e:
        return error_response(
            error_code="NOT_FOUND",
            message=str(e),
            status_code=404
        )
    except ProcessingError as e:
        return error_response(
            error_code="PROCESSING_ERROR",
            message=str(e),
            status_code=500
        )
    except Exception as e:
        current_app.logger.error(f"Failed to delete document: {str(e)}")
        return error_response(
            error_code="DOCUMENT_DELETE_FAILED",
            message="Failed to delete document",
            status_code=500,
            details=str(e)
        )


@knowledge_bp.route('/search', methods=['POST'])
@jwt_required()
@tenant_required
def search_knowledge(tenant_id):
    """Search the knowledge base with enhanced options."""
    try:
        data = validate_json_data(request, required_fields=['query'])
        
        query = data['query']
        limit = data.get('limit', 10)
        min_similarity = data.get('min_similarity', 0.7)
        model = data.get('model')  # Optional embedding model
        source_ids = data.get('source_ids')  # Optional source filtering
        
        # Validate parameters
        if not query.strip():
            return error_response(
                error_code="VALIDATION_ERROR",
                message="Search query cannot be empty",
                status_code=400
            )
        
        if limit < 1 or limit > 50:
            return error_response(
                error_code="VALIDATION_ERROR",
                message="Limit must be between 1 and 50",
                status_code=400
            )
        
        if min_similarity < 0 or min_similarity > 1:
            return error_response(
                error_code="VALIDATION_ERROR",
                message="Minimum similarity must be between 0 and 1",
                status_code=400
            )
        
        # Validate model if provided
        if model and not KnowledgeService.validate_embedding_model(model):
            return error_response(
                error_code="VALIDATION_ERROR",
                message=f"Unsupported embedding model: {model}",
                status_code=400
            )
        
        # Validate source IDs if provided
        if source_ids:
            if not isinstance(source_ids, list) or not all(isinstance(sid, int) for sid in source_ids):
                return error_response(
                    error_code="VALIDATION_ERROR",
                    message="source_ids must be a list of integers",
                    status_code=400
                )
        
        results = KnowledgeService.search_knowledge(
            tenant_id=tenant_id,
            query=query,
            limit=limit,
            min_similarity=min_similarity,
            model=model,
            source_ids=source_ids
        )
        
        return success_response(
            message="Knowledge search completed successfully",
            data={
                'query': query,
                'results': results,
                'total': len(results),
                'limit': limit,
                'min_similarity': min_similarity,
                'model_used': model,
                'source_ids_filter': source_ids
            }
        )
        
    except ValidationError as e:
        return error_response(
            error_code="VALIDATION_ERROR",
            message=str(e),
            status_code=400
        )
    except ProcessingError as e:
        return error_response(
            error_code="PROCESSING_ERROR",
            message=str(e),
            status_code=500
        )
    except Exception as e:
        current_app.logger.error(f"Failed to search knowledge: {str(e)}")
        return error_response(
            error_code="KNOWLEDGE_SEARCH_FAILED",
            message="Failed to search knowledge base",
            status_code=500,
            details=str(e)
        )


@knowledge_bp.route('/sources/<int:source_id>/embeddings', methods=['POST'])
@jwt_required()
@tenant_required
def generate_source_embeddings(tenant_id, source_id):
    """Generate embeddings for all documents in a knowledge source."""
    try:
        result = KnowledgeService.generate_embeddings(tenant_id, source_id=source_id)
        
        return success_response(
            message="Embeddings generated successfully",
            data=result
        )
        
    except ValidationError as e:
        return error_response(
            error_code="VALIDATION_ERROR",
            message=str(e),
            status_code=400
        )
    except ProcessingError as e:
        return error_response(
            error_code="PROCESSING_ERROR",
            message=str(e),
            status_code=500
        )
    except Exception as e:
        current_app.logger.error(f"Failed to generate source embeddings: {str(e)}")
        return error_response(
            error_code="EMBEDDING_GENERATION_FAILED",
            message="Failed to generate embeddings",
            status_code=500,
            details=str(e)
        )


@knowledge_bp.route('/sources/<int:source_id>/reindex', methods=['POST'])
@jwt_required()
@tenant_required
def reindex_source_embeddings(tenant_id, source_id):
    """Re-index embeddings for a knowledge source."""
    try:
        result = KnowledgeService.reindex_embeddings(tenant_id, source_id)
        
        return success_response(
            message="Embeddings re-indexed successfully",
            data=result
        )
        
    except ValidationError as e:
        return error_response(
            error_code="VALIDATION_ERROR",
            message=str(e),
            status_code=400
        )
    except ProcessingError as e:
        return error_response(
            error_code="PROCESSING_ERROR",
            message=str(e),
            status_code=500
        )
    except Exception as e:
        current_app.logger.error(f"Failed to re-index source embeddings: {str(e)}")
        return error_response(
            error_code="EMBEDDING_REINDEX_FAILED",
            message="Failed to re-index embeddings",
            status_code=500,
            details=str(e)
        )


@knowledge_bp.route('/documents/<int:document_id>/embeddings', methods=['POST'])
@jwt_required()
@tenant_required
def generate_document_embeddings(tenant_id, document_id):
    """Generate embeddings for a specific document."""
    try:
        result = KnowledgeService.generate_embeddings(tenant_id, document_id=document_id)
        
        return success_response(
            message="Document embeddings generated successfully",
            data=result
        )
        
    except ValidationError as e:
        return error_response(
            error_code="VALIDATION_ERROR",
            message=str(e),
            status_code=400
        )
    except ProcessingError as e:
        return error_response(
            error_code="PROCESSING_ERROR",
            message=str(e),
            status_code=500
        )
    except Exception as e:
        current_app.logger.error(f"Failed to generate document embeddings: {str(e)}")
        return error_response(
            error_code="EMBEDDING_GENERATION_FAILED",
            message="Failed to generate document embeddings",
            status_code=500,
            details=str(e)
        )


@knowledge_bp.route('/models', methods=['GET'])
@jwt_required()
def get_embedding_models():
    """Get available embedding models."""
    try:
        models = KnowledgeService.get_available_embedding_models()
        
        return success_response(
            message="Available embedding models retrieved successfully",
            data={
                'models': models,
                'default_model': 'text-embedding-ada-002'
            }
        )
        
    except ProcessingError as e:
        return error_response(
            error_code="PROCESSING_ERROR",
            message=str(e),
            status_code=500
        )
    except Exception as e:
        current_app.logger.error(f"Failed to get embedding models: {str(e)}")
        return error_response(
            error_code="EMBEDDING_MODELS_FAILED",
            message="Failed to retrieve embedding models",
            status_code=500,
            details=str(e)
        )


@knowledge_bp.route('/stats', methods=['GET'])
@jwt_required()
@tenant_required
def get_knowledge_stats(tenant_id):
    """Get knowledge base statistics."""
    try:
        from app.models.knowledge import KnowledgeSource, Document, Chunk
        from sqlalchemy import func
        
        # Get source statistics
        source_stats = KnowledgeSource.query.filter_by(tenant_id=tenant_id)\
            .with_entities(
                KnowledgeSource.status,
                func.count(KnowledgeSource.id).label('count')
            )\
            .group_by(KnowledgeSource.status)\
            .all()
        
        # Get document statistics
        doc_stats = Document.query.filter_by(tenant_id=tenant_id)\
            .with_entities(
                func.count(Document.id).label('total_documents'),
                func.sum(Document.token_count).label('total_tokens')
            )\
            .first()
        
        # Get chunk statistics
        chunk_stats = Chunk.query.filter_by(tenant_id=tenant_id)\
            .with_entities(
                func.count(Chunk.id).label('total_chunks')
            )\
            .first()
        
        # Get embedding statistics
        try:
            embedding_stats = KnowledgeService.get_embedding_stats(tenant_id)
        except Exception as e:
            current_app.logger.warning(f"Failed to get embedding stats: {str(e)}")
            embedding_stats = {
                'total_embeddings': 0,
                'embeddings_by_model': {},
                'total_chunks': 0,
                'embedded_chunks': 0,
                'embedding_coverage': 0
            }
        
        # Format source statistics
        sources_by_status = {status: count for status, count in source_stats}
        
        return success_response(
            message="Knowledge statistics retrieved successfully",
            data={
                'sources': {
                    'total': sum(sources_by_status.values()),
                    'by_status': sources_by_status,
                    'active': sources_by_status.get('completed', 0),
                    'processing': sources_by_status.get('processing', 0),
                    'pending': sources_by_status.get('pending', 0),
                    'error': sources_by_status.get('error', 0)
                },
                'documents': {
                    'total': doc_stats.total_documents or 0,
                    'total_tokens': doc_stats.total_tokens or 0
                },
                'chunks': {
                    'total': chunk_stats.total_chunks or 0
                },
                'embeddings': embedding_stats
            }
        )
        
    except Exception as e:
        current_app.logger.error(f"Failed to get knowledge stats: {str(e)}")
        return error_response(
            error_code="KNOWLEDGE_STATS_FAILED",
            message="Failed to retrieve knowledge statistics",
            status_code=500,
            details=str(e)
        )
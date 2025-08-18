"""Knowledge management service for RAG system."""
import os
import hashlib
import mimetypes
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse
import requests
from werkzeug.utils import secure_filename
from flask import current_app
from app.models.knowledge import KnowledgeSource, Document, Chunk, Embedding
from app.services.document_processor import DocumentProcessor
from app.services.web_scraper import WebScraper
from app.services.text_chunker import TextChunker, ChunkConfig
from app.services.embedding_service import EmbeddingService
from app import db
from app.utils.exceptions import ValidationError, ProcessingError


class KnowledgeService:
    """Service for managing knowledge base operations."""
    
    ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'md', 'txt', 'html', 'htm'}
    MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB
    
    @classmethod
    def create_document_source(cls, tenant_id: int, name: str, description: str = None, 
                             tags: List[str] = None) -> KnowledgeSource:
        """Create a new document-based knowledge source."""
        try:
            source = KnowledgeSource.create_document_source(
                tenant_id=tenant_id,
                name=name,
                description=description,
                tags=tags or []
            )
            source.save()
            return source
        except Exception as e:
            current_app.logger.error(f"Failed to create document source: {str(e)}")
            raise ProcessingError(f"Failed to create knowledge source: {str(e)}")
    
    @classmethod
    def create_url_source(cls, tenant_id: int, name: str, url: str, 
                         description: str = None, tags: List[str] = None,
                         crawl_frequency: str = 'manual', max_depth: int = 1) -> KnowledgeSource:
        """Create a new URL-based knowledge source."""
        try:
            # Validate URL
            if not cls._is_valid_url(url):
                raise ValidationError("Invalid URL format")
            
            source = KnowledgeSource.create_url_source(
                tenant_id=tenant_id,
                name=name,
                url=url,
                description=description,
                tags=tags or [],
                crawl_frequency=crawl_frequency,
                max_depth=max_depth
            )
            source.save()
            return source
        except ValidationError:
            raise
        except Exception as e:
            current_app.logger.error(f"Failed to create URL source: {str(e)}")
            raise ProcessingError(f"Failed to create knowledge source: {str(e)}")
    
    @classmethod
    def upload_document(cls, tenant_id: int, source_id: int, file, title: str = None) -> Document:
        """Upload and process a document."""
        try:
            # Validate file
            if not file or not file.filename:
                raise ValidationError("No file provided")
            
            if not cls._is_allowed_file(file.filename):
                raise ValidationError(f"File type not allowed. Allowed types: {', '.join(cls.ALLOWED_EXTENSIONS)}")
            
            # Get source
            source = KnowledgeSource.get_by_id(source_id)
            if not source or source.tenant_id != tenant_id:
                raise ValidationError("Knowledge source not found")
            
            if source.source_type != 'document':
                raise ValidationError("Source is not configured for document uploads")
            
            # Secure filename
            filename = secure_filename(file.filename)
            if not filename:
                raise ValidationError("Invalid filename")
            
            # Create upload directory if it doesn't exist
            upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'knowledge', str(tenant_id))
            os.makedirs(upload_dir, exist_ok=True)
            
            # Save file
            file_path = os.path.join(upload_dir, filename)
            file.save(file_path)
            
            # Get file info
            file_size = os.path.getsize(file_path)
            mime_type = mimetypes.guess_type(filename)[0]
            
            # Process document using DocumentProcessor
            processor_result = DocumentProcessor.extract_text_from_file(file_path, mime_type)
            
            # Create document
            document = Document.create(
                tenant_id=tenant_id,
                source_id=source_id,
                title=title or processor_result['metadata'].get('title', filename),
                content=processor_result['content'],
                filename=filename,
                file_path=file_path,
                file_size=file_size,
                mime_type=mime_type,
                token_count=processor_result['token_count'],
                content_hash=processor_result['content_hash']
            )
            
            # Mark as processing
            document.mark_as_processing()
            document.save()
            
            # Create chunks using TextChunker
            chunker = TextChunker()
            chunks_data = chunker.chunk_document_content(
                processor_result['content'], 
                processor_result['metadata']
            )
            
            # Save chunks to database
            for chunk_data in chunks_data:
                chunk = Chunk.create(
                    tenant_id=tenant_id,
                    document_id=document.id,
                    content=chunk_data['content'],
                    position=chunk_data['position'],
                    token_count=chunk_data['token_count'],
                    overlap_start=chunk_data['overlap_start'],
                    overlap_end=chunk_data['overlap_end'],
                    extra_data={
                        'chunk_type': chunk_data.get('chunk_type', 'unknown'),
                        'is_first': chunk_data.get('is_first', False),
                        'is_last': chunk_data.get('is_last', False)
                    }
                )
                chunk.save()
            
            # Mark document as completed
            document.mark_as_completed()
            document.save()
            
            # Generate embeddings for the document
            try:
                embedding_service = EmbeddingService()
                embeddings = embedding_service.create_document_embeddings(tenant_id, document.id)
                current_app.logger.info(f"Generated {len(embeddings)} embeddings for document {document.id}")
            except Exception as e:
                current_app.logger.warning(f"Failed to generate embeddings for document {document.id}: {str(e)}")
                # Don't fail the entire upload if embedding generation fails
            
            # Update source statistics
            source.update_statistics()
            source.save()
            
            current_app.logger.info(f"Successfully processed document {filename} with {len(chunks_data)} chunks")
            
            return document
            
        except (ValidationError, ProcessingError):
            raise
        except Exception as e:
            current_app.logger.error(f"Failed to upload document: {str(e)}")
            raise ProcessingError(f"Failed to upload document: {str(e)}")
    
    @classmethod
    def crawl_url(cls, tenant_id: int, source_id: int, url: str = None) -> List[Document]:
        """Crawl URL and create documents."""
        try:
            # Get source
            source = KnowledgeSource.get_by_id(source_id)
            if not source or source.tenant_id != tenant_id:
                raise ValidationError("Knowledge source not found")
            
            if source.source_type != 'url':
                raise ValidationError("Source is not configured for URL crawling")
            
            # Use source URL if not provided
            crawl_url = url or source.source_url
            if not crawl_url:
                raise ValidationError("No URL to crawl")
            
            # Mark source as processing
            source.mark_as_processing()
            source.save()
            
            try:
                # Crawl URL using WebScraper
                with WebScraper(respect_robots=True, delay=1.0) as scraper:
                    scraped_content = scraper.scrape_url(crawl_url, max_depth=source.max_depth)
                
                documents = []
                
                for content_data in scraped_content:
                    # Check for duplicate content
                    content_hash = hashlib.sha256(content_data['content'].encode('utf-8')).hexdigest()
                    existing_doc = Document.find_by_content_hash(tenant_id, content_hash)
                    
                    if existing_doc:
                        current_app.logger.info(f"Skipping duplicate content from {content_data['url']}")
                        continue
                    
                    # Create document
                    document = Document.create(
                        tenant_id=tenant_id,
                        source_id=source_id,
                        title=content_data['title'],
                        content=content_data['content'],
                        url=content_data['url'],
                        token_count=content_data['token_count'],
                        content_hash=content_hash
                    )
                    
                    # Mark as processing
                    document.mark_as_processing()
                    document.save()
                    
                    # Create chunks using TextChunker
                    chunker = TextChunker()
                    chunks_data = chunker.chunk_document_content(
                        content_data['content'], 
                        content_data['metadata']
                    )
                    
                    # Save chunks to database
                    for chunk_data in chunks_data:
                        chunk = Chunk.create(
                            tenant_id=tenant_id,
                            document_id=document.id,
                            content=chunk_data['content'],
                            position=chunk_data['position'],
                            token_count=chunk_data['token_count'],
                            overlap_start=chunk_data['overlap_start'],
                            overlap_end=chunk_data['overlap_end'],
                            extra_data={
                                'chunk_type': chunk_data.get('chunk_type', 'unknown'),
                                'is_first': chunk_data.get('is_first', False),
                                'is_last': chunk_data.get('is_last', False),
                                'source_url': content_data['url']
                            }
                        )
                        chunk.save()
                    
                    # Mark document as completed
                    document.mark_as_completed()
                    document.save()
                    
                    # Generate embeddings for the document
                    try:
                        embedding_service = EmbeddingService()
                        embeddings = embedding_service.create_document_embeddings(tenant_id, document.id)
                        current_app.logger.info(f"Generated {len(embeddings)} embeddings for document {document.id}")
                    except Exception as e:
                        current_app.logger.warning(f"Failed to generate embeddings for document {document.id}: {str(e)}")
                        # Don't fail the entire crawl if embedding generation fails
                    
                    documents.append(document)
                    
                    current_app.logger.info(f"Successfully processed URL {content_data['url']} with {len(chunks_data)} chunks")
                
                # Mark source as completed
                source.mark_as_completed()
                source.update_statistics()
                source.save()
                
                return documents
                
            except Exception as e:
                # Mark source as error
                source.mark_as_error(str(e))
                source.save()
                raise
                
        except (ValidationError, ProcessingError):
            raise
        except Exception as e:
            current_app.logger.error(f"Failed to crawl URL: {str(e)}")
            raise ProcessingError(f"Failed to crawl URL: {str(e)}")
    
    @classmethod
    def search_knowledge(cls, tenant_id: int, query: str, limit: int = 10, 
                        min_similarity: float = 0.7, model: str = None, 
                        source_ids: List[int] = None) -> List[Dict[str, Any]]:
        """Search knowledge base for relevant information using vector similarity."""
        try:
            # Try vector similarity search first
            try:
                embedding_service = EmbeddingService()
                vector_results = embedding_service.search_similar_chunks(
                    tenant_id=tenant_id,
                    query=query,
                    limit=limit,
                    min_similarity=min_similarity,
                    model=model,
                    source_ids=source_ids
                )
                
                if vector_results:
                    current_app.logger.info(f"Found {len(vector_results)} results using vector search")
                    return vector_results
                    
            except Exception as e:
                current_app.logger.warning(f"Vector search failed, falling back to text search: {str(e)}")
            
            # Fallback to text-based search if vector search fails or returns no results
            from sqlalchemy import and_, or_
            
            search_terms = query.lower().split()
            
            # Search in document titles and content
            documents = Document.query.join(KnowledgeSource).filter(
                and_(
                    Document.tenant_id == tenant_id,
                    KnowledgeSource.status == 'completed',
                    or_(*[
                        Document.title.ilike(f'%{term}%') 
                        for term in search_terms
                    ])
                )
            ).limit(limit).all()
            
            results = []
            for doc in documents:
                # Calculate simple relevance score based on term matches
                title_lower = doc.title.lower()
                content_lower = (doc.content or '').lower()
                
                score = 0
                for term in search_terms:
                    if term in title_lower:
                        score += 2  # Title matches are more important
                    if term in content_lower:
                        score += 1
                
                if score > 0:
                    results.append({
                        'document_id': doc.id,
                        'title': doc.title,
                        'content': doc.content[:500] if doc.content else '',
                        'content_preview': doc.content[:500] if doc.content else '',
                        'source_name': doc.source.name,
                        'source_type': doc.source.source_type,
                        'url': doc.url,
                        'similarity_score': min(score / 10.0, 1.0),  # Normalize to 0-1 range
                        'citations': {
                            'source': doc.source.name,
                            'title': doc.title,
                            'url': doc.url or doc.source.source_url,
                            'document_id': doc.id,
                            'source_id': doc.source.id,
                            'source_type': doc.source.source_type
                        },
                        'metadata': {
                            'document_title': doc.title,
                            'source_name': doc.source.name,
                            'source_type': doc.source.source_type,
                            'url': doc.url,
                            'search_type': 'text_fallback'
                        }
                    })
            
            # Sort by relevance score
            results.sort(key=lambda x: x['similarity_score'], reverse=True)
            
            current_app.logger.info(f"Found {len(results)} results using text search fallback")
            return results
            
        except Exception as e:
            current_app.logger.error(f"Failed to search knowledge: {str(e)}")
            raise ProcessingError(f"Failed to search knowledge: {str(e)}")
    
    @classmethod
    def get_sources(cls, tenant_id: int, status: str = None) -> List[KnowledgeSource]:
        """Get knowledge sources for tenant."""
        try:
            query = KnowledgeSource.query.filter_by(tenant_id=tenant_id)
            
            if status:
                query = query.filter_by(status=status)
            
            return query.order_by(KnowledgeSource.created_at.desc()).all()
            
        except Exception as e:
            current_app.logger.error(f"Failed to get sources: {str(e)}")
            raise ProcessingError(f"Failed to get sources: {str(e)}")
    
    @classmethod
    def get_source_documents(cls, tenant_id: int, source_id: int) -> List[Document]:
        """Get documents for a knowledge source."""
        try:
            source = KnowledgeSource.get_by_id(source_id)
            if not source or source.tenant_id != tenant_id:
                raise ValidationError("Knowledge source not found")
            
            return Document.get_by_source(source_id)
            
        except ValidationError:
            raise
        except Exception as e:
            current_app.logger.error(f"Failed to get source documents: {str(e)}")
            raise ProcessingError(f"Failed to get source documents: {str(e)}")
    
    @classmethod
    def delete_source(cls, tenant_id: int, source_id: int) -> bool:
        """Delete a knowledge source and all its documents."""
        try:
            source = KnowledgeSource.get_by_id(source_id)
            if not source or source.tenant_id != tenant_id:
                raise ValidationError("Knowledge source not found")
            
            # Delete associated files
            for document in source.documents:
                if document.file_path and os.path.exists(document.file_path):
                    try:
                        os.remove(document.file_path)
                    except OSError:
                        pass  # File might already be deleted
            
            # Delete source (cascades to documents, chunks, embeddings)
            source.delete()
            
            return True
            
        except ValidationError:
            raise
        except Exception as e:
            current_app.logger.error(f"Failed to delete source: {str(e)}")
            raise ProcessingError(f"Failed to delete source: {str(e)}")
    
    @classmethod
    def delete_document(cls, tenant_id: int, document_id: int) -> bool:
        """Delete a document."""
        try:
            document = Document.get_by_id(document_id)
            if not document or document.tenant_id != tenant_id:
                raise ValidationError("Document not found")
            
            # Delete associated file
            if document.file_path and os.path.exists(document.file_path):
                try:
                    os.remove(document.file_path)
                except OSError:
                    pass  # File might already be deleted
            
            # Update source statistics
            source = document.source
            document.delete()
            source.update_statistics()
            source.save()
            
            return True
            
        except ValidationError:
            raise
        except Exception as e:
            current_app.logger.error(f"Failed to delete document: {str(e)}")
            raise ProcessingError(f"Failed to delete document: {str(e)}")
    
    @staticmethod
    def _is_allowed_file(filename: str) -> bool:
        """Check if file extension is allowed."""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in KnowledgeService.ALLOWED_EXTENSIONS
    
    @classmethod
    def generate_embeddings(cls, tenant_id: int, source_id: int = None, document_id: int = None) -> Dict[str, Any]:
        """Generate embeddings for a source or specific document."""
        try:
            embedding_service = EmbeddingService()
            
            if document_id:
                # Generate embeddings for specific document
                document = Document.get_by_id(document_id)
                if not document or document.tenant_id != tenant_id:
                    raise ValidationError("Document not found")
                
                embeddings = embedding_service.create_document_embeddings(tenant_id, document_id)
                
                return {
                    'document_id': document_id,
                    'embeddings_created': len(embeddings),
                    'status': 'completed'
                }
                
            elif source_id:
                # Generate embeddings for all documents in source
                source = KnowledgeSource.get_by_id(source_id)
                if not source or source.tenant_id != tenant_id:
                    raise ValidationError("Knowledge source not found")
                
                documents = Document.get_by_source(source_id)
                total_embeddings = 0
                
                for document in documents:
                    try:
                        embeddings = embedding_service.create_document_embeddings(tenant_id, document.id)
                        total_embeddings += len(embeddings)
                    except Exception as e:
                        current_app.logger.warning(f"Failed to generate embeddings for document {document.id}: {str(e)}")
                        continue
                
                return {
                    'source_id': source_id,
                    'documents_processed': len(documents),
                    'embeddings_created': total_embeddings,
                    'status': 'completed'
                }
            else:
                raise ValidationError("Either source_id or document_id must be provided")
                
        except (ValidationError, ProcessingError):
            raise
        except Exception as e:
            current_app.logger.error(f"Failed to generate embeddings: {str(e)}")
            raise ProcessingError(f"Failed to generate embeddings: {str(e)}")
    
    @classmethod
    def reindex_embeddings(cls, tenant_id: int, source_id: int) -> Dict[str, Any]:
        """Re-index embeddings for a knowledge source."""
        try:
            embedding_service = EmbeddingService()
            result = embedding_service.reindex_knowledge_source(tenant_id, source_id)
            
            current_app.logger.info(f"Re-indexed embeddings for source {source_id}: {result}")
            return result
            
        except Exception as e:
            current_app.logger.error(f"Failed to re-index embeddings: {str(e)}")
            raise ProcessingError(f"Failed to re-index embeddings: {str(e)}")
    
    @classmethod
    def get_embedding_stats(cls, tenant_id: int) -> Dict[str, Any]:
        """Get embedding statistics for tenant."""
        try:
            return EmbeddingService.get_embedding_stats(tenant_id)
        except Exception as e:
            current_app.logger.error(f"Failed to get embedding stats: {str(e)}")
            raise ProcessingError(f"Failed to get embedding stats: {str(e)}")
    
    @classmethod
    def get_available_embedding_models(cls) -> Dict[str, int]:
        """Get available embedding models and their dimensions."""
        try:
            # Return supported models without initializing the service
            return EmbeddingService.SUPPORTED_MODELS.copy()
        except Exception as e:
            current_app.logger.error(f"Failed to get available models: {str(e)}")
            raise ProcessingError(f"Failed to get available models: {str(e)}")
    
    @classmethod
    def validate_embedding_model(cls, model: str) -> bool:
        """Validate if an embedding model is supported."""
        try:
            # Validate model without initializing the service
            return model in EmbeddingService.SUPPORTED_MODELS
        except Exception as e:
            current_app.logger.error(f"Failed to validate model: {str(e)}")
            return False
    
    @staticmethod
    def _is_allowed_file(filename: str) -> bool:
        """Check if file extension is allowed."""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in KnowledgeService.ALLOWED_EXTENSIONS
    
    @staticmethod
    def _is_valid_url(url: str) -> bool:
        """Validate URL format."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    

"""Embedding service for generating and managing vector embeddings."""
import os
import logging
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from openai import OpenAI
from flask import current_app
from app.models.knowledge import Chunk, Embedding
from app import db
from app.utils.exceptions import ProcessingError


class EmbeddingService:
    """Service for generating and managing vector embeddings."""
    
    DEFAULT_MODEL = "text-embedding-ada-002"
    DEFAULT_DIMENSION = 1536
    BATCH_SIZE = 100  # Process embeddings in batches
    MAX_RETRIES = 3  # Maximum retries for API calls
    RETRY_DELAY = 1.0  # Initial delay between retries (seconds)
    
    # Supported embedding models and their dimensions
    SUPPORTED_MODELS = {
        "text-embedding-ada-002": 1536,
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072
    }
    
    def __init__(self):
        self.logger = logging.getLogger("embedding.service")
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize OpenAI client."""
        try:
            api_key = current_app.config.get('OPENAI_API_KEY')
            if not api_key:
                raise ProcessingError("OpenAI API key not configured")
            
            self.client = OpenAI(api_key=api_key)
            self.logger.info("OpenAI client initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize OpenAI client: {str(e)}")
            raise ProcessingError(f"Failed to initialize embedding service: {str(e)}")
    
    def generate_embedding(self, text: str, model: str = None) -> np.ndarray:
        """Generate embedding for a single text with retry logic."""
        if not self.client:
            self._initialize_client()
        
        model = model or self.DEFAULT_MODEL
        
        # Clean and prepare text
        text = self._prepare_text(text)
        
        if not text.strip():
            raise ProcessingError("Empty text provided for embedding")
        
        # Retry logic for API calls
        for attempt in range(self.MAX_RETRIES):
            try:
                # Generate embedding using OpenAI
                response = self.client.embeddings.create(
                    input=text,
                    model=model
                )
                
                # Extract embedding vector
                embedding_vector = np.array(response.data[0].embedding)
                
                self.logger.debug(f"Generated embedding with dimension {len(embedding_vector)} using model {model}")
                return embedding_vector
                
            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    import time
                    delay = self.RETRY_DELAY * (2 ** attempt)  # Exponential backoff
                    self.logger.warning(f"Embedding generation attempt {attempt + 1} failed, retrying in {delay}s: {str(e)}")
                    time.sleep(delay)
                    continue
                else:
                    self.logger.error(f"Failed to generate embedding after {self.MAX_RETRIES} attempts: {str(e)}")
                    raise ProcessingError(f"Failed to generate embedding: {str(e)}")
    
    def generate_embeddings_batch(self, texts: List[str], model: str = None) -> List[np.ndarray]:
        """Generate embeddings for multiple texts in batch."""
        if not self.client:
            self._initialize_client()
        
        model = model or self.DEFAULT_MODEL
        embeddings = []
        
        try:
            # Process in batches to avoid API limits
            for i in range(0, len(texts), self.BATCH_SIZE):
                batch_texts = texts[i:i + self.BATCH_SIZE]
                
                # Clean and prepare texts
                prepared_texts = [self._prepare_text(text) for text in batch_texts]
                
                # Filter out empty texts
                valid_texts = [(idx, text) for idx, text in enumerate(prepared_texts) if text.strip()]
                
                if not valid_texts:
                    # Add empty embeddings for this batch
                    embeddings.extend([np.array([]) for _ in batch_texts])
                    continue
                
                # Generate embeddings for valid texts
                response = self.client.embeddings.create(
                    input=[text for _, text in valid_texts],
                    model=model
                )
                
                # Map embeddings back to original positions
                batch_embeddings = [np.array([]) for _ in batch_texts]
                for j, (original_idx, _) in enumerate(valid_texts):
                    batch_embeddings[original_idx] = np.array(response.data[j].embedding)
                
                embeddings.extend(batch_embeddings)
                
                self.logger.debug(f"Generated batch embeddings {i+1}-{min(i+self.BATCH_SIZE, len(texts))}/{len(texts)}")
            
            return embeddings
            
        except Exception as e:
            self.logger.error(f"Failed to generate batch embeddings: {str(e)}")
            raise ProcessingError(f"Failed to generate batch embeddings: {str(e)}")
    
    def create_chunk_embedding(self, tenant_id: int, chunk_id: int, model: str = None) -> Embedding:
        """Create embedding for a specific chunk."""
        try:
            # Get chunk
            chunk = Chunk.get_by_id(chunk_id)
            if not chunk or chunk.tenant_id != tenant_id:
                raise ProcessingError("Chunk not found")
            
            # Check if embedding already exists
            existing_embedding = Embedding.query.filter_by(
                tenant_id=tenant_id,
                chunk_id=chunk_id,
                model_name=model or self.DEFAULT_MODEL
            ).first()
            
            if existing_embedding:
                self.logger.info(f"Embedding already exists for chunk {chunk_id}")
                return existing_embedding
            
            # Generate embedding
            embedding_vector = self.generate_embedding(chunk.content, model)
            
            # Create embedding record
            embedding = Embedding.create_from_vector(
                tenant_id=tenant_id,
                chunk_id=chunk_id,
                vector=embedding_vector,
                model_name=model or self.DEFAULT_MODEL
            )
            
            self.logger.info(f"Created embedding for chunk {chunk_id}")
            return embedding
            
        except Exception as e:
            self.logger.error(f"Failed to create chunk embedding: {str(e)}")
            raise ProcessingError(f"Failed to create chunk embedding: {str(e)}")
    
    def create_document_embeddings(self, tenant_id: int, document_id: int, model: str = None) -> List[Embedding]:
        """Create embeddings for all chunks in a document."""
        try:
            from app.models.knowledge import Document
            
            # Get document
            document = Document.get_by_id(document_id)
            if not document or document.tenant_id != tenant_id:
                raise ProcessingError("Document not found")
            
            # Get chunks
            chunks = Chunk.get_by_document(document_id)
            if not chunks:
                self.logger.warning(f"No chunks found for document {document_id}")
                return []
            
            embeddings = []
            model_name = model or self.DEFAULT_MODEL
            
            # Check which chunks already have embeddings
            existing_embeddings = Embedding.query.filter_by(
                tenant_id=tenant_id,
                model_name=model_name
            ).filter(
                Embedding.chunk_id.in_([chunk.id for chunk in chunks])
            ).all()
            
            existing_chunk_ids = {emb.chunk_id for emb in existing_embeddings}
            chunks_to_process = [chunk for chunk in chunks if chunk.id not in existing_chunk_ids]
            
            if not chunks_to_process:
                self.logger.info(f"All chunks in document {document_id} already have embeddings")
                return existing_embeddings
            
            # Generate embeddings in batch
            chunk_texts = [chunk.content for chunk in chunks_to_process]
            embedding_vectors = self.generate_embeddings_batch(chunk_texts, model)
            
            # Create embedding records
            for chunk, vector in zip(chunks_to_process, embedding_vectors):
                if vector.size > 0:  # Skip empty embeddings
                    embedding = Embedding.create_from_vector(
                        tenant_id=tenant_id,
                        chunk_id=chunk.id,
                        vector=vector,
                        model_name=model_name
                    )
                    embeddings.append(embedding)
            
            # Add existing embeddings
            embeddings.extend(existing_embeddings)
            
            self.logger.info(f"Created {len(embeddings)} embeddings for document {document_id}")
            return embeddings
            
        except Exception as e:
            self.logger.error(f"Failed to create document embeddings: {str(e)}")
            raise ProcessingError(f"Failed to create document embeddings: {str(e)}")
    
    def search_similar_chunks(self, tenant_id: int, query: str, limit: int = 10, 
                            min_similarity: float = 0.7, model: str = None, 
                            source_ids: List[int] = None) -> List[Dict[str, Any]]:
        """Search for similar chunks using vector similarity with enhanced relevance scoring."""
        try:
            model_name = model or self.DEFAULT_MODEL
            
            # Generate query embedding
            query_vector = self.generate_embedding(query, model_name)
            
            # Build query for embeddings
            query_builder = Embedding.query.join(Chunk).filter(
                Embedding.tenant_id == tenant_id,
                Embedding.model_name == model_name
            )
            
            # Filter by source IDs if provided
            if source_ids:
                from app.models.knowledge import Document
                query_builder = query_builder.join(Document).filter(
                    Document.source_id.in_(source_ids)
                )
            
            embeddings = query_builder.all()
            
            if not embeddings:
                self.logger.warning(f"No embeddings found for tenant {tenant_id}")
                return []
            
            # Calculate similarities with enhanced scoring
            similarities = []
            query_terms = set(query.lower().split())
            
            for embedding in embeddings:
                try:
                    # Calculate cosine similarity
                    cosine_sim = self._calculate_cosine_similarity(
                        query_vector, 
                        embedding.get_vector()
                    )
                    
                    if cosine_sim < min_similarity:
                        continue
                    
                    chunk = embedding.chunk
                    document = chunk.document if chunk else None
                    
                    # Enhanced relevance scoring
                    relevance_score = self._calculate_relevance_score(
                        cosine_sim, chunk, document, query_terms
                    )
                    
                    similarities.append({
                        'embedding': embedding,
                        'cosine_similarity': cosine_sim,
                        'relevance_score': relevance_score,
                        'chunk': chunk,
                        'document': document
                    })
                        
                except Exception as e:
                    self.logger.warning(f"Failed to calculate similarity for embedding {embedding.id}: {str(e)}")
                    continue
            
            # Sort by relevance score (highest first)
            similarities.sort(key=lambda x: x['relevance_score'], reverse=True)
            
            # Format results with enhanced metadata
            results = []
            for item in similarities[:limit]:
                chunk = item['chunk']
                document = item['document']
                
                result = {
                    'chunk_id': chunk.id,
                    'document_id': document.id if document else None,
                    'content': chunk.content,
                    'content_preview': chunk.get_content_preview(300),
                    'similarity_score': float(item['cosine_similarity']),
                    'relevance_score': float(item['relevance_score']),
                    'citations': self._generate_enhanced_citations(chunk, document, query),
                    'metadata': {
                        'chunk_position': chunk.position,
                        'token_count': chunk.token_count,
                        'document_title': document.title if document else None,
                        'source_name': document.source.name if document and document.source else None,
                        'source_type': document.source.source_type if document and document.source else None,
                        'url': document.url if document else None,
                        'model_used': model_name,
                        'search_query': query,
                        'chunk_overlap_start': chunk.overlap_start,
                        'chunk_overlap_end': chunk.overlap_end
                    }
                }
                results.append(result)
            
            self.logger.info(f"Found {len(results)} similar chunks for query with model {model_name}")
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to search similar chunks: {str(e)}")
            raise ProcessingError(f"Failed to search similar chunks: {str(e)}")
    
    def reindex_knowledge_source(self, tenant_id: int, source_id: int, model: str = None) -> Dict[str, Any]:
        """Re-index all documents in a knowledge source."""
        try:
            from app.models.knowledge import KnowledgeSource, Document
            
            # Get source
            source = KnowledgeSource.get_by_id(source_id)
            if not source or source.tenant_id != tenant_id:
                raise ProcessingError("Knowledge source not found")
            
            # Get documents
            documents = Document.get_by_source(source_id)
            if not documents:
                return {
                    'source_id': source_id,
                    'documents_processed': 0,
                    'embeddings_created': 0,
                    'embeddings_updated': 0
                }
            
            model_name = model or self.DEFAULT_MODEL
            total_embeddings_created = 0
            total_embeddings_updated = 0
            
            # Process each document
            for document in documents:
                try:
                    # Delete existing embeddings for this model
                    existing_embeddings = Embedding.query.join(Chunk).filter(
                        Chunk.document_id == document.id,
                        Embedding.model_name == model_name
                    ).all()
                    
                    embeddings_updated = len(existing_embeddings)
                    for embedding in existing_embeddings:
                        embedding.delete()
                    
                    # Create new embeddings
                    new_embeddings = self.create_document_embeddings(
                        tenant_id, document.id, model_name
                    )
                    
                    total_embeddings_created += len(new_embeddings)
                    total_embeddings_updated += embeddings_updated
                    
                    self.logger.info(f"Re-indexed document {document.id}: {len(new_embeddings)} embeddings")
                    
                except Exception as e:
                    self.logger.error(f"Failed to re-index document {document.id}: {str(e)}")
                    continue
            
            # Update source status
            source.mark_as_completed()
            source.save()
            
            result = {
                'source_id': source_id,
                'documents_processed': len(documents),
                'embeddings_created': total_embeddings_created,
                'embeddings_updated': total_embeddings_updated
            }
            
            self.logger.info(f"Re-indexed knowledge source {source_id}: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to re-index knowledge source: {str(e)}")
            raise ProcessingError(f"Failed to re-index knowledge source: {str(e)}")
    
    def _prepare_text(self, text: str) -> str:
        """Prepare text for embedding generation."""
        if not text:
            return ""
        
        # Basic text cleaning
        text = text.strip()
        
        # Remove excessive whitespace
        import re
        text = re.sub(r'\s+', ' ', text)
        
        # Truncate if too long (OpenAI has token limits)
        max_tokens = 8000  # Conservative limit for text-embedding-ada-002
        if len(text.split()) > max_tokens:
            text = ' '.join(text.split()[:max_tokens])
        
        return text
    
    def _calculate_cosine_similarity(self, vector1: np.ndarray, vector2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        try:
            # Ensure vectors are numpy arrays
            v1 = np.array(vector1)
            v2 = np.array(vector2)
            
            # Calculate cosine similarity
            dot_product = np.dot(v1, v2)
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            
            # Ensure result is between -1 and 1
            return max(-1.0, min(1.0, float(similarity)))
            
        except Exception as e:
            self.logger.warning(f"Failed to calculate cosine similarity: {str(e)}")
            return 0.0
    
    def _calculate_relevance_score(self, cosine_sim: float, chunk: Chunk, document, query_terms: set) -> float:
        """Calculate enhanced relevance score combining multiple factors."""
        try:
            # Start with cosine similarity (weight: 0.7)
            relevance_score = cosine_sim * 0.7
            
            # Add text-based relevance (weight: 0.2)
            if chunk and chunk.content:
                content_lower = chunk.content.lower()
                term_matches = sum(1 for term in query_terms if term in content_lower)
                text_relevance = min(term_matches / max(len(query_terms), 1), 1.0)
                relevance_score += text_relevance * 0.2
            
            # Add document-level factors (weight: 0.1)
            doc_boost = 0.0
            if document:
                # Boost for title matches
                if document.title and any(term in document.title.lower() for term in query_terms):
                    doc_boost += 0.3
                
                # Boost for recent documents (if timestamp available)
                if hasattr(document, 'created_at') and document.created_at:
                    from datetime import datetime, timedelta
                    if isinstance(document.created_at, str):
                        # Handle string timestamps
                        try:
                            from dateutil.parser import parse
                            doc_date = parse(document.created_at)
                        except:
                            doc_date = None
                    else:
                        doc_date = document.created_at
                    
                    if doc_date and (datetime.utcnow() - doc_date) < timedelta(days=30):
                        doc_boost += 0.1
            
            relevance_score += doc_boost * 0.1
            
            # Ensure score is between 0 and 1
            return max(0.0, min(1.0, relevance_score))
            
        except Exception as e:
            self.logger.warning(f"Failed to calculate relevance score: {str(e)}")
            return cosine_sim  # Fallback to cosine similarity
    
    def _generate_citations(self, chunk: Chunk, document) -> Dict[str, Any]:
        """Generate citation information for a chunk."""
        citations = {
            'chunk_id': chunk.id,
            'position': chunk.position
        }
        
        if document:
            citations.update({
                'document_id': document.id,
                'document_title': document.title,
                'document_url': document.url
            })
            
            if document.source:
                citations.update({
                    'source_id': document.source.id,
                    'source_name': document.source.name,
                    'source_type': document.source.source_type,
                    'source_url': document.source.source_url
                })
        
        return citations
    
    def _generate_enhanced_citations(self, chunk: Chunk, document, query: str) -> Dict[str, Any]:
        """Generate enhanced citation information with additional context."""
        citations = self._generate_citations(chunk, document)
        
        # Add enhanced citation metadata
        citations.update({
            'citation_text': self._generate_citation_text(chunk, document),
            'context_snippet': self._extract_context_snippet(chunk, query),
            'confidence_score': self._calculate_citation_confidence(chunk, document),
            'access_date': datetime.utcnow().isoformat(),
            'chunk_metadata': {
                'token_count': chunk.token_count,
                'has_overlap': chunk.overlap_start > 0 or chunk.overlap_end > 0,
                'is_first_chunk': chunk.position == 0,
                'chunk_type': chunk.get_metadata('chunk_type', 'text')
            }
        })
        
        return citations
    
    def _generate_citation_text(self, chunk: Chunk, document) -> str:
        """Generate formatted citation text."""
        if not document:
            return f"Chunk {chunk.id}"
        
        citation_parts = []
        
        # Add document title
        if document.title:
            citation_parts.append(f'"{document.title}"')
        
        # Add source information
        if document.source:
            if document.source.source_type == 'url' and document.url:
                citation_parts.append(f"Retrieved from {document.url}")
            elif document.source.source_type == 'document' and document.filename:
                citation_parts.append(f"From document: {document.filename}")
            
            # Add source name if different from title
            if document.source.name and document.source.name != document.title:
                citation_parts.append(f"Source: {document.source.name}")
        
        # Add chunk position for longer documents
        if chunk.position > 0:
            citation_parts.append(f"Section {chunk.position + 1}")
        
        return ", ".join(citation_parts) if citation_parts else f"Document {document.id}"
    
    def _extract_context_snippet(self, chunk: Chunk, query: str, snippet_length: int = 200) -> str:
        """Extract relevant context snippet from chunk content."""
        if not chunk.content:
            return ""
        
        content = chunk.content
        query_terms = query.lower().split()
        
        # Find the best position to extract snippet
        best_pos = 0
        best_score = 0
        
        # Look for positions with highest query term density
        for i in range(0, len(content) - snippet_length, 50):
            snippet = content[i:i + snippet_length].lower()
            score = sum(snippet.count(term) for term in query_terms)
            
            if score > best_score:
                best_score = score
                best_pos = i
        
        # Extract snippet and clean it up
        snippet = content[best_pos:best_pos + snippet_length]
        
        # Try to start and end at word boundaries
        if best_pos > 0:
            space_pos = snippet.find(' ')
            if space_pos > 0:
                snippet = snippet[space_pos + 1:]
        
        if len(content) > best_pos + snippet_length:
            last_space = snippet.rfind(' ')
            if last_space > snippet_length * 0.8:  # Only if we're not cutting too much
                snippet = snippet[:last_space]
            snippet += "..."
        
        return snippet.strip()
    
    def _calculate_citation_confidence(self, chunk: Chunk, document) -> float:
        """Calculate confidence score for citation reliability."""
        confidence = 0.5  # Base confidence
        
        # Boost for complete documents
        if document:
            if document.processing_status == 'completed':
                confidence += 0.2
            
            # Boost for verified sources
            if document.source and document.source.status == 'completed':
                confidence += 0.1
            
            # Boost for documents with metadata
            if document.content_hash:
                confidence += 0.1
        
        # Boost for chunks with good metadata
        if chunk:
            if chunk.token_count and chunk.token_count > 50:  # Substantial content
                confidence += 0.1
        
        return min(1.0, confidence)
    
    def get_supported_models(self) -> Dict[str, int]:
        """Get supported embedding models and their dimensions."""
        return self.SUPPORTED_MODELS.copy()
    
    def validate_model(self, model: str) -> bool:
        """Validate if the model is supported."""
        return model in self.SUPPORTED_MODELS
    
    def get_model_dimension(self, model: str) -> int:
        """Get the dimension for a specific model."""
        return self.SUPPORTED_MODELS.get(model, self.DEFAULT_DIMENSION)
    
    @classmethod
    def get_embedding_stats(cls, tenant_id: int) -> Dict[str, Any]:
        """Get embedding statistics for a tenant."""
        try:
            from sqlalchemy import func
            
            # Get embedding counts by model
            model_stats = Embedding.query.filter_by(tenant_id=tenant_id)\
                .with_entities(
                    Embedding.model_name,
                    func.count(Embedding.id).label('count')
                )\
                .group_by(Embedding.model_name)\
                .all()
            
            # Get total chunks and embedded chunks
            total_chunks = Chunk.query.filter_by(tenant_id=tenant_id).count()
            
            embedded_chunks = Chunk.query.join(Embedding)\
                .filter(Chunk.tenant_id == tenant_id)\
                .distinct(Chunk.id)\
                .count()
            
            return {
                'total_embeddings': sum(count for _, count in model_stats),
                'embeddings_by_model': {model: count for model, count in model_stats},
                'total_chunks': total_chunks,
                'embedded_chunks': embedded_chunks,
                'embedding_coverage': (embedded_chunks / max(total_chunks, 1)) * 100
            }
            
        except Exception as e:
            logging.getLogger("embedding.service").error(f"Failed to get embedding stats: {str(e)}")
            return {
                'error': str(e),
                'total_embeddings': 0,
                'embeddings_by_model': {},
                'total_chunks': 0,
                'embedded_chunks': 0,
                'embedding_coverage': 0
            }
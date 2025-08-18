"""Knowledge management models for RAG system."""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, Boolean, JSON, LargeBinary, Numeric
from sqlalchemy.orm import relationship
from app.models.base import TenantAwareModel, SoftDeleteMixin, AuditMixin, get_fk_reference


class KnowledgeSource(TenantAwareModel, SoftDeleteMixin, AuditMixin):
    """Knowledge source model for documents and URLs."""
    
    __tablename__ = 'knowledge_sources'
    
    # Basic information
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Source type and location
    source_type = Column(String(50), nullable=False, index=True)  # document, url, text
    source_url = Column(String(1000), nullable=True)  # For URL sources
    
    # Processing status
    status = Column(String(50), default='pending', nullable=False, index=True)  # pending, processing, completed, error, disabled
    last_crawled_at = Column(String(50), nullable=True)  # ISO datetime string
    last_error = Column(Text, nullable=True)
    
    # Configuration
    crawl_frequency = Column(String(50), nullable=True)  # daily, weekly, monthly, manual
    max_depth = Column(Integer, default=1, nullable=False)  # For URL crawling
    
    # Statistics
    document_count = Column(Integer, default=0, nullable=False)
    chunk_count = Column(Integer, default=0, nullable=False)
    total_tokens = Column(Integer, default=0, nullable=False)
    
    # Metadata
    extra_data = Column(JSON, default=dict, nullable=False)
    tags = Column(JSON, default=list, nullable=False)
    
    # Relationships
    documents = relationship('Document', back_populates='source', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<KnowledgeSource {self.name}>'
    
    def get_metadata(self, key, default=None):
        """Get metadata value."""
        return self.extra_data.get(key, default) if self.extra_data else default
    
    def set_metadata(self, key, value):
        """Set metadata value."""
        if self.extra_data is None:
            self.extra_data = {}
        self.extra_data[key] = value
        return self
    
    def add_tag(self, tag):
        """Add tag to source."""
        if self.tags is None:
            self.tags = []
        if tag not in self.tags:
            self.tags.append(tag)
        return self
    
    def remove_tag(self, tag):
        """Remove tag from source."""
        if self.tags and tag in self.tags:
            self.tags.remove(tag)
        return self
    
    def has_tag(self, tag):
        """Check if source has specific tag."""
        return self.tags and tag in self.tags
    
    def mark_as_processing(self):
        """Mark source as being processed."""
        self.status = 'processing'
        self.last_error = None
        return self
    
    def mark_as_completed(self):
        """Mark source as successfully processed."""
        from datetime import datetime
        self.status = 'completed'
        self.last_crawled_at = datetime.utcnow().isoformat()
        self.last_error = None
        return self
    
    def mark_as_error(self, error_message):
        """Mark source as having an error."""
        self.status = 'error'
        self.last_error = str(error_message)
        return self
    
    def disable(self):
        """Disable the source."""
        self.status = 'disabled'
        return self
    
    def enable(self):
        """Enable the source."""
        if self.status == 'disabled':
            self.status = 'pending'
        return self
    
    def update_statistics(self):
        """Update document and chunk statistics."""
        if self.documents:
            self.document_count = len(self.documents)
            self.chunk_count = sum(len(doc.chunks) for doc in self.documents if doc.chunks)
            self.total_tokens = sum(doc.token_count or 0 for doc in self.documents)
        else:
            self.document_count = 0
            self.chunk_count = 0
            self.total_tokens = 0
        return self
    
    def to_dict(self, exclude=None):
        """Convert to dictionary."""
        exclude = exclude or []
        data = super().to_dict(exclude=exclude)
        
        # Add computed fields
        data['is_active'] = self.status not in ['disabled', 'error']
        data['needs_processing'] = self.status == 'pending'
        data['has_error'] = self.status == 'error'
        
        return data
    
    @classmethod
    def create_document_source(cls, tenant_id, name, **kwargs):
        """Create a document-based knowledge source."""
        return cls.create(
            tenant_id=tenant_id,
            name=name,
            source_type='document',
            **kwargs
        )
    
    @classmethod
    def create_url_source(cls, tenant_id, name, url, **kwargs):
        """Create a URL-based knowledge source."""
        return cls.create(
            tenant_id=tenant_id,
            name=name,
            source_type='url',
            source_url=url,
            **kwargs
        )
    
    @classmethod
    def get_active_sources(cls, tenant_id):
        """Get active knowledge sources."""
        return cls.query.filter_by(
            tenant_id=tenant_id,
            status='completed'
        ).all()
    
    @classmethod
    def get_sources_needing_processing(cls, tenant_id=None):
        """Get sources that need processing."""
        query = cls.query.filter_by(status='pending')
        
        if tenant_id:
            query = query.filter_by(tenant_id=tenant_id)
        
        return query.all()


class Document(TenantAwareModel, SoftDeleteMixin, AuditMixin):
    """Document model for knowledge base."""
    
    __tablename__ = 'documents'
    
    # Source relationship
    source_id = Column(Integer, ForeignKey(get_fk_reference('knowledge_sources')), nullable=False, index=True)
    source = relationship('KnowledgeSource', back_populates='documents')
    
    # Document information
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=True)  # Full document content
    content_hash = Column(String(64), nullable=True, index=True)  # SHA-256 hash for deduplication
    
    # File information (for uploaded documents)
    filename = Column(String(255), nullable=True)
    file_path = Column(String(1000), nullable=True)
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    
    # URL information (for crawled content)
    url = Column(String(1000), nullable=True)
    
    # Processing information
    token_count = Column(Integer, nullable=True)
    language = Column(String(10), nullable=True)  # Detected language
    
    # Status
    processing_status = Column(String(50), default='pending', nullable=False)  # pending, processing, completed, error
    
    # Metadata
    extra_data = Column(JSON, default=dict, nullable=False)
    
    # Relationships
    chunks = relationship('Chunk', back_populates='document', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Document {self.title}>'
    
    def get_metadata(self, key, default=None):
        """Get metadata value."""
        return self.extra_data.get(key, default) if self.extra_data else default
    
    def set_metadata(self, key, value):
        """Set metadata value."""
        if self.extra_data is None:
            self.extra_data = {}
        self.extra_data[key] = value
        return self
    
    def generate_content_hash(self):
        """Generate SHA-256 hash of content for deduplication."""
        if self.content:
            import hashlib
            self.content_hash = hashlib.sha256(self.content.encode('utf-8')).hexdigest()
        return self
    
    def mark_as_processing(self):
        """Mark document as being processed."""
        self.processing_status = 'processing'
        return self
    
    def mark_as_completed(self):
        """Mark document as successfully processed."""
        self.processing_status = 'completed'
        return self
    
    def mark_as_error(self):
        """Mark document as having processing error."""
        self.processing_status = 'error'
        return self
    
    def get_chunk_count(self):
        """Get number of chunks for this document."""
        return len(self.chunks) if self.chunks else 0
    
    def to_dict(self, exclude=None):
        """Convert to dictionary."""
        exclude = exclude or []
        exclude.append('content')  # Don't include full content by default
        
        data = super().to_dict(exclude=exclude)
        
        # Add computed fields
        data['chunk_count'] = self.get_chunk_count()
        data['is_processed'] = self.processing_status == 'completed'
        data['has_error'] = self.processing_status == 'error'
        
        # Add source info
        if self.source:
            data['source_name'] = self.source.name
            data['source_type'] = self.source.source_type
        
        return data
    
    @classmethod
    def find_by_content_hash(cls, tenant_id, content_hash):
        """Find document by content hash."""
        return cls.query.filter_by(
            tenant_id=tenant_id,
            content_hash=content_hash
        ).first()
    
    @classmethod
    def get_by_source(cls, source_id):
        """Get documents for a specific source."""
        return cls.query.filter_by(source_id=source_id).all()


class Chunk(TenantAwareModel, SoftDeleteMixin):
    """Text chunk model for vector embeddings."""
    
    __tablename__ = 'chunks'
    
    # Document relationship
    document_id = Column(Integer, ForeignKey(get_fk_reference('documents')), nullable=False, index=True)
    document = relationship('Document', back_populates='chunks')
    
    # Chunk information
    content = Column(Text, nullable=False)
    position = Column(Integer, nullable=False)  # Position within document
    token_count = Column(Integer, nullable=True)
    
    # Overlap information (for context preservation)
    overlap_start = Column(Integer, default=0, nullable=False)  # Characters of overlap at start
    overlap_end = Column(Integer, default=0, nullable=False)  # Characters of overlap at end
    
    # Metadata
    extra_data = Column(JSON, default=dict, nullable=False)
    
    # Relationships
    embeddings = relationship('Embedding', back_populates='chunk', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Chunk {self.id} from {self.document.title}>'
    
    def get_metadata(self, key, default=None):
        """Get metadata value."""
        return self.extra_data.get(key, default) if self.extra_data else default
    
    def set_metadata(self, key, value):
        """Set metadata value."""
        if self.extra_data is None:
            self.extra_data = {}
        self.extra_data[key] = value
        return self
    
    def get_content_preview(self, max_length=200):
        """Get content preview."""
        if not self.content:
            return ""
        
        preview = self.content.strip()[:max_length]
        if len(self.content) > max_length:
            preview += "..."
        
        return preview
    
    def has_embeddings(self):
        """Check if chunk has embeddings."""
        return len(self.embeddings) > 0
    
    def to_dict(self, exclude=None):
        """Convert to dictionary."""
        exclude = exclude or []
        data = super().to_dict(exclude=exclude)
        
        # Add computed fields
        data['content_preview'] = self.get_content_preview()
        data['has_embeddings'] = self.has_embeddings()
        data['embedding_count'] = len(self.embeddings) if self.embeddings else 0
        
        # Add document info
        if self.document:
            data['document_title'] = self.document.title
            data['document_id'] = self.document.id
        
        return data
    
    @classmethod
    def get_by_document(cls, document_id):
        """Get chunks for a specific document."""
        return cls.query.filter_by(document_id=document_id)\
                      .order_by(cls.position)\
                      .all()


class Embedding(TenantAwareModel):
    """Vector embedding model for semantic search."""
    
    __tablename__ = 'embeddings'
    
    # Chunk relationship
    chunk_id = Column(Integer, ForeignKey(get_fk_reference('chunks')), nullable=False, index=True)
    chunk = relationship('Chunk', back_populates='embeddings')
    
    # Embedding information
    model_name = Column(String(100), nullable=False)  # e.g., 'text-embedding-ada-002'
    vector_data = Column(LargeBinary, nullable=False)  # Serialized vector data
    dimension = Column(Integer, nullable=False)  # Vector dimension
    
    # Metadata
    extra_data = Column(JSON, default=dict, nullable=False)
    
    def __repr__(self):
        return f'<Embedding {self.model_name} for chunk {self.chunk_id}>'
    
    def get_vector(self):
        """Get vector as numpy array."""
        import numpy as np
        import pickle
        return pickle.loads(self.vector_data)
    
    def set_vector(self, vector):
        """Set vector from numpy array."""
        import numpy as np
        import pickle
        self.vector_data = pickle.dumps(vector)
        self.dimension = len(vector)
        return self
    
    def calculate_similarity(self, other_vector):
        """Calculate cosine similarity with another vector."""
        import numpy as np
        
        vector1 = self.get_vector()
        vector2 = other_vector
        
        # Cosine similarity
        dot_product = np.dot(vector1, vector2)
        norm1 = np.linalg.norm(vector1)
        norm2 = np.linalg.norm(vector2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def to_dict(self, exclude=None):
        """Convert to dictionary."""
        exclude = exclude or []
        exclude.append('vector_data')  # Don't include binary data
        
        data = super().to_dict(exclude=exclude)
        
        # Add chunk info
        if self.chunk:
            data['chunk_content_preview'] = self.chunk.get_content_preview()
            data['document_title'] = self.chunk.document.title if self.chunk.document else None
        
        return data
    
    @classmethod
    def find_similar(cls, tenant_id, query_vector, model_name, limit=10, min_similarity=0.7):
        """Find similar embeddings using cosine similarity."""
        # This is a basic implementation. In production, you'd use a vector database
        # like pgvector, Pinecone, or Weaviate for efficient similarity search
        
        embeddings = cls.query.filter_by(
            tenant_id=tenant_id,
            model_name=model_name
        ).all()
        
        similarities = []
        for embedding in embeddings:
            similarity = embedding.calculate_similarity(query_vector)
            if similarity >= min_similarity:
                similarities.append((embedding, similarity))
        
        # Sort by similarity (highest first)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:limit]
    
    @classmethod
    def create_from_vector(cls, tenant_id, chunk_id, vector, model_name, **kwargs):
        """Create embedding from vector."""
        embedding = cls.create(
            tenant_id=tenant_id,
            chunk_id=chunk_id,
            model_name=model_name,
            **kwargs
        )
        embedding.set_vector(vector)
        embedding.save()
        
        return embedding
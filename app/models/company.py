"""Company and related models."""
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import JSON
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship
import uuid
from app import db


class Company(db.Model):
    """Company model for AI Secretary users."""
    __tablename__ = 'companies'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    vat_number = Column(String(50))
    address = Column(Text)
    phone = Column(String(50))
    email = Column(String(255))
    business_area = Column(String(255))
    ai_instructions = Column(Text)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    channels = relationship("CommunicationChannel", back_populates="company", cascade="all, delete-orphan")
    documents = relationship("KnowledgeDocument", back_populates="company", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Company {self.name}>'
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': str(self.id),
            'name': self.name,
            'vat_number': self.vat_number,
            'address': self.address,
            'phone': self.phone,
            'email': self.email,
            'business_area': self.business_area,
            'ai_instructions': self.ai_instructions,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class CommunicationChannel(db.Model):
    """Communication channels for AI Secretary."""
    __tablename__ = 'communication_channels'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey('companies.id'), nullable=False)
    channel_type = Column(String(50), nullable=False)  # phone, email, telegram, etc.
    config = Column(JSON)  # Channel-specific configuration
    enabled = Column(Boolean, default=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    company = relationship("Company", back_populates="channels")
    
    def __repr__(self):
        return f'<CommunicationChannel {self.channel_type} for {self.company.name}>'
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': str(self.id),
            'company_id': str(self.company_id),
            'channel_type': self.channel_type,
            'config': self.config,
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class KnowledgeDocument(db.Model):
    """Documents uploaded to the knowledge base."""
    __tablename__ = 'knowledge_documents'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey('companies.id'), nullable=False)
    filename = Column(String(255), nullable=False)
    content_type = Column(String(100))
    file_size = Column(Integer)
    # vector_embeddings would be added when we implement pgvector
    document_metadata = Column(JSON)
    processing_status = Column(String(50), default='pending')  # pending, processing, completed, error
    
    # Metadata
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)
    
    # Relationships
    company = relationship("Company", back_populates="documents")
    
    def __repr__(self):
        return f'<KnowledgeDocument {self.filename}>'
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': str(self.id),
            'company_id': str(self.company_id),
            'filename': self.filename,
            'content_type': self.content_type,
            'file_size': self.file_size,
            'metadata': self.document_metadata,
            'processing_status': self.processing_status,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None
        }
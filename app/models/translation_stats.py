"""Translation statistics and monitoring models."""
from datetime import datetime, timedelta
from sqlalchemy import Index
from app import db
from app.models.base import BaseModel


class TranslationStats(BaseModel):
    """Model for tracking translation coverage statistics."""
    
    __tablename__ = 'translation_stats'
    
    language = db.Column(db.String(5), nullable=False, index=True)
    total_strings = db.Column(db.Integer, default=0, nullable=False)
    translated_strings = db.Column(db.Integer, default=0, nullable=False)
    fuzzy_strings = db.Column(db.Integer, default=0, nullable=False)
    untranslated_strings = db.Column(db.Integer, default=0, nullable=False)
    coverage_percentage = db.Column(db.Float, default=0.0, nullable=False)
    status = db.Column(db.String(20), default='incomplete', nullable=False)  # complete, good, partial, incomplete, missing, error
    last_extraction = db.Column(db.DateTime, nullable=True)
    last_compilation = db.Column(db.DateTime, nullable=True)
    validation_errors = db.Column(db.Integer, default=0, nullable=False)
    
    # Add indexes for performance
    __table_args__ = (
        Index('idx_translation_stats_language', 'language'),
        Index('idx_translation_stats_status', 'status'),
        Index('idx_translation_stats_coverage', 'coverage_percentage'),
    )
    
    def __repr__(self):
        return f'<TranslationStats {self.language}: {self.coverage_percentage}%>'
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'language': self.language,
            'total_strings': self.total_strings,
            'translated_strings': self.translated_strings,
            'fuzzy_strings': self.fuzzy_strings,
            'untranslated_strings': self.untranslated_strings,
            'coverage_percentage': self.coverage_percentage,
            'status': self.status,
            'last_extraction': self.last_extraction.isoformat() if self.last_extraction else None,
            'last_compilation': self.last_compilation.isoformat() if self.last_compilation else None,
            'validation_errors': self.validation_errors,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    @classmethod
    def get_by_language(cls, language: str):
        """Get translation stats for a specific language."""
        return cls.query.filter_by(language=language).first()
    
    @classmethod
    def get_all_languages(cls):
        """Get translation stats for all languages."""
        return cls.query.order_by(cls.language).all()
    
    @classmethod
    def update_stats(cls, language: str, stats_data: dict):
        """Update or create translation stats for a language."""
        stats = cls.get_by_language(language)
        
        if not stats:
            stats = cls(language=language)
            db.session.add(stats)
        
        # Update fields
        stats.total_strings = stats_data.get('total_messages', 0)
        stats.translated_strings = stats_data.get('translated_messages', 0)
        stats.fuzzy_strings = stats_data.get('fuzzy_messages', 0)
        stats.untranslated_strings = stats_data.get('untranslated_messages', 0)
        stats.coverage_percentage = stats_data.get('coverage_percentage', 0.0)
        stats.status = stats_data.get('status', 'incomplete')
        
        if 'last_extraction' in stats_data:
            stats.last_extraction = stats_data['last_extraction']
        
        if 'last_compilation' in stats_data:
            stats.last_compilation = stats_data['last_compilation']
        
        if 'validation_errors' in stats_data:
            stats.validation_errors = stats_data['validation_errors']
        
        db.session.commit()
        return stats


class MissingTranslation(BaseModel):
    """Model for tracking missing translations."""
    
    __tablename__ = 'missing_translations'
    
    language = db.Column(db.String(5), nullable=False, index=True)
    message_id = db.Column(db.Text, nullable=False)
    message_context = db.Column(db.Text, nullable=True)
    source_file = db.Column(db.String(255), nullable=True)
    line_number = db.Column(db.Integer, nullable=True)
    first_seen = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    occurrence_count = db.Column(db.Integer, default=1, nullable=False)
    priority = db.Column(db.String(10), default='medium', nullable=False)  # high, medium, low
    is_resolved = db.Column(db.Boolean, default=False, nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)
    
    # Add indexes for performance
    __table_args__ = (
        Index('idx_missing_translations_language', 'language'),
        Index('idx_missing_translations_resolved', 'is_resolved'),
        Index('idx_missing_translations_priority', 'priority'),
        Index('idx_missing_translations_last_seen', 'last_seen'),
        db.UniqueConstraint('language', 'message_id', name='uq_missing_translation_lang_msg'),
    )
    
    def __repr__(self):
        return f'<MissingTranslation {self.language}: {self.message_id[:50]}...>'
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'language': self.language,
            'message_id': self.message_id,
            'message_context': self.message_context,
            'source_file': self.source_file,
            'line_number': self.line_number,
            'first_seen': self.first_seen.isoformat(),
            'last_seen': self.last_seen.isoformat(),
            'occurrence_count': self.occurrence_count,
            'priority': self.priority,
            'is_resolved': self.is_resolved,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    @classmethod
    def log_missing(cls, language: str, message_id: str, source_file: str = None, 
                   line_number: int = None, context: str = None):
        """Log a missing translation or update existing record."""
        existing = cls.query.filter_by(
            language=language,
            message_id=message_id
        ).first()
        
        if existing:
            # Update existing record
            existing.last_seen = datetime.utcnow()
            existing.occurrence_count += 1
            existing.is_resolved = False
            existing.resolved_at = None
            
            # Update source info if provided
            if source_file:
                existing.source_file = source_file
            if line_number:
                existing.line_number = line_number
            if context:
                existing.message_context = context
        else:
            # Create new record
            existing = cls(
                language=language,
                message_id=message_id,
                source_file=source_file,
                line_number=line_number,
                message_context=context
            )
            db.session.add(existing)
        
        db.session.commit()
        return existing
    
    @classmethod
    def mark_resolved(cls, language: str, message_id: str):
        """Mark a missing translation as resolved."""
        missing = cls.query.filter_by(
            language=language,
            message_id=message_id
        ).first()
        
        if missing:
            missing.is_resolved = True
            missing.resolved_at = datetime.utcnow()
            db.session.commit()
            return True
        
        return False
    
    @classmethod
    def get_unresolved_by_language(cls, language: str):
        """Get all unresolved missing translations for a language."""
        return cls.query.filter_by(
            language=language,
            is_resolved=False
        ).order_by(cls.priority.desc(), cls.occurrence_count.desc()).all()
    
    @classmethod
    def get_unresolved_count(cls, language: str = None):
        """Get count of unresolved missing translations."""
        query = cls.query.filter_by(is_resolved=False)
        if language:
            query = query.filter_by(language=language)
        return query.count()
    
    @classmethod
    def cleanup_resolved(cls, days_old: int = 30):
        """Clean up old resolved missing translations."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        deleted_count = cls.query.filter(
            cls.is_resolved == True,
            cls.resolved_at < cutoff_date
        ).delete()
        
        db.session.commit()
        return deleted_count


class TranslationValidationError(BaseModel):
    """Model for tracking translation validation errors."""
    
    __tablename__ = 'translation_validation_errors'
    
    language = db.Column(db.String(5), nullable=False, index=True)
    message_id = db.Column(db.Text, nullable=False)
    error_type = db.Column(db.String(50), nullable=False)  # placeholder_mismatch, html_tag_mismatch, fuzzy_translation, etc.
    error_message = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(10), default='warning', nullable=False)  # error, warning, info
    source_file = db.Column(db.String(255), nullable=True)
    line_number = db.Column(db.Integer, nullable=True)
    first_detected = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_detected = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    detection_count = db.Column(db.Integer, default=1, nullable=False)
    is_resolved = db.Column(db.Boolean, default=False, nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)
    
    # Add indexes for performance
    __table_args__ = (
        Index('idx_validation_errors_language', 'language'),
        Index('idx_validation_errors_type', 'error_type'),
        Index('idx_validation_errors_severity', 'severity'),
        Index('idx_validation_errors_resolved', 'is_resolved'),
        db.UniqueConstraint('language', 'message_id', 'error_type', name='uq_validation_error_lang_msg_type'),
    )
    
    def __repr__(self):
        return f'<TranslationValidationError {self.language}: {self.error_type}>'
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'language': self.language,
            'message_id': self.message_id,
            'error_type': self.error_type,
            'error_message': self.error_message,
            'severity': self.severity,
            'source_file': self.source_file,
            'line_number': self.line_number,
            'first_detected': self.first_detected.isoformat(),
            'last_detected': self.last_detected.isoformat(),
            'detection_count': self.detection_count,
            'is_resolved': self.is_resolved,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    @classmethod
    def log_error(cls, language: str, message_id: str, error_type: str, 
                  error_message: str, severity: str = 'warning',
                  source_file: str = None, line_number: int = None):
        """Log a validation error or update existing record."""
        existing = cls.query.filter_by(
            language=language,
            message_id=message_id,
            error_type=error_type
        ).first()
        
        if existing:
            # Update existing record
            existing.last_detected = datetime.utcnow()
            existing.detection_count += 1
            existing.error_message = error_message
            existing.severity = severity
            existing.is_resolved = False
            existing.resolved_at = None
            
            # Update source info if provided
            if source_file:
                existing.source_file = source_file
            if line_number:
                existing.line_number = line_number
        else:
            # Create new record
            existing = cls(
                language=language,
                message_id=message_id,
                error_type=error_type,
                error_message=error_message,
                severity=severity,
                source_file=source_file,
                line_number=line_number
            )
            db.session.add(existing)
        
        db.session.commit()
        return existing
    
    @classmethod
    def mark_resolved(cls, language: str, message_id: str, error_type: str):
        """Mark a validation error as resolved."""
        error = cls.query.filter_by(
            language=language,
            message_id=message_id,
            error_type=error_type
        ).first()
        
        if error:
            error.is_resolved = True
            error.resolved_at = datetime.utcnow()
            db.session.commit()
            return True
        
        return False
    
    @classmethod
    def get_unresolved_by_language(cls, language: str):
        """Get all unresolved validation errors for a language."""
        return cls.query.filter_by(
            language=language,
            is_resolved=False
        ).order_by(cls.severity.desc(), cls.detection_count.desc()).all()
    
    @classmethod
    def get_error_summary(cls, language: str = None):
        """Get summary of validation errors by type and severity."""
        query = cls.query.filter_by(is_resolved=False)
        if language:
            query = query.filter_by(language=language)
        
        errors = query.all()
        
        summary = {
            'total_errors': len(errors),
            'by_severity': {'error': 0, 'warning': 0, 'info': 0},
            'by_type': {}
        }
        
        for error in errors:
            summary['by_severity'][error.severity] += 1
            if error.error_type not in summary['by_type']:
                summary['by_type'][error.error_type] = 0
            summary['by_type'][error.error_type] += 1
        
        return summary
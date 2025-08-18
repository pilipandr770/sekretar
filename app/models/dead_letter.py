"""Dead letter task model."""
from datetime import datetime
from app.models.base import BaseModel, db


class DeadLetterTask(BaseModel):
    """Model to store dead letter tasks."""
    __tablename__ = 'dead_letter_tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String(255), unique=True, nullable=False)
    original_task_name = db.Column(db.String(255), nullable=False)
    args = db.Column(db.JSON)
    kwargs = db.Column(db.JSON)
    exception = db.Column(db.Text)
    failure_reason = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime)
    retry_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(50), default='pending')  # pending, processed, failed
    
    def __repr__(self):
        return f'<DeadLetterTask {self.task_id}>'
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'original_task_name': self.original_task_name,
            'args': self.args,
            'kwargs': self.kwargs,
            'exception': self.exception,
            'failure_reason': self.failure_reason,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'retry_count': self.retry_count,
            'status': self.status
        }
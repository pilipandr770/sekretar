#!/usr/bin/env python3
"""Create database migration for KYB models."""

from app import create_app, db
from app.models.company import Company, CommunicationChannel, KnowledgeDocument
from app.models.kyb_monitoring import Counterparty, CounterpartySnapshot, CounterpartyDiff, KYBAlert

def create_migration():
    """Create database migration."""
    app = create_app()
    
    with app.app_context():
        print("Creating database tables...")
        
        # Create all tables
        db.create_all()
        
        print("✅ Database tables created successfully!")
        print("\nCreated tables:")
        print("- companies")
        print("- communication_channels") 
        print("- knowledge_documents")
        print("- counterparties")
        print("- kyb_checks")
        print("- change_monitoring")
        print("- sanctions_matches")

if __name__ == '__main__':
    create_migration()
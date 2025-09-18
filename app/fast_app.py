"""
Optimized App Factory for Fast Development
"""

import os
from flask import Flask
from app.config.fast_dev import FastDevelopmentConfig

def create_fast_app():
    """Create a fast, optimized Flask app"""
    app = Flask(__name__)
    
    # Use fast configuration
    app.config.from_object(FastDevelopmentConfig)
    
    # Initialize only essential extensions
    from app.extensions import db, jwt, cors
    
    db.init_app(app)
    jwt.init_app(app)
    cors.init_app(app)
    
    # Register only essential blueprints
    from app.auth.routes import auth_bp
    from app.main.routes import main_bp
    from app.api.routes import api_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    
    # Create tables
    with app.app_context():
        db.create_all()
    
    return app

"""
Performance optimization for Flask app
"""
import os
from flask import Flask

def optimize_app_performance(app: Flask):
    """Apply performance optimizations"""
    
    # Disable debug toolbar in production-like mode
    app.config['DEBUG_TB_ENABLED'] = False
    
    # Optimize template loading
    app.jinja_env.auto_reload = False
    app.jinja_env.cache_size = 400
    
    # Disable unnecessary features for development
    if not app.config.get('TESTING'):
        app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000  # 1 year
    
    # Optimize database connections
    if 'sqlite' in app.config.get('DATABASE_URL', '').lower():
        # SQLite optimizations
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,
            'pool_recycle': 300,
            'connect_args': {
                'timeout': 20,
                'check_same_thread': False
            }
        }
    
    return app

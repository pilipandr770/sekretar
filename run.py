#!/usr/bin/env python3
"""Application entry point."""
import os
from app import create_app, socketio

app = create_app()

if __name__ == '__main__':
    # Use SocketIO's run method for development
    socketio.run(
        app,
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=app.config.get('DEBUG', False)
    )
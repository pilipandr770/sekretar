"""
WebSocket connection manager with graceful degradation and error handling.
"""
import logging
import time
from typing import Optional, Dict, Any, Callable
from flask import current_app
from flask_socketio import SocketIO
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class WebSocketConnectionManager:
    """Manages WebSocket connections with retry limits and graceful degradation."""
    
    def __init__(self, app=None):
        self.app = app
        self.socketio = None
        self.websocket_available = False
        self.connection_attempts = 0
        self.max_connection_attempts = 3
        self.retry_delay = 5  # seconds
        self.last_attempt_time = 0
        self.error_counts = defaultdict(lambda: deque(maxlen=10))  # Track last 10 errors per type
        self.error_rate_limit = 5  # Max 5 errors per minute per type
        self.graceful_degradation_enabled = True
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize WebSocket manager with Flask app."""
        self.app = app
        
        # Initialize SocketIO with error handling
        self.socketio = self._initialize_socketio()
        
        # Configure WebSocket settings
        self._configure_websocket_settings()
        
        logger.info(f"WebSocket manager initialized (WebSocket available: {self.websocket_available})")
    
    def _initialize_socketio(self) -> Optional[SocketIO]:
        """
        Initialize SocketIO with proper error handling and retry limits.
        
        Returns:
            SocketIO instance or None if initialization fails
        """
        current_time = time.time()
        
        # Check if we've exceeded retry attempts
        if self.connection_attempts >= self.max_connection_attempts:
            if current_time - self.last_attempt_time < 300:  # 5 minutes cooldown
                logger.debug("WebSocket initialization skipped (cooldown period)")
                return None
            else:
                # Reset attempts after cooldown
                self.connection_attempts = 0
        
        self.last_attempt_time = current_time
        self.connection_attempts += 1
        
        try:
            # Get SocketIO configuration
            config = self._get_socketio_config()
            
            # Create SocketIO instance
            socketio = SocketIO(
                async_mode=config.get('async_mode', 'threading'),
                cors_allowed_origins=config.get('cors_allowed_origins', ['*']),
                logger=config.get('logger', False),
                engineio_logger=config.get('engineio_logger', False),
                ping_timeout=config.get('ping_timeout', 60),
                ping_interval=config.get('ping_interval', 25),
                max_http_buffer_size=config.get('max_http_buffer_size', 1000000),
                allow_upgrades=config.get('allow_upgrades', True),
                transports=config.get('transports', ['polling', 'websocket'])
            )
            
            # Initialize with app
            socketio.init_app(self.app)
            
            # Test WebSocket functionality
            if self._test_websocket_functionality(socketio):
                self.websocket_available = True
                self.connection_attempts = 0  # Reset on success
                
                if not hasattr(self, '_websocket_success_logged'):
                    logger.info("✅ WebSocket (SocketIO) initialized successfully")
                    self._websocket_success_logged = True
                
                return socketio
            else:
                raise Exception("WebSocket functionality test failed")
                
        except ImportError as e:
            self._log_error('import_error', f"SocketIO library not available: {e}")
            self.websocket_available = False
            return None
            
        except Exception as e:
            error_type = type(e).__name__
            self._log_error('initialization_error', f"WebSocket initialization failed ({error_type}): {e}")
            self.websocket_available = False
            
            # Enable graceful degradation
            if self.graceful_degradation_enabled:
                self._enable_graceful_degradation()
            
            return None
    
    def _get_socketio_config(self) -> Dict[str, Any]:
        """
        Get SocketIO configuration from app config.
        
        Returns:
            Configuration dictionary
        """
        # Get CORS origins from app config, with fallback to allow all
        cors_origins = self.app.config.get('SOCKETIO_CORS_ALLOWED_ORIGINS')
        if not cors_origins:
            cors_origins = self.app.config.get('CORS_ORIGINS', ['*'])
        
        return {
            'async_mode': self.app.config.get('SOCKETIO_ASYNC_MODE', 'threading'),
            'cors_allowed_origins': cors_origins,
            'logger': self.app.config.get('SOCKETIO_LOGGER', self.app.debug),
            'engineio_logger': self.app.config.get('SOCKETIO_ENGINEIO_LOGGER', self.app.debug),
            'ping_timeout': self.app.config.get('SOCKETIO_PING_TIMEOUT', 60),
            'ping_interval': self.app.config.get('SOCKETIO_PING_INTERVAL', 25),
            'max_http_buffer_size': self.app.config.get('SOCKETIO_MAX_HTTP_BUFFER_SIZE', 1000000),
            'allow_upgrades': True,
            'transports': ['polling', 'websocket']
        }
    
    def _test_websocket_functionality(self, socketio: SocketIO) -> bool:
        """
        Test basic WebSocket functionality.
        
        Args:
            socketio: SocketIO instance to test
            
        Returns:
            True if WebSocket is functional, False otherwise
        """
        try:
            # Basic functionality test - check if we can register handlers
            @socketio.on('test_connection')
            def handle_test_connection():
                return {'status': 'ok'}
            
            # Check if SocketIO is properly initialized
            if hasattr(socketio, 'server') and socketio.server is not None:
                return True
            
            return False
            
        except Exception as e:
            logger.debug(f"WebSocket functionality test failed: {e}")
            return False
    
    def _configure_websocket_settings(self):
        """Configure WebSocket-related application settings."""
        if self.websocket_available:
            self.app.config['WEBSOCKET_ENABLED'] = True
            self.app.config['REAL_TIME_NOTIFICATIONS'] = True
            logger.info("🔌 Real-time features enabled")
        else:
            self.app.config['WEBSOCKET_ENABLED'] = False
            self.app.config['REAL_TIME_NOTIFICATIONS'] = False
            logger.info("🔌 Real-time features disabled (WebSocket unavailable)")
    
    def _enable_graceful_degradation(self):
        """Enable graceful degradation when WebSocket is unavailable."""
        # Configure fallback mechanisms
        self.app.config['NOTIFICATION_FALLBACK_ENABLED'] = True
        self.app.config['POLLING_NOTIFICATIONS'] = True
        self.app.config['WEBSOCKET_FALLBACK_INTERVAL'] = 30  # seconds
        
        logger.info("🔄 WebSocket graceful degradation enabled")
    
    def _log_error(self, error_type: str, message: str):
        """
        Log error with rate limiting to prevent spam.
        
        Args:
            error_type: Type of error for rate limiting
            message: Error message to log
        """
        current_time = time.time()
        
        # Clean old errors (older than 1 minute)
        minute_ago = current_time - 60
        while self.error_counts[error_type] and self.error_counts[error_type][0] < minute_ago:
            self.error_counts[error_type].popleft()
        
        # Check if we should log this error
        if len(self.error_counts[error_type]) < self.error_rate_limit:
            self.error_counts[error_type].append(current_time)
            
            if error_type == 'import_error':
                logger.warning(f"⚠️  {message}")
            elif error_type == 'initialization_error':
                if self.connection_attempts == 1:
                    logger.warning(f"⚠️  {message}")
                elif self.connection_attempts >= self.max_connection_attempts:
                    logger.error(f"❌ WebSocket initialization failed after {self.max_connection_attempts} attempts, disabling WebSocket features")
                else:
                    logger.debug(f"WebSocket attempt {self.connection_attempts}: {message}")
            else:
                logger.warning(f"⚠️  WebSocket {error_type}: {message}")
        else:
            # Rate limited - log debug message
            logger.debug(f"WebSocket error rate limited: {error_type}")
    
    def get_socketio(self) -> Optional[SocketIO]:
        """
        Get SocketIO instance if available.
        
        Returns:
            SocketIO instance or None if unavailable
        """
        if self.websocket_available and self.socketio:
            return self.socketio
        return None
    
    def emit_with_fallback(self, event: str, data: Any, room: Optional[str] = None, 
                          fallback_callback: Optional[Callable] = None) -> bool:
        """
        Emit WebSocket event with fallback handling.
        
        Args:
            event: Event name
            data: Event data
            room: Room to emit to (optional)
            fallback_callback: Callback to execute if WebSocket unavailable
            
        Returns:
            True if event was emitted, False if fallback was used
        """
        try:
            if self.websocket_available and self.socketio:
                if room:
                    self.socketio.emit(event, data, room=room)
                else:
                    self.socketio.emit(event, data)
                return True
            else:
                # Use fallback mechanism
                if fallback_callback:
                    fallback_callback(event, data, room)
                else:
                    logger.debug(f"WebSocket unavailable, skipping event: {event}")
                return False
                
        except Exception as e:
            self._log_error('emit_error', f"Failed to emit event {event}: {e}")
            
            # Try fallback
            if fallback_callback:
                try:
                    fallback_callback(event, data, room)
                    return False
                except Exception as fallback_error:
                    logger.debug(f"Fallback also failed for event {event}: {fallback_error}")
            
            return False
    

    
    def get_status(self) -> Dict[str, Any]:
        """
        Get WebSocket manager status.
        
        Returns:
            Status dictionary with connection info
        """
        return {
            'websocket_available': self.websocket_available,
            'connection_attempts': self.connection_attempts,
            'max_connection_attempts': self.max_connection_attempts,
            'last_attempt_time': self.last_attempt_time,
            'graceful_degradation_enabled': self.graceful_degradation_enabled,
            'real_time_notifications': self.app.config.get('REAL_TIME_NOTIFICATIONS', False),
            'websocket_enabled': self.app.config.get('WEBSOCKET_ENABLED', False),
            'notification_fallback_enabled': self.app.config.get('NOTIFICATION_FALLBACK_ENABLED', False)
        }
    
    def retry_connection(self) -> bool:
        """
        Manually retry WebSocket connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        logger.info("🔄 Retrying WebSocket connection...")
        
        # Reset cooldown
        self.last_attempt_time = 0
        self.connection_attempts = 0
        
        # Try to reinitialize
        self.socketio = self._initialize_socketio()
        self._configure_websocket_settings()
        
        return self.websocket_available


# Global instance
websocket_manager = WebSocketConnectionManager()


def init_websocket_manager(app):
    """Initialize WebSocket manager for the application."""
    websocket_manager.init_app(app)
    
    # Set global socketio variable for compatibility
    import app
    app.socketio = websocket_manager.get_socketio()
    
    return websocket_manager


def get_websocket_manager():
    """Get the global WebSocket manager instance."""
    return websocket_manager


def get_socketio():
    """Get SocketIO instance using the global manager."""
    return websocket_manager.get_socketio()


def emit_with_fallback(event: str, data: Any, room: Optional[str] = None, 
                      fallback_callback: Optional[Callable] = None) -> bool:
    """Emit WebSocket event with fallback using the global manager."""
    return websocket_manager.emit_with_fallback(event, data, room, fallback_callback)



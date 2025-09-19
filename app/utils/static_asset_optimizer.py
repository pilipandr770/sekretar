"""
Static asset optimization for improved loading performance.
"""

import os
import hashlib
import gzip
import time
from typing import Dict, Any, Optional, List
from flask import Flask, request, current_app, send_from_directory, abort
from werkzeug.middleware.shared_data import SharedDataMiddleware
import structlog

logger = structlog.get_logger(__name__)


class StaticAssetOptimizer:
    """Optimizes static asset delivery for better performance."""
    
    def __init__(self, app=None):
        self.app = app
        self.asset_cache = {}
        self.compression_cache = {}
        self.asset_stats = {
            'requests': 0,
            'cache_hits': 0,
            'compressions': 0,
            'total_bytes_served': 0,
            'total_bytes_saved': 0
        }
        
        if app:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Initialize static asset optimizer with Flask app."""
        self.app = app
        
        # Configure static file serving
        self._configure_static_serving()
        
        # Set up asset caching
        self._setup_asset_caching()
        
        # Configure compression
        self._setup_compression()
        
        # Add cache headers
        self._setup_cache_headers()
        
        logger.info("Static asset optimizer initialized")
    
    def _configure_static_serving(self):
        """Configure optimized static file serving."""
        if not self.app:
            return
        
        # Override default static file handler
        @self.app.route('/static/<path:filename>')
        def optimized_static(filename):
            """Serve static files with optimizations."""
            return self._serve_static_file(filename)
        
        # Configure static folder settings
        static_folder = self.app.static_folder or 'static'
        if not os.path.exists(static_folder):
            os.makedirs(static_folder, exist_ok=True)
            logger.info("Created static folder", path=static_folder)
    
    def _serve_static_file(self, filename: str):
        """Serve static file with optimizations."""
        self.asset_stats['requests'] += 1
        
        static_folder = self.app.static_folder or 'static'
        file_path = os.path.join(static_folder, filename)
        
        # Check if file exists
        if not os.path.exists(file_path):
            abort(404)
        
        # Get file info
        file_stat = os.stat(file_path)
        file_size = file_stat.st_size
        file_mtime = file_stat.st_mtime
        
        # Generate ETag
        etag = self._generate_etag(file_path, file_mtime, file_size)
        
        # Check if client has cached version
        if request.headers.get('If-None-Match') == etag:
            self.asset_stats['cache_hits'] += 1
            return '', 304
        
        # Check for compression support
        accept_encoding = request.headers.get('Accept-Encoding', '')
        supports_gzip = 'gzip' in accept_encoding
        
        # Serve compressed version if available and supported
        if supports_gzip and self._should_compress(filename):
            compressed_response = self._serve_compressed(file_path, filename, etag)
            if compressed_response:
                return compressed_response
        
        # Serve regular file
        self.asset_stats['total_bytes_served'] += file_size
        
        response = send_from_directory(static_folder, filename)
        response.headers['ETag'] = etag
        
        return response
    
    def _generate_etag(self, file_path: str, mtime: float, size: int) -> str:
        """Generate ETag for file."""
        etag_data = f"{file_path}:{mtime}:{size}"
        return f'"{hashlib.md5(etag_data.encode()).hexdigest()}"'
    
    def _should_compress(self, filename: str) -> bool:
        """Check if file should be compressed."""
        compressible_extensions = {
            '.js', '.css', '.html', '.htm', '.xml', '.json',
            '.txt', '.svg', '.csv', '.md'
        }
        
        _, ext = os.path.splitext(filename.lower())
        return ext in compressible_extensions
    
    def _serve_compressed(self, file_path: str, filename: str, etag: str):
        """Serve compressed version of file."""
        # Check compression cache
        cache_key = f"{file_path}:{os.path.getmtime(file_path)}"
        
        if cache_key in self.compression_cache:
            compressed_data = self.compression_cache[cache_key]
            self.asset_stats['cache_hits'] += 1
        else:
            # Compress file
            try:
                with open(file_path, 'rb') as f:
                    original_data = f.read()
                
                compressed_data = gzip.compress(original_data)
                
                # Cache compressed data (limit cache size)
                if len(self.compression_cache) < 100:
                    self.compression_cache[cache_key] = compressed_data
                
                self.asset_stats['compressions'] += 1
                
                # Calculate savings
                original_size = len(original_data)
                compressed_size = len(compressed_data)
                savings = original_size - compressed_size
                self.asset_stats['total_bytes_saved'] += savings
                
                logger.debug(
                    "File compressed",
                    filename=filename,
                    original_size=original_size,
                    compressed_size=compressed_size,
                    savings_percent=round(savings / original_size * 100, 1)
                )
                
            except Exception as e:
                logger.warning("Compression failed", filename=filename, error=str(e))
                return None
        
        # Create response
        from flask import Response
        
        response = Response(
            compressed_data,
            mimetype=self._get_mimetype(filename)
        )
        
        response.headers['Content-Encoding'] = 'gzip'
        response.headers['ETag'] = etag
        response.headers['Vary'] = 'Accept-Encoding'
        
        self.asset_stats['total_bytes_served'] += len(compressed_data)
        
        return response
    
    def _get_mimetype(self, filename: str) -> str:
        """Get MIME type for file."""
        import mimetypes
        
        mimetype, _ = mimetypes.guess_type(filename)
        return mimetype or 'application/octet-stream'
    
    def _setup_asset_caching(self):
        """Set up asset caching strategies."""
        if not self.app:
            return
        
        # Configure cache control for different asset types
        cache_rules = {
            '.css': 86400,      # 1 day
            '.js': 86400,       # 1 day
            '.png': 604800,     # 1 week
            '.jpg': 604800,     # 1 week
            '.jpeg': 604800,    # 1 week
            '.gif': 604800,     # 1 week
            '.svg': 604800,     # 1 week
            '.ico': 2592000,    # 30 days
            '.woff': 2592000,   # 30 days
            '.woff2': 2592000,  # 30 days
            '.ttf': 2592000,    # 30 days
            '.eot': 2592000,    # 30 days
        }
        
        self.cache_rules = cache_rules
    
    def _setup_compression(self):
        """Set up asset compression."""
        # Pre-compress common static files
        if self.app and self.app.static_folder:
            self._precompress_assets()
    
    def _precompress_assets(self):
        """Pre-compress static assets for faster serving."""
        static_folder = self.app.static_folder
        
        if not os.path.exists(static_folder):
            return
        
        compressible_files = []
        
        # Find compressible files
        for root, dirs, files in os.walk(static_folder):
            for file in files:
                if self._should_compress(file):
                    file_path = os.path.join(root, file)
                    compressible_files.append(file_path)
        
        # Compress files
        compressed_count = 0
        for file_path in compressible_files:
            try:
                # Check if already compressed recently
                gz_path = file_path + '.gz'
                
                if (os.path.exists(gz_path) and 
                    os.path.getmtime(gz_path) > os.path.getmtime(file_path)):
                    continue
                
                # Compress file
                with open(file_path, 'rb') as f_in:
                    with gzip.open(gz_path, 'wb') as f_out:
                        f_out.write(f_in.read())
                
                compressed_count += 1
                
            except Exception as e:
                logger.warning("Pre-compression failed", file=file_path, error=str(e))
        
        if compressed_count > 0:
            logger.info("Pre-compressed static assets", count=compressed_count)
    
    def _setup_cache_headers(self):
        """Set up cache headers for static assets."""
        if not self.app:
            return
        
        @self.app.after_request
        def add_static_cache_headers(response):
            """Add cache headers for static assets."""
            if request.endpoint == 'static' or request.path.startswith('/static/'):
                filename = request.path.split('/')[-1]
                _, ext = os.path.splitext(filename.lower())
                
                # Get cache duration for file type
                cache_duration = self.cache_rules.get(ext, 3600)  # Default 1 hour
                
                # Set cache headers
                response.cache_control.max_age = cache_duration
                response.cache_control.public = True
                
                # Add immutable directive for versioned assets
                if self._is_versioned_asset(filename):
                    response.cache_control.immutable = True
                
                # Add ETag if not present
                if not response.get_etag()[0]:
                    response.add_etag()
            
            return response
    
    def _is_versioned_asset(self, filename: str) -> bool:
        """Check if asset has version hash in filename."""
        # Look for hash patterns like: app.a1b2c3d4.js or style-v1.2.3.css
        import re
        
        patterns = [
            r'\.[a-f0-9]{8,}\.',  # Hash pattern
            r'-v\d+\.\d+\.\d+\.',  # Version pattern
            r'\.\d{10,}\.',        # Timestamp pattern
        ]
        
        return any(re.search(pattern, filename) for pattern in patterns)
    
    def get_asset_stats(self) -> Dict[str, Any]:
        """Get static asset serving statistics."""
        stats = self.asset_stats.copy()
        
        # Calculate additional metrics
        if stats['requests'] > 0:
            stats['cache_hit_rate'] = (stats['cache_hits'] / stats['requests']) * 100
            stats['compression_rate'] = (stats['compressions'] / stats['requests']) * 100
        else:
            stats['cache_hit_rate'] = 0
            stats['compression_rate'] = 0
        
        if stats['total_bytes_served'] > 0:
            stats['compression_savings_rate'] = (
                stats['total_bytes_saved'] / 
                (stats['total_bytes_served'] + stats['total_bytes_saved'])
            ) * 100
        else:
            stats['compression_savings_rate'] = 0
        
        return stats
    
    def clear_cache(self):
        """Clear asset caches."""
        self.asset_cache.clear()
        self.compression_cache.clear()
        logger.info("Asset caches cleared")
    
    def optimize_assets(self):
        """Run asset optimization tasks."""
        if not self.app or not self.app.static_folder:
            return
        
        # Pre-compress assets
        self._precompress_assets()
        
        # Clean up old compressed files
        self._cleanup_old_compressed_files()
        
        logger.info("Asset optimization completed")
    
    def _cleanup_old_compressed_files(self):
        """Clean up old compressed files."""
        static_folder = self.app.static_folder
        
        if not os.path.exists(static_folder):
            return
        
        cleaned_count = 0
        
        for root, dirs, files in os.walk(static_folder):
            for file in files:
                if file.endswith('.gz'):
                    gz_path = os.path.join(root, file)
                    original_path = gz_path[:-3]  # Remove .gz extension
                    
                    # Remove if original file doesn't exist or is newer
                    if (not os.path.exists(original_path) or
                        os.path.getmtime(original_path) > os.path.getmtime(gz_path)):
                        try:
                            os.remove(gz_path)
                            cleaned_count += 1
                        except Exception as e:
                            logger.warning("Failed to remove old compressed file", 
                                         file=gz_path, error=str(e))
        
        if cleaned_count > 0:
            logger.info("Cleaned up old compressed files", count=cleaned_count)


class LazyLoadingManager:
    """Manages lazy loading of heavy components."""
    
    def __init__(self, app=None):
        self.app = app
        self.lazy_components = {}
        self.load_stats = {
            'components_registered': 0,
            'components_loaded': 0,
            'total_load_time': 0
        }
        
        if app:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Initialize lazy loading manager."""
        self.app = app
        logger.info("Lazy loading manager initialized")
    
    def register_lazy_component(self, name: str, loader_func, dependencies: List[str] = None):
        """Register a component for lazy loading."""
        self.lazy_components[name] = {
            'loader': loader_func,
            'dependencies': dependencies or [],
            'loaded': False,
            'instance': None,
            'load_time': None
        }
        
        self.load_stats['components_registered'] += 1
        logger.debug("Lazy component registered", name=name)
    
    def load_component(self, name: str):
        """Load a lazy component and its dependencies."""
        if name not in self.lazy_components:
            raise ValueError(f"Component '{name}' not registered")
        
        component = self.lazy_components[name]
        
        if component['loaded']:
            return component['instance']
        
        # Load dependencies first
        for dep in component['dependencies']:
            self.load_component(dep)
        
        # Load component
        start_time = time.time()
        
        try:
            component['instance'] = component['loader']()
            component['loaded'] = True
            component['load_time'] = time.time() - start_time
            
            self.load_stats['components_loaded'] += 1
            self.load_stats['total_load_time'] += component['load_time']
            
            logger.debug(
                "Lazy component loaded",
                name=name,
                load_time_ms=round(component['load_time'] * 1000, 2)
            )
            
            return component['instance']
            
        except Exception as e:
            logger.error("Failed to load lazy component", name=name, error=str(e))
            raise
    
    def get_component(self, name: str):
        """Get a component, loading it if necessary."""
        return self.load_component(name)
    
    def is_loaded(self, name: str) -> bool:
        """Check if a component is loaded."""
        return self.lazy_components.get(name, {}).get('loaded', False)
    
    def get_load_stats(self) -> Dict[str, Any]:
        """Get lazy loading statistics."""
        stats = self.load_stats.copy()
        
        if stats['components_loaded'] > 0:
            stats['avg_load_time'] = stats['total_load_time'] / stats['components_loaded']
        else:
            stats['avg_load_time'] = 0
        
        stats['load_rate'] = (
            stats['components_loaded'] / max(1, stats['components_registered']) * 100
        )
        
        return stats


# Global instances
static_asset_optimizer = StaticAssetOptimizer()
lazy_loading_manager = LazyLoadingManager()


def init_static_optimization(app):
    """Initialize static asset optimization for the Flask app."""
    static_asset_optimizer.init_app(app)
    lazy_loading_manager.init_app(app)
    
    return {
        'static_optimizer': static_asset_optimizer,
        'lazy_manager': lazy_loading_manager
    }
#!/usr/bin/env python3
"""
JavaScript Minification Script for AI Secretary
Minifies JavaScript files to reduce bundle sizes
"""

import os
import sys
import json
import gzip
import hashlib
from pathlib import Path
from typing import List, Dict, Tuple

# Try to import jsmin, fallback to basic minification
try:
    from jsmin import jsmin
    HAS_JSMIN = True
except ImportError:
    HAS_JSMIN = False
    print("Warning: jsmin not available, using basic minification")

class JavaScriptMinifier:
    def __init__(self, static_dir: str = "app/static"):
        self.static_dir = Path(static_dir)
        self.js_dir = self.static_dir / "js"
        self.minified_dir = self.js_dir / "min"
        self.manifest_file = self.minified_dir / "manifest.json"
        
        # Create minified directory if it doesn't exist
        self.minified_dir.mkdir(exist_ok=True)
        
        # Load existing manifest
        self.manifest = self.load_manifest()
        
        # Define module groups for bundling
        self.module_groups = {
            'core': [
                'browser-compatibility.js',
                'module-loader.js',
                'error-handler.js',
                'loading-manager.js',
                'ui-state-manager.js'
            ],
            'auth': [
                'auth-manager.js',
                'navigation-controller.js',
                'dropdown-manager.js'
            ],
            'i18n': [
                'i18n.js',
                'language-switcher.js',
                'language-persistence-manager.js',
                'enhanced-language-switcher.js'
            ],
            'websocket': [
                'websocket-client.js',
                'websocket-status-dashboard.js'
            ],
            'features': [
                'inbox-features.js',
                'crm-features.js',
                'calendar-features.js',
                'api-tester.js'
            ]
        }
    
    def load_manifest(self) -> Dict:
        """Load the manifest file containing file hashes and versions"""
        if self.manifest_file.exists():
            try:
                with open(self.manifest_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {}
    
    def save_manifest(self):
        """Save the manifest file"""
        with open(self.manifest_file, 'w') as f:
            json.dump(self.manifest, f, indent=2)
    
    def get_file_hash(self, file_path: Path) -> str:
        """Get MD5 hash of file content"""
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()[:8]
    
    def needs_minification(self, source_file: Path, minified_file: Path) -> bool:
        """Check if file needs to be minified"""
        if not minified_file.exists():
            return True
        
        source_hash = self.get_file_hash(source_file)
        manifest_key = source_file.name
        
        if manifest_key not in self.manifest:
            return True
        
        return self.manifest[manifest_key].get('hash') != source_hash
    
    def minify_file(self, source_file: Path) -> Tuple[str, Dict]:
        """Minify a single JavaScript file"""
        print(f"Minifying {source_file.name}...")
        
        with open(source_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Get original size
        original_size = len(content.encode('utf-8'))
        
        # Minify content
        if HAS_JSMIN:
            minified_content = jsmin(content)
        else:
            minified_content = self.basic_minify(content)
        
        # Get minified size
        minified_size = len(minified_content.encode('utf-8'))
        
        # Calculate compression ratio
        compression_ratio = (original_size - minified_size) / original_size * 100
        
        # Create versioned filename
        file_hash = hashlib.md5(minified_content.encode('utf-8')).hexdigest()[:8]
        base_name = source_file.stem
        minified_filename = f"{base_name}.{file_hash}.min.js"
        minified_file = self.minified_dir / minified_filename
        
        # Write minified file
        with open(minified_file, 'w', encoding='utf-8') as f:
            f.write(minified_content)
        
        # Create gzipped version for size comparison
        gzipped_size = len(gzip.compress(minified_content.encode('utf-8')))
        
        # Update manifest
        self.manifest[source_file.name] = {
            'hash': self.get_file_hash(source_file),
            'minified_file': minified_filename,
            'original_size': original_size,
            'minified_size': minified_size,
            'gzipped_size': gzipped_size,
            'compression_ratio': round(compression_ratio, 2)
        }
        
        return minified_content, {
            'original_size': original_size,
            'minified_size': minified_size,
            'gzipped_size': gzipped_size,
            'compression_ratio': compression_ratio
        }
    
    def basic_minify(self, content: str) -> str:
        """Basic JavaScript minification without external dependencies"""
        lines = content.split('\n')
        minified_lines = []
        
        in_multiline_comment = False
        
        for line in lines:
            # Remove leading/trailing whitespace
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Handle multiline comments
            if '/*' in line and '*/' not in line:
                in_multiline_comment = True
                continue
            elif '*/' in line:
                in_multiline_comment = False
                continue
            elif in_multiline_comment:
                continue
            
            # Skip single-line comments (but preserve URLs)
            if line.startswith('//') and 'http' not in line:
                continue
            
            # Remove inline comments (basic approach)
            if '//' in line and 'http' not in line:
                comment_pos = line.find('//')
                # Make sure it's not inside a string
                if line[:comment_pos].count('"') % 2 == 0 and line[:comment_pos].count("'") % 2 == 0:
                    line = line[:comment_pos].rstrip()
            
            if line:
                minified_lines.append(line)
        
        # Join lines and remove extra spaces
        minified = ' '.join(minified_lines)
        
        # Basic space reduction
        minified = minified.replace('  ', ' ')
        minified = minified.replace(' {', '{')
        minified = minified.replace('{ ', '{')
        minified = minified.replace(' }', '}')
        minified = minified.replace('} ', '}')
        minified = minified.replace(' (', '(')
        minified = minified.replace('( ', '(')
        minified = minified.replace(' )', ')')
        minified = minified.replace(') ', ')')
        minified = minified.replace(' ;', ';')
        minified = minified.replace('; ', ';')
        minified = minified.replace(' ,', ',')
        minified = minified.replace(', ', ',')
        
        return minified
    
    def create_bundle(self, group_name: str, files: List[str]) -> Tuple[str, Dict]:
        """Create a bundled and minified file from multiple sources"""
        print(f"Creating bundle: {group_name}")
        
        combined_content = []
        total_original_size = 0
        
        for filename in files:
            source_file = self.js_dir / filename
            if source_file.exists():
                with open(source_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    combined_content.append(f"// {filename}")
                    combined_content.append(content)
                    combined_content.append("")  # Add separator
                    total_original_size += len(content.encode('utf-8'))
            else:
                print(f"Warning: {filename} not found, skipping")
        
        if not combined_content:
            return "", {}
        
        # Combine all content
        full_content = '\n'.join(combined_content)
        
        # Minify combined content
        if HAS_JSMIN:
            minified_content = jsmin(full_content)
        else:
            minified_content = self.basic_minify(full_content)
        
        # Calculate sizes
        minified_size = len(minified_content.encode('utf-8'))
        gzipped_size = len(gzip.compress(minified_content.encode('utf-8')))
        compression_ratio = (total_original_size - minified_size) / total_original_size * 100
        
        # Create versioned bundle filename
        bundle_hash = hashlib.md5(minified_content.encode('utf-8')).hexdigest()[:8]
        bundle_filename = f"{group_name}-bundle.{bundle_hash}.min.js"
        bundle_file = self.minified_dir / bundle_filename
        
        # Write bundle file
        with open(bundle_file, 'w', encoding='utf-8') as f:
            f.write(minified_content)
        
        # Update manifest
        self.manifest[f"{group_name}-bundle"] = {
            'files': files,
            'bundle_file': bundle_filename,
            'original_size': total_original_size,
            'minified_size': minified_size,
            'gzipped_size': gzipped_size,
            'compression_ratio': round(compression_ratio, 2)
        }
        
        return minified_content, {
            'original_size': total_original_size,
            'minified_size': minified_size,
            'gzipped_size': gzipped_size,
            'compression_ratio': compression_ratio
        }
    
    def minify_all(self):
        """Minify all JavaScript files"""
        print("Starting JavaScript minification...")
        
        total_stats = {
            'files_processed': 0,
            'total_original_size': 0,
            'total_minified_size': 0,
            'total_gzipped_size': 0
        }
        
        # Process individual files
        for js_file in self.js_dir.glob("*.js"):
            if js_file.name.endswith('.min.js'):
                continue  # Skip already minified files
            
            minified_file = self.minified_dir / f"{js_file.stem}.min.js"
            
            if self.needs_minification(js_file, minified_file):
                try:
                    _, stats = self.minify_file(js_file)
                    total_stats['files_processed'] += 1
                    total_stats['total_original_size'] += stats['original_size']
                    total_stats['total_minified_size'] += stats['minified_size']
                    total_stats['total_gzipped_size'] += stats['gzipped_size']
                    
                    print(f"  {js_file.name}: {stats['original_size']} → {stats['minified_size']} bytes "
                          f"({stats['compression_ratio']:.1f}% reduction)")
                except Exception as e:
                    print(f"Error minifying {js_file.name}: {e}")
            else:
                print(f"  {js_file.name}: up to date")
        
        # Create bundles
        for group_name, files in self.module_groups.items():
            try:
                _, stats = self.create_bundle(group_name, files)
                if stats:
                    print(f"  {group_name} bundle: {stats['original_size']} → {stats['minified_size']} bytes "
                          f"({stats['compression_ratio']:.1f}% reduction)")
            except Exception as e:
                print(f"Error creating {group_name} bundle: {e}")
        
        # Save manifest
        self.save_manifest()
        
        # Print summary
        if total_stats['files_processed'] > 0:
            overall_compression = (
                (total_stats['total_original_size'] - total_stats['total_minified_size']) /
                total_stats['total_original_size'] * 100
            )
            
            print(f"\nMinification complete:")
            print(f"  Files processed: {total_stats['files_processed']}")
            print(f"  Original size: {self.format_size(total_stats['total_original_size'])}")
            print(f"  Minified size: {self.format_size(total_stats['total_minified_size'])}")
            print(f"  Gzipped size: {self.format_size(total_stats['total_gzipped_size'])}")
            print(f"  Overall compression: {overall_compression:.1f}%")
        else:
            print("\nAll files are up to date.")
    
    def format_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
    
    def clean_old_files(self):
        """Remove old minified files that are no longer referenced"""
        print("Cleaning old minified files...")
        
        # Get all referenced files from manifest
        referenced_files = set()
        for entry in self.manifest.values():
            if 'minified_file' in entry:
                referenced_files.add(entry['minified_file'])
            if 'bundle_file' in entry:
                referenced_files.add(entry['bundle_file'])
        
        # Remove unreferenced files
        removed_count = 0
        for minified_file in self.minified_dir.glob("*.min.js"):
            if minified_file.name not in referenced_files:
                minified_file.unlink()
                removed_count += 1
                print(f"  Removed: {minified_file.name}")
        
        if removed_count == 0:
            print("  No old files to remove")
        else:
            print(f"  Removed {removed_count} old files")
    
    def get_manifest_for_template(self) -> Dict:
        """Get manifest data formatted for use in templates"""
        template_manifest = {}
        
        for key, data in self.manifest.items():
            if 'minified_file' in data:
                template_manifest[key] = {
                    'url': f"/static/js/min/{data['minified_file']}",
                    'size': data['minified_size'],
                    'gzipped_size': data['gzipped_size']
                }
            elif 'bundle_file' in data:
                template_manifest[key] = {
                    'url': f"/static/js/min/{data['bundle_file']}",
                    'size': data['minified_size'],
                    'gzipped_size': data['gzipped_size'],
                    'files': data['files']
                }
        
        return template_manifest

def main():
    """Main function"""
    if len(sys.argv) > 1:
        static_dir = sys.argv[1]
    else:
        static_dir = "app/static"
    
    minifier = JavaScriptMinifier(static_dir)
    
    # Check if jsmin is available and suggest installation
    if not HAS_JSMIN:
        print("For better minification, install jsmin: pip install jsmin")
        print()
    
    # Minify all files
    minifier.minify_all()
    
    # Clean old files
    minifier.clean_old_files()
    
    # Save template manifest
    template_manifest = minifier.get_manifest_for_template()
    template_manifest_file = minifier.minified_dir / "template-manifest.json"
    with open(template_manifest_file, 'w') as f:
        json.dump(template_manifest, f, indent=2)
    
    print(f"\nTemplate manifest saved to: {template_manifest_file}")
    print("Use this manifest in your templates to reference minified files.")

if __name__ == "__main__":
    main()
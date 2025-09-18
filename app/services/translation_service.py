"""Translation management service for i18n administration."""
import os
import re
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from pathlib import Path
from flask import current_app
from flask_babel import gettext as _
from babel.messages import Catalog
from babel.messages.pofile import read_po, write_po
from babel.messages.mofile import write_mo
from babel.messages.extract import extract_from_dir
from babel.util import LOCALTZ
from app import db
from app.utils.i18n import LANGUAGES
import structlog

logger = structlog.get_logger()


class TranslationValidationError(Exception):
    """Exception raised for translation validation errors."""
    pass


class TranslationService:
    """Service for managing translations and monitoring coverage."""
    
    def __init__(self):
        app_root = Path(current_app.root_path)
        self.translations_dir = app_root / 'translations'
        self.template_dir = app_root / 'templates'
        self.static_dir = app_root / 'static'
        self.babel_cfg = app_root.parent / 'babel.cfg'
        
    def extract_messages(self) -> Dict[str, Any]:
        """Extract all translatable messages from the application."""
        try:
            logger.info("Starting message extraction")
            
            # Create translations directory if it doesn't exist
            self.translations_dir.mkdir(exist_ok=True)
            
            # Extract messages using Babel
            catalog = Catalog()
            
            # Define extraction methods
            extraction_methods = [
                ('**.py', 'python'),
                ('**/templates/**.html', 'jinja2'),
                ('**/static/js/**.js', 'javascript'),
            ]
            
            extracted_count = 0
            
            # Extract from Python files
            for filename, lineno, message, comments, context in extract_from_dir(
                current_app.root_path,
                method_map=[('**.py', 'python')],
                options_map={'python': {'keywords': '_:1,2 gettext:1 ngettext:1,2 lazy_gettext:1 _l:1'}},
                comment_tags=['TRANSLATORS:'],
                strip_comments=True
            ):
                catalog.add(message, locations=[(filename, lineno)], auto_comments=comments)
                extracted_count += 1
            
            # Extract from Jinja2 templates
            for filename, lineno, message, comments, context in extract_from_dir(
                self.template_dir,
                method_map=[('**.html', 'jinja2')],
                options_map={'jinja2': {'extensions': 'jinja2.ext.autoescape,jinja2.ext.with_'}},
                comment_tags=['TRANSLATORS:'],
                strip_comments=True
            ):
                catalog.add(message, locations=[(filename, lineno)], auto_comments=comments)
                extracted_count += 1
            
            # Extract from JavaScript files
            for filename, lineno, message, comments, context in extract_from_dir(
                self.static_dir,
                method_map=[('**.js', 'javascript')],
                options_map={'javascript': {'keywords': '_:1 gettext:1 ngettext:1,2'}},
                comment_tags=['TRANSLATORS:'],
                strip_comments=True
            ):
                catalog.add(message, locations=[(filename, lineno)], auto_comments=comments)
                extracted_count += 1
            
            # Write messages.pot file
            pot_file = self.translations_dir / 'messages.pot'
            with open(pot_file, 'wb') as f:
                write_po(f, catalog, sort_output=True, sort_by_file=True)
            
            # Update existing .po files
            updated_languages = []
            for lang_code in LANGUAGES.keys():
                if self._update_po_file(lang_code, catalog):
                    updated_languages.append(lang_code)
            
            result = {
                'extracted_messages': extracted_count,
                'total_unique_messages': len(catalog),
                'updated_languages': updated_languages,
                'pot_file': str(pot_file),
                'timestamp': datetime.now(LOCALTZ).isoformat()
            }
            
            logger.info("Message extraction completed", **result)
            return result
            
        except Exception as e:
            logger.error("Failed to extract messages", error=str(e), exc_info=True)
            raise TranslationValidationError(f"Message extraction failed: {str(e)}")
    
    def _update_po_file(self, language: str, template_catalog: Catalog) -> bool:
        """Update a .po file with new messages from template catalog."""
        try:
            lang_dir = self.translations_dir / language / 'LC_MESSAGES'
            lang_dir.mkdir(parents=True, exist_ok=True)
            
            po_file = lang_dir / 'messages.po'
            
            if po_file.exists():
                # Load existing catalog
                with open(po_file, 'rb') as f:
                    catalog = read_po(f, locale=language)
                
                # Update with new messages
                catalog.update(template_catalog, update_header_comment=True)
            else:
                # Create new catalog
                catalog = Catalog(locale=language)
                catalog.update(template_catalog)
            
            # Write updated catalog
            with open(po_file, 'wb') as f:
                write_po(f, catalog, sort_output=True, sort_by_file=True)
            
            logger.info(f"Updated .po file for {language}", file=str(po_file))
            return True
            
        except Exception as e:
            logger.error(f"Failed to update .po file for {language}", error=str(e))
            return False
    
    def compile_translations(self) -> Dict[str, Any]:
        """Compile all .po files to .mo files."""
        try:
            logger.info("Starting translation compilation")
            
            compiled_languages = []
            compilation_errors = []
            
            for lang_code in LANGUAGES.keys():
                try:
                    if self._compile_language(lang_code):
                        compiled_languages.append(lang_code)
                except Exception as e:
                    compilation_errors.append({
                        'language': lang_code,
                        'error': str(e)
                    })
            
            result = {
                'compiled_languages': compiled_languages,
                'compilation_errors': compilation_errors,
                'timestamp': datetime.now(LOCALTZ).isoformat()
            }
            
            logger.info("Translation compilation completed", **result)
            return result
            
        except Exception as e:
            logger.error("Failed to compile translations", error=str(e), exc_info=True)
            raise TranslationValidationError(f"Translation compilation failed: {str(e)}")
    
    def _compile_language(self, language: str) -> bool:
        """Compile a single language's .po file to .mo file."""
        lang_dir = self.translations_dir / language / 'LC_MESSAGES'
        po_file = lang_dir / 'messages.po'
        mo_file = lang_dir / 'messages.mo'
        
        if not po_file.exists():
            logger.warning(f"No .po file found for {language}")
            return False
        
        try:
            # Read .po file
            with open(po_file, 'rb') as f:
                catalog = read_po(f, locale=language)
            
            # Write .mo file
            with open(mo_file, 'wb') as f:
                write_mo(f, catalog)
            
            logger.info(f"Compiled {language} translations", 
                       po_file=str(po_file), mo_file=str(mo_file))
            return True
            
        except Exception as e:
            logger.error(f"Failed to compile {language} translations", error=str(e))
            raise
    
    def get_translation_coverage(self) -> Dict[str, Dict[str, Any]]:
        """Get translation coverage statistics for all languages."""
        try:
            coverage_stats = {}
            
            for lang_code, lang_name in LANGUAGES.items():
                stats = self._get_language_coverage(lang_code)
                coverage_stats[lang_code] = {
                    'language_name': lang_name,
                    'language_code': lang_code,
                    **stats
                }
            
            return coverage_stats
            
        except Exception as e:
            logger.error("Failed to get translation coverage", error=str(e), exc_info=True)
            raise TranslationValidationError(f"Coverage calculation failed: {str(e)}")
    
    def _get_language_coverage(self, language: str) -> Dict[str, Any]:
        """Get coverage statistics for a specific language."""
        lang_dir = self.translations_dir / language / 'LC_MESSAGES'
        po_file = lang_dir / 'messages.po'
        
        if not po_file.exists():
            return {
                'total_messages': 0,
                'translated_messages': 0,
                'untranslated_messages': 0,
                'fuzzy_messages': 0,
                'coverage_percentage': 0.0,
                'status': 'missing',
                'last_updated': None
            }
        
        try:
            with open(po_file, 'rb') as f:
                catalog = read_po(f, locale=language)
            
            total_messages = len(catalog)
            translated_messages = 0
            fuzzy_messages = 0
            untranslated_messages = 0
            
            for message in catalog:
                if message.id:  # Skip header
                    if message.string:
                        if message.fuzzy:
                            fuzzy_messages += 1
                        else:
                            translated_messages += 1
                    else:
                        untranslated_messages += 1
            
            # Calculate coverage percentage (excluding fuzzy)
            if total_messages > 0:
                coverage_percentage = (translated_messages / total_messages) * 100
            else:
                coverage_percentage = 0.0
            
            # Determine status
            if coverage_percentage >= 95:
                status = 'complete'
            elif coverage_percentage >= 75:
                status = 'good'
            elif coverage_percentage >= 50:
                status = 'partial'
            else:
                status = 'incomplete'
            
            return {
                'total_messages': total_messages,
                'translated_messages': translated_messages,
                'untranslated_messages': untranslated_messages,
                'fuzzy_messages': fuzzy_messages,
                'coverage_percentage': round(coverage_percentage, 2),
                'status': status,
                'last_updated': datetime.fromtimestamp(po_file.stat().st_mtime).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get coverage for {language}", error=str(e))
            return {
                'total_messages': 0,
                'translated_messages': 0,
                'untranslated_messages': 0,
                'fuzzy_messages': 0,
                'coverage_percentage': 0.0,
                'status': 'error',
                'last_updated': None,
                'error': str(e)
            }
    
    def get_missing_translations(self, language: Optional[str] = None) -> Dict[str, List[str]]:
        """Get list of missing translations by language."""
        try:
            missing_translations = {}
            
            languages_to_check = [language] if language else LANGUAGES.keys()
            
            for lang_code in languages_to_check:
                missing_translations[lang_code] = self._get_missing_for_language(lang_code)
            
            return missing_translations
            
        except Exception as e:
            logger.error("Failed to get missing translations", error=str(e), exc_info=True)
            raise TranslationValidationError(f"Missing translations check failed: {str(e)}")
    
    def _get_missing_for_language(self, language: str) -> List[str]:
        """Get missing translations for a specific language."""
        lang_dir = self.translations_dir / language / 'LC_MESSAGES'
        po_file = lang_dir / 'messages.po'
        
        if not po_file.exists():
            return []
        
        try:
            missing_messages = []
            
            with open(po_file, 'rb') as f:
                catalog = read_po(f, locale=language)
            
            for message in catalog:
                if message.id and not message.string:
                    missing_messages.append(message.id)
            
            return missing_messages
            
        except Exception as e:
            logger.error(f"Failed to get missing translations for {language}", error=str(e))
            return []
    
    def validate_translations(self, language: Optional[str] = None) -> List[Dict[str, Any]]:
        """Validate translations for consistency and correctness."""
        try:
            validation_errors = []
            
            languages_to_check = [language] if language else LANGUAGES.keys()
            
            for lang_code in languages_to_check:
                errors = self._validate_language(lang_code)
                validation_errors.extend(errors)
            
            return validation_errors
            
        except Exception as e:
            logger.error("Failed to validate translations", error=str(e), exc_info=True)
            raise TranslationValidationError(f"Translation validation failed: {str(e)}")
    
    def _validate_language(self, language: str) -> List[Dict[str, Any]]:
        """Validate translations for a specific language."""
        lang_dir = self.translations_dir / language / 'LC_MESSAGES'
        po_file = lang_dir / 'messages.po'
        
        if not po_file.exists():
            return [{
                'language': language,
                'type': 'missing_file',
                'message': f'Translation file not found: {po_file}',
                'severity': 'error'
            }]
        
        try:
            validation_errors = []
            
            with open(po_file, 'rb') as f:
                catalog = read_po(f, locale=language)
            
            for message in catalog:
                if not message.id:  # Skip header
                    continue
                
                # Check for missing translations
                if not message.string:
                    validation_errors.append({
                        'language': language,
                        'type': 'missing_translation',
                        'message_id': message.id,
                        'message': f'Missing translation for: {message.id}',
                        'severity': 'warning',
                        'locations': [f"{loc[0]}:{loc[1]}" for loc in message.locations]
                    })
                    continue
                
                # Check for placeholder consistency
                source_placeholders = self._extract_placeholders(message.id)
                target_placeholders = self._extract_placeholders(message.string)
                
                if source_placeholders != target_placeholders:
                    validation_errors.append({
                        'language': language,
                        'type': 'placeholder_mismatch',
                        'message_id': message.id,
                        'message': f'Placeholder mismatch: source has {source_placeholders}, target has {target_placeholders}',
                        'severity': 'error',
                        'locations': [f"{loc[0]}:{loc[1]}" for loc in message.locations]
                    })
                
                # Check for HTML tag consistency
                if self._has_html_tags(message.id):
                    source_tags = self._extract_html_tags(message.id)
                    target_tags = self._extract_html_tags(message.string)
                    
                    if source_tags != target_tags:
                        validation_errors.append({
                            'language': language,
                            'type': 'html_tag_mismatch',
                            'message_id': message.id,
                            'message': f'HTML tag mismatch: source has {source_tags}, target has {target_tags}',
                            'severity': 'error',
                            'locations': [f"{loc[0]}:{loc[1]}" for loc in message.locations]
                        })
                
                # Check for fuzzy translations
                if message.fuzzy:
                    validation_errors.append({
                        'language': language,
                        'type': 'fuzzy_translation',
                        'message_id': message.id,
                        'message': f'Fuzzy translation needs review: {message.id}',
                        'severity': 'info',
                        'locations': [f"{loc[0]}:{loc[1]}" for loc in message.locations]
                    })
            
            return validation_errors
            
        except Exception as e:
            logger.error(f"Failed to validate {language} translations", error=str(e))
            return [{
                'language': language,
                'type': 'validation_error',
                'message': f'Validation failed: {str(e)}',
                'severity': 'error'
            }]
    
    def _extract_placeholders(self, text: str) -> set:
        """Extract placeholders from text (%(name)s format)."""
        return set(re.findall(r'%\([^)]+\)[sd]', text))
    
    def _has_html_tags(self, text: str) -> bool:
        """Check if text contains HTML tags."""
        return bool(re.search(r'<[^>]+>', text))
    
    def _extract_html_tags(self, text: str) -> set:
        """Extract HTML tags from text."""
        return set(re.findall(r'<[^>]+>', text))
    
    def update_translation(self, language: str, message_id: str, translation: str) -> bool:
        """Update a specific translation."""
        try:
            lang_dir = self.translations_dir / language / 'LC_MESSAGES'
            po_file = lang_dir / 'messages.po'
            
            if not po_file.exists():
                logger.error(f"Translation file not found for {language}")
                return False
            
            # Read existing catalog
            with open(po_file, 'rb') as f:
                catalog = read_po(f, locale=language)
            
            # Find and update the message
            message = catalog.get(message_id)
            if message:
                message.string = translation
                message.fuzzy = False  # Remove fuzzy flag
                
                # Write updated catalog
                with open(po_file, 'wb') as f:
                    write_po(f, catalog, sort_output=True, sort_by_file=True)
                
                logger.info(f"Updated translation for {language}", 
                           message_id=message_id, translation=translation)
                return True
            else:
                logger.error(f"Message not found in catalog: {message_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to update translation", 
                        language=language, message_id=message_id, error=str(e))
            return False
    
    def get_translation_statistics(self) -> Dict[str, Any]:
        """Get comprehensive translation statistics."""
        try:
            coverage_stats = self.get_translation_coverage()
            
            # Calculate overall statistics
            total_languages = len(LANGUAGES)
            complete_languages = sum(1 for stats in coverage_stats.values() 
                                   if stats['status'] == 'complete')
            
            total_messages = max((stats['total_messages'] for stats in coverage_stats.values()), default=0)
            
            overall_coverage = 0
            if total_messages > 0:
                total_translated = sum(stats['translated_messages'] for stats in coverage_stats.values())
                overall_coverage = (total_translated / (total_messages * total_languages)) * 100
            
            return {
                'overall_coverage': round(overall_coverage, 2),
                'total_languages': total_languages,
                'complete_languages': complete_languages,
                'total_messages': total_messages,
                'languages': coverage_stats,
                'last_updated': datetime.now(LOCALTZ).isoformat()
            }
            
        except Exception as e:
            logger.error("Failed to get translation statistics", error=str(e), exc_info=True)
            raise TranslationValidationError(f"Statistics calculation failed: {str(e)}")
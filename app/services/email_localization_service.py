"""Email template localization service for multi-language email support."""
import logging
from typing import Dict, Optional, Any, List, Tuple
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, Template, TemplateNotFound
from flask import current_app, render_template_string
from flask_babel import gettext, ngettext, lazy_gettext as _l

from app.models import User, Tenant
from app.utils.i18n import get_user_language, LANGUAGES
from app.utils.database import db

logger = logging.getLogger(__name__)


class EmailLocalizationService:
    """Service for localizing email templates and content."""
    
    def __init__(self):
        self.logger = logging.getLogger("email.localization")
        self.template_cache = {}
        self.fallback_language = 'en'
        self._jinja_env = None
    
    @property
    def jinja_env(self):
        """Lazy initialization of Jinja2 environment."""
        if self._jinja_env is None:
            # Initialize Jinja2 environment for email templates
            self._jinja_env = Environment(
                loader=FileSystemLoader([
                    'app/templates/emails',
                    'app/templates'
                ]),
                autoescape=True,
                extensions=['jinja2.ext.i18n']
            )
            
            # Install gettext functions for Jinja2 if we have an app context
            try:
                if current_app:
                    self._jinja_env.install_gettext_translations(
                        current_app.babel.domain,
                        newstyle=True
                    )
            except RuntimeError:
                # No app context, skip gettext installation
                pass
        
        return self._jinja_env
    
    def get_user_language_preference(self, user: User) -> str:
        """Get user's language preference with fallbacks."""
        if user and hasattr(user, 'language') and user.language:
            if user.language in LANGUAGES:
                return user.language
        
        # Try tenant default language
        if user and user.tenant_id:
            tenant = Tenant.query.get(user.tenant_id)
            if tenant and hasattr(tenant, 'default_language') and tenant.default_language:
                if tenant.default_language in LANGUAGES:
                    return tenant.default_language
        
        return self.fallback_language
    
    def get_localized_template_path(self, template_name: str, language: str) -> str:
        """Get localized template path with fallback logic."""
        # Try language-specific template first
        localized_path = f"emails/{language}/{template_name}"
        
        # Check if localized template exists
        try:
            self.jinja_env.get_template(localized_path)
            return localized_path
        except TemplateNotFound:
            pass
        
        # Try fallback language
        if language != self.fallback_language:
            fallback_path = f"emails/{self.fallback_language}/{template_name}"
            try:
                self.jinja_env.get_template(fallback_path)
                return fallback_path
            except TemplateNotFound:
                pass
        
        # Try generic template
        generic_path = f"emails/{template_name}"
        try:
            self.jinja_env.get_template(generic_path)
            return generic_path
        except TemplateNotFound:
            pass
        
        # Last resort: return the requested path (will cause error if used)
        return localized_path
    
    def get_localized_template(self, template_name: str, language: str) -> Optional[Template]:
        """Get localized email template."""
        cache_key = f"{template_name}_{language}"
        
        # Check cache first
        if cache_key in self.template_cache:
            return self.template_cache[cache_key]
        
        try:
            template_path = self.get_localized_template_path(template_name, language)
            template = self.jinja_env.get_template(template_path)
            
            # Cache the template
            self.template_cache[cache_key] = template
            return template
        
        except TemplateNotFound as e:
            self.logger.error(f"Email template not found: {template_name} for language {language}")
            return None
        except Exception as e:
            self.logger.error(f"Error loading email template {template_name}: {str(e)}")
            return None
    
    def render_localized_email(
        self, 
        template_name: str, 
        context: Dict[str, Any], 
        language: str,
        user: Optional[User] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Render localized email template.
        
        Returns:
            Tuple of (subject, html_content) or (None, None) if failed
        """
        try:
            # Get user language if not provided
            if not language and user:
                language = self.get_user_language_preference(user)
            elif not language:
                language = self.fallback_language
            
            # Get localized template
            template = self.get_localized_template(template_name, language)
            if not template:
                self.logger.error(f"Could not load template {template_name} for language {language}")
                return None, None
            
            # Add localization context
            localized_context = self._prepare_localization_context(context, language, user)
            
            # Render template
            rendered_content = template.render(**localized_context)
            
            # Extract subject from rendered content (if template includes subject)
            subject, html_content = self._extract_subject_and_content(rendered_content)
            
            self.logger.info(f"Successfully rendered email template {template_name} for language {language}")
            return subject, html_content
        
        except Exception as e:
            self.logger.error(f"Error rendering email template {template_name}: {str(e)}")
            return None, None
    
    def get_localized_subject(
        self, 
        subject_key: str, 
        language: str, 
        user: Optional[User] = None,
        **kwargs
    ) -> str:
        """Get localized email subject."""
        try:
            # Set language context for gettext
            with current_app.test_request_context():
                # Temporarily set language
                from flask import session
                original_lang = session.get('language')
                session['language'] = language
                
                try:
                    # Get translated subject
                    subject = str(gettext(subject_key))
                    
                    # Format with parameters if provided
                    if kwargs:
                        subject = subject.format(**kwargs)
                    
                    return subject
                finally:
                    # Restore original language
                    if original_lang:
                        session['language'] = original_lang
                    elif 'language' in session:
                        del session['language']
        
        except Exception as e:
            self.logger.error(f"Error getting localized subject {subject_key}: {str(e)}")
            return subject_key
    
    def send_localized_email(
        self,
        recipient: User,
        template_name: str,
        context: Dict[str, Any],
        subject_key: Optional[str] = None,
        subject_params: Optional[Dict[str, Any]] = None,
        priority: str = 'normal'
    ) -> bool:
        """Send localized email to user."""
        try:
            # Get user's language preference
            language = self.get_user_language_preference(recipient)
            
            # Render email content
            subject, html_content = self.render_localized_email(
                template_name, context, language, recipient
            )
            
            if not html_content:
                self.logger.error(f"Failed to render email template {template_name}")
                return False
            
            # Get localized subject if provided
            if subject_key:
                subject = self.get_localized_subject(
                    subject_key, language, recipient, **(subject_params or {})
                )
            elif not subject:
                subject = "Notification"  # Fallback subject
            
            # Send email using notification service
            from app.services.notification_service import NotificationService
            notification_service = NotificationService()
            
            notification = notification_service.create_notification(
                tenant_id=recipient.tenant_id,
                recipient=recipient.email,
                notification_type='email',
                subject=subject,
                body=self._html_to_text(html_content),  # Plain text version
                html_body=html_content,
                user_id=recipient.id,
                priority=priority,
                variables=context
            )
            
            if notification:
                notification_service.send_notification_async(notification.id)
                self.logger.info(f"Queued localized email for {recipient.email} in {language}")
                return True
            
            return False
        
        except Exception as e:
            self.logger.error(f"Error sending localized email: {str(e)}")
            return False
    
    def _prepare_localization_context(
        self, 
        context: Dict[str, Any], 
        language: str,
        user: Optional[User] = None
    ) -> Dict[str, Any]:
        """Prepare context with localization helpers."""
        localized_context = context.copy()
        
        # Add localization helpers
        localized_context.update({
            'language': language,
            'user_language': language,
            'available_languages': LANGUAGES,
            'language_name': LANGUAGES.get(language, language),
            'user': user,
            'current_date': datetime.now(),
            'gettext': lambda x: self._get_translated_text(x, language),
            'ngettext': lambda s, p, n: self._get_plural_text(s, p, n, language),
            '_': lambda x: self._get_translated_text(x, language),
        })
        
        # Add formatting helpers
        localized_context.update({
            'format_date': lambda d: self._format_date(d, language),
            'format_datetime': lambda d: self._format_datetime(d, language),
            'format_currency': lambda a, c='EUR': self._format_currency(a, c, language),
            'format_number': lambda n: self._format_number(n, language),
        })
        
        return localized_context
    
    def _get_translated_text(self, text: str, language: str) -> str:
        """Get translated text for specific language."""
        try:
            with current_app.test_request_context():
                from flask import session
                original_lang = session.get('language')
                session['language'] = language
                
                try:
                    return str(gettext(text))
                finally:
                    if original_lang:
                        session['language'] = original_lang
                    elif 'language' in session:
                        del session['language']
        except:
            return text
    
    def _get_plural_text(self, singular: str, plural: str, count: int, language: str) -> str:
        """Get plural text for specific language."""
        try:
            with current_app.test_request_context():
                from flask import session
                original_lang = session.get('language')
                session['language'] = language
                
                try:
                    return str(ngettext(singular, plural, count))
                finally:
                    if original_lang:
                        session['language'] = original_lang
                    elif 'language' in session:
                        del session['language']
        except:
            return plural if count != 1 else singular
    
    def _format_date(self, date: datetime, language: str) -> str:
        """Format date according to language locale."""
        if not date:
            return ""
        
        formats = {
            'en': '%B %d, %Y',
            'de': '%d. %B %Y',
            'uk': '%d %B %Y'
        }
        
        format_str = formats.get(language, formats['en'])
        return date.strftime(format_str)
    
    def _format_datetime(self, datetime_obj: datetime, language: str) -> str:
        """Format datetime according to language locale."""
        if not datetime_obj:
            return ""
        
        formats = {
            'en': '%B %d, %Y at %I:%M %p',
            'de': '%d. %B %Y um %H:%M',
            'uk': '%d %B %Y о %H:%M'
        }
        
        format_str = formats.get(language, formats['en'])
        return datetime_obj.strftime(format_str)
    
    def _format_currency(self, amount: float, currency: str, language: str) -> str:
        """Format currency according to language locale."""
        if amount is None:
            return ""
        
        if language == 'de':
            return f"{amount:,.2f} {currency}".replace(',', 'X').replace('.', ',').replace('X', '.')
        elif language == 'uk':
            return f"{amount:,.2f} {currency}"
        else:  # English
            return f"{currency} {amount:,.2f}"
    
    def _format_number(self, number: float, language: str) -> str:
        """Format number according to language locale."""
        if number is None:
            return ""
        
        if language == 'de':
            return f"{number:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        else:
            return f"{number:,.2f}"
    
    def _extract_subject_and_content(self, rendered_content: str) -> Tuple[Optional[str], str]:
        """Extract subject line from rendered email content."""
        lines = rendered_content.split('\n')
        subject = None
        content_lines = []
        
        # Look for subject line at the beginning
        for i, line in enumerate(lines):
            line = line.strip()
            if line.startswith('Subject:'):
                subject = line[8:].strip()
                # Skip this line and any empty lines after it
                content_lines = lines[i+1:]
                break
            elif line.startswith('SUBJECT:'):
                subject = line[8:].strip()
                content_lines = lines[i+1:]
                break
            else:
                content_lines.append(line)
        
        # Join remaining content
        content = '\n'.join(content_lines).strip()
        
        return subject, content
    
    def _html_to_text(self, html_content: str) -> str:
        """Convert HTML content to plain text."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            return soup.get_text(separator='\n', strip=True)
        except ImportError:
            # Fallback: simple HTML tag removal
            import re
            text = re.sub(r'<[^>]+>', '', html_content)
            return text.strip()
    
    def clear_template_cache(self, template_name: Optional[str] = None, language: Optional[str] = None):
        """Clear template cache."""
        if template_name and language:
            cache_key = f"{template_name}_{language}"
            self.template_cache.pop(cache_key, None)
        elif template_name:
            # Clear all language variants of this template
            keys_to_remove = [k for k in self.template_cache.keys() if k.startswith(f"{template_name}_")]
            for key in keys_to_remove:
                self.template_cache.pop(key, None)
        else:
            # Clear entire cache
            self.template_cache.clear()
    
    def get_available_templates(self, language: str) -> List[str]:
        """Get list of available email templates for a language."""
        templates = []
        
        try:
            # Check language-specific templates
            lang_path = f"emails/{language}"
            try:
                template_list = self.jinja_env.list_templates(filter_func=lambda x: x.startswith(lang_path))
                templates.extend([t.replace(f"{lang_path}/", "") for t in template_list])
            except:
                pass
            
            # Check generic templates
            try:
                generic_list = self.jinja_env.list_templates(filter_func=lambda x: x.startswith("emails/") and "/" not in x[7:])
                templates.extend([t.replace("emails/", "") for t in generic_list])
            except:
                pass
            
            return list(set(templates))  # Remove duplicates
        
        except Exception as e:
            self.logger.error(f"Error getting available templates: {str(e)}")
            return []
    
    def validate_template(self, template_name: str, language: str) -> Dict[str, Any]:
        """Validate email template and return validation results."""
        result = {
            'valid': False,
            'exists': False,
            'errors': [],
            'warnings': []
        }
        
        try:
            # Check if template exists
            template = self.get_localized_template(template_name, language)
            if not template:
                result['errors'].append(f"Template {template_name} not found for language {language}")
                return result
            
            result['exists'] = True
            
            # Try to render with minimal context
            test_context = {
                'user': {'name': 'Test User', 'email': 'test@example.com'},
                'company_name': 'Test Company',
                'message': 'Test message'
            }
            
            subject, content = self.render_localized_email(template_name, test_context, language)
            
            if content:
                result['valid'] = True
                
                # Check for common issues
                if not subject:
                    result['warnings'].append("No subject line found in template")
                
                if len(content) < 50:
                    result['warnings'].append("Template content seems very short")
                
                if 'test@example.com' in content.lower():
                    result['warnings'].append("Template may contain test data")
            else:
                result['errors'].append("Template failed to render")
        
        except Exception as e:
            result['errors'].append(f"Template validation error: {str(e)}")
        
        return result


# Global service instance (lazy initialization)
_email_localization_service = None


def get_email_localization_service() -> EmailLocalizationService:
    """Get the global email localization service instance."""
    global _email_localization_service
    if _email_localization_service is None:
        _email_localization_service = EmailLocalizationService()
    return _email_localization_service


def send_localized_email(recipient: User, template_name: str, context: Dict[str, Any], **kwargs) -> bool:
    """Convenience function to send localized email."""
    return get_email_localization_service().send_localized_email(recipient, template_name, context, **kwargs)


def render_localized_email(template_name: str, context: Dict[str, Any], language: str, user: Optional[User] = None) -> Tuple[Optional[str], Optional[str]]:
    """Convenience function to render localized email."""
    return get_email_localization_service().render_localized_email(template_name, context, language, user)
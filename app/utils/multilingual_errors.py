"""
Multilingual Error Messages

This module provides multilingual error message support with automatic
language detection and fallback to English.
"""
import logging
from typing import Dict, Any, Optional, List
from flask import request, session, current_app, has_request_context
import structlog

logger = structlog.get_logger(__name__)


def _(text: str) -> str:
    """Safe gettext function that works with or without Babel."""
    try:
        if current_app and 'babel' in current_app.extensions:
            from flask_babel import gettext
            return gettext(text)
    except (ImportError, RuntimeError, KeyError):
        pass
    return text


def ngettext(singular: str, plural: str, n: int) -> str:
    """Safe ngettext function that works with or without Babel."""
    try:
        if current_app and 'babel' in current_app.extensions:
            from flask_babel import ngettext as babel_ngettext
            return babel_ngettext(singular, plural, n)
    except (ImportError, RuntimeError, KeyError):
        pass
    return singular if n == 1 else plural


class MultilingualErrorMessages:
    """Manages multilingual error messages with automatic language detection."""
    
    def __init__(self):
        self.supported_languages = ['en', 'de', 'uk']
        self.default_language = 'en'
        self.error_messages = self._load_error_messages()
    
    def _load_error_messages(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Load error messages for all supported languages."""
        return {
            'en': {
                # Database errors
                'database_connection_failed': {
                    'user': 'We are experiencing technical difficulties. Please try again in a few moments.',
                    'admin': 'Database connection failed. Check database service status and connection settings.',
                    'title': 'Database Connection Error',
                    'resolution_steps': [
                        'Check database service status',
                        'Verify connection settings',
                        'Review database logs',
                        'Contact system administrator if issue persists'
                    ]
                },
                'database_query_failed': {
                    'user': 'Unable to process your request. Please try again.',
                    'admin': 'Database query failed. Check query syntax and database schema.',
                    'title': 'Database Query Error',
                    'resolution_steps': [
                        'Review query syntax',
                        'Check database schema',
                        'Verify data integrity',
                        'Check database logs for details'
                    ]
                },
                
                # Authentication errors
                'authentication_failed': {
                    'user': 'Invalid credentials. Please check your email and password.',
                    'admin': 'User authentication failed. Check user credentials and account status.',
                    'title': 'Authentication Failed',
                    'resolution_steps': [
                        'Verify email and password',
                        'Check account status',
                        'Reset password if necessary',
                        'Contact support if issue persists'
                    ]
                },
                'token_expired': {
                    'user': 'Your session has expired. Please log in again.',
                    'admin': 'JWT token has expired. User needs to re-authenticate.',
                    'title': 'Session Expired',
                    'resolution_steps': [
                        'Log in again',
                        'Check token expiration settings',
                        'Clear browser cache if necessary'
                    ]
                },
                'insufficient_permissions': {
                    'user': 'You do not have permission to perform this action.',
                    'admin': 'User lacks required permissions for this operation.',
                    'title': 'Access Denied',
                    'resolution_steps': [
                        'Contact administrator for access',
                        'Review user permissions',
                        'Check role assignments'
                    ]
                },
                
                # External service errors
                'external_service_unavailable': {
                    'user': 'This feature is temporarily unavailable. Please try again later.',
                    'admin': 'External service is unavailable. Check service status and configuration.',
                    'title': 'Service Unavailable',
                    'resolution_steps': [
                        'Check external service status',
                        'Verify API credentials',
                        'Review network connectivity',
                        'Check service documentation for updates'
                    ]
                },
                'api_rate_limit_exceeded': {
                    'user': 'Too many requests. Please wait a moment before trying again.',
                    'admin': 'API rate limit exceeded. Consider implementing request throttling.',
                    'title': 'Rate Limit Exceeded',
                    'resolution_steps': [
                        'Wait before making more requests',
                        'Implement request throttling',
                        'Review API usage patterns',
                        'Consider upgrading service plan'
                    ]
                },
                
                # Configuration errors
                'configuration_missing': {
                    'user': 'This feature is not available due to system configuration.',
                    'admin': 'Required configuration is missing. Check environment variables.',
                    'title': 'Configuration Missing',
                    'resolution_steps': [
                        'Set required environment variables',
                        'Review configuration documentation',
                        'Restart application after configuration changes',
                        'Validate configuration settings'
                    ]
                },
                'configuration_invalid': {
                    'user': 'System configuration error. Please contact support.',
                    'admin': 'Invalid configuration detected. Review and correct settings.',
                    'title': 'Configuration Error',
                    'resolution_steps': [
                        'Review configuration values',
                        'Check configuration format',
                        'Validate against documentation',
                        'Test configuration changes'
                    ]
                },
                
                # Network errors
                'network_timeout': {
                    'user': 'Request timed out. Please check your connection and try again.',
                    'admin': 'Network timeout occurred. Check network connectivity and timeouts.',
                    'title': 'Network Timeout',
                    'resolution_steps': [
                        'Check network connectivity',
                        'Review timeout settings',
                        'Test network performance',
                        'Consider increasing timeout values'
                    ]
                },
                'connection_refused': {
                    'user': 'Unable to connect to the service. Please try again later.',
                    'admin': 'Connection refused. Check service availability and network configuration.',
                    'title': 'Connection Refused',
                    'resolution_steps': [
                        'Check service status',
                        'Verify network configuration',
                        'Review firewall settings',
                        'Test connectivity'
                    ]
                }
            },
            
            'de': {
                # Database errors
                'database_connection_failed': {
                    'user': 'Wir haben technische Schwierigkeiten. Bitte versuchen Sie es in wenigen Augenblicken erneut.',
                    'admin': 'Datenbankverbindung fehlgeschlagen. Überprüfen Sie den Datenbankdienststatus und die Verbindungseinstellungen.',
                    'title': 'Datenbankverbindungsfehler',
                    'resolution_steps': [
                        'Datenbankdienststatus überprüfen',
                        'Verbindungseinstellungen überprüfen',
                        'Datenbankprotokolle überprüfen',
                        'Systemadministrator kontaktieren, falls das Problem weiterhin besteht'
                    ]
                },
                'database_query_failed': {
                    'user': 'Ihre Anfrage kann nicht verarbeitet werden. Bitte versuchen Sie es erneut.',
                    'admin': 'Datenbankabfrage fehlgeschlagen. Überprüfen Sie die Abfragesyntax und das Datenbankschema.',
                    'title': 'Datenbankabfragefehler',
                    'resolution_steps': [
                        'Abfragesyntax überprüfen',
                        'Datenbankschema überprüfen',
                        'Datenintegrität überprüfen',
                        'Datenbankprotokolle für Details überprüfen'
                    ]
                },
                
                # Authentication errors
                'authentication_failed': {
                    'user': 'Ungültige Anmeldedaten. Bitte überprüfen Sie Ihre E-Mail und Ihr Passwort.',
                    'admin': 'Benutzerauthentifizierung fehlgeschlagen. Überprüfen Sie Benutzeranmeldedaten und Kontostatus.',
                    'title': 'Authentifizierung fehlgeschlagen',
                    'resolution_steps': [
                        'E-Mail und Passwort überprüfen',
                        'Kontostatus überprüfen',
                        'Passwort zurücksetzen, falls erforderlich',
                        'Support kontaktieren, falls das Problem weiterhin besteht'
                    ]
                },
                'token_expired': {
                    'user': 'Ihre Sitzung ist abgelaufen. Bitte melden Sie sich erneut an.',
                    'admin': 'JWT-Token ist abgelaufen. Benutzer muss sich erneut authentifizieren.',
                    'title': 'Sitzung abgelaufen',
                    'resolution_steps': [
                        'Erneut anmelden',
                        'Token-Ablaufeinstellungen überprüfen',
                        'Browser-Cache löschen, falls erforderlich'
                    ]
                },
                'insufficient_permissions': {
                    'user': 'Sie haben keine Berechtigung, diese Aktion auszuführen.',
                    'admin': 'Benutzer hat nicht die erforderlichen Berechtigungen für diese Operation.',
                    'title': 'Zugriff verweigert',
                    'resolution_steps': [
                        'Administrator für Zugriff kontaktieren',
                        'Benutzerberechtigungen überprüfen',
                        'Rollenzuweisungen überprüfen'
                    ]
                },
                
                # External service errors
                'external_service_unavailable': {
                    'user': 'Diese Funktion ist vorübergehend nicht verfügbar. Bitte versuchen Sie es später erneut.',
                    'admin': 'Externer Dienst ist nicht verfügbar. Überprüfen Sie Dienststatus und Konfiguration.',
                    'title': 'Dienst nicht verfügbar',
                    'resolution_steps': [
                        'Status des externen Dienstes überprüfen',
                        'API-Anmeldedaten überprüfen',
                        'Netzwerkverbindung überprüfen',
                        'Dienstdokumentation für Updates überprüfen'
                    ]
                },
                'api_rate_limit_exceeded': {
                    'user': 'Zu viele Anfragen. Bitte warten Sie einen Moment, bevor Sie es erneut versuchen.',
                    'admin': 'API-Ratenlimit überschritten. Erwägen Sie die Implementierung einer Anfragedrosselung.',
                    'title': 'Ratenlimit überschritten',
                    'resolution_steps': [
                        'Warten Sie, bevor Sie weitere Anfragen stellen',
                        'Anfragedrosselung implementieren',
                        'API-Nutzungsmuster überprüfen',
                        'Erwägen Sie ein Upgrade des Serviceplans'
                    ]
                }
            },
            
            'uk': {
                # Database errors
                'database_connection_failed': {
                    'user': 'У нас технічні труднощі. Будь ласка, спробуйте ще раз через кілька хвилин.',
                    'admin': 'Не вдалося підключитися до бази даних. Перевірте статус служби бази даних та налаштування підключення.',
                    'title': 'Помилка підключення до бази даних',
                    'resolution_steps': [
                        'Перевірити статус служби бази даних',
                        'Перевірити налаштування підключення',
                        'Переглянути журнали бази даних',
                        'Звернутися до системного адміністратора, якщо проблема не зникає'
                    ]
                },
                'database_query_failed': {
                    'user': 'Не вдається обробити ваш запит. Будь ласка, спробуйте ще раз.',
                    'admin': 'Запит до бази даних не виконано. Перевірте синтаксис запиту та схему бази даних.',
                    'title': 'Помилка запиту до бази даних',
                    'resolution_steps': [
                        'Переглянути синтаксис запиту',
                        'Перевірити схему бази даних',
                        'Перевірити цілісність даних',
                        'Переглянути журнали бази даних для деталей'
                    ]
                },
                
                # Authentication errors
                'authentication_failed': {
                    'user': 'Неправильні облікові дані. Будь ласка, перевірте вашу електронну пошту та пароль.',
                    'admin': 'Автентифікація користувача не вдалася. Перевірте облікові дані користувача та статус облікового запису.',
                    'title': 'Автентифікація не вдалася',
                    'resolution_steps': [
                        'Перевірити електронну пошту та пароль',
                        'Перевірити статус облікового запису',
                        'Скинути пароль, якщо необхідно',
                        'Звернутися до підтримки, якщо проблема не зникає'
                    ]
                },
                'token_expired': {
                    'user': 'Ваша сесія закінчилася. Будь ласка, увійдіть знову.',
                    'admin': 'JWT токен закінчився. Користувач повинен повторно автентифікуватися.',
                    'title': 'Сесія закінчилася',
                    'resolution_steps': [
                        'Увійти знову',
                        'Перевірити налаштування закінчення токена',
                        'Очистити кеш браузера, якщо необхідно'
                    ]
                },
                'insufficient_permissions': {
                    'user': 'У вас немає дозволу на виконання цієї дії.',
                    'admin': 'Користувач не має необхідних дозволів для цієї операції.',
                    'title': 'Доступ заборонено',
                    'resolution_steps': [
                        'Звернутися до адміністратора за доступом',
                        'Переглянути дозволи користувача',
                        'Перевірити призначення ролей'
                    ]
                },
                
                # External service errors
                'external_service_unavailable': {
                    'user': 'Ця функція тимчасово недоступна. Будь ласка, спробуйте пізніше.',
                    'admin': 'Зовнішній сервіс недоступний. Перевірте статус сервісу та конфігурацію.',
                    'title': 'Сервіс недоступний',
                    'resolution_steps': [
                        'Перевірити статус зовнішнього сервісу',
                        'Перевірити облікові дані API',
                        'Переглянути мережеве підключення',
                        'Перевірити документацію сервісу на оновлення'
                    ]
                },
                'api_rate_limit_exceeded': {
                    'user': 'Занадто багато запитів. Будь ласка, зачекайте хвилину перед повторною спробою.',
                    'admin': 'Перевищено ліміт швидкості API. Розгляньте можливість впровадження обмеження запитів.',
                    'title': 'Перевищено ліміт швидкості',
                    'resolution_steps': [
                        'Зачекати перед наступними запитами',
                        'Впровадити обмеження запитів',
                        'Переглянути шаблони використання API',
                        'Розглянути можливість оновлення плану сервісу'
                    ]
                }
            }
        }
    
    def get_current_language(self) -> str:
        """Get current user language with fallback."""
        try:
            # Try to get language from Babel
            if current_app and 'babel' in current_app.extensions:
                from flask_babel import get_locale
                locale = get_locale()
                if locale and str(locale) in self.supported_languages:
                    return str(locale)
            
            # Try to get from request context
            if has_request_context():
                # Check URL parameter
                lang = request.args.get('lang')
                if lang and lang in self.supported_languages:
                    return lang
                
                # Check session
                lang = session.get('language')
                if lang and lang in self.supported_languages:
                    return lang
                
                # Check Accept-Language header
                if request.accept_languages:
                    lang = request.accept_languages.best_match(self.supported_languages)
                    if lang:
                        return lang
            
        except Exception as e:
            logger.warning(f"Failed to detect language: {e}")
        
        return self.default_language
    
    def get_error_message(
        self,
        error_key: str,
        audience: str = 'user',
        language: Optional[str] = None,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Get error message in specified language.
        
        Args:
            error_key: Error message key
            audience: Target audience ('user' or 'admin')
            language: Language code (auto-detected if None)
            context: Additional context for message formatting
            
        Returns:
            Error message data with title, message, and resolution steps
        """
        if language is None:
            language = self.get_current_language()
        
        context = context or {}
        
        # Get message template
        lang_messages = self.error_messages.get(language, self.error_messages[self.default_language])
        message_template = lang_messages.get(error_key)
        
        if not message_template:
            # Fallback to English
            lang_messages = self.error_messages[self.default_language]
            message_template = lang_messages.get(error_key)
        
        if not message_template:
            # Generic fallback
            return self._get_generic_error_message(audience, language)
        
        # Get message for audience
        message = message_template.get(audience, message_template.get('user', ''))
        title = message_template.get('title', 'Error')
        resolution_steps = message_template.get('resolution_steps', [])
        
        # Apply context formatting if needed
        if context and '{' in message:
            try:
                message = message.format(**context)
            except (KeyError, ValueError) as e:
                logger.warning(f"Failed to format error message: {e}")
        
        return {
            'title': title,
            'message': message,
            'resolution_steps': resolution_steps,
            'language': language,
            'error_key': error_key,
            'audience': audience
        }
    
    def _get_generic_error_message(self, audience: str, language: str) -> Dict[str, Any]:
        """Get generic error message when specific message is not available."""
        generic_messages = {
            'en': {
                'user': {
                    'title': 'Error',
                    'message': 'An error occurred. Please try again or contact support.',
                    'resolution_steps': [
                        'Try again',
                        'Refresh the page',
                        'Contact support if issue persists'
                    ]
                },
                'admin': {
                    'title': 'System Error',
                    'message': 'An error occurred. Check logs for details.',
                    'resolution_steps': [
                        'Check application logs',
                        'Review error details',
                        'Identify root cause',
                        'Apply appropriate fix'
                    ]
                }
            },
            'de': {
                'user': {
                    'title': 'Fehler',
                    'message': 'Ein Fehler ist aufgetreten. Bitte versuchen Sie es erneut oder kontaktieren Sie den Support.',
                    'resolution_steps': [
                        'Erneut versuchen',
                        'Seite aktualisieren',
                        'Support kontaktieren, falls das Problem weiterhin besteht'
                    ]
                },
                'admin': {
                    'title': 'Systemfehler',
                    'message': 'Ein Fehler ist aufgetreten. Überprüfen Sie die Protokolle für Details.',
                    'resolution_steps': [
                        'Anwendungsprotokolle überprüfen',
                        'Fehlerdetails überprüfen',
                        'Grundursache identifizieren',
                        'Entsprechende Lösung anwenden'
                    ]
                }
            },
            'uk': {
                'user': {
                    'title': 'Помилка',
                    'message': 'Сталася помилка. Будь ласка, спробуйте ще раз або зверніться до підтримки.',
                    'resolution_steps': [
                        'Спробувати ще раз',
                        'Оновити сторінку',
                        'Звернутися до підтримки, якщо проблема не зникає'
                    ]
                },
                'admin': {
                    'title': 'Системна помилка',
                    'message': 'Сталася помилка. Перевірте журнали для деталей.',
                    'resolution_steps': [
                        'Перевірити журнали додатку',
                        'Переглянути деталі помилки',
                        'Визначити основну причину',
                        'Застосувати відповідне виправлення'
                    ]
                }
            }
        }
        
        lang_generic = generic_messages.get(language, generic_messages['en'])
        audience_generic = lang_generic.get(audience, lang_generic['user'])
        
        return {
            'title': audience_generic['title'],
            'message': audience_generic['message'],
            'resolution_steps': audience_generic['resolution_steps'],
            'language': language,
            'error_key': 'generic_error',
            'audience': audience
        }
    
    def categorize_error_by_exception(self, error: Exception) -> str:
        """Categorize error based on exception type."""
        error_type = type(error).__name__.lower()
        error_message = str(error).lower()
        
        # Database errors
        if any(keyword in error_type for keyword in ['database', 'sql', 'connection']):
            if 'connection' in error_message or 'connect' in error_message:
                return 'database_connection_failed'
            return 'database_query_failed'
        
        # Authentication errors
        if any(keyword in error_type for keyword in ['auth', 'token', 'jwt']):
            if 'expired' in error_message:
                return 'token_expired'
            if 'permission' in error_message or 'forbidden' in error_message:
                return 'insufficient_permissions'
            return 'authentication_failed'
        
        # Network errors
        if any(keyword in error_type for keyword in ['timeout', 'connection', 'network']):
            if 'timeout' in error_message:
                return 'network_timeout'
            if 'refused' in error_message or 'unreachable' in error_message:
                return 'connection_refused'
            return 'external_service_unavailable'
        
        # Configuration errors
        if any(keyword in error_type for keyword in ['config', 'environment', 'setting']):
            if 'missing' in error_message or 'not found' in error_message:
                return 'configuration_missing'
            return 'configuration_invalid'
        
        return 'generic_error'
    
    def create_multilingual_error_response(
        self,
        error: Exception,
        context: Dict[str, Any] = None,
        include_technical_details: bool = None
    ) -> Dict[str, Any]:
        """
        Create multilingual error response.
        
        Args:
            error: The exception that occurred
            context: Additional context information
            include_technical_details: Whether to include technical details
            
        Returns:
            Multilingual error response
        """
        if include_technical_details is None:
            include_technical_details = current_app.config.get('DEBUG', False) if current_app else False
        
        # Categorize the error
        error_key = self.categorize_error_by_exception(error)
        
        # Determine audience
        audience = 'admin' if include_technical_details else 'user'
        
        # Get current language
        language = self.get_current_language()
        
        # Get error message
        error_data = self.get_error_message(
            error_key=error_key,
            audience=audience,
            language=language,
            context=context
        )
        
        response = {
            'title': error_data['title'],
            'user_message': error_data['message'],
            'error_category': error_key,
            'resolution_steps': error_data['resolution_steps'],
            'language': language
        }
        
        # Add technical details if requested
        if include_technical_details:
            response['technical_details'] = {
                'error_type': type(error).__name__,
                'error_message': str(error),
                'context': context or {}
            }
            
            # Add request context if available
            if has_request_context():
                response['technical_details']['request_context'] = {
                    'method': request.method,
                    'path': request.path,
                    'remote_addr': request.remote_addr
                }
        
        return response


# Global instance
_multilingual_error_messages = None


def get_multilingual_error_messages() -> MultilingualErrorMessages:
    """Get or create multilingual error messages instance."""
    global _multilingual_error_messages
    
    if _multilingual_error_messages is None:
        _multilingual_error_messages = MultilingualErrorMessages()
    
    return _multilingual_error_messages


def get_localized_error_message(
    error_key: str,
    audience: str = 'user',
    language: Optional[str] = None,
    context: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Convenience function to get localized error message.
    
    Args:
        error_key: Error message key
        audience: Target audience ('user' or 'admin')
        language: Language code (auto-detected if None)
        context: Additional context for message formatting
        
    Returns:
        Localized error message data
    """
    messages = get_multilingual_error_messages()
    return messages.get_error_message(error_key, audience, language, context)


def create_localized_error_response(
    error: Exception,
    context: Dict[str, Any] = None,
    include_technical_details: bool = None
) -> Dict[str, Any]:
    """
    Convenience function to create localized error response.
    
    Args:
        error: The exception that occurred
        context: Additional context information
        include_technical_details: Whether to include technical details
        
    Returns:
        Localized error response
    """
    messages = get_multilingual_error_messages()
    return messages.create_multilingual_error_response(error, context, include_technical_details)
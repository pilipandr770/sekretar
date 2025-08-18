"""Custom exceptions for the application."""


class BaseAppException(Exception):
    """Base exception for application-specific errors."""
    
    def __init__(self, message: str, error_code: str = None):
        self.message = message
        self.error_code = error_code or self.__class__.__name__.upper()
        super().__init__(self.message)


class ValidationError(BaseAppException):
    """Exception raised for validation errors."""
    pass


class ProcessingError(BaseAppException):
    """Exception raised for processing errors."""
    pass


class AuthenticationError(BaseAppException):
    """Exception raised for authentication errors."""
    pass


class AuthorizationError(BaseAppException):
    """Exception raised for authorization errors."""
    pass


class OAuthError(BaseAppException):
    """Exception raised for OAuth-related errors."""
    pass


class ExternalAPIError(BaseAppException):
    """Exception raised for external API errors."""
    pass


class TenantError(BaseAppException):
    """Exception raised for tenant-related errors."""
    pass


class BillingError(BaseAppException):
    """Exception raised for billing-related errors."""
    pass


class KYBError(BaseAppException):
    """Exception raised for KYB monitoring errors."""
    pass


class RateLimitError(BaseAppException):
    """Exception raised when rate limits are exceeded."""
    pass


class ConfigurationError(BaseAppException):
    """Exception raised for configuration errors."""
    pass


class StripeError(BaseAppException):
    """Exception raised for Stripe integration errors."""
    pass
"""
Environment Configuration Analyzer

This module provides functionality to analyze and parse all .env files
in the project to identify unique variables, categorize them, and determine
critical configuration requirements.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum


class VariableCategory(Enum):
    """Categories for environment variables"""
    CRITICAL = "critical"
    DATABASE = "database"
    EXTERNAL_SERVICES = "external_services"
    AUTHENTICATION = "authentication"
    COMMUNICATION = "communication"
    APPLICATION = "application"
    DEVELOPMENT = "development"
    TESTING = "testing"
    MONITORING = "monitoring"
    SECURITY = "security"


@dataclass
class EnvironmentVariable:
    """Represents an environment variable with its metadata"""
    name: str
    value: str
    category: VariableCategory
    description: str = ""
    is_required: bool = False
    is_secret: bool = False
    default_value: Optional[str] = None
    found_in_files: List[str] = field(default_factory=list)
    example_value: Optional[str] = None


@dataclass
class EnvAnalysisReport:
    """Report containing analysis results of environment files"""
    total_variables: int
    unique_variables: int
    critical_variables: List[str]
    secret_variables: List[str]
    duplicate_variables: Dict[str, List[str]]
    missing_in_example: List[str]
    categories: Dict[VariableCategory, List[str]]
    file_analysis: Dict[str, Dict[str, Any]]


class EnvAnalyzer:
    """Analyzes environment configuration files"""
    
    def __init__(self, project_root: Optional[str] = None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.env_files = [
            ".env",
            ".env.development", 
            ".env.example",
            ".env.local",
            ".env.production",
            ".env.test"
        ]
        self.variables: Dict[str, EnvironmentVariable] = {}
        self.file_contents: Dict[str, Dict[str, str]] = {}
        
        # Patterns for categorizing variables
        self.category_patterns = {
            VariableCategory.CRITICAL: [
                r"SECRET_KEY", r"JWT_SECRET_KEY", r"DATABASE_URL"
            ],
            VariableCategory.DATABASE: [
                r"DATABASE_", r"POSTGRES_", r"SQLITE_", r"DB_", r"REDIS_"
            ],
            VariableCategory.EXTERNAL_SERVICES: [
                r"OPENAI_", r"GEMINI_", r"STRIPE_", r"_API_", r"_URL$"
            ],
            VariableCategory.AUTHENTICATION: [
                r"GOOGLE_CLIENT", r"JWT_", r"OAUTH_", r"AUTH_"
            ],
            VariableCategory.COMMUNICATION: [
                r"TELEGRAM_", r"SIGNAL_", r"SMTP_", r"MAIL_", r"EMAIL_"
            ],
            VariableCategory.APPLICATION: [
                r"APP_", r"FLASK_", r"FRONTEND_", r"UPLOAD_", r"MAX_CONTENT"
            ],
            VariableCategory.DEVELOPMENT: [
                r"DEBUG", r"TEMPLATES_AUTO_RELOAD", r"LOG_LEVEL", r"LOG_FORMAT"
            ],
            VariableCategory.TESTING: [
                r"TEST_", r"TESTING", r"WTF_CSRF_ENABLED"
            ],
            VariableCategory.MONITORING: [
                r"GRAFANA_", r"PROMETHEUS_", r"HEALTH_CHECK", r"SERVICE_DETECTION"
            ],
            VariableCategory.SECURITY: [
                r"CORS_", r"RATE_LIMIT", r"CSRF_", r"SESSION_"
            ]
        }
        
        # Patterns for identifying secret variables
        self.secret_patterns = [
            r".*KEY.*", r".*SECRET.*", r".*PASSWORD.*", r".*TOKEN.*", 
            r".*WEBHOOK.*", r".*CLIENT_SECRET.*"
        ]
        
        # Critical variables that must be present
        self.critical_variables = {
            "SECRET_KEY", "JWT_SECRET_KEY", "DATABASE_URL"
        }

    def parse_env_file(self, file_path: str) -> Dict[str, str]:
        """Parse a single .env file and return key-value pairs"""
        env_vars = {}
        full_path = self.project_root / file_path
        
        if not full_path.exists():
            return env_vars
            
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    
                    # Parse KEY=VALUE format
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # Remove quotes if present
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                            
                        env_vars[key] = value
                        
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            
        return env_vars

    def categorize_variable(self, var_name: str) -> VariableCategory:
        """Categorize a variable based on its name"""
        for category, patterns in self.category_patterns.items():
            for pattern in patterns:
                if re.search(pattern, var_name, re.IGNORECASE):
                    return category
        return VariableCategory.APPLICATION

    def is_secret_variable(self, var_name: str) -> bool:
        """Check if a variable contains sensitive information"""
        for pattern in self.secret_patterns:
            if re.search(pattern, var_name, re.IGNORECASE):
                return True
        return False

    def get_variable_description(self, var_name: str, category: VariableCategory) -> str:
        """Generate description for a variable based on its name and category"""
        descriptions = {
            # Critical variables
            "SECRET_KEY": "Flask secret key for session encryption and security",
            "JWT_SECRET_KEY": "Secret key for JWT token signing and verification",
            "DATABASE_URL": "Primary database connection URL",
            
            # Database variables
            "TEST_DATABASE_URL": "Database URL for testing environment",
            "POSTGRES_USER": "PostgreSQL database username",
            "POSTGRES_PASSWORD": "PostgreSQL database password",
            "POSTGRES_DB": "PostgreSQL database name",
            "REDIS_URL": "Redis server connection URL",
            "SQLITE_DATABASE_URL": "SQLite database file path",
            
            # External services
            "OPENAI_API_KEY": "OpenAI API key for AI services",
            "OPENAI_MODEL": "OpenAI model to use (e.g., gpt-4, gpt-3.5-turbo)",
            "GEMINI_API_KEY": "Google Gemini API key",
            "STRIPE_SECRET_KEY": "Stripe secret key for payment processing",
            "STRIPE_PUBLISHABLE_KEY": "Stripe publishable key for frontend",
            "STRIPE_WEBHOOK_SECRET": "Stripe webhook endpoint secret",
            
            # Authentication
            "GOOGLE_CLIENT_ID": "Google OAuth client ID",
            "GOOGLE_CLIENT_SECRET": "Google OAuth client secret",
            "GOOGLE_REDIRECT_URI": "Google OAuth redirect URI",
            
            # Communication
            "TELEGRAM_BOT_TOKEN": "Telegram bot token for messaging",
            "SIGNAL_PHONE_NUMBER": "Signal phone number for messaging",
            "SMTP_SERVER": "SMTP server for email sending",
            "SMTP_USERNAME": "SMTP username for email authentication",
            "SMTP_PASSWORD": "SMTP password for email authentication",
            
            # Application
            "FLASK_ENV": "Flask environment (development, production, testing)",
            "FLASK_APP": "Flask application entry point",
            "APP_NAME": "Application display name",
            "APP_URL": "Application base URL",
            "FRONTEND_URL": "Frontend application URL",
            "DEFAULT_LANGUAGE": "Default language for internationalization",
            "UPLOAD_FOLDER": "Directory for file uploads",
            "MAX_CONTENT_LENGTH": "Maximum file upload size in bytes",
            
            # Development
            "DEBUG": "Enable debug mode (true/false)",
            "LOG_LEVEL": "Logging level (DEBUG, INFO, WARNING, ERROR)",
            "LOG_FORMAT": "Log format (text, json)",
            
            # Testing
            "TESTING": "Enable testing mode (true/false)",
            "WTF_CSRF_ENABLED": "Enable CSRF protection (true/false)",
        }
        
        if var_name in descriptions:
            return descriptions[var_name]
        
        # Generate generic description based on category
        category_descriptions = {
            VariableCategory.CRITICAL: "Critical system configuration",
            VariableCategory.DATABASE: "Database connection configuration",
            VariableCategory.EXTERNAL_SERVICES: "External service API configuration",
            VariableCategory.AUTHENTICATION: "Authentication and OAuth configuration",
            VariableCategory.COMMUNICATION: "Communication service configuration",
            VariableCategory.APPLICATION: "Application-specific configuration",
            VariableCategory.DEVELOPMENT: "Development environment configuration",
            VariableCategory.TESTING: "Testing environment configuration",
            VariableCategory.MONITORING: "Monitoring and health check configuration",
            VariableCategory.SECURITY: "Security and protection configuration"
        }
        
        return category_descriptions.get(category, "Application configuration variable")

    def get_example_value(self, var_name: str, category: VariableCategory) -> str:
        """Generate example value for a variable"""
        examples = {
            "SECRET_KEY": "your-secret-key-here-change-in-production",
            "JWT_SECRET_KEY": "your-jwt-secret-key-here-change-in-production",
            "DATABASE_URL": "sqlite:///ai_secretary.db",
            "TEST_DATABASE_URL": "sqlite:///test_ai_secretary.db",
            "SQLITE_DATABASE_URL": "sqlite:///ai_secretary.db",
            "OPENAI_API_KEY": "sk-your-openai-api-key-here",
            "OPENAI_MODEL": "gpt-4",
            "GEMINI_API_KEY": "your-gemini-api-key-here",
            "GEMINI_MODEL": "gemini-pro",
            "STRIPE_SECRET_KEY": "sk_test_your-stripe-secret-key",
            "STRIPE_PUBLISHABLE_KEY": "pk_test_your-stripe-publishable-key",
            "STRIPE_WEBHOOK_SECRET": "whsec_your-webhook-secret",
            "GOOGLE_CLIENT_ID": "your-google-client-id.apps.googleusercontent.com",
            "GOOGLE_CLIENT_SECRET": "your-google-client-secret",
            "GOOGLE_REDIRECT_URI": "http://localhost:5000/api/v1/auth/google/callback",
            "GOOGLE_CALENDAR_ID": "your-calendar-id@group.calendar.google.com",
            "GOOGLE_CALENDAR_TIMEZONE": "Europe/Berlin",
            "TELEGRAM_BOT_TOKEN": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
            "TELEGRAM_WEBHOOK_URL": "https://your-domain.com/api/v1/channels/telegram/webhook",
            "SIGNAL_CLI_PATH": "signal-cli",
            "SIGNAL_PHONE_NUMBER": "+1234567890",
            "SMTP_SERVER": "smtp.gmail.com",
            "SMTP_PORT": "587",
            "SMTP_USERNAME": "your-email@gmail.com",
            "SMTP_PASSWORD": "your-app-password",
            "FLASK_ENV": "development",
            "FLASK_APP": "app",
            "APP_NAME": "AI Secretary",
            "APP_URL": "http://localhost:5000",
            "FRONTEND_URL": "http://localhost:3000",
            "DEFAULT_LANGUAGE": "en",
            "UPLOAD_FOLDER": "uploads",
            "MAX_CONTENT_LENGTH": "16777216",
            "LOG_LEVEL": "DEBUG",
            "LOG_FORMAT": "text",
            "DEBUG": "true",
            "TESTING": "false",
            "REDIS_URL": "redis://localhost:6379/0",
            "CELERY_BROKER_URL": "redis://localhost:6379/1",
            "CELERY_RESULT_BACKEND": "redis://localhost:6379/2",
            "CACHE_TYPE": "simple",
            "DATABASE_AUTO_CREATE": "true",
            "DATABASE_AUTO_MIGRATE": "true",
            "DATABASE_AUTO_SEED": "false",
            "SQLITE_TIMEOUT": "20",
            "SQLITE_CHECK_SAME_THREAD": "false",
            "SERVICE_DETECTION_ENABLED": "true",
            "DATABASE_DETECTION_ENABLED": "true",
            "CACHE_DETECTION_ENABLED": "true",
            "EXTERNAL_SERVICE_DETECTION_ENABLED": "true",
            "CONFIG_VALIDATION_ENABLED": "true",
            "JWT_COOKIE_SECURE": "false",
            "JWT_COOKIE_CSRF_PROTECT": "false",
            "WTF_CSRF_ENABLED": "false"
        }
        
        if var_name in examples:
            return examples[var_name]
        
        # Generate generic examples based on patterns
        if var_name.endswith("_URL") or var_name.startswith("URL_"):
            if "WEBHOOK" in var_name:
                return "https://your-domain.com/webhook"
            elif "API" in var_name:
                return "https://api.example.com"
            elif "REDIRECT" in var_name:
                return "http://localhost:5000/callback"
            else:
                return "https://example.com"
        elif var_name.endswith("_PORT") or var_name == "PORT":
            return "5000"
        elif "TIMEOUT" in var_name:
            return "30"
        elif var_name.endswith("_ENABLED") or "ENABLED" in var_name:
            return "true"
        elif "PASSWORD" in var_name or "SECRET" in var_name or var_name.endswith("_KEY"):
            return "your-secret-value-here"
        elif "EMAIL" in var_name or var_name.endswith("_EMAIL"):
            return "your-email@example.com"
        elif "PHONE" in var_name or var_name.endswith("_PHONE"):
            return "+1234567890"
        elif "SIZE" in var_name or "LENGTH" in var_name:
            return "16777216"
        elif "POOL" in var_name:
            return "5"
        elif "OVERFLOW" in var_name:
            return "10"
        elif var_name.endswith("_ID"):
            return "your-id-here"
        elif var_name.endswith("_NAME"):
            return "AI Secretary"
        elif var_name.endswith("_PATH"):
            return "/path/to/resource"
        elif var_name.endswith("_FOLDER"):
            return "uploads"
        else:
            return "your-value-here"

    def analyze_all_files(self) -> EnvAnalysisReport:
        """Analyze all environment files and generate comprehensive report"""
        # Parse all files
        for file_name in self.env_files:
            self.file_contents[file_name] = self.parse_env_file(file_name)
        
        # Collect all unique variables
        all_variables = set()
        for file_vars in self.file_contents.values():
            all_variables.update(file_vars.keys())
        
        # Analyze each variable
        for var_name in all_variables:
            category = self.categorize_variable(var_name)
            is_secret = self.is_secret_variable(var_name)
            is_required = var_name in self.critical_variables
            description = self.get_variable_description(var_name, category)
            example_value = self.get_example_value(var_name, category)
            
            # Find which files contain this variable
            found_in_files = []
            sample_value = ""
            for file_name, file_vars in self.file_contents.items():
                if var_name in file_vars:
                    found_in_files.append(file_name)
                    if not sample_value and file_vars[var_name]:
                        sample_value = file_vars[var_name]
            
            self.variables[var_name] = EnvironmentVariable(
                name=var_name,
                value=sample_value,
                category=category,
                description=description,
                is_required=is_required,
                is_secret=is_secret,
                example_value=example_value,
                found_in_files=found_in_files
            )
        
        # Generate analysis report
        return self._generate_report()

    def _generate_report(self) -> EnvAnalysisReport:
        """Generate comprehensive analysis report"""
        total_vars = sum(len(vars) for vars in self.file_contents.values())
        unique_vars = len(self.variables)
        
        critical_vars = [name for name, var in self.variables.items() if var.is_required]
        secret_vars = [name for name, var in self.variables.items() if var.is_secret]
        
        # Find duplicates
        duplicates = {}
        for var_name, var in self.variables.items():
            if len(var.found_in_files) > 1:
                duplicates[var_name] = var.found_in_files
        
        # Find variables missing in .env.example
        example_vars = set(self.file_contents.get(".env.example", {}).keys())
        missing_in_example = [name for name in self.variables.keys() 
                            if name not in example_vars and not name.startswith("TEST_")]
        
        # Categorize variables
        categories = {}
        for category in VariableCategory:
            categories[category] = [
                name for name, var in self.variables.items() 
                if var.category == category
            ]
        
        # File analysis
        file_analysis = {}
        for file_name, file_vars in self.file_contents.items():
            file_analysis[file_name] = {
                "variable_count": len(file_vars),
                "has_secrets": any(self.is_secret_variable(var) for var in file_vars.keys()),
                "missing_critical": [var for var in self.critical_variables 
                                   if var not in file_vars],
                "unique_variables": [var for var in file_vars.keys() 
                                   if len(self.variables[var].found_in_files) == 1]
            }
        
        return EnvAnalysisReport(
            total_variables=total_vars,
            unique_variables=unique_vars,
            critical_variables=critical_vars,
            secret_variables=secret_vars,
            duplicate_variables=duplicates,
            missing_in_example=missing_in_example,
            categories=categories,
            file_analysis=file_analysis
        )

    def get_critical_variables(self) -> List[EnvironmentVariable]:
        """Get list of critical variables that must be configured"""
        return [var for var in self.variables.values() if var.is_required]

    def get_variables_by_category(self, category: VariableCategory) -> List[EnvironmentVariable]:
        """Get variables filtered by category"""
        return [var for var in self.variables.values() if var.category == category]

    def print_analysis_summary(self, report: EnvAnalysisReport) -> None:
        """Print a summary of the analysis results"""
        print("=== Environment Configuration Analysis ===")
        print(f"Total variables found: {report.total_variables}")
        print(f"Unique variables: {report.unique_variables}")
        print(f"Critical variables: {len(report.critical_variables)}")
        print(f"Secret variables: {len(report.secret_variables)}")
        print(f"Variables with duplicates: {len(report.duplicate_variables)}")
        print(f"Missing in .env.example: {len(report.missing_in_example)}")
        
        print("\n=== File Analysis ===")
        for file_name, analysis in report.file_analysis.items():
            print(f"{file_name}: {analysis['variable_count']} variables")
            if analysis['missing_critical']:
                print(f"  Missing critical: {', '.join(analysis['missing_critical'])}")
        
        print("\n=== Category Distribution ===")
        for category, variables in report.categories.items():
            if variables:
                print(f"{category.value}: {len(variables)} variables")


if __name__ == "__main__":
    # Example usage
    analyzer = EnvAnalyzer()
    report = analyzer.analyze_all_files()
    analyzer.print_analysis_summary(report)
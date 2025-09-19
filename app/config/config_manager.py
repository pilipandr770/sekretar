"""
Configuration Manager

This module provides functionality to manage environment configuration,
unify .env files, generate documentation, and validate configurations
for different environments.
"""

import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

from .env_analyzer import EnvAnalyzer, EnvironmentVariable, VariableCategory, EnvAnalysisReport


@dataclass
class ConfigValidationResult:
    """Result of configuration validation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    missing_required: List[str]
    invalid_values: List[str]
    recommendations: List[str]


@dataclass
class ConfigUnificationResult:
    """Result of configuration unification process"""
    created_files: List[str]
    removed_files: List[str]
    unified_variables: Dict[str, str]
    backup_location: Optional[str]
    warnings: List[str]
    errors: List[str]


class ConfigManager:
    """Manages environment configuration unification and validation"""
    
    def __init__(self, project_root: Optional[str] = None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.analyzer = EnvAnalyzer(str(self.project_root))
        self.backup_dir = self.project_root / ".config_backup"
        
        # Files to keep after unification
        self.keep_files = {".env.example", ".env"}
        
        # Files to remove after unification
        self.remove_files = {
            ".env.development", 
            ".env.local", 
            ".env.production", 
            ".env.test"
        }

    def create_backup(self) -> str:
        """Create backup of existing configuration files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"config_backup_{timestamp}"
        backup_path.mkdir(parents=True, exist_ok=True)
        
        # Backup all .env files
        for env_file in self.analyzer.env_files:
            source_path = self.project_root / env_file
            if source_path.exists():
                dest_path = backup_path / env_file
                shutil.copy2(source_path, dest_path)
                print(f"Backed up {env_file} to {dest_path}")
        
        return str(backup_path)

    def analyze_configurations(self) -> EnvAnalysisReport:
        """Analyze all existing configuration files"""
        return self.analyzer.analyze_all_files()

    def generate_env_example(self, report: EnvAnalysisReport) -> str:
        """Generate comprehensive .env.example file with documentation"""
        content = []
        
        # Header
        content.append("# AI Secretary Environment Configuration")
        content.append("# Copy this file to .env and fill in your actual values")
        content.append("# DO NOT commit .env file to version control")
        content.append("")
        content.append("# Last updated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        content.append("")
        
        # Group variables by category
        category_order = [
            VariableCategory.CRITICAL,
            VariableCategory.DATABASE,
            VariableCategory.AUTHENTICATION,
            VariableCategory.EXTERNAL_SERVICES,
            VariableCategory.COMMUNICATION,
            VariableCategory.APPLICATION,
            VariableCategory.SECURITY,
            VariableCategory.MONITORING,
            VariableCategory.DEVELOPMENT,
            VariableCategory.TESTING
        ]
        
        category_headers = {
            VariableCategory.CRITICAL: "CRITICAL CONFIGURATION",
            VariableCategory.DATABASE: "DATABASE CONFIGURATION", 
            VariableCategory.AUTHENTICATION: "AUTHENTICATION & OAUTH",
            VariableCategory.EXTERNAL_SERVICES: "EXTERNAL SERVICES & APIs",
            VariableCategory.COMMUNICATION: "COMMUNICATION SERVICES",
            VariableCategory.APPLICATION: "APPLICATION SETTINGS",
            VariableCategory.SECURITY: "SECURITY CONFIGURATION",
            VariableCategory.MONITORING: "MONITORING & HEALTH CHECKS",
            VariableCategory.DEVELOPMENT: "DEVELOPMENT SETTINGS",
            VariableCategory.TESTING: "TESTING CONFIGURATION"
        }
        
        for category in category_order:
            variables = self.analyzer.get_variables_by_category(category)
            if not variables:
                continue
                
            # Category header
            header = category_headers.get(category, category.value.upper())
            content.append(f"# === {header} ===")
            content.append("")
            
            # Sort variables by importance (required first)
            variables.sort(key=lambda v: (not v.is_required, v.name))
            
            for var in variables:
                # Add description as comment
                if var.description:
                    content.append(f"# {var.description}")
                
                # Add requirement status
                if var.is_required:
                    content.append("# REQUIRED: This variable must be set")
                else:
                    content.append("# OPTIONAL: This variable has fallback behavior")
                
                # Add security warning for secrets
                if var.is_secret:
                    content.append("# WARNING: This is a secret value - keep it secure!")
                
                # Add the variable with example value
                example_val = var.example_value or "your-value-here"
                if var.is_secret and not var.is_required:
                    content.append(f"# {var.name}={example_val}")
                else:
                    content.append(f"{var.name}={example_val}")
                
                content.append("")
            
            content.append("")
        
        # Add footer with instructions
        content.extend([
            "# === CONFIGURATION NOTES ===",
            "#",
            "# For local development:",
            "# 1. Copy this file to .env",
            "# 2. Fill in the required values (marked as REQUIRED above)",
            "# 3. Optional values can be left empty for fallback behavior",
            "#",
            "# For production deployment:",
            "# 1. Set all required variables in your hosting platform",
            "# 2. Use strong, unique values for all secrets",
            "# 3. Enable all security features",
            "#",
            "# For more information, see the documentation at:",
            "# https://github.com/your-repo/ai-secretary/blob/main/docs/CONFIGURATION.md",
            ""
        ])
        
        return "\n".join(content)

    def generate_development_env(self, report: EnvAnalysisReport) -> str:
        """Generate .env file for local development with safe defaults"""
        content = []
        
        # Header
        content.extend([
            "# AI Secretary - Local Development Configuration",
            "# This file contains safe defaults for local development",
            "# Generated automatically - modify as needed",
            "",
            f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ""
        ])
        
        # Critical variables with development defaults
        content.extend([
            "# === CRITICAL CONFIGURATION ===",
            "SECRET_KEY=dev-secret-key-change-in-production-" + os.urandom(16).hex(),
            "JWT_SECRET_KEY=dev-jwt-secret-" + os.urandom(16).hex(),
            ""
        ])
        
        # Database configuration - SQLite for development
        content.extend([
            "# === DATABASE CONFIGURATION ===",
            "# Using SQLite for local development",
            "DATABASE_URL=sqlite:///ai_secretary.db",
            "TEST_DATABASE_URL=sqlite:///test_ai_secretary.db",
            "",
            "# SQLite specific settings",
            "SQLITE_TIMEOUT=20",
            "SQLITE_CHECK_SAME_THREAD=false",
            ""
        ])
        
        # Application settings
        content.extend([
            "# === APPLICATION SETTINGS ===",
            "FLASK_ENV=development",
            "FLASK_APP=app",
            "DEBUG=true",
            "",
            "APP_NAME=AI Secretary (Development)",
            "APP_URL=http://localhost:5000",
            "FRONTEND_URL=http://localhost:3000",
            "",
            "DEFAULT_LANGUAGE=en",
            "UPLOAD_FOLDER=uploads",
            "MAX_CONTENT_LENGTH=16777216",
            ""
        ])
        
        # Development settings
        content.extend([
            "# === DEVELOPMENT SETTINGS ===",
            "LOG_LEVEL=DEBUG",
            "LOG_FORMAT=text",
            "TEMPLATES_AUTO_RELOAD=true",
            "",
            "# Service detection (enabled for development)",
            "SERVICE_DETECTION_ENABLED=true",
            "DATABASE_DETECTION_ENABLED=true",
            "CACHE_DETECTION_ENABLED=true",
            ""
        ])
        
        # Cache configuration - simple fallback
        content.extend([
            "# === CACHE CONFIGURATION ===",
            "# Using simple cache for development (no Redis required)",
            "CACHE_TYPE=simple",
            "REDIS_URL=",
            "CELERY_BROKER_URL=",
            "CELERY_RESULT_BACKEND=",
            ""
        ])
        
        # External services - disabled by default
        content.extend([
            "# === EXTERNAL SERVICES ===",
            "# Add your API keys here when needed",
            "# OPENAI_API_KEY=your-openai-key-here",
            "# GEMINI_API_KEY=your-gemini-key-here",
            "# STRIPE_SECRET_KEY=sk_test_your-stripe-key",
            "# TELEGRAM_BOT_TOKEN=your-telegram-token",
            "",
            "# OAuth configuration (optional for development)",
            "# GOOGLE_CLIENT_ID=your-google-client-id",
            "# GOOGLE_CLIENT_SECRET=your-google-client-secret",
            "GOOGLE_REDIRECT_URI=http://localhost:5000/api/v1/auth/google/callback",
            ""
        ])
        
        # Security settings for development
        content.extend([
            "# === SECURITY SETTINGS ===",
            "# Relaxed security for development",
            "JWT_COOKIE_SECURE=false",
            "JWT_COOKIE_CSRF_PROTECT=false",
            "WTF_CSRF_ENABLED=false",
            ""
        ])
        
        return "\n".join(content)

    def validate_configuration(self, env_file: str = ".env") -> ConfigValidationResult:
        """Validate configuration file for completeness and correctness"""
        errors = []
        warnings = []
        missing_required = []
        invalid_values = []
        recommendations = []
        
        env_path = self.project_root / env_file
        if not env_path.exists():
            errors.append(f"Configuration file {env_file} does not exist")
            return ConfigValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                missing_required=missing_required,
                invalid_values=invalid_values,
                recommendations=recommendations
            )
        
        # Parse the configuration file
        env_vars = self.analyzer.parse_env_file(env_file)
        
        # Check for required variables
        critical_vars = self.analyzer.get_critical_variables()
        for var in critical_vars:
            if var.name not in env_vars or not env_vars[var.name]:
                missing_required.append(var.name)
        
        # Validate specific configurations
        self._validate_database_config(env_vars, errors, warnings, recommendations)
        self._validate_security_config(env_vars, errors, warnings, recommendations)
        self._validate_external_services(env_vars, warnings, recommendations)
        
        # Check for development secrets in production
        if env_vars.get("FLASK_ENV") == "production":
            self._validate_production_config(env_vars, errors, warnings)
        
        is_valid = len(errors) == 0 and len(missing_required) == 0
        
        return ConfigValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            missing_required=missing_required,
            invalid_values=invalid_values,
            recommendations=recommendations
        )

    def _validate_database_config(self, env_vars: Dict[str, str], 
                                errors: List[str], warnings: List[str], 
                                recommendations: List[str]) -> None:
        """Validate database configuration"""
        database_url = env_vars.get("DATABASE_URL", "")
        
        if not database_url:
            errors.append("DATABASE_URL is required")
            return
        
        if database_url.startswith("sqlite:"):
            recommendations.append("Consider using PostgreSQL for production")
        elif database_url.startswith("postgresql:"):
            if "localhost" in database_url:
                warnings.append("Database URL points to localhost - ensure this is correct for your environment")

    def _validate_security_config(self, env_vars: Dict[str, str],
                                errors: List[str], warnings: List[str],
                                recommendations: List[str]) -> None:
        """Validate security configuration"""
        secret_key = env_vars.get("SECRET_KEY", "")
        jwt_secret = env_vars.get("JWT_SECRET_KEY", "")
        
        if not secret_key:
            errors.append("SECRET_KEY is required")
        elif len(secret_key) < 32:
            warnings.append("SECRET_KEY should be at least 32 characters long")
        elif "dev-secret" in secret_key or "change" in secret_key.lower():
            warnings.append("SECRET_KEY appears to be a development/example value")
        
        if not jwt_secret:
            errors.append("JWT_SECRET_KEY is required")
        elif len(jwt_secret) < 32:
            warnings.append("JWT_SECRET_KEY should be at least 32 characters long")
        elif "dev-jwt" in jwt_secret or "change" in jwt_secret.lower():
            warnings.append("JWT_SECRET_KEY appears to be a development/example value")

    def _validate_external_services(self, env_vars: Dict[str, str],
                                  warnings: List[str], recommendations: List[str]) -> None:
        """Validate external service configurations"""
        # Check for placeholder values
        placeholder_patterns = ["your-", "change-", "example", "test-key"]
        
        for key, value in env_vars.items():
            if any(pattern in value.lower() for pattern in placeholder_patterns):
                if "API_KEY" in key or "SECRET" in key or "TOKEN" in key:
                    warnings.append(f"{key} appears to contain a placeholder value")
        
        # Check for missing but recommended services
        if not env_vars.get("OPENAI_API_KEY"):
            recommendations.append("Consider setting up OpenAI API key for AI features")
        
        if not env_vars.get("REDIS_URL"):
            recommendations.append("Consider setting up Redis for better performance")

    def _validate_production_config(self, env_vars: Dict[str, str],
                                  errors: List[str], warnings: List[str]) -> None:
        """Validate production-specific configuration"""
        if env_vars.get("DEBUG", "").lower() == "true":
            errors.append("DEBUG should be false in production")
        
        if env_vars.get("JWT_COOKIE_SECURE", "").lower() != "true":
            warnings.append("JWT_COOKIE_SECURE should be true in production")
        
        if env_vars.get("WTF_CSRF_ENABLED", "").lower() != "true":
            warnings.append("WTF_CSRF_ENABLED should be true in production")

    def unify_configurations(self) -> ConfigUnificationResult:
        """Unify all configuration files into .env.example and .env"""
        created_files = []
        removed_files = []
        warnings = []
        errors = []
        
        try:
            # Create backup
            backup_location = self.create_backup()
            
            # Analyze existing configurations
            report = self.analyze_configurations()
            
            # Generate new .env.example
            env_example_content = self.generate_env_example(report)
            env_example_path = self.project_root / ".env.example"
            
            with open(env_example_path, 'w', encoding='utf-8') as f:
                f.write(env_example_content)
            created_files.append(".env.example")
            
            # Generate development .env if it doesn't exist
            env_path = self.project_root / ".env"
            if not env_path.exists():
                env_content = self.generate_development_env(report)
                with open(env_path, 'w', encoding='utf-8') as f:
                    f.write(env_content)
                created_files.append(".env")
            else:
                warnings.append(".env already exists - not overwriting")
            
            # Remove duplicate .env files
            for file_name in self.remove_files:
                file_path = self.project_root / file_name
                if file_path.exists():
                    file_path.unlink()
                    removed_files.append(file_name)
            
            # Extract unified variables
            unified_variables = {}
            for var_name, var in self.analyzer.variables.items():
                unified_variables[var_name] = var.example_value or ""
            
            return ConfigUnificationResult(
                created_files=created_files,
                removed_files=removed_files,
                unified_variables=unified_variables,
                backup_location=backup_location,
                warnings=warnings,
                errors=errors
            )
            
        except Exception as e:
            errors.append(f"Error during unification: {str(e)}")
            return ConfigUnificationResult(
                created_files=created_files,
                removed_files=removed_files,
                unified_variables={},
                backup_location=None,
                warnings=warnings,
                errors=errors
            )

    def print_validation_report(self, result: ConfigValidationResult) -> None:
        """Print configuration validation report"""
        print("=== Configuration Validation Report ===")
        print(f"Status: {'✅ VALID' if result.is_valid else '❌ INVALID'}")
        print()
        
        if result.errors:
            print("🚨 ERRORS:")
            for error in result.errors:
                print(f"  - {error}")
            print()
        
        if result.missing_required:
            print("⚠️  MISSING REQUIRED:")
            for missing in result.missing_required:
                print(f"  - {missing}")
            print()
        
        if result.warnings:
            print("⚠️  WARNINGS:")
            for warning in result.warnings:
                print(f"  - {warning}")
            print()
        
        if result.recommendations:
            print("💡 RECOMMENDATIONS:")
            for rec in result.recommendations:
                print(f"  - {rec}")
            print()

    def print_unification_report(self, result: ConfigUnificationResult) -> None:
        """Print configuration unification report"""
        print("=== Configuration Unification Report ===")
        print()
        
        if result.created_files:
            print("✅ CREATED FILES:")
            for file in result.created_files:
                print(f"  - {file}")
            print()
        
        if result.removed_files:
            print("🗑️  REMOVED FILES:")
            for file in result.removed_files:
                print(f"  - {file}")
            print()
        
        if result.backup_location:
            print(f"💾 BACKUP LOCATION: {result.backup_location}")
            print()
        
        if result.warnings:
            print("⚠️  WARNINGS:")
            for warning in result.warnings:
                print(f"  - {warning}")
            print()
        
        if result.errors:
            print("🚨 ERRORS:")
            for error in result.errors:
                print(f"  - {error}")
            print()
        
        print(f"📊 UNIFIED VARIABLES: {len(result.unified_variables)}")


if __name__ == "__main__":
    # Example usage
    manager = ConfigManager()
    
    # Analyze current configuration
    print("Analyzing current configuration...")
    report = manager.analyze_configurations()
    manager.analyzer.print_analysis_summary(report)
    
    # Validate current .env
    print("\nValidating current configuration...")
    validation = manager.validate_configuration()
    manager.print_validation_report(validation)
    
    # Unify configurations
    print("\nUnifying configurations...")
    unification = manager.unify_configurations()
    manager.print_unification_report(unification)
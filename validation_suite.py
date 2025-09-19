#!/usr/bin/env python3
"""
Comprehensive Validation Suite for AI Secretary Project
Implements task 8.1: Комплексная валидация проекта

This suite runs all created validators and performs comprehensive project validation
to ensure the application is ready for deployment.
"""

import os
import sys
import json
import time
import logging
import subprocess
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

# Add app directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.utils.config_validator import ConfigValidator, ValidationReport
from app.utils.health_validator import HealthValidator
from app.utils.route_validator import RouteValidator
from gitignore_validator import GitignoreValidator


@dataclass
class ValidationSuiteResult:
    """Comprehensive validation result."""
    success: bool
    timestamp: datetime = field(default_factory=datetime.now)
    config_validation: Optional[ValidationReport] = None
    health_validation: Optional[Dict[str, Any]] = None
    route_validation: Optional[Dict[str, Any]] = None
    gitignore_validation: Optional[Dict[str, Any]] = None
    startup_test: Optional[Dict[str, Any]] = None
    api_endpoints_test: Optional[Dict[str, Any]] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    duration: float = 0.0


class ValidationSuite:
    """
    Comprehensive validation suite for project readiness.
    
    Runs all validators and performs integration tests to ensure
    the application is ready for deployment.
    """
    
    def __init__(self, config_file: str = ".env"):
        self.config_file = config_file
        self.logger = self._setup_logging()
        self.result = ValidationSuiteResult(success=True)
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for validation suite."""
        logger = logging.getLogger('validation_suite')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
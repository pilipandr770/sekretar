#!/usr/bin/env python3
"""
Wrapper for the comprehensive test dataset CLI tool.
"""
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run the CLI
from tests.infrastructure.dataset_cli import main

if __name__ == '__main__':
    sys.exit(main())
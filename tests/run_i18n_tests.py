"""
Test runner for comprehensive i18n functionality tests.
Runs all i18n tests and generates a comprehensive report.
"""
import pytest
import sys
import os
import json
import time
from datetime import datetime
from pathlib import Path


def run_i18n_test_suite():
    """Run the complete i18n test suite and generate report."""
    
    print("🌍 Starting Comprehensive i18n Test Suite")
    print("=" * 60)
    
    # Test files to run
    test_files = [
        'tests/test_i18n_comprehensive_suite.py',
        'tests/test_i18n_integration_end_to_end.py', 
        'tests/test_i18n_frontend_javascript.py',
        'tests/test_i18n_translation_quality.py'
    ]
    
    # Check if test files exist
    missing_files = []
    for test_file in test_files:
        if not os.path.exists(test_file):
            missing_files.append(test_file)
    
    if missing_files:
        print(f"❌ Missing test files: {missing_files}")
        return False
    
    # Run tests with detailed output
    start_time = time.time()
    
    # Configure pytest arguments
    pytest_args = [
        '-v',  # verbose output
        '--tb=short',  # short traceback format
        '--strict-markers',  # strict marker checking
        '--disable-warnings',  # disable warnings for cleaner output
        '--color=yes',  # colored output
        '--durations=10',  # show 10 slowest tests
        '--junitxml=tests/i18n_test_results.xml',  # JUnit XML output
        '--html=tests/i18n_test_report.html',  # HTML report (if pytest-html is available)
        '--self-contained-html',  # self-contained HTML report
    ]
    
    # Add test files
    pytest_args.extend(test_files)
    
    print("Running tests with pytest...")
    print(f"Command: pytest {' '.join(pytest_args)}")
    print("-" * 60)
    
    # Run pytest
    exit_code = pytest.main(pytest_args)
    
    end_time = time.time()
    duration = end_time - start_time
    
    print("-" * 60)
    print(f"⏱️  Test execution completed in {duration:.2f} seconds")
    
    # Generate summary report
    generate_test_summary(exit_code, duration, test_files)
    
    return exit_code == 0


def generate_test_summary(exit_code, duration, test_files):
    """Generate a summary report of the test execution."""
    
    timestamp = datetime.now().isoformat()
    
    summary = {
        'timestamp': timestamp,
        'duration_seconds': round(duration, 2),
        'exit_code': exit_code,
        'success': exit_code == 0,
        'test_files': test_files,
        'test_categories': {
            'unit_tests': 'Language detection, translation services, localization formatting',
            'integration_tests': 'End-to-end language switching, API integration, database integration',
            'frontend_tests': 'JavaScript i18n client, browser-based language switching',
            'quality_tests': 'Translation completeness, consistency, validation'
        },
        'coverage_areas': [
            'Language Detection Service',
            'Translation Management Service', 
            'Localization Formatting Service',
            'Email Localization Service',
            'JavaScript i18n Client',
            'API Endpoints Integration',
            'Template Integration',
            'Session Management',
            'Database Integration',
            'Translation File Validation',
            'Translation Quality Assurance',
            'Error Handling and Fallbacks',
            'Performance and Caching'
        ]
    }
    
    # Write summary to file
    summary_file = 'tests/i18n_test_summary.json'
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print("\n📊 Test Summary Report")
    print("=" * 60)
    print(f"Timestamp: {timestamp}")
    print(f"Duration: {duration:.2f} seconds")
    print(f"Exit Code: {exit_code}")
    print(f"Success: {'✅ PASSED' if exit_code == 0 else '❌ FAILED'}")
    print(f"Test Files: {len(test_files)}")
    
    print("\n🧪 Test Categories:")
    for category, description in summary['test_categories'].items():
        print(f"  • {category}: {description}")
    
    print(f"\n📄 Detailed reports saved to:")
    print(f"  • Summary: {summary_file}")
    print(f"  • JUnit XML: tests/i18n_test_results.xml")
    print(f"  • HTML Report: tests/i18n_test_report.html (if pytest-html available)")
    
    if exit_code == 0:
        print("\n🎉 All i18n tests passed successfully!")
        print("The i18n implementation meets all requirements:")
        print("  ✅ Language detection and switching")
        print("  ✅ Translation services and utilities")
        print("  ✅ Localization formatting")
        print("  ✅ Frontend JavaScript integration")
        print("  ✅ API endpoint integration")
        print("  ✅ Template and UI integration")
        print("  ✅ Translation quality and completeness")
        print("  ✅ Error handling and fallbacks")
    else:
        print("\n⚠️  Some tests failed. Please review the detailed output above.")
        print("Common issues to check:")
        print("  • Missing translation files")
        print("  • API endpoints not implemented")
        print("  • Database schema issues")
        print("  • JavaScript dependencies")
        print("  • Template integration")


def run_specific_test_category(category):
    """Run tests for a specific category."""
    
    category_files = {
        'unit': ['tests/test_i18n_comprehensive_suite.py'],
        'integration': ['tests/test_i18n_integration_end_to_end.py'],
        'frontend': ['tests/test_i18n_frontend_javascript.py'],
        'quality': ['tests/test_i18n_translation_quality.py']
    }
    
    if category not in category_files:
        print(f"❌ Unknown test category: {category}")
        print(f"Available categories: {list(category_files.keys())}")
        return False
    
    test_files = category_files[category]
    
    print(f"🧪 Running {category} tests")
    print("=" * 40)
    
    pytest_args = ['-v', '--tb=short'] + test_files
    exit_code = pytest.main(pytest_args)
    
    print(f"\n{category.title()} tests: {'✅ PASSED' if exit_code == 0 else '❌ FAILED'}")
    return exit_code == 0


def main():
    """Main entry point for the test runner."""
    
    if len(sys.argv) > 1:
        category = sys.argv[1]
        success = run_specific_test_category(category)
    else:
        success = run_i18n_test_suite()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
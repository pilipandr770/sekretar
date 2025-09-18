#!/bin/bash

# Comprehensive i18n Test Suite Runner
# This script runs all i18n tests and generates reports

set -e  # Exit on any error

echo "🌍 AI Secretary - Comprehensive i18n Test Suite"
echo "=============================================="

# Check if we're in the right directory
if [ ! -f "app/__init__.py" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    exit 1
fi

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Warning: No virtual environment detected"
    echo "   Consider activating your virtual environment first"
    echo "   Example: source venv/bin/activate"
    echo ""
fi

# Install test dependencies if needed
echo "📦 Checking test dependencies..."
pip install -q pytest pytest-html pytest-cov pytest-mock selenium beautifulsoup4 || {
    echo "⚠️  Some test dependencies could not be installed"
    echo "   Tests will run with available dependencies"
}

# Create test results directory
mkdir -p tests/results

# Set environment variables for testing
export TESTING=true
export FLASK_ENV=testing
export DATABASE_URL=sqlite:///:memory:
export SECRET_KEY=test-secret-key-for-i18n-tests
export WTF_CSRF_ENABLED=false

echo ""
echo "🧪 Running i18n Test Suite..."
echo "------------------------------"

# Run the test suite
python tests/run_i18n_tests.py

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 All i18n tests completed successfully!"
    echo ""
    echo "📊 Test Results Summary:"
    echo "  ✅ Language Detection Service: Tested"
    echo "  ✅ Translation Management: Tested"
    echo "  ✅ Localization Formatting: Tested"
    echo "  ✅ Email Localization: Tested"
    echo "  ✅ Frontend JavaScript i18n: Tested"
    echo "  ✅ API Integration: Tested"
    echo "  ✅ End-to-End Workflows: Tested"
    echo "  ✅ Translation Quality: Tested"
    echo ""
    echo "📄 Reports generated:"
    echo "  • tests/i18n_test_summary.json"
    echo "  • tests/i18n_test_results.xml"
    echo "  • tests/i18n_test_report.html (if available)"
    echo ""
    echo "✨ The i18n implementation is ready for production!"
else
    echo ""
    echo "❌ Some tests failed. Please review the output above."
    echo ""
    echo "🔍 Common troubleshooting steps:"
    echo "  1. Check that all required dependencies are installed"
    echo "  2. Ensure database is properly configured"
    echo "  3. Verify that translation files exist"
    echo "  4. Check that API endpoints are implemented"
    echo "  5. Ensure Selenium WebDriver is available for frontend tests"
    echo ""
    exit 1
fi
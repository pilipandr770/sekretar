@echo off
REM Comprehensive i18n Test Suite Runner for Windows
REM This script runs all i18n tests and generates reports

echo 🌍 AI Secretary - Comprehensive i18n Test Suite
echo ==============================================

REM Check if we're in the right directory
if not exist "app\__init__.py" (
    echo ❌ Error: Please run this script from the project root directory
    exit /b 1
)

REM Check if virtual environment is activated
if "%VIRTUAL_ENV%"=="" (
    echo ⚠️  Warning: No virtual environment detected
    echo    Consider activating your virtual environment first
    echo    Example: venv\Scripts\activate
    echo.
)

REM Install test dependencies if needed
echo 📦 Checking test dependencies...
pip install -q pytest pytest-html pytest-cov pytest-mock selenium beautifulsoup4 2>nul || (
    echo ⚠️  Some test dependencies could not be installed
    echo    Tests will run with available dependencies
)

REM Create test results directory
if not exist "tests\results" mkdir "tests\results"

REM Set environment variables for testing
set TESTING=true
set FLASK_ENV=testing
set DATABASE_URL=sqlite:///:memory:
set SECRET_KEY=test-secret-key-for-i18n-tests
set WTF_CSRF_ENABLED=false

echo.
echo 🧪 Running i18n Test Suite...
echo ------------------------------

REM Run the test suite
python tests\run_i18n_tests.py

REM Check exit code
if %ERRORLEVEL% equ 0 (
    echo.
    echo 🎉 All i18n tests completed successfully!
    echo.
    echo 📊 Test Results Summary:
    echo   ✅ Language Detection Service: Tested
    echo   ✅ Translation Management: Tested
    echo   ✅ Localization Formatting: Tested
    echo   ✅ Email Localization: Tested
    echo   ✅ Frontend JavaScript i18n: Tested
    echo   ✅ API Integration: Tested
    echo   ✅ End-to-End Workflows: Tested
    echo   ✅ Translation Quality: Tested
    echo.
    echo 📄 Reports generated:
    echo   • tests\i18n_test_summary.json
    echo   • tests\i18n_test_results.xml
    echo   • tests\i18n_test_report.html (if available)
    echo.
    echo ✨ The i18n implementation is ready for production!
) else (
    echo.
    echo ❌ Some tests failed. Please review the output above.
    echo.
    echo 🔍 Common troubleshooting steps:
    echo   1. Check that all required dependencies are installed
    echo   2. Ensure database is properly configured
    echo   3. Verify that translation files exist
    echo   4. Check that API endpoints are implemented
    echo   5. Ensure Selenium WebDriver is available for frontend tests
    echo.
    exit /b 1
)
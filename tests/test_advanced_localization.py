"""Tests for advanced localization features."""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from flask import Flask
from app import create_app
from app.services.localization_service import LocalizationService
from app.utils.template_filters import init_template_filters
from app.utils.localization_context import init_localization_context_processor


class TestAdvancedLocalization:
    """Test advanced localization features."""
    
    @pytest.fixture
    def app(self):
        """Create test app."""
        app = create_app('testing')
        return app
    
    @pytest.fixture
    def localization_service(self):
        """Create localization service instance."""
        return LocalizationService()
    
    def test_date_formatting(self, app, localization_service):
        """Test date formatting with different locales."""
        with app.app_context():
            test_date = datetime(2023, 12, 25, 14, 30, 0)
            
            # Test English formatting
            formatted = localization_service.format_date(test_date, 'medium', 'en')
            assert isinstance(formatted, str)
            assert len(formatted) > 0
            
            # Test German formatting
            formatted_de = localization_service.format_date(test_date, 'medium', 'de')
            assert isinstance(formatted_de, str)
            assert len(formatted_de) > 0
            
            # Test Ukrainian formatting
            formatted_uk = localization_service.format_date(test_date, 'medium', 'uk')
            assert isinstance(formatted_uk, str)
            assert len(formatted_uk) > 0
    
    def test_time_formatting(self, app, localization_service):
        """Test time formatting with different locales."""
        with app.app_context():
            test_time = datetime(2023, 12, 25, 14, 30, 0)
            
            # Test different formats
            for format_type in ['short', 'medium', 'long']:
                formatted = localization_service.format_time(test_time, format_type, 'en')
                assert isinstance(formatted, str)
                assert len(formatted) > 0
    
    def test_datetime_formatting(self, app, localization_service):
        """Test datetime formatting with different locales."""
        with app.app_context():
            test_datetime = datetime(2023, 12, 25, 14, 30, 0)
            
            # Test different formats
            for format_type in ['short', 'medium', 'long']:
                formatted = localization_service.format_datetime(test_datetime, format_type, 'en')
                assert isinstance(formatted, str)
                assert len(formatted) > 0
    
    def test_currency_formatting(self, app, localization_service):
        """Test currency formatting with different locales and currencies."""
        with app.app_context():
            test_amount = Decimal('1234.56')
            
            # Test different currencies
            currencies = ['EUR', 'USD', 'GBP', 'UAH']
            locales = ['en', 'de', 'uk']
            
            for currency in currencies:
                for locale in locales:
                    formatted = localization_service.format_currency(test_amount, currency, locale)
                    assert isinstance(formatted, str)
                    assert len(formatted) > 0
                    # Check that currency symbol or code is present
                    assert (currency in formatted or 
                           '€' in formatted or '$' in formatted or '£' in formatted or 
                           '₴' in formatted or any(c in formatted for c in ['€', '$', '£', '₴']))
    
    def test_number_formatting(self, app, localization_service):
        """Test number formatting with different locales."""
        with app.app_context():
            test_numbers = [1234, 1234.56, Decimal('1234567.89')]
            
            for number in test_numbers:
                for locale in ['en', 'de', 'uk']:
                    formatted = localization_service.format_number(number, locale)
                    assert isinstance(formatted, str)
                    assert len(formatted) > 0
    
    def test_percent_formatting(self, app, localization_service):
        """Test percentage formatting with different locales."""
        with app.app_context():
            test_percentages = [0.1234, 0.5, 1.0]
            
            for percentage in test_percentages:
                for locale in ['en', 'de', 'uk']:
                    formatted = localization_service.format_percent(percentage, locale)
                    assert isinstance(formatted, str)
                    assert len(formatted) > 0
                    assert '%' in formatted
    
    def test_relative_time_formatting(self, app, localization_service):
        """Test relative time formatting with different locales."""
        with app.app_context():
            now = datetime.utcnow()
            
            # Test past times
            past_times = [
                now - timedelta(minutes=5),
                now - timedelta(hours=2),
                now - timedelta(days=1),
                now - timedelta(days=3)
            ]
            
            # Test future times
            future_times = [
                now + timedelta(minutes=15),
                now + timedelta(hours=4),
                now + timedelta(days=2)
            ]
            
            all_times = past_times + future_times
            
            for test_time in all_times:
                for locale in ['en', 'de', 'uk']:
                    formatted = localization_service.get_relative_time(test_time, locale)
                    assert isinstance(formatted, str)
                    assert len(formatted) > 0
    
    def test_file_size_formatting(self, app, localization_service):
        """Test file size formatting with different locales."""
        with app.app_context():
            test_sizes = [0, 1024, 1048576, 1073741824]
            
            for size in test_sizes:
                for locale in ['en', 'de', 'uk']:
                    formatted = localization_service.format_file_size(size, locale)
                    assert isinstance(formatted, str)
                    assert len(formatted) > 0
                    assert any(unit in formatted for unit in ['B', 'KB', 'MB', 'GB', 'КБ', 'МБ', 'ГБ'])
    
    def test_pluralization(self, app, localization_service):
        """Test pluralization with different locales."""
        with app.app_context():
            test_counts = [0, 1, 2, 5, 21, 101]
            
            for count in test_counts:
                for locale in ['en', 'de', 'uk']:
                    result = localization_service.pluralize(count, 'item', 'items', locale)
                    assert isinstance(result, str)
                    assert len(result) > 0
    
    def test_locale_info(self, app, localization_service):
        """Test locale information retrieval."""
        with app.app_context():
            for locale in ['en', 'de', 'uk']:
                info = localization_service.get_locale_info(locale)
                assert isinstance(info, dict)
                assert 'code' in info or len(info) == 0  # Empty dict is acceptable fallback
    
    def test_month_names(self, app, localization_service):
        """Test localized month names."""
        with app.app_context():
            for locale in ['en', 'de', 'uk']:
                months = localization_service.get_month_names(locale)
                assert isinstance(months, dict)
                assert 'wide' in months
                assert 'abbreviated' in months
                assert len(months['wide']) == 12
                assert len(months['abbreviated']) == 12
    
    def test_day_names(self, app, localization_service):
        """Test localized day names."""
        with app.app_context():
            for locale in ['en', 'de', 'uk']:
                days = localization_service.get_day_names(locale)
                assert isinstance(days, dict)
                assert 'wide' in days
                assert 'abbreviated' in days
                assert len(days['wide']) == 7
                assert len(days['abbreviated']) == 7
    
    def test_rtl_locale_detection(self, app, localization_service):
        """Test RTL locale detection."""
        with app.app_context():
            # Our supported locales are all LTR
            for locale in ['en', 'de', 'uk']:
                is_rtl = localization_service.is_rtl_locale(locale)
                assert isinstance(is_rtl, bool)
                assert is_rtl is False  # All our locales are LTR
    
    def test_template_filters_initialization(self, app):
        """Test template filters initialization."""
        with app.app_context():
            # Test that filters can be initialized without errors
            result = init_template_filters(app)
            assert result is True
            
            # Test that filters are registered
            assert 'format_date' in app.jinja_env.filters
            assert 'format_datetime' in app.jinja_env.filters
            assert 'format_time' in app.jinja_env.filters
            assert 'format_currency' in app.jinja_env.filters
            assert 'format_number' in app.jinja_env.filters
            assert 'format_percent' in app.jinja_env.filters
            assert 'relative_time' in app.jinja_env.filters
            assert 'format_file_size' in app.jinja_env.filters
            assert 'pluralize_count' in app.jinja_env.filters
    
    def test_template_globals_initialization(self, app):
        """Test template globals initialization."""
        with app.app_context():
            init_template_filters(app)
            
            # Test that globals are registered
            assert 'get_locale_info' in app.jinja_env.globals
            assert 'get_month_names' in app.jinja_env.globals
            assert 'get_day_names' in app.jinja_env.globals
            assert 'is_rtl_locale' in app.jinja_env.globals
    
    def test_template_tests_initialization(self, app):
        """Test template tests initialization."""
        with app.app_context():
            init_template_filters(app)
            
            # Test that template tests are registered
            assert 'past' in app.jinja_env.tests
            assert 'future' in app.jinja_env.tests
            assert 'today' in app.jinja_env.tests
            assert 'this_week' in app.jinja_env.tests
            assert 'this_month' in app.jinja_env.tests
    
    def test_context_processor_initialization(self, app):
        """Test localization context processor initialization."""
        with app.app_context():
            processor = init_localization_context_processor(app)
            assert processor is not None
            
            # Test context generation
            context = processor.get_localization_context()
            assert isinstance(context, dict)
            assert 'locale' in context
            assert 'localization' in context
            assert 'available_languages' in context
            assert 'current_time' in context
    
    def test_template_filter_error_handling(self, app):
        """Test template filter error handling."""
        with app.app_context():
            init_template_filters(app)
            
            # Test filters with invalid input
            date_filter = app.jinja_env.filters['format_date']
            result = date_filter(None)
            assert result == ''
            
            number_filter = app.jinja_env.filters['format_number']
            result = number_filter(None)
            assert result == ''
            
            currency_filter = app.jinja_env.filters['format_currency']
            result = currency_filter(None)
            assert result == ''
    
    def test_localization_service_error_handling(self, app, localization_service):
        """Test localization service error handling."""
        with app.app_context():
            # Test with invalid locale
            result = localization_service.format_date(datetime.now(), 'medium', 'invalid')
            assert isinstance(result, str)
            assert len(result) > 0
            
            # Test with None values - should return fallback format
            result = localization_service.format_currency(None, 'EUR')
            assert isinstance(result, str)
            assert 'EUR' in result
    
    def test_javascript_integration_file_exists(self):
        """Test that JavaScript localization file exists."""
        import os
        js_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app', 'static', 'js', 'localization.js')
        assert os.path.exists(js_file)
        
        # Test that file contains expected classes and methods
        with open(js_file, 'r', encoding='utf-8') as f:
            content = f.read()
            assert 'class LocalizationClient' in content
            assert 'formatDate' in content
            assert 'formatCurrency' in content
            assert 'formatNumber' in content
            assert 'formatRelativeTime' in content
    
    def test_demo_template_exists(self):
        """Test that localization demo template exists."""
        import os
        template_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app', 'templates', 'localization_demo.html')
        assert os.path.exists(template_file)
        
        # Test that template contains expected elements
        with open(template_file, 'r', encoding='utf-8') as f:
            content = f.read()
            assert 'Advanced Localization Features Demo' in content
            assert 'format_date' in content
            assert 'format_currency' in content
            assert 'relative_time' in content
            assert 'data-localize' in content


class TestLocalizationIntegration:
    """Test localization integration with Flask app."""
    
    @pytest.fixture
    def app(self):
        """Create test app."""
        return create_app('testing')
    
    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()
    
    def test_localization_demo_route(self, client):
        """Test localization demo route."""
        response = client.get('/localization-demo')
        assert response.status_code == 200
        assert b'Advanced Localization Features Demo' in response.data
    
    def test_localization_demo_with_language_parameter(self, client):
        """Test localization demo with language parameter."""
        # Test with German
        response = client.get('/localization-demo?lang=de')
        assert response.status_code == 200
        
        # Test with Ukrainian
        response = client.get('/localization-demo?lang=uk')
        assert response.status_code == 200
        
        # Test with English
        response = client.get('/localization-demo?lang=en')
        assert response.status_code == 200
    
    def test_template_rendering_with_filters(self, app):
        """Test template rendering with localization filters."""
        with app.app_context():
            from flask import render_template_string
            from datetime import datetime
            
            template = """
            {{ test_date|format_date('medium') }}
            {{ test_number|format_number }}
            {{ test_amount|format_currency('EUR') }}
            """
            
            result = render_template_string(
                template,
                test_date=datetime(2023, 12, 25),
                test_number=1234.56,
                test_amount=1234.56
            )
            
            assert isinstance(result, str)
            assert len(result.strip()) > 0
    
    def test_context_processor_injection(self, app):
        """Test that localization context is injected into templates."""
        with app.app_context():
            from flask import render_template_string
            
            template = """
            {{ locale.code }}
            {{ locale.name }}
            {{ available_languages|length }}
            """
            
            result = render_template_string(template)
            assert isinstance(result, str)
            assert len(result.strip()) > 0


if __name__ == '__main__':
    pytest.main([__file__])
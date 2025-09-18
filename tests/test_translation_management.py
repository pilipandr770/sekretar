"""Tests for translation management system."""
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from app.services.translation_service import TranslationService, TranslationValidationError
from app.models.translation_stats import TranslationStats, MissingTranslation, TranslationValidationError as ValidationErrorModel
from app.utils.translation_monitor import TranslationMonitor, monitored_gettext
from app.utils.i18n import LANGUAGES


class TestTranslationService:
    """Test translation service functionality."""
    
    def test_translation_service_initialization(self, app):
        """Test translation service can be initialized."""
        with app.app_context():
            service = TranslationService()
            assert service is not None
            assert service.translations_dir is not None
    
    def test_get_translation_coverage(self, app):
        """Test getting translation coverage statistics."""
        with app.app_context():
            service = TranslationService()
            
            # Mock the file system operations
            with patch.object(service, '_get_language_coverage') as mock_coverage:
                mock_coverage.return_value = {
                    'total_messages': 100,
                    'translated_messages': 80,
                    'untranslated_messages': 20,
                    'fuzzy_messages': 5,
                    'coverage_percentage': 80.0,
                    'status': 'good',
                    'last_updated': '2024-01-01T00:00:00'
                }
                
                coverage = service.get_translation_coverage()
                
                assert isinstance(coverage, dict)
                assert len(coverage) == len(LANGUAGES)
                
                for lang_code in LANGUAGES.keys():
                    assert lang_code in coverage
                    assert coverage[lang_code]['coverage_percentage'] == 80.0
    
    def test_validate_translations(self, app):
        """Test translation validation."""
        with app.app_context():
            service = TranslationService()
            
            # Mock validation results
            with patch.object(service, '_validate_language') as mock_validate:
                mock_validate.return_value = [
                    {
                        'language': 'de',
                        'type': 'missing_translation',
                        'message_id': 'test_message',
                        'message': 'Missing translation for: test_message',
                        'severity': 'warning',
                        'locations': ['test.py:10']
                    }
                ]
                
                errors = service.validate_translations('de')
                
                assert isinstance(errors, list)
                assert len(errors) == 1
                assert errors[0]['language'] == 'de'
                assert errors[0]['type'] == 'missing_translation'
    
    def test_get_missing_translations(self, app):
        """Test getting missing translations."""
        with app.app_context():
            service = TranslationService()
            
            # Mock missing translations
            with patch.object(service, '_get_missing_for_language') as mock_missing:
                mock_missing.return_value = ['missing_message_1', 'missing_message_2']
                
                missing = service.get_missing_translations('de')
                
                assert isinstance(missing, dict)
                assert 'de' in missing
                assert len(missing['de']) == 2
                assert 'missing_message_1' in missing['de']


class TestTranslationStats:
    """Test translation statistics model."""
    
    def test_create_translation_stats(self, app, db_session):
        """Test creating translation statistics."""
        with app.app_context():
            stats = TranslationStats(
                language='de',
                total_strings=100,
                translated_strings=80,
                coverage_percentage=80.0,
                status='good'
            )
            
            db_session.add(stats)
            db_session.commit()
            
            assert stats.id is not None
            assert stats.language == 'de'
            assert stats.coverage_percentage == 80.0
    
    def test_update_stats(self, app, db_session):
        """Test updating translation statistics."""
        with app.app_context():
            # Test update_stats class method
            stats_data = {
                'total_messages': 150,
                'translated_messages': 120,
                'fuzzy_messages': 10,
                'untranslated_messages': 20,
                'coverage_percentage': 80.0,
                'status': 'good'
            }
            
            stats = TranslationStats.update_stats('de', stats_data)
            
            assert stats.language == 'de'
            assert stats.total_strings == 150
            assert stats.translated_strings == 120
            assert stats.coverage_percentage == 80.0
    
    def test_get_by_language(self, app, db_session):
        """Test getting stats by language."""
        with app.app_context():
            # Create test stats
            stats = TranslationStats(
                language='uk',
                total_strings=50,
                translated_strings=25,
                coverage_percentage=50.0,
                status='partial'
            )
            db_session.add(stats)
            db_session.commit()
            
            # Test retrieval
            retrieved = TranslationStats.get_by_language('uk')
            assert retrieved is not None
            assert retrieved.language == 'uk'
            assert retrieved.coverage_percentage == 50.0


class TestMissingTranslation:
    """Test missing translation model."""
    
    def test_log_missing_translation(self, app, db_session):
        """Test logging missing translation."""
        with app.app_context():
            missing = MissingTranslation.log_missing(
                language='de',
                message_id='test_missing_message',
                source_file='test.py',
                line_number=10
            )
            
            assert missing.language == 'de'
            assert missing.message_id == 'test_missing_message'
            assert missing.source_file == 'test.py'
            assert missing.line_number == 10
            assert missing.occurrence_count == 1
            assert not missing.is_resolved
    
    def test_log_missing_translation_duplicate(self, app, db_session):
        """Test logging duplicate missing translation."""
        with app.app_context():
            # Log first occurrence
            missing1 = MissingTranslation.log_missing(
                language='de',
                message_id='duplicate_message'
            )
            
            # Log duplicate
            missing2 = MissingTranslation.log_missing(
                language='de',
                message_id='duplicate_message'
            )
            
            # Should be the same record with incremented count
            assert missing1.id == missing2.id
            assert missing2.occurrence_count == 2
    
    def test_mark_resolved(self, app, db_session):
        """Test marking missing translation as resolved."""
        with app.app_context():
            # Create missing translation
            missing = MissingTranslation.log_missing(
                language='de',
                message_id='resolve_test_message'
            )
            
            # Mark as resolved
            success = MissingTranslation.mark_resolved('de', 'resolve_test_message')
            
            assert success
            assert missing.is_resolved
            assert missing.resolved_at is not None
    
    def test_get_unresolved_count(self, app, db_session):
        """Test getting unresolved missing translation count."""
        with app.app_context():
            # Create some missing translations
            MissingTranslation.log_missing('de', 'message1')
            MissingTranslation.log_missing('de', 'message2')
            MissingTranslation.log_missing('uk', 'message3')
            
            # Mark one as resolved
            MissingTranslation.mark_resolved('de', 'message1')
            
            # Test counts
            de_count = MissingTranslation.get_unresolved_count('de')
            uk_count = MissingTranslation.get_unresolved_count('uk')
            total_count = MissingTranslation.get_unresolved_count()
            
            assert de_count == 1  # message2 is unresolved
            assert uk_count == 1  # message3 is unresolved
            assert total_count == 2  # total unresolved


class TestTranslationValidationError:
    """Test translation validation error model."""
    
    def test_log_validation_error(self, app, db_session):
        """Test logging validation error."""
        with app.app_context():
            error = ValidationErrorModel.log_error(
                language='de',
                message_id='test_message',
                error_type='placeholder_mismatch',
                error_message='Placeholder mismatch detected',
                severity='error'
            )
            
            assert error.language == 'de'
            assert error.message_id == 'test_message'
            assert error.error_type == 'placeholder_mismatch'
            assert error.severity == 'error'
            assert error.detection_count == 1
    
    def test_get_error_summary(self, app, db_session):
        """Test getting error summary."""
        with app.app_context():
            # Create some validation errors
            ValidationErrorModel.log_error('de', 'msg1', 'type1', 'error1', 'error')
            ValidationErrorModel.log_error('de', 'msg2', 'type2', 'error2', 'warning')
            ValidationErrorModel.log_error('de', 'msg3', 'type1', 'error3', 'error')
            
            summary = ValidationErrorModel.get_error_summary('de')
            
            assert summary['total_errors'] == 3
            assert summary['by_severity']['error'] == 2
            assert summary['by_severity']['warning'] == 1
            assert summary['by_type']['type1'] == 2
            assert summary['by_type']['type2'] == 1


class TestTranslationMonitor:
    """Test translation monitoring functionality."""
    
    def test_translation_monitor_initialization(self):
        """Test translation monitor can be initialized."""
        monitor = TranslationMonitor()
        assert monitor.enabled
        assert monitor.log_to_database
        assert monitor.log_to_file
    
    def test_monitored_gettext(self, app):
        """Test monitored gettext function."""
        with app.app_context():
            # Mock gettext to return original message (simulating missing translation)
            with patch('app.utils.translation_monitor.gettext') as mock_gettext:
                mock_gettext.return_value = 'test_message'
                
                with patch('app.utils.translation_monitor.get_locale') as mock_locale:
                    mock_locale.return_value = 'de'  # Non-English locale
                    
                    with patch('app.utils.translation_monitor.translation_monitor') as mock_monitor:
                        result = monitored_gettext('test_message')
                        
                        assert result == 'test_message'
                        mock_monitor.log_missing_translation.assert_called_once()
    
    def test_enable_disable_monitoring(self):
        """Test enabling and disabling monitoring."""
        monitor = TranslationMonitor()
        
        assert monitor.enabled
        
        monitor.disable_monitoring()
        assert not monitor.enabled
        
        monitor.enable_monitoring()
        assert monitor.enabled


@pytest.fixture
def app():
    """Create test Flask app."""
    from app import create_app
    
    app = create_app('testing')
    
    # Override config for testing
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False,
        'TRANSLATION_MONITORING_ENABLED': True
    })
    
    with app.app_context():
        from app import db
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def db_session(app):
    """Create database session for testing."""
    from app import db
    
    with app.app_context():
        yield db.session
        db.session.rollback()
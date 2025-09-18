"""CLI commands for translation management."""
import click
from flask import current_app
from flask.cli import with_appcontext
from app.services.translation_service import TranslationService, TranslationValidationError
from app.models.translation_stats import TranslationStats, MissingTranslation, TranslationValidationError as ValidationErrorModel
from app.utils.i18n import LANGUAGES
from app import db
import structlog

logger = structlog.get_logger()


@click.group()
def translations():
    """Translation management commands."""
    pass


@translations.command()
@with_appcontext
def extract():
    """Extract translatable messages from the application."""
    click.echo("Extracting translatable messages...")
    
    try:
        translation_service = TranslationService()
        result = translation_service.extract_messages()
        
        click.echo(f"✅ Extraction completed successfully!")
        click.echo(f"   - Extracted {result['extracted_messages']} messages")
        click.echo(f"   - Total unique messages: {result['total_unique_messages']}")
        click.echo(f"   - Updated languages: {', '.join(result['updated_languages'])}")
        
        # Update database statistics
        for lang_code in LANGUAGES.keys():
            TranslationStats.update_stats(lang_code, {
                'last_extraction': result['timestamp']
            })
        
    except TranslationValidationError as e:
        click.echo(f"❌ Extraction failed: {e}", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        raise click.Abort()


@translations.command()
@with_appcontext
def compile():
    """Compile translation files (.po to .mo)."""
    click.echo("Compiling translation files...")
    
    try:
        translation_service = TranslationService()
        result = translation_service.compile_translations()
        
        click.echo(f"✅ Compilation completed successfully!")
        click.echo(f"   - Compiled languages: {', '.join(result['compiled_languages'])}")
        
        if result['compilation_errors']:
            click.echo("⚠️  Compilation errors:")
            for error in result['compilation_errors']:
                click.echo(f"   - {error['language']}: {error['error']}")
        
        # Update database statistics
        for lang_code in result['compiled_languages']:
            TranslationStats.update_stats(lang_code, {
                'last_compilation': result['timestamp']
            })
        
    except TranslationValidationError as e:
        click.echo(f"❌ Compilation failed: {e}", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        raise click.Abort()


@translations.command()
@click.option('--language', '-l', help='Validate specific language only')
@with_appcontext
def validate(language):
    """Validate translations for consistency and correctness."""
    if language:
        click.echo(f"Validating {language} translations...")
    else:
        click.echo("Validating all translations...")
    
    try:
        translation_service = TranslationService()
        validation_errors = translation_service.validate_translations(language)
        
        if not validation_errors:
            click.echo("✅ All translations are valid!")
            return
        
        # Group errors by severity
        errors_by_severity = {'error': [], 'warning': [], 'info': []}
        for error in validation_errors:
            errors_by_severity[error['severity']].append(error)
        
        # Display summary
        click.echo(f"Found {len(validation_errors)} validation issues:")
        for severity, errors in errors_by_severity.items():
            if errors:
                click.echo(f"   - {severity.upper()}: {len(errors)}")
        
        # Store validation errors in database
        for error in validation_errors:
            ValidationErrorModel.log_error(
                language=error['language'],
                message_id=error.get('message_id', ''),
                error_type=error['type'],
                error_message=error['message'],
                severity=error['severity'],
                source_file=error.get('locations', [None])[0] if error.get('locations') else None
            )
        
        # Display detailed errors if requested
        if click.confirm("Show detailed validation errors?"):
            for error in validation_errors:
                click.echo(f"\n{error['severity'].upper()}: {error['type']}")
                click.echo(f"Language: {error['language']}")
                click.echo(f"Message: {error['message']}")
                if error.get('message_id'):
                    click.echo(f"Message ID: {error['message_id']}")
                if error.get('locations'):
                    click.echo(f"Locations: {', '.join(error['locations'])}")
        
    except TranslationValidationError as e:
        click.echo(f"❌ Validation failed: {e}", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        raise click.Abort()


@translations.command()
@with_appcontext
def coverage():
    """Show translation coverage statistics."""
    click.echo("Translation Coverage Report")
    click.echo("=" * 50)
    
    try:
        translation_service = TranslationService()
        coverage_stats = translation_service.get_translation_coverage()
        
        # Update database with latest stats
        for lang_code, stats in coverage_stats.items():
            TranslationStats.update_stats(lang_code, stats)
        
        # Display coverage for each language
        for lang_code, lang_name in LANGUAGES.items():
            stats = coverage_stats.get(lang_code, {})
            
            click.echo(f"\n{lang_name} ({lang_code}):")
            click.echo(f"  Status: {stats.get('status', 'unknown')}")
            click.echo(f"  Coverage: {stats.get('coverage_percentage', 0):.1f}%")
            click.echo(f"  Total messages: {stats.get('total_messages', 0)}")
            click.echo(f"  Translated: {stats.get('translated_messages', 0)}")
            click.echo(f"  Untranslated: {stats.get('untranslated_messages', 0)}")
            click.echo(f"  Fuzzy: {stats.get('fuzzy_messages', 0)}")
            
            if stats.get('last_updated'):
                click.echo(f"  Last updated: {stats['last_updated']}")
        
        # Overall statistics
        total_languages = len(coverage_stats)
        complete_languages = len([s for s in coverage_stats.values() if s.get('status') == 'complete'])
        avg_coverage = sum(s.get('coverage_percentage', 0) for s in coverage_stats.values()) / total_languages if total_languages else 0
        
        click.echo(f"\nOverall Statistics:")
        click.echo(f"  Complete languages: {complete_languages}/{total_languages}")
        click.echo(f"  Average coverage: {avg_coverage:.1f}%")
        
    except Exception as e:
        click.echo(f"❌ Failed to get coverage statistics: {e}", err=True)
        raise click.Abort()


@translations.command()
@click.option('--language', '-l', help='Show missing translations for specific language only')
@click.option('--limit', '-n', default=10, help='Limit number of results to show')
@with_appcontext
def missing(language, limit):
    """Show missing translations."""
    if language:
        click.echo(f"Missing translations for {language}:")
    else:
        click.echo("Missing translations (all languages):")
    
    click.echo("=" * 50)
    
    try:
        translation_service = TranslationService()
        missing_translations = translation_service.get_missing_translations(language)
        
        total_missing = 0
        for lang_code, missing_list in missing_translations.items():
            if missing_list:
                click.echo(f"\n{LANGUAGES.get(lang_code, lang_code)} ({lang_code}): {len(missing_list)} missing")
                
                # Show first few missing translations
                for i, message_id in enumerate(missing_list[:limit]):
                    click.echo(f"  {i+1}. {message_id}")
                    
                    # Log to database
                    MissingTranslation.log_missing(lang_code, message_id)
                
                if len(missing_list) > limit:
                    click.echo(f"  ... and {len(missing_list) - limit} more")
                
                total_missing += len(missing_list)
        
        if total_missing == 0:
            click.echo("✅ No missing translations found!")
        else:
            click.echo(f"\nTotal missing translations: {total_missing}")
        
    except Exception as e:
        click.echo(f"❌ Failed to get missing translations: {e}", err=True)
        raise click.Abort()


@translations.command()
@click.option('--language', '-l', required=True, help='Language code')
@click.option('--message-id', '-m', required=True, help='Message ID to update')
@click.option('--translation', '-t', required=True, help='Translation text')
@with_appcontext
def update(language, message_id, translation):
    """Update a specific translation."""
    if language not in LANGUAGES:
        click.echo(f"❌ Invalid language code: {language}", err=True)
        click.echo(f"Available languages: {', '.join(LANGUAGES.keys())}")
        raise click.Abort()
    
    click.echo(f"Updating translation for '{message_id}' in {language}...")
    
    try:
        translation_service = TranslationService()
        success = translation_service.update_translation(language, message_id, translation)
        
        if success:
            click.echo("✅ Translation updated successfully!")
            
            # Mark missing translation as resolved
            MissingTranslation.mark_resolved(language, message_id)
            
            # Mark related validation errors as resolved
            ValidationErrorModel.mark_resolved(language, message_id, 'missing_translation')
        else:
            click.echo("❌ Failed to update translation", err=True)
            raise click.Abort()
        
    except Exception as e:
        click.echo(f"❌ Failed to update translation: {e}", err=True)
        raise click.Abort()


@translations.command()
@with_appcontext
def status():
    """Show translation system status."""
    click.echo("Translation System Status")
    click.echo("=" * 50)
    
    try:
        # Get database statistics
        db_stats = TranslationStats.get_all_languages()
        
        # Get missing translations count
        missing_counts = {}
        validation_error_counts = {}
        
        for lang_code in LANGUAGES.keys():
            missing_counts[lang_code] = MissingTranslation.get_unresolved_count(lang_code)
            validation_error_counts[lang_code] = ValidationErrorModel.get_error_summary(lang_code)
        
        # Display status for each language
        for lang_code, lang_name in LANGUAGES.items():
            click.echo(f"\n{lang_name} ({lang_code}):")
            
            # Find database stats
            db_stat = next((s for s in db_stats if s.language == lang_code), None)
            
            if db_stat:
                click.echo(f"  Coverage: {db_stat.coverage_percentage:.1f}%")
                click.echo(f"  Status: {db_stat.status}")
                click.echo(f"  Total strings: {db_stat.total_strings}")
                click.echo(f"  Translated: {db_stat.translated_strings}")
                click.echo(f"  Missing: {missing_counts[lang_code]}")
                click.echo(f"  Validation errors: {validation_error_counts[lang_code].get('total_errors', 0)}")
                
                if db_stat.last_extraction:
                    click.echo(f"  Last extraction: {db_stat.last_extraction}")
                if db_stat.last_compilation:
                    click.echo(f"  Last compilation: {db_stat.last_compilation}")
            else:
                click.echo(f"  No statistics available")
                click.echo(f"  Missing: {missing_counts[lang_code]}")
                click.echo(f"  Validation errors: {validation_error_counts[lang_code].get('total_errors', 0)}")
        
        # Overall health
        total_missing = sum(missing_counts.values())
        total_errors = sum(s.get('total_errors', 0) for s in validation_error_counts.values())
        
        click.echo(f"\nOverall Health:")
        click.echo(f"  Total missing translations: {total_missing}")
        click.echo(f"  Total validation errors: {total_errors}")
        
        if total_missing == 0 and total_errors == 0:
            click.echo("  Status: ✅ Healthy")
        elif total_missing < 10 and total_errors < 5:
            click.echo("  Status: ⚠️  Warning")
        else:
            click.echo("  Status: ❌ Critical")
        
    except Exception as e:
        click.echo(f"❌ Failed to get system status: {e}", err=True)
        raise click.Abort()


@translations.command()
@click.option('--days', '-d', default=30, help='Clean up resolved items older than N days')
@with_appcontext
def cleanup(days):
    """Clean up old resolved translation issues."""
    click.echo(f"Cleaning up resolved translation issues older than {days} days...")
    
    try:
        # Clean up resolved missing translations
        missing_deleted = MissingTranslation.cleanup_resolved(days)
        
        # Clean up resolved validation errors (implement similar method)
        # validation_deleted = ValidationErrorModel.cleanup_resolved(days)
        
        click.echo(f"✅ Cleanup completed!")
        click.echo(f"   - Deleted {missing_deleted} resolved missing translation records")
        # click.echo(f"   - Deleted {validation_deleted} resolved validation error records")
        
    except Exception as e:
        click.echo(f"❌ Cleanup failed: {e}", err=True)
        raise click.Abort()


def init_translation_commands(app):
    """Initialize translation CLI commands."""
    app.cli.add_command(translations)
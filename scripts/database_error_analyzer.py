#!/usr/bin/env python3
"""
Database Error Analyzer CLI Tool

Command-line tool for analyzing database initialization errors,
generating troubleshooting reports, and providing recovery guidance.
"""
import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Add the parent directory to the path so we can import from app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.database_error_logger import get_database_error_logger
from app.utils.database_errors import get_database_error_handler, DatabaseErrorCode


def analyze_errors(hours: int = 24, output_format: str = 'text'):
    """
    Analyze database errors from the last N hours.
    
    Args:
        hours: Number of hours to analyze
        output_format: Output format ('text', 'json', 'csv')
    """
    error_logger = get_database_error_logger()
    
    print(f"🔍 Analyzing database errors from the last {hours} hours...")
    
    # Get error summary
    summary = error_logger.get_error_summary(hours)
    patterns = error_logger.get_error_patterns()
    
    if output_format == 'json':
        report = {
            'summary': summary,
            'patterns': patterns,
            'analysis_timestamp': datetime.now().isoformat()
        }
        print(json.dumps(report, indent=2))
        return
    
    # Text output
    print(f"\n📊 Error Summary ({hours} hours)")
    print("=" * 50)
    print(f"Total errors: {summary['total_errors']}")
    
    if summary['error_counts']:
        print("\nErrors by code:")
        for error_code, count in sorted(summary['error_counts'].items(), key=lambda x: x[1], reverse=True):
            print(f"  {error_code}: {count}")
    
    if summary['severity_counts']:
        print("\nErrors by severity:")
        for severity, count in summary['severity_counts'].items():
            print(f"  {severity}: {count}")
    
    print(f"\nRecovery statistics:")
    print(f"  Attempted: {summary['recovery_stats']['attempted']}")
    print(f"  Successful: {summary['recovery_stats']['successful']}")
    print(f"  Success rate: {summary['recovery_success_rate']:.1%}")
    
    if summary['most_common_error']:
        print(f"\nMost common error: {summary['most_common_error']}")
    
    # Pattern analysis
    if patterns['patterns']:
        print(f"\n🔄 Error Patterns")
        print("=" * 50)
        for pattern in patterns['patterns']:
            print(f"  {pattern['error_code']}: {pattern['pattern']} ({pattern['count']} occurrences)")
    
    if patterns['trends']['peak_error_hour']:
        print(f"\nPeak error hour: {patterns['trends']['peak_error_hour']}")


def generate_report(hours: int = 24, output_file: str = None, include_traces: bool = False):
    """
    Generate comprehensive troubleshooting report.
    
    Args:
        hours: Number of hours to analyze
        output_file: Output file path (optional)
        include_traces: Whether to include stack traces
    """
    error_logger = get_database_error_logger()
    
    print(f"📋 Generating troubleshooting report for the last {hours} hours...")
    
    report = error_logger.generate_troubleshooting_report(
        include_stack_traces=include_traces,
        hours=hours
    )
    
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"✅ Report saved to: {output_file}")
    else:
        # Print summary to console
        metadata = report['report_metadata']
        summary = report['error_summary']
        recommendations = report['recommendations']
        
        print(f"\n📋 Troubleshooting Report")
        print("=" * 50)
        print(f"Generated: {metadata['generated_at']}")
        print(f"Time period: {metadata['time_period_hours']} hours")
        print(f"Errors analyzed: {metadata['total_errors_analyzed']}")
        
        print(f"\n📊 Summary")
        print(f"Total errors: {summary['total_errors']}")
        print(f"Recovery success rate: {summary['recovery_success_rate']:.1%}")
        
        if recommendations:
            print(f"\n💡 Recommendations")
            print("-" * 30)
            for rec in recommendations:
                priority_icon = {
                    'critical': '🚨',
                    'high': '⚠️',
                    'medium': '⚡',
                    'low': 'ℹ️'
                }.get(rec['priority'], 'ℹ️')
                
                print(f"{priority_icon} {rec['title']} ({rec['priority']})")
                print(f"   {rec['description']}")
                print(f"   Action: {rec['action']}")
                print()


def show_recovery_suggestions(error_code: str = None):
    """
    Show recovery suggestions for database errors.
    
    Args:
        error_code: Specific error code to show suggestions for
    """
    error_handler = get_database_error_handler()
    
    if error_code:
        try:
            db_error_code = DatabaseErrorCode(error_code)
            print(f"🔧 Recovery suggestions for {error_code}")
            print("=" * 50)
            
            # This would need to be implemented in the error handler
            # For now, show general message
            print("Recovery suggestions would be shown here based on the error code.")
            
        except ValueError:
            print(f"❌ Unknown error code: {error_code}")
            print("Available error codes:")
            for code in DatabaseErrorCode:
                print(f"  {code.value}")
    else:
        print("🔧 Available Error Codes")
        print("=" * 50)
        for code in DatabaseErrorCode:
            print(f"  {code.value}: {code.name}")


def clear_error_history():
    """Clear the error history."""
    error_handler = get_database_error_handler()
    error_handler.clear_error_history()
    print("✅ Error history cleared")


def export_errors(output_file: str, hours: int = 24):
    """
    Export errors to file.
    
    Args:
        output_file: Output file path
        hours: Number of hours of errors to export
    """
    error_logger = get_database_error_logger()
    
    print(f"📤 Exporting errors from the last {hours} hours to {output_file}...")
    
    try:
        error_logger.export_errors_to_json(output_file, hours)
        print(f"✅ Errors exported to: {output_file}")
    except Exception as e:
        print(f"❌ Export failed: {e}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Database Error Analyzer - Analyze and troubleshoot database initialization errors"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze database errors')
    analyze_parser.add_argument('--hours', type=int, default=24, help='Hours to analyze (default: 24)')
    analyze_parser.add_argument('--format', choices=['text', 'json'], default='text', help='Output format')
    
    # Report command
    report_parser = subparsers.add_parser('report', help='Generate troubleshooting report')
    report_parser.add_argument('--hours', type=int, default=24, help='Hours to analyze (default: 24)')
    report_parser.add_argument('--output', help='Output file path')
    report_parser.add_argument('--include-traces', action='store_true', help='Include stack traces')
    
    # Recovery command
    recovery_parser = subparsers.add_parser('recovery', help='Show recovery suggestions')
    recovery_parser.add_argument('--error-code', help='Specific error code to show suggestions for')
    
    # Clear command
    subparsers.add_parser('clear', help='Clear error history')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export errors to file')
    export_parser.add_argument('output_file', help='Output file path')
    export_parser.add_argument('--hours', type=int, default=24, help='Hours to export (default: 24)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == 'analyze':
            analyze_errors(args.hours, args.format)
        elif args.command == 'report':
            generate_report(args.hours, args.output, args.include_traces)
        elif args.command == 'recovery':
            show_recovery_suggestions(args.error_code)
        elif args.command == 'clear':
            clear_error_history()
        elif args.command == 'export':
            export_errors(args.output_file, args.hours)
    
    except KeyboardInterrupt:
        print("\n⏹️ Operation cancelled by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
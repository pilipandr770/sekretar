#!/usr/bin/env python3
"""Test script for route validation."""
import os
import sys

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app import create_app
from app.utils.route_validator import RouteValidator


def main():
    """Test route validation."""
    print("🔍 Testing route validation...")
    
    try:
        # Create app instance
        app = create_app()
        
        with app.app_context():
            # Create route validator
            validator = RouteValidator(app)
            
            # Validate all routes
            result = validator.validate_all_routes()
            
            print(f"✅ Route validation completed")
            print(f"   Total routes: {result.total_routes}")
            print(f"   Valid routes: {result.valid_routes}")
            print(f"   Issues found: {len(result.issues)}")
            print(f"   Errors: {len(result.errors)}")
            print(f"   Warnings: {len(result.warnings)}")
            
            # Show issues by severity
            if result.issues:
                print("\n📋 Issues by severity:")
                from collections import defaultdict
                issues_by_severity = defaultdict(list)
                for issue in result.issues:
                    issues_by_severity[issue.severity].append(issue)
                
                for severity in ['critical', 'high', 'medium', 'low']:
                    if severity in issues_by_severity:
                        print(f"   {severity.title()}: {len(issues_by_severity[severity])}")
                        for issue in issues_by_severity[severity][:3]:  # Show first 3
                            print(f"     - {issue.route} ({issue.method}): {issue.description}")
                        if len(issues_by_severity[severity]) > 3:
                            print(f"     ... and {len(issues_by_severity[severity]) - 3} more")
            
            # Show route summary
            summary = validator.get_route_summary()
            if 'routes_by_blueprint' in summary:
                print(f"\n📊 Routes by blueprint:")
                for blueprint, routes in summary['routes_by_blueprint'].items():
                    print(f"   {blueprint}: {len(routes)} routes")
            
            # Generate report
            print("\n📄 Generating detailed report...")
            report = validator.generate_route_report()
            
            # Save report to file
            with open('route_validation_report.md', 'w', encoding='utf-8') as f:
                f.write(report)
            
            print("✅ Report saved to route_validation_report.md")
            
    except Exception as e:
        print(f"❌ Error during route validation: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
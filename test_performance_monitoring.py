#!/usr/bin/env python3
"""Test script for performance monitoring system."""

import os
import sys
import time
from datetime import datetime

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_performance_models():
    """Test performance monitoring models."""
    
    # Set up Flask app context
    from app import create_app, db
    
    app = create_app()
    
    with app.app_context():
        try:
            # Import models
            from app.models.performance import PerformanceMetric, SlowQuery, ServiceHealth, PerformanceAlert
            
            print("✅ Performance models imported successfully")
            
            # Test PerformanceMetric
            print("\n📊 Testing PerformanceMetric...")
            PerformanceMetric.log_request(
                endpoint='/test',
                method='GET',
                status_code=200,
                response_time_ms=150.5,
                db_query_time_ms=25.0,
                db_query_count=2,
                cache_hits=1,
                cache_misses=0
            )
            print("✅ PerformanceMetric logged successfully")
            
            # Test SlowQuery
            print("\n🐌 Testing SlowQuery...")
            SlowQuery.log_slow_query(
                query_text="SELECT * FROM users WHERE id = ?",
                execution_time_ms=1500.0,
                endpoint='/test',
                rows_examined=1000,
                rows_returned=1
            )
            print("✅ SlowQuery logged successfully")
            
            # Test ServiceHealth
            print("\n🏥 Testing ServiceHealth...")
            ServiceHealth.update_service_status(
                service_name='database',
                service_type='database',
                status='healthy',
                response_time_ms=10.5,
                check_type='ping'
            )
            print("✅ ServiceHealth updated successfully")
            
            # Test PerformanceAlert
            print("\n🚨 Testing PerformanceAlert...")
            alert = PerformanceAlert.create_or_update_alert(
                alert_type='slow_request',
                severity='medium',
                title='Test Slow Request',
                description='This is a test alert for slow request',
                endpoint='/test',
                metric_value=2500.0,
                threshold_value=2000.0
            )
            print("✅ PerformanceAlert created successfully")
            
            # Test queries
            print("\n🔍 Testing queries...")
            
            # Get slow requests
            slow_requests = PerformanceMetric.get_slow_requests(threshold_ms=100, hours=1)
            print(f"Found {len(slow_requests)} slow requests")
            
            # Get endpoint stats
            stats = PerformanceMetric.get_endpoint_stats('/test', hours=1)
            print(f"Endpoint stats: {stats}")
            
            # Get service health summary
            health_summary = ServiceHealth.get_service_status_summary()
            print(f"Service health summary: {health_summary}")
            
            # Get active alerts
            active_alerts = PerformanceAlert.get_active_alerts()
            print(f"Found {len(active_alerts)} active alerts")
            
            print("\n🎉 All performance monitoring tests passed!")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_performance_models()
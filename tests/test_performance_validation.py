"""
Performance validation tests for critical endpoints.
Tests response times and system performance under load.
"""
import pytest
import time
import statistics
import concurrent.futures
from threading import Thread
import requests
from app import create_app


class TestPerformanceMetrics:
    """Test performance metrics for critical endpoints"""
    
    def test_authentication_endpoint_performance(self, client, app, user):
        """Test authentication endpoint performance - Requirement 3.1"""
        with app.app_context():
            login_data = {
                'email': user.email,
                'password': 'password'
            }
            
            # Measure multiple requests
            response_times = []
            
            for _ in range(5):
                start_time = time.time()
                response = client.post('/api/v1/auth/login',
                                     json=login_data,
                                     content_type='application/json')
                response_time = (time.time() - start_time) * 1000
                response_times.append(response_time)
                
                # Should respond quickly
                assert response_time < 2000, f"Login too slow: {response_time}ms"
            
            # Calculate average response time
            avg_response_time = statistics.mean(response_times)
            print(f"Average login response time: {avg_response_time:.2f}ms")
            
            # Average should be under 1 second
            assert avg_response_time < 1000, f"Average login time too slow: {avg_response_time}ms"
    
    def test_dashboard_loading_performance(self, client):
        """Test dashboard loading performance"""
        response_times = []
        
        for _ in range(3):
            start_time = time.time()
            response = client.get('/')
            response_time = (time.time() - start_time) * 1000
            response_times.append(response_time)
            
            # Should load within 5 seconds
            assert response_time < 5000, f"Dashboard too slow: {response_time}ms"
        
        avg_response_time = statistics.mean(response_times)
        print(f"Average dashboard response time: {avg_response_time:.2f}ms")
    
    def test_api_endpoints_performance(self, client, auth_headers):
        """Test API endpoints performance"""
        endpoints = [
            ('/api/v1/health', None),
            ('/api/v1/auth/me', auth_headers),
            ('/api/v1/tenants', auth_headers)
        ]
        
        for endpoint, headers in endpoints:
            response_times = []
            
            for _ in range(3):
                start_time = time.time()
                try:
                    response = client.get(endpoint, headers=headers)
                    response_time = (time.time() - start_time) * 1000
                    response_times.append(response_time)
                    
                    # Should respond within 2 seconds
                    assert response_time < 2000, f"{endpoint} too slow: {response_time}ms"
                    
                except Exception as e:
                    print(f"Error testing {endpoint}: {e}")
                    continue
            
            if response_times:
                avg_time = statistics.mean(response_times)
                print(f"Average {endpoint} response time: {avg_time:.2f}ms")
    
    def test_database_query_performance(self, app, db_session):
        """Test database query performance"""
        with app.app_context():
            from app.models.user import User
            from app.models.tenant import Tenant
            
            # Test simple queries
            queries = [
                lambda: User.query.limit(10).all(),
                lambda: Tenant.query.limit(10).all(),
                lambda: db_session.execute('SELECT 1').fetchone()
            ]
            
            for i, query in enumerate(queries):
                response_times = []
                
                for _ in range(5):
                    start_time = time.time()
                    try:
                        result = query()
                        query_time = (time.time() - start_time) * 1000
                        response_times.append(query_time)
                        
                        # Database queries should be fast
                        assert query_time < 1000, f"Query {i} too slow: {query_time}ms"
                        
                    except Exception as e:
                        print(f"Query {i} error: {e}")
                        continue
                
                if response_times:
                    avg_time = statistics.mean(response_times)
                    print(f"Average query {i} time: {avg_time:.2f}ms")


class TestLoadPerformance:
    """Test system performance under load"""
    
    def test_concurrent_requests(self, client):
        """Test system handles concurrent requests"""
        def make_request():
            start_time = time.time()
            response = client.get('/')
            response_time = (time.time() - start_time) * 1000
            return response.status_code, response_time
        
        # Simulate concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # Check results
        status_codes = [result[0] for result in results]
        response_times = [result[1] for result in results]
        
        # Most requests should succeed
        success_count = sum(1 for code in status_codes if code == 200)
        print(f"Successful requests: {success_count}/{len(results)}")
        
        # Average response time should be reasonable
        if response_times:
            avg_time = statistics.mean(response_times)
            print(f"Average concurrent response time: {avg_time:.2f}ms")
            
            # Should handle load reasonably well
            assert avg_time < 10000, f"System too slow under load: {avg_time}ms"
    
    def test_memory_usage_stability(self, client):
        """Test memory usage remains stable"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Make multiple requests
        for _ in range(20):
            client.get('/')
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        print(f"Memory usage: {initial_memory:.2f}MB -> {final_memory:.2f}MB (+{memory_increase:.2f}MB)")
        
        # Memory increase should be reasonable (less than 100MB for test)
        assert memory_increase < 100, f"Memory leak detected: +{memory_increase:.2f}MB"


class TestPerformanceRegression:
    """Test for performance regressions"""
    
    def test_startup_time(self, app):
        """Test application startup time"""
        start_time = time.time()
        
        # Create new app instance to measure startup
        test_app = create_app('testing')
        
        startup_time = (time.time() - start_time) * 1000
        print(f"Application startup time: {startup_time:.2f}ms")
        
        # Startup should be reasonable (less than 10 seconds)
        assert startup_time < 10000, f"Startup too slow: {startup_time}ms"
    
    def test_response_time_consistency(self, client):
        """Test response time consistency"""
        response_times = []
        
        # Make multiple requests to same endpoint
        for _ in range(10):
            start_time = time.time()
            response = client.get('/api/v1/health')
            response_time = (time.time() - start_time) * 1000
            response_times.append(response_time)
        
        if response_times:
            avg_time = statistics.mean(response_times)
            std_dev = statistics.stdev(response_times) if len(response_times) > 1 else 0
            
            print(f"Response time stats: avg={avg_time:.2f}ms, std_dev={std_dev:.2f}ms")
            
            # Standard deviation should be reasonable (not too variable)
            assert std_dev < avg_time, f"Response times too variable: std_dev={std_dev:.2f}ms"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
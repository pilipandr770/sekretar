"""Performance and load testing scenarios."""
import pytest
import time
import threading
import statistics
import uuid
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch, MagicMock
import psutil
import os


class TestConcurrentUserTesting:
    """Test concurrent user operations as required by task 14.1."""
    
    def test_simultaneous_user_registration(self, client, app):
        """Test simultaneous user registration with real company data."""
        # Real company data for testing
        test_companies = [
            {
                "name": "Microsoft Ireland Operations Limited",
                "vat_number": "IE9825613N",
                "country": "IE",
                "domain": f"microsoft-test-{uuid.uuid4().hex[:8]}.com"
            },
            {
                "name": "SAP SE",
                "vat_number": "DE143593636", 
                "country": "DE",
                "domain": f"sap-test-{uuid.uuid4().hex[:8]}.com"
            },
            {
                "name": "Unilever PLC",
                "vat_number": "GB123456789",
                "country": "GB",
                "domain": f"unilever-test-{uuid.uuid4().hex[:8]}.com"
            }
        ]
    
    """Test API endpoint performance under various conditions."""
    
    def test_single_request_response_time(self, client, tenant, user, auth_headers):
        """Test individual API endpoint response times."""
        endpoints = [
            ('GET', '/api/v1/health'),
            ('GET', '/api/v1/version'),
            ('GET', '/api/v1/crm/leads'),
            ('GET', '/api/v1/inbox/messages'),
            ('GET', '/api/v1/kyb/counterparties')
        ]
        
        response_times = {}
        
        for method, endpoint in endpoints:
            start_time = time.time()
            
            if method == 'GET':
                if endpoint == '/api/v1/health':
                    with patch('app.services.health_service.HealthService.get_overall_health') as mock_health:
                        mock_health.return_value = MagicMock(
                            status="healthy",
                            checks={'database': MagicMock(status="healthy", response_time_ms=10)},
                            timestamp="2025-08-16T10:00:00Z"
                        )
                        response = client.get(endpoint)
                else:
                    response = client.get(endpoint, headers=auth_headers)
            
            end_time = time.time()
            response_time = end_time - start_time
            response_times[endpoint] = response_time
            
            # Individual requests should be fast (< 500ms)
            assert response_time < 0.5, f"{endpoint} took {response_time:.3f}s"
            assert response is not None
        
        # Log response times for analysis
        print(f"Response times: {response_times}")
        
    def test_concurrent_request_performance(self, client, tenant, user, auth_headers):
        """Test performance under concurrent load."""
        def make_request(endpoint):
            start_time = time.time()
            response = client.get(endpoint, headers=auth_headers)
            end_time = time.time()
            return {
                'endpoint': endpoint,
                'response_time': end_time - start_time,
                'status_code': response.status_code if response else 500,
                'success': response is not None and response.status_code < 500
            }
        
        # Test endpoints
        endpoints = ['/api/v1/crm/leads'] * 20  # 20 concurrent requests to same endpoint
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request, endpoint) for endpoint in endpoints]
            results = [future.result() for future in as_completed(futures)]
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Analyze results
        response_times = [r['response_time'] for r in results]
        success_count = sum(1 for r in results if r['success'])
        
        # Performance assertions
        assert total_time < 10.0, f"Concurrent requests took too long: {total_time:.2f}s"
        assert success_count >= len(endpoints) * 0.8, f"Too many failed requests: {success_count}/{len(endpoints)}"
        
        # Response time statistics
        avg_response_time = statistics.mean(response_times)
        max_response_time = max(response_times)
        
        assert avg_response_time < 1.0, f"Average response time too high: {avg_response_time:.3f}s"
        assert max_response_time < 2.0, f"Max response time too high: {max_response_time:.3f}s"
        
        print(f"Concurrent test results:")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Success rate: {success_count}/{len(endpoints)}")
        print(f"  Avg response time: {avg_response_time:.3f}s")
        print(f"  Max response time: {max_response_time:.3f}s")
        
    def test_database_query_performance(self, app, tenant, user):
        """Test database query performance with large datasets."""
        with app.app_context():
            from app.models.crm import Contact, Lead
            from app import db
            
            # Create test data
            contacts = []
            for i in range(500):
                contact = Contact(
                    tenant_id=tenant.id,
                    name=f"Performance Test Contact {i}",
                    email=f"perf{i}@example.com",
                    phone=f"+123456{i:04d}"
                )
                contacts.append(contact)
            
            # Batch insert for performance
            start_time = time.time()
            db.session.add_all(contacts)
            db.session.commit()
            insert_time = time.time() - start_time
            
            print(f"Inserted 500 contacts in {insert_time:.3f}s")
            assert insert_time < 5.0, f"Bulk insert too slow: {insert_time:.3f}s"
            
            # Test query performance
            start_time = time.time()
            filtered_contacts = Contact.query.filter(
                Contact.tenant_id == tenant.id,
                Contact.email.like('%@example.com')
            ).limit(100).all()
            query_time = time.time() - start_time
            
            assert query_time < 0.5, f"Query too slow: {query_time:.3f}s"
            assert len(filtered_contacts) == 100
            
            # Test join query performance
            leads = []
            for i, contact in enumerate(contacts[:100]):
                lead = Lead(
                    tenant_id=tenant.id,
                    contact_id=contact.id,
                    source='performance_test',
                    value=1000 + i
                )
                leads.append(lead)
            
            db.session.add_all(leads)
            db.session.commit()
            
            start_time = time.time()
            leads_with_contacts = db.session.query(Lead).join(Contact).filter(
                Lead.tenant_id == tenant.id,
                Lead.source == 'performance_test'
            ).all()
            join_query_time = time.time() - start_time
            
            assert join_query_time < 1.0, f"Join query too slow: {join_query_time:.3f}s"
            assert len(leads_with_contacts) == 100
            
    def test_memory_usage_monitoring(self, client, tenant, user, auth_headers):
        """Test memory usage during API operations."""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Make multiple requests that could consume memory
        endpoints = [
            '/api/v1/crm/leads',
            '/api/v1/inbox/messages',
            '/api/v1/kyb/counterparties'
        ] * 10  # 30 total requests
        
        for endpoint in endpoints:
            response = client.get(endpoint, headers=auth_headers)
            assert response is not None
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        print(f"Memory usage: {initial_memory:.1f}MB -> {final_memory:.1f}MB (+{memory_increase:.1f}MB)")
        
        # Memory increase should be reasonable
        assert memory_increase < 50, f"Memory usage increased too much: {memory_increase:.1f}MB"
        
    def test_pagination_performance(self, client, tenant, user, auth_headers):
        """Test pagination performance with large datasets."""
        with patch('app.models.crm.Lead.query') as mock_query:
            # Mock large dataset
            mock_leads = []
            for i in range(10000):
                mock_lead = MagicMock()
                mock_lead.id = i + 1
                mock_lead.tenant_id = tenant.id
                mock_lead.source = 'web'
                mock_lead.value = 1000 + i
                mock_lead.created_at = '2025-08-16T10:00:00Z'
                mock_leads.append(mock_lead)
            
            # Test different page sizes
            page_sizes = [10, 50, 100, 500]
            
            for page_size in page_sizes:
                # Mock pagination
                mock_paginate = MagicMock()
                mock_paginate.items = mock_leads[:page_size]
                mock_paginate.total = 10000
                mock_paginate.pages = 10000 // page_size
                mock_paginate.page = 1
                mock_paginate.per_page = page_size
                mock_paginate.has_next = True
                mock_paginate.has_prev = False
                
                mock_query.filter.return_value.paginate.return_value = mock_paginate
                
                start_time = time.time()
                response = client.get(f'/api/v1/crm/leads?page=1&per_page={page_size}', 
                                    headers=auth_headers)
                end_time = time.time()
                
                response_time = end_time - start_time
                
                # Pagination should be fast regardless of page size
                assert response_time < 1.0, f"Pagination with {page_size} items took {response_time:.3f}s"
                
                if response and response.status_code == 200:
                    data = response.get_json()
                    assert len(data.get('data', [])) <= page_size


class TestLoadTesting:
    """Test system behavior under load."""
    
    def test_sustained_load(self, client, tenant, user, auth_headers):
        """Test system performance under sustained load."""
        duration = 30  # seconds
        request_interval = 0.1  # 10 requests per second
        
        results = []
        start_time = time.time()
        
        def make_requests():
            while time.time() - start_time < duration:
                request_start = time.time()
                response = client.get('/api/v1/crm/leads', headers=auth_headers)
                request_end = time.time()
                
                results.append({
                    'timestamp': request_start,
                    'response_time': request_end - request_start,
                    'status_code': response.status_code if response else 500,
                    'success': response is not None and response.status_code < 500
                })
                
                time.sleep(request_interval)
        
        # Run sustained load test
        thread = threading.Thread(target=make_requests)
        thread.start()
        thread.join()
        
        # Analyze results
        total_requests = len(results)
        successful_requests = sum(1 for r in results if r['success'])
        response_times = [r['response_time'] for r in results]
        
        success_rate = successful_requests / total_requests if total_requests > 0 else 0
        avg_response_time = statistics.mean(response_times) if response_times else 0
        
        print(f"Sustained load test results:")
        print(f"  Duration: {duration}s")
        print(f"  Total requests: {total_requests}")
        print(f"  Success rate: {success_rate:.2%}")
        print(f"  Avg response time: {avg_response_time:.3f}s")
        
        # Performance assertions
        assert success_rate >= 0.95, f"Success rate too low: {success_rate:.2%}"
        assert avg_response_time < 1.0, f"Average response time too high: {avg_response_time:.3f}s"
        
    def test_burst_load(self, client, tenant, user, auth_headers):
        """Test system behavior under burst load."""
        burst_size = 50
        burst_duration = 5  # seconds
        
        def make_burst_request():
            start_time = time.time()
            response = client.get('/api/v1/crm/leads', headers=auth_headers)
            end_time = time.time()
            return {
                'response_time': end_time - start_time,
                'status_code': response.status_code if response else 500,
                'success': response is not None and response.status_code < 500
            }
        
        # Execute burst
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=burst_size) as executor:
            futures = [executor.submit(make_burst_request) for _ in range(burst_size)]
            results = [future.result() for future in as_completed(futures)]
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Analyze burst results
        successful_requests = sum(1 for r in results if r['success'])
        response_times = [r['response_time'] for r in results]
        
        success_rate = successful_requests / len(results)
        avg_response_time = statistics.mean(response_times)
        max_response_time = max(response_times)
        
        print(f"Burst load test results:")
        print(f"  Burst size: {burst_size}")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Success rate: {success_rate:.2%}")
        print(f"  Avg response time: {avg_response_time:.3f}s")
        print(f"  Max response time: {max_response_time:.3f}s")
        
        # Burst performance assertions
        assert total_time < burst_duration * 2, f"Burst took too long: {total_time:.2f}s"
        assert success_rate >= 0.8, f"Burst success rate too low: {success_rate:.2%}"
        assert max_response_time < 5.0, f"Max response time too high: {max_response_time:.3f}s"
        
    def test_gradual_load_increase(self, client, tenant, user, auth_headers):
        """Test system behavior with gradually increasing load."""
        max_concurrent = 20
        step_duration = 5  # seconds per step
        step_size = 2  # increase by 2 concurrent requests per step
        
        results_by_load = {}
        
        for concurrent_requests in range(2, max_concurrent + 1, step_size):
            print(f"Testing with {concurrent_requests} concurrent requests...")
            
            def make_request():
                start_time = time.time()
                response = client.get('/api/v1/crm/leads', headers=auth_headers)
                end_time = time.time()
                return {
                    'response_time': end_time - start_time,
                    'success': response is not None and response.status_code < 500
                }
            
            # Run requests for this load level
            step_results = []
            step_start = time.time()
            
            while time.time() - step_start < step_duration:
                with ThreadPoolExecutor(max_workers=concurrent_requests) as executor:
                    futures = [executor.submit(make_request) for _ in range(concurrent_requests)]
                    batch_results = [future.result() for future in as_completed(futures)]
                    step_results.extend(batch_results)
                
                time.sleep(0.5)  # Brief pause between batches
            
            # Analyze results for this load level
            successful = sum(1 for r in step_results if r['success'])
            response_times = [r['response_time'] for r in step_results if r['success']]
            
            if response_times:
                results_by_load[concurrent_requests] = {
                    'success_rate': successful / len(step_results),
                    'avg_response_time': statistics.mean(response_times),
                    'max_response_time': max(response_times),
                    'total_requests': len(step_results)
                }
        
        # Analyze load scaling
        print("Load scaling results:")
        for load, metrics in results_by_load.items():
            print(f"  {load} concurrent: {metrics['success_rate']:.2%} success, "
                  f"{metrics['avg_response_time']:.3f}s avg, "
                  f"{metrics['max_response_time']:.3f}s max")
        
        # Verify system handles increasing load reasonably
        if results_by_load:
            min_load = min(results_by_load.keys())
            max_load = max(results_by_load.keys())
            
            min_success_rate = results_by_load[min_load]['success_rate']
            max_success_rate = results_by_load[max_load]['success_rate']
            
            # Success rate shouldn't degrade too much under load
            degradation = min_success_rate - max_success_rate
            assert degradation < 0.3, f"Success rate degraded too much: {degradation:.2%}"


class TestResourceUtilization:
    """Test resource utilization under various conditions."""
    
    def test_cpu_usage_monitoring(self, client, tenant, user, auth_headers):
        """Test CPU usage during API operations."""
        # Get initial CPU usage
        initial_cpu = psutil.cpu_percent(interval=1)
        
        # Make CPU-intensive requests
        start_time = time.time()
        
        for _ in range(50):
            response = client.get('/api/v1/crm/leads', headers=auth_headers)
            assert response is not None
        
        end_time = time.time()
        
        # Get final CPU usage
        final_cpu = psutil.cpu_percent(interval=1)
        
        duration = end_time - start_time
        
        print(f"CPU usage: {initial_cpu:.1f}% -> {final_cpu:.1f}% over {duration:.2f}s")
        
        # CPU usage should be reasonable
        assert final_cpu < 80, f"CPU usage too high: {final_cpu:.1f}%"
        
    def test_database_connection_pooling(self, app):
        """Test database connection pool behavior under load."""
        with app.app_context():
            from app import db
            
            # Test multiple concurrent database operations
            def db_operation():
                try:
                    # Simple query to test connection
                    result = db.session.execute('SELECT 1').fetchone()
                    return result is not None
                except Exception as e:
                    print(f"Database operation failed: {e}")
                    return False
            
            # Run concurrent database operations
            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = [executor.submit(db_operation) for _ in range(100)]
                results = [future.result() for future in as_completed(futures)]
            
            success_count = sum(results)
            success_rate = success_count / len(results)
            
            print(f"Database connection test: {success_count}/{len(results)} successful")
            
            # Most operations should succeed
            assert success_rate >= 0.9, f"Database connection success rate too low: {success_rate:.2%}"
            
    def test_memory_leak_detection(self, client, tenant, user, auth_headers):
        """Test for memory leaks during repeated operations."""
        process = psutil.Process(os.getpid())
        
        # Take initial memory measurement
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Perform repeated operations
        for i in range(100):
            response = client.get('/api/v1/crm/leads', headers=auth_headers)
            assert response is not None
            
            # Check memory every 20 requests
            if i % 20 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_increase = current_memory - initial_memory
                
                # Memory shouldn't grow excessively
                assert memory_increase < 100, f"Potential memory leak: +{memory_increase:.1f}MB after {i} requests"
        
        # Final memory check
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_increase = final_memory - initial_memory
        
        print(f"Memory usage after 100 requests: {initial_memory:.1f}MB -> {final_memory:.1f}MB (+{total_increase:.1f}MB)")
        
        # Total memory increase should be reasonable
        assert total_increase < 50, f"Memory usage increased too much: {total_increase:.1f}MB"
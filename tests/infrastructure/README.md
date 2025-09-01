# Comprehensive Testing Infrastructure

This directory contains the comprehensive testing infrastructure for the AI Secretary platform. The infrastructure is designed to conduct thorough system testing using real company data from public sources.

## Overview

The comprehensive testing infrastructure consists of several key components:

1. **Test Orchestrator** - Coordinates test execution and generates reports
2. **Test Environment** - Manages isolated test environment setup
3. **Test Data Manager** - Collects and validates real company data
4. **Test Runner** - Main entry point for executing tests
5. **Configuration** - Centralized configuration management

## Architecture

```
tests/infrastructure/
├── __init__.py                 # Package initialization
├── test_orchestrator.py        # Main test coordination
├── test_environment.py         # Environment management
├── test_data_manager.py        # Real data collection
├── models.py                   # Data models
├── config.py                   # Configuration
├── runner.py                   # Main entry point
└── README.md                   # This file
```

## Key Features

### Real Company Data Integration

The infrastructure collects real company data from public sources:

- **VIES Database**: EU VAT number validation
- **GLEIF Database**: LEI code validation and corporate data
- **Companies House**: UK company information
- **OpenCorporates**: International company database

### Isolated Test Environment

- Dedicated test database (SQLite or PostgreSQL)
- Isolated Redis instance for caching and queues
- Temporary file system for test artifacts
- Automatic cleanup after test execution

### Comprehensive Reporting

- Detailed test execution reports
- Issue identification and categorization
- Improvement plans with prioritized action items
- User action recommendations
- Performance metrics and analysis

### Test Categories

The infrastructure supports multiple test categories:

1. **User Registration** - Complete user onboarding flow
2. **API Endpoints** - REST API functionality testing
3. **CRM Functionality** - Contact and lead management
4. **KYB Monitoring** - Know Your Business compliance
5. **AI Agents** - Intelligent agent functionality
6. **Billing** - Payment and subscription management
7. **Calendar** - Google Calendar integration
8. **Knowledge** - Document processing and search
9. **Communication** - Multi-channel messaging
10. **Integration** - External service integration
11. **Performance** - Load and stress testing
12. **Security** - Security vulnerability testing

## Usage

### Basic Usage

```python
from tests.infrastructure.runner import run_comprehensive_tests

# Run all tests with default configuration
report = await run_comprehensive_tests()

# Print summary
print(f"Overall Status: {report.overall_status}")
print(f"Total Tests: {sum(suite.total_tests for suite in report.suite_results)}")
print(f"Passed: {sum(suite.passed for suite in report.suite_results)}")
```

### Command Line Usage

```bash
# Run comprehensive tests
python tests/infrastructure/runner.py

# Run with verbose logging
python tests/infrastructure/runner.py --verbose

# Run with parallel execution
python tests/infrastructure/runner.py --parallel

# Skip cleanup for debugging
python tests/infrastructure/runner.py --no-cleanup
```

### Configuration

The infrastructure can be configured through environment variables:

```bash
# Test environment
export TEST_DATABASE_URL="postgresql://user:pass@localhost/test_db"
export TEST_REDIS_URL="redis://localhost:6380/0"

# External API configuration
export VIES_API_URL="https://ec.europa.eu/taxation_customs/vies/services/checkVatService"
export GLEIF_API_URL="https://api.gleif.org/api/v1"

# Test execution settings
export MAX_EXECUTION_TIME_MINUTES="120"
export CONCURRENT_USERS="10"
export DETAILED_LOGGING="true"
```

## Real Company Data

The infrastructure uses real company data from public sources for realistic testing:

### Sample Companies

- **Microsoft Ireland Operations Limited** (IE9825613N)
- **SAP SE** (DE143593636)
- **Unilever PLC** (GB440861235)
- **ING Groep N.V.** (NL002491986B04)
- **Nokia Corporation** (FI09140687)
- **LVMH Moët Hennessy Louis Vuitton SE** (FR40775670417)

### Data Validation

All company data is validated through:

1. **VAT Number Validation** - VIES service verification
2. **LEI Code Validation** - GLEIF database lookup
3. **Data Consistency Checks** - Cross-reference validation
4. **Freshness Verification** - Regular data updates

## Test Execution Flow

1. **Environment Setup**
   - Create isolated test database
   - Start dedicated Redis instance
   - Prepare test data directories

2. **Data Preparation**
   - Collect real company data from public APIs
   - Validate data integrity and freshness
   - Cache data for test execution

3. **Test Execution**
   - Execute tests in defined order
   - Collect performance metrics
   - Track issues and failures

4. **Analysis and Reporting**
   - Analyze test results
   - Identify critical issues
   - Generate improvement plans
   - Create user action items

5. **Cleanup**
   - Clean up test environment
   - Save test artifacts
   - Generate final reports

## Report Structure

The comprehensive report includes:

### Executive Summary
- Overall system health status
- Total execution time
- High-level test statistics

### Detailed Results
- Test suite breakdown
- Individual test results
- Performance metrics
- Error analysis

### Issue Analysis
- Critical issues requiring immediate attention
- Issue categorization by severity and type
- Affected components identification
- Reproduction steps

### Improvement Plan
- Prioritized action items
- Estimated effort and timeline
- Dependencies and prerequisites
- Acceptance criteria

### User Actions
- Immediate actions required
- Configuration changes needed
- Manual verification steps
- Follow-up recommendations

## Performance Metrics

The infrastructure tracks various performance metrics:

- **Response Times** - API endpoint response times
- **Throughput** - Requests per second capacity
- **Error Rates** - Failure rate analysis
- **Resource Usage** - CPU, memory, and database utilization
- **Concurrency** - Multi-user performance testing

## Security Testing

Security testing includes:

- **Authentication** - Login/logout flow security
- **Authorization** - Role-based access control
- **Input Validation** - SQL injection and XSS prevention
- **Data Protection** - PII handling and encryption
- **Session Management** - Token security and expiration

## Integration Testing

External service integration testing:

- **Payment Processing** - Stripe webhook handling
- **OAuth Flows** - Google OAuth integration
- **Email Services** - SMTP configuration testing
- **Calendar Sync** - Google Calendar integration
- **Messaging** - Telegram and Signal integration

## Troubleshooting

### Common Issues

1. **Database Connection Failures**
   - Check database URL configuration
   - Verify database server is running
   - Ensure proper permissions

2. **Redis Connection Issues**
   - Verify Redis server availability
   - Check port configuration
   - Ensure Redis is not password protected

3. **External API Rate Limits**
   - Monitor API usage quotas
   - Implement proper rate limiting
   - Use caching to reduce API calls

4. **Test Environment Cleanup**
   - Ensure proper cleanup after tests
   - Check for orphaned processes
   - Verify temporary files are removed

### Debug Mode

Enable debug mode for detailed logging:

```bash
export DETAILED_LOGGING="true"
export LOG_LEVEL="DEBUG"
python tests/infrastructure/runner.py --verbose
```

## Contributing

When adding new tests to the infrastructure:

1. **Follow the Test Pattern**
   - Use async functions for test implementations
   - Accept `context` and `real_company_data` parameters
   - Return structured results with success/failure status

2. **Register Test Suites**
   - Add tests to appropriate categories
   - Use descriptive test names
   - Include proper error handling

3. **Use Real Data**
   - Leverage the provided company data
   - Validate data before use
   - Handle API failures gracefully

4. **Document Tests**
   - Add docstrings to test functions
   - Document expected behavior
   - Include troubleshooting notes

## Dependencies

The infrastructure requires:

- **Python 3.8+**
- **asyncio** for asynchronous execution
- **httpx** for HTTP client functionality
- **redis** for Redis connectivity
- **psycopg2** for PostgreSQL support
- **pytest** for test framework integration

## License

This testing infrastructure is part of the AI Secretary platform and follows the same licensing terms as the main project.
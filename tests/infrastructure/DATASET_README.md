# Comprehensive Test Dataset System

This system provides a comprehensive test dataset with real company data from different EU countries, including valid VAT numbers and LEI codes for realistic testing of the AI Secretary platform.

## Overview

The comprehensive test dataset system consists of several components:

1. **Test Dataset Builder** - Collects and builds comprehensive dataset
2. **Data Validation & Refresh Manager** - Validates and refreshes data
3. **CLI Tool** - Command-line interface for dataset management
4. **Test Suite** - Automated tests for the dataset system

## Features

### Real Company Data Collection
- Companies from 16+ EU countries (DE, FR, IT, ES, NL, BE, AT, IE, FI, SE, DK, PL, CZ, HU, PT, GB)
- Mix of large corporations and SMEs
- Valid VAT numbers verified through VIES
- Valid LEI codes verified through GLEIF
- Industry and size distribution

### Data Validation & Quality
- Automated VAT number validation via VIES API
- LEI code validation via GLEIF API
- Data freshness monitoring
- Quality metrics and reporting
- Failed validation retry mechanisms

### Dataset Management
- Persistent dataset storage
- Incremental data refresh
- Filtering and selection capabilities
- Export functionality
- Comprehensive reporting

## Components

### 1. ComprehensiveTestDatasetBuilder

Main class for building the comprehensive test dataset.

```python
from tests.infrastructure.test_dataset_builder import ComprehensiveTestDatasetBuilder
from tests.infrastructure.config import ComprehensiveTestConfig

config = ComprehensiveTestConfig.get_config()['data_manager']
builder = ComprehensiveTestDatasetBuilder(config)

await builder.initialize()
dataset = await builder.build_comprehensive_dataset()
```

**Key Methods:**
- `build_comprehensive_dataset()` - Build complete dataset
- `get_companies_by_criteria()` - Filter companies by various criteria
- `get_dataset_summary()` - Get dataset statistics
- `refresh_dataset()` - Refresh stale data

### 2. DataValidationRefreshManager

Manages validation and refresh of company data.

```python
from tests.infrastructure.data_validation_refresh import DataValidationRefreshManager

manager = DataValidationRefreshManager(config)
await manager.initialize()

# Validate dataset
validation_result = await manager.validate_dataset(dataset)

# Refresh stale data
refreshed_dataset = await manager.refresh_stale_data(dataset)

# Get quality report
quality_report = manager.get_data_quality_report(dataset)
```

**Key Methods:**
- `validate_dataset()` - Validate entire dataset
- `refresh_stale_data()` - Refresh stale company data
- `get_validation_statistics()` - Get validation statistics
- `get_data_quality_report()` - Generate quality report

### 3. Dataset CLI Tool

Command-line interface for dataset management.

```bash
# Build comprehensive dataset
python tests/infrastructure/dataset_cli.py build

# Validate existing dataset
python tests/infrastructure/dataset_cli.py validate --detailed

# Show dataset summary
python tests/infrastructure/dataset_cli.py summary

# Show validation statistics
python tests/infrastructure/dataset_cli.py stats --show-failures

# Generate quality report
python tests/infrastructure/dataset_cli.py quality

# List companies with filtering
python tests/infrastructure/dataset_cli.py list --countries DE,FR --industries Technology

# Export dataset
python tests/infrastructure/dataset_cli.py export dataset_export.json --include-validation-details

# Refresh stale data
python tests/infrastructure/dataset_cli.py refresh --retry-failed
```

## Configuration

The system is configured through `ComprehensiveTestConfig` in `tests/infrastructure/config.py`.

### Key Configuration Options

```python
TEST_DATA_MANAGER = {
    'vies_api_url': 'https://ec.europa.eu/taxation_customs/vies/services/checkVatService',
    'gleif_api_url': 'https://api.gleif.org/api/v1',
    'rate_limits': {
        'vies': 10,      # requests per minute
        'gleif': 60,     # requests per minute
    },
    'timeout_seconds': 30,
    'retry_attempts': 3,
    'cache_duration_hours': 24
}
```

### Environment Variables

```bash
# API Configuration
VIES_API_URL=https://ec.europa.eu/taxation_customs/vies/services/checkVatService
GLEIF_API_URL=https://api.gleif.org/api/v1

# Rate Limiting
VIES_RATE_LIMIT=10
GLEIF_RATE_LIMIT=60

# Validation Configuration
DATA_CACHE_DURATION_HOURS=24
API_TIMEOUT_SECONDS=30
API_RETRY_ATTEMPTS=3
```

## Dataset Structure

### CompanyData Model

```python
@dataclass
class CompanyData:
    name: str                           # Company name
    vat_number: Optional[str]           # VAT number (e.g., "DE143593636")
    lei_code: Optional[str]             # LEI code (e.g., "529900T8BM49AURSDO55")
    country_code: str                   # ISO country code (e.g., "DE")
    address: Optional[str]              # Company address
    industry: Optional[str]             # Industry sector
    size: Optional[str]                 # Company size (Large, Medium, Small)
    source: str                         # Data source identifier
    validation_status: str              # VALID, INVALID, PENDING, etc.
    last_validated: Optional[datetime]  # Last validation timestamp
    additional_data: Dict[str, Any]     # Validation results and metadata
```

### Sample Companies

The dataset includes companies such as:

- **SAP SE** (Germany) - Technology, Large
- **LVMH** (France) - Luxury Goods, Large  
- **ING Groep N.V.** (Netherlands) - Financial Services, Large
- **Microsoft Ireland** (Ireland) - Technology, Large
- **Nokia Corporation** (Finland) - Technology, Large
- **Spotify AB** (Sweden) - Technology, Large
- **Banco Santander** (Spain) - Financial Services, Large
- **Unilever PLC** (UK) - Consumer Goods, Large

## Usage Examples

### Basic Dataset Building

```python
import asyncio
from tests.infrastructure.test_dataset_builder import ComprehensiveTestDatasetBuilder
from tests.infrastructure.config import ComprehensiveTestConfig

async def build_dataset():
    config = ComprehensiveTestConfig.get_config()['data_manager']
    builder = ComprehensiveTestDatasetBuilder(config)
    
    await builder.initialize()
    try:
        # Build comprehensive dataset
        dataset = await builder.build_comprehensive_dataset()
        print(f"Built dataset with {len(dataset)} companies")
        
        # Get summary
        summary = builder.get_dataset_summary()
        print(f"Countries: {summary['countries']}")
        print(f"Industries: {summary['industries']}")
        
    finally:
        await builder.cleanup()

asyncio.run(build_dataset())
```

### Dataset Validation

```python
async def validate_dataset():
    config = ComprehensiveTestConfig.get_config()['data_manager']
    
    builder = ComprehensiveTestDatasetBuilder(config)
    validator = DataValidationRefreshManager(config)
    
    await builder.initialize()
    await validator.initialize()
    
    try:
        # Load dataset
        dataset = builder.comprehensive_dataset
        if not dataset:
            dataset = await builder.build_comprehensive_dataset()
        
        # Validate dataset
        result = await validator.validate_dataset(dataset)
        print(f"Validation completed: {result['statistics']}")
        
        # Generate quality report
        quality_report = validator.get_data_quality_report(dataset)
        print(f"Data quality issues: {len(quality_report['issues'])}")
        
    finally:
        await builder.cleanup()
        await validator.cleanup()

asyncio.run(validate_dataset())
```

### Filtering Companies

```python
# Get German technology companies
german_tech = builder.get_companies_by_criteria(
    countries=['DE'],
    industries=['Technology'],
    validation_status=['VALID'],
    limit=10
)

# Get large companies with valid VAT numbers
large_companies = builder.get_companies_by_criteria(
    sizes=['Large'],
    limit=20
)

# Get companies from specific countries
eu_companies = builder.get_companies_by_criteria(
    countries=['DE', 'FR', 'IT', 'ES', 'NL']
)
```

## Data Sources

### VIES (VAT Information Exchange System)
- **URL**: https://ec.europa.eu/taxation_customs/vies/
- **Purpose**: Validate EU VAT numbers
- **Rate Limit**: 10 requests per minute
- **Coverage**: All EU member states

### GLEIF (Global Legal Entity Identifier Foundation)
- **URL**: https://api.gleif.org/
- **Purpose**: Validate LEI codes and get corporate data
- **Rate Limit**: 60 requests per minute
- **Coverage**: Global LEI database

## Quality Metrics

The system tracks various quality metrics:

### Data Completeness
- Percentage of companies with VAT numbers
- Percentage of companies with LEI codes
- Percentage of companies with addresses
- Percentage of companies with industry classification

### Validation Coverage
- VAT validation coverage percentage
- LEI validation coverage percentage
- VAT validation success rate
- LEI validation success rate

### Data Freshness
- Percentage of fresh data (within configured age limit)
- Percentage of stale data (older than age limit)
- Percentage of data without validation timestamps

## Error Handling

### Rate Limiting
- Automatic rate limiting for external APIs
- Exponential backoff for failed requests
- Request queuing and batching

### Validation Failures
- Retry mechanism for failed validations
- Tracking of persistent failures
- Detailed error logging and reporting

### Data Quality Issues
- Automatic issue detection and categorization
- Severity classification (Critical, High, Medium, Low)
- Remediation suggestions

## Testing

### Running Tests

```bash
# Run all dataset tests
pytest tests/test_comprehensive_dataset.py -v

# Run specific test
pytest tests/test_comprehensive_dataset.py::TestComprehensiveDataset::test_build_comprehensive_dataset -v

# Run with detailed logging
pytest tests/test_comprehensive_dataset.py -v -s --log-cli-level=INFO
```

### Manual Testing

```bash
# Run demonstration
python tests/test_comprehensive_dataset.py

# Test CLI functionality
python tests/infrastructure/dataset_cli.py build
python tests/infrastructure/dataset_cli.py summary
python tests/infrastructure/dataset_cli.py quality
```

## File Structure

```
tests/infrastructure/
├── test_dataset_builder.py          # Main dataset builder
├── data_validation_refresh.py       # Validation and refresh manager
├── dataset_cli.py                   # Command-line interface
├── models.py                        # Data models
├── config.py                        # Configuration
├── test_data_manager.py             # Base data manager
├── DATASET_README.md                # This documentation
└── __init__.py

tests/
├── test_comprehensive_dataset.py    # Test suite
└── conftest.py                      # Test configuration
```

## Performance Considerations

### Rate Limiting
- VIES API: 10 requests per minute
- GLEIF API: 60 requests per minute
- Automatic throttling and queuing

### Caching
- Dataset persistence to JSON files
- Validation result caching
- Configurable cache duration

### Batch Processing
- Companies processed in configurable batches
- Parallel processing where possible
- Progress tracking and reporting

## Troubleshooting

### Common Issues

1. **Rate Limit Exceeded**
   - Reduce batch size in configuration
   - Increase delays between requests
   - Check rate limit settings

2. **Validation Failures**
   - Check internet connectivity
   - Verify API endpoints are accessible
   - Review error logs for specific failures

3. **Dataset Not Loading**
   - Check file permissions
   - Verify JSON file format
   - Clear cache and rebuild

4. **Memory Issues**
   - Reduce dataset size
   - Process in smaller batches
   - Increase available memory

### Debug Mode

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or set environment variable:
```bash
export LOG_LEVEL=DEBUG
```

## Contributing

When adding new companies or data sources:

1. Update the predefined companies list in `test_dataset_builder.py`
2. Add appropriate validation logic
3. Update configuration if needed
4. Add tests for new functionality
5. Update this documentation

## Security Considerations

- Only uses publicly available company data
- No sensitive or confidential information
- Rate limiting respects API terms of service
- Validation results are cached locally only
- No personal data (PII) is collected or stored

## License

This test dataset system is part of the AI Secretary platform testing infrastructure and follows the same license terms as the main project.
# Database CLI Commands

This document describes the database initialization and management CLI commands available in the AI Secretary application.

## Overview

The database CLI commands provide tools for:
- Manual database initialization
- Database health checking and troubleshooting
- Database repair and recovery
- Database reset for development environments

## Commands

### `flask database init`

Initialize database with schema, migrations, and seed data.

**Usage:**
```bash
flask database init [OPTIONS]
```

**Options:**
- `--force` - Force initialization even if database exists
- `--skip-seeding` - Skip data seeding during initialization
- `--admin-email TEXT` - Admin user email address (default: admin@ai-secretary.com)
- `--admin-password TEXT` - Admin user password (default: admin123)

**Examples:**
```bash
# Basic initialization
flask database init

# Force reinitialize existing database
flask database init --force

# Initialize without seeding data
flask database init --skip-seeding

# Initialize with custom admin credentials
flask database init --admin-email admin@example.com --admin-password mypassword
```

### `flask database health`

Check database health and connectivity.

**Usage:**
```bash
flask database health [OPTIONS]
```

**Options:**
- `--detailed` - Show detailed health information
- `--performance` - Include performance metrics

**Examples:**
```bash
# Basic health check
flask database health

# Detailed health check with performance metrics
flask database health --detailed --performance
```

### `flask database status`

Show current database initialization status.

**Usage:**
```bash
flask database status
```

**Output includes:**
- Database connection status
- Schema existence
- Migration status
- Seeding completion status
- Database type and table count
- Overall status and suggestions

### `flask database repair`

Repair common database issues.

**Usage:**
```bash
flask database repair [OPTIONS]
```

**Options:**
- `--auto-fix` - Automatically attempt to fix issues
- `--dry-run` - Show what would be repaired without making changes

**Examples:**
```bash
# Check what repairs are needed
flask database repair --dry-run

# Automatically fix detected issues
flask database repair --auto-fix
```

### `flask database reset`

Reset database for development environments.

**Usage:**
```bash
flask database reset [OPTIONS]
```

**Options:**
- `--confirm` - Confirm the reset operation
- `--keep-data` - Keep user data, only reset schema (not yet implemented)

**Safety:**
- Only works in development environments
- Production environments are protected from reset

**Examples:**
```bash
# Reset database (requires confirmation)
flask database reset --confirm
```

### `flask database troubleshoot`

Generate comprehensive troubleshooting report.

**Usage:**
```bash
flask database troubleshoot [OPTIONS]
```

**Options:**
- `--format [json|text]` - Output format (default: text)
- `--output PATH` - Output file path

**Examples:**
```bash
# Generate text report to console
flask database troubleshoot

# Generate JSON report to file
flask database troubleshoot --format json --output report.json
```

## Common Use Cases

### First-time Setup

```bash
# Initialize database for the first time
flask database init

# Check if initialization was successful
flask database status
```

### Troubleshooting Issues

```bash
# Check database health
flask database health --detailed

# Generate troubleshooting report
flask database troubleshoot

# Attempt automatic repairs
flask database repair --auto-fix
```

### Development Reset

```bash
# Reset database in development
flask database reset --confirm

# Reinitialize after reset
flask database init
```

### Health Monitoring

```bash
# Quick health check
flask database health

# Detailed health with performance metrics
flask database health --detailed --performance

# Check current status
flask database status
```

## Error Handling

All commands include comprehensive error handling and will:
- Provide clear error messages
- Suggest resolution steps
- Exit with appropriate error codes
- Log detailed information for troubleshooting

## Security Considerations

- Reset command is disabled in production environments
- Sensitive information is masked in logs and output
- Default admin credentials should be changed after initialization
- Database connection strings are masked in status output

## Integration with Other Systems

These CLI commands integrate with:
- Database initialization system (DatabaseInitializer)
- Health validation system (HealthValidator)
- Data seeding system (DataSeeder)
- Error handling and recovery systems
- Logging and monitoring systems

## Requirements Mapping

These CLI commands fulfill the following requirements from the database initialization specification:

- **Requirement 4.4**: Database health validation and troubleshooting
- **Requirement 6.3**: Error recovery and troubleshooting tools
- **Requirement 6.4**: Manual intervention and repair options

## Examples of Output

### Status Command Output
```
📊 Database Status Report
==================================================
Database Connection: ✅
Schema Exists: ✅
Migrations Current: ✅
Seeding Complete: ✅
Last Initialization: 2025-09-18 10:00:00
Database Type: sqlite
Table Count: 25

Overall Status: ✅ READY
```

### Health Command Output
```
🏥 Checking database health...
Overall Status: ✅ HEALTHY
Checks Passed: 4/4
Database Connectivity: ✅

📋 Detailed Health Report:
Schema Integrity: ✅
Data Integrity: ✅

📊 Performance Metrics:
   • Connection Pool Size: 5
   • Active Connections: 1
   • Query Response Time: 15ms
```

### Repair Command Output
```
🔧 Checking for database issues to repair...
Found issues with status: WARNING

📋 Found 2 issues:
   1. Missing system tenant
   2. Admin user not found

🔧 Attempting automatic repairs...
✅ Database repair completed successfully!
🔧 Repairs performed:
   • Created system tenant
   • Created admin user with default credentials
```
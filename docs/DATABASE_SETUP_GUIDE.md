# Database Setup Guide

This guide explains how to set up and manage the AI Secretary database using both the new comprehensive initialization system and legacy methods for backward compatibility.

## Overview

The AI Secretary application now includes a comprehensive database initialization system that provides:

- Automatic schema creation and validation
- Migration management
- Data seeding with admin user creation
- Health checking and repair capabilities
- Environment-specific configuration
- Backward compatibility with existing setup procedures

## Quick Start

### Using the New System

The simplest way to initialize the database is using the enhanced initialization script:

```bash
# Initialize database with new system
python init_database.py

# Or use the comprehensive database manager
python scripts/database_manager.py init
```

### Using PowerShell (Windows)

```powershell
# Initialize database
.\scripts\database-manager.ps1 init

# Check database health
.\scripts\database-manager.ps1 health

# Reset database (with confirmation)
.\scripts\database-manager.ps1 reset
```

## Available Commands

### Python Scripts

#### `init_database.py`
Enhanced database initialization with new system integration:
```bash
python init_database.py
```
- Uses new initialization system when available
- Falls back to legacy method for compatibility
- Creates admin user with credentials: admin@ai-secretary.com / admin123

#### `create_admin_user.py`
Admin user creation with data seeding integration:
```bash
python create_admin_user.py
```
- Uses new data seeding system when available
- Falls back to direct database creation
- Supports both PostgreSQL and SQLite

#### `scripts/database_manager.py`
Comprehensive database management:
```bash
# Initialize database
python scripts/database_manager.py init

# Initialize with force (drops existing data)
python scripts/database_manager.py init --force

# Check database health
python scripts/database_manager.py health

# Repair database issues
python scripts/database_manager.py repair

# Get database status
python scripts/database_manager.py status

# Reset database completely
python scripts/database_manager.py reset --force
```

### PowerShell Scripts

#### `scripts/database-manager.ps1`
Enhanced PowerShell interface:
```powershell
# Initialize database
.\scripts\database-manager.ps1 init

# Initialize with force
.\scripts\database-manager.ps1 init -Force

# Check health
.\scripts\database-manager.ps1 health

# Repair database
.\scripts\database-manager.ps1 repair

# Get status
.\scripts\database-manager.ps1 status

# Reset database
.\scripts\database-manager.ps1 reset -Force

# Seed data only
.\scripts\database-manager.ps1 seed

# Run migrations
.\scripts\database-manager.ps1 migrate
```

#### `scripts/init-db.ps1`
Enhanced initialization script:
```powershell
.\scripts\init-db.ps1
```
- Tries new system first
- Falls back to migration-based approach
- Creates admin user automatically

#### `scripts/manage-schema.ps1`
Enhanced schema management:
```powershell
# Create schema
.\scripts\manage-schema.ps1 create

# Get schema info
.\scripts\manage-schema.ps1 info

# Initialize database
.\scripts\manage-schema.ps1 init

# Check health
.\scripts\manage-schema.ps1 health

# Repair database
.\scripts\manage-schema.ps1 repair

# Drop schema (with confirmation)
.\scripts\manage-schema.ps1 drop
```

## Environment-Specific Setup

### Development Environment

For local development with SQLite:
```bash
# Set environment variables
export FLASK_ENV=development
export DATABASE_URL=sqlite:///ai_secretary.db

# Initialize database
python init_database.py
```

### Production Environment

For production with PostgreSQL:
```bash
# Set environment variables
export FLASK_ENV=production
export DATABASE_URL=postgresql://user:pass@localhost/ai_secretary

# Initialize database
python scripts/database_manager.py init
```

### Testing Environment

For testing with isolated database:
```bash
# Set environment variables
export FLASK_ENV=testing
export DATABASE_URL=sqlite:///test.db

# Initialize test database
python scripts/database_manager.py init --force
```

## Backward Compatibility

### Legacy Scripts

The following legacy scripts continue to work:

- `init_database.py` - Enhanced with new system integration
- `create_admin_user.py` - Enhanced with data seeding integration
- `scripts/init-db.ps1` - Enhanced with new system fallback
- `scripts/manage-schema.ps1` - Enhanced with new capabilities

### Legacy Compatibility Layer

For maximum compatibility, use the legacy setup script:
```bash
python scripts/legacy_database_setup.py
```

This script:
- Tries new system first
- Falls back to legacy methods
- Ensures database is ready regardless of available systems
- Provides verification of setup

## Troubleshooting

### Database Connection Issues

1. **Check database health:**
   ```bash
   python scripts/database_manager.py health
   ```

2. **Repair database:**
   ```bash
   python scripts/database_manager.py repair
   ```

3. **Reset database:**
   ```bash
   python scripts/database_manager.py reset --force
   ```

### Migration Issues

1. **Run migrations manually:**
   ```powershell
   .\scripts\database-manager.ps1 migrate
   ```

2. **Check migration status:**
   ```bash
   flask db current
   flask db history
   ```

### Schema Issues

1. **Check schema info:**
   ```bash
   python scripts/schema_info.py
   ```

2. **Recreate schema:**
   ```bash
   python scripts/schema_create.py
   ```

### Admin User Issues

1. **Recreate admin user:**
   ```bash
   python create_admin_user.py
   ```

2. **Seed data only:**
   ```powershell
   .\scripts\database-manager.ps1 seed
   ```

## Default Credentials

After successful initialization, you can log in with:

- **Email:** admin@ai-secretary.com
- **Password:** admin123
- **Tenant:** AI Secretary System (or Default Tenant for legacy)

## Validation

To validate that your database setup is working correctly:

```bash
# Run startup validation
python validate_startup.py

# Check application can start
python run.py --validate-only
```

## Advanced Usage

### Custom Configuration

You can customize the initialization process by setting environment variables:

```bash
# Custom admin credentials
export ADMIN_EMAIL=custom@example.com
export ADMIN_PASSWORD=custompass123

# Custom tenant information
export DEFAULT_TENANT_NAME="My Company"
export DEFAULT_TENANT_DOMAIN="mycompany.com"

# Initialize with custom settings
python scripts/database_manager.py init
```

### Health Monitoring

Set up continuous health monitoring:

```bash
# Add to cron job for regular health checks
0 */6 * * * /path/to/python /path/to/scripts/database_manager.py health
```

### Backup Before Operations

Always backup before major operations:

```bash
# SQLite backup
cp ai_secretary.db ai_secretary.db.backup

# PostgreSQL backup
pg_dump ai_secretary > backup.sql

# Then run operations
python scripts/database_manager.py reset --force
```

## Migration from Legacy Setup

If you're migrating from an older setup:

1. **Backup existing data:**
   ```bash
   # Backup your current database
   cp ai_secretary.db ai_secretary.db.old
   ```

2. **Test new system:**
   ```bash
   # Validate new system works
   python validate_startup.py
   ```

3. **Initialize with new system:**
   ```bash
   # Use new initialization
   python scripts/database_manager.py init
   ```

4. **Verify migration:**
   ```bash
   # Check everything works
   python scripts/database_manager.py health
   ```

## Support

If you encounter issues:

1. Check the logs for detailed error messages
2. Run health checks to identify specific problems
3. Use repair functions to fix common issues
4. Fall back to legacy methods if needed
5. Reset database as last resort (with backup)

The new system is designed to be robust and provide clear error messages with suggested solutions for common problems.
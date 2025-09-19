#!/usr/bin/env python3
"""Script to create performance monitoring tables."""

import sqlite3
import os

def create_performance_tables():
    """Create performance monitoring tables in SQLite database."""
    
    # Connect to database
    db_path = 'ai_secretary.db'
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found. Creating new database.")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Create performance_metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint VARCHAR(255) NOT NULL,
                method VARCHAR(10) NOT NULL,
                status_code INTEGER NOT NULL,
                response_time_ms REAL NOT NULL,
                db_query_time_ms REAL DEFAULT 0.0,
                db_query_count INTEGER DEFAULT 0,
                cache_hits INTEGER DEFAULT 0,
                cache_misses INTEGER DEFAULT 0,
                user_id INTEGER,
                tenant_id INTEGER,
                ip_address VARCHAR(45),
                user_agent TEXT,
                timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                memory_usage_mb REAL,
                cpu_usage_percent REAL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for performance_metrics
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_performance_endpoint_time ON performance_metrics(endpoint, timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_performance_slow_requests ON performance_metrics(response_time_ms, timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_performance_errors ON performance_metrics(status_code, timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_performance_user_metrics ON performance_metrics(user_id, timestamp)")
        
        # Create slow_queries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS slow_queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_hash VARCHAR(64) NOT NULL,
                query_text TEXT NOT NULL,
                normalized_query TEXT NOT NULL,
                execution_time_ms REAL NOT NULL,
                rows_examined INTEGER,
                rows_returned INTEGER,
                endpoint VARCHAR(255),
                user_id INTEGER,
                tenant_id INTEGER,
                timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                database_name VARCHAR(100),
                table_names TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for slow_queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_slow_query_hash_time ON slow_queries(query_hash, timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_slow_query_execution_time ON slow_queries(execution_time_ms, timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_slow_query_endpoint ON slow_queries(endpoint, timestamp)")
        
        # Create service_health table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS service_health (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_name VARCHAR(100) NOT NULL,
                service_type VARCHAR(50) NOT NULL,
                endpoint_url VARCHAR(500),
                status VARCHAR(20) NOT NULL,
                response_time_ms REAL,
                error_message TEXT,
                check_type VARCHAR(50) NOT NULL,
                last_check DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                next_check DATETIME,
                version VARCHAR(50),
                extra_metadata TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for service_health
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_service_health_name_status ON service_health(service_name, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_service_health_last_check ON service_health(last_check)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_service_health_next_check ON service_health(next_check)")
        
        # Create performance_alerts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type VARCHAR(50) NOT NULL,
                severity VARCHAR(20) NOT NULL,
                title VARCHAR(255) NOT NULL,
                description TEXT NOT NULL,
                endpoint VARCHAR(255),
                service_name VARCHAR(100),
                metric_value REAL,
                threshold_value REAL,
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                acknowledged_by INTEGER,
                acknowledged_at DATETIME,
                resolved_at DATETIME,
                first_occurrence DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_occurrence DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                occurrence_count INTEGER NOT NULL DEFAULT 1,
                alert_metadata TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for performance_alerts
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_performance_alert_type_status ON performance_alerts(alert_type, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_performance_alert_severity ON performance_alerts(severity, first_occurrence)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_performance_alert_endpoint ON performance_alerts(endpoint, status)")
        
        conn.commit()
        print("✅ Performance monitoring tables created successfully!")
        
        # Verify tables were created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%performance%' OR name LIKE '%slow_queries%' OR name LIKE '%service_health%'")
        tables = cursor.fetchall()
        
        print("\n📋 Created tables:")
        for table in tables:
            print(f"  - {table[0]}")
            
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    create_performance_tables()
"""
Dashboard service for AI Secretary monitoring.
Provides real-time system health dashboards and metrics visualization.
"""

import time
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
import psutil
from flask import current_app
import structlog

logger = structlog.get_logger()


@dataclass
class DashboardWidget:
    """Dashboard widget configuration."""
    id: str
    title: str
    type: str  # chart, metric, status, table, etc.
    config: Dict[str, Any]
    data_source: str
    refresh_interval: int = 30  # seconds
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Dashboard:
    """Dashboard configuration."""
    id: str
    title: str
    description: str
    widgets: List[DashboardWidget]
    layout: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['widgets'] = [widget.to_dict() for widget in self.widgets]
        return data


class DashboardService:
    """Service for managing monitoring dashboards."""
    
    def __init__(self):
        self.dashboards: Dict[str, Dashboard] = {}
        self.widget_data_cache: Dict[str, Any] = {}
        self.cache_timestamps: Dict[str, datetime] = {}
        self._setup_default_dashboards()
    
    def _setup_default_dashboards(self):
        """Set up default monitoring dashboards."""
        # System Overview Dashboard
        system_dashboard = self._create_system_overview_dashboard()
        self.dashboards[system_dashboard.id] = system_dashboard
        
        # Application Performance Dashboard
        app_dashboard = self._create_application_dashboard()
        self.dashboards[app_dashboard.id] = app_dashboard
        
        # Error Monitoring Dashboard
        error_dashboard = self._create_error_dashboard()
        self.dashboards[error_dashboard.id] = error_dashboard
        
        # Business Metrics Dashboard
        business_dashboard = self._create_business_dashboard()
        self.dashboards[business_dashboard.id] = business_dashboard
    
    def _create_system_overview_dashboard(self) -> Dashboard:
        """Create system overview dashboard."""
        widgets = [
            DashboardWidget(
                id="system_status",
                title="System Status",
                type="status",
                config={
                    "status_indicators": [
                        {"name": "Application", "key": "app_status"},
                        {"name": "Database", "key": "db_status"},
                        {"name": "Redis", "key": "redis_status"},
                        {"name": "Celery", "key": "celery_status"}
                    ]
                },
                data_source="system_health",
                refresh_interval=10
            ),
            DashboardWidget(
                id="cpu_usage",
                title="CPU Usage",
                type="gauge",
                config={
                    "min": 0,
                    "max": 100,
                    "unit": "%",
                    "thresholds": [
                        {"value": 70, "color": "yellow"},
                        {"value": 85, "color": "red"}
                    ]
                },
                data_source="system_metrics",
                refresh_interval=5
            ),
            DashboardWidget(
                id="memory_usage",
                title="Memory Usage",
                type="gauge",
                config={
                    "min": 0,
                    "max": 100,
                    "unit": "%",
                    "thresholds": [
                        {"value": 80, "color": "yellow"},
                        {"value": 90, "color": "red"}
                    ]
                },
                data_source="system_metrics",
                refresh_interval=5
            ),
            DashboardWidget(
                id="disk_usage",
                title="Disk Usage",
                type="gauge",
                config={
                    "min": 0,
                    "max": 100,
                    "unit": "%",
                    "thresholds": [
                        {"value": 85, "color": "yellow"},
                        {"value": 95, "color": "red"}
                    ]
                },
                data_source="system_metrics",
                refresh_interval=30
            ),
            DashboardWidget(
                id="system_load",
                title="System Load Average",
                type="line_chart",
                config={
                    "time_range": "1h",
                    "y_axis": {"label": "Load Average"},
                    "series": [
                        {"name": "1min", "color": "#1f77b4"},
                        {"name": "5min", "color": "#ff7f0e"},
                        {"name": "15min", "color": "#2ca02c"}
                    ]
                },
                data_source="system_load",
                refresh_interval=15
            ),
            DashboardWidget(
                id="network_io",
                title="Network I/O",
                type="line_chart",
                config={
                    "time_range": "1h",
                    "y_axis": {"label": "Bytes/sec"},
                    "series": [
                        {"name": "Bytes Sent", "color": "#1f77b4"},
                        {"name": "Bytes Received", "color": "#ff7f0e"}
                    ]
                },
                data_source="network_metrics",
                refresh_interval=10
            )
        ]
        
        layout = {
            "grid": {
                "columns": 12,
                "rows": 8
            },
            "widgets": [
                {"id": "system_status", "x": 0, "y": 0, "w": 12, "h": 1},
                {"id": "cpu_usage", "x": 0, "y": 1, "w": 3, "h": 2},
                {"id": "memory_usage", "x": 3, "y": 1, "w": 3, "h": 2},
                {"id": "disk_usage", "x": 6, "y": 1, "w": 3, "h": 2},
                {"id": "system_load", "x": 0, "y": 3, "w": 6, "h": 3},
                {"id": "network_io", "x": 6, "y": 3, "w": 6, "h": 3}
            ]
        }
        
        return Dashboard(
            id="system_overview",
            title="System Overview",
            description="Overall system health and resource usage",
            widgets=widgets,
            layout=layout
        )
    
    def _create_application_dashboard(self) -> Dashboard:
        """Create application performance dashboard."""
        widgets = [
            DashboardWidget(
                id="request_rate",
                title="Request Rate",
                type="metric",
                config={
                    "unit": "req/min",
                    "format": "number"
                },
                data_source="app_metrics",
                refresh_interval=10
            ),
            DashboardWidget(
                id="response_time",
                title="Response Time (P95)",
                type="metric",
                config={
                    "unit": "ms",
                    "format": "number",
                    "thresholds": [
                        {"value": 1000, "color": "yellow"},
                        {"value": 2000, "color": "red"}
                    ]
                },
                data_source="app_metrics",
                refresh_interval=10
            ),
            DashboardWidget(
                id="error_rate",
                title="Error Rate",
                type="metric",
                config={
                    "unit": "%",
                    "format": "percentage",
                    "thresholds": [
                        {"value": 1, "color": "yellow"},
                        {"value": 5, "color": "red"}
                    ]
                },
                data_source="app_metrics",
                refresh_interval=10
            ),
            DashboardWidget(
                id="active_users",
                title="Active Users",
                type="metric",
                config={
                    "unit": "users",
                    "format": "number"
                },
                data_source="app_metrics",
                refresh_interval=30
            ),
            DashboardWidget(
                id="request_timeline",
                title="Request Timeline",
                type="line_chart",
                config={
                    "time_range": "1h",
                    "y_axis": {"label": "Requests/min"},
                    "series": [
                        {"name": "Total Requests", "color": "#1f77b4"},
                        {"name": "Successful", "color": "#2ca02c"},
                        {"name": "Errors", "color": "#d62728"}
                    ]
                },
                data_source="request_timeline",
                refresh_interval=15
            ),
            DashboardWidget(
                id="response_time_distribution",
                title="Response Time Distribution",
                type="histogram",
                config={
                    "buckets": [50, 100, 200, 500, 1000, 2000, 5000],
                    "x_axis": {"label": "Response Time (ms)"},
                    "y_axis": {"label": "Request Count"}
                },
                data_source="response_time_dist",
                refresh_interval=30
            ),
            DashboardWidget(
                id="top_endpoints",
                title="Top Endpoints by Request Count",
                type="table",
                config={
                    "columns": [
                        {"key": "endpoint", "title": "Endpoint"},
                        {"key": "count", "title": "Requests"},
                        {"key": "avg_response_time", "title": "Avg Response Time (ms)"},
                        {"key": "error_rate", "title": "Error Rate (%)"}
                    ],
                    "sort_by": "count",
                    "limit": 10
                },
                data_source="endpoint_stats",
                refresh_interval=60
            ),
            DashboardWidget(
                id="database_connections",
                title="Database Connections",
                type="line_chart",
                config={
                    "time_range": "1h",
                    "y_axis": {"label": "Connections"},
                    "series": [
                        {"name": "Active", "color": "#1f77b4"},
                        {"name": "Idle", "color": "#ff7f0e"}
                    ]
                },
                data_source="db_connections",
                refresh_interval=30
            )
        ]
        
        layout = {
            "grid": {"columns": 12, "rows": 10},
            "widgets": [
                {"id": "request_rate", "x": 0, "y": 0, "w": 3, "h": 1},
                {"id": "response_time", "x": 3, "y": 0, "w": 3, "h": 1},
                {"id": "error_rate", "x": 6, "y": 0, "w": 3, "h": 1},
                {"id": "active_users", "x": 9, "y": 0, "w": 3, "h": 1},
                {"id": "request_timeline", "x": 0, "y": 1, "w": 8, "h": 3},
                {"id": "response_time_distribution", "x": 8, "y": 1, "w": 4, "h": 3},
                {"id": "top_endpoints", "x": 0, "y": 4, "w": 8, "h": 3},
                {"id": "database_connections", "x": 8, "y": 4, "w": 4, "h": 3}
            ]
        }
        
        return Dashboard(
            id="application_performance",
            title="Application Performance",
            description="Application performance metrics and request analytics",
            widgets=widgets,
            layout=layout
        )
    
    def _create_error_dashboard(self) -> Dashboard:
        """Create error monitoring dashboard."""
        widgets = [
            DashboardWidget(
                id="error_summary",
                title="Error Summary",
                type="status",
                config={
                    "metrics": [
                        {"name": "Total Errors (24h)", "key": "total_errors"},
                        {"name": "Error Rate", "key": "error_rate"},
                        {"name": "Critical Errors", "key": "critical_errors"},
                        {"name": "New Error Types", "key": "new_error_types"}
                    ]
                },
                data_source="error_summary",
                refresh_interval=30
            ),
            DashboardWidget(
                id="errors_by_severity",
                title="Errors by Severity",
                type="pie_chart",
                config={
                    "colors": {
                        "critical": "#d62728",
                        "high": "#ff7f0e",
                        "medium": "#ffbb78",
                        "low": "#2ca02c"
                    }
                },
                data_source="errors_by_severity",
                refresh_interval=30
            ),
            DashboardWidget(
                id="errors_by_category",
                title="Errors by Category",
                type="bar_chart",
                config={
                    "x_axis": {"label": "Category"},
                    "y_axis": {"label": "Count"},
                    "orientation": "horizontal"
                },
                data_source="errors_by_category",
                refresh_interval=30
            ),
            DashboardWidget(
                id="error_timeline",
                title="Error Timeline",
                type="line_chart",
                config={
                    "time_range": "24h",
                    "y_axis": {"label": "Error Count"},
                    "series": [
                        {"name": "Critical", "color": "#d62728"},
                        {"name": "High", "color": "#ff7f0e"},
                        {"name": "Medium", "color": "#ffbb78"},
                        {"name": "Low", "color": "#2ca02c"}
                    ]
                },
                data_source="error_timeline",
                refresh_interval=60
            ),
            DashboardWidget(
                id="top_errors",
                title="Top Errors",
                type="table",
                config={
                    "columns": [
                        {"key": "message", "title": "Error Message"},
                        {"key": "count", "title": "Count"},
                        {"key": "severity", "title": "Severity"},
                        {"key": "last_seen", "title": "Last Seen"},
                        {"key": "affected_users", "title": "Affected Users"}
                    ],
                    "sort_by": "count",
                    "limit": 10
                },
                data_source="top_errors",
                refresh_interval=60
            )
        ]
        
        layout = {
            "grid": {"columns": 12, "rows": 8},
            "widgets": [
                {"id": "error_summary", "x": 0, "y": 0, "w": 12, "h": 1},
                {"id": "errors_by_severity", "x": 0, "y": 1, "w": 4, "h": 3},
                {"id": "errors_by_category", "x": 4, "y": 1, "w": 4, "h": 3},
                {"id": "error_timeline", "x": 8, "y": 1, "w": 4, "h": 3},
                {"id": "top_errors", "x": 0, "y": 4, "w": 12, "h": 4}
            ]
        }
        
        return Dashboard(
            id="error_monitoring",
            title="Error Monitoring",
            description="Error tracking and analysis dashboard",
            widgets=widgets,
            layout=layout
        )
    
    def _create_business_dashboard(self) -> Dashboard:
        """Create business metrics dashboard."""
        widgets = [
            DashboardWidget(
                id="active_tenants",
                title="Active Tenants",
                type="metric",
                config={"unit": "tenants", "format": "number"},
                data_source="business_metrics",
                refresh_interval=300
            ),
            DashboardWidget(
                id="messages_processed",
                title="Messages Processed (24h)",
                type="metric",
                config={"unit": "messages", "format": "number"},
                data_source="business_metrics",
                refresh_interval=60
            ),
            DashboardWidget(
                id="ai_requests",
                title="AI Requests (24h)",
                type="metric",
                config={"unit": "requests", "format": "number"},
                data_source="business_metrics",
                refresh_interval=60
            ),
            DashboardWidget(
                id="revenue_metrics",
                title="Revenue Metrics",
                type="status",
                config={
                    "metrics": [
                        {"name": "MRR", "key": "mrr"},
                        {"name": "Active Subscriptions", "key": "active_subscriptions"},
                        {"name": "Trial Conversions", "key": "trial_conversions"}
                    ]
                },
                data_source="revenue_metrics",
                refresh_interval=3600
            )
        ]
        
        layout = {
            "grid": {"columns": 12, "rows": 4},
            "widgets": [
                {"id": "active_tenants", "x": 0, "y": 0, "w": 3, "h": 1},
                {"id": "messages_processed", "x": 3, "y": 0, "w": 3, "h": 1},
                {"id": "ai_requests", "x": 6, "y": 0, "w": 3, "h": 1},
                {"id": "revenue_metrics", "x": 0, "y": 1, "w": 12, "h": 2}
            ]
        }
        
        return Dashboard(
            id="business_metrics",
            title="Business Metrics",
            description="Key business performance indicators",
            widgets=widgets,
            layout=layout
        )
    
    def get_dashboard(self, dashboard_id: str) -> Optional[Dashboard]:
        """Get dashboard by ID."""
        return self.dashboards.get(dashboard_id)
    
    def list_dashboards(self) -> List[Dict[str, Any]]:
        """List all available dashboards."""
        return [
            {
                "id": dashboard.id,
                "title": dashboard.title,
                "description": dashboard.description
            }
            for dashboard in self.dashboards.values()
        ]
    
    def get_widget_data(self, data_source: str, widget_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get data for a specific widget."""
        # Check cache first
        cache_key = f"{data_source}_{hash(str(widget_config))}"
        if cache_key in self.cache_timestamps:
            cache_age = datetime.utcnow() - self.cache_timestamps[cache_key]
            if cache_age.total_seconds() < 30:  # 30 second cache
                return self.widget_data_cache.get(cache_key, {})
        
        # Generate fresh data
        data = self._generate_widget_data(data_source, widget_config)
        
        # Cache the data
        self.widget_data_cache[cache_key] = data
        self.cache_timestamps[cache_key] = datetime.utcnow()
        
        return data
    
    def _generate_widget_data(self, data_source: str, widget_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate data for widget based on data source."""
        try:
            if data_source == "system_health":
                return self._get_system_health_data()
            elif data_source == "system_metrics":
                return self._get_system_metrics_data()
            elif data_source == "system_load":
                return self._get_system_load_data()
            elif data_source == "network_metrics":
                return self._get_network_metrics_data()
            elif data_source == "app_metrics":
                return self._get_app_metrics_data()
            elif data_source == "request_timeline":
                return self._get_request_timeline_data()
            elif data_source == "response_time_dist":
                return self._get_response_time_distribution_data()
            elif data_source == "endpoint_stats":
                return self._get_endpoint_stats_data()
            elif data_source == "db_connections":
                return self._get_db_connections_data()
            elif data_source == "error_summary":
                return self._get_error_summary_data()
            elif data_source == "errors_by_severity":
                return self._get_errors_by_severity_data()
            elif data_source == "errors_by_category":
                return self._get_errors_by_category_data()
            elif data_source == "error_timeline":
                return self._get_error_timeline_data()
            elif data_source == "top_errors":
                return self._get_top_errors_data()
            elif data_source == "business_metrics":
                return self._get_business_metrics_data()
            elif data_source == "revenue_metrics":
                return self._get_revenue_metrics_data()
            else:
                return {"error": f"Unknown data source: {data_source}"}
                
        except Exception as e:
            logger.error("Failed to generate widget data", data_source=data_source, error=str(e))
            return {"error": str(e)}
    
    def _get_system_health_data(self) -> Dict[str, Any]:
        """Get system health status data."""
        from app.utils.monitoring import health_checker
        
        health_status = health_checker.run_checks()
        
        return {
            "app_status": "healthy" if health_status['status'] == 'healthy' else "unhealthy",
            "db_status": health_status['checks'].get('database', {}).get('status', 'unknown'),
            "redis_status": health_status['checks'].get('redis', {}).get('status', 'unknown'),
            "celery_status": "healthy"  # Would need Celery integration
        }
    
    def _get_system_metrics_data(self) -> Dict[str, Any]:
        """Get current system metrics."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                "cpu_usage": cpu_percent,
                "memory_usage": memory.percent,
                "disk_usage": disk.percent,
                "memory_available_gb": memory.available / (1024**3),
                "disk_free_gb": disk.free / (1024**3)
            }
        except Exception as e:
            logger.error("Failed to get system metrics", error=str(e))
            return {"error": str(e)}
    
    def _get_system_load_data(self) -> Dict[str, Any]:
        """Get system load average data."""
        try:
            if hasattr(psutil, 'getloadavg'):
                load_avg = psutil.getloadavg()
                return {
                    "timestamp": datetime.utcnow().isoformat(),
                    "load_1min": load_avg[0],
                    "load_5min": load_avg[1],
                    "load_15min": load_avg[2]
                }
            else:
                return {"error": "Load average not available on this platform"}
        except Exception as e:
            return {"error": str(e)}
    
    def _get_network_metrics_data(self) -> Dict[str, Any]:
        """Get network I/O metrics."""
        try:
            net_io = psutil.net_io_counters()
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _get_app_metrics_data(self) -> Dict[str, Any]:
        """Get application metrics data."""
        from app.services.monitoring_service import monitoring_service
        
        if monitoring_service and monitoring_service.metrics_collector:
            metrics = monitoring_service.get_metrics_summary()
            app_metrics = metrics.get('application', {})
            
            return {
                "request_rate": app_metrics.get('request_count', 0) / 60,  # per minute
                "response_time_p95": app_metrics.get('response_time_p95', 0),
                "error_rate": (app_metrics.get('error_count', 0) / max(app_metrics.get('request_count', 1), 1)) * 100,
                "active_users": 0,  # Would need session tracking
                "database_connections": app_metrics.get('database_connections', 0)
            }
        
        return {"error": "Monitoring service not available"}
    
    def _get_request_timeline_data(self) -> Dict[str, Any]:
        """Get request timeline data."""
        # This would typically come from time-series data
        # For now, return mock data structure
        return {
            "series": [
                {
                    "name": "Total Requests",
                    "data": []  # Would contain time-series data points
                },
                {
                    "name": "Successful",
                    "data": []
                },
                {
                    "name": "Errors",
                    "data": []
                }
            ]
        }
    
    def _get_response_time_distribution_data(self) -> Dict[str, Any]:
        """Get response time distribution data."""
        return {
            "buckets": [50, 100, 200, 500, 1000, 2000, 5000],
            "counts": [0, 0, 0, 0, 0, 0, 0]  # Would contain actual distribution
        }
    
    def _get_endpoint_stats_data(self) -> Dict[str, Any]:
        """Get endpoint statistics data."""
        return {
            "data": []  # Would contain endpoint statistics
        }
    
    def _get_db_connections_data(self) -> Dict[str, Any]:
        """Get database connections data."""
        return {
            "series": [
                {"name": "Active", "data": []},
                {"name": "Idle", "data": []}
            ]
        }
    
    def _get_error_summary_data(self) -> Dict[str, Any]:
        """Get error summary data."""
        from app.services.error_tracking_service import error_tracking_service
        
        summary = error_tracking_service.get_error_summary(24)
        
        return {
            "total_errors": summary.get('total_errors', 0),
            "error_rate": f"{summary.get('error_rate', 0):.2f}%",
            "critical_errors": summary.get('errors_by_severity', {}).get('critical', 0),
            "new_error_types": len(summary.get('top_errors', []))
        }
    
    def _get_errors_by_severity_data(self) -> Dict[str, Any]:
        """Get errors by severity data."""
        from app.services.error_tracking_service import error_tracking_service
        
        summary = error_tracking_service.get_error_summary(24)
        return summary.get('errors_by_severity', {})
    
    def _get_errors_by_category_data(self) -> Dict[str, Any]:
        """Get errors by category data."""
        from app.services.error_tracking_service import error_tracking_service
        
        summary = error_tracking_service.get_error_summary(24)
        return summary.get('errors_by_category', {})
    
    def _get_error_timeline_data(self) -> Dict[str, Any]:
        """Get error timeline data."""
        from app.services.error_tracking_service import error_tracking_service
        
        trends = error_tracking_service.get_error_trends(24)
        return trends.get('hourly_counts', [])
    
    def _get_top_errors_data(self) -> Dict[str, Any]:
        """Get top errors data."""
        from app.services.error_tracking_service import error_tracking_service
        
        summary = error_tracking_service.get_error_summary(24)
        return {"data": summary.get('top_errors', [])}
    
    def _get_business_metrics_data(self) -> Dict[str, Any]:
        """Get business metrics data."""
        # This would typically query the database for business metrics
        return {
            "active_tenants": 0,
            "messages_processed": 0,
            "ai_requests": 0
        }
    
    def _get_revenue_metrics_data(self) -> Dict[str, Any]:
        """Get revenue metrics data."""
        return {
            "mrr": "$0",
            "active_subscriptions": 0,
            "trial_conversions": "0%"
        }


# Global dashboard service
dashboard_service = DashboardService()


def init_dashboard_service(app):
    """Initialize dashboard service."""
    logger.info("Dashboard service initialized")
    return dashboard_service
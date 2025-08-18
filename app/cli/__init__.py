"""CLI commands for the application."""
from app.cli import data_retention


def init_app(app):
    """Initialize CLI commands with Flask app."""
    data_retention.init_app(app)
"""CLI commands for the application."""
from app.cli import data_retention, translation_commands, seed_data, database_commands, performance


def init_app(app):
    """Initialize CLI commands with Flask app."""
    data_retention.init_app(app)
    translation_commands.init_translation_commands(app)
    seed_data.init_app(app)
    database_commands.init_app(app)
    performance.init_app(app)
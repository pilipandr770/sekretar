"""Channels package."""
from flask import Blueprint

channels_bp = Blueprint('channels', __name__)

from app.channels import routes
from app.channels import websocket_handlers
from app.channels import widget_api
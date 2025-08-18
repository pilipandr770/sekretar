"""Inbox package."""
from flask import Blueprint

inbox_bp = Blueprint('inbox', __name__)

from app.inbox import routes
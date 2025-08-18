"""Admin package for user and role management."""
from flask import Blueprint

admin_bp = Blueprint('admin', __name__)

from app.admin import routes
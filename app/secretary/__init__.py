"""Secretary setup and management blueprint."""
from flask import Blueprint

secretary_bp = Blueprint('secretary', __name__)

from app.secretary import routes
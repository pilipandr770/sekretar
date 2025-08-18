"""Knowledge package."""
from flask import Blueprint

knowledge_bp = Blueprint('knowledge', __name__)

from app.knowledge import routes
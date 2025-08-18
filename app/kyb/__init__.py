"""KYB package."""
from flask import Blueprint

kyb_bp = Blueprint('kyb', __name__)

from app.kyb import routes
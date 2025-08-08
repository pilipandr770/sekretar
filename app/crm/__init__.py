"""CRM package."""
from flask import Blueprint

crm_bp = Blueprint('crm', __name__)

from app.crm import routes
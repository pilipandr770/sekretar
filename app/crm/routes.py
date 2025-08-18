"""CRM routes with comprehensive functionality."""
from app.crm import crm_bp

# Import all CRM endpoints to register them with the blueprint
import app.api.crm
import app.api.crm_endpoints
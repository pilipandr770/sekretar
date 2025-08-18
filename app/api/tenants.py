"""Tenant management API endpoints."""
from flask import request, Blueprint
from flask_jwt_extended import jwt_required, get_current_user
from flask_babel import gettext as _
from sqlalchemy.exc import IntegrityError
from app.models.tenant import Tenant
from app.
"""Inbox management API endpoints."""
from flask import Blueprint, request, g
from flask_jwt_extended import jwt_required, get_current_user
from flask_babel import gettext as _
from sqlalchemy import and_, or_,
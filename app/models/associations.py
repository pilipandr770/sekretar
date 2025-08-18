"""Association tables for many-to-many relationships."""
from sqlalchemy import Column, Integer, ForeignKey, Table
from app.models.base import BaseModel, get_fk_reference


# Association table for user-role many-to-many relationship
from app.utils.schema import get_schema_name

# Get schema name for table args
schema_name = get_schema_name()
table_args = {'schema': schema_name} if schema_name else {}

user_roles = Table(
    'user_roles',
    BaseModel.metadata,
    Column('user_id', Integer, ForeignKey(get_fk_reference('users')), primary_key=True),
    Column('role_id', Integer, ForeignKey(get_fk_reference('roles')), primary_key=True),
    **table_args
)
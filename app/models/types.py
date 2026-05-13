"""
Cross-database type definitions for SQLAlchemy.

Provides UUID support for both SQLite and PostgreSQL.
"""

import uuid as _uuid
from sqlalchemy import TypeDecorator, CHAR, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class GUID(TypeDecorator):
    """
    Platform-independent GUID type.
    
    Uses CHAR(32) or VARCHAR for SQLite, native UUID for PostgreSQL.
    
    Automatically stores UUIDs as strings in SQLite but as native
    UUID objects in PostgreSQL.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        """Load the appropriate implementation for the target dialect."""
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        """Convert Python UUID to database representation."""
        if value is None:
            return value
        if not isinstance(value, _uuid.UUID):
            value = _uuid.UUID(str(value))
        if dialect.name == "postgresql":
            return value  # PG_UUID(as_uuid=True) handles wire encoding
        return str(value).replace("-", "")  # SQLite: 32-char hex

    def process_result_value(self, value, dialect):
        """Convert database representation back to Python UUID."""
        if value is None or isinstance(value, _uuid.UUID):
            return value
        try:
            return _uuid.UUID(str(value))
        except (ValueError, AttributeError):
            return value

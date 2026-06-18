"""The single declarative ``Base`` every ORM model inherits from.

A metadata-wide naming convention gives every index, constraint, and foreign
key a deterministic name. Without it, Alembic autogenerate emits unnamed or
backend-chosen names that differ between machines, producing noisy or
unrepeatable migration diffs. With it, ``alembic check`` stays meaningful as the
source-of-truth comparison between the models and the migration history.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base shared by all pattern-mirror ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

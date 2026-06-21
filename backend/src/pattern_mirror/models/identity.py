"""Identity and subjects: ``users``, their ``user_roles``, and document ``subjects``.

One ``users`` table for everyone who logs in, with roles in a join table (D1):
manager/HR is a role distinction, not a type distinction, so audit FKs stay
uniform (to ``users.id``) and one person can hold both roles. ``subjects`` are
the people documents are *about* (candidates, employees); they do not
authenticate, and their minimised demographics (D3) are what make the
per-manager pattern detection possible. Identity and demographics are projected
from UBS HRIS/ATS; this app is not their system of record.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import TIMESTAMP, ForeignKey, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pattern_mirror.db.base import Base
from pattern_mirror.models.columns import uuid_pk
from pattern_mirror.models.enums import (
    SubjectType,
    UserRole,
    subject_type_enum,
    user_role_enum,
)
from pattern_mirror.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from pattern_mirror.models.documents import Document


class User(TimestampMixin, Base):
    """An authenticated identity (manager and/or HR); attributes synced from HRIS."""

    __tablename__ = "users"

    id: Mapped[uuid_pk]
    external_user_id: Mapped[str] = mapped_column(String, unique=True)
    legal_name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String, unique=True)
    department: Mapped[str | None] = mapped_column(String)
    avatar_blob_ref: Mapped[str | None] = mapped_column(String)
    active: Mapped[bool] = mapped_column(server_default=text("true"))

    roles: Mapped[list["UserRoleAssignment"]] = relationship(back_populates="user")
    documents: Mapped[list["Document"]] = relationship(back_populates="owner")


class UserRoleAssignment(Base):
    """A role granted to a user; composite-keyed so a user can hold more than one."""

    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[UserRole] = mapped_column(user_role_enum, primary_key=True)
    granted_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="roles")


class Subject(TimestampMixin, Base):
    """A person a document is about: an interview candidate or a promotion employee."""

    __tablename__ = "subjects"

    id: Mapped[uuid_pk]
    subject_type: Mapped[SubjectType] = mapped_column(subject_type_enum)
    legal_name: Mapped[str] = mapped_column(String)
    external_ref: Mapped[str | None] = mapped_column(String)
    gender: Mapped[str | None] = mapped_column(String)
    age_band: Mapped[str | None] = mapped_column(String)
    hired: Mapped[bool | None]
    resume_blob_ref: Mapped[str | None] = mapped_column(String)

    documents: Mapped[list["Document"]] = relationship(back_populates="subject")

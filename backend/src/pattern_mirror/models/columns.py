"""Reusable column type aliases for the ORM models.

``uuid_pk`` is the surrogate primary key every table (except the ``regions``
lookup, keyed by its jurisdiction code) uses: a UUID generated database-side by
``gen_random_uuid()`` (in core PostgreSQL since 13, so no ``pgcrypto``). Defined
once as an annotated type and reused via ``Mapped[uuid_pk]`` — SQLAlchemy's
recommended way to share a column definition without duplicating it per model.
"""

import uuid
from typing import Annotated

from sqlalchemy import Uuid, text
from sqlalchemy.orm import mapped_column

uuid_pk = Annotated[
    uuid.UUID,
    mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()")),
]

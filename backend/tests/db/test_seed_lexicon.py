"""The 0002 seed satisfies the AC and its lemma_keys agree with the live utility.

Asserts the three acceptance scenarios (all seven categories covered, every entry
cited, region-scoped to SG) against the migrated database, plus a drift guard: each
seeded ``lemma_key`` must equal what ``engine.lemmatiser`` produces today, so a
spaCy/model change that would silently break matching fails here instead.
"""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pattern_mirror.engine.lemmatiser import lemma_key
from pattern_mirror.models.dictionary import Dictionary
from pattern_mirror.models.enums import BiasCategory

pytestmark = pytest.mark.db


def test_all_seven_categories_are_covered(db_session: Session) -> None:
    seeded = set(db_session.scalars(select(Dictionary.category).distinct()).all())

    assert seeded == set(BiasCategory)


def test_every_entry_cites_a_source(db_session: Session) -> None:
    uncited = db_session.scalar(
        select(func.count()).select_from(Dictionary).where(Dictionary.citation_id.is_(None))
    )

    assert uncited == 0


def test_every_entry_is_region_scoped_to_sg(db_session: Session) -> None:
    regions = set(db_session.scalars(select(Dictionary.region_code).distinct()).all())

    assert regions == {"SG"}


def test_seeded_lemma_keys_match_the_live_utility(db_session: Session) -> None:
    entries = db_session.execute(select(Dictionary.term, Dictionary.lemma_key)).all()

    assert entries
    mismatched = {term: key for term, key in entries if lemma_key(term) != key}
    assert not mismatched

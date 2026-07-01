"""Approve/reject/defer resolve a queued addition; approve makes the phrase a live hit.

Approve materialises a live dictionary row (proven by re-running Stage-1 matching over a fresh
document), reject and defer add none, and every path records who decided and when. Terminal and
duplicate states raise typed conflicts. Asserted against the test database.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.core.errors import (
    AdditionAlreadyDecidedError,
    DictionaryEntryExistsError,
    PendingAdditionNotFoundError,
)
from pattern_mirror.engine.dictionary import load_active_rules, match_dictionary
from pattern_mirror.engine.tokenisation import lemmatise_with_offsets
from pattern_mirror.models.dictionary import Dictionary
from pattern_mirror.models.enums import (
    BiasCategory,
    CitationSourceType,
    DictionaryAdditionStatus,
)
from pattern_mirror.models.growth import DictionaryProposal, PendingDictionaryAddition
from pattern_mirror.models.identity import User
from pattern_mirror.models.reference import Citation
from pattern_mirror.services.dictionary_approval import (
    approve_addition,
    defer_addition,
    reject_addition,
)

pytestmark = pytest.mark.db

_PHRASE = "synergy wizard"
_LEMMA_KEY = " ".join(token.lemma for token in lemmatise_with_offsets(_PHRASE))


def _hr_user(db_session: Session) -> User:
    user = User(
        external_user_id=f"growth-hr-{uuid.uuid4()}",
        legal_name="Growth HR Reviewer",
        email=f"growth.hr.{uuid.uuid4()}@example.com",
    )
    db_session.add(user)
    db_session.flush()
    return user


def _seed_addition(
    db_session: Session,
    *,
    lemma_key: str = _LEMMA_KEY,
    category: BiasCategory = BiasCategory.age,
    with_citation: bool = True,
) -> PendingDictionaryAddition:
    """A queued addition with its proposal and (by default) a found citation."""
    citation_id = None
    if with_citation:
        citation = Citation(
            source_type=CitationSourceType.academic,
            title="Age-coded hiring language",
            reference="doi:10.1000/synergy",
            publication_year=2020,
            finding="The phrasing screens out older applicants.",
        )
        db_session.add(citation)
        db_session.flush()
        citation_id = citation.id
    proposal = DictionaryProposal(phrase=_PHRASE, lemma_key=lemma_key, citation_id=citation_id)
    db_session.add(proposal)
    db_session.flush()
    addition = PendingDictionaryAddition(
        proposal_id=proposal.id,
        phrase=_PHRASE,
        lemma_key=lemma_key,
        proposed_category=category,
        explanation="Signals youth-coded culture, deterring older candidates.",
    )
    db_session.add(addition)
    db_session.flush()
    return addition


def test_approve_creates_live_cited_entry_with_audit_columns(db_session: Session) -> None:
    actor = _hr_user(db_session)
    addition = _seed_addition(db_session)

    entry = approve_addition(db_session, addition_id=addition.id, actor_id=actor.id)

    assert entry.region_code == "SG"
    assert entry.term == _PHRASE
    assert entry.lemma_key == _LEMMA_KEY
    assert entry.category is BiasCategory.age
    assert entry.explanation == addition.explanation
    assert entry.active is True
    assert entry.citation_id == addition.proposal.citation_id
    assert entry.last_updated_by == actor.id
    assert entry.source_proposal_id == addition.proposal_id

    assert addition.status is DictionaryAdditionStatus.approved
    assert addition.decided_by == actor.id
    assert addition.decided_at is not None


def test_approved_phrase_fires_as_a_dictionary_hit(db_session: Session) -> None:
    # The proof the loop closes: an approved phrase is caught by Stage-1, not only the Contextual
    # Pass. Re-run the deterministic matcher over a fresh document containing the phrase.
    actor = _hr_user(db_session)
    addition = _seed_addition(db_session)
    approve_addition(db_session, addition_id=addition.id, actor_id=actor.id)

    rules = load_active_rules(db_session, "SG")
    flags = match_dictionary(f"We need a {_PHRASE} for this role.", rules)

    assert any(flag.lemma_key == _LEMMA_KEY for flag in flags)


def test_reject_adds_no_row_and_records_the_decision(db_session: Session) -> None:
    actor = _hr_user(db_session)
    addition = _seed_addition(db_session)

    reject_addition(db_session, addition_id=addition.id, actor_id=actor.id)

    assert addition.status is DictionaryAdditionStatus.rejected
    assert addition.decided_by == actor.id
    assert addition.decided_at is not None
    rows = db_session.scalars(select(Dictionary).where(Dictionary.lemma_key == _LEMMA_KEY)).all()
    assert rows == []


def test_defer_adds_no_row_and_stays_decidable(db_session: Session) -> None:
    actor = _hr_user(db_session)
    addition = _seed_addition(db_session)

    defer_addition(db_session, addition_id=addition.id, actor_id=actor.id)
    assert addition.status is DictionaryAdditionStatus.deferred
    deferred_rows = db_session.scalars(
        select(Dictionary).where(Dictionary.lemma_key == _LEMMA_KEY)
    ).all()
    assert deferred_rows == []

    # A deferred addition can still be approved later.
    entry = approve_addition(db_session, addition_id=addition.id, actor_id=actor.id)
    assert entry.lemma_key == _LEMMA_KEY
    assert addition.status is DictionaryAdditionStatus.approved


def test_deciding_an_already_decided_addition_conflicts(db_session: Session) -> None:
    actor = _hr_user(db_session)
    addition = _seed_addition(db_session)
    approve_addition(db_session, addition_id=addition.id, actor_id=actor.id)

    with pytest.raises(AdditionAlreadyDecidedError):
        reject_addition(db_session, addition_id=addition.id, actor_id=actor.id)


def test_approving_a_duplicate_phrase_conflicts(db_session: Session) -> None:
    # Two additions for the same phrase and category: the second approval would breach the
    # (region_code, lemma_key, category) unique constraint, so it is rejected as a conflict.
    actor = _hr_user(db_session)
    first = _seed_addition(db_session)
    second = _seed_addition(db_session)
    approve_addition(db_session, addition_id=first.id, actor_id=actor.id)

    with pytest.raises(DictionaryEntryExistsError):
        approve_addition(db_session, addition_id=second.id, actor_id=actor.id)


def test_deciding_an_unknown_addition_raises_not_found(db_session: Session) -> None:
    actor = _hr_user(db_session)
    with pytest.raises(PendingAdditionNotFoundError):
        approve_addition(db_session, addition_id=uuid.uuid4(), actor_id=actor.id)

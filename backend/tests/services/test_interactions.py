"""record_interaction logs the event and toggles the flag's dismissal on dismiss/undo."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.core.errors import FlagNotFoundError
from pattern_mirror.models.documents import Document
from pattern_mirror.models.engine import Flag, FlagDismissal, FlagInteraction
from pattern_mirror.models.enums import DocType, FlagInteractionKind
from pattern_mirror.models.identity import User
from pattern_mirror.services.analysis import analyze_document
from pattern_mirror.services.interactions import (
    deactivate_document_dismissals,
    record_interaction,
)

pytestmark = pytest.mark.db


def _manager(db_session: Session, suffix: str) -> User:
    user = User(
        external_user_id=f"interactions-{suffix}",
        legal_name="Interactions Manager",
        email=f"{suffix}@example.test",
    )
    db_session.add(user)
    db_session.flush()
    return user


def _flag_on_a_document(db_session: Session, owner: User) -> Flag:
    """A real persisted dictionary flag, carrying a genuine dismissal signature."""
    document = Document(owner_id=owner.id, doc_type=DocType.jd)
    db_session.add(document)
    db_session.flush()
    result = analyze_document(
        db_session,
        document_id=document.id,
        owner_id=owner.id,
        content="We want a digital native.",
    )
    return result.flags[0]


def _dismissals_for(db_session: Session, flag: Flag) -> list[FlagDismissal]:
    return list(
        db_session.scalars(
            select(FlagDismissal).where(FlagDismissal.document_id == flag.document_id)
        ).all()
    )


def test_accept_logs_an_event_and_writes_no_dismissal(db_session: Session) -> None:
    owner = _manager(db_session, "accept")
    flag = _flag_on_a_document(db_session, owner)

    record_interaction(
        db_session,
        flag_id=flag.id,
        owner_id=owner.id,
        kind=FlagInteractionKind.accept,
        accepted_alternative="recent graduate",
    )

    events = list(
        db_session.scalars(select(FlagInteraction).where(FlagInteraction.flag_id == flag.id)).all()
    )
    assert [e.kind for e in events] == [FlagInteractionKind.accept]
    assert events[0].accepted_alternative == "recent graduate"
    assert _dismissals_for(db_session, flag) == []


def test_dismiss_logs_an_event_and_writes_a_matching_dismissal(db_session: Session) -> None:
    owner = _manager(db_session, "dismiss")
    flag = _flag_on_a_document(db_session, owner)

    result = record_interaction(
        db_session, flag_id=flag.id, owner_id=owner.id, kind=FlagInteractionKind.dismiss
    )

    assert result.dismissal is not None
    dismissal = result.dismissal
    assert dismissal.active is True
    # The dismissal's signature is copied straight off the flag the manager saw.
    assert dismissal.document_id == flag.document_id
    assert dismissal.rule_id == flag.dictionary_entry_id
    assert dismissal.normalised_span == flag.normalised_span
    assert dismissal.sentence_fingerprint == flag.sentence_fingerprint


def test_undo_deactivates_the_dismissal(db_session: Session) -> None:
    owner = _manager(db_session, "undo")
    flag = _flag_on_a_document(db_session, owner)

    record_interaction(
        db_session, flag_id=flag.id, owner_id=owner.id, kind=FlagInteractionKind.dismiss
    )
    result = record_interaction(
        db_session, flag_id=flag.id, owner_id=owner.id, kind=FlagInteractionKind.undo
    )

    assert result.dismissal is not None
    assert result.dismissal.active is False
    events = list(
        db_session.scalars(select(FlagInteraction).where(FlagInteraction.flag_id == flag.id)).all()
    )
    assert [e.kind for e in events] == [FlagInteractionKind.dismiss, FlagInteractionKind.undo]


def test_undo_without_a_prior_dismissal_is_a_noop(db_session: Session) -> None:
    owner = _manager(db_session, "undo-noop")
    flag = _flag_on_a_document(db_session, owner)

    result = record_interaction(
        db_session, flag_id=flag.id, owner_id=owner.id, kind=FlagInteractionKind.undo
    )

    assert result.dismissal is None
    assert _dismissals_for(db_session, flag) == []


def test_redismiss_reuses_one_dismissal_row(db_session: Session) -> None:
    owner = _manager(db_session, "redismiss")
    flag = _flag_on_a_document(db_session, owner)

    record_interaction(
        db_session, flag_id=flag.id, owner_id=owner.id, kind=FlagInteractionKind.dismiss
    )
    record_interaction(
        db_session, flag_id=flag.id, owner_id=owner.id, kind=FlagInteractionKind.undo
    )
    record_interaction(
        db_session, flag_id=flag.id, owner_id=owner.id, kind=FlagInteractionKind.dismiss
    )

    dismissals = _dismissals_for(db_session, flag)
    assert len(dismissals) == 1
    assert dismissals[0].active is True


def test_a_flag_on_another_users_document_is_not_found(db_session: Session) -> None:
    owner = _manager(db_session, "owner")
    intruder = _manager(db_session, "intruder")
    flag = _flag_on_a_document(db_session, owner)

    with pytest.raises(FlagNotFoundError):
        record_interaction(
            db_session, flag_id=flag.id, owner_id=intruder.id, kind=FlagInteractionKind.dismiss
        )


def test_a_missing_flag_is_not_found(db_session: Session) -> None:
    owner = _manager(db_session, "missing")

    with pytest.raises(FlagNotFoundError):
        record_interaction(
            db_session, flag_id=uuid.uuid4(), owner_id=owner.id, kind=FlagInteractionKind.accept
        )


def test_recheck_deactivates_all_of_a_documents_active_dismissals(db_session: Session) -> None:
    owner = _manager(db_session, "recheck")
    flag = _flag_on_a_document(db_session, owner)
    record_interaction(
        db_session, flag_id=flag.id, owner_id=owner.id, kind=FlagInteractionKind.dismiss
    )

    count = deactivate_document_dismissals(db_session, flag.document_id)

    assert count == 1
    dismissals = _dismissals_for(db_session, flag)
    assert all(d.active is False for d in dismissals)


def test_recheck_leaves_another_documents_dismissals_untouched(db_session: Session) -> None:
    owner = _manager(db_session, "recheck-scope")
    mine = _flag_on_a_document(db_session, owner)
    other = _flag_on_a_document(db_session, owner)
    record_interaction(
        db_session, flag_id=mine.id, owner_id=owner.id, kind=FlagInteractionKind.dismiss
    )
    record_interaction(
        db_session, flag_id=other.id, owner_id=owner.id, kind=FlagInteractionKind.dismiss
    )

    deactivate_document_dismissals(db_session, mine.document_id)

    assert _dismissals_for(db_session, other)[0].active is True

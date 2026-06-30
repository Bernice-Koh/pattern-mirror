"""The Pattern Aggregator surfaces gender-correlated writing patterns and withholds noise."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from pattern_mirror.models.documents import AnalysisRun, Document
from pattern_mirror.models.engine import Flag
from pattern_mirror.models.enums import (
    AnalysisRunStatus,
    AnalysisTrigger,
    BiasCategory,
    DocType,
    FlagScope,
    FlagSourceStage,
    SubjectType,
)
from pattern_mirror.models.identity import Subject, User
from pattern_mirror.services.pattern_aggregator import (
    PatternMode,
    aggregate_writing_patterns,
)

pytestmark = pytest.mark.db

_THRESHOLD = 0.05


def _manager(session: Session, suffix: str) -> User:
    user = User(
        external_user_id=f"aggregator-{suffix}",
        legal_name="Aggregator Manager",
        email=f"{suffix}@example.test",
    )
    session.add(user)
    session.flush()
    return user


def _run(
    session: Session,
    document_id: uuid.UUID,
    *,
    status: AnalysisRunStatus = AnalysisRunStatus.complete,
    started_at: datetime | None = None,
) -> AnalysisRun:
    run = AnalysisRun(
        document_id=document_id,
        trigger=AnalysisTrigger.typing_pause,
        content_hash="0" * 64,
        status=status,
    )
    if started_at is not None:
        run.started_at = started_at
    session.add(run)
    session.flush()
    return run


def _flag(
    document_id: uuid.UUID,
    run_id: uuid.UUID,
    term: str,
    category: BiasCategory,
    *,
    suppressed: bool = False,
) -> Flag:
    return Flag(
        document_id=document_id,
        analysis_run_id=run_id,
        source_stage=FlagSourceStage.dictionary,
        category=category,
        scope=FlagScope.general,
        raw_span=term,
        normalised_span=term,
        sentence_fingerprint="f" * 64,
        rationale={},
        suppressed=suppressed,
    )


def _feedback(
    session: Session,
    owner: User,
    *,
    gender: str,
    terms: list[tuple[str, BiasCategory]],
    role_title: str | None = None,
    reference_jd_id: uuid.UUID | None = None,
    run_status: AnalysisRunStatus = AnalysisRunStatus.complete,
    suppressed_terms: tuple[str, ...] = (),
) -> Document:
    """A feedback note about one gendered subject, analysed once with ``terms`` flagged."""
    subject = Subject(subject_type=SubjectType.candidate, legal_name="Candidate", gender=gender)
    session.add(subject)
    session.flush()
    document = Document(
        owner_id=owner.id,
        doc_type=DocType.feedback,
        subject_id=subject.id,
        role_title=role_title,
        reference_jd_id=reference_jd_id,
    )
    session.add(document)
    session.flush()
    run = _run(session, document.id, status=run_status)
    for term, category in terms:
        session.add(_flag(document.id, run.id, term, category, suppressed=term in suppressed_terms))
    session.flush()
    return document


_SHARP = ("sharp", BiasCategory.gender)


def test_significant_pattern_surfaces_across_time(db_session: Session) -> None:
    owner = _manager(db_session, "surface")
    male_docs = [_feedback(db_session, owner, gender="male", terms=[_SHARP]) for _ in range(5)]
    for _ in range(5):
        _feedback(db_session, owner, gender="female", terms=[])

    patterns = aggregate_writing_patterns(db_session, owner_id=owner.id, threshold=_THRESHOLD)

    assert len(patterns) == 1
    pattern = patterns[0]
    assert pattern.mode is PatternMode.across_time
    assert pattern.term == "sharp"
    assert pattern.category is BiasCategory.gender
    assert pattern.p_value < _THRESHOLD
    assert pattern.group_counts == {"male": 5, "female": 0}
    assert pattern.supporting_count == 5
    assert set(pattern.document_ids) == {doc.id for doc in male_docs}


def test_balanced_term_is_withheld(db_session: Session) -> None:
    owner = _manager(db_session, "balanced")
    for _ in range(4):
        _feedback(db_session, owner, gender="male", terms=[("dependable", BiasCategory.gender)])
    for _ in range(4):
        _feedback(db_session, owner, gender="female", terms=[("dependable", BiasCategory.gender)])

    patterns = aggregate_writing_patterns(db_session, owner_id=owner.id, threshold=_THRESHOLD)

    assert patterns == []


def test_suppressed_flags_still_count_as_writing(db_session: Session) -> None:
    owner = _manager(db_session, "suppressed")
    for _ in range(5):
        _feedback(db_session, owner, gender="male", terms=[_SHARP], suppressed_terms=("sharp",))
    for _ in range(5):
        _feedback(db_session, owner, gender="female", terms=[])

    patterns = aggregate_writing_patterns(db_session, owner_id=owner.id, threshold=_THRESHOLD)

    assert len(patterns) == 1
    assert patterns[0].supporting_count == 5


def test_only_the_latest_complete_run_counts(db_session: Session) -> None:
    owner = _manager(db_session, "latest-run")
    # A male note whose term was removed on re-analysis: an older run flagged it, the newer did not.
    revised = _feedback(db_session, owner, gender="male", terms=[])
    older = _run(db_session, revised.id, started_at=datetime.now(UTC) - timedelta(hours=1))
    db_session.add(_flag(revised.id, older.id, "sharp", BiasCategory.gender))
    db_session.flush()
    for _ in range(4):
        _feedback(db_session, owner, gender="male", terms=[_SHARP])
    for _ in range(5):
        _feedback(db_session, owner, gender="female", terms=[])

    patterns = aggregate_writing_patterns(db_session, owner_id=owner.id, threshold=_THRESHOLD)

    assert len(patterns) == 1
    assert patterns[0].group_counts == {"male": 4, "female": 0}
    assert revised.id not in patterns[0].document_ids


def test_incomplete_runs_are_excluded(db_session: Session) -> None:
    owner = _manager(db_session, "incomplete")
    for _ in range(5):
        _feedback(
            db_session,
            owner,
            gender="male",
            terms=[_SHARP],
            run_status=AnalysisRunStatus.running,
        )
    for _ in range(5):
        _feedback(db_session, owner, gender="female", terms=[])

    patterns = aggregate_writing_patterns(db_session, owner_id=owner.id, threshold=_THRESHOLD)

    assert patterns == []


def test_per_role_pattern_is_scoped_to_one_role(db_session: Session) -> None:
    owner = _manager(db_session, "per-role")
    role_a = Document(owner_id=owner.id, doc_type=DocType.jd, role_title="Trader")
    role_b = Document(owner_id=owner.id, doc_type=DocType.jd, role_title="Analyst")
    db_session.add_all([role_a, role_b])
    db_session.flush()
    for _ in range(4):
        _feedback(
            db_session,
            owner,
            gender="male",
            terms=[_SHARP],
            reference_jd_id=role_a.id,
            role_title="Trader",
        )
    for _ in range(4):
        _feedback(
            db_session,
            owner,
            gender="female",
            terms=[],
            reference_jd_id=role_a.id,
            role_title="Trader",
        )
    for _ in range(3):
        _feedback(
            db_session,
            owner,
            gender="male",
            terms=[("dependable", BiasCategory.gender)],
            reference_jd_id=role_b.id,
            role_title="Analyst",
        )
    for _ in range(3):
        _feedback(
            db_session,
            owner,
            gender="female",
            terms=[("dependable", BiasCategory.gender)],
            reference_jd_id=role_b.id,
            role_title="Analyst",
        )

    patterns = aggregate_writing_patterns(db_session, owner_id=owner.id, threshold=_THRESHOLD)

    per_role = [pattern for pattern in patterns if pattern.mode is PatternMode.per_role]
    assert len(per_role) == 1
    assert per_role[0].role_title == "Trader"
    assert per_role[0].term == "sharp"


def test_no_documents_returns_empty(db_session: Session) -> None:
    owner = _manager(db_session, "empty")
    assert aggregate_writing_patterns(db_session, owner_id=owner.id, threshold=_THRESHOLD) == []

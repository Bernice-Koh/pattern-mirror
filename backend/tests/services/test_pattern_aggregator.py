"""The Pattern Aggregator surfaces gender-correlated writing patterns and withholds noise."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from pattern_mirror.models.documents import AnalysisRun, Document
from pattern_mirror.models.engine import Flag, FlagInteraction
from pattern_mirror.models.enums import (
    AnalysisRunStatus,
    AnalysisTrigger,
    BiasCategory,
    DocType,
    DocumentStatus,
    FlagInteractionKind,
    FlagScope,
    FlagSourceStage,
    SubjectType,
)
from pattern_mirror.models.identity import Subject, User
from pattern_mirror.services.pattern_aggregator import (
    AdoptionTrendPoint,
    CategoryImprovement,
    FlagVolumePoint,
    PatternMode,
    aggregate_adoption_trend,
    aggregate_category_improvements,
    aggregate_decision_patterns,
    aggregate_flag_volume_trend,
    aggregate_patterns,
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


def _decided_flag(
    session: Session,
    owner: User,
    *,
    category: BiasCategory,
    span: str,
    kind: FlagInteractionKind | None,
    present_in_final: bool,
    suppressed: bool = False,
    submitted_at: datetime | None = None,
) -> Document:
    """A submitted document carrying one flag the manager accepted, dismissed, or ignored."""
    final_text = f"a notably {span} contributor" if present_in_final else "a balanced contributor"
    document = Document(
        owner_id=owner.id,
        doc_type=DocType.feedback,
        status=DocumentStatus.submitted,
        submitted_content=final_text,
        submitted_at=submitted_at,
    )
    session.add(document)
    session.flush()
    run = _run(session, document.id)
    flag = _flag(document.id, run.id, span, category, suppressed=suppressed)
    session.add(flag)
    session.flush()
    if kind is not None:
        session.add(FlagInteraction(flag_id=flag.id, kind=kind))
        session.flush()
    return document


def test_decision_pattern_surfaces_a_category_adopted_differently(db_session: Session) -> None:
    owner = _manager(db_session, "decision")
    for index in range(6):
        _decided_flag(
            db_session,
            owner,
            category=BiasCategory.gender,
            span=f"aggressive{index}",
            kind=FlagInteractionKind.dismiss,
            present_in_final=True,  # dismissed and kept -> rejection
        )
    for index in range(6):
        _decided_flag(
            db_session,
            owner,
            category=BiasCategory.age,
            span=f"young{index}",
            kind=FlagInteractionKind.accept,
            present_in_final=False,  # explicit accept -> adoption
        )

    patterns = aggregate_decision_patterns(db_session, owner_id=owner.id, threshold=_THRESHOLD)

    by_category = {pattern.category: pattern for pattern in patterns}
    assert by_category[BiasCategory.gender].adoption_rate == 0.0
    assert by_category[BiasCategory.gender].rejected_count == 6
    assert by_category[BiasCategory.age].adoption_rate == 1.0
    assert by_category[BiasCategory.age].total_count == 6
    assert all(pattern.p_value < _THRESHOLD for pattern in patterns)


def test_uniform_decisions_surface_nothing(db_session: Session) -> None:
    owner = _manager(db_session, "uniform")
    for index, category in enumerate([BiasCategory.gender, BiasCategory.age] * 4):
        _decided_flag(
            db_session,
            owner,
            category=category,
            span=f"term{index}",
            kind=FlagInteractionKind.accept,
            present_in_final=False,
        )

    assert aggregate_decision_patterns(db_session, owner_id=owner.id, threshold=_THRESHOLD) == []


def test_unsurfaced_flags_do_not_count_as_decisions(db_session: Session) -> None:
    owner = _manager(db_session, "unsurfaced")
    # Judge-suppressed, never shown, never acted on: excluded from the adoption denominator.
    _decided_flag(
        db_session,
        owner,
        category=BiasCategory.gender,
        span="bossy",
        kind=None,
        present_in_final=True,
        suppressed=True,
    )

    assert aggregate_decision_patterns(db_session, owner_id=owner.id, threshold=_THRESHOLD) == []


def test_no_submitted_documents_returns_empty(db_session: Session) -> None:
    owner = _manager(db_session, "no-submit")
    _feedback(db_session, owner, gender="male", terms=[_SHARP])  # a draft run, never submitted

    assert aggregate_decision_patterns(db_session, owner_id=owner.id, threshold=_THRESHOLD) == []


def test_aggregate_patterns_returns_both_families(db_session: Session) -> None:
    owner = _manager(db_session, "report")
    male_docs = [_feedback(db_session, owner, gender="male", terms=[_SHARP]) for _ in range(5)]
    for _ in range(5):
        _feedback(db_session, owner, gender="female", terms=[])

    report = aggregate_patterns(db_session, owner_id=owner.id, threshold=_THRESHOLD)

    assert {doc.id for doc in male_docs} == set(report.writing_patterns[0].document_ids)
    assert report.decision_patterns == ()
    assert report.adoption_trend == ()  # the feedback notes were never submitted


def test_adoption_trend_buckets_by_submission_month(db_session: Session) -> None:
    owner = _manager(db_session, "trend")
    january = datetime(2026, 1, 15, tzinfo=UTC)
    february = datetime(2026, 2, 10, tzinfo=UTC)
    # January: one accepted, one dismissed-and-kept -> 1 of 2 adopted.
    _decided_flag(
        db_session,
        owner,
        category=BiasCategory.gender,
        span="sharp-jan-a",
        kind=FlagInteractionKind.accept,
        present_in_final=False,
        submitted_at=january,
    )
    _decided_flag(
        db_session,
        owner,
        category=BiasCategory.gender,
        span="sharp-jan-b",
        kind=FlagInteractionKind.dismiss,
        present_in_final=True,
        submitted_at=january,
    )
    # February: both accepted -> 2 of 2 adopted.
    for span in ("sharp-feb-a", "sharp-feb-b"):
        _decided_flag(
            db_session,
            owner,
            category=BiasCategory.gender,
            span=span,
            kind=FlagInteractionKind.accept,
            present_in_final=False,
            submitted_at=february,
        )

    trend = aggregate_adoption_trend(db_session, owner_id=owner.id)

    assert trend == [
        AdoptionTrendPoint(period="2026-01", adopted_count=1, total_count=2, adoption_rate=0.5),
        AdoptionTrendPoint(period="2026-02", adopted_count=2, total_count=2, adoption_rate=1.0),
    ]


def test_adoption_trend_empty_without_submissions(db_session: Session) -> None:
    owner = _manager(db_session, "trend-empty")
    _feedback(db_session, owner, gender="male", terms=[_SHARP])  # a draft run, never submitted

    assert aggregate_adoption_trend(db_session, owner_id=owner.id) == []


def test_adoption_trend_excludes_documents_without_a_submission_timestamp(
    db_session: Session,
) -> None:
    owner = _manager(db_session, "trend-no-timestamp")
    _decided_flag(
        db_session,
        owner,
        category=BiasCategory.gender,
        span="undated",
        kind=FlagInteractionKind.accept,
        present_in_final=False,
        submitted_at=None,
    )

    assert aggregate_adoption_trend(db_session, owner_id=owner.id) == []


def _submitted_doc(
    session: Session,
    owner: User,
    *,
    terms: list[tuple[str, BiasCategory]],
    submitted_at: datetime,
) -> Document:
    """A submitted document carrying ``terms`` as surfaced flags (an empty list is a clean doc)."""
    document = Document(
        owner_id=owner.id,
        doc_type=DocType.feedback,
        status=DocumentStatus.submitted,
        submitted_content="the final text",
        submitted_at=submitted_at,
    )
    session.add(document)
    session.flush()
    run = _run(session, document.id)
    for term, category in terms:
        session.add(_flag(document.id, run.id, term, category))
    session.flush()
    return document


def test_flag_volume_trend_averages_flags_per_document_by_month(db_session: Session) -> None:
    owner = _manager(db_session, "volume")
    january = datetime(2026, 1, 15, tzinfo=UTC)
    february = datetime(2026, 2, 10, tzinfo=UTC)
    # January: two flags on one doc, plus a clean doc -> 2 flags over 2 documents.
    _submitted_doc(
        db_session,
        owner,
        terms=[("sharp", BiasCategory.gender), ("aggressive", BiasCategory.gender)],
        submitted_at=january,
    )
    _submitted_doc(db_session, owner, terms=[], submitted_at=january)
    # February: one flag over three documents.
    _submitted_doc(db_session, owner, terms=[("bossy", BiasCategory.gender)], submitted_at=february)
    _submitted_doc(db_session, owner, terms=[], submitted_at=february)
    _submitted_doc(db_session, owner, terms=[], submitted_at=february)

    trend = aggregate_flag_volume_trend(db_session, owner_id=owner.id)

    assert trend == [
        FlagVolumePoint("2026-01", document_count=2, flag_count=2, flags_per_document=1.0),
        FlagVolumePoint("2026-02", document_count=3, flag_count=1, flags_per_document=1 / 3),
    ]


def test_flag_volume_trend_empty_without_submissions(db_session: Session) -> None:
    owner = _manager(db_session, "volume-empty")
    _feedback(db_session, owner, gender="male", terms=[_SHARP])  # a draft run, never submitted

    assert aggregate_flag_volume_trend(db_session, owner_id=owner.id) == []


def test_flag_volume_trend_excludes_unsurfaced_flags(db_session: Session) -> None:
    owner = _manager(db_session, "volume-suppressed")
    # Judge-suppressed, never shown, never acted on: not flagged language the manager saw.
    _decided_flag(
        db_session,
        owner,
        category=BiasCategory.gender,
        span="bossy",
        kind=None,
        present_in_final=True,
        suppressed=True,
        submitted_at=datetime(2026, 1, 15, tzinfo=UTC),
    )

    trend = aggregate_flag_volume_trend(db_session, owner_id=owner.id)

    assert trend == [
        FlagVolumePoint("2026-01", document_count=1, flag_count=0, flags_per_document=0.0)
    ]


def test_category_improvements_reports_a_fallen_category(db_session: Session) -> None:
    owner = _manager(db_session, "improved")
    _submitted_doc(
        db_session,
        owner,
        terms=[("sharp", BiasCategory.gender)],
        submitted_at=datetime(2026, 1, 15, tzinfo=UTC),
    )
    _submitted_doc(db_session, owner, terms=[], submitted_at=datetime(2026, 6, 10, tzinfo=UTC))

    improvements = aggregate_category_improvements(db_session, owner_id=owner.id)

    assert improvements == [
        CategoryImprovement(
            category=BiasCategory.gender,
            first_period="2026-01",
            last_period="2026-06",
            first_rate=1.0,
            last_rate=0.0,
            reduction=1.0,
        )
    ]


def test_category_improvements_needs_two_periods(db_session: Session) -> None:
    owner = _manager(db_session, "improved-one-period")
    _submitted_doc(
        db_session,
        owner,
        terms=[("sharp", BiasCategory.gender)],
        submitted_at=datetime(2026, 1, 15, tzinfo=UTC),
    )

    assert aggregate_category_improvements(db_session, owner_id=owner.id) == []


def test_category_improvements_excludes_a_worsened_category(db_session: Session) -> None:
    owner = _manager(db_session, "worsened")
    _submitted_doc(db_session, owner, terms=[], submitted_at=datetime(2026, 1, 15, tzinfo=UTC))
    _submitted_doc(
        db_session,
        owner,
        terms=[("sharp", BiasCategory.gender)],
        submitted_at=datetime(2026, 6, 10, tzinfo=UTC),
    )

    assert aggregate_category_improvements(db_session, owner_id=owner.id) == []


def test_category_improvements_order_largest_reduction_first(db_session: Session) -> None:
    owner = _manager(db_session, "improved-order")
    _submitted_doc(
        db_session,
        owner,
        terms=[
            ("sharp", BiasCategory.gender),
            ("aggressive", BiasCategory.gender),
            ("young", BiasCategory.age),
        ],
        submitted_at=datetime(2026, 1, 15, tzinfo=UTC),
    )
    _submitted_doc(db_session, owner, terms=[], submitted_at=datetime(2026, 6, 10, tzinfo=UTC))

    improvements = aggregate_category_improvements(db_session, owner_id=owner.id)

    assert [item.category for item in improvements] == [BiasCategory.gender, BiasCategory.age]
    assert [item.reduction for item in improvements] == [2.0, 1.0]

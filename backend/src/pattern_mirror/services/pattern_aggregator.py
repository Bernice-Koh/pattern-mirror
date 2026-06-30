"""The Pattern Aggregator: significant patterns over a manager's flag history (#66, §6/§13).

A deterministic Module — no LLM — that reads persisted flags, documents, and subjects, builds
the contingency tables, and surfaces only patterns clearing the Fisher's-exact gate. Writing
patterns correlate a coded term with a subject demographic; per-role narrows to one JD's
candidates, across-time spans the manager's whole history. The statistics live in
``significance``; this module is the queries and the table-building around them.
"""

import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import StrEnum, auto

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pattern_mirror.models.documents import AnalysisRun, Document
from pattern_mirror.models.engine import Flag
from pattern_mirror.models.enums import (
    AnalysisRunStatus,
    BiasCategory,
    DocType,
    FlagInteractionKind,
)
from pattern_mirror.models.identity import Subject
from pattern_mirror.services.behavioural_states import (
    ADOPTION_STATES,
    BehaviouralState,
    FlagOutcome,
    classify,
)
from pattern_mirror.services.significance import Contingency, fisher_p_value, is_significant

# Writing patterns correlate a term with the subject's gender; age (3+ bands) needs a
# one-vs-rest test and is deferred until a dimension beyond gender is in the demo data.
_DIMENSION_GENDER = "gender"

# Documents a writing pattern can be about: those describing a person, not the JD itself.
_SUBJECT_DOC_TYPES = (DocType.feedback, DocType.promotion)


class PatternMode(StrEnum):
    """Whether a writing pattern was computed within one role or across the manager's history."""

    per_role = auto()
    across_time = auto()


@dataclass(frozen=True)
class WritingPattern:
    """A coded term that correlates with subject gender beyond chance (design spec §2 View 3)."""

    mode: PatternMode
    term: str
    category: BiasCategory
    dimension: str
    group_counts: dict[str, int]
    supporting_count: int
    p_value: float
    role_title: str | None
    document_ids: tuple[uuid.UUID, ...]


@dataclass(frozen=True)
class DecisionPattern:
    """A bias category whose adoption rate differs from the rest beyond chance (§13, Layer 2)."""

    category: BiasCategory
    adopted_count: int
    rejected_count: int
    total_count: int
    adoption_rate: float
    p_value: float
    document_ids: tuple[uuid.UUID, ...]


@dataclass(frozen=True)
class AdoptionTrendPoint:
    """The manager's overall adoption rate within one calendar month (§13, the "over time" view).

    Descriptive, not significance-gated: a trend line states the rate, it makes no categorical
    claim, so the Fisher's gate that guards the decision patterns does not apply here.
    """

    period: str
    adopted_count: int
    total_count: int
    adoption_rate: float


@dataclass(frozen=True)
class FlagVolumePoint:
    """Average flags raised per submitted document within one calendar month (§2 View 3).

    A writing-volume trend: how much flagged language the manager wrote, not how they decided on it.
    Descriptive, not significance-gated, like the adoption trend.
    """

    period: str
    document_count: int
    flag_count: int
    flags_per_document: float


@dataclass(frozen=True)
class CategoryImprovement:
    """A bias category whose flags-per-document fell from the manager's first period to the latest.

    Only falls are reported (``reduction`` is always positive), so ``first_rate`` is never zero and
    the share reduction ``reduction / first_rate`` is well defined for the dashboard.
    """

    category: BiasCategory
    first_period: str
    last_period: str
    first_rate: float
    last_rate: float
    reduction: float


@dataclass(frozen=True)
class PatternReport:
    """The manager's full dashboard payload: both pattern families, each already gated."""

    writing_patterns: tuple[WritingPattern, ...]
    decision_patterns: tuple[DecisionPattern, ...]
    adoption_trend: tuple[AdoptionTrendPoint, ...]
    flag_volume_trend: tuple[FlagVolumePoint, ...]
    category_improvements: tuple[CategoryImprovement, ...]


@dataclass(frozen=True)
class _SubjectDoc:
    """A manager's analysed document about a subject: its grouping keys and flagged terms."""

    document_id: uuid.UUID
    group: str
    role_title: str | None
    reference_jd_id: uuid.UUID | None
    terms: frozenset[tuple[str, BiasCategory]]

    def _role_key(self) -> str | None:
        """The per-role grouping key: the linked JD if set, else the role title."""
        if self.reference_jd_id is not None:
            return str(self.reference_jd_id)
        return self.role_title


def _subject_document_rows(
    session: Session, owner_id: uuid.UUID
) -> list[tuple[uuid.UUID, str | None, uuid.UUID | None, str]]:
    """The manager's gendered-subject docs as (id, role_title, reference_jd_id, gender) rows."""
    rows = session.execute(
        select(Document.id, Document.role_title, Document.reference_jd_id, Subject.gender)
        .join(Subject, Document.subject_id == Subject.id)
        .where(
            Document.owner_id == owner_id,
            Document.doc_type.in_(_SUBJECT_DOC_TYPES),
            Subject.gender.is_not(None),
        )
    ).all()
    return [(doc_id, role_title, ref_jd, gender) for doc_id, role_title, ref_jd, gender in rows]


def _latest_complete_run_by_document(
    session: Session, document_ids: list[uuid.UUID]
) -> dict[uuid.UUID, uuid.UUID]:
    """Map each document to its newest complete run, so regenerated flags are not double-counted."""
    rows = session.execute(
        select(AnalysisRun.document_id, AnalysisRun.id)
        .where(
            AnalysisRun.document_id.in_(document_ids),
            AnalysisRun.status == AnalysisRunStatus.complete,
        )
        .order_by(AnalysisRun.document_id, AnalysisRun.started_at.desc(), AnalysisRun.id.desc())
    ).all()
    latest: dict[uuid.UUID, uuid.UUID] = {}
    for document_id, run_id in rows:
        latest.setdefault(document_id, run_id)
    return latest


def _terms_by_document(
    session: Session, run_by_document: dict[uuid.UUID, uuid.UUID]
) -> dict[uuid.UUID, frozenset[tuple[str, BiasCategory]]]:
    """The distinct (term, category) flagged in each document's latest run, suppressed included."""
    document_by_run = {run_id: document_id for document_id, run_id in run_by_document.items()}
    rows = session.execute(
        select(Flag.analysis_run_id, Flag.normalised_span, Flag.category).where(
            Flag.analysis_run_id.in_(list(document_by_run))
        )
    ).all()
    accumulator: dict[uuid.UUID, set[tuple[str, BiasCategory]]] = defaultdict(set)
    for run_id, span, category in rows:
        accumulator[document_by_run[run_id]].add((span, category))
    return {document_id: frozenset(terms) for document_id, terms in accumulator.items()}


def _load_subject_docs(session: Session, owner_id: uuid.UUID) -> list[_SubjectDoc]:
    """Assemble the analysed subject-documents the writing patterns are computed over."""
    rows = _subject_document_rows(session, owner_id)
    document_ids = [doc_id for doc_id, _, _, _ in rows]
    if not document_ids:
        return []
    run_by_document = _latest_complete_run_by_document(session, document_ids)
    terms_by_document = _terms_by_document(session, run_by_document)
    return [
        _SubjectDoc(
            document_id=doc_id,
            group=gender,
            role_title=role_title,
            reference_jd_id=ref_jd,
            terms=terms_by_document.get(doc_id, frozenset()),
        )
        for doc_id, role_title, ref_jd, gender in rows
        if doc_id in run_by_document
    ]


def _present_count(docs: list[_SubjectDoc], group: str, term: str, category: BiasCategory) -> int:
    """How many of ``group``'s documents flagged ``(term, category)``."""
    return sum(1 for doc in docs if doc.group == group and (term, category) in doc.terms)


def _patterns_over(
    docs: list[_SubjectDoc], mode: PatternMode, threshold: float, role_title: str | None
) -> list[WritingPattern]:
    """Run Fisher's per term over a document set already scoped to one mode (and role)."""
    group_totals = Counter(doc.group for doc in docs)
    if len(group_totals) < 2:
        return []
    (group_a, total_a), (group_b, total_b) = group_totals.most_common(2)
    scoped = [doc for doc in docs if doc.group in (group_a, group_b)]
    all_terms = {term for doc in scoped for term in doc.terms}

    patterns: list[WritingPattern] = []
    for term, category in sorted(all_terms):
        present_a = _present_count(scoped, group_a, term, category)
        present_b = _present_count(scoped, group_b, term, category)
        table = Contingency(present_a, present_b, total_a - present_a, total_b - present_b)
        p_value = fisher_p_value(table)
        if not is_significant(p_value, threshold):
            continue
        document_ids = tuple(doc.document_id for doc in scoped if (term, category) in doc.terms)
        patterns.append(
            WritingPattern(
                mode=mode,
                term=term,
                category=category,
                dimension=_DIMENSION_GENDER,
                group_counts={group_a: present_a, group_b: present_b},
                supporting_count=present_a + present_b,
                p_value=p_value,
                role_title=role_title,
                document_ids=document_ids,
            )
        )
    return patterns


def _per_role_patterns(docs: list[_SubjectDoc], threshold: float) -> list[WritingPattern]:
    """Group documents by role and run the writing-pattern test within each named role."""
    by_role: dict[str, list[_SubjectDoc]] = defaultdict(list)
    for doc in docs:
        role_key = doc._role_key()
        if role_key is not None:
            by_role[role_key].append(doc)
    patterns: list[WritingPattern] = []
    for role_docs in by_role.values():
        role_title = role_docs[0].role_title
        patterns.extend(_patterns_over(role_docs, PatternMode.per_role, threshold, role_title))
    return patterns


def aggregate_writing_patterns(
    session: Session, *, owner_id: uuid.UUID, threshold: float
) -> list[WritingPattern]:
    """Surface the manager's significant writing patterns, per-role and across-time.

    Args:
        session: The active database session.
        owner_id: The manager whose history is analysed (their data only).
        threshold: The Fisher's-exact significance bar; patterns at or above it are withheld.

    Returns:
        Significant patterns sorted by ascending p-value then term, across both modes.
    """
    docs = _load_subject_docs(session, owner_id)
    patterns = _patterns_over(docs, PatternMode.across_time, threshold, None)
    patterns.extend(_per_role_patterns(docs, threshold))
    patterns.sort(key=lambda pattern: (pattern.p_value, pattern.term, pattern.category.value))
    return patterns


@dataclass(frozen=True)
class _ClassifiedFlag:
    """One distinct flagged thing on a submitted document, reduced to its behavioural state."""

    document_id: uuid.UUID
    category: BiasCategory
    state: BehaviouralState


def _submitted_content_by_document(session: Session, owner_id: uuid.UUID) -> dict[uuid.UUID, str]:
    """The manager's submitted documents mapped to their final text (the §13 outcome of record)."""
    rows = session.execute(
        select(Document.id, Document.submitted_content).where(
            Document.owner_id == owner_id,
            Document.submitted_content.is_not(None),
        )
    ).all()
    return {doc_id: content for doc_id, content in rows if content is not None}


@dataclass(frozen=True)
class _FlagGroup:
    """One distinct flagged thing the manager saw: a ``(document, span, fingerprint)`` group."""

    document_id: uuid.UUID
    category: BiasCategory
    raw_span: str
    interaction_kinds: tuple[FlagInteractionKind, ...]


def _surfaced_flag_groups(session: Session, document_ids: list[uuid.UUID]) -> list[_FlagGroup]:
    """Group each document's flags by ``(span, fingerprint)`` and keep the ones the manager saw.

    Flags regenerate every run, so a dismissal recorded on one run's flag and the surviving flag
    on a later run share a signature; grouping collects the decision wherever it was logged. A group
    never surfaced (all suppressed, no interaction) is a flag the manager never saw.
    """
    flags = session.scalars(
        select(Flag)
        .where(Flag.document_id.in_(document_ids))
        .options(selectinload(Flag.interactions))
    ).all()
    by_signature: dict[tuple[uuid.UUID, str, str], list[Flag]] = defaultdict(list)
    for flag in flags:
        signature = (flag.document_id, flag.normalised_span, flag.sentence_fingerprint)
        by_signature[signature].append(flag)

    groups: list[_FlagGroup] = []
    for (document_id, _, _), group in by_signature.items():
        interactions = sorted(
            (event for flag in group for event in flag.interactions),
            key=lambda event: event.created_at,
        )
        surfaced = any(not flag.suppressed for flag in group) or bool(interactions)
        if not surfaced:
            continue
        groups.append(
            _FlagGroup(
                document_id=document_id,
                category=group[0].category,
                raw_span=group[0].raw_span,
                interaction_kinds=tuple(event.kind for event in interactions),
            )
        )
    return groups


def _classified_flags(
    session: Session, content_by_document: dict[uuid.UUID, str]
) -> list[_ClassifiedFlag]:
    """Reduce each surfaced flag on the submitted documents to its behavioural state."""
    classified: list[_ClassifiedFlag] = []
    for group in _surfaced_flag_groups(session, list(content_by_document)):
        state = classify(
            FlagOutcome(
                flagged_text=group.raw_span,
                interaction_kinds=group.interaction_kinds,
                final_text=content_by_document[group.document_id],
            )
        )
        classified.append(_ClassifiedFlag(group.document_id, group.category, state))
    return classified


def _decision_pattern_for(
    category: BiasCategory, classified: list[_ClassifiedFlag], threshold: float
) -> DecisionPattern | None:
    """One category's adoption-rate pattern, tested against the other categories; None if noise."""
    in_category = [item for item in classified if item.category is category]
    others = [item for item in classified if item.category is not category]
    adopted = sum(1 for item in in_category if item.state in ADOPTION_STATES)
    other_adopted = sum(1 for item in others if item.state in ADOPTION_STATES)
    table = Contingency(
        adopted, other_adopted, len(in_category) - adopted, len(others) - other_adopted
    )
    p_value = fisher_p_value(table)
    if not is_significant(p_value, threshold):
        return None
    return DecisionPattern(
        category=category,
        adopted_count=adopted,
        rejected_count=len(in_category) - adopted,
        total_count=len(in_category),
        adoption_rate=adopted / len(in_category),
        p_value=p_value,
        document_ids=tuple(sorted({item.document_id for item in in_category}, key=str)),
    )


def aggregate_decision_patterns(
    session: Session, *, owner_id: uuid.UUID, threshold: float
) -> list[DecisionPattern]:
    """Surface bias categories the manager adopts or rejects at a significantly different rate.

    Args:
        session: The active database session.
        owner_id: The manager whose decisions are analysed (their data only, never HR's).
        threshold: The Fisher's-exact significance bar; categories at or above it are withheld.

    Returns:
        Significant decision patterns sorted by ascending p-value then category.
    """
    content_by_document = _submitted_content_by_document(session, owner_id)
    if not content_by_document:
        return []
    classified = _classified_flags(session, content_by_document)
    categories = {item.category for item in classified}
    patterns = [
        pattern
        for category in categories
        if (pattern := _decision_pattern_for(category, classified, threshold)) is not None
    ]
    patterns.sort(key=lambda pattern: (pattern.p_value, pattern.category.value))
    return patterns


def _period_by_document(session: Session, owner_id: uuid.UUID) -> dict[uuid.UUID, str]:
    """Map each submitted document to its ``YYYY-MM`` submission month, the trend's time anchor."""
    rows = session.execute(
        select(Document.id, Document.submitted_at).where(
            Document.owner_id == owner_id,
            Document.submitted_content.is_not(None),
            Document.submitted_at.is_not(None),
        )
    ).all()
    return {doc_id: submitted_at.strftime("%Y-%m") for doc_id, submitted_at in rows}


def aggregate_adoption_trend(session: Session, *, owner_id: uuid.UUID) -> list[AdoptionTrendPoint]:
    """Track the manager's overall adoption rate month by month (design spec §13, "over time").

    Buckets every classified flag by the submission month of its document and reports the share
    that landed in an adoption state. Descriptive context for the dashboard, not a gated claim.

    Args:
        session: The active database session.
        owner_id: The manager whose decisions are analysed (their data only, never HR's).

    Returns:
        One point per month the manager submitted a flagged document, ordered chronologically.
    """
    content_by_document = _submitted_content_by_document(session, owner_id)
    if not content_by_document:
        return []
    period_by_document = _period_by_document(session, owner_id)
    states_by_period: dict[str, list[BehaviouralState]] = defaultdict(list)
    for item in _classified_flags(session, content_by_document):
        period = period_by_document.get(item.document_id)
        if period is not None:
            states_by_period[period].append(item.state)

    trend: list[AdoptionTrendPoint] = []
    for period in sorted(states_by_period):
        states = states_by_period[period]
        adopted = sum(1 for state in states if state in ADOPTION_STATES)
        trend.append(
            AdoptionTrendPoint(
                period=period,
                adopted_count=adopted,
                total_count=len(states),
                adoption_rate=adopted / len(states),
            )
        )
    return trend


def aggregate_flag_volume_trend(session: Session, *, owner_id: uuid.UUID) -> list[FlagVolumePoint]:
    """Track the average flags raised per submitted document, month by month (§2 View 3).

    Counts the distinct flags the manager was shown on each submitted document and averages them
    over every document submitted that month, so a clean document pulls the average down. The
    writing-volume counterpart to the adoption trend: descriptive context, not a gated claim.

    Args:
        session: The active database session.
        owner_id: The manager whose writing is analysed (their data only, never HR's).

    Returns:
        One point per month the manager submitted a document, ordered chronologically.
    """
    period_by_document = _period_by_document(session, owner_id)
    if not period_by_document:
        return []
    documents_by_period: Counter[str] = Counter(period_by_document.values())
    flags_by_period: Counter[str] = Counter()
    for group in _surfaced_flag_groups(session, list(period_by_document)):
        period = period_by_document.get(group.document_id)
        if period is not None:
            flags_by_period[period] += 1

    return [
        FlagVolumePoint(
            period=period,
            document_count=documents_by_period[period],
            flag_count=flags_by_period[period],
            flags_per_document=flags_by_period[period] / documents_by_period[period],
        )
        for period in sorted(documents_by_period)
    ]


def aggregate_category_improvements(
    session: Session, *, owner_id: uuid.UUID
) -> list[CategoryImprovement]:
    """Per-category fall in flags-per-document from the manager's first period to the latest.

    Compares each bias category's average flags per document in the earliest month against the
    latest and reports only the categories that fell. Needs at least two months to establish a
    trend; with less history it returns nothing rather than inventing one.

    Args:
        session: The active database session.
        owner_id: The manager whose writing is analysed (their data only, never HR's).

    Returns:
        Improved categories, largest reduction first.
    """
    period_by_document = _period_by_document(session, owner_id)
    periods = sorted(set(period_by_document.values()))
    if len(periods) < 2:
        return []
    first, last = periods[0], periods[-1]
    documents_by_period: Counter[str] = Counter(period_by_document.values())

    first_flags: Counter[BiasCategory] = Counter()
    last_flags: Counter[BiasCategory] = Counter()
    for group in _surfaced_flag_groups(session, list(period_by_document)):
        period = period_by_document.get(group.document_id)
        if period == first:
            first_flags[group.category] += 1
        elif period == last:
            last_flags[group.category] += 1

    improvements: list[CategoryImprovement] = []
    for category in first_flags.keys() | last_flags.keys():
        first_rate = first_flags[category] / documents_by_period[first]
        last_rate = last_flags[category] / documents_by_period[last]
        reduction = first_rate - last_rate
        if reduction > 0:
            improvements.append(
                CategoryImprovement(
                    category=category,
                    first_period=first,
                    last_period=last,
                    first_rate=first_rate,
                    last_rate=last_rate,
                    reduction=reduction,
                )
            )
    improvements.sort(key=lambda item: (-item.reduction, item.category.value))
    return improvements


def aggregate_patterns(session: Session, *, owner_id: uuid.UUID, threshold: float) -> PatternReport:
    """The Module's public face: the gated pattern families plus the descriptive trends."""
    return PatternReport(
        writing_patterns=tuple(
            aggregate_writing_patterns(session, owner_id=owner_id, threshold=threshold)
        ),
        decision_patterns=tuple(
            aggregate_decision_patterns(session, owner_id=owner_id, threshold=threshold)
        ),
        adoption_trend=tuple(aggregate_adoption_trend(session, owner_id=owner_id)),
        flag_volume_trend=tuple(aggregate_flag_volume_trend(session, owner_id=owner_id)),
        category_improvements=tuple(aggregate_category_improvements(session, owner_id=owner_id)),
    )

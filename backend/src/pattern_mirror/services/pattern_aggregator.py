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
from sqlalchemy.orm import Session

from pattern_mirror.models.documents import AnalysisRun, Document
from pattern_mirror.models.engine import Flag
from pattern_mirror.models.enums import AnalysisRunStatus, BiasCategory, DocType
from pattern_mirror.models.identity import Subject
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

"""Standalone synthetic seed for the dictionary-growth review queue (#72 manual testing).

Inserts a few queued additions, each with its proposal, four agent arguments, and a citation, so
the HR review queue, the audit modal (#91), and approve/reject/defer render against real data
without running the live four-agent pipeline. Synthetic data only, idempotent by phrase, and
deliberately NOT part of ``seed_demo`` — run on demand:
``python -m pattern_mirror.jobs.seed_growth_demo``.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.db.session import get_sessionmaker
from pattern_mirror.jobs.seed_demo import DEMO_HR_EXTERNAL_ID
from pattern_mirror.models.audit import AgentRun
from pattern_mirror.models.enums import (
    AgentName,
    BiasCategory,
    CitationSourceType,
    DictionaryAdditionStatus,
    FlagScope,
)
from pattern_mirror.models.growth import DictionaryProposal, PendingDictionaryAddition
from pattern_mirror.models.identity import User
from pattern_mirror.models.reference import Citation

_MODEL = "seed-demo"


@dataclass(frozen=True)
class _CitationSeed:
    source_type: CitationSourceType
    title: str
    reference: str
    publication_year: int | None
    finding: str


@dataclass(frozen=True)
class _CandidateSeed:
    phrase: str
    category: BiasCategory
    explanation: str
    proposer_reasoning: str
    skeptic_supports: bool
    skeptic_reasoning: str
    categorizer_reasoning: str
    citation_reasoning: str
    citation: _CitationSeed
    deferred: bool = False


# Multiword synthetic phrases unlikely to collide with the seeded SG lexicon, so an approval in
# the demo creates a fresh live row rather than a duplicate-entry conflict.
CANDIDATES: list[_CandidateSeed] = [
    _CandidateSeed(
        phrase="high-energy self-starter",
        category=BiasCategory.age,
        explanation="Youth-coded energy language that deters experienced older applicants.",
        proposer_reasoning=(
            "'High-energy' pairs stamina with youth and signals a preference for younger hires "
            "without any job-related basis."
        ),
        skeptic_supports=True,
        skeptic_reasoning=(
            "It reads as generic enthusiasm, but the repeated pairing with 'self-starter' skews "
            "the applicant pool younger, so it still merits an entry."
        ),
        categorizer_reasoning="Applies across hiring broadly, not to one role.",
        citation_reasoning="TAFEP guidance names energy-coded phrasing as age-discriminatory.",
        citation=_CitationSeed(
            source_type=CitationSourceType.tafep,
            title="TAFEP Fair Employment Guidelines",
            reference="TAFEP-FEG-2021-4.2",
            publication_year=2021,
            finding="Age-coded phrasing such as 'high-energy' discourages older applicants.",
        ),
    ),
    _CandidateSeed(
        phrase="cultural fit",
        category=BiasCategory.race,
        explanation="Vague 'fit' language that masks in-group bias on race and nationality.",
        proposer_reasoning=(
            "'Cultural fit' rewards similarity to the existing team and reliably screens out "
            "candidates from different backgrounds."
        ),
        skeptic_supports=False,
        skeptic_reasoning=(
            "Some teams mean values alignment, which is legitimate; the phrase is broad enough "
            "that a blanket dictionary entry risks over-flagging."
        ),
        categorizer_reasoning="Bias is general across hiring, not confined to a single role.",
        citation_reasoning="Research links unstructured 'fit' judgements to demographic bias.",
        citation=_CitationSeed(
            source_type=CitationSourceType.academic,
            title="Hiring as Cultural Matching",
            reference="doi:10.1177/0003122412463213",
            publication_year=2012,
            finding="'Cultural fit' judgements reproduce evaluators' own demographic backgrounds.",
        ),
    ),
    _CandidateSeed(
        phrase="recent graduate",
        category=BiasCategory.age,
        explanation="Recency-of-graduation framing that excludes career-changers.",
        proposer_reasoning=(
            "Requiring a 'recent graduate' uses time since study as a proxy for age and excludes "
            "equally qualified older candidates."
        ),
        skeptic_supports=True,
        skeptic_reasoning=(
            "It can describe a genuine early-career level, but as written it gates on age rather "
            "than skill, so it belongs in the dictionary."
        ),
        categorizer_reasoning="A broadly biased hiring phrase, not role-specific.",
        citation_reasoning="Guidance flags graduation-recency as indirect age bias.",
        citation=_CitationSeed(
            source_type=CitationSourceType.regulatory,
            title="Guidelines on Non-Discriminatory Job Advertisements",
            reference="MOM-JA-2019-3",
            publication_year=2019,
            finding="Recency-of-graduation criteria indirectly discriminate on age.",
        ),
    ),
    _CandidateSeed(
        phrase="native english speaker",
        category=BiasCategory.nationality,
        explanation="Nativeness framing that screens on nationality and race rather than ability.",
        proposer_reasoning=(
            "'Native speaker' gates on where someone grew up rather than their actual command of "
            "the language, excluding fluent non-native candidates."
        ),
        skeptic_supports=True,
        skeptic_reasoning=(
            "Language proficiency can be a real requirement, but 'native' is the wrong proxy for "
            "it and skews on nationality, so it warrants an entry."
        ),
        categorizer_reasoning="Applies across roles wherever language is listed — general.",
        citation_reasoning="TAFEP treats 'native speaker' wording as a nationality proxy.",
        citation=_CitationSeed(
            source_type=CitationSourceType.tafep,
            title="TAFEP Fair Employment Guidelines",
            reference="TAFEP-FEG-2021-5.1",
            publication_year=2021,
            finding="'Native speaker' requirements indirectly discriminate on nationality.",
        ),
        deferred=True,
    ),
]


def _lemma(phrase: str) -> str:
    """A demo lemma key; the real matcher lemmatises, but display and uniqueness only need this."""
    return phrase.lower().strip()


def _agent_runs(proposal_id: uuid.UUID, candidate: _CandidateSeed) -> list[AgentRun]:
    """The four agent arguments the audit modal replays, with the outputs each agent records."""
    citation = candidate.citation
    outputs = {
        AgentName.proposer: {
            "supports_inclusion": True,
            "category": candidate.category.value,
            "reasoning": candidate.proposer_reasoning,
        },
        AgentName.skeptic: {
            "supports_inclusion": candidate.skeptic_supports,
            "reasoning": candidate.skeptic_reasoning,
        },
        AgentName.categorizer: {
            "scope": FlagScope.general.value,
            "reasoning": candidate.categorizer_reasoning,
        },
        AgentName.citation: {
            "found_support": True,
            "citation": {
                "source_type": citation.source_type.value,
                "title": citation.title,
                "reference": citation.reference,
                "publication_year": citation.publication_year,
                "finding": citation.finding,
            },
            "reasoning": candidate.citation_reasoning,
        },
    }
    return [
        AgentRun(
            agent_name=agent_name,
            model=_MODEL,
            input={"phrase": candidate.phrase},
            output=output,
            proposal_id=proposal_id,
        )
        for agent_name, output in outputs.items()
    ]


def seed_growth_queue(session: Session, *, hr_user_id: uuid.UUID | None = None) -> int:
    """Insert any demo candidate not already queued; return how many were created.

    Args:
        session: An open database session; the caller owns the transaction.
        hr_user_id: The reviewer stamped on the deferred candidate, if a demo HR user exists.

    Returns:
        The number of new pending additions inserted (0 on a re-run).
    """
    queued = set(session.scalars(select(PendingDictionaryAddition.lemma_key)).all())
    created = 0
    for candidate in CANDIDATES:
        lemma_key = _lemma(candidate.phrase)
        if lemma_key in queued:
            continue

        citation = candidate.citation
        citation_row = Citation(
            source_type=citation.source_type,
            title=citation.title,
            reference=citation.reference,
            publication_year=citation.publication_year,
            finding=citation.finding,
        )
        session.add(citation_row)
        session.flush()

        proposal = DictionaryProposal(
            phrase=candidate.phrase,
            lemma_key=lemma_key,
            citation_id=citation_row.id,
        )
        session.add(proposal)
        session.flush()
        session.add_all(_agent_runs(proposal.id, candidate))

        addition = PendingDictionaryAddition(
            proposal_id=proposal.id,
            phrase=candidate.phrase,
            lemma_key=lemma_key,
            proposed_category=candidate.category,
            explanation=candidate.explanation,
        )
        if candidate.deferred:
            addition.status = DictionaryAdditionStatus.deferred
            addition.decided_by = hr_user_id
            addition.decided_at = datetime.now(UTC)
        session.add(addition)
        session.flush()
        created += 1

    return created


def main() -> None:  # pragma: no cover
    """Seed the growth review queue against the configured database, committing once."""
    session = get_sessionmaker()()
    try:
        hr_user = session.scalar(select(User).where(User.external_user_id == DEMO_HR_EXTERNAL_ID))
        seed_growth_queue(session, hr_user_id=hr_user.id if hr_user else None)
        session.commit()
    finally:
        session.close()


if __name__ == "__main__":  # pragma: no cover
    main()

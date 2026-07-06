"""Standalone synthetic seed for the dictionary-growth review queue (#72 manual testing).

Inserts queued additions across every bias category, each with its proposal, four agent arguments,
a citation, and a spread of backing contextual flags — so the HR review queue, the audit modal
(#91), approve/reject/defer, and the word cloud (sized by flag count, coloured by category) all
render against real data without running the live four-agent pipeline. The backing flags sit on an
unsubmitted draft owned by a synthetic non-persona user, so they weight the cloud without touching
the HR or Pattern Dashboard aggregates. Synthetic data only, idempotent by phrase, and deliberately
NOT part of ``seed_demo`` — run on demand: ``python -m pattern_mirror.jobs.seed_growth_demo``.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.db.session import get_sessionmaker
from pattern_mirror.jobs.seed_demo import DEMO_HR_EXTERNAL_ID
from pattern_mirror.models.audit import AgentRun
from pattern_mirror.models.documents import Document
from pattern_mirror.models.engine import Flag
from pattern_mirror.models.enums import (
    AgentName,
    BiasCategory,
    CitationSourceType,
    DictionaryAdditionStatus,
    DocType,
    FlagScope,
    FlagSourceStage,
)
from pattern_mirror.models.growth import DictionaryProposal, PendingDictionaryAddition
from pattern_mirror.models.identity import User
from pattern_mirror.models.reference import Citation

_MODEL = "seed-demo"

# Owner of the throwaway JD drafts that back each candidate's word-cloud weight. Deliberately not a
# demo persona and never submitted, so these flags size the cloud without touching the HR or Pattern
# Dashboard aggregates, which read submitted documents only.
_FLAG_OWNER_EXTERNAL_ID = "demo-growth-flags"


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
    # Contextual-pass hits backing this candidate — the recurrence that triggered review, and the
    # word-cloud weight. Higher = larger and more central in the cloud (design spec section 4).
    flag_count: int = 1
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
        flag_count=17,
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
        flag_count=24,
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
        flag_count=9,
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
        flag_count=4,
        deferred=True,
    ),
    _CandidateSeed(
        phrase="work hard play hard",
        category=BiasCategory.gender,
        explanation="Bro-culture framing that skews the applicant pool male.",
        proposer_reasoning=(
            "'Work hard, play hard' signals a masculine social culture and deters women and "
            "carers, with no bearing on the work itself."
        ),
        skeptic_supports=True,
        skeptic_reasoning=(
            "It sounds like harmless culture-setting, but the phrase reliably reads as male-coded "
            "and narrows the pool, so it warrants an entry."
        ),
        categorizer_reasoning="A general culture-coded phrase seen across many roles.",
        citation_reasoning="Gendered-wording research flags the phrase as masculine-coded.",
        citation=_CitationSeed(
            source_type=CitationSourceType.academic,
            title="Evidence That Gendered Wording in Job Advertisements Exists",
            reference="doi:10.1037/a0022530",
            publication_year=2011,
            finding="Masculine-coded wording lowers job appeal for women applicants.",
        ),
        flag_count=21,
    ),
    _CandidateSeed(
        phrase="no family commitments",
        category=BiasCategory.family_status,
        explanation="Availability framing that screens out carers and parents.",
        proposer_reasoning=(
            "Asking for 'no family commitments' filters on caregiving status rather than the "
            "ability to do the job, which disadvantages women in particular."
        ),
        skeptic_supports=True,
        skeptic_reasoning=(
            "A role may have real availability needs, but this phrasing gates on family status "
            "directly, so it belongs in the dictionary."
        ),
        categorizer_reasoning="Applies across roles wherever availability is described — general.",
        citation_reasoning="TAFEP names family-status criteria discriminatory unless justified.",
        citation=_CitationSeed(
            source_type=CitationSourceType.tafep,
            title="TAFEP Fair Employment Guidelines",
            reference="TAFEP-FEG-2021-6.3",
            publication_year=2021,
            finding="Family-status criteria discourage carers and are rarely job-justified.",
        ),
        flag_count=14,
    ),
    _CandidateSeed(
        phrase="able-bodied",
        category=BiasCategory.disability,
        explanation="Physical-ability framing not tied to a specific job task.",
        proposer_reasoning=(
            "'Able-bodied' excludes candidates with disabilities without naming the actual "
            "physical task the role requires."
        ),
        skeptic_supports=True,
        skeptic_reasoning=(
            "Some roles have genuine physical demands, but those should be stated as tasks; "
            "'able-bodied' as a blanket term is discriminatory."
        ),
        categorizer_reasoning="A general disability-coded term, not confined to one role.",
        citation_reasoning="Guidance requires job-task justification, not blanket ability terms.",
        citation=_CitationSeed(
            source_type=CitationSourceType.regulatory,
            title="Guidelines on Non-Discriminatory Job Advertisements",
            reference="MOM-JA-2019-7",
            publication_year=2019,
            finding="Blanket physical-ability requirements exclude disabled applicants.",
        ),
        flag_count=7,
    ),
    _CandidateSeed(
        phrase="clean-shaven",
        category=BiasCategory.religion,
        explanation="Grooming requirement that conflicts with religious practice.",
        proposer_reasoning=(
            "A 'clean-shaven' requirement burdens candidates whose faith involves facial hair, "
            "with no job-related basis in most roles."
        ),
        skeptic_supports=True,
        skeptic_reasoning=(
            "Specific safety roles may need it, but as a general appearance rule it screens on "
            "religion and should be flagged."
        ),
        categorizer_reasoning="A general appearance rule, not specific to a single safety role.",
        citation_reasoning="TAFEP treats unjustified grooming rules as religious discrimination.",
        citation=_CitationSeed(
            source_type=CitationSourceType.tafep,
            title="TAFEP Fair Employment Guidelines",
            reference="TAFEP-FEG-2021-8.1",
            publication_year=2021,
            finding="Grooming rules not justified by the job can discriminate on religion.",
        ),
        flag_count=5,
    ),
    _CandidateSeed(
        phrase="fresh perspective",
        category=BiasCategory.age,
        explanation="Novelty framing frequently used as a proxy for youth.",
        proposer_reasoning=(
            "'Fresh perspective' is often shorthand for a younger hire and pairs with other "
            "youth-coded language in the same posts."
        ),
        skeptic_supports=False,
        skeptic_reasoning=(
            "It can genuinely mean new thinking from any age; a dictionary entry risks flagging "
            "legitimate calls for innovation."
        ),
        categorizer_reasoning="Broad hiring phrase, not tied to a single role.",
        citation_reasoning="AARP research links novelty framing to age-biased shortlisting.",
        citation=_CitationSeed(
            source_type=CitationSourceType.academic,
            title="Age Bias in Hiring Language",
            reference="doi:10.1093/geront/gnw067",
            publication_year=2016,
            finding="Novelty-coded phrasing lowers callback rates for older applicants.",
        ),
        flag_count=11,
    ),
    _CandidateSeed(
        phrase="mother tongue proficiency",
        category=BiasCategory.race,
        explanation="Heritage-language framing that stands in for race or ethnicity.",
        proposer_reasoning=(
            "'Mother tongue proficiency' asks for a heritage relationship to a language rather "
            "than demonstrable skill, standing in for ethnicity."
        ),
        skeptic_supports=True,
        skeptic_reasoning=(
            "Language skill can be a real need, but 'mother tongue' gates on heritage, so it "
            "belongs in the dictionary."
        ),
        categorizer_reasoning="Applies across roles that list language needs — general.",
        citation_reasoning="TAFEP treats heritage-language wording as an indirect race proxy.",
        citation=_CitationSeed(
            source_type=CitationSourceType.tafep,
            title="TAFEP Fair Employment Guidelines",
            reference="TAFEP-FEG-2021-5.4",
            publication_year=2021,
            finding="'Mother tongue' requirements indirectly discriminate on race and ethnicity.",
        ),
        flag_count=2,
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


def _flag_owner(session: Session) -> User:
    """The synthetic owner of the JD drafts that back the candidates' word-cloud weights."""
    owner = session.scalar(select(User).where(User.external_user_id == _FLAG_OWNER_EXTERNAL_ID))
    if owner is None:
        owner = User(
            external_user_id=_FLAG_OWNER_EXTERNAL_ID,
            legal_name="Growth Signal (demo)",
            email="growth.signal@example.invalid",
        )
        session.add(owner)
        session.flush()
    return owner


def _seed_candidate_flags(session: Session, owner: User, candidate: _CandidateSeed) -> None:
    """Insert ``flag_count`` contextual, general flags for one candidate on an unsubmitted draft.

    The draft is never submitted and names no subject, so these flags feed the word cloud's
    frequency weight (``GET /growth/pending-additions``) without reaching the HR effectiveness or
    Pattern Dashboard aggregates, which read submitted documents only.
    """
    lemma_key = _lemma(candidate.phrase)
    document = Document(
        owner_id=owner.id,
        doc_type=DocType.jd,
        content=f"Growth signal draft: {candidate.phrase}.",
    )
    session.add(document)
    session.flush()
    session.add_all(
        Flag(
            document_id=document.id,
            source_stage=FlagSourceStage.contextual,
            category=candidate.category,
            scope=FlagScope.general,
            raw_span=candidate.phrase,
            normalised_span=lemma_key,
            sentence_fingerprint="growth-demo",
            rationale={"explanation": candidate.explanation},
        )
        for _ in range(candidate.flag_count)
    )
    session.flush()


def seed_growth_queue(session: Session, *, hr_user_id: uuid.UUID | None = None) -> int:
    """Insert any demo candidate not already queued; return how many were created.

    Args:
        session: An open database session; the caller owns the transaction.
        hr_user_id: The reviewer stamped on the deferred candidate, if a demo HR user exists.

    Returns:
        The number of new pending additions inserted (0 on a re-run).
    """
    queued = set(session.scalars(select(PendingDictionaryAddition.lemma_key)).all())
    owner = _flag_owner(session)
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
        _seed_candidate_flags(session, owner, candidate)
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

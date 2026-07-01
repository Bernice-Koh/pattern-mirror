"""The four dictionary-growth Agents: Proposer, Skeptic, Categorizer, Citation.

Each makes one schema-enforced Anthropic call (via Instructor) over a recurring phrase the
Contextual Pass keeps proposing, and returns a validated verdict. The four run independently;
the 3-of-4 gate over their outputs lives in ``review``. The LLM is a boundary, so raw model
text is parsed into a Pydantic schema here before any of it reaches the gate or the database
(CODE_STYLE). Per-agent model choice is settled in ADR 0012.
"""

import time
from dataclasses import dataclass

from pydantic import BaseModel, Field

from pattern_mirror.engine.llm_agent import StructuredCompletionClient
from pattern_mirror.models.enums import BiasCategory, CitationSourceType, FlagScope

_MAX_TOKENS = 2048

_PROPOSER_SYSTEM = (
    "You are the Proposer in a four-agent review deciding whether a phrase that a bias "
    "checker keeps raising across hiring documents should join the fair-employment "
    "dictionary. Argue FOR inclusion: name the protected characteristic it skews toward "
    "(gender, age, race, nationality, religion, disability, or family status) and why it is "
    "biased across hiring contexts generally, not just here. Choose the single best-fitting "
    "category. If you genuinely cannot justify a dictionary entry, decline "
    "(supports_inclusion=false) rather than force a weak case."
)

_SKEPTIC_SYSTEM = (
    "You are the Skeptic in a four-agent review deciding whether a recurring phrase should "
    "join the fair-employment dictionary. Argue AGAINST inclusion: is it standard business "
    "language, too narrow to one role, or thin on evidence of real bias? After making the "
    "strongest case against, give your honest verdict — does the phrase still merit a "
    "dictionary entry despite your objections?"
)

_CATEGORIZER_SYSTEM = (
    "You are the Categorizer in a four-agent review of a recurring hiring phrase. Decide its "
    "scope. 'general' means the phrase is biased across hiring broadly, so a dictionary should "
    "catch it as a fast deterministic hit. 'role_specific' means it is biased only for "
    "particular roles and should stay a context-only flag, never a dictionary entry."
)

_CITATION_SYSTEM = (
    "You are the Citation agent in a four-agent review of a recurring hiring phrase. Search "
    "your knowledge for academic or regulatory support that this phrasing reflects bias toward "
    "a protected characteristic. If credible support exists, return the source: its type, "
    "title, reference, publication year if known, and the finding that applies. If none "
    "exists, set found_support=false. Never fabricate a source — no support is a valid, "
    "expected outcome that simply blocks dictionary inclusion."
)


class ProposerResult(BaseModel):
    """The Proposer's case for adding the phrase, with its best-fit category."""

    supports_inclusion: bool = Field(
        description="True if the phrase warrants a dictionary entry; false to decline."
    )
    category: BiasCategory = Field(
        description="The single protected characteristic the phrase skews toward."
    )
    reasoning: str = Field(description="One or two sentences arguing for inclusion.")


class SkepticResult(BaseModel):
    """The Skeptic's case against, and its honest verdict after making it."""

    supports_inclusion: bool = Field(
        description="The honest verdict: True if it still merits an entry despite the objections."
    )
    reasoning: str = Field(description="One or two sentences arguing against inclusion.")


class CategorizerResult(BaseModel):
    """The Categorizer's scope call: dictionary-eligible or context-only."""

    scope: FlagScope = Field(
        description="'general' for a dictionary candidate; 'role_specific' for context-only."
    )
    reasoning: str = Field(description="One or two sentences justifying the scope.")


class FoundCitation(BaseModel):
    """A source the Citation agent found supporting the bias claim."""

    source_type: CitationSourceType = Field(description="Whether the source is academic, etc.")
    title: str = Field(description="The source title.")
    reference: str = Field(description="A locator: DOI, URL, regulation clause, or guideline id.")
    publication_year: int | None = Field(default=None, description="Year, if known.")
    finding: str = Field(description="The specific finding that supports the bias claim.")


class CitationResult(BaseModel):
    """The Citation agent's search outcome; ``citation`` is present iff support was found."""

    found_support: bool = Field(description="True if credible academic/regulatory support exists.")
    citation: FoundCitation | None = Field(
        default=None, description="The source found; null when found_support is false."
    )
    reasoning: str = Field(description="One or two sentences on the search outcome.")


@dataclass(frozen=True)
class GrowthAgentRun[R: BaseModel]:
    """A completed growth-agent call: its parsed result plus what the audit log needs."""

    result: R
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int


def _format_candidate(phrase: str, excerpts: list[str]) -> str:
    listing = "\n".join(f"- {excerpt}" for excerpt in excerpts) or "- (no excerpts supplied)"
    return f'Candidate phrase: "{phrase}"\n\nWhere it appeared:\n{listing}'


def _call_agent[R: BaseModel](
    client: StructuredCompletionClient,
    *,
    model: str,
    system: str,
    user: str,
    response_model: type[R],
) -> GrowthAgentRun[R]:
    """Make one schema-enforced Anthropic call and wrap its result with usage/latency."""
    started = time.monotonic()
    parsed, completion = client.create_with_completion(
        model=model,
        max_tokens=_MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
        response_model=response_model,
    )
    latency_ms = int((time.monotonic() - started) * 1000)
    result: R = parsed
    usage = getattr(completion, "usage", None)
    return GrowthAgentRun(
        result=result,
        prompt_tokens=getattr(usage, "input_tokens", None),
        completion_tokens=getattr(usage, "output_tokens", None),
        latency_ms=latency_ms,
    )


def run_proposer(
    client: StructuredCompletionClient, *, phrase: str, excerpts: list[str], model: str
) -> GrowthAgentRun[ProposerResult]:
    """Argue for including the phrase and pick its category; return the validated result."""
    return _call_agent(
        client,
        model=model,
        system=_PROPOSER_SYSTEM,
        user=_format_candidate(phrase, excerpts),
        response_model=ProposerResult,
    )


def run_skeptic(
    client: StructuredCompletionClient, *, phrase: str, excerpts: list[str], model: str
) -> GrowthAgentRun[SkepticResult]:
    """Argue against inclusion, then give an honest verdict; return the validated result."""
    return _call_agent(
        client,
        model=model,
        system=_SKEPTIC_SYSTEM,
        user=_format_candidate(phrase, excerpts),
        response_model=SkepticResult,
    )


def run_categorizer(
    client: StructuredCompletionClient, *, phrase: str, excerpts: list[str], model: str
) -> GrowthAgentRun[CategorizerResult]:
    """Classify the phrase's scope as general or role-specific; return the validated result."""
    return _call_agent(
        client,
        model=model,
        system=_CATEGORIZER_SYSTEM,
        user=_format_candidate(phrase, excerpts),
        response_model=CategorizerResult,
    )


def run_citation(
    client: StructuredCompletionClient, *, phrase: str, excerpts: list[str], model: str
) -> GrowthAgentRun[CitationResult]:
    """Search for academic/regulatory support for the bias claim; return the validated result."""
    return _call_agent(
        client,
        model=model,
        system=_CITATION_SYSTEM,
        user=_format_candidate(phrase, excerpts),
        response_model=CitationResult,
    )

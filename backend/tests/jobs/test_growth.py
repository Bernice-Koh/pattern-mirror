"""run_growth_review wires the trigger to the four-agent review and commits the batch.

The trigger runs against real ``flags`` in the test database; the Anthropic calls are faked (one
fake keyed on the requested schema, per CONVENTIONS), so the wiring is exercised offline.
"""

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.core.config import Settings
from pattern_mirror.engine.fingerprint import compute_sentence_fingerprint
from pattern_mirror.engine.growth.agents import (
    CategorizerResult,
    CitationResult,
    FoundCitation,
    ProposerResult,
    SkepticResult,
)
from pattern_mirror.engine.lemmatiser import lemma_key
from pattern_mirror.jobs.growth import run_growth_review
from pattern_mirror.models.documents import Document
from pattern_mirror.models.engine import Flag
from pattern_mirror.models.enums import (
    BiasCategory,
    CitationSourceType,
    DocType,
    FlagScope,
    FlagSourceStage,
)
from pattern_mirror.models.growth import PendingDictionaryAddition
from pattern_mirror.models.identity import User

pytestmark = pytest.mark.db

_PHRASE = "culture add"


class _FakeUsage:
    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _FakeCompletion:
    def __init__(self, usage: _FakeUsage) -> None:
        self.usage = usage


class _FakeGrowthClient:
    """Returns the result registered for the requested schema, serving all four agents."""

    def __init__(self, results: dict[type, Any]) -> None:
        self._results = results
        self._completion = _FakeCompletion(_FakeUsage(200, 60))

    def create_with_completion(self, **kwargs: Any) -> tuple[Any, Any]:
        return self._results[kwargs["response_model"]], self._completion


def _settings() -> Settings:
    return Settings(app_env="test", database_url="postgresql+psycopg://unused")


def _advancing_results() -> dict[type, Any]:
    return {
        ProposerResult: ProposerResult(
            supports_inclusion=True, category=BiasCategory.gender, reasoning="for"
        ),
        SkepticResult: SkepticResult(supports_inclusion=True, reasoning="against"),
        CategorizerResult: CategorizerResult(scope=FlagScope.general, reasoning="scope"),
        CitationResult: CitationResult(
            found_support=True,
            citation=FoundCitation(
                source_type=CitationSourceType.academic,
                title="Coded language",
                reference="doi:10.1/x",
                publication_year=2019,
                finding="Deters applicants.",
            ),
            reasoning="search",
        ),
    }


def _seed_recurring_phrase(session: Session) -> None:
    for m in range(3):
        user = User(
            external_user_id=f"mgr-{m}", legal_name=f"Manager {m}", email=f"mgr{m}@example.invalid"
        )
        session.add(user)
        session.flush()
        content = f"We really value a {_PHRASE} on doc {m}."
        document = Document(owner_id=user.id, doc_type=DocType.jd, content=content)
        session.add(document)
        session.flush()
        start = content.index(_PHRASE)
        session.add(
            Flag(
                document_id=document.id,
                source_stage=FlagSourceStage.contextual,
                category=BiasCategory.gender,
                scope=FlagScope.general,
                raw_span=_PHRASE,
                normalised_span=lemma_key(_PHRASE),
                sentence_fingerprint=compute_sentence_fingerprint(
                    content, start, start + len(_PHRASE)
                ),
                start_offset=start,
                end_offset=start + len(_PHRASE),
                rationale={"explanation": "coded language"},
            )
        )
    session.flush()


def test_run_growth_review_reviews_triggered_candidates_and_queues_advances(
    db_session: Session,
) -> None:
    _seed_recurring_phrase(db_session)
    client = _FakeGrowthClient(_advancing_results())

    outcomes = run_growth_review(db_session, client=client, settings=_settings())

    assert len(outcomes) == 1
    assert outcomes[0].advanced is True

    pending = db_session.scalars(select(PendingDictionaryAddition)).all()
    assert len(pending) == 1
    assert pending[0].lemma_key == lemma_key(_PHRASE)


def test_run_growth_review_with_no_candidates_is_a_no_op(db_session: Session) -> None:
    client = _FakeGrowthClient(_advancing_results())

    outcomes = run_growth_review(db_session, client=client, settings=_settings())

    assert outcomes == []
    assert db_session.scalars(select(PendingDictionaryAddition)).all() == []

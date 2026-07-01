"""The four growth agents: schema-parsed output, usage, and prompts carrying the candidate.

The Anthropic call is replaced by a deterministic fake implementing the one method the agents
use, so these run offline and never touch the live API (CONVENTIONS).
"""

from collections.abc import Callable
from typing import Any

import pytest
from pydantic import BaseModel

from pattern_mirror.engine.growth.agents import (
    CategorizerResult,
    CitationResult,
    FoundCitation,
    ProposerResult,
    SkepticResult,
    run_categorizer,
    run_citation,
    run_proposer,
    run_skeptic,
)
from pattern_mirror.models.enums import BiasCategory, CitationSourceType, FlagScope

AgentRunner = Callable[..., Any]


class _FakeUsage:
    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _FakeCompletion:
    def __init__(self, usage: _FakeUsage) -> None:
        self.usage = usage


class _FakeClient:
    """Returns a fixed result + usage and records the call kwargs for assertions."""

    def __init__(
        self, result: BaseModel, *, input_tokens: int = 200, output_tokens: int = 60
    ) -> None:
        self._result = result
        self._completion = _FakeCompletion(_FakeUsage(input_tokens, output_tokens))
        self.calls: list[dict[str, Any]] = []

    def create_with_completion(self, **kwargs: Any) -> tuple[Any, Any]:
        self.calls.append(kwargs)
        return self._result, self._completion


def test_run_proposer_returns_parsed_result_and_usage() -> None:
    client = _FakeClient(
        ProposerResult(supports_inclusion=True, category=BiasCategory.gender, reasoning="biased"),
        input_tokens=200,
        output_tokens=60,
    )

    run = run_proposer(client, phrase="cultural fit", excerpts=["a strong cultural fit"], model="m")

    assert run.result.supports_inclusion is True
    assert run.result.category is BiasCategory.gender
    assert run.prompt_tokens == 200
    assert run.completion_tokens == 60
    assert run.latency_ms >= 0


def test_run_citation_parses_a_found_source() -> None:
    found = FoundCitation(
        source_type=CitationSourceType.academic,
        title="Bias in hiring language",
        reference="doi:10.1000/x",
        publication_year=2019,
        finding="Coded phrasing deters applicants.",
    )
    client = _FakeClient(CitationResult(found_support=True, citation=found, reasoning="found"))

    run = run_citation(client, phrase="cultural fit", excerpts=["a strong cultural fit"], model="m")

    assert run.result.found_support is True
    assert run.result.citation is not None
    assert run.result.citation.reference == "doi:10.1000/x"


_CASES: list[tuple[AgentRunner, type[BaseModel], BaseModel]] = [
    (
        run_proposer,
        ProposerResult,
        ProposerResult(supports_inclusion=True, category=BiasCategory.age, reasoning="r"),
    ),
    (run_skeptic, SkepticResult, SkepticResult(supports_inclusion=False, reasoning="r")),
    (run_categorizer, CategorizerResult, CategorizerResult(scope=FlagScope.general, reasoning="r")),
    (
        run_citation,
        CitationResult,
        CitationResult(found_support=False, reasoning="none found"),
    ),
]


@pytest.mark.parametrize(("runner", "schema", "result"), _CASES)
def test_each_agent_requests_its_schema_with_the_candidate(
    runner: AgentRunner, schema: type[BaseModel], result: BaseModel
) -> None:
    client = _FakeClient(result)

    runner(client, phrase="digital native", excerpts=["we need a digital native"], model="model-x")

    call = client.calls[0]
    assert call["model"] == "model-x"
    assert call["response_model"] is schema
    content = call["messages"][0]["content"]
    assert "digital native" in content
    assert "we need a digital native" in content

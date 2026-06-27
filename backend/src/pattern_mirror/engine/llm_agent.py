"""Shared plumbing for the LLM Agent stages: Instructor client, pricing, cost estimate.

The Contextual Pass, Judge, and Recommendations stages each make one schema-enforced
Anthropic call; the client contract, pricing table, and cost estimate are identical and
live here once. Stage modules own only their prompt and schema.
"""

from decimal import Decimal
from typing import Any, Protocol, cast

import instructor
from anthropic import Anthropic

from pattern_mirror.core.config import Settings

# Static USD/MTok (input, output); an unknown model logs a null cost, never a wrong one.
_PRICES_USD_PER_MTOK: dict[str, tuple[str, str]] = {
    "claude-sonnet-4-6": ("3", "15"),
    "claude-haiku-4-5": ("1", "5"),
}


class StructuredCompletionClient(Protocol):
    """Schema-validated Instructor output plus the raw completion, the only method used.

    A Protocol so the Agents accept a deterministic test fake without coupling to Instructor.
    """

    def create_with_completion(self, **kwargs: Any) -> tuple[Any, Any]: ...


def estimate_cost_usd(
    model: str, prompt_tokens: int | None, completion_tokens: int | None
) -> Decimal | None:
    """Estimate the call cost from token usage, or None if pricing/usage is unavailable."""
    price = _PRICES_USD_PER_MTOK.get(model)
    if price is None or prompt_tokens is None or completion_tokens is None:
        return None
    input_price, output_price = price
    per_million = Decimal(1_000_000)
    return (
        Decimal(prompt_tokens) * Decimal(input_price)
        + Decimal(completion_tokens) * Decimal(output_price)
    ) / per_million


def build_instructor_client(settings: Settings) -> StructuredCompletionClient | None:
    """Build the Instructor-wrapped Anthropic client, or None when no API key is configured.

    Network-free: no request is made until ``create_with_completion`` is called. None lets
    the orchestrator degrade an Agent stage to a passthrough. One client serves every stage;
    the model is chosen per call.
    """
    if settings.anthropic_api_key is None:
        return None
    client = instructor.from_anthropic(Anthropic(api_key=settings.anthropic_api_key))
    return cast(StructuredCompletionClient, client)

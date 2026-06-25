"""Central registry of LLM models used across the AI task pipeline.

This is the single source of truth for which models the UI may select and which
cheap model drives the intent router. OpenRouter model identifiers are used
everywhere (the backend talks to OpenRouter via settings.OPENAI_HOST).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelInfo:
    """A selectable LLM: ``id`` is the OpenRouter model id, ``name`` the UI label."""
    id: str
    name: str


MAIN_MODELS: list[ModelInfo] = [
    ModelInfo("anthropic/claude-opus-4.8", "Claude Opus 4.8"),
    ModelInfo("anthropic/claude-sonnet-4.6", "Claude Sonnet 4.6"),
    ModelInfo("anthropic/claude-haiku-4.5", "Claude Haiku 4.5"),
    ModelInfo("google/gemini-3.1-pro-preview", "Gemini 3.1 Pro"),
    ModelInfo("openai/gpt-5.5-pro", "GPT-5.5 Pro"),
]

ALLOWED_MODEL_IDS: frozenset[str] = frozenset(m.id for m in MAIN_MODELS)

DEFAULT_MODEL: str = "anthropic/claude-sonnet-4.6"
"""Default main agent used when none is provided or an unknown one is requested."""

ROUTER_MODEL: str = "anthropic/claude-sonnet-4.6"
"""Cheaper/faster model for the intent router and internal scaffolding. NOT
haiku-4.5: that model's only OpenRouter providers (Bedrock/Anthropic-direct) are
region-blocked on the prod account (403 'Request not allowed'), whereas
sonnet/opus route through an allowed provider. The router additionally retries on
the main model, but scaffolding does not — so this must be a model that works."""

SCAFFOLD_MODEL: str = ROUTER_MODEL
"""Model for internal scaffolding that is NOT a user-facing artifact — the test
plan and the subtask plan. Cheaper/faster than the main agent so it stays off the
slow critical path; the actual files still use the user's chosen main model."""


def normalize_model(model: str | None) -> str:
    """Return a valid main-agent model id, falling back to the default.

    Accepts the legacy Opus 4.7 id and upgrades it to 4.8 transparently so old
    sessions keep working after the registry bump.
    """
    if not model:
        return DEFAULT_MODEL
    if model == "anthropic/claude-opus-4.7":
        return "anthropic/claude-opus-4.8"
    return model if model in ALLOWED_MODEL_IDS else DEFAULT_MODEL

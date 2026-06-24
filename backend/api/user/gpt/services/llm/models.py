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
    ModelInfo("google/gemini-3.1-pro-preview", "Gemini 3.1 Pro"),
    ModelInfo("openai/gpt-5.5-pro", "GPT-5.5 Pro"),
]

ALLOWED_MODEL_IDS: frozenset[str] = frozenset(m.id for m in MAIN_MODELS)

DEFAULT_MODEL: str = "anthropic/claude-sonnet-4.6"
"""Default main agent used when none is provided or an unknown one is requested."""

ROUTER_MODEL: str = "anthropic/claude-haiku-4.5"
"""Fixed cheap, fast model for the intent router. Never user-selectable: it only
decides 'modify' vs 'answer' and must stay inexpensive regardless of the main agent."""

SCAFFOLD_MODEL: str = "anthropic/claude-haiku-4.5"
"""Fast model for internal scaffolding that is NOT a user-facing artifact — the
test plan and the subtask plan. Using a cheap/fast model here cuts the slow
sequential model round-trips out of the critical path without touching the
quality of the actual files (which still use the user's chosen main model)."""


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

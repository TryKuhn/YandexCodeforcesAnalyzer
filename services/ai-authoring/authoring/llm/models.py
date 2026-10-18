"""Registry of the LLMs the service uses (OpenRouter ids).

* ``MAIN_MODELS`` -- selectable in the UI for answers, edits and generation;
  Claude Opus 5.5 is the default.
* ``ROUTER_MODELS`` -- the cheap intent router: Claude Haiku 5.5, falling back
  to Sonnet 5.5 when Haiku's providers refuse the request (a regional block on
  OpenRouter shows up as 403 "not allowed").
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelInfo:
    id: str
    name: str
    vendor: str
    # input / output USD per 1M tokens, for the UI hint
    price_in: float
    price_out: float
    context: int


MAIN_MODELS: tuple[ModelInfo, ...] = (
    ModelInfo("anthropic/claude-opus-5.5", "Claude Opus 5.5", "anthropic", 4.0, 20.0, 1_000_000),
    ModelInfo("anthropic/claude-sonnet-5.5", "Claude Sonnet 5.5", "anthropic", 2.0, 10.0, 1_000_000),
    ModelInfo("openai/gpt-6.1-sol", "GPT-6.1 Sol", "openai", 2.0, 10.0, 1_050_000),
)

DEFAULT_MODEL = "anthropic/claude-opus-5.5"

ROUTER_MODELS: tuple[str, ...] = (
    "anthropic/claude-haiku-5.5",
    "anthropic/claude-sonnet-5.5",
)

ALLOWED_MODEL_IDS = frozenset(m.id for m in MAIN_MODELS)

# ids stored by older sessions / the retired gpt service -> current ones
_LEGACY = {
    "anthropic/claude-opus-4.8": DEFAULT_MODEL,
    "anthropic/claude-opus-4.7": DEFAULT_MODEL,
    "anthropic/claude-sonnet-4.6": "anthropic/claude-sonnet-5.5",
    "anthropic/claude-haiku-4.5": "anthropic/claude-sonnet-5.5",
    "openai/gpt-5.5-pro": "openai/gpt-6.1-sol",
    "google/gemini-3.1-pro-preview": DEFAULT_MODEL,
}


def normalize_model(model: str | None) -> str:
    """A selectable model id: legacy ids are upgraded, unknown ones fall back to the default."""
    if not model:
        return DEFAULT_MODEL
    model = _LEGACY.get(model, model)
    return model if model in ALLOWED_MODEL_IDS else DEFAULT_MODEL


def is_anthropic(model: str) -> bool:
    return model.startswith("anthropic/")

"""Unit tests for the LLM model registry (services.llm.models)."""
from api.user.gpt.services.llm import models as m


def test_main_models_present_and_typed():
    assert isinstance(m.MAIN_MODELS, list)
    assert len(m.MAIN_MODELS) >= 1
    for info in m.MAIN_MODELS:
        assert isinstance(info, m.ModelInfo)
        assert isinstance(info.id, str) and info.id
        assert isinstance(info.name, str) and info.name


def test_modelinfo_is_frozen():
    info = m.MAIN_MODELS[0]
    import dataclasses
    assert dataclasses.is_dataclass(info)
    try:
        info.id = "changed"  # frozen → should raise
    except dataclasses.FrozenInstanceError:
        pass
    else:  # pragma: no cover
        raise AssertionError("ModelInfo should be frozen")


def test_allowed_model_ids_matches_main_models():
    assert isinstance(m.ALLOWED_MODEL_IDS, frozenset)
    assert m.ALLOWED_MODEL_IDS == frozenset(x.id for x in m.MAIN_MODELS)


def test_default_and_router_model_constants():
    assert isinstance(m.DEFAULT_MODEL, str) and m.DEFAULT_MODEL
    assert m.DEFAULT_MODEL in m.ALLOWED_MODEL_IDS
    # Router/scaffold use a cheaper/fast model. (Not haiku-4.5: it's region-
    # blocked on prod; sonnet works, so they may coincide with a main model.)
    assert isinstance(m.ROUTER_MODEL, str) and m.ROUTER_MODEL
    assert isinstance(m.SCAFFOLD_MODEL, str) and m.SCAFFOLD_MODEL


def test_normalize_model_none_returns_default():
    assert m.normalize_model(None) == m.DEFAULT_MODEL
    assert m.normalize_model("") == m.DEFAULT_MODEL


def test_normalize_model_unknown_returns_default():
    assert m.normalize_model("totally/unknown") == m.DEFAULT_MODEL


def test_normalize_model_known_passthrough():
    known = m.MAIN_MODELS[0].id
    assert m.normalize_model(known) == known


def test_normalize_model_upgrades_legacy_opus():
    assert m.normalize_model("anthropic/claude-opus-4.7") == "anthropic/claude-opus-4.8"

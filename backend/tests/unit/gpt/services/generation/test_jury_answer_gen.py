"""Unit tests for jury reference-solver generation (generation.jury_answer_gen)."""
import pytest

from api.user.gpt.services.generation import jury_answer_gen as jag


@pytest.mark.asyncio
async def test_generate_delegates_to_file_gen(monkeypatch):
    captured = {}

    async def fake_generate(file_type, statement, model):
        captured["args"] = (file_type, statement, model)
        return "jury code"

    monkeypatch.setattr(
        "api.user.gpt.services.generation.jury_answer_gen.file_gen.generate",
        fake_generate,
    )
    out = await jag.generate({"name": "x"}, "model-z")
    assert out == "jury code"
    assert captured["args"] == ("jury_answer", {"name": "x"}, "model-z")

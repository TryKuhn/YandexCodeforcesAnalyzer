"""Shared fixtures for Polygon tests.

``polygon_api`` replaces the transport (``client.request``) with a recorder, so
tests go through the real wrappers/routes and assert exactly which Polygon
method was called with which (already serialized) parameters.
"""
from dataclasses import dataclass, field
from typing import Any

import pytest

import api.user.polygon.client as client_mod


@dataclass
class PolygonCall:
    method: str
    params: dict[str, Any]
    kind: str
    api_key: str
    api_secret: str


@dataclass
class FakePolygon:
    """Records calls; ``respond(method, value)`` scripts the result.

    ``value`` may be a plain value, an exception (raised), a callable taking the
    serialized params, or a list wrapped by ``sequence=True`` to return in turn.
    """

    calls: list[PolygonCall] = field(default_factory=list)
    responses: dict[str, Any] = field(default_factory=dict)

    def respond(self, method: str, value: Any, *, sequence: bool = False) -> None:
        self.responses[method] = iter(value) if sequence else value

    async def __call__(self, method, params, *, api_key, api_secret, kind="json",
                       session=None):
        text, binary = client_mod.split_params(params)
        self.calls.append(PolygonCall(method, {**text, **binary}, kind, api_key, api_secret))
        value = self.responses.get(method)
        if hasattr(value, "__next__"):
            value = next(value)
        if isinstance(value, BaseException):
            raise value
        if callable(value):
            return value({**text, **binary})
        return value

    @property
    def methods(self) -> list[str]:
        return [c.method for c in self.calls]

    def last(self, method: str | None = None) -> PolygonCall:
        calls = [c for c in self.calls if method is None or c.method == method]
        assert calls, f"no call to {method}"
        return calls[-1]


@pytest.fixture
def polygon_api(monkeypatch) -> FakePolygon:
    fake = FakePolygon()
    monkeypatch.setattr(client_mod, "request", fake)
    return fake

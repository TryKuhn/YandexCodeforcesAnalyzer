"""Unit tests for api/user/auth/location.py — IP geolocation helper."""
import pytest

import api.user.auth.location as location_mod
from api.user.auth.location import get_location


@pytest.mark.parametrize("ip", ["127.0.0.1", "localhost", "testclient", "172.18.0.5"])
@pytest.mark.asyncio
async def test_local_ips_short_circuit(ip):
    assert await get_location(ip) == "Локальная сеть"


class _FakeResponse:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


class _FakeAsyncClient:
    def __init__(self, data):
        self._data = data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url):
        return _FakeResponse(self._data)


@pytest.mark.asyncio
async def test_success_returns_city_country(monkeypatch):
    data = {"status": "success", "city": "Berlin", "country": "Germany"}
    monkeypatch.setattr(
        location_mod.httpx, "AsyncClient", lambda timeout=1.0: _FakeAsyncClient(data)
    )
    assert await get_location("8.8.8.8") == "Berlin, Germany"


@pytest.mark.asyncio
async def test_non_success_status_returns_unknown(monkeypatch):
    data = {"status": "fail"}
    monkeypatch.setattr(
        location_mod.httpx, "AsyncClient", lambda timeout=1.0: _FakeAsyncClient(data)
    )
    assert await get_location("8.8.8.8") == "Неизвестное местоположение"


@pytest.mark.asyncio
async def test_exception_returns_unknown(monkeypatch):
    class _BoomClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            raise RuntimeError("network down")

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(location_mod.httpx, "AsyncClient", _BoomClient)
    assert await get_location("8.8.8.8") == "Неизвестное местоположение"

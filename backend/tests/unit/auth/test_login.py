"""Unit tests for api/user/auth/login.py — register/login handlers called directly.

Covers the error branches (duplicate login, missing Admin role, unknown login,
empty stored password, wrong password) plus the happy paths. ``get_location``
is monkeypatched in the module namespace to avoid the network call.
"""
import importlib

import pytest

from api.pydantic_schemas import UserLogin, UserRegister
from models import RefreshToken, Role, User

# NOTE: ``api.user.auth.__init__`` binds the *function* ``login`` as an
# attribute of the package, which shadows the submodule when accessed via
# attribute lookup. Use importlib to reliably grab the real module object so
# monkeypatching ``get_location`` targets the module-under-test namespace.
login_mod = importlib.import_module("api.user.auth.login")


class _FakeClient:
    host = "127.0.0.1"


class _FakeRequest:
    """Minimal stand-in for fastapi.Request used by login()."""

    def __init__(self, host="127.0.0.1", headers=None):
        self.client = _FakeClient()
        self.client.host = host
        self.headers = headers or {"user-agent": "pytest-agent"}


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    async def fake_location(ip):
        return "Локальная сеть"

    monkeypatch.setattr(login_mod, "get_location", fake_location)


async def _seed_role(db, name="Admin"):
    role = Role(name=name)
    db.add(role)
    await db.flush()
    return role


# --------------------------------------------------------------------------- #
# login
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_login_unknown_login_401(db):
    with pytest.raises(Exception) as exc:
        await login_mod.login(
            UserLogin(login="ghost", password="x"), request=_FakeRequest(), db=db
        )
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_login_empty_password_401(db):
    role = await _seed_role(db, "Plain")
    db.add(User(login="emptypw", password="", email="e@e.com", role_id=role.id))
    await db.commit()
    with pytest.raises(Exception) as exc:
        await login_mod.login(
            UserLogin(login="emptypw", password="whatever"),
            request=_FakeRequest(),
            db=db,
        )
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_login_wrong_password_401(db):
    from api.crypt import hash_password

    role = await _seed_role(db, "Plain")
    db.add(
        User(
            login="realuser",
            password=hash_password("Correct1!"),
            email="r@e.com",
            role_id=role.id,
        )
    )
    await db.commit()
    with pytest.raises(Exception) as exc:
        await login_mod.login(
            UserLogin(login="realuser", password="Wrong1!"),
            request=_FakeRequest(),
            db=db,
        )
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_login_success_creates_refresh_token(db):
    from sqlalchemy import select

    from api.crypt import hash_password

    role = await _seed_role(db, "Plain")
    db.add(
        User(
            login="gooduser",
            password=hash_password("Correct1!"),
            email="g@e.com",
            role_id=role.id,
        )
    )
    await db.commit()

    token = await login_mod.login(
        UserLogin(login="gooduser", password="Correct1!"),
        request=_FakeRequest(host="8.8.8.8", headers={"user-agent": "UA"}),
        db=db,
    )
    assert token.token_type == "Bearer"
    assert token.access_token and token.refresh_token

    rows = (await db.execute(select(RefreshToken))).scalars().all()
    assert len(rows) == 1
    assert rows[0].user_agent.startswith("Локальная сеть")


@pytest.mark.asyncio
async def test_login_uses_unknown_when_no_client(db):
    from api.crypt import hash_password

    role = await _seed_role(db, "Plain")
    db.add(
        User(
            login="noclient",
            password=hash_password("Correct1!"),
            email="n@e.com",
            role_id=role.id,
        )
    )
    await db.commit()

    req = _FakeRequest()
    req.client = None  # exercises the "unknown" client_ip branches
    token = await login_mod.login(
        UserLogin(login="noclient", password="Correct1!"), request=req, db=db
    )
    assert token.access_token


# --------------------------------------------------------------------------- #
# register
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_register_duplicate_login_400(db):
    role = await _seed_role(db, "Admin")
    db.add(User(login="dupuser", password="x", email="d@e.com", role_id=role.id))
    await db.commit()

    with pytest.raises(Exception) as exc:
        await login_mod.register(
            UserRegister(login="dupuser", password="Correct1!", email="d2@e.com"),
            request=_FakeRequest(),
            db=db,
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_register_missing_admin_role_500(db):
    # No Admin role seeded.
    with pytest.raises(Exception) as exc:
        await login_mod.register(
            UserRegister(login="newuser", password="Correct1!", email="x@e.com"),
            request=_FakeRequest(),
            db=db,
        )
    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_register_success_logs_in(db):
    from sqlalchemy import select

    await _seed_role(db, "Admin")
    await db.commit()

    token = await login_mod.register(
        UserRegister(login="brandnew", password="Correct1!", email="bn@e.com"),
        request=_FakeRequest(),
        db=db,
    )
    assert token.token_type == "Bearer"
    user = (
        (await db.execute(select(User).filter_by(login="brandnew")))
        .scalars()
        .first()
    )
    assert user is not None
    assert user.password != "Correct1!"  # hashed

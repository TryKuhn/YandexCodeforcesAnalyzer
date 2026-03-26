from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.tests.api_tests.test_base import client
from backend.app.database import get_db
from backend.models.refresh_token import RefreshToken
from backend.models.user import User


# Codeforces keys should be removed from db
def test_unlink_codeforces_removes_keys_from_db():
    login = "unlink_cf_user_1"
    refresh_token_value = "refresh_1"

    db = get_db()
    try:
        user = User(
            login=login,
            password="fake_password_hash",
            email=f"{login}@example.com",
            codeforces_api_key="fake_cf_key",
            codeforces_api_secret="fake_cf_secret",
        )
        db.add(user)
        db.commit()

        db_refresh_token = RefreshToken(
            user_login=login,
            refresh_token=refresh_token_value,
            created_at=datetime.now(timezone.utc),
            expires_in=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db.add(db_refresh_token)
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/unlink_codeforces",
        json={
            "refresh_token": refresh_token_value,
        },
    )

    db = get_db()
    try:
        updated_user = db.query(User).filter(User.login == login).first()
    finally:
        db.close()

    assert response.status_code == 200
    assert response.json() == {"message": "Codeforces account unlinked!"}
    assert updated_user is not None
    assert updated_user.codeforces_api_key is None
    assert updated_user.codeforces_api_secret is None
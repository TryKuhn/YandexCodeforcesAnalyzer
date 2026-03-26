from datetime import datetime, timedelta, timezone

from backend.tests.api_tests.test_base import client
from backend.app.database import get_db
from backend.models.refresh_token import RefreshToken
from backend.models.user import User


# Yandex token should be removed from db
def test_unlink_yandex_removes_token_from_db():
    login = "unlink_yandex_user_2"
    refresh_token_value = "refresh_2"

    db = get_db()
    try:
        user = User(
            login=login,
            password="fake_password_hash",
            email=f"{login}@example.com",
            yandex_access_token="fake_yandex_access_token",
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
        "/unlink_yandex",
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
    assert response.json() == {"message": "Yandex account unlinked!"}
    assert updated_user is not None
    assert updated_user.yandex_access_token is None
"""Password hashing/verification and opaque token hashing."""
import hashlib

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password):
    """Hash a plaintext password with bcrypt for storage."""
    return pwd_context.hash(password)


def verify_password(plain_password, hashed_password):
    """Check a plaintext password against a stored bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def hash_token(token: str):
    """Return the SHA-256 hex digest of a token, used for opaque lookups."""
    return hashlib.sha256(token.encode()).hexdigest()

"""Where an export goes: the user's own ejudge (profile integration) or the server's one (EJUDGE_* env).

Everything the export needs is gathered into one :class:`EjudgeConfig`, so the
rest of the code does not care where it came from. The user's account wins;
without one the server-wide settings are used (if configured).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt.secrets import decrypt, decrypt_optional
from api.user.ejudge.common import EjudgeError
from models.user.integrations import EjudgeAccount
from settings import settings


def parse_contests(raw: str) -> frozenset[int]:
    return frozenset(int(x) for x in raw.replace(";", ",").split(",") if x.strip().isdigit())


@dataclass(frozen=True)
class EjudgeConfig:
    source: str  # "user" | "server"
    ssh_host: str = ""
    ssh_port: int = 22
    ssh_user: str = "ejudge"
    ssh_key_path: str = ""  # server: a key file mounted into the container
    ssh_key: str = ""  # user: the private key text
    ssh_key_passphrase: str = ""
    ssh_password: str = ""
    known_hosts_path: str = ""  # server: a known_hosts file
    host_key: str = ""  # user: "SHA256:..." fingerprint or known_hosts line(s)
    insecure: bool = False
    judges_dir: str = "/home/judges"
    web_url: str = ""
    web_login: str = ""
    web_password: str = ""
    allowed_contests: frozenset[int] = field(default_factory=frozenset)
    # how the host builds checkers etc.; the same for every host
    cxx: str = "g++ -O2 -std=gnu++20"
    gvaluer_path: str = ""
    package_type: str = "linux"

    @property
    def configured(self) -> bool:
        """SSH access is the minimum; the web part (reload) is optional."""
        return bool(self.ssh_host and self.judges_dir)

    @property
    def web_reload(self) -> bool:
        return bool(self.web_url and self.web_login)


def server_config() -> EjudgeConfig:
    s = settings
    return EjudgeConfig(
        source="server",
        ssh_host=s.EJUDGE_SSH_HOST,
        ssh_port=s.EJUDGE_SSH_PORT,
        ssh_user=s.EJUDGE_SSH_USER,
        ssh_key_path=s.EJUDGE_SSH_KEY_PATH,
        known_hosts_path=s.EJUDGE_SSH_KNOWN_HOSTS,
        insecure=s.EJUDGE_SSH_INSECURE,
        judges_dir=s.EJUDGE_JUDGES_DIR,
        web_url=s.EJUDGE_URL,
        web_login=s.EJUDGE_LOGIN,
        web_password=s.EJUDGE_PASSWORD,
        allowed_contests=frozenset(s.ejudge_allowed_contests),
        cxx=s.EJUDGE_CXX,
        gvaluer_path=s.EJUDGE_GVALUER_PATH,
        package_type=s.EJUDGE_PACKAGE_TYPE,
    )


def account_config(account: EjudgeAccount) -> EjudgeConfig:
    """Decrypts the secrets (EjudgeError if they cannot be read any more)."""
    try:
        secret = decrypt(account.ssh_secret_enc)
        passphrase = decrypt_optional(account.ssh_key_passphrase_enc)
        web_password = decrypt_optional(account.web_password_enc)
    except Exception as e:  # SecretError
        raise EjudgeError(f"интеграция ejudge: {e}") from e
    by_key = account.auth_method == "key"
    return EjudgeConfig(
        source="user",
        ssh_host=account.ssh_host,
        ssh_port=account.ssh_port,
        ssh_user=account.ssh_user,
        ssh_key=secret if by_key else "",
        ssh_key_passphrase=passphrase if by_key else "",
        ssh_password="" if by_key else secret,
        host_key=account.host_key or "",
        insecure=account.insecure_host_key,
        judges_dir=account.judges_dir,
        web_url=account.web_url or "",
        web_login=account.web_login or "",
        web_password=web_password,
        allowed_contests=parse_contests(account.allowed_contests or ""),
        cxx=settings.EJUDGE_CXX,
        # a gvaluer binary path is a path on the server's own ejudge host: ours is compiled instead
        gvaluer_path="",
        package_type=settings.EJUDGE_PACKAGE_TYPE,
    )


async def resolve(user_id: int, db: AsyncSession) -> EjudgeConfig:
    """The user's ejudge if linked, otherwise the server's."""
    account = await db.get(EjudgeAccount, user_id)
    return account_config(account) if account is not None else server_config()

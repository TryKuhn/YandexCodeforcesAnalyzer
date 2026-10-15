from collections.abc import Mapping
from hashlib import sha512
from random import randrange


def _to_bytes(value: str | bytes) -> bytes:
    return value if isinstance(value, bytes) else str(value).encode("utf-8")


def create_signature(method_name: str, params: Mapping[str, str | bytes], secret: str) -> str:
    """Build a Polygon API ``apiSig`` for the given method and params.

    Polygon requires ``rand + sha512(rand/method?k1=v1&k2=v2...#secret)`` where
    ``rand`` is a 6-char random prefix and params are sorted by key, then value.
    The string is built from bytes so binary values (e.g. a statement image
    sent as a multipart file) are signed as-is, like Polygon does on its side.
    """
    random_string = f"{randrange(1000000):06d}"
    pairs = sorted((_to_bytes(k), _to_bytes(v)) for k, v in params.items())
    signature = (
        random_string.encode()
        + b"/" + method_name.encode()
        + b"?" + b"&".join(k + b"=" + v for k, v in pairs)
        + b"#" + secret.encode()
    )
    return f"{random_string}{sha512(signature).hexdigest()}"

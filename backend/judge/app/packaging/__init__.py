"""Import and export of problem packages; every external format is a plugin."""
from .base import Package, PackageError, PackageFormat, PackageTest
from .native import NativeFormat
from .polygon import PolygonFormat

_FORMATS: dict[str, PackageFormat] = {
    fmt.name: fmt for fmt in (NativeFormat(), PolygonFormat())
}


def get(name: str) -> PackageFormat:
    try:
        return _FORMATS[name]
    except KeyError:
        raise PackageError(f"unknown package format: {name}") from None


def available() -> tuple[str, ...]:
    return tuple(_FORMATS)


def register(fmt: PackageFormat) -> None:
    """Add a format at runtime, so a new system needs no changes here."""
    if fmt.name in _FORMATS:
        raise ValueError(f"format already registered: {fmt.name}")
    _FORMATS[fmt.name] = fmt


__all__ = [
    "NativeFormat",
    "Package",
    "PackageError",
    "PackageFormat",
    "PackageTest",
    "PolygonFormat",
    "available",
    "get",
    "register",
]

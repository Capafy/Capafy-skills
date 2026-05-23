from __future__ import annotations

try:
    import tomllib  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - Python 3.8-3.10
    from packaging._shared.common import minimal_toml as tomllib  # type: ignore[no-redef]


def safe_toml_loads(text: str) -> dict:
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        if normalized == text:
            raise
        return tomllib.loads(normalized)


__all__ = ["safe_toml_loads", "tomllib"]

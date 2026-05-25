from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any, Optional


def _build_builtin_runtimes() -> tuple[object, ...]:
    from packaging.configure.runtimes.claude_code.url_proxy import ClaudeCodeRuntime
    from packaging.configure.runtimes.codex.url_proxy import CodexRuntime
    from packaging.configure.runtimes.openclaw import OpenClawRuntime

    return (
        CodexRuntime(),
        ClaudeCodeRuntime(),
        OpenClawRuntime(),
    )


class _LazyBuiltinRuntimes(Sequence):
    def __init__(self) -> None:
        self._cache: Optional[tuple[object, ...]] = None

    def _items(self) -> tuple[object, ...]:
        if self._cache is None:
            self._cache = _build_builtin_runtimes()
        return self._cache

    def __iter__(self) -> Iterator[object]:
        return iter(self._items())

    def __len__(self) -> int:
        return len(self._items())

    def __getitem__(self, index):
        return self._items()[index]


BUILTIN_RUNTIMES = _LazyBuiltinRuntimes()


def __getattr__(name: str) -> Any:
    if name == "CodexRuntime":
        from packaging.configure.runtimes.codex.url_proxy import CodexRuntime

        return CodexRuntime
    if name == "ClaudeCodeRuntime":
        from packaging.configure.runtimes.claude_code.url_proxy import ClaudeCodeRuntime

        return ClaudeCodeRuntime
    if name == "OpenClawRuntime":
        from packaging.configure.runtimes.openclaw import OpenClawRuntime

        return OpenClawRuntime
    raise AttributeError(name)

__all__ = [
    "BUILTIN_RUNTIMES",
]

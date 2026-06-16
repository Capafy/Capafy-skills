from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Optional


def _build_builtin_runtimes() -> tuple[object, ...]:
    from packaging.runtimes.adapters import list_runtime_adapters

    runtimes = []
    for adapter in list_runtime_adapters():
        if adapter.url_proxy_runtime_factory is not None:
            runtimes.append(adapter.url_proxy_runtime_factory())
    return tuple(runtimes)


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


__all__ = [
    "BUILTIN_RUNTIMES",
]

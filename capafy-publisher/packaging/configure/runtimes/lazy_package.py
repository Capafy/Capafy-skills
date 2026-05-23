from __future__ import annotations

from importlib import import_module
import sys
from typing import Any, Callable


def make_runtime_package_getattr(
    package_name: str,
    *,
    class_exports: dict[str, tuple[str, str]],
    module_exports: frozenset[str],
) -> Callable[[str], Any]:
    def __getattr__(name: str) -> Any:
        class_export = class_exports.get(name)
        if class_export is not None:
            module_name, attr_name = class_export
            module = import_module(f"{package_name}.{module_name}")
            value = getattr(module, attr_name)
            return value
        if name in module_exports:
            module = import_module(f"{package_name}.{name}")
            sys.modules[package_name].__dict__[name] = module
            return module
        raise AttributeError(name)

    return __getattr__


__all__ = ["make_runtime_package_getattr"]

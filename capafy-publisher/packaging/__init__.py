from __future__ import annotations

from importlib import metadata
import site
import sysconfig
from pathlib import Path


def _extend_with_external_packaging_path() -> None:
    local_package_dir = Path(__file__).resolve().parent
    candidate_roots = []
    with_site = getattr(site, "getsitepackages", None)
    if callable(with_site):
        candidate_roots.extend(Path(path) for path in with_site())
    user_site = getattr(site, "getusersitepackages", None)
    if callable(user_site):
        candidate_roots.append(Path(user_site()))
    for key in ("purelib", "platlib"):
        value = sysconfig.get_paths().get(key)
        if value:
            candidate_roots.append(Path(value))

    for root in dict.fromkeys(candidate_roots):
        candidate = root / "packaging"
        if not candidate.is_dir():
            continue
        try:
            if candidate.resolve() == local_package_dir:
                continue
        except OSError:
            continue
        candidate_text = str(candidate)
        if candidate_text not in __path__:
            __path__.append(candidate_text)


_extend_with_external_packaging_path()


try:
    __version__ = metadata.version("packaging")
except metadata.PackageNotFoundError:  # pragma: no cover - host environment dependent
    __version__ = ""

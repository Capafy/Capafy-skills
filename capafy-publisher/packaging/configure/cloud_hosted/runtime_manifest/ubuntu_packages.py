from __future__ import annotations


UNMAPPED_PACKAGE_REASON = "No Ubuntu package mapping is defined yet; follow up in the skill or LLM workflow."


_LINUX_DIRECT_RULES = {
    "python3": "python3",
    "git": "git",
    "curl": "curl",
    "ffmpeg": "ffmpeg",
    "nodejs": "nodejs",
    "npm": "npm",
}

_LINUX_RENAME_RULES = {
    "sqlite": "sqlite3",
    "chromium": "chromium-browser",
}

_PACKAGE_RULES_BY_MANAGER: dict[str, dict[str, str]] = {
    "brew": {
        "python@3": "python3",
        "git": "git",
        "curl": "curl",
        "ffmpeg": "ffmpeg",
        "sqlite": "sqlite3",
        "node": "nodejs",
        "chromium": "chromium-browser",
    },
    "winget": {
        "python.python.3": "python3",
        "git.git": "git",
        "curl.curl": "curl",
        "gyan.ffmpeg": "ffmpeg",
        "sqlite.sqlite": "sqlite3",
        "openjs.nodejs": "nodejs",
    },
    "choco": {
        "python": "python3",
        "git": "git",
        "curl": "curl",
        "ffmpeg": "ffmpeg",
        "sqlite": "sqlite3",
        "nodejs": "nodejs",
    },
    "scoop": {
        "python": "python3",
        "git": "git",
        "curl": "curl",
        "ffmpeg": "ffmpeg",
        "sqlite": "sqlite3",
        "nodejs": "nodejs",
    },
    "dnf": {
        "python3": "python3",
        "git": "git",
        "curl": "curl",
        "ffmpeg": "ffmpeg",
        "sqlite": "sqlite3",
        "nodejs": "nodejs",
        "npm": "npm",
        "chromium": "chromium-browser",
    },
    "yum": {
        "python3": "python3",
        "git": "git",
        "curl": "curl",
        "ffmpeg": "ffmpeg",
        "sqlite": "sqlite3",
        "nodejs": "nodejs",
        "npm": "npm",
        "chromium": "chromium-browser",
    },
    "rpm": {
        "python3": "python3",
        "git": "git",
        "curl": "curl",
        "ffmpeg": "ffmpeg",
        "sqlite": "sqlite3",
        "nodejs": "nodejs",
        "npm": "npm",
        "chromium": "chromium-browser",
    },
    "apk": {
        "python3": "python3",
        "git": "git",
        "curl": "curl",
        "ffmpeg": "ffmpeg",
        "sqlite": "sqlite3",
        "nodejs": "nodejs",
        "npm": "npm",
        "chromium": "chromium-browser",
    },
    "pacman": {
        "python": "python3",
        "git": "git",
        "curl": "curl",
        "ffmpeg": "ffmpeg",
        "sqlite": "sqlite3",
        "nodejs": "nodejs",
        "npm": "npm",
        "chromium": "chromium-browser",
    },
}


def _normalized_manager(manager: object) -> str:
    return str(manager or "").strip().lower()


def _normalized_package_name(name: object) -> str:
    return str(name or "").strip().lower()


def _map_package_name_to_ubuntu(source_manager: str, source_name: str) -> str | None:
    if not source_name:
        return None
    if source_manager == "apt":
        return source_name

    manager_rules = _PACKAGE_RULES_BY_MANAGER.get(source_manager, {})
    mapped_name = manager_rules.get(source_name)
    if mapped_name:
        return mapped_name

    if source_manager in {"dnf", "yum", "rpm", "apk"}:

        if source_name in _LINUX_DIRECT_RULES:
            return _LINUX_DIRECT_RULES[source_name]
        return _LINUX_RENAME_RULES.get(source_name)
    return None


def derive_ubuntu_system_packages(system_packages: dict | None) -> dict:
    if not isinstance(system_packages, dict):
        system_packages = {}

    source_manager = _normalized_manager(system_packages.get("manager"))
    raw_packages = system_packages.get("packages", [])

    mapped_by_name: dict[str, dict] = {}
    unmapped_packages: list[dict] = []
    for item in raw_packages if isinstance(raw_packages, list) else []:
        if not isinstance(item, dict):
            continue
        original_name = str(item.get("name", "")).strip()
        if not original_name:
            continue
        normalized_name = _normalized_package_name(original_name)
        version_hint = str(item.get("version", "")).strip()
        ubuntu_name = _map_package_name_to_ubuntu(source_manager, normalized_name)
        if not ubuntu_name:
            unmapped_packages.append(
                {
                    "source_manager": source_manager or None,
                    "source_name": original_name,
                    "version_hint": version_hint,
                    "reason": UNMAPPED_PACKAGE_REASON,
                }
            )
            continue
        mapped_by_name[ubuntu_name] = {
            "name": ubuntu_name,
            "source_manager": source_manager or None,
            "source_name": original_name,
            "version_hint": version_hint,
            "confidence": "high",
        }

    return {
        "target_os": "ubuntu",
        "target_package_manager": "apt",
        "derivation_mode": "rules",
        "source_manager": source_manager or None,
        "packages": [mapped_by_name[name] for name in sorted(mapped_by_name)],
        "unmapped_packages": sorted(unmapped_packages, key=lambda item: item["source_name"]),
    }

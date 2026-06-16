from __future__ import annotations

from pathlib import PurePosixPath


def _normalize_relpath(value: object) -> str:
    normalized = str(value or "").strip().replace("\\", "/").strip("/")
    if not normalized:
        return ""
    return PurePosixPath(normalized).as_posix()


def _contract_config_files(profile: dict, key: str) -> list[str]:
    contract = profile.get("platform_contract", {})
    if not isinstance(contract, dict):
        return []
    files = contract.get(key, [])
    if not isinstance(files, list):
        return []
    result: list[str] = []
    for item in files:
        normalized = _normalize_relpath(item)
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def is_scan_only_config_path(path: object) -> bool:
    normalized = _normalize_relpath(path)
    return normalized == "_scan_only" or normalized.startswith("_scan_only/")


def collect_packaged_config_paths(profile: dict) -> list[str]:
    result: list[str] = []
    for path in (
        collect_required_packaged_config_paths(profile)
        + collect_optional_packaged_config_paths(profile)
    ):
        if path not in result:
            result.append(path)
    return result


def collect_required_packaged_config_paths(profile: dict) -> list[str]:
    return [
        path
        for path in _contract_config_files(profile, "config_files")
        if not is_scan_only_config_path(path)
    ]


def collect_optional_packaged_config_paths(profile: dict) -> list[str]:
    return [
        path
        for path in _contract_config_files(profile, "optional_config_files")
        if not is_scan_only_config_path(path)
    ]


def collect_scan_only_config_paths(profile: dict) -> list[str]:
    return [
        path
        for path in (
            _contract_config_files(profile, "config_files")
            + _contract_config_files(profile, "optional_config_files")
        )
        if is_scan_only_config_path(path)
    ]


def redaction_strategy_for_config_path(path: object) -> str:
    normalized = _normalize_relpath(path)
    suffix = PurePosixPath(normalized).suffix.lower()
    name = PurePosixPath(normalized).name.lower()
    if suffix in {".yaml", ".yml"}:
        return "yaml_stage_config"
    if suffix == ".toml":
        return "toml_stage_config"
    if suffix == ".json":
        return "json_stage_config"
    if name == ".env" or name.endswith(".env"):
        return "env_stage_config"
    return ""


def collect_redacted_config_files(profile: dict) -> list[dict[str, str]]:
    redacted: list[dict[str, str]] = []
    for path in collect_packaged_config_paths(profile):
        strategy = redaction_strategy_for_config_path(path)
        if not strategy:
            continue
        redacted.append({"target_path": path, "strategy": strategy})
    return redacted


__all__ = [
    "collect_optional_packaged_config_paths",
    "collect_packaged_config_paths",
    "collect_redacted_config_files",
    "collect_required_packaged_config_paths",
    "collect_scan_only_config_paths",
    "is_scan_only_config_path",
    "redaction_strategy_for_config_path",
]

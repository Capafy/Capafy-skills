from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Callable, Optional

from packaging._shared.config_files.toml_loader import safe_toml_loads, tomllib
from packaging._shared.config_files.yaml_loader import safe_yaml_mapping_loads
from packaging._shared.reviewed_scan.query import reviewed_url_proxy_has_any_side_field
from packaging.configure.config_errors import invalid_json_config_error, invalid_text_config_error
from packaging.configure.sensitive.literals import looks_like_platform_managed_placeholder_value


@dataclass(frozen=True)
class PlaceholderReviewRequirement:
    label: str
    source: str
    side_name: str
    fields: frozenset[str]
    group: str = ""


def placeholder_requirement_if_managed(
    *,
    value: object,
    label: str,
    source: str,
    side_name: str,
    fields: frozenset[str],
    group: str = "",
) -> Optional[PlaceholderReviewRequirement]:
    if not looks_like_platform_managed_placeholder_value(str(value or "").strip()):
        return None
    return PlaceholderReviewRequirement(
        label=label,
        source=source,
        side_name=side_name,
        fields=fields,
        group=group,
    )


def append_placeholder_requirement_if_managed(
    requirements: list[PlaceholderReviewRequirement],
    *,
    value: object,
    label: str,
    source: str,
    side_name: str,
    fields: frozenset[str],
    group: str = "",
) -> None:
    requirement = placeholder_requirement_if_managed(
        value=value,
        label=label,
        source=source,
        side_name=side_name,
        fields=fields,
        group=group,
    )
    if requirement is not None:
        requirements.append(requirement)


def append_key_url_placeholder_requirements(
    requirements: list[PlaceholderReviewRequirement],
    *,
    source: str,
    group: str,
    key_value: object,
    key_label: str,
    key_field: str,
    url_value: object,
    url_label: str,
    url_field: str,
) -> None:
    append_placeholder_requirement_if_managed(
        requirements,
        value=key_value,
        label=key_label,
        source=source,
        side_name="api_key",
        fields=frozenset({key_field}),
        group=group,
    )
    append_placeholder_requirement_if_managed(
        requirements,
        value=url_value,
        label=url_label,
        source=source,
        side_name="url",
        fields=frozenset({url_field}),
        group=group,
    )


def load_json_config_for_review(
    staging_root: Path,
    relpath: str,
    *,
    label: str,
) -> Optional[dict[str, Any]]:
    config_path = Path(staging_root) / relpath
    if not config_path.is_file():
        return None
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except OSError:
        return None
    except json.JSONDecodeError as exc:
        raise invalid_json_config_error(label, relpath, exc) from exc
    return payload if isinstance(payload, dict) else None


def load_toml_config_for_review(
    staging_root: Path,
    relpath: str,
    *,
    label: str,
) -> Optional[dict[str, Any]]:
    config_path = Path(staging_root) / relpath
    if not config_path.is_file():
        return None
    try:
        payload = safe_toml_loads(config_path.read_text(encoding="utf-8"))
    except OSError:
        return None
    except tomllib.TOMLDecodeError as exc:
        raise invalid_text_config_error(label, "TOML", relpath, str(exc)) from exc
    return payload if isinstance(payload, dict) else None


def load_yaml_config_for_review(
    staging_root: Path,
    relpath: str,
    *,
    label: str = "YAML config",
) -> Optional[dict[str, Any]]:
    config_path = Path(staging_root) / relpath
    if not config_path.is_file():
        return None
    try:
        payload = safe_yaml_mapping_loads(
            config_path.read_text(encoding="utf-8"),
            label=label,
        )
    except OSError:
        return None
    except (RuntimeError, ValueError) as exc:
        raise invalid_text_config_error(label, "YAML", relpath, str(exc)) from exc
    return payload


def validate_placeholder_review_requirements(
    reviewed_scan: dict[str, Any],
    *,
    requirements: list[PlaceholderReviewRequirement],
    error_prefix: str,
) -> None:
    missing = [
        requirement.label
        for requirement in requirements
        if not reviewed_url_proxy_has_any_side_field(
            reviewed_scan,
            source=requirement.source,
            side_name=requirement.side_name,
            fields=requirement.fields,
            group=requirement.group,
        )
    ]
    if missing:
        raise ValueError(f"{error_prefix}: {', '.join(sorted(missing))}")


def validate_config_placeholder_review_requirements(
    staging_root: Path,
    *,
    reviewed_scan: dict[str, Any],
    relpath: str,
    loader: Callable[[Path, str], Optional[dict[str, Any]]],
    requirement_builder: Callable[[dict[str, Any]], list[PlaceholderReviewRequirement]],
    error_prefix: str,
) -> None:
    payload = loader(Path(staging_root), relpath)
    if payload is None:
        return
    requirements = requirement_builder(payload)
    if not requirements:
        return
    validate_placeholder_review_requirements(
        reviewed_scan,
        requirements=requirements,
        error_prefix=error_prefix,
    )


def json_config_review_loader(label: str) -> Callable[[Path, str], Optional[dict[str, Any]]]:
    return lambda staging_root, relpath: load_json_config_for_review(
        staging_root,
        relpath,
        label=label,
    )


def toml_config_review_loader(label: str) -> Callable[[Path, str], Optional[dict[str, Any]]]:
    return lambda staging_root, relpath: load_toml_config_for_review(
        staging_root,
        relpath,
        label=label,
    )


def yaml_config_review_loader(label: str) -> Callable[[Path, str], Optional[dict[str, Any]]]:
    return lambda staging_root, relpath: load_yaml_config_for_review(
        staging_root,
        relpath,
        label=label,
    )


__all__ = [
    "PlaceholderReviewRequirement",
    "append_key_url_placeholder_requirements",
    "append_placeholder_requirement_if_managed",
    "load_json_config_for_review",
    "load_toml_config_for_review",
    "load_yaml_config_for_review",
    "placeholder_requirement_if_managed",
    "json_config_review_loader",
    "toml_config_review_loader",
    "validate_config_placeholder_review_requirements",
    "validate_placeholder_review_requirements",
    "yaml_config_review_loader",
]

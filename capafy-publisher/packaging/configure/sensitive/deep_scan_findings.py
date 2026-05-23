from __future__ import annotations

import re
from pathlib import Path

from packaging._shared.common.constants import STRUCTURED_ASSIGNMENT_PATTERNS
from packaging.configure.contracts import (
    PROCESS_ENV_SOURCE,
    DeepScanFinding,
    DeepScanFindingsInput,
    EnvVar,
    FieldLocation,
    GenericValue,
)
from packaging.configure.scan.structured_scan_policy import infer_assignment_service
from packaging.configure.sensitive.literals import infer_managed_value_type, looks_like_platform_managed_placeholder_value
from packaging.configure.sensitive.placeholders import build_placeholder, split_source
from packaging.configure.staging.source_boundary import final_zip_source_relpaths, normalize_packaged_source_relpath


_SOURCE_FIELD_TOKEN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*")
_ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _load_generic_findings(payload: object) -> tuple[DeepScanFinding, ...]:
    if payload is None:
        return ()
    if not isinstance(payload, list):
        raise ValueError("deep_scan_findings.generic must be an array")

    findings: list[DeepScanFinding] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"deep_scan_findings.generic[{index}] must be an object")
        value = str(item.get("value", "") or "").strip()
        source = str(item.get("source", "") or "").strip()
        if not value or not source:
            continue
        field = str(item.get("field", "") or "").strip()
        value_type = str(item.get("value_type", "") or "").strip() or "value"
        findings.append(
            DeepScanFinding(
                value=value,
                source=source,
                field=field,
                value_type=value_type,
            )
        )
    return tuple(findings)


def _load_env_var_findings(payload: object) -> tuple[EnvVar, ...]:
    if payload is None:
        return ()
    if not isinstance(payload, list):
        raise ValueError("deep_scan_findings.env_var must be an array")

    env_vars: list[EnvVar] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"deep_scan_findings.env_var[{index}] must be an object")
        value = str(item.get("value", "") or "").strip()
        field = str(item.get("field", "") or "").strip()
        if not value or not field:
            raise ValueError(f"deep_scan_findings.env_var[{index}] must include non-empty value and field")
        if not _ENV_NAME_PATTERN.fullmatch(field):
            raise ValueError(f"deep_scan_findings.env_var[{index}].field must be a valid env var name")
        value_type = str(item.get("value_type", "") or "").strip() or infer_managed_value_type(field, value)
        service = infer_assignment_service(PROCESS_ENV_SOURCE, field, value)
        env_vars.append(
            EnvVar(
                name=field,
                referenced_in=(),
                process_value=value,
                placeholder=build_placeholder(
                    service,
                    "\n".join((PROCESS_ENV_SOURCE, field)),
                    field=field,
                    locator="",
                    value_type=value_type,
                ),
            )
        )
    return tuple(env_vars)


def load_deep_scan_findings(payload: object) -> DeepScanFindingsInput:
    if payload is None:
        return DeepScanFindingsInput()
    if not isinstance(payload, dict):
        raise ValueError("deep_scan_findings must be an object with generic and env_var arrays")
    generic = _load_generic_findings(payload.get("generic"))
    env_var = _load_env_var_findings(payload.get("env_var"))
    return DeepScanFindingsInput(generic=generic, env_var=env_var)


def load_deep_scan_findings_json(raw_json: str | None) -> DeepScanFindingsInput:
    if raw_json is None or not str(raw_json).strip():
        return DeepScanFindingsInput()
    import json

    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"failed to parse deep_scan_findings_json: {exc}") from exc
    return load_deep_scan_findings(payload)


def load_deep_scan_findings_file(path: str | None) -> DeepScanFindingsInput:
    if not path:
        return DeepScanFindingsInput()
    findings_path = Path(path).expanduser()
    if not findings_path.is_file():
        raise ValueError(f"deep_scan_findings_file not found: {path}")
    return load_deep_scan_findings_json(findings_path.read_text(encoding="utf-8"))


def _location_from_source(source: str, value_type: str, *, field: str = "") -> FieldLocation:
    normalized_source = str(source or "").strip()
    _source_path, source_detail = split_source(normalized_source)
    _ = value_type
    return FieldLocation.from_source_detail(source_detail, field=field)


def _normalize_field_from_finding(finding: DeepScanFinding) -> str:
    field = str(finding.field or "").strip()
    if field:
        return field
    _source_path, source_detail = split_source(str(finding.source or "").strip())
    if source_detail.startswith("toml:") and "." in source_detail:
        return source_detail.rsplit(".", 1)[-1].strip()
    if source_detail.startswith("json:") and "/" in source_detail:
        return source_detail.rsplit("/", 1)[-1].strip()
    if source_detail.startswith("line "):
        return "value"
    return "value"


def _field_from_text_context(file_text: str, value: str) -> str:
    if not file_text or not value:
        return ""
    for raw_line in file_text.splitlines():
        if value not in raw_line:
            continue
        for pattern in STRUCTURED_ASSIGNMENT_PATTERNS:
            match = pattern.match(raw_line)
            if match and value in match.group("value"):
                return str(match.group("key") or "").strip()
        prefix = raw_line.split(value, 1)[0]
        tokens = _SOURCE_FIELD_TOKEN_PATTERN.findall(prefix)
        if tokens:
            return tokens[-1].strip()
    return ""


def _resolve_source_file(staging_root: Path, source_relpath: str) -> Path:
    normalized = source_relpath.replace("\\", "/").lstrip("/")
    if not normalized or normalized.startswith("../") or "/../" in normalized:
        raise ValueError(f"deep_scan_findings.source must be a staging-relative file path: {source_relpath}")
    path = (staging_root / normalized).resolve()
    root = staging_root.resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"deep_scan_findings.source escapes staging root: {source_relpath}")
    if not path.is_file():
        raise ValueError(f"deep_scan_findings.source file not found in staging: {source_relpath}")
    return path


def _generic_findings_to_values(
    staging_root: Path,
    findings: tuple[DeepScanFinding, ...],
    *,
    verify_sources: bool,
    agent_type: str,
) -> tuple[GenericValue, ...]:
    generic_values: list[GenericValue] = []
    seen_generic: set[tuple[str, str, str]] = set()
    packaged_sources = final_zip_source_relpaths(
        staging_root=staging_root,
        excluded_relpaths=(),
        agent_type=agent_type,
    )
    for finding in findings:
        if looks_like_platform_managed_placeholder_value(finding.value):
            continue
        source_relpath, source_detail = split_source(str(finding.source or "").strip())
        source_relpath = normalize_packaged_source_relpath(source_relpath)
        if source_relpath not in packaged_sources:
            continue
        field = _normalize_field_from_finding(finding)
        location = _location_from_source(finding.source, finding.value_type, field=field)
        file_text = ""
        if verify_sources:
            source_file = _resolve_source_file(staging_root, source_relpath)
            try:
                file_text = source_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise ValueError(f"deep_scan_findings.source must be a UTF-8 text file: {source_relpath}") from exc
            if finding.value not in file_text:
                raise ValueError(f"deep_scan_findings value not found in source file: {source_relpath}")
        if field == "value":
            field = _field_from_text_context(file_text, finding.value) or field
        key = (field, source_relpath, finding.value)
        if key in seen_generic:
            continue
        seen_generic.add(key)
        value_type = str(finding.value_type or "").strip() or infer_managed_value_type(field, finding.value)
        service = infer_assignment_service(source_relpath, field, finding.value)
        occurrence_index = sum(
            1
            for existing in generic_values
            if existing.source_relpath == source_relpath
            and existing.field == field
            and existing.value_type == value_type
        ) + 1
        if location.occurrence_index <= 0:
            location = FieldLocation(
                fmt=location.fmt,
                occurrence_index=occurrence_index,
                line_number=location.line_number,
                json_pointer=location.json_pointer,
                toml_section=location.toml_section,
                key_path=location.key_path,
            )
        generic_values.append(
            GenericValue(
                field=field,
                source_relpath=source_relpath,
                location=location,
                original_value=finding.value,
                placeholder=build_placeholder(
                    service,
                    "\n".join((source_relpath, source_detail, str(location.occurrence_index))),
                    field=field,
                    locator="",
                    value_type=value_type,
                ),
                value_type=value_type,
            )
        )
    return tuple(generic_values)


def deep_scan_findings_to_generic_values_for_staging(
    staging_root: Path,
    findings: DeepScanFindingsInput,
    *,
    agent_type: str = "run_online",
    verify_sources: bool = True,
) -> tuple[GenericValue, ...]:
    return _generic_findings_to_values(
        staging_root,
        findings.generic,
        verify_sources=verify_sources,
        agent_type=agent_type,
    )


def deep_scan_findings_to_reviewed_inputs_for_staging(
    staging_root: Path,
    findings: DeepScanFindingsInput,
    *,
    agent_type: str = "run_online",
    verify_sources: bool = True,
) -> tuple[tuple[GenericValue, ...], tuple[EnvVar, ...]]:
    generic_values = deep_scan_findings_to_generic_values_for_staging(
        staging_root,
        findings,
        verify_sources=verify_sources,
        agent_type=agent_type,
    )
    return generic_values, tuple(findings.env_var)


__all__ = [
    "DeepScanFinding",
    "deep_scan_findings_to_generic_values_for_staging",
    "deep_scan_findings_to_reviewed_inputs_for_staging",
    "load_deep_scan_findings",
    "load_deep_scan_findings_file",
    "load_deep_scan_findings_json",
]

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

from packaging.publish.artifacts.bundle_context import VALID_AGENT_TYPES
from packaging.publish.selection.selection_groups import (
    SELECTION_GROUP_KEYS,
    normalize_documented_selection_groups,
    selected_items_for_group,
    strip_default_selection_fields,
)
from packaging.publish.selection.selectable import is_absolute_like_path

PACKAGE_REPORT_ALLOWED_STATUSES = {0, 2}

_DOCUMENTED_AGENT_RUNTIME_BY_ENV_ID = {
    "claude_code": "claude",
    "codex": "codex",
    "hermes": "hermes",
    "openclaw": "openclaw",
}
_ENV_ID_BY_DOCUMENTED_AGENT_RUNTIME = {
    "claude": "claude_code",
    "claude_code": "claude_code",
    "codex": "codex",
    "hermes": "hermes",
    "openclaw": "openclaw",
}

# Default language codes accepted by the platform addAgent endpoint; the value is
# stored on the card's defaultLanguageCode field. Keep in sync with backend docs.
SUPPORTED_DEFAULT_LANGUAGE_CODES = frozenset(
    {"en", "es", "fr", "de", "it", "ja", "zh", "zh-TW", "ar", "nl", "ko", "pt"}
)
_CANONICAL_LANGUAGE_CODE_BY_LOWER = {code.lower(): code for code in SUPPORTED_DEFAULT_LANGUAGE_CODES}


def normalize_default_language_code(value: object) -> Optional[str]:
    """Return the canonical language code, or None when no value is provided.

    Input is matched case-insensitively (so ``zh-tw`` resolves to ``zh-TW``).
    Raises ValueError when a non-empty value is not in the supported enum.
    """
    candidate = str(value or "").strip()
    if not candidate:
        return None
    canonical = _CANONICAL_LANGUAGE_CODE_BY_LOWER.get(candidate.lower())
    if canonical is None:
        raise ValueError(f"Unknown default language code: {value}")
    return canonical


def documented_agent_runtime_from_values(*values: object) -> str:
    for value in values:
        candidate = str(value or "").strip()
        if not candidate:
            continue
        runtime = _DOCUMENTED_AGENT_RUNTIME_BY_ENV_ID.get(candidate)
        if runtime:
            return runtime
    return ""


def env_id_from_agent_runtime(agent_runtime: object) -> str:
    runtime = str(agent_runtime or "").strip()
    if not runtime:
        return ""
    env_id = _ENV_ID_BY_DOCUMENTED_AGENT_RUNTIME.get(runtime)
    if env_id:
        return env_id
    return ""


def normalize_agent_type(agent_type: object) -> str:
    normalized = str(agent_type or "").strip().lower()
    if not normalized:
        return "run_online"
    if normalized not in VALID_AGENT_TYPES:
        raise ValueError(f"Unknown agentType: {agent_type}")
    return normalized


def _normalize_int(value: object) -> Optional[int]:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    normalized = str(value or "").strip()
    if not normalized:
        return None
    try:
        return int(normalized)
    except ValueError:
        return None


def _is_confirmed(value: object) -> bool:
    normalized = _normalize_int(value)
    if normalized is not None:
        return normalized == 1
    normalized_text = str(value or "").strip().lower()
    return normalized_text == "true"


def _status_code(value: object, *, allowed: set[int]) -> Optional[int]:
    if isinstance(value, bool):
        return None
    normalized = _normalize_int(value)
    return normalized if normalized in allowed else None


def _workflow_selection_groups(value: object) -> Dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"workflowInfo is not a valid JSON object: {exc}") from exc
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ValueError("workflowInfo must be an object or a JSON object string")
    raw_groups = value.get("selection_groups")
    if "selection_groups" in value and not isinstance(raw_groups, dict):
        raise ValueError("workflow_info.selection_groups must be an object")
    if isinstance(raw_groups, dict):
        for key in SELECTION_GROUP_KEYS:
            if key not in raw_groups:
                continue
            items = raw_groups.get(key)
            if not isinstance(items, list):
                raise ValueError(f"workflow_info.selection_groups.{key} must be an array")
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError(f"workflow_info.selection_groups.{key} array items must be objects")
                path = item.get("path")
                if not isinstance(path, str) or not path.strip():
                    raise ValueError(f"workflow_info.selection_groups.{key} items must include path")
                if is_absolute_like_path(path):
                    raise ValueError(
                        f"workflow_info.selection_groups.{key} item path must be a logical path, not an absolute path"
                    )
                purpose = item.get("purpose")
                if purpose is not None and not isinstance(purpose, str):
                    raise ValueError(f"workflow_info.selection_groups.{key} item purpose must be a string")
                confirmation = item.get("requires_user_confirmation")
                if confirmation is not None and not isinstance(confirmation, bool):
                    raise ValueError(
                        f"workflow_info.selection_groups.{key} item requires_user_confirmation must be a boolean"
                    )
    return strip_default_selection_fields(
        normalize_documented_selection_groups(raw_groups)
    )


@dataclass(frozen=True)
class LatestVersion:
    agent_id: str
    agent_version_id: str
    agent_package_id: Optional[str]
    agent_runtime: str
    env_id: str
    agent_type: str
    is_confirmed_skills: bool
    is_confirmed_config_keys: bool
    status: Optional[int]
    audit_status: Optional[int]
    selection_groups: Dict[str, Any]
    package_url: Any = None
    version_no: Any = None
    version_name: Any = None
    title: Any = None
    short_description: Any = None

    @classmethod
    def from_response(cls, agent_id: str, payload: dict[str, Any]) -> "LatestVersion":
        normalized_agent_id = str(agent_id or "").strip()
        if not normalized_agent_id:
            raise ValueError("agent_id must not be empty")
        if not isinstance(payload, dict):
            raise ValueError("latest-version response must be an object")
        response_agent_id = str(payload.get("agentId", "") or normalized_agent_id).strip()
        agent_version_id = str(payload.get("agentVersionId", "") or "").strip()
        agent_runtime = str(payload.get("agentRuntime", "") or "").strip()
        agent_package_id = str(payload.get("agentPackageId", "") or "").strip() or None
        return cls(
            agent_id=response_agent_id,
            agent_version_id=agent_version_id,
            agent_package_id=agent_package_id,
            agent_runtime=agent_runtime,
            env_id=env_id_from_agent_runtime(agent_runtime),
            agent_type=normalize_agent_type(payload.get("agentType")),
            is_confirmed_skills=_is_confirmed(payload.get("isConfirmedSkills")),
            is_confirmed_config_keys=_is_confirmed(payload.get("isConfirmedConfigKeys")),
            status=_status_code(payload.get("status"), allowed={0, 1, 2, 3, 4, 5, 6}),
            audit_status=_status_code(payload.get("auditStatus"), allowed={0, 1, 2, 3, 4}),
            selection_groups=_workflow_selection_groups(payload.get("workflowInfo")),
            package_url=payload.get("packageUrl"),
            version_no=payload.get("versionNo"),
            version_name=payload.get("versionName"),
            title=payload.get("title"),
            short_description=payload.get("shortDescription"),
        )

    @property
    def status_complete(self) -> bool:
        configuration_confirmed = self.agent_type == "download" or self.is_confirmed_config_keys
        return bool(
            self.agent_version_id
            and self.agent_package_id
            and self.agent_type in VALID_AGENT_TYPES
            and self.status is not None
            and self.audit_status is not None
            and self.is_confirmed_skills
            and configuration_confirmed
        )

    @property
    def can_report_published(self) -> bool:
        return self.status == 4 and self.audit_status == 4 and self.status_complete

    def public_payload(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_version_id": self.agent_version_id,
            "agent_package_id": self.agent_package_id,
            "agent_type": self.agent_type,
            "agent_runtime": self.agent_runtime,
            "platform_status": self.status,
            "audit_status": self.audit_status,
            "is_confirmed_skills": self.is_confirmed_skills,
            "is_confirmed_config_keys": self.is_confirmed_config_keys,
            "version_no": self.version_no,
            "version_name": self.version_name,
            "title": self.title,
            "short_description": self.short_description,
            "selection_groups": self.selection_groups,
            "status_complete": self.status_complete,
            "can_report_published": self.can_report_published,
            "status_reason": {
                0: "draft_review_not_started",
                1: "under_review",
                2: "review_rejected",
                3: "review_passed_pending_listing",
                4: "listed",
                5: "expired",
                6: "delisted",
            }.get(self.status, "platform_status_incomplete"),
        }


def skill_selection_gate(latest: object) -> Optional[str]:
    """Return the shared platform Skill-selection gate result."""
    if not bool(getattr(latest, "is_confirmed_skills", False)):
        return "not_confirmed"
    groups = normalize_documented_selection_groups(
        getattr(latest, "selection_groups", {})
    )
    if not selected_items_for_group(groups, "skills"):
        return "empty"
    return None


__all__ = [
    "documented_agent_runtime_from_values",
    "env_id_from_agent_runtime",
    "LatestVersion",
    "normalize_default_language_code",
    "PACKAGE_REPORT_ALLOWED_STATUSES",
    "normalize_agent_type",
    "SUPPORTED_DEFAULT_LANGUAGE_CODES",
    "VALID_AGENT_TYPES",
    "skill_selection_gate",
]

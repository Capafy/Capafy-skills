from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Tuple

from packaging.publish.domain.contexts import PrepareContext, StageContext

from packaging.publish.profiles.download.prepare import run_download_prepare
from packaging.publish.profiles.download.stage import stage_buyout
from packaging.publish.profiles.run_online.prepare import run_run_online_prepare
from packaging.publish.profiles.run_online.stage import stage_cloud_hosted


@dataclass(frozen=True)
class PublishProfile:
    stage: Callable[[StageContext], Dict[str, Any]]
    prepare: Callable[[PrepareContext], Tuple[Dict[str, Any], int]]


_REGISTRY: Dict[str, PublishProfile] = {
    "run_online": PublishProfile(
        stage=stage_cloud_hosted,
        prepare=run_run_online_prepare,
    ),
    "download": PublishProfile(
        stage=stage_buyout,
        prepare=run_download_prepare,
    ),
}


def get_publish_profile(agent_type: str) -> PublishProfile:
    normalized = str(agent_type).strip()
    if not normalized:
        raise ValueError("Unknown agent_type: empty")
    try:
        return _REGISTRY[normalized]
    except KeyError as exc:
        raise ValueError(f"Unknown agent_type: {agent_type}") from exc


__all__ = [
    "PublishProfile",
    "get_publish_profile",
]

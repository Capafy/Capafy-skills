from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Tuple

from packaging._shared.mode_dispatch import lookup_mode
from packaging.configure.contexts import ConfigureContext, StageContext

from packaging.configure.buyout.configure import run_buyout_configure
from packaging.configure.buyout.stage import stage_buyout
from packaging.configure.cloud_hosted.configure import run_cloud_hosted_configure
from packaging.configure.cloud_hosted.stage import stage_cloud_hosted


@dataclass(frozen=True)
class ConfigureMode:
    name: str
    stage: Callable[[StageContext], Dict[str, Any]]
    configure: Callable[[ConfigureContext], Tuple[Dict[str, Any], int]]


CLOUD_HOSTED = ConfigureMode(
    name="run_online",
    stage=stage_cloud_hosted,
    configure=run_cloud_hosted_configure,
)

BUYOUT = ConfigureMode(
    name="download",
    stage=stage_buyout,
    configure=run_buyout_configure,
)

_REGISTRY: Dict[str, ConfigureMode] = {
    "run_online": CLOUD_HOSTED,
    "download": BUYOUT,
}


def get_configure_mode(agent_type: str) -> ConfigureMode:
    return lookup_mode(_REGISTRY, agent_type)


__all__ = [
    "BUYOUT",
    "CLOUD_HOSTED",
    "ConfigureMode",
    "get_configure_mode",
]

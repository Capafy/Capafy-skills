from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EffectiveScanGroups:
    url_proxy: list[dict]
    generic: list[dict]
    env_var: list[dict]
    excludes: list[dict]

    @classmethod
    def from_reviewed_scan(cls, payload: dict) -> "EffectiveScanGroups":
        return cls(
            url_proxy=_list_dict_items(payload, "url_proxy"),
            generic=_list_dict_items(payload, "generic"),
            env_var=_list_dict_items(payload, "env_var"),
            excludes=_list_dict_items(payload, "excludes"),
        )

    def to_scan_groups_dict(self) -> dict:
        result = {
            "url_proxy": list(self.url_proxy),
            "generic": list(self.generic),
            "env_var": list(self.env_var),
            "excludes": list(self.excludes),
        }
        assert "_review" not in result, "EffectiveScanGroups must never contain _review"
        return result


def _list_dict_items(payload: dict, key: str) -> list[dict]:
    value = payload.get(key, [])
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


__all__ = ["EffectiveScanGroups"]

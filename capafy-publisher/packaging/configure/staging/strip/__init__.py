from __future__ import annotations

from packaging.configure.staging.strip.fallback import (
    StripSummary,
    apply_strip,
    collect_strip_targets as collect_reviewed_input_strip_targets,
    replace_values_in_staging,
)
from packaging.configure.staging.strip.generic import apply_generic_to_staging
from packaging.configure.staging.strip.batch import (
    _run_strip_by_platform_groups,
    collect_strip_targets,
    run_strip_batch,
)


__all__ = [
    "StripSummary",
    "apply_generic_to_staging",
    "apply_strip",
    "collect_reviewed_input_strip_targets",
    "collect_strip_targets",
    "replace_values_in_staging",
    "run_strip_batch",
    "_run_strip_by_platform_groups",
]

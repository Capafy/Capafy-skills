from __future__ import annotations

import sys

from packaging.runtimes.hermes import config as _runtime_config


sys.modules[__name__] = _runtime_config

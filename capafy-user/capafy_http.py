from __future__ import annotations

from pathlib import Path
import sys
from typing import Optional

try:
    from scripts.capafy_http import request
    from scripts.capafy_http import _main as _scripts_main
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from scripts.capafy_http import request
    from scripts.capafy_http import _main as _scripts_main


def _main(argv: Optional[list[str]] = None) -> int:
    return _scripts_main(argv)


if __name__ == "__main__":
    sys.exit(_main())

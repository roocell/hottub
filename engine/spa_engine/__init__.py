from __future__ import annotations

import sys
from pathlib import Path

__all__ = ["__version__"]
__version__ = "0.1.0"

# Dev-only: prefer local geckolib checkout when present.
_repo_root = Path(__file__).resolve().parents[2]
_local_geckolib_src = _repo_root / "geckolib" / "src"
if _local_geckolib_src.is_dir():
    _local_geckolib_src_str = str(_local_geckolib_src)
    if _local_geckolib_src_str not in sys.path:
        sys.path.insert(0, _local_geckolib_src_str)

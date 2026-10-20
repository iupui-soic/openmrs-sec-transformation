"""Study-window settings, read from [tool.ose-icse27] in pyproject.toml.

pyproject.toml is the ONE place to change the study end date (`window_end`).
Mining scripts (via common.py) and analysis scripts all import from here.

`activity_end` is kept as a separate setting on purpose: it defines which
repositories count as "active" (the 44-repo sample and the 49-repo comparison
cohort). Moving it would change the sample, so it stays frozen unless the
sample definition itself is deliberately revised.
"""
from __future__ import annotations

from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ImportError:  # Python 3.9/3.10
    import tomli as tomllib

_PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"
_CFG = tomllib.loads(_PYPROJECT.read_text())["tool"]["ose-icse27"]

WINDOW_START = _CFG["window_start"]
WINDOW_END = _CFG["window_end"]          # study end date (single source of truth)
ACTIVITY_START = _CFG["activity_start"]
ACTIVITY_END = _CFG["activity_end"]      # sample-definition window; see docstring

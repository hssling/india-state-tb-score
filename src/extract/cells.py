"""Cell parsers. Blanks, dashes and NA are errors: callers decide their meaning."""
from __future__ import annotations

import re

_INT = re.compile(r"^\*?(\d+(?:,\d+)*)\*?$")
_COUNT = re.compile(r"^\*?(\d+(?:,\d+)*)(?:\.(\d+))?\*?$")
_N_PCT = re.compile(r"^\s*(\S+?)\s*\(\s*(\d+(?:\.\d+)?)\s*%\s*\)\s*$")


def parse_int(s: str) -> int:
    """'1,23,456' / '1,234,567' / '*89' -> int; ValueError for anything else."""
    m = _INT.match(s.strip())
    if not m:
        raise ValueError(f"not an integer cell: {s!r}")
    return int(m.group(1).replace(",", ""))


def parse_count(s: str) -> int:
    """Like parse_int, but also accepts integral floats: '63.0' -> 63.

    CTD prints some count columns from a spreadsheet as '4607.0'. A
    non-integral value ('63.5') is not a count and raises ValueError.
    """
    m = _COUNT.match(s.strip())
    if not m or (m.group(2) is not None and int(m.group(2)) != 0):
        raise ValueError(f"not a count cell: {s!r}")
    return int(m.group(1).replace(",", ""))


def parse_n_pct(s: str) -> tuple[int, float]:
    """'62795 (99%)' -> (62795, 99.0)."""
    m = _N_PCT.match(s)
    if not m:
        raise ValueError(f"not an 'n (pct%)' cell: {s!r}")
    return parse_int(m.group(1)), float(m.group(2))

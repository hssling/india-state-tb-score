"""Task 5: indicator achievement and scoring rules R1-R3 (analysis plan 5.2, 6).

R4 (threshold bands) is not implemented: ITR2024 states no bands (plan 6.1).
"""
import csv
from collections import defaultdict

POINTS = {1: 20, 2: 10, 3: 10, 4: 15, 5: 10, 6: 15, 7: 10, 8: 5, 9: 5}
RULES = ("R1", "R2", "R3")
UDST_BENCHMARK = 0.7  # indicator 3 denominator = 0.7 x net notified (plan 5.2)


def load(path):
    """Read a CSV into a list of dict rows (all values strings)."""
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _num(v):
    if v is None:
        return None
    v = str(v).strip()
    return None if v == "" else float(v.replace(",", ""))


def achievement(rows):
    """state -> {indicator: a or None}. Blank value or zero denominator -> None.

    Not capped. Indicators with no rows are absent, not None.
    """
    out = defaultdict(dict)
    for r in rows:
        ind = int(r["indicator"])
        num, den = _num(r["numerator"]), _num(r["denominator"])
        if ind == 3 and den is not None:
            den = UDST_BENCHMARK * den
        out[r["state"]][ind] = None if num is None or den is None or den == 0 else num / den
    return dict(out)


def score(ach, rule, indicators=range(1, 10), rescale=False):
    """state -> score (or None if a used indicator is not computable).

    Indicators absent for every state are skipped. rescale=True gives
    100 x points earned / max points of the indicators used.
    """
    if rule == "R4":
        raise NotImplementedError("R4 bands not documented")
    if rule not in RULES:
        raise ValueError(f"unknown rule {rule!r}")
    used = [i for i in indicators if any(i in a for a in ach.values())]
    best = {}
    if rule == "R3":
        for i in used:
            vals = [a[i] for a in ach.values() if a.get(i) is not None]
            best[i] = max(vals) if vals else None
    max_pts = sum(POINTS[i] for i in used)
    out = {}
    for state, a in ach.items():
        total = 0.0
        for i in used:
            v = a.get(i)  # a state lacking a used indicator is non-computable
            if v is None:
                total = None
                break
            if rule == "R1":
                total += POINTS[i] * min(v, 1.0)
            elif rule == "R2":
                total += POINTS[i] * v
            else:  # R3; if every computable a is 0, 0/0 is taken as 0 points
                total += POINTS[i] * v / best[i] if best[i] else 0.0
        if total is not None and rescale:
            total = 100.0 * total / max_pts if max_pts else None
        out[state] = total
    return out

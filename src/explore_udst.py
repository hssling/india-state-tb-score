"""EXPLORATORY (not pre-specified): Q1 with indicator 3 scaled to CTD's national figure.

Usage: python -I src/explore_udst.py

Logged as a dated deviation in plan section 13 (17 November 2026); added after the final
review of the analysis, not before it. It is not part of the confirmatory Q1 verdict
(plan 6.1: "not reproducible" is claimed only against R1-R4).

Question: how much of the Q1 band violation is explained by indicator 3's numerator? The
only state-wise column with a rifampicin result (annexure 4.7) counts fewer patients than
the national figure CTD prints in Table 11.1 (key performance indicator 4). For score year
2023, every state's indicator 3 achievement is multiplied by

    k = CTD's national share ÷ the annexures' national share,

where CTD's share is read from the recorded source note of indicator 3
(data/source_choices.csv) and the annexures' share is the sum of the indicator 3
numerators over the sum of their denominators (data/extracted/itr2024_indicators.csv).
No number is typed here. The R1, R2 and R3 partial scores and the plan 7.2 band test are
then recomputed exactly as in src/q1_reproduce.py. Under R3 the scaling cancels (each
achievement is divided by the scaled maximum), so R3 is unchanged by construction.

Writes outputs/exploratory_udst_scaling_2023.csv: one row per state and rule
(row_type "state") and one summary row per rule (row_type "rule_summary"); every row has
label = "exploratory".
"""
import csv
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import score as sc  # noqa: E402
from src.q1_reproduce import select_rule  # noqa: E402

YEAR = 2023
LABEL = "exploratory"
OUT = os.path.join(ROOT, "outputs", f"exploratory_udst_scaling_{YEAR}.csv")
COLS = ["label", "score_year", "row_type", "rule", "state", "published", "a3_annexure",
        "a3_scaled", "partial", "residual", "in_band", "violation", "n_in_band",
        "n_compared", "max_violation", "outside", "k", "ctd_share", "annexure_numerator",
        "annexure_denominator"]


def ctd_share(choices_path):
    """CTD's national indicator 3 share (a proportion) from the recorded source note, and
    the annexure counts the note states (checked against the extracted data by caller)."""
    rows = [r for r in sc.load(choices_path)
            if (r["score_year"], r["indicator"], r["component"]) == (str(YEAR), "3", "numerator")]
    if len(rows) != 1:
        raise ValueError("source_choices.csv: expected one 2023 indicator 3 numerator row")
    note = rows[0]["note"]
    m = re.search(r"prints (\d+(?:\.\d+)?)% of notified patients", note)
    c = re.search(r"gives ([\d,]+) / ([\d,]+) = ", note)
    if not (m and c):
        raise ValueError("source_choices.csv: CTD share or annexure counts not in the note")
    return float(m.group(1)) / 100, int(c.group(1).replace(",", "")), int(c.group(2).replace(",", ""))


def scaling_factor(rows, choices_path):
    """(k, ctd share, annexure numerator, annexure denominator) for indicator 3."""
    share, note_k, note_n = ctd_share(choices_path)
    ind3 = [r for r in rows if r["indicator"] == "3"]
    num = sum(int(r["numerator"]) for r in ind3)
    den = sum(int(r["denominator"]) for r in ind3)
    if (num, den) != (note_k, note_n):
        raise ValueError(f"indicator 3 counts {num}/{den} differ from the source note "
                         f"{note_k}/{note_n}")
    return share / (num / den), share, num, den


def scaled_achievement(ach, k):
    """A copy of ach with every computable indicator 3 achievement multiplied by k."""
    out = {}
    for s, a in ach.items():
        b = dict(a)
        if b.get(3) is not None:
            b[3] = b[3] * k
        out[s] = b
    return out


def _fmt(x):
    return "" if x is None else repr(x)


def main():
    ext = os.path.join(ROOT, "data", "extracted")
    rows = [r for r in sc.load(os.path.join(ext, f"itr{YEAR + 1}_indicators.csv"))
            if int(r["score_year"]) == YEAR]
    published = {r["state"]: (None if r["score"].strip() == "" else float(r["score"]))
                 for r in sc.load(os.path.join(ext, f"itr{YEAR + 1}_scores.csv"))
                 if int(r["score_year"]) == YEAR}
    k, share, num, den = scaling_factor(rows, os.path.join(ROOT, "data", "source_choices.csv"))

    ach = sc.achievement(rows)
    available = sorted({i for a in ach.values() for i in a})
    missing = [i for i in range(1, 10) if i not in available]
    missing_points = sum(sc.POINTS[i] for i in missing)
    scaled = scaled_achievement(ach, k)
    partial = {r: sc.score(scaled, r) for r in sc.RULES}
    res = select_rule(published, partial, missing_points, missing_indicators=missing)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLS)
        for r in sc.RULES:
            p = res["per_rule"][r]
            w.writerow([LABEL, YEAR, "rule_summary", r, "", "", "", "", "", "", "", "",
                        p["n_in_band"], p["n_compared"], _fmt(p["max_violation"]),
                        "; ".join(sorted(p["outside"])), repr(k), repr(share), num, den])
        for r in sc.RULES:
            for s in sorted(res["per_state"]):
                e = res["per_state"][s][r]
                in_band = e.get("in_band")
                w.writerow([LABEL, YEAR, "state", r, s, _fmt(e["published"]),
                            _fmt(ach[s].get(3)), _fmt(scaled[s].get(3)), _fmt(e["partial"]),
                            _fmt(e["residual"]), "" if in_band is None else int(in_band),
                            _fmt(e.get("violation")), "", "", "", "", "", "", "", ""])

    print(f"EXPLORATORY: indicator 3 scaled by k = {share:.2f} / ({num}/{den}) = {k:.4f}")
    for r in sc.RULES:
        p = res["per_rule"][r]
        out = "; ".join(f"{s} {v:+.2f}" for s, v in sorted(p["outside"].items()))
        print(f"{r}: in band {p['n_in_band']}/{p['n_compared']}, max violation "
              f"{p['max_violation']:.2f}; outside: {out or 'none'}")
    print(f"excluded (not computable): {', '.join(res['excluded']) or 'none'}")
    print(f"wrote {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()

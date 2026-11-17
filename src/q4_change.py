"""Task 9b: Q4 change over time, score years 2022 and 2023 (analysis plan 10).

Usage: python -I src/q4_change.py

Only comparison (b) of 10.1 is run: both years re-scored under one
definition. No edition prints numeric state scores for 2022, so (a), the
published change, is not possible (plan 13 item 2). Both years are scored
on the indicators available in both, {1,2,3,4,6}, as the rescaled partial
score (plan 13 item 7; controller ruling R24), and again with indicator 1
excluded, {2,3,4,6} (plan 13 item 5). Rules: outputs/q1_2023_selection.json
rules_for_q2q4 (primary) and sensitivity_rules. Primary row: R2, {1,2,3,4,6}.

Noise model (10.2), per state s, indicator i, year t (uncapped, every rule):
  indicator 1   Poisson   se = sqrt(numerator) / target
  indicator 3   p = numerator / net notified, n = net notified,
                se = sqrt(p (1 - p) / n) / 0.7
  2, 4, 5, 6, 8, 9  binomial  se = sqrt(a (1 - a) / n), n = denominator
  7             se = 0 (expenditure ratio)
A binomial indicator with a > 1 (p > 1 for indicator 3) is a data error:
flagged, its se is not computable, so is the state's SE.
SE_s,t = sqrt(sum_i pts_i^2 se_si^2), pts_i the points in use (x 100 /
max points when rescaled; / the year's maximum a over states under R3).
Criterion (10.3): |s_2023 - s_2022| > 1.96 sqrt(SE_2023^2 + SE_2022^2).
10.4: Spearman's rho (q3_validity.spearman_ci) between s_2022 and the
change, over the states with a score in both years; change as % of s_2022.
Union territories are flagged by canonical UT status (ruling R28).

Writes outputs/q4_2022_2023_states.csv and outputs/q4_2022_2023_summary.csv.
"""
import csv
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import score as sc  # noqa: E402
from src import states  # noqa: E402
from src.q3_validity import spearman_ci  # noqa: E402

Z975 = 1.96
YEARS = (2022, 2023)
COMMON = (1, 2, 3, 4, 6)       # ruling R24 / plan 13 item 7
NO_IND1 = (2, 3, 4, 6)         # plan 13 item 5
SETS = ((COMMON, "1,2,3,4,6"), (NO_IND1, "2,3,4,6 (indicator 1 excluded)"))
UTS = ("Andaman and Nicobar Islands", "Chandigarh",
       "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Jammu and Kashmir",
       "Ladakh", "Lakshadweep", "Puducherry")  # ruling R28: canonical UT status


def _used(ach, indicators):
    return [i for i in indicators if any(i in a for a in ach.values())]


def _component(i, a, n):
    """(se, flag) for one achievement; se None if not computable, flag a
    data-error description or ''."""
    if i == 7:
        return 0.0, ""
    if a is None or n is None or n <= 0:
        return None, ""
    if i == 1:  # Poisson: sqrt(numerator) / target, numerator = a x target
        return (math.sqrt(a / n) if a >= 0 else None), ""
    if i == 3:  # binomial on the proportion tested, against the 0.7 benchmark
        p = sc.UDST_BENCHMARK * a
        if p > 1:
            return None, f"indicator 3: binomial p = {p:.4g} > 1 ({p * n:g}/{n:g})"
        return math.sqrt(p * (1 - p) / n) / sc.UDST_BENCHMARK, ""
    if a > 1:
        return None, f"indicator {i}: binomial a = {a:.4g} > 1 ({a * n:g}/{n:g})"
    return math.sqrt(a * (1 - a) / n), ""


def se_components(ach, n, indicators):
    """state -> {indicator: se or None} over the indicators of `indicators`
    present in ach (as score.score). See score_se for ach and n."""
    used = _used(ach, indicators)
    return {s: {i: _component(i, a.get(i), n.get(s, {}).get(i))[0] for i in used}
            for s, a in ach.items()}


def se_flags(ach, n, indicators):
    """state -> [data-error flag, ...] (binomial a > 1) over the indicators."""
    used = _used(ach, indicators)
    out = {}
    for s, a in ach.items():
        f = [_component(i, a.get(i), n.get(s, {}).get(i))[1] for i in used]
        f = [x for x in f if x]
        if f:
            out[s] = f
    return out


def score_se(ach, n, rule, indicators, rescale=True, best=None):
    """state -> SE of the score (plan 10.2), or None if not computable.

    ach: state -> {indicator: a}, uncapped achievement as score.achievement
      gives it for ONE score year (indicator 3: a = numerator / (0.7 x net
      notified)).
    n: state -> {indicator: n}, the denominator as stored in the extracted
      CSV: indicator 1 the target (se = sqrt(a x target) / target =
      sqrt(numerator) / target); indicator 3 the net notified count, before
      the 0.7 benchmark (p = 0.7 a); every other indicator its denominator.
    Points in use: POINTS[i], x 100 / (sum of POINTS over the indicators used)
    if rescale, and / best[i] under R3. best defaults to the maximum a over
    the states of ach with a computable a (as score.score), treated as fixed.
    The same uncapped se is used under every rule (R1 is not capped here).
    """
    if rule not in sc.RULES:
        raise ValueError(f"unknown rule {rule!r}")
    used = _used(ach, indicators)
    max_pts = sum(sc.POINTS[i] for i in used)
    factor = 100.0 / max_pts if rescale and max_pts else 1.0
    if rule == "R3" and best is None:
        best = {}
        for i in used:
            vals = [a[i] for a in ach.values() if a.get(i) is not None]
            best[i] = max(vals) if vals else None
    pts = {}
    for i in used:
        p = sc.POINTS[i] * factor
        if rule == "R3":
            p = p / best[i] if best.get(i) else 0.0  # as score.score: 0/0 -> 0 points
        pts[i] = p
    comp = se_components(ach, n, used)
    out = {}
    for s, c in comp.items():
        if any(c.get(i) is None for i in used):
            out[s] = None
        else:
            out[s] = math.sqrt(sum(pts[i] ** 2 * c[i] ** 2 for i in used))
    return out


def exceeds_noise(s_t, s_prev, se_t, se_prev):
    """Plan 10.3: |s_t - s_prev| > 1.96 sqrt(se_t^2 + se_prev^2) (strict)."""
    return abs(s_t - s_prev) > Z975 * math.sqrt(se_t ** 2 + se_prev ** 2)


def compare(s_prev, se_prev, s_t, se_t, labels=("t-1", "t"), notes=None):
    """state -> {change, pct_change, threshold, exceeds, excluded_reason}.

    A state lacking a score or an SE in either year is excluded from 10.3
    (exceeds None) with the reason; change and pct_change are still given
    where both scores exist. notes: optional (prev, t) dicts state -> text
    appended to an SE reason.
    """
    notes = notes or ({}, {})
    out = {}
    for s in sorted(set(s_prev) | set(s_t)):
        why = []
        for lab, sv, sev, nt in ((labels[0], s_prev, se_prev, notes[0]),
                                 (labels[1], s_t, se_t, notes[1])):
            if sv.get(s) is None:
                why.append(f"score not computable in {lab}")
            elif sev.get(s) is None:
                why.append(f"SE not computable in {lab}" + (f" ({nt[s]})" if s in nt else ""))
        a, b = s_prev.get(s), s_t.get(s)
        change = b - a if a is not None and b is not None else None
        pct = 100.0 * change / a if change is not None and a else None
        if why:
            thr, exc = None, None
        else:
            thr = Z975 * math.sqrt(se_t[s] ** 2 + se_prev[s] ** 2)
            exc = exceeds_noise(b, a, se_t[s], se_prev[s])
        out[s] = {"change": change, "pct_change": pct, "threshold": thr,
                  "exceeds": exc, "excluded_reason": "; ".join(why)}
    return out


# ---- run -------------------------------------------------------------------

def _cell(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return str(int(v))
    return repr(v) if isinstance(v, float) else str(v)


def _write(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        for r in rows:
            w.writerow([_cell(r[h]) for h in header])


def load_year(ext, year):
    """(ach, n, net_notified) for one score year from its edition's CSV."""
    rows = [r for r in sc.load(os.path.join(ext, f"itr{year + 1}_indicators.csv"))
            if int(r["score_year"]) == year]
    ach = sc.achievement(rows)  # ignores score_year: rows filtered above
    states.require_all(ach, year)
    n = {}
    for r in rows:
        n.setdefault(r["state"], {})[int(r["indicator"])] = sc._num(r["denominator"])
    nn = {}
    for s, d in n.items():  # net notified feeds indicators 2, 3 and 4 (source_choices)
        if not d.get(2) or d.get(2) != d.get(3) or d.get(2) != d.get(4):
            raise ValueError(f"{year} {s}: net notified differs across indicators 2-4")
        nn[s] = int(d[2]) if d[2] == int(d[2]) else d[2]
    return ach, n, nn


def _states_with_se0(comp):
    return sorted(s for s, c in comp.items() if any(v == 0.0 for v in c.values()))


def main():
    ext = os.path.join(ROOT, "data", "extracted")
    out_dir = os.path.join(ROOT, "outputs")
    with open(os.path.join(out_dir, "q1_2023_selection.json"), encoding="utf-8") as f:
        sel = json.load(f)
    primary = list(sel["rules_for_q2q4"])
    rules = list(dict.fromkeys(primary + list(sel["sensitivity_rules"])))
    data = {y: load_year(ext, y) for y in YEARS}
    for y in YEARS:
        missing = [i for i in COMMON if not any(i in a for a in data[y][0].values())]
        if missing:
            raise ValueError(f"{y}: common indicators {missing} absent")
    lab = tuple(str(y) for y in YEARS)

    state_rows, summary = [], []
    for inds, set_label in SETS:
        comp = {y: se_components(data[y][0], data[y][1], inds) for y in YEARS}
        flags = {y: {s: "; ".join(f) for s, f in
                     se_flags(data[y][0], data[y][1], inds).items()} for y in YEARS}
        se0 = {y: _states_with_se0(comp[y]) for y in YEARS}
        for rule in rules:
            role = "primary" if rule in primary else "sensitivity"
            is_primary = int(rule in primary and inds == COMMON)
            s = {y: sc.score(data[y][0], rule, indicators=inds, rescale=True) for y in YEARS}
            se = {y: score_se(data[y][0], data[y][1], rule, inds) for y in YEARS}
            cmp_ = compare(s[2022], se[2022], s[2023], se[2023], labels=lab,
                           notes=(flags[2022], flags[2023]))
            states.require_all(cmp_, 2023)
            for st in states.ALL:
                c = cmp_[st]
                state_rows.append({
                    "rule": rule, "rule_role": role, "indicator_set": set_label,
                    "primary": is_primary, "state": st, "ut": int(st in UTS),
                    "net_notified_2022": data[2022][2][st], "net_notified_2023": data[2023][2][st],
                    "s_2022": s[2022][st], "se_2022": se[2022][st],
                    "s_2023": s[2023][st], "se_2023": se[2023][st], **c})
            compared = [st for st in states.ALL if cmp_[st]["exceeds"] is not None]
            n_exc = sum(1 for st in compared if cmp_[st]["exceeds"])
            excluded = [f"{st} ({cmp_[st]['excluded_reason']})" for st in states.ALL
                        if cmp_[st]["exceeds"] is None]
            rho, lo, hi, rn = spearman_ci(
                {st: s[2022][st] for st in states.ALL},
                {st: cmp_[st]["change"] for st in states.ALL})
            summary.append({
                "rule": rule, "rule_role": role, "indicator_set": set_label,
                "primary": is_primary, "n_compared": len(compared), "n_exceeds": n_exc,
                "share": n_exc / len(compared) if compared else None,
                "excluded": "; ".join(excluded), "rho": rho, "rho_lo": lo, "rho_hi": hi,
                "rho_n": rn, "n_states_se0_2022": len(se0[2022]),
                "n_states_se0_2023": len(se0[2023]),
                "se0_states_2022": "; ".join(se0[2022]),
                "se0_states_2023": "; ".join(se0[2023])})

    _write(os.path.join(out_dir, "q4_2022_2023_states.csv"),
           ["rule", "rule_role", "indicator_set", "primary", "state", "ut",
            "net_notified_2022", "net_notified_2023", "s_2022", "se_2022", "s_2023",
            "se_2023", "change", "pct_change", "threshold", "exceeds", "excluded_reason"],
           state_rows)
    _write(os.path.join(out_dir, "q4_2022_2023_summary.csv"),
           ["rule", "rule_role", "indicator_set", "primary", "n_compared", "n_exceeds",
            "share", "excluded", "rho", "rho_lo", "rho_hi", "rho_n", "n_states_se0_2022",
            "n_states_se0_2023", "se0_states_2022", "se0_states_2023"], summary)

    print("Q4 change 2022 -> 2023, both re-scored (rescaled partial; plan 10.1 (b))")
    for r in summary:
        tag = " [PRIMARY]" if r["primary"] else ""
        ci = "no interval" if r["rho_lo"] is None else f"{r['rho_lo']:.3f} to {r['rho_hi']:.3f}"
        print(f"  {r['rule']} {{{r['indicator_set']}}}{tag}: exceeds noise "
              f"{r['n_exceeds']}/{r['n_compared']} = {r['share']:.3f}; "
              f"10.4 rho {r['rho']:.3f} ({ci}), n {r['rho_n']}; "
              f"se=0 states 2022 {r['n_states_se0_2022']}, 2023 {r['n_states_se0_2023']}")
        print(f"    excluded: {r['excluded'] or 'none'}")


if __name__ == "__main__":
    main()

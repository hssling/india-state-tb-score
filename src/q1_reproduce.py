"""Q1 reconstruction and rule selection (analysis plan 7.1-7.3).

Usage: python -I src/q1_reproduce.py <score_year>

Writes outputs/q1_<year>.csv (one row per state x rule) and
outputs/q1_<year>_selection.json (the select_rule result plus score_kind),
and prints the verdict and a per-rule summary.
"""
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import score as sc  # noqa: E402

TOL = 0.01   # plan 7.1: match / band tolerance, both bounds
EPS = 1e-9   # floating-point slack so that values exactly on a bound count as on it
R4_STATUS = "not evaluable: no bands documented"


def _key(x):
    """Ranking key for a float: equal to 9 decimals counts as tied."""
    return round(x, 9)


def _ranked(rules, primary, secondary):
    """Rules sorted by (primary, secondary); also the rules tied for first."""
    order = sorted(rules, key=lambda r: (_key(primary[r]), secondary[r], r))
    if not order:
        return order, []
    top = (_key(primary[order[0]]), secondary[order[0]])
    tied = [r for r in order if (_key(primary[r]), secondary[r]) == top]
    return order, tied


def select_rule(published, partial_by_rule, missing_points, missing_indicators=None):
    """Plan 7.1 (missing_points == 0) or 7.2 (missing_points > 0), then 7.3.

    published: state -> published score (None or absent = not available).
    partial_by_rule: rule -> {state: unrescaled partial score or None}, or
        rule -> str for a rule that is not evaluable (the str is its status).
    missing_points: sum of maximum points of the missing indicators.
    missing_indicators: the missing indicator numbers (required if
        missing_points > 0; their points must sum to missing_points).
    """
    partial_case = missing_points > 0
    if partial_case:
        if not missing_indicators:
            raise ValueError("missing_indicators required when missing_points > 0")
        if sum(sc.POINTS[i] for i in missing_indicators) != missing_points:
            raise ValueError("missing_indicators do not sum to missing_points")
    missing_indicators = sorted(missing_indicators or [])

    evaluated = [r for r, v in partial_by_rule.items() if not isinstance(v, str)]
    states = set(published)
    for r in evaluated:
        states |= set(partial_by_rule[r])
    # Exclusions (plan 7): not computable under any evaluated rule, or no published score.
    excluded = sorted(
        s for s in states
        if published.get(s) is None
        or any(partial_by_rule[r].get(s) is None for r in evaluated))
    compared = sorted(states - set(excluded))
    if not compared:
        raise ValueError("no computable state to compare")

    per_rule, per_state = {}, {s: {} for s in sorted(states)}
    for r, v in partial_by_rule.items():
        if isinstance(v, str):
            per_rule[r] = {"status": v}

    upper = missing_points + TOL
    for r in evaluated:
        for s in excluded:
            per_state[s][r] = {"published": published.get(s),
                               "partial": partial_by_rule[r].get(s),
                               "residual": None, "excluded": True}
        residuals = {s: published[s] - partial_by_rule[r][s] for s in compared}
        for s in compared:
            res = residuals[s]
            entry = {"published": published[s], "partial": partial_by_rule[r][s],
                     "residual": res, "excluded": False}
            if partial_case:
                in_band = -TOL - EPS <= res <= upper + EPS
                entry["in_band"] = in_band
                entry["violation"] = 0.0 if in_band else max(-TOL - res, res - upper)
            else:
                entry["match"] = abs(res) <= TOL + EPS
            per_state[s][r] = entry
        if partial_case:
            outside = {s: residuals[s] for s in compared
                       if not per_state[s][r]["in_band"]}
            per_rule[r] = {
                "n_compared": len(compared),
                "n_in_band": len(compared) - len(outside),
                "max_violation": max((per_state[s][r]["violation"] for s in compared),
                                     default=0.0),
                "outside": outside,
                "admissible": not outside,
            }
        else:
            mism = {s: residuals[s] for s in compared if not per_state[s][r]["match"]}
            per_rule[r] = {
                "n_compared": len(compared),
                "n_match": len(compared) - len(mism),
                "max_abs_error": max((abs(x) for x in residuals.values()), default=0.0),
                "mismatches": mism,
                "reproduces": not mism,
            }

    sensitivity = []
    if partial_case:
        admissible = [r for r in evaluated if per_rule[r]["admissible"]]
        ranking, tied = _ranked(evaluated,
                                {r: per_rule[r]["max_violation"] for r in evaluated},
                                {r: len(per_rule[r]["outside"]) for r in evaluated})
        if len(admissible) == 1:
            k = admissible[0]
            verdict = (f"consistent with rule {k}; not fully reproducible because "
                       f"indicator(s) {', '.join(map(str, missing_indicators))} "
                       f"are unpublished")
            rules = [k]
        elif len(admissible) > 1:
            verdict = "cannot discriminate"
            rules = list(admissible)
        else:
            verdict = "not reproducible"
            rules = tied
            sensitivity = [r for r in sc.RULES if r in evaluated]
    else:
        admissible = [r for r in evaluated if per_rule[r]["reproduces"]]
        err = {r: per_rule[r]["max_abs_error"] for r in evaluated}
        nmis = {r: len(per_rule[r]["mismatches"]) for r in evaluated}
        ranking, tied = _ranked(evaluated, err, nmis)
        if admissible:
            verdict = "reproduced"
            _, rules = _ranked(admissible, err, nmis)
        else:
            verdict = "not reproducible"
            rules = tied
    chosen = rules[0] if len(rules) == 1 else None

    return {
        "verdict": verdict,
        "admissible": admissible,
        "chosen": chosen,
        "rules_for_q2q4": rules,
        "sensitivity_rules": sensitivity,
        "ranking": ranking,
        "missing_points": missing_points,
        "missing_indicators": missing_indicators,
        "excluded": excluded,
        "per_rule": per_rule,
        "per_state": per_state,
    }


def _fmt(x):
    return "" if x is None else repr(x)


def main(argv):
    if len(argv) != 2:
        sys.exit("usage: python -I src/q1_reproduce.py <score_year>")
    year = int(argv[1])
    edition = f"itr{year + 1}"
    ext = os.path.join(ROOT, "data", "extracted")
    rows = [r for r in sc.load(os.path.join(ext, f"{edition}_indicators.csv"))
            if int(r["score_year"]) == year]
    pub_rows = [r for r in sc.load(os.path.join(ext, f"{edition}_scores.csv"))
                if int(r["score_year"]) == year]
    if not rows or not pub_rows:
        sys.exit(f"no rows for score year {year}")
    published = {r["state"]: (None if r["score"].strip() == "" else float(r["score"]))
                 for r in pub_rows}

    ach = sc.achievement(rows)
    available = sorted({i for a in ach.values() for i in a})
    missing = [i for i in range(1, 10) if i not in available]
    missing_points = sum(sc.POINTS[i] for i in missing)

    partial = {r: sc.score(ach, r) for r in sc.RULES}
    rescaled = {r: sc.score(ach, r, rescale=True) for r in sc.RULES}
    res = select_rule(published, {**partial, "R4": R4_STATUS}, missing_points,
                      missing_indicators=missing)
    res["score_year"] = year
    res["available_indicators"] = available
    res["score_kind"] = "rescaled partial" if missing else "full"

    out_dir = os.path.join(ROOT, "outputs")
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, f"q1_{year}.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["score_year", "state", "rule", "published", "partial",
                    "rescaled_partial", "residual", "in_band", "violation", "excluded"])
        for s in sorted(res["per_state"]):
            for r in sc.RULES:
                e = res["per_state"][s][r]
                in_band = e.get("in_band", e.get("match"))
                viol = e.get("violation")
                if not missing and e["residual"] is not None:
                    viol = max(0.0, abs(e["residual"]) - TOL) if not in_band else 0.0
                w.writerow([year, s, r, _fmt(e["published"]), _fmt(e["partial"]),
                            _fmt(rescaled[r].get(s)), _fmt(e["residual"]),
                            "" if in_band is None else int(in_band),
                            _fmt(viol), int(e["excluded"])])
    json_path = os.path.join(out_dir, f"q1_{year}_selection.json")
    with open(json_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, indent=2, sort_keys=True)

    print(f"Q1 {year} verdict: {res['verdict']}")
    print(f"missing indicators: {missing or 'none'} ({missing_points} points); "
          f"score kind: {res['score_kind']}")
    print(f"excluded (not computable): {', '.join(res['excluded']) or 'none'}")
    for r in sc.RULES:
        p = res["per_rule"][r]
        if missing:
            out = "; ".join(f"{s} {v:+.2f}" for s, v in sorted(p["outside"].items()))
            print(f"{r}: in band {p['n_in_band']}/{p['n_compared']}, "
                  f"max violation {p['max_violation']:.2f}; outside: {out or 'none'}")
        else:
            out = "; ".join(f"{s} {v:+.2f}" for s, v in sorted(p["mismatches"].items()))
            print(f"{r}: match {p['n_match']}/{p['n_compared']}, "
                  f"max abs error {p['max_abs_error']:.2f}; mismatches: {out or 'none'}")
    print(f"R4: {res['per_rule']['R4']['status']}")
    print(f"admissible: {res['admissible'] or 'none'}; chosen: {res['chosen']}; "
          f"rules for Q2-Q4: {res['rules_for_q2q4']}; "
          f"sensitivity: {res['sensitivity_rules'] or 'none'}")
    print(f"wrote {os.path.relpath(csv_path, ROOT)} and {os.path.relpath(json_path, ROOT)}")


if __name__ == "__main__":
    main(sys.argv)

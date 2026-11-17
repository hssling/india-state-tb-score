"""Task 9a: Q3 validity (analysis plan 9).

Usage: python -I src/q3_validity.py 2023

Primary (9.1): Spearman's rho between the 7.3 score (rescaled partial score
over the indicators available, under each rule of outputs/q1_<year>_
selection.json) and ICMR NTPS 2019-21 prevalence over the survey's
reporting units. A unit's score is the population-weighted mean of its
member states' scores (population: data/extracted/itr2024_population.csv,
plan 3); members without a score are excluded from the weighting and
listed; a unit with no scored member is dropped and listed. States the
survey does not cover (ntps_not_covered.csv) are listed and excluded.
Secondary (9.2): rho between the state-level 7.3 score and MDR/RR-TB
treatment success (success / cohort_n, annexure 4.13); a blank or zero
cohort is excluded and listed. The 9.2 score-year-2020 analysis is not
possible (plan 13, item 7).

Every interval: Fisher z with Fieller's variance, SE = sqrt(1.06/(n-3)),
tanh(atanh(rho) +/- 1.96 SE); none if n <= 3. No P values (plan 9.4).

Writes outputs/q3_<year>_units.csv, _summary.csv, _secondary_states.csv.
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
from src.q2_robust import spearman  # noqa: E402

Z975 = 1.96
FIELLER = 1.06
POPULATION_CSV = "itr2024_population.csv"  # plan 3: one population, 2024 edition


def fieller_se(n):
    """Fieller's standard error of atanh(Spearman's rho): sqrt(1.06/(n-3))."""
    return math.sqrt(FIELLER / (n - 3))


def fisher_ci(rho, n):
    """(lo, hi) 95% Fisher-z interval with Fieller's SE; (None, None) if n <= 3
    or rho is None. |rho| = 1 gives the degenerate interval (rho, rho)."""
    if rho is None or n <= 3:
        return None, None
    if abs(rho) >= 1.0:
        return rho, rho
    z, se = math.atanh(rho), fieller_se(n)
    return math.tanh(z - Z975 * se), math.tanh(z + Z975 * se)


def spearman_ci(x, y):
    """(rho, lo, hi, n) for Spearman's rho (average ranks, Pearson of ranks).

    x and y are either two dicts, paired by key (keys in both with non-None
    values), or two parallel lists of equal length (pairs with a None are
    dropped). n is the number of pairs used. rho is None if n < 2 or one
    side has no spread; lo and hi are None if n <= 3.
    """
    if isinstance(x, dict) and isinstance(y, dict):
        a, b = x, y
    elif isinstance(x, dict) or isinstance(y, dict):
        raise ValueError("pass two dicts or two parallel lists")
    else:
        if len(x) != len(y):
            raise ValueError(f"parallel lists differ in length: {len(x)} vs {len(y)}")
        a, b = dict(enumerate(x)), dict(enumerate(y))
    n = sum(1 for k, v in a.items() if v is not None and b.get(k) is not None)
    rho = spearman(a, b)
    lo, hi = fisher_ci(rho, n)
    return rho, lo, hi, n


def unit_scores(units, scores, population):
    """Per unit: {"unit", "scored", "excluded", "score"}.

    units: [{"unit": name, "members": [state, ...]}]. A member is scored if
    scores.get(member) is not None; its weight is population[member]
    (ValueError if missing or not positive). score is the population-
    weighted mean over the scored members, or None (unit dropped) if none.
    """
    out = []
    for u in units:
        scored = [m for m in u["members"] if scores.get(m) is not None]
        excluded = [m for m in u["members"] if scores.get(m) is None]
        for m in scored:
            if not population.get(m) or population[m] <= 0:
                raise ValueError(f"{u['unit']}: no population for scored member {m}")
        if scored:
            w = sum(population[m] for m in scored)
            s = sum(population[m] * scores[m] for m in scored) / w
        else:
            s = None
        out.append({"unit": u["unit"], "scored": scored, "excluded": excluded, "score": s})
    return out


# ---- run -------------------------------------------------------------------

def _cell(v):
    return "" if v is None else repr(v) if isinstance(v, float) else str(v)


def _write(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        for r in rows:
            w.writerow([_cell(r[h]) for h in header])


def load_inputs(ext):
    units = [{"unit": r["unit"], "unit_type": r["unit_type"],
              "members": r["member_states"].split(";"),
              "prevalence": float(r["prevalence"]),
              "ci_low": float(r["ci_low"]), "ci_high": float(r["ci_high"])}
             for r in sc.load(os.path.join(ext, "ntps_units.csv"))]
    not_covered = [r["state"] for r in sc.load(os.path.join(ext, "ntps_not_covered.csv"))]
    members = [m for u in units for m in u["members"]]
    if len(members) != len(set(members)):
        raise ValueError("a state belongs to two survey units")
    states.require_all(members + not_covered, 2023)  # every unit accounted for once
    if set(members) & set(not_covered):
        raise ValueError("a not-covered state is also a unit member")
    pop = {r["state"]: float(r["population"])
           for r in sc.load(os.path.join(ext, POPULATION_CSV)) if r["state"] != "INDIA"}
    states.require_all(pop, 2023)
    return units, not_covered, pop


def secondary_rows(state_scores, drtb):
    """State rows for 9.2: success / cohort_n, excluded if blank or zero."""
    rows = []
    for s in states.ALL:
        r = drtb[s]
        n, suc = sc._num(r["cohort_n"]), sc._num(r["success"])
        sco = state_scores.get(s)
        if not n or suc is None:
            why = "cohort blank or zero"
        elif sco is None:
            why = "no score"
        else:
            why = ""
        rows.append({"state": s, "score": sco, "cohort_n": r["cohort_n"],
                     "success": r["success"],
                     "success_rate": suc / n if n and suc is not None else None,
                     "included": 0 if why else 1, "excluded_reason": why})
    return rows


def main(argv):
    if len(argv) != 2:
        sys.exit("usage: python -I src/q3_validity.py <score_year>")
    year = int(argv[1])
    if year != 2023:
        sys.exit("Q3 is run for score year 2023 only (plan 9.1; 9.2 with 2020 is "
                 "not possible, plan 13 item 7)")
    edition = f"itr{year + 1}"
    ext = os.path.join(ROOT, "data", "extracted")
    out_dir = os.path.join(ROOT, "outputs")
    with open(os.path.join(out_dir, f"q1_{year}_selection.json"), encoding="utf-8") as f:
        sel = json.load(f)
    if sel["score_kind"] != "rescaled partial":
        sys.exit(f"7.3 score kind {sel['score_kind']!r} is not implemented here")
    primary = list(sel["rules_for_q2q4"])
    rules = list(dict.fromkeys(primary + list(sel["sensitivity_rules"])))
    inds = list(sel["available_indicators"])

    rows = [r for r in sc.load(os.path.join(ext, f"{edition}_indicators.csv"))
            if int(r["score_year"]) == year]
    ach = sc.achievement(rows)
    units, not_covered, pop = load_inputs(ext)
    drtb = {r["state"]: r for r in sc.load(os.path.join(ext, f"{edition}_drtb_outcomes.csv"))}
    states.require_all(drtb, year)

    unit_out, summary, sec_out = [], [], []
    for rule in rules:
        role = "primary" if rule in primary else "sensitivity"
        st = sc.score(ach, rule, indicators=inds, rescale=True)
        us = unit_scores(units, st, pop)
        for u, res in zip(units, us):
            unit_out.append({
                "rule": rule, "role": role, "unit": u["unit"], "unit_type": u["unit_type"],
                "members_scored": ";".join(res["scored"]),
                "members_excluded": ";".join(res["excluded"]),
                "unit_score": res["score"], "dropped": int(res["score"] is None),
                "prevalence": u["prevalence"], "ci_low": u["ci_low"], "ci_high": u["ci_high"]})
        x = {r["unit"]: r["score"] for r in us}
        y = {u["unit"]: u["prevalence"] for u in units}
        rho, lo, hi, n = spearman_ci(x, y)
        no_score = [m for r in us for m in r["excluded"]]
        dropped = [r["unit"] for r in us if r["score"] is None]
        excl = [f"not covered by the survey: {', '.join(not_covered)}"]
        if no_score:
            excl.append(f"member without score: {', '.join(no_score)}")
        if dropped:
            excl.append(f"unit dropped (no scored member): {', '.join(dropped)}")
        summary.append({"rule": rule, "role": role, "analysis": "9.1 primary",
                        "measure": "NTPS prevalence (unit)", "rho": rho, "lo": lo, "hi": hi,
                        "n": n, "expected_direction": "negative", "excluded": "; ".join(excl)})

        sec = secondary_rows(st, drtb)
        sec_out += [{"rule": rule, "role": role, **r} for r in sec]
        rho, lo, hi, n = spearman_ci(
            {r["state"]: r["score"] for r in sec if r["included"]},
            {r["state"]: r["success_rate"] for r in sec if r["included"]})
        excl = [f"{r['excluded_reason']}: {r['state']}" for r in sec if not r["included"]]
        summary.append({"rule": rule, "role": role, "analysis": "9.2 secondary",
                        "measure": "MDR/RR-TB treatment success (state)", "rho": rho,
                        "lo": lo, "hi": hi, "n": n, "expected_direction": "not pre-specified",
                        "excluded": "; ".join(excl)})

    _write(os.path.join(out_dir, f"q3_{year}_units.csv"),
           ["rule", "role", "unit", "unit_type", "members_scored", "members_excluded",
            "unit_score", "dropped", "prevalence", "ci_low", "ci_high"], unit_out)
    _write(os.path.join(out_dir, f"q3_{year}_summary.csv"),
           ["rule", "role", "analysis", "measure", "rho", "lo", "hi", "n",
            "expected_direction", "excluded"], summary)
    _write(os.path.join(out_dir, f"q3_{year}_secondary_states.csv"),
           ["rule", "role", "state", "score", "cohort_n", "success", "success_rate",
            "included", "excluded_reason"], sec_out)

    print(f"Q3 validity, score year {year} (rescaled partial over indicators {inds})")
    for r in summary:
        ci = "no interval" if r["lo"] is None else f"{r['lo']:.3f} to {r['hi']:.3f}"
        rho = "NA" if r["rho"] is None else f"{r['rho']:.3f}"
        print(f"  {r['rule']} ({r['role']}) {r['analysis']}: rho {rho} ({ci}), n {r['n']}")
        print(f"    excluded: {r['excluded']}")


if __name__ == "__main__":
    main(sys.argv)

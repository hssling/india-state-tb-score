"""Task 7: Q2 robustness (analysis plan 8).

Usage: python -I src/q2_robust.py <score_year>

Reads outputs/q1_<year>_selection.json for the rules; writes
outputs/q2_<year>_summary.csv, _fifths.csv and _saturation.csv.
Ranks: 1 = highest score, ties average. Alt rankings are compared with the
base on the states present in both, each ranking re-ranked within that set.
"""
import csv
import json
import math
import os
import random
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import score as sc  # noqa: E402

SEED = 20261117
N_DRAWS = 10000
SETTINGS = (("c63", 63.0), ("alpha1", None))
SAT_LEVEL = 0.95
VARIANT3_NOTE = ("variant 3 dropped: 5.3 AGREE (annexure 1.2 'expected' equals "
                 "CTD's target within 0.1%)")


def dirichlet_weights(c, n, seed, indicators=None):
    """n draws of {indicator: points}, points summing to 100 (plan 8.1).

    alpha_i = c * w_i (w_i = CTD points rescaled to sum 1 over `indicators`),
    or 1 for every indicator when c is None. Fresh Random(seed) per call.
    """
    inds = list(range(1, 10)) if indicators is None else list(indicators)
    tot = sum(sc.POINTS[i] for i in inds)
    alpha = {i: (1.0 if c is None else c * sc.POINTS[i] / tot) for i in inds}
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        g = {i: rng.gammavariate(alpha[i], 1.0) for i in inds}
        s = sum(g.values())
        out.append({i: 100.0 * g[i] / s for i in inds})
    return out


def _fmatrix(ach, rule, inds):
    """state -> [f_rule(a_i) for i in inds], or None if any a_i is missing."""
    best = {}
    if rule == "R3":
        for i in inds:
            vals = [a[i] for a in ach.values() if a.get(i) is not None]
            best[i] = max(vals) if vals else None
    elif rule not in ("R1", "R2"):
        raise ValueError(f"unknown rule {rule!r}")
    out = {}
    for s, a in ach.items():
        row = []
        for i in inds:
            v = a.get(i)
            if v is None:
                row = None
                break
            if rule == "R1":
                row.append(min(v, 1.0))
            elif rule == "R2":
                row.append(v)
            else:
                row.append(v / best[i] if best[i] else 0.0)
        out[s] = row
    return out


def draw_scores(ach, rule, indicators, weights):
    """state -> sum_i weights[i] * f_rule(a_i) (weights sum to 100), or None."""
    inds = list(indicators)
    w = [weights[i] for i in inds]
    return {s: (None if r is None else sum(x * y for x, y in zip(w, r)))
            for s, r in _fmatrix(ach, rule, inds).items()}


def average_ranks(scores):
    """1 = highest; ties get the average of the ranks they span."""
    items = sorted(((s, v) for s, v in scores.items() if v is not None),
                   key=lambda kv: -kv[1])
    ranks, i = {}, 0
    while i < len(items):
        j = i
        while j + 1 < len(items) and items[j + 1][1] == items[i][1]:
            j += 1
        for k in range(i, j + 1):
            ranks[items[k][0]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def _common_ranks(a, b):
    common = ({s for s, v in a.items() if v is not None}
              & {s for s, v in b.items() if v is not None})
    return (average_ranks({s: a[s] for s in common}),
            average_ranks({s: b[s] for s in common}))


def _pearson(x, y):
    mx, my = sum(x) / len(x), sum(y) / len(y)
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    if sxx == 0 or syy == 0:
        return None
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(sxx * syy)


def spearman(a, b):
    """Pearson on average ranks over the states in both score dicts."""
    ra, rb = _common_ranks(a, b)
    keys = sorted(ra)
    if len(keys) < 2:
        return None
    return _pearson([ra[k] for k in keys], [rb[k] for k in keys])


def rank_shift(base, alt):
    """Absolute rank change of alt vs base score dicts, on common states."""
    rb, ra = _common_ranks(base, alt)
    d = {s: ra[s] - rb[s] for s in rb}
    ab = [abs(v) for v in d.values()]
    return {"n": len(d), "change": d,
            "median_abs": statistics.median(ab) if ab else None,
            "max_abs": max(ab) if ab else None}


def fifth_size(n):
    return n // 5


def saturation_table(ach):
    """indicator -> (share of computable states with a >= 0.95, saturated)."""
    out = {}
    for i in sorted({i for a in ach.values() for i in a}):
        vals = [a[i] for a in ach.values() if a.get(i) is not None]
        if not vals:
            continue
        k = sum(1 for v in vals if v >= SAT_LEVEL)
        out[i] = (k / len(vals), 5 * k >= 4 * len(vals))  # integer test: exact 80%
    return out


def saturated(ach):
    """Indicators with >= 80% of computable states at a >= 0.95 (inclusive)."""
    return [i for i, (_, flag) in saturation_table(ach).items() if flag]


def leave_one_out(ach, rule, indicators):
    """{dropped indicator: rescaled score dict without it}."""
    inds = list(indicators)
    return {d: sc.score(ach, rule, indicators=[i for i in inds if i != d],
                        rescale=True) for d in inds}


def _quartiles(x):
    q = statistics.quantiles(x, n=4, method="inclusive")
    return q[0], statistics.median(x), q[2]


def _tails(x):
    q = statistics.quantiles(x, n=40, method="inclusive")
    return q[0], statistics.median(x), q[-1]


def _cell(x):
    if x is None:
        return ""
    return x if isinstance(x, (str, int)) else repr(float(x))


def main(argv):
    if len(argv) != 2:
        sys.exit("usage: python -I src/q2_robust.py <score_year>")
    year = int(argv[1])
    edition = f"itr{year + 1}"
    ext = os.path.join(ROOT, "data", "extracted")
    out_dir = os.path.join(ROOT, "outputs")
    with open(os.path.join(out_dir, f"q1_{year}_selection.json"), encoding="utf-8") as f:
        sel = json.load(f)
    with open(os.path.join(out_dir, "q1_target_check.txt"), encoding="utf-8") as f:
        text = f.read().upper()
    if "AGREE" not in text.replace("DISAGREE", ""):
        sys.exit("5.3 is not AGREE: variant 3 is required but not implemented")
    primary = list(sel["rules_for_q2q4"])
    rules = list(dict.fromkeys(primary + list(sel["sensitivity_rules"])))
    inds = list(sel["available_indicators"])

    rows = [r for r in sc.load(os.path.join(ext, f"{edition}_indicators.csv"))
            if int(r["score_year"]) == year]
    ach = sc.achievement(rows)
    pub = {r["state"]: float(r["score"])
           for r in sc.load(os.path.join(ext, f"{edition}_scores.csv"))
           if int(r["score_year"]) == year and r["score"].strip() != ""}

    # variant 4: indicator 4 with the matched-cohort denominator (plan 8.1)
    cohort = {r["state"]: (sc._num(r["success"]), sc._num(r["cohort_notified"]))
              for r in sc.load(os.path.join(ext, f"{edition}_tsr_cohort.csv"))}
    ach4 = {s: dict(a) for s, a in ach.items()}
    for s in ach4:
        suc, den = cohort.get(s, (None, None))
        ach4[s][4] = None if suc is None or not den else suc / den

    sat = saturation_table(ach)
    sat_inds = [i for i in inds if sat[i][1]]
    with open(os.path.join(out_dir, f"q2_{year}_saturation.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["indicator", "n_computable", "share_ge_0.95", "saturated"])
        for i in inds:
            n = sum(1 for a in ach.values() if a.get(i) is not None)
            w.writerow([i, n, repr(sat[i][0]), int(sat[i][1])])

    cols = ["rule", "role", "variant", "setting", "n_compared", "note",
            "median_change", "median_change_q1", "median_change_q3",
            "max_change", "max_change_q1", "max_change_q3",
            "spearman", "spearman_p2.5", "spearman_p97.5"]
    summary, fifths = [], []
    for rule in rules:
        role = "primary" if rule in primary else "sensitivity"
        base = sc.score(ach, rule, indicators=inds, rescale=True)

        def det(variant, alt, note=""):
            sh = rank_shift(base, alt)
            summary.append({"rule": rule, "role": role, "variant": variant,
                            "n_compared": sh["n"], "note": note,
                            "median_change": sh["median_abs"],
                            "max_change": sh["max_abs"],
                            "spearman": spearman(alt, pub)})

        det("base", base)
        for d, alt in leave_one_out(ach, rule, inds).items():
            det(f"2_loo_drop_{d}", alt)
        summary.append({"rule": rule, "role": role, "variant": "3_burden",
                        "note": VARIANT3_NOTE})
        det("4_matched_cohort", sc.score(ach4, rule, indicators=inds, rescale=True))
        if sat_inds:
            keep = [i for i in inds if i not in sat_inds]
            det("5_saturated_removed",
                sc.score(ach, rule, indicators=keep, rescale=True),
                "removed " + ",".join(map(str, sat_inds)))
        else:
            summary.append({"rule": rule, "role": role,
                            "variant": "5_saturated_removed", "note": "empty"})

        # variant 1: weight perturbation, on the base-computable states
        fm = _fmatrix(ach, rule, inds)
        states = sorted(s for s, v in base.items() if v is not None)
        n = len(states)
        rb = average_ranks(base)
        k = fifth_size(n)
        order = sorted(states, key=lambda s: (rb[s], s))
        top_set = set(order[:k])
        bot_set = set(order[n - k:]) if k else set()
        pk = [s for s in states if s in pub]
        pub_r = average_ranks({s: pub[s] for s in pk})
        pubv = [pub_r[s] for s in pk]
        for sname, c in SETTINGS:
            ws = dirichlet_weights(c, N_DRAWS, SEED, indicators=inds)
            med, mx, rho = [], [], []
            top_ct = dict.fromkeys(states, 0)
            bot_ct = dict.fromkeys(states, 0)
            for wd in ws:
                wv = [wd[i] for i in inds]
                sco = {s: sum(x * y for x, y in zip(wv, fm[s])) for s in states}
                rd = average_ranks(sco)
                ab = [abs(rd[s] - rb[s]) for s in states]
                med.append(statistics.median(ab))
                mx.append(max(ab))
                rp = average_ranks({s: sco[s] for s in pk})
                rho.append(_pearson([rp[s] for s in pk], pubv))
                for s in states:
                    if rd[s] <= k:
                        top_ct[s] += 1
                    if rd[s] > n - k:
                        bot_ct[s] += 1
            a1, a2, a3 = _quartiles(med)
            b1, b2, b3 = _quartiles(mx)
            r1, r2, r3 = _tails([x for x in rho if x is not None])
            summary.append({"rule": rule, "role": role, "variant": "1_weights",
                            "setting": sname, "n_compared": n,
                            "note": f"{N_DRAWS} draws; seed {SEED}",
                            "median_change": a2, "median_change_q1": a1,
                            "median_change_q3": a3, "max_change": b2,
                            "max_change_q1": b1, "max_change_q3": b3,
                            "spearman": r2, "spearman_p2.5": r1,
                            "spearman_p97.5": r3})
            for s in states:
                fifths.append({"state": s, "rule": rule, "setting": sname,
                               "base_fifth": ("top" if s in top_set else
                                              "bottom" if s in bot_set else "middle"),
                               "share_top_fifth": top_ct[s] / N_DRAWS,
                               "share_bottom_fifth": bot_ct[s] / N_DRAWS})

    with open(os.path.join(out_dir, f"q2_{year}_summary.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in summary:
            w.writerow([_cell(r.get(c)) for c in cols])
    fcols = ["state", "rule", "setting", "base_fifth", "share_top_fifth",
             "share_bottom_fifth"]
    with open(os.path.join(out_dir, f"q2_{year}_fifths.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(fcols)
        for r in fifths:
            w.writerow([_cell(r[c]) for c in fcols])

    print(f"Q2 score year {year}; indicators {inds}; rules {rules} "
          f"(primary {primary}); score kind: {sel['score_kind']}")
    print(VARIANT3_NOTE)
    print("saturated indicators:", sat_inds or "empty")

    def g(r, k):
        v = r.get(k)
        return "-" if v in (None, "") else f"{float(v):.2f}"

    for r in summary:
        if r["variant"] == "3_burden":
            continue
        if r["variant"] == "5_saturated_removed" and r.get("note") == "empty":
            print(f"{r['rule']} {r['variant']:<22}empty")
            continue
        print(f"{r['rule']} {r['variant']:<22}{r.get('setting', ''):<7}"
              f"medchg {g(r, 'median_change')} maxchg {g(r, 'max_change')} "
              f"rho {g(r, 'spearman')}")


if __name__ == "__main__":
    main(sys.argv)

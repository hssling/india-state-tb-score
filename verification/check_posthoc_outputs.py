"""Recompute the point values of the post hoc analyses (plan section 13, 20 November 2026)
with code of this file only (standard library; nothing of src/ is imported).

Run as: python -I verification/check_posthoc_outputs.py

Tolerance 1e-9 (relative 1e-9 for values above 1). What is recomputed:

(a) every row of outputs/posthoc_summary.csv and outputs/posthoc_q4_states.csv carries
    label = "post hoc";
(b) Q4 (rules R2 and R1, indicators 1, 2, 3, 4 and 6), from the registered output
    outputs/q4_2022_2023_states.csv (itself reproduced byte for byte by check_all): the
    number of states compared and exceeding noise; the inverse-variance-weighted mean change;
    the multiplicative overdispersion factor phi (mean squared z-score, z winsorised at its
    inclusive 10th and 90th percentiles); the DerSimonian-Laird tau^2; the counts outside
    the 95% (z 1.96) and 99.8% (z 3.09) limits under each; the Bonferroni threshold and
    count; the Benjamini-Hochberg count; the expected false positives (0.05 k); and the
    per-state flags of outputs/posthoc_q4_states.csv;
(c) the Wilson sensitivity, from data/extracted/itr2023_indicators.csv and
    itr2024_indicators.csv: each state's score SE rebuilt from its numerators and
    denominators (Poisson for indicator 1; binomial otherwise, indicator 3 on the proportion
    tested of net notified, divided by 0.7; points x 100/70), with a zero binomial SE at a
    proportion of 0 or 1 replaced by the Wilson SE; then the counts of (b) and the number of
    states whose category changes;
(d) Oldham's point values (Pearson r and Spearman rho of the change with the two-year mean)
    for both indicator sets and both rules, and n;
(e) Q3: Spearman's rho of the unit score with the survey prevalence (outputs/q3_2023_units.csv)
    and the half-width tanh(1.96 sqrt(1.06 / (n - 3))).

NOT re-derived here: the bootstrap intervals (Oldham) and the bootstrap and lognormal
percentiles (Q3). They are reproduced by the seeded build (src/posthoc.py, seed 20261120)
and checked byte for byte by check_all; this check reads them as printed and checks only
that each interval is ordered.
"""
import csv
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOL = 1e-9
RULES = ("R2", "R1")
SETS = ("1,2,3,4,6", "2,3,4,6 (indicator 1 excluded)")
INDS = (1, 2, 3, 4, 6)
POINTS = {1: 20, 2: 10, 3: 10, 4: 15, 6: 15}
BENCH = 0.7
Z = 1.96


def read(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def close(a: float, b: float) -> bool:
    return abs(a - b) <= TOL * max(1.0, abs(a), abs(b))


# ------------------------------------------------------------------ statistics

def pearson(x, y):
    mx, my = sum(x) / len(x), sum(y) / len(y)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    return sxy / math.sqrt(sxx * syy)


def ranks(x):
    order = sorted(range(len(x)), key=lambda i: x[i])
    r = [0.0] * len(x)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and x[order[j + 1]] == x[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(x, y):
    return pearson(ranks(x), ranks(y))


def noise_stats(d, se):
    w = [1 / s ** 2 for s in se]
    m = sum(a * b for a, b in zip(w, d)) / sum(w)
    z = [(a - m) / s for a, s in zip(d, se)]
    q = statistics.quantiles(z, n=10, method="inclusive")
    zw = [min(max(v, q[0]), q[-1]) for v in z]
    phi = sum(v * v for v in zw) / len(z)
    qstat = sum(a * (b - m) ** 2 for a, b in zip(w, d))
    tau2 = max(0.0, (qstat - (len(d) - 1)) / (sum(w) - sum(a * a for a in w) / sum(w)))
    k = math.sqrt(phi) if phi > 1 else 1.0
    flags = [(abs(a - m) > 1.96 * k * s, abs(a - m) > 3.09 * k * s,
              abs(a - m) > 1.96 * math.sqrt(s * s + tau2),
              abs(a - m) > 3.09 * math.sqrt(s * s + tau2)) for a, s in zip(d, se)]
    return m, phi, tau2, flags


# ------------------------------------------------------------------ Wilson rebuild

def wilson(p, n):
    return math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / (1 + Z * Z / n)


def state_se(rows, wilson_at_bounds):
    """state -> score SE (indicators 1, 2, 3, 4, 6, rescaled), None if a binomial
    proportion exceeds 1; and state -> number of components replaced by the Wilson SE."""
    by = {}
    for r in rows:
        if int(r["indicator"]) in INDS:
            by.setdefault(r["state"], {})[int(r["indicator"])] = (
                float(r["numerator"]), float(r["denominator"]))
    f = 100.0 / sum(POINTS.values())
    out, repl = {}, {}
    for s, v in by.items():
        tot, bad = 0.0, False
        for i in INDS:
            num, den = v[i]
            if i == 1:
                se = math.sqrt(num) / den
            else:
                p = num / den
                if p > 1:
                    bad = True
                    break
                se = math.sqrt(p * (1 - p) / den)
                if wilson_at_bounds and p in (0.0, 1.0):
                    se = wilson(p, den)
                    repl[s] = repl.get(s, 0) + 1
                if i == 3:
                    se /= BENCH
            tot += (POINTS[i] * f) ** 2 * se ** 2
        out[s] = None if bad else math.sqrt(tot)
    return out, repl


# ------------------------------------------------------------------ checks

def problems(root: Path = ROOT) -> list[str]:
    out: list[str] = []
    summ = read(root / "outputs" / "posthoc_summary.csv")
    st_rows = read(root / "outputs" / "posthoc_q4_states.csv")
    for name, rows in (("posthoc_summary.csv", summ), ("posthoc_q4_states.csv", st_rows)):
        if any(r["label"] != "post hoc" for r in rows):
            out.append(f"{name}: a row is not labelled 'post hoc'")

    def get(analysis, rule, variant, quantity, iset=SETS[0]):
        hit = [r for r in summ if (r["analysis"], r["rule"], r["se_variant"], r["quantity"])
               == (analysis, rule, variant, quantity) and r["indicator_set"] in (iset, "")]
        if len(hit) != 1:
            raise KeyError((analysis, rule, variant, quantity, iset))
        return hit[0]

    def cmp(label, printed, value):
        if not close(float(printed), float(value)):
            out.append(f"{label}: printed {printed}, recomputed {value!r}")

    reg = read(root / "outputs" / "q4_2022_2023_states.csv")
    ext = root / "data" / "extracted"
    y22 = [r for r in read(ext / "itr2023_indicators.csv") if r["score_year"] == "2022"]
    y23 = [r for r in read(ext / "itr2024_indicators.csv") if r["score_year"] == "2023"]
    base_se = (state_se(y22, False)[0], state_se(y23, False)[0])
    wil = (state_se(y22, True), state_se(y23, True))

    for rule in RULES:
        rows = [r for r in reg if r["rule"] == rule and r["indicator_set"] == SETS[0]]
        comp = [r for r in rows if r["exceeds"] != ""]
        names = [r["state"] for r in comp]
        d = [float(r["change"]) for r in comp]
        se = [math.sqrt(float(r["se_2022"]) ** 2 + float(r["se_2023"]) ** 2) for r in comp]
        k = len(comp)
        # the independent SE rebuild must equal the registered SEs
        for r in comp:
            for y, b in (("2022", base_se[0]), ("2023", base_se[1])):
                if not close(b[r["state"]], float(r[f"se_{y}"])):
                    out.append(f"{rule} {r['state']} se_{y}: rebuilt {b[r['state']]!r}, "
                               f"registered {r[f'se_{y}']}")
        exc = [abs(a) > 1.96 * s for a, s in zip(d, se)]
        if exc != [r["exceeds"] == "1" for r in comp]:
            out.append(f"{rule}: registered verdicts not reproduced")
        m, phi, tau2, flags = noise_stats(d, se)
        a, v = "Q4 noise", "binomial"
        cmp(f"{rule} n_compared", get(a, rule, v, "n_compared")["value"], k)
        cmp(f"{rule} n_exceeds", get(a, rule, v, "n_exceeds_registered")["value"], sum(exc))
        cmp(f"{rule} ivw mean", get(a, rule, v, "ivw_mean_change")["value"], m)
        cmp(f"{rule} phi", get(a, rule, v, "phi")["value"], phi)
        cmp(f"{rule} tau2", get(a, rule, v, "tau2")["value"], tau2)
        keys = ("n_outside95_mult", "n_outside998_mult", "n_outside95_add", "n_outside998_add")
        for j, q in enumerate(keys):
            cmp(f"{rule} {q}", get(a, rule, v, q)["value"], sum(f[j] for f in flags))
        zb = statistics.NormalDist().inv_cdf(1 - 0.05 / (2 * k))
        zs = [abs(a_) / s for a_, s in zip(d, se)]
        p = sorted(math.erfc(x / math.sqrt(2)) for x in zs)
        n_bh = max([j for j in range(1, k + 1) if p[j - 1] <= 0.05 * j / k], default=0)
        a2 = "Q4 multiplicity"
        cmp(f"{rule} z_bonferroni", get(a2, rule, v, "z_bonferroni")["value"], zb)
        cmp(f"{rule} n_bonferroni", get(a2, rule, v, "n_exceeds_bonferroni")["value"],
            sum(x > zb for x in zs))
        cmp(f"{rule} n_bh", get(a2, rule, v, "n_exceeds_bh")["value"], n_bh)
        cmp(f"{rule} expected FP", get(a2, rule, v, "expected_false_positives")["value"], 0.05 * k)
        prs = {r["state"]: r for r in st_rows if r["rule"] == rule and r["se_variant"] == v}
        cols = ("outside95_mult", "outside998_mult", "outside95_add", "outside998_add")
        for s, fl in zip(names, flags):
            if tuple(prs[s][c] == "1" for c in cols) != fl:
                out.append(f"{rule} {s}: per-state funnel flags differ")
            if (prs[s]["exceeds_bonferroni"] == "1") != (abs(float(prs[s]["change"])) /
                                                        float(prs[s]["se_change"]) > zb):
                out.append(f"{rule} {s}: per-state Bonferroni flag differs")

        # (c) Wilson
        sew = [math.sqrt(wil[0][0][s] ** 2 + wil[1][0][s] ** 2) for s in names]
        excw = [abs(a_) / s > 1.96 for a_, s in zip(d, sew)]
        mw, phiw, tau2w, flw = noise_stats(d, sew)
        v = "wilson"
        cmp(f"{rule} wilson phi", get(a, rule, v, "phi")["value"], phiw)
        cmp(f"{rule} wilson tau2", get(a, rule, v, "tau2")["value"], tau2w)
        cmp(f"{rule} wilson n_exceeds", get(a, rule, v, "n_exceeds_registered")["value"], sum(excw))
        for j, q in enumerate(keys):
            cmp(f"{rule} wilson {q}", get(a, rule, v, q)["value"], sum(f[j] for f in flw))
        repl = set(wil[0][1]) | set(wil[1][1])
        cmp(f"{rule} n_states_wilson", get(a, rule, v, "n_states_wilson")["value"], len(repl))
        before = [(e,) + f for e, f in zip(exc, flags)]
        after = [(e,) + f for e, f in zip(excw, flw)]
        for j, q in enumerate(("registered",) + tuple(c for c in cols)):
            cmp(f"{rule} n_changed_{q}", get(a, rule, v, f"n_changed_{q}")["value"],
                sum(b[j] != c[j] for b, c in zip(before, after)))

        # (d) Oldham
        for iset in SETS:
            rs = [r for r in reg if r["rule"] == rule and r["indicator_set"] == iset
                  and r["s_2022"] and r["s_2023"]]
            ch = [float(r["s_2023"]) - float(r["s_2022"]) for r in rs]
            mean = [(float(r["s_2023"]) + float(r["s_2022"])) / 2 for r in rs]
            for q, val in (("oldham_r", pearson(ch, mean)), ("oldham_rho", spearman(ch, mean))):
                row = get("Q4 regression to the mean", rule, "binomial", q, iset)
                cmp(f"{rule} {iset} {q}", row["value"], val)
                cmp(f"{rule} {iset} {q} n", row["n"], len(rs))
                if not float(row["lo"]) <= float(row["hi"]):
                    out.append(f"{rule} {iset} {q}: interval not ordered")

    # (e) Q3
    units = read(root / "outputs" / "q3_2023_units.csv")
    for rule in RULES:
        us = [u for u in units if u["rule"] == rule and u["dropped"] == "0"]
        n = len(us)
        a = "Q3 prevalence uncertainty"
        cmp(f"{rule} Q3 rho", get(a, rule, "", "rho_point")["value"],
            spearman([float(u["unit_score"]) for u in us], [float(u["prevalence"]) for u in us]))
        cmp(f"{rule} Q3 half-width", get(a, rule, "", "rho_half_width_at_0")["value"],
            math.tanh(1.96 * math.sqrt(1.06 / (n - 3))))
        for q in ("rho_bootstrap", "rho_prevalence_only"):
            row = get(a, rule, "", q)
            cmp(f"{rule} {q} n", row["n"], n)
            if not float(row["lo"]) <= float(row["value"]) <= float(row["hi"]):
                out.append(f"{rule} {q}: median outside its percentiles")
    return out


def main() -> int:
    bad = problems()
    for b in bad:
        print(f"FAIL: {b}")
    if bad:
        return 1
    print("OK: post hoc point values recomputed (Q4 funnel, multiplicity, Wilson, Oldham; "
          "Q3 rho and precision); bootstrap intervals read as printed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

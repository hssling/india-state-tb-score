"""POST HOC (not pre-specified): four analyses added after peer review of the manuscript.

Usage: python -I src/posthoc.py

Logged as a dated entry in plan section 13 (20 November 2026). They were requested by two
referees and approved by the author after the registered analyses, the exploratory analysis
and the manuscript were complete. None of them replaces a registered result; each is
reported beside the result it qualifies. Every output row has label = "post hoc".

Rules: R2 (the registered primary rule of Q2-Q4, outputs/q1_2023_selection.json) and R1
beside it. Seed SEED = 20261120 (the plan's own seed belongs to the registered analyses),
reset with a new random.Random(SEED) before each analysis, rule and indicator set, so every
bootstrap starts from the same sequence.

1. Q4, overdispersion-adjusted noise (funnel). Over the states compared by the registered
   test (indicators 1, 2, 3, 4 and 6, rescaled), each state's change d_s = s_2023 - s_2022
   with SE_s = sqrt(SE_2022^2 + SE_2023^2) (plan 10.2) is compared with the
   inverse-variance-weighted mean change m = sum(w d) / sum(w), w = 1 / SE^2.
   (a) Multiplicative (Spiegelhalter 2005, Stat Med 24:1185): z_s = (d_s - m) / SE_s;
       the z-scores are winsorised at their 10th and 90th percentiles
       (statistics.quantiles(n=10, method="inclusive")); phi = mean of the squared
       winsorised z. Limits m +/- z sqrt(phi) SE_s if phi > 1, else m +/- z SE_s.
   (b) Additive: DerSimonian-Laird tau^2 = max(0, (Q - (k - 1)) / (sum w - sum w^2 / sum w)),
       Q = sum w (d - m)^2. Limits m +/- z sqrt(SE_s^2 + tau^2).
   A state is outside if |d_s - m| > the half-width, at z = 1.96 (95%) and z = 3.09
   (99.8%). This asks whether a change is unusual relative to the other states; the
   registered test (plan 10.3) asks whether a change differs from zero beyond sampling
   noise.
   Sensitivity (SE variant "wilson"): a binomial component at a proportion of 0 or 1 has
   se = 0 under plan 10.2. Here it is replaced by the Wilson-interval SE, the half-width
   of the 95% Wilson score interval divided by 1.96,
       se_W = sqrt(p (1 - p) / n + z^2 / (4 n^2)) / (1 + z^2 / n),   z = 1.96
   (for indicator 3, of the proportion tested, then divided by 0.7 as in plan 10.2). The
   registered test and both funnel tests are repeated, and the states whose category
   changes are counted. Variant "binomial" is the registered noise model.
2. Q4, multiplicity of the registered test: z_s = |d_s| / SE_s, two-sided P = erfc(z/sqrt 2).
   Bonferroni: z_s > the normal quantile at 1 - 0.05 / (2 k). Benjamini-Hochberg at a false
   discovery rate of 5%: the largest j with P_(j) <= 0.05 j / k, and the j smallest P.
   The expected number of false positives of the unadjusted test if no state changed is
   0.05 k.
3. Q4, regression to the mean (Oldham's method): the Pearson correlation of each state's
   change with its two-year mean (s_2022 + s_2023) / 2, over the states with a score in
   both years (as plan 10.4), with a bootstrap 95% interval (states resampled with
   replacement, N_BOOT draws; 2.5th and 97.5th percentiles by statistics.quantiles(n=40,
   method="inclusive"), as plan 8.2). Spearman's rho of the same pair is given as a
   sensitivity. Both indicator sets of Q4.
4. Q3, prevalence uncertainty: each survey unit's prevalence is drawn from a lognormal
   fitted to its published 95% CI (mu = (ln lo + ln hi) / 2, sigma = (ln hi - ln lo) /
   (2 x 1.96)), and the units are resampled with replacement; Spearman's rho with the
   rebuilt 2023 unit score is recomputed (N_BOOT draws: in each draw one prevalence per
   unit, then the resample). Reported: the median and the 2.5th and 97.5th percentiles,
   also with the prevalence draw alone (no resampling). The precision of rho with n units
   is the half-width of the plan 9.1 interval at rho = 0: tanh(1.96 sqrt(1.06 / (n - 3))).

Writes outputs/posthoc_q4_states.csv and outputs/posthoc_summary.csv.
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
from src import states  # noqa: E402
from src.q2_robust import _pearson  # noqa: E402
from src.q3_validity import FIELLER, spearman_ci  # noqa: E402
from src.q4_change import (COMMON, NO_IND1, UTS, YEARS, Z975, _used, compare,  # noqa: E402
                           load_year, se_components)

LABEL = "post hoc"
SEED = 20261120
N_BOOT = 10000
ALPHA = 0.05
Z95, Z998 = 1.96, 3.09  # funnel limits (Spiegelhalter 2005): 95% and 99.8%
WINSOR = 0.10
RULES = ("R2", "R1")
SE_VARIANTS = ("binomial", "wilson")
SET_LABELS = {COMMON: "1,2,3,4,6", NO_IND1: "2,3,4,6 (indicator 1 excluded)"}
BINOMIAL = (2, 3, 4, 5, 6, 8, 9)
OUT_STATES = os.path.join(ROOT, "outputs", "posthoc_q4_states.csv")
OUT_SUMMARY = os.path.join(ROOT, "outputs", "posthoc_summary.csv")


# ---- noise model: Wilson sensitivity ------------------------------------------------------

def wilson_se(p, n, z=Z975):
    """Half-width of the 95% Wilson score interval for a proportion p of n, divided by z."""
    return math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)


def wilson_components(ach, n, indicators):
    """se_components (plan 10.2) with every binomial se = 0 at a proportion of 0 or 1
    replaced by the Wilson SE. Returns (components, state -> [replaced indicators])."""
    comp = se_components(ach, n, indicators)
    replaced = {}
    for s, c in comp.items():
        for i, se in c.items():
            if se != 0.0 or i not in BINOMIAL:
                continue
            a, d = ach[s][i], n[s][i]
            p = sc.UDST_BENCHMARK * a if i == 3 else a
            if p not in (0.0, 1.0):
                raise ValueError(f"{s} indicator {i}: se 0 at p = {p}")
            w = wilson_se(p, d)
            c[i] = w / sc.UDST_BENCHMARK if i == 3 else w
            replaced.setdefault(s, []).append(i)
    return comp, replaced


def points_in_use(ach, rule, indicators, rescale=True):
    """indicator -> points in use, exactly as q4_change.score_se (x 100 / max points if
    rescaled; / the year's maximum achievement under R3, treated as fixed)."""
    used = _used(ach, indicators)
    max_pts = sum(sc.POINTS[i] for i in used)
    factor = 100.0 / max_pts if rescale and max_pts else 1.0
    pts = {}
    for i in used:
        p = sc.POINTS[i] * factor
        if rule == "R3":
            vals = [a[i] for a in ach.values() if a.get(i) is not None]
            best = max(vals) if vals else None
            p = p / best if best else 0.0
        pts[i] = p
    return pts


def score_se_from(comp, pts):
    """state -> sqrt(sum_i pts_i^2 se_i^2), None if a component is not computable."""
    out = {}
    for s, c in comp.items():
        if any(c.get(i) is None for i in pts):
            out[s] = None
        else:
            out[s] = math.sqrt(sum(pts[i] ** 2 * c[i] ** 2 for i in pts))
    return out


# ---- 1. funnel ----------------------------------------------------------------------------

def ivw_mean(d, se):
    w = [1 / s ** 2 for s in se]
    return sum(wi * di for wi, di in zip(w, d)) / sum(w)


def winsorised(z, share=WINSOR):
    """z clamped to its `share` and 1 - `share` quantiles (inclusive method)."""
    q = statistics.quantiles(z, n=round(1 / share), method="inclusive")
    lo, hi = q[0], q[-1]
    return [min(max(v, lo), hi) for v in z]


def phi_multiplicative(d, se, m):
    """Spiegelhalter's overdispersion factor: mean squared 10%-winsorised z-score."""
    z = [(di - m) / s for di, s in zip(d, se)]
    return sum(v * v for v in winsorised(z)) / len(z)


def tau2_dl(d, se, m):
    """DerSimonian-Laird between-state variance of the changes about m (the IVW mean)."""
    w = [1 / s ** 2 for s in se]
    q = sum(wi * (di - m) ** 2 for wi, di in zip(w, d))
    denom = sum(w) - sum(wi * wi for wi in w) / sum(w)
    return max(0.0, (q - (len(d) - 1)) / denom)


def funnel(d, se):
    """(m, phi, tau2, flags): flags[k] = (mult95, mult998, add95, add998) per state."""
    m = ivw_mean(d, se)
    phi = phi_multiplicative(d, se, m)
    tau2 = tau2_dl(d, se, m)
    infl = math.sqrt(phi) if phi > 1 else 1.0
    flags = []
    for di, s in zip(d, se):
        dev = abs(di - m)
        flags.append((dev > Z95 * infl * s, dev > Z998 * infl * s,
                      dev > Z95 * math.sqrt(s * s + tau2), dev > Z998 * math.sqrt(s * s + tau2)))
    return m, phi, tau2, flags


# ---- 2. multiplicity ----------------------------------------------------------------------

def p_two_sided(z):
    return math.erfc(abs(z) / math.sqrt(2))


def bonferroni_z(k, alpha=ALPHA):
    return statistics.NormalDist().inv_cdf(1 - alpha / (2 * k))


def bh_reject(p, q=ALPHA):
    """Benjamini-Hochberg: list of booleans (rejected), in the order of p."""
    k = len(p)
    order = sorted(range(k), key=lambda j: p[j])
    last = 0
    for rank_, j in enumerate(order, start=1):
        if p[j] <= q * rank_ / k:
            last = rank_
    keep = set(order[:last])
    return [j in keep for j in range(k)]


# ---- 3 and 4. bootstrap -------------------------------------------------------------------

def tails(x):
    q = statistics.quantiles(x, n=40, method="inclusive")
    return q[0], q[-1]


def oldham(s_prev, s_t, rng, n_boot=N_BOOT):
    """(r, lo, hi, n, n_undefined, rho_s, rho_lo, rho_hi): Pearson r of change with the
    two-year mean, its bootstrap interval, and Spearman's rho with its bootstrap interval."""
    keys = sorted(k for k in s_prev if s_prev[k] is not None and s_t.get(k) is not None)
    d = [s_t[k] - s_prev[k] for k in keys]
    mean = [(s_t[k] + s_prev[k]) / 2 for k in keys]
    n = len(keys)
    r = _pearson(d, mean)
    rho = spearman_ci(d, mean)[0]
    rs, rhos, undefined = [], [], 0
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        bd, bm = [d[j] for j in idx], [mean[j] for j in idx]
        br, bs = _pearson(bd, bm), spearman_ci(bd, bm)[0]
        if br is None or bs is None:
            undefined += 1
            continue
        rs.append(br)
        rhos.append(bs)
    lo, hi = tails(rs)
    slo, shi = tails(rhos)
    return r, lo, hi, n, undefined, rho, slo, shi


def lognormal_params(lo, hi, z=Z975):
    if lo <= 0 or hi <= lo:
        raise ValueError(f"CI {lo}-{hi} cannot be fitted by a lognormal")
    return (math.log(lo) + math.log(hi)) / 2, (math.log(hi) - math.log(lo)) / (2 * z)


def prevalence_bootstrap(units, rng, resample=True, n_boot=N_BOOT):
    """(median, p2.5, p97.5, n_undefined) of Spearman's rho of score with prevalence drawn
    from each unit's lognormal; with resample, the units are also resampled."""
    params = [lognormal_params(u["lo"], u["hi"]) for u in units]
    score = [u["score"] for u in units]
    n = len(units)
    out, undefined = [], 0
    for _ in range(n_boot):
        prev = [rng.lognormvariate(mu, sg) for mu, sg in params]
        idx = [rng.randrange(n) for _ in range(n)] if resample else list(range(n))
        rho = spearman_ci([score[j] for j in idx], [prev[j] for j in idx])[0]
        if rho is None:
            undefined += 1
            continue
        out.append(rho)
    lo, hi = tails(out)
    return statistics.median(out), lo, hi, undefined


def rho_half_width(n):
    """Half-width of the plan 9.1 interval at rho = 0 with n units."""
    return math.tanh(Z975 * math.sqrt(FIELLER / (n - 3)))


# ---- run ----------------------------------------------------------------------------------

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
            w.writerow([_cell(r.get(h)) for h in header])


def _registered(out_dir):
    """(rule, state) -> row of the registered Q4 output (indicators 1, 2, 3, 4, 6)."""
    with open(os.path.join(out_dir, "q4_2022_2023_states.csv"), encoding="utf-8") as f:
        return {(r["rule"], r["state"]): r for r in csv.DictReader(f)
                if r["indicator_set"] == SET_LABELS[COMMON]}


def q4_states(data, rule, inds, variant):
    """state -> dict of scores, SEs and change under one rule, indicator set and SE variant."""
    s = {y: sc.score(data[y][0], rule, indicators=inds, rescale=True) for y in YEARS}
    se, repl = {}, {}
    for y in YEARS:
        ach, n = data[y][0], data[y][1]
        if variant == "binomial":
            comp, repl[y] = se_components(ach, n, inds), {}
        else:
            comp, repl[y] = wilson_components(ach, n, inds)
        se[y] = score_se_from(comp, points_in_use(ach, rule, inds))
    cmp_ = compare(s[2022], se[2022], s[2023], se[2023], labels=("2022", "2023"))
    out = {}
    for st in states.ALL:
        c = cmp_[st]
        both = c["exceeds"] is not None
        out[st] = {"s_2022": s[2022][st], "s_2023": s[2023][st], "se_2022": se[2022][st],
                   "se_2023": se[2023][st], "change": c["change"], "pct_change": c["pct_change"],
                   "mean_2022_2023": ((s[2022][st] + s[2023][st]) / 2
                                      if c["change"] is not None else None),
                   "se_change": (math.sqrt(se[2022][st] ** 2 + se[2023][st] ** 2)
                                 if both else None),
                   "exceeds_registered": c["exceeds"],
                   "excluded_reason": c["excluded_reason"],
                   "wilson_replaced": "; ".join(
                       f"{y}: indicator {', '.join(map(str, repl[y][st]))}"
                       for y in YEARS if st in repl[y])}
    return out


def main():
    ext = os.path.join(ROOT, "data", "extracted")
    out_dir = os.path.join(ROOT, "outputs")
    with open(os.path.join(out_dir, "q1_2023_selection.json"), encoding="utf-8") as f:
        sel = json.load(f)
    if list(sel["rules_for_q2q4"]) != [RULES[0]] or RULES[1] not in sel["sensitivity_rules"]:
        raise ValueError("post hoc rules assume R2 primary and R1 a registered sensitivity rule")
    data = {y: load_year(ext, y) for y in YEARS}
    reg = _registered(out_dir)

    state_rows, summary = [], []

    def add(analysis, rule, iset, variant, quantity, value, lo=None, hi=None, n=None, note=""):
        summary.append({"label": LABEL, "analysis": analysis, "rule": rule,
                        "indicator_set": iset, "se_variant": variant, "quantity": quantity,
                        "value": value, "lo": lo, "hi": hi, "n": n, "note": note})

    iset = SET_LABELS[COMMON]
    cat = {}  # (rule, variant) -> {state: (registered, mult95, mult998, add95, add998)}
    for rule in RULES:
        role = "primary" if rule == RULES[0] else "sensitivity"
        for variant in SE_VARIANTS:
            st = q4_states(data, rule, COMMON, variant)
            if variant == "binomial":  # the registered model: must equal the committed output
                for s, v in st.items():
                    r = reg[(rule, s)]
                    for col in ("s_2022", "s_2023", "se_2022", "se_2023", "change"):
                        if _cell(v[col]) != r[col]:
                            raise ValueError(f"{rule} {s} {col}: {v[col]!r} differs from the "
                                             f"registered output {r[col]!r}")
            comp = [s for s in states.ALL if st[s]["exceeds_registered"] is not None]
            d = [st[s]["change"] for s in comp]
            se = [st[s]["se_change"] for s in comp]
            k = len(comp)
            m, phi, tau2, flags = funnel(d, se)
            z = [di / si for di, si in zip(d, se)]
            p = [p_two_sided(v) for v in z]
            zb = bonferroni_z(k)
            bh = bh_reject(p)
            fl = dict(zip(comp, flags))
            cat[(rule, variant)] = {}
            for s in states.ALL:
                v = st[s]
                row = {"label": LABEL, "rule": rule, "rule_role": role, "se_variant": variant,
                       "indicator_set": iset, "state": s, "ut": int(s in UTS), **v}
                if s in fl:
                    j = comp.index(s)
                    row.update({"z_registered": z[j], "p_two_sided": p[j],
                                "exceeds_bonferroni": abs(z[j]) > zb, "exceeds_bh": bh[j],
                                "z_funnel": (v["change"] - m) / v["se_change"],
                                "outside95_mult": fl[s][0], "outside998_mult": fl[s][1],
                                "outside95_add": fl[s][2], "outside998_add": fl[s][3]})
                    cat[(rule, variant)][s] = (v["exceeds_registered"],) + fl[s]
                state_rows.append(row)
            n_exc = sum(st[s]["exceeds_registered"] for s in comp)
            a = "Q4 noise"
            add(a, rule, iset, variant, "n_compared", k, n=k)
            add(a, rule, iset, variant, "n_exceeds_registered", n_exc, n=k,
                note="plan 10.3: |change| > 1.96 SE of the change")
            add(a, rule, iset, variant, "ivw_mean_change", m, n=k)
            add(a, rule, iset, variant, "phi", phi, n=k,
                note="mean squared 10%-winsorised z-score (Spiegelhalter 2005)")
            add(a, rule, iset, variant, "tau2", tau2, n=k, note="DerSimonian-Laird")
            for j, (q, lev) in enumerate((("mult", "95"), ("mult", "99.8"), ("add", "95"),
                                          ("add", "99.8"))):
                add(a, rule, iset, variant, f"n_outside{lev.replace('.', '')}_{q}",
                    sum(f[j] for f in flags), n=k,
                    note=f"{'multiplicative' if q == 'mult' else 'additive'} overdispersion; "
                         f"{lev}% limits about the IVW mean change")
            if variant == "binomial":
                a2 = "Q4 multiplicity"
                add(a2, rule, iset, variant, "z_bonferroni", zb, n=k,
                    note=f"normal quantile at 1 - {ALPHA}/(2 x {k})")
                add(a2, rule, iset, variant, "n_exceeds_bonferroni",
                    sum(abs(v) > zb for v in z), n=k)
                add(a2, rule, iset, variant, "n_exceeds_bh", sum(bh), n=k,
                    note=f"Benjamini-Hochberg, false discovery rate {ALPHA}")
                add(a2, rule, iset, variant, "expected_false_positives", ALPHA * k, n=k,
                    note=f"{ALPHA} x {k}, unadjusted test, if no state changed")
            else:
                repl = sorted(s for s in states.ALL if st[s]["wilson_replaced"])
                add(a, rule, iset, variant, "n_states_wilson", len(repl),
                    note="; ".join(repl))
        base, wil = cat[(rule, "binomial")], cat[(rule, "wilson")]
        names = ("registered", "outside95_mult", "outside998_mult", "outside95_add",
                 "outside998_add")
        for j, nm in enumerate(names):
            changed = sorted(s for s in base if s in wil and base[s][j] != wil[s][j])
            add("Q4 noise", rule, iset, "wilson", f"n_changed_{nm}", len(changed),
                n=len(base), note="; ".join(changed) or "none")

    for rule in RULES:
        for inds in (COMMON, NO_IND1):
            st = q4_states(data, rule, inds, "binomial")
            rng = random.Random(SEED)
            r, lo, hi, n, und, rho, slo, shi = oldham(
                {s: st[s]["s_2022"] for s in states.ALL},
                {s: st[s]["s_2023"] for s in states.ALL}, rng)
            note = f"{N_BOOT} bootstrap draws, seed {SEED}; {und} undefined"
            add("Q4 regression to the mean", rule, SET_LABELS[inds], "binomial",
                "oldham_r", r, lo, hi, n, "Pearson r of change with the two-year mean; " + note)
            add("Q4 regression to the mean", rule, SET_LABELS[inds], "binomial",
                "oldham_rho", rho, slo, shi, n, "Spearman rho, sensitivity; " + note)

    with open(os.path.join(out_dir, "q3_2023_units.csv"), encoding="utf-8") as f:
        q3 = list(csv.DictReader(f))
    for rule in RULES:
        units = [{"score": float(u["unit_score"]), "lo": float(u["ci_low"]),
                  "hi": float(u["ci_high"]), "prev": float(u["prevalence"])}
                 for u in q3 if u["rule"] == rule and u["dropped"] == "0"]
        n = len(units)
        point = spearman_ci([u["score"] for u in units], [u["prev"] for u in units])[0]
        a = "Q3 prevalence uncertainty"
        add(a, rule, "", "", "rho_point", point, n=n, note="registered plan 9.1 estimate")
        for resample, q in ((True, "rho_bootstrap"), (False, "rho_prevalence_only")):
            rng = random.Random(SEED)
            med, lo, hi, und = prevalence_bootstrap(units, rng, resample)
            add(a, rule, "", "", q, med, lo, hi, n,
                f"median and 2.5th-97.5th percentiles; lognormal prevalence"
                f"{' and units resampled' if resample else ''}; {N_BOOT} draws, seed {SEED}; "
                f"{und} undefined")
        add(a, rule, "", "", "rho_half_width_at_0", rho_half_width(n), n=n,
            note="tanh(1.96 sqrt(1.06/(n - 3)))")

    _write(OUT_STATES,
           ["label", "rule", "rule_role", "se_variant", "indicator_set", "state", "ut",
            "s_2022", "se_2022", "s_2023", "se_2023", "change", "pct_change", "mean_2022_2023",
            "se_change", "z_registered", "p_two_sided", "exceeds_registered",
            "exceeds_bonferroni", "exceeds_bh", "z_funnel", "outside95_mult",
            "outside998_mult", "outside95_add", "outside998_add", "wilson_replaced",
            "excluded_reason"], state_rows)
    _write(OUT_SUMMARY, ["label", "analysis", "rule", "indicator_set", "se_variant", "quantity",
                         "value", "lo", "hi", "n", "note"], summary)

    print(f"POST HOC analyses (plan section 13, 20 November 2026); seed {SEED}")
    for r in summary:
        v = r["value"]
        v = f"{v:.4f}" if isinstance(v, float) else v
        ci = (f" ({r['lo']:.3f} to {r['hi']:.3f})" if r["lo"] is not None else "")
        print(f"  {r['analysis']} | {r['rule']} {r['se_variant']} {r['indicator_set']} | "
              f"{r['quantity']}: {v}{ci}" + (f" | {r['note']}" if r["note"] and
                                            r["quantity"].startswith("n_changed") else ""))
    print(f"wrote {os.path.relpath(OUT_STATES, ROOT)} and {os.path.relpath(OUT_SUMMARY, ROOT)}")


if __name__ == "__main__":
    main()

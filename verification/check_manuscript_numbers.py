"""Check every number in the manuscript against the committed outputs.

Run as: python -I verification/check_manuscript_numbers.py

The manuscript (manuscript/, git-ignored) is kept private until an editorial
decision. When manuscript/ is absent this prints
"SKIPPED: manuscript/ not present (kept private until a decision)" and exits 0, and
check_all counts the step as skipped. It is also skipped while manuscript/ exists but
manuscript/manuscript.md has not been written.

When manuscript/manuscript.md is present, these checks run:

1. every expected string from want() (the REQUIRED labels of the catalogue) occurs in
   the manuscript, as a whole token (not as part of a longer number, and not after a
   minus sign);
2. the headline strings of ABSTRACT_REQUIRED occur inside the '## Abstract' section;
3. every number in the prose is accounted for: after every specific catalogue string
   (not a bare one- or two-digit integer, which would mask every such number) and the
   ALLOW patterns are masked out, no digit may remain. ALLOW masks only the study's
   years (2019-2026), exhibit, section, rule, question and indicator names (each digit
   run ending at a non-digit, so "indicator 6, 25" leaves 25), reference superscripts
   and the AI model's version. Markdown table rows (lines starting with "|", which
   exhibits/make_tables.py generates) and everything from the "References" heading on are not
   scanned. A changed number therefore fails twice: its expected string goes missing
   and the changed value is unaccounted;
4. if exhibits/make_tables.py and manuscript/tables.md exist, tables.md equals a
   fresh rendering (so the tables are not stale against outputs/), and manuscript.md
   carries tables.md verbatim.

catalogue() is a dict of label -> string, derived from outputs/, data/, the code's own
constants (src/) and, for constants the code does not hold, the registered plan
(docs/analysis_plan.md); want() is its REQUIRED subset. Software versions are read from
ENVIRONMENT.md, which pins the versions that produced the committed outputs.
Number formats (decimals, the minus sign U+2212, en dash ranges, thousands
separators) are fixed once, in the "Number formats" section below, and
exhibits/make_tables.py imports the same helpers, so the text and the tables
cannot drift apart in format. As the prose takes shape, add labels to catalogue() and
list the ones the text must carry in REQUIRED.
Exit 1 on any failure.
"""
from __future__ import annotations

import csv
import fnmatch
import importlib.util
import json
import math
import statistics
import re
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SKIP_DIR = "SKIPPED: manuscript/ not present (kept private until a decision)"
SKIP_MS = "SKIPPED: manuscript/manuscript.md not written yet"

# --------------------------------------------------------------------------------------
# Number formats: the only place they are fixed
# --------------------------------------------------------------------------------------
MINUS = "−"  # true minus sign, never a hyphen
EN_DASH = "–"  # ranges between two non-negative numbers
TO = " to "  # ranges where a bound is negative (an en dash would read as a minus)
DP = {
    "score": 2,  # State TB Score points, residuals, violations, thresholds
    "rho": 2,  # Spearman rho and its interval
    "pct": 1,  # percentages
    "pct_small": 3,  # small relative differences (target check, population check)
    "change": 2,  # score changes (points)
}


def num(x: float, dp: int) -> str:
    """Fixed decimals, U+2212 for negatives, and no negative zero ("-0.00" -> "0.00")."""
    s = f"{x:.{dp}f}"
    if s.startswith("-"):
        s = s[1:] if float(s) == 0 else MINUS + s[1:]
    return s


def count(n: int) -> str:
    """Integer with thousands separators: 1,023,924."""
    if int(n) != n:
        raise ValueError(f"not an integer count: {n!r}")
    s = f"{int(n):,}"
    return MINUS + s[1:] if s.startswith("-") else s


def rank(x: float) -> str:
    """A rank or rank change: whole numbers without decimals, average ranks to one decimal."""
    return num(x, 0) if float(x) == int(x) else num(x, 1)


def rng(lo: str, hi: str) -> str:
    """Join two formatted bounds: en dash, or ' to ' if either bound is negative."""
    sep = TO if lo.startswith(MINUS) or hi.startswith(MINUS) else EN_DASH
    return f"{lo}{sep}{hi}"


def pct(k: float, n: float, dp: int = DP["pct"]) -> str:
    """k as a percentage of n: '68.6%'."""
    return num(100 * k / n, dp) + "%"


def k_of_n(k: int, n: int) -> str:
    """'24 of 35'."""
    return f"{count(k)} of {count(n)}"


def k_of_n_pct(k: int, n: int) -> str:
    """Absolute numbers with the percentage (IJMR): '24 of 35 (68.6%)'."""
    return f"{k_of_n(k, n)} ({pct(k, n)})"


def rho(r: float) -> str:
    return num(r, DP["rho"])


def rho_ci(r: float, lo: float, hi: float) -> str:
    """'−0.24 (95% CI −0.63 to 0.26)'."""
    return f"{rho(r)} (95% CI {rng(rho(lo), rho(hi))})"


def n_eq(n: int) -> str:
    """'n = 19'."""
    return f"n = {count(n)}"


def listing(items: list[str]) -> str:
    """'A', 'A and B', 'A, B and C' (UK style, no serial comma)."""
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


# --------------------------------------------------------------------------------------
# Loaders
# --------------------------------------------------------------------------------------
def read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def q1_selection(root: Path) -> dict:
    return json.loads((root / "outputs" / "q1_2023_selection.json").read_text(encoding="utf-8"))


def target_check(root: Path) -> dict:
    """The numbers of outputs/q1_target_check.txt."""
    text = (root / "outputs" / "q1_target_check.txt").read_text(encoding="utf-8")

    def grab(pattern: str) -> str:
        m = re.search(pattern, text, re.M)
        if not m:
            raise ValueError(f"q1_target_check.txt: no match for {pattern!r}")
        return m.group(1)

    return {
        "expected": int(grab(r"INDIA row: (\d+)$")),
        "target": int(grab(r"Total\): (\d+)$")),
        "difference": int(grab(r"Difference \(expected - target\): (-?\d+)$")),
        "tolerance": grab(r"^Tolerance: \|difference\| <= (\d+(?:\.\d+)?%) of the target"),
        "verdict": grab(r"^Verdict: (\w+)$"),
    }


def target_relative(root: Path) -> str:
    """The one string for the plan 5.3 relative difference, used by text and tables."""
    tc = target_check(root)
    return pct(tc["difference"], tc["target"], DP["pct_small"])


def source_note(root: Path, year: str, indicator: str, component: str) -> str:
    for r in read_csv(root / "data" / "source_choices.csv"):
        if (r["score_year"], r["indicator"], r["component"]) == (year, indicator, component):
            return r["note"]
    raise KeyError((year, indicator, component))


def indicator3_contrast(root: Path) -> dict:
    """Indicator 3, score year 2023: the annexure share against Table 11.1's printed share.

    The counts are summed from data/extracted/itr2024_indicators.csv; the printed 58% is
    read from the source note, which must also print the same computed share.
    """
    rows = [r for r in read_csv(root / "data" / "extracted" / "itr2024_indicators.csv")
            if r["indicator"] == "3"]
    k = sum(int(r["numerator"]) for r in rows)
    n = sum(int(r["denominator"]) for r in rows)
    note = source_note(root, "2023", "3", "numerator")
    m = re.search(r"prints (\d+(?:\.\d+)?)% of notified patients", note)
    if not m:
        raise ValueError("source_choices 2023/3: Table 11.1 share not found")
    m2 = re.search(r"= (\d+\.\d)% nationally", note)
    if not m2 or m2.group(1) + "%" != pct(k, n):
        raise ValueError("source_choices 2023/3: recorded share differs from the extracted counts")
    printed = float(m.group(1))
    return {"k": k, "n": n, "share": pct(k, n), "printed": m.group(1) + "%",
            "printed_value": printed}


def population_check(root: Path) -> dict:
    rows = read_csv(root / "data" / "extracted" / "itr2024_population.csv")
    states = [float(r["population"]) for r in rows if r["state"] != "INDIA"]
    india = next(float(r["population"]) for r in rows if r["state"] == "INDIA")
    total = sum(states)
    return {"n_units": len(states), "sum": round(total), "india": round(india),
            "diff_pct": num(100 * (total - india) / india, DP["pct_small"]) + "%"}


MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December")
WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
         "eleven", "twelve")


def plan_text(root: Path) -> str:
    return (root / "docs" / "analysis_plan.md").read_text(encoding="utf-8")


def plan_facts(root: Path) -> dict:
    """Constants fixed in the registered plan that the code does not hold as a constant."""
    text = plan_text(root)

    def grab(pattern: str) -> re.Match:
        m = re.search(pattern, text, re.M)
        if not m:
            raise ValueError(f"analysis_plan.md: no match for {pattern!r}")
        return m

    reg = grab(r"pushed to the public repository \S+ at (\d{4})-(\d\d)-(\d\d)T(\d\d:\d\d:\d\d)Z")
    y, mo, d, t = reg.groups()
    deviations = text.split("## 13. Deviations", 1)[1]
    n_dev = len(re.findall(r"^\d+\. \*\*", deviations, re.M))
    return {
        "alpha": grab(r"alpha_i = (\d+) for every i").group(1),
        "sat_share": int(grab(r"at least (\d+)% of the states for which it is computable").group(1)),
        "registration": f"{int(d)} {MONTHS[int(mo) - 1]} {y} at {t} UTC",
        "n_deviations": n_dev,
    }


def q4_ind4_error(root: Path) -> dict:
    """The treatment-success achievement above 1 that excludes a state from the noise test
    (plan 10.2), with the cohort whose outcomes it counts (an artefact of the same-period
    denominator: outcomes of the previous year's cohort over this year's notified)."""
    r = next(r for r in read_csv(root / "outputs" / "q4_2022_2023_summary.csv")
             if r["primary"] == "1")
    m = re.search(r"^(.+?) \(SE not computable in (\d{4}) \(indicator (\d): binomial a = "
                  r"(\d+(?:\.\d+)?) > 1 \((\d+)/(\d+)\)\)\)$", r["excluded"])
    if not m:
        raise ValueError("q4 summary: excluded state not in the expected form")
    state, k = m.group(1), int(m.group(5))
    cohort = next(c for c in read_csv(root / "data" / "extracted" / "itr2024_tsr_cohort.csv")
                  if c["state"] == state)
    if int(cohort["success"]) != k:
        raise ValueError(f"{state}: q4 success {k} differs from the cohort file")
    return {"state": state, "year": m.group(2), "indicator": m.group(3),
            "a": m.group(4), "k": k, "n": int(m.group(6)),
            "cohort_year": cohort["cohort_year"], "cohort_n": int(cohort["cohort_notified"])}


def explore_udst(root: Path) -> dict[str, dict]:
    """Rule -> summary row of the exploratory indicator 3 scaling (plan section 13)."""
    rows = read_csv(root / "outputs" / "exploratory_udst_scaling_2023.csv")
    if any(r["label"] != "exploratory" for r in rows):
        raise ValueError("exploratory_udst_scaling_2023.csv: a row is not labelled exploratory")
    return {r["rule"]: r for r in rows if r["row_type"] == "rule_summary"}


def survey_not_covered(root: Path) -> dict[str, list[str]]:
    """States the survey excludes, and states it does not name (data/extracted)."""
    rows = read_csv(root / "data" / "extracted" / "ntps_not_covered.csv")
    named = [r["state"] for r in rows if r["reason"] != "not listed in survey units"]
    unnamed = [r["state"] for r in rows if r["reason"] == "not listed in survey units"]
    return {"excluded": named, "not_named": unnamed}


def q3_measure(root: Path) -> dict:
    """Age bound and population base of the survey measure, read from the printed label."""
    u = read_csv(root / "data" / "extracted" / "ntps_units.csv")[0]["measure_verbatim"]
    age = re.search(r"aged ≥ (\d+) years", u)
    per = re.search(r"per (\d+) (\d{3}) population", u)
    if not (age and per):
        raise ValueError("ntps_units.csv: measure label not in the expected form")
    return {"age": int(age.group(1)), "per": int(per.group(1) + per.group(2))}


def environment(root: Path) -> dict[str, str]:
    """Software versions pinned in ENVIRONMENT.md ('- Python 3.14.0', '- pdfplumber 0.11.8')."""
    text = (root / "ENVIRONMENT.md").read_text(encoding="utf-8")
    out = dict(re.findall(r"^- (Python|pdfplumber) (\d+(?:\.\d+)+)\s*$", text, re.M))
    if set(out) != {"Python", "pdfplumber"}:
        raise ValueError("ENVIRONMENT.md: Python and pdfplumber versions not both pinned")
    return out


def figure_constants(root: Path) -> dict[str, str]:
    """Figure 3's dodge of near-coincident error bars, read from exhibits/make_figures.py;
    empty if the script is absent."""
    script = root / "exhibits" / "make_figures.py"
    if not script.exists():
        return {}
    src = script.read_text(encoding="utf-8")
    gap = re.search(r"^DODGE_GAP = (\d+(?:\.\d+)?)", src, re.M)
    pt = re.search(r"^DODGE_PT = (\d+(?:\.\d+)?)", src, re.M)
    if not (gap and pt):
        raise ValueError("make_figures.py: DODGE_GAP or DODGE_PT not found")
    apart = 2 * float(pt.group(1))  # each bar of a pair moves DODGE_PT points
    return {"fig3.dodge_gap": f"less than {gap.group(1)} points apart",
            "fig3.dodge_pt": f"{rank(apart)} pt apart"}


def q3_excluded(summary_excluded: str) -> dict[str, list[str]]:
    """Parse 'not covered by the survey: A, B; member without score: C; ...'."""
    out: dict[str, list[str]] = {}
    for part in summary_excluded.split("; "):
        key, _, names = part.partition(": ")
        out[key] = [x.strip() for x in names.split(", ") if x.strip()]
    return out


# --------------------------------------------------------------------------------------
# Expected strings
# --------------------------------------------------------------------------------------
def catalogue(root: Path = ROOT) -> dict[str, str]:
    """label -> string, for every number the manuscript may quote. All derived from files."""
    w: dict[str, str] = {}

    # ---- Q1: reproducibility (outputs/q1_2023_selection.json, q1_target_check.txt)
    sel = q1_selection(root)
    w["q1.verdict"] = sel["verdict"]
    w["q1.chosen_rule"] = sel["chosen"]
    w["q1.score_kind"] = sel["score_kind"]
    w["q1.missing_indicators"] = "indicators " + listing([str(i) for i in sel["missing_indicators"]])
    w["q1.missing_points"] = f"{count(sel['missing_points'])} points"
    w["q1.available_points"] = f"{count(100 - sel['missing_points'])} points"
    w["q1.excluded"] = listing(sel["excluded"])
    w["q1.n_published"] = f"{count(len(sel['per_state']))} states and union territories"
    for rule, d in sel["per_rule"].items():
        if "n_in_band" not in d:
            continue
        w[f"q1.{rule}.in_band"] = k_of_n(d["n_in_band"], d["n_compared"])
        w[f"q1.{rule}.max_violation"] = num(d["max_violation"], DP["score"])
        res = [s[rule]["residual"] for s in sel["per_state"].values() if not s[rule]["excluded"]]
        w[f"q1.{rule}.residual_range"] = rng(num(min(res), DP["score"]),
                                            num(max(res), DP["score"]))
    tc = target_check(root)
    w["q1.target.expected"] = count(tc["expected"])
    w["q1.target.target"] = count(tc["target"])
    w["q1.target.difference"] = count(tc["difference"])
    w["q1.target.relative"] = target_relative(root)
    w["q1.target.tolerance"] = tc["tolerance"]

    # ---- indicator 3 contrast (data/extracted + data/source_choices.csv)
    c3 = indicator3_contrast(root)
    w["ind3.annexure_counts"] = k_of_n(c3["k"], c3["n"])
    w["ind3.annexure_share"] = c3["share"]
    w["ind3.table11_1_share"] = c3["printed"]

    # ---- population check (Q3 weights)
    pc = population_check(root)
    w["pop.sum"] = count(pc["sum"])
    w["pop.india"] = count(pc["india"])
    w["pop.diff"] = pc["diff_pct"]

    # ---- Q2: robustness (outputs/q2_2023_summary.csv, q2_2023_saturation.csv)
    for r in read_csv(root / "outputs" / "q2_2023_summary.csv"):
        if not r["n_compared"]:
            continue
        key = f"q2.{r['rule']}.{r['variant']}" + (f".{r['setting']}" if r["setting"] else "")
        w[key + ".n"] = n_eq(int(r["n_compared"]))
        w[key + ".spearman"] = rho(float(r["spearman"]))
        if r["variant"] == "base":
            continue
        w[key + ".median_change"] = rank(float(r["median_change"]))
        w[key + ".max_change"] = rank(float(r["max_change"]))
        if r["spearman_p2.5"]:
            w[key + ".median_change_iqr"] = rng(rank(float(r["median_change_q1"])),
                                                rank(float(r["median_change_q3"])))
            w[key + ".max_change_iqr"] = rng(rank(float(r["max_change_q1"])),
                                             rank(float(r["max_change_q3"])))
            w[key + ".spearman_range"] = rng(rho(float(r["spearman_p2.5"])),
                                             rho(float(r["spearman_p97.5"])))
    sat = read_csv(root / "outputs" / "q2_2023_saturation.csv")
    w["q2.n_saturated"] = count(sum(int(r["saturated"]) for r in sat))
    top = max(sat, key=lambda r: float(r["share_ge_0.95"]))
    w["q2.max_share_ge_0.95"] = pct(float(top["share_ge_0.95"]), 1)
    w["q2.max_share_ge_0.95.indicator"] = f"indicator {top['indicator']}"

    # ---- Q3: validity (outputs/q3_2023_summary.csv, q3_2023_units.csv)
    for r in read_csv(root / "outputs" / "q3_2023_summary.csv"):
        if not r["n"]:
            continue
        a = "primary" if r["analysis"].startswith("9.1") else "secondary"
        key = f"q3.{r['rule']}.{a}"
        w[key + ".rho_ci"] = rho_ci(float(r["rho"]), float(r["lo"]), float(r["hi"]))
        w[key + ".n"] = n_eq(int(r["n"]))
        if r["rule"] == sel["chosen"] and a == "primary":
            ex = q3_excluded(r["excluded"])
            w["q3.not_covered"] = listing(ex["not covered by the survey"])
            w["q3.unit_dropped"] = listing(ex["unit dropped (no scored member)"])
    units = [u for u in read_csv(root / "outputs" / "q3_2023_units.csv")
             if u["rule"] == sel["chosen"]]
    kept = [u for u in units if u["dropped"] == "0"]
    w["q3.units_printed"] = f"{count(len(units))} reporting units"
    w["q3.units_analysed"] = f"{count(len(kept))} units"
    w["q3.units_group"] = f"{count(sum(u['unit_type'] == 'group' for u in kept))} state groups"
    w["q3.states_covered"] = (
        f"{count(sum(len(u['members_scored'].split(';')) for u in kept))} states and union territories")

    # ---- Q4: change over time (outputs/q4_2022_2023_summary.csv)
    for r in read_csv(root / "outputs" / "q4_2022_2023_summary.csv"):
        iset = "all" if r["indicator_set"] == "1,2,3,4,6" else "no1"
        key = f"q4.{r['rule']}.{iset}"
        w[key + ".exceeds"] = k_of_n_pct(int(r["n_exceeds"]), int(r["n_compared"]))
        w[key + ".rho_ci"] = rho_ci(float(r["rho"]), float(r["rho_lo"]), float(r["rho_hi"]))
        w[key + ".rho_n"] = n_eq(int(r["rho_n"]))
        w[key + ".rho_context"] = f"{rho(float(r['rho']))} under {r['rule']}"
        if r["rule"] == sel["chosen"] and iset == "all":
            w["q4.n_states"] = f"{count(int(r['n_compared']))} states and union territories"
            w["q4.excluded"] = r["excluded"].split(" (")[0]
            w["q4.se0_2022"] = count(int(r["n_states_se0_2022"]))
            w["q4.se0_2023"] = count(int(r["n_states_se0_2023"]))
            # in context, so that the check never masks a bare "3" or "2" elsewhere
            w["q4.se0_counts"] = (f"{count(int(r['n_states_se0_2022']))} states in 2022 and "
                                  f"{count(int(r['n_states_se0_2023']))} in 2023")
    err = q4_ind4_error(root)
    w["q4.ind4_error.counts"] = (f"{count(err['k'])} successful outcomes of its "
                                 f"{err['cohort_year']} cohort of {count(err['cohort_n'])}")
    w["q4.ind4_error.denominator"] = f"{count(err['n'])} net notified patients of {err['year']}"
    w["q4.ind4_error.a"] = f"achievement of {err['a']}"
    # a binomial indicator at full achievement has se = 0 (plan 10.2)
    w["q4.se0_cause"] = f"{pct(1, 1, 0)} on a binomial indicator"

    # ---- headline phrasing of values that the tables give bare
    sat_top = max(sat, key=lambda r: float(r["share_ge_0.95"]))
    k_top = round(float(sat_top["share_ge_0.95"]) * int(sat_top["n_computable"]))
    w["q2.max_share_ge_0.95.k_of_n"] = k_of_n_pct(k_top, int(sat_top["n_computable"]))
    m = q3_measure(root)
    w["q3.age"] = f"{count(m['age'])} years"
    w["q3.per"] = f"per {count(m['per'])}"
    w["q3.age_short"] = f"≥{count(m['age'])} y"  # tables and figures abbreviate years (IJMR)
    w["q3.units_analysed_reporting"] = f"{count(len(kept))} reporting units"
    nc = survey_not_covered(root)
    w["q3.survey_excluded"] = listing(nc["excluded"])
    w["q3.survey_not_named"] = listing(nc["not_named"])
    cov = read_csv(root / "data" / "extracted" / "ntps_cluster_coverage.csv")
    india = next(r for r in cov if r["state"] == "INDIA")
    w["q3.clusters"] = (f"{count(int(india['clusters_completed']))} of "
                        f"{count(int(india['clusters_planned']))} planned clusters")
    from src.q2_robust import fifth_size
    n2 = next(int(r["n_compared"]) for r in read_csv(root / "outputs" / "q2_2023_summary.csv")
              if r["rule"] == sel["chosen"] and r["variant"] == "base")
    w["q2.fifth_size"] = f"{count(fifth_size(n2))} states in each fifth"
    w.update(figure_constants(root))

    # ---- exploratory (plan section 13): indicator 3 scaled to CTD's national figure
    for rule, r in explore_udst(root).items():
        w[f"explore.{rule}.in_band"] = k_of_n(int(r["n_in_band"]), int(r["n_compared"]))
        w[f"explore.{rule}.outside"] = listing(r["outside"].split("; ") if r["outside"] else [])

    # ---- plan 9.3: deaths and loss to follow-up, descriptive context only
    ctx = read_csv(root / "data" / "extracted" / "itr2024_outcomes_context.csv")
    nat = next(r for r in ctx if r["state"] == "INDIA")
    st = [r for r in ctx if r["state"] != "INDIA" and int(r["cohort_notified"]) > 0]
    n_nat = int(nat["cohort_notified"])
    for col, key in (("died", "died"), ("lost_to_follow_up", "ltfu")):
        k = int(nat[col])
        shares = [int(r[col]) / int(r["cohort_notified"]) for r in st]
        w[f"ctx.{key}.national"] = (k_of_n_pct(k, n_nat) if key == "died"
                                    else f"{count(k)} ({pct(k, n_nat)})")
        w[f"ctx.{key}.states"] = (f"median {pct(statistics.median(shares), 1)} (range "
                                  f"{rng(pct(min(shares), 1), pct(max(shares), 1))})")
    w["ctx.n_states"] = f"{count(len(st))} states and union territories"

    # ---- Methods constants: from the code where it holds them, else from the plan
    from src.q1_reproduce import TOL
    from src.q2_robust import N_DRAWS, SAT_LEVEL, SEED, SETTINGS
    from src.q3_validity import FIELLER
    from src.q4_change import Z975
    from src.score import POINTS, UDST_BENCHMARK
    pf = plan_facts(root)
    w["methods.total_points"] = f"{count(sum(POINTS.values()))} points"
    w["methods.udst"] = pct(UDST_BENCHMARK, 1, 0) + " of net notified patients"
    w["methods.udst_se"] = f"divided by {UDST_BENCHMARK}"  # plan 10.2: indicator 3 se
    # plan 7.2: under R2 an expenditure ratio above 1 would give indicator 7 more than
    # its maximum points
    w["methods.r2_cap"] = f"more than its {count(POINTS[7])} points"
    w["methods.tolerance"] = f"{num(TOL, 2)} points"
    w["methods.draws"] = f"{count(N_DRAWS)} draws"
    w["methods.seed"] = f"seed {SEED}"
    c = next(v for k, v in SETTINGS if v is not None)
    w["methods.c"] = f"c = {count(int(c))}"
    w["methods.alpha"] = f"α = {pf['alpha']}"
    w["methods.z"] = num(Z975, 2)
    level = math.erf(Z975 / math.sqrt(2))  # two-sided coverage of ±Z975
    w["methods.ci_level"] = f"{num(100 * level, 0)}% confidence interval"
    w["methods.central_draws"] = f"central {num(100 * level, 0)}% of draws"
    w["methods.fieller"] = f"{num(FIELLER, 2)} ÷ (n − 3)"  # plan 9.1: SE = sqrt(1.06 / (n - 3))
    w["methods.sat_share"] = f"{pf['sat_share']}% of states"
    w["methods.sat_level"] = num(SAT_LEVEL, 2)
    w["methods.registration"] = pf["registration"]
    w["methods.n_deviations"] = f"{WORDS[pf['n_deviations']]} dated entries"
    env = environment(root)
    w["methods.python"] = f"Python {env['Python']}"
    w["methods.pdfplumber"] = f"pdfplumber {env['pdfplumber']}"
    return w


# Labels (fnmatch patterns) whose strings MUST appear in the manuscript. The rest of the
# catalogue may appear (it is accounted for in the number scan) but is not required,
# because IJMR forbids repeating table and figure data in the text.
REQUIRED = [
    # Q1 (one primary number per question in Results; the rest are in the exhibits)
    "q1.verdict", "q1.n_published", "q1.missing_indicators", "q1.missing_points",
    "q1.available_points", "q1.excluded", "q1.R2.in_band", "q1.R2.max_violation",
    "ind3.annexure_share", "ind3.table11_1_share",
    "pop.diff",
    # Q2
    "q2.R2.1_weights.c63.spearman_range",
    # Q3
    "q3.R2.primary.rho_ci", "q3.R2.primary.n",
    "q3.units_printed", "q3.units_analysed", "q3.states_covered", "q3.survey_excluded",
    "q3.survey_not_named",
    "q3.age", "q3.per", "q3.clusters",
    # Q4 and the disclosures of the Discussion
    "q4.R2.all.exceeds", "q4.R2.all.rho_n", "q4.R2.no1.rho_ci", "q4.R1.no1.rho_context",
    "q4.excluded", "q4.se0_counts", "q4.se0_cause", "q4.ind4_error.*",
    # exploratory (plan section 13)
    "explore.R2.in_band", "explore.R2.outside",
    # plan 9.3: deaths and loss to follow-up, reported descriptively
    "ctx.*",
    # Methods constants. The seed value is not printed in the blinded text (it can be
    # searched for in the deposited code), so methods.seed is not required.
    "methods.total_points", "methods.udst", "methods.udst_se", "methods.r2_cap",
    "methods.tolerance", "methods.draws", "methods.c", "methods.alpha", "methods.z",
    "methods.ci_level", "methods.central_draws", "methods.fieller", "methods.sat_share",
    "methods.sat_level", "methods.registration", "methods.n_deviations", "methods.python",
    "methods.pdfplumber",
]

# Headline numbers that the abstract itself must carry (checked inside the abstract).
ABSTRACT_REQUIRED = [
    "q1.missing_points", "q1.R2.in_band", "q1.R2.max_violation", "q1.verdict",
    "q2.R2.1_weights.c63.spearman_range",
    "q3.R2.primary.rho_ci", "q3.R2.primary.n",
    "q4.R2.all.exceeds",
]


def want(root: Path = ROOT, required: list[str] = REQUIRED) -> dict[str, str]:
    """label -> expected string that the manuscript must contain (the REQUIRED labels)."""
    cat = catalogue_cached(root)
    out: dict[str, str] = {}
    for pat in required:
        hits = fnmatch.filter(cat, pat)
        if not hits:
            raise KeyError(f"REQUIRED label matches nothing in the catalogue: {pat}")
        out.update({k: cat[k] for k in hits})
    return out


# --------------------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------------------
# Numbers in the prose that are not results: years, exhibit and section numbers,
# reference superscripts, rule, question and indicator names, the AI model's version.
# Each entry must match a non-result number only, and must not swallow a neighbouring
# number: every digit run ends at a non-digit (END).
END = r"(?![\d]|[.,]\d)"
YEAR = r"20(?:19|2[0-6])"  # the years the study refers to, 2019 to 2026, and no others
EXHIBIT_NO = r"[IVX\d]+(?:\.\d+)?" + END
ALLOW = [
    rf"(?<![\d.,]){YEAR}(?:[–-](?:20)?(?:19|2[0-6]))?{END}",  # 2023, 2019–21, 2022-2023
    r"95% CI",
    rf"\b(?:Table|Figure|Web table|Web figure)s? {EXHIBIT_NO}(?:(?:–| and ){EXHIBIT_NO})*",
    rf"(?:annexure|Annexure)s? \d+(?:\.\d+)?{END}",
    rf"§\d+(?:\.\d+)*{END}",  # plan sections
    r"\^[\d,–-]+\^",  # pandoc superscript reference numbers
    r"\bR[1-4]\b",  # scoring rule names
    rf"\b[Ii]ndicators? [1-9]{END}(?:(?:, and |, | and |–)[1-9]{END})*",  # indicator numbers
    r"\bQ[1-4]\b",
    r"\bClaude Opus \d+(?:\.\d+)?\b",  # the AI model's name (Methods disclosure)
]
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
# a number token of the skeleton: thousands separators kept, list commas not ("4,5" is two)
SKEL_NUMBER = re.compile(r"\d+(?:,\d{3}(?!\d))*(?:\.\d+)?")


def _token(s: str) -> re.Pattern:
    """s as a whole token: not inside a longer number and not after a minus sign or hyphen
    (so "−0.48" does not satisfy "0.48": a sign flip is a changed number)."""
    return re.compile(r"(?<![\d.,−-])" + re.escape(s) + r"(?![\d]|[.,]\d)")


def _maskable(s: str) -> bool:
    """A catalogue string masks prose only if it is specific. A bare one- or two-digit
    integer (a rank change, a count) would mask every such number in the text, so it
    must be quoted through a label that carries words around it."""
    return not re.fullmatch(r"\d{1,2}", s)


def missing(text: str, wants: dict[str, str]) -> list[tuple[str, str]]:
    """(label, expected) for every expected string absent from text."""
    return [(k, v) for k, v in wants.items() if not _token(v).search(text)]


def prose(text: str) -> str:
    """The text that is scanned for numbers: everything before the References heading,
    and the Legends to Figures section, without table rows. The references (citation
    data) and the tables (rendered from outputs/, checked by stale_tables and
    tables_not_inserted) are not scanned."""
    out, scan = [], True
    for ln in text.splitlines():
        if re.match(r"^#+\s*References\b", ln.strip()):
            scan = False
        elif re.match(r"^#+\s*Legends to Figures\b", ln.strip()):
            scan = True
        if scan and not ln.lstrip().startswith("|"):
            out.append(ln)
    return "\n".join(out)


def section(text: str, heading: str) -> str:
    """The lines under a '#' heading, up to the next heading of any level ('' if absent)."""
    out, inside = [], False
    for ln in text.splitlines():
        if re.match(r"^#+\s", ln):
            if inside:
                break
            inside = re.match(rf"^#+\s*{re.escape(heading)}\b", ln) is not None
            continue
        if inside:
            out.append(ln)
    return "\n".join(out)


def unaccounted(text: str, wants: dict[str, str], allow: list[str] = ALLOW) -> list[str]:
    """Numbers left in the prose after masking every specific expected string and ALLOW."""
    t = prose(text)
    for v in sorted({v for v in wants.values() if _maskable(v)}, key=len, reverse=True):
        t = _token(v).sub(" ", t)
    for pat in allow:
        t = re.sub(pat, " ", t)
    return NUMBER.findall(t)


def stale_tables(root: Path) -> str | None:
    """Return a message if manuscript/tables.md differs from a fresh make_tables rendering."""
    script = root / "exhibits" / "make_tables.py"
    tables = root / "manuscript" / "tables.md"
    if not (script.exists() and tables.exists()):
        return None
    spec = importlib.util.spec_from_file_location("make_tables", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if mod.render(root) != tables.read_text(encoding="utf-8"):
        return "manuscript/tables.md is stale: re-run python -I exhibits/make_tables.py"
    return None


def tables_not_inserted(root: Path, text: str) -> str | None:
    """Return a message if manuscript.md does not carry tables.md verbatim (comments aside)."""
    tables = root / "manuscript" / "tables.md"
    if not tables.exists():
        return None
    body = "\n".join(ln for ln in tables.read_text(encoding="utf-8").splitlines()
                     if not ln.startswith("<!--")).strip()
    if body not in text:
        return "manuscript.md does not carry manuscript/tables.md verbatim: re-insert the tables"
    return None


# --------------------------------------------------------------------------------------
# Whole-phrase requirements per section, label and year checks, and a golden
# skeleton of every number token
# --------------------------------------------------------------------------------------
# Each phrase is a literal with {label} placeholders filled from catalogue(); it must occur
# whole inside its own section (so "0.82" -> "0.83" or "n = 19" -> "n = 34" fails: the
# label's words plus the value are required, not the value alone). Every number-bearing
# phrase of the Abstract and the Results is listed.
SECTION_REQUIRED: dict[str, list[str]] = {
    "Abstract": [
        "India TB Reports 2023 and 2024",
        "National TB Prevalence Survey 2019–21",
        "the 2023 scores were rebuilt",
        "Two indicators ({q1.missing_points})",
        "(closest: {q1.R2.in_band} states; largest excess {q1.R2.max_violation} points)",
        "ρ with the published ranking {q2.R2.1_weights.c63.spearman_range} over the "
        "{methods.central_draws}",
        "ρ {q3.R2.primary.rho_ci}, {q3.R2.primary.n} units",
        "Between 2022 and 2023, {q4.R2.all.exceeds} states changed by more than noise",
        "(exploratory analysis)",
    ],
    "Methods": [
        "{methods.total_points}", "{methods.udst}", "{methods.udst_se}", "{methods.r2_cap}",
        "{methods.tolerance}", "{methods.draws}", "{methods.c}", "{methods.alpha}",
        "{methods.z}", "{methods.ci_level}", "{methods.fieller}", "{methods.sat_share}",
        "{methods.sat_level}", "{methods.registration}", "{methods.n_deviations}",
        "{methods.python}", "{methods.pdfplumber}", "by {pop.diff}", "score year 2020",
        "as the plan records (§4)", "One exploratory analysis, not pre-specified",
        "({ind3.table11_1_share} ÷ {ind3.annexure_share})",
    ],
    "Results": [
        "worth {q1.missing_points}, are not published by state (Table I)",
        "Of the {q1.n_published}, Karnataka",
        "its indicator 5 denominator is blank",
        "the residual lay in the band for {q1.R2.in_band} states",
        "(Figure 1)",
        "(R4 could not be tested)",
        "R2 was carried into Q2–Q4",
        "ρ with the published ranking was {q2.R2.1_weights.c63.spearman_range} over the "
        "{methods.central_draws} (Table III)",
        "Leaving out indicator 1 or indicator 3",
        "leaving out indicator 4",
        "Web tables 1 and 2", "Web table 3",
        "The survey prints {q3.units_printed}, from {q3.clusters}",
        "{q3.units_analysed} representing {q3.states_covered} were analysed",
        "{q3.survey_excluded} not covered, and {q3.survey_not_named} not named by the survey",
        "In the exploratory analysis, with indicator 3 scaled to CTD's national figure, "
        "{explore.R2.in_band} states lay in the band under R2; the exception, "
        "{explore.R2.outside}, lay below it",
        "was ρ {q3.R2.primary.rho_ci}, {q3.R2.primary.n} (Table IV, Figure 3)",
        "{ctx.died.national} patients of the 2022 cohort died",
        "and {ctx.ltfu.national} were lost to follow-up",
        "across the {ctx.n_states}, death had a {ctx.died.states}",
        "loss to follow-up a {ctx.ltfu.states}",
        "Between 2022 and 2023, {q4.R2.all.exceeds} states changed by more than noise "
        "(Table IV, Figure 4)",
        "its 2023 SE could not be computed",
        "Web table 4",
    ],
    "Discussion": [
        "{q4.se0_counts}", "{q4.se0_cause}", "{q4.ind4_error.a}",
        "the {q4.ind4_error.counts} are divided by the {q4.ind4_error.denominator}",
        "brought {explore.R2.in_band} states into the band under R2 (exploratory)",
        "{q3.survey_not_named} is not named by the survey",
        "{q4.R2.no1.rho_ci}",
        "and {q4.R1.no1.rho_context}", "{ind3.annexure_share} against {ind3.table11_1_share} of notified patients",
        "Q3 rests on {q3.units_analysed}", "the survey (2019–21)",
        "not from the {q4.R2.all.rho_n} association",
    ],
}
SECTION_ORDER = ("Abstract", "Methods", "Results", "Discussion", "Legends to Figures")
SKELETON = "number_skeleton.json"
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4}
# Year phrases are pinned in SECTION_REQUIRED (report years 2023 and 2024, change years
# 2022 and 2023, survey span 2019-21). Every other year in a checked section must be one of:
YEARS_ALLOWED = {"2019", "2021", "2022", "2023", "2024"}


@lru_cache(maxsize=4)
def catalogue_cached(root: Path) -> dict[str, str]:
    return catalogue(root)


def fill(template: str, cat: dict[str, str]) -> str:
    """Substitute {label} placeholders with the catalogue strings."""
    return re.sub(r"\{([^}]+)\}", lambda m: cat[m.group(1)], template)


def squash(s: str) -> str:
    return re.sub(r"\s+", " ", s)


def phrase_problems(text: str, root: Path) -> list[str]:
    """Required whole phrases missing from their own section."""
    cat = catalogue_cached(root)
    out = []
    for sec, phrases in SECTION_REQUIRED.items():
        body = squash(section(text, sec))
        for ph in phrases:
            want_s = squash(fill(ph, cat))
            if not _token(want_s).search(body):
                out.append(f"MISSING in {sec}: {want_s!r}")
    return out


ROMAN_LIST = re.compile(r"\bTables? ([IVX]+\b(?:(?:–| and |, )[IVX]+\b)*)")


def skel_spans(s: str) -> list[tuple[int, int, str]]:
    """(start, end, token) of the skeleton tokens of `s`, in order: every number, and the
    Roman numerals of Table citations (Tables are numbered I-IV, so a swap of one cited
    table for another is a change of token like any other)."""
    out = [(m.start(), m.end(), m.group()) for m in SKEL_NUMBER.finditer(s)]
    for m in ROMAN_LIST.finditer(s):
        out += [(m.start(1) + r.start(), m.start(1) + r.end(), r.group())
                for r in re.finditer(r"[IVX]+", m.group(1))]
    return sorted(out)


def skeleton(text: str) -> dict[str, list[str]]:
    """The ordered tokens of each checked section, nothing masked."""
    return {sec: [t for _, _, t in skel_spans(section(text, sec))] for sec in SECTION_ORDER}


def skeleton_problems(text: str, root: Path) -> list[str]:
    path = root / "manuscript" / SKELETON
    if not path.exists():
        return [f"{SKELETON} missing: after review run "
                "python -I verification/check_manuscript_numbers.py --regenerate"]
    gold = json.loads(path.read_text(encoding="utf-8"))
    now = skeleton(text)
    out = []
    for sec in SECTION_ORDER:
        a, b = gold.get(sec, []), now[sec]
        if a != b:
            k = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
            now_tok = b[k] if k < len(b) else "(none)"
            gold_tok = a[k] if k < len(a) else "(none)"
            out.append(f"SKELETON {sec}: token {k + 1} is {now_tok!r}, golden has {gold_tok!r} "
                       f"({len(b)} tokens now, {len(a)} in the golden file)")
    return out


def _nums(group: str, roman: bool) -> list[int]:
    """'I', 'I and II', 'I–IV' or '1, 2' to integers (a dash is an inclusive range)."""
    toks = re.findall(r"[IVX]+|\d+", group)
    vals = [ROMAN.get(t, 0) if roman else int(t) for t in toks]
    if "–" in group and len(vals) == 2:
        return list(range(vals[0], vals[1] + 1))
    return vals


def citations(text: str) -> dict[str, list[int]]:
    """Exhibit citations in reading order, by type, from the prose (Abstract to Legends)."""
    t = prose(text)
    t = re.sub(r"(?m)^\*\*(?:Figure|Table|Web table) [IVX\d]+\.\*\*", " ", t)  # legend labels
    t = re.sub(r"(?m)^#+.*$", " ", t)
    found: dict[str, list[int]] = {"Table": [], "Figure": [], "Web table": []}
    arabic = r"\d+(?![\d.]\d)"  # "Table 11.2" is a table of the source report, not ours
    for word, kind, item in (("Web tables?", "Web table", arabic),
                             ("Tables?", "Table", r"[IVX]+\b"), ("Figures?", "Figure", arabic)):
        pat = re.compile(rf"(?<!Web )\b{word} ({item}(?:(?:–| and |, ){item})*)")
        for m in pat.finditer(t):
            found[kind] += _nums(m.group(1), kind == "Table")
    return found


def exhibit_problems(text: str) -> list[str]:
    """Cited exhibits exist, are first cited in ascending order, and each is cited."""
    out = []
    have = {
        "Table": {ROMAN[r] for r in re.findall(r"(?m)^\*\*Table ([IVX]+)\.", text) if r in ROMAN},
        "Figure": {int(n) for n in re.findall(r"(?m)^\*\*Figure (\d+)\.\*\*", text)},
        "Web table": {int(n) for n in re.findall(r"(?m)^\*\*Web table (\d+)\.", text)},
    }
    for kind, nums in citations(text).items():
        if have[kind] != {1, 2, 3, 4}:
            out.append(f"EXHIBITS: {kind} captions found {sorted(have[kind])}, expected 1-4")
        bad = sorted({n for n in nums if n not in have[kind]})
        if bad:
            out.append(f"EXHIBITS: {kind} {bad} cited but not present")
        first = list(dict.fromkeys(nums))
        if first != sorted(first):
            out.append(f"EXHIBITS: first citations of {kind}s out of order: {first}")
        never = sorted(have[kind] - set(nums))
        if never:
            out.append(f"EXHIBITS: {kind} {never} never cited in the text")
    return out


def label_problems(text: str, root: Path) -> list[str]:
    """Q in 1-4, R in 1-4 (R4 is the threshold-band rule, stated untestable), indicators
    in 1-9, and years from the data-tied set."""
    t = re.sub(r"(?m)^#+.*$", " ", prose(text))
    out = []
    for q in re.findall(r"\bQ(\d+)", t):
        if not 1 <= int(q) <= 4:
            out.append(f"LABEL: Q{q} outside Q1-Q4")
    for r in re.findall(r"\bR(\d+)\b", t):
        if not 1 <= int(r) <= 4:
            out.append(f"LABEL: R{r} outside R1-R4")
    for m in re.finditer(r"\b[Ii]ndicators? (\d+(?:(?:, and |, | and |–)\d+)*)", t):
        for n in re.findall(r"\d+", m.group(1)):
            if not 1 <= int(n) <= 9:
                out.append(f"LABEL: indicator {n} outside 1-9")
    reg_years = set(re.findall(r"\b20\d\d\b", catalogue_cached(root)["methods.registration"]))
    for sec in SECTION_ORDER:
        body = section(text, sec).replace("2019–21", " ").replace("score year 2020", " ")  # pinned above
        for y in re.findall(r"(?<![\d.,])(20\d\d)(?!\d)", body):
            if y not in YEARS_ALLOWED | reg_years:
                out.append(f"LABEL: year {y} in {sec} is not tied to the data")
    return out


def problems(root: Path, text: str) -> list[str]:
    """Every problem found in `text` taken as the manuscript (empty if clean)."""
    out = []
    for label, v in missing(text, want(root)):
        out.append(f"MISSING {label}: {v!r}")
    abstract = section(text, "Abstract")
    if not abstract.strip():
        out.append("MISSING the abstract (no '## Abstract' section)")
    else:
        for label, v in missing(abstract, want(root, ABSTRACT_REQUIRED)):
            out.append(f"MISSING in the abstract {label}: {v!r}")
    for n in unaccounted(text, catalogue_cached(root)):
        out.append(f"UNACCOUNTED number in prose: {n!r}")
    out += phrase_problems(text, root)
    out += exhibit_problems(text)
    out += label_problems(text, root)
    out += skeleton_problems(text, root)
    for msg in (stale_tables(root), tables_not_inserted(root, text)):
        if msg:
            out.append(msg)
    return out


def main(root: Path = ROOT, argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not (root / "manuscript").is_dir():
        print(SKIP_DIR)
        return 0
    ms = root / "manuscript" / "manuscript.md"
    if not ms.exists():
        print(SKIP_MS)
        return 0
    text = ms.read_text(encoding="utf-8")
    if "--regenerate" in argv:
        gold = skeleton(text)
        (root / "manuscript" / SKELETON).write_text(
            json.dumps(gold, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote manuscript/{SKELETON}: " + ", ".join(f"{k} {len(v)}" for k, v in gold.items()))
        return 0
    found = problems(root, text)
    for ln in found:
        print(ln)
    n_ph = sum(len(v) for v in SECTION_REQUIRED.values())
    print(f"{len(want(root))} expected strings ({len(want(root, ABSTRACT_REQUIRED))} in the "
          f"abstract), {n_ph} section phrases; {len(found)} problem(s)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())

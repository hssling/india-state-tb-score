"""Check every number in the manuscript against the committed outputs.

Run as: python -I verification/check_manuscript_numbers.py

The manuscript (manuscript/, git-ignored) is kept private until an editorial
decision. Ruling R6: when manuscript/ is absent this prints
"SKIPPED: manuscript/ not present (kept private until a decision)" and exits 0, and
check_all counts the step as skipped. It is also skipped while manuscript/ exists but
manuscript/manuscript.md has not been written.

When manuscript/manuscript.md is present, three checks run:

1. every expected string from want() (the REQUIRED labels of the catalogue) occurs in
   the manuscript, as a whole token (not as part of a longer number);
2. every number in the prose is accounted for: after every catalogue string and the
   ALLOW patterns are masked out, no digit may remain. Markdown table rows (lines
   starting with "|", which make_tables.py generates) and everything from the
   "References" heading on are not scanned. A changed number therefore fails twice:
   its expected string goes missing and the changed value is unaccounted;
3. if manuscript/make_tables.py and manuscript/tables.md exist, tables.md equals a
   fresh rendering (so the tables are not stale against outputs/).

catalogue() is a dict of label -> string, derived from outputs/ and data/ only; want()
is its REQUIRED subset.
Number formats (decimals, the minus sign U+2212, en dash ranges, thousands
separators) are fixed once, in the "Number formats" section below, and
manuscript/make_tables.py imports the same helpers, so the text and the tables
cannot drift apart in format. As the prose takes shape, add labels to catalogue() and
list the ones the text must carry in REQUIRED.
Exit 1 on any failure.
"""
from __future__ import annotations

import csv
import fnmatch
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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
        "verdict": grab(r"^Verdict: (\w+)$"),
    }


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
            "diff_pct": num(100 * (total - india) / india, 3) + "%"}


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
    w["q1.target.relative"] = pct(tc["difference"], tc["target"], 2)

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
        if r["rule"] == sel["chosen"] and iset == "all":
            w["q4.excluded"] = r["excluded"].split(" (")[0]
            w["q4.se0_2022"] = count(int(r["n_states_se0_2022"]))
            w["q4.se0_2023"] = count(int(r["n_states_se0_2023"]))
    return w


# Labels (fnmatch patterns) whose strings MUST appear in the manuscript. The rest of the
# catalogue may appear (it is accounted for in the number scan) but is not required,
# because IJMR forbids repeating table and figure data in the text. Part b edits this
# list as the prose takes shape.
REQUIRED = [
    "q1.verdict", "q1.n_published", "q1.missing_indicators", "q1.missing_points",
    "q1.excluded", "q1.R2.in_band", "q1.R2.max_violation",
    "ind3.annexure_share", "ind3.table11_1_share",
    "pop.diff",
    "q2.R2.1_weights.c63.spearman_range",
    "q3.R2.primary.rho_ci", "q3.R2.primary.n", "q3.R2.secondary.rho_ci", "q3.R2.secondary.n",
    "q3.units_analysed", "q3.states_covered", "q3.not_covered",
    "q4.R2.all.exceeds", "q4.R2.all.rho_ci", "q4.R2.all.rho_n", "q4.R2.no1.exceeds",
    "q4.excluded",
]


def want(root: Path = ROOT, required: list[str] = REQUIRED) -> dict[str, str]:
    """label -> expected string that the manuscript must contain (the REQUIRED labels)."""
    cat = catalogue(root)
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
# Numbers in the prose that are not results: years, section and exhibit numbers,
# confidence levels, reference superscripts. Part b extends this list deliberately;
# each entry must be a non-result number.
ALLOW = [
    r"(?<![\d.,])(?:19|20)\d\d(?:[–-](?:19|20)?\d\d)?(?![\d.,]\d)",  # years, 2019-21
    r"95% CI",
    r"\b(?:Table|Figure|Web table|Web figure)s? [IVX\d]+(?:\.\d+)?",
    r"(?:annexure|Annexure) \d+(?:\.\d+)?",
    r"§\d+(?:\.\d+)*",  # plan sections
    r"\^[\d,–-]+\^",  # pandoc superscript reference numbers
    r"\bR[1-4]\b",  # scoring rule names
    r"\b[Ii]ndicators? \d(?:(?:, | and |–)\d)*",  # indicator numbers
    r"\bQ[1-4]\b",
]
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _token(s: str) -> re.Pattern:
    """s as a whole token: not inside a longer number."""
    return re.compile(r"(?<![\d.,])" + re.escape(s) + r"(?![\d]|[.,]\d)")


def missing(text: str, wants: dict[str, str]) -> list[tuple[str, str]]:
    """(label, expected) for every expected string absent from text."""
    return [(k, v) for k, v in wants.items() if not _token(v).search(text)]


def prose(text: str) -> str:
    """The text that is scanned for numbers: no table rows, nothing from References on."""
    out = []
    for ln in text.splitlines():
        if re.match(r"^#+\s*References\b", ln.strip()):
            break
        if not ln.lstrip().startswith("|"):
            out.append(ln)
    return "\n".join(out)


def unaccounted(text: str, wants: dict[str, str], allow: list[str] = ALLOW) -> list[str]:
    """Numbers left in the prose after masking every expected string and ALLOW pattern."""
    t = prose(text)
    for v in sorted(set(wants.values()), key=len, reverse=True):
        t = _token(v).sub(" ", t)
    for pat in allow:
        t = re.sub(pat, " ", t)
    return NUMBER.findall(t)


def stale_tables(root: Path) -> str | None:
    """Return a message if manuscript/tables.md differs from a fresh make_tables rendering."""
    script = root / "manuscript" / "make_tables.py"
    tables = root / "manuscript" / "tables.md"
    if not (script.exists() and tables.exists()):
        return None
    spec = importlib.util.spec_from_file_location("make_tables", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if mod.render(root) != tables.read_text(encoding="utf-8"):
        return "manuscript/tables.md is stale: re-run python -I manuscript/make_tables.py"
    return None


def main(root: Path = ROOT) -> int:
    if not (root / "manuscript").is_dir():
        print(SKIP_DIR)
        return 0
    ms = root / "manuscript" / "manuscript.md"
    if not ms.exists():
        print(SKIP_MS)
        return 0
    text = ms.read_text(encoding="utf-8")
    wants = want(root)
    bad = 0
    for label, v in missing(text, wants):
        print(f"MISSING {label}: {v!r}")
        bad += 1
    for n in unaccounted(text, catalogue(root)):
        print(f"UNACCOUNTED number in prose: {n!r}")
        bad += 1
    msg = stale_tables(root)
    if msg:
        print(msg)
        bad += 1
    print(f"{len(wants)} expected strings; {bad} problem(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

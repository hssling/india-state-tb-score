"""Render every manuscript table from outputs/ and data/ to manuscript/tables.md.

Run as: python -I exhibits/make_tables.py [--profile ijmr|jph]   (from the repository root)

The manuscript itself is kept private until an editorial decision (manuscript/ is not in
the repository); this script is deposited so that every table can be regenerated from the
committed outputs.

Every number is read from the committed files and formatted with the helpers of
verification/check_manuscript_numbers.py, so the tables and the number check share
one set of formats. No number is typed here. The short phrases of Table I (sources
and noted mismatches) are written here, and each is guarded by an assertion on the
source note it summarises, so a changed source choice stops the rendering instead
of leaving a stale phrase.

IJMR (Instructions for Authors): tables numbered with Roman numerals; 3-5 columns and 4-16
rows for the four main tables; footnote symbols *, dagger, double dagger, section;
items that do not fit go online as web tables.

Profiles (--profile): "ijmr" (default) writes manuscript/tables.md as above. "jph" (Journal of
Public Health) writes manuscript/jph_v2/tables.md with the same tables and numbers, numbered
in Arabic numerals: Table 1 (robustness) in the text, and Supplementary Tables S1-S10 online
in first-citation order, including (JPH only) the plan's section 13 log, the post hoc analyses
(plan section 13, 20 November 2026) and the change by state. LABELS holds each profile's exhibit names and order.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import inspect  # noqa: E402

from src.q1_reproduce import TOL  # noqa: E402
from src.q2_robust import N_DRAWS, SAT_LEVEL, SEED, saturation_table  # noqa: E402
from src.q4_change import Z975  # noqa: E402
from src.score import POINTS, UDST_BENCHMARK  # noqa: E402
from verification.check_manuscript_numbers import (  # noqa: E402
    DP, EN_DASH, MINUS, count, pct, k_of_n, k_of_n_pct, listing, num, population_check, q1_selection,
    q3_excluded, rank, read_csv, target_check, target_relative, rho, rng, indicator3_contrast,
)

FOOT = ["*", "†", "‡", "§", "‖", "¶"]

# Exhibit names by profile. Keys: ind (indicators), repro (Q1 by rule), robust (Q2, primary
# rule), valid (Q3 and Q4 by rule), rob_R1 / rob_R3 (Q2 under the other rules), resid (Q1
# residuals by state), scores (Q4 scores by state), and the figures. "order" is the order of
# the blocks ("SUPP" is the heading of the online tables), "main" the main-text tables.
LABELS = {
    "ijmr": {
        "ind": "Table I", "repro": "Table II", "robust": "Table III", "valid": "Table IV",
        "rob_R1": "Web table 1", "rob_R3": "Web table 2", "resid": "Web table 3",
        "scores": "Web table 4", "fig_resid": "Figure 1", "fig_change": "Figure 4",
        "data": "data sharing statement", "SUPP": "# Web tables",
        "order": ("ind", "repro", "robust", "valid", "SUPP", "rob_R1", "rob_R3", "resid",
                  "scores"),
        "main": ("ind", "repro", "robust", "valid"),
        "out": "manuscript/tables.md",
    },
    "jph": {
        "log": "Supplementary Table S1", "ind": "Supplementary Table S2",
        "repro": "Supplementary Table S3", "robust": "Table 1",
        "resid": "Supplementary Table S4", "rob_R1": "Supplementary Table S5",
        "rob_R3": "Supplementary Table S6", "valid": "Supplementary Table S7",
        "posthoc": "Supplementary Table S8", "change": "Supplementary Table S9",
        "scores": "Supplementary Table S10", "fig_resid": "Figure 1", "fig_change": "Figure 3",
        "fig_fifths": "Supplementary Figure S1",
        "data": "Data Availability Statement", "SUPP": "# Supplementary tables",
        "order": ("robust", "SUPP", "log", "ind", "repro", "resid", "rob_R1", "rob_R3",
                  "valid", "posthoc", "change", "scores"),
        "main": ("robust",),
        "out": "manuscript/jph_v2/tables.md",
        # JPH only (after peer review): the flat Dirichlet is centred on equal weights, not
        # on CTD's; the plan 9.3 descriptive context is given in the validity table's note
        "flat_label": True, "ctx_note": True,
    },
}
IJMR_LABELS = LABELS["ijmr"]


def both(a: str, b: str) -> str:
    """'Tables III and IV' for two tables of one kind, else 'Table 1 and Supplementary Table S6'."""
    if a.startswith("Table ") and b.startswith("Table "):
        return f"Tables {a.split(' ', 1)[1]} and {b.split(' ', 1)[1]}"
    return f"{a} and {b}"
TIMES = "×"
ALPHA = "α"
RHO = "ρ"


def rho_ci_cell(r: float, lo: float, hi: float) -> str:
    """Table cell: rho (lo to hi); the column or row label says '(95% CI)'."""
    return f"{rho(r)} ({rng(rho(lo), rho(hi))})"


# --------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------
def md_table(header: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def block(title: str, header, rows, notes: list[str], main: bool = True) -> str:
    if main:
        ncol, nrow = len(header), len(rows)
        assert 3 <= ncol <= 5, f"{title}: {ncol} columns (IJMR: 3-5)"
        assert 4 <= nrow <= 16, f"{title}: {nrow} rows (IJMR: 4-16)"
    # footnote asterisks in titles and notes are escaped so Markdown cannot read them
    # as emphasis ("rule*" before the closing "**", "*Indicator ..." at line start)
    def esc(t: str) -> str:
        return t.replace("*", "\\*")

    notes = [esc(n) for n in notes]
    parts = [f"**{esc(title)}**", "", md_table(header, rows), ""]
    parts += [n + "  " for n in notes[:-1]] + notes[-1:]
    return "\n".join(parts).rstrip() + "\n"


def plan_indicators(root: Path) -> dict[int, tuple[int, str]]:
    """Indicator number -> (points, name) from the plan's section 5.1 table."""
    text = (root / "docs" / "analysis_plan.md").read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r"^\| ([1-9]) \| (\d+) \| ([^|]+?) \|", text, re.M):
        out[int(m.group(1))] = (int(m.group(2)), m.group(3).strip())
    assert sorted(out) == list(range(1, 10)), "plan 5.1 table not parsed"
    for i, (pts, _) in out.items():
        assert pts == POINTS[i], f"plan points for indicator {i} differ from src/score.py"
    return out


def choices(root: Path) -> dict[tuple[str, str, str], dict]:
    return {(r["score_year"], r["indicator"], r["component"]): r
            for r in read_csv(root / "data" / "source_choices.csv")}


def annex(table_id: str) -> str:
    m = re.fullmatch(r"Annexure (\d+(?:\.\d+)?)", table_id)
    assert m, table_id
    return "A" + m.group(1)


# --------------------------------------------------------------------------------------
# Table I: the nine indicators
# --------------------------------------------------------------------------------------
MISSING_REASON = {
    "no_source": "Missing: no state-wise source",
    "no_denominator": "Missing: no table with the defined denominator",
    "total_check": "Missing: state rows do not sum to the printed India row",
}


def source_cell(ch: dict, year: str, i: int) -> str:
    num_r, den_r = ch[(year, str(i), "numerator")], ch[(year, str(i), "denominator")]
    if num_r["table_id"] == "not located":
        assert den_r["table_id"] == "not located"
        return MISSING_REASON["no_source"]
    if num_r["table_id"] == "missing":
        assert "denominator" in num_r["note"] and den_r["table_id"] == "missing"
        return MISSING_REASON["no_denominator"]
    if num_r["note"].startswith("NOT EXTRACTED"):
        assert "printed-total" in num_r["note"]
        return MISSING_REASON["total_check"]
    den = annex(den_r["table_id"])
    if i == 3:
        den = f"{num(UDST_BENCHMARK, 1)} {TIMES} {den}†"
    return f"{annex(num_r['table_id'])} ÷ {den}"


def mismatch_cell(ch: dict, defs: list[dict], i: int) -> str:
    """Noted definitional mismatches and judgement calls, each guarded by its source note."""
    def note(year, comp):
        return ch[(year, str(i), comp)]["note"]

    out = []
    if i == 1:
        assert "NOT PERFORMED" in note("2022", "denominator")
        out.append("2022: annexure 'target' column; national target not printed")
    if i in (2, 3, 4):
        assert "JUDGEMENT CALL" in note("2022", "denominator")
        out.append("2022: net notified taken as the by-sex total of A1.6 (no 'net' column)")
    if i == 3:
        assert "DEFINITIONAL MISMATCH (not pre-specified" in note("2023", "numerator")
        out.insert(0, "Numerator counts bacteriologically confirmed patients only "
                      "(not pre-specified)‡")
    if i == 4:
        d21 = next(d for d in defs if (d["edition"], d["indicator_no"]) == ("2021", "4"))
        assert d21["note"].startswith("DIFFERS")
        out.insert(0, "Same-period denominator, as defined; the 2021 edition's "
                      "previous-year cohort is tested in Q2")
    if i == 5:
        assert "'paid at least once' is printed and is used" in note("2023", "numerator")
        assert "Karnataka" in note("2023", "denominator")
        out.append("'Paid at least once', as defined; Karnataka denominator blank")
    if i == 6:
        assert "JUDGEMENT CALL" in note("2023", "numerator")
        out.append("'Initiated on treatment' column, not 'second-line'")
    if i == 8:
        assert "DEFINITIONAL MISMATCH (§5.5)" in note("2023", "numerator")
        out.append("Household contacts <5 y given TPT, not children <6 y given "
                   "isoniazid (pre-specified)")
    return "; ".join(out) if out else "—"


def table1(root: Path, L: dict = IJMR_LABELS) -> str:
    ind = plan_indicators(root)
    ch = choices(root)
    defs = read_csv(root / "data" / "extracted" / "definitions.csv")
    t71 = next(d for d in defs if (d["edition"], d["indicator_no"]) == ("2023", "total"))
    rows = []
    for i in range(1, 10):
        pts, name = ind[i]
        rows.append([f"{i}. {name}", count(pts), source_cell(ch, "2023", i),
                     source_cell(ch, "2022", i), mismatch_cell(ch, defs, i)])
    sel = q1_selection(root)
    miss23 = [i for i in range(1, 10) if rows[i - 1][2].startswith("Missing")]
    miss22 = [i for i in range(1, 10) if rows[i - 1][3].startswith("Missing")]
    assert miss23 == sel["missing_indicators"], "Table I and Q1 disagree on missing indicators"
    pts23 = sum(POINTS[i] for i in miss23)
    pts22 = sum(POINTS[i] for i in miss22)
    notes = [
        f"*Definitions: Central TB Division, ntep.in/node/1662, restated in India TB Report "
        f"2023, Table 7.1 (PDF p. {t71['source_page']}). Sources are annexures (A) of the "
        f"India TB Report 2024 (score year 2023) and 2023 (score year 2022), as numerator "
        f"÷ denominator; tables, columns and PDF pages are listed in the deposited "
        f"source-choice file. Points missing: {count(pts23)} in 2023 (indicators "
        f"{listing([str(i) for i in miss23])}), {count(pts22)} in 2022 (indicators "
        f"{listing([str(i) for i in miss22])}).",
        f"†The state benchmark of CTD's universal drug-susceptibility testing page: "
        f"{num(100 * UDST_BENCHMARK, 0)}% of net notified patients.",
        f"‡See {L['repro']}, footnote *.",
        "HIV, human immunodeficiency virus; IPT, isoniazid preventive therapy; MDR/RR-TB, "
        "multidrug- or rifampicin-resistant TB; PLHIV, people living with HIV; ROP, Record "
        "of Proceedings; TPT, TB preventive treatment; UDST, universal drug-susceptibility "
        "testing; y, years.",
    ]
    return block(f"{L['ind']}. The nine indicators of the State TB Score and their sources",
                 ["Indicator", "Points", "Score year 2023*", "Score year 2022*",
                  "Noted mismatch"], rows, notes, "ind" in L["main"])


# --------------------------------------------------------------------------------------
# Table II: Q1 by rule
# --------------------------------------------------------------------------------------
def table2(root: Path, L: dict = IJMR_LABELS) -> str:
    sel = q1_selection(root)
    mp = sel["missing_points"]
    rows = []
    for rule, d in sel["per_rule"].items():
        if "n_in_band" not in d:
            assert d["status"].startswith("not evaluable")
            rows.append([rule, "—", "—", "—", "Not tested§"])
            continue
        res = [s[rule]["residual"] for s in sel["per_state"].values()
               if not s[rule]["excluded"]]
        rows.append([rule, k_of_n(d["n_in_band"], d["n_compared"]),
                     num(d["max_violation"], DP["score"]),
                     rng(num(min(res), DP["score"]), num(max(res), DP["score"])),
                     "Yes" if d["admissible"] else "No"])
    c3 = indicator3_contrast(root)
    n = next(d["n_compared"] for d in sel["per_rule"].values() if "n_compared" in d)
    # plan 7.2: the states outside the band are listed for each rule; the primary rule's
    # list is printed here, R1 and R3 are marked in Web table 3
    q1rows = read_csv(root / "outputs" / "q1_2023.csv")
    outside = [r["state"] for r in q1rows
               if r["rule"] == sel["chosen"] and r["excluded"] == "0" and r["in_band"] == "0"]
    assert len(outside) == sel["per_rule"][sel["chosen"]]["n_compared"] -         sel["per_rule"][sel["chosen"]]["n_in_band"]
    tol = num(TOL, 2)
    notes = [
        f"*Indicator 3: the only state-wise column with a rifampicin result counts "
        f"{k_of_n(c3['k'], c3['n'])} net notified patients ({c3['share']}); Table 11.1 of the "
        f"same report prints {c3['printed']} of notified patients offered rifampicin "
        "sensitivity testing.",
        f"†Residual = published score (India TB Report 2024, Table 11.2) {MINUS} partial "
        f"score rebuilt from the {count(100 - mp)} points of the available indicators "
        f"({listing([str(i) for i in sel['available_indicators']])}). A state is inside the "
        f"admissibility band if {MINUS}{tol} ≤ residual ≤ {count(mp)} + {tol}, "
        f"{count(mp)} being the points of the missing indicators "
        f"({listing([str(i) for i in sel['missing_indicators']])}); a rule is admissible if "
        f"every state is inside. Violation: distance of a residual outside the band.",
        f"‡Verdict over R1{EN_DASH}R4: {sel['verdict']}. {listing(sel['excluded'])} "
        f"excluded (indicator 5 not computable); n = {count(n)}. {sel['chosen']} has the "
        f"smallest maximum violation and is carried into {both(L['robust'], L['valid'])}. "
        f"Outside the band "
        f"under {sel['chosen']} ({count(len(outside))} states): {listing(outside)}; under the "
        f"other rules, see {L['resid']}.",
        "§No Central TB Division document states threshold bands for R4.",
        "R1, proportional, capped at the indicator's maximum; R2, proportional, uncapped; "
        "R3, relative to the best state; R4, threshold bands.",
    ]
    return block(f"{L['repro']}. Reproducing the published 2023 scores, by scoring rule*",
                 ["Rule", "States inside the band†, n of N",
                  "Maximum violation (points)", "Residual range (points)",
                  "Admissible‡"], rows, notes, "repro" in L["main"])


# --------------------------------------------------------------------------------------
# Table III / web tables 1-2: Q2 by variant
# --------------------------------------------------------------------------------------
def q2_rows(root: Path, rule: str, flat_label: bool = False) -> tuple[list[list[str]], dict]:
    """flat_label (JPH): the alpha = 1 row is labelled as a flat Dirichlet, centred on equal
    weights (alpha_i = 1 for every i), not as weights drawn around CTD's."""
    rs = [r for r in read_csv(root / "outputs" / "q2_2023_summary.csv") if r["rule"] == rule]
    info = {"n": {r["n_compared"] for r in rs if r["n_compared"]}}
    rows = []
    order = (["base"] + ["1_weights"]
             + sorted(r["variant"] for r in rs if r["variant"].startswith("2_loo"))
             + ["4_matched_cohort", "3_burden", "5_saturated_removed"])
    for v in order:
        for r in [r for r in rs if r["variant"] == v]:
            if v == "base":
                rows.append([f"Base: rebuilt score ({rule}, rescaled partial)", "—",
                             "—", rho(float(r["spearman"]))])
            elif v == "1_weights":
                s = r["setting"]
                lab = (f"c = {count(int(s[1:]))}" if s.startswith("c")
                       else f"{ALPHA} = {count(int(s[5:]))} for each indicator")
                m = re.match(r"(\d+) draws; seed (\d+)", r["note"])
                info["draws"], info["seed"] = int(m.group(1)), m.group(2)
                name = (f"Weights from a flat Dirichlet, centred on equal weights ({lab})*"
                        if flat_label and not s.startswith("c")
                        else f"Weights drawn around CTD's ({lab})*")
                rows.append([
                    name,
                    f"{rank(float(r['median_change']))} "
                    f"({rng(rank(float(r['median_change_q1'])), rank(float(r['median_change_q3'])))})",
                    f"{rank(float(r['max_change']))} "
                    f"({rng(rank(float(r['max_change_q1'])), rank(float(r['max_change_q3'])))})",
                    f"{rho(float(r['spearman']))} "
                    f"({rng(rho(float(r['spearman_p2.5'])), rho(float(r['spearman_p97.5'])))})",
                ])
            elif v.startswith("2_loo"):
                i = v.rsplit("_", 1)[1]
                rows.append([f"Indicator {i} left out", rank(float(r["median_change"])),
                             rank(float(r["max_change"])), rho(float(r["spearman"]))])
            elif v == "4_matched_cohort":
                rows.append(["Treatment success on the matched cohort†",
                             rank(float(r["median_change"])), rank(float(r["max_change"])),
                             rho(float(r["spearman"]))])
            elif v == "3_burden":
                assert "dropped" in r["note"] and "AGREE" in r["note"]
                rows.append(["Notification against estimated burden‡", "Not run",
                             "Not run", "Not run"])
            elif v == "5_saturated_removed":
                assert r["note"] == "empty"
                rows.append(["Saturated indicators removed§", "Not run", "Not run",
                             "Not run"])
    unres = [r for r in rs if r["variant"] == "7.3_unrescaled_check"]
    assert unres and "rank-identical" in unres[0]["note"]
    assert len(info["n"]) == 1
    info["n"] = int(info["n"].pop())
    return rows, info


def q2_notes(root: Path, info: dict) -> list[str]:
    sat = read_csv(root / "outputs" / "q2_2023_saturation.csv")
    top = max(sat, key=lambda r: float(r["share_ge_0.95"]))
    tc_note = next(r for r in read_csv(root / "data" / "source_choices.csv")
                   if (r["score_year"], r["indicator"], r["component"]) == ("2023", "1", "denominator"))
    tc = target_check(root)
    assert tc["verdict"] == "AGREE" and "AGREE" in tc_note["note"]
    rel, tol = target_relative(root), tc["tolerance"]
    sel = q1_selection(root)
    assert (info["draws"], info["seed"]) == (N_DRAWS, str(SEED))
    # plan 8.1 item 5: saturated if >= 80% of states; src/q2_robust.py tests it as 5k >= 4n
    assert "5 * k >= 4 * len(vals)" in inspect.getsource(saturation_table)
    sat_share = pct(4, 5, 0)
    return [
        f"Rank changes are absolute changes against the base ranking; n = {count(info['n'])} "
        f"states and union territories ({listing(sel['excluded'])} not computable). {RHO} is "
        f"Spearman's rank correlation with the published 2023 ranking (Table 11.2). The "
        f"unrescaled partial score ranks every state identically to the rescaled score.",
        f"*Dirichlet weights, {count(info['draws'])} draws (fixed, pre-registered seed): median "
        f"(interquartile range) over draws of each rank-change measure; {RHO} as median "
        f"(2.5th{EN_DASH}97.5th percentile).",
        "†Previous year's notified cohort as the denominator of indicator 4.",
        f"‡Not run: the annexure 'expected' total agreed with the national target "
        f"(difference {rel}, tolerance {tol}), so no independent burden denominator exists.",
        f"§Not run: no indicator was saturated (achievement ≥{num(SAT_LEVEL, 2)} in at least "
        f"{sat_share} of states); the highest was indicator {top['indicator']}, at or above "
        f"{num(SAT_LEVEL, 2)} in "
        f"{k_of_n_pct(round(float(top['share_ge_0.95']) * int(top['n_computable'])), int(top['n_computable']))}"
        f" states.",
    ]


def table3(root: Path, rule: str, title: str, main: bool, flat_label: bool = False) -> str:
    rows, info = q2_rows(root, rule, flat_label)
    return block(title, ["Variant", "Median rank change", "Maximum rank change",
                         f"{RHO} with the published ranking"], rows, q2_notes(root, info), main)


# --------------------------------------------------------------------------------------
# Table IV: Q3 and Q4 by rule
# --------------------------------------------------------------------------------------
def table4(root: Path, L: dict = IJMR_LABELS) -> str:
    sel = q1_selection(root)
    rules = ["R1", "R2", "R3"]
    q3 = read_csv(root / "outputs" / "q3_2023_summary.csv")
    q4 = read_csv(root / "outputs" / "q4_2022_2023_summary.csv")

    def q3row(prefix, label):
        rs = {r["rule"]: r for r in q3 if r["analysis"].startswith(prefix)}
        ns = {rs[k]["n"] for k in rules}
        assert len(ns) == 1
        return ([label.format(n=count(int(ns.pop())))]
                + [rho_ci_cell(float(rs[k]["rho"]), float(rs[k]["lo"]), float(rs[k]["hi"]))
                   for k in rules])

    def q4rows(iset, label):
        rs = {r["rule"]: r for r in q4 if r["indicator_set"].startswith(iset)}
        n = {rs[k]["rho_n"] for k in rules}
        assert len(n) == 1
        return [
            [f"Q4, indicators {label}: change exceeds noise, n of N (%)"]
            + [k_of_n_pct(int(rs[k]["n_exceeds"]), int(rs[k]["n_compared"])) for k in rules],
            [f"Q4, indicators {label}: {RHO} (95% CI) of 2022 score with change "
             f"(n = {count(int(n.pop()))})"]
            + [rho_ci_cell(float(rs[k]["rho"]), float(rs[k]["rho_lo"]), float(rs[k]["rho_hi"]))
               for k in rules],
        ]

    sets = [r["indicator_set"] for r in q4 if r["rule"] == sel["chosen"]]
    full = next(s for s in sets if "excluded" not in s)
    no1 = next(s for s in sets if "excluded" in s).split(" (")[0]
    rows = [q3row("9.1", f"Q3: {RHO} (95% CI) with NTPS prevalence* "
                         "(n = {n} survey units)"),
            q3row("9.2", f"Q3: {RHO} (95% CI) with MDR/RR-TB treatment success† "
                         "(n = {n} states)")]
    rows += q4rows(full, full.replace(",", ", "))
    rows += q4rows(no1 + " ", no1.replace(",", ", ") + "‡")

    q3p = next(r for r in q3 if r["rule"] == sel["chosen"] and r["analysis"].startswith("9.1"))
    q3s = next(r for r in q3 if r["rule"] == sel["chosen"] and r["analysis"].startswith("9.2"))
    ex = q3_excluded(q3p["excluded"])
    q4p = next(r for r in q4 if r["rule"] == sel["chosen"] and r["indicator_set"] == full)
    pc = population_check(root)
    units = [u for u in read_csv(root / "outputs" / "q3_2023_units.csv")
             if u["rule"] == sel["chosen"]]
    groups = sum(u["unit_type"] == "group" and u["dropped"] == "0" for u in units)
    dr = {r["state"]: r for r in read_csv(root / "data" / "extracted" / "itr2024_drtb_outcomes.csv")}

    def _why(reason: str, state: str) -> str:
        if reason == "cohort blank or zero":  # say which, from the extracted cell
            return "cohort blank" if dr[state]["cohort_n"] == "" else "cohort zero"
        return reason
    sec_ex = [f"{p.split(': ')[1]} ({_why(p.split(': ')[0], p.split(': ')[1])})"
              for p in q3s["excluded"].split("; ")]
    notes = [
        f"Scores are rebuilt under each rule (rescaled partial score); "
        f"{sel['chosen']} is the primary rule. {RHO} is Spearman's rank correlation with a "
        f"Fisher-z 95% confidence interval (Fieller variance); no P values are computed. "
        f"Q4: a state's change exceeds noise if |change| > {num(Z975, 2)} {TIMES} its standard error; "
        f"{q4p['excluded'].split(' (')[0]} excluded (standard error not computable in 2023). "
        f"States with a zero-variance component: {count(int(q4p['n_states_se0_2022']))} in "
        f"2022, {count(int(q4p['n_states_se0_2023']))} in 2023.",
        f"*ICMR National TB Prevalence Survey 2019{EN_DASH}21, microbiologically confirmed "
        f"pulmonary TB per 100,000 aged ≥15 y, by state or state group "
        f"({count(groups)} groups, scored as population-weighted means). Not covered: "
        f"{listing(ex['not covered by the survey'])}; {listing(ex['unit dropped (no scored member)'])}"
        f" unit dropped (no score). Populations from annexure 1.2: the "
        f"{count(pc['n_units'])} units sum to {count(pc['sum'])} against India's "
        f"{count(pc['india'])} ({pc['diff_pct']}). Negative {RHO} is expected if the score "
        "tracks less TB.",
        f"†Annexure 4.13, by state; not in the score. Excluded: {listing(sec_ex)}.",
        "‡Indicator 1 excluded because its 2022 denominator could not be checked "
        "against a national target.",
        "ICMR, Indian Council of Medical Research; MDR/RR-TB, multidrug- or "
        "rifampicin-resistant TB; NTPS, National TB Prevalence Survey; y, years.",
    ]
    if L.get("ctx_note"):
        notes.insert(-1, ctx_note(root))
    return block(f"{L['valid']}. Validity (Q3, score year 2023) and change over time "
                 "(Q4, 2022 to 2023), by scoring rule",
                 ["Measure"] + [r + (" (primary)" if r == sel["chosen"] else "") for r in rules], rows, notes,
                 "valid" in L["main"])


# --------------------------------------------------------------------------------------
# Web tables 3-4: per-state values
# --------------------------------------------------------------------------------------
REPO_NOTE = ("Per-state values for every rule are in the deposited per-state output files "
             "(see the {data}).")


def web_q1(root: Path, L: dict = IJMR_LABELS) -> str:
    """R1 and R3 residuals only; the primary-rule residual is what Figure 1 plots, and
    IJMR forbids the same data in tabular and graphic form."""
    sel = q1_selection(root)
    rules = [r for r in sel["sensitivity_rules"] if r != sel["chosen"]]
    rows = []
    for st, d in sel["per_state"].items():
        row = [st, num(d[rules[0]]["published"], DP["score"])]
        for rule in rules:
            x = d[rule]
            row.append("Not computable" if x["excluded"] else
                       num(x["residual"], DP["score"]) + ("" if x["in_band"] else "*"))
        rows.append(row)
    mp = sel["missing_points"]
    notes = [f"Residual = published {MINUS} rebuilt partial score (points); the published "
             f"score (India TB Report 2024, Table 11.2) is given for reference. Rule "
             f"{sel['chosen']} is shown in {L['fig_resid']}. *Outside the admissibility band "
             f"({MINUS}{num(TOL, 2)} to {count(mp)} + {num(TOL, 2)} points). "
             f"{listing(sel['excluded'])}: indicator 5 not computable.",
             REPO_NOTE.format(data=L["data"])]
    return block(f"{L['resid']}. Residual of the published 2023 score by state, rules "
                 f"{listing(rules)}",
                 ["State or union territory", "Published score"]
                 + [f"Residual, {r}" for r in rules], rows, notes, main=False)


def web_q4(root: Path, L: dict = IJMR_LABELS) -> str:
    """2022 and 2023 rebuilt scores with their SEs, per rule and indicator set. The
    change, threshold and verdict are what Figure 4 plots, so they are not repeated."""
    sel = q1_selection(root)
    rules = list(sel["sensitivity_rules"])
    allr = read_csv(root / "outputs" / "q4_2022_2023_states.csv")
    sets = list(dict.fromkeys(r["indicator_set"] for r in allr))
    states = list(dict.fromkeys(r["state"] for r in allr))
    by = {(r["indicator_set"], r["rule"], r["state"]): r for r in allr}

    def sc(s, se):
        v = num(float(s), DP["score"])
        return f"{v} ({num(float(se), DP['score'])})" if se else f"{v} (not computable)"

    rows, over = [], set()
    for iset in sets:
        label = iset.split(" (")[0].replace(",", ", ")
        rows.append([f"**Indicators {label}**"] + [""] * (2 * len(rules)))
        for st in states:
            row = [st + ("†" if by[(iset, rules[0], st)]["ut"] == "1" else "")]
            for rule in rules:
                r = by[(iset, rule, st)]
                for y in ("2022", "2023"):
                    row.append(sc(r[f"s_{y}"], r[f"se_{y}"]))
                    if float(r[f"s_{y}"]) > 100:
                        over.add(rule)
            rows.append(row)
    notes = [f"Rebuilt score (rescaled partial score), standard error (SE) in parentheses. "
             f"The change between the years under {sel['chosen']}, indicators "
             f"{sets[0].replace(',', ', ')}, is shown in {L['fig_change']}.",
             "†Union territory."]
    if over:
        over = sorted(over)
        notes.append(f"{listing(over)} {'is' if len(over) == 1 else 'are'} uncapped; "
                     f"scores can exceed 100.")
    notes.append(REPO_NOTE.format(data=L["data"]))
    header = ["State or union territory"] + [f"{r}, {y}" for r in rules
                                             for y in ("2022", "2023")]
    return block(f"{L['scores']}. Rebuilt scores for score years 2022 and 2023 (SE), by rule "
                 "and indicator set", header, rows, notes, main=False)


# --------------------------------------------------------------------------------------
# Journal of Public Health supplement only: the section 13 log, the post hoc analyses and
# the change by state
# --------------------------------------------------------------------------------------
# Each section 13 entry: (opening words of its bold title, type). A deviation changes what
# the plan specified; a note records the plan applied as written, or corrects a record.
LOG_TYPES = {
    1: ("Indicator 7", "Note: plan applied as written (§5.4, item 5)"),
    2: ("Score years compared in Q4", "Deviation"),
    3: ("Indicator 8, score year 2022", "Note: plan applied as written (§5.4, item 2)"),
    4: ("Indicator 5, score year 2022", "Note: plan applied as written (§5.4, item 4)"),
    5: ("Indicator 1, score year 2022", "Deviation"),
    6: ("Definition stated in the 2021 edition", "Note"),
    7: ("Score year 2020 in Q3", "Deviation"),
    8: ("Exploratory analysis", "Deviation: exploratory analysis added"),
    9: ("Indicator 8 flag", "Deviation"),
    10: ("Correction to item 5", "Note: correction"),
    11: ("Post hoc analyses after peer review", "Post hoc analyses (after peer review)"),
}


def log_entries(root: Path) -> list[tuple[int, str, str]]:
    """(number, date, bold title) of every section 13 entry, in order."""
    text = (root / "docs" / "analysis_plan.md").read_text(encoding="utf-8")
    sec = text.split("## 13. Deviations", 1)[1]
    out, date = [], None
    for ln in sec.splitlines():
        m = re.match(r"^\*\*(\d{1,2} \w+ \d{4})\.\*\*$", ln.strip())
        if m:
            date = m.group(1)
            continue
        m = re.match(r"^(\d+)\. \*\*(.+?)\*\*", ln)
        if m and date:
            out.append((int(m.group(1)), date, m.group(2).rstrip(".")))
    return out


def log_table(root: Path, L: dict) -> str:
    rows = []
    entries = log_entries(root)
    assert [n for n, _, _ in entries] == sorted(LOG_TYPES), "section 13 entries changed"
    for n, date, title in entries:
        start, kind = LOG_TYPES[n]
        assert title.startswith(start), f"section 13 entry {n}: {title!r}"
        rows.append([str(n), date, title, kind])
    notes = [
        "Entries of §13 (Deviations) of the registered analysis plan, as dated there. A "
        "deviation changes what the plan specified; a note records the plan applied as "
        "written, or corrects a record. The full text of each entry is in the deposited "
        f"plan (see the {L['data']}).",
    ]
    return block(f"{L['log']}. Dated entries of the analysis plan's deviations log",
                 ["Entry", "Date", "Subject", "Type"], rows, notes, main=False)


def _posthoc_rows(root: Path) -> list[dict]:
    rows = read_csv(root / "outputs" / "posthoc_summary.csv")
    assert all(r["label"] == "post hoc" for r in rows)
    return rows


def posthoc_table(root: Path, L: dict) -> str:
    rows = _posthoc_rows(root)
    rules = ("R2", "R1")
    full, no1 = "1,2,3,4,6", "2,3,4,6 (indicator 1 excluded)"

    def g(analysis, rule, variant, q, iset=full):
        hit = [r for r in rows if (r["analysis"], r["rule"], r["se_variant"], r["quantity"])
               == (analysis, rule, variant, q) and r["indicator_set"] in (iset, "")]
        assert len(hit) == 1, (analysis, rule, variant, q, iset)
        return hit[0]

    def kn(analysis, rule, variant, q):
        k = int(float(g("Q4 noise", rule, "binomial", "n_compared")["value"]))
        return k_of_n(int(float(g(analysis, rule, variant, q)["value"])), k)

    def ci(r):
        return f"{rho(float(r['value']))} ({rng(rho(float(r['lo'])), rho(float(r['hi'])))})"

    zb = num(float(g("Q4 multiplicity", "R2", "binomial", "z_bonferroni")["value"]), 2)
    body = [["**Q4: change beyond sampling noise (registered test and multiplicity)**", "", ""]]
    body.append([f"Exceeds noise, registered test (absolute z > {num(Z975, 2)})"]
                 + [kn("Q4 noise", r, "binomial", "n_exceeds_registered") for r in rules])
    body.append([f"Exceeds noise, Bonferroni (absolute z > {zb})"]
                 + [kn("Q4 multiplicity", r, "binomial", "n_exceeds_bonferroni") for r in rules])
    body.append(["Exceeds noise, Benjamini–Hochberg (false discovery rate 5%)"]
                 + [kn("Q4 multiplicity", r, "binomial", "n_exceeds_bh") for r in rules])
    body.append(["Expected false positives of the registered test if no state changed"]
                 + [num(float(g("Q4 multiplicity", r, "binomial",
                                "expected_false_positives")["value"]), 2) for r in rules])
    body.append(["**Q4: change unusual relative to other states (funnel)**", "", ""])
    body.append(["Inverse-variance-weighted mean change (points)"]
                 + [num(float(g("Q4 noise", r, "binomial", "ivw_mean_change")["value"]), 2)
                    for r in rules])
    for variant, tag in (("binomial", ""), ("wilson", ", Wilson SE*")):
        body.append([f"Multiplicative overdispersion factor φ{tag}"]
                     + [num(float(g("Q4 noise", r, variant, "phi")["value"]), 1) for r in rules])
        for q, lab in (("n_outside95_mult", "95%"), ("n_outside998_mult", "99.8%")):
            body.append([f"Outside the {lab} limits, multiplicative{tag}"]
                        + [kn("Q4 noise", r, variant, q) for r in rules])
        body.append([f"Between-state variance τ² (DerSimonian–Laird){tag}"]
                    + [num(float(g("Q4 noise", r, variant, "tau2")["value"]), 2) for r in rules])
        for q, lab in (("n_outside95_add", "95%"), ("n_outside998_add", "99.8%")):
            body.append([f"Outside the {lab} limits, additive{tag}"]
                        + [kn("Q4 noise", r, variant, q) for r in rules])
    body.append(["States whose category changes with Wilson SEs*: registered test; "
                 "multiplicative 95%, 99.8%; additive 95%, 99.8%"]
                + ["; ".join(count(int(float(g("Q4 noise", r, "wilson", f"n_changed_{q}")["value"])))
                             for q in ("registered", "outside95_mult", "outside998_mult",
                                       "outside95_add", "outside998_add")) for r in rules])
    body.append(["**Q4: regression to the mean (Oldham's method)†**", "", ""])
    for iset, lab in ((full, "1, 2, 3, 4, 6"), (no1, "2, 3, 4, 6")):
        n = g("Q4 regression to the mean", "R2", "binomial", "oldham_r", iset)["n"]
        body.append([f"Indicators {lab}: Pearson r (95% CI) of change with two-year mean "
                     f"(n = {n})"]
                    + [ci(g("Q4 regression to the mean", r, "binomial", "oldham_r", iset))
                       for r in rules])
        body.append([f"Indicators {lab}: Spearman {RHO} (95% CI), sensitivity"]
                    + [ci(g("Q4 regression to the mean", r, "binomial", "oldham_rho", iset))
                       for r in rules])
    body.append(["**Q3: association with prevalence, survey uncertainty propagated‡**", "", ""])
    n3 = g("Q3 prevalence uncertainty", "R2", "", "rho_point")["n"]
    body.append([f"Registered {RHO} (n = {n3} units)"]
                + [rho(float(g("Q3 prevalence uncertainty", r, "", "rho_point")["value"]))
                   for r in rules])
    body.append([f"{RHO}, prevalence drawn and units resampled: median (central 95% of draws)"]
                + [ci(g("Q3 prevalence uncertainty", r, "", "rho_bootstrap")) for r in rules])
    body.append([f"{RHO}, prevalence drawn only: median (central 95% of draws)"]
                + [ci(g("Q3 prevalence uncertainty", r, "", "rho_prevalence_only"))
                   for r in rules])
    hw = num(float(g("Q3 prevalence uncertainty", "R2", "", "rho_half_width_at_0")["value"]), 2)
    body.append([f"Half-width of the 95% CI of {RHO} at {RHO} = 0 (n = {n3})", f"±{hw}", f"±{hw}"])
    wil = g("Q4 noise", "R2", "wilson", "n_states_wilson")["note"].split("; ")
    changed = [g("Q4 noise", r, "wilson", "n_changed_outside95_add")["note"] for r in rules]
    note_seed = next(r for r in rows if r["quantity"] == "oldham_r")["note"]
    m = re.search(r"(\d+) bootstrap draws, seed (\d+)", note_seed)
    notes = [
        "Post hoc analyses, added after peer review (plan §13, entry 11); not pre-specified. "
        "Rules R2 (primary) and R1; indicators 1, 2, 3, 4 and 6, rescaled, unless stated; "
        f"{count(int(m.group(1)))} bootstrap draws (seed {m.group(2)}, reset for each analysis "
        "and rule). The funnel compares each state's change with the inverse-variance-weighted "
        "mean change: it asks whether a change is unusual relative to other states, whereas "
        "the registered test asks whether it differs from zero beyond sampling noise. "
        "Multiplicative limits: mean ± z√φ SE, φ the mean squared 10%-winsorised z-score "
        "(Spiegelhalter 2005); additive limits: mean ± z√(SE² + τ²); z = 1.96 (95%) and "
        "3.09 (99.8%).",
        f"*Binomial SEs of zero (a proportion of 0 or 1) replaced by the Wilson-interval SE, "
        f"for {listing(wil)}. Category changed under the additive 95% limits: "
        f"{'; '.join(f'{r}, {c}' for r, c in zip(rules, changed))}.",
        "†Correlation of each state's change with the mean of its 2022 and 2023 scores; "
        "states resampled for the interval (2.5th and 97.5th percentiles).",
        "‡Each unit's prevalence drawn from a lognormal distribution fitted to its published "
        "95% CI.",
    ]
    return block(f"{L['posthoc']}. Post hoc analyses: change against overdispersed noise, "
                 "multiplicity, regression to the mean and prevalence uncertainty",
                 ["Analysis", "R2 (primary)", "R1"], body, notes, main=False)


def change_table(root: Path, L: dict) -> str:
    """Change by state under the primary rule (indicators 1, 2, 3, 4, 6): plan 10.4's
    percentage change, the registered verdict and the post hoc flags."""
    sel = q1_selection(root)
    rule = sel["chosen"]
    ph = {r["state"]: r for r in read_csv(root / "outputs" / "posthoc_q4_states.csv")
          if r["rule"] == rule and r["se_variant"] == "binomial"}
    reg = [r for r in read_csv(root / "outputs" / "q4_2022_2023_states.csv")
           if r["rule"] == rule and r["primary"] == "1"]
    yn = {"1": "Yes", "0": "No", "": "—"}
    rows = []
    for r in sorted(reg, key=lambda r: -float(r["change"])):
        p = ph[r["state"]]
        assert p["change"] == r["change"] and p["exceeds_registered"] == r["exceeds"]
        thr = num(float(r["threshold"]), DP["score"]) if r["threshold"] else "Not computable"
        rows.append([r["state"] + ("†" if r["ut"] == "1" else ""),
                     num(float(r["change"]), DP["change"]),
                     num(float(r["pct_change"]), 1), thr, yn[r["exceeds"]],
                     yn[p["exceeds_bonferroni"]], yn[p["exceeds_bh"]],
                     f"{yn[p['outside95_mult']]} / {yn[p['outside95_add']]}"])
    err = next(r for r in read_csv(root / "outputs" / "q4_2022_2023_summary.csv")
               if r["primary"] == "1")
    m = re.search(r"^(.+?) \(SE not computable in (\d{4}) \(indicator (\d): binomial a = "
                  r"(\d+(?:\.\d+)?) > 1 \((\d+)/(\d+)\)\)\)$", err["excluded"])
    state, year, ind, a, k, n = m.groups()
    coh = next(c for c in read_csv(root / "data" / "extracted" / "itr2024_tsr_cohort.csv")
               if c["state"] == state)
    assert coh["success"] == k
    notes = [
        f"Rule {rule}; indicators 1, 2, 3, 4 and 6, rescaled; sorted by change. Change in "
        f"points, and as a percentage of the 2022 score (plan §10.4). Noise threshold = "
        f"{num(Z975, 2)} {TIMES} the standard error (SE) of the change; registered verdict "
        f"(plan §10.3) and, post hoc, after Bonferroni and Benjamini–Hochberg adjustment and "
        f"outside the 95% limits of the overdispersed funnel (multiplicative / additive; "
        f"{L['posthoc']}). The registered markings of {L['fig_change']} are not adjusted "
        "for multiplicity.",
        "†Union territory. B–H, Benjamini–Hochberg; mult., multiplicative; add., additive.",
        f"{state}'s {year} treatment-success achievement of {a} (indicator {ind}) is an "
        f"artefact of the same-period denominator: the {count(int(k))} successful outcomes of "
        f"its {coh['cohort_year']} cohort of {count(int(coh['cohort_notified']))} are divided "
        f"by the {count(int(n))} net notified patients of {year}; neither printed value is "
        f"wrong. The achievement excludes {state} from the noise test but not from the "
        f"n = {err['rho_n']} association between the 2022 score and the change. Under R2 the "
        f"uncapped value inflates {state}'s own score and rank ({L['fig_fifths']}), and under "
        f"R3 it sets the indicator {ind} maximum, so results under both rules carry this "
        "artefact.",
    ]
    return block(f"{L['change']}. Change in the rebuilt score by state, 2022 to 2023 "
                 f"(rule {rule}), with post hoc adjustments",
                 ["State or union territory", "Change (points)", "% of 2022 score",
                  "Threshold (points)", "Beyond noise", "Bonferroni", "B–H",
                  "Funnel 95% (mult. / add.)"], rows, notes, main=False)


def ctx_note(root: Path) -> str:
    """Plan 9.3: deaths and loss to follow-up, descriptive context only (2022 cohort)."""
    import statistics
    ctx = read_csv(root / "data" / "extracted" / "itr2024_outcomes_context.csv")
    nat = next(r for r in ctx if r["state"] == "INDIA")
    st = [r for r in ctx if r["state"] != "INDIA" and int(r["cohort_notified"]) > 0]
    n = int(nat["cohort_notified"])

    def share(col):
        v = [int(r[col]) / int(r["cohort_notified"]) for r in st]
        return (f"median {pct(statistics.median(v), 1)} "
                f"(range {rng(pct(min(v), 1), pct(max(v), 1))})")
    ltfu = int(nat["lost_to_follow_up"])
    return (f"Descriptive context (plan §9.3; no association computed): "
            f"{k_of_n_pct(int(nat['died']), n)} patients of the 2022 cohort died and "
            f"{count(ltfu)} ({pct(ltfu, n)}) were lost to follow-up (annexure 3.3 of the India "
            f"TB Report 2024); across the {count(len(st))} states and union territories, death "
            f"had a {share('died')} and loss to follow-up a {share('lost_to_follow_up')}.")


# --------------------------------------------------------------------------------------
def render(root: Path = ROOT, profile: str = "ijmr") -> str:
    L = LABELS[profile]
    sel = q1_selection(root)
    others = [r for r in sel["sensitivity_rules"] if r != sel["chosen"]]
    assert len(others) == 2, "web table numbering assumes two sensitivity rules"
    blocks = {
        "ind": lambda: table1(root, L),
        "repro": lambda: table2(root, L),
        "robust": lambda: table3(root, sel["chosen"], f"{L['robust']}. Robustness of the 2023 "
                                 f"ranking to defensible alternatives (rule {sel['chosen']})",
                                 "robust" in L["main"], L.get("flat_label", False)),
        "valid": lambda: table4(root, L),
        "SUPP": lambda: L["SUPP"] + "\n",
        "resid": lambda: web_q1(root, L),
        "scores": lambda: web_q4(root, L),
        "log": lambda: log_table(root, L),
        "posthoc": lambda: posthoc_table(root, L),
        "change": lambda: change_table(root, L),
    }
    for rule in others:
        blocks[f"rob_{rule}"] = (lambda rule=rule: table3(
            root, rule, f"{L[f'rob_{rule}']}. Robustness of the 2023 ranking "
            f"(rule {rule}; layout as {L['robust']})", f"rob_{rule}" in L["main"],
            L.get("flat_label", False)))
    parts = ["<!-- Generated by exhibits/make_tables.py from outputs/ and data/. "
             "Do not edit by hand. -->\n"]
    parts += [blocks[k]() for k in L["order"]]
    return "\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    profile = argv[argv.index("--profile") + 1] if "--profile" in argv else "ijmr"
    if profile not in LABELS:
        raise SystemExit(f"unknown profile {profile!r}: one of {sorted(LABELS)}")
    out = ROOT / LABELS[profile]["out"]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(ROOT, profile), encoding="utf-8", newline="\n")
    print(f"wrote {out.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

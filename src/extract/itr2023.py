"""Extract the India TB Report 2023 edition (score year 2022).

Mapped by the rules of docs/analysis_plan.md §5.4 (item 6), as for the 2024
edition (itr2024.py). Every table is checked against the national row it
prints; a table that fails is not used (§5.4 item 2) and the failure is
recorded. No score is computed here, and the edition prints none.

Run: python -I src/extract/itr2023.py
Writes data/extracted/itr2023_{indicators,tsr_cohort,drtb_outcomes}.csv and
the edition's rows of data/source_choices.csv (score year 2022) and
data/extracted/definitions.csv (edition 2023); other rows are kept.

In itr2023_indicators.csv, pdf_page and table_id are "numerator;denominator"
composites, as in itr2024_indicators.csv.
"""
from __future__ import annotations

import re
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from src import states  # noqa: E402
from src.extract import annex  # noqa: E402
from src.extract.annex import Column, Spec, Table  # noqa: E402

PDF = ROOT / "data_raw" / "india_tb_report" / "ITR2023.pdf"
SOURCE_FILE = "data_raw/india_tb_report/ITR2023.pdf"
EDITION = 2023
SCORE_YEAR = 2022
LIST_PAGES = (207, 208, 209, 210)  # "List of Annexures" (text layer)
FIRST_ANNEX_PAGE = 211
FOOTER = re.compile(r"\d*\s*INDIA TB REPORT 2023\s*\d*")
DEF_PAGES = (107, 108)  # chapter 7, "TB SCORE", Table 7.1; Table 7.2 on 108

# Headers are flattened from the printed (multi-line) headers; the text layer
# splits the "fi" ligature ("notif ied"), which is written here as "notified".
SPECS: dict[str, Spec] = {s.key: s for s in (
    Spec("a1_2", "1.2", None, "Target TB patients expected TB patients notif ied", 9, {
        "target_total": Column((2,), "Target TB patients expected to be notified: Total"),
        "notified_total": Column(
            (5,), "TB patients notified, n (% achievement against target): Total"),
    }),
    Spec("a1_6", "1.6", "1.6 GENDER DISAGGREGATED DATA ON TOTAL TB NOTIFICATION",
         "State TB Cases Notified Paediatric TB Cases Notified", 9, {
             "net_notified": Column(
                 (0, 1, 2), "TB Cases Notified: Male + Female + Trans Gender (sum of the "
                            "three printed cells)"),
         }, min_cells=8, plain_lead=3),
    Spec("a2_1", "2.1", "2.1 SCREENING FOR HIV IN NOTIFIED TB",
         "State TB patients with known HIV status", 3, {
             "hiv_known_total": Column((2,), "TB patients with known HIV status, n (%): Total"),
         }),
    Spec("a3_3", "3.3", "3.3 TREATMENT OUTCOME OF TB PATIENTS", "State TB Cure Success Death", 8, {
        "cohort_notified": Column((0,), "TB patients Notified"),
        "success": Column((2,), "Success Rate, n (%)"),
    }),
    Spec("a4_7", "4.7", None, "State/UT Bacteriologically conf irmed", 13, {
        "rif_known_total": Column(
            (5,), "Bacteriologically confirmed TB patients with valid rapid DRT result for at "
                  "least Rifampicin (RS/RR), n (%): Total TB"),
        "rr_diagnosed_total": Column(
            (8,), "Rifampicin resistant TB patients diagnosed (MDR/RR-TB), n (%): Total TB"),
    }, header_on_every_page=False),
    Spec("a4_9", "4.9", None, "State/UT Rifampicin-resistant TB patients initiated on treatment", 8, {
        "mdr_initiated_total": Column(
            (2,), "Rifampicin-resistant TB patients initiated on treatment (MDR/RR-TB), n (%): "
                  "Total TB"),
    }),
    Spec("a4_13", "4.13", "4.13 TREATMENT OUTCOME OF MDR/RR-TB PATIENTS",
         "State/UT Total MDR/ Cured Treatment", 7, {
             "cohort_n": Column((0,), "Total MDR/RR-TB initiated"),
             "cured": Column((1,), "Cured"),
             "success": Column((2,), "Treatment success"),
         }, absent=("Lakshadweep",)),
    Spec("a7_2", "7.2", None, "States/UTs No. of Screening, diagnosis and treatment of TB", 8, {
        "eligible_tpt": Column(
            (6,), "No. of HHC <5years of PBCT not diagnosed TB and eligible for TPT (%)"),
        "initiated_tpt": Column((7,), "No. of HHC <5years of PBCT initiated TPT (%)"),
    }),
    Spec("a9", "9", "9. NI-KSHAY POSHAN YOJANA",
         "State/UTs/UTs TOTAL BANK DETAILS BENEFICIARIES PAID", 3, {
             "notified": Column((0,), "TOTAL NOTIFICATION"),
             "paid_once": Column(
                 (2,), "BENEFICIARIES PAID OF AT LEAST ONE BENEFIT OF TOTAL NOTIFIED (%)"),
         }),
)}

# Tables whose state sums differ from their printed national row. They are
# not used (§5.4 item 2); the mismatch must still be present when re-run.
FAILS_PRINTED_TOTAL = ("a7_2",)


# ---- tables ------------------------------------------------------------------

def _doc(pdf: Path) -> annex.Doc:
    return annex.Doc(pdf)


@lru_cache(maxsize=None)
def _locate(pdf: str) -> tuple[int, dict[str, tuple[int, ...]], dict[str, int]]:
    doc = _doc(Path(pdf))
    if not doc.lines(LIST_PAGES[0])[0].startswith("List of Annexures"):
        raise ValueError(f"List of Annexures not on PDF p. {LIST_PAGES[0]}")
    listed = annex.annexure_list(doc, LIST_PAGES)
    off, pages = annex.locate(doc, list(SPECS.values()), listed, FIRST_ANNEX_PAGE)
    return off, pages, listed


def locate_tables(pdf: Path = PDF) -> tuple[int, dict[str, tuple[int, ...]]]:
    off, pages, _ = _locate(str(pdf))
    return off, pages


@lru_cache(maxsize=None)
def _all_tables(pdf: str) -> tuple[dict[str, Table], dict[str, list[tuple[str, int, int]]]]:
    doc = _doc(Path(pdf))
    _, pages, _ = _locate(pdf)
    good: dict[str, Table] = {}
    failed: dict[str, list[tuple[str, int, int]]] = {}
    for key, spec in SPECS.items():
        t = annex.extract_table(doc, spec, pages[key], SCORE_YEAR, FOOTER, check=False)
        bad = annex.national_mismatches(t)
        if key in FAILS_PRINTED_TOTAL:
            if not bad:
                raise ValueError(f"{spec.table_id} now matches its printed total: re-examine")
            for i in range(spec.ncells):  # the note says every column differs
                col = Column((i,), str(i))
                tot = sum(v for s in states.ALL
                          if (v := annex._col_value(t.cells[s], col, spec.table_id)) is not None)
                if tot == annex._col_value(t.cells["India"], col, spec.table_id):
                    raise ValueError(f"{spec.table_id} column {i} matches its printed total")
            failed[key] = bad
        else:
            annex.check_national(t)  # raises on a mismatch
            good[key] = t
    # The net-notified note quotes annexure 1.4 (paediatric; PDF 217) rows and
    # annexure 1.6's paediatric cells for Chandigarh and Delhi.
    a14 = doc.lines(217)
    for line in ("496 18 514 277 4 281 260 (93.9) 3 (75) 263 (93.6)",
                 "7867 2258 10125 8122 838 8960 7419 (91.3) 730 (87.1) 8149 (90.9)"):
        if line not in a14:
            raise ValueError(f"annexure 1.4 row not on PDF p. 217: {line!r}")
    for s, want in (("Chandigarh", ["122", "158", "1"]), ("Delhi", ["3487", "5468", "3"])):
        if [c.n for c in good["a1_6"].cells[s][3:6]] != want:
            raise ValueError(f"annexure 1.6 paediatric cells of {s} changed")
    # Annexure 9 'TOTAL NOTIFICATION' is annexure 1.2's notified count.
    for s in states.ALL:
        if good["a9"].rows[s]["notified"] != good["a1_2"].rows[s]["notified_total"]:
            raise ValueError(f"annexure 9 and 1.2 notified differ for {s}")
    return good, failed


def extract_tables(pdf: Path = PDF) -> dict[str, Table]:
    """Tables that pass the printed-total check."""
    return _all_tables(str(pdf))[0]


def printed_total_failures(pdf: Path = PDF) -> dict[str, list[tuple[str, int, int]]]:
    """(column, state sum, printed national) per failing table."""
    return _all_tables(str(pdf))[1]


# ---- scores and definition -----------------------------------------------------

_SCORE_LINE = re.compile(r"TB[\s-]*(score|index)", re.I)
_TWO_DEC = re.compile(r"\b\d{1,3}\.\d{2}\b")


def extract_scores(pdf: Path = PDF) -> None:
    """The edition prints no numeric state scores: returns None.

    Checked: no text-layer line naming the TB score or TB index carries a
    two-decimal value, and Table 7.2 (top-5 ranks only) sits on PDF p. 108,
    which has no text layer (outlined glyphs).
    """
    doc = _doc(pdf)
    for p in range(1, doc.n_pages() + 1):
        for line in doc.lines(p):
            if _SCORE_LINE.search(line) and _TWO_DEC.search(line):
                raise ValueError(f"possible printed score on PDF p. {p}: {line!r}")
    if doc.chars(DEF_PAGES[1]) != 0:
        raise ValueError(f"PDF p. {DEF_PAGES[1]} now has a text layer: re-read Table 7.2")
    return None


# Table 7.1 (PDF p. 107), two text columns interleaved: each indicator is the
# join of fragments, all checked against the page text, and its points end
# the line that starts with its number. Rows 8 and 9 are on PDF p. 108, which
# has no text layer; they were transcribed from the rendered page and their
# points are checked against the stated total of 100.
TABLE_7_1: tuple[tuple[int, int, int, tuple[str, ...]], ...] = (
    (1, 20, 107, ("% of Target TB notification achieved", "(Source: Ni-kshay)")),
    (2, 10, 107, ("% of net TB notified patients with known HIV", "status (Source: Ni-kshay)")),
    (3, 10, 107, ("% of net TB notified patients with UDST done", "(Source: Ni-kshay)")),
    (4, 15, 107, ("Treatment Success Rate for net TB patients", "(Source: Ni-kshay)")),
    (5, 10, 107, ("% of Eligible beneficiaries paid at least once",
                  "under Ni-kshay Poshan Yojana (Source: Ni-", "kshay)")),
    (6, 15, 107, ("% of MDR/ RR patients initiated on treatment", "out of net diagnosed",
                  "(Source: PMDT Quarterly Reports )")),
    (7, 10, 107, ("% of expenditure amongst ROP", "(Source: PFMS)")),
    (8, 5, 108, ("% of children <5/<6 years given chemoprophylaxis against the total "
                 "eligible children identified (Source: Ni-kshay)",)),
    (9, 5, 108, ("% of PLHIV given IPT against total eligible PLHIV (Source: NACP)",)),
)
_PARAMETERS = {
    1: "Achievement of TB notification among the targets identified.",
    2: "HIV testing/ screening of TB notified patients.",
    3: "UDST coverage among the TB notified patients.",
    4: "Treatment Success Rate of TB notified patients.",
    5: "Ni-kshay Poshan Yojana implementation.",
    6: "DRTB treatment initiation among the diagnosed patients.",
    7: "Utilisation of the allotted budget.",
    8: "Latent TB infection management",
    9: "Latent TB infection management",
}
_DIFF_NOTES = {
    1: "Same quantity as plan §5.1 row 1; no numerator/denominator wording given.",
    2: "Says 'net TB notified patients' (denominator), as plan §5.1 row 2.",
    3: "Denominator stated as net notified; no 70% state benchmark is stated "
       "(plan §5.1 row 3 and §5.2 use 0.7 x net notified).",
    4: "'for net TB patients'; the cohort period is not stated.",
    5: "'paid at least once' among eligible beneficiaries, as plan §5.1 row 5.",
    6: "'out of net diagnosed', as plan §5.1 row 6; source named as PMDT Quarterly Reports.",
    7: "'amongst ROP'; source named as PFMS.",
    8: "Age band '<5/<6 years' (plan §5.1 row 8: < 6 years); 'chemoprophylaxis', drug "
       "not named. One row with indicator 9 under the parameter 'Latent TB infection "
       "management'.",
    9: "IPT among eligible PLHIV, as plan §5.1 row 9; source named as NACP.",
}


def _join(frags: tuple[str, ...]) -> str:
    """Join line fragments; a word hyphenated at a line end ("Ni-" "kshay)") is rejoined."""
    return re.sub(r"(?<=\w-) (?=\w)", "", " ".join(frags))


def definitions(pdf: Path = PDF) -> list[dict]:
    doc = _doc(pdf)
    text107 = " ".join(doc.lines(107))
    for frag in ("TB SCORE", "The TB Index currently in usage consists of 9 indicators:",
                 "indicators sum up to a total of 100."):
        if frag not in text107:
            raise ValueError(f"Table 7.1 text not on PDF p. 107: {frag!r}")
    if doc.chars(108) != 0:
        raise ValueError("PDF p. 108 now has a text layer: re-read Table 7.1 rows 8-9")
    lines107 = doc.lines(107)
    if sum(pts for _, pts, _, _ in TABLE_7_1) != 100:
        raise ValueError("Table 7.1 points do not sum to the stated 100")
    rows: list[dict] = []
    base = {"edition": EDITION, "score_year": SCORE_YEAR}
    extract_scores(pdf)
    rows.append({**base, "indicator_no": "scores", "points": "", "source_page": "108",
                 "indicator_text_verbatim": "Table 7.2: State TB-score for 2022 (Top-5, States "
                                            "with population <50 lakhs/>50 lakhs and Uts)",
                 "note": "no state scores printed in ITR2023. Table 7.2 lists only ranks 1-5 "
                         "per category (no score values); PDF p. 108 has no text layer "
                         "(outlined glyphs), caption transcribed from the rendered page. "
                         "No text-layer line naming the TB score/index carries a score value."})
    rows.append({**base, "indicator_no": "categories", "points": "", "source_page": "108",
                 "indicator_text_verbatim": "STATES WITH POPULATION <50 LAKHS; STATES WITH "
                                            "POPULATION >50 LAKHS; UNION TERRITORIES",
                 "note": "Column headings of Table 7.2 (ranking categories); transcribed from "
                         "the rendered page (no text layer)."})
    rows.append({**base, "indicator_no": "total", "points": 100, "source_page": "107",
                 "indicator_text_verbatim": "The TB Index currently in usage consists of 9 "
                                            "indicators: ... The individual indicators sum up "
                                            "to a total of 100.",
                 "note": "Table 7.1: TB Index currently in usage (PDF 107-108). Score names "
                         "used: 'TB SCORE', 'TB Index'. Numerators and denominators are not "
                         "stated separately; each indicator is one phrase."})
    for n, pts, page, frags in TABLE_7_1:
        if page == 107:
            for frag in frags:
                if frag not in text107:
                    raise ValueError(f"Table 7.1 indicator {n}: {frag!r} not on PDF p. 107")
            hits = [l for l in lines107 if l.startswith(f"{n} ") and l.endswith(f" {pts}")]
            if len(hits) != 1:
                raise ValueError(f"Table 7.1 indicator {n}: points {pts} not found once")
            src = "read from the text layer"
        else:
            src = ("transcribed from the rendered page (PDF p. 108 has no text layer); points "
                   "checked against the stated total of 100")
        rows.append({**base, "indicator_no": n, "points": pts, "source_page": page,
                     "indicator_text_verbatim": _join(frags),
                     "note": f"Parameter: '{_PARAMETERS[n]}'. {_DIFF_NOTES[n]} Text {src}."})
    return rows


# ---- indicators ------------------------------------------------------------------

# indicator -> ((numerator table, column), (denominator table, column))
SOURCES: dict[int, tuple[tuple[str, str], tuple[str, str]]] = {
    1: (("a1_2", "notified_total"), ("a1_2", "target_total")),
    2: (("a2_1", "hiv_known_total"), ("a1_6", "net_notified")),
    3: (("a4_7", "rif_known_total"), ("a1_6", "net_notified")),
    4: (("a3_3", "success"), ("a1_6", "net_notified")),
    6: (("a4_9", "mdr_initiated_total"), ("a4_7", "rr_diagnosed_total")),
}
MISSING = {
    5: "5: no state-wise table with the eligible-beneficiary denominator of plan §5.1 row 5 "
       "(annexure 9, PDF 323-324, prints payments of total notified only); missing under "
       "§5.4 item 4 (controller ruling R18, 17 Nov 2026).",
    7: "7: no state-wise table of expenditure against the approved ROP (chapter 15, "
       "Table 15.1 Financial Performance, PDF 176, is national only; no such annexure).",
    8: "8: annexure 7.2 (PDF 303-304) fails the printed-total check in every column "
       "(plan §5.4 item 2); extraction stopped, not corrected.",
    9: "9: no state-wise PLHIV IPT/TPT count (annexure 2.5, PDF 229-230, prints PLHIV "
       "screened/referred/tested/diagnosed only; annexure 2.9 is national).",
}


def _check_missing_sources(pdf: Path) -> None:
    """Re-verify the grounds for indicators 7 and 9 being missing."""
    doc = _doc(pdf)
    _, _, listed = _locate(str(pdf))
    ann = " ".join(" ".join(doc.lines(p)) for p in LIST_PAGES)
    if re.search(r"expenditure|record of proceedings|\bROP\b|fund util", ann, re.I):
        raise ValueError("the annexure list names an expenditure table: re-examine indicator 7")
    a25 = " ".join(" ".join(doc.lines(p)) for p in (229, 230))
    if listed["2.5"] + 30 != 229 or not a25.startswith("State/UT Cumulative No. of PLHIV"):
        raise ValueError("annexure 2.5 not on PDF p. 229")
    a29 = " ".join(" ".join(doc.lines(p)) for p in (229, 230, 237, 238))
    if re.search(r"\bIPT\b|\bTPT\b|preventive|isoniazid", a29, re.I):
        raise ValueError("annexure 2.5/2.9 mentions preventive therapy: re-examine indicator 9")


def build_indicators(tables: dict[str, Table]) -> tuple[list[dict], dict[int, tuple[int, int]]]:
    rows: list[dict] = []
    totals: dict[int, tuple[int, int]] = {}
    for ind, ((nt, nc), (dt, dc)) in sorted(SOURCES.items()):
        num_t, den_t = tables[nt], tables[dt]
        totals[ind] = (num_t.national[nc], den_t.national[dc])
        for s in states.ALL:
            rows.append({
                "score_year": SCORE_YEAR, "state": s, "indicator": ind,
                "numerator": num_t.rows[s][nc], "denominator": den_t.rows[s][dc],
                "source_file": SOURCE_FILE,
                "pdf_page": f"{num_t.row_pages[s]};{den_t.row_pages[s]}",
                "table_id": f"{num_t.spec.table_id};{den_t.spec.table_id}",
            })
    return rows, totals


def extract_drtb_outcomes(tables: dict[str, Table]) -> tuple[list[dict], dict[str, int]]:
    """Annexure 4.13, MDR/RR-TB outcomes of the 2020 cohort (Q3 secondary).

    No 'completed' column is printed: completed = success - cured.
    Lakshadweep is not printed: its row is blank.
    """
    t = tables["a4_13"]
    rows = []
    for s in states.ALL:
        v = t.rows[s]
        if v["cured"] is not None and v["success"] is not None:
            completed = v["success"] - v["cured"]
            if completed < 0 or (v["cohort_n"] is not None and v["success"] > v["cohort_n"]):
                raise ValueError(f"Annexure 4.13 {s}: inconsistent {v}")
        else:
            completed = None
        rows.append({"state": s, "cohort_year": 2020, "cohort_n": v["cohort_n"],
                     "cured": v["cured"], "completed": completed, "success": v["success"],
                     "source_file": SOURCE_FILE,
                     "pdf_page": t.row_pages[s] or ";".join(map(str, t.pages)),
                     "table_id": t.spec.table_id})
    return rows, dict(t.national)


# ---- source choices (plan §5.4 item 7) ---------------------------------------------

# Pages without a text layer rendered and read in the bounded search for a
# national 2022 notification target (controller ruling R19, 17 Nov 2026):
# lists of tables/figures (21-23), executive summary (24, 25, 27), chapter 2
# (43, 44), chapter 3B (61, 62), and Tables 15.3 and 15.5 (178, 180; these
# two have a text layer and were also read as text). No target was found.
R19_PAGES = (21, 22, 23, 24, 25, 27, 43, 44, 61, 62, 178, 180)

def _pages(pages: dict[str, tuple[int, ...]], key: str) -> str:
    return ";".join(map(str, pages[key]))


def _pct(c: annex.Cell) -> float:
    return float(c.pct.strip("()% "))


def source_choices(pdf: Path = PDF) -> list[dict]:
    tables = extract_tables(pdf)
    failed = printed_total_failures(pdf)
    _, pages, _ = _locate(str(pdf))
    a12, a16, a21, a47 = (tables[k] for k in ("a1_2", "a1_6", "a2_1", "a4_7"))

    def ch(key: str, col: str) -> tuple[str, str, str]:
        return SPECS[key].table_id, _pages(pages, key), SPECS[key].columns[col].header

    # Evidence for the net-notified choice: annexure 2.1's printed percentages.
    match = 0
    worst = (0.0, "")
    for s in states.ALL:
        c = a21.cells[s][2]
        d = abs(round(100 * a21.rows[s]["hiv_known_total"] / a16.rows[s]["net_notified"], 1)
                - _pct(c))
        match += d < 0.05
        worst = max(worst, (round(d, 1), s))
    ev = []
    for s in ("Delhi", "Puducherry", "Chandigarh"):
        h, n, g = (a21.rows[s]["hiv_known_total"], a16.rows[s]["net_notified"],
                   a12.rows[s]["notified_total"])
        ev.append(f"{s}: printed {_pct(a21.cells[s][2])}%; {h:,}/{n:,} (1.6) = {h / n:.1%}; "
                  f"{h:,}/{g:,} (1.2) = {h / g:.1%}")
    net = ch("a1_6", "net_notified")
    net_note = (
        "Net notified (plan §5.4 item 7). JUDGEMENT CALL: no column in this edition is "
        "labelled 'net' for all patients (annexure 1.4 is paediatric only; there is no "
        "patient-transfer annexure). Used: annexure 1.6 'TB Cases Notified', Male + Female + "
        "Trans Gender, which counts patients by current PHI: its paediatric cells track "
        "annexure 1.4's labelled 'Net paediatric TB patients* notified (Based On Current "
        "PHI)' (PDF 217-218), e.g. Chandigarh 122+158+1 = 281 = net 281 (514 by diagnosing "
        "PHI), Delhi 3,487+5,468+3 = 8,958 vs net 8,960 (10,125 by diagnosing PHI). The same "
        "column feeds indicators 2, 3 and 4. Not used: annexure 1.2 'TB patients notified' "
        "(the edition's only printed total; its counts equal annexure 9 'TOTAL "
        "NOTIFICATION' and differ from current-PHI counts). Evidence: annexure 2.1's printed "
        f"percentages follow 1.6, not 1.2 ({'; '.join(ev)}). They match 1.6 to the printed "
        f"decimal in {match} of 36 units; largest difference {worst[0]} points ({worst[1]}), "
        "so 2.1's own (unprinted) denominator is close to, not identical with, 1.6. "
        f"National: 1.6 sum {a16.national['net_notified']:,} vs 1.2 "
        f"{a12.national['notified_total']:,}.")
    rif_n, net_n = a47.national["rif_known_total"], a16.national["net_notified"]
    bad72 = failed["a7_2"]
    bad72_txt = "; ".join(f"{c}: state sum {a:,} vs INDIA {b:,}" for c, a, b in bad72)
    cols72 = len(bad72)
    target = a12.national["target_total"]
    searched = ", ".join(map(str, R19_PAGES))
    rows = [
        (1, "numerator", *ch("a1_2", "notified_total"), "§5.1 row 1",
         "Total TB patients notified in 2022 (annexure 1.2; the PHI basis is not stated; equal "
         "state by state to annexure 9 'TOTAL NOTIFICATION', checked in code)."),
        (1, "denominator", *ch("a1_2", "target_total"), "§5.1 row 1; §5.3",
         f"§5.3 outcome: NOT PERFORMED; §5.3 could not be run, a §13 deviation (17 Nov "
         f"2026). The edition prints no national 2022 notification target outside annexure "
         f"1.2: none in its text layer (every text page searched for 'target'; no KPI table "
         f"like ITR2024's Table 11.1), and none in a bounded visual search of the rendered "
         f"pages without a text layer (controller ruling R19; PDF {searched}: list of tables "
         f"and figures, executive summary, chapters 2 and 3B on notification, Tables 15.3 and "
         f"15.5). Used: annexure 1.2 'Target' (INDIA {target:,}) as each state's "
         f"denominator. The column is labelled 'Target TB patients expected to be notified', "
         f"which begins with the words of plan §5.1 row 1's denominator 'Target TB patients "
         f"estimated for the year'; the annexure prints notification as '% achievement "
         f"against target' on it, and Table 7.1 indicator 1 is '% of Target TB notification "
         f"achieved'. Q4 additionally reports the comparison with indicator 1 excluded."),
        (2, "numerator", *ch("a2_1", "hiv_known_total"), "§5.1 row 2",
         "Count of the Total 'n (%)' cell."),
        (2, "denominator", *net, "§5.1 row 2; §5.4 item 7", net_note),
        (3, "numerator", *ch("a4_7", "rif_known_total"), "§5.1 row 3; §5.4 items 1 and 7",
         "Source of indicator 3 (§5.4 item 7). Same choice as score year 2023: the only "
         "state-wise column counting patients with rifampicin status known (RS/RR), printed "
         "for bacteriologically confirmed patients; no state-wise 'UDST done' among all "
         "notified (annexures 4.2-4.5 count tests or samples). National share "
         f"{rif_n:,} / {net_n:,} = {rif_n / net_n:.1%} of net notified. No national KPI for "
         "'offered rifampicin testing' is printed in the edition's text layer to compare with."),
        (3, "denominator", *net, "§5.1 row 3; §5.2 last item; §5.4 item 7",
         "Stored as the net notified count. The 0.7 benchmark of §5.2 is applied at scoring "
         "time, not here; the edition's own definition (Table 7.1) states no benchmark. "
         + net_note),
        (4, "numerator", *ch("a3_3", "success"), "§5.1 row 4",
         "Outcome successful (cured or treatment completed), 2021 cohort, total sector."),
        (4, "denominator", *net, "§5.1 row 4; §5.4 item 7",
         "The 'same-period denominator from the edition's notification annexure' (§5.1 row 4), "
         "as for score year 2023: 2022 net notified. " + net_note),
        (4, "denominator_matched_cohort", *ch("a3_3", "cohort_notified"), "§8.1 item 4",
         "Q2 variant only: patients notified in 2021 whose outcomes annexure 3.3 reports. "
         "Stored in data/extracted/itr2023_tsr_cohort.csv."),
        (5, "numerator", "missing", _pages(pages, "a9"), "", "§5.1 row 5; §5.4 item 4; §5.5",
         "MISSING for 2022 (controller ruling R18, 17 Nov 2026; §13). No state-wise table "
         "matches plan §5.1 row 5's denominator, total eligible TB patients: annexure 9 "
         "(Ni-kshay Poshan Yojana) prints 'BENEFICIARIES PAID OF AT LEAST ONE BENEFIT OF "
         "TOTAL NOTIFIED (%)' against 'TOTAL NOTIFICATION' (equal to annexure 1.2 notified, "
         "checked in code) and no eligible-beneficiary count. §5.4 item 4: no value is "
         "imputed and no other denominator is substituted."),
        (5, "denominator", "missing", _pages(pages, "a9"), "", "§5.1 row 5; §5.4 item 4",
         "MISSING; see numerator. Annexure 9 has no eligible-beneficiary column."),
        (6, "numerator", *ch("a4_9", "mdr_initiated_total"), "§5.1 row 6",
         "Total MDR/RR-TB initiated on treatment (first column group, Total TB). This edition "
         "has no separate 'second-line' column group."),
        (6, "denominator", *ch("a4_7", "rr_diagnosed_total"), "§5.1 row 6",
         "MDR/RR-TB diagnosed, Total TB. The edition does not state its facility basis (no "
         "footnote); Table 7.1 says 'out of net diagnosed'. Annexure 4.8 prints no "
         "diagnosed column to cross-check."),
        (7, "numerator", "not located", "", "", "§5.1 row 7; §5.4 items 4-5",
         "Not located in ITR2023 (no state-wise expenditure-against-ROP table in the annexure "
         "list; chapter 15 Table 15.1 is national). The search outside the reports was closed "
         "by the author on 17 Nov 2026 (§5.4 item 5); indicator 7 is missing."),
        (7, "denominator", "not located", "", "", "§5.1 row 7; §5.4 items 4-5",
         "Missing; see numerator."),
        (8, "numerator", *ch("a7_2", "initiated_tpt"), "§5.1 row 8; §5.4 item 2; §5.5",
         f"NOT EXTRACTED: annexure 7.2 fails the printed-total check in {cols72} of 2 extracted "
         f"columns ({bad72_txt}); every other column of the table also differs. §5.4 item 2: "
         "extraction stopped, not corrected; indicator 8 is missing for 2022 unless ruled "
         "otherwise. If used, DEFINITIONAL MISMATCH (§5.5): household contacts under 5, not "
         "children under 6 (the edition's Table 7.1 says '<5/<6 years')."),
        (8, "denominator", *ch("a7_2", "eligible_tpt"), "§5.1 row 8; §5.4 item 2; §5.5",
         "NOT EXTRACTED; see numerator. Would be contacts under 5 not diagnosed with TB and "
         "eligible for TPT."),
        (9, "numerator", "not located", "", "", "§5.1 row 9; §5.4 item 4",
         "Missing. Annexure 2.5 (PDF 229-230) prints no PLHIV given IPT/TPT; annexure 2.9 "
         "(PDF 237-238) is national and has none either."),
        (9, "denominator", "not located", "", "", "§5.1 row 9; §5.4 item 4",
         "Missing. No eligible-PLHIV count (PLHIV with active TB ruled out)."),
        ("published_score", "score", "not printed", "108", "", "§2 Q1; §7; §10.1",
         "No state scores printed in ITR2023: Table 7.2 (PDF 108, no text layer) lists only "
         "the top-5 ranks per category for 2022. Q4 therefore compares 2022 and 2023 "
         "re-scored under one definition only (§10.1 (b); §13)."),
        ("q3_secondary", "numerator", *ch("a4_13", "success"), "§9.2",
         "MDR/RR-TB treatment success, 2020 cohort; completed = success - cured (no "
         "'completed' column printed). data/extracted/itr2023_drtb_outcomes.csv."),
        ("q3_secondary", "denominator", *ch("a4_13", "cohort_n"), "§9.2",
         "Lakshadweep is not printed in annexure 4.13: blank row."),
        ("scoring_rule_R4", "bands", "not stated", "107;108;178;179", "", "§6.1; §5.4 item 7",
         "ITR2023 states no threshold bands for the score (Table 7.1 and text, PDF 107-108; "
         "Table 15.3 key deliverables and Table 15.4 key conditionalities, PDF 178-179, name "
         "the score or bands for other measures only)."),
    ]
    cols = ("indicator", "component", "table_id", "pdf_pages", "column_header_verbatim",
            "rule_from_plan", "note")
    return [{"score_year": SCORE_YEAR, **dict(zip(cols, r))} for r in rows]


# ---- writing ---------------------------------------------------------------------

def write_all(pdf: Path, extracted: Path, choices_path: Path) -> dict:
    tables = extract_tables(pdf)
    _check_missing_sources(pdf)
    if extract_scores(pdf) is None:
        print("no state scores printed in ITR2023")
    ind_rows, totals = build_indicators(tables)
    annex.write_csv(extracted / "itr2023_indicators.csv",
                    ["score_year", "state", "indicator", "numerator", "denominator",
                     "source_file", "pdf_page", "table_id"], ind_rows)
    dr_rows, _ = extract_drtb_outcomes(tables)
    annex.write_csv(extracted / "itr2023_drtb_outcomes.csv",
                    ["state", "cohort_year", "cohort_n", "cured", "completed", "success",
                     "source_file", "pdf_page", "table_id"], dr_rows)
    t33 = tables["a3_3"]
    annex.write_csv(extracted / "itr2023_tsr_cohort.csv",
                    ["state", "cohort_year", "cohort_notified", "success",
                     "source_file", "pdf_page", "table_id"],
                    [{"state": s, "cohort_year": 2021, **t33.rows[s], "source_file": SOURCE_FILE,
                      "pdf_page": t33.row_pages[s], "table_id": t33.spec.table_id}
                     for s in states.ALL])
    annex.merge_source_choices(choices_path, SCORE_YEAR, source_choices(pdf))
    annex.merge_definitions(extracted / "definitions.csv", EDITION, definitions(pdf))
    return {"tables": tables, "totals": totals, "indicators": ind_rows,
            "failed": printed_total_failures(pdf)}


def main() -> None:
    res = write_all(PDF, ROOT / "data" / "extracted", ROOT / "data" / "source_choices.csv")
    off, pages = locate_tables(PDF)
    print(f"Annexure PDF-page offset (from titled annexures): +{off}")
    print("National-total checks (state sum = printed national row):")
    for t in res["tables"].values():
        for col, total, nat, nblank in annex.check_national(t):
            extra = f"; blank: {', '.join(t.blanks[col])}" if nblank else ""
            print(f"  {t.spec.table_id} {col}: {total} = national {nat} OK{extra}")
    for key, bad in res["failed"].items():
        for col, total, nat in bad:
            print(f"  {SPECS[key].table_id} {col}: {total} != national {nat} FAIL (not used)")
    present = sorted({r["indicator"] for r in res["indicators"]})
    print(f"Indicators extracted: {present}")
    for ind in sorted(MISSING):
        print("Missing " + MISSING[ind])


if __name__ == "__main__":
    main()

"""Extract the India TB Report 2024 edition (score year 2023).

Driven by docs/analysis_plan.md §5 (indicator definitions, §5.3 target
check, §5.4 source rules, §5.5 mismatches). Every extracted table is checked
against the national row the report prints; a mismatch stops the run.

Run: python -I src/extract/itr2024.py
Writes data/extracted/itr2024_*.csv, data/source_choices.csv and
outputs/q1_target_check.txt. No score is computed here.
"""
from __future__ import annotations

import csv
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[2]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from src import states  # noqa: E402
from src.extract import cells, pdftext  # noqa: E402

PDF = ROOT / "data_raw" / "india_tb_report" / "ITR2024.pdf"
SOURCE_FILE = "data_raw/india_tb_report/ITR2024.pdf"
SCORE_YEAR = 2023
TABLE_11_1_TARGET = 2_761_682  # plan §5.3
TOLERANCE = 0.001  # plan §5.3: 0.1%
PAGE_OFFSET = 30  # PDF page = printed annexure page + 30 (plan §5.1)


# ---- cells -----------------------------------------------------------------

class Cell(NamedTuple):
    n: str | None  # the count as printed; None for a blank cell
    pct: str | None
    raw: str


_PCT = re.compile(r"^\(\s*-?\d+(?:\.\d+)?\s*%?\s*\)$")
_NUM = re.compile(r"^\*?\d[\d,]*(?:\.\d+)?\*?$")
_TOKEN = re.compile(r"\(\s*-?\d+(?:\.\d+)?\s*%?\s*\)|\S+")
# Printed in place of a value: not available, nothing, spreadsheet errors.
BLANKS = frozenset({"NA", "-", "–", "#N/A", "#DIV/0!"})


def split_cells(text: str) -> list[Cell]:
    """Split the value part of a table row into cells.

    A cell is a count with an optional "(pct)" after it, a blank marker
    (NA, -, #N/A, #DIV/0!), or a lone "(pct)" printed without a count
    (annexure 1.4, Lakshadweep "(0)"), which is a blank count. Percentages
    that CTD wraps onto the next line are not part of `text`; callers skip
    those lines, so a count whose percentage wrapped is still one cell.
    """
    out: list[Cell] = []
    for tok in _TOKEN.findall(text):
        if _PCT.match(tok):
            last = out[-1] if out else None
            if last is not None and last.n is not None and last.pct is None:
                out[-1] = Cell(last.n, tok, f"{last.raw} {tok}")
            else:
                out.append(Cell(None, tok, tok))
        elif tok in BLANKS:
            out.append(Cell(None, None, tok))
        elif _NUM.match(tok):
            out.append(Cell(tok, None, tok))
        else:
            raise ValueError(f"unexpected token {tok!r} in row {text!r}")
    return out


def parse_rows(lines: list[str], ncells: int, national_label: str,
               require_national: bool = True,
               ) -> tuple[dict[str, list[Cell]], list[Cell] | None]:
    """State rows and the national row of one table.

    Wrapped State/UT names are rejoined first. Lines that are neither a
    State/UT row nor the national row (headers, wrapped percentages,
    footnotes) are skipped. A row whose cell count
    differs from `ncells` raises ValueError naming the row.
    """
    rows: dict[str, list[Cell]] = {}
    national: list[Cell] | None = None
    for line in states.join_wrapped_names(list(lines)):
        hit = states.leading_state(line)
        if hit is None and line.startswith(national_label + " "):
            label, rest = national_label, line[len(national_label) + 1:]
        elif hit is not None:
            label, rest = hit
        else:
            continue
        cs = split_cells(rest)
        if len(cs) != ncells:
            raise ValueError(
                f"{label}: {len(cs)} cells, header has {ncells}: {line!r}")
        if label == national_label:
            if national is not None:
                raise ValueError(f"two {national_label} rows")
            national = cs
        else:
            if label in rows:
                raise ValueError(f"duplicate row for {label}: {line!r}")
            rows[label] = cs
    if national is None and require_national:
        raise ValueError(f"no {national_label} row")
    return rows, national


# ---- tables ----------------------------------------------------------------

@dataclass(frozen=True)
class Column:
    index: int  # 0-based cell index after the State/UT name
    header: str  # verbatim (flattened) column header
    count: bool = False  # parse with cells.parse_count (integral floats)


@dataclass(frozen=True)
class Spec:
    key: str
    table_id: str
    title: str  # verbatim start of the first page's first line
    printed_page: int
    pages: tuple[int, ...]
    ncells: int
    columns: dict[str, Column]
    national_label: str = "INDIA"


SPECS: dict[str, Spec] = {s.key: s for s in (
    Spec("a1_2", "Annexure 1.2", "1.2. TB case notification", 157, (187, 188), 9, {
        "target_total": Column(2, "Target of TB patients expected to be notified: Total"),
        "notified_total": Column(5, "TB patients notified, n(% of achievement against target): Total"),
    }),
    Spec("a1_4", "Annexure 1.4", "1.4. Patient transfer status and treatment initiation status",
         161, (191, 192), 9, {
        "net_notified_total": Column(
            5, "Net TB patients* notified (Based on current PHI); public–private disaggregated: Total"),
    }),
    Spec("a2_1", "Annexure 2.1", "2.1. TB patients with known HIV status", 169, (199,), 3, {
        "hiv_known_total": Column(2, "TB patients with known HIV status, n (%): Total"),
    }),
    Spec("a3_3", "Annexure 3.3", "3.3. Treatment outcome of TB patients notified in 2022 (total)",
         192, (222, 223), 8, {
        "cohort_notified": Column(0, "TB patients notified"),
        "success": Column(2, "Success rate, n(%)"),
    }),
    Spec("a4_7", "Annexure 4.7", "4.7. PMDT case finding in 2023 - I", 230, (260, 261, 262), 12, {
        "rif_known_total": Column(
            8, "No. of bacteriologically confirmed TB cases with valid rapid DRT result "
               "for at least rifampicin (RS/RR): Total"),
        "rr_diagnosed_total": Column(
            11, "No. of rifampicin resistant TB cases diagnosed (MDR/RR-TB): Total"),
    }),
    Spec("a4_8", "Annexure 4.8", "4.8. PMDT case finding in 2023 - II", 233, (263, 264), 9, {
        "rr_diagnosed": Column(0, "No. of Rifampicin resistant TB cases diagnosed (MDR/RR-TB)"),
    }, national_label="Grand Total"),
    Spec("a4_9", "Annexure 4.9", "4.9. Treatment initiation in MDR/RR-TB", 235, (265, 266), 15, {
        "mdr_initiated_total": Column(
            2, "Multidrug-resistant/rifampicin-resistant TB cases initiated on treatment "
               "among diagnosed: Total"),
    }),
    Spec("a4_13", "Annexure 4.13", "4.13. Treatment outcome of MDR/RR-TB cases initiated on "
         "treatment in 2021", 243, (273, 274), 7, {
        "cohort_n": Column(0, "Total MDR/RR-TB initiated on treatment"),
        "cured": Column(1, "Cured"),
        "success": Column(2, "Treatment success"),
    }),
    Spec("a7_2", "Annexure 7.2", "7.2. TB preventive treatment among eligible household "
         "contacts (<5 years of age) of PBCT", 252, (282, 283), 8, {
        "hhc_u5": Column(0, "No. of HHC <5years of PBCT", count=True),
        "eligible_tpt": Column(
            6, "No. of HHC <5 years of PBCT not diagnosed TB and eligible for TPT (%)"),
        "initiated_tpt": Column(7, "No. of HHC <5 years of PBCT initiated TPT (%)"),
    }),
    Spec("a9", "Annexure 9", "9. Nikshay Poshan Yojana", 279, (309,), 4, {
        "eligible": Column(0, "Eligible beneficiaries"),
        "paid_once": Column(3, "Beneficiaries paid at least one benefit of total eligible beneficiaries"),
    }),
)}

_TITLE = re.compile(r"^\d+(?:\.\d+)?\.\s")


@dataclass
class Table:
    spec: Spec
    rows: dict[str, dict[str, int | None]]
    pages: dict[str, int]
    national: dict[str, int]
    blanks: dict[str, list[str]]  # column -> states printed blank


@lru_cache(maxsize=None)
def _lines(pdf: str, page: int) -> tuple[str, ...]:
    return tuple(pdftext.page_lines(Path(pdf), page))


def _value(cell: Cell, col: Column, where: str) -> int | None:
    if cell.n is None:
        return None
    try:
        return cells.parse_count(cell.n) if col.count else cells.parse_int(cell.n)
    except ValueError as e:
        raise ValueError(f"{where}: {e}") from None


def extract_table(pdf: Path, spec: Spec) -> Table:
    first, last = spec.pages[0], spec.pages[-1]
    if first != spec.printed_page + PAGE_OFFSET:
        raise ValueError(f"{spec.table_id}: PDF page {first} != printed {spec.printed_page} + 30")
    head = _lines(str(pdf), first)
    if not head or not head[0].startswith(spec.title):
        raise ValueError(f"{spec.table_id}: PDF page {first} starts {head[:1]!r}")
    for pg in spec.pages[1:]:
        if _TITLE.match(_lines(str(pdf), pg)[0]):
            raise ValueError(f"{spec.table_id}: page {pg} starts a new table")
    nxt = _lines(str(pdf), last + 1)
    if not nxt or not _TITLE.match(nxt[0]):
        raise ValueError(f"{spec.table_id}: table may continue on page {last + 1}")

    rows: dict[str, list[Cell]] = {}
    pages: dict[str, int] = {}
    national: list[Cell] | None = None
    for pg in spec.pages:
        r, nat = parse_rows(list(_lines(str(pdf), pg)), spec.ncells,
                            spec.national_label, require_national=False)
        if nat is not None:
            if national is not None:
                raise ValueError(f"{spec.table_id}: two national rows")
            national = nat
        for s, cs in r.items():
            if s in rows:
                raise ValueError(f"{spec.table_id}: {s} on two pages")
            rows[s], pages[s] = cs, pg
    if national is None:
        raise ValueError(f"{spec.table_id}: no {spec.national_label} row")
    states.require_all(rows, SCORE_YEAR)

    out_rows: dict[str, dict[str, int | None]] = {}
    blanks: dict[str, list[str]] = {c: [] for c in spec.columns}
    for s in states.ALL:
        out_rows[s] = {}
        for name, col in spec.columns.items():
            v = _value(rows[s][col.index], col, f"{spec.table_id} {s} {name}")
            out_rows[s][name] = v
            if v is None:
                blanks[name].append(s)
    nat_vals: dict[str, int] = {}
    for name, col in spec.columns.items():
        v = _value(national[col.index], col, f"{spec.table_id} {spec.national_label} {name}")
        if v is None:
            raise ValueError(f"{spec.table_id}: national {name} is blank")
        nat_vals[name] = v
    t = Table(spec, out_rows, pages, nat_vals, blanks)
    check_national(t)
    return t


def check_national(t: Table) -> list[tuple[str, int, int, int]]:
    """State sum == printed national row, for every extracted column.

    Blank state cells are left out of the sum. Returns (column, state sum,
    national, number of blank states); raises ValueError on a mismatch.
    """
    res = []
    for name in t.spec.columns:
        total = sum(v[name] for v in t.rows.values() if v[name] is not None)
        if total != t.national[name]:
            raise ValueError(
                f"{t.spec.table_id} {name}: state sum {total} != "
                f"{t.spec.national_label} {t.national[name]}")
        res.append((name, total, t.national[name], len(t.blanks[name])))
    return res


@lru_cache(maxsize=None)
def _tables(pdf: str) -> dict[str, Table]:
    tables = {k: extract_table(Path(pdf), s) for k, s in SPECS.items()}
    # Annexures 4.7 and 4.8 both print MDR/RR-TB diagnosed; they must agree.
    a7, a8 = tables["a4_7"], tables["a4_8"]
    for s in states.ALL:
        if a7.rows[s]["rr_diagnosed_total"] != a8.rows[s]["rr_diagnosed"]:
            raise ValueError(f"MDR/RR-TB diagnosed differs between 4.7 and 4.8 for {s}")
    return tables


def extract_tables(pdf: Path = PDF) -> dict[str, Table]:
    return _tables(str(pdf))


# ---- Table 11.2 and Table 11.1 ----------------------------------------------

SCORES_PAGE = 123
_SCORE = re.compile(r"(.+?)\s+(\d{1,3}\.\d{2})(?=\s|$)")


def _try_canonical(name: str) -> str | None:
    try:
        return states.canonical(name)
    except KeyError:
        return None


def _is_prefix(name: str) -> bool:
    n = " ".join(name.replace("&", " and ").split()).casefold()
    return any(s.casefold().startswith(n + " ") for s in states.ALL)


def parse_scores(lines: list[str]) -> dict[str, str]:
    """Table 11.2: two (State/UT, score) columns per line; scores as printed.

    A name wrapped at the end of a left-hand cell ("Dadra and Nagar Haveli
    and Daman 98.04 ...") is completed by the leading words of the next line
    ("and Diu Puducherry 91.56").
    """
    try:
        start = next(i for i, l in enumerate(lines) if l.startswith("Table 11.2"))
    except StopIteration:
        raise ValueError("Table 11.2 not found") from None
    out: dict[str, str] = {}
    pending: tuple[str, str] | None = None

    def add(name: str, score: str) -> None:
        if name in out:
            raise ValueError(f"Table 11.2: duplicate {name}")
        out[name] = score

    for line in lines[start + 1:]:
        if line.startswith("#TBHarega"):
            break
        if line.startswith("States/UTs"):
            continue
        pairs = [(m.group(1).strip(), m.group(2)) for m in _SCORE.finditer(line)]
        if not pairs:
            raise ValueError(f"Table 11.2: unparsed line {line!r}")
        if pending is not None:
            words = pairs[0][0].split()
            for k in range(1, len(words)):
                full = _try_canonical(pending[0] + " " + " ".join(words[:k]))
                if full is not None:
                    add(full, pending[1])
                    pairs[0] = (" ".join(words[k:]), pairs[0][1])
                    pending = None
                    break
            if pending is not None:
                raise ValueError(f"Table 11.2: cannot complete {pending[0]!r} from {line!r}")
        for name, score in pairs:
            canon = _try_canonical(name)
            if canon is not None:
                add(canon, score)
            elif _is_prefix(name) and pending is None:
                pending = (name, score)
            else:
                raise ValueError(f"Table 11.2: unknown unit {name!r} in {line!r}")
    if pending is not None:
        raise ValueError(f"Table 11.2: unfinished name {pending[0]!r}")
    return out


def extract_scores(pdf: Path = PDF) -> dict[str, str]:
    scores = parse_scores(list(_lines(str(pdf), SCORES_PAGE)))
    states.require_all(scores, SCORE_YEAR)
    return scores


_TARGET = re.compile(
    r"^1 Achievement in TB case notification against target \(Total\) ([\d,]+) ")


def table_11_1_target(pdf: Path = PDF) -> int:
    hits = [m for m in map(_TARGET.match, _lines(str(pdf), SCORES_PAGE)) if m]
    if len(hits) != 1:
        raise ValueError("Table 11.1 total notification target not found once")
    return cells.parse_int(hits[0].group(1))


def target_verdict(expected: int, target: int) -> str:
    return "AGREE" if abs(expected - target) <= TOLERANCE * target else "DISAGREE"


def target_check(pdf: Path = PDF, out: Path | None = None) -> dict:
    """Plan §5.3: annexure 1.2 national "expected" vs Table 11.1 target."""
    t = extract_tables(pdf)["a1_2"]
    target = table_11_1_target(pdf)
    if target != TABLE_11_1_TARGET:
        raise ValueError(f"Table 11.1 target {target} != plan's {TABLE_11_1_TARGET}")
    expected = t.national["target_total"]
    state_sum = sum(v["target_total"] for v in t.rows.values() if v["target_total"] is not None)
    diff = expected - target
    rel = diff / target
    verdict = target_verdict(expected, target)
    res = {"expected": expected, "state_sum": state_sum, "target": target,
           "difference": diff, "relative": rel, "verdict": verdict}
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join([
            "Plan §5.3 notification-target check, score year 2023 (India TB Report 2024)",
            f"Annexure 1.2 (PDF pp. {', '.join(map(str, t.spec.pages))}), column "
            f"\"{t.spec.columns['target_total'].header}\", INDIA row: {expected}",
            f"Sum of the 36 State/UT rows of that column: {state_sum}",
            f"Table 11.1 (PDF p. {SCORES_PAGE}), annual target for TB case notification (Total): {target}",
            f"Difference (expected - target): {diff}",
            f"Relative difference: {rel:.6%} of the target",
            f"Tolerance: |difference| <= 0.1% of the target = {TOLERANCE * target:.3f}",
            f"Verdict: {verdict}",
            "",
        ]), encoding="utf-8")
    return res


# ---- indicators ------------------------------------------------------------

# indicator -> ((numerator table, column), (denominator table, column))
SOURCES: dict[int, tuple[tuple[str, str], tuple[str, str]]] = {
    1: (("a1_2", "notified_total"), ("a1_2", "target_total")),
    2: (("a2_1", "hiv_known_total"), ("a1_4", "net_notified_total")),
    3: (("a4_7", "rif_known_total"), ("a1_4", "net_notified_total")),
    4: (("a3_3", "success"), ("a1_4", "net_notified_total")),
    5: (("a9", "paid_once"), ("a9", "eligible")),
    6: (("a4_9", "mdr_initiated_total"), ("a4_7", "rr_diagnosed_total")),
    8: (("a7_2", "initiated_tpt"), ("a7_2", "eligible_tpt")),
}

MISSING = {
    7: "7: no state-wise table located in ITR2024 (no annexure or table on expenditure "
       "against the approved ROP; Table 16.1, PDF p. 174, is national only). Controller "
       "ruling R4: no web search, no download.",
    9: "9: not located. Annexure 2.5 (PDF pp. 203-204) prints PLHIV screened, referred, "
       "tested and diagnosed with TB, but no PLHIV given IPT/TPT and no eligible-PLHIV "
       "denominator; no other state-wise table in the annexure list.",
}
NOT_COMPUTABLE_1 = ("1: not computable. §5.3 DISAGREE: annexure 1.2 'expected' is not "
                    "CTD's target and state targets are not published.")


def _check_missing_sources(pdf: Path) -> None:
    """Re-verify the grounds for indicators 7 and 9 being missing."""
    ann = " ".join(" ".join(_lines(str(pdf), p)) for p in (182, 183, 184))
    if not ann.startswith("List of Annexures"):
        raise ValueError("annexure list not on PDF pp. 182-184")
    if re.search(r"expenditure|record of proceedings|\bROP\b|fund util", ann, re.I):
        raise ValueError("the annexure list names an expenditure table: re-examine indicator 7")
    a25 = " ".join(" ".join(_lines(str(pdf), p)) for p in (203, 204))
    if not a25.startswith("2.5. Intensified TB case finding activities in ART centres"):
        raise ValueError("annexure 2.5 not on PDF p. 203")
    if re.search(r"\bIPT\b|\bTPT\b|preventive|isoniazid", a25, re.I):
        raise ValueError("annexure 2.5 mentions preventive therapy: re-examine indicator 9")


def build_indicators(tables: dict[str, Table], verdict: str,
                     ) -> tuple[list[dict], dict[int, tuple[int, int]]]:
    """Long-form indicator rows and, per indicator, the printed national
    (numerator, denominator) totals. Blank cells stay None."""
    rows: list[dict] = []
    totals: dict[int, tuple[int, int]] = {}
    for ind, ((nt, nc), (dt, dc)) in sorted(SOURCES.items()):
        if ind == 1 and verdict != "AGREE":
            continue
        num_t, den_t = tables[nt], tables[dt]
        totals[ind] = (num_t.national[nc], den_t.national[dc])
        for s in states.ALL:
            rows.append({
                "score_year": SCORE_YEAR, "state": s, "indicator": ind,
                "numerator": num_t.rows[s][nc], "denominator": den_t.rows[s][dc],
                "source_file": SOURCE_FILE,
                "pdf_page": f"{num_t.pages[s]};{den_t.pages[s]}",
                "table_id": f"{num_t.spec.table_id};{den_t.spec.table_id}",
            })
    return rows, totals


def extract_drtb_outcomes(tables: dict[str, Table]) -> tuple[list[dict], dict[str, int]]:
    """Annexure 4.13, MDR/RR-TB outcomes of the 2021 cohort (Q3 secondary).

    The table prints Cured and Treatment success, not Completed, so
    completed = success - cured (success = cured + completed).
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
        rows.append({"state": s, "cohort_year": 2021, "cohort_n": v["cohort_n"],
                     "cured": v["cured"], "completed": completed, "success": v["success"],
                     "source_file": SOURCE_FILE, "pdf_page": t.pages[s],
                     "table_id": t.spec.table_id})
    return rows, dict(t.national)


# ---- source choices (plan §5.4 item 7) -----------------------------------

def _pages(key: str) -> str:
    return ";".join(map(str, SPECS[key].pages))


def source_choices(check: dict) -> list[dict]:
    v = check["verdict"]
    ch = lambda key, col: (SPECS[key].table_id, _pages(key), SPECS[key].columns[col].header)  # noqa: E731
    net = ch("a1_4", "net_notified_total")
    net_note = ("Net notified (plan §5.4 item 7): annexure 1.4 'Net TB patients* notified "
                "(Based on current PHI)' Total, the only column the report labels 'net'; the "
                "same column feeds indicators 2, 3 and 4. Not used: annexure 1.2 notified "
                "(diagnosing PHI, gross) and annexure 4.7 'Total TB cases notified (2023)' "
                "(case concept, current facility), which the report does not call net.")
    rows = [
        (1, "numerator", *ch("a1_2", "notified_total"), "§5.1 row 1",
         "Total TB patients notified in 2023 (by diagnosing PHI)."
         + ("" if v == "AGREE" else " Not used: §5.3 DISAGREE.")),
        (1, "denominator", *ch("a1_2", "target_total"), "§5.1 row 1; §5.3",
         f"§5.3 outcome: {v}. Annexure 1.2 INDIA 'expected' {check['expected']} vs Table 11.1 "
         f"target {check['target']} (PDF p. {SCORES_PAGE}); difference {check['difference']} "
         f"({check['relative']:.4%}); tolerance 0.1%. "
         + ("Each state's annexure 1.2 'expected' is its denominator; the §8.1 item 3 "
            "burden variant is dropped." if v == "AGREE" else
            "Indicator 1 not computable (§5.4 item 4); annexure 1.2 'expected' becomes "
            "the §8.1 item 3 burden denominator.")),
        (2, "numerator", *ch("a2_1", "hiv_known_total"), "§5.1 row 2",
         "Count of the Total 'n (%)' cell."),
        (2, "denominator", *net, "§5.1 row 2; §5.4 item 7", net_note),
        (3, "numerator", *ch("a4_7", "rif_known_total"), "§5.1 row 3; §5.4 items 1 and 7",
         "Source of indicator 3 (§5.4 item 7). JUDGEMENT CALL: the only state-wise column "
         "in the report that counts patients with rifampicin status known (RS/RR); it is "
         "printed for bacteriologically confirmed patients. No state-wise table prints "
         "'UDST done' among all notified (annexure 1.3 has no testing columns; annexures "
         "4.2-4.5 count tests or samples, not patients); Table 11.1's "
         "'offered rifampicin sensitivity testing' is national only."),
        (3, "denominator", *net, "§5.1 row 3; §5.2 last item; §5.4 item 7",
         "Stored as the net notified count. The 0.7 benchmark of §5.2 is applied at "
         "scoring time (denominator = 0.7 x stored value), not here. " + net_note),
        (4, "numerator", *ch("a3_3", "success"), "§5.1 row 4",
         "Outcome successful (cured or treatment completed), 2022 cohort, total sector."),
        (4, "denominator", *net, "§5.1 row 4; §5.4 item 7",
         "The 'same-period denominator from the edition's notification annexure' (§5.1 "
         "row 4): 2023 net notified. " + net_note),
        (4, "denominator_matched_cohort", *ch("a3_3", "cohort_notified"), "§8.1 item 4",
         "Q2 variant only: patients notified in 2022 whose outcomes annexure 3.3 reports "
         "(printed note: 'total notified DSTB cases by current facility'). Stored in "
         "data/extracted/itr2024_tsr_cohort.csv."),
        (5, "numerator", *ch("a9", "paid_once"), "§5.1 row 5; §5.5",
         "Indicator 5 quantity (§5.5): 'paid at least once' is printed and is used, "
         "following the definition. 'All benefits paid' (Table 11.1 KPI) is not printed by state."),
        (5, "denominator", *ch("a9", "eligible"), "§5.1 row 5",
         "Total eligible TB patients. Karnataka printed '-' (blank): not computable (§5.2); "
         "the INDIA row equals the sum of the other 35 units."),
        (6, "numerator", *ch("a4_9", "mdr_initiated_total"), "§5.1 row 6",
         "JUDGEMENT CALL: 'initiated on treatment' (first column group), not 'initiated on "
         "second-line treatment', because the definition says 'initiated on treatment'."),
        (6, "denominator", *ch("a4_7", "rr_diagnosed_total"), "§5.1 row 6",
         "Net MDR patients diagnosed: annexure 4.7 counts 'based on current facility' "
         "(printed footnote). Identical, state by state, to annexure 4.8 first column "
         f"(PDF {_pages('a4_8')}), checked in code."),
        (7, "numerator", "not located", "", "", "§5.1 row 7; §5.4 items 4-5",
         "Missing. No state-wise expenditure-against-ROP table in ITR2024 (annexure list "
         "PDF 182-184; list of tables PDF 25; Table 16.1 PDF 174 is national). Controller "
         "ruling R4: no web search or download in this task."),
        (7, "denominator", "not located", "", "", "§5.1 row 7; §5.4 items 4-5",
         "Missing; see numerator."),
        (8, "numerator", *ch("a7_2", "initiated_tpt"), "§5.1 row 8; §5.5",
         "DEFINITIONAL MISMATCH (§5.5): household contacts under 5 years given TPT, not "
         "children under 6 given isoniazid chemoprophylaxis."),
        (8, "denominator", *ch("a7_2", "eligible_tpt"), "§5.1 row 8; §5.5",
         "Eligible = contacts under 5 not diagnosed with TB, matching 'total identified "
         "minus active TB'. DEFINITIONAL MISMATCH (§5.5): under 5, not under 6."),
        (9, "numerator", "not located", "", "", "§5.1 row 9; §5.4 item 4",
         "Missing. Candidate annexure 2.5 (PDF 203-204) prints no PLHIV given IPT/TPT."),
        (9, "denominator", "not located", "", "", "§5.1 row 9; §5.4 item 4",
         "Missing. Annexure 2.5 prints no eligible-PLHIV count (PLHIV with active TB "
         "ruled out)."),
        ("published_score", "score", "Table 11.2", str(SCORES_PAGE), "TB score",
         "§2 Q1; §7", "36 units, two decimals, stored as printed."),
        ("q3_secondary", "numerator", *ch("a4_13", "success"), "§9.2",
         "MDR/RR-TB treatment success, 2021 cohort; completed = success - cured "
         "(no 'completed' column printed). data/extracted/itr2024_drtb_outcomes.csv."),
        ("q3_secondary", "denominator", *ch("a4_13", "cohort_n"), "§9.2",
         "Lakshadweep printed #N/A in every cell: blank."),
        ("scoring_rule_R4", "bands", "not stated", "123;124;175", "", "§6.1; §5.4 item 7",
         "ITR2024 states no threshold bands for the score (chapter 11 text and Table 11.2 "
         "PDF 123; Box 11.1 PDF 124; Table 16.3 PDF 175). Other CTD documents not searched "
         "in this task."),
    ]
    cols = ("indicator", "component", "table_id", "pdf_pages", "column_header_verbatim",
            "rule_from_plan", "note")
    return [{"score_year": SCORE_YEAR, **dict(zip(cols, r))} for r in rows]


# ---- writing ---------------------------------------------------------------

def _fmt(v) -> str:
    return "" if v is None else str(v)


def _write_csv(path: Path, header: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        for r in rows:
            w.writerow([_fmt(r[h]) for h in header])


def write_all(pdf: Path, extracted: Path, choices_path: Path, check_path: Path) -> dict:
    tables = extract_tables(pdf)
    _check_missing_sources(pdf)
    check = target_check(pdf, check_path)
    scores = extract_scores(pdf)
    _write_csv(extracted / "itr2024_scores.csv",
               ["score_year", "state", "score", "source_file", "pdf_page", "table_id"],
               [{"score_year": SCORE_YEAR, "state": s, "score": scores[s],
                 "source_file": SOURCE_FILE, "pdf_page": SCORES_PAGE, "table_id": "Table 11.2"}
                for s in states.ALL])
    ind_rows, totals = build_indicators(tables, check["verdict"])
    _write_csv(extracted / "itr2024_indicators.csv",
               ["score_year", "state", "indicator", "numerator", "denominator",
                "source_file", "pdf_page", "table_id"], ind_rows)
    dr_rows, _ = extract_drtb_outcomes(tables)
    _write_csv(extracted / "itr2024_drtb_outcomes.csv",
               ["state", "cohort_year", "cohort_n", "cured", "completed", "success",
                "source_file", "pdf_page", "table_id"], dr_rows)
    t33 = tables["a3_3"]
    _write_csv(extracted / "itr2024_tsr_cohort.csv",
               ["state", "cohort_year", "cohort_notified", "success",
                "source_file", "pdf_page", "table_id"],
               [{"state": s, "cohort_year": 2022, **t33.rows[s], "source_file": SOURCE_FILE,
                 "pdf_page": t33.pages[s], "table_id": t33.spec.table_id}
                for s in states.ALL])
    _write_csv(choices_path,
               ["score_year", "indicator", "component", "table_id", "pdf_pages",
                "column_header_verbatim", "rule_from_plan", "note"],
               source_choices(check))
    return {"tables": tables, "check": check, "totals": totals, "indicators": ind_rows}


def main() -> None:
    res = write_all(PDF, ROOT / "data" / "extracted", ROOT / "data" / "source_choices.csv",
                    ROOT / "outputs" / "q1_target_check.txt")
    print("National-total checks (state sum = printed national row):")
    for t in res["tables"].values():
        for col, total, nat, nblank in check_national(t):
            extra = f"; blank: {', '.join(t.blanks[col])}" if nblank else ""
            print(f"  {t.spec.table_id} {col}: {total} = {t.spec.national_label} {nat} OK{extra}")
    c = res["check"]
    print(f"Plan 5.3: expected {c['expected']} vs target {c['target']}: "
          f"{c['relative']:.4%} -> {c['verdict']}")
    present = sorted({r["indicator"] for r in res["indicators"]})
    print(f"Indicators extracted: {present}")
    if c["verdict"] != "AGREE":
        print("Missing " + NOT_COMPUTABLE_1)
    for ind in sorted(MISSING):
        print("Missing " + MISSING[ind])


if __name__ == "__main__":
    main()

"""Extract the ICMR National TB Prevalence Survey 2019-21: state and state-group units.

Plan §9.1 (ruling R9). The survey reports microbiologically confirmed
pulmonary TB per 100,000 population aged >= 15 years for 20 "state groups"
(Table 20, PDF pp. 90-91). Table 20 prints two such measures; the one the
report calls its best estimate (the model with imputation and inverse
probability weighting) is used, and checked against Table 21 (PDF p. 95) and
annexure 9.2, Model 6 (PDF pp. 143-144).

Membership of each unit is read from the report, never inferred: annexure 9.2
labels each Table 20 row with an abbreviation (linked by identical P, N and
estimates), and the list of abbreviations (PDF pp. 10-11) expands it into
States/UTs. Section 2.1 (PDF p. 23) excludes Andaman & Nicobar and
Lakshadweep from the survey. Ladakh is not named anywhere in the report and
is listed as not covered.

No correlation is computed and no score is joined (Q3 is Task 9).

Run: python -I src/extract/ntps.py
Writes data/extracted/ntps_{units,not_covered,national}.csv and the "ntps"
rows of data/source_choices.csv (other rows are kept).
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
from src.extract import annex, pdftext  # noqa: E402

PDF = ROOT / "data_raw" / "icmr_ntps" / "NTPS_2019_21_report.pdf"
SOURCE_FILE = "data_raw/icmr_ntps/NTPS_2019_21_report.pdf"
TAG = "ntps"  # score_year column of data/source_choices.csv
TABLE = "Table 20"
T20_PAGES = (90, 91)
T21_PAGE = 95
ANNEX_PAGES = (142, 143, 144)  # annexure 9.2 "TB Prevalence by models"
ABBREV_PAGES = (10, 11, 12)
DESIGN_PAGE = 23
BEST_PAGES = (90, 93)
N_UNITS = 20  # "The country was grouped into 20 State groups" (p. 23)

HEADER = "Robust standard errors model with imputation and inverse probability weighting"
_HEADER_LINES = ("P N Crude Prevalence Robust standard errors", "model with imputation",
                 "and inverse probability", "weighting")
EXCLUSION_QUOTE = (
    "A population-based cross-sectional survey covered the entire country of India, except "
    "two small Union Territories i.e. Andaman & Nicobar islands and Lakshadweep islands which "
    "has less than 0.05% of the country’s population. These islands were excluded due to "
    "anticipated logistical and transportation issues.")
EXCLUSION_REASON = ("These islands were excluded due to anticipated logistical and "
                    "transportation issues.")
EXCLUDED = ("Andaman and Nicobar Islands", "Lakshadweep")
BEST_QUOTES = (
    (90, "The best estimates of the microbiologically confirmed PTB in India was 316 "
         "(290-342) per lakh population for the year 2021."),
    (93, "The best estimates of the microbiologically confirmed PTB for the 20 state groups "
         "are given in the figure 20."),
)
# Verbatim phrases of the abbreviation list that name one canonical unit.
PHRASES = {"Dadra, Nagar Haveli, Daman, Diu": "Dadra and Nagar Haveli and Daman and Diu"}

_EST = r"(\d+)\s*\(\s*(\d+)\s*-\s*(\d+)\s*\)"


# ---- parsers -------------------------------------------------------------------

def parse_row(line: str, ncounts: int) -> tuple[str, list[int], list[tuple[int, int, int]]] | None:
    """'Label P N est (lo - hi) est (lo - hi)' -> (label, counts, estimates);
    None if the line is not such a row. Exactly two estimates per row."""
    pat = (r"^([^\d(][^()]*?)" + r"\s+(\d+)" * ncounts
           + r"\s+" + _EST + r"\s*" + _EST + r"$")
    m = re.match(pat, line.strip())
    if not m:
        return None
    g = m.groups()
    counts = [int(x) for x in g[1:1 + ncounts]]
    e = [int(x) for x in g[1 + ncounts:]]
    return g[0].strip(), counts, [tuple(e[0:3]), tuple(e[3:6])]


def estimate_rows(lines: list[str], ncounts: int) -> list[tuple]:
    """Rows of an estimate table body. A label printed over several lines
    ("Himachal Pradesh," / "Uttarakhand," / "Jammu & Kashmir") is rejoined:
    a non-row line continues the previous label only if that label ends with
    a comma. Any other non-row line raises ValueError."""
    rows: list[list] = []
    for line in lines:
        r = parse_row(line, ncounts)
        if r is not None:
            rows.append(list(r))
        elif rows and rows[-1][0].endswith(","):
            rows[-1][0] = f"{rows[-1][0]} {line.strip()}"
        else:
            raise ValueError(f"unexpected line: {line!r}")
    return [tuple(r) for r in rows]


_ABBR = re.compile(r"^([A-Z][A-Za-z&-]*(?:,[A-Z]+)*)\s+(.+)$")


def parse_abbreviations(lines: list[str]) -> dict[str, str]:
    """Abbreviation -> expansion. An expansion with an unclosed '(' continues
    on the following line(s)."""
    out: dict[str, str] = {}
    last = None
    for line in lines:
        line = line.strip()
        if last and out[last].count("(") > out[last].count(")"):
            out[last] = f"{out[last]} {line}"
            continue
        m = _ABBR.match(line)
        if not m:
            continue  # page heading ("Abbreviations")
        last = m.group(1)
        if last in out:
            raise ValueError(f"duplicate abbreviation {last!r}")
        out[last] = m.group(2)
    return out


def members_of(expansion: str) -> list[str]:
    """Canonical States/UTs named by an abbreviation's expansion. A group name
    followed by a parenthesised list ('North Eastern States (...)') is the
    list. KeyError for any part that is not a State/UT."""
    m = re.fullmatch(r"[^()]*\((.*)\)", expansion)
    text = m.group(1) if m else expansion
    for phrase, name in PHRASES.items():
        text = text.replace(phrase, name)
    return [states.canonical(p) for p in re.split(r",\s*|\s+And\s+", text) if p.strip()]


# ---- the report ------------------------------------------------------------------

@lru_cache(maxsize=None)
def _lines(pdf: str, page: int) -> tuple[str, ...]:
    lines = tuple(pdftext.page_lines(Path(pdf), page))
    if not "".join(lines).strip():
        raise ValueError(f"BLOCKED: PDF p. {page} has no text layer (no OCR)")
    return lines


def _text(pdf: str, page: int) -> str:
    return " ".join(_lines(pdf, page))


def _body(lines: tuple[str, ...], start: str, stop: str) -> list[str]:
    """Lines after the line equal to `start` up to the first starting with `stop`."""
    i = lines.index(start) + 1
    j = next(k for k in range(i, len(lines)) if lines[k].startswith(stop))
    return list(lines[i:j])


def _check_header(lines: tuple[str, ...], page: int) -> None:
    i = lines.index(_HEADER_LINES[0])
    if lines[i:i + 4] != _HEADER_LINES:
        raise ValueError(f"{TABLE} column header changed on PDF p. {page}")


def _table20(pdf: str) -> tuple[str, dict, list[dict]]:
    p90, p91 = (_lines(pdf, p) for p in T20_PAGES)
    t = next(k for k, ln in enumerate(p90) if ln.startswith(TABLE + " "))
    title = f"{p90[t]} {p90[t + 1]}"[len(TABLE) + 1:]
    if title != ("Prevalence of microbiologically confirmed pulmonary TB among population "
                 "aged ≥ 15 years in India (per 100 000 population) by gender, age group "
                 "and states"):
        raise ValueError(f"{TABLE} title changed: {title!r}")
    for lines, page in ((p90, 90), (p91, 91)):
        _check_header(lines, page)
    india = [ln for ln in p90 if ln.startswith("India ")]
    if len(india) != 1:
        raise ValueError(f"{TABLE}: expected one India row, got {india}")
    nat = parse_row(india[0], 2)
    units = []
    for lines, page, start, stop in ((p90, 90, "State Group", "RESULTS 63"),
                                     (p91, 91, "weighting", "Crude prevalence and their")):
        for label, counts, ests in estimate_rows(_body(lines, start, stop), 2):
            units.append({"unit": label, "n_positive": counts[0], "n_screened": counts[1],
                          "crude": ests[0], "best": ests[1], "pdf_page": page})
    return title, {"unit": "India", "n_positive": nat[1][0], "n_screened": nat[1][1],
                   "crude": nat[2][0], "best": nat[2][1], "pdf_page": 90}, units


def _table21(pdf: str) -> dict[str, tuple[int, int, int]]:
    lines = _lines(pdf, T21_PAGE)
    if not lines[0].startswith("Table 21 Adjusted prevalence of all forms of TB"):
        raise ValueError(f"Table 21 not on PDF p. {T21_PAGE}")
    rows = estimate_rows(_body(lines, "and Paediatric age group", "RESULTS 68"), 0)
    return {label: ests[0] for label, _, ests in rows}


_ANNEX_ROW = re.compile(r"^([A-Z][A-Z, ]*?)\s+(\d+)\s+([\d,]+)((?:\s+\d+){6})$")


def _annex92(pdf: str) -> list[dict]:
    """Annexure 9.2 state-group rows: label, P, N, Model 1..6 (est, lo, hi), page."""
    if "9.2 TB Prevalence by models" not in _lines(pdf, ANNEX_PAGES[0]):
        raise ValueError(f"annexure 9.2 not on PDF p. {ANNEX_PAGES[0]}")
    body: list[tuple[str, int]] = []
    on = False
    for page in ANNEX_PAGES[1:]:
        for ln in _lines(pdf, page):
            if ln == "State Group":
                on = True
            elif ln.startswith("Model - 1,"):
                on = False
            elif on and not (ln.startswith("P N Model 1") or re.fullmatch(r"ANNEXURES \d+", ln)):
                body.append((ln, page))
    if len(body) % 2:
        raise ValueError("annexure 9.2: rows and interval lines do not pair")
    out = []
    for (row, page), (ci, _) in zip(body[0::2], body[1::2]):
        m = _ANNEX_ROW.match(row)
        cis = re.findall(r"\((\d+) - (\d+)\)", ci)
        if not m or len(cis) != 6 or re.sub(r"\(\d+ - \d+\)|\s", "", ci):
            raise ValueError(f"annexure 9.2: unexpected rows {row!r} / {ci!r}")
        ests = [int(x) for x in m.group(4).split()]
        out.append({"label": m.group(1), "p": int(m.group(2)),
                    "n": int(m.group(3).replace(",", "")), "page": page,
                    "models": [(e, int(lo), int(hi)) for e, (lo, hi) in zip(ests, cis)]})
    return out


def _abbreviations(pdf: str) -> tuple[dict[str, str], dict[str, int]]:
    lines, pages = [], []
    for page in ABBREV_PAGES:
        for ln in _lines(pdf, page):
            lines.append(ln)
            pages.append(page)
    if lines[0] != "Abbreviations":
        raise ValueError(f"list of abbreviations not on PDF p. {ABBREV_PAGES[0]}")
    ab = parse_abbreviations(lines)
    where = {}
    for k in ab:  # page of the line that starts the abbreviation
        where[k] = next(p for ln, p in zip(lines, pages) if ln.startswith(k + " "))
    return ab, where


def _check_quotes(pdf: str) -> None:
    if EXCLUSION_QUOTE not in _text(pdf, DESIGN_PAGE):
        raise ValueError(f"exclusion of the islands not found on PDF p. {DESIGN_PAGE}")
    for page, quote in BEST_QUOTES:
        if quote not in _text(pdf, page):
            raise ValueError(f"'best estimates' wording not found on PDF p. {page}")


@lru_cache(maxsize=None)
def _mentions_ladakh(pdf: str) -> list[int]:
    import pdfplumber  # only to count pages; lines come from pdftext
    with pdfplumber.open(pdf) as doc:
        n = len(doc.pages)
        return [i for i in range(1, n + 1)
                if "ladakh" in (doc.pages[i - 1].extract_text() or "").casefold()]


@lru_cache(maxsize=None)
def _extract(pdf: str) -> dict:
    title, nat, rows = _table20(pdf)
    if len(rows) != N_UNITS:
        raise ValueError(f"{TABLE}: {len(rows)} state groups, expected {N_UNITS}")
    for key in ("n_positive", "n_screened"):  # printed total
        tot = sum(r[key] for r in rows)
        if tot != nat[key]:
            raise ValueError(f"{TABLE}: {key} sums to {tot}, India row prints {nat[key]}")
    t21 = _table21(pdf)
    if set(t21) != {r["unit"] for r in rows} | {"India"}:
        raise ValueError(f"Table 21 labels differ from {TABLE}: {sorted(t21)}")
    for r in rows + [nat]:
        if t21[r["unit"]] != r["best"]:
            raise ValueError(f"Table 21 differs from {TABLE} for {r['unit']}")
        est, lo, hi = r["best"]
        if not lo < est < hi:
            raise ValueError(f"{r['unit']}: CI ({lo}-{hi}) does not bracket {est}")
    _check_quotes(pdf)
    ab, ab_page = _abbreviations(pdf)
    annex92 = _annex92(pdf)
    if len(annex92) != N_UNITS:
        raise ValueError(f"annexure 9.2: {len(annex92)} state groups, expected {N_UNITS}")
    measure = f"{title}: {HEADER}"
    units, seen = [], {}
    for r in rows:
        hits = [a for a in annex92 if (a["p"], a["n"]) == (r["n_positive"], r["n_screened"])
                and a["models"][0] == r["crude"] and a["models"][5] == r["best"]]
        if len(hits) != 1:
            raise ValueError(f"{r['unit']}: {len(hits)} matching annexure 9.2 rows")
        a = hits[0]
        abbr = a["label"].replace(" ", "")
        if abbr not in ab:
            raise ValueError(f"annexure 9.2 label {a['label']!r} not in the abbreviation list")
        listed = members_of(ab[abbr])
        head = ab[abbr].split(" (")[0]
        named = (listed if r["unit"] == head
                 else [states.canonical(x) for x in r["unit"].split(", ")])
        if listed[:len(named)] != named:
            raise ValueError(f"{r['unit']!r} does not agree with {abbr} = {ab[abbr]!r}")
        members = [s for s in listed if s not in EXCLUDED]
        for s in members:
            if s in seen:
                raise ValueError(f"{s} in both {seen[s]!r} and {r['unit']!r}")
            seen[s] = r["unit"]
        note = (f"Members from the list of abbreviations (PDF p. {ab_page[abbr]}): "
                f"'{abbr} {ab[abbr]}'. Linked to this {TABLE} row through annexure 9.2 "
                f"(PDF p. {a['page']}), whose row '{a['label']}' prints the same P, N, "
                f"Model 1 (crude) and Model 6 estimates.")
        dropped = [s for s in listed if s in EXCLUDED]
        if dropped:
            note += (f" {' and '.join(dropped)}: not surveyed ('{EXCLUSION_REASON}', "
                     f"PDF p. {DESIGN_PAGE}); listed in ntps_not_covered.csv.")
        est, lo, hi = r["best"]
        units.append({
            "unit": r["unit"], "unit_type": "group" if len(members) > 1 else "state",
            "member_states": members, "prevalence": est, "ci_low": lo, "ci_high": hi,
            "n_positive": r["n_positive"], "n_screened": r["n_screened"],
            "measure_verbatim": measure, "source_file": SOURCE_FILE,
            "pdf_page": r["pdf_page"], "table_id": TABLE, "unit_abbrev": abbr,
            "membership_pages": f"{ab_page[abbr]};{a['page']}", "note": note})
    ladakh = _mentions_ladakh(pdf)
    if ladakh:
        raise ValueError(f"the report mentions Ladakh on PDF pp. {ladakh}: re-examine")
    not_covered = [{"state": s, "reason": EXCLUSION_REASON, "source_file": SOURCE_FILE,
                    "pdf_page": DESIGN_PAGE,
                    "note": f"Section 2.1 Study Design: '{EXCLUSION_QUOTE}' The list of "
                            f"abbreviations nevertheless names it in a group label "
                            f"({'TN,PY,AN' if s.startswith('Andaman') else 'KL,LD'})."}
                   for s in EXCLUDED]
    not_covered.append({
        "state": "Ladakh", "reason": "not listed in survey units", "source_file": SOURCE_FILE,
        "pdf_page": "",
        "note": "No page of the report names Ladakh. 'Jammu & Kashmir' (HP,UK,JK, PDF p. 10) "
                "is not taken to include it: membership is not inferred."})
    for row in not_covered:
        if row["state"] in seen:
            raise ValueError(f"{row['state']} is both covered and not covered")
        seen[row["state"]] = "not covered"
    states.require_all(seen, 2023)
    est, lo, hi = nat["best"]
    national = {"unit": "India", "prevalence": est, "ci_low": lo, "ci_high": hi,
                "n_positive": nat["n_positive"], "n_screened": nat["n_screened"],
                "measure_verbatim": measure, "source_file": SOURCE_FILE,
                "pdf_page": nat["pdf_page"], "table_id": TABLE}
    return {"units": units, "not_covered": not_covered, "national": national,
            "abbreviations": {u["unit_abbrev"]: ab[u["unit_abbrev"]] for u in units}}


def extract(pdf: Path = PDF) -> dict:
    """Units, not-covered States/UTs and the national row (fails loudly)."""
    return _extract(str(pdf))


# ---- outputs ---------------------------------------------------------------------

UNIT_COLS = ["unit", "unit_type", "member_states", "prevalence", "ci_low", "ci_high",
             "n_positive", "n_screened", "measure_verbatim", "source_file", "pdf_page",
             "table_id", "unit_abbrev", "membership_pages", "note"]
NOT_COVERED_COLS = ["state", "reason", "source_file", "pdf_page", "note"]
NATIONAL_COLS = ["unit", "prevalence", "ci_low", "ci_high", "n_positive", "n_screened",
                 "measure_verbatim", "source_file", "pdf_page", "table_id"]


def source_choices(res: dict) -> list[dict]:
    base = {"score_year": TAG, "indicator": "q3_primary"}
    groups = "; ".join(f"{k} = {v}" for k, v in res["abbreviations"].items())
    return [
        base | {"component": "prevalence", "table_id": TABLE, "pdf_pages": "90;91",
                "column_header_verbatim": HEADER,
                "rule_from_plan": "§9.1 (ruling R9): microbiologically confirmed pulmonary TB "
                                  "per 100,000 aged >= 15 years, with 95% CI",
                "note": f"{TABLE} ('{res['units'][0]['measure_verbatim'].split(': ')[0]}') "
                        "prints two measures for each of the 20 state groups, both "
                        "microbiologically confirmed pulmonary TB per 100,000 aged >= 15 years: "
                        "'Crude Prevalence' (exact binomial CI) and the column used here. The "
                        "report calls the latter its best estimate ('" + BEST_QUOTES[0][1]
                        + "', PDF p. 90; '" + BEST_QUOTES[1][1] + "', PDF p. 93) and plots it "
                        "in Figure 20 (PDF p. 94). Checked equal to Table 21's first column "
                        "(PDF p. 95) and annexure 9.2 Model 6 (PDF pp. 143-144). The crude "
                        "column is not used."},
        base | {"component": "membership", "table_id": "List of abbreviations; annexure 9.2",
                "pdf_pages": "10;11;143;144", "column_header_verbatim": "State Group",
                "rule_from_plan": "§9.1 Aggregation; membership read from the report, "
                                  "never inferred",
                "note": f"Each {TABLE} row is linked to its annexure 9.2 row by identical P, N "
                        "and estimates; the annexure's label is expanded from the list of "
                        f"abbreviations. {groups}."},
        base | {"component": "not_covered", "table_id": "Section 2.1 Study Design",
                "pdf_pages": str(DESIGN_PAGE), "column_header_verbatim": EXCLUSION_QUOTE,
                "rule_from_plan": "§9.1 Aggregation: States the survey does not cover are "
                                  "listed and excluded",
                "note": "Andaman and Nicobar Islands and Lakshadweep are excluded as printed, "
                        "although the abbreviations TN,PY,AN and KL,LD name them. Ladakh is "
                        "named nowhere in the report: 'not listed in survey units'. See "
                        "data/extracted/ntps_not_covered.csv."},
        base | {"component": "national", "table_id": TABLE, "pdf_pages": "90",
                "column_header_verbatim": f"India: {HEADER}",
                "rule_from_plan": "Recorded, not mixed into the units",
                "note": f"India {res['national']['prevalence']} ({res['national']['ci_low']}-"
                        f"{res['national']['ci_high']}); data/extracted/ntps_national.csv."},
    ]


def write_all(pdf: Path, extracted: Path, choices_path: Path) -> dict:
    res = extract(pdf)
    annex.write_csv(extracted / "ntps_units.csv", UNIT_COLS,
                    [u | {"member_states": ";".join(u["member_states"])} for u in res["units"]])
    annex.write_csv(extracted / "ntps_not_covered.csv", NOT_COVERED_COLS, res["not_covered"])
    annex.write_csv(extracted / "ntps_national.csv", NATIONAL_COLS, [res["national"]])
    annex.merge_source_choices(choices_path, TAG, source_choices(res))
    return res


def main() -> None:
    res = write_all(PDF, ROOT / "data" / "extracted", ROOT / "data" / "source_choices.csv")
    nat = res["national"]
    print(f"{TABLE}: {len(res['units'])} units; India {nat['prevalence']} "
          f"({nat['ci_low']}-{nat['ci_high']}), P and N sum to the India row")
    for u in res["units"]:
        print(f"  {u['unit']} [{u['unit_abbrev']}] {u['prevalence']} "
              f"({u['ci_low']}-{u['ci_high']}): {'; '.join(u['member_states'])}")
    for r in res["not_covered"]:
        print(f"  not covered: {r['state']} ({r['reason']})")


if __name__ == "__main__":
    main()

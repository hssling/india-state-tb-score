"""India TB Report 2021 edition (score year 2020): BLOCKED.

The file is a scan. Every page is a mosaic of images with no text layer
(one page in 352 carries 130 characters of a photo caption), so no table can
be read without OCR, and the task rules forbid OCR-guessing numbers. This
module records that finding reproducibly and writes the edition's rows of
data/extracted/definitions.csv. It writes no indicator file and no source
choice: the freeze rule (plan §5.4 item 7) records choices only together with
an extraction.

Pages located visually (PDF page = printed page + 22, from the annexure
contents page, printed 185 = PDF 207, and chapter 7, printed 65 = PDF 87):
see NEEDED_PAGES.

Run: python -I src/extract/itr2021.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from src.extract import annex  # noqa: E402

PDF = ROOT / "data_raw" / "india_tb_report" / "ITR2021.pdf"
EDITION = 2021
SCORE_YEAR = 2020

# PDF page -> what is on it (titles read from the rendered annexure contents,
# PDF 207-208; table pages are the first page of each annexure).
NEEDED_PAGES: dict[int, str] = {
    87: "chapter 7 'State TB Score' text and 'STATE TB SCORE Indicators: Maximum Total "
        "Score 100', indicators 1-7 (printed p. 65)",
    88: "indicators 8-9; district rankings (printed p. 66)",
    207: "Annexures contents, part 1 (printed p. 185)",
    208: "Annexures contents, part 2 (printed p. 186)",
    211: "annexure 1.2 TB case notification rate and achievement against target (printed 189)",
    217: "annexure 1.4 Patient transfer status & treatment initiation status (printed 195)",
    227: "annexure 2.1 TB-HIV (printed 205)",
    233: "annexure 2.4 Intensified TB case finding activities in ART centre (printed 211)",
    254: "annexure 3.3 Treatment outcome of TB patients notified in 2019 (Total) (printed 232)",
    286: "annexure 4.2 Case finding - UDST testing & MDR patients management (printed 264)",
    293: "annexure 4.5 Treatment outcome of MDR/RR TB patients initiated during 2017 "
         "(printed 271)",
    314: "annexure 7 Nikshay Poshan Yojana (printed 292)",
    319: "annexure 8.3 Contact tracing and isoniazid chemoprophylaxis in household "
         "contacts < 6 years (printed 297)",
}


class Blocked(RuntimeError):
    """The edition cannot be extracted under the task rules."""


def text_layer_status(pdf: Path = PDF) -> dict:
    doc = annex.Doc(pdf)
    with_text = {p: doc.chars(p) for p in NEEDED_PAGES if doc.chars(p) > 0}
    return {"pages": doc.n_pages(), "checked": sorted(NEEDED_PAGES), "with_text": with_text}


def extract_tables(pdf: Path = PDF) -> None:
    st = text_layer_status(pdf)
    if not st["with_text"]:
        raise Blocked(
            "ITR2021: no text layer on the needed pages (PDF "
            + ", ".join(map(str, st["checked"]))
            + "); the tables are scanned images and OCR is not allowed")
    raise Blocked(f"ITR2021: pages {sorted(st['with_text'])} now have text: write the extractor")


# The definition as printed on PDF pp. 87-88 (printed 65-66), read from the
# rendered scan: there is no text layer, so it cannot be machine-checked.
_TRANSCRIBED = ("Transcribed by eye from the scanned page (no text layer; not machine-"
                "verified; needs a second reader).")
_INDICATORS: tuple[tuple[int, int, int, str, str, str, str], ...] = (
    (1, 20, 87, "% of Target TB notification achieved",
     "Total TB patients notified during the defined period",
     "Target TB patients estimated for the year", "As plan §5.1 row 1."),
    (2, 10, 87, "% of TB notified patients with known HIV status",
     "Number of patients with HIV status known i.e., HIV result is either positive or "
     "negative/ Reactive or Non-reactive",
     "Net TB patients notified during the defined period", "As plan §5.1 row 2."),
    (3, 10, 87, "% of TB notified patients with UDST done",
     "Number of patients with UDST done and Rifampicin status known i.e,. Rifampicin status "
     "is either Sensitive or Resistant",
     "State Benchmark of Net TB patients notified during the defined period",
     "As plan §5.1 row 3; the benchmark level (70% in plan §5.2) is not stated here."),
    (4, 15, 87, "Treatment Success Rate",
     "Number of TB patients with treatment outcome given as success i.e.,. either cured or "
     "treatment completed",
     "Net TB patients notified during the same period previous year",
     "DIFFERS from plan §5.1 row 4 ('during the same period'): the denominator is the "
     "previous year's net notified, i.e. the treatment cohort (the matched-cohort "
     "denominator of §8.1 item 4)."),
    (5, 10, 87, "% of Eligible beneficiaries paid under Nikshay Poshan Yojana",
     "TB patients in whom payment has been done at least once",
     "Total eligible TB patients during the same period",
     "As plan §5.1 row 5 ('at least once')."),
    (6, 15, 87, "% of MDR/ RR patients initiated on treatment out of total diagnosed",
     "Number of MDR patients initiated on treatment during the defined period",
     "Net MDR patients diagnosed during the defined period",
     "As plan §5.1 row 6 (name says 'total diagnosed', denominator 'Net')."),
    (7, 10, 87, "% of expenditure amongst the approved ROP",
     "Fund utilised in the defined period", "ROP as approved during the financial year",
     "As plan §5.1 row 7."),
    (8, 5, 88, "% of children given chemoprophylaxis from the total eligible children "
               "identified",
     "Number of children < 6 years given Isoniazid Chemoprophylaxis",
     "No. of children < 6 years eligible for chemoprophylaxis (Totalchildren identified – "
     "Children with active TB detected/treated)",
     "As plan §5.1 row 8 (< 6 years, isoniazid)."),
    (9, 5, 88, "% of PLHIV given IPT from the total eligible PLHIV",
     "Number of PLHIV given IPT",
     "No. of PLHIV in whom active TB has been ruled out among the PLHIV attending the ART "
     "centre", "As plan §5.1 row 9."),
)


def definitions() -> list[dict]:
    base = {"edition": EDITION, "score_year": SCORE_YEAR}
    rows = [
        {**base, "indicator_no": "scores", "points": "", "source_page": "87;88",
         "indicator_text_verbatim": "",
         "note": "Not determined (BLOCKED): the edition has no text layer and could not be "
                 "searched. Chapter 7 (PDF 83-90, printed 61-68) shows no state score table; "
                 "PDF 88 ranks districts only (top 5 in the country; aspirational and tribal "
                 "districts). " + _TRANSCRIBED},
        {**base, "indicator_no": "categories", "points": "", "source_page": "87",
         "indicator_text_verbatim": "The country was grouped into 3 categories viz: Union "
                                    "Territories, States with population less than 50 lakhs "
                                    "& States with population more than 50 lakhs.",
         "note": "Districts are also ranked on the same indicators. " + _TRANSCRIBED},
        {**base, "indicator_no": "total", "points": 100, "source_page": "87",
         "indicator_text_verbatim": "STATE TB SCORE Indicators: Maximum Total Score 100",
         "note": "Table of 9 indicators with numerator, denominator and score columns. "
                 + _TRANSCRIBED},
    ]
    for n, pts, page, name, num, den, diff in _INDICATORS:
        rows.append({**base, "indicator_no": n, "points": pts, "source_page": page,
                     "indicator_text_verbatim":
                         f"{name} | Numerator: {num} | Denominator: {den}",
                     "note": f"{diff} {_TRANSCRIBED}"})
    if sum(r["points"] for r in rows if isinstance(r["indicator_no"], int)) != 100:
        raise ValueError("2021 points do not sum to the stated 100")
    return rows


def write_definitions(extracted: Path) -> None:
    annex.merge_definitions(extracted / "definitions.csv", EDITION, definitions())


def main() -> None:
    write_definitions(ROOT / "data" / "extracted")
    try:
        extract_tables(PDF)
    except Blocked as e:
        print(f"BLOCKED: {e}")
        for p, what in NEEDED_PAGES.items():
            print(f"  PDF p. {p}: {what}")


if __name__ == "__main__":
    main()

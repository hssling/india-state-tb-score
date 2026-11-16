"""Task 4: India TB Report 2024 (score year 2023) extraction."""
import csv
from pathlib import Path

import pytest

from src import states
from src.extract import itr2024

PDF = Path("data_raw/india_tb_report/ITR2024.pdf")
needs_pdf = pytest.mark.skipif(not PDF.exists(), reason="data_raw/ITR2024.pdf absent")
EXTRACTED = Path("data/extracted")


# ---- cell and row parsing (no PDF needed) ---------------------------------

def test_split_cells_blank_count_with_percentage():
    # Annexure 1.4, Lakshadweep: private cells print "(0)" with no count.
    c = itr2024.split_cells("6 (100) (0) 6 14 (100) (0) 14 14 (100) NA 14 (100)")
    assert [x.n for x in c] == ["6", None, "6", "14", None, "14", "14", None, "14"]


def test_split_cells_wrapped_percentages_are_ignored():
    c = itr2024.split_cells("15052 1075 16127 7258 (51%)")
    assert [x.n for x in c] == ["15052", "1075", "16127", "7258"]


def test_split_cells_spreadsheet_errors_are_blank_cells():
    c = itr2024.split_cells("9 (64%) #DIV/0! 9 (64%) #N/A - NA")
    assert [x.n for x in c] == ["9", None, "9", None, None, None]


def test_split_cells_rejects_text():
    with pytest.raises(ValueError):
        itr2024.split_cells("12 abc 4")


def test_parse_rows_joins_names_and_skips_percentage_lines():
    lines = ["States/UTs Public Private Total",
             "Andaman and 655 92 747", "Nicobar Islands",
             "Bihar 1 2 3", "(63%) (26%) (52%)",
             "INDIA 656 94 750", "(57%) (28%) (50%)"]
    rows, national = itr2024.parse_rows(lines, ncells=3, national_label="INDIA")
    assert [c.n for c in rows["Andaman and Nicobar Islands"]] == ["655", "92", "747"]
    assert [c.n for c in rows["Bihar"]] == ["1", "2", "3"]
    assert [c.n for c in national] == ["656", "94", "750"]


def test_parse_rows_fails_loudly_on_cell_count_mismatch():
    with pytest.raises(ValueError, match="Goa"):
        itr2024.parse_rows(["Goa 1 2", "INDIA 1 2 3"], ncells=3, national_label="INDIA")


def test_parse_rows_rejects_duplicate_state():
    with pytest.raises(ValueError, match="Goa"):
        itr2024.parse_rows(["Goa 1", "Goa 2", "INDIA 3"], ncells=1, national_label="INDIA")


def test_parse_rows_requires_one_national_row():
    with pytest.raises(ValueError, match="INDIA"):
        itr2024.parse_rows(["Goa 1"], ncells=1, national_label="INDIA")


def test_scores_parse_two_column_wrapped_layout():
    lines = ["Table 11.2: TB score of States/UTs",
             "States/UTs TB score States/UTs TB score",
             "Chhattisgarh 78.13 Nagaland 81.31",
             "Dadra and Nagar Haveli and Daman 98.04 Odisha 93.45",
             "and Diu Puducherry 91.56",
             "Jammu & Kashmir 87.82 Uttar Pradesh 87.40",
             "Ladakh 94.82",
             "#TBHaregaDeshJeetega India TB Report 2024 93"]
    got = itr2024.parse_scores(lines)
    assert got == {"Chhattisgarh": "78.13", "Nagaland": "81.31",
                   "Dadra and Nagar Haveli and Daman and Diu": "98.04",
                   "Odisha": "93.45", "Puducherry": "91.56",
                   "Jammu and Kashmir": "87.82", "Uttar Pradesh": "87.40",
                   "Ladakh": "94.82"}


def test_target_verdict_tolerance():
    assert itr2024.target_verdict(2_761_682 + 2761, 2_761_682) == "AGREE"
    assert itr2024.target_verdict(2_761_682 - 2761, 2_761_682) == "AGREE"
    assert itr2024.target_verdict(2_761_682 + 2762, 2_761_682) == "DISAGREE"


# ---- the 2024 edition ------------------------------------------------------

@needs_pdf
def test_scores_36_units():
    scores = itr2024.extract_scores(PDF)
    assert len(scores) == 36
    states.require_all(scores, 2023)
    assert scores["Odisha"] == "93.45"
    assert scores["Manipur"] == "71.61"
    assert scores["Dadra and Nagar Haveli and Daman and Diu"] == "98.04"


@needs_pdf
def test_each_table_matches_printed_total():
    tables = itr2024.extract_tables(PDF)
    assert tables, "no tables extracted"
    for key, t in tables.items():
        states.require_all(t.rows, 2023)
        for col in t.spec.columns:
            vals = [r[col] for r in t.rows.values() if r[col] is not None]
            assert sum(vals) == t.national[col], (key, col)
    # and per indicator: numerators and denominators sum to the printed rows
    verdict = itr2024.target_check(PDF)["verdict"]
    rows, totals = itr2024.build_indicators(tables, verdict)
    assert totals
    for ind, (num_total, den_total) in totals.items():
        mine = [r for r in rows if r["indicator"] == ind]
        assert sum(r["numerator"] for r in mine if r["numerator"] is not None) == num_total, ind
        assert sum(r["denominator"] for r in mine if r["denominator"] is not None) == den_total, ind


@needs_pdf
def test_expected_equals_target(tmp_path):
    out = tmp_path / "q1_target_check.txt"
    res = itr2024.target_check(PDF, out)
    assert res["target"] == 2_761_682
    assert res["verdict"] in ("AGREE", "DISAGREE")
    text = out.read_text(encoding="utf-8")
    assert "2761682" in text
    assert f"Verdict: {res['verdict']}" in text


@needs_pdf
def test_indicator_rows():
    tables = itr2024.extract_tables(PDF)
    verdict = itr2024.target_check(PDF)["verdict"]
    rows, _ = itr2024.build_indicators(tables, verdict)
    present = {r["indicator"] for r in rows}
    assert present <= set(range(1, 10))
    assert 7 not in present and 9 not in present
    assert (1 in present) == (verdict == "AGREE")
    for ind in present:
        mine = [r for r in rows if r["indicator"] == ind]
        assert len(mine) == 36, ind
        states.require_all([r["state"] for r in mine], 2023)
    # a blank printed cell stays blank: Karnataka's NPY eligible count is "-"
    ka5 = next(r for r in rows if r["indicator"] == 5 and r["state"] == "Karnataka")
    assert ka5["denominator"] is None and ka5["numerator"] is not None


@needs_pdf
def test_drtb_outcomes():
    rows, national = itr2024.extract_drtb_outcomes(itr2024.extract_tables(PDF))
    assert len(rows) == 36
    states.require_all([r["state"] for r in rows], 2023)
    for r in rows:
        if r["success"] is not None:
            assert r["success"] == r["cured"] + r["completed"]
    for col in ("cohort_n", "cured", "success"):
        assert sum(r[col] for r in rows if r[col] is not None) == national[col]


@needs_pdf
def test_committed_csvs_match_extraction(tmp_path):
    itr2024.write_all(PDF, tmp_path / "extracted", tmp_path / "source_choices.csv",
                      tmp_path / "q1_target_check.txt")
    for name in ("itr2024_scores.csv", "itr2024_indicators.csv",
                 "itr2024_drtb_outcomes.csv", "itr2024_tsr_cohort.csv"):
        assert (tmp_path / "extracted" / name).read_text(encoding="utf-8") == \
            (EXTRACTED / name).read_text(encoding="utf-8"), name
    assert (tmp_path / "source_choices.csv").read_text(encoding="utf-8") == \
        Path("data/source_choices.csv").read_text(encoding="utf-8")


def test_source_choices_cover_every_indicator():
    with open("data/source_choices.csv", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows and set(rows[0]) >= {
        "score_year", "indicator", "component", "table_id", "pdf_pages",
        "column_header_verbatim", "rule_from_plan", "note"}
    for i in range(1, 10):
        comps = {r["component"] for r in rows if r["indicator"] == str(i)}
        assert {"numerator", "denominator"} <= comps, i

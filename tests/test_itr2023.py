"""Task 8a: India TB Report 2023 (score year 2022) extraction."""
import csv
import re
from pathlib import Path

import pytest

from src import states
from src.extract import annex, itr2023

PDF = Path("data_raw/india_tb_report/ITR2023.pdf")
needs_pdf = pytest.mark.skipif(not PDF.exists(), reason="data_raw/ITR2023.pdf absent")
EXTRACTED = Path("data/extracted")
FOOT = re.compile(r"\d*\s*INDIA TB REPORT 2023\s*\d*")


# ---- row assembly (no PDF needed) ------------------------------------------

def test_split_cells_na_percentage():
    c = annex.split_cells("11 (55) 0 (NA) 11 (55)")
    assert [x.n for x in c] == ["11", "0", "11"]


def test_assemble_rows_names_wrapped_around_values():
    lines = ["Public Private Total",
             "Andaman & Nicobar", "520 10 530", "Islands",
             "Andhra 1 2 3", "Pradesh (41) (93.1)",
             "Dadra And Nagar", "Haveli And Daman 9 8 17", "And Diu",
             "India 530 20 550", "(98) (97)"]
    rows, nat = annex.assemble_rows(lines, 3, ("India",), 2022)
    assert [c.n for c in rows["Andaman and Nicobar Islands"]] == ["520", "10", "530"]
    assert [c.n for c in rows["Andhra Pradesh"]] == ["1", "2", "3"]
    assert [c.n for c in rows["Dadra and Nagar Haveli and Daman and Diu"]] == ["9", "8", "17"]
    assert [c.n for c in nat] == ["530", "20", "550"]


def test_assemble_rows_strips_footer_with_wrapped_percentages():
    lines = ["Goa 1 2 3", "221 INDIA TB REPORT 2023(23) (86.3)", "Gujarat 4 5 6"]
    rows, nat = annex.assemble_rows(lines, 3, ("India",), 2022, FOOT)
    assert set(rows) == {"Goa", "Gujarat"} and nat is None


def test_assemble_rows_fails_loudly():
    with pytest.raises(ValueError, match="Goa"):
        annex.assemble_rows(["Goa 1 2"], 3, ("India",), 2022)
    with pytest.raises(ValueError, match="unexpected line"):
        annex.assemble_rows(["Goa 1 2 3", "Some note 4"], 3, ("India",), 2022)
    with pytest.raises(ValueError, match="footer"):
        annex.assemble_rows(["Goa 1 2 3", "195 INDIA TB REPORT 2023 (12) 44"], 3, ("India",), 2022,
                            FOOT)
    with pytest.raises(ValueError, match="duplicate"):
        annex.assemble_rows(["Goa 1", "Goa 2"], 1, ("India",), 2022)


def test_merge_source_choices_keeps_other_years(tmp_path):
    path = tmp_path / "sc.csv"
    row = lambda y, n: {k: "" for k in annex.SOURCE_CHOICE_COLS} | {  # noqa: E731
        "score_year": y, "indicator": n}
    annex.merge_source_choices(path, 2023, [row(2023, 1)])
    annex.merge_source_choices(path, 2022, [row(2022, 1), row(2022, 2)])
    annex.merge_source_choices(path, 2023, [row(2023, 5)])
    with open(path, encoding="utf-8", newline="") as f:
        got = [(r["score_year"], r["indicator"]) for r in csv.DictReader(f)]
    assert got == [("2023", "5"), ("2022", "1"), ("2022", "2")]


# ---- the 2023 edition --------------------------------------------------------

@needs_pdf
def test_no_state_scores_printed():
    assert itr2023.extract_scores(PDF) is None


@needs_pdf
def test_annexure_pages_found_by_title():
    off, pages = itr2023.locate_tables(PDF)
    assert off == 30
    assert pages["a1_2"] == (213, 214) and pages["a2_1"] == (225,)
    assert pages["a9"] == (323, 324)


@needs_pdf
def test_each_table_matches_printed_total():
    tables = itr2023.extract_tables(PDF)
    assert set(tables) == set(itr2023.SPECS) - set(itr2023.FAILS_PRINTED_TOTAL)
    for key, t in tables.items():
        states.require_all(t.rows, 2022)
        for col in t.spec.columns:
            vals = [r[col] for r in t.rows.values() if r[col] is not None]
            assert sum(vals) == t.national[col], (key, col)
    rows, totals = itr2023.build_indicators(tables)
    assert set(totals) == {1, 2, 3, 4, 6}
    for ind, (num_total, den_total) in totals.items():
        mine = [r for r in rows if r["indicator"] == ind]
        assert sum(r["numerator"] for r in mine if r["numerator"] is not None) == num_total, ind
        assert sum(r["denominator"] for r in mine if r["denominator"] is not None) == den_total, ind


@needs_pdf
def test_annexure_7_2_fails_its_printed_total():
    # Plan §5.4 item 2: the mismatch stops extraction of indicator 8.
    bad = itr2023.printed_total_failures(PDF)["a7_2"]
    assert ("eligible_tpt", 291602, 291690) in bad
    assert ("initiated_tpt", 169662, 168665) in bad


@needs_pdf
def test_spot_values():
    t = itr2023.extract_tables(PDF)
    assert t["a1_2"].national == {"target_total": 2780000, "notified_total": 2422121}
    assert t["a2_1"].rows["Delhi"]["hiv_known_total"] == 75497
    assert t["a1_6"].rows["Delhi"]["net_notified"] == 44850 + 43312 + 62
    assert t["a4_9"].rows["Maharashtra"]["mdr_initiated_total"] == 10793
    assert t["a9"].rows["Manipur"]["paid_once"] == 140


@needs_pdf
def test_indicator_rows():
    rows, _ = itr2023.build_indicators(itr2023.extract_tables(PDF))
    present = {r["indicator"] for r in rows}
    # 5: no eligible-beneficiary denominator (ruling R18); 7, 9 not located; 8 fails its total
    assert present == {1, 2, 3, 4, 6}
    assert set(itr2023.MISSING) == {5, 7, 8, 9}
    for ind in present:
        mine = [r for r in rows if r["indicator"] == ind]
        assert len(mine) == 36, ind
        states.require_all([r["state"] for r in mine], 2022)
        assert all(r["score_year"] == 2022 for r in mine)


@needs_pdf
def test_drtb_outcomes():
    rows, national = itr2023.extract_drtb_outcomes(itr2023.extract_tables(PDF))
    assert len(rows) == 36
    states.require_all([r["state"] for r in rows], 2022)
    lk = next(r for r in rows if r["state"] == "Lakshadweep")  # not printed in 4.13
    assert lk["cohort_n"] is None and lk["success"] is None and lk["pdf_page"] == "293;294"
    for r in rows:
        if r["success"] is not None:
            assert r["success"] == r["cured"] + r["completed"]
    for col in ("cohort_n", "cured", "success"):
        assert sum(r[col] for r in rows if r[col] is not None) == national[col]


@needs_pdf
def test_definitions_2023():
    rows = itr2023.definitions(PDF)
    ind = {str(r["indicator_no"]): r for r in rows if str(r["indicator_no"]).isdigit()}
    assert sorted(ind, key=int) == [str(i) for i in range(1, 10)]
    assert sum(int(r["points"]) for r in ind.values()) == 100
    assert ind["1"]["points"] == 20 and ind["6"]["points"] == 15
    scores = next(r for r in rows if r["indicator_no"] == "scores")
    assert "no state scores printed in ITR2023" in scores["note"]


@needs_pdf
def test_committed_csvs_match_extraction(tmp_path):
    itr2023.write_all(PDF, tmp_path / "extracted", tmp_path / "source_choices.csv")
    assert not (tmp_path / "extracted" / "itr2023_scores.csv").exists()
    assert not (EXTRACTED / "itr2023_scores.csv").exists()
    for name in ("itr2023_indicators.csv", "itr2023_drtb_outcomes.csv",
                 "itr2023_tsr_cohort.csv"):
        assert (tmp_path / "extracted" / name).read_text(encoding="utf-8") == \
            (EXTRACTED / name).read_text(encoding="utf-8"), name
    assert _rows_of(tmp_path / "source_choices.csv", "score_year", "2022") == \
        _rows_of(Path("data/source_choices.csv"), "score_year", "2022")
    assert _rows_of(tmp_path / "extracted" / "definitions.csv", "edition", "2023") == \
        _rows_of(EXTRACTED / "definitions.csv", "edition", "2023")


def _rows_of(path: Path, key: str, value: str) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r[key] == value]
    assert rows, (path, value)
    return rows


def test_source_choices_cover_every_indicator_2022():
    rows = _rows_of(Path("data/source_choices.csv"), "score_year", "2022")
    for i in range(1, 10):
        comps = {r["component"] for r in rows if r["indicator"] == str(i)}
        assert {"numerator", "denominator"} <= comps, i
    assert {r["indicator"] for r in rows} >= {"published_score", "scoring_rule_R4"}
    for i in ("5", "7", "9"):  # missing: no table matches the definition
        assert {r["table_id"] for r in rows if r["indicator"] == i} <= {"missing", "not located"}
    one = next(r for r in rows if r["indicator"] == "1" and r["component"] == "denominator")
    assert "§5.3 could not be run" in one["note"] and "§13 deviation" in one["note"]


def test_definitions_csv_has_each_edition():
    with open(EXTRACTED / "definitions.csv", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert set(rows[0]) == set(annex.DEFINITION_COLS)
    eds = {r["edition"] for r in rows}
    assert {"2024", "2023", "2021"} <= eds
    for ed, year in (("2024", "2023"), ("2023", "2022"), ("2021", "2020")):
        mine = [r for r in rows if r["edition"] == ed]
        assert all(r["score_year"] == year for r in mine), ed
        assert any(r["indicator_no"] == "scores" for r in mine), ed

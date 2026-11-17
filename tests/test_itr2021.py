"""India TB Report 2021 (score year 2020).

The edition is a scan: its pages carry no text layer, so no table can be
read without OCR, which the plan does not allow (never OCR-guess numbers).
These tests pin that finding, so that a text-layer copy, if one is obtained,
makes them fail and the extraction is revisited.
"""
import csv
from pathlib import Path

import pytest

from src.extract import itr2021

PDF = Path("data_raw/india_tb_report/ITR2021.pdf")
needs_pdf = pytest.mark.skipif(not PDF.exists(), reason="data_raw/ITR2021.pdf absent")


@needs_pdf
def test_needed_pages_have_no_text_layer():
    status = itr2021.text_layer_status(PDF)
    assert status["pages"] == 352
    assert status["with_text"] == {}  # every needed page: zero characters
    assert set(status["checked"]) >= {87, 88, 207, 208, 211, 217, 227, 254, 286, 314, 319}


@needs_pdf
def test_extraction_reports_blocked():
    with pytest.raises(itr2021.Blocked, match="no text layer"):
        itr2021.extract_tables(PDF)


def test_definitions_rows_2021():
    with open("data/extracted/definitions.csv", encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["edition"] == "2021"]
    assert rows
    assert all(r["score_year"] == "2020" for r in rows)
    ind = {r["indicator_no"]: r for r in rows if r["indicator_no"].isdigit()}
    assert sorted(ind, key=int) == [str(i) for i in range(1, 10)]
    assert sum(int(r["points"]) for r in ind.values()) == 100
    assert all("no text layer" in r["note"] for r in rows)
    assert rows == [{k: str(v) for k, v in r.items()} for r in itr2021.definitions()]


def test_no_2020_source_choices_before_extraction():
    # Freeze rule (plan §5.4 item 7): choices for 2020 are recorded only with
    # an extraction; none can be made from a scan, so none are recorded.
    with open("data/source_choices.csv", encoding="utf-8", newline="") as f:
        assert not [r for r in csv.DictReader(f) if r["score_year"] == "2020"]

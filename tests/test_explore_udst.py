"""Exploratory indicator 3 scaling (plan section 13), synthetic inputs only."""
import csv

import pytest

from src import explore_udst as ex
from src import score as sc

NOTE = ("JUDGEMENT CALL: ... the chosen numerator gives 30 / 100 = 30.0% nationally, while "
        "Table 11.1 (PDF p.123, KPI 4) prints 45% of notified patients 'offered ...'.")


def _choices(tmp_path, note=NOTE):
    p = tmp_path / "source_choices.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["score_year", "indicator", "component", "note"])
        w.writerow(["2023", "3", "numerator", note])
        w.writerow(["2023", "3", "denominator", "other"])
    return p


ROWS = [
    {"score_year": "2023", "state": "A", "indicator": "3", "numerator": "10", "denominator": "40"},
    {"score_year": "2023", "state": "B", "indicator": "3", "numerator": "20", "denominator": "60"},
]


def test_scaling_factor_is_ctd_share_over_annexure_share(tmp_path):
    k, share, num, den = ex.scaling_factor(ROWS, _choices(tmp_path))
    assert (share, num, den) == (0.45, 30, 100)
    assert k == pytest.approx(0.45 / 0.30)


def test_note_counts_must_match_the_extracted_data(tmp_path):
    bad = NOTE.replace("30 / 100", "31 / 100")
    with pytest.raises(ValueError, match="differ from the source note"):
        ex.scaling_factor(ROWS, _choices(tmp_path, bad))


def test_only_indicator_3_is_scaled_and_blanks_stay_blank():
    ach = {"A": {1: 0.5, 3: 0.4}, "B": {1: 0.9, 3: None}}
    out = ex.scaled_achievement(ach, 1.5)
    assert out["A"] == {1: 0.5, 3: pytest.approx(0.6)}
    assert out["B"] == {1: 0.9, 3: None}
    assert ach["A"][3] == 0.4  # input not modified


def test_r3_is_unchanged_by_a_common_scaling():
    ach = {"A": {3: 0.4, 4: 0.8}, "B": {3: 0.2, 4: 0.9}}
    before = sc.score(ach, "R3")
    after = sc.score(ex.scaled_achievement(ach, 1.7), "R3")
    assert after == pytest.approx(before)

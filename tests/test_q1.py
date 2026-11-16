"""Task 6: Q1 rule selection (plan 7.1-7.3), synthetic inputs only."""
import pytest

from src.q1_reproduce import select_rule


def test_exact_match_reproduced():
    pub = {"A": 50.00, "B": 72.35}
    parts = {"R1": {"A": 50.004, "B": 72.341}, "R2": {"A": 51.0, "B": 72.35}}
    res = select_rule(pub, parts, 0)
    assert res["verdict"] == "reproduced"
    assert res["admissible"] == ["R1"]
    assert res["chosen"] == "R1"
    assert res["rules_for_q2q4"] == ["R1"]
    assert res["sensitivity_rules"] == []
    assert res["per_rule"]["R1"]["n_match"] == 2
    assert res["per_rule"]["R2"]["mismatches"] == {"A": pytest.approx(-1.0)}
    assert res["per_state"]["A"]["R1"]["match"] is True
    assert res["per_state"]["A"]["R2"]["match"] is False
    assert res["excluded"] == []


def test_full_not_reproducible_ranking():
    pub = {"A": 50.0, "B": 60.0}
    parts = {"R1": {"A": 50.0, "B": 62.0},   # max abs error 2
             "R2": {"A": 49.5, "B": 60.5},   # max abs error 0.5
             "R3": {"A": 53.0, "B": 60.0}}   # max abs error 3
    res = select_rule(pub, parts, 0)
    assert res["verdict"] == "not reproducible"
    assert res["admissible"] == []
    assert res["chosen"] == "R2"
    assert res["rules_for_q2q4"] == ["R2"]
    assert res["sensitivity_rules"] == []
    assert res["per_rule"]["R2"]["max_abs_error"] == pytest.approx(0.5)
    assert res["per_rule"]["R1"]["mismatches"] == {"B": pytest.approx(-2.0)}


def test_tie_break_max_abs_error_then_mismatch_count():
    pub = {"A": 50.0, "B": 60.0, "C": 70.0}
    parts = {"R1": {"A": 49.0, "B": 59.0, "C": 70.0},  # max 1, 2 mismatches
             "R2": {"A": 49.0, "B": 60.0, "C": 70.0},  # max 1, 1 mismatch
             "R3": {"A": 51.0, "B": 61.0, "C": 69.0}}  # max 1, 3 mismatches
    res = select_rule(pub, parts, 0)
    assert res["verdict"] == "not reproducible"
    assert res["chosen"] == "R2"
    assert res["ranking"] == ["R2", "R1", "R3"]
    # still tied after both keys: no single choice, Q2-Q4 run under each
    tied = {"R1": {"A": 49.0, "B": 60.0, "C": 70.0},
            "R2": {"A": 50.0, "B": 61.0, "C": 70.0}}
    res2 = select_rule(pub, tied, 0)
    assert res2["chosen"] is None
    assert res2["rules_for_q2q4"] == ["R1", "R2"]


def test_residual_outside_missing_points_inadmissible():
    pub = {"A": 80.0, "B": 90.0}
    parts = {"R1": {"A": 70.0, "B": 85.0},   # residuals 10, 5: in band [0, 15]
             "R2": {"A": 60.0, "B": 85.0},   # residual 20 > 15: out
             "R3": {"A": 81.0, "B": 85.0}}   # residual -1 < 0: out
    res = select_rule(pub, parts, 15, missing_indicators=[7, 9])
    assert res["admissible"] == ["R1"]
    assert res["per_rule"]["R2"]["admissible"] is False
    assert res["per_rule"]["R2"]["max_violation"] == pytest.approx(20 - 15.01)
    assert res["per_rule"]["R2"]["outside"] == {"A": pytest.approx(20.0)}
    assert res["per_rule"]["R3"]["max_violation"] == pytest.approx(1 - 0.01)
    assert res["per_rule"]["R3"]["n_in_band"] == 1
    assert res["per_state"]["A"]["R2"]["in_band"] is False


def test_one_admissible_consistent_with():
    pub = {"A": 80.0, "B": 90.0}
    parts = {"R1": {"A": 70.0, "B": 85.0}, "R2": {"A": 60.0, "B": 85.0}}
    res = select_rule(pub, parts, 15, missing_indicators=[7, 9])
    assert res["verdict"] == ("consistent with rule R1; not fully reproducible "
                              "because indicator(s) 7, 9 are unpublished")
    assert res["chosen"] == "R1"
    assert res["rules_for_q2q4"] == ["R1"]
    assert res["sensitivity_rules"] == []


def test_two_admissible_rules_cannot_discriminate():
    pub = {"A": 80.0, "B": 90.0}
    parts = {"R1": {"A": 70.0, "B": 85.0}, "R2": {"A": 72.0, "B": 84.0},
             "R3": {"A": 50.0, "B": 85.0}}
    res = select_rule(pub, parts, 15, missing_indicators=[7, 9])
    assert res["verdict"] == "cannot discriminate"
    assert res["admissible"] == ["R1", "R2"]
    assert res["chosen"] is None
    assert res["rules_for_q2q4"] == ["R1", "R2"]
    assert res["sensitivity_rules"] == []


def test_no_admissible_chooses_smallest_violation():
    pub = {"A": 80.0, "B": 90.0, "C": 50.0}
    parts = {"R1": {"A": 60.0, "B": 70.0, "C": 50.0},   # viol 4.99 (A,B out)
             "R2": {"A": 60.0, "B": 85.0, "C": 50.0},   # viol 4.99 (A out)
             "R3": {"A": 90.0, "B": 85.0, "C": 50.0}}   # viol 9.99
    res = select_rule(pub, parts, 15, missing_indicators=[7, 9])
    assert res["verdict"] == "not reproducible"
    assert res["admissible"] == []
    assert res["chosen"] == "R2"            # tie on violation, fewer outside
    assert res["rules_for_q2q4"] == ["R2"]
    assert res["sensitivity_rules"] == ["R1", "R2", "R3"]
    assert res["per_rule"]["R1"]["max_violation"] == pytest.approx(4.99)
    assert res["per_rule"]["R2"]["max_violation"] == pytest.approx(4.99)
    assert sorted(res["per_rule"]["R1"]["outside"]) == ["A", "B"]


def test_tolerance_boundaries():
    pub = {"A": 50.0, "B": 65.01}
    # A: residual exactly -0.01; B: residual exactly 15 + 0.01
    parts = {"R1": {"A": 50.01, "B": 50.0}}
    res = select_rule(pub, parts, 15, missing_indicators=[7, 9])
    assert res["per_state"]["A"]["R1"]["in_band"] is True
    assert res["per_state"]["B"]["R1"]["in_band"] is True
    assert res["per_state"]["A"]["R1"]["violation"] == 0.0
    assert res["admissible"] == ["R1"]
    # just beyond the bounds is outside
    out = select_rule({"A": 50.0, "B": 65.02}, {"R1": {"A": 50.02, "B": 50.0}},
                      15, missing_indicators=[7, 9])
    assert out["per_rule"]["R1"]["n_in_band"] == 0
    # full case: |error| exactly 0.01 matches
    full = select_rule({"A": 50.0, "B": 60.0}, {"R1": {"A": 50.01, "B": 59.99}}, 0)
    assert full["verdict"] == "reproduced"


def test_excluded_states_listed():
    pub = {"A": 80.0, "B": 90.0, "K": 40.0}
    parts = {"R1": {"A": 70.0, "B": 85.0, "K": None},
             "R2": {"A": 70.0, "B": 85.0, "K": None},
             "R4": "not evaluable: no bands documented"}
    res = select_rule(pub, parts, 15, missing_indicators=[7, 9])
    assert res["excluded"] == ["K"]
    assert res["per_state"]["K"]["R1"]["excluded"] is True
    assert "K" not in res["per_rule"]["R1"]["outside"]
    assert res["per_rule"]["R1"]["n_compared"] == 2
    assert res["per_rule"]["R4"] == {"status": "not evaluable: no bands documented"}
    assert res["verdict"] == "cannot discriminate"   # R4 is not a failure
    assert res["admissible"] == ["R1", "R2"]


def test_empty_comparison_raises():
    pub = {"A": 80.0, "K": None}
    parts = {"R1": {"A": None, "K": 40.0}, "R2": {"A": None, "K": 40.0}}
    with pytest.raises(ValueError, match="no computable state to compare"):
        select_rule(pub, parts, 15, missing_indicators=[7, 9])
    with pytest.raises(ValueError, match="no computable state to compare"):
        select_rule(pub, parts, 0)


def test_missing_indicators_must_match_missing_points():
    with pytest.raises(ValueError):
        select_rule({"A": 1.0}, {"R1": {"A": 1.0}}, 15, missing_indicators=[7])
    with pytest.raises(ValueError):
        select_rule({"A": 1.0}, {"R1": {"A": 1.0}}, 15)

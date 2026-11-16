"""Task 5: indicator achievement and scoring rules R1-R3 (synthetic inputs only)."""
import pytest

from src import score


def row(state, ind, num, den, year=2023):
    return {"score_year": str(year), "state": state, "indicator": str(ind),
            "numerator": num, "denominator": den}


def test_zero_denominator_is_none():
    ach = score.achievement([row("A", 2, "5", "0")])
    assert ach["A"][2] is None


def test_blank_numerator_and_denominator_are_none_not_zero():
    ach = score.achievement([row("A", 2, "", "10"), row("B", 5, "3", "")])
    assert ach["A"][2] is None
    assert ach["B"][5] is None


def test_zero_numerator_positive_denominator_is_zero():
    assert score.achievement([row("A", 2, "0", "10")])["A"][2] == 0.0


def test_achievement_not_capped_before_rules():
    ach = score.achievement([row("A", 3, "840", "1000")])
    assert ach["A"][3] == pytest.approx(1.2)


def test_missing_indicators_absent_not_none():
    ach = score.achievement([row("A", 1, "5", "10")])
    assert set(ach["A"]) == {1}


def test_r1_caps_r2_does_not():
    ach = {"A": {3: 1.2}}
    assert score.score(ach, "R1", indicators=[3])["A"] == pytest.approx(10.0)
    assert score.score(ach, "R2", indicators=[3])["A"] == pytest.approx(12.0)


def test_r3_relative_to_best():
    ach = {"A": {2: 0.5}, "B": {2: 1.0}, "C": {2: None}}
    s = score.score(ach, "R3", indicators=[2])
    assert s["B"] == pytest.approx(10.0)
    assert s["A"] == pytest.approx(5.0)
    assert s["C"] is None


def test_r3_max_over_computable_states_only():
    ach = {"A": {2: 0.4}, "B": {2: 0.8}, "C": {2: None}}
    assert score.score(ach, "R3", indicators=[2])["A"] == pytest.approx(5.0)


def test_unknown_rule_raises():
    with pytest.raises(ValueError):
        score.score({"A": {1: 1.0}}, "R9")


def test_r4_not_implemented():
    with pytest.raises(NotImplementedError, match="R4 bands not documented"):
        score.score({"A": {1: 1.0}}, "R4")


def test_none_indicator_makes_score_none():
    ach = {"A": {1: 1.0, 2: None}, "B": {1: 1.0, 2: 1.0}}
    s = score.score(ach, "R1", indicators=[1, 2])
    assert s["A"] is None
    assert s["B"] == pytest.approx(30.0)


def test_unrequested_indicator_ignored():
    ach = {"A": {1: 1.0, 2: None}}
    assert score.score(ach, "R1", indicators=[1])["A"] == pytest.approx(20.0)


def test_partial_not_rescaled_sums_available_points():
    ach = {"A": {i: 1.0 for i in (1, 2, 3, 4, 5, 6, 8)}}
    assert score.score(ach, "R1")["A"] == pytest.approx(85.0)


def test_rescale_partial_to_100():
    ach = {"A": {i: 1.0 for i in (1, 2, 3, 4, 5, 6, 8)}}
    # indicators 7 and 9 absent for every state
    assert score.score(ach, "R1", rescale=True)["A"] == pytest.approx(100.0)


def test_rescale_half():
    ach = {"A": {1: 0.5, 2: 0.5}}
    assert score.score(ach, "R2", indicators=[1, 2], rescale=True)["A"] == pytest.approx(50.0)


def test_points_and_rules():
    assert sum(score.POINTS.values()) == 100
    assert score.RULES == ("R1", "R2", "R3")


def test_load_roundtrip(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("state,indicator,numerator,denominator\nA,1,5,10\n", encoding="utf-8")
    rows = score.load(p)
    assert rows == [{"state": "A", "indicator": "1", "numerator": "5", "denominator": "10"}]

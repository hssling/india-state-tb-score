"""Task 9b: Q4 change over time helpers (plan 10), synthetic inputs only."""
import math

import pytest

from src.q4_change import compare, exceeds_noise, score_se, se_components
from src.score import score

COMMON = (1, 2, 3, 4, 6)
NO_IND1 = (2, 3, 4, 6)


def test_score_se_formula():
    # indicator 1: 100 notified against a target of 400 -> a = 0.25, n = target
    #   se_1 = sqrt(100) / 400 = 0.025 (Poisson)
    # indicator 3: 35 tested of 100 net notified -> a = 35 / (0.7 x 100) = 0.5,
    #   n = net notified = 100, p = 0.35, se_3 = sqrt(0.35 x 0.65 / 100) / 0.7
    ach = {"X": {1: 0.25, 3: 0.5}}
    n = {"X": {1: 400, 3: 100}}
    comp = se_components(ach, n, (1, 3))
    assert comp["X"][1] == pytest.approx(0.025)
    assert comp["X"][3] == pytest.approx(math.sqrt(0.35 * 0.65 / 100) / 0.7)
    se3_sq = 0.35 * 0.65 / 100 / 0.49  # 0.0046428571...
    # rescaled to 100 over 30 points: pts_1 = 200/3, pts_3 = 100/3
    expected = math.sqrt((200 / 3) ** 2 * 0.025 ** 2 + (100 / 3) ** 2 * se3_sq)
    assert expected == pytest.approx(2.81718, abs=1e-5)
    assert score_se(ach, n, "R2", (1, 3))["X"] == pytest.approx(expected)
    # unrescaled: pts 20 and 10
    unres = math.sqrt(20 ** 2 * 0.025 ** 2 + 10 ** 2 * se3_sq)
    assert unres == pytest.approx(0.845154, abs=1e-6)
    assert score_se(ach, n, "R2", (1, 3), rescale=False)["X"] == pytest.approx(unres)
    # same uncapped se under R1 (a <= 1 here, so R1 = R2 anyway)
    assert score_se(ach, n, "R1", (1, 3))["X"] == pytest.approx(expected)


def test_score_se_plain_binomial_and_r1_uncapped():
    # indicator 4: a = 0.8 of n = 400 -> se = sqrt(0.8 x 0.2 / 400) = 0.02
    # indicator 1: a = 1.2 against target 1000 (allowed: Poisson, not binomial)
    ach = {"X": {1: 1.2, 4: 0.8}}
    n = {"X": {1: 1000, 4: 400}}
    se1 = math.sqrt(1200) / 1000
    exp = math.sqrt(20 ** 2 * se1 ** 2 + 15 ** 2 * 0.02 ** 2)
    # R1 uses the same uncapped se although indicator 1 is above the cap
    for rule in ("R1", "R2"):
        assert score_se(ach, n, rule, (1, 4), rescale=False)["X"] == pytest.approx(exp)


def test_exceeds_noise_boundary():
    thr = 1.96 * 5.0  # se 3 and 4 -> sqrt(9 + 16) = 5
    assert exceeds_noise(thr, 0.0, 3.0, 4.0) is False      # exactly at: not exceeding
    assert exceeds_noise(0.0, thr, 3.0, 4.0) is False      # either direction
    above = math.nextafter(thr, math.inf)
    assert exceeds_noise(above, 0.0, 3.0, 4.0) is True
    assert exceeds_noise(0.0, above, 3.0, 4.0) is True
    assert exceeds_noise(5.0, 5.0, 0.0, 0.0) is False      # zero change, zero noise
    assert exceeds_noise(5.0, 4.0, 0.0, 0.0) is True


def test_binomial_a_gt_1_not_computable():
    # Lakshadweep-like: indicator 4 printed as 21 / 14 -> a = 1.5
    ach = {"L": {1: 0.5, 4: 1.5}, "Y": {1: 0.5, 4: 0.5}}
    n = {"L": {1: 12, 4: 14}, "Y": {1: 12, 4: 14}}
    comp = se_components(ach, n, (1, 4))
    assert comp["L"][4] is None
    assert comp["L"][1] is not None
    assert score_se(ach, n, "R2", (1, 4))["L"] is None
    assert score_se(ach, n, "R2", (1, 4))["Y"] is not None
    # indicator 3 above the 70% benchmark is allowed (p <= 1), p > 1 is not
    ach3 = {"A": {3: 17 / (0.7 * 22)}, "B": {3: 30 / (0.7 * 22)}}
    n3 = {"A": {3: 22}, "B": {3: 22}}
    c3 = se_components(ach3, n3, (3,))
    p = 17 / 22
    assert c3["A"][3] == pytest.approx(math.sqrt(p * (1 - p) / 22) / 0.7)
    assert c3["B"][3] is None
    # a missing or non-computable achievement makes the SE non-computable
    assert score_se({"Z": {1: None, 4: 0.5}}, {"Z": {1: 0, 4: 10}}, "R2", (1, 4))["Z"] is None


def test_r3_points_divided_by_year_max():
    ach = {"A": {2: 0.5}, "B": {2: 0.8}}
    n = {"A": {2: 100}, "B": {2: 400}}
    se_a = math.sqrt(0.25 / 100)                 # 0.05
    se_b = math.sqrt(0.8 * 0.2 / 400)            # 0.02
    out = score_se(ach, n, "R3", (2,), rescale=False)
    assert out["A"] == pytest.approx(10 / 0.8 * se_a)   # 0.625
    assert out["B"] == pytest.approx(10 / 0.8 * se_b)
    # rescaled: 100 / 10 points -> x10
    assert score_se(ach, n, "R3", (2,))["A"] == pytest.approx(100 / 0.8 * se_a)
    # an explicitly supplied maximum is treated as fixed
    assert score_se(ach, n, "R3", (2,), rescale=False, best={2: 0.5})["A"] == \
        pytest.approx(10 / 0.5 * se_a)
    # the maximum is taken from the ach passed (one score year), not across years
    assert score_se({"A": {2: 0.5}}, {"A": {2: 100}}, "R3", (2,), rescale=False)["A"] == \
        pytest.approx(10 / 0.5 * se_a)


def test_common_indicator_set_rescaled_to_100():
    # 2023-like ach with indicators 5 and 8 present; they are ignored
    full = {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 0.2, 6: 1.0, 8: 0.1}
    ach = {"F": dict(full), "G": {**full, 2: 0.5}}
    assert score(ach, "R2", indicators=COMMON, rescale=True)["F"] == pytest.approx(100.0)
    assert score(ach, "R2", indicators=NO_IND1, rescale=True)["F"] == pytest.approx(100.0)
    n = {s: {1: 10000, 2: 100, 3: 1000, 4: 50, 5: 9, 6: 20, 8: 9} for s in ach}
    se1 = math.sqrt(1.0 / 10000)          # Poisson: sqrt(10000) / 10000
    se2 = math.sqrt(0.25 / 100)           # binomial at a = 0.5
    se3 = math.sqrt(0.7 * 0.3 / 1000) / 0.7
    # binomial a = 1 -> se 0 for 4 and 6
    exp_common = math.sqrt((20 * 100 / 70 * se1) ** 2 + (10 * 100 / 70 * se2) ** 2
                           + (10 * 100 / 70 * se3) ** 2)
    exp_no1 = math.sqrt((10 * 100 / 50 * se2) ** 2 + (10 * 100 / 50 * se3) ** 2)
    assert score_se(ach, n, "R2", COMMON)["G"] == pytest.approx(exp_common)
    assert score_se(ach, n, "R2", NO_IND1)["G"] == pytest.approx(exp_no1)
    assert se_components(ach, n, COMMON)["G"][4] == 0.0


def test_state_excluded_if_noncomputable_either_year():
    s_prev = {"A": 50.0, "B": 60.0, "C": 70.0, "D": 40.0}
    se_prev = {"A": None, "B": 1.0, "C": 1.0, "D": 1.0}
    s_t = {"A": 80.0, "B": None, "C": 75.0, "D": 41.0}
    se_t = {"A": 1.0, "B": 1.0, "C": 1.0, "D": None}
    rows = compare(s_prev, se_prev, s_t, se_t, labels=("2022", "2023"))
    assert rows["A"]["exceeds"] is None
    assert "SE not computable in 2022" in rows["A"]["excluded_reason"]
    assert rows["B"]["exceeds"] is None
    assert "score not computable in 2023" in rows["B"]["excluded_reason"]
    assert rows["D"]["exceeds"] is None
    assert "SE not computable in 2023" in rows["D"]["excluded_reason"]
    assert rows["C"]["excluded_reason"] == ""
    thr = 1.96 * math.sqrt(2.0)
    assert rows["C"]["threshold"] == pytest.approx(thr)
    assert rows["C"]["exceeds"] is True
    assert rows["C"]["change"] == pytest.approx(5.0)
    assert rows["C"]["pct_change"] == pytest.approx(100 * 5 / 70)
    # change and pct_change still reported where both scores exist
    assert rows["A"]["change"] == pytest.approx(30.0)
    assert rows["B"]["change"] is None

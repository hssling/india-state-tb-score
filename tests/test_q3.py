"""Task 9a: Q3 validity helpers (plan 9), synthetic inputs only."""
import math

import pytest

from src.q3_validity import fieller_se, fisher_ci, spearman_ci, unit_scores


def test_spearman_known_values():
    # y has a tie (7, 7) -> average ranks 3.5; Pearson of the ranks = 8/sqrt(95)
    rho, lo, hi, n = spearman_ci([1, 2, 3, 4, 5], [5, 6, 7, 8, 7])
    assert n == 5
    assert rho == pytest.approx(8 / math.sqrt(95))
    # perfectly reversed order
    assert spearman_ci([1, 2, 3, 4, 5], [9, 7, 5, 3, 1])[0] == pytest.approx(-1.0)


def test_spearman_keyed_by_common_keys():
    x = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "only_x": 9, "none_x": None}
    y = {"a": 5, "b": 6, "c": 7, "d": 8, "e": 7, "only_y": 0, "none_x": 3}
    rho, _, _, n = spearman_ci(x, y)
    assert n == 5
    assert rho == pytest.approx(8 / math.sqrt(95))


def test_spearman_lists_must_be_parallel():
    with pytest.raises(ValueError):
        spearman_ci([1, 2, 3], [1, 2])


def test_fisher_ci_small_n_returns_none():
    for n in (2, 3):
        assert fisher_ci(0.5, n) == (None, None)
    rho, lo, hi, n = spearman_ci([1, 2, 3], [1, 3, 2])
    assert n == 3 and rho == pytest.approx(0.5)
    assert (lo, hi) == (None, None)
    assert fisher_ci(0.5, 4) != (None, None)


def test_fieller_se_used():
    assert fieller_se(13) == pytest.approx(math.sqrt(1.06 / 10))
    lo, hi = fisher_ci(0.5, 13)
    se = math.sqrt(1.06 / 10)
    assert lo == pytest.approx(math.tanh(math.atanh(0.5) - 1.96 * se))
    assert hi == pytest.approx(math.tanh(math.atanh(0.5) + 1.96 * se))
    # not the plain 1/sqrt(n-3) standard error
    assert lo != pytest.approx(math.tanh(math.atanh(0.5) - 1.96 / math.sqrt(10)))
    # spearman_ci uses the same interval
    x = list(range(1, 14))
    y = [2, 1, 4, 3, 6, 5, 8, 7, 10, 9, 12, 11, 13]
    rho, lo2, hi2, n = spearman_ci(x, y)
    assert n == 13
    assert (lo2, hi2) == pytest.approx(fisher_ci(rho, 13))


def test_population_weighted_unit_score():
    units = [{"unit": "G", "members": ["A", "B"]}, {"unit": "C", "members": ["C"]}]
    scores = {"A": 80.0, "B": 50.0, "C": 70.0}
    pop = {"A": 3_000_000.0, "B": 1_000_000.0, "C": 5.0}
    out = {u["unit"]: u for u in unit_scores(units, scores, pop)}
    assert out["G"]["score"] == pytest.approx((80 * 3 + 50 * 1) / 4)
    assert out["G"]["scored"] == ["A", "B"] and out["G"]["excluded"] == []
    assert out["C"]["score"] == pytest.approx(70.0)


def test_unit_with_no_scored_member_dropped():
    units = [{"unit": "K", "members": ["K"]}, {"unit": "G", "members": ["A", "B"]}]
    scores = {"K": None, "A": None, "B": 60.0}
    pop = {"K": 1.0, "A": 1.0, "B": 1.0}
    out = {u["unit"]: u for u in unit_scores(units, scores, pop)}
    assert out["K"]["score"] is None
    assert out["K"]["scored"] == [] and out["K"]["excluded"] == ["K"]
    assert out["G"]["score"] == pytest.approx(60.0)


def test_members_without_score_listed():
    units = [{"unit": "G", "members": ["A", "B", "C"]}]
    scores = {"A": 90.0, "C": 30.0}  # B absent from the scores entirely
    pop = {"A": 1.0, "B": 100.0, "C": 3.0}
    (u,) = unit_scores(units, scores, pop)
    assert u["excluded"] == ["B"]
    assert u["scored"] == ["A", "C"]
    assert u["score"] == pytest.approx((90 * 1 + 30 * 3) / 4)


def test_scored_member_without_population_fails_loudly():
    units = [{"unit": "G", "members": ["A", "B"]}]
    with pytest.raises(ValueError, match="B"):
        unit_scores(units, {"A": 1.0, "B": 2.0}, {"A": 1.0})

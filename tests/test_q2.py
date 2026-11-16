"""Task 7: Q2 robustness helpers (plan 8), synthetic inputs only."""
import statistics

import pytest

from src import score as sc
from src.q2_robust import (average_ranks, dirichlet_weights, draw_scores,
                           fifth_size, rank_shift, saturated, spearman,
                           leave_one_out)


def test_weights_sum_to_100():
    for c in (63, None):
        for w in dirichlet_weights(c, 50, 1):
            assert sum(w.values()) == pytest.approx(100.0)
            assert set(w) == set(range(1, 10))


def test_weight_cv_matches_formula():
    draws = dirichlet_weights(63, 10000, 20261117)
    x = [d[1] for d in draws]  # indicator 1 = 20 points
    cv = statistics.pstdev(x) / statistics.mean(x)
    assert cv == pytest.approx(0.25, abs=0.01)


def test_seeded_reproducible():
    assert dirichlet_weights(63, 5, 7) == dirichlet_weights(63, 5, 7)
    assert dirichlet_weights(63, 5, 7) != dirichlet_weights(63, 5, 8)


def test_weights_over_available_indicators():
    d = dirichlet_weights(63, 3, 1, indicators=[1, 2, 4])
    assert set(d[0]) == {1, 2, 4}


def test_saturated_threshold():
    # 4 of 5 computable states >= 0.95 (0.95 inclusive) -> exactly 80%
    ach = {f"s{i}": {1: v, 2: 0.5} for i, v in enumerate([0.95, 1.2, 1.0, 0.99, 0.2])}
    assert saturated(ach) == [1]
    ach["s4"][1] = 0.949999
    ach["s5"] = {1: 0.5, 2: 0.5}  # 4 of 6 -> below 80%
    assert saturated(ach) == []


def test_saturated_ignores_uncomputable():
    ach = {"a": {1: 1.0}, "b": {1: 1.0}, "c": {1: None}}
    assert saturated(ach) == [1]


def test_rank_ties_average():
    r = average_ranks({"a": 10.0, "b": 8.0, "c": 8.0, "d": 1.0})
    assert r == {"a": 1.0, "b": 2.5, "c": 2.5, "d": 4.0}


def test_spearman_identity_is_one():
    s = {"a": 3.0, "b": 2.0, "c": 9.0, "d": 4.0}
    assert spearman(s, s) == pytest.approx(1.0)
    assert spearman(s, {k: -v for k, v in s.items()}) == pytest.approx(-1.0)


def test_rank_shift_on_common_states():
    base = {"a": 3.0, "b": 2.0, "c": 1.0}
    alt = {"a": 1.0, "b": 2.0, "c": 3.0, "z": 5.0}
    out = rank_shift(base, alt)
    assert out["median_abs"] == 2.0 and out["max_abs"] == 2.0
    assert out["n"] == 3


def test_leave_one_out_rescales():
    ach = {"a": {1: 1.0, 2: 0.5, 3: 0.0}, "b": {1: 0.5, 2: 1.0, 3: 1.0}}
    out = leave_one_out(ach, "R2", [1, 2, 3])
    assert set(out) == {1, 2, 3}
    # drop indicator 3 (10 pts): remaining 30 pts rescaled to 100
    assert out[3]["a"] == pytest.approx(100 * (20 * 1 + 10 * 0.5) / 30)


def test_fifth_size_floor():
    assert fifth_size(35) == 7
    assert fifth_size(36) == 7
    assert fifth_size(4) == 0


def test_draw_score_matches_score_at_ctd_weights():
    ach = {"a": {1: 1.3, 2: 0.5, 4: 0.9}, "b": {1: 0.5, 2: 1.0, 4: 0.2},
           "c": {1: 0.9, 2: 0.7, 4: None}}
    inds = [1, 2, 4]
    tot = sum(sc.POINTS[i] for i in inds)
    w = {i: 100.0 * sc.POINTS[i] / tot for i in inds}
    for rule in sc.RULES:
        ref = sc.score(ach, rule, indicators=inds, rescale=True)
        got = draw_scores(ach, rule, inds, w)
        for s in ach:
            if ref[s] is None:
                assert got[s] is None
            else:
                assert got[s] == pytest.approx(ref[s])


def test_spearman_restricted_to_base_states():
    from src.q2_robust import restrict_to_base
    base = {"a": 3.0, "b": 2.0, "c": 1.0, "k": None}
    alt = {"a": 3.0, "b": 2.0, "c": 1.0, "k": 10.0}
    pub = {"a": 3.0, "b": 2.0, "c": 1.0, "k": 0.0}
    assert spearman(alt, pub) < 1.0  # extra state would change rho
    r = restrict_to_base(alt, base)
    assert set(r) == {"a", "b", "c"}
    assert spearman(r, pub) == pytest.approx(1.0)

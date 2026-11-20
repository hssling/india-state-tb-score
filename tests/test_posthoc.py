"""Post hoc analyses (plan section 13, 20 November 2026), synthetic inputs only."""
import math
import random
import statistics

import pytest

from src import posthoc as ph
from src.q4_change import score_se, se_components


def test_wilson_se_at_the_bounds_and_inside():
    z = 1.96
    # p = 1 of n = 10: sqrt(z^2 / (4 n^2)) / (1 + z^2 / n) = (z / 20) / (1 + 0.38416)
    assert ph.wilson_se(1.0, 10) == pytest.approx((z / 20) / (1 + z * z / 10))
    assert ph.wilson_se(0.0, 10) == pytest.approx(ph.wilson_se(1.0, 10))
    # the 95% Wilson interval of 10/10 is (0.7225, 1): half-width / z
    lo = 10 / (10 + z * z)
    assert ph.wilson_se(1.0, 10) == pytest.approx((1 - lo) / 2 / z, rel=1e-12)
    # inside (0, 1) it is close to, and below, the plain binomial SE for large n
    assert ph.wilson_se(0.3, 10000) == pytest.approx(math.sqrt(0.3 * 0.7 / 10000), rel=1e-3)


def test_wilson_components_replace_only_zero_binomial_se():
    # X: indicator 4 at 1 (se 0), indicator 3 tested 70 of 100 (p = 0.7 x a = 1, se 0),
    # indicator 1 a Poisson count (never replaced); Y: nothing at a bound
    ach = {"X": {1: 0.5, 3: 1 / 0.7, 4: 1.0}, "Y": {1: 0.5, 3: 0.5, 4: 0.8}}
    n = {"X": {1: 400, 3: 100, 4: 50}, "Y": {1: 400, 3: 100, 4: 50}}
    comp, repl = ph.wilson_components(ach, n, (1, 3, 4))
    plain = se_components(ach, n, (1, 3, 4))
    assert repl == {"X": [3, 4]}
    assert comp["X"][4] == pytest.approx(ph.wilson_se(1.0, 50))
    assert comp["X"][3] == pytest.approx(ph.wilson_se(1.0, 100) / 0.7)
    assert comp["X"][1] == plain["X"][1]
    assert comp["Y"] == plain["Y"]


@pytest.mark.parametrize("rule", ["R1", "R2", "R3"])
def test_points_in_use_reproduces_the_registered_score_se(rule):
    ach = {"A": {1: 0.9, 2: 0.6, 4: 0.85}, "B": {1: 1.1, 2: 0.7, 4: 0.9},
           "C": {1: 0.7, 2: 0.4, 4: None}}
    n = {s: {1: 1000, 2: 300, 4: 250} for s in ach}
    got = ph.score_se_from(se_components(ach, n, (1, 2, 4)),
                           ph.points_in_use(ach, rule, (1, 2, 4)))
    want = score_se(ach, n, rule, (1, 2, 4))
    assert got.keys() == want.keys()
    for s in ach:
        assert got[s] == (pytest.approx(want[s]) if want[s] is not None else None)


def test_ivw_mean_phi_and_tau2_by_hand():
    d, se = [1.0, 2.0, 4.0], [1.0, 1.0, 2.0]
    m = ph.ivw_mean(d, se)
    assert m == pytest.approx((1 + 2 + 1) / 2.25)  # weights 1, 1, 0.25
    w = [1, 1, 0.25]
    q = sum(wi * (di - m) ** 2 for wi, di in zip(w, d))
    assert ph.tau2_dl(d, se, m) == pytest.approx(max(0.0, (q - 2) / (2.25 - 2.0625 / 2.25)))
    # no spread beyond sampling: tau2 truncated at zero
    assert ph.tau2_dl([0.0, 0.1, -0.1], [1.0, 1.0, 1.0], 0.0) == 0.0


def test_winsorised_clamps_at_the_10th_and_90th_percentiles():
    z = list(range(11))  # inclusive deciles of 0..10 are 1..9
    assert ph.winsorised([float(v) for v in z]) == [1.0] + [float(v) for v in range(1, 10)] + [9.0]


def test_funnel_flags_multiplicative_and_additive():
    # 20 states, changes 0 with SE 1, and one state with change 10 and SE 1
    d, se = [0.0] * 20 + [10.0], [1.0] * 21
    m, phi, tau2, flags = ph.funnel(d, se)
    assert m == pytest.approx(10 / 21)
    z = [(v - m) / 1.0 for v in d]
    assert phi == pytest.approx(sum(v * v for v in ph.winsorised(z)) / 21)
    assert phi < 1  # the outlier is winsorised away: no inflation
    assert flags[-1][:2] == (True, True)  # 9.5 > 3.09
    assert not any(any(f) for f in flags[:-1])
    assert tau2 > 0
    assert flags[-1][2] == (abs(10 - m) > 1.96 * math.sqrt(1 + tau2))


def test_multiplicity():
    assert ph.bonferroni_z(35) == pytest.approx(3.1888, abs=1e-4)
    assert ph.p_two_sided(1.96) == pytest.approx(0.05, abs=1e-4)
    # BH: p sorted 0.001, 0.02, 0.03, 0.2 with k = 4 -> thresholds 0.0125, 0.025, 0.0375, 0.05
    assert ph.bh_reject([0.2, 0.02, 0.001, 0.03]) == [False, True, True, True]
    assert ph.bh_reject([0.5, 0.6]) == [False, False]


def test_oldham_point_and_reproducible_bootstrap():
    s_prev = {"a": 70.0, "b": 75.0, "c": 80.0, "d": 85.0, "e": 90.0, "f": None}
    s_t = {"a": 72.0, "b": 75.5, "c": 83.0, "d": 86.0, "e": 95.0, "f": 80.0}
    keys = ["a", "b", "c", "d", "e"]
    d = [s_t[k] - s_prev[k] for k in keys]
    mean = [(s_t[k] + s_prev[k]) / 2 for k in keys]
    out1 = ph.oldham(s_prev, s_t, random.Random(ph.SEED), n_boot=200)
    out2 = ph.oldham(s_prev, s_t, random.Random(ph.SEED), n_boot=200)
    assert out1 == out2
    r, lo, hi, n = out1[:4]
    assert n == 5
    assert r == pytest.approx(statistics.correlation(d, mean))
    assert lo <= r <= hi


def test_lognormal_fit_and_prevalence_bootstrap():
    mu, sg = ph.lognormal_params(100.0, 400.0)
    assert math.exp(mu) == pytest.approx(200.0)
    assert sg == pytest.approx(math.log(4) / (2 * 1.96))
    with pytest.raises(ValueError):
        ph.lognormal_params(0.0, 10.0)
    units = [{"score": float(s), "lo": 100.0 + 10 * s, "hi": 200.0 + 10 * s}
             for s in range(8)]
    a = ph.prevalence_bootstrap(units, random.Random(1), resample=True, n_boot=300)
    b = ph.prevalence_bootstrap(units, random.Random(1), resample=True, n_boot=300)
    assert a == b
    med, lo, hi, und = ph.prevalence_bootstrap(units, random.Random(1), resample=False,
                                               n_boot=300)
    assert lo <= med <= hi and und == 0 and med > 0


def test_rho_half_width_with_19_units():
    assert ph.rho_half_width(19) == pytest.approx(math.tanh(1.96 * math.sqrt(1.06 / 16)))
    assert round(ph.rho_half_width(19), 2) == 0.47


def _copy_inputs(tmp_path):
    import shutil
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for rel in ("outputs/posthoc_summary.csv", "outputs/posthoc_q4_states.csv",
                "outputs/q4_2022_2023_states.csv", "outputs/q3_2023_units.csv",
                "data/extracted/itr2023_indicators.csv", "data/extracted/itr2024_indicators.csv"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / rel, tmp_path / rel)
    return tmp_path


def test_independent_check_passes_and_catches_an_edit(tmp_path):
    from verification import check_posthoc_outputs as chk
    root = _copy_inputs(tmp_path)
    assert chk.problems(root) == []
    p = root / "outputs" / "posthoc_summary.csv"
    text = p.read_text(encoding="utf-8")
    line = next(ln for ln in text.splitlines() if ",R2,1,2,3,4,6," not in ln
                and ",n_exceeds_bonferroni," in ln and ",R2," in ln)
    p.write_text(text.replace(line, line.replace(",23,", ",24,", 1)), encoding="utf-8")
    assert any("n_bonferroni" in m for m in chk.problems(root))

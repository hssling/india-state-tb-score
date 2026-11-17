"""Unit tests of verification/check_manuscript_numbers.py: formats, matching, skip path."""
import shutil
from pathlib import Path

import pytest

from verification import check_manuscript_numbers as cmn

ROOT = Path(__file__).resolve().parents[1]
M = "−"
D = "–"


# ---- number formats ------------------------------------------------------------------
def test_num_uses_true_minus_and_no_negative_zero():
    assert cmn.num(-0.2351, 2) == f"{M}0.24"
    assert cmn.num(0.0594, 2) == "0.06"
    assert cmn.num(-0.004, 2) == "0.00"
    assert cmn.num(12.5, 0) == "12"  # round-half-even, as Python formats


def test_count_thousands_and_integer_only():
    assert cmn.count(1023924) == "1,023,924"
    assert cmn.count(-1150) == f"{M}1,150"
    with pytest.raises(ValueError):
        cmn.count(2.5)


def test_rank_drops_decimals_for_whole_ranks():
    assert cmn.rank(3.0) == "3"
    assert cmn.rank(2.5) == "2.5"


def test_ranges_en_dash_or_to():
    assert cmn.rng("0.82", "0.93") == f"0.82{D}0.93"
    assert cmn.rng(f"{M}0.63", "0.26") == f"{M}0.63 to 0.26"
    assert cmn.rng(f"{M}0.58", f"{M}0.04") == f"{M}0.58 to {M}0.04"


def test_counts_with_percentages_and_rho_ci():
    assert cmn.k_of_n_pct(24, 35) == "24 of 35 (68.6%)"
    assert cmn.pct(1023924, 2552257) == "40.1%"
    assert cmn.rho_ci(-0.2351, -0.6316, 0.2589) == f"{M}0.24 (95% CI {M}0.63 to 0.26)"
    assert cmn.n_eq(19) == "n = 19"
    assert cmn.listing(["A"]) == "A"
    assert cmn.listing(["A", "B", "C"]) == "A, B and C"


# ---- matching --------------------------------------------------------------------------
def test_missing_requires_whole_tokens():
    wants = {"a": "20 of 35", "b": "n = 19"}
    assert cmn.missing("In 20 of 35 states (n = 19 units).", wants) == []
    # '120 of 35' and 'n = 190' must not satisfy the expected strings
    assert [k for k, _ in cmn.missing("In 120 of 35 states (n = 190).", wants)] == ["a", "b"]


def test_unaccounted_flags_changed_numbers_but_not_allowed_ones():
    wants = {"a": "24 of 35 (68.6%)"}
    ok = "In 2023, 24 of 35 (68.6%) states changed (Table IV, §10.3)."
    assert cmn.unaccounted(ok, wants) == []
    bad = "In 2023, 25 of 35 (68.6%) states changed."
    assert cmn.unaccounted(bad, wants) == ["25", "35", "68.6"]


def test_unaccounted_skips_table_rows_and_references():
    text = "Text.\n| 1 | 2 |\n## References\n1. Smith 2020;12:34."
    assert cmn.unaccounted(text, {}) == []


# ---- derivation from the committed outputs --------------------------------------------
def test_want_is_derived_and_required_labels_exist():
    w = cmn.want(ROOT)
    assert set(w) >= set(cmn.REQUIRED) - {p for p in cmn.REQUIRED if "*" in p}
    assert w["q1.verdict"] == "not reproducible"
    assert w["ind3.annexure_share"] == "40.1%"
    assert w["ind3.table11_1_share"] == "58%"
    assert w["pop.diff"] == f"{M}0.025%"
    assert w["q4.R2.all.exceeds"] == "24 of 35 (68.6%)"


def test_unknown_required_label_is_an_error():
    with pytest.raises(KeyError):
        cmn.want(ROOT, required=["q9.nothing"])


# ---- skip path (ruling R6) --------------------------------------------------------------
def test_skips_when_manuscript_dir_absent(tmp_path, capsys):
    assert cmn.main(tmp_path) == 0
    assert capsys.readouterr().out.strip() == cmn.SKIP_DIR
    assert cmn.SKIP_DIR.startswith("SKIPPED")


def test_skips_when_manuscript_md_absent(tmp_path, capsys):
    (tmp_path / "manuscript").mkdir()
    assert cmn.main(tmp_path) == 0
    assert capsys.readouterr().out.strip().startswith("SKIPPED")


def _fake_repo(tmp_path):
    for d in ("outputs", "data"):
        shutil.copytree(ROOT / d, tmp_path / d)
    (tmp_path / "manuscript").mkdir()
    return tmp_path


def test_passes_when_text_carries_every_required_string(tmp_path):
    root = _fake_repo(tmp_path)
    body = "\n".join(f"- {v}" for v in cmn.want(root).values())
    (root / "manuscript" / "manuscript.md").write_text(body, encoding="utf-8")
    assert cmn.main(root) == 0


def test_fails_on_a_changed_number(tmp_path, capsys):
    root = _fake_repo(tmp_path)
    body = "\n".join(f"- {v}" for v in cmn.want(root).values())
    body = body.replace("24 of 35 (68.6%)", "23 of 35 (68.6%)")
    (root / "manuscript" / "manuscript.md").write_text(body, encoding="utf-8")
    assert cmn.main(root) == 1
    out = capsys.readouterr().out
    assert "MISSING q4.R2.all.exceeds" in out and "UNACCOUNTED number in prose: '23'" in out


def test_stale_tables_detected(tmp_path):
    ms = tmp_path / "manuscript"
    ms.mkdir()
    (ms / "make_tables.py").write_text("def render(root):\n    return 'fresh'\n", encoding="utf-8")
    (ms / "tables.md").write_text("fresh", encoding="utf-8")
    assert cmn.stale_tables(tmp_path) is None
    (ms / "tables.md").write_text("old", encoding="utf-8")
    assert "stale" in cmn.stale_tables(tmp_path)


def test_sign_flip_is_caught():
    want = "0.48 (95% CI 0.16\u20130.71)"
    for sign in ("\u2212", "-"):
        flipped = f"Rho was {sign}{want}."
        assert cmn.missing(flipped, {"a": want}) == [("a", want)]
        assert cmn.unaccounted(flipped, {"a": want}) != []
    assert cmn.missing(f"Rho was {want}.", {"a": want}) == []

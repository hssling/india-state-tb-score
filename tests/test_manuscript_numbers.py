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
    for d in ("outputs", "data", "docs"):
        shutil.copytree(ROOT / d, tmp_path / d)
    shutil.copy(ROOT / "ENVIRONMENT.md", tmp_path / "ENVIRONMENT.md")
    (tmp_path / "manuscript").mkdir()
    return tmp_path


def _text(root):
    """A minimal manuscript: an abstract with its headline strings, then every string."""
    abstract = "\n".join(f"- {v}" for v in cmn.want(root, cmn.ABSTRACT_REQUIRED).values())
    body = "\n".join(f"- {v}" for v in cmn.want(root).values())
    return f"# Title\n\n## Abstract\n\n{abstract}\n\n## Introduction\n\n{body}\n"


def test_passes_when_text_carries_every_required_string(tmp_path):
    root = _fake_repo(tmp_path)
    (root / "manuscript" / "manuscript.md").write_text(_text(root), encoding="utf-8")
    assert cmn.main(root) == 0


def test_fails_on_a_changed_number(tmp_path, capsys):
    root = _fake_repo(tmp_path)
    body = _text(root)
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


# ---- part b: blind spots of the number scan, the abstract, Methods constants ------------
def test_only_study_years_are_masked():
    assert cmn.unaccounted("In 2019–21, 2022 and 2023 (registered 2026).", {}) == []
    # a four-digit number in the 19xx/20xx range that is not a study year is not a year
    assert cmn.unaccounted("Of 1987 patients, 2061 were notified.", {}) == ["1987", "2061"]
    assert cmn.unaccounted("2023.5 points", {}) == ["2023.5"]


def test_indicator_names_do_not_swallow_the_next_number():
    assert cmn.unaccounted("indicators 1, 2, 3, 4 and 6 and indicator 9", {}) == []
    assert cmn.unaccounted("indicator 6, 25 of 35", {}) == ["25", "35"]
    assert cmn.unaccounted("indicator 12", {}) == ["12"]
    assert cmn.unaccounted("Tables I and II, Web tables 1 and 2", {}) == []
    assert cmn.unaccounted("Table II, 36 states", {}) == ["36"]


def test_bare_small_integers_do_not_mask_the_prose():
    # a catalogue holding a bare "3" must not account for every 3 in the text
    assert cmn.unaccounted("3 states", {"q": "3"}) == ["3"]
    assert cmn.unaccounted("3 states in 2022", {"q": "3 states in 2022"}) == []


def test_abstract_section_is_found():
    text = "## Abstract\n\nA 1.\n\n**Keywords:** x\n\n## Introduction\n\nB 2."
    assert "A 1." in cmn.section(text, "Abstract")
    assert "B 2." not in cmn.section(text, "Abstract")
    assert cmn.section(text, "Missing") == ""


def test_headline_missing_from_the_abstract_fails(tmp_path, capsys):
    root = _fake_repo(tmp_path)
    body = "\n".join(f"- {v}" for v in cmn.want(root).values())
    text = f"## Abstract\n\nNo numbers here.\n\n## Introduction\n\n{body}\n"
    (root / "manuscript" / "manuscript.md").write_text(text, encoding="utf-8")
    assert cmn.main(root) == 1
    assert "MISSING in the abstract q4.R2.all.exceeds" in capsys.readouterr().out


def test_tables_must_be_inserted_verbatim(tmp_path):
    ms = tmp_path / "manuscript"
    ms.mkdir()
    (ms / "tables.md").write_text("<!-- generated -->\n| a | 1 |\n", encoding="utf-8")
    assert cmn.tables_not_inserted(tmp_path, "text\n| a | 1 |\nmore") is None
    assert "verbatim" in cmn.tables_not_inserted(tmp_path, "text\n| a | 2 |\n")


def test_methods_constants_are_derived():
    w = cmn.catalogue(ROOT)
    assert w["methods.draws"] == "10,000 draws"
    assert w["methods.seed"] == "seed 20261117"
    assert w["methods.c"] == "c = 63"
    assert w["methods.alpha"] == "α = 1"
    assert w["methods.z"] == "1.96"
    assert w["methods.ci_level"] == "95% confidence interval"
    assert w["methods.sat_share"] == "80% of states"
    assert w["methods.sat_level"] == "0.95"
    assert w["methods.tolerance"] == "0.01 points"
    assert w["q1.target.tolerance"] == "0.1%"
    assert w["methods.udst"] == "70% of net notified patients"
    assert w["methods.registration"] == "16 November 2026 at 19:06:50 UTC"
    assert w["methods.n_deviations"] == "seven dated deviations"
    assert w["q4.ind4_error.counts"] == "21 successful outcomes against 14 net notified patients"
    assert w["q4.se0_counts"] == "3 states in 2022 and 2 in 2023"
    assert w["methods.udst_se"] == "divided by 0.7"
    assert w["methods.r2_cap"] == "more than its 10 points"
    assert w["q3.clusters"] == "443 of 625 planned clusters"
    assert w["q2.fifth_size"] == "7 states in each fifth"
    assert w["q4.R1.no1.rho_context"] == "−0.30 under R1"
    assert "methods.seed" not in cmn.want(ROOT)  # not printed in the blinded text




# ---- fix round 1: figure legends are scanned; versions come from ENVIRONMENT.md -------
def test_figure_legends_are_scanned_but_references_and_tables_are_not():
    text = ("Intro 2023.\n## References\n1. Smith. J. 2020;12:34.\n## Tables\n"
            "Footnote: 99 units.\n| 7 | 8 |\n## Legends to Figures\n"
            "**Figure 1.** One point per state (n = 41).\n| 5 |\n")
    assert cmn.unaccounted(text, {}) == ["41"]
    assert cmn.unaccounted(text, {"n": "n = 41"}) == []


def test_versions_are_read_from_environment_md(tmp_path):
    (tmp_path / "ENVIRONMENT.md").write_text("# Env\n\n- Python 3.99.1\n- pdfplumber 9.8.7\n",
                                             encoding="utf-8")
    assert cmn.environment(tmp_path) == {"Python": "3.99.1", "pdfplumber": "9.8.7"}
    (tmp_path / "ENVIRONMENT.md").write_text("- Python 3.99.1\n", encoding="utf-8")
    with pytest.raises(ValueError):
        cmn.environment(tmp_path)
    env = cmn.environment(ROOT)
    w = cmn.catalogue(ROOT)
    assert w["methods.python"] == f"Python {env['Python']}"
    assert w["methods.pdfplumber"] == f"pdfplumber {env['pdfplumber']}"

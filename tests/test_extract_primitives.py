from pathlib import Path

import pytest

from src import states
from src.extract import cells, pdftext

ITR2024 = Path("data_raw/india_tb_report/ITR2024.pdf")
needs_pdf = pytest.mark.skipif(not ITR2024.exists(), reason="data_raw/ITR2024.pdf absent")


def test_canonical_rejects_unknown():
    with pytest.raises(KeyError):
        states.canonical("Atlantis")


def test_canonical_rejects_national_rows():
    for n in ("India", "Total", "Grand Total"):
        with pytest.raises(KeyError):
            states.canonical(n)


def test_canonical_aliases_and_case():
    assert states.canonical("jammu  &  KASHMIR") == "Jammu and Kashmir"
    assert states.canonical("Orissa") == "Odisha"
    assert states.canonical("NCT of Delhi") == "Delhi"
    assert states.canonical("DNH and DD") == "Dadra and Nagar Haveli and Daman and Diu"
    assert states.canonical("Andaman & Nicobar Islands") == "Andaman and Nicobar Islands"


def test_all_has_36_in_table_order():
    assert len(states.ALL) == 36 and len(set(states.ALL)) == 36
    assert list(states.ALL) == sorted(states.ALL)
    assert all("&" not in s for s in states.ALL)


def test_join_requires_all_units():
    names = [s for s in states.ALL if s != "Ladakh"]
    with pytest.raises(ValueError, match="Ladakh"):
        states.require_all(names, 2023)
    states.require_all(states.ALL, 2023)


def test_require_all_pre_2020():
    names = [s for s in states.ALL
             if s not in ("Ladakh", "Dadra and Nagar Haveli and Daman and Diu")]
    names += ["Dadra and Nagar Haveli", "Daman and Diu"]
    states.require_all(names, 2019)
    with pytest.raises(ValueError, match="Ladakh"):
        states.require_all(names, 2021)
    with pytest.raises(ValueError, match="extra"):
        states.require_all(list(states.ALL), 2019)


def test_parse_cells():
    assert cells.parse_int("1,23,456") == 123456
    assert cells.parse_int(" 1,234,567 ") == 1234567
    assert cells.parse_int("*89") == 89 and cells.parse_int("89*") == 89
    assert cells.parse_n_pct("62795 (99%)") == (62795, 99.0)
    assert cells.parse_n_pct("62795(99%)") == (62795, 99.0)
    assert cells.parse_n_pct("1,23,456 (99.5%)") == (123456, 99.5)


@pytest.mark.parametrize("bad", ["", "  ", "-", "NA", "abc", "12 ab"])
def test_parse_int_rejects_blank_and_text(bad):
    with pytest.raises(ValueError):
        cells.parse_int(bad)


@needs_pdf
def test_rotated_page_rows():
    # Annexure 7.2 runs over PDF pages 282 (A-K) and 283 (Ladakh-West Bengal).
    lines = pdftext.page_lines(ITR2024, 282) + pdftext.page_lines(ITR2024, 283)
    assert any(l.startswith("Uttar Pradesh ") for l in lines)
    assert any(l.startswith("Andhra Pradesh 4607.0 4301 (93%)") for l in lines)
    assert not any("noitacifiton" in l or "sraey" in l for l in lines)


@needs_pdf
def test_rotated_pages_have_all_states():
    lines = []
    for pg in (282, 283):
        lines += states.join_wrapped_names(pdftext.page_lines(ITR2024, pg))
    found = {h[0] for h in map(states.leading_state, lines) if h}
    assert len(found) >= 30
    states.require_all(found, 2023)


@needs_pdf
def test_wrapped_names_rejoined():
    p282 = states.join_wrapped_names(pdftext.page_lines(ITR2024, 282))
    assert any(l.startswith("Dadra and Nagar Haveli and Daman and Diu 69.0 ") for l in p282)
    p284 = states.join_wrapped_names(pdftext.page_lines(ITR2024, 284))
    assert any(l.startswith("Andaman and Nicobar Islands 861 ") for l in p284)
    assert any(l.startswith("Dadra and Nagar Haveli and Daman and Diu 1327 ") for l in p284)


@needs_pdf
def test_upright_page_rows():
    lines = pdftext.page_lines(ITR2024, 199)
    assert "Andhra Pradesh 62795 (99%) 26412 (100%) 89207 (99%)" in lines

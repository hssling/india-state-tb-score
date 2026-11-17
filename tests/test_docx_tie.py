"""Fixture tests of verification/check_docx_tie.py with a docx built by python-docx."""
import pytest

docx = pytest.importorskip("docx")

from verification import check_docx_tie as tie  # noqa: E402


def make(path, results="Between 2022 and 2023, 24 of 35 states (Table II)."):
    d = docx.Document()
    for h in ("Abstract", "Introduction", "Results", "References"):
        d.add_paragraph(h)
        if h == "Results":
            p = d.add_paragraph(results)
            p.add_run("12").font.superscript = True  # follows a digit-free word below
            d.add_paragraph("Value 2024")
            q = d.paragraphs[-1]
            q.add_run("3").font.superscript = True  # 2024 then superscript 3
    d.add_table(rows=1, cols=1).cell(0, 0).text = "99 in a table"
    d.save(str(path))


def test_sections_tokens_and_superscript_separation(tmp_path):
    f = tmp_path / "a.docx"
    make(f)
    secs = tie.docx_sections(f)
    assert set(secs) == {"Abstract", "Introduction", "Results", "References"}
    toks = tie.tokens(secs["Results"])
    assert toks == ["2022", "2023", "24", "35", "II", "12", "2024", "3"]  # "2024" + sup 3 stay apart
    assert "99" not in " ".join(toks)  # table cells are not part of a section


def test_compare_reports_the_first_difference(tmp_path):
    f, g = tmp_path / "a.docx", tmp_path / "b.docx"
    make(f)
    make(g, results="Between 2022 and 2023, 25 of 35 states (Table II).")
    a = tie.tokens(tie.docx_sections(f)["Results"])
    b = tie.tokens(tie.docx_sections(g)["Results"])
    assert tie.compare(a, a) is None
    assert "'24'" in tie.compare(a, b) and "'25'" in tie.compare(a, b)


def test_md_clean_separates_carets():
    assert tie.tokens(tie.md_clean("in 2024^2^ and **35**")) == ["2024", "2", "35"]

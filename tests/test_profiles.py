"""Fixture tests of the journal profiles (check_manuscript_numbers.PROFILES): the IJMR set and
the Journal of Public Health (JPH) set. A small synthetic JPH manuscript is used, not the
(git-ignored) real one."""
import importlib.util
import json
import re
from pathlib import Path

import pytest

from verification import check_docx_tie as tie
from verification import check_manuscript_numbers as cmn
from verification import mutate_manuscript as mm

ROOT = Path(__file__).resolve().parents[1]

JPH_FIXTURE = """# Title

## Abstract

**Background:** Text.

**Methods:** Under R2, 20 of 35 states.

**Results:** Between 2022 and 2023, ρ 0.82–0.93.

**Conclusions:** Text.

**Keywords:** A; B

## Introduction

Ignored 99 here.

## Methods

Draws: 10,000 draws (Supplementary Table S1), indicators 1, 2 and 3 (India TB Report 2024, Table 11.2).^4,5^

## Results

Supplementary Table S2 shows 85,231 of 2,360,036 (3.6%) (Figure 1). Table I, Supplementary Figure S1 and Supplementary Tables S3 and S4. Figure 2, Supplementary Table S5.

## Discussion

### Main finding of this study

Q4 and R3 apply (Supplementary Table S6, Figure 3); Supplementary Table S7; Supplementary Tables S8–S10.

### What is already known on this topic

Text.

### What this study adds

1. **Publish the rule.** Seven of 9 items.
2. **Judge against noise.** Text.

### Limitations of this study

n = 7 states.

### Conclusions

Text.

## References

1. Source. 2030.

## Tables

**Table I. A**

| a | b |
|---|---|
| 1 | 2 |

# Supplementary tables

**Supplementary Table S1. a**

**Supplementary Table S2. b**

**Supplementary Table S3. c**

**Supplementary Table S4. d**

**Supplementary Table S5. e**

**Supplementary Table S6. f**

**Supplementary Table S7. g**

**Supplementary Table S8. h**

**Supplementary Table S9. i**

**Supplementary Table S10. j**

## Legends to Figures

**Fig. 1.** One, n = 5.

Alt text: a plot.

**Fig. 2.** Two.

**Fig. 3.** Three.

## Supplementary figure

**Supplementary Fig. S1.** Four, 7 states.
"""


def test_profile_lookup_by_directory_and_name():
    assert cmn.profile_for() is cmn.IJMR
    assert cmn.profile_for("manuscript") is cmn.IJMR
    assert cmn.profile_for("manuscript/jph_v2") is cmn.JPH
    assert cmn.profile_for(str(ROOT / "manuscript" / "jph_v2")) is cmn.JPH
    assert cmn.profile_for(name="jph") is cmn.JPH
    with pytest.raises(SystemExit):
        cmn.profile_for("elsewhere")
    prof, d = cmn.cli_profile(["--manuscript-dir", "manuscript/jph_v2"], ROOT)
    assert prof is cmn.JPH and d == ROOT / "manuscript" / "jph_v2"
    prof, d = cmn.cli_profile([], ROOT)
    assert prof is cmn.IJMR and d == ROOT / "manuscript"


def test_profile_constants():
    assert cmn.IJMR.count_pct == cmn.JPH.count_pct == cmn.COUNT_PCT
    assert cmn.k_of_n_pct(24, 35) == "24 of 35 (68.6%)"
    assert cmn.k_of_n_pct(24, 35, "{pct} ({k_of_n})") == "68.6% (24 of 35)"
    assert [e.roman for e in cmn.IJMR.exhibits if e.kind == "Table"] == [True]
    assert [e.roman for e in cmn.JPH.exhibits if e.kind == "Table"] == [True]  # Table I
    assert cmn.JPH.title_in_ms and cmn.JPH.ms_docx == cmn.JPH.title_docx == "01_manuscript.docx"
    assert "Data availability" in cmn.JPH.section_order
    assert dict(cmn.IJMR.display_limits) == {("Table",): 4, ("Figure",): 4}
    assert dict(cmn.JPH.display_limits) == {("Table", "Figure"): 4}
    assert cmn.IJMR.allow == tuple(cmn.ALLOW)
    assert (cmn.JPH.abstract_max, cmn.JPH.main_min, cmn.JPH.main_max) == (200, 2000, 3000)


def test_section_is_level_aware():
    disc = cmn.section(JPH_FIXTURE, "Discussion")
    assert "Seven of 9 items" in disc and "n = 7 states" in disc
    assert "###" not in disc and "Main finding" not in disc
    assert "Source" not in disc  # stops at the next '##'
    assert cmn.section(JPH_FIXTURE, "Supplementary figure").strip().endswith("7 states.")


def test_jph_citations_and_exhibits():
    c = cmn.citations(JPH_FIXTURE, cmn.JPH)
    assert c["Table"] == [1]  # "Table 11.2" (a source table) is not Table 1
    assert c["Figure"] == [1, 2, 3]
    assert c["Supplementary Table"] == list(range(1, 11))  # "S8–S10" is a range
    assert c["Supplementary Figure"] == [1]
    assert cmn.exhibit_problems(JPH_FIXTURE, cmn.JPH) == []
    swapped = JPH_FIXTURE.replace("Supplementary Tables S3 and S4", "Supplementary Tables S4 and S3")
    assert any("out of order" in p for p in cmn.exhibit_problems(swapped, cmn.JPH))
    extra = JPH_FIXTURE.replace("**Fig. 3.** Three.", "**Fig. 3.** Three.\n\n**Fig. 4.** Four.")
    extra = extra.replace("Figure 3);", "Figure 3); Figure 4;")
    msgs = " ".join(cmn.exhibit_problems(extra, cmn.JPH))
    assert "limit 4" in msgs and "captions found" in msgs


def test_jph_structure():
    assert cmn.structure_problems(JPH_FIXTURE, cmn.JPH) == []
    assert cmn.structure_problems(JPH_FIXTURE, cmn.IJMR) == []
    gone = JPH_FIXTURE.replace("### What this study adds\n", "")
    assert any("What this study adds" in p for p in cmn.structure_problems(gone, cmn.JPH))
    swapped = (JPH_FIXTURE.replace("### Main finding of this study", "### TMP")
               .replace("### Limitations of this study", "### Main finding of this study")
               .replace("### TMP", "### Limitations of this study"))
    assert any("order" in p for p in cmn.structure_problems(swapped, cmn.JPH))
    no_head = JPH_FIXTURE.replace("**Conclusions:** Text.", "Text.")
    assert any("Conclusions" in p for p in cmn.structure_problems(no_head, cmn.JPH))


def test_jph_unaccounted_masks_labels_and_list_numbers_only():
    t = "## Results\n\nSupplementary Tables S3 and S4 and Supplementary Figure S1, 17 left.\n"
    assert cmn.unaccounted(t, {}, list(cmn.JPH.allow)) == ["17"]
    assert "3" in cmn.unaccounted(t, {}, list(cmn.IJMR.allow))
    t = "## Discussion\n\n1. **Publish.** Then 2. items.\n"
    assert cmn.unaccounted(t, {}, list(cmn.JPH.allow)) == ["2"]


def test_jph_skeleton_and_mutations_cover_subsections(tmp_path):
    order = cmn.JPH.section_order
    sk = cmn.skeleton(JPH_FIXTURE, order)
    # sub-headed text and list item numbers are part of the Discussion's tokens
    assert sk["Discussion"] == ["4", "3", "6", "3", "7", "8", "10", "1", "9", "2", "7"]
    assert sk["Supplementary figure"] == ["1", "7"]
    spans = mm.token_spans(JPH_FIXTURE, order)
    by_sec = {}
    for s, a, b in spans:
        by_sec.setdefault(s, []).append(JPH_FIXTURE[a:b])
    assert by_sec == {k: v for k, v in sk.items() if v}  # the harness mutates what is checked
    d = tmp_path / "manuscript" / "jph_v2"
    d.mkdir(parents=True)
    (d / cmn.SKELETON).write_text(json.dumps(sk), encoding="utf-8")
    assert cmn.skeleton_problems(JPH_FIXTURE, tmp_path, cmn.JPH) == []
    assert cmn.skeleton_problems(JPH_FIXTURE.replace("Seven of 9", "Seven of 8"), tmp_path, cmn.JPH)


def test_ijmr_token_spans_unchanged_by_level_awareness():
    text = "## Methods\n\n1 and 2.\n\n## Results\n\n3.\n\n### Sub\n\n4.\n\n## References\n\n5.\n"
    spans = mm.token_spans(text)
    assert [(s, text[a:b]) for s, a, b in spans] == [("Methods", "1"), ("Methods", "2"),
                                                     ("Results", "3"), ("Results", "4")]


def test_docx_tie_ignores_list_numbers_word_numbers_itself():
    assert tie.tokens(tie.md_clean("1. **Publish** 15 points\n2. **Drop** it")) == ["15"]
    assert tie.tokens(tie.md_clean("In 2024^2^ and **35**")) == ["2024", "2", "35"]


def _make_tables():
    spec = importlib.util.spec_from_file_location("make_tables", ROOT / "exhibits" / "make_tables.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_make_tables_profiles():
    mt = _make_tables()
    ijmr = mt.render(ROOT)
    assert mt.render(ROOT, "ijmr") == ijmr
    jph = mt.render(ROOT, "jph")
    assert not re.search(r"\bTables? (?:II|III|IV)\b|Web table", jph)  # only Table I
    caps = re.findall(r"(?m)^\*\*((?:Supplementary )?Table S?[IVX\d]+)\.", jph)
    assert caps == ["Table I"] + [f"Supplementary Table S{i}" for i in range(1, 11)]
    assert "carried into Table I and Supplementary Table S7" in jph
    assert "layout as Table I" in jph and "Data Availability Statement" in jph
    # footnotes as lower-case letters (JPH), section references ("§13") kept
    assert "^a^" in jph and "§13" in jph and "†" not in jph and "‡" not in jph
    # the flat Dirichlet is labelled as centred on equal weights in the JPH tables only
    assert "centred on equal weights (α = 1 for each indicator)" in jph
    assert "centred on equal weights" not in ijmr
    # the same numbers: every number token of the IJMR tables is in the JPH tables; the JPH
    # set adds the section 13 log, the post hoc tables and the descriptive context note
    num = re.compile(r"\d[\d,.]*")
    strip_labels = lambda t: re.sub(  # noqa: E731
        r"(?:Supplementary )?(?:Table|Figure|Web table)s? S?[IVX\d]+(?![\d.]\d)", "", t)
    from collections import Counter
    shared = Counter(num.findall(strip_labels(ijmr))) - Counter(num.findall(strip_labels(jph)))
    assert not shared, f"IJMR table numbers missing from the JPH tables: {dict(shared)}"
    assert mt.both("Table III", "Table IV") == "Tables III and IV"
    assert mt.both("Table 1", "Supplementary Table S6") == "Table 1 and Supplementary Table S6"


def test_jph_section13_log_types_cover_every_entry():
    mt = _make_tables()
    entries = mt.log_entries(ROOT)
    assert [n for n, _, _ in entries] == sorted(mt.LOG_TYPES)
    assert entries[-1][1] == "20 November 2026"
    kinds = [mt.LOG_TYPES[n][1].split(":")[0] for n, _, _ in entries]
    assert kinds.count("Deviation") == 5 and kinds.count("Note") == 5


def test_jph_profile_requires_post_hoc_labels():
    req = cmn.JPH.req()
    assert "posthoc.R2.bonferroni" in req and "q4.R2.no1.rho_ci" not in req
    assert cmn.IJMR.req() == cmn.REQUIRED and cmn.IJMR.abstract_req() == cmn.ABSTRACT_REQUIRED
    cat = cmn.catalogue(ROOT)
    want = cmn.want(ROOT, req)
    # a changed post hoc count is a missing string and an unaccounted number
    text = "\n".join(want.values())
    bad = text.replace(cat["posthoc.R2.bonferroni"],
                       cat["posthoc.R2.bonferroni"].replace("23 of", "21 of"))
    assert cmn.missing(bad, want) == [("posthoc.R2.bonferroni", cat["posthoc.R2.bonferroni"])]
    assert "21" in cmn.unaccounted(bad, cat, list(cmn.JPH.allow))


def _docx(tmp_path, parts):
    docx = pytest.importorskip("docx")
    from docx.enum.text import WD_BREAK
    d = docx.Document()
    for part in parts:
        if part == "BREAK":
            d.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        else:
            d.add_paragraph(part)
    path = tmp_path / "ms.docx"
    d.save(str(path))
    return path


def test_jph_title_page_and_abstract_page_layout(tmp_path):
    good = ["Title", "Professor", "BREAK", "Abstract", "Background: text.", "Keywords: A; B",
            "BREAK", "Introduction", "Text."]
    title, probs = tie.title_page_layout(_docx(tmp_path, good))
    assert probs == [] and "Professor" in title
    no_break = [x for i, x in enumerate(good) if i != 6]  # abstract runs into the text
    assert any("Introduction" in p for p in tie.title_page_layout(_docx(tmp_path, no_break))[1])
    mid = good[:5] + ["BREAK"] + good[5:]  # a page break inside the abstract page
    assert tie.title_page_layout(_docx(tmp_path, mid))[1]
    no_title = good[2:]
    assert tie.title_page_layout(_docx(tmp_path, no_title))[1]

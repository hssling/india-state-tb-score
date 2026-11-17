"""Fixture tests of the manuscript checks: skeleton, exhibit citations, labels and the
mutation harness. They use a small synthetic manuscript, not the (git-ignored) real one."""
import json
from pathlib import Path

from verification import check_manuscript_numbers as cmn
from verification import mutate_manuscript as mm

ROOT = Path(__file__).resolve().parents[1]

FIXTURE = """# Title

## Abstract

**Results:** Under R2, 20 of 35 states (Table I). Between 2022 and 2023, ρ 0.82–0.93.

## Introduction

Ignored 99 here.

## Methods

Draws: 10,000 draws (Figure 1), indicators 1, 2 and 3.^4,5^

## Results

Web table 1 shows 85,231 of 2,360,036 (3.6%). Tables II and III, Figure 2, Web tables 2.

## Discussion

Q4 and R3 apply (Table IV, Figures 3–4); Web table 3 and Web table 4.

## References

1. Source. Table 11.2 is a source table. 2030.

## Tables

**Table I. A**

| a | b |
|---|---|
| 1 | 2 |

**Table II. B**

**Table III. C**

**Table IV. D**

# Web tables

**Web table 1. a**

**Web table 2. b**

**Web table 3. c**

**Web table 4. d**

## Legends to Figures

**Figure 1.** One, n = 5.

**Figure 2.** Two.

**Figure 3.** Three.

**Figure 4.** Four.
"""


def test_skeleton_tokens_keep_thousands_and_split_lists():
    sk = cmn.skeleton(FIXTURE)
    assert sk["Methods"] == ["10,000", "1", "1", "2", "3", "4", "5"]
    assert sk["Abstract"][-5:] == ["I", "2022", "2023", "0.82", "0.93"]  # Table I is a token
    assert "85,231" in sk["Results"] and "2,360,036" in sk["Results"]
    assert "99" not in sum(sk.values(), [])  # the Introduction is not checked


def test_skeleton_catches_a_single_token_change(tmp_path):
    (tmp_path / "manuscript").mkdir()
    (tmp_path / "manuscript" / cmn.SKELETON).write_text(
        json.dumps(cmn.skeleton(FIXTURE)), encoding="utf-8")
    assert cmn.skeleton_problems(FIXTURE, tmp_path) == []
    for old, new in (("0.82", "0.83"), ("(Table IV,", "(Table III,"), ("Figure 1", "Figure 2"),
                     ("2022", "2023"), ("n = 5", "n = 6")):
        assert cmn.skeleton_problems(FIXTURE.replace(old, new, 1), tmp_path), (old, new)


def test_skeleton_missing_file_is_a_problem(tmp_path):
    (tmp_path / "manuscript").mkdir()
    assert "missing" in cmn.skeleton_problems(FIXTURE, tmp_path)[0]


def test_citations_roman_arabic_and_source_tables():
    c = cmn.citations(FIXTURE)
    assert c["Table"] == [1, 2, 3, 4]
    assert c["Figure"] == [1, 2, 3, 4]
    assert c["Web table"] == [1, 2, 3, 4]  # "Table 11.2" and legend labels do not count
    assert cmn.exhibit_problems(FIXTURE) == []


def test_exhibit_checks():
    swapped = FIXTURE.replace("(Table I)", "(Table V)")
    assert any("cited but not present" in p for p in cmn.exhibit_problems(swapped))
    reordered = FIXTURE.replace("Tables II and III", "Tables III and II")
    assert any("out of order" in p for p in cmn.exhibit_problems(reordered))
    uncited = FIXTURE.replace("Web table 3 and ", "")
    assert any("never cited" in p for p in cmn.exhibit_problems(uncited))
    missing_caption = FIXTURE.replace("**Figure 4.** Four.", "")
    assert any("captions found" in p for p in cmn.exhibit_problems(missing_caption))


def test_label_ranges_and_years():
    assert cmn.label_problems(FIXTURE, ROOT) == []
    bad = FIXTURE.replace("Q4", "Q5").replace("R3", "R7").replace("indicators 1, 2 and 3",
                                                                    "indicators 1, 2 and 10")
    msgs = " ".join(cmn.label_problems(bad, ROOT))
    assert "Q5" in msgs and "R7" in msgs and "indicator 10" in msgs
    assert any("year 2025" in p for p in cmn.label_problems(
        FIXTURE.replace("Between 2022 and 2023", "Between 2022 and 2025"), ROOT))


def test_token_spans_and_mutations():
    spans = mm.token_spans(FIXTURE)
    secs = {s for s, _, _ in spans}
    assert secs == {"Abstract", "Methods", "Results", "Discussion", "Legends to Figures"}
    assert all(FIXTURE[a:b].replace(",", "").replace(".", "").isdigit() or FIXTURE[a:b] in mm.ROMAN_NEXT
               for _, a, b in spans)
    inc = list(mm.mutations(FIXTURE, "inc"))
    assert len(inc) == len(spans)
    assert all(m != FIXTURE for _, m in inc)
    assert mm.bump("0.99") == "0.90" and mm.bump("10,000") == "10,001" and mm.bump("II") == "III"
    swap = list(mm.mutations(FIXTURE, "swap"))
    assert swap and all(m != FIXTURE for _, m in swap)


def test_run_counts_caught_and_escaped():
    caught, total, escaped = mm.run(ROOT, FIXTURE, ("inc",), check=lambda t: t != FIXTURE)
    assert (caught, total, escaped) == (total, total, [])
    caught, total, escaped = mm.run(ROOT, FIXTURE, ("inc",), check=lambda t: False)
    assert caught == 0 and len(escaped) == total > 0
    # a checker blind to one section misses exactly that section's tokens
    blind = lambda t: cmn.skeleton(t)["Methods"] != cmn.skeleton(FIXTURE)["Methods"]  # noqa: E731
    caught, total, escaped = mm.run(ROOT, FIXTURE, ("inc",), check=blind)
    assert caught == len(cmn.skeleton(FIXTURE)["Methods"]) and escaped

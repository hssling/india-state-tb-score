# Mutation record

Each check was shown to fail on a deliberate break. All breaks were made in a scratch
clone (`git clone . <scratch>/mut`), never in this repository or its history, and the
clone was restored (`git checkout -- .` or `git reset --hard origin/main`) between
runs. Run on 17 November 2026 against the tree of the commit just before this file was added (clone without `data_raw/`
unless stated, so `check_extraction_totals` was skipped in the full runs).

| # | Check | Break | Result |
|---|-------|-------|--------|
| a1 | byte-for-byte reproduction (check_all) | one extracted value edited | caught |
| a2 | check_extraction_totals | state sum shifted by 1 in the extractor's check | caught |
| b1 | check_plan_order | a line before section 13 of the plan edited and committed | caught |
| b2 | check_plan_order | history rewritten so a `src/` commit precedes the plan's second commit | caught |
| c | check_deviations | the word "Exploratory" added to an output | caught |
| d | pytest step of check_all | a source constant changed so tests fail | caught |

## a1. Edited extracted value

```
sed -i '2s/,89.73,/,89.74,/' data/extracted/itr2024_scores.csv
python -I verification/check_all.py
```

```
[ok] pytest
[ok] q1_reproduce 2023
[ok] q2_robust 2023
[ok] q3_validity 2023
[ok] q4_change
[FAIL] byte-for-byte reproduction of outputs/ and data/
    M data/extracted/itr2024_scores.csv
     M outputs/q1_2023.csv
     M outputs/q1_2023_selection.json
     M outputs/q3_2023_secondary_states.csv
     M outputs/q3_2023_summary.csv
     M outputs/q3_2023_units.csv
     M outputs/q4_2022_2023_states.csv
     M outputs/q4_2022_2023_summary.csv
    (files differ from the committed versions)
[SKIP] check_extraction_totals
[ok] check_plan_order
[ok] check_deviations

7/8 checks passed (1 skipped)      # exit 1
```

The unit tests did not catch this edit; the byte-for-byte step did, because the
analyses re-run from the edited value and their outputs no longer match the commit.

## a2. Extraction total check (source PDF present)

`ITR2024.pdf` copied into the clone's `data_raw/`; in `src/extract/itr2024.py`,
`check_national` made to compute `total = 1 + sum(...)`.

```
python -I verification/check_extraction_totals.py
```

```
FAIL: ITR2024: ValueError: Annexure 1.2 target_total: state sum 2762833 != INDIA 2762832
SKIPPED: source PDFs not present (run tools/fetch_sources.py); not checked: ITR2023, NTPS, ITR2021
exit=1
```

## b1. Plan edited before section 13

Line 13 of `docs/analysis_plan.md` (background text) edited and committed.

```
python -I verification/check_plan_order.py
```

```
FAIL: docs/analysis_plan.md differs from its registered text before section 13 (first difference at line 13)
exit=1
```

## b2. Reordered history

A commit adding `src/early.py` was placed between the plan's first and second commits
with `git branch early 7836057`, a commit on it, and
`git rebase --onto early 7836057 main`. The rebase gives the registration commit a new
SHA, so 999da8b is no longer in HEAD's history.

```
python -I verification/check_plan_order.py
```

```
FAIL: registration commit 999da8b is not an ancestor of HEAD
exit=1
```

The "commit touching src/, data/extracted/ or outputs/ precedes registration" branch
of the check, and the "edit before section 13" and "edit in section 13 is allowed"
cases, are covered by `tests/test_verification.py` on temporary repositories.

## c. Unlogged exploratory label

A copy of an output with a column named "Exploratory" added (`outputs/q4_copy.csv`;
removed afterwards). Before the break the check printed `OK: no exploratory outputs`.

```
python -I verification/check_deviations.py
```

```
FAIL: outputs/q4_copy.csv: 1 'exploratory' label(s) with no dated section 13 entry naming the file
exit=1
```

## d. A failing test

`RULES = ("R1", "R2", "R3")` changed to `RULES = ("R1", "R2")` in `src/score.py`.

```
python -I verification/check_all.py
```

```
[FAIL] pytest
    ...
    E       AssertionError: assert ('R1', 'R2') == ('R1', 'R2', 'R3')
    FAILED tests/test_q1.py::test_no_admissible_chooses_smallest_violation
    FAILED tests/test_q4.py::test_r3_points_divided_by_year_max
    FAILED tests/test_score.py::test_r3_relative_to_best
    FAILED tests/test_score.py::test_r3_max_over_computable_states_only
    FAILED tests/test_score.py::test_points_and_rules
    5 failed, 118 passed, 28 skipped in 4.59s
[ok] q1_reproduce 2023
...
[FAIL] byte-for-byte reproduction of outputs/ and data/
...
6/8 checks passed (1 skipped)      # exit 1
```

## Manuscript numbers (check_manuscript_numbers.py)

Run on 17 November 2026 on a scratch copy of the repository (not the repository itself); the
real `manuscript/manuscript.md` was never edited (MD5 identical before and after). The
unmutated copy passes (53 expected strings, 8 in the abstract, 0 problems). Each of the 92
numeric tokens in the Abstract (22) and Results (70) prose, excluding table rows and
reference superscripts, was changed once, one at a time, by adding 1 to its last digit
(9 becomes 0). A change counts as caught only if the checker exits 1 with a `MISSING` or
`UNACCOUNTED` line (not a crash).

| Class of token | Mutated | Caught |
|---|---|---|
| Values (counts, percentages, coefficients, intervals, limits) | 56 | 55 |
| Labels: study years (2019-2026), `21` of "2019–21", Q1–Q4, R1–R3, indicator numbers, Table, Figure and Web table numbers | 36 | 0 |
| **All** | **92** | **55** |

Not caught (37):

- 36 label tokens. These are masked by design (the ALLOW patterns in the checker's
  docstring): a label is not a value derived from the code, so changing "Table II" to
  "Table III", "indicator 4" to "indicator 5" or "2023" to "2024" is not detected. Cross-
  references and years need reading, or a separate label check.
- 1 value: the Results sentence "0.82–0.93" changed to "0.83–0.93". The abstract still
  carries the correct "0.82–0.93", so the required string is present, and 0.83 is itself
  a catalogue value of the same form (elsewhere in the study), so the changed number is
  masked rather than unaccounted.

Known limits of the check:

1. **Masking is by value, not by label.** Any number equal to some catalogue value is
   accepted wherever it occurs. A swap to another catalogue value of the same form passes
   (for example "n = 19" changed to "n = 34" in the Results prose, where 34 is a catalogue
   count and the Abstract still carries "n = 19"; confirmed on the scratch copy: exit 0,
   no problem reported). The REQUIRED strings give coverage only where the label's own
   string is missing from the whole text.
2. **Numbers written as words** ("two indicators", "nine indicators", "four questions",
   "one in five") are not checked.
3. Table rows are checked by the separate rendering test (`tables.md` equals a fresh
   rendering of `outputs/`), not by the prose scan.

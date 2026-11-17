# India's State TB Score: reproducibility, robustness and validity

India's Central TB Division (CTD) rates every state and union territory with a
**State TB Score**: nine programme indicators with fixed maximum points summing
to 100. Improvement in the score is now a key deliverable in each state's
programme implementation plan under the National TB Elimination Programme, so
funding follows it.

This repository holds a test of that score:

- **Q1. Reproducibility.** Can the published 2023 State TB Scores (India TB
  Report 2024, Table 11.2) be reproduced from the indicator values the same
  report publishes, using CTD's published definition?
- **Q2. Robustness.** How much does the ranking move under defensible
  alternative weights, indicator sets and denominators?
- **Q3. Validity.** Do higher-scoring states have lower TB prevalence in the
  ICMR National TB Prevalence Survey 2019–21?
- **Q4. Change over time.** Is a state's year-on-year change in score larger
  than the change expected from indicator noise alone?

## Pre-registration

The analysis plan, [`docs/analysis_plan.md`](docs/analysis_plan.md), is dated
17 November 2026 and was committed and pushed to this public repository
**before any indicator value was extracted and before any computation**. The
commit history and GitHub's timestamps are the record of that order. Any
change to the plan after registration is logged, with its date, in the plan's
Deviations section; any analysis not in the plan is labelled exploratory.

The approved study design is in
[`docs/superpowers/specs/2026-11-17-state-tb-score-design.md`](docs/superpowers/specs/2026-11-17-state-tb-score-design.md)
and the implementation plan in
[`docs/superpowers/plans/2026-11-17-state-tb-score.md`](docs/superpowers/plans/2026-11-17-state-tb-score.md).

## Data

All inputs are published, aggregate, state-level government data: editions of
the *India TB Report* (CTD, Ministry of Health and Family Welfare) and the
report of the ICMR National TB Prevalence Survey 2019–21. The source PDFs are
not redistributed here. A fetch script will download them from their official
URLs and verify each against the SHA-256 digest recorded in the plan.

## Reproducing the analysis

Python 3.11 or later. Analysis code uses the standard library only;
`pdfplumber` is needed for the extraction scripts and `pytest` for the tests.
The committed outputs were produced with the versions pinned in
[`ENVIRONMENT.md`](ENVIRONMENT.md). Run everything from the repository root.

```
# 1. Fetch the source PDFs into data_raw/ and verify their SHA-256 digests
python -I tools/fetch_sources.py

# 2. Extract the tables (rewrites data/extracted/ and data/source_choices.csv)
python -I src/extract/itr2024.py
python -I src/extract/itr2023.py
python -I src/extract/ntps.py
python -I src/extract/itr2021.py      # reports BLOCKED: that edition is a scan

# 3. Run the analyses (rewrites outputs/)
python -I src/q1_reproduce.py 2023
python -I src/q2_robust.py 2023
python -I src/q3_validity.py 2023
python -I src/q4_change.py

# 4. Verify: tests, analyses, extraction totals, plan order, deviations log,
#    and byte-for-byte reproduction of the committed outputs
python -I verification/check_all.py
```

`check_all.py` prints `N/N checks passed` and exits non-zero on any failure.
The extraction-totals check is reported as skipped when the source PDFs are
not present. `verification/MUTATIONS.md` records one deliberate break per check
and the failure each produced.

### Files

Inputs and extracted data:

- `data/source_manifest.csv`: URL, size and SHA-256 digest of each source PDF.
- `data/extracted/*.csv`: indicator values, populations, outcomes, printed
  scores and prevalence estimates extracted from the PDFs, with source file,
  PDF page and table for every value.
- `data/extracted/definitions.csv`: each edition's indicator definitions, as printed.
- `data/source_choices.csv`: for each value, which table was used and why.

Outputs (`outputs/`):

- `q1_2023.csv`: reconstructed 2023 scores under each scoring rule, against the published scores.
- `q1_2023_selection.json`: which scoring rules fit the published scores, and the rules carried into Q2 to Q4.
- `q1_target_check.txt`: the plan 5.3 check of the notification target against annexure 1.2.
- `q2_2023_summary.csv`: rank agreement with the base score under each alternative weighting, indicator set and denominator.
- `q2_2023_fifths.csv`: share of states that move between fifths under each alternative.
- `q2_2023_saturation.csv`: for each indicator, the share of states at 95% or more of target.
- `q3_2023_summary.csv`: rank correlations of score with NTPS prevalence and with the secondary measures.
- `q3_2023_units.csv`: score and prevalence for each NTPS reporting unit.
- `q3_2023_secondary_states.csv`: state-level score and treatment success for the secondary analysis.
- `q4_2022_2023_states.csv`: each state's change in score between score years 2022 and 2023, with its noise threshold.
- `q4_2022_2023_summary.csv`: number of states whose change exceeds the threshold, and the rank correlation of change with the 2022 score.

Code: `src/score.py` (indicator achievement and scoring rules), `src/states.py`
(canonical state and union territory names), `src/extract/` (table extractors),
`src/q1_reproduce.py` to `src/q4_change.py` (analyses), `tools/fetch_sources.py`
(download and verification), `tests/` (unit tests), `verification/` (checks).

## Licence

Code: MIT (see [`LICENSE`](LICENSE)). The government source documents remain
the property of their publishers and are not covered by this licence.

## Author

Siddalingaiah H S, MD, Professor, Department of Community Medicine, Shridevi
Institute of Medical Sciences and Research Hospital, Tumkur, Karnataka, India.
ORCID [0000-0002-4771-8285](https://orcid.org/0000-0002-4771-8285).

Citation metadata: [`CITATION.cff`](CITATION.cff).

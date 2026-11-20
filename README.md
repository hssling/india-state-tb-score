# India's State TB Score: reproducibility, robustness and validity

**Archived release:** v1.0.0, doi:[10.5281/zenodo.24323627](https://doi.org/10.5281/zenodo.24323627) (concept DOI, always the latest version: [10.5281/zenodo.24323626](https://doi.org/10.5281/zenodo.24323626)).

India's Central TB Division (CTD) rates every state and union territory with a
**State TB Score**: nine programme indicators with fixed maximum points summing
to 100. From the 2024 cycle, the score's annual improvement is a key deliverable
in each state's programme implementation plan under the National TB Elimination
Programme.

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
not redistributed here. A fetch script downloads them from their official URLs
and verifies each against the SHA-256 digest recorded in the plan.

## Post hoc analyses (after peer review)

Four analyses were added on 20 November 2026, after two referees reviewed the
manuscript, and are logged as a dated entry in section 13 of the plan. They are **post
hoc**: not pre-specified, labelled "post hoc" in code and output, reported beside the
registered results and never in place of them. They use their own seed (20261120), and
are run under the registered primary rule R2 with R1 beside it.

1. **Q4 against overdispersed noise.** Each state's 2022 to 2023 change is compared with
   the inverse-variance-weighted mean change, with funnel limits widened by multiplicative
   (Spiegelhalter 2005) and additive (DerSimonian–Laird) overdispersion, and with
   Wilson-interval standard errors for proportions of 0 or 1 as a sensitivity analysis.
   This asks whether a change is unusual relative to other states; the registered test
   asks whether it differs from zero beyond sampling noise.
2. **Q4 multiplicity.** The registered count with Bonferroni and Benjamini–Hochberg
   adjustment, and the expected number of false positives.
3. **Q4 regression to the mean.** Oldham's method (change against the two-year mean),
   with a bootstrap interval.
4. **Q3 uncertainty in prevalence.** Survey prevalence drawn from a lognormal fitted to
   each unit's published 95% CI, with the units resampled.

`verification/check_posthoc_outputs.py` recomputes their point values with independent
code; the bootstrap intervals are reproduced by the seeded build.

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
python -I src/explore_udst.py        # exploratory, logged in plan section 13
python -I src/posthoc.py             # post hoc (after peer review), plan section 13

# 4. Exhibits: tables and figures of the manuscript (written to manuscript/,
#    which is kept private and not in this repository; needs matplotlib)
python -I exhibits/make_tables.py
python -I exhibits/make_figures.py
#    (--profile jph renders the Journal of Public Health set into manuscript/jph_v2/:
#    Arabic table numbering, the post hoc tables, figures at an 84 mm column width)

# 5. Verify: tests, analyses, extraction totals, plan order, deviations log,
#    the post hoc point values, and byte-for-byte reproduction of the committed outputs
python -I verification/check_all.py
```

`check_all.py` prints `N/N checks passed` (with the number of skipped checks)
and exits non-zero on any failure; "all passed" can include skips. The
extraction-totals check is skipped when the source PDFs are not present, and
the manuscript checks are skipped when `manuscript/` is absent (it is not in
this repository).

**Full verification needs a git clone** (`git clone
https://github.com/hssling/india-state-tb-score`). The order of registration
and analysis and the byte-for-byte reproduction of the committed outputs are
checked against the git history; in a copy without `.git`, such as a release
archive, those two checks print `SKIPPED: not a git checkout` and are counted
as skipped. `verification/MUTATIONS.md` records one deliberate break per check
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
- `exploratory_udst_scaling_2023.csv`: **exploratory, not pre-specified** (plan
  section 13): the Q1 band test repeated with each state's indicator 3
  achievement scaled to CTD's national figure.
- `posthoc_q4_states.csv`: **post hoc, after peer review** (plan section 13, 20
  November 2026): for each state under R2 and R1, and with binomial or Wilson standard
  errors, the 2022 to 2023 change, its z-score, the registered verdict, the Bonferroni and
  Benjamini–Hochberg verdicts and the overdispersed funnel flags.
- `posthoc_summary.csv`: **post hoc**: overdispersion factor, between-state variance and
  counts outside the funnel limits; multiplicity counts; Oldham's correlation with its
  bootstrap interval; and the Q3 correlation with prevalence uncertainty propagated.

Code: `src/score.py` (indicator achievement and scoring rules), `src/states.py`
(canonical state and union territory names), `src/extract/` (table extractors),
`src/q1_reproduce.py` to `src/q4_change.py` (analyses), `src/explore_udst.py`
(the exploratory analysis), `src/posthoc.py` (the post hoc analyses), `exhibits/` (the scripts that render the
manuscript's tables and figures from `outputs/` and `data/`),
`tools/fetch_sources.py` (download and verification), `tests/` (unit tests),
`verification/` (checks). The analyses need the standard library only;
pdfplumber is imported only by `src/extract/`.

## Licence

- **Code** (`src/`, `exhibits/`, `tools/`, `tests/`, `verification/`): MIT (see
  [`LICENSE`](LICENSE)).
- **Derived data** (`data/extracted/`, `data/source_choices.csv` and
  `outputs/`): Creative Commons Attribution 4.0 International (CC BY 4.0; see
  [`LICENSE-DATA`](LICENSE-DATA)). The underlying figures come from Government
  of India publications (India TB Reports, Central TB Division, Ministry of
  Health and Family Welfare; report of the ICMR National TB Prevalence Survey
  2019–21).

The government source documents themselves remain the property of their
publishers, are not redistributed here and are not covered by either licence.

## Author

Siddalingaiah H S, MD, Professor, Department of Community Medicine, Shridevi
Institute of Medical Sciences and Research Hospital, Tumkur, Karnataka, India.
ORCID [0000-0002-4771-8285](https://orcid.org/0000-0002-4771-8285).

Citation metadata: [`CITATION.cff`](CITATION.cff).

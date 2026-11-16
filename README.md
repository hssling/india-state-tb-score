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

To follow. The code (Python, standard library for all analysis; pdfplumber for
table extraction only) and the commands to reproduce every table and figure
will be added after the plan.

## Licence

Code: MIT (see [`LICENSE`](LICENSE)). The government source documents remain
the property of their publishers and are not covered by this licence.

## Author

Siddalingaiah H S, MD, Professor, Department of Community Medicine, Shridevi
Institute of Medical Sciences and Research Hospital, Tumkur, Karnataka, India.
ORCID [0000-0002-4771-8285](https://orcid.org/0000-0002-4771-8285).

Citation metadata: [`CITATION.cff`](CITATION.cff).

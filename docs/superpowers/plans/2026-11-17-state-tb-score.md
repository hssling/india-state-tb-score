# State TB Score Study Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Test whether India's State TB Score can be reproduced from published data (Q1), whether its ranking is robust (Q2), whether it tracks TB prevalence (Q3), and whether year-on-year changes in it exceed noise (Q4). Deliver this as a reproducible public repository and an IJMR manuscript.

**Architecture:**
- **Pipeline:** report PDFs (git-ignored, fetched and verified by SHA-256) → extracted state-level CSVs, each value keyed to its source page and checked against a total the report prints → indicator achievements → scores under rules R1–R4 → Q1–Q4 analyses → tables and figures rendered by code → manuscript numbers checked against the code.
- **Pre-registration:** the dated analysis plan is pushed to a public GitHub repo before any extraction of indicator values or any computation.

**Tech Stack:**
- Python 3.11.
- pdfplumber, for extraction only.
- The standard library for all analysis, including `random` (seeded) and `statistics`.
- pytest.
- pandoc and Word COM for the docx build.

**Spec:** `docs/superpowers/specs/2026-11-17-state-tb-score-design.md`. Read §8, "Decisions after the builder check", before any task.

## Global Constraints

**Running code and data**
- Every script runs as `python -I <script>`. The analysis imports nothing outside the standard library; pdfplumber is imported only under `src/extract/`.
- `data_raw/` is git-ignored. No PDF from CTD or ICMR is ever committed. `tools/fetch_sources.py` downloads each file and verifies it against `data/source_manifest.csv`.
- Extracted CSVs go in `data/extracted/`, which is committed. Every row carries `source_file`, `pdf_page` and `table_id`.
- Canonical state names come from one map, `src/states.py`. Any name not in the map raises an error and is never dropped silently.

**Numbers and checks**
- No number is typed into the manuscript. Every number is checked against the code by `verification/check_manuscript_numbers.py`, and that check is mutation-tested.
- Confirmatory rules are R1–R4 only. Anything added later is labelled `exploratory` in code and output, and logged with a date in `docs/analysis_plan.md` §Deviations.

**Repository and manuscript**
- `manuscript/` is git-ignored. Repository: `hssling/india-state-tb-score` (public); code licence MIT; author Siddalingaiah H S, ORCID 0000-0002-4771-8285.
- Paper language must not narrate its drafting history.

**Fixed values**
- Indicator points: 20, 10, 10, 15, 10, 15, 10, 5, 5, for indicators 1–9 in the ntep.in/node/1662 order.
- UDST denominator: the state benchmark is 70% of net notified patients.
- Reproduction tolerance: ±0.01 per state.
- Dirichlet: c = 63 (primary), and alpha_i = 1 for every i (extreme bound). 10,000 draws, seed 20261117.

## Review Focus

1. **State names differ across tables and editions.** Examples: "Jammu & Kashmir" against "Jammu and Kashmir"; Dadra and Nagar Haveli and Daman and Diu merged in 2020; Ladakh separated in 2019. Every join must match all 36 units or fail with the unmatched names. → Task 3 test `test_canonical_rejects_unknown` and `test_join_requires_all_units`.
2. **Rotated landscape tables extract with reversed text, and long state names wrap across lines.** Extraction must give exactly the report's unit count, and the national row must equal the column sums. → Task 3 test `test_rotated_page_rows`; Task 4 national-total check on every table.
3. **Indian digit grouping and combined cells.** Figures such as "1,23,456" and cells such as "62795 (99%)" must parse to integers and to the stated percentage, with the percentage checked against numerator over denominator. → Task 3 test `test_parse_cells`.
4. **Zero or absent denominators in small UTs** (for example, Lakshadweep with no MDR/RR-TB patients). Achievement is `None`, never 0 or 100. The state's score under each rule is reported as not computable on that indicator, and Q1 lists it. → Task 5 test `test_zero_denominator_is_none`.
5. **Achievement above 100%** (UDST against the 70% benchmark, notification above target). It must reach the rules uncapped, so that R1 and R2 can differ. → Task 5 test `test_achievement_not_capped_before_rules`.

---

### Task 1: Repository, design and pre-registered analysis plan, pushed public

**Files:**
- Create: `README.md`, `LICENSE` (MIT), `.gitignore`, `CITATION.cff`, `docs/analysis_plan.md`
- Keep: `docs/superpowers/specs/2026-11-17-state-tb-score-design.md`, this plan

**`.gitignore`:** `data_raw/`, `manuscript/`, `outputs/scratch/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `**/~$*`, `**/*_signed.*`.

**`docs/analysis_plan.md` must pin, as numbered sections:**
- **Questions:** Q1–Q4 as in design §2.
- **Data seen before this plan:** the 2024 edition's Table 11.2 (published 2023 scores) and the annexure lists; the existence and SHA-256 of the five files. No indicator value has been extracted.
- **Indicator definitions:** the nine numerators, denominators and points from ntep.in/node/1662, each mapped to the annexure table it will come from in each edition. Where the source is not yet known, mark it "to be located"; the rules for locating it are fixed here, and the search for indicator 7 is limited to official public NHM/PIP documents.
- **Rules:**
  - R1: points = pts × min(a, 1).
  - R2: points = pts × a.
  - R3: points = pts × a / max over states of a.
  - R4: threshold bands, used only if a CTD document states the bands.

  Achievement a is a proportion, and a > 1 is allowed.
- **Rule selection:** design §8 calls 1–3, verbatim in substance, including admissibility (0 ≤ residual ≤ missing points) and the "cannot discriminate" outcome.
- **Q2:**
  - The variants of design §6.3.
  - Saturated indicator: at least 80% of computable states have a ≥ 0.95.
  - Rank measures: median and maximum absolute rank change; the share of draws in which each state stays in the top or bottom fifth (7 units each); Spearman rank agreement with the published ranking.
- **Q3:**
  - Primary: Spearman ρ between the score and ICMR prevalence over the survey's reporting units, with the score population-weighted to those units. Interval: Fisher-z 95% CI, with the n stated.
  - Secondary: DR-TB treatment success, and the score year 2020.
  - No P values.
- **Q4:** for each state and indicator, the binomial standard error √(a(1−a)/n) of each achievement, propagated to the score as √Σ (pts_i² × se_i²). A change counts as exceeding noise if |Δscore| > 1.96 × √(se_t² + se_{t−1}²). Report the share of states whose published change exceeds noise.
- **§Deviations:** empty, dated.

- [ ] **Step 1:** Run `git init` in `tb_state_score/`. Write the files above. `README.md` states the purpose, says that the plan predates any computation, and gives the reproduce commands as "to follow".
- [ ] **Step 2:** Run `git add -A && git status`. Expected: no file under `data_raw/` and none under `manuscript/` is staged.
- [ ] **Step 3:** Commit `docs: pre-registered analysis plan for the State TB Score study, before any extraction or computation`.
- [ ] **Step 4:** Run `gh repo create hssling/india-state-tb-score --public --source . --push`. Expected: the remote URL is printed, and `gh api repos/hssling/india-state-tb-score/commits` shows the commit with its timestamp. Record the commit SHA and the UTC time in `docs/analysis_plan.md` §Deviations as the registration point; this is the second commit.

### Task 2: Source manifest and fetch script

**Files:**
- Create: `data/source_manifest.csv` with the columns `file,url,bytes,sha256,retrieved_utc`, one row for each of the five PDFs, using the digests recorded on 16–17 Nov 2026.
- Create: `tools/fetch_sources.py`, `tests/test_fetch.py`

**Interfaces:**
- Produces: `fetch_sources.verify(path: Path, sha256: str) -> None`, which raises `ValueError` on a mismatch; `fetch_sources.main() -> int`, which downloads only missing files, verifies every file and returns 0.

- [ ] **Step 1:** Write the tests:
  - `test_verify_accepts_matching_digest`
  - `test_verify_rejects_tampered_file` (write bytes to a temporary file and flip one byte).
- [ ] **Step 2:** Run `python -I -m pytest tests/test_fetch.py -v`. Expected: FAIL, because the module does not exist yet.
- [ ] **Step 3:** Implement with `urllib.request` and `hashlib`.
- [ ] **Step 4:** Run the tests, then `python -I tools/fetch_sources.py`. Expected: PASS; "5 files verified".
- [ ] **Step 5:** Commit.

### Task 3: Extraction primitives

**Files:**
- Create: `src/states.py`, `src/extract/pdftext.py`, `src/extract/cells.py`, `tests/test_extract_primitives.py`

**Interfaces:**
- Produces:
  - `states.canonical(name: str) -> str`: 36 canonical names, following the order of the 2024 Table 11.2.
  - `states.ALL: tuple[str, ...]`.
  - `states.require_all(names: Iterable[str], year: int) -> None`: the units valid in year `year`; Ladakh exists from score year 2020.
  - `pdftext.page_lines(pdf_path: Path, page: int) -> list[str]`: rotation-aware. When the upright text is mostly reversed words, re-extract with the page rotated.
  - `cells.parse_int(s: str) -> int`, which handles Indian grouping; `cells.parse_n_pct(s: str) -> tuple[int, float]`.
- [ ] **Step 1:** Write the tests:
  - `test_canonical_rejects_unknown`: `canonical("Atlantis")` raises `KeyError`.
  - `test_join_requires_all_units`: `require_all` without "Ladakh" for 2023 raises `ValueError` naming Ladakh.
  - `test_parse_cells`: `parse_int("1,23,456") == 123456`; `parse_n_pct("62795 (99%)") == (62795, 99.0)`.
  - `test_rotated_page_rows`: `page_lines` on `ITR2024.pdf` page 282 (annexure 7.2) returns lines containing "Uttar Pradesh" read forwards. Skip the test when `data_raw/` is absent.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** Commit.

### Task 4: Extract the 2024 edition (score year 2023)

**Files:**
- Create: `src/extract/itr2024.py`, `tests/test_itr2024.py`
- Create: `data/extracted/itr2024_scores.csv` (Table 11.2), `data/extracted/itr2024_indicators.csv`

**Interfaces:**
- Consumes: Task 3.
- Produces:
  - `itr2024_indicators.csv`, in long form, with the columns `score_year,state,indicator,numerator,denominator,source_file,pdf_page,table_id`, where `indicator` is in 1..9.
  - `itr2024_drtb_outcomes.csv`: MDR/RR-TB treatment success by state, from annexure 4.13. It is Q3's secondary measure.

**Rules:**
- Missing indicators get no rows. The run prints which ones are missing and why (for example, "7: no state-wise table located").
- Indicator 7 is located from official NHM/PIP sources only (spec §8 call 4). Any download needs the author's permission first, so pause and ask.
- [ ] **Step 1:** Write the tests:
  - `test_scores_36_units`: 36 rows; Odisha 93.45; Manipur 71.61.
  - `test_each_table_matches_printed_total`: for every extracted table, the sum of the state numerators equals the printed India row, and likewise for the denominators.
  - `test_expected_equals_target`: report whether the annexure 1.2 national "expected" total equals 2,761,682 (Table 11.1). This settles spec §8 call 6, and the result is written to `outputs/q1_target_check.txt`.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement one extractor function per annexure. Page numbers are taken from the 2024 annexure list, with the offset that the PDF page is the printed page + 30.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** Commit, with the extracted CSVs.

### Task 5: Indicators and scoring rules

**Files:**
- Create: `src/score.py`, `tests/test_score.py`

**Interfaces:**
- Consumes: `data/extracted/itr{edition}_indicators.csv`.
- Produces:
  - `achievement(rows) -> dict[str, dict[int, float | None]]`: state → indicator → achievement.
  - `RULES = {"R1", "R2", "R3"}`, plus "R4" only when the bands are documented.
  - `score(ach, rule: str, indicators: Iterable[int] = range(1, 10), rescale: bool = False) -> dict[str, float | None]`.
  - `POINTS: dict[int, int]`.
- [ ] **Step 1:** Write the tests:
  - `test_zero_denominator_is_none`.
  - `test_achievement_not_capped_before_rules`: 840 / (0.7 × 1000) gives 1.2.
  - `test_r1_caps_r2_does_not`: on that input, R1 gives 10.0 and R2 gives 12.0.
  - `test_r3_relative_to_best`.
  - `test_rescale_partial_to_100`: with indicators 1–6 and 8–9 only, a perfect state scores 100.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement. The UDST denominator is 0.7 × the net notified patients.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** Commit.

### Task 6: Q1 reconstruction and rule selection

**Files:**
- Create: `src/q1_reproduce.py`, `tests/test_q1.py`, `outputs/q1_*.csv`

**Interfaces:**
- Produces: `select_rule(published: dict, partial_by_rule: dict, missing_points: int) -> dict`, with the keys `admissible: list[str]`, `chosen: str | None`, `per_state: dict` (residual and match flag) and `verdict: str`. The verdict is one of `reproduced`, `partially reproduced`, `cannot discriminate` or `not reproducible`.
- [ ] **Step 1:** Write the tests, with synthetic inputs:
  - `test_exact_match_reproduced`;
  - `test_residual_outside_missing_points_inadmissible`;
  - `test_two_admissible_rules_cannot_discriminate`;
  - `test_tie_break_max_abs_error_then_mismatch_count`.
- [ ] **Step 2:** Run the tests. Expected: FAIL. Implement, run again, PASS.
- [ ] **Step 3:** Run `python -I src/q1_reproduce.py 2023`. Expected: it writes `outputs/q1_2023.csv` and prints the verdict. Do not interpret the result in prose yet.
- [ ] **Step 4:** Commit.

### Task 7: Q2 robustness

**Files:**
- Create: `src/q2_robust.py`, `tests/test_q2.py`

**Interfaces:**
- Consumes: `score.achievement`, `score.score`, and Q1's chosen or admissible rules.
- Produces:
  - `dirichlet_weights(c: float | None, n: int, seed: int) -> list[dict[int, float]]`: `random.gammavariate`; points sum to 100; `c=None` means alpha_i = 1 for every i.
  - `rank_shift(base: dict, alt: dict) -> dict`.
  - `saturated(ach) -> list[int]`.
- [ ] **Step 1:** Write the tests:
  - `test_weights_sum_to_100`;
  - `test_weight_cv_matches_formula`: at c = 63, over 10,000 draws, the coefficient of variation of the 20-point weight is 0.25 ± 0.01;
  - `test_seeded_reproducible`;
  - `test_saturated_threshold`: exactly 80% of states with a ≥ 0.95 counts as saturated.
- [ ] **Step 2:** Run the tests. Expected: FAIL. Implement, run again, PASS.
- [ ] **Step 3:** Run the variants of spec §6.3. The burden-denominator variant runs only if Task 4 found that "expected" differs from the target, or if an independent estimate exists; otherwise the output says that it was dropped.
- [ ] **Step 4:** Commit.

### Task 8: Earlier editions and the ICMR survey

**Files:**
- Create: `src/extract/itr2023.py`, `src/extract/itr2021.py`, `src/extract/ntps.py`, their tests, and the corresponding CSVs in `data/extracted/`.

**Rules:**
- Each extractor records the score definition its edition states, in `data/extracted/definitions.csv`, and whether the edition prints state scores.
- `ntps.py` writes the survey's reporting units, the states they contain, the prevalence and its 95% CI, and the source page.
- [ ] **Step 1:** Write the tests:
  - the printed-total checks, as in Task 4;
  - `test_ntps_units_cover_states`: every state maps to exactly one survey unit, or is listed as not covered.
- [ ] **Step 2:** Run the tests. Expected: FAIL. Implement, run again, PASS.
- [ ] **Step 3:** Commit.

### Task 9: Q3 validity and Q4 change

**Files:**
- Create: `src/q3_validity.py`, `src/q4_change.py`, their tests.

**Interfaces:**
- Produces:
  - `spearman_ci(x: list[float], y: list[float]) -> tuple[float, float, float, int]`: ρ, the lower and upper Fisher-z 95% bounds, and n.
  - `score_se(ach, n, rule) -> dict[str, float]`.
  - `exceeds_noise(s_t, s_prev, se_t, se_prev) -> bool`.
- [ ] **Step 1:** Write the tests:
  - `test_spearman_known_values` (ties handled by average ranks);
  - `test_fisher_ci_small_n_returns_none`: n ≤ 3 gives no interval;
  - `test_score_se_formula`;
  - `test_exceeds_noise_boundary`.
- [ ] **Step 2:** Run the tests. Expected: FAIL. Implement, run again, PASS.
- [ ] **Step 3:** Run both on the extracted years. Q4 runs on published scores and on re-scored years under one definition (spec §8 call 7).
- [ ] **Step 4:** Commit.

### Task 10: Verification suite, and release of the code

**Files:**
- Create: `verification/check_all.py`, which runs pytest, then every `src/q*.py`, then each check below, and prints "N/N checks passed".
- Create: `verification/check_extraction_totals.py`, `verification/check_plan_order.py`.
  - `check_plan_order.py` asserts that the commit adding `docs/analysis_plan.md` precedes every commit touching `src/` or `data/extracted/`.
- Create: `verification/check_deviations.py`, which requires every `exploratory` label in `outputs/` to appear in §Deviations.
- [ ] **Step 1:** Write the checks.
- [ ] **Step 2:** For each check, make one deliberate break and confirm the check fails: edit one extracted value, reorder history in a scratch clone, and add an unlogged exploratory label. Record the results in `verification/MUTATIONS.md`.
- [ ] **Step 3:** Commit. Ask the author before pushing and before creating the GitHub release and Zenodo DOI v1.0.0.

### Task 11: Manuscript for IJMR

**Files:**
- Create (git-ignored): `manuscript/manuscript.md`, `manuscript/make_tables.py`, `manuscript/build.py`, `verification/check_manuscript_numbers.py` (committed).

- [ ] **Step 1:** Read IJMR's own author guidelines. Confirm that there is no mandatory APC; if there is one, stop and tell the author. Record the word limits, the abstract structure, the reference style and the reporting guideline in `manuscript/journal_rules.md`.
- [ ] **Step 2:** Have `make_tables.py` render every table from `outputs/`. Write the prose with numbers taken only from the code.
- [ ] **Step 3:** In `check_manuscript_numbers.py`, derive every number in the text from the code. Mutation-test it: change each number in a copy, and every change must be caught.
- [ ] **Step 4:** Build the docx with pandoc, render it through Word COM, and check the reference numbering, figure placement, word count and abstract limit.
- [ ] **Step 5:** Commit the checks only. The manuscript stays local until a decision.

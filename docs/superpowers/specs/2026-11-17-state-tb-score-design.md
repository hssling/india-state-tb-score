# Design: does India's State TB Score measure what it is used to reward?

Date: 17 November 2026. Author of the study: Siddalingaiah H S (single author).
Status: design, awaiting the author's approval. Nothing has been computed.

## 1. Intent

The author wants work that the National TB Elimination Programme (NTEP) and its Central TB Division (CTD) can act on. It should guide policy, practice or operations, and be novel.

CTD rates every state and union territory (UT) with a **State TB Score**: nine programme indicators with fixed maximum points summing to 100 (definition: ntep.in/node/1662). The score is no longer just a league table:
- **Awards:** the best-scoring states were given awards in 2019 (India TB Report 2020, p. 60).
- **Funding plans:** from the 2024 cycle, "% improvement in Annual TB Score" is a key deliverable in each state's programme implementation plan (PIP), the plan that sets its NTEP funding (India TB Report 2024, Table 16.3).
- **Incentives and penalties:** separate "key conditionalities" attach a +5% to −5% incentive or penalty to the share of districts meeting notification and treatment-success targets (Table 16.4). Those are the same quantities that dominate the score.

Money now follows the score. Nobody has published a test of whether it can be reproduced from the data CTD publishes, whether its ranking is stable to defensible choices, or whether high scores go with less TB. This study does those three things, and turns the results into concrete advice: which indicators to keep, fix or drop, and how to state the score so that a change in it means a change in performance.

## 2. Questions (to be fixed in a dated analysis plan before any computing)

- **Q1. Reproducibility.** Can the published 2023 State TB Scores (India TB Report 2024, Table 11.2, 36 states/UTs) be reproduced from the indicator values the same report publishes in its annexures, using CTD's published definition?
- **Q2. Robustness.** How much does the ranking move under defensible alternatives?
  - **Weights:** perturb the weights around CTD's.
  - **Leave-one-out:** drop each indicator in turn.
  - **Notification denominator:** use estimated burden instead of CTD's target.
  - **Treatment success:** use the matched cohort (the patients notified in the previous year, whose outcomes the annexures report) instead of the same-period denominator in CTD's definition.
  - **Saturated indicators:** remove indicators on which nearly every state scores near the maximum.
- **Q3. Validity.** Do higher-scoring states have less TB, or better TB control by an independent measure? Independent measures:
  - state TB prevalence from the ICMR National TB Prevalence Survey 2019–21;
  - the ratio of notified to estimated patients;
  - treatment outcomes not in the score.
- **Q4. Change over time.** Using the 2022 and 2020 scores (2023 and 2021 editions), is a state's year-on-year change in score larger than the change expected from indicator noise alone? This tests the "% improvement" deliverable.

## 3. What is known now (recon, 16-17 Nov 2026)

- **Definition** (ntep.in): nine indicators with their numerators, denominators and maximum points (20, 10, 10, 15, 10, 15, 10, 5, 5). It does **not** say how an indicator percentage becomes points: proportional, capped at 100%, relative to the best state, or by thresholds. Q1 must establish this.
- **India TB Report 2024** (CTD; 316 pages; SHA-256 e37f9f40…): Table 11.2 prints 2023 scores to two decimals, with no per-indicator breakdown. The state-wise annexures include:
  - notification against expected patients (1.2);
  - HIV status known (2.1);
  - treatment outcomes of the 2022 cohort (3.1–3.3);
  - MDR/RR-TB treatment initiation (4.9);
  - child TB preventive treatment (7.2);
  - case finding in ART centres (2.5);
  - a Ni-kshay Poshan Yojana table (around PDF p. 309).

  Not yet located: state-wise spending against the approved Record of Proceedings (indicator 7), and the PLHIV preventive-therapy figure in the form indicator 9 needs. Landscape tables extract with reversed text and need rotation-aware extraction.
- **India TB Report 2020** (SHA-256 63b94080…): describes the score and the 2019 awards; no numeric state scores have been found yet.
- **Other editions:** CTD's site also lists the 2023 (51.7 MB) and 2021 (223.4 MB) editions. The 2019, 2022 and 2025 editions are not listed there.
- **Gap:** a novelty search found no published test of the State TB Score. The nearest work is on data quality of Ni-kshay case-finding records (Glob Health Action 2023; PLOS Glob Public Health) and one district certification survey (JFMPC). Q1–Q4 are new.

## 4. Goals, non-goals, anti-goals

**Goals**
- A reproducible reconstruction, a robustness analysis and a validity check of the 2023 score, extended to earlier years as far as the published data allow.
- Findings stated as programme actions: indicator by indicator, keep, fix (and how) or drop. Also, how the "% improvement" deliverable should be defined so that it tracks real change.
- Every number derived by code from the published tables, none typed. Prose and tables checked against the code, and the checks mutation-tested, as in the author's earlier papers.

**Non-goals**
- District-level analysis (the reports do not publish district indicators).
- Designing and validating a replacement index. The paper may state principles and show one illustrative variant, but it does not propose an official new score.
- Causal claims about why a state scores as it does.

**Anti-goals: things that would make the paper a failure even if every number is right**
- Naming and shaming states. Ranks are reported because the score produces them, but the unit of critique is the score, not the states.
- Implying data manipulation or "gaming". A high score that does not track lower TB is a measurement finding, not an accusation.
- Presenting robustness results as a verdict that the score is useless when they show only that some indicators carry no information.

## 5. Approaches considered

- **A (chosen by the author).** Do one year thoroughly, then extend. Q1–Q3 on the 2023 score with the data already in hand; then Q4 with the 2023 and 2021 editions.
  - *For:* the core paper does not depend on finding the missing editions.
  - *Against:* Q4 may cover only two or three time points.
- **B.** Multi-year from the start (all editions 2019–2025).
  - *For:* the strongest design for Q4.
  - *Against:* three editions are not on CTD's site, and the large files cost a lot of extraction work before any result exists.
- **C.** Test the published ranking only, without reconstruction.
  - *For:* quickest.
  - *Against:* cannot say whether the published scores are right, and that is the most actionable finding.

## 6. The design

### 6.1 Data

**Sources**
- **India TB Report editions.** 2024 (score year 2023) is in hand. 2023 (score year 2022) and 2021 (score year 2020) are to be downloaded with the author's permission. 2019, 2022 and 2025 are to be sought from other official mirrors.
- **ICMR National TB Prevalence Survey 2019–21** (tbcindia.mohfw.gov.in). It gives state or state-group prevalence; to be downloaded with the author's permission.
- **Population denominators.** From the report's own notification-rate columns, so that the score and its alternatives share one population.

**Handling**
- Each file is recorded with its URL, download date and SHA-256 in a manifest.
- The government PDFs are not redistributed in any public repository. A fetch script downloads them and verifies their digests, as in the author's WHO work.
- Extracted tables are written to CSV, with the source page recorded for every value. Every extracted table is checked against a total the report itself prints (national row, or a column sum), and extraction fails loudly on a mismatch.

### 6.2 Q1. Reconstruction

**Scoring rules to try**, pre-specified in the plan:
- **R1:** points = maximum points × min(achievement, 100%);
- **R2:** proportional without a cap;
- **R3:** relative to the best state;
- **R4:** threshold bands, only if a CTD document states them.

**Criterion.** A rule reproduces the score if it matches every published score within ±0.01 (two-decimal rounding). If it matches some states but not others, list the mismatches and look for a common cause (for example, a UT, a small denominator, or a missing indicator).

**If no rule reproduces the score**, that is the Q1 finding: it cannot be reproduced from published data. The paper then states what extra information would make it reproducible.

**Indicators with no published state-wise value (7, possibly 9).** Reconstruct the partial score from the indicators that are available. Report the implied residual: published score minus the partial reconstruction. Judge whether that residual stays within the dropped indicators' maximum points. Do not impute values.

### 6.3 Q2. Robustness

**Variants** of the reconstructed score:
- weight perturbation: weights drawn around CTD's (Dirichlet, seeded, standard library only), 10,000 draws;
- leave-one-indicator-out;
- notification against estimated burden instead of the target, where estimates exist;
- treatment success on the matched cohort;
- removal of saturated indicators.

**Measures of rank movement:**
- the median and maximum change in rank;
- how often each state stays in the top and bottom fifth;
- rank agreement with the published ranking (Spearman, as a technical measure).

**Saturated indicator** (definition to be fixed in the plan): between-state spread small enough that the points it gives are near-constant across states.

### 6.4 Q3. Validity

**Measures:**
- **Prevalence:** compare the score with ICMR state or state-group prevalence, aggregating the score to the survey's groups by population weight.
- **Notified versus expected:** compare the score with notified over expected patients.
- **Outcomes outside the score:** compare the score with outcomes it does not include, such as death and loss to follow-up.

**Reporting.** Associations are descriptive, with intervals, and no P values (the target journals discourage them). The sample is at most 36 units, and the paper says plainly what that limits.

### 6.5 Q4. Change over time

- **Change against noise:** compare each state's observed score change between available years with the change expected from binomial noise in each indicator. The expected change is computed from that indicator's own numerator and denominator.
- **What "% improvement" rewards:** report how much of the deliverable rewards states for regression from an unusually low year. Small-denominator UTs are expected to be the noisiest.

### 6.6 Products

**The project folder.** A new folder, `tb_state_score/`, laid out like the author's other projects:
- `docs/` holds the design and the dated analysis plan;
- `src/` holds the extraction and analysis code;
- `verification/` holds the checks;
- `manuscript/` is kept out of any public repository until a decision, like Papers C and D;
- `data_raw/` is git-ignored.

**Order of work:** the plan is committed before the first computation.

**The manuscript:** IMRD, with tables and figures rendered by code. RECORD is the reporting guideline (routinely collected data). Ethics approval is not required: published aggregate data only.

## 7. Constraints

- **Author and venue:** single author. The journal must be hybrid (subscription route) or APC-free; never a mandatory APC.
- **Downloads:** each needs the author's explicit permission, stating file, source and size.
- **No meta language:** no drafting-history language in any manuscript text; corrections are stated as findings.
- **Pre-registration:** the analysis plan is dated and committed before computing. Deviations are logged with dates.
- **Tools:** Python. pdfplumber (installed) for extraction only; the analysis uses the standard library, like the author's other projects.
- **Read-only material:** the author's other projects stay read-only (`tb_bopas_repo`, `manuscript_3_TB_BOPAS`, the OHB assets).

## 8. Decisions after the builder check (17 Nov 2026)

**Facts found since §3**
- **Scoring formula.** A published district study (Niwari, JFMPC 2025) applies a domain score of % achievement × weight ÷ 100, summed over the domains. This is R1 or R2; the open question is only whether achievement is capped at 100%.
- **UDST denominator.** CTD's UDST page sets the denominator as a state benchmark of 70% of notified patients, so achievement on that indicator can exceed 100%. Reconstruction can therefore tell a capped rule from an uncapped one.

**Calls made by the analyst** (listed for the author to check)

1. **Scoring rules.**
   - R1–R4 are the confirmatory set and are fixed in the plan.
   - Any rule added after seeing the data is labelled exploratory and logged as a dated deviation.
   - "Not reproducible" is claimed only against R1–R4. Exploratory fits are reported beside that claim.
   - The source of every rule (CTD page, JFMPC study, or inference) is stated.
2. **Choosing a rule.**
   - The rule with the smallest maximum absolute error across states is chosen, then the smallest number of mismatches.
   - If indicator 7 (and possibly 9) is unavailable, rules are compared on the residual: published score minus the partial score. A rule is admissible only if every residual lies within 0 and the missing indicators' maximum points.
   - If several rules are admissible, the paper says Q1 cannot discriminate between them. Q2–Q4 are then run under each admissible rule.
3. **The score Q2–Q4 use.**
   - If the full score is reproduced, Q2–Q4 use it.
   - Otherwise they use the partial score rescaled to 100 as the primary analysis, with the unrescaled partial score as a check.
   - Q2–Q4 run in either case: each concerns the indicators, not the published total.
4. **Indicator 7 (spending against the approved budget).**
   - Other official public sources are allowed, such as state PIP Records of Proceedings and NHM financial management reports, each download with the author's permission.
   - The search for them is time-boxed. If none is found, indicator 7 is treated as missing under call 2.
5. **Q3 validity measures.**
   - **Primary:** ICMR state or state-group prevalence (2019–21), an independent survey.
   - **Dropped:** notified ÷ expected patients, because it is indicator 1's own quantity and so circular.
   - **Dropped as validity measures:** death and loss to follow-up, because they are arithmetically tied to treatment success (indicator 4). They are kept only as descriptive context.
   - **Secondary:** DR-TB treatment outcomes (not in the score), and the score in the year closest to the survey (2020).
   - **Limitation:** the time gap between the survey and the 2023 score is stated as one.
6. **Notification target versus expected patients.**
   - Whether annexure 1.2's "expected" patients equal CTD's target is checked first: the national annexure total against Table 11.1's annual target of 2,761,682.
   - If they are the same quantity, the Q2 "estimated burden" variant uses an independent estimate (ICMR prevalence scaled to incidence is not attempted). Without such an estimate, the variant is dropped and the paper says so.
7. **Definition by year.**
   - The definition each edition states for its score year is recorded.
   - Q4 compares (a) the published scores and (b) all years re-scored under one definition, the current one.
   - If the indicators or weights changed, (b) is primary and the change is reported.
8. **Q4 in the same manuscript.**
   - Q4 is a section of the one paper, using score years 2020, 2022 and 2023, as far as each edition prints scores.
   - If an edition prints none, Q4 uses the years available, and the paper states the gaps.
   - The paper is not held for the missing editions (2019, 2022, 2025).
9. **Weight perturbation.**
   - Dirichlet with alpha_i = c × w_i around CTD's weights w_i. The coefficient of variation of weight i is √((1 − w_i) / (w_i (c + 1))).
   - c = 63 gives 25% for the 20-point indicator and about 55% for the 5-point ones. The exact value is fixed in the plan.
   - A second, deliberately wide setting (concentration = 9, i.e. one per indicator) is reported as an extreme bound.

**Decisions by the author** (17 Nov 2026)
- **Pre-registration.** A public GitHub repository is created now, holding only this design and the dated analysis plan. It is pushed before the first computation, and GitHub's timestamp is the evidence. Code joins it later. The manuscript stays out of it until a decision.
- **Downloads approved.**
  - India TB Report 2023 edition (51.7 MB) and 2021 edition (223.4 MB), for the 2022 and 2020 scores.
  - ICMR National TB Prevalence Survey 2019–21 report (14.6 MB), the primary validity measure.
- **Target journal.** *Indian Journal of Medical Research*. Its publication model (it must be hybrid or APC-free) and its format rules are confirmed from its own guidelines before any formatting.

## 9. Left to the builder

- The extraction method for rotated tables.
- The code layout within `src/`.
- Figure design.
- Exact names for the saturation threshold and the noise model, within the definitions above.
- The order of the extraction tasks.

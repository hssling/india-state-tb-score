# Pre-registered analysis plan: India's State TB Score — reproducibility, robustness and validity

**Date of this plan:** 17 November 2026
**Author:** Siddalingaiah H S, MD, Professor, Department of Community Medicine, Shridevi Institute of Medical Sciences and Research Hospital, Tumkur, Karnataka, India. ORCID 0000-0002-4771-8285. Single author.
**Repository:** https://github.com/hssling/india-state-tb-score
**Status:** registered before any indicator value was extracted and before any computation. The registration point (commit SHA and UTC time of the public push) is recorded in §13.
**Design:** `docs/superpowers/specs/2026-11-17-state-tb-score-design.md` (approved 17 November 2026). Where this plan and the design differ, this plan governs.

---

## 1. Background and scope

The Central TB Division (CTD) of India's National TB Elimination Programme (NTEP) rates each state and union territory (UT) with a State TB Score made of nine programme indicators whose maximum points sum to 100 (definition: ntep.in/node/1662). Improvement in the score is a key deliverable in each state's programme implementation plan from the 2024 cycle (India TB Report 2024, Table 16.3), and separate key conditionalities attach a +5% to −5% incentive or penalty to quantities that dominate the score (Table 16.4).

The unit of analysis is the state or UT (36 units in score year 2023). The study uses published aggregate data only. District-level analysis, the design of a replacement index, and causal explanation of any state's score are out of scope. Results are stated as properties of the score, not of the states.

## 2. Questions

- **Q1. Reproducibility.** Can the published 2023 State TB Scores (India TB Report 2024, Table 11.2, 36 states/UTs) be reproduced from the indicator values the same report publishes in its annexures, using CTD's published definition?
- **Q2. Robustness.** How much does the ranking move under defensible alternatives: perturbed weights around CTD's; leaving out each indicator in turn; notification against estimated burden instead of CTD's target; treatment success on the matched cohort instead of the denominator in CTD's definition; and removal of saturated indicators?
- **Q3. Validity.** Do higher-scoring states have less TB, measured independently by state or state-group TB prevalence in the ICMR National TB Prevalence Survey 2019–21?
- **Q4. Change over time.** Using the scores for score years 2020, 2022 and 2023 (India TB Report 2021, 2023 and 2024 editions), is a state's year-on-year change in score larger than the change expected from indicator noise alone?

## 3. Data sources

The following files were downloaded on 16–17 November 2026 to `data_raw/`, which is excluded from the repository. They are not redistributed; a fetch script will download them from the URLs below and verify each digest.

| File | Content | SHA-256 | URL |
|---|---|---|---|
| `data_raw/india_tb_report/ITR2024.pdf` | India TB Report 2024 (score year 2023) | `e37f9f406153b5e9a19726538c3f4d09dc4c470281c34fe511adaa56a0e22765` | https://tbcindia.mohfw.gov.in/wp-content/uploads/2024/10/TB-Report_for-Web_08_10-2024-1.pdf |
| `data_raw/india_tb_report/ITR2023.pdf` | India TB Report 2023 (score year 2022) | `0817ac3a1e7a03273438073d4e685f88aa93507ad115ec5c6588edfddc8f0b7b` | https://tbcindia.mohfw.gov.in/wp-content/uploads/2023/05/5646719104TB_AR_2023_04-04-2023_LRP_final.pdf |
| `data_raw/india_tb_report/ITR2021.pdf` | India TB Report 2021 (score year 2020) | `692267fd532e01289a23c7b6551245ac94a1e5d6894060d2612c4337e6c410c3` | https://tbcindia.mohfw.gov.in/wp-content/uploads/2023/05/4504484964TB-Annual-Report-2021-210321-High-Resolution.pdf |
| `data_raw/india_tb_report/ITR2020.pdf` | India TB Report 2020 (description of the score; 2019 awards) | `63b9408015dae510858e0eef2711e809d398bfe3149dd21c94390b258c007e7e` | https://tbcindia.mohfw.gov.in/wp-content/uploads/2023/05/India-TB-Report-2020.pdf |
| `data_raw/icmr_ntps/NTPS_2019_21_report.pdf` | ICMR National TB Prevalence Survey 2019–21, report | `884ffdd205d3b69569b06b3058ea77c490d44b1f2af6c3622f99282d60f04f83` | https://tbcindia.mohfw.gov.in/wp-content/uploads/2023/05/25032022161020NATBPSReport.pdf |

The 2019, 2022 and 2025 editions of the India TB Report are not listed on CTD's site. The analysis is not held for them; if any is obtained from an official source, its use is logged in §13.

**Population.** Wherever a population weight is needed, a state's population is derived from annexure 1.2 of the 2024 edition as notified patients ÷ notification rate per 100,000 × 10⁵, so that the score and its alternatives share one population.

## 4. Data seen before this plan

Before this plan was written, the following parts of the source files had been viewed. Nothing else had been read for numeric content.

- **India TB Report 2024:**
  - the list of tables and the list of annexures;
  - Table 11.1 (national achievement on key performance indicators, including the annual notification target of 2,761,682);
  - Table 11.2 (the published 2023 State TB Scores for 36 units, for example Odisha 93.45 and Manipur 71.61);
  - Tables 16.3 and 16.4 (State TB Score improvement as a key deliverable of the programme implementation plan; the ±5% key conditionalities);
  - the first lines of annexures 2.1 (HIV status known; state rows), 1.2, 4.9 and 7.2 (column headers only; the pages are rotated).
- **India TB Report 2020:** the description of the score (printed pages 59–60): nine indicators, three categories of state (UTs; states with population below 50 lakh; states with population above 50 lakh), and the 2019 awards.
- **All five files:** their existence and SHA-256 digests (§3).

No indicator value has been extracted or analysed beyond the glimpses listed above, and nothing has been computed.

Two facts from outside the source files inform the plan. A published district study (Niwari district; *J Family Med Prim Care* 2025) applies a domain score of percentage achievement × weight ÷ 100, summed over domains. CTD's universal drug-susceptibility testing (UDST) page sets the UDST denominator as a state benchmark of 70% of notified patients, so achievement on that indicator can exceed 100%.

## 5. Indicator definitions

### 5.1 The nine indicators

The definitions are those published by CTD at ntep.in/node/1662 (read on 16 November 2026), which cites the India TB Report 2021 and the NTEP Training Modules 5–9 (2020). Indicators are numbered 1–9 in the order of that page. Indicator names, numerators and denominators are given as published there; maximum points sum to 100.

| # | Points | Indicator | Numerator | Denominator | Source, 2024 edition (score year 2023): annexure, printed page (PDF page) |
|---|---|---|---|---|---|
| 1 | 20 | % of target TB notification achieved | Total TB patients notified during the defined period | Target TB patients estimated for the year | Annexure 1.2, p. 157 (PDF 187); denominator as decided by §5.3 |
| 2 | 10 | % of TB notified patients with known HIV status | Number of patients with HIV status known (HIV result positive or negative / reactive or non-reactive) | Net TB patients notified during the defined period | Annexure 2.1, p. 169 (PDF 199) |
| 3 | 10 | % of TB notified patients with UDST done | Number of patients with UDST done and rifampicin status known (sensitive or resistant) | State benchmark of net TB patients notified during the defined period (set by CTD's UDST page at 70% of notified: §5.2) | To be located (§5.4) |
| 4 | 15 | Treatment success rate | Number of TB patients with outcome successful (cured or treatment completed) | Net TB patients notified during the same period | Annexure 3.3 (2022 cohort, total), p. 192 (PDF 222), for the numerator and the matched-cohort denominator of §8.1 item 4; the same-period denominator from the edition's notification annexure (§5.4) |
| 5 | 10 | % of eligible beneficiaries paid under Nikshay Poshan Yojana | TB patients in whom payment has been done at least once | Total eligible TB patients during the same period | Ni-kshay Poshan Yojana state table, near PDF p. 309 (§5.5) |
| 6 | 15 | % of MDR/RR-TB patients initiated on treatment out of the total diagnosed | Number of MDR patients initiated on treatment during the defined period | Net MDR patients diagnosed during the defined period | Annexure 4.9, p. 235 (PDF 265) |
| 7 | 10 | % of expenditure amongst the approved Record of Proceedings (ROP) | Fund utilised in the defined period | ROP approved during the financial year | To be located (§5.4, item 5) |
| 8 | 5 | % of children given chemoprophylaxis from the total eligible children identified | Number of children < 6 years given isoniazid chemoprophylaxis | Number of children < 6 years eligible (total children identified minus children with active TB detected or treated) | Annexure 7.2 (TB preventive treatment among household contacts < 5 years), p. 252 (PDF 282); definitional mismatch (§5.5) |
| 9 | 5 | % of PLHIV given IPT from the total eligible PLHIV | Number of PLHIV given IPT | Number of PLHIV in whom active TB has been ruled out among those attending ART centres | To be located (§5.4); candidate: annexure 2.5, p. 173 (PDF 203) |

Other tables used: annexure 4.13 (MDR/RR-TB treatment outcomes, p. 243, PDF 273) for the Q3 secondary measure; Table 11.2 for the published 2023 scores; Table 11.1 for the national notification target.

In the 2024 edition, the PDF page number of an annexure page equals its printed page number plus 30.

### 5.2 Achievement

For each state s and indicator i, achievement is the proportion a_si = numerator_si / denominator_si, as defined in §5.1.

- a is a proportion, not a percentage, and is **not capped** before a scoring rule is applied: a > 1 is allowed (for example, notification above target, or UDST above the 70% benchmark).
- If the denominator is zero or not published for a state, a_si is **not computable**. It is never set to 0 or 1, and no value is imputed. The state's score under any rule that needs that indicator is reported as not computable, and the state is listed.
- A state row that is printed with a blank or zero denominator, or a blank numerator, falls under the previous item. A zero numerator over a positive denominator is an achievement of 0.
- The UDST denominator (indicator 3) is 0.7 × the state's net notified patients, the state benchmark set on CTD's UDST page.

### 5.3 Notification target

Before any reconstruction, the national total of "expected" patients in annexure 1.2 is compared with the annual notification target in Table 11.1 (2,761,682). The result is written to `outputs/q1_target_check.txt`.

- **Agreement:** "expected" is taken to be CTD's target if the two national totals agree within 0.1%, that is, if |national "expected" − 2,761,682| ≤ 0.001 × 2,761,682.
- **If they agree:** indicator 1 uses each state's annexure 1.2 "expected" as its denominator. The burden-denominator variant of Q2 (§8.1, item 3) is dropped, because no independent state-wise burden estimate is pre-specified, and the paper says so.
- **If they disagree:** indicator 1 is not computable, because the state targets are not published, and it is treated as missing under §5.4, item 4; the reconstruction is then partial (§7.2). The burden-denominator variant uses annexure 1.2 "expected" as the burden denominator.
- No other burden source is introduced, except as an exploratory analysis logged as a dated deviation (§13).

### 5.4 Rules for locating a source

For each indicator and each edition:

1. The source is the state-wise table in that edition whose numerator and denominator match the definition in §5.1, found from the edition's list of tables and list of annexures. Its table number and PDF page are recorded for every value extracted.
2. Every extracted table is checked against a total the report itself prints (the national row, or a column sum). A mismatch stops the extraction; it is not corrected silently.
3. A table that gives a percentage without its numerator and denominator is used for scoring, and the achievement is marked as having no count denominator for the noise model of Q4 (§10.2).
4. If no state-wise table covering every unit exists in the edition, the indicator is **missing** for that score year and the analysis proceeds under §7.2. No value is imputed and no other edition's value is substituted.
5. **Indicator 7.** The search outside the India TB Report is limited to official, public National Health Mission and programme implementation plan documents (state PIP Records of Proceedings and NHM financial management reports). Each download needs the author's prior permission. The search closes when extraction for score year 2023 is complete; if no source covering every unit has been found by then, indicator 7 is missing. A source found later is used only as a dated deviation (§13).
6. The 2023 and 2021 editions (score years 2022 and 2020) are mapped by the same rules; their annexure numbers are to be located. The definition each edition states for its score year (indicators, points, denominators) is recorded in `data/extracted/definitions.csv`, together with whether the edition prints state scores.
7. **Freeze point.** Before any score is computed, every source choice is recorded in a committed file, `data/source_choices.csv`, with one row per choice for each score year. It records: the table and column used for each numerator and denominator, including which "net notified" column feeds indicators 2, 3 and 4; the sources of indicators 3 and 9; the quantity used for indicator 5 (§5.5); the outcome of §5.3; and the outcome of the search for a CTD statement of R4 bands. Any change to a recorded choice after that commit is a dated deviation (§13).

### 5.5 Pre-specified definitional mismatches

- **Indicator 8.** The definition counts children under 6 years given isoniazid chemoprophylaxis. The 2024 edition's annexure 7.2 reports TB preventive treatment among household contacts under 5 years. Indicator 8 is computed from the published under-5 table and flagged as a definitional mismatch in every output that uses it.
- **Indicator 5.** The definition counts patients paid at least once; the 2024 edition's key performance indicator table uses "all benefits paid". Indicator 5 is computed from whichever quantity the state-wise table reports. If the table prints both, "paid at least once" is used, following the definition. The quantity used is recorded in `data/source_choices.csv` (§5.4, item 7).

## 6. Scoring rules

### 6.1 Confirmatory rules

For indicator i with maximum points pts_i and achievement a (a proportion, uncapped), the points awarded are:

- **R1 (proportional, capped):** points = pts_i × min(a, 1).
- **R2 (proportional, uncapped):** points = pts_i × a.
- **R3 (relative to the best state):** points = pts_i × a / max over states of a, where the maximum is taken over the states for which a is computable in that score year.
- **R4 (threshold bands):** points awarded by bands of achievement. R4 is used only if a CTD document states the bands; otherwise it is not tested, and the paper says so.

A state's score is the sum of its points over the indicators in the score.

**Source of each rule.** R1 and R2 follow the published district application (percentage achievement × weight ÷ 100; §4), which does not state whether achievement is capped; both are therefore tested. R3 is an inference: a common construction for composite indices. R4 is CTD's, if a CTD document states it.

R1–R4 are the confirmatory set. Any rule added after the data have been seen is labelled **exploratory** in code and output, and logged with its date in §13. "Not reproducible" is claimed only against R1–R4; exploratory fits are reported beside that claim.

### 6.2 Partial and rescaled scores

- **Partial score:** the sum of points over the indicators available for that score year.
- **Rescaled partial score:** 100 × partial score ÷ (sum of pts_i over the available indicators).
- When all nine indicators are available, the partial score and the rescaled partial score are both the full score.

## 7. Q1: reconstruction and rule selection

**Exclusions.** A state whose score is not computable under a rule (§5.2) is excluded from the comparison of rules in both §7.1 and §7.2 and is listed. "Every computable state" below means every state not so excluded.

### 7.1 Full reconstruction (all nine indicators available)

- **Match:** a state matches under a rule if |reconstructed − published| ≤ 0.01, where the reconstructed score is unrounded and the published score is as printed to two decimals.
- **Reported for each rule:** the number of matching states, the maximum absolute error, and the list of mismatching states with their errors. Mismatches are examined for a common cause (for example, a UT, a small denominator, or a definitional mismatch of §5.5).
- **Verdict:**
  - **reproduced:** a rule matches every computable state;
  - otherwise, **not reproducible** against R1–R4. The paper then states what further information would make the score reproducible.
- **Ranking of rules:** rules are ranked by the smallest maximum absolute error across computable states, with ties broken by the fewest mismatching states. This ranking selects the rule for Q2–Q4 (§7.3).

### 7.2 Partial reconstruction (indicator 7, and possibly 9 or 1, missing)

- For each rule, each state's residual is published score − partial score.
- **Admissibility band:** a rule is **admissible** only if every computable state's residual lies between 0 and the missing indicators' maximum points, with the tolerance of §7.1 at both bounds: −0.01 ≤ residual ≤ missing points + 0.01.
- **Assumption:** the band assumes that each missing indicator's achievement satisfies a ≤ 1, so that its points lie between 0 and its maximum. Under R1 and R3 this holds by construction. Under R2 it is an assumption: an expenditure ratio (indicator 7) above 1 would give points above the maximum, and the paper states this.
- **Violation:** for a state, the violation is the distance of its residual outside the band, max(0, −0.01 − residual, residual − (missing points + 0.01)); for a rule, it is the maximum violation over computable states.
- **Verdict:**
  - exactly one admissible rule Rk: **"consistent with rule Rk; not fully reproducible because indicator(s) <list of missing indicators> are unpublished"**;
  - two or more admissible rules: **cannot discriminate**; Q1 cannot tell the admissible rules apart;
  - no admissible rule: **not reproducible** against R1–R4.
- For each rule, the number of states inside the band, the maximum violation and the list of states outside the band are reported.

### 7.3 The rule and the score used by Q2–Q4

**Rule.**

- Full reconstruction, reproduced: the rule that reproduces the score. If more than one rule matches every computable state, the ranking of §7.1 chooses between them; if they remain tied, Q2–Q4 are run under each.
- Full reconstruction, not reproduced: the first-ranked rule of §7.1 (smallest maximum absolute error, then fewest mismatches).
- Partial reconstruction, exactly one admissible rule: that rule.
- Partial reconstruction, cannot discriminate: Q2–Q4 are run under each admissible rule.
- Partial reconstruction, no admissible rule: the rule with the smallest maximum violation of the admissibility band (ties broken by the fewest states outside the band). Q2–Q4 are also run under each of R1, R2 and R3 as a sensitivity analysis.

**Score.**

- With all nine indicators available, the full score (§6.2).
- Otherwise, the **rescaled partial score** (§6.2) is the primary analysis, with the unrescaled partial score as a check.
- Q2–Q4 are run in every case, because each concerns the indicators, not the published total.

## 8. Q2: robustness

### 8.1 Variants

Each variant is computed under the rule, or each of the rules, fixed by §7.3.

1. **Weight perturbation.** Weights are drawn from a Dirichlet distribution around CTD's weights w_i = pts_i ÷ 100, with alpha_i = c × w_i. Each draw is generated with the Python standard library (`random.gammavariate`, normalised to sum 1) and multiplied by 100, so that the points sum to 100.
   - **Primary setting:** c = 63. The coefficient of variation of weight i is √((1 − w_i) ÷ (w_i (c + 1))): 0.25 for the 20-point indicator, 0.30 for the 15-point indicators, 0.375 for the 10-point indicators and 0.54 for the 5-point indicators.
   - **Extreme bound:** alpha_i = 1 for every i (total concentration 9, one per indicator).
   - 10,000 draws for each setting. The random seed is **20261117**, and it is reset to 20261117 before each weight setting and before each rule, so that every setting and every rule uses the same sequence of draws.
   - Where indicators are missing, the Dirichlet is taken over the available indicators, with w_i the CTD weights rescaled to sum to 1.
2. **Leave one indicator out.** Each available indicator is dropped in turn, and the remaining points are rescaled to 100.
3. **Notification against estimated burden.** Run only if §5.3 finds that annexure 1.2 "expected" and CTD's target disagree. Indicator 1 is then added to the score with annexure 1.2 "expected" as its denominator, as the burden denominator. If they agree, the variant is dropped, as fixed in §5.3. No other burden source, and no scaling of ICMR prevalence to incidence, is used except as a logged exploratory deviation.
4. **Treatment success on the matched cohort.** Indicator 4 with the matched-cohort denominator (the patients notified in the previous year, whose outcomes the annexures report) in place of the denominator in CTD's definition.
5. **Removal of saturated indicators.** An indicator is **saturated** if at least 80% of the states for which it is computable have a ≥ 0.95 (both bounds inclusive). All saturated indicators are removed together, and the remaining points are rescaled to 100. If no indicator is saturated, the variant is reported as empty.

### 8.2 Rank measures

States are ranked from 1 (highest score) to n; tied scores receive the average of the ranks they span. Each variant is compared with the base ranking (the score of §7.3):

- **Rank change.** For each deterministic variant (items 2–5), the **median** and the **maximum absolute change in rank** across states. For the weight perturbation, the median and the maximum absolute change in rank across states are computed for each draw, and the **median and interquartile range of each over the draws** are reported.
- **Top and bottom fifth.** For the weight perturbation, the **share of draws in which each state stays in the top fifth or in the bottom fifth** of the base ranking: 7 units each when 36 units are ranked, ⌊n/5⌋ units when n units are computable.
- **Agreement with the published ranking.** The **Spearman rank correlation with the published ranking** (Table 11.2), as a technical measure of agreement; for the weight perturbation, its median and its 2.5th and 97.5th percentiles over draws.
- **Quantiles** over draws are computed with `statistics.quantiles(..., method="inclusive")`: n = 4 for the interquartile range, and n = 40 for the 2.5th and 97.5th percentiles (the first and last cut points).

## 9. Q3: validity

### 9.1 Primary measure

- **Measure:** Spearman's ρ between the score of §7.3 (not the published Table 11.2 score) for score year 2023 and TB prevalence from the ICMR National TB Prevalence Survey 2019–21, over the survey's state and state-group reporting units.
- **Prevalence:** microbiologically confirmed pulmonary TB per 100,000 population aged 15 years and over, the survey's primary outcome, with its 95% CI recorded. If the state or state-group table prints a different single measure, that measure is used and named. If it prints several, the microbiologically confirmed pulmonary TB, age ≥ 15 years measure is used.
- **Aggregation:** where a reporting unit contains several states, the unit's score is the population-weighted mean of its member states' scores. Each state's population is taken from annexure 1.2 of the 2024 edition as notified patients ÷ notification rate per 100,000 × 10⁵ (§3). States the survey does not cover are listed and excluded.
- **Ties:** average ranks; ρ is the Pearson correlation of the ranks.
- **Interval:** Fisher-z 95% confidence interval with Fieller's variance for Spearman's ρ: z = atanh(ρ), SE = √(1.06 ÷ (n − 3)), interval tanh(z ± 1.96 × SE). The number of units n is stated with every estimate. If n ≤ 3, no interval is given. Every Spearman interval in this plan is computed this way.
- **Expected direction under validity:** negative (higher score, lower prevalence).

### 9.2 Secondary measures

- Spearman's ρ, with its 95% CI (§9.1) and n, between the score of §7.3 and **MDR/RR-TB treatment success** by state (annexure 4.13), an outcome not in the score.
- The primary analysis repeated with the score for **score year 2020**, the year closest to the survey: the 2020 indicators re-scored under the §7.3 rule, with the published 2020 score, where printed, as a check.

### 9.3 Measures not used for validity

- Notified ÷ expected patients is indicator 1's own quantity, and is not used (circular).
- Death and loss to follow-up are arithmetically tied to treatment success (indicator 4); they are reported as descriptive context only.

### 9.4 Reporting

All associations are descriptive, with intervals. **No P values** are reported. The sample is at most 36 states and fewer survey units, and the time gap between the survey (2019–21) and the 2023 score is stated as a limitation.

## 10. Q4: change over time

### 10.1 Scores compared

Q4 uses score years 2020, 2022 and 2023, as far as each edition prints state scores, and compares consecutive available years. It is run on (a) the published scores and (b) all available years re-scored under one definition, the current one (§5.4, item 6). If the indicators or weights changed between editions, (b) is primary and the change is reported. Years for which no edition prints scores are stated as gaps.

### 10.2 Noise model

For each state s, indicator i and score year t, the standard error of the achievement, se_si, is:

- **Indicator 1** (a count against a target): Poisson, se = √(numerator) ÷ target.
- **Indicator 3** (against the 70% benchmark): binomial on the proportion tested, p = numerator ÷ net notified, with n = net notified; then se = √(p (1 − p) ÷ n) ÷ 0.7.
- **Indicators 2, 4, 5, 6, 8 and 9:** binomial, se = √(a (1 − a) ÷ n), where n is the indicator's denominator.
- **A binomial indicator with a > 1** is a data error. It is flagged, and its se is not computable.
- **Indicator 7** (an expenditure ratio, not a count) and any indicator taken from a table that prints a percentage without its numerator and denominator (§5.4, item 3) have se = 0.

The standard error of the score is SE_s,t = √(Σ_i pts_i² × se_si²), summed over the indicators in the score, with pts_i the points in use (rescaled where §7.3 rescales). Under R3, pts_i is divided by the maximum achievement over states, which is treated as fixed. If any indicator's se is not computable for a state, that state's SE is not computable; the state is excluded from §10.3 and listed.

The same uncapped standard errors are used under every rule.

**Direction of bias.** The two simplifications act in opposite directions, so the overall bias is mixed:

- se = 0 for indicator 7 and for percentage-only tables understates noise. It is anti-conservative: a change is more likely to be judged as exceeding noise.
- The uncapped se under R1 overstates noise for a state whose achievement is at or above the cap, because capped points do not vary. It is conservative: a change is less likely to be judged as exceeding noise.

The number of states with at least one se = 0 component is reported for each score year.

### 10.3 Criterion

A state's change between years t − 1 and t **exceeds noise** if

|score_t − score_(t−1)| > 1.96 × √(SE_t² + SE_(t−1)²).

The primary result is the **share of states whose change exceeds noise**, given with the count and the number of states compared, for each pair of years. Which change is primary follows §10.1:

- if the definition (indicators, points or denominators) changed between the two years, the **re-scored change (b)** is primary and the published change (a) is secondary;
- otherwise, the **published change (a)** is primary and the re-scored change (b) is secondary.

### 10.4 Regression from a low year

As a descriptive measure of what a "% improvement" deliverable rewards, Spearman's ρ between score_(t−1) and the change score_t − score_(t−1) is reported with its 95% CI (§9.1) and n, together with each state's change expressed as a percentage of score_(t−1). Small-denominator UTs are identified in the output.

## 11. Software and reproducibility

- Python 3.11 or later (3.14 is used). Every script is run as `python -I <script>`.
- pdfplumber is used for table extraction only. All analysis uses the Python standard library (`random`, seeded as above; `statistics`; `math`).
- Every extracted value carries its source file, PDF page and table number. Every number in the manuscript is derived by code and checked against the code by an automated check.
- The source PDFs are fetched and verified against the digests in §3; they are not redistributed.

## 12. Reporting principles

- Ranks are reported because the score produces them; the unit of critique is the score, not the states.
- A high score that does not track lower TB is reported as a measurement finding, not as evidence of data manipulation.
- Robustness results are reported as evidence about specific indicators, not as a verdict on the score as a whole.
- The reporting guideline is RECORD (routinely collected health data). Ethics approval is not required: only published aggregate data are used.

## 13. Deviations

**Registration point.** This plan, as of commit 999da8b (full SHA 999da8b01fa28444090f00680659a9b367452f3d), was pushed to the public repository https://github.com/hssling/india-state-tb-score at 2026-11-16T19:06:50Z (17 November 2026, 00:36 IST), as recorded by GitHub's `pushed_at` for the repository. The repository's public events, saved in `docs/registration_event.json`, record the creation of branch main by that push (2026-11-16T19:06:51Z) and the next push (2026-11-16T19:07:29Z), whose `before` is this commit. At that point no indicator value had been extracted and nothing had been computed. Every later commit is after registration.

Deviations from this plan are logged here, each with its date.

**17 November 2026.**

1. **Indicator 7 (expenditure against the approved ROP).** As anticipated by §5.4 item 5, the search outside the India TB Report was carried out once, in official public sources (National Health Mission ROP and PIP pages, a state NHM site, and parliamentary replies; a parliamentary committee report on TB could not be retrieved). No state-wise table covering every unit was found. The author closed the search, and indicator 7 is missing for every score year. This entry is recorded for completeness.
2. **Score years compared in Q4.** The 2023 edition prints no numeric state scores for score year 2022: its Table 7.2 lists only the top five states in each of three categories, by rank. The 2021 edition is a scanned document without a text layer, so its tables cannot be extracted without optical character recognition. By the author's decision, score year 2020 is dropped. Q4 compares score years 2022 and 2023, both re-scored under one definition (§10.1 (b)). The comparison of published scores (§10.1 (a)) is not possible.
3. **Indicator 8, score year 2022.** In the 2023 edition, the state rows of annexure 7.2 (TB preventive treatment among household contacts under 5 years) do not sum to its printed India row. The discrepancies are as follows: household contacts under 5 years, 292,845 (state sum) against 292,945 (India row); contacts eligible for TB preventive treatment, 291,602 against 291,690; contacts started on TB preventive treatment, 169,662 against 168,665. Under §5.4 item 2 the table is not used, and indicator 8 is missing for score year 2022.
4. **Indicator 5, score year 2022.** The 2023 edition's state table for Ni-kshay Poshan Yojana (annexure 9) reports patients paid at least one benefit as a share of all notified patients, and gives no count of eligible beneficiaries. No table matches the denominator of §5.1 (total eligible TB patients). Under §5.4 item 4, indicator 5 is missing for score year 2022, and no other denominator is substituted.
5. **Indicator 1, score year 2022.** The 2023 edition prints no national notification target for 2022 other than the total of annexure 1.2. Its text layer was searched in full. The pages without a text layer that could carry such a target were inspected visually: the lists of tables and figures, the executive summary, the chapters on disease burden and case finding, and Tables 15.3 and 15.5. The agreement test of §5.3 therefore could not be run. For each state, indicator 1 uses as its denominator the annexure 1.2 column labelled "Target TB patients expected to be notified", against which the annexure itself prints achievement. Q4 additionally reports the comparison with indicator 1 excluded.
6. **Definition stated in the 2021 edition.** The 2021 edition defines the denominator of indicator 4 (treatment success rate) as net TB patients notified during the same period of the previous year, rather than during the same period (§5.1). This is noted only; score year 2020 is not analysed (item 2).
7. **Score year 2020 in Q3, and the indicators of the Q4 re-scored comparison.** The secondary validity analysis with score year 2020 (§9.2) is not possible, because score year 2020 is not analysed (item 2). The Q4 re-scored comparison uses the indicators available in both 2022 and 2023 (indicators 1, 2, 3, 4 and 6), so that both years are scored under one definition (§10.1 (b)).
8. **Exploratory analysis: indicator 3 scaled to CTD's national figure.** This analysis was not pre-specified; it was added after the final review of the analysis, by the author's decision, and is labelled exploratory in code and output. `src/explore_udst.py` writes `outputs/exploratory_udst_scaling_2023.csv`. For score year 2023, each state's indicator 3 achievement is multiplied by k, the ratio of CTD's national share (Table 11.1, key performance indicator 4, as recorded in `data/source_choices.csv`) to the annexures' national share (the indicator 3 numerators summed over states, divided by the denominators summed over states, from `data/extracted/`); the R1, R2 and R3 partial scores and the §7.2 band counts are then recomputed. Under R3 the scaling cancels by construction. The result is reported beside the confirmatory Q1 verdict (§6.1), not in place of it.
9. **Indicator 8 flag (§5.5).** §5.5 asks that indicator 8 be flagged as a definitional mismatch in every output that uses it. The flag is carried in `data/source_choices.csv` (the indicator 8 rows, marked DEFINITIONAL MISMATCH) and in the manuscript's Table I (column "Noted mismatch"), rather than as a flag in each output file in `outputs/`. No value or result changes.
10. **Correction to item 5.** Item 5 described Tables 15.3 and 15.5 of the 2023 edition as pages without a text layer. That description is corrected: those tables have a text layer, and they were read both as text and visually. The finding of item 5 is unchanged.

**20 November 2026.**

11. **Post hoc analyses after peer review of the manuscript.** Two referees of the manuscript asked for four further analyses, and the author approved them on 20 November 2026, after the registered analyses, the exploratory analysis of item 8 and the manuscript were complete. They are post hoc: not pre-specified, labelled "post hoc" in code and in every output row (`src/posthoc.py` writes `outputs/posthoc_q4_states.csv` and `outputs/posthoc_summary.csv`), and reported beside the registered results they qualify, never in place of them. They use their own seed, 20261120 (the seed of §8.1 belongs to the registered analyses), reset before each analysis, rule and indicator set, with 10,000 bootstrap draws where a bootstrap is used. Each is run under R2, the rule fixed by §7.3, with R1 beside it. The analyses and the reason for each:
    - **(a) Q4, change against overdispersed noise.** Reason: the binomial noise of §10.2 is a lower bound, because it omits non-sampling error and true variation between states, so the thresholds of the largest states are a fraction of a point and the §10.3 test detects almost any change. Each state's 2022 to 2023 change in the rebuilt score (indicators 1, 2, 3, 4 and 6, rescaled) is compared with the inverse-variance-weighted mean change, with funnel limits widened by a multiplicative overdispersion factor estimated from 10%-winsorised z-scores (Spiegelhalter, Stat Med 2005;24:1185) and, separately, by an additive DerSimonian–Laird between-state variance; states outside the 95% (z = 1.96) and 99.8% (z = 3.09) limits are counted. This asks whether a change is unusual relative to other states, a different question from §10.3, which asks whether a change differs from zero beyond sampling noise. A sensitivity analysis replaces the zero SE that §10.2 gives a binomial proportion of 0 or 1 with a Wilson-interval SE and counts the states whose category changes.
    - **(b) Q4, multiplicity.** Reason: §10.3 tests 35 states at the 5% level each, so about 1.75 states would exceed noise by chance if none changed. The count is repeated with a Bonferroni threshold (0.05/35, two-sided) and with Benjamini–Hochberg control of the false discovery rate at 5%.
    - **(c) Q4, regression to the mean.** Reason: the §10.4 correlation between the 2022 score and the change is biased towards negative values by regression to the mean, so it cannot show whether low-scoring states improve more. Oldham's method, the correlation of the change with the mean of the two years' scores, is reported with a bootstrap 95% interval (states resampled), for both indicator sets of Q4.
    - **(d) Q3, uncertainty in prevalence.** Reason: §9.1 correlates the score with the survey's point estimates, whose own 95% confidence intervals are wide. Each unit's prevalence is drawn from a lognormal distribution fitted to its published interval, the units are resampled, and Spearman's ρ with the rebuilt 2023 score is recomputed; the median and the 2.5th and 97.5th percentiles are reported, with the half-width of the §9.1 interval at ρ = 0 as the precision attainable with the number of units.

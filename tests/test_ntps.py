"""Task 8b: ICMR National TB Prevalence Survey 2019-21, state and state-group units."""
import csv
from pathlib import Path

import pytest

from src import states
from src.extract import annex, ntps

PDF = Path("data_raw/icmr_ntps/NTPS_2019_21_report.pdf")
needs_pdf = pytest.mark.skipif(not PDF.exists(), reason="data_raw/icmr_ntps PDF absent")
EXTRACTED = Path("data/extracted")


def _read(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# ---- parsers (no PDF needed) -------------------------------------------------

def test_parse_estimate_row():
    r = ntps.parse_row("Andhra Pradesh 49 16151 303 (225 - 401) 265(138 - 392)", 2)
    assert r == ("Andhra Pradesh", [49, 16151], [(303, 225, 401), (265, 138, 392)])
    r = ntps.parse_row("Delhi 534 (365 - 704) 747 (510 - 984)", 0)
    assert r == ("Delhi", [], [(534, 365, 704), (747, 510, 984)])
    assert ntps.parse_row("Uttarakhand,", 2) is None


def test_rows_rejoin_wrapped_labels_and_fail_loudly():
    lines = ["Gujarat 31 22750 136 (93 - 193) 141 (78 - 203)",
             "Himachal Pradesh, 22 7182 306 (192 - 463) 344 (154 - 534)",
             "Uttarakhand,", "Jammu & Kashmir",
             "Haryana 19 4515 421 (254 - 656) 465 (326 - 605)"]
    rows = ntps.estimate_rows(lines, 2)
    assert [r[0] for r in rows] == [
        "Gujarat", "Himachal Pradesh, Uttarakhand, Jammu & Kashmir", "Haryana"]
    with pytest.raises(ValueError, match="unexpected line"):
        ntps.estimate_rows(["Gujarat 31 22750 136 (93 - 193) 141 (78 - 203)", "Kerala"], 2)


def test_parse_abbreviations_joins_wrapped_expansion():
    ab = ntps.parse_abbreviations([
        "Abbreviations", "GJ,DN,DD Gujarat, Dadra, Nagar Haveli, Daman, Diu",
        "NE North Eastern States (Arunachal Pradesh, Assam, Manipur, Meghalaya,",
        "Mizoram, Nagaland, Tripura And Sikkim)", "OD Odisha"])
    assert ab["GJ,DN,DD"] == "Gujarat, Dadra, Nagar Haveli, Daman, Diu"
    assert ab["NE"].endswith("Tripura And Sikkim)") and ab["OD"] == "Odisha"


def test_members_of_expansion():
    assert ntps.members_of("Gujarat, Dadra, Nagar Haveli, Daman, Diu") == [
        "Gujarat", "Dadra and Nagar Haveli and Daman and Diu"]
    assert ntps.members_of("Tamil Nadu, Pondicherry, Andaman & Nicobar") == [
        "Tamil Nadu", "Puducherry", "Andaman and Nicobar Islands"]
    ne = ntps.members_of("North Eastern States (Arunachal Pradesh, Assam, Manipur, "
                         "Meghalaya, Mizoram, Nagaland, Tripura And Sikkim)")
    assert len(ne) == 8 and ne[-1] == "Sikkim"
    with pytest.raises(KeyError):
        ntps.members_of("Gujarat, Dadra")


def test_merge_source_choices_accepts_a_tag(tmp_path):
    path = tmp_path / "sc.csv"
    row = lambda y, n: {k: "" for k in annex.SOURCE_CHOICE_COLS} | {  # noqa: E731
        "score_year": y, "indicator": n}
    annex.merge_source_choices(path, 2023, [row(2023, 1)])
    annex.merge_source_choices(path, "ntps", [row("ntps", "q3_primary")])
    annex.merge_source_choices(path, 2022, [row(2022, 1)])
    annex.merge_source_choices(path, "ntps", [row("ntps", "q3_primary")])
    got = [(r["score_year"], r["indicator"]) for r in _read(path)]
    assert got == [("2023", "1"), ("2022", "1"), ("ntps", "q3_primary")]


# ---- the report --------------------------------------------------------------

@needs_pdf
def test_ntps_units_cover_states():
    res = ntps.extract(PDF)
    seen: dict[str, str] = {}
    for u in res["units"]:
        for s in u["member_states"]:
            assert s == states.canonical(s)
            assert s not in seen, (s, seen.get(s), u["unit"])  # at most one unit
            seen[s] = u["unit"]
    for row in res["not_covered"]:
        assert row["state"] == states.canonical(row["state"])
        assert row["state"] not in seen, row["state"]
        seen[row["state"]] = "not covered"
    states.require_all(seen, 2023)  # every state exactly once
    assert {r["state"] for r in res["not_covered"]} == {
        "Andaman and Nicobar Islands", "Lakshadweep", "Ladakh"}


@needs_pdf
def test_twenty_units_and_printed_totals():
    res = ntps.extract(PDF)
    assert len(res["units"]) == 20  # "The country was grouped into 20 State groups" (p. 23)
    assert sum(u["n_positive"] for u in res["units"]) == res["national"]["n_positive"] == 981
    assert sum(u["n_screened"] for u in res["units"]) == res["national"]["n_screened"] == 322480


@needs_pdf
def test_ci_brackets_estimate():
    res = ntps.extract(PDF)
    for u in res["units"] + [res["national"]]:
        assert u["ci_low"] < u["prevalence"] < u["ci_high"], u["unit"]


@needs_pdf
def test_spot_values():
    units = {u["unit"]: u for u in ntps.extract(PDF)["units"]}
    d = units["Delhi"]  # Table 20, PDF p. 90
    assert (d["prevalence"], d["ci_low"], d["ci_high"], d["pdf_page"]) == (534, 365, 704, 90)
    ne = units["North Eastern States"]  # Table 20, PDF p. 91
    assert (ne["prevalence"], ne["ci_low"], ne["ci_high"], ne["pdf_page"]) == (276, 123, 429, 91)
    assert ne["unit_type"] == "group" and len(ne["member_states"]) == 8
    assert units["Gujarat"]["member_states"] == [
        "Gujarat", "Dadra and Nagar Haveli and Daman and Diu"]
    assert units["Kerala"]["member_states"] == ["Kerala"]  # Lakshadweep not surveyed


@needs_pdf
def test_national_estimate_kept_apart():
    res = ntps.extract(PDF)
    nat = res["national"]
    assert (nat["prevalence"], nat["ci_low"], nat["ci_high"]) == (316, 290, 342)
    assert "India" not in {u["unit"] for u in res["units"]}


@needs_pdf
def test_committed_csvs_match_extraction(tmp_path):
    ntps.write_all(PDF, tmp_path / "extracted", tmp_path / "source_choices.csv")
    for name in ("ntps_units.csv", "ntps_not_covered.csv", "ntps_national.csv",
                 "ntps_cluster_coverage.csv"):
        assert (tmp_path / "extracted" / name).read_text(encoding="utf-8") == \
            (EXTRACTED / name).read_text(encoding="utf-8"), name
    mine = [r for r in _read(tmp_path / "source_choices.csv") if r["score_year"] == "ntps"]
    committed = [r for r in _read(Path("data/source_choices.csv")) if r["score_year"] == "ntps"]
    assert mine and mine == committed


def test_source_choices_ntps_rows():
    rows = [r for r in _read(Path("data/source_choices.csv")) if r["score_year"] == "ntps"]
    assert {r["indicator"] for r in rows} == {"q3_primary"}
    prev = next(r for r in rows if r["component"] == "prevalence")
    assert prev["table_id"] == "Table 20" and prev["pdf_pages"] == "90;91"
    assert prev["column_header_verbatim"] == (
        "Robust standard errors model with imputation and inverse probability weighting")
    assert "§9.1" in prev["rule_from_plan"]


@needs_pdf
def test_cluster_coverage_counts_and_total():
    rows = {r["state"]: r for r in ntps.cluster_coverage(PDF)}
    assert rows["INDIA"]["clusters_completed"] == 443 and rows["INDIA"]["clusters_planned"] == 625
    assert sum(r["clusters_completed"] for s, r in rows.items() if s != "INDIA") == 443
    no_cluster = {s for s, r in rows.items() if s != "INDIA" and r["clusters_completed"] == 0}
    # survey group members with no completed cluster, plus the three units not covered
    assert no_cluster == {"Goa", "Puducherry", "Dadra and Nagar Haveli and Daman and Diu",
                          "Sikkim", "Mizoram", "Tripura", "Andaman and Nicobar Islands",
                          "Lakshadweep", "Ladakh"}
    assert rows["Chhattisgarh"]["clusters_completed"] == 13  # printed 'Chhatisgarh'


def test_cluster_state_reads_the_leading_name():
    assert ntps._cluster_state("Tamil Nadu Thiruvallur Chinnamandalai Rural 1099") == "Tamil Nadu"
    assert ntps._cluster_state("Chhatisgarh Raipur Mudpar Rural 1089") == "Chhattisgarh"
    with pytest.raises(ValueError):
        ntps._cluster_state("Atlantis Somewhere Rural 1")

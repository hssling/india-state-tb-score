"""Re-run the national-total checks of every extracted table, writing nothing.

Run as: python -I verification/check_extraction_totals.py

Reuses the extractors' own check functions (state sum = printed national row).
Sources whose PDF is absent are reported as SKIPPED (run tools/fetch_sources.py);
if any is absent the script still exits 0 and check_all counts it as skipped.
Exit 1 on any failed check.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from src.extract import annex, itr2021, itr2023, itr2024, ntps  # noqa: E402

SKIP = "SKIPPED: source PDFs not present (run tools/fetch_sources.py)"


def run_itr2024() -> str:
    n = 0
    for t in itr2024.extract_tables(itr2024.PDF).values():  # raises on a failed table
        for col, total, nat, _ in itr2024.check_national(t):
            if total != nat:
                raise AssertionError(f"{t.spec.table_id} {col}: {total} != {nat}")
            n += 1
    return f"ITR2024: {n} national totals match"


def run_itr2023() -> str:
    n = 0
    for t in itr2023.extract_tables(itr2023.PDF).values():
        for col, total, nat, _ in annex.check_national(t):
            if total != nat:
                raise AssertionError(f"{t.spec.table_id} {col}: {total} != {nat}")
            n += 1
    failed = itr2023.printed_total_failures(itr2023.PDF)
    if set(failed) != set(itr2023.FAILS_PRINTED_TOTAL):
        raise AssertionError(f"printed-total failures {sorted(failed)} differ from the "
                             f"documented {sorted(itr2023.FAILS_PRINTED_TOTAL)}")
    return (f"ITR2023: {n} national totals match; documented non-matching table(s) "
            f"{', '.join(sorted(failed))} still fail (not used, plan 13 item 3)")


def run_ntps() -> str:
    res = ntps.extract(ntps.PDF)  # raises unless P and N sum to the India row
    return f"NTPS: {len(res['units'])} units; P and N sum to the India row"


def run_itr2021() -> str:
    st = itr2021.text_layer_status(itr2021.PDF)
    if st["with_text"]:
        raise AssertionError(f"ITR2021 now has a text layer on pages {sorted(st['with_text'])}: "
                             f"re-examine plan 13 item 2")
    return ("ITR2021: BLOCKED as documented (scanned, no text layer on the needed pages; "
            "plan 13 item 2)")


SOURCES = [("ITR2024", itr2024.PDF, run_itr2024), ("ITR2023", itr2023.PDF, run_itr2023),
           ("NTPS", ntps.PDF, run_ntps), ("ITR2021", itr2021.PDF, run_itr2021)]


def main() -> int:
    failed, absent = 0, []
    for name, pdf, fn in SOURCES:
        if not Path(pdf).exists():
            absent.append(name)
            continue
        try:
            print(f"OK: {fn()}")
        except Exception as e:  # noqa: BLE001  any extractor error is a failed check
            failed += 1
            print(f"FAIL: {name}: {type(e).__name__}: {e}")
    if absent:
        print(f"{SKIP}; not checked: {', '.join(absent)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

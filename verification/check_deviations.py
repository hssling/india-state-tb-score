"""Check that every 'exploratory' label in outputs/ is logged in plan section 13.

Run as: python -I verification/check_deviations.py

Each output file containing the word 'exploratory' (case-insensitive) needs a dated
entry in section 13 that names the file and itself says 'exploratory'.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADING = "## 13. Deviations"
DATE = re.compile(r"^\*\*\d{1,2} \w+ \d{4}\.?\*\*\.?$")
ENTRY = re.compile(r"^\d+\.\s")


def section13_entries(plan: str) -> list[tuple[str, str]]:
    """(date, entry text) for every numbered entry under a bold date line in section 13."""
    lines = plan.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.strip() == HEADING)
    entries: list[tuple[str, str]] = []
    date = None
    for ln in lines[start + 1:]:
        if DATE.match(ln.strip()):
            date = ln.strip().strip("*. ")
        elif ENTRY.match(ln) and date:
            entries.append((date, ln))
    return entries


def problems(root: Path = ROOT) -> tuple[list[str], list[str]]:
    """(unlogged labels, files with a logged label)."""
    entries = section13_entries((root / "docs" / "analysis_plan.md").read_text(encoding="utf-8"))
    bad, ok = [], []
    for f in sorted((root / "outputs").rglob("*")):
        if not f.is_file():
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        n = len(re.findall("exploratory", text, re.I))
        if not n:
            continue
        rel = f.relative_to(root).as_posix()
        if any("exploratory" in e.lower() and (f.name in e or rel in e) for _, e in entries):
            ok.append(rel)
        else:
            bad.append(f"{rel}: {n} 'exploratory' label(s) with no dated section 13 entry "
                       f"naming the file")
    return bad, ok


def main() -> int:
    bad, ok = problems()
    if bad:
        for b in bad:
            print(f"FAIL: {b}")
        return 1
    if ok:
        print(f"OK: exploratory labels logged in section 13 for {', '.join(ok)}")
    else:
        print("OK: no exploratory outputs")
    return 0


if __name__ == "__main__":
    sys.exit(main())

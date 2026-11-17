"""Run the whole verification: tests, analyses, checks, and byte-for-byte reproduction.

Run as: python -I verification/check_all.py   (steps run from the repo root)

Steps run as `python -I ...` subprocesses. After the analyses, `git status --porcelain`
on the generated outputs and extracted data must be empty, i.e. every committed output
is reproduced byte for byte. Prints "N/N checks passed" (skipped steps are counted
separately); exits 1 on any failure.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = [sys.executable, "-I"]
REPRODUCED = ("outputs/", "data/extracted/", "data/source_choices.csv")

STEPS = [
    ("pytest", PY + ["-m", "pytest", "-q"]),
    ("q1_reproduce 2023", PY + ["src/q1_reproduce.py", "2023"]),
    ("q2_robust 2023", PY + ["src/q2_robust.py", "2023"]),
    ("q3_validity 2023", PY + ["src/q3_validity.py", "2023"]),
    ("q4_change", PY + ["src/q4_change.py"]),
]
CHECKS = [
    ("check_extraction_totals", PY + ["verification/check_extraction_totals.py"]),
    ("check_plan_order", PY + ["verification/check_plan_order.py"]),
    ("check_deviations", PY + ["verification/check_deviations.py"]),
    ("check_manuscript_numbers", PY + ["verification/check_manuscript_numbers.py"]),
]


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


def tail(text: str, n: int = 15) -> str:
    return "\n".join("    " + ln for ln in text.strip().splitlines()[-n:])


def main() -> int:
    tally = {"passed": 0, "failed": 0, "skipped": 0}

    def report(name: str, status: str, detail: str = "") -> None:
        print(f"[{status}] {name}")
        if detail:
            print(detail)

    def go(name: str, cmd: list[str]) -> None:
        r = run(cmd)
        out = r.stdout + r.stderr
        if r.returncode != 0:
            tally["failed"] += 1
            report(name, "FAIL", tail(out))
        elif any(ln.startswith("SKIPPED") for ln in out.splitlines()):
            tally["skipped"] += 1
            report(name, "SKIP", tail(out))
        else:
            tally["passed"] += 1
            report(name, "ok")

    for name, cmd in STEPS:
        go(name, cmd)

    label = "byte-for-byte reproduction of outputs/ and data/"
    st = run(["git", "status", "--porcelain", "--", *REPRODUCED])
    if st.returncode != 0 or st.stdout.strip():
        tally["failed"] += 1
        report(label, "FAIL", tail(st.stdout or st.stderr)
               + "\n    (files differ from the committed versions)")
    else:
        tally["passed"] += 1
        report(label, "ok")

    for name, cmd in CHECKS:
        go(name, cmd)

    total = tally["passed"] + tally["failed"]
    note = f" ({tally['skipped']} skipped)" if tally["skipped"] else ""
    print(f"\n{tally['passed']}/{total} checks passed{note}")
    return 1 if tally["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())

"""Run the whole verification: tests, analyses, checks, and byte-for-byte reproduction.

Run as: python -I verification/check_all.py   (steps run from the repo root)

Steps run as `python -I ...` subprocesses. The post hoc analyses (src/posthoc.py, plan
section 13, 20 November 2026) run with the analyses, and check_posthoc_outputs recomputes
their point values independently. After the analyses, `git status --porcelain`
on the generated outputs and extracted data must be empty, i.e. every committed output
is reproduced byte for byte. In a copy without .git (a release archive), that step and
check_plan_order print "SKIPPED: not a git checkout ..." and are counted as skipped: clone
the repository to verify the history and the byte reproduction. Prints "N/N checks
passed" (skipped steps are counted separately); exits 1 on any failure.

When the private manuscript/jph_v2 directory (the Journal of Public Health set) is present,
its number check and docx tie run as two further steps, with that set's profile.
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
    ("explore_udst (exploratory)", PY + ["src/explore_udst.py"]),
    ("posthoc (post hoc, after peer review)", PY + ["src/posthoc.py"]),
]
CHECKS = [
    ("check_extraction_totals", PY + ["verification/check_extraction_totals.py"]),
    ("check_plan_order", PY + ["verification/check_plan_order.py"]),
    ("check_deviations", PY + ["verification/check_deviations.py"]),
    ("check_posthoc_outputs", PY + ["verification/check_posthoc_outputs.py"]),
    ("check_manuscript_numbers", PY + ["verification/check_manuscript_numbers.py"]),
    ("check_docx_tie", PY + ["verification/check_docx_tie.py"]),
]
# The Journal of Public Health set (manuscript/jph_v2, git-ignored like the rest of
# manuscript/): checked with its own profile when the directory is present. Without it the
# steps are not listed, so the output of a checkout without that set is unchanged.
JPH_DIR = "manuscript/jph_v2"
JPH_CHECKS = [
    ("check_manuscript_numbers (jph_v2)",
     PY + ["verification/check_manuscript_numbers.py", "--manuscript-dir", JPH_DIR]),
    ("check_docx_tie (jph_v2)",
     PY + ["verification/check_docx_tie.py", "--manuscript-dir", JPH_DIR]),
]


def checks(root: Path = ROOT) -> list[tuple[str, list[str]]]:
    """CHECKS, and the jph_v2 checks when manuscript/jph_v2 exists."""
    return CHECKS + (JPH_CHECKS if (root / JPH_DIR).is_dir() else [])


NOT_GIT = ("SKIPPED: not a git checkout (clone the repository to verify history and byte "
           "reproduction)")


def is_git_checkout(root: Path) -> bool:
    """True if root is a git working tree (a release archive has no .git)."""
    return (root / ".git").exists()


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
    if not is_git_checkout(ROOT):
        tally["skipped"] += 1
        report(label, "SKIP", "    " + NOT_GIT)
    else:
        st = run(["git", "status", "--porcelain", "--", *REPRODUCED])
        if st.returncode != 0 or st.stdout.strip():
            tally["failed"] += 1
            report(label, "FAIL", tail(st.stdout or st.stderr)
                   + "\n    (files differ from the committed versions)")
        else:
            tally["passed"] += 1
            report(label, "ok")

    for name, cmd in checks():
        go(name, cmd)

    total = tally["passed"] + tally["failed"]
    note = f" ({tally['skipped']} skipped)" if tally["skipped"] else ""
    print(f"\n{tally['passed']}/{total} checks passed{note}")
    return 1 if tally["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())

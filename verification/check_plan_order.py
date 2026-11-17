"""Check that the analysis plan was registered before any code, extraction or output.

Run as: python -I verification/check_plan_order.py

1. The registration commit (plan section 13, "Registration point") is an ancestor of HEAD.
2. Every commit touching src/, data/extracted/ or outputs/ is a strict descendant of it.
3. The plan's text before the "## 13. Deviations" heading is identical at the
   registration commit and at HEAD (later edits may only touch section 13).
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRATION = "999da8b"
GUARDED = ("src", "data/extracted", "outputs")
PLAN = "docs/analysis_plan.md"
HEADING = "## 13. Deviations"


def git(repo: Path, *args: str, ok=(0,)) -> subprocess.CompletedProcess:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                       encoding="utf-8")
    if r.returncode not in ok:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r


def is_ancestor(repo: Path, a: str, b: str) -> bool:
    return git(repo, "merge-base", "--is-ancestor", a, b, ok=(0, 1)).returncode == 0


def plan_before_section13(repo: Path, rev: str) -> list[str]:
    text = git(repo, "show", f"{rev}:{PLAN}").stdout
    lines = text.splitlines()
    idx = [i for i, ln in enumerate(lines) if ln.strip() == HEADING]
    if len(idx) != 1:
        raise RuntimeError(f"{PLAN} at {rev}: expected one {HEADING!r} heading, found {len(idx)}")
    return lines[:idx[0]]


def problems(repo: Path = ROOT, registration: str = REGISTRATION,
             guarded: tuple[str, ...] = GUARDED) -> list[str]:
    out: list[str] = []
    reg = git(repo, "rev-parse", "--verify", f"{registration}^{{commit}}").stdout.strip()
    if not is_ancestor(repo, reg, "HEAD"):
        return [f"registration commit {registration} is not an ancestor of HEAD"]
    for c in git(repo, "log", "--format=%H", "--", *guarded).stdout.split():
        if c == reg or not is_ancestor(repo, reg, c):
            out.append(f"commit {c[:7]} touches {'/'.join(guarded)} but is not a descendant "
                       f"of the registration commit {registration}")
    before_reg = plan_before_section13(repo, reg)
    before_head = plan_before_section13(repo, "HEAD")
    if before_reg != before_head:
        n = next((i for i, (x, y) in enumerate(zip(before_reg, before_head)) if x != y),
                 min(len(before_reg), len(before_head)))
        out.append(f"{PLAN} differs from its registered text before section 13 "
                   f"(first difference at line {n + 1})")
    return out


def main() -> int:
    bad = problems()
    if bad:
        for b in bad:
            print(f"FAIL: {b}")
        return 1
    n = len(git(ROOT, "log", "--format=%H", f"{REGISTRATION}..HEAD").stdout.split())
    print(f"OK: {REGISTRATION} is an ancestor of HEAD; no src/data/outputs commit precedes it; "
          f"plan text before section 13 unchanged across {n} later commits")
    return 0


if __name__ == "__main__":
    sys.exit(main())

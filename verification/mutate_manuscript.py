"""Mutation test of check_manuscript_numbers.py on the manuscript.

Run as: python -I verification/mutate_manuscript.py [--kind inc|swap|both] [--list]
                                                     [--manuscript-dir DIR] [--profile NAME]

Every number token (and Table numeral) of the Abstract, Methods, Results, Discussion and Legends to Figures of
manuscript/manuscript.md is changed, one token at a time, in a copy of the text held in
memory (the file is never written), and the full checker (check_manuscript_numbers.problems)
is run on the copy. A mutation is caught if the checker reports at least one problem.
Two kinds of change:

- inc:  the token's last digit goes up by one (9 becomes 0), the format kept; a Roman
        numeral of a Table citation goes to the next one;
- swap: the token is replaced by the next different token of the same section, which is
        a value of the right form (an existing number of the text).

Prints caught/total and every uncaught mutation; exits 1 if any is uncaught. Prints
"SKIPPED" and exits 0 when manuscript/manuscript.md is absent (it is git-ignored).
--manuscript-dir (default manuscript) runs it on another manuscript directory with that
directory's profile (check_manuscript_numbers.PROFILES; jph for manuscript/jph_v2); the
checked sections are the profile's.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from verification import check_manuscript_numbers as cmn  # noqa: E402


def token_spans(text: str, order: tuple[str, ...] = cmn.SECTION_ORDER) -> list[tuple[str, int, int]]:
    """(section, start, end) of every number token in the checked sections, in order. A
    sub-heading ('###') inside a section neither ends it nor carries tokens."""
    spans, sec, level, pos = [], None, 0, 0
    for line in text.splitlines(keepends=True):
        m = re.match(r"^(#+)\s", line)
        if m:
            if sec and len(m.group(1)) > level:
                pos += len(line)
                continue
            sec = next((s for s in order
                        if re.match(rf"^#+\s*{re.escape(s)}\b", line)), None)
            level = len(m.group(1))
        elif sec:
            spans += [(sec, pos + a, pos + b) for a, b, _ in cmn.skel_spans(line)]
        pos += len(line)
    return spans


ROMAN_NEXT = {"I": "II", "II": "III", "III": "IV", "IV": "V"}


def bump(tok: str) -> str:
    """The token with its last digit increased by one (9 becomes 0); a Roman numeral goes to
    the next one."""
    if tok in ROMAN_NEXT:
        return ROMAN_NEXT[tok]
    return tok[:-1] + str((int(tok[-1]) + 1) % 10)


def mutations(text: str, kind: str = "inc", order: tuple[str, ...] = cmn.SECTION_ORDER):
    """Yield (description, mutated_text) for every number token of the checked sections."""
    spans = token_spans(text, order)
    for i, (sec, a, b) in enumerate(spans):
        old = text[a:b]
        if kind == "inc":
            new = bump(old)
        else:  # swap with the next different token of the same section
            same = [text[x:y] for s, x, y in spans if s == sec]
            k = [j for j, (s, x, y) in enumerate(spans) if s == sec].index(i)
            new = next((t for t in same[k + 1:] + same[:k] if t != old), None)
            if new is None:
                continue
        ctx = text[max(0, a - 25):b + 12].replace("\n", " ")
        yield f"{sec}: {old} -> {new} | ...{ctx}...", text[:a] + new + text[b:]


def run(root: Path, text: str, kinds=("inc", "swap"), check=None,
        profile: "cmn.Profile | None" = None, ms_dir: Path | None = None
        ) -> tuple[int, int, list[str]]:
    """(caught, total, descriptions of the uncaught mutations)."""
    profile = profile or cmn.IJMR
    check = check or (lambda t: cmn.problems(root, t, profile, ms_dir))
    caught, total, escaped = 0, 0, []
    for kind in kinds:
        for desc, mutated in mutations(text, kind, profile.section_order):
            total += 1
            if check(mutated):
                caught += 1
            else:
                escaped.append(f"[{kind}] {desc}")
    return caught, total, escaped


def main(argv: list[str]) -> int:
    profile, ms_dir = cmn.cli_profile(argv, ROOT)
    ms = ms_dir / "manuscript.md"
    if not ms.exists():
        rel = ms.relative_to(ROOT).as_posix() if ms.is_relative_to(ROOT) else str(ms)
        print(f"SKIPPED: {rel} not present (kept private until a decision)")
        return 0
    kind = argv[argv.index("--kind") + 1] if "--kind" in argv else "both"
    kinds = ("inc", "swap") if kind == "both" else (kind,)
    text = ms.read_text(encoding="utf-8")
    if cmn.problems(ROOT, text, profile, ms_dir):
        print("The unmutated manuscript already fails the checker; fix that first.")
        return 1
    caught, total, escaped = 0, 0, []
    for k in kinds:
        c, t, e = run(ROOT, text, (k,), profile=profile, ms_dir=ms_dir)
        print(f"{k}: caught {c} of {t}")
        caught, total, escaped = caught + c, total + t, escaped + e
    print(f"caught {caught} of {total}")
    for e in escaped:
        print("UNCAUGHT", e)
    return 1 if escaped else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

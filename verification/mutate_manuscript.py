"""Mutation test of check_manuscript_numbers.py on the manuscript.

Run as: python -I verification/mutate_manuscript.py [--kind inc|swap|both] [--list]

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
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from verification import check_manuscript_numbers as cmn  # noqa: E402


def token_spans(text: str) -> list[tuple[str, int, int]]:
    """(section, start, end) of every number token in the checked sections, in order."""
    spans, sec, pos = [], None, 0
    for line in text.splitlines(keepends=True):
        if re.match(r"^#+\s", line):
            sec = next((s for s in cmn.SECTION_ORDER
                        if re.match(rf"^#+\s*{re.escape(s)}\b", line)), None)
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


def mutations(text: str, kind: str = "inc"):
    """Yield (description, mutated_text) for every number token of the checked sections."""
    spans = token_spans(text)
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


def run(root: Path, text: str, kinds=("inc", "swap"), check=None) -> tuple[int, int, list[str]]:
    """(caught, total, descriptions of the uncaught mutations)."""
    check = check or (lambda t: cmn.problems(root, t))
    caught, total, escaped = 0, 0, []
    for kind in kinds:
        for desc, mutated in mutations(text, kind):
            total += 1
            if check(mutated):
                caught += 1
            else:
                escaped.append(f"[{kind}] {desc}")
    return caught, total, escaped


def main(argv: list[str]) -> int:
    ms = ROOT / "manuscript" / "manuscript.md"
    if not ms.exists():
        print("SKIPPED: manuscript/manuscript.md not present (kept private until a decision)")
        return 0
    kind = argv[argv.index("--kind") + 1] if "--kind" in argv else "both"
    kinds = ("inc", "swap") if kind == "both" else (kind,)
    text = ms.read_text(encoding="utf-8")
    if cmn.problems(ROOT, text):
        print("The unmutated manuscript already fails the checker; fix that first.")
        return 1
    caught, total, escaped = 0, 0, []
    for k in kinds:
        c, t, e = run(ROOT, text, (k,))
        print(f"{k}: caught {c} of {t}")
        caught, total, escaped = caught + c, total + t, escaped + e
    print(f"caught {caught} of {total}")
    for e in escaped:
        print("UNCAUGHT", e)
    return 1 if escaped else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

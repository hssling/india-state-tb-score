"""Tie the submission .docx files to the Markdown sources.

Run as: python -I verification/check_docx_tie.py

The .docx files in manuscript/submission/ are what the journal receives; the Markdown files
are what check_manuscript_numbers.py verifies. This check extracts the text of
02_blinded_manuscript.docx and 01_first_page.docx (zipfile and XML only) and requires:

1. For each of the Abstract, Methods, Results, Discussion and Legends to Figures: the
   ordered number tokens (and Table numerals) of the .docx section equal those of
   manuscript.md (the skeleton tokens of check_manuscript_numbers; a superscript run is
   separated from its neighbour, as the Markdown's ^1^ is);
2. The ordered number tokens of the whole first page equal those of first_page.md, and the
   title page quotes the counts of manuscript/word_counts.json ("N words", "counted in
   Microsoft Word"), which are within IJMR's limits.

Prints "SKIPPED" and exits 0 when manuscript/ or the .docx files are absent (all are
git-ignored). Exit 1 on any difference.
"""
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from verification import check_manuscript_numbers as cmn  # noqa: E402

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
HEADINGS = ("Abstract", "Introduction", "Methods", "Results", "Discussion", "References",
            "Tables", "Legends to Figures")


def docx_paragraphs(path: Path) -> list[tuple[str, bool]]:
    """(text, in_table) for every paragraph of word/document.xml, in order. Superscript
    runs are set off by spaces; tab and break elements become spaces."""
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    out: list[tuple[str, bool]] = []

    def para(p: ET.Element, in_table: bool) -> None:
        parts = []
        for r in p.iter(f"{W}r"):
            sup = r.find(f"{W}rPr/{W}vertAlign")
            is_sup = sup is not None and sup.get(f"{W}val") == "superscript"
            txt = "".join((t.text or "") if t.tag == f"{W}t" else " "
                          for t in r if t.tag in (f"{W}t", f"{W}tab", f"{W}br"))
            parts.append(f" {txt} " if is_sup else txt)
        out.append(("".join(parts), in_table))

    body = root.find(f"{W}body")
    for el in body:
        if el.tag == f"{W}p":
            para(el, False)
        elif el.tag == f"{W}tbl":
            for p in el.iter(f"{W}p"):
                para(p, True)
    return out


def docx_sections(path: Path) -> dict[str, str]:
    """The text of each checked section of the blinded manuscript, headings excluded and
    table cells left out."""
    sections: dict[str, list[str]] = {}
    current = None
    for text, in_table in docx_paragraphs(path):
        t = text.strip()
        if not in_table and t in HEADINGS:
            current = t
            sections.setdefault(current, [])
            continue
        if current and not in_table:
            sections[current].append(text)
    return {k: "\n".join(v) for k, v in sections.items()}


def md_clean(s: str) -> str:
    """Markdown to plain text for token comparison: emphasis, escapes and carets removed."""
    return s.replace("**", "").replace("*", "").replace("\\", "").replace("^", " ")


def tokens(s: str) -> list[str]:
    return [t for _, _, t in cmn.skel_spans(s)]


def only_numbers(s: str) -> list[str]:
    return cmn.SKEL_NUMBER.findall(s)


def compare(a: list[str], b: list[str]) -> str | None:
    if a == b:
        return None
    k = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    return (f"token {k + 1}: docx {a[k] if k < len(a) else '(none)'!r}, "
            f"markdown {b[k] if k < len(b) else '(none)'!r} ({len(a)} vs {len(b)} tokens)")


def problems(root: Path) -> list[str]:
    sub = root / "manuscript" / "submission"
    out = []
    ms = (root / "manuscript" / "manuscript.md").read_text(encoding="utf-8")
    secs = docx_sections(sub / "02_blinded_manuscript.docx")
    for name in cmn.SECTION_ORDER:
        if name not in secs:
            out.append(f"02_blinded_manuscript.docx: no '{name}' heading")
            continue
        msg = compare(tokens(secs[name]), tokens(md_clean(cmn.section(ms, name))))
        if msg:
            out.append(f"02_blinded_manuscript.docx {name}: {msg}")
    fp_docx = "\n".join(t for t, _ in docx_paragraphs(sub / "01_first_page.docx"))
    fp_md = (root / "manuscript" / "first_page.md").read_text(encoding="utf-8")
    msg = compare(only_numbers(fp_docx), only_numbers(md_clean(fp_md)))
    if msg:
        out.append(f"01_first_page.docx: {msg}")
    counts_path = root / "manuscript" / "word_counts.json"
    if not counts_path.exists():
        out.append("manuscript/word_counts.json missing (run manuscript/build_docx.py)")
    else:
        w = json.loads(counts_path.read_text(encoding="utf-8"))
        flat = re.sub(r"\s+", " ", fp_docx)
        for want in (f"{w['main_text']:,} words", f"Abstract: {w['abstract']} words"):
            if want not in flat:
                out.append(f"01_first_page.docx does not quote Word's count {want!r}")
        if flat.count("counted in Microsoft Word") < 2:
            out.append("01_first_page.docx does not say the counts were taken in Microsoft Word")
        if w["abstract"] > 250 or w["main_text"] > 3000:
            out.append(f"Word counts over IJMR's limits: {w}")
    return out


def main(root: Path = ROOT) -> int:
    sub = root / "manuscript" / "submission"
    need = [root / "manuscript" / "manuscript.md", root / "manuscript" / "first_page.md",
            sub / "02_blinded_manuscript.docx", sub / "01_first_page.docx"]
    if not (root / "manuscript").is_dir() or not all(p.exists() for p in need):
        print("SKIPPED: manuscript/ or its .docx files not present (kept private until a decision)")
        return 0
    found = problems(root)
    for ln in found:
        print(ln)
    print(f"docx tie: {len(found)} problem(s)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())

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

--manuscript-dir DIR (default manuscript) ties DIR's set with DIR's profile
(check_manuscript_numbers.PROFILES). The Journal of Public Health set (manuscript/jph_v2;
single-anonymised review, so nothing is blinded) is one main file, 01_manuscript.docx: its
title page (tied to title_page.md) is page 1, the abstract with its keywords stands alone on
page 2 (a page break before the "Abstract" heading, none inside the abstract, and one after
the Keywords paragraph, before "Introduction"), then the text, the end matter, the
references, Table I and the legends. The limits are that journal's (abstract at most 200
words, main text 2,000 to 3,000), the checked sections are the profile's, including the
end-matter Data availability section, and the Supplementary figure section of
05_supplementary_material.docx is tied as well.
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
# further section headings of the Journal of Public Health files (with the end matter)
JPH_HEADINGS = ("Supplementary material", "Supplementary tables", "Supplementary figure",
                "Funding", "Acknowledgements", "Conflict of interest", "Author contributions",
                "Data availability")


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


def docx_items(path: Path) -> list[tuple[str, str]]:
    """The body in order, as ("p", text) for a paragraph outside a table, ("t", "") for a
    table and ("break", "") for a page break (a page-break run, or a paragraph that starts a
    new page)."""
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    out: list[tuple[str, str]] = []
    for el in root.find(f"{W}body"):
        if el.tag == f"{W}tbl":
            out.append(("t", ""))
            continue
        if el.tag != f"{W}p":
            continue
        if el.find(f"{W}pPr/{W}pageBreakBefore") is not None:
            out.append(("break", ""))
        text = []
        for r in el.iter(f"{W}r"):
            for t in r:
                if t.tag == f"{W}br" and t.get(f"{W}type") == "page":
                    if "".join(text).strip():
                        out.append(("p", "".join(text)))
                    text = []
                    out.append(("break", ""))
                elif t.tag == f"{W}t":
                    text.append(t.text or "")
                elif t.tag in (f"{W}br", f"{W}tab"):
                    text.append(" ")
        if "".join(text).strip():
            out.append(("p", "".join(text)))
    return out


def title_page_layout(path: Path) -> tuple[str, list[str]]:
    """(text of the title page, problems): the title page is page 1, and the abstract with
    its keywords stands alone on page 2."""
    items = docx_items(path)
    out: list[str] = []
    try:
        a = items.index(("p", "Abstract"))
        i = next(k for k, it in enumerate(items) if it == ("p", "Introduction"))
    except (ValueError, StopIteration):
        return "", [f"{path.name}: no 'Abstract' or 'Introduction' heading"]
    before = items[:a]
    title = "\n".join(t for kind, t in before if kind == "p")
    if not title.strip():
        out.append(f"{path.name}: no title page before the abstract")
    if any(kind == "break" for kind, _ in before[:-1]) or not before or before[-1][0] != "break":
        out.append(f"{path.name}: the title page is not page 1 alone (one page break must "
                   "end it, directly before 'Abstract')")
    page2 = items[a + 1:i]
    if not page2 or page2[-1][0] != "break":
        out.append(f"{path.name}: no page break between the abstract page and 'Introduction'")
    body = [it for it in page2[:-1]]
    if any(kind != "p" for kind, _ in body):
        out.append(f"{path.name}: the abstract page holds a page break or a table")
    elif not body or not body[-1][1].startswith("Keywords"):
        out.append(f"{path.name}: the abstract page does not end with the keywords")
    return title, out


def docx_sections(path: Path, headings: tuple[str, ...] = HEADINGS) -> dict[str, str]:
    """The text of each checked section of the blinded manuscript, headings excluded and
    table cells left out."""
    sections: dict[str, list[str]] = {}
    current = None
    for text, in_table in docx_paragraphs(path):
        t = text.strip()
        if not in_table and t in headings:
            current = t
            sections.setdefault(current, [])
            continue
        if current and not in_table:
            sections[current].append(text)
    return {k: "\n".join(v) for k, v in sections.items()}


def md_clean(s: str) -> str:
    """Markdown to plain text for token comparison: emphasis, escapes and carets removed, and
    the item numbers of a numbered list opening in bold ("1. **Publish"), which Word
    numbers itself, left out."""
    s = re.sub(cmn.ALLOW_LIST, "", s)
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


def problems(root: Path, profile: "cmn.Profile | None" = None,
             ms_dir: Path | None = None) -> list[str]:
    profile = profile or cmn.IJMR
    ms_dir = ms_dir or root / profile.dir
    heads = HEADINGS if profile is cmn.IJMR else HEADINGS + JPH_HEADINGS
    sub = ms_dir / "submission"
    out = []
    ms = (ms_dir / "manuscript.md").read_text(encoding="utf-8")
    secs = docx_sections(sub / profile.ms_docx, heads)
    extra_sections = {sec for _, sec in profile.docx_extra}
    for name in [s for s in profile.section_order if s not in extra_sections]:
        if name not in secs:
            out.append(f"{profile.ms_docx}: no '{name}' heading")
            continue
        msg = compare(tokens(secs[name]), tokens(md_clean(cmn.section(ms, name))))
        if msg:
            out.append(f"{profile.ms_docx} {name}: {msg}")
    for docx_name, name in profile.docx_extra:
        extra = docx_sections(sub / docx_name, heads)
        if name not in extra:
            out.append(f"{docx_name}: no '{name}' heading")
            continue
        msg = compare(tokens(extra[name]), tokens(md_clean(cmn.section(ms, name))))
        if msg:
            out.append(f"{docx_name} {name}: {msg}")
    if profile.title_in_ms:
        fp_docx, layout = title_page_layout(sub / profile.ms_docx)
        out += layout
    else:
        fp_docx = "\n".join(t for t, _ in docx_paragraphs(sub / profile.title_docx))
    fp_md = (ms_dir / profile.title_md).read_text(encoding="utf-8")
    msg = compare(only_numbers(fp_docx), only_numbers(md_clean(fp_md)))
    if msg:
        out.append(f"{profile.title_docx}: {msg}")
    counts_path = ms_dir / "word_counts.json"
    if not counts_path.exists():
        rel = (counts_path.relative_to(root).as_posix() if counts_path.is_relative_to(root)
               else str(counts_path))
        out.append(f"{rel} missing (run manuscript/build_docx.py)")
    else:
        w = json.loads(counts_path.read_text(encoding="utf-8"))
        flat = re.sub(r"\s+", " ", fp_docx)
        for want in (f"{w['main_text']:,} words", f"Abstract: {w['abstract']} words"):
            if want not in flat:
                out.append(f"{profile.title_docx} does not quote Word's count {want!r}")
        if flat.count("counted in Microsoft Word") < 2:
            out.append(f"{profile.title_docx} does not say the counts were taken in Microsoft Word")
        if profile is cmn.IJMR:
            if w["abstract"] > 250 or w["main_text"] > 3000:
                out.append(f"Word counts over IJMR's limits: {w}")
        elif not (w["abstract"] <= profile.abstract_max
                  and profile.main_min <= w["main_text"] <= profile.main_max):
            out.append(f"Word counts outside the {profile.name} limits: {w}")
    return out


def main(root: Path = ROOT, argv: list[str] | None = None) -> int:
    """Options: --manuscript-dir DIR (default manuscript) and --profile NAME."""
    argv = sys.argv[1:] if argv is None else argv
    profile, ms_dir = cmn.cli_profile(argv, root)
    sub = ms_dir / "submission"
    need = [ms_dir / "manuscript.md", ms_dir / profile.title_md,
            sub / profile.ms_docx, sub / profile.title_docx]
    need += [sub / d for d, _ in profile.docx_extra]
    if not (root / "manuscript").is_dir() or not all(p.exists() for p in need):
        if profile is cmn.IJMR:
            print("SKIPPED: manuscript/ or its .docx files not present (kept private until a decision)")
        else:
            print(f"SKIPPED: {profile.dir}/ or its .docx files not present")
        return 0
    found = problems(root, profile, ms_dir)
    for ln in found:
        print(ln)
    print(f"docx tie: {len(found)} problem(s)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())

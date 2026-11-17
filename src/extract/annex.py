"""Shared annexure machinery for the earlier India TB Report editions.

The 2024 extractor (itr2024.py) reads tables whose State/UT rows sit on one
line each. The 2023 edition wraps names around their values ("Andaman &" /
"520 10 530 ..." / "Nicobar Islands", or "Dadra And Nagar" / "Haveli And
Daman 980 ..." / "And Diu") and wraps percentages onto later lines, so rows
are rebuilt here by a small state machine (assemble_rows). Every check of
the 2024 extractor is kept: cell count per row, one national row, all units
present, blanks kept blank, state sums equal to the printed national row.

Annexure pages are located from the edition's own "List of Annexures": the
PDF-page offset is derived from the annexures whose title is in the text
layer, never assumed, and every table page is verified by its title or its
first header line.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

import pdfplumber

from src import states
from src.extract import cells, pdftext


# ---- page text ---------------------------------------------------------------

@lru_cache(maxsize=None)
def _open(pdf: str) -> pdfplumber.PDF:
    # Kept open for the life of the process: the earlier editions are large
    # (ITR2021 is 223 MB), and pdftext.page_lines reopens the file per page.
    return pdfplumber.open(pdf)


@lru_cache(maxsize=None)
def _page_lines(pdf: str, page: int) -> tuple[str, ...]:
    """Same rules as pdftext.page_lines (rotation-aware), one shared handle."""
    pg = _open(pdf).pages[page - 1]
    if pdftext._is_rotated(pg.chars):
        out = tuple(pdftext._rotated_lines(pg.chars))
    else:
        out = tuple((pg.extract_text() or "").splitlines())
    pg.close()
    return out


@lru_cache(maxsize=None)
def _char_count(pdf: str, page: int) -> int:
    pg = _open(pdf).pages[page - 1]
    n = len(pg.chars)
    pg.close()
    return n


class Doc:
    """Lazy, cached page access to one PDF."""

    def __init__(self, pdf: Path):
        self.pdf = str(pdf)

    def lines(self, page: int) -> tuple[str, ...]:
        return _page_lines(self.pdf, page)

    def range_lines(self, first: int, last: int) -> list[tuple[str, ...]]:
        return [self.lines(p) for p in range(first, last + 1)]

    def chars(self, page: int) -> int:
        return _char_count(self.pdf, page)

    def n_pages(self) -> int:
        return len(_open(self.pdf).pages)


# ---- cells -------------------------------------------------------------------

class Cell(NamedTuple):
    n: str | None  # the count as printed; None for a blank cell
    pct: str | None
    raw: str


# "(NA)" is printed as the percentage of a zero denominator: "0 (NA)".
_PCT = re.compile(r"^\(\s*(?:-?\d+(?:\.\d+)?\s*%?|NA)\s*\)$")
_NUM = re.compile(r"^\*?\d[\d,]*(?:\.\d+)?\*?$")
_TOKEN = re.compile(r"\(\s*(?:-?\d+(?:\.\d+)?\s*%?|NA)\s*\)|\S+")
BLANKS = frozenset({"NA", "-", "–", "#N/A", "#DIV/0!"})


def split_cells(text: str) -> list[Cell]:
    """Cells of the value part of a row (same rules as itr2024.split_cells).

    A count with an optional "(pct)" after it, a blank marker, or a lone
    "(pct)" without a count (a blank count). A "(pct)" that follows a count
    which already has one starts a new, blank cell.
    """
    out: list[Cell] = []
    for tok in _TOKEN.findall(text):
        if _PCT.match(tok):
            last = out[-1] if out else None
            if last is not None and last.n is not None and last.pct is None:
                out[-1] = Cell(last.n, tok, f"{last.raw} {tok}")
            else:
                out.append(Cell(None, tok, tok))
        elif tok in BLANKS:
            out.append(Cell(None, None, tok))
        elif _NUM.match(tok):
            out.append(Cell(tok, None, tok))
        else:
            raise ValueError(f"unexpected token {tok!r} in row {text!r}")
    return out


def pct_only(cs: list[Cell]) -> bool:
    """True for a line of wrapped percentages (no count, no blank marker)."""
    return all(c.n is None and c.pct is not None and c.raw == c.pct for c in cs)


# ---- rows --------------------------------------------------------------------

# A value starts with a digit (or "*digit"), "(", "#", or is a blank marker.
_VALUE_START = re.compile(r"^(?:\*?\d|\(|#)")


def _is_value(tok: str) -> bool:
    return bool(_VALUE_START.match(tok)) or tok in BLANKS


def split_name(line: str) -> tuple[list[str], str]:
    """Leading words before the first value-like token, and the rest."""
    toks = line.split()
    k = next((j for j, t in enumerate(toks) if _is_value(t)), len(toks))
    return toks[:k], " ".join(toks[k:])


def _norm(s: str) -> str:
    return states.normalize(s)  # same normalisation as the canonical lookup


@lru_cache(maxsize=None)
def _unit_keys(year: int) -> dict[str, str]:
    """Normalised spelling -> canonical name, for the units valid in `year`."""
    return states.spellings(year)


def _complete(name: str, year: int) -> str | None:
    return _unit_keys(year).get(_norm(name))


def _prefix(name: str, year: int) -> bool:
    n = _norm(name)
    return any(k == n or k.startswith(n + " ") for k in _unit_keys(year))


@dataclass
class _Row:
    words: list[str]
    cells: list[Cell] | None
    lines: list[str] = field(default_factory=list)


def assemble_rows(lines: list[str], ncells: int, national: tuple[str, ...], year: int,
                  footer: re.Pattern | None = None, min_cells: int | None = None,
                  ) -> tuple[dict[str, list[Cell]], list[Cell] | None]:
    """State rows and the national row of one table page.

    Lines before the first State/UT name are header lines and are skipped;
    processing stops after the national row. Between those, every line must
    be a State/UT row, a continuation of the current row's name, the
    current row's values (when its name was printed alone), a line of
    wrapped percentages, or a page footer; anything else raises ValueError.

    A row must have `ncells` cells, or between `min_cells` and `ncells` when
    `min_cells` is given (see Spec.min_cells).
    """
    rows: dict[str, list[Cell]] = {}
    nat: list[Cell] | None = None
    cur: _Row | None = None
    started = False
    nat_keys = {_norm(x) for x in national}

    def flush(r: _Row | None) -> None:
        nonlocal nat
        if r is None:
            return
        name = " ".join(r.words)
        if r.cells is None:
            raise ValueError(f"row {name!r} has no values: {r.lines!r}")
        if not (min_cells or ncells) <= len(r.cells) <= ncells:
            raise ValueError(f"{name}: {len(r.cells)} cells, header has {ncells}: {r.lines!r}")
        if _norm(name) in nat_keys:
            if nat is not None:
                raise ValueError(f"two national rows ({name})")
            nat = r.cells
            return
        canon = _complete(name, year)
        if canon is None:
            raise ValueError(f"not a State/UT for {year}: {name!r} in {r.lines!r}")
        if canon in rows:
            raise ValueError(f"duplicate row for {canon}: {r.lines!r}")
        rows[canon] = r.cells

    for raw in lines:
        line = raw
        if footer is not None:
            line = footer.sub(" ", line).strip()
            if line != raw.strip():  # a footer was removed
                if not line:
                    continue
                if not pct_only(split_cells(line)):
                    raise ValueError(f"footer line carries values: {raw!r}")
                continue
        words, rest = split_name(line)
        name = " ".join(words)
        if not started:
            if words and (_prefix(name, year) or _norm(name) in nat_keys):
                started = True
            else:
                continue  # header
        cs = split_cells(rest) if rest else []
        has_values = bool(cs) and not pct_only(cs)
        if words:
            if cur is not None and _prefix(" ".join(cur.words + words), year):
                cur.words += words
                cur.lines.append(raw)
                if has_values:
                    if cur.cells is not None:
                        raise ValueError(f"two value lines for {' '.join(cur.words)}: {cur.lines!r}")
                    cur.cells = cs
                continue
            if _prefix(name, year) or _norm(name) in nat_keys:
                flush(cur)
                cur = _Row(list(words), cs if has_values else None, [raw])
                if _norm(name) in nat_keys:
                    flush(cur)
                    cur = None
                    break
                continue
            raise ValueError(f"unexpected line inside the table: {raw!r}")
        if has_values:
            if cur is None or cur.cells is not None:
                raise ValueError(f"values without a row name: {raw!r}")
            cur.cells = cs
            cur.lines.append(raw)
        # else: wrapped percentages; their counts are already in the row
    flush(cur)
    return rows, nat


# ---- list of annexures and page location -------------------------------------

_LIST_ENTRY = re.compile(r"^(\d{1,2}(?:\.\d{1,2})?)\s+(?:.*\s)?(\d{3})$")


def annexure_list(doc: Doc, pages: tuple[int, ...]) -> dict[str, int]:
    """Annexure number -> printed page, from the edition's List of Annexures."""
    out: dict[str, int] = {}
    for p in pages:
        for line in doc.lines(p):
            m = _LIST_ENTRY.match(line.strip())
            if m:
                if m.group(1) in out:
                    raise ValueError(f"annexure {m.group(1)} listed twice")
                out[m.group(1)] = int(m.group(2))
    return out


@dataclass(frozen=True)
class Column:
    indices: tuple[int, ...]  # 0-based cell indices after the name; summed if several
    header: str  # verbatim (flattened) column header
    count: bool = False  # parse with cells.parse_count (integral floats)


@dataclass(frozen=True)
class Spec:
    key: str
    annex: str  # annexure number as listed, e.g. "1.2"
    title: str | None  # verbatim title line start, if the title is in the text layer
    header: str  # verbatim start of the first header line on every page
    ncells: int
    columns: dict[str, Column]
    national: tuple[str, ...] = ("India", "INDIA")
    header_on_every_page: bool = True  # False: continuation pages print rows only
    # Units the table does not print at all (their row is written blank).
    absent: tuple[str, ...] = ()
    # Rows may have fewer cells (down to min_cells) where a lone "(pct)" of a
    # blank count is printed after a count whose own percentage wrapped, so
    # that the two cannot be told apart. Allowed only when every extracted
    # column lies in the first `plain_lead` cells and those cells are printed
    # as bare counts (checked row by row).
    min_cells: int | None = None
    plain_lead: int = 0

    @property
    def table_id(self) -> str:
        return f"Annexure {self.annex}"


@dataclass
class Table:
    spec: Spec
    pages: tuple[int, ...]
    rows: dict[str, dict[str, int | None]]
    row_pages: dict[str, int | None]
    national: dict[str, int]
    blanks: dict[str, list[str]]
    cells: dict[str, list[Cell]]  # the printed cells of each row ("India" = national)


def find_title(doc: Doc, title: str, first: int, last: int) -> int:
    hits = [first + i for i, ls in enumerate(doc.range_lines(first, last))
            if ls and ls[0].startswith(title)]
    if len(hits) != 1:
        raise ValueError(f"title {title!r} found on pages {hits}, expected once")
    return hits[0]


def locate(doc: Doc, specs: list[Spec], listed: dict[str, int], first: int,
           ) -> tuple[int, dict[str, tuple[int, ...]]]:
    """PDF-page offset and each spec's PDF pages.

    The offset (PDF page - printed page) is measured on every spec whose title
    is in the text layer, by searching pages first..end for the title; all
    must agree. A spec's pages run from its listed page to the page before the
    next listed annexure. Every page must start with the spec's title (first
    page, when titled) or carry its header line within its first three lines.
    """
    last = doc.n_pages()
    offsets = {s.key: find_title(doc, s.title, first, last) - listed[s.annex]
               for s in specs if s.title is not None}
    if not offsets or len(set(offsets.values())) != 1:
        raise ValueError(f"inconsistent annexure page offsets: {offsets}")
    off = next(iter(offsets.values()))
    order = sorted(listed.values())
    pages: dict[str, tuple[int, ...]] = {}
    for s in specs:
        start = listed[s.annex]
        nxt = min(p for p in order if p > start)
        pg = tuple(range(start + off, nxt + off))
        for i, p in enumerate(pg):
            ls = doc.lines(p)
            if i == 0 and s.title is not None and not ls[0].startswith(s.title):
                raise ValueError(f"{s.table_id}: PDF page {p} starts {ls[:1]!r}")
            if i > 0 and not s.header_on_every_page:
                if ls and states.leading_state(ls[0]) is None:
                    raise ValueError(f"{s.table_id}: continuation page {p} starts {ls[:1]!r}")
                continue
            if not any(l.startswith(s.header) for l in ls[:3 + (2 if i == 0 and s.title else 0)]):
                raise ValueError(f"{s.table_id}: PDF page {p} lacks header {s.header!r}: {ls[:4]!r}")
        pages[s.key] = pg
    return off, pages


def _value(cell: Cell, col: Column, where: str) -> int | None:
    if cell.n is None:
        return None
    try:
        return cells.parse_count(cell.n) if col.count else cells.parse_int(cell.n)
    except ValueError as e:
        raise ValueError(f"{where}: {e}") from None


def _col_value(cs: list[Cell], col: Column, where: str) -> int | None:
    vals = [_value(cs[i], col, where) for i in col.indices]
    if any(v is None for v in vals):
        if len(vals) > 1 and not all(v is None for v in vals):
            raise ValueError(f"{where}: some summed cells blank: {[cs[i].raw for i in col.indices]}")
        return None
    return sum(vals)  # type: ignore[arg-type]


def extract_table(doc: Doc, spec: Spec, pages: tuple[int, ...], year: int,
                  footer: re.Pattern | None, check: bool = True) -> Table:
    if spec.min_cells is not None:
        used = [i for c in spec.columns.values() for i in c.indices]
        if not spec.plain_lead or max(used) >= spec.plain_lead:
            raise ValueError(f"{spec.table_id}: min_cells needs columns within plain_lead")
    rows: dict[str, list[Cell]] = {}
    row_pages: dict[str, int | None] = {}
    national: list[Cell] | None = None
    for pg in pages:
        r, nat = assemble_rows(list(doc.lines(pg)), spec.ncells, spec.national, year, footer,
                               spec.min_cells)
        if nat is not None:
            if national is not None:
                raise ValueError(f"{spec.table_id}: two national rows")
            national = nat
        for s, cs in r.items():
            if s in rows:
                raise ValueError(f"{spec.table_id}: {s} on two pages")
            rows[s], row_pages[s] = cs, pg
    if national is None:
        raise ValueError(f"{spec.table_id}: no national row")
    printed_absent = [u for u in spec.absent if u in rows]
    if printed_absent:
        raise ValueError(f"{spec.table_id}: {printed_absent} printed after all")
    states.require_all(list(rows) + list(spec.absent), year)
    if spec.plain_lead:
        # The leading cells print no percentage, so a "(pct)" attached to one
        # of them is the lone percentage of the next (blank) cell.
        def detach(cs: list[Cell]) -> list[Cell]:
            out: list[Cell] = []
            for i, c in enumerate(cs):
                if i < spec.plain_lead and c.n is not None and c.pct is not None:
                    out += [Cell(c.n, None, c.n), Cell(None, c.pct, c.pct)]
                else:
                    out.append(c)
            if len(out) > spec.ncells:
                raise ValueError(f"{spec.table_id}: {len(out)} cells after detaching: "
                                 f"{[c.raw for c in cs]}")
            return out
        rows = {s: detach(cs) for s, cs in rows.items()}
        national = detach(national)
        for s, cs in list(rows.items()) + [("national", national)]:
            lead = cs[:spec.plain_lead]
            if any(c.n is None or c.pct is not None for c in lead):
                raise ValueError(f"{spec.table_id} {s}: leading cells not bare counts: "
                                 f"{[c.raw for c in lead]}")
    order = states.units(year)
    out: dict[str, dict[str, int | None]] = {}
    blanks: dict[str, list[str]] = {c: [] for c in spec.columns}
    for s in order:
        out[s] = {}
        for name, col in spec.columns.items():
            v = None if s in spec.absent else _col_value(rows[s], col, f"{spec.table_id} {s} {name}")
            out[s][name] = v
            if v is None:
                blanks[name].append(s)
        row_pages.setdefault(s, None)
    nat_vals: dict[str, int] = {}
    for name, col in spec.columns.items():
        v = _col_value(national, col, f"{spec.table_id} national {name}")
        if v is None:
            raise ValueError(f"{spec.table_id}: national {name} is blank")
        nat_vals[name] = v
    t = Table(spec, pages, out, row_pages, nat_vals, blanks, {**rows, "India": national})
    if check:
        check_national(t)
    return t


def national_mismatches(t: Table) -> list[tuple[str, int, int]]:
    """(column, state sum, printed national) for every column that differs."""
    out = []
    for name in t.spec.columns:
        total = sum(v[name] for v in t.rows.values() if v[name] is not None)
        if total != t.national[name]:
            out.append((name, total, t.national[name]))
    return out


def check_national(t: Table) -> list[tuple[str, int, int, int]]:
    """State sum == printed national row for every extracted column (blanks
    left out). Returns (column, state sum, national, number of blanks)."""
    res = []
    for name in t.spec.columns:
        total = sum(v[name] for v in t.rows.values() if v[name] is not None)
        if total != t.national[name]:
            raise ValueError(f"{t.spec.table_id} {name}: state sum {total} != "
                             f"national {t.national[name]}")
        res.append((name, total, t.national[name], len(t.blanks[name])))
    return res


# ---- writing -----------------------------------------------------------------

def _fmt(v) -> str:
    return "" if v is None else str(v)


def write_csv(path: Path, header: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        for r in rows:
            w.writerow([_fmt(r[h]) for h in header])


SOURCE_CHOICE_COLS = ["score_year", "indicator", "component", "table_id", "pdf_pages",
                      "column_header_verbatim", "rule_from_plan", "note"]


def _year_key(y: str) -> tuple:
    """Numeric score years first, descending; then tags ("ntps") by name."""
    return (0, -int(y), "") if y.isdigit() else (1, 0, y)


def merge_source_choices(path: Path, score_year: int | str, rows: list[dict]) -> None:
    """Replace `score_year`'s rows in data/source_choices.csv, keeping the
    other years' rows; years are kept in descending order, followed by
    non-year tags such as "ntps" (the prevalence survey)."""
    key = str(score_year)
    old: list[dict] = []
    if path.exists():
        with open(path, encoding="utf-8", newline="") as f:
            old = [r for r in csv.DictReader(f) if r["score_year"] != key]
    new = [{k: _fmt(r[k]) for k in SOURCE_CHOICE_COLS} for r in rows]
    years = sorted({r["score_year"] for r in old} | {key}, key=_year_key)
    merged = [r for y in years for r in (new if y == key else
                                         [o for o in old if o["score_year"] == y])]
    write_csv(path, SOURCE_CHOICE_COLS, merged)


DEFINITION_COLS = ["edition", "score_year", "indicator_no", "indicator_text_verbatim",
                   "points", "source_page", "note"]


def merge_definitions(path: Path, edition: int, rows: list[dict]) -> None:
    """Replace `edition`'s rows in data/extracted/definitions.csv, keeping the
    other editions' rows; editions in descending order."""
    old: list[dict] = []
    if path.exists():
        with open(path, encoding="utf-8", newline="") as f:
            old = [r for r in csv.DictReader(f) if r["edition"] != str(edition)]
    new = [{k: _fmt(r[k]) for k in DEFINITION_COLS} for r in rows]
    eds = sorted({int(r["edition"]) for r in old} | {edition}, reverse=True)
    merged = [r for e in eds for r in (new if e == edition else
                                       [o for o in old if o["edition"] == str(e)])]
    write_csv(path, DEFINITION_COLS, merged)

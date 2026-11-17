"""Figures 1-4 of the manuscript: deterministic rendering of outputs/ by code.

Run as: python -I exhibits/make_figures.py   (from the repository root)

Every figure is a plot of committed files in outputs/ (and data/extracted/ for the
survey unit abbreviations), drawn by matplotlib from this script. No image is
generated, edited or retouched by artificial intelligence or by hand (IJMR: "AI
should not be used for generating figures"). The same inputs give the same pixels:
fixed sizes, no timestamps in the files, fixed SVG hash salt.

Output, in manuscript/figures/:
- figureN.tif  greyscale ('L'), 600 dpi, LZW, no alpha channel (IJMR upload format);
- figureN.png  the same pixels, for the docx build;
- figureN.svg  editable vector source (IJMR asks for editable figure files);
- figure_notes.md  what each figure plots and its abbreviation key, for the legends.

Greyscale only: identity is carried by marker shape, fill and hatching, never by
colour; titles and explanations belong in the legends, not on the images. Counts
that Tables II and IV report are not repeated on the images (IJMR: no data in both
tabular and graphic form).
"""
from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch, Polygon  # noqa: E402
from matplotlib import transforms  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from PIL import Image  # noqa: E402  (a matplotlib dependency; used only to write 'L' files)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.q4_change import Z975  # noqa: E402

OUT = ROOT / "manuscript" / "figures"
DPI = 600
MINUS = "−"
FONT_PT = 9

BLACK, DARK, MID, LIGHT, PALE = "#000000", "#404040", "#808080", "#b0b0b0", "#e0e0e0"

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    # IJMR: lettering of uniform size, legible after reduction to column width.
    # One size for every piece of text: FONT_PT at a 6.5 in (two-column) width.
    "font.size": FONT_PT,
    "axes.labelsize": FONT_PT,
    "xtick.labelsize": FONT_PT,
    "ytick.labelsize": FONT_PT,
    "legend.fontsize": FONT_PT,
    "axes.linewidth": 0.8,
    "xtick.major.width": 0.8,
    "ytick.major.width": 0.8,
    "lines.linewidth": 1.0,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.unicode_minus": True,
    "svg.hashsalt": "tb-state-score",
    "svg.fonttype": "none",
})


def read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def selection() -> dict:
    return json.loads((ROOT / "outputs" / "q1_2023_selection.json").read_text(encoding="utf-8"))


def save(fig, name: str) -> None:
    """Write TIFF and PNG as 8-bit greyscale without alpha, and an editable SVG."""
    OUT.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=DPI, facecolor="white", metadata={"Software": None})
    buf.seek(0)
    img = Image.open(buf).convert("RGB").convert("L")
    img.save(OUT / f"{name}.tif", format="TIFF", compression="tiff_lzw", dpi=(DPI, DPI))
    img.save(OUT / f"{name}.png", format="PNG", dpi=(DPI, DPI), optimize=False)
    fig.savefig(OUT / f"{name}.svg", format="svg", facecolor="white",
                metadata={"Date": None, "Creator": None})
    plt.close(fig)


# --------------------------------------------------------------------------------------
# Figure 1: Q1, published score against the rebuilt partial score (primary rule)
# --------------------------------------------------------------------------------------
def figure1() -> str:
    sel = selection()
    rule, mp = sel["chosen"], sel["missing_points"]
    rows = [r for r in read_csv(ROOT / "outputs" / "q1_2023.csv")
            if r["rule"] == rule and r["excluded"] == "0"]
    x = [float(r["partial"]) for r in rows]
    y = [float(r["published"]) for r in rows]
    inb = [r["in_band"] == "1" for r in rows]
    lo, hi = min(x) - 5, max(y) + 5
    fig, ax = plt.subplots(figsize=(6.5, 5.6))
    band = Polygon([(lo, lo), (hi, hi), (hi, hi + mp), (lo, lo + mp)], closed=True,
                   facecolor=PALE, edgecolor="none", zorder=0)
    ax.add_patch(band)
    ax.plot([lo, hi], [lo, hi], color=DARK, lw=0.8, ls="--", zorder=1)
    ax.plot([lo, hi], [lo + mp, hi + mp], color=DARK, lw=0.8, ls=":", zorder=1)
    ax.scatter([a for a, k in zip(x, inb) if k], [b for b, k in zip(y, inb) if k],
               s=34, marker="o", facecolor="white", edgecolor=BLACK, linewidth=0.9,
               zorder=3)
    ax.scatter([a for a, k in zip(x, inb) if not k], [b for b, k in zip(y, inb) if not k],
               s=38, marker="^", facecolor=BLACK, edgecolor=BLACK, linewidth=0.6, zorder=3)
    ax.set_xlim(5 * int(min(x) / 5) - 2, 5 * int(max(x) / 5 + 1) + 2)
    ax.set_ylim(5 * int(min(y) / 5) - 2, 5 * int(max(y) / 5 + 1) + 2)
    ax.set_xlabel(f"Rebuilt partial score, {rule} (points; maximum {100 - mp})")
    ax.set_ylabel("Published State TB Score, 2023 (points)")
    n = len(inb)
    ax.legend(handles=[
        Patch(facecolor=PALE, edgecolor="none",
              label=f"Admissibility band: published {MINUS} rebuilt from 0 to {mp} points"),
        Line2D([], [], color=DARK, ls="--", lw=0.8, label="Published = rebuilt"),
        Line2D([], [], color=DARK, ls=":", lw=0.8, label=f"Published = rebuilt + {mp}"),
        Line2D([], [], marker="o", ls="", markerfacecolor="white", markeredgecolor=BLACK,
               label="Inside the band"),
        Line2D([], [], marker="^", ls="", markerfacecolor=BLACK, markeredgecolor=BLACK,
               label="Outside the band"),
    ], loc="upper left", frameon=False)
    fig.tight_layout()
    save(fig, "figure1")
    excl = ", ".join(sel["excluded"])
    return (f"Figure 1. One point per state or union territory (n = {n}); {excl} not "
            f"plotted (not computable). x: partial score under {rule} from indicators "
            f"{', '.join(map(str, sel['available_indicators']))}; y: India TB Report 2024, "
            f"Table 11.2. Shaded: published {MINUS} rebuilt between 0 and {mp} points "
            f"(indicators {', '.join(map(str, sel['missing_indicators']))} missing).")


# --------------------------------------------------------------------------------------
# Figure 2: Q2, share of draws in which each top- or bottom-fifth state stays there
# --------------------------------------------------------------------------------------
def figure2() -> str:
    sel = selection()
    rule = sel["chosen"]
    rows = [r for r in read_csv(ROOT / "outputs" / "q2_2023_fifths.csv")
            if r["rule"] == rule and r["base_fifth"] in ("top", "bottom")]
    share = {(r["state"], r["setting"]): 100 * float(r["share_stays"]) for r in rows}
    fifth = {r["state"]: r["base_fifth"] for r in rows}
    settings = ["c63", "alpha1"]
    assert {r["setting"] for r in rows} == set(settings)
    order = []
    for f in ("top", "bottom"):
        st = sorted((s for s in fifth if fifth[s] == f),
                    key=lambda s: (-share[(s, "c63")], -share[(s, "alpha1")], s))
        order.append((f, st))
    labels, ypos, y = [], [], 0.0
    group_y = {}
    for f, st in order:
        group_y[f] = y
        y += 0.9
        for s in st:
            labels.append(s)
            ypos.append(y)
            y += 1.0
        y += 0.6
    h = 0.38
    fig, ax = plt.subplots(figsize=(6.5, 6.4))
    style = {"c63": dict(color=DARK, edgecolor=BLACK, hatch=None),
             "alpha1": dict(color="white", edgecolor=BLACK, hatch="////")}
    for k, s_ in enumerate(settings):
        vals = [share[(s, s_)] for s in labels]
        ax.barh([p + (k - 0.5) * h for p in ypos], vals, height=h, linewidth=0.6,
                **style[s_])
    ax.set_yticks(ypos, labels)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("Weight draws in which the state stays in its base fifth (%)")
    ax.tick_params(axis="y", length=0)
    n_f = len(order[0][1])
    names = {"top": "Top fifth of the base ranking", "bottom": "Bottom fifth of the base ranking"}
    for f, gy in group_y.items():
        ax.text(-0.02, gy + 0.1, names[f], transform=ax.get_yaxis_transform(), ha="right",
                va="center", fontweight="bold")
    draws = next(r for r in read_csv(ROOT / "outputs" / "q2_2023_summary.csv")
                 if r["rule"] == rule and r["setting"] == "c63")["note"].split(";")[0]
    draws = f"{int(draws.split()[0]):,} draws"
    ax.legend(handles=[
        Patch(facecolor=DARK, edgecolor=BLACK, label="Weights near CTD's (c = 63)"),
        Patch(facecolor="white", edgecolor=BLACK, hatch="////",
              label="Weights spread widely (α = 1 for each indicator)"),
    ], loc="upper center", bbox_to_anchor=(0.45, -0.09), ncol=1, frameon=False)
    fig.tight_layout()
    save(fig, "figure2")
    return (f"Figure 2. Rule {rule}; {n_f} states in each base fifth; {draws} per setting "
            f"(outputs/q2_2023_fifths.csv, share_stays).")


# --------------------------------------------------------------------------------------
# Figure 3: Q3, survey-unit score against prevalence with its 95% CI
# --------------------------------------------------------------------------------------
def figure3() -> str:
    sel = selection()
    rule = sel["chosen"]
    units = [u for u in read_csv(ROOT / "outputs" / "q3_2023_units.csv")
             if u["rule"] == rule and u["dropped"] == "0"]
    abbrev = {u["unit"]: u["unit_abbrev"].replace(",", "+")
              for u in read_csv(ROOT / "data" / "extracted" / "ntps_units.csv")}
    fig, ax = plt.subplots(figsize=(6.5, 5.4))
    order = sorted(units, key=lambda u: float(u["unit_score"]))
    dodge, pairs = {}, []
    for a_, b_ in zip(order, order[1:]):
        if float(b_["unit_score"]) - float(a_["unit_score"]) < DODGE_GAP:
            dodge[a_["unit"]], dodge[b_["unit"]] = -DODGE_PT, DODGE_PT
            pairs.append((abbrev[a_["unit"]], abbrev[b_["unit"]]))
    for kind, marker, face in (("state", "o", "white"), ("group", "s", BLACK)):
        us = [u for u in units if u["unit_type"] == kind]
        x = [float(u["unit_score"]) for u in us]
        y = [float(u["prevalence"]) for u in us]
        err = [[b - float(u["ci_low"]) for b, u in zip(y, us)],
               [float(u["ci_high"]) - b for b, u in zip(y, us)]]
        for xi, yi, lo_, hi_, u in zip(x, y, err[0], err[1], us):
            # bars of units closer than DODGE_GAP points are drawn DODGE_PT apart (display
            # offset only; markers stay at the true score)
            off = dodge.get(u["unit"], 0.0)
            tr = transforms.offset_copy(ax.transData, fig=fig, x=off, y=0, units="points")
            ax.errorbar([xi], [yi], yerr=[[lo_], [hi_]], fmt="none", ecolor=MID,
                        elinewidth=0.8, capsize=2, zorder=1, transform=tr)
        ax.scatter(x, y, marker=marker, s=34, facecolor=face, edgecolor=BLACK,
                   linewidth=0.9, zorder=3)
    for u in units:
        a = abbrev[u["unit"]]
        dx, dy, ha = LABEL_OFFSET.get(a, (4, 3, "left"))
        ax.annotate(a, (float(u["unit_score"]), float(u["prevalence"])), xytext=(dx, dy),
                    textcoords="offset points", color=BLACK, ha=ha)
    ax.set_xlabel(f"Rebuilt State TB Score, 2023 ({rule}, rescaled; points)")
    ax.set_ylabel("TB prevalence, age ≥15 y (per 100 000)")
    # bars drawn with an offset transform do not update the data limits: set them here
    ax.set_ylim(0, 50 * (int(max(float(u["ci_high"]) for u in units) / 50) + 1))
    ax.legend(handles=[
        Line2D([], [], marker="o", ls="", markerfacecolor="white", markeredgecolor=BLACK,
               label="Single state"),
        Line2D([], [], marker="s", ls="", markerfacecolor=BLACK, markeredgecolor=BLACK,
               label="State group (population-weighted score)"),
        Line2D([], [], color=MID, lw=0.8, label="95% confidence interval"),
    ], loc="lower left", frameon=False)
    fig.tight_layout()
    save(fig, "figure3")
    key = "; ".join(f"{abbrev[u['unit']]}, " + (u["unit"] if u["unit_type"] == "state" else
                    " + ".join(u["members_scored"].split(";")))
                    for u in sorted(units, key=lambda u: abbrev[u["unit"]]))
    nc = "; ".join(f"{abbrev[u['unit']]}: only {listing(u['members_scored'].split(';'))} "
                   f"scored; {listing(u['members_not_covered'].split(';'))} not covered by "
                   f"the survey" for u in units if u["members_not_covered"])
    dg = "; ".join(f"{a} and {b}" for a, b in pairs)
    return (f"Figure 3. {len(units)} ICMR National TB Prevalence Survey 2019–21 "
            f"reporting units (rule {rule}). Abbreviations as printed by the survey: {key}. "
            f"{nc}. Error bars of {dg} (scores less than {DODGE_GAP} points apart) are drawn "
            f"{2 * DODGE_PT:g} pt apart for legibility; the markers are at the true scores.")


def listing(items: list[str]) -> str:
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


DODGE_GAP = 0.3  # score points: closer error bars are drawn apart
DODGE_PT = 2.5  # display offset of each bar of such a pair, in points

# Label placement only (points in offset units, alignment), to avoid overprinting.
LABEL_OFFSET = {"TS": (-4, 3, "right"), "NE": (4, -9, "left"), "WB": (-4, 3, "right"),
                "MH+GA": (4, -9, "left")}


# --------------------------------------------------------------------------------------
# Figure 4: Q4, change 2022 -> 2023 per state with the +/- noise threshold
# --------------------------------------------------------------------------------------
def figure4() -> str:
    sel = selection()
    rule = sel["chosen"]
    rows = [r for r in read_csv(ROOT / "outputs" / "q4_2022_2023_states.csv")
            if r["rule"] == rule and r["primary"] == "1"]
    iset = {r["indicator_set"] for r in rows}
    assert len(iset) == 1
    iset = iset.pop()
    shown = [r for r in rows if r["threshold"]]
    dropped = [r["state"] for r in rows if not r["threshold"]]
    shown.sort(key=lambda r: float(r["change"]))
    fig, ax = plt.subplots(figsize=(6.5, 8.6))
    ys = list(range(len(shown)))
    for yv, r in zip(ys, shown):
        t = float(r["threshold"])
        ax.plot([-t, t], [yv, yv], color=LIGHT, lw=4.2, solid_capstyle="butt", zorder=1)
    exc = [r["exceeds"] == "1" for r in shown]
    ch = [float(r["change"]) for r in shown]
    ax.scatter([c for c, e in zip(ch, exc) if e], [y for y, e in zip(ys, exc) if e],
               marker="o", s=30, facecolor=BLACK, edgecolor=BLACK, zorder=3)
    ax.scatter([c for c, e in zip(ch, exc) if not e], [y for y, e in zip(ys, exc) if not e],
               marker="o", s=30, facecolor="white", edgecolor=BLACK, linewidth=0.9, zorder=3)
    ax.axvline(0, color=DARK, lw=0.7, zorder=0)
    ax.set_yticks(ys, [r["state"] + (" †" if r["ut"] == "1" else "") for r in shown])
    ax.tick_params(axis="y", length=0)
    ax.set_ylim(-0.8, len(shown) - 0.2)
    ax.set_xlabel(f"Change in rebuilt score, 2022 to 2023 ({rule}; points)")
    ax.legend(handles=[
        Line2D([], [], color=LIGHT, lw=4.2, label=f"± noise threshold ({Z975:.2f} SE of the change)"),
        Line2D([], [], marker="o", ls="", markerfacecolor=BLACK, markeredgecolor=BLACK,
               label="Change exceeds noise"),
        Line2D([], [], marker="o", ls="", markerfacecolor="white", markeredgecolor=BLACK,
               label="Change within noise"),
    ], loc="upper center", bbox_to_anchor=(0.4, -0.06), frameon=False)
    fig.tight_layout()
    save(fig, "figure4")
    return (f"Figure 4. Rule {rule}, indicators {iset.replace(',', ', ')}, rescaled; "
            f"{len(shown)} states and union territories († union territory); "
            f"{', '.join(dropped)} not plotted (standard error not computable in 2023).")


def main() -> int:
    notes = [figure1(), figure2(), figure3(), figure4()]
    (OUT / "figure_notes.md").write_text(
        "<!-- Generated by exhibits/make_figures.py. Facts for the figure legends. -->\n\n"
        + "\n\n".join(notes) + "\n", encoding="utf-8", newline="\n")
    for p in sorted(OUT.iterdir()):
        print(f"wrote {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

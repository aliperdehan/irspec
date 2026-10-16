"""The matplotlib backend: the figure list drawn without TeX.

    irspec plot DIR --backend matplotlib --formats png,svg-text,pdf

reads DIR/figures.json (written by `irspec session`; or a path to any such
file) and writes one picture per spectrum into DIR/figures/matplotlib/. It
draws the same figure as the TeX pipeline (geometry in layout.py: the same axis
box, x axis, y limits, trace, peak labels and leader ticks) from the same plain
CSVs and peak lists, so the two agree on everything but the y tick spacing and
antialiasing. It needs matplotlib (`pip install irspec[matplotlib]`) and no TeX.

Formats: png, tiff, pdf, svg (text as outlines, draws the same anywhere),
svg-text (labels stay <text>, editable; the font must be installed where it is
opened). Fonts: STIX Two Text when matplotlib can find it, else the STIXGeneral
that ships with matplotlib; which one was used is printed.
"""
import argparse
import os
import sys

import numpy as np

from . import layout
from .export import ExportError, parse_formats, stems_of
from .figure import FIGURES_NAME, Figure, read_figures

FORMATS = ("png", "tiff", "pdf", "svg", "svg-text")
EXT = {"png": ".png", "tiff": ".tiff", "pdf": ".pdf", "svg": ".svg", "svg-text": ".svg"}
SUFFIX = {"svg-text": "_text"}
# Unhinted text: with hinting on, glyph advances are rounded to whole pixels and
# an 8 pt label comes out 9% wider than TeX's (measured: 23.8 pt against 21.7;
# unhinted, 21.76).
RC = {"text.hinting": "none"}


def _pyplot():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        raise ExportError("matplotlib is not installed: pip install matplotlib "
                          "(or pip install 'irspec[matplotlib]')")
    return matplotlib, plt


def pick_font():
    """(family, note): STIX Two Text if matplotlib finds it, else STIXGeneral."""
    from matplotlib import font_manager as fm
    for fam in ("STIX Two Text", "STIXGeneral"):
        try:
            path = fm.findfont(fm.FontProperties(family=fam), fallback_to_default=False)
        except ValueError:
            continue
        return fam, f"{fam} ({os.path.basename(path)})"
    return "DejaVu Serif", "DejaVu Serif (no STIX font found)"


def read_plain(path):
    a = np.genfromtxt(path, delimiter=",", skip_header=1)
    return a[:, 0], a[:, 1]


def draw(fig: Figure, folder, size=layout.DEFAULT_SIZE, caption=True, family=None):
    """One Figure -> a matplotlib Figure. `folder` is what fig.csv is relative to."""
    matplotlib, plt = _pyplot()
    from matplotlib.ticker import FixedLocator, FuncFormatter, MultipleLocator
    family = family or pick_font()[0]
    x, y = layout.window(*read_plain(os.path.join(folder, fig.csv)))
    lo, hi = layout.ylimits(y, fig.ymin)
    w, h = size
    out = plt.figure(figsize=size)
    ax = out.add_axes([0.85 / w, 1.0 / h, 1 - 0.95 / w, 1 - 1.1 / h])
    mono = layout.TEXT_PT
    ax.plot(x, y, color=layout.TRACE_COLOR, lw=layout.TRACE_PT, solid_joinstyle="round",
            solid_capstyle="butt", zorder=2)
    ax.set_xlim(*layout.XLIM)
    ax.set_ylim(lo, hi)
    ax.xaxis.set_major_locator(FixedLocator(np.arange(4000, 999, -layout.X_MAJOR)))
    ax.xaxis.set_minor_locator(MultipleLocator(layout.X_MINOR))
    ax.yaxis.set_major_locator(FixedLocator(layout.y_ticks(lo, hi)))
    fmt = FuncFormatter(lambda v, _: layout.fmt_number(v))
    ax.xaxis.set_major_formatter(fmt)
    ax.yaxis.set_major_formatter(fmt)
    ax.tick_params(which="major", direction="out", length=layout.MAJOR_TICK_PT, width=0.2,
                   top=True, right=True, labelsize=mono, pad=3)
    ax.tick_params(which="minor", direction="out", length=layout.MINOR_TICK_PT, width=0.2,
                   top=True, bottom=True)
    for s in ax.spines.values():
        s.set_linewidth(layout.FRAME_PT)
    ax.set_xlabel("Wavenumber / cm⁻¹", fontsize=mono, labelpad=6)
    ax.set_ylabel(fig.axis, fontsize=mono, labelpad=8)
    ax.set_axisbelow(False)

    for px, ly in fig.peaks:
        if not (min(layout.XLIM) <= px <= max(layout.XLIM)):
            continue
        ax.plot([px, px], [ly, ly + layout.LEADER_UNITS], color=layout.TICK_COLOR,
                lw=layout.TICK_PT, solid_capstyle="butt", zorder=3)
        ax.text(px, ly, f"{px:.1f}", rotation=90, ha="center", va="top",
                fontsize=layout.LABEL_PT, zorder=4, clip_on=True,
                bbox=dict(boxstyle="square,pad=0.125", fc=(1, 1, 1, 0.85), ec="none"))
    if caption and fig.title:
        out.text(0.5, 0.22 / h, fig.title, ha="center", va="bottom", style="italic",
                 fontsize=layout.CAPTION_PT)
    for t in out.findobj(matplotlib.text.Text):
        t.set_fontfamily(family)
    return out


def render(path, formats, outdir=None, size=layout.DEFAULT_SIZE, dpi=300, caption=True):
    """Draw every figure in `path` (a figures.json, or a session folder) in each
    of `formats`; returns the written paths."""
    matplotlib, plt = _pyplot()
    if os.path.isdir(path):
        path = os.path.join(path, FIGURES_NAME)
    if not os.path.exists(path):
        raise ExportError(f"{path} not found: run `irspec session DIR` first")
    figures, folder = read_figures(path)
    outdir = outdir or os.path.join(folder, "figures", "matplotlib")
    os.makedirs(outdir, exist_ok=True)
    family, note = pick_font()
    print(f"matplotlib {matplotlib.__version__}, font: {note}")
    written = []
    for fig, stem in zip(figures, stems_of(figures)):
        for fmt in formats:
            f = draw(fig, folder, size, caption, family)
            dest = os.path.join(outdir, stem + SUFFIX.get(fmt, "") + EXT[fmt])
            kw = {}
            rc = {**RC, "svg.fonttype": "none" if fmt == "svg-text" else "path"}
            if fmt == "png":
                kw = dict(dpi=dpi, format="png")
            elif fmt == "tiff":
                kw = dict(dpi=dpi, format="tiff", pil_kwargs={"compression": "tiff_lzw"})
            elif fmt == "pdf":
                kw = dict(format="pdf")
                rc["pdf.fonttype"] = 42
            else:
                kw = dict(format="svg")
            with matplotlib.rc_context(rc):
                f.savefig(dest, **kw)
            plt.close(f)
            written.append(dest)
    return written


def parse_size(text):
    try:
        w, h = (float(v) for v in text.lower().split("x"))
        assert w > 1 and h > 1
        return w, h
    except Exception:
        raise ExportError(f"--size needs WIDTHxHEIGHT in inches, e.g. 10x6.6; got {text!r}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="irspec plot --backend matplotlib", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("session", help="a session folder, or its figures.json")
    ap.add_argument("--formats", default="png", help="comma list of: " + ", ".join(FORMATS))
    ap.add_argument("--out", default=None, help="folder (default: DIR/figures/matplotlib)")
    ap.add_argument("--size", default="10x6.6", help="inches, WIDTHxHEIGHT (default 10x6.6)")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--no-caption", action="store_true", help="leave the title off the picture")
    a = ap.parse_args(argv)
    formats = parse_formats(a.formats, FORMATS)
    for p in render(a.session, formats, a.out, parse_size(a.size), a.dpi, not a.no_caption):
        print(f"wrote {p}")


if __name__ == "__main__":
    main()

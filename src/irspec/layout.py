"""The geometry every drawing backend shares, so a spectrum looks the same
whichever one draws it. The numbers are measured on the TeX figure (the
reference): the PDF of the author's phenacetin spectrum and four more y ranges
made from it, frame and tick-label positions read with pdfplumber. The R script
(data/irspec.R) repeats these constants; tests/test_backends.py compares them.

What is the same as the TeX figure: the axis box, the x axis (4000 to 650, major
every 500, minor every 100, labels "4,000"), the trace (0.5 pt, #B03A2E), the
peak labels (8 pt, rotated, hanging below their label_y, a 3-unit grey leader
tick up to the curve), where the y limits fall. What is not: tick spacing on y
(pgfplots' rule is its own; here the smallest 1-2-5 step giving at most 12
intervals) and, by a hair, antialiasing.
"""
import math

import numpy as np

from . import kinds

# The IR kind's frame (kinds.IR holds the numbers; these names are kept for the R script's test
# and the callers that draw IR only). Each function below takes a kind, IR by default.
XLIM = kinds.IR.xlim             # drawn reversed: high wavenumber on the left
X_MAJOR, X_MINOR = 500.0, kinds.IR.x_minor
LOWER_PAD, UPPER_PAD = kinds.IR.pad
# frame bottom = bottom - LOWER_PAD x range  (measured: 0.0984-0.0985 on five ranges)
# frame top    = top    + UPPER_PAD x range  (measured: 0.0016-0.0018)
TRACE_COLOR = "#B03A2E"          # nulabreport's nuirred
TRACE_PT = 0.5
TICK_COLOR = "#ACACAC"           # TeX gray!65
TICK_PT = 0.4                    # TeX `thin`
LEADER_UNITS = 3.0               # the leader tick's length, in y units
LABEL_PT = 8.0                   # \scriptsize at 12 pt
TEXT_PT = 12.0                   # tick labels, axis labels
CAPTION_PT = 10.0
FRAME_PT = 0.4
MAJOR_TICK_PT, MINOR_TICK_PT = 4.2, 2.1   # measured: 4.2 pt major ticks in the PDF
MAX_Y_INTERVALS = 12
DEFAULT_SIZE = (10.0, 6.6)       # inches, the picture files' own size


def window(x, y, kind=kinds.IR):
    """The part of the spectrum the figure shows: the kind's default frame (IR: 650 to 4000 cm-1)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    m = (x >= min(kind.xlim)) & (x <= max(kind.xlim)) & np.isfinite(y)
    return x[m], y[m]


def xlimits(xmin=None, xmax=None, kind=kinds.IR):
    """(left, right) of the x axis: the figure's own `xmin` and `xmax` (a crop), else the kind's
    xlim, in the kind's direction (IR, reversed: (xmax, xmin), high wavenumber on the left). For
    IR the ticks need no change: the majors are the XLIM ones that fall inside, the minors every
    100 (measured on the TeX figure for two crops, 2026-11-10)."""
    lo = min(kind.xlim) if xmin is None else float(xmin)
    hi = max(kind.xlim) if xmax is None else float(xmax)
    if not lo < hi:
        raise ValueError(f"xmin ({lo:g}) must be below xmax ({hi:g})")
    reversed_x = kind.xlim[0] > kind.xlim[1]   # IR: high wavenumber on the left
    return (hi, lo) if reversed_x else (lo, hi)


def ylimits(y, ymin=None, ymax=None, kind=kinds.IR):
    """(bottom, top) of the y axis. `y` is the windowed intensity; `ymin` and `ymax`, when given,
    are the lowest and the highest value the figure must show (the frame goes a little beyond
    both). The padding is the same fraction of the span from `ymin` to `ymax`, wherever they
    come from: measured on the TeX figure with ymax=100 and 110 (ymin -5), ymax=110 alone and
    ymin=20 with ymax=105, and the crop of x does not change it (TeX scales y on all the data)."""
    top = float(np.max(y)) if ymax is None else float(ymax)
    base = float(np.min(y)) if ymin is None else float(ymin)
    if not base < top:
        raise ValueError(f"ymin ({base:g}) must be below ymax ({top:g})")
    span = top - base
    lower, upper = kind.pad
    return base - lower * span, top + upper * span


def y_step(lo, hi):
    """Smallest 1-2-5 x 10^k step with at most MAX_Y_INTERVALS intervals."""
    span = hi - lo
    k = math.floor(math.log10(span / MAX_Y_INTERVALS)) if span > 0 else 0
    for m in (1, 2, 5, 10, 20, 50):
        step = m * 10.0 ** k
        if span / step <= MAX_Y_INTERVALS + 1e-9:
            return step
    return 10.0 ** (k + 2)


def y_ticks(lo, hi):
    step = y_step(lo, hi)
    first = math.ceil(lo / step - 1e-9)
    last = math.floor(hi / step + 1e-9)
    return [round(i * step, 10) for i in range(first, last + 1)]


def fmt_number(v):
    """Tick label: thousands comma, a real minus sign, no trailing .0."""
    s = f"{v:,.0f}" if float(v).is_integer() else f"{v:,g}"
    return s.replace("-", "−")

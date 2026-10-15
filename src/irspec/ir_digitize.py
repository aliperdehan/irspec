#!/usr/bin/env python3
"""ir_digitize.py -- an IR spectrum published only as a picture -> the house CSVs.

    python3 ir_digitize.py convert IMAGE --name NAME --out csv/NAME.csv \\
        --plain-out plain/NAME.csv [--overlay check.png] [--check PEAKS]
    ... --palleros --x-ticks 3500,3000,... --y-ends TOP:BOTTOM   (book figures, section 5)
    ... --omnic                                                  (OMNIC screenshots, section 6)

Self-contained, like this folder's other tools: what a future session needs
to reproduce a conversion is in this docstring, not only in a report's notes
or in chat. If you learn something new about an image layout, the fix goes
here.

===============================================================================
1. WHAT THIS IS FOR
===============================================================================
Some reference spectra exist only as images. The first case (LR6 prelab,
2026-09-28): trans-cinnamic acid has no IR on the NIST WebBook, and the
spectra ChemicalBook serves (e.g. chemicalbook.com/SpectrumEN_140-10-3_IR*.htm)
are SDBS plot images (GIF or JPEG, 715 x 553 px). This script reads the trace
off the image and writes the same two CSVs jdx_tool.py writes for a .jdx,
using jdx_tool.py's own writers, so \\irspectrum, spa_peaks.py and ir_corr.py
read the result like any other reference spectrum:

    --out        archival CSV: ';NAME;' header, semicolons, decimal commas,
                 descending wavenumber, fractional Transmittance (0-1), full
                 range -- the shape a WebBook %T .jdx converts to.
    --plain-out  plain CSV: 'wavenumber,intensity', ascending, %T (x100),
                 clipped >= 650 cm-1 at write time (jdx_tool.CLIP_CM).

Check the sampling line of the plot header before using one. SDBS publishes
several spectra per compound: 'NUJOL MULL' ones carry the mull's own C-H
bands (about 2950-2850, 1460, 1377 cm-1; for cinnamic acid, IR2, the two
strongest bands in the plot are Nujol), 'KBR DISC' ones do not. For
comparing against this lab's diamond-ATR spectra, prefer KBr disc or a
neat/ATR spectrum. Neither is ATR: ATR band intensities grow towards low
wavenumber and bands can sit a few cm-1 lower.

===============================================================================
2. CALIBRATION
===============================================================================
--layout sdbs (default). Detected, never assumed, from the image itself:
  - the plot box: the two long horizontal frame lines that enclose the
    trace (the top one is 100 %T, the bottom one 0 %T) and the two long
    vertical lines between them.
  - the x-axis: SDBS IR plots run 4000 -> 400 cm-1 with a change of scale
    at 2000 (4000-2000 at half the scale of 2000-400). The long tick marks
    just below the bottom frame line are every 500 cm-1: 4000, 3500, 3000,
    2500, 2000, 1500, 1000, 500. The script requires exactly eight, checks
    that the first four intervals are equal and the last three are equal
    (to within 1 px), and maps x piecewise-linearly through them. Below
    500 the 2000-400 scale is extrapolated to the right frame line (400).
  - the y-axis: the left frame's tick marks at 100, 50 and 0; the 50 tick
    must sit midway (to within 1 px), which checks the frame read.
  If any check fails, the script stops and says which, rather than
  guessing. Use --layout manual then.

--layout manual, for any other plot: give the box and at least two
calibration points per axis, in image pixels (0,0 = top left):
    --box LEFT,TOP,RIGHT,BOTTOM --x PX=WN --x PX=WN ... --y PX=T --y PX=T
Several --x points make a piecewise-linear map (for a scale change like
SDBS's). T is in %T. Only %T plots are supported: an absorbance plot would
need its own y-direction and is refused rather than silently inverted.

Resolution is set by the image. On a 715 px SDBS plot one pixel is 7.6 cm-1
above 2000 and 3.8 cm-1 below it, and 0.31 %T. Two bands closer than about
10 cm-1 above 2000 (5 cm-1 below) merge into one trough; nothing can recover
that from the picture.

===============================================================================
3. TRACE EXTRACTION
===============================================================================
Dark pixels (grey < --threshold, default 128) inside the box, not on the
frame lines. Connected blobs smaller than --min-blob pixels (default 6) are
dropped: JPEG speckle, not trace. In each pixel column the trace is a
vertical run of pixels: the line drawn from the previous column's value to
the next one's. The script writes TWO points per column, at the column
centre -/+ 0.25 px: the end of the run nearest the previous column's value
first, then the other end. That keeps every trough and peak tip exactly (a
single mean or median per column would cut them) while wavenumber still
strictly decreases. If a column holds more than one run (a crossing blob),
the one continuing the previous column is taken. Runs thicker than the line
(estimated from the flattest columns) are trimmed by half the line width at
each end, so a 2-3 px pen does not bias tips outwards.

===============================================================================
4. VERIFICATION (printed every run; exit status 2 if a check fails)
===============================================================================
  a. Calibration residuals (sdbs layout): the tick-spacing checks above.
  b. Trace fidelity: the digitized curve is drawn back onto a blank image
     of the same size and compared with the extracted trace pixels. Recall
     = share of trace pixels within 1 px of the redrawn curve; precision =
     the reverse. Both must be >= 0.98. --overlay PATH saves the original
     with the redrawn curve in red, for looking at.
  c. Optional peak check: --check "3067:52,3027:47,..." (wavenumber:%T,
     e.g. typed from the peak table SDBS prints under the plot) or
     --check-file with one 'wn %T' pair per line. Each listed peak is
     matched to the nearest digitized trough within 1.5 px (in cm-1 at
     that point of the axis). Matched peaks report their error; peaks with
     no trough that close are reported as unresolved at this resolution
     (usually a shoulder or one of a close pair), not as failures.
     The table is not read automatically: tesseract misreads SDBS's small
     bitmap font (2966 -> 24966), and the glyphs are resampled (106
     distinct pixel shapes for ten digits on IR2), so template matching is
     not reliable either. Type it, or read it off the image.

Validated 2026-09-28 on both SDBS No. 1997 (trans-cinnamic acid) images,
against their printed peak tables (35 peaks each, typed by hand):

                         IR1, KBr disc (JPEG)   IR2, Nujol mull (GIF)
    calibration          ticks 66/66/66/66, 131/132/132 px; ratio 1.995;
                         right frame 401 cm-1 (400 expected) -- both
    redraw recall/prec.  1.0000 / 1.0000         1.0000 / 1.0000
    peaks matched        32/35                   32/35
    |dwn| median, max    1.3, 6.3 cm-1           1.2, 10.3 cm-1
    unresolved           2671 (merged w. 2683),  3056 (merged w. 3066),
                         2614, 987               2966, 1620

The largest position errors (6-10 cm-1) are all in the broad acid O-H
envelope, 2500-2700 cm-1, where the trough bottoms are flat over several
pixels at 7.6 cm-1/px; sharp bands agree to 0-3 cm-1.

SDBS's printed %T is NOT on its own plot's scale. On both images the
digitized troughs fit  plot %T = 1.035-1.046 x table %T + 0.1-0.9  with
~1 %T scatter (fitted on the peaks within 5 %T, which drops a few %T
digits that are ambiguous in the bitmap font: 5/6/8). The tool reproduces
the plot (redraw = 1.0000); expect the peak check's d%T to run about +2
on SDBS images for this reason, not as an error.

===============================================================================
5. --palleros (--layout palleros): the book's own spectra (Units 21, 22, ...)
===============================================================================
    python3 ir_digitize.py convert Palleros_Fig22-3_IR_methyl-trans-cinnamate.png --palleros \\
        --name METHYL_TRANS_CINNAMATE --x-ticks 3500,3000,2500,2000,1500,1000 \\
        --y-ends 72.70:24.50 --out csv/NAME.csv --plain-out plain/NAME.csv \\
        --overlay check.png --check "3027.1,2948.8,1717.2,..."
Input: the clean black-on-white figure palleros_figs.py writes (a Nicolet-style
plot: an L of axis lines, long x ticks at the labelled wavenumbers, five y
ticks, only the two end values printed on the y axis, band positions printed
vertically under the troughs).
  - deskew: the x axis line is fitted in 100 px windows; tilt over 0.05 degrees
    is rotated out first (Figs. 21.2 / 21.11 measure 0.18 / 0.28 degrees, 7-12 px
    across the width -- enough to push the bottom y tick off the axis). The
    overlay is of the levelled image. Fig. 22.3 is already level.
  - x: the ticks under the axis are found (dark in rows 6-10 below it, no wider
    than 12 px); --x-ticks gives their wavenumbers left to right and is
    REQUIRED -- tesseract misreads this plotter font (2500 -> 2900, 1000 -> 7).
    The count must match. Spacing is checked: constant, or one change of scale
    (Unit 21 plots run 2:1 at 2000 cm-1 like SDBS; Fig. 22.3 is linear).
    Mapping is piecewise linear through the ticks, so the 2.6 % non-square mask
    pixels do not matter.
  - y: the five tick marks left of the y axis must be equally spaced (3.5 %; the
    printed ones wander by ~1 %) and the lowest must sit on the x axis. --y-ends
    TOP:BOTTOM are the values printed at the two ends (e.g. 72.70:24.50). ASSUMED
    to belong to the top and bottom tick; there is no printed %T to check them
    against, so treat %T as good to the plot, not to the instrument.
  - trace: ink above the x axis and right of the y axis, keeping only blobs of at
    least --blob-frac (0.05) of the biggest one. The trace is one connected blob;
    band labels, their leader dashes (a gap separates them from the trough tip)
    and specks are not.
  - the pen is ~7 px (360 ppi). With the thin-pen rule (both ends of every
    column's ink, which keeps tips exact on SDBS/OMNIC lines) every one of the 7
    columns across a steep stroke spans the stroke's whole height and the
    polyline zigzags up and down it: a jagged, thick curve in \\irspectrum. For
    pen >= 4 px centreline() is used instead: trim the run by (pen-1)/2 -> the
    curve's vertical range within half a pen; its middle is the curve on a
    monotone stroke; at a spike tip (hi the largest of its neighbours, range
    > 1.5 px) the tip itself. One point per column, single valued. The redraw
    check allows half a pen of reach.
  - verification: --check "wn,wn,..." takes the band positions PRINTED under the
    troughs (read them off the figure; %T not needed, 'wn:%T' also accepted).
    Reading them is the point of the check: a misread digit shows up as a
    distant trough. Fig. 22.3's last band is printed 767.6 (it can be misread as
    787.6; the thin-pen rule found a shallow trough at 787 within 1 cm-1 and
    'confirmed' the wrong digit; the centreline finds the deep spike at 766 and
    a 787.6 label misses it by 21 cm-1).
  - --align (DEFAULT ON for --palleros when --check is given; --no-align): the
    plotter's tick marks and its pen path are offset from each other by a few
    pixels, and by a different amount per figure: the troughs sit 4.2 px
    (Fig. 22.3), 2.9 px (Fig. 21.2) and 0.4 px (Fig. 21.11) from where the ticks
    put the printed band positions. The printed positions are the instrument's
    own, so x is shifted by the median offset of the troughs that lie within
    8 px of a printed band (needs 4), and the shift and the scatter are printed.
    After that the check is no longer independent of the shift, only of the
    scatter, which is the accuracy: sharp bands within ~2 cm-1, broad ones
    (3027, 2949 in Fig. 22.3) within ~4, because a broad minimum of the plotted
    curve is not where the peak picker put the band.
  Validated 2026-10-06 against the printed band positions (tolerance half a pen):
        figure                     recall/prec.   shift          matched   |dwn| median, max
        22.3 methyl cinnamate IR   0.9918/1.0000  -5.6 cm-1 4.2px  10/11    0.9, 3.6 (2949 broad: unresolved)
        21.2 benzophenone IR       0.9909/0.9984  -3.5 cm-1 2.9px   7/7     0.5, 1.3
        21.11 cinnamaldehyde IR    0.9896/0.9982  +0.4 cm-1 0.4px   5/7     0.2, 1.5 (3028, 2742 unresolved:
                                                                              scatter 6.3 cm-1, labels likely misread)
  (Fig. 21.11's printed '2814.6' and '1675.8' are black boxes in the book's
  JBIG2 scan, so only the seven legible ones were listed.) Resolution 1.3 cm-1
  per pixel on a 3500-700 axis, 1.2-2.5 on 4000-500 (coarser above 2000).
  The earlier, thin-pen version reported 11/11, 7/7 and 7/7 within 1.9 cm-1;
  that was flattered by the zigzag (it put each tip at an arbitrary end of the
  plateau), not a better measurement.

===============================================================================
6. --omnic (--layout omnic): full-screen OMNIC screenshots (.bmp, 1600x900)
===============================================================================
    python3 ir_digitize.py convert "Org2_exp.15.3 acetaminophen.bmp" --omnic \\
        --name ACETAMINOPHEN --out csv/NAME.csv --plain-out plain/NAME.csv \\
        [--check "3324.94,3161.15,..."] [--overlay check.png]
For the instructor's authentic spectra that exist only as screenshots of
OMNIC's own window (LR1-2/ir/authentic-instructor/). Colour matters here, so
the RGB image is used, not just grey:
  - the trace is the pure red (255,0,0) line; the black peak labels,
    black axes, grey axis lines and the window chrome do not match it. The
    mask is limited to the plot (right of the y axis, above the x axis, as far
    as the x axis line runs -- which can be past the last major tick: the
    phenacetin plot has its last tick at 1000 cm-1 and runs to ~523).
  - the axes are GREY lines (192) with BLACK ticks: x major ticks every 500
    cm-1 just below the axis, one y tick per labelled value to the left.
  - the tick VALUES are read with tesseract from the labels: each label goes to
    its nearest tick and the labelled ticks must lie on one arithmetic
    progression (median of pairwise slopes; a clear majority must agree), which
    is extended to unlabelled ticks (the last x tick, 500, has no label).
    tesseract garbles some y labels (50 -> 5, -10 -> 10) -- they are reported
    and ignored, not trusted. If the majority rule fails: --x-first V --x-step S
    (value of the leftmost tick, change per tick, e.g. 4000 and -500) and
    --y-first / --y-step likewise (top tick, e.g. 100 and -10).
  - y: OMNIC puts the label text ~8 px above its tick; the TICK is the value.
  - Resolution is the screen's: 1455 px over 3500 cm-1 = 2.4 cm-1 per px, 0.2 %T
    per px. These are screenshots of a 1600x900 desktop, not the data; where
    the .SPA exists use spa_tool.py. Band positions here are the nearest pixel.
  Validated 2026-10-06 against OMNIC's own printed peak labels (the labels are
  OMNIC's peak picker on the real data):
        acetaminophen   recall/prec. 1.0000/1.0000, 22/22 matched, |dwn| median 1.7, max 2.7 cm-1
        phenacetin      1.0000/1.0000, 29/30 matched, median 1.0, max 3.5 (605.2 at the
                        very right edge: no trough that close)
  The errors are mostly negative (-2 cm-1 at 3300, ~0 at 800): about one pixel,
  from where OMNIC draws the line relative to its ticks. Not corrected.
  Not done: the printed peak labels are not read (rotated text, tesseract
  unreliable); give them to --check by hand.

Needs numpy and Pillow (both in the system python3 here); --omnic also uses
tesseract if it is installed (OCR of the tick labels, else --x-first etc.).
"""
import argparse
import os
import sys
from collections import deque

import numpy as np
from PIL import Image, ImageDraw

from . import jdx_tool  # noqa: E402  (house CSV writers)

SDBS_TICKS = [4000, 3500, 3000, 2500, 2000, 1500, 1000, 500]


class CalibrationError(Exception):
    pass


# ---------------------------------------------------------------------------
# calibration
# ---------------------------------------------------------------------------
def _runs(idx):
    """Consecutive integer runs in a sorted index array -> [(start, end)]."""
    if len(idx) == 0:
        return []
    out, s, p = [], idx[0], idx[0]
    for v in idx[1:]:
        if v != p + 1:
            out.append((s, p))
            s = v
        p = v
    out.append((s, p))
    return out


def find_box(dark):
    """Plot box = the two long vertical frame lines, and the long horizontal
    lines they end on. SDBS draws other full-width rules (header and table
    boxes), so the box is the horizontal pair the verticals span."""
    h, w = dark.shape
    cols = [c for c in range(w) if dark[:, c].sum() > 0.4 * h]
    vruns = _runs(np.array(cols))
    if len(vruns) < 2:
        raise CalibrationError("could not find two vertical frame lines")
    left, right = vruns[0][1], vruns[-1][0]
    # the longest run of the left frame line; its ends overshoot the box
    # (the 4000 tick continues it below), so the box is the first and last
    # full horizontal line inside that run
    a, b = max(_runs(np.where(dark[:, left])[0]), key=lambda r: r[1] - r[0])
    full = [r for r in range(a, b + 1) if dark[r, left:right + 1].mean() > 0.9]
    if len(full) < 2:
        raise CalibrationError("no pair of full horizontal frame lines on the left frame")
    return left, full[0], right, full[-1]


def sdbs_calibration(dark, box):
    left, top, right, bottom = box
    report = []
    # x: long ticks, the columns dark for 4+ px right below the frame
    below = dark[bottom + 1:bottom + 6, :]
    ticks = [c for c in range(left, right + 1) if below[:4, c].all()]
    ticks = [int(a) for a, _ in _runs(np.array(ticks))]
    if len(ticks) != 8:
        raise CalibrationError(f"expected 8 long x ticks (4000..500 every 500), found {len(ticks)} at {ticks}")
    if abs(ticks[0] - left) > 1:
        raise CalibrationError(f"first long tick at {ticks[0]}, frame at {left}: not a 4000 cm-1 start")
    d = np.diff(ticks)
    hi, lo = d[:4], d[4:]
    report.append(f"x ticks px {ticks}; 4000-2000 steps {[int(v) for v in hi]}, "
                  f"2000-500 steps {[int(v) for v in lo]}")
    if np.ptp(hi) > 1 or np.ptp(lo) > 1:
        raise CalibrationError("uneven tick spacing inside one scale segment")
    ratio = lo.mean() / hi.mean()
    report.append(f"scale ratio below/above 2000: {ratio:.3f} (SDBS: 2)")
    if abs(ratio - 2) > 0.05:
        raise CalibrationError(f"scale ratio {ratio:.3f}, expected 2: not the SDBS x-axis")
    px = list(ticks) + [right]
    per_px = 500 / lo.mean()
    wn = SDBS_TICKS + [500 - (right - ticks[-1]) * per_px]
    report.append(f"right frame = {wn[-1]:.0f} cm-1 (extrapolated; SDBS: 400)")
    # y: ticks on the left frame at 100 / 50 / 0
    ylines = [r for r in range(top, bottom + 1) if dark[r, left - 4:left].all()]
    yl = [a for a, _ in _runs(np.array(ylines))]
    mid = (top + bottom) / 2
    if not yl or min(abs(r - mid) for r in yl) > 1:
        raise CalibrationError(f"no 50 %T tick near row {mid:.1f} (left ticks at {yl})")
    report.append(f"y: 100 %T row {top}, 0 %T row {bottom}, 50 %T tick within 1 px of midpoint")
    return (np.array(px, float), np.array(wn, float)), (np.array([top, bottom], float), np.array([100.0, 0.0])), report


def parse_pairs(items, what):
    pts = []
    for it in items or []:
        try:
            a, b = it.split("=")
            pts.append((float(a), float(b)))
        except ValueError:
            sys.exit(f"--{what} {it!r}: expected PX=VALUE")
    if len(pts) < 2:
        sys.exit(f"--layout manual needs at least two --{what} points")
    pts.sort()
    return np.array([p for p, _ in pts]), np.array([v for _, v in pts])


def interp_extrap(v, xp, fp):
    """Piecewise-linear through (xp, fp), extended linearly past both ends."""
    v = np.asarray(v, float)
    out = np.interp(v, xp, fp)
    lo, hi = v < xp[0], v > xp[-1]
    out[lo] = fp[0] + (v[lo] - xp[0]) * (fp[1] - fp[0]) / (xp[1] - xp[0])
    out[hi] = fp[-1] + (v[hi] - xp[-1]) * (fp[-1] - fp[-2]) / (xp[-1] - xp[-2])
    return out


# ---------------------------------------------------------------------------
# tick-based layouts: palleros, omnic
# ---------------------------------------------------------------------------
def _centres(idx, maxw, lo=None):
    """Centres of the runs in a sorted index array no wider than maxw (wider
    runs are text or filled bars, not tick marks). Runs starting before `lo`
    are clipped to it (a tick butting against an axis line)."""
    out = []
    for a, b in _runs(np.asarray(idx)):
        if lo is not None and a < lo <= b:
            a = lo
        if b - a + 1 <= maxw:
            out.append((a + b) / 2)
    return out


def ocr_numbers(grey, box, scale=3, psm=11):
    """tesseract on a crop -> [(text, cx, cy)] in image pixels. Digits, '.'
    and '-' only. [] if tesseract is missing or reads nothing."""
    import shutil, subprocess, tempfile
    if not shutil.which("tesseract"):
        return []
    l, t, r, b = (int(v) for v in box)
    crop = Image.fromarray(grey[t:b, l:r]).resize(((r - l) * scale, (b - t) * scale), Image.LANCZOS)
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "c.png")
        crop.save(p)
        res = subprocess.run(["tesseract", p, "-", "--psm", str(psm), "-c",
                              "tessedit_char_whitelist=0123456789.-", "tsv"],
                             capture_output=True, text=True)
    out = []
    for line in res.stdout.splitlines()[1:]:
        f = line.split("\t")
        if len(f) == 12 and f[11].strip() and f[0] == "5":
            x, y, w_, h_ = (int(v) / scale for v in f[6:10])
            out.append((f[11].strip(), l + x + w_ / 2, t + y + h_ / 2))
    return out


def label_progression(ticks, labels, what):
    """Values for every tick from OCR'd labels: each label goes to its nearest
    tick; the labelled ticks must form an arithmetic progression (tick index
    -> value), which is then extended to unlabelled ticks. -> values array."""
    ticks = np.asarray(ticks, float)
    gap = np.median(np.diff(ticks))
    got = {}
    for text, pos in labels:
        try:
            v = float(text)
        except ValueError:
            continue
        k = int(np.argmin(np.abs(ticks - pos)))
        if abs(ticks[k] - pos) < abs(gap) * 0.5:
            got[k] = v
    if len(got) < 2:
        raise CalibrationError(f"{what}: OCR read fewer than 2 tick labels (got {sorted(got.items())}); "
                               f"give the values explicitly")
    ks = np.array(sorted(got))
    vs = np.array([got[k] for k in ks])
    # tesseract drops or garbles the odd label (50 -> 5, -10 -> 10), so the
    # progression is the one most labels agree on (median of pairwise slopes),
    # and it is only accepted if a clear majority of the labels sit on it
    sl = [(vs[j] - vs[i]) / (ks[j] - ks[i]) for i in range(len(ks)) for j in range(i + 1, len(ks))]
    slope = float(np.median(sl))
    icpt = float(np.median(vs - slope * ks))
    ok = np.abs(ks * slope + icpt - vs) <= 0.01 * abs(slope) + 1e-9
    if ok.sum() < max(3, 0.6 * len(ks)):
        raise CalibrationError(f"{what}: OCR'd labels {sorted(got.items())} do not agree on one "
                               f"arithmetic progression; give the values explicitly")
    slope, icpt = np.polyfit(ks[ok], vs[ok], 1)
    if (~ok).any():
        print(f"  note   {what}: {int((~ok).sum())} OCR label(s) off the progression, ignored: "
              f"{[(int(k), v) for k, v, g in zip(ks, vs, ok) if not g]}")
    return np.round(np.arange(len(ticks)) * slope + icpt, 6) + 0.0


def components(mask):
    """8-connected components of a bool mask -> list of (rows, cols) arrays."""
    h, w = mask.shape
    seen = np.zeros_like(mask)
    out = []
    for r0, c0 in zip(*np.nonzero(mask)):
        if seen[r0, c0]:
            continue
        comp, q = [], deque([(r0, c0)])
        seen[r0, c0] = True
        while q:
            r, c = q.popleft()
            comp.append((r, c))
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < h and 0 <= cc < w and mask[rr, cc] and not seen[rr, cc]:
                        seen[rr, cc] = True
                        q.append((rr, cc))
        a = np.array(comp)
        out.append((a[:, 0], a[:, 1]))
    return out


def keep_big_components(mask, frac):
    """Keep components with at least `frac` of the largest one's pixels: the
    trace is one big blob; band labels, leader dashes and specks are not."""
    comps = components(mask)
    if not comps:
        return mask
    big = max(len(c[0]) for c in comps)
    out = np.zeros_like(mask)
    for rr, cc in comps:
        if len(rr) >= frac * big:
            out[rr, cc] = True
    return out


def deskew_by_xaxis(grey, report):
    """Palleros figures were scanned slightly tilted (0.2-0.3 degrees, 6-8 px
    over the width, enough to put the bottom y tick off the axis line). The
    x axis line is the reference: fit its row against column in windows over
    the middle of the plot, and if the tilt exceeds 0.05 degrees rotate the
    whole figure so it is level (bicubic, then re-thresholded to 1 bit).
    -> grey (rotated or as given)."""
    dark = grey < 128
    h, w = dark.shape
    approx = int(np.argmax(dark[int(h * 0.55):].sum(1))) + int(h * 0.55)
    xs, ys = [], []
    for c0 in range(int(w * 0.15), int(w * 0.85) - 100, 100):
        sub = dark[max(approx - 40, 0):approx + 40, c0:c0 + 100].sum(1)
        if sub.max() < 90:
            continue
        r = np.arange(len(sub)) + max(approx - 40, 0)
        top = sub > 0.8 * sub.max()
        xs.append(c0 + 50); ys.append(r[top].mean())
    if len(xs) < 6:
        return grey
    slope = np.polyfit(xs, ys, 1)[0]
    ang = float(np.degrees(np.arctan(slope)))
    if abs(ang) < 0.05:
        return grey
    im = Image.fromarray((dark * 255).astype(np.uint8)).rotate(ang, resample=Image.BICUBIC, fillcolor=0)
    out = np.where(np.array(im) > 127, 0, 255).astype(np.uint8)
    report.append(f"deskew: x axis tilted {ang:+.2f} degrees ({slope * w:+.1f} px over the width); "
                  f"rotated {ang:+.2f} degrees")
    return out


def palleros_layout(grey, args, report):
    """Palleros (Nicolet-style) IR plot, black ink on white: an L of axis
    lines, long tick marks under the x axis at the labelled wavenumbers, five
    tick marks on the y axis (top, 3 inside, bottom) and only the two end
    values printed there. -> box, xcal, ycal, trace mask."""
    grey = deskew_by_xaxis(grey, report)
    dark = grey < 128
    h, w = dark.shape
    rows = _runs(np.where(dark.sum(1) > 0.5 * w)[0])
    cols = _runs(np.where(dark.sum(0) > 0.4 * h)[0])
    if not rows or not cols:
        raise CalibrationError("no x-axis line (a dark row over half the width) or y-axis line "
                               "(a dark column over 40% of the height)")
    ax_t, ax_b = rows[-1]
    ay_l, ay_r = cols[0]
    report.append(f"axes: x line rows {ax_t}-{ax_b}, y line columns {ay_l}-{ay_r}")

    # x ticks: dark in every one of the rows 6..10 below the axis line
    band = dark[ax_b + 6:ax_b + 11].all(0)
    xt = _centres(np.where(band)[0], 12, lo=ay_r + 1)
    xt = [c for c in xt if c > ay_r]
    if args.x_ticks:
        vals = [float(v) for v in args.x_ticks.split(",")]
        if len(vals) != len(xt):
            raise CalibrationError(f"--x-ticks gives {len(vals)} values but {len(xt)} tick marks "
                                   f"were found under the axis, at px {[round(c) for c in xt]}")
        vals = np.array(vals)
    else:
        raise CalibrationError(f"--x-ticks is required: the wavenumbers printed under the {len(xt)} tick "
                               f"marks, left to right (tesseract misreads this plotter font -- 2500 as "
                               f"2900, 1000 as 7 -- so the labels are not read automatically)")
    if np.any(np.diff(vals) >= 0):
        raise CalibrationError(f"x tick values must decrease left to right, got {vals.tolist()}")
    sp = np.diff(xt)
    seg = [f"{abs(v):.0f}" for v in np.diff(vals)]
    report.append(f"x: {len(xt)} ticks at px {[round(c) for c in xt]} = {vals.astype(int).tolist()} cm-1; "
                  f"px per step {[round(v, 1) for v in sp]}")
    # a scale change shows up as spacing proportional to the wavenumber step;
    # anything else (uneven within a constant-step run) is a misread
    dens = sp / np.abs(np.diff(vals))
    uniq = []
    for d in dens:
        if not uniq or abs(d - uniq[-1][0]) > 0.02 * uniq[-1][0]:
            uniq.append([d, 1])
        else:
            uniq[-1][1] += 1
    report.append("x scale segments (px per cm-1 x steps): " +
                  ", ".join(f"{d:.3f} x{n}" for d, n in uniq))
    if len(uniq) > 2:
        raise CalibrationError(f"x spacing changes scale {len(uniq) - 1} times; expected at most one")

    # y ticks on the left of the y line
    if not args.y_ends:
        raise CalibrationError("--y-ends TOP:BOTTOM is required (the two values printed at the "
                               "top and bottom of the y axis, e.g. 72.70:24.50)")
    try:
        ytop, ybot = (float(v) for v in args.y_ends.split(":"))
    except ValueError:
        raise CalibrationError("--y-ends expects TOP:BOTTOM, e.g. 72.70:24.50")
    yb = dark[:, max(ay_l - 8, 0):max(ay_l - 3, 1)].all(1)
    yt = _centres(np.where(yb[:ax_b + 8])[0], 10)
    if len(yt) < 3:
        raise CalibrationError(f"found only {len(yt)} y tick marks left of the y axis")
    ys = np.diff(yt)
    report.append(f"y: {len(yt)} ticks at rows {[round(c) for c in yt]}; spacing {[round(v, 1) for v in ys]} px")
    if np.ptp(ys) > 0.035 * ys.mean():
        raise CalibrationError("y ticks not equally spaced (within 3.5%)")
    if abs(yt[-1] - (ax_t + ax_b) / 2) > 4:
        raise CalibrationError(f"bottom y tick at row {yt[-1]:.0f} is not on the x axis (rows {ax_t}-{ax_b})")
    ycal = (np.array([yt[0], yt[-1]]), np.array([ytop, ybot]))
    report.append(f"y: top tick = {ytop} %T, bottom tick (on the x axis) = {ybot} %T "
                  f"(assumed: only the end values are printed)")
    xcal = (np.array(xt), vals)

    region = np.zeros_like(dark)
    region[:ax_t - 1, ay_r + 2:] = dark[:ax_t - 1, ay_r + 2:]
    mask = keep_big_components(region, args.blob_frac)
    box = (ay_r, int(yt[0]), w - 1, int(yt[-1]))
    return box, xcal, ycal, mask, Image.fromarray(grey)


def omnic_layout(rgb, args, report):
    """OMNIC full-screen screenshot: grey axis lines, black tick marks (major
    every 500 cm-1 below the x axis, one per labelled y value to the left),
    trace in pure red, peak labels in black. -> box, xcal, ycal, trace mask."""
    grey = rgb.sum(2) // 3
    h, w, _ = rgb.shape
    nonwhite = rgb.sum(2) < 700
    black = rgb.sum(2) < 100
    # x axis: the long grey/black row in the lower part of the window
    cand = np.where(nonwhite[:, 100:w - 40].sum(1) > 0.6 * (w - 140))[0]
    cand = cand[cand > h * 0.5]
    rows = _runs(cand)
    if not rows:
        raise CalibrationError("no x-axis line found (a long non-white row in the lower half)")
    ax_t, ax_b = rows[0]
    # y axis: the long non-white column left of the plot
    ccand = np.where(nonwhite[int(h * 0.2):ax_t, :int(w * 0.2)].sum(0) > 0.6 * (ax_t - h * 0.2))[0]
    if len(ccand) == 0:
        raise CalibrationError("no y-axis line found")
    ay_l, ay_r = _runs(ccand)[-1]
    report.append(f"axes: x line rows {ax_t}-{ax_b}, y line columns {ay_l}-{ay_r}")

    xt = _centres(np.where(black[ax_b + 1:ax_b + 4].all(0))[0], 4)
    yt = _centres(np.where(black[:, max(ay_l - 3, 0):ay_l].all(1))[0], 4)
    if len(xt) < 2 or len(yt) < 2:
        raise CalibrationError(f"found {len(xt)} x tick marks and {len(yt)} y tick marks")
    xt = [c for c in xt if c >= ay_l]
    ya, yb_ = max(_runs(np.where(nonwhite[:, ay_l])[0]), key=lambda r: r[1] - r[0])
    yt = [c for c in yt if ya - 3 <= c <= yb_ + 3]
    if len(xt) < 2 or len(yt) < 2:
        raise CalibrationError(f"found {len(xt)} x tick marks and {len(yt)} y tick marks")

    g8 = grey.astype(np.uint8)
    if args.x_first is not None and args.x_step is not None:
        xv = args.x_first + args.x_step * np.arange(len(xt))
    else:
        lab = ocr_numbers(g8, (ay_l - 20, ax_b + 8, w - 40, ax_b + 28), scale=4)
        xv = label_progression(xt, [(t, cx) for t, cx, _ in lab], "x ticks")
    if args.y_first is not None and args.y_step is not None:
        yv = args.y_first + args.y_step * np.arange(len(yt))
    else:
        lab = ocr_numbers(g8, (max(ay_l - 60, 0), min(yt) - 14, ay_l - 4, max(yt) + 14), scale=4, psm=6)
        yv = label_progression(yt, [(t, cy) for t, _, cy in lab], "y ticks")
    if np.any(np.diff(xv) >= 0) or np.any(np.diff(yv) >= 0):
        raise CalibrationError(f"tick values must decrease left to right and top to bottom: "
                               f"x {xv.tolist()}, y {yv.tolist()}")
    for what, tk, v in (("x", xt, xv), ("y", yt, yv)):
        sp = np.diff(tk)
        if np.ptp(sp) > 0.02 * sp.mean() + 1.5:
            raise CalibrationError(f"{what} tick spacing uneven: {sp.tolist()}")
    report.append(f"x: {len(xt)} major ticks at px {[round(c) for c in xt]} = {xv.tolist()} cm-1")
    report.append(f"y: {len(yt)} ticks at rows {[round(c) for c in yt]} = {yv.tolist()} %T")

    red = (rgb[..., 0] > 200) & (rgb[..., 1] < 90) & (rgb[..., 2] < 110)
    region = np.zeros_like(red)
    top = max(int(yt[0]) - 8, 0)
    # the axis line can run past the last major tick (phenacetin: last tick
    # 1000 cm-1, line to ~650), and so does the trace
    xr = int(np.where(nonwhite[ax_t, 100:w - 20])[0].max()) + 100
    region[top:ax_t - 1, ay_r + 2:xr + 1] = red[top:ax_t - 1, ay_r + 2:xr + 1]
    mask = keep_big_components(region, args.blob_frac)
    box = (ay_r, top, xr, ax_t)
    return box, (np.array(xt), xv), (np.array(yt), yv), mask, None


# ---------------------------------------------------------------------------
# trace
# ---------------------------------------------------------------------------
def drop_small_blobs(mask, min_size):
    h, w = mask.shape
    seen = np.zeros_like(mask)
    keep = np.zeros_like(mask)
    for r0, c0 in zip(*np.nonzero(mask)):
        if seen[r0, c0]:
            continue
        comp, q = [], deque([(r0, c0)])
        seen[r0, c0] = True
        while q:
            r, c = q.popleft()
            comp.append((r, c))
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < h and 0 <= cc < w and mask[rr, cc] and not seen[rr, cc]:
                        seen[rr, cc] = True
                        q.append((rr, cc))
        if len(comp) >= min_size:
            for r, c in comp:
                keep[r, c] = True
    return keep


def extract_trace(mask):
    """-> list of (col, row_entry, row_exit) in pixel coordinates, and the pen
    width. A thin pen (SDBS, OMNIC: 1-3 px) gives the two ends of each
    column's run, so every tip is kept. A thick pen (Palleros: ~7 px at 360
    ppi) needs another rule, see centreline()."""
    h, w = mask.shape
    col_runs = {c: _runs(np.nonzero(mask[:, c])[0]) for c in range(w)}
    # pen width: median run length over columns with one short run (flat bits)
    lens = [b - a + 1 for rs in col_runs.values() if len(rs) == 1 for a, b in rs]
    pen = int(np.percentile(lens, 20)) if lens else 1
    trim = (pen - 1) / 2
    if pen >= 4:
        sel, prev = [], None
        for c in range(w):
            rs = col_runs[c]
            if not rs:
                continue
            if prev is None:
                a, b = max(rs, key=lambda r: r[1] - r[0])
            else:  # the run whose middle continues the previous one
                a, b = min(rs, key=lambda r: abs((r[0] + r[1]) / 2 - prev))
            sel.append((c, a, b))
            prev = (a + b) / 2
        return centreline(sel, pen), pen
    pts, prev = [], None
    for c in range(w):
        rs = col_runs[c]
        if not rs:
            continue
        if prev is None:
            a, b = max(rs, key=lambda r: r[1] - r[0])
        else:
            a, b = min(rs, key=lambda r: min(abs(r[0] - prev), abs(r[1] - prev)))
        if b - a + 1 > pen:
            a, b = a + trim, b - trim
        else:
            a = b = (a + b) / 2
        entry, exit_ = (a, b) if prev is None or abs(a - prev) <= abs(b - prev) else (b, a)
        pts.append((c, entry, exit_))
        prev = exit_
    return pts, pen


def centreline(sel, pen):
    """Single-valued centreline of a thick pen. A stroke of width p swept along
    the curve covers, in each column, the curve's vertical range within half a
    pen to either side, widened by p/2: trimming the run by (p-1)/2 at both
    ends gives that range, [lo, hi]. Writing both ends as the column's points
    (what the thin-pen rule does) makes every one of the p columns across a
    steep stroke span the whole stroke height, and the polyline zigzags over it
    (jagged, thick curve). On a monotone stroke the middle of [lo, hi] IS the
    curve; only at a spike tip is it not (the range then covers both legs), so
    where hi is the largest of its neighbours (a trough tip) or lo the smallest
    (a peak tip) and the range is steep, the tip itself is used."""
    r = (pen - 1) / 2
    c = np.array([s[0] for s in sel], float)
    lo = np.array([s[1] for s in sel], float) + r
    hi = np.array([s[2] for s in sel], float) - r
    bad = hi < lo
    lo[bad] = hi[bad] = (lo[bad] + hi[bad]) / 2
    y = (lo + hi) / 2
    k = int(pen)
    for i in range(len(c)):
        j0, j1 = max(i - k, 0), min(i + k + 1, len(c))
        if hi[i] - y[i] > 1.5 and hi[i] >= hi[j0:j1].max():
            y[i] = hi[i]                      # trough tip (image y grows downward)
        elif y[i] - lo[i] > 1.5 and lo[i] <= lo[j0:j1].min():
            y[i] = lo[i]                      # peak tip
    return [(int(ci), yi, yi) for ci, yi in zip(c, y)]


def redraw(pts, shape):
    img = Image.new("1", (shape[1], shape[0]), 0)
    d = ImageDraw.Draw(img)
    xy = []
    for c, e, x in pts:
        xy += [(c, e), (c, x)]
    d.line(xy, fill=1, width=1)
    return np.array(img, bool)


def dilate(m, n=1):
    """n-pixel square dilation (the pen is wider than 1 px on the Palleros
    figures, so a trace pixel is 'covered' within half a pen of the centre)."""
    out = m.copy()
    for _ in range(n):
        m = out.copy()
        out[1:] |= m[:-1]; out[:-1] |= m[1:]
        m = out.copy()
        out[:, 1:] |= m[:, :-1]; out[:, :-1] |= m[:, 1:]
    return out


def troughs(xs, ys):
    """Local minima of a descending-x series, plateaus -> their middle."""
    out, i, n = [], 1, len(ys)
    while i < n - 1:
        j = i
        while j + 1 < n and ys[j + 1] == ys[i]:
            j += 1
        if ys[i - 1] > ys[i] and j + 1 < n and ys[j + 1] > ys[i]:
            k = (i + j) // 2
            out.append((xs[k], ys[k]))
        i = j + 1
    return out


def parse_check(spec, path):
    pairs = []
    if spec:
        for tok in spec.replace(" ", "").split(","):
            if tok:
                a, _, b = tok.partition(":")
                pairs.append((float(a), float(b) if b else None))
    if path:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.split("#")[0].split()
                if line:
                    pairs.append((float(line[0]), float(line[1]) if len(line) > 1 else None))
    return pairs


# ---------------------------------------------------------------------------
def cmd_convert(args):
    img = Image.open(args.image)
    rgb = np.array(img.convert("RGB")).astype(int)
    grey = np.array(img.convert("L"))
    dark = grey < args.threshold
    failed = False

    mask = base = None
    try:
        if args.layout == "sdbs":
            box = find_box(dark)
            xcal, ycal, report = sdbs_calibration(dark, box)
        elif args.layout == "palleros":
            report = []
            box, xcal, ycal, mask, base = palleros_layout(grey, args, report)
        elif args.layout == "omnic":
            report = []
            box, xcal, ycal, mask, base = omnic_layout(rgb, args, report)
        else:
            if not args.box:
                sys.exit("--layout manual needs --box LEFT,TOP,RIGHT,BOTTOM")
            box = tuple(int(v) for v in args.box.split(","))
            xcal, ycal = parse_pairs(args.x, "x"), parse_pairs(args.y, "y")
            report = ["manual calibration"]
    except CalibrationError as e:
        sys.exit(f"{args.image}: calibration failed: {e}\n(use --layout manual)")
    left, top, right, bottom = box
    print(f"{args.image}: {grey.shape[1]}x{grey.shape[0]} px, plot box l={left} t={top} r={right} b={bottom}")
    for line in report:
        print("  calib  " + line)

    if mask is None:
        mask = np.zeros_like(dark)
        mask[top + 1:bottom, left + 1:right] = dark[top + 1:bottom, left + 1:right]
        mask = drop_small_blobs(mask, args.min_blob)
    pts, pen = extract_trace(mask)
    ncols = (np.nonzero(mask.any(0))[0].max() - np.nonzero(mask.any(0))[0].min() + 1
             if args.layout in ("palleros", "omnic") else right - left - 1)
    print(f"  trace  {len(pts)}/{ncols} columns, pen {pen} px")
    if len(pts) < 0.95 * ncols:
        print("  FAIL   trace missing in more than 5% of columns")
        failed = True

    cols = np.array([c + dc for c, _, _ in pts for dc in (-0.25, 0.25)])
    rows = np.array([r for _, e, x in pts for r in (e, x)])
    wn = interp_extrap(cols, *xcal)
    pct = interp_extrap(rows, *ycal)
    if np.any(np.diff(wn) >= 0):
        sys.exit("x calibration is not monotonic")
    step = np.abs(np.gradient(wn, cols))  # cm-1 per px at each point

    # fidelity
    rd = redraw(pts, mask.shape)
    reach = 1 + int(np.ceil((pen - 1) / 2))
    recall = (mask & dilate(rd, reach)).sum() / max(mask.sum(), 1)
    precision = (rd & dilate(mask, 1)).sum() / max(rd.sum(), 1)
    ok = recall >= 0.98 and precision >= 0.98
    failed |= not ok
    print(f"  redraw recall {recall:.4f}, precision {precision:.4f}  {'ok' if ok else 'FAIL (< 0.98)'}")
    print(f"  resolution {step.max():.1f} cm-1/px (max), {step.min():.1f} (min); "
          f"{100 / abs(ycal[0][1] - ycal[0][0]) * abs(ycal[1][1] - ycal[1][0]) / 100:.2f} %T/px")

    check = parse_check(args.check, args.check_file)
    if check:
        align = args.align if args.align is not None else args.layout == "palleros"
        if align:
            # The plotter's ticks and its pen path are offset from each other by a few
            # pixels (measured: +3.9 px, 5 cm-1 on Fig. 22.3, in the same direction
            # on every sharp band). The printed band positions are the instrument's
            # own numbers, so shift x by the median offset of the troughs that sit
            # within 8 px of a printed band, and say so. Residual scatter afterwards
            # is the honest accuracy; the check below is then no longer independent
            # of the shift, only of the scatter.
            tr0 = troughs(wn, pct)
            tw0 = np.array([t[0] for t in tr0])
            offs = []
            for w0, _ in check:
                if len(tw0):
                    j = int(np.argmin(np.abs(tw0 - w0)))
                    if abs(tw0[j] - w0) <= 8 * np.interp(w0, wn[::-1], step[::-1]):
                        offs.append(tw0[j] - w0)
            if len(offs) >= 4:
                sh = float(np.median(offs))
                wn = wn - sh
                print(f"  align  x shifted by {-sh:+.1f} cm-1 ({-sh / float(np.median(step)):+.1f} px) = median offset of "
                      f"{len(offs)} troughs from their printed positions (scatter {np.std(offs):.1f} cm-1)")
            else:
                print(f"  align  skipped: only {len(offs)} troughs within 8 px of a printed band (need 4)")
        tr = troughs(wn, pct)
        tw = np.array([t[0] for t in tr])
        # each trough counts for the nearest listed peak only; a listed peak
        # whose trough was taken by a closer one is a merged close pair
        owner = {}
        for k, (w0, _) in enumerate(check):
            if len(tw):
                j = int(np.argmin(np.abs(tw - w0)))
                if j not in owner or abs(tw[j] - w0) < abs(tw[j] - check[owner[j]][0]):
                    owner[j] = k
        taken = {k: j for j, k in owner.items()}
        dw, dt, pairs, printed = [], [], [], []
        print(f"  peak check against {len(check)} listed peaks:")
        for k, (w0, t0) in enumerate(check):
            tol = max(1.5, (pen - 1) / 2) * np.interp(w0, wn[::-1], step[::-1])  # a thick pen blurs the tip by ~half its width
            j = taken.get(k)
            if j is None or abs(tw[j] - w0) > tol:
                near = [check[owner[jj]][0] for jj in owner if abs(tw[jj] - w0) <= tol and owner[jj] != k]
                why = f"merged with {near[0]:.0f}" if near else f"no trough within {tol:.0f} cm-1"
                print(f"    {w0:6.0f} {'' if t0 is None else f'{t0:5.1f}%'}  unresolved ({why})")
                continue
            dw.append(tw[j] - w0); printed.append((w0, tr[j][1]))
            if t0 is None:
                print(f"    {w0:6.0f}  -> {tw[j]:7.1f} {tr[j][1]:5.1f}%   dwn {tw[j] - w0:+5.1f}")
                continue
            dt.append(tr[j][1] - t0); pairs.append((t0, tr[j][1]))
            print(f"    {w0:6.0f} {t0:5.1f}%  -> {tw[j]:7.1f} {tr[j][1]:5.1f}%   "
                  f"dwn {tw[j] - w0:+5.1f}  d%T {tr[j][1] - t0:+5.1f}")
        if dw:
            dw, dt = np.abs(dw), np.array(dt)
            print(f"  matched {len(dw)}/{len(check)}: |dwn| median {np.median(dw):.1f}, max {dw.max():.1f} cm-1"
                  + (f"; d%T median {np.median(dt):+.1f}, |d%T| max {np.abs(dt).max():.1f}" if len(dt) else ""))

    if args.peaklist and check and printed:
        # the \\irspectrum peak argument from the PRINTED band positions (exact),
        # each at the %T of the trough it was matched to; label offsets and
        # staggering are spa_peaks.py's own recipe
        from . import spa_peaks
        pxyl = spa_peaks.assign_label_y(printed)
        print("  peaklist:", spa_peaks.format_peaklist(pxyl))
        print("  ymin suggestion:", int(min(ly for _, _, ly in pxyl) // 5 * 5 - 5))

    if args.overlay:
        ov = (base if base is not None else Image.open(args.image)).convert("RGB")
        d = ImageDraw.Draw(ov)
        xy = [(c, r) for c, e, x in pts for r in (e, x)]
        # OMNIC's own trace is red, so a red overlay would be invisible on it
        d.line(xy, fill=(0, 90, 255) if args.layout == "omnic" else (220, 30, 30), width=1)
        os.makedirs(os.path.dirname(args.overlay) or ".", exist_ok=True)
        ov.save(args.overlay)
        print(f"  overlay -> {args.overlay}")

    meta = {"title": args.name, "cas": "", "axis_label": "Transmittance"}
    frac = pct / 100.0
    if args.out:
        jdx_tool.write_csv(wn, frac, meta, args.out, args.name)
        print(f"  csv    -> {args.out} ({len(wn)} points, {wn[-1]:.0f}-{wn[0]:.0f} cm-1)")
    if args.plain_out:
        jdx_tool.write_plain_csv(wn, frac, meta, args.plain_out)
        print(f"  plain  -> {args.plain_out}")
    if failed:
        sys.exit(2)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("convert", help="one plot image -> archival CSV [+ plain CSV]")
    p.add_argument("image")
    p.add_argument("--name", required=True, help="compound name: CSV header; caps, underscores, no spaces")
    p.add_argument("--out", help="archival CSV path")
    p.add_argument("--plain-out", help="plain CSV path (>=650 cm-1, %%T)")
    p.add_argument("--layout", choices=["sdbs", "manual", "palleros", "omnic"], default="sdbs")
    p.add_argument("--palleros", dest="layout", action="store_const", const="palleros",
                   help="shortcut for --layout palleros")
    p.add_argument("--omnic", dest="layout", action="store_const", const="omnic",
                   help="shortcut for --layout omnic")
    p.add_argument("--x-ticks", help="palleros: wavenumbers of the long x tick marks, left to right "
                                     "(omit to read them with tesseract)")
    p.add_argument("--y-ends", help="palleros: TOP:BOTTOM, the %%T values printed at the ends of the y axis")
    p.add_argument("--x-first", type=float, help="omnic: wavenumber of the first (leftmost) major tick")
    p.add_argument("--x-step", type=float, help="omnic: wavenumber change per major tick (e.g. -500)")
    p.add_argument("--y-first", type=float, help="omnic: %%T of the top y tick")
    p.add_argument("--y-step", type=float, help="omnic: %%T change per y tick (e.g. -10)")
    p.add_argument("--blob-frac", type=float, default=0.05,
                   help="palleros/omnic: keep ink blobs at least this fraction of the biggest (default 0.05)")
    p.add_argument("--box", help="manual: LEFT,TOP,RIGHT,BOTTOM frame pixels")
    p.add_argument("--x", action="append", help="manual: PX=WAVENUMBER (repeat)")
    p.add_argument("--y", action="append", help="manual: PX=%%T (repeat)")
    p.add_argument("--threshold", type=int, default=128, help="grey level below which a pixel is ink (default 128)")
    p.add_argument("--min-blob", type=int, default=6, help="drop ink blobs smaller than this many px (default 6)")
    p.add_argument("--check", help='reference peaks "wn:%%T,wn:%%T,..."')
    p.add_argument("--check-file", help="reference peaks, one 'wn %%T' per line")
    p.add_argument("--align", action=argparse.BooleanOptionalAction, default=None,
                   help="shift x by the median offset of the traced troughs from the printed --check bands "
                        "(default on for --palleros, off otherwise)")
    p.add_argument("--peaklist", action="store_true",
                   help="with --check: print the \\irspectrum peak list built from the checked (printed) positions")
    p.add_argument("--overlay", help="save the image with the digitized curve drawn in red")
    p.set_defaults(func=cmd_convert)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

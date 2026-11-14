#!/usr/bin/env python3
"""gel_tool.py -- SDS-PAGE gel photo -> straightened image, lane profiles, bands,
molecular-mass calibration, and a report figure with a label file for \\gelfigure.

Moved here from nulabreport's tools/gel_tool.py (2026-11-14); the output is byte for byte what that script wrote.

Written 2026-11-12 for CHEM341L Lab 5 (SDS-PAGE, gel re-run by the lab assistants,
photographed through a wet plastic sleeve: ~/Downloads/Lab5/photos/20261110_145912.jpg).
Pure Python: Pillow, numpy, scipy (no OpenCV). Run it with plain `python3` (scipy is
installed in the user site-packages on the author's Mac, which `python3 -I` hides).

    irspec gel all        LR/gel/gel.json   # everything below, in order
    irspec gel straighten LR/gel/gel.json   # straightened.png, preview_grid.png
    irspec gel lanes      LR/gel/gel.json   # + lanes.csv
    irspec gel bands      LR/gel/gel.json   # + bands.csv, profiles.csv
    irspec gel calibrate  LR/gel/gel.json   # + calibration.csv, estimates.csv
    irspec gel figure     LR/gel/gel.json   # + gel.png, gel_labels.csv, check.png

Each subcommand runs the pipeline up to and including its own stage (all of it takes a few
seconds) and writes that stage's files. Nothing is clicked or typed interactively: every
choice made by hand lives in the JSON config (section 2). A run writes only the files
named above, into the config's `out_dir` (refused when that is inside a `photos/` or
`sources/` folder), plus the config itself when it fills in a missing proposal (corners,
ladder assignment); it never deletes anything. Positions in the config and the CSVs are
pixels of the STRAIGHTENED image (straightened.png) unless said otherwise.

===============================================================================
1. PIPELINE
===============================================================================
 1. Load the photo and apply its EXIF orientation (`ImageOps.exif_transpose`). Phone
    photos are stored landscape with an orientation tag; `search_box` and `corners` are
    in the CORRECTED image (portrait 6120 x 8160 for the Lab 5 photo).
 2. straighten: a perspective warp of the quadrilateral `corners` (TL, TR, BR, BL) to a
    rectangle, with `Image.transform(..., PERSPECTIVE, coeffs)`. PIL's 8 coefficients
    map OUTPUT pixels to INPUT pixels, so they are solved with the rectangle's corners
    as (u, v) and the photo's corners as targets (`solve_perspective`). The rectangle's
    size is the mean length of opposite edges, i.e. the photo's own scale. Without
    `corners` in the config they are proposed (`propose_corners`) and written into it:
    check them on preview_grid.png (the uncorrected `search_box` crop with a grid
    labelled in photo pixels and the corners drawn on), edit, re-run.
    Proposal: mask of gel pixels, B - R > `blue_min` (default BLUE_MIN), largest
    connected component, NO hole filling (comb fingers that flopped over and touch their
    neighbours enclose the wells; filling them moved the top edge 45 px up onto the
    fingers). Left/right edges: first/last mask column of every body row, robust line
    fit. Bottom: last mask row per column, robust fit (a torn corner is trimmed as
    outliers). Top = the BOTTOMS OF THE WELLS: per column, the top of the run of gel that
    holds the body's middle row (a finger lying over a well sits above that run, with
    bench between), the 80th percentile per strip of 1/40 of the width, robust fit.
    Corners = the four lines' intersections. The top of straightened.png is therefore the
    well bottoms, and the lane labels of the figure sit on it.
 3. lanes: the signal is an optical-density-like value from the RED channel,
    OD = -log10(R / R_ref): Coomassie absorbs around 595 nm, which the red channel sees.
    (It is not a calibrated absorbance: the photo is gamma-encoded and the camera's tone
    curve flattens dark bands, so heights and areas only rank bands; positions are what
    the tool measures.) Per column, the 98th percentile (LANE_PCT) of the OD between the
    wells and the front, each row's median across the gel taken off first, minus its grey
    opening one lane pitch wide, shows a hump per LOADED lane only: one band is enough to
    lift it, while empty lanes, and a lane loaded with no protein (Lab 5's creatine), stay
    at the noise. (The column MEAN, tried first, missed a lane with a single band: on the
    synthetic demo gel such lanes read 0.011-0.02, Lab 5's empty ones 0.009-0.014.) So the humps are
    not numbered 1..n in order: their centres (FWHM midpoints; a lane's hump can be
    double-topped) are fitted to a lattice x = x0 + k * pitch with integer k, numbered
    from the left so that the margins left of lane 1 and right of lane `count` are equal
    (`fit_lattice`). A loaded lane keeps its measured centre, an empty lane gets the
    lattice's. Lane width = the median hump FWHM; a lane's profile averages the middle
    `window` of it. `lanes.centres` in the config replaces all of this.
    Gaps: the strips between neighbouring lanes' full widths (a loaded lane's own FWHM)
    and the two margins, middle GAP_CORE of each. They hold no sample, so they are where
    the local background and the front are read.
 4. bands:
    - Front: the handoff's rule first (the row with the highest mean OD across the full
      width, since the front crosses the empty lanes too), then measured in every gap
      (argmax of the gap's OD within FRONT_WIN of that row, parabola for the sub-pixel
      position). A lane's front is the gaps on its two sides interpolated at its centre.
      Not a straight line across the gel: on Lab 5 the front is 15-18 px higher across
      lanes 1-5 than across 6-10, with a step between lanes 5 and 6 (sec. 4).
    - Origin = front - run. The top of the resolving gel is too faint to find lane by
      lane next to loaded lanes (bands and the BSA aggregate spill into the narrow gaps),
      but its distance from the front is nearly constant: `run` is the median, over every
      band-free column (gaps and empty lanes), of front minus the faint dark ridge at the
      top of the resolving gel, searched within RUN_WIN of a first estimate (the ridge
      maximum between ORIGIN_SEARCH of the way down to the front, on a 2-D smoothed OD
      image). Printed with its IQR, which says how far to trust it. `bands.run` (one
      number) or `bands.origin` (one number, or {"lane": y}) in the config override it;
      Lab 5's bottom gel needs `origin` (sec. 4).
    - Background: each gap's per-row median R with a grey CLOSING OPEN_FRAC of the run
      wide (rolling maximum then minimum of R: the front, the origin ridge and stray
      marks are closed over), interpolated linearly in x between the lane's two gaps and
      divided out pixel by pixel. Only the slowly varying stain and lighting go. The
      front stays in every lane's profile, as a peak flagged `at_front`: dividing it out
      carved the Lab 5 ladder's 25 kDa band, which runs on the front line, into two false
      shoulders. What is left of the floor under the bands is removed by a grey opening
      (rolling minimum then maximum) of the same width, smoothed.
    - Rf = (y_band - origin) / (front - origin), with the lane's own origin and front.
    - Peaks: `scipy.signal.find_peaks` between the origin and PAST_FRONT of the run below
      the front, with `prominence` (OD units) and `distance` (fraction of the run).
      Position is sub-pixel (parabola through the top three samples); width is the FWHM
      (`peak_widths`, rel_height 0.5); area is the integral of the corrected profile
      across that FWHM (OD x px), a relative number only. `at_front` = Rf at or past the
      upper half-width of the front (1 - front FWHM / 2 / run). `unresolved` = the
      valley between a peak and its neighbour stays above VALLEY_FRAC of the lower one:
      a band dark enough to flatten in the photo reads as two maxima, and a shoulder
      looks the same.
 5. calibrate: `ladder.assign` maps kDa to a band's y in straightened pixels; each is
    snapped to the nearest detected ladder peak within ASSIGN_TOL of the run (it stops
    when none is that close, or when two sizes snap to one peak). A size left out is
    excluded. Positions, not peak numbers: a change of `prominence` renumbers the peaks.
    Without `assign`, a proposal is written into the config. The two reference bands are
    found in the BLUE channel (`reference_bands`): Coomassie-blue bands and the blue
    front reflect blue and barely show there, while the prestained ladder's red (75 kDa)
    and green (25 kDa) bands, with Coomassie on top, read near-black and absorb blue too.
    In the red channel they are no taller than the blue bands around them. The proposal
    assigns the sizes above, between and below them by order, keeping the most
    prominent peaks when there are more than the ladder has. It stops if there are
    fewer, and leaves the bands below the lower anchor (20, 17, 11 kDa, compressed at
    the front) unassigned, with a note.
    `ladder.reference_channel`: "red" (default) uses every band's red-channel position;
    "blue" takes the two reference bands' positions from the blue channel, which the
    front does not disturb.
    `ladder.fit`: "linear" (default: log10 kDa = a + b Rf, least squares), "quadratic",
    or "point-to-point" (straight lines in log10 kDa between neighbouring ladder bands,
    extended beyond the end bands). All three are printed side by side, with r^2 for
    the two fits, the ladder residuals and the main sample bands' estimates.
    calibration.csv: each assigned point, its fitted mass and residual (kDa and %), and
    the fit. estimates.csv: every peak of every named non-ladder lane, with its mass from
    the chosen model and `extrapolated` = 1 outside the ladder's Rf range. No protein
    names are attached to sample bands: that is the report's call.
 6. figure: gel.png is the straightened image cropped to `figure.crop` (fractions
    [x0, y0, x1, y1] of the straightened image; default full width, from FIG_TOP below
    the well bottoms, which hides their ragged edge, to 0.06 of the height below the mean
    front), colour kept, as a palette PNG (median-cut palette, no dithering). Colours
    are kept first and width second: the first entry of FIG_COLOURS x FIG_WIDTHS whose
    file fits `figure.target_kb` (fewer than 256 colours merged Lab 5's near-black
    reference bands into the blue ones and banded the background; an octree palette
    blotched it). gel_labels.csv holds everything \\gelfigure draws, positions as
    FRACTIONS of gel.png from its top-left corner (y runs DOWN), never pixels:
    `kind,x,y,text`. `lane`: x = lane centre, y = 0, text = the lane's label. `mark`: y = a
    calibration band's measured position, x = 0 when the ladder is in the left half of
    the gel, 1 in the right, text = its kDa (`figure.marks` picks which). `arrow`: x = the
    right edge of a band's lane window, y = the band, only for `figure.arrows` entries
    {"lane": n, "peak": i, "text": "..."}. A text with a comma is refused (plain CSV).
    check.png (NOT for the report): straightened.png with the gaps (cyan), lane windows
    (white), each lane's origin (green) and front (magenta), its corrected profile (white
    trace), every peak (yellow tick and number, orange at the front) and the ladder's
    assigned sizes drawn on.

===============================================================================
2. CONFIG (JSON; paths relative to the config's folder, or ~)
===============================================================================
  {
    "photo": "../photos/20261110_145912.jpg",
    "out_dir": ".",
    "search_box": [1600, 2000, 3750, 3900],   # x0, y0, x1, y1 in the corrected photo
    "blue_min": 40,                           # gel mask threshold for the corner proposal
    "corners": [[x, y], [x, y], [x, y], [x, y]],   # TL, TR, BR, BL; proposed if absent
    "lanes": {
      "count": 10,
      "names":  {"1": "Ladder", "2": "BSA 0.1%", ...},  # named lanes are reported
      "labels": {"1": "L", ...},       # text above each lane in the figure (default: number)
      "window": 0.6,                   # middle fraction of the lane width averaged
      "centres": {"1": x, ...},        # optional: replaces the lane detection
      "width_px": 109                  # optional: replaces the measured lane width
    },
    "bands": {"prominence": 0.03, "distance": 0.015,
              "run": 484, "origin": 158, "front": 630},     # the last three optional
    "ladder": {"lane": 1, "sizes": [245, 180, 135, 100, 75, 63, 48, 35, 25, 20, 17, 11],
               "anchors": [75, 25], "fit": "linear", "reference_channel": "red",
               "assign": {"245": 188.3, "180": 216.9, ...}},    # proposed if absent
    "figure": {"crop": [0, 0.015, 1, 0.62], "target_kb": 250, "marks": [245, 75, 25],
               "arrows": [{"lane": 5, "peak": 2, "text": "a"}]}
  }

===============================================================================
3. DEFAULTS AND WHY
===============================================================================
  BLUE_MIN 40        B - R is ~85 on the top Lab 5 gel and -15..+8 on the bench around
                     it; 20 or less let the tinted sleeve near its wells into the mask
                     and tilted the top edge. The paler bottom gel (B - R 11-41 below the
                     front) needs `blue_min` 10.
  WINDOW 0.6         the handoff's "middle ~60 %" of a lane: off the lane edges, where
                     bands curl, and off Lab 5's bubble beside lane 5.
  LANE_PCT 98        at the 98th percentile loaded lanes read 0.50-0.58 (Lab 5 top gel),
                     0.69-1.10 (bottom gel), 0.24-0.46 (synthetic demo gel); empty lanes
                     <= 0.053 (a bubble or speck).
  LANE_PROM 0.3      of the tallest hump, which those numbers clear by a factor of two.
  GAP_CORE 0.6       middle of each gap (gaps are ~40 px on Lab 5, so ~25 px are read).
  OPEN_FRAC 0.15     background closing/opening width, of the run (73 px on Lab 5):
                     about twice the widest band's FWHM there (BSA 37 px; egg albumin's
                     main band with its shoulder 44 px), so it passes under the bands.
  SMOOTH_FRAC 0.004  Gaussian sigma of a lane profile, of the run (~2 px): JPEG noise.
  PROMINENCE 0.03    the empty creatine lane's largest peak off the front is 0.020.
  DISTANCE_FRAC 0.015 of the run (7 px), well under the closest ladder pair (28 px).
  ORIGIN_SEARCH 0.10-0.45 of the way to the front; RUN_WIN 0.06 of the run around the
                     first estimate; RIDGE_SIGMA 3 px (y) x 6 px (x).
  FRONT_WIN 0.06     of the height around the full-width front row.
  ASSIGN_TOL 0.02    of the run (10 px) for snapping `assign`; REF_MATCH 0.05 for
                     matching a blue-channel reference band to a red-channel peak (the
                     bottom gel's 25 kDa band: blue 701, merged red peak 719).
  VALLEY_FRAC 0.8    the egg-albumin shoulder's valley is 0.87 of the lower peak.
  RUN_IQR_WARN 0.05  warn when the run's IQR exceeds this share of it: 2 % on the top
                     gel, 9 % on the bottom gel, whose ridge rule had failed.
  FLANK_WARN 0.01    note a lane whose two flanking fronts differ by more than this
                     share of the run (Lab 5 lane 5: 7.7 px, 1.6 %).

===============================================================================
4. MEASURED ON THE LAB 5 PHOTO (2026-11-12)
===============================================================================
  Top gel (Ali's): corners proposed (1887.6, 2463.7) (3446.3, 2461.0) (3447.3, 3606.6)
  (1857.8, 3600.7) -> 1574 x 1141 px. Loaded humps at x 107, 265, 558, 713 = lanes 1, 2,
  4, 5 (lattice residuals -2.9 to +4.9 px, pitch 150.5, margins 110 / 110 px); lane 3
  (creatine) blank, as expected.
  Front in the 11 gaps: 629.1, 630.0, 632.2, 633.1, 635.4 | 643.1, 647.5, 648.0, 648.4,
  643.3, 639.9 (FWHM 36 px): 15-18 px higher on the left. The resolving gel's top edge is
  a faint dark ridge (OD +0.06), at y ~145 near lanes 1-4 and ~163 across 6-10, so it is
  shifted the same way; front minus ridge over 680 band-free columns: median 484 px,
  IQR 478-487 (300-520: 486, 800-1574: 485; 0-300 reads 476, next to the ladder and the
  BSA aggregate). A straight-line front fitted through the empty lanes 3 and 6-10
  missed the left half by up to 7 px; dividing by those lanes put the front at the wrong
  row for lanes 1-5. Hence the gaps.
  Ladder: 11 peaks; 245-35 kDa resolved; the 25 kDa band (blue-channel y 624, red
  618) runs ON the front (630) and the next band (659, Rf 1.06) is past it. Blue OD: 75
  kDa 0.40, 25 kDa 0.68, every other band <= 0.12. Linear fit r^2 0.968 with a
  systematic bow (residuals -22, -7, +7, +14, +22, +9, 0, -11, -5 % from 245 to 25 kDa);
  quadratic r^2 0.987. Changing origin or front cannot remove the bow: Rf is linear in y.
  `reference_channel` red vs blue on the top gel (25 kDa at y 618 vs 624) moves every
  sample estimate by under 1 kDa (<= 0.7 %, linear model). Lane 5's flanking fronts
  differ by 7.7 px (+/-0.008 in Rf; printed as a note).
  Bottom gel (another pair's, cross-check only, `crosscheck_bottom/`): `blue_min` 10;
  its resolving gel starts at a STEP at y 155-160 (paler stacking gel above), not a
  ridge, and the ridge rule read 286 (run IQR 406-444, 9 % of the run: the warning
  RUN_IQR_WARN was added for this), so its config sets `origin` 158 for every lane, by
  eye, where the top gel uses front - run per lane; `reference_channel` blue (its
  25 kDa band's red peak merges with the front 18 px away). Same bow (-23 ... +23 %).
  Like for like (both blue, linear): the single, clean bands agree within 0.2-1.8 %
  (lane 4 upper 95.2 / 95.7 kDa; lane 5: 169.5 / 167.7, 148.5 / 145.9, 43.9 / 44.0).
  The flat-topped bands are flagged pairs on the bottom gel and compare only as ranges
  (lane 2 main: top 84.8, bottom 78.5-84.4; lane 5 main: 64.8 vs 63.4-67.5); lane 4's
  main band is a maximum plus a shoulder on the top gel (45.4-52.0) and one peak on the
  bottom (52.8).
  Synthetic demo gel (examples/tex/gel-demo/make_gel.py, every band on one line): the
  planted 66, 78, 45, 150 and 50 kDa come back within 0.22 %, mirrored gel included; the
  smoke test checks this.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

try:
    from scipy import ndimage, signal
except ImportError:  # pragma: no cover
    sys.exit("gel_tool.py needs scipy (run with plain python3, not python3 -I)")

BLUE_MIN = 40
WINDOW = 0.6
LANE_PROM = 0.3
LANE_PCT = 98
OPEN_FRAC = 0.15
SMOOTH_FRAC = 0.004
PROMINENCE = 0.03
DISTANCE_FRAC = 0.015
ORIGIN_SEARCH = (0.10, 0.45)
RUN_WIN = 0.06
RIDGE_SIGMA_Y, RIDGE_SIGMA_X = 3, 6
FRONT_WIN = 0.06
GAP_CORE = 0.6
GAP_EDGE = 0.008
GAP_MIN_PX = 6
PAST_FRONT = 0.08
ASSIGN_TOL = 0.02
REF_MATCH = 0.05
VALLEY_FRAC = 0.8
RUN_IQR_WARN = 0.05
FLANK_WARN = 0.01
FIG_WIDTHS = (1000, 900, 800, 700, 600, 500, 400)
FIG_COLOURS = (256, 192, 128, 96, 64)
FIG_TOP = 0.015
TARGET_KB = 250
DEFAULT_SIZES = [245, 180, 135, 100, 75, 63, 48, 35, 25, 20, 17, 11]


# ----------------------------------------------------------------------------- config
class Config:
    def __init__(self, path: str):
        self.path = Path(path).expanduser().resolve()
        self.base = self.path.parent
        self.data = json.loads(self.path.read_text())
        self.dirty = False

    def resolve(self, p: str) -> Path:
        q = Path(os.path.expanduser(p))
        return q if q.is_absolute() else (self.base / q).resolve()

    @property
    def out(self) -> Path:
        d = self.resolve(self.data.get("out_dir", "."))
        for forbidden in ("photos", "sources"):
            if forbidden in d.parts:
                sys.exit(f"out_dir {d} is inside a '{forbidden}' folder; refusing to write there")
        d.mkdir(parents=True, exist_ok=True)
        return d

    def sect(self, name: str) -> dict:
        return self.data.setdefault(name, {})

    def save(self):
        if self.dirty:
            self.path.write_text(dump_json(self.data) + "\n")
            print(f"  config updated: {self.path.name}")
            self.dirty = False


def dump_json(v, ind=0) -> str:
    """JSON with a list of numbers (corners, sizes) kept on one line."""
    pad = "  " * (ind + 1)
    if isinstance(v, dict):
        if not v:
            return "{}"
        items = [f"{pad}{json.dumps(k)}: {dump_json(x, ind + 1)}" for k, x in v.items()]
        return "{\n" + ",\n".join(items) + "\n" + "  " * ind + "}"
    if isinstance(v, list) and all(not isinstance(x, (dict, list)) or
                                   (isinstance(x, list) and all(not isinstance(y, (dict, list)) for y in x))
                                   for x in v):
        return json.dumps(v)
    if isinstance(v, list):
        return "[\n" + ",\n".join(pad + dump_json(x, ind + 1) for x in v) + "\n" + "  " * ind + "]"
    return json.dumps(v)


def rel(p: Path) -> str:
    return str(p).replace(str(Path.home()), "~")


# ----------------------------------------------------------------------------- geometry
def robust_line(t, s, k=3.0, n_iter=8):
    """Fit s = a + b t by least squares, trimming points beyond k robust sigmas."""
    t = np.asarray(t, float)
    s = np.asarray(s, float)
    keep = np.isfinite(s)
    for _ in range(n_iter):
        b, a = np.polyfit(t[keep], s[keep], 1)
        res = s - (a + b * t)
        sig = 1.4826 * np.median(np.abs(res[keep])) + 0.5
        new = np.isfinite(s) & (np.abs(res) <= k * sig)
        if (new == keep).all():
            break
        keep = new
    return a, b, keep


def intersect(row_line, col_line):
    """row_line: y = a + b x (top/bottom); col_line: x = c + d y (left/right)."""
    a, b = row_line
    c, d = col_line
    y = (a + b * c) / (1 - b * d)
    x = c + d * y
    return [round(float(x), 1), round(float(y), 1)]


def propose_corners(rgb: np.ndarray, box, blue_min=BLUE_MIN) -> list:
    x0, y0, x1, y1 = box
    a = rgb[y0:y1, x0:x1].astype(np.int16)
    mask = (a[..., 2] - a[..., 0]) > blue_min
    mask = ndimage.binary_opening(mask, iterations=2)
    lab, n = ndimage.label(mask)
    if n == 0:
        sys.exit("no blue gel found inside search_box")
    sizes = ndimage.sum(mask, lab, range(1, n + 1))
    # no hole filling: comb fingers that flopped over and touch their neighbours
    # enclose the wells, and filling them would move the top edge up to the fingers
    mask = lab == (1 + int(np.argmax(sizes)))
    h, w = mask.shape
    cols = np.arange(w)
    rows = np.arange(h)
    count = mask.sum(1)
    body = count >= 0.9 * np.percentile(count, 90)
    body_rows = rows[body]
    # left / right edges from body rows
    first = np.array([np.argmax(mask[r]) for r in body_rows], float)
    last = np.array([w - 1 - np.argmax(mask[r, ::-1]) for r in body_rows], float)
    la, lb, _ = robust_line(body_rows, first)
    ra, rb, _ = robust_line(body_rows, last)
    # columns well inside the edges
    xin0 = int(max(la + lb * body_rows.min(), la + lb * body_rows.max())) + 10
    xin1 = int(min(ra + rb * body_rows.min(), ra + rb * body_rows.max())) - 10
    inner = cols[xin0:xin1]
    any_col = mask[:, inner].any(0)
    # top of the run of gel that holds the body's middle row: a comb finger that has
    # flopped over a well lies ABOVE that run, with bench showing between them
    mid = int(np.median(body_rows))
    above = ~mask[:mid, inner]
    has_gap = above.any(0)
    run_top = np.where(has_gap, mid - np.argmax(above[::-1], 0), 0).astype(float)
    top_first = np.where(any_col, run_top, np.nan)
    bot_last = np.where(any_col, h - 1 - np.argmax(mask[::-1, inner], 0), np.nan)
    # top = well bottoms: deepest run top per strip, robust fit over strips
    nstrip = 40
    edges = np.linspace(0, len(inner), nstrip + 1).astype(int)
    sx, sy = [], []
    for i in range(nstrip):
        seg = top_first[edges[i]:edges[i + 1]]
        if np.isfinite(seg).any():
            # 80th percentile, not the maximum: a bubble just below the well bottom
            # leaves a hole whose lower edge would otherwise win
            sy.append(float(np.nanpercentile(seg, 80)))
            sx.append(float(inner[edges[i]:edges[i + 1]].mean()))
    ta, tb, tkeep = robust_line(sx, sy, k=2.5)
    ba, bb, _ = robust_line(inner, bot_last, k=2.5)
    # back to photo coordinates
    def shift_row(a_, b_):  # y = a + b x in crop -> photo
        return (a_ + y0 - b_ * x0, b_)

    def shift_col(c_, d_):  # x = c + d y in crop -> photo
        return (c_ + x0 - d_ * y0, d_)

    top, bot = shift_row(ta, tb), shift_row(ba, bb)
    left, right = shift_col(la, lb), shift_col(ra, rb)
    return [intersect(top, left), intersect(top, right),
            intersect(bot, right), intersect(bot, left)]


def solve_perspective(quad, W, H):
    """Coefficients for PIL's PERSPECTIVE transform: output (u, v) -> input (x, y)."""
    src = [(0, 0), (W, 0), (W, H), (0, H)]
    A, b = [], []
    for (u, v), (x, y) in zip(src, quad):
        A.append([u, v, 1, 0, 0, 0, -u * x, -v * x])
        b.append(x)
        A.append([0, 0, 0, u, v, 1, -u * y, -v * y])
        b.append(y)
    return tuple(np.linalg.solve(np.array(A, float), np.array(b, float)))


def dist(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # very old Pillow
        return ImageFont.load_default()


# ----------------------------------------------------------------------------- stages
class Gel:
    """Holds every stage's results; each stage method fills its part."""

    def __init__(self, cfg: Config):
        self.cfg = cfg

    # 1-2 ---------------------------------------------------------------------
    def straighten(self, write=True):
        cfg = self.cfg
        photo_path = cfg.resolve(cfg.data["photo"])
        photo = ImageOps.exif_transpose(Image.open(photo_path)).convert("RGB")
        box = cfg.data.get("search_box") or [0, 0, photo.width, photo.height]
        if not cfg.data.get("corners"):
            corners = propose_corners(np.asarray(photo), box, float(cfg.data.get("blue_min", BLUE_MIN)))
            cfg.data["corners"] = corners
            cfg.data["corners_note"] = ("proposed from the gel's edges by gel_tool.py; "
                                        "check preview_grid.png, edit, re-run")
            cfg.dirty = True
            print(f"  corners proposed (TL, TR, BR, BL): {corners}")
        quad = cfg.data["corners"]
        W = round((dist(quad[0], quad[1]) + dist(quad[3], quad[2])) / 2)
        H = round((dist(quad[0], quad[3]) + dist(quad[1], quad[2])) / 2)
        coeffs = solve_perspective(quad, W, H)
        img = photo.transform((W, H), Image.Transform.PERSPECTIVE, coeffs,
                              resample=Image.Resampling.BICUBIC)
        self.img = img
        self.rgb = np.asarray(img).astype(float)
        self.R = np.clip(self.rgb[..., 0], 1, None)
        self.Bc = np.clip(self.rgb[..., 2], 1, None)
        self.W, self.H = W, H
        if write:
            out = cfg.out
            img.save(out / "straightened.png")
            self.preview_grid(photo, box, quad, out / "preview_grid.png")
            print(f"  straightened: {W} x {H} px -> {rel(out / 'straightened.png')}")
        return self

    def preview_grid(self, photo, box, quad, path):
        x0, y0, x1, y1 = box
        crop = photo.crop((x0, y0, x1, y1))
        d = ImageDraw.Draw(crop)
        f = font(max(14, (x1 - x0) // 70))
        step = 100
        for gx in range((x0 // step + 1) * step, x1, step):
            major = gx % 500 == 0
            d.line([(gx - x0, 0), (gx - x0, y1 - y0)], fill=(255, 0, 0) if major else (255, 160, 160),
                   width=3 if major else 1)
            if gx % 200 == 0:
                d.text((gx - x0 + 4, 4), str(gx), fill=(200, 0, 0), font=f)
        for gy in range((y0 // step + 1) * step, y1, step):
            major = gy % 500 == 0
            d.line([(0, gy - y0), (x1 - x0, gy - y0)], fill=(255, 0, 0) if major else (255, 160, 160),
                   width=3 if major else 1)
            if gy % 200 == 0:
                d.text((4, gy - y0 + 4), str(gy), fill=(200, 0, 0), font=f)
        pts = [(p[0] - x0, p[1] - y0) for p in quad]
        d.line(pts + [pts[0]], fill=(255, 200, 0), width=3)
        for name, p in zip(("TL", "TR", "BR", "BL"), pts):
            d.ellipse([p[0] - 10, p[1] - 10, p[0] + 10, p[1] + 10], outline=(0, 0, 0), width=3)
            d.text((p[0] + 12, p[1] + 12), name, fill=(0, 0, 0), font=f)
        crop.save(path)

    # 3 -----------------------------------------------------------------------
    def od(self, R, ref=None):
        ref = np.median(R) if ref is None else ref
        return -np.log10(R / ref)

    def lanes(self, write=True):
        cfg, R, W, H = self.cfg, self.R, self.W, self.H
        ls = cfg.sect("lanes")
        count = int(ls.get("count", 10))
        self.count = count
        # global dye front guess (the handoff's rule): the row with the highest mean OD
        # across the FULL width, since the front runs through the empty lanes as well
        rowmean = self.od(R).mean(1)
        lo, hi = int(0.2 * H), int(0.98 * H)
        self.front_guess = lo + int(np.argmax(ndimage.gaussian_filter1d(rowmean, 2)[lo:hi]))
        r0, r1 = int(0.05 * H), int(self.front_guess - 0.03 * H)
        # per column, a high percentile of the OD (each row's median across the gel taken
        # off first, which removes the origin ridge, the gradient and anything else that
        # runs across): one band lifts it, so a lane with a single band is found too. The
        # column MEAN was used first and missed sparse lanes (synthetic gel: 0.011-0.02,
        # against 0.009-0.014 for Lab 5's empty lanes); at the 98th percentile loaded lanes
        # read 0.24-1.10 and empty ones <= 0.053 on the three gels tried (sec. 4)
        band = ndimage.gaussian_filter(self.od(R[r0:r1]), 2)
        band = band - np.median(band, axis=1, keepdims=True)
        col = np.percentile(band, LANE_PCT, axis=0)
        p0 = W / count
        col_s = ndimage.gaussian_filter1d(col, p0 * 0.06)
        base = ndimage.uniform_filter1d(ndimage.grey_opening(col_s, size=int(1.2 * p0)), int(0.3 * p0))
        hump = col_s - base
        pk, props = signal.find_peaks(hump, distance=0.6 * p0, prominence=LANE_PROM * hump.max())
        pk = pk[(pk > 0.25 * p0) & (pk < W - 0.25 * p0)]  # the gel's cut edges are not lanes
        fwhm, _, lips, rips = signal.peak_widths(hump, pk, rel_height=0.5)
        pk = (lips + rips) / 2  # FWHM midpoint: a lane's hump can be double-topped
        self.hump = hump
        names = {int(k): v for k, v in ls.get("names", {}).items()}
        labels = {int(k): v for k, v in ls.get("labels", {}).items()}
        lane_w = float(ls.get("width_px") or np.median(fwhm))
        width = {}
        if ls.get("centres"):
            centres = {int(k): float(v) for k, v in ls["centres"].items()}
            pitch = float(np.median(np.diff(sorted(centres.values()))))
            self.lane_fit = "config"
            loaded = {n for n in centres if names.get(n)}
        else:
            centres, pitch, info = fit_lattice(pk, p0, W, count)
            loaded = set()
            for x, n, wd in zip(pk, info["numbers"], fwhm):  # a loaded lane keeps its measured centre
                if 1 <= n <= count:
                    centres[n] = float(x)
                    width[n] = float(wd)
                    loaded.add(n)
            self.lane_fit = info
        self.pitch, self.lane_w = pitch, lane_w
        win = float(ls.get("window", WINDOW))
        hw = max(2.0, win * lane_w / 2)
        self.lane = {}
        for n in range(1, count + 1):
            c = centres[n]
            ext = width.get(n, lane_w) / 2
            self.lane[n] = dict(centre=c, left=c - hw, right=c + hw, ext_left=c - ext, ext_right=c + ext,
                                loaded=n in loaded, name=names.get(n, ""), label=labels.get(n, str(n)))
        # gaps: the band-free strips between neighbouring lanes' full extents, and the two
        # margins; their middle GAP_CORE is what the local background and front are read from
        edge = max(4, int(GAP_EDGE * W))
        bounds = [edge] + [v for n in range(1, count + 1)
                           for v in (self.lane[n]["ext_left"], self.lane[n]["ext_right"])] + [W - edge]
        self.gaps = []
        for i in range(0, len(bounds), 2):
            a, b = bounds[i], bounds[i + 1]
            m, h = (a + b) / 2, GAP_CORE * (b - a) / 2
            c0, c1 = int(round(m - h)), int(round(m + h))
            self.gaps.append(dict(x=m, c0=c0, c1=c1, ok=c1 - c0 >= GAP_MIN_PX))
        if write:
            with open(cfg.out / "lanes.csv", "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["lane", "lane_name", "centre_x", "window_left_x", "window_right_x", "loaded"])
                for n, L in self.lane.items():
                    w.writerow([n, L["name"], f"{L['centre']:.1f}", f"{L['left']:.1f}",
                                f"{L['right']:.1f}", int(L["loaded"])])
            print(f"  lanes: {len(pk)} loaded lane humps at x = "
                  + ", ".join(f"{x:.0f}" for x in pk)
                  + f"; pitch {pitch:.1f} px; lane width (median FWHM) {lane_w:.1f} px; window {2 * hw:.1f} px")
            if isinstance(self.lane_fit, dict):
                print("  lattice: humps are lanes " + ", ".join(str(v) for v in self.lane_fit["numbers"])
                      + "; residuals " + ", ".join(f"{r:+.1f}" for r in self.lane_fit["residuals"]) + " px"
                      + f"; margins {self.lane_fit['margins'][0]:.1f} / {self.lane_fit['margins'][1]:.1f} px")
            bad = [i for i, g in enumerate(self.gaps) if not g["ok"]]
            if bad:
                print(f"  WARNING: gaps {bad} are narrower than {GAP_MIN_PX} px; their neighbours are used")
        return self

    # 4 -----------------------------------------------------------------------
    def lane_cols(self, n):
        L = self.lane[n]
        return slice(int(round(L["left"])), int(round(L["right"])) + 1)

    def bands(self, write=True):
        cfg, R, H, W = self.cfg, self.R, self.H, self.W
        bs = cfg.sect("bands")
        win = int(FRONT_WIN * H)
        a0, a1 = max(0, self.front_guess - win), min(H - 1, self.front_guess + win)
        # each gap: per-row median R (the local background) and the front in it
        gaps = [g for g in self.gaps if g["ok"]]
        fw = []
        for g in gaps:
            g["R"] = np.median(R[:, g["c0"]:g["c1"] + 1], axis=1)
            g["B"] = np.median(self.Bc[:, g["c0"]:g["c1"] + 1], axis=1)
            p = ndimage.gaussian_filter1d(self.od(g["R"]), 2)
            i = a0 + int(np.argmax(p[a0:a1]))
            g["front"] = i + parabola(p, i)
            fw.append(signal.peak_widths(p, [i], rel_height=0.5)[0][0])
        self.front_fwhm = float(np.median(fw))
        gx = np.array([g["x"] for g in gaps])
        gF = np.array([g["front"] for g in gaps])
        # run length (origin to front): over every band-free column, the faint ridge at the
        # top of the resolving gel searched within RUN_WIN of a first estimate from the
        # empty lanes, then the median of (front - ridge)
        clean = np.zeros(W, bool)
        for g in gaps:
            clean[g["c0"]:g["c1"] + 1] = True
        for L in self.lane.values():
            if not L["loaded"]:
                clean[int(L["left"]):int(L["right"]) + 1] = True
        cols = np.where(clean)[0]
        sm = ndimage.gaussian_filter(self.od(R), (RIDGE_SIGMA_Y, RIDGE_SIGMA_X))
        Fc = a0 + np.argmax(sm[a0:a1, cols], axis=0)
        first = []
        for x, f in zip(cols, Fc):
            o0, o1 = int(ORIGIN_SEARCH[0] * f), int(ORIGIN_SEARCH[1] * f)
            first.append(f - (o0 + int(np.argmax(sm[o0:o1, x]))))
        run0 = float(np.median(first))
        Lc = []
        for x, f in zip(cols, Fc):
            o0, o1 = int(f - run0 * (1 + RUN_WIN)), int(f - run0 * (1 - RUN_WIN))
            Lc.append(f - (o0 + int(np.argmax(sm[o0:o1, x]))))
        Lc = np.array(Lc, float)
        self.run_cols = (cols, Lc)
        if bs.get("run") is not None:
            run_all, self.run_src = float(bs["run"]), "config"
        else:
            run_all, self.run_src = float(np.median(Lc)), "measured"
        self.run_all = run_all
        # local background: each gap's profile with the front, the origin ridge and any
        # stray mark closed over (a grey closing on R, i.e. a rolling maximum then minimum,
        # OPEN_FRAC of the run wide), so only the slowly varying stain and lighting divide
        # out. The front itself stays in every lane's profile (flagged at_front): dividing
        # it out carved the Lab 5 ladder's 25 kDa band, which runs on the front line, into
        # two false shoulders.
        ow = max(3, int(OPEN_FRAC * run_all))
        gR = np.stack([ndimage.uniform_filter1d(ndimage.grey_closing(g["R"], size=ow), max(1, ow // 2))
                       for g in gaps])
        gB = np.stack([ndimage.uniform_filter1d(ndimage.grey_closing(g["B"], size=ow), max(1, ow // 2))
                       for g in gaps])
        self.run_iqr = tuple(np.percentile(Lc, [25, 75]))
        front_cfg = bs.get("front")
        origin_cfg = bs.get("origin")
        prom = float(bs.get("prominence", PROMINENCE))
        dfrac = float(bs.get("distance", DISTANCE_FRAC))
        self.prof, self.peaks = {}, {}
        for n, L in self.lane.items():
            c = L["centre"]
            # the two gaps flanking this lane (the nearest usable one on each side)
            li = int(np.searchsorted(gx, c)) - 1
            ri = li + 1
            li, ri = max(li, 0), min(ri, len(gx) - 1)
            if li == ri:
                t = 0.0
            else:
                t = (c - gx[li]) / (gx[ri] - gx[li])
            L["flank"] = (float(gF[li]), float(gF[ri]))
            yf = float(gF[li] + t * (gF[ri] - gF[li])) if front_cfg is None else lane_value(front_cfg, n)
            y0 = yf - run_all if origin_cfg is None else lane_value(origin_cfg, n)
            run = yf - y0
            L.update(origin=y0, front=yf, run=run)
            cs = self.lane_cols(n)
            xg = np.arange(cs.start, cs.stop)
            tt = np.clip((xg - gx[li]) / (gx[ri] - gx[li]), 0, 1) if li != ri else np.zeros(len(xg))
            Rbg = gR[li][:, None] * (1 - tt[None, :]) + gR[ri][:, None] * tt[None, :]
            Bbg = gB[li][:, None] * (1 - tt[None, :]) + gB[ri][:, None] * tt[None, :]
            od = (-np.log10(R[:, cs] / np.clip(Rbg, 1, None))).mean(1)
            L["od_blue"] = ndimage.gaussian_filter1d(
                (-np.log10(self.Bc[:, cs] / np.clip(Bbg, 1, None))).mean(1), max(0.5, SMOOTH_FRAC * run_all))
            od_s = ndimage.gaussian_filter1d(od, max(0.5, SMOOTH_FRAC * run))
            ow = max(3, int(OPEN_FRAC * run))
            base = ndimage.uniform_filter1d(ndimage.grey_opening(od_s, size=ow), max(1, ow // 2))
            base = np.minimum(base, od_s)
            corr = od_s - base
            self.prof[n] = dict(raw=od_s, base=base, corr=corr)
            s0 = int(math.ceil(y0 + 0.005 * run))
            s1 = int(min(H - 2, math.floor(yf + PAST_FRONT * run)))
            pk, pp = signal.find_peaks(corr[s0:s1], prominence=prom, distance=max(1, dfrac * run))
            pk = pk + s0
            widths, wh, lips, rips = signal.peak_widths(corr, pk, rel_height=0.5)
            front_rf = 1 - (self.front_fwhm / 2) / run
            out = []
            for i, y in enumerate(pk):
                yc = y + parabola(corr, y)
                l, r = lips[i], rips[i]
                xx = np.linspace(l, r, max(3, int((r - l) * 4)))
                yy = np.interp(xx, np.arange(H), corr)
                area = float(np.sum((yy[1:] + yy[:-1]) / 2 * np.diff(xx)))
                rf = float((yc - y0) / run)
                out.append(dict(index=i, y=float(yc), Rf=rf, height=float(corr[y]), width=float(widths[i]),
                                area=area, prominence=float(pp["prominences"][i]), at_front=int(rf >= front_rf),
                                unresolved=0))
            # a pair whose valley stays above VALLEY_FRAC of the lower peak is not resolved: a
            # band dark enough to flatten in the photo reads as two maxima (Lab 5's bottom gel,
            # BSA and gamma globulin), and a shoulder looks the same (top gel, egg albumin)
            for p1, p2 in zip(out, out[1:]):
                i1, i2 = int(round(p1["y"])), int(round(p2["y"]))
                valley = float(corr[i1:i2 + 1].min()) if i2 > i1 else 0.0
                if valley >= VALLEY_FRAC * min(p1["height"], p2["height"]):
                    p1["unresolved"] = p2["unresolved"] = 1
            self.peaks[n] = out
        if write:
            self.write_bands()
        return self

    def reported_lanes(self):
        named = [n for n in self.lane if self.lane[n]["name"]]
        return named or list(self.lane)

    def write_bands(self):
        out = self.cfg.out
        with open(out / "bands.csv", "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["lane", "lane_name", "peak_index", "y_px", "Rf", "height", "width", "area",
                        "prominence", "at_front", "unresolved"])
            for n in self.reported_lanes():
                for p in self.peaks[n]:
                    w.writerow([n, self.lane[n]["name"], p["index"], f"{p['y']:.1f}", f"{p['Rf']:.4f}",
                                f"{p['height']:.4f}", f"{p['width']:.1f}", f"{p['area']:.3f}",
                                f"{p['prominence']:.4f}", p["at_front"], p["unresolved"]])
        with open(out / "profiles.csv", "w", newline="") as fh:
            w = csv.writer(fh)
            lanes = self.reported_lanes()
            w.writerow(["y_px"] + [f"lane{n}_od" for n in lanes])
            for y in range(self.H):
                w.writerow([y] + [f"{self.prof[n]['corr'][y]:.4f}" for n in lanes])
        gaps = [g for g in self.gaps if g["ok"]]
        print("  front in the gaps (x: y): " + ", ".join(f"{g['x']:.0f}: {g['front']:.1f}" for g in gaps)
              + f"; front FWHM {self.front_fwhm:.1f} px")
        cols, Lc = self.run_cols
        print(f"  run origin->front ({self.run_src}): {self.run_all:.1f} px; over {len(cols)} band-free "
              f"columns median {np.median(Lc):.1f}, IQR {self.run_iqr[0]:.0f}-{self.run_iqr[1]:.0f}")
        spread = (self.run_iqr[1] - self.run_iqr[0]) / np.median(Lc)
        if spread > RUN_IQR_WARN and self.run_src == "measured" and self.cfg.sect("bands").get("origin") is None:
            print(f"  WARNING: the run's IQR is {100 * spread:.0f} % of it (Lab 5's top gel: 2 %): the origin ridge "
                  "was not found reliably. Look at check.png and set bands.origin or bands.run in the config")
        for n in self.reported_lanes():
            f1, f2 = self.lane[n]["flank"]
            if abs(f1 - f2) > FLANK_WARN * self.lane[n]["run"]:
                print(f"  note: lane {n}'s two flanking fronts differ by {abs(f1 - f2):.1f} px; its front and Rf are "
                      f"less certain than the others' (about +/-{abs(f1 - f2) / 2 / self.lane[n]['run']:.3f} in Rf)")
        for n in self.reported_lanes():
            L = self.lane[n]
            ps = self.peaks[n]
            print(f"  lane {n} ({L['name'] or 'empty'}): origin {L['origin']:.1f}, front {L['front']:.1f} "
                  f"(flanks {L['flank'][0]:.1f} / {L['flank'][1]:.1f}), {len(ps)} peaks: " + ", ".join(
                      f"#{p['index']} Rf {p['Rf']:.3f} h {p['height']:.3f}{' F' if p['at_front'] else ''}"
                      f"{' U' if p['unresolved'] else ''}"
                      for p in ps))

    # 5 -----------------------------------------------------------------------
    def calibrate(self, write=True):
        cfg = self.cfg
        ld = cfg.sect("ladder")
        lane = int(ld.get("lane", 1))
        sizes = [float(s) for s in ld.get("sizes", DEFAULT_SIZES)]
        anchors = [float(a) for a in ld.get("anchors", [75, 25])]
        peaks = self.peaks[lane]
        ref_idx = self.reference_bands(lane, len(anchors))
        L = self.lane[lane]
        if not ld.get("assign"):
            prop = propose_assignment(peaks, sizes, anchors, ref_idx)
            ld["assign"] = {f"{kda:g}": round(peaks[i]["y"], 1) for i, kda in prop.items()}
            ld["assign_note"] = ("proposed by gel_tool.py from the two reference bands: kDa -> the band's y in "
                                 "straightened pixels (snapped to the nearest detected peak); check check.png; "
                                 "a size left out is excluded from the fit")
            cfg.dirty = True
            print("  ladder assignment proposed: " + ", ".join(
                f"{k} kDa = #{i} (y {peaks[i]['y']:.1f})" for i, k in ((i, f"{v:g}") for i, v in prop.items())))
        # "reference_channel": "blue" takes the two reference bands' positions from the blue
        # channel, where the blue dye front does not show (sec. 4: on Lab 5 the 25 kDa band
        # sits on the front, and its red-channel peak is the two merged)
        blue_y = {}
        if ld.get("reference_channel", "red") == "blue":
            for idx, (yb, odb) in zip(ref_idx, getattr(self, "ref_blue", [])):
                blue_y[idx] = yb
        tol = ASSIGN_TOL * L["run"]
        pts = []
        for k, yv in ld["assign"].items():
            if yv is None:
                continue
            kda, yv = float(k), float(yv)
            near = min(peaks, key=lambda p: abs(p["y"] - yv))
            if abs(near["y"] - yv) > tol:
                sys.exit(f"ladder.assign: no ladder peak within {tol:.1f} px of y {yv} ({k} kDa); the nearest is "
                         f"#{near['index']} at y {near['y']:.1f}. Check check.png and correct the config")
            y = float(blue_y.get(near["index"], near["y"]))
            pts.append((near["index"], kda, (y - L["origin"]) / L["run"], y))
        pts.sort(key=lambda t: t[3])
        idxs = [t[0] for t in pts]
        if len(set(idxs)) != len(idxs):
            sys.exit(f"ladder.assign: two sizes snap to the same peak ({idxs}); correct the config")
        model = ld.get("fit", "linear")
        rf = np.array([t[2] for t in pts])
        lm = np.log10([t[1] for t in pts])
        fits = {name: make_model(name, rf, lm) for name in MODELS}
        if model not in fits:
            sys.exit(f"ladder.fit must be one of {', '.join(MODELS)}, not {model!r}")
        fn, r2 = fits[model]
        pred = fn(rf)
        self.fit = dict(model=model, fn=fn, r2=r2, n=len(pts), rf_min=float(rf.min()), rf_max=float(rf.max()),
                        lane=lane, points=pts, all=fits)
        # anchors check: the coloured reference bands are the ones dark in the blue channel
        anchor_idx = {t[0] for t in pts if t[1] in anchors}
        if set(ref_idx) != anchor_idx:
            print("  WARNING: the anchors (" + ", ".join(f"{a:g}" for a in anchors) + " kDa) snap to peaks "
                  + str(sorted(anchor_idx)) + ", but the bands dark in the blue channel are peaks "
                  + str(sorted(ref_idx)))
        if write:
            out = cfg.out
            with open(out / "calibration.csv", "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["peak_index", "kDa", "y_px", "Rf", "log10_kDa", "fit_kDa", "residual_kDa", "residual_pct"])
                for (idx, kda, r, y), pr in zip(pts, pred):
                    fk = 10 ** pr
                    w.writerow([idx, f"{kda:g}", f"{y:.1f}", f"{r:.4f}", f"{math.log10(kda):.4f}", f"{fk:.2f}",
                                f"{fk - kda:+.2f}", f"{100 * (fk - kda) / kda:+.2f}"])
                w.writerow([])
                w.writerow(["# fit", f"{model}: {fn.text}", f"r2 = {r2:.5f}" if r2 is not None else "r2 n/a",
                            f"n = {len(pts)}", f"Rf range {rf.min():.4f}-{rf.max():.4f}"])
            with open(out / "estimates.csv", "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["lane", "lane_name", "peak_index", "y_px", "Rf", "height", "area", "est_kDa",
                            "extrapolated", "at_front", "unresolved"])
                for n in self.reported_lanes():
                    if n == lane:
                        continue
                    for p in self.peaks[n]:
                        est = 10 ** float(fn(np.array([p["Rf"]]))[0])
                        ext = int(p["Rf"] < rf.min() or p["Rf"] > rf.max())
                        w.writerow([n, self.lane[n]["name"], p["index"], f"{p['y']:.1f}", f"{p['Rf']:.4f}",
                                    f"{p['height']:.4f}", f"{p['area']:.3f}", f"{est:.1f}", ext, p["at_front"],
                                    p["unresolved"]])
            names = list(MODELS)
            print(f"  fit ({model}, used): log10(kDa) = {fn.text}; n = {len(pts)}, Rf {rf.min():.3f}-{rf.max():.3f}")
            print("    r^2: " + ", ".join(f"{m} {fits[m][1]:.5f}" if fits[m][1] is not None else f"{m} n/a"
                                         for m in names))
            print("    ladder residuals (%):    " + "  ".join(f"{m:>15s}" for m in names[:2]))
            for (idx, kda, r, y) in pts:
                res = [100 * (10 ** float(fits[m][0](np.array([r]))[0]) - kda) / kda for m in names[:2]]
                print(f"    #{idx:<2d} {kda:6g} kDa  Rf {r:.4f}  " + "  ".join(f"{v:+15.1f}" for v in res))
            print("    sample bands (height >= 0.1, off the front), est. kDa: " + "  ".join(f"{m:>14s}" for m in names))
            for n in self.reported_lanes():
                if n == lane:
                    continue
                for pk in self.peaks[n]:
                    if pk["height"] < 0.1 or pk["at_front"]:
                        continue
                    ests = [10 ** float(fits[m][0](np.array([pk["Rf"]]))[0]) for m in names]
                    ext = "  (outside the ladder's Rf range)" if not rf.min() <= pk["Rf"] <= rf.max() else ""
                    print(f"      lane {n} #{pk['index']} Rf {pk['Rf']:.3f}:" + "".join(f"{e:15.1f}" for e in ests) + ext)
        return self

    def reference_bands(self, lane, k):
        """Ladder peaks that are the coloured reference bands: dark in the BLUE channel.

        Coomassie-blue bands (and the blue dye front) reflect blue and barely register in
        the blue channel; the prestained ladder's red (75 kDa) and green (25 kDa) bands,
        with Coomassie on top, read near-black and absorb blue as well. On Lab 5 the two
        stand out at blue OD 0.39 and 0.66 against <= 0.12 for every other ladder band,
        while in the red channel they are no taller than the blue bands around them.
        """
        L = self.lane[lane]
        pb = L["od_blue"]
        y0, yf, run = L["origin"], L["front"], L["run"]
        s0, s1 = int(y0), int(min(self.H - 2, yf + PAST_FRONT * run))
        pk, pp = signal.find_peaks(pb[s0:s1], prominence=0.03, distance=max(1, DISTANCE_FRAC * run))
        pk = pk + s0
        top = sorted(pk[np.argsort(-pb[pk])[:k]])
        peaks = self.peaks[lane]
        out = []
        for y in top:
            near = min(peaks, key=lambda p: abs(p["y"] - y))
            if abs(near["y"] - y) <= REF_MATCH * run:
                out.append(near["index"])
            print(f"  reference band in the blue channel at y {y} (blue OD {pb[y]:.2f}) -> ladder peak "
                  f"#{near['index']} at y {near['y']:.1f}")
        self.ref_blue = [(int(y), float(pb[y])) for y in top]
        return out

    # 6 -----------------------------------------------------------------------
    def figure(self, write=True):
        cfg = self.cfg
        fs = cfg.sect("figure")
        W, H = self.W, self.H
        fmean = float(np.mean([self.lane[n]["front"] for n in self.lane]))
        crop = fs.get("crop") or [0, FIG_TOP, 1, round(min(1.0, (fmean + 0.06 * H) / H), 4)]
        cx0, cy0, cx1, cy1 = [int(round(c * s)) for c, s in zip(crop, (W, H, W, H))]
        cw, ch = cx1 - cx0, cy1 - cy0
        im = self.img.crop((cx0, cy0, cx1, cy1))
        target = float(fs.get("target_kb", TARGET_KB)) * 1024
        best = None
        # colours first, then width: fewer than 256 colours merged Lab 5's near-black
        # reference bands into the blue ones and banded the background
        for nc in FIG_COLOURS:
            for width in [w for w in FIG_WIDTHS if w <= cw] or [cw]:
                small = im.resize((width, round(ch * width / cw)), Image.Resampling.LANCZOS)
                q = small.quantize(colors=nc, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
                buf = io.BytesIO()
                q.save(buf, format="PNG", optimize=True)
                if buf.tell() <= target:
                    best = (width, nc, buf.getvalue())
                    break
            if best:
                break
        if best is None:
            best = (width, nc, buf.getvalue())
            print(f"  WARNING: nothing fits {target / 1024:.0f} KB; wrote the smallest ({len(best[2]) / 1024:.0f} KB)")
        # labels
        rows = []
        for n, L in self.lane.items():
            fx = (L["centre"] - cx0) / cw
            if 0 <= fx <= 1:
                rows.append(("lane", fx, 0.0, L["label"]))
        if hasattr(self, "fit"):
            lane = self.fit["lane"]
            side = 0.0 if self.lane[lane]["centre"] < W / 2 else 1.0
            marks = fs.get("marks")
            for idx, kda, rf, y in self.fit["points"]:
                if marks is None or kda in [float(m) for m in marks]:
                    rows.append(("mark", side, (y - cy0) / ch, f"{kda:g}"))
        for arr in fs.get("arrows", []):
            n, i = int(arr["lane"]), int(arr["peak"])
            p = self.peaks[n][i]
            rows.append(("arrow", (self.lane[n]["right"] - cx0) / cw, (p["y"] - cy0) / ch, arr.get("text", "")))
        for r in rows:
            if "," in r[3] or "\n" in r[3]:
                sys.exit(f"label text {r[3]!r} contains a comma or a newline; the label file is plain CSV")
        if write:
            out = cfg.out
            (out / "gel.png").write_bytes(best[2])
            with open(out / "gel_labels.csv", "w", newline="") as fh:
                fh.write("kind,x,y,text\n")
                for kind, x, y, t in rows:
                    fh.write(f"{kind},{x:.4f},{y:.4f},{t}\n")
            print(f"  figure: crop {crop} -> gel.png {best[0]} px wide, {best[1]} colours, "
                  f"{len(best[2]) / 1024:.0f} KB; {len(rows)} labels")
            self.check_png(out / "check.png")
        return self

    def check_png(self, path):
        im = self.img.copy()
        d = ImageDraw.Draw(im)
        f = font(max(14, self.W // 80))
        fsmall = font(max(11, self.W // 110))
        for g in self.gaps:
            if g["ok"]:
                for x in (g["c0"], g["c1"]):
                    d.line([(x, 0), (x, self.H)], fill=(0, 255, 255), width=1)
        for n, L in self.lane.items():
            for x in (L["left"], L["right"]):
                d.line([(x, 0), (x, self.H)], fill=(255, 255, 255), width=1)
            d.text((L["centre"] - 6, 4), str(n), fill=(255, 255, 255), font=f)
            d.line([(L["left"] - 10, L["origin"]), (L["right"] + 10, L["origin"])], fill=(0, 255, 0), width=3)
            d.line([(L["left"] - 10, L["front"]), (L["right"] + 10, L["front"])], fill=(255, 0, 255), width=3)
            if n in self.reported_lanes():
                corr = self.prof[n]["corr"]
                scale = (L["right"] - L["left"]) * 0.9 / max(0.05, corr.max())
                pts = [(L["left"] + corr[y] * scale, y) for y in range(self.H)]
                d.line(pts, fill=(255, 255, 255), width=2)
                for p in self.peaks[n]:
                    col = (255, 120, 0) if p["at_front"] else (255, 255, 0)
                    d.line([(L["left"], p["y"]), (L["right"], p["y"])], fill=col, width=2)
                    d.text((L["right"] + 3, p["y"] - 8), str(p["index"]), fill=col, font=fsmall)
        if hasattr(self, "fit"):
            L = self.lane[self.fit["lane"]]
            for idx, kda, rf, y in self.fit["points"]:
                d.text((max(2, L["left"] - 70), y - 8), f"{kda:g}", fill=(255, 255, 255), font=fsmall)
        d.text((10, self.H - 40), "green origin, magenta front, yellow peaks (orange: at front), "
               "white trace = corrected lane OD, cyan = gaps (local background and front)", fill=(255, 255, 255), font=fsmall)
        im.save(path)


# ----------------------------------------------------------------------------- helpers
def parabola(p, i):
    """Sub-sample offset of the extremum through samples i-1, i, i+1."""
    if i <= 0 or i >= len(p) - 1:
        return 0.0
    a, b, c = p[i - 1], p[i], p[i + 1]
    den = a - 2 * b + c
    return 0.0 if den == 0 else float(0.5 * (a - c) / den)


MODELS = ("linear", "quadratic", "point-to-point")


def make_model(name, rf, lm):
    """A calibration model log10(kDa) = f(Rf): returns (callable with .text, r^2 or None)."""
    if name in ("linear", "quadratic"):
        c = np.polyfit(rf, lm, 1 if name == "linear" else 2)

        def fn(x, c=c):
            return np.polyval(c, x)
        fn.text = poly_text(c)
        pr = fn(rf)
        return fn, 1 - float(((lm - pr) ** 2).sum()) / float(((lm - lm.mean()) ** 2).sum())
    # point-to-point: straight lines in log10(kDa) between neighbouring ladder bands;
    # beyond the end bands, the end segment is extended (flagged as extrapolated anyway)
    o = np.argsort(rf)
    xs, ys = rf[o], lm[o]

    def fn(x, xs=xs, ys=ys):
        x = np.asarray(x, float)
        y = np.interp(x, xs, ys)
        lo, hi = x < xs[0], x > xs[-1]
        y[lo] = ys[0] + (x[lo] - xs[0]) * (ys[1] - ys[0]) / (xs[1] - xs[0])
        y[hi] = ys[-1] + (x[hi] - xs[-1]) * (ys[-1] - ys[-2]) / (xs[-1] - xs[-2])
        return y
    fn.text = "point-to-point between the ladder bands"
    return fn, None


def poly_text(c):
    """log10(kDa) polynomial in Rf as text, constant term first."""
    terms = [f"{c[-1]:.5f}"]
    for power, v in enumerate(reversed(c[:-1]), start=1):
        terms.append(f"({v:.5f}) Rf" + ("" if power == 1 else f"^{power}"))
    return " + ".join(terms)


def lane_value(v, n):
    """A config override: one number for every lane, or {"lane": value, ...}."""
    if isinstance(v, dict):
        if str(n) not in v:
            sys.exit(f"lane {n} missing from a per-lane override {v}")
        return float(v[str(n)])
    return float(v)


def fit_lattice(pk, p0, W, count):
    """Fit hump centres to x = x0 + k * pitch (integer k); number lanes so the margins match."""
    if len(pk) == 0:
        sys.exit("no loaded lane found in the column profile; give lanes.centres in the config")
    if len(pk) == 1:
        pitch = p0
        k = np.array([0])
        x0 = pk[0]
    else:
        pitch = p0
        for _ in range(10):
            k = np.round((pk - pk[0]) / pitch)
            if len(set(k)) < len(k):
                break
            pitch, x0 = np.polyfit(k, pk, 1)
        k = np.round((pk - pk[0]) / pitch)
        pitch, x0 = np.polyfit(k, pk, 1)
    # lane 1 centre = x0 - s * pitch for an integer shift s; choose equal margins
    want = (W - (count - 1) * pitch) / 2
    s = int(round((x0 - want) / pitch))
    first = x0 - s * pitch
    centres = {n: float(first + (n - 1) * pitch) for n in range(1, count + 1)}
    numbers = [int(kk + s + 1) for kk in k]
    resid = [float(x - centres[n]) for x, n in zip(pk, numbers)]
    margins = (first, W - (first + (count - 1) * pitch))
    if min(numbers) < 1 or max(numbers) > count:
        print(f"  WARNING: lattice numbering puts a loaded lane outside 1..{count}: {numbers}")
    return centres, float(pitch), dict(numbers=numbers, residuals=resid, margins=margins)


def propose_assignment(peaks, sizes, anchors, ref_idx):
    # every peak, at_front included: on the Lab 5 gel the 25 kDa reference band runs on the front line
    off = list(peaks)
    if len(ref_idx) != 2:
        sys.exit(f"found {len(ref_idx)} reference bands in the blue channel, not 2; "
                 "write ladder.assign in the config by hand from check.png")
    ref = sorted([p for p in off if p["index"] in ref_idx], key=lambda p: p["y"])
    hi_a, lo_a = max(anchors), min(anchors)
    i_hi, i_lo = sizes.index(hi_a), sizes.index(lo_a)
    above = [p for p in off if p["y"] < ref[0]["y"]]
    between = [p for p in off if ref[0]["y"] < p["y"] < ref[1]["y"]]
    want_above, want_between = i_hi, i_lo - i_hi - 1
    if len(above) < want_above or len(between) < want_between:
        sys.exit(f"cannot propose a ladder assignment: {len(above)} peaks above the {hi_a:g} kDa band "
                 f"(the ladder has {want_above}) and {len(between)} between the reference bands (it has "
                 f"{want_between}); write ladder.assign in the config by hand from check.png")
    # more peaks than ladder bands: keep the most prominent, in order of position
    keep_a = sorted(sorted(above, key=lambda p: -p["prominence"])[:want_above], key=lambda p: p["y"])
    keep_b = sorted(sorted(between, key=lambda p: -p["prominence"])[:want_between], key=lambda p: p["y"])
    for p in above + between:
        if p not in keep_a and p not in keep_b:
            print(f"  note: ladder peak #{p['index']} (Rf {p['Rf']:.3f}, prominence {p['prominence']:.3f}) "
                  "left out of the proposal: less prominent than the ladder bands around it")
    above, between = keep_a, keep_b
    assign = {}
    for p, s in zip(above, sizes[:i_hi]):
        assign[p["index"]] = s
    assign[ref[0]["index"]] = hi_a
    for p, s in zip(between, sizes[i_hi + 1:i_lo]):
        assign[p["index"]] = s
    assign[ref[1]["index"]] = lo_a
    below = [p for p in off if p["y"] > ref[1]["y"]]
    for p, s in zip(below, sizes[i_lo + 1:]):
        print(f"  note: ladder peak #{p['index']} (Rf {p['Rf']:.3f}) below the {lo_a:g} kDa band is not "
              f"assigned; it may be {s:g} kDa or several bands compressed together (add it by hand if resolved)")
    return dict(sorted(assign.items()))


# ----------------------------------------------------------------------------- CLI
STAGES = ["straighten", "lanes", "bands", "calibrate", "figure"]


def run(stage: str, config: str):
    cfg = Config(config)
    g = Gel(cfg)
    last = STAGES.index(stage) if stage != "all" else len(STAGES) - 1
    print(f"gel_tool.py {stage} {rel(cfg.path)}")
    for i, name in enumerate(STAGES[:last + 1]):
        getattr(g, name)(write=(stage == "all" or i == last))
    cfg.save()
    return g


def main(argv=None):
    ap = argparse.ArgumentParser(prog="irspec gel", description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=STAGES + ["all"])
    ap.add_argument("config", help="the gel's JSON config (see the module docstring, sec. 2)")
    a = ap.parse_args(argv)
    run(a.stage, a.config)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""spa_tool.py -- standalone OMNIC .SPA/.SPG toolkit for nulabreport IR work.

Self-contained: everything a future session (human or Claude, with or without
project-knowledge access) needs to reproduce this lab's IR pipeline byte-for-
byte is in this file, not spread across a chat-only "standing instructions"
document. If you are extending this script, extend the rule documented here
and the docstring beside it -- don't fork the logic into a one-off snippet.

WHAT THIS IS FOR
    The department's Thermo Nicolet iS5 exports OMNIC binary .SPA (and
    occasionally .SPG, same format) files. Nothing installed on a normal lab
    laptop opens them directly. This script parses them itself (validated
    against a real Spectragryph CSV export to 0.0000 %T -- see read_spa())
    and gets you from raw binary to whatever you actually need:

      convert   .SPA -> the house two-CSV pair, optionally with a peak list
                (manual or automatic) for a nulabreport \\irspectrum call.
      plot      .SPA -> a legacy matplotlib PNG/SVG, for the rare case you
                need something outside the pandoc/nulabreport pipeline.
      batch     several .SPA files -> CSVs for all of them plus one ready-
                to-build pandoc Markdown document using nulabreport's
                peer-share mode (\\labsetup{furniture=false, captions=bare}):
                one spectrum per landscape page, footer caption, no report
                chrome. Feed the .md this produces to pdfmd.py to get the
                actual PDF -- this script does not invoke pandoc/pdfmd
                itself, on purpose: building the PDF is nulabreport's job
                (see nulabreport's own CLAUDE.md), this script's job stops
                at hard, checkable inputs (CSVs, peak lists, a markdown
                document that already follows every layout rule below).

===============================================================================
1. RECOGNISING WHAT YOU'VE GOT
===============================================================================
Both .SPA and .SPG (despite the "group" name, this lab's .SPG exports have
always been single spectra) start with the ASCII magic string
b"Spectral Data File\\r\\n" and share the identical binary layout below --
read_spa() handles both via the same reader; it never assumes extension.

Two point-count/resolution combinations have been seen in this lab's data:
  - 934 points,  3999.64 -> 401.12 cm^-1,  ~56 KB files
  - 3734 points, 4000    -> 400    cm^-1,  ~18-20 KB files
Small file size does NOT mean low resolution (3734-point files are smaller
because of a shorter header, not fewer points). Never hardcode a point count;
read it from the file every time (the reader below already does this).

Filenames may be Latin or Cyrillic, and may contain a typo the student made
on purpose (i.e. really is the filename on disk, e.g. "resgent.SPA" for
"reagent") -- never silently "fix" a filename; the CSV/report calls must
match what's actually on disk. clean_stem() below only strips a numeric
upload-prefix like "1782821956657_", nothing else.

===============================================================================
2. THE VALIDATED PARSER
===============================================================================
OMNIC .SPA stores a small section table starting at byte offset 304 (0x130).
Each entry is 16 bytes: uint16 key, uint32 offset, uint32 size (+ padding).
The spectrum itself lives in the section with key 0x0003; size/4 gives the
float32 point count. The x-axis endpoints (first/last wavenumber) are
float32 at byte offsets 576 and 580. Walk the table until key == 0.

This is copied verbatim from the parser validated in this lab's earlier
sessions (diffed against a real Spectragryph CSV export of the same file,
max difference 0.0000 %T) -- see read_spa() below. Do not change the
offsets without re-validating the same way: parse one file, confirm n
matches size/4, confirm the x-range is sane (~4000 -> 400), and if a
Spectragryph CSV of the same file exists, diff the two.

The OMNIC header also stores its own text peak-picks as
"B<wavenumber>,<depth>" strings (e.g. "B1674,42") -- a free cross-check on
any peaks this script finds, if you want one; not parsed here since nothing
downstream has needed it yet.

===============================================================================
3. TRANSMITTANCE VS ABSORBANCE -- DETECT PER FILE, NEVER ASSUME
===============================================================================
Most files are %Transmittance (baseline high, ~95-105; bands point down). A
few come through as Absorbance (baseline ~0; bands point up; can even dip
slightly negative). Detect per file with axis_of() below -- a real batch has
had exactly one absorbance file mixed in among otherwise-transmittance data.

This is a DEFAULT GUESS, not an enforced decision: nulabreport's own
\\irspectrum/\\irspectrumcompare take the axis label as an explicit LaTeX
argument, so a wrong guess (e.g. a weak-contact spectrum with an
unrepresentative median) is overridden right there in the report call,
without re-running this script. Never silently convert between the two.

===============================================================================
4. THE DETECTOR-NOISE TAIL (<650 cm^-1) AND THE TWO-CSV CONVENTION
===============================================================================
The iS5's DTGS/KBr detector loses sensitivity below ~650 cm^-1 -- data there
is mostly noise. Every file gets TWO CSVs, clipped differently:

  archival (<stem>.csv)        FULL range, untouched. Semicolon-delimited,
                                decimal commas, mirroring a Spectragryph
                                export. Nothing in this pipeline ever trims
                                it -- it is the raw record.
  plain    (<stem>_plain.csv)  Clipped to >=650 cm^-1 AT WRITE TIME (not
                                just wherever it's eventually plotted). This
                                is what \\irspectrum/\\irspectrumcompare read,
                                and what plot() below plots.

Filtering at write time, once, means every downstream consumer reads
already-clean data instead of each re-implementing (and risking forgetting)
the same 650 cm^-1 rule.

===============================================================================
5. PEAKS: A SINGLE SOURCE OF TRUTH
===============================================================================
A nulabreport \\irspectrum peak argument is "wavenumber/label_y" pairs: the
label_y is NOT looked up by the LaTeX macro, it is supplied by whoever
identified the peak -- normally this script. That is deliberate: the same
peak you verify numerically for a Discussion section is the same x/label_y
pair that ends up on the figure, so nothing is ever discussed but left
unlabelled, and there is never a second list to keep in sync.

Recipe (assign_label_y() below): label_y = trough_y - gap (default gap=5,
just past the macro's leader-tick length). Only increase the offset, in
~5-unit steps, when two peaks sit close enough in wavenumber (default
45 cm^-1) that their rotated labels would otherwise collide -- never a
blanket large offset (an over-large gap reads as "label floating far below
the line", which is wrong).

Two picking modes:
  manual  you already know the wavenumbers (e.g. from a Discussion you're
          writing). Give --peaks; each one's actual trough is found within
          +/-15 cm^-1 (never eyeballed).
  auto    a real trough search (scipy.signal.find_peaks on the inverted
          trace), parameterised to approximate Spectragryph's own
          peak-picking dialog as closely as this script's documented (not
          byte-verified) interpretation allows: --threshold (% of the
          window's own dynamic range a trough must clear), --prominence
          (scipy prominence, native %T units), --distance (minimum
          wavenumber gap between accepted peaks). Defaults 5%, 3, 8 cm^-1
          match Spectragryph's own documented defaults.

After picking, render, look at the actual PNG, nudge a number if two labels
collide, rerun. No automatic collision avoidance beyond the staggering
above -- consistent with the rest of this package's philosophy for a
stubborn layout.

===============================================================================
6. AXIS/RANGE SUGGESTIONS FOR THE REPORT CALL
===============================================================================
suggest_bounds() below turns a peak list (plus the raw clipped data) into a
starting point for \\irspectrum's own optional arguments:
  xmin/xmax   always 650 / the file's own true maximum wavenumber, rounded
              up to the nearest 50 -- this just documents the clip already
              applied in the CSV; \\irspectrum does not currently take an
              xmin/xmax argument, so this is informational rather than
              something to paste into the call.
  ymin        a little below the lowest label_y (pgfplots' automatic
              y-range covers the plotted curve only, not labels placed
              below the data minimum -- an unlabelled range silently clips
              them). Same recipe as the ymin suggestion in the batch/manual
              CLI output: floor(min(label_y)/5)*5 - 5.
  ymax        the data's own local maximum in the clipped window, rounded
              up to the nearest 5 plus a couple of points of headroom --
              informational; \\irspectrum's automatic top is normally fine
              and this is only worth pasting in for a spectrum that's
              unusually flat near the top of its own frame.
This is a starting point, not a final answer -- check it against the actual
render (see nulabreport's own manual, and CLAUDE.md's "look at the output"
rule) the same as every other constant in this pipeline.

===============================================================================
7. LEGACY matplotlib PNG/SVG -- THE EXCEPTION, NOT THE DEFAULT
===============================================================================
Before the pandoc/LaTeX pipeline, every file got a matplotlib PNG/SVG pair.
plot() below reproduces those house conventions for the rare cases pgfplots
genuinely struggles with (arrows annotating named bands onto a curve is the
one real example) or work happening outside nulabreport entirely:
  figsize (10, 4.5); line width 0.8; house colour #b03a2e (same hex as
  nulabreport.sty's \\nuirred); x-axis inverted (4000 -> 650); axis labels
  "Wavenumber / cm$^{-1}$" and the detected y-axis; top/right spines
  hidden; SVG text kept editable (svg.fonttype = 'none'); British spelling
  in any caption/label text you add on top. The plotted arrays are filtered
  to x >= 650 directly (not just via xlim) -- the noisy tail's extreme
  values wreck y-autoscaling even when the axis limits hide them.

===============================================================================
8. PEER-SHAREABLE SPECTRA: THE BATCH/LANDSCAPE MARKDOWN
===============================================================================
Sometimes the deliverable is not a lab report at all: a clean PDF of just
the spectra, one per page, full-page, no NU letterhead. nulabreport's own
\\labsetup has two keys for this (furniture=false suppresses the logo/footer
badge; captions=bare pins the caption to the page's bottom edge instead of
typesetting it under the figure, and lets the plot fill the freed space),
and batch() below writes the markdown that uses them correctly:

  - ONE continuous \\begin{landscape}...\\end{landscape} wrapping every
    spectrum, pages separated by a bare \\clearpage -- NOT one landscape
    block per spectrum (nesting a fresh landscape environment per figure
    inserts an empty page between each real one).
  - height=6.8in per figure (not right up against the ~7.3in
    \\textheight ceiling landscape mode inherits from the portrait page's
    own width at margin=0.6in on A4 -- headroom for a tall axis label or a
    long footer caption without silently pushing out an extra blank page
    under \\flushbottom).
  - metadata.yaml-equivalent front matter inline in the one .md file (no
    title page, no bibliography needed for a peer-share document):
    documentclass article, 12pt, a4, lang en-GB, mainfont "STIX Two Text",
    margin=0.6in, header-includes loading nulabreport and setting
    \\labsetup{furniture=false, captions=bare}.

Build the resulting .md with pdfmd.py (never bare pandoc -- see
nulabreport's own CLAUDE.md for why: frontmatter/engine-fallback/citeproc
behaviour a bare pandoc invocation silently skips). Then LOOK AT THE
RENDER (pdftoppm -r 300 -png, read the PNG) before calling it done --
specifically confirm the caption is a bottom-pinned footer line, not
typeset inline under the plot; that distinction has regressed silently
before.

===============================================================================
9. QUICK REFERENCE
===============================================================================
    python3 spa_tool.py convert sample.SPA
    python3 spa_tool.py convert sample.SPA --mode manual --peaks 3320.8,1650.8
    python3 spa_tool.py convert sample.SPA --mode auto
    python3 spa_tool.py plot sample.SPA --png sample.png --svg sample.svg
    python3 spa_tool.py batch --manifest batch.json --out-dir share --md share.md

See --help on each subcommand for the full flag list.
"""
import argparse
import json
import os
import re
import struct
import sys

import numpy as np

CLIP_CM = 650.0
NURED = "#b03a2e"          # nulabreport.sty's \nuirred, same hex
MAGIC = b"Spectral Data File\r\n"


# =============================================================================
# 2. THE VALIDATED PARSER -- do not change these offsets without re-validating
#    against a real Spectragryph export (see module docstring sec. 2).
# =============================================================================
def read_spa(fn):
    """Return (x, y): wavenumber and intensity arrays from an OMNIC .SPA/.SPG
    file. Validated against a Spectragryph export to 0.0000 %T. Handles both
    the 934-point and 3734-point files seen in this lab's data."""
    with open(fn, "rb") as f:
        data = f.read()
    if not data.startswith(MAGIC):
        # Not fatal -- some exports have a slightly different leading blip --
        # but worth a loud warning since every offset below assumes this
        # layout.
        sys.stderr.write(
            f"warning: {fn} does not start with the expected "
            f"'Spectral Data File' magic bytes; parsing anyway, but verify "
            f"the result (see module docstring sec. 2).\n"
        )
    firstx = struct.unpack_from("<f", data, 576)[0]   # max wavenumber
    lastx = struct.unpack_from("<f", data, 580)[0]     # min wavenumber
    p = 304
    off = sz = None
    while p < 512:
        key = struct.unpack_from("<H", data, p)[0]
        offset = struct.unpack_from("<I", data, p + 2)[0]
        size = struct.unpack_from("<I", data, p + 6)[0]
        if key == 3:            # 0x0003 = spectral data block
            off, sz = offset, size
        if key == 0:
            break
        p += 16
    if off is None:
        raise ValueError(
            f"{fn}: no key=0x0003 section found in the table starting at "
            f"byte 304 -- this file's layout doesn't match the validated "
            f"format (see module docstring sec. 2)."
        )
    n = sz // 4
    y = np.array(struct.unpack_from("<%df" % n, data, off))
    x = np.linspace(firstx, lastx, n)
    return x, y


def clean_stem(name):
    """Strip a numeric upload-prefix (e.g. '1782821956657_reagent' ->
    'reagent'). Never transliterates or otherwise "fixes" a filename --
    Cyrillic names and deliberate typos are preserved as-is (see module
    docstring sec. 1)."""
    stem = os.path.splitext(os.path.basename(name))[0]
    return re.sub(r"^\d{10,}_", "", stem)


# =============================================================================
# 3. AXIS DETECTION
# =============================================================================
def axis_of(y, mask=None):
    """Default per-file transmittance/absorbance guess (module docstring
    sec. 3). The report call can always override this explicitly."""
    yy = y[mask] if mask is not None else y
    return "Transmittance %" if np.median(yy) > 10 else "Absorbance"


# =============================================================================
# 4. THE TWO-CSV CONVENTION
# =============================================================================
def write_archival_csv(x, y, out_stem, axis_label):
    """Full-range, untouched, semicolon/decimal-comma archival CSV (module
    docstring sec. 4). out_stem is a path prefix; writes '<out_stem>.csv'."""
    path = f"{out_stem}.csv"
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f";{os.path.basename(out_stem)};\r\n")
        f.write(f"Wavenumbers [1/cm];{axis_label};\r\n")
        for xi, yi in zip(x, y):
            f.write(f"{xi:.3f};{yi:.4f};\r\n".replace(".", ","))
    return path


def write_plain_csv(x, y, out_stem, clip=CLIP_CM):
    """Clipped (>=clip cm^-1, AT WRITE TIME) plain CSV -- what \\irspectrum
    reads (module docstring sec. 4). out_stem is a path prefix; writes
    '<out_stem>_plain.csv'."""
    path = f"{out_stem}_plain.csv"
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("wavenumber,intensity\n")
        for xi, yi in zip(x, y):
            if xi < clip:
                continue
            f.write(f"{xi:.3f},{yi:.4f}\n")
    return path


def write_csvs(x, y, out_stem, axis_label, clip=CLIP_CM):
    """Write BOTH the archival and plain CSV at the same stem (e.g. 'csv/7'
    writes 'csv/7.csv' and 'csv/7_plain.csv'). Use write_archival_csv() /
    write_plain_csv() directly when the two need to live in different
    directories (see process_entry() in batch mode)."""
    archival_path = write_archival_csv(x, y, out_stem, axis_label)
    plain_path = write_plain_csv(x, y, out_stem, clip)
    return archival_path, plain_path


# =============================================================================
# 5. PEAK PICKING
# =============================================================================
def find_peaks_auto(x, y, threshold_pct=5.0, prominence=3.0, distance_cm=8.0,
                     window=CLIP_CM):
    """Trough search over the plotted window (x >= window). Two independent
    gates must both pass: scipy prominence (native y units), and the
    trough's own depth vs. the window's dynamic range (threshold_pct)."""
    from scipy.signal import find_peaks

    mask = x >= window
    xw, yw = x[mask], y[mask]
    inv = -yw
    yrange = yw.max() - yw.min()
    min_depth = threshold_pct / 100.0 * yrange

    dx = abs(xw[1] - xw[0])
    distance_idx = max(1, int(round(distance_cm / dx)))

    idx, _props = find_peaks(inv, prominence=prominence, distance=distance_idx)
    peaks = []
    for i in idx:
        if (yw.max() - yw[i]) < min_depth:
            continue
        peaks.append((float(xw[i]), float(yw[i])))
    peaks.sort(key=lambda p: p[0])
    return peaks


def find_peaks_manual(x, y, wanted, axis_label, window_cm=15.0, order=3):
    """For each wavenumber in `wanted`, find the actual LOCAL trough (or
    crest, for absorbance) nearest that wavenumber -- never trust the
    nominal value itself as the plotted point.

    This deliberately does NOT just take the single deepest point within
    +/-window_cm: two real, distinct features can sit closer than 2*window_cm
    apart (a shallow shoulder ~19 cm^-1 from a much deeper neighbouring
    band is a real case in this lab's own data -- a naive whole-window
    argmin picks up the neighbour's slope instead of the shoulder's own,
    shallower minimum). Instead it finds every genuine local extremum
    (scipy.signal.argrelextrema, order=`order` points either side) within
    the window and takes whichever one is closest in wavenumber to the
    target -- i.e. "the trough near here", not "the deepest thing within
    reach". Falls back to a plain windowed argmin/argmax only if the window
    contains no local extremum at all (a flat or monotonic stretch)."""
    from scipy.signal import argrelextrema

    is_transmittance = axis_label.startswith("Transmittance")
    cmp = np.less if is_transmittance else np.greater
    (extrema_idx,) = argrelextrema(y, cmp, order=order)

    peaks = []
    for wn in wanted:
        cand = extrema_idx[(x[extrema_idx] >= wn - window_cm) & (x[extrema_idx] <= wn + window_cm)]
        if len(cand):
            i = cand[np.argmin(np.abs(x[cand] - wn))]
            x_at, y_at = float(x[i]), float(y[i])
        else:
            win = (x >= wn - window_cm) & (x <= wn + window_cm)
            if not win.any():
                sys.stderr.write(f"warning: no data within {window_cm} cm-1 of {wn}\n")
                continue
            i_local = np.argmin(y[win]) if is_transmittance else np.argmax(y[win])
            x_at, y_at = float(x[win][i_local]), float(y[win][i_local])
        peaks.append((x_at, y_at))
    return peaks


def assign_label_y(peaks, gap=5.0, collision_cm=45.0, step=5.0):
    """label_y = trough_y - gap, staggered further in `step`-sized increments
    only when two peaks sit within collision_cm of each other (module
    docstring sec. 5). Returns (x, y, label_y) triples, sorted by x."""
    peaks = sorted(peaks, key=lambda p: p[0])
    out = []
    prev_x = prev_labely = None
    for x_, y_ in peaks:
        base = y_ - gap
        if prev_x is not None and abs(x_ - prev_x) < collision_cm:
            label_y = min(base, prev_labely - step)
        else:
            label_y = base
        out.append((x_, y_, label_y))
        prev_x, prev_labely = x_, label_y
    return out


def format_peaklist(peaks_xyl, digits_x=1):
    """The exact \\irspectrum 4th-argument string: x/label_y pairs."""
    return ",".join(f"{x_:.{digits_x}f}/{ly:.1f}" for x_, _, ly in peaks_xyl)


def format_review_table(peaks_xyl, ptype="x+y", digits_x=4, digits_y=4):
    lines = []
    for x_, y_, _ly in peaks_xyl:
        if ptype == "x":
            lines.append(f"{x_:.{digits_x}f}")
        elif ptype == "y":
            lines.append(f"{y_:.{digits_y}f}")
        else:
            lines.append(f"{x_:.{digits_x}f} / {y_:.{digits_y}f}%T")
    return lines


# =============================================================================
# 6. AXIS/RANGE SUGGESTIONS
# =============================================================================
def suggest_bounds(x, y, peaks_xyl, clip=CLIP_CM):
    mask = x >= clip
    xmax = float(np.ceil(x[mask].max() / 50.0) * 50.0)
    out = {"xmin": clip, "xmax": xmax}
    if peaks_xyl:
        low = min(ly for _, _, ly in peaks_xyl)
        out["ymin"] = int(low // 5 * 5 - 5)
    ymax_data = float(y[mask].max())
    out["ymax"] = int(np.ceil(ymax_data / 5.0) * 5.0 + 5)
    return out


# =============================================================================
# 7. LEGACY matplotlib PNG/SVG
# =============================================================================
def plot(x, y, axis_label, out_png=None, out_svg=None, clip=CLIP_CM):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    mask = x >= clip
    xw, yw = x[mask], y[mask]

    if out_svg:
        plt.rcParams["svg.fonttype"] = "none"

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(xw, yw, lw=0.8, color=NURED)
    ax.set_xlim(4000, clip)
    ax.set_xlabel("Wavenumber / cm$^{-1}$")
    ax.set_ylabel(axis_label)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()

    written = []
    if out_png:
        fig.savefig(out_png, dpi=300)
        written.append(out_png)
    if out_svg:
        fig.savefig(out_svg)
        written.append(out_svg)
    plt.close(fig)
    return written


# =============================================================================
# 8. BATCH -> PEER-SHARE MARKDOWN
# =============================================================================
MD_FRONTMATTER = """---
documentclass: article
fontsize: 12pt
papersize: a4
lang: en-GB
mainfont: "STIX Two Text"
geometry:
  - margin=0.6in
header-includes: |
  \\usepackage{nulabreport}
  \\labsetup{furniture=false, captions=bare}
---
"""

IRSPECTRUM_TEMPLATE = """\\irspectrum
  [width=\\linewidth,height=6.8in,ymin={ymin}]
  {{{csv_rel}}}
  {{{axis_label}}}
  {{{peaklist}}}
  {{{title}}}
\\clearpage
"""


def latex_escape(s):
    """Escape the handful of LaTeX-special characters that can plausibly
    show up in an axis label or a spectrum title (student names, "Unknown
    N", "Transmittance %", ...). A bare '%' is the one that actually bites
    here -- unescaped, it starts a LaTeX comment and truncates the rest of
    the macro call. \\ is escaped first so the backslashes this function
    itself inserts are not re-escaped."""
    s = s.replace("\\", r"\textbackslash{}")
    for ch, esc in (("%", r"\%"), ("&", r"\&"), ("_", r"\_"), ("#", r"\#"),
                    ("$", r"\$"), ("{", r"\{"), ("}", r"\}")):
        s = s.replace(ch, esc)
    return s


def process_entry(entry, csv_dir, plain_dir):
    """entry: dict with at least 'spa' (path) and 'title'. Optional:
    'mode' (auto/manual, default auto), 'peaks' (comma string, manual mode),
    'threshold', 'prominence', 'distance' (auto mode), 'ymin' (override the
    suggested value). Returns a dict ready for the markdown template plus
    the full peak/bounds info for the review printout."""
    spa_path = entry["spa"]
    title = entry.get("title") or clean_stem(spa_path)
    stem = clean_stem(spa_path)

    x, y = read_spa(spa_path)
    mask = x >= CLIP_CM
    axis_label = entry.get("axis") or axis_of(y, mask)

    archival_path = write_archival_csv(x, y, os.path.join(csv_dir, stem), axis_label)
    plain_path = write_plain_csv(x, y, os.path.join(plain_dir, stem))

    mode = entry.get("mode", "auto")
    if mode == "manual":
        wanted = [float(v) for v in str(entry["peaks"]).split(",")]
        peaks = find_peaks_manual(x, y, wanted, axis_label)
    else:
        peaks = find_peaks_auto(
            x, y,
            threshold_pct=entry.get("threshold", 5.0),
            prominence=entry.get("prominence", 3.0),
            distance_cm=entry.get("distance", 8.0),
        )
    peaks_xyl = assign_label_y(peaks)
    bounds = suggest_bounds(x, y, peaks_xyl)
    ymin = entry.get("ymin", bounds.get("ymin", 0))

    return {
        "title": title,
        "stem": stem,
        "axis_label": axis_label,
        "peaklist": format_peaklist(peaks_xyl),
        "ymin": ymin,
        "bounds": bounds,
        "n_peaks": len(peaks_xyl),
        "archival_path": archival_path,
        "plain_path": plain_path,
    }


def batch(manifest, out_dir, md_path, csv_subdir="csv", plain_subdir="plain"):
    csv_dir = os.path.join(out_dir, csv_subdir)
    plain_dir = os.path.join(out_dir, plain_subdir)
    os.makedirs(csv_dir, exist_ok=True)
    os.makedirs(plain_dir, exist_ok=True)

    results = []
    for entry in manifest:
        r = process_entry(entry, csv_dir, plain_dir)
        results.append(r)
        print(f"# {r['stem']}  axis={r['axis_label']}  n_peaks={r['n_peaks']}  "
              f"ymin={r['ymin']}  -> {r['plain_path']}")

    body = ["\\begin{landscape}"]
    for r in results:
        csv_rel = os.path.relpath(r["plain_path"], out_dir)
        body.append(IRSPECTRUM_TEMPLATE.format(
            ymin=r["ymin"], csv_rel=csv_rel,
            axis_label=latex_escape(r["axis_label"]),
            peaklist=r["peaklist"], title=latex_escape(r["title"]),
        ))
    body.append("\\end{landscape}")

    md = MD_FRONTMATTER + "\n" + "\n".join(body)
    os.makedirs(os.path.dirname(md_path) or ".", exist_ok=True)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    return md_path, results


# =============================================================================
# CLI
# =============================================================================
def cmd_convert(args):
    x, y = read_spa(args.spa)
    mask = x >= CLIP_CM
    axis_label = args.axis or axis_of(y, mask)
    out_stem = args.out or os.path.splitext(args.spa)[0]
    write_csvs(x, y, out_stem, axis_label)

    if args.mode == "manual":
        if not args.peaks:
            sys.exit("manual mode needs --peaks 3320.8,1650.8,...")
        wanted = [float(v) for v in args.peaks.split(",")]
        peaks = find_peaks_manual(x, y, wanted, axis_label)
    else:
        peaks = find_peaks_auto(x, y, threshold_pct=args.threshold,
                                 prominence=args.prominence,
                                 distance_cm=args.distance)

    peaks_xyl = assign_label_y(peaks, gap=args.gap, collision_cm=args.collision_cm)
    bounds = suggest_bounds(x, y, peaks_xyl)

    print(f"# {args.spa}  axis={axis_label}  n_peaks={len(peaks_xyl)}  "
          f"(mode={args.mode}, threshold={args.threshold}%, "
          f"prominence={args.prominence}, distance={args.distance}cm-1)")
    for line in format_review_table(peaks_xyl, args.type, args.digits_x, args.digits_y):
        print("  ", line)
    print()
    print("peaklist:", format_peaklist(peaks_xyl, args.digits_x))
    print("ymin suggestion:", bounds.get("ymin", "n/a"))
    print("xmax (informational):", bounds["xmax"])


def cmd_plot(args):
    x, y = read_spa(args.spa)
    mask = x >= CLIP_CM
    axis_label = args.axis or axis_of(y, mask)
    written = plot(x, y, axis_label, out_png=args.png, out_svg=args.svg)
    for w in written:
        print("wrote", w)


def cmd_batch(args):
    if args.manifest:
        with open(args.manifest) as f:
            manifest = json.load(f)
    else:
        if not args.spa:
            sys.exit("batch needs --manifest FILE.json or --spa FILE1.SPA FILE2.SPA ...")
        titles = args.titles.split(",") if args.titles else [None] * len(args.spa)
        if len(titles) != len(args.spa):
            sys.exit("--titles must have exactly one entry per --spa file")
        manifest = [{"spa": s, "title": t} for s, t in zip(args.spa, titles)]

    md_path, results = batch(manifest, args.out_dir, args.md)
    print(f"\nwrote {md_path} ({len(results)} spectra)")
    print("build it with pdfmd.py -- never bare pandoc (see nulabreport's CLAUDE.md)")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="command", required=True)

    p_conv = sub.add_parser("convert", help="one .SPA -> CSV pair [+ peak list]")
    p_conv.add_argument("spa")
    p_conv.add_argument("--out", default=None, help="output CSV stem (default: input stem)")
    p_conv.add_argument("--axis", default=None, help="override axis label instead of auto-detecting")
    p_conv.add_argument("--mode", choices=["auto", "manual"], default="auto")
    p_conv.add_argument("--peaks", default="", help="manual mode: comma list of wavenumbers")
    p_conv.add_argument("--threshold", type=float, default=5.0)
    p_conv.add_argument("--prominence", type=float, default=3.0)
    p_conv.add_argument("--distance", type=float, default=8.0)
    p_conv.add_argument("--gap", type=float, default=5.0)
    p_conv.add_argument("--collision-cm", type=float, default=45.0)
    p_conv.add_argument("--type", choices=["x+y", "x", "y"], default="x+y")
    p_conv.add_argument("--digits-x", type=int, default=4)
    p_conv.add_argument("--digits-y", type=int, default=4)
    p_conv.set_defaults(func=cmd_convert)

    p_plot = sub.add_parser("plot", help="one .SPA -> legacy matplotlib PNG/SVG")
    p_plot.add_argument("spa")
    p_plot.add_argument("--png", default=None)
    p_plot.add_argument("--svg", default=None)
    p_plot.add_argument("--axis", default=None)
    p_plot.set_defaults(func=cmd_plot)

    p_batch = sub.add_parser("batch", help="several .SPA -> CSVs + one peer-share markdown")
    p_batch.add_argument("--manifest", default=None,
                          help="JSON list of {spa, title, mode, peaks, threshold, "
                               "prominence, distance, ymin, axis} -- see module docstring")
    p_batch.add_argument("--spa", nargs="+", default=None,
                          help="quick mode: files in the order they should appear; "
                               "pairs with --titles; always uses auto peak-picking")
    p_batch.add_argument("--titles", default=None, help="comma list matching --spa, one title each")
    p_batch.add_argument("--out-dir", required=True, help="directory for csv/ and plain/ subfolders")
    p_batch.add_argument("--md", required=True, help="output .md path")
    p_batch.set_defaults(func=cmd_batch)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

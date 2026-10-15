#!/usr/bin/env python3
"""spa_peaks.py -- IR peak-picker for nulabreport: OMNIC .SPA, WebBook/JCAMP
.jdx, or either house CSV convention, all through one CLI.

Two jobs, matching the two modes the author asked for:

  1. For a .SPA input only: parse it into the house two-CSV convention
     (archival = full range; plain = clipped to >=650 cm^-1 at write time --
     see SPA_PROCESSING_INSTRUCTIONS.md sec. 2 and 4, the validated reader is
     copied verbatim from there). A .jdx or .csv input is NOT re-written to
     CSV here -- see section 0 below for why.

  2. Peak picking, in two modes:
       --mode manual   you already know the wavenumbers (e.g. from a
                        Discussion you're writing); pass them with --peaks
                        and this script only computes each one's trough
                        depth and a non-colliding label_y.
       --mode auto     genuine automated peak search over the raw data,
                        parameterised the way Spectragryph's own peak-label
                        dialog is (the author's spec, verbatim):
                          type       x+y / x / y / gamma / libs / xrf
                          threshold  % of the spectrum's own dynamic range
                                     (max-min over the plotted window) that
                                     a trough must clear to count at all
                          prominence scipy's prominence, in native y units
                                     (%T points) -- how much the trough
                                     stands out from its shoulders
                          digits x/y number of decimal places to report
                          angle      passed straight through to the figure;
                                     nulabreport's own \\Lab@irpeak already
                                     draws every label rotated 90 degrees
                                     (the Spectragryph default), so this is
                                     only a sanity echo, not a knob this
                                     script can turn independently.

  IMPORTANT, told plainly rather than silently assumed: Spectragryph is
  closed-source and wasn't run side-by-side with this script, so "threshold"
  and "prominence" below are this script's own, documented interpretation of
  what those two dialog fields do -- not a byte-for-byte reproduction. They
  are exposed as CLI flags precisely so they can be tuned per spectrum
  against your own judgement (or a real Spectragryph screenshot), the same
  way nulabreport's own peak-labelling has always worked: render, look,
  nudge, rerun.

  Also told plainly: "type" (x+y / x-only / y-only) changes what THIS
  SCRIPT prints for you to review, not what the LaTeX figure shows. Every
  real spectrum in this package's own corpus, and standard organic-chemistry
  practice generally, labels IR peaks by wavenumber alone -- \\Lab@irpeak
  only ever draws the x value. So the figure's own label is always x-only,
  matching the house convention already in use; --type here only controls
  the verification table this script prints, so you can cross-check against
  a real x+y peak-picking readout without the figure itself getting
  cluttered with intensity numbers nobody asked to see on the page.

===============================================================================
0. THREE INPUT FORMATS, ONE PEAK-FINDER (added 2026-09-22)
===============================================================================
Originally this script only read raw OMNIC .SPA binaries. It now also
accepts a .jdx (WebBook/JCAMP-DX reference spectrum) or a .csv (either house
convention -- the semicolon/decimal-comma archival form, or the comma/
decimal-point "plain" form) directly, auto-detected from the extension and,
for CSV, from its first data line. This does NOT duplicate jdx_tool.py or
spa_tool.py's own CSV-writing jobs:

  - .SPA input:  unchanged behaviour -- writes the archival+plain CSV pair
                 (write_csvs()), THEN peak-picks off the raw array.
  - .jdx input:  decoded in-memory via jdx_tool.read_jdx() (imported from
                 this same tools/ folder, never re-implemented here -- see
                 jdx_tool.py's own module docstring for the validated
                 parser). Nothing is written to disk; producing that
                 compound's csv/ and plain/ files is jdx_tool.py's job
                 (`jdx_tool.py batch jdx/ --out-dir csv/ --name-map ...`),
                 done once when the reference is first added. This script
                 only peak-picks, reusing whatever plain CSV already exists
                 -- or, if you hand it the raw .jdx directly, decodes it the
                 same way jdx_tool.py would, purely in memory, to peak-pick
                 without needing the plain CSV to exist yet.
  - .csv input:  read directly, format auto-detected (see read_house_csv()
                 below). Nothing is written back.

  Two things a .jdx input does that a .SPA/.csv one doesn't, both because
  jdx sources vary in ways OMNIC data never does:

  - FRACTIONAL TRANSMITTANCE IS RESCALED x100 FOR PEAK-FINDING ONLY.
    WebBook .jdx Transmittance is fractional (0-1); this lab's own %T scale
    (0-100) is what every default threshold/prominence value in this script
    is tuned against. Peak-finding on the raw 0-1 data with prominence=3.0
    would find nothing (the whole dynamic range is <=1.0). This is NOT the
    Absorbance<->Transmittance conversion jdx_tool.py's own docstring
    correctly refuses to do silently -- it is a within-Transmittance
    unit rescale (fraction -> percent), done here purely so this script's
    peak-finding parameters mean the same thing regardless of source. The
    wavenumbers/intensities this prints are on the same 0-100 scale that
    compound's own plain CSV is on -- as of 2026-09-22, jdx_tool.py's
    `convert --plain-out` / `batch --plain-dir` writes that plain CSV with
    the identical x100 rescale (see jdx_tool.py's own docstring sec. 5), so
    the peak list here and the plotted curve agree with no manual step.
    (Before that date this was done by a one-off script, since folded into
    jdx_tool.py itself and deleted -- if you're reading an old note that
    still points at a one-off script, it no longer exists; use
    jdx_tool.py's --plain-out/--plain-dir instead.)
  - ABSORBANCE SOURCES SEARCH FOR PEAKS, NOT TROUGHS. A .jdx file's own
    ##YUNITS can be Absorbance (e.g. WebBook's propiophenone, confirmed in
    LR3's decode_notes.md) instead of Transmittance. Absorbance bands point
    UP; Transmittance bands point DOWN (troughs). The original version of
    this script always inverted y and searched for troughs, which is
    correct for every OMNIC file (always %T) but silently wrong for an
    Absorbance .jdx -- it would have found the gaps between real bands,
    not the bands themselves. find_peaks_auto()/assign_label_y() now take
    an explicit `absorbance` flag; load_spectrum() below sets it correctly
    from the source's own axis label, so the CLI does this right without
    the caller having to know or ask.

  A CSV's axis label cannot always be recovered from the file alone: the
  "plain" 2-column form has no header field for it (by house convention it
  is always already on the lab's %T-equivalent scale, so this script
  assumes Transmittance for a bare plain CSV) and even the archival form's
  header only ever says "Transmittance" or "Absorbance" verbatim -- read
  and trusted as-is. Override either guess with --axis if a particular file
  needs it.

===============================================================================
1. THE VALIDATED .SPA READER (unchanged)
===============================================================================
Kept verbatim; see spa_tool.py's own module docstring for the full history
of this reader (934- and 3734-point files, validated against a real
Spectragryph export to 0.0000 %T).
"""
import argparse
import csv
import os
import struct
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jdx_tool  # noqa: E402  -- same tools/ folder; see section 0 above


# --- the validated reader, copied verbatim from SPA_PROCESSING_INSTRUCTIONS.md ----
def read_spa(fn):
    """Return (x, y): wavenumber and intensity arrays from an OMNIC .SPA/.SPG file.
    Validated against Spectragryph export to 0.0000 %T. Handles 934- and 3734-point files."""
    data = open(fn, 'rb').read()
    firstx = struct.unpack_from('<f', data, 576)[0]   # max wavenumber
    lastx = struct.unpack_from('<f', data, 580)[0]     # min wavenumber
    p = 304
    off = sz = None
    while p < 512:
        key = struct.unpack_from('<H', data, p)[0]
        offset = struct.unpack_from('<I', data, p + 2)[0]
        size = struct.unpack_from('<I', data, p + 6)[0]
        if key == 3:
            off, sz = offset, size
        if key == 0:
            break
        p += 16
    n = sz // 4
    y = np.array(struct.unpack_from('<%df' % n, data, off))
    x = np.linspace(firstx, lastx, n)
    return x, y


def axis_of(y, mask):
    return 'Transmittance %' if np.median(y[mask]) > 10 else 'Absorbance'


def write_csvs(x, y, out_stem, axis_label):
    """House two-CSV convention (SPA_PROCESSING_INSTRUCTIONS.md sec. 4)."""
    with open(f'{out_stem}.csv', 'w', encoding='utf-8') as f:
        f.write(f';{out_stem};\r\n')
        f.write(f'Wavenumbers [1/cm];{axis_label};\r\n')
        for xi, yi in zip(x, y):
            f.write(f'{xi:.3f};{yi:.4f};\r\n'.replace('.', ','))
    with open(f'{out_stem}_plain.csv', 'w', encoding='utf-8') as f:
        f.write('wavenumber,intensity\n')
        for xi, yi in zip(x, y):
            if xi < 650:
                continue
            f.write(f'{xi:.3f},{yi:.4f}\n')


# =============================================================================
# SECTION 0 SUPPORT: reading a .jdx or either house CSV convention directly
# =============================================================================
def read_house_csv(path):
    """Read either house CSV convention and return (x, y, axis_label).
    Auto-detected from the first data line:
      - archival: ';name;' / 'Wavenumbers [1/cm];AxisLabel;' header, then
        'x;y;' rows, decimal commas (jdx_tool.py's write_csv(), spa_tool.py's
        write_archival_csv()).
      - plain: 'wavenumber,intensity' header, then 'x,y' rows, decimal point
        (jdx_tool.py's decoded output shape, spa_tool.py's write_plain_csv()).
    Order in the file (ascending or descending) is preserved as given --
    find_peaks_auto() doesn't care. A bare plain CSV has no axis field in
    the file itself; by house convention it is already on the %T-equivalent
    scale, so this returns 'Transmittance %' for it -- override with --axis
    if a particular file is actually Absorbance on the plain convention."""
    with open(path, encoding="utf-8") as f:
        lines = [ln.rstrip("\r\n") for ln in f if ln.strip()]
    if not lines:
        raise ValueError(f"{path}: empty file")

    if lines[0].startswith(";"):
        # archival: ';name;' then 'Wavenumbers [1/cm];AxisLabel;' then data
        axis_label = lines[1].split(";")[1]
        xs, ys = [], []
        for line in lines[2:]:
            parts = line.split(";")
            xs.append(float(parts[0].replace(",", ".")))
            ys.append(float(parts[1].replace(",", ".")))
        return np.array(xs), np.array(ys), axis_label

    # plain: 'wavenumber,intensity' header then 'x,y' rows
    xs, ys = [], []
    for line in lines[1:]:
        x_str, y_str = line.split(",")[:2]
        xs.append(float(x_str))
        ys.append(float(y_str))
    return np.array(xs), np.array(ys), "Transmittance %"


def read_jdx_as_xy(path):
    """Decode a .jdx via jdx_tool.read_jdx() (never re-implemented here) and
    return (x, y, axis_label) ready for peak-finding. Fractional Transmittance
    is rescaled x100 for peak-finding purposes only -- see module docstring
    section 0 for exactly why this is not the Absorbance<->Transmittance
    conversion jdx_tool.py itself refuses to do."""
    xs, ys, meta = jdx_tool.read_jdx(path)
    xs = np.array(xs)
    ys = np.array(ys)
    if meta["axis_label"] == "Transmittance":
        ys = ys * 100.0
        axis_label = "Transmittance %"
    else:
        axis_label = "Absorbance"
    return xs, ys, axis_label


def load_spectrum(path, axis_override=None):
    """Dispatch on extension: .spa/.spg -> raw binary reader; .jdx ->
    jdx_tool; .csv -> either house convention. Returns (x, y, axis_label,
    kind) where kind is 'spa' / 'jdx' / 'csv' -- callers use kind to decide
    whether write_csvs() should run (only ever for 'spa'; see section 0)."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".spa", ".spg"):
        x, y = read_spa(path)
        axis_label = axis_override or axis_of(y, x >= 650)
        return x, y, axis_label, "spa"
    elif ext == ".jdx":
        x, y, axis_label = read_jdx_as_xy(path)
        return x, y, (axis_override or axis_label), "jdx"
    elif ext == ".csv":
        x, y, axis_label = read_house_csv(path)
        return x, y, (axis_override or axis_label), "csv"
    else:
        raise ValueError(f"{path}: unrecognised extension {ext!r} -- expected .SPA/.SPG/.jdx/.csv")


def find_peaks_auto(x, y, threshold_pct=5.0, prominence=3.0, distance_cm=8.0,
                     window=650, absorbance=False):
    """Local-extremum search over the plotted window (x >= window). For
    Transmittance data (absorbance=False, the default -- every OMNIC file
    and most WebBook .jdx files), bands are TROUGHS: inverts y and searches
    for minima. For Absorbance data (absorbance=True -- e.g. WebBook's
    propiophenone, confirmed Absorbance-native in LR3's decode_notes.md),
    bands point UP: searches y directly for maxima instead. Getting this
    backwards finds the gaps between real bands, not the bands themselves --
    see module docstring section 0 for how this is now set automatically
    from the source's own axis label rather than left for the caller to
    remember.

    Returns a list of (wavenumber, y_at_peak) sorted by wavenumber.

    Two independent gates, both must pass (see module docstring for what each
    one is trying to approximate):
      - prominence: scipy's own prominence, in native y units (%T points, or
        Absorbance units).
      - threshold_pct: the band's OWN depth/height (distance from a full,
        unabsorbed baseline) must be at least this fraction of the
        spectrum's dynamic range over the plotted window.
    """
    from scipy.signal import find_peaks

    mask = x >= window
    xw, yw = x[mask], y[mask]
    sig = yw if absorbance else -yw
    yrange = yw.max() - yw.min()
    min_depth = threshold_pct / 100.0 * yrange

    # scipy needs an index-space distance; the data is evenly spaced in x
    # for OMNIC and cm^-1-native jdx files. A jdx file decoded from
    # MICROMETERS (see jdx_tool.py docstring sec. 3) is NOT evenly spaced
    # in cm^-1 after conversion -- dx below is only the FIRST interval, so
    # `distance` drifts across such a file's range. Not fixed here; if a
    # micrometer-sourced file's peak list looks wrong, check this first.
    dx = abs(xw[1] - xw[0])
    distance_idx = max(1, int(round(distance_cm / dx)))

    idx, props = find_peaks(sig, prominence=prominence, distance=distance_idx)
    peaks = []
    for i in idx:
        depth = (yw[i] - yw.min()) if absorbance else (yw.max() - yw[i])
        if depth < min_depth:
            continue
        peaks.append((float(xw[i]), float(yw[i])))
    peaks.sort(key=lambda p: p[0])
    return peaks


def assign_label_y(peaks, gap=5.0, collision_cm=45.0, step=5.0, absorbance=False):
    """label_y = trough_y - gap (Transmittance: label sits below the dip) or
    peak_y + gap (Absorbance: label sits above the band -- bands point up,
    so a label placed the Transmittance way would sit ON TOP of the curve
    instead of clear of it), staggered further when two peaks sit close
    enough in wavenumber for their (rotated) labels to collide -- exactly
    the recipe in nulabreport.sty sec.15 / SPA_PROCESSING_INSTRUCTIONS.md
    sec.5: small gap by default, only pushed further in ~5-unit steps for a
    genuinely close pair, never a blanket large offset.
    """
    sign = 1.0 if absorbance else -1.0
    peaks = sorted(peaks, key=lambda p: p[0])
    out = []
    prev_x = None
    prev_labely = None
    for x_, y_ in peaks:
        base = y_ + sign * gap
        if prev_x is not None and abs(x_ - prev_x) < collision_cm:
            label_y = max(base, prev_labely + sign * step) if absorbance else min(base, prev_labely - step)
        else:
            label_y = base
        out.append((x_, y_, label_y))
        prev_x, prev_labely = x_, label_y
    return out


def format_peaklist(peaks_xyl, digits_x=1, ):
    """Emit the exact `\\irspectrum` 4th-argument string: x/label_y pairs."""
    return ",".join(f"{x_:.{digits_x}f}/{ly:.1f}" for x_, _, ly in peaks_xyl)


def format_review_table(peaks_xyl, ptype="x+y", digits_x=4, digits_y=4, axis_label="Transmittance %"):
    """Human-readable verification table (script's own review output --
    NOT what appears on the figure; see module docstring)."""
    unit = "%T" if axis_label.startswith("Transmittance") else "A"
    lines = []
    for x_, y_, ly in peaks_xyl:
        if ptype == "x":
            lines.append(f"{x_:.{digits_x}f}")
        elif ptype == "y":
            lines.append(f"{y_:.{digits_y}f}")
        else:
            lines.append(f"{x_:.{digits_x}f} / {y_:.{digits_y}f}{unit}")
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help=".SPA/.SPG, .jdx, or house .csv (archival or plain) file to process")
    ap.add_argument("--out", default=None, help=".SPA input only: output CSV stem (default: input stem)")
    ap.add_argument("--axis", default=None, help="override axis label instead of auto-detecting (e.g. 'Absorbance')")
    ap.add_argument("--mode", choices=["auto", "manual"], default="auto")
    ap.add_argument("--peaks", default="", help="manual mode: comma list of wavenumbers, e.g. 3320.8,1650.8,1224.6")
    ap.add_argument("--threshold", type=float, default=5.0, help="auto mode: %% of dynamic range (default 5, Spectragryph default)")
    ap.add_argument("--prominence", type=float, default=3.0, help="auto mode: scipy prominence in native y units (default 3, Spectragryph default)")
    ap.add_argument("--distance", type=float, default=8.0, help="auto mode: minimum wavenumber gap between accepted peaks, cm-1 (default 8)")
    ap.add_argument("--type", choices=["x+y", "x", "y"], default="x+y", help="review-table content (figure label is always x-only, see docstring)")
    ap.add_argument("--digits-x", type=int, default=4)
    ap.add_argument("--digits-y", type=int, default=4)
    ap.add_argument("--angle", type=int, default=90, help="sanity echo only -- the figure always rotates labels 90 degrees")
    ap.add_argument("--gap", type=float, default=5.0, help="default label_y offset below (Transmittance) or above (Absorbance) the band")
    ap.add_argument("--collision-cm", type=float, default=45.0, help="wavenumber gap below which neighbouring labels are staggered")
    ap.add_argument("--step", type=float, default=5.0, help="extra label_y offset per staggered collision (native y units -- see --gap)")
    args = ap.parse_args()

    x, y, axis_label, kind = load_spectrum(args.input, axis_override=args.axis)
    absorbance = axis_label == "Absorbance"

    if absorbance:
        window_mask = x >= 650
        yrange = float(y[window_mask].max() - y[window_mask].min())
        sys.stderr.write(
            f"note: Absorbance input -- --threshold/--prominence/--gap are native y "
            f"units (Absorbance, typically 0-1), NOT the %T-tuned defaults "
            f"(prominence=3.0, gap=5.0, step=5.0 assume a 0-100 scale). This "
            f"file's own dynamic range over the plotted window is {yrange:.4f} A; "
            f"scale --prominence/--gap/--step down accordingly (e.g. "
            f"--prominence {max(yrange * 0.05, 0.005):.3f} --gap "
            f"{max(yrange * 0.08, 0.01):.3f} --step {max(yrange * 0.08, 0.01):.3f}) "
            f"or you will get 0 peaks (prominence too strict) or every label "
            f"collapsed to the same offset (gap/step swallowing real height "
            f"differences) -- both reproduced and documented 2026-09-22.\n"
        )

    if kind == "spa":
        out_stem = args.out or args.input.rsplit(".", 1)[0]
        write_csvs(x, y, out_stem, axis_label)
    elif args.out:
        sys.stderr.write(f"note: --out is ignored for a .{kind} input -- see module docstring section 0\n")

    if args.mode == "manual":
        if not args.peaks:
            sys.exit("manual mode needs --peaks 3320.8,1650.8,...")
        wanted = [float(v) for v in args.peaks.split(",")]
        peaks = []
        for wn in wanted:
            win = (x >= wn - 15) & (x <= wn + 15)
            if absorbance:
                i_local = np.argmax(y[win])
            else:
                i_local = np.argmin(y[win])
            y_at = y[win][i_local]
            x_at = x[win][i_local]
            peaks.append((float(x_at), float(y_at)))
    else:
        peaks = find_peaks_auto(x, y, threshold_pct=args.threshold,
                                 prominence=args.prominence,
                                 distance_cm=args.distance,
                                 absorbance=absorbance)

    peaks_xyl = assign_label_y(peaks, gap=args.gap, collision_cm=args.collision_cm,
                                step=args.step, absorbance=absorbance)

    print(f"# {args.input}  kind={kind}  axis={axis_label}  n_peaks={len(peaks_xyl)}  "
          f"(mode={args.mode}, threshold={args.threshold}%, prominence={args.prominence}, "
          f"distance={args.distance}cm-1, type={args.type}, digits_x={args.digits_x}, "
          f"digits_y={args.digits_y}, angle={args.angle})")
    for line in format_review_table(peaks_xyl, args.type, args.digits_x, args.digits_y, axis_label):
        print("  ", line)
    print()
    print("peaklist:", format_peaklist(peaks_xyl))
    if peaks_xyl:
        if absorbance:
            print("ymax suggestion:", int(max(ly for _, _, ly in peaks_xyl) // 5 * 5 + 5))
        else:
            print("ymin suggestion:", int(min(ly for _, _, ly in peaks_xyl) // 5 * 5 - 5))
    else:
        print("ymin suggestion: n/a")


if __name__ == "__main__":
    main()

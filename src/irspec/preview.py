"""irspec preview: one spectrum, drawn as plain text on stdout.

    irspec preview FILE [--width N] [--height N] [--ascii] [--json]

FILE is an OMNIC .SPA/.SPG, a JCAMP-DX .jdx or a house CSV (archival or plain),
read the way `irspec peaks` reads them. Nothing is written, nothing is asked,
no terminal is needed; the output is the same text on a terminal and in a pipe,
except for the width default (the terminal's own when stdout is a terminal, 80
columns otherwise) and the dot characters (Braille when stdout's encoding is
UTF-8, else `. : * |`).

The plot has the wavenumber axis from the figure's limits (layout.XLIM, 4000 to
650 left to right), intensity up, the trace in the figure's window and the
y limits the figure would use (layout.ylimits, with the `ymin` the session would
write). Each picked peak gets a symbol (1-9, then A-Z, then a-z) under the band
(above it for an absorbance spectrum), and the text block below lists the
peaks with their symbols. A peak whose cell has no free room near the curve is
listed with `-` and is not marked.

What the figure would show is worked out by the code `irspec session` runs:
the peaks by `ir_organize._finish` (hence `find_peaks_auto`, `assign_label_y`,
`find_peaks_manual` for bare numbers), the jdx conversions as the plain CSV
session writes (fractional %T times 100, absorbance to %T, x to 3 and y to 4
decimals). If FILE is listed in a manifest.json in its folder or the folder
above, that entry's peaks, thresholds, `axis` and `ymin` are used, as a re-run
of the session would. Otherwise the peaks are the automatic ones.

--json prints exactly one object on stdout and no plot:

    {"file", "kind", "axis", "converted_from", "points", "range": {"x", "y"},
     "ymin", "peaks": [[wavenumber, label_y], ...], "peaks_from"}

Exit status: 0 done; 2 when the file cannot be read or drawn (the reason is on
stderr). The honest limit: shape, ranges, peak positions and which peaks are
marked. Not fonts, the exact placement of the labels in the figure or its tick
spacing.
"""
import argparse
import json
import os
import shutil
import sys

import numpy as np

from . import layout

DEFAULT_WIDTH = 80      # columns when stdout is not a terminal
DEFAULT_HEIGHT = 20     # rows of plot
MIN_WIDTH, MIN_HEIGHT = 30, 3
SYMBOLS = "123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
TRANSMITTANCE = "Transmittance %"

# Braille dot (column, row) -> bit
_BRAILLE = {(0, 0): 0x01, (0, 1): 0x02, (0, 2): 0x04, (1, 0): 0x08,
            (1, 1): 0x10, (1, 2): 0x20, (0, 3): 0x40, (1, 3): 0x80}


class PreviewError(Exception):
    """A reason to stop with exit status 2."""


# -----------------------------------------------------------------------------
# reading: the spectrum as the figure would have it
# -----------------------------------------------------------------------------
def find_manifest_entry(path):
    """(entry, manifest_path) of the manifest.json entry for `path`, looked for in the file's
    folder and the one above it; (None, None) if there is none."""
    target = os.path.normcase(os.path.abspath(path))
    folder = os.path.dirname(target)
    for base in (folder, os.path.dirname(folder)):
        mpath = os.path.join(base, "manifest.json")
        try:
            with open(mpath, encoding="utf-8") as f:
                entries = json.load(f)
        except (OSError, ValueError):
            continue
        if not isinstance(entries, list):
            continue
        for e in entries:
            if not isinstance(e, dict):
                continue
            name = e.get("file") or e.get("spa") or e.get("jdx")
            if isinstance(name, str) and os.path.normcase(
                    os.path.abspath(os.path.join(base, name))) == target:
                return e, mpath
    return None, None


def load(path, entry):
    """(x, y, axis, absorbance, kind, converted_from) as `irspec session` would draw FILE."""
    from . import absorbance_to_transmittance as a2t
    from . import jdx_tool, spa_peaks, spa_tool
    ext = os.path.splitext(path)[1].lower()
    axis_given = (entry or {}).get("axis")
    if ext in (".spa", ".spg"):
        x, y = spa_tool.read_spa(path)
        axis = axis_given or spa_tool.axis_of(y, x >= spa_tool.CLIP_CM)
        return x, y, axis, axis.startswith("Absorbance"), "spa", None
    if ext in (".jdx", ".dx", ".jcm"):
        from . import session
        xs, ys, meta = jdx_tool.read_jdx(path)
        kind = session._jdx_kind(path)
        if kind == "quantir":  # absorptivity: scaled to an absorbance as the session does
            e = entry or {}
            top = max(ys)
            if "cl" in e:
                cl = float(e["cl"])
            elif "peak_a" in e and top > 0:
                cl = float(e["peak_a"]) / top
            else:
                raise PreviewError(
                    f"{path} is a NIST QUANT-IR gas file (absorptivity, not an absorbance): it "
                    f"is drawn only when a manifest entry for it has \"peak_a\" or \"cl\"")
            ys = [v * cl for v in ys]
        rows = sorted(((float(a), float(b)) for a, b in zip(xs, ys)), key=lambda p: p[0])
        x = np.array([round(a, 3) for a, _ in rows])
        if kind != "transmittance":  # session: plain CSV, then absorbance_to_transmittance
            dec = jdx_tool.y_decimals([b for _, b in rows])
            a = [round(b, dec) for _, b in rows]
            y = np.array([round(v, 4) for v in a2t.convert_series(a, to="transmittance")])
            return x, y, TRANSMITTANCE, False, "jdx", "Absorbance"
        y = np.array([round(b * 100.0, 4) for _, b in rows])
        return x, y, TRANSMITTANCE, False, "jdx", None
    if ext == ".csv":
        x, y, axis = spa_peaks.read_house_csv(path)
        return x, y, axis, axis.startswith("Absorbance"), "csv", None
    raise PreviewError(f"{path}: unrecognised extension {ext!r}; expected .SPA/.SPG, .jdx or .csv")


def read_spectrum(path, entry):
    if not os.path.isfile(path):
        raise PreviewError(f"{path}: no such file")
    try:
        loaded = load(path, entry)
    except PreviewError:
        raise
    except Exception as e:  # a reader's own complaint, or a file that is not what its name says
        reason = str(e) or type(e).__name__
        raise PreviewError(f"{path}: cannot be read ({reason})")
    x, y = np.asarray(loaded[0], float), np.asarray(loaded[1], float)
    if x.size < 3 or x.size != y.size:
        raise PreviewError(f"{path}: not enough data points")
    xw, _ = layout.window(x, y)
    if xw.size < 3:
        raise PreviewError(f"{path}: no data between {min(layout.XLIM):g} and "
                           f"{max(layout.XLIM):g} cm-1")
    return (x, y) + loaded[2:]


def work_out(path):
    """Everything the preview shows, as a dict (the --json object plus the arrays)."""
    entry, mpath = find_manifest_entry(path)
    return work_out_entry(path, entry, mpath)


def work_out_entry(path, entry, mpath):
    """work_out with the manifest entry given (None for none) and the manifest it came from, for
    a caller that already knows them, such as `irspec session --preview`, which previews a file
    from where it will be filed."""
    from . import ir_organize as _io
    x, y, axis, absorbance, kind, converted = read_spectrum(path, entry)
    probe = dict(entry) if entry else {}
    from_manifest = bool(entry and "peaks" in entry)
    try:
        # session's own code, so the picks, label heights and ymin are session's
        result = _io._finish(probe, "", x, y, axis, absorbance, "", "")
    except Exception as e:
        raise PreviewError(f"{path}: peaks cannot be picked ({str(e) or type(e).__name__})")
    xw, yw = layout.window(x, y)
    peaks = [[float(a), float(b)] for a, b in probe["peaks"]]
    ymin = result["ymin"]
    return {
        "file": path, "kind": kind, "axis": axis, "converted_from": converted,
        "points": int(x.size),
        "range": {"x": [float(x.min()), float(x.max())],
                  "y": [float(yw.min()), float(yw.max())]},
        "ymin": None if ymin is None else float(ymin),
        "peaks": peaks,
        "peaks_from": "manifest.json" if from_manifest else "automatic",
        "_xw": xw, "_yw": yw, "_absorbance": absorbance, "_manifest": mpath,
        "_window_points": int(xw.size), "_entry": entry,
    }


# -----------------------------------------------------------------------------
# drawing
# -----------------------------------------------------------------------------
def default_width():
    """The terminal's width when stdout is a terminal, else DEFAULT_WIDTH."""
    try:
        if sys.stdout.isatty():
            return shutil.get_terminal_size().columns
    except (AttributeError, ValueError, OSError):
        pass
    return DEFAULT_WIDTH


def utf8_stdout():
    return (getattr(sys.stdout, "encoding", None) or "").lower().replace("_", "-") in ("utf-8", "utf8")


def _line(dots, x0, y0, x1, y1):
    """Set the dots of a straight line (Bresenham) in the boolean grid `dots`."""
    h, w = dots.shape
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    while True:
        if 0 <= x0 < w and 0 <= y0 < h:
            dots[y0, x0] = True
        if x0 == x1 and y0 == y1:
            return
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def trace_dots(xw, yw, cols, rows, lo, hi):
    """The curve as a (rows*4, cols*2) boolean grid of dots, x from layout.XLIM."""
    w, h = cols * 2, rows * 4
    left, right = layout.XLIM
    px = np.rint((left - xw) / (left - right) * (w - 1)).astype(int)
    py = np.rint((hi - yw) / (hi - lo) * (h - 1)).astype(int)
    dots = np.zeros((h, w), dtype=bool)
    order = np.argsort(px, kind="stable")
    px, py = px[order], py[order]
    for i in range(len(px) - 1):
        _line(dots, int(px[i]), int(py[i]), int(px[i + 1]), int(py[i + 1]))
    return dots


def cell_char(block, braille):
    """The character for one 4 x 2 block of dots."""
    if not block.any():
        return " "
    if braille:
        bits = 0
        for (cx, cy), bit in _BRAILLE.items():
            if block[cy, cx]:
                bits |= bit
        return chr(0x2800 + bits)
    rows_lit = np.nonzero(block.any(axis=1))[0]
    if rows_lit[-1] - rows_lit[0] >= 3:
        return "|"                       # steep: the cell is crossed top to bottom
    mean = float(rows_lit.mean())
    return "." if mean >= 2.5 else ":" if mean >= 1.5 else "*"


def _fmt_y(v):
    return f"{v:.4g}".replace("−", "-")


def _fmt_x(v):
    return layout.fmt_number(v).replace("−", "-")


def place_peaks(grid, dots, peaks, xw, yw, cols, rows, lo, hi, absorbance):
    """Mark each peak in the character grid; returns the symbol (or "-") of each peak."""
    left, right = layout.XLIM
    order = np.argsort(xw)
    xs, ys = xw[order], yw[order]
    step = -1 if absorbance else 1       # a transmittance band points down: the symbol hangs below it
    symbols = [None] * len(peaks)
    for n in sorted(range(len(peaks)), key=lambda i: peaks[i][0], reverse=True):
        px, _ = peaks[n]
        if not (min(layout.XLIM) <= px <= max(layout.XLIM)):
            symbols[n] = "-"
            continue
        col = int(round((left - px) / (left - right) * (cols * 2 - 1))) // 2
        yv = float(np.interp(px, xs, ys))
        row = int(round((hi - yv) / (hi - lo) * (rows * 4 - 1))) // 4
        sym = SYMBOLS[n] if n < len(SYMBOLS) else "+"
        symbols[n] = "-"
        for k in range(1, 5):
            r = row + step * k
            if 0 <= r < rows and 0 <= col < cols and grid[r][col] == " " \
                    and not dots[r * 4:r * 4 + 4, col * 2:col * 2 + 2].any():
                grid[r][col] = sym
                symbols[n] = sym
                break
    return symbols


def draw(info, width, height, braille):
    """The plot as a list of lines."""
    xw, yw, absorbance = info["_xw"], info["_yw"], info["_absorbance"]
    lo, hi = layout.ylimits(yw, info["ymin"])
    ticks = [t for t in layout.y_ticks(lo, hi)]
    # the y labels: the ticks, top down, at least 2 rows apart
    rows_for = {}
    last = -10
    for t in sorted(ticks, reverse=True):
        r = int(round((hi - t) / (hi - lo) * (height - 1)))
        if 0 <= r < height and r - last >= 2:
            rows_for[r] = _fmt_y(t)
            last = r
    lw = max([len(s) for s in rows_for.values()] + [1])
    cols = width - lw - 2
    if cols < 10:
        raise PreviewError(f"--width {width} is too narrow for this plot")

    dots = trace_dots(xw, yw, cols, height, lo, hi)
    grid = [[cell_char(dots[r * 4:r * 4 + 4, c * 2:c * 2 + 2], braille) for c in range(cols)]
            for r in range(height)]
    symbols = place_peaks(grid, dots, info["peaks"], xw, yw, cols, height, lo, hi, absorbance)

    left, right = layout.XLIM
    major = layout.X_MAJOR
    tick_cols = {}
    v = np.floor(left / major) * major
    while v >= right:
        if v <= left:
            tick_cols[v] = int(round((left - v) / (left - right) * (cols * 2 - 1))) // 2
        v -= major
    axis_line = ["-"] * cols
    for c in tick_cols.values():
        axis_line[c] = "+"
    label_row = [" "] * cols
    taken = [False] * (cols + 1)

    def put(text, start):
        start = max(0, min(start, cols - len(text)))
        if any(taken[max(0, start - 1):start + len(text) + 1]):
            return
        for i, ch in enumerate(text):
            label_row[start + i] = ch
            taken[start + i] = True
    end = _fmt_x(right)                   # the right-hand end is always labelled; the ticks give way
    put(end, cols - len(end))
    for v, c in sorted(tick_cols.items(), reverse=True):
        text = _fmt_x(v)
        put(text, c - len(text) // 2)

    pad = " " * lw
    out = []
    for r in range(height):
        label = rows_for.get(r, "")
        out.append(f"{label:>{lw}} |" + "".join(grid[r]).rstrip())
    out.append(f"{pad} +" + "".join(axis_line))
    out.append(f"{pad}  " + "".join(label_row).rstrip())
    return [ln.rstrip() for ln in out], symbols


def public(info):
    """The --json object: info without the arrays and flags the drawing needs."""
    return {k: v for k, v in info.items() if not k.startswith("_")}


def pack(items, width, indent="  "):
    """Items laid out in columns that fit `width`."""
    w = max(len(s) for s in items) + 2
    per = max(1, (width - len(indent)) // w)
    lines = []
    for i in range(0, len(items), per):
        lines.append((indent + "".join(s.ljust(w) for s in items[i:i + per])).rstrip())
    return lines


def render(info, width, height, braille):
    """The whole text: header, plot, block."""
    plot, symbols = draw(info, width, height, braille)
    absorbance = info["_absorbance"]
    lines = [f"{os.path.basename(info['file'])}  --  {info['axis']} against wavenumber (cm-1)"
             + ("" if info["_manifest"] is None else "  (manifest.json entry used)"), ""]
    lines += plot
    lines.append("")
    xr, yr = info["range"]["x"], info["range"]["y"]
    lines.append(f"file:    {info['file']}")
    axis = info["axis"]
    if info["converted_from"]:
        axis += f" (the file is {info['converted_from']}, converted: %T = 100 x 10^-A)"
    elif absorbance:
        axis += " (drawn as absorbance, bands point up)"
    lines.append(f"axis:    {axis}")
    lines.append(f"points:  {info['points']} ({info['_window_points']} between "
                 f"{min(layout.XLIM):g} and {max(layout.XLIM):g} cm-1)")
    lines.append(f"range:   {xr[1]:g} to {xr[0]:g} cm-1; "
                 f"intensity {yr[0]:.4g} to {yr[1]:.4g}")
    ymin = "the data's own minimum" if info["ymin"] is None else f"{info['ymin']:g}"
    lines.append(f"ymin:    {ymin}")
    n = len(info["peaks"])
    src = "from manifest.json" if info["peaks_from"] == "manifest.json" else "picked automatically"
    lines.append(f"peaks:   {n} ({src}); wavenumber/label height")
    if n:
        items = [f"{s} {px:.1f}/{ly:.1f}" for s, (px, ly) in zip(symbols, info["peaks"])]
        lines += pack(items, width)
        if "-" in symbols:
            lines.append("  (- : listed, not marked in the plot)")
    return "\n".join(ln.rstrip() for ln in lines) + "\n"


# -----------------------------------------------------------------------------
# command line
# -----------------------------------------------------------------------------
def build_parser():
    p = argparse.ArgumentParser(
        prog="irspec preview",
        description="Print one spectrum (.SPA, .jdx or house CSV) as plain text: the trace in the "
                    "figure's window, the picked peaks marked and numbered, and what the session "
                    "would do with it (detected axis, conversion, points, range, peaks).",
        epilog="Draws the peaks and limits with the code `irspec session` uses, from manifest.json "
               "if the file is listed there. The honest limit: shape, ranges, peak positions and "
               "which peaks are marked; not fonts, the exact placement of the labels or the tick "
               "spacing of the figure. Without --ascii, Braille dots are used when stdout is UTF-8; "
               "the ASCII characters are . (low) : (middle) * (high) in their cell and | for a steep "
               "stretch. Width: the terminal's when stdout is a terminal, else 80. "
               "Exit status: 0 done; 2 the file cannot be read or drawn.")
    p.add_argument("file", metavar="FILE", help=".SPA/.SPG, .jdx or .csv file")
    p.add_argument("--width", type=int, metavar="N",
                   help="columns of the text (default: the terminal's width, or 80 when piped)")
    p.add_argument("--height", type=int, metavar="N",
                   help=f"rows of plot (default {DEFAULT_HEIGHT})")
    p.add_argument("--ascii", action="store_true",
                   help="draw with . : * | instead of Braille dots")
    p.add_argument("--json", action="store_true",
                   help="print one JSON object (file, axis, points, range, ymin, peaks) and no plot")
    return p


def main(argv=None):
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    try:
        width = args.width if args.width is not None else default_width()
        height = args.height if args.height is not None else DEFAULT_HEIGHT
        if width < MIN_WIDTH:
            raise PreviewError(f"--width must be at least {MIN_WIDTH} (got {width})")
        if height < MIN_HEIGHT:
            raise PreviewError(f"--height must be at least {MIN_HEIGHT} (got {height})")
        info = work_out(args.file)
        if args.json:
            print(json.dumps(public(info), ensure_ascii=False))
        else:
            text = render(info, width, height, utf8_stdout() and not args.ascii)
            sys.stdout.write(text)
        return 0
    except PreviewError as e:
        print(f"irspec preview: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()

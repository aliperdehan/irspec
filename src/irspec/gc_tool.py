#!/usr/bin/env python3
"""gc_tool.py -- standalone Thermo Xcalibur .RAW (GC) toolkit for nulabreport.

Self-contained, in the same spirit as spa_tool.py: everything a future session
(human or Claude, with or without project-knowledge access) needs to reproduce
this pipeline is in this file. If you learn something new about the format,
the fix goes in THIS docstring, not only in chat.

Needs only numpy (no scipy, no Thermo DLLs, no .NET/mono).
Moved here from nulabreport's tools/gc_tool.py (2026-11-13); the output
is byte for byte what that script wrote.

WHAT THIS IS FOR
    The department's Thermo TRACE GC Ultra (FID, AI/AS 3000 autosampler)
    saves Xcalibur "Finnigan" .RAW files. Nothing on a normal laptop opens
    them. This script reads them itself and gets you to what a report needs:

      info       .RAW -> acquisition date, instrument, detector, point count,
                 time range, sampling interval, and the full instrument
                 method text (oven program, inlet, carrier, FID) -- what the
                 Experimental section's conditions are copied from.
      convert    .RAW -> the house two-CSV pair (sec. 3).
      integrate  .RAW or either CSV -> peak table (tR, height, w1/2, area,
                 area %) as a markdown table, plus the peak list argument
                 for nulabreport's \\chromatogram macro, plus a ymax
                 suggestion.
      batch      several .RAW files -> CSVs for all of them plus one ready-
                 to-build peer-share Markdown document (one chromatogram per
                 landscape page), same shape spa_tool.py batch makes for IR.
                 Build it with nulabreport's pdfmd.py, never bare pandoc
                 (nulabreport's CLAUDE.md sec. 5); this script does not invoke pandoc.

===============================================================================
1. THE .RAW LAYOUT (reverse-engineered 2026-09-26; validated, not guessed)
===============================================================================
Thermo has never published this format. Everything below was found by
inspecting the bytes of CHEM211L LR4's five files (Summer26/CHEM211L/
labreports/appendix/L4 GS data/raw/Lab4_group{1..5}.RAW) and checking the
result against the CSVs the lab's Xcalibur exported from those same files
(.../csv/Lab4_group{1..5}.csv): every signal value in all five matches
EXACTLY, and every time value matches to the CSV's printed 9 decimals.

  offset 0      uint16 0xA101, then UTF-16LE "Finnigan"      (magic)
  offset 0x24   uint16 file version -- 63 in every file seen so far
  offset 0x28   FILETIME (100 ns ticks since 1601-01-01 UTC): acquisition
  ~1356..       the "sequence row": UTF-16 Pascal strings (int32 length +
                text) -- method path, raw file name, data folder, ... Their
                lengths vary with the names, so NOTHING after this point is
                at a fixed offset. (It happened to be for all five LR4
                files, which is why a fixed offset would have passed the
                validation above and still broken on the next file.)
  run header    contains int32 DATA_ADDR, then exactly 20 bytes later int32
                INDEX_ADDR. Found by searching for that self-consistent pair
                (find_run_header()), not by offset.
  DATA_ADDR     the chromatogram: N float64 (little-endian) detector values,
                contiguous. INDEX_ADDR == DATA_ADDR + 8*N exactly.
  INDEX_ADDR    int32 (1, 0, 1, N): N is the point count
                float64 at +72: first retention time, min (0.0 here)
                float64 at +80: last retention time, min
  later         UTF-16 "Channel 1", "TRACE GC", ..., "Counts" (signal unit)

The time axis is NOT stored per point: t_i = t0 + i*(t_last - t0)/(N - 1).
For this instrument that is 10 Hz (0.1 s = 0.001667 min per point); the
5 files have N = 7195..7202 points, which is exactly why their CSVs differ
in length and why the last time differs (11.99 vs 11.99333 min).

The instrument method is embedded as plain UTF-16 text between the header
and DATA_ADDR (method_text()). A "Sample Volume (µl)" line contains a
non-ASCII µ, so the string scanner accepts Latin-1 as well as ASCII.

A file of a DIFFERENT version, or a GC-MS .RAW (thousands of scans, each
with a mass spectrum), has not been seen. read_raw() refuses anything whose
run header is not found or not self-consistent, and warns on any version
other than 63. If you get a new one: export its chromatogram as CSV from
Xcalibur on the lab PC and run
    irspec gc verify NEW.RAW EXPORT.csv
before trusting anything else this script says about it. For GC-MS data
use ThermoRawFileParser instead; this reader handles one analog channel.

===============================================================================
2. RECOGNISING THE LAB'S OWN CSV EXPORT
===============================================================================
Xcalibur's CSV export (what's in .../L4 GS data/csv/) looks like this:
    <UTF-8 BOM>CHROMATOGRAM
    C:\\...\\Lab4_group1.RAW
    Data points: 7197
    Time(min),Counts
    0,603700
    0.001666667,604410
    ...
write_xcalibur_csv() writes the same shape (it is this script's archival
CSV), and read_any() reads it back, as well as the plain CSV below.

===============================================================================
3. THE TWO-CSV CONVENTION (same idea as the IR tools)
===============================================================================
  csv/<stem>.csv          archival: Xcalibur-export shape, full run,
                          untouched values. Diffable against a real export.
  plain/<stem>_plain.csv  what \\chromatogram reads:  time,signal
                          (comma, decimal point, one header row, full run
                          -- nothing is clipped; crop with xmin/xmax in the
                          macro call instead, so the data stays whole).

===============================================================================
4. PEAKS, BASELINE, INTEGRATION
===============================================================================
Numbers here are the tool's own, NOT Xcalibur's: Xcalibur integrates with
its own (ICIS/Genesis) rules, and nobody exported its peak table for LR4.
What the tool does, so a report can describe it in a sentence or two:

  - a 5-point moving average for FINDING things (apex, boundaries, w1/2);
    the raw signal for MEASURING heights and areas;
  - noise sigma = 1.4826 * MAD(diff(signal)) / sqrt(2);
  - a candidate peak is a local maximum of the smoothed trace whose
    prominence is at least --min-prominence x sigma (default 20; manual
    mode lowers it to 3 so small requested peaks are still candidates);
  - ONE baseline for the whole trace (--baseline), chosen per run:
      auto      SNIP (Ryan et al. 1988), half-window 0.6 min, lifted to the
                middle of the noise band. Follows slow drift; can undercut
                a sharp bend (the oven ramp starting at 8 min).
      flat[:m]  the median of the first m minutes (default 0.5), before
                anything elutes -- what the session that made LR4's tables
                used (~606 060 counts for group 1). Overestimates anything
                eluting after the 8-min ramp (1-pentanol: window from 8.03).
      t1,t2,..  piecewise-linear through the smoothed signal at those
                times: LR4's own "~606 000 until 1-pentanol, linear after".
                Put anchors on genuine baseline only -- not on a peak, a
                tail, or the unknown 7.2-min hump -- and put one AT any
                bend (8.0 for this oven program): anchors 6.0 -> 8.95
                straight across the bend pushed the corrected trace
                10 000 counts negative in between.
      none      zero: the input is already corrected (`crop --correct`).
    A whole-trace baseline, not a straight line between each peak's two
    ends: a slowly-tailing peak's tail is below the noise per point, so
    any per-peak slope test ends it early -- the first two versions did,
    and got 1-butanol's area ~50% and then ~100x too small.
  - boundaries: walk out from the apex until the baseline-corrected
    smoothed trace stays under 3 sigma (of the averaged trace) for 3
    points, or rises again by 2x that above the lowest point passed (a
    valley between overlapping peaks: drop-line split there);
  - apex tR by a parabola through the three highest smoothed points;
    h = highest raw point within +/-3 points of the apex, minus baseline;
    w1/2 where the corrected smoothed trace crosses half its apex height
    (interpolated only between samples that bracket it). A valley above
    half-height leaves the width and triangulation area unresolved (nan),
    excluded from triangulation percentages; trapezoidal area still holds;
  - TWO area methods, both printed, from the same peak windows:
      triangulation   A = h * w1/2               (LR4 Formula 3, Table 4)
      integration     trapezoidal rule over the corrected RAW signal,
                      negatives clipped to 0     (LR4 Table 5)
    both in counts*min, each with its own area % over the ANALYTE peaks
    only: --solvent peaks are labelled on the plot but left out of the
    total (LR4 Formula 4). --known 'Name=%,...' adds Known % and Error %
    columns (|found - known| / known x 100) and their mean.

Manual mode (--peaks) picks, for each requested tR, the candidate apex
CLOSEST in time within --window (default 0.08 min), never the tallest one
in the window -- the same lesson spa_tool.py's find_peaks_manual() learned
on IR shoulders (see nulabreport's tools/CLAUDE.md).

Missing samples (including crop --exclude's NaNs) split the trace into
independent finite segments for noise, smoothing, baseline and measurement.
A peak whose boundary search reaches a gap is unresolved: auto mode omits
it; requesting it explicitly stops with a missing-samples diagnostic. No
area is interpolated across an exclusion.

Validation, LR4 group 1, anchors 2.5,4.5,6.6,8.0,8.5,8.97,9.6 (LR4's own
hand/earlier-session numbers in brackets):
    h:        8895 [9351]  17841 [18374]  37784 [38579]  40550 [41381]  78982 [78587]
    w1/2:   0.0454 [.0432] 0.0465 [.0447] 0.0658 [.0661] 0.0949 [.0946] 0.0941 [.0933]
    tri %:    2.69 [2.69]   5.54 [5.46]   16.57 [16.99]  25.65 [26.05]  49.55 [48.81]
    trapz:     515 [576]     937 [1093]    3168 [4135]    4767 [5283]    8869 [8840]
The integration areas of the early peaks are smaller than LR4's because
LR4's flat baseline counted the acetone tail under methanol/ethanol/
1-propanol as their area; here the anchors put the tail in the baseline.

===============================================================================
5. THE \\chromatogram PEAK LIST, AND CROPPING
===============================================================================
    tR/apex_y/label_y/{Name},...      ({} for no name: the label is tR alone)
apex_y is where the leader line starts, label_y where the label's bottom
edge sits (data units = counts, of the CSV being PLOTTED -- so integrate
the cropped CSV, not the raw one, when you plot a cropped one). The tool
raises a label clear of a neighbour it would overlap (estimated from its
character count and the plot size -- give --plot-size W,H in cm for a
stack panel or --landscape for a peer-share page) and prints a ymax that
leaves room for every label; pass it, the same "explicit, overridable"
rule \\irspectrum uses for ymin.

Cropping, two ways:
  axis only    --xmin/--xmax/--ymax on integrate: the CSV stays the full run,
               the axis shows a window. A --ymax below a saturated peak
               (LR4 groups 4/5: 2.6e7 and 7.3e7 counts) pins that peak's
               label under the top edge, clamps its apex_y to ymax, and
               adds `restrict y to domain*=-ymax:ymax` to the options --
               without both, TeX overflows ("! Dimension too large") on
               every label in the plot, not just that one.
  a new CSV    `crop`: trim to a window, --correct subtracts the baseline,
               --exclude a-b blanks ranges (written as nan: the macro draws
               a gap) -- LR4's Figure 2, "trimmed, baseline-corrected,
               excluded regions removed". Then integrate THAT file with
               --baseline none.
"""

import argparse
import datetime
import json
import os
import re
import struct
import sys

import numpy as np

KNOWN_VERSIONS = {63}
MAGIC = b"\x01\xa1" + "Finnigan".encode("utf-16le")


# =============================================================================
# 1. READING .RAW
# =============================================================================
class RawFormatError(Exception):
    pass


def find_run_header(b, search_limit=65536):
    """Find the (DATA_ADDR, INDEX_ADDR) int32 pair, 20 bytes apart, that is
    self-consistent with the index record it points to (module docstring
    sec. 1). Returns (data_addr, index_addr, n). Refuses 0 or >1 matches."""
    hits = []
    lim = min(len(b) - 24, search_limit)
    for p in range(0, lim):
        d = struct.unpack_from("<i", b, p)[0]
        if d <= 0 or d >= len(b):
            continue
        ix = struct.unpack_from("<i", b, p + 20)[0]
        if ix <= d or ix + 88 > len(b) or (ix - d) % 8:
            continue
        n = (ix - d) // 8
        if n < 2 or struct.unpack_from("<4i", b, ix) != (1, 0, 1, n):
            continue
        hits.append((d, ix, n))
    hits = sorted(set(hits))
    if len(hits) != 1:
        raise RawFormatError(
            f"expected exactly one self-consistent run header, found {len(hits)} "
            "-- not a layout this script has been validated on (docstring sec. 1)")
    return hits[0]


def _utf16_strings(b, start, end):
    """(offset, text) for every run of >=3 printable UTF-16LE characters
    (ASCII or Latin-1, so the 'µ' in 'Sample Volume (µl)' survives)."""
    out = []
    for m in re.finditer(rb"(?:[\x20-\x7e\xa0-\xff]\x00){3,}", b[start:end]):
        out.append((start + m.start(), m.group().decode("utf-16le")))
    return out


def method_text(b, data_addr):
    """The embedded instrument method as a list of lines: autosampler block
    plus the TRACE GC method (oven, inlet, carrier, detector, signal). The
    OLE container names ('Root Entry', 'Data', 'Text') and temp-file paths
    around it are dropped."""
    strings = _utf16_strings(b, 0, data_addr)
    start = next((i for i, (_, s) in enumerate(strings) if s == "Root Entry"), None)
    if start is None:
        return []
    noise = {"Root Entry", "Data", "Text", "TRACE", "AI-AS 3000"}
    lines, pending = [], ""
    prev_end = None
    for off, s in strings[start:]:
        # "Sample Volume (" + "µ" + "l): ..." arrives as adjacent runs
        if pending and prev_end is not None and off - prev_end <= 2:
            pending += s
        else:
            if pending:
                lines.append(pending)
            pending = s
        prev_end = off + 2 * len(s)
    if pending:
        lines.append(pending)
    return [l.rstrip() for l in lines if l not in noise and not l.startswith("C:\\")]


def read_raw(path):
    """-> dict(time, signal, meta). time in min, signal as stored (counts)."""
    with open(path, "rb") as f:
        b = f.read()
    if not b.startswith(MAGIC):
        raise RawFormatError(f"{path}: not a Finnigan/Xcalibur .RAW (bad magic)")
    version = struct.unpack_from("<H", b, 0x24)[0]
    if version not in KNOWN_VERSIONS:
        print(f"WARNING: {path}: file version {version}, only {sorted(KNOWN_VERSIONS)} "
              "validated -- run `gc_tool.py verify` against an Xcalibur CSV export "
              "before trusting this (docstring sec. 1)", file=sys.stderr)

    data_addr, index_addr, n = find_run_header(b)
    signal = np.frombuffer(b, "<f8", count=n, offset=data_addr).copy()
    t0, t1 = struct.unpack_from("<2d", b, index_addr + 72)
    if not (np.isfinite(t0) and np.isfinite(t1) and 0 <= t0 < t1 < 1e4):
        raise RawFormatError(f"{path}: implausible time range {t0!r}..{t1!r}")
    time = t0 + np.arange(n) * (t1 - t0) / (n - 1)

    ft = struct.unpack_from("<Q", b, 0x28)[0]
    acquired = datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=ft // 10)

    tail = [s for _, s in _utf16_strings(b, index_addr, len(b))]
    head = [s for _, s in _utf16_strings(b, 0, data_addr)]
    method = method_text(b, data_addr)
    detector = next((l.split()[1] for l in method
                     if re.match(r"(Right|Left) \w+ Method$", l)
                     and l.split()[1] not in ("SSL", "Carrier", "PTV", "Signal")), None)
    meta = {
        "path": path,
        "version": version,
        "acquired": acquired,
        "instrument": next((s for s in head if "GC" in s and "Xcalibur" not in s), None),
        "method_file": next((s for s in head if s.lower().endswith(".meth")), None),
        "channel": next((s for s in tail if s.startswith("Channel")), None),
        "units": "Counts" if "Counts" in tail else None,
        "detector": detector,
        "method": method,
        "data_addr": data_addr,
        "index_addr": index_addr,
        "n": n,
        "t0": t0,
        "t1": t1,
    }
    return {"time": time, "signal": signal, "meta": meta}


# =============================================================================
# 2. CSV IN/OUT
# =============================================================================
def _fmt_time(t):
    s = f"{t:.9f}".rstrip("0").rstrip(".")
    return s or "0"


def _fmt_signal(y):
    return str(int(y)) if float(y).is_integer() else repr(float(y))


def write_xcalibur_csv(time, signal, path, source_name):
    """Archival CSV, Xcalibur-export shape (docstring sec. 2)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        f.write("CHROMATOGRAM\r\n")
        f.write(f"{source_name}\r\n")
        f.write(f"Data points: {len(time)}\r\n")
        f.write("Time(min),Counts\r\n")
        for t, y in zip(time, signal):
            f.write(f"{_fmt_time(t)},{_fmt_signal(y)}\r\n")
    return path


def write_plain_csv(time, signal, path):
    """What \\chromatogram reads: time,signal (docstring sec. 3)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("time,signal\n")
        for t, y in zip(time, signal):
            f.write(f"{t:.6f},{_fmt_signal(y)}\n")
    return path


def read_any(path):
    """.RAW, an Xcalibur CSV export, or a plain CSV -> (time, signal, meta)."""
    if path.lower().endswith(".raw"):
        r = read_raw(path)
        return r["time"], r["signal"], r["meta"]
    with open(path, encoding="utf-8-sig") as f:
        lines = f.read().splitlines()
    i = next(i for i, l in enumerate(lines) if re.match(r"\s*(Time\(min\)|time),", l))
    arr = np.array([[float(v) for v in l.split(",")[:2]] for l in lines[i + 1:] if l.strip()])
    return arr[:, 0], arr[:, 1], {"path": path}


def clean_stem(name):
    return os.path.splitext(os.path.basename(name))[0]


def batch_stems(sources):
    """-> one output stem per source, in order. A stem shared by several
    different inputs gets the part of each input's path that tells them
    apart (A/run.RAW and B/run.RAW -> A-run, B-run); stems that do not
    collide stay as clean_stem() gives them. Never depends on the order.
    Exits with a message when two inputs are the same file, or when even
    the full paths give the same name."""
    stems = [clean_stem(s) for s in sources]
    paths = [os.path.realpath(s) for s in sources]
    out = list(stems)
    groups = {}
    for i, st in enumerate(stems):
        groups.setdefault(st, []).append(i)
    for st, idx in groups.items():
        if len(idx) < 2:
            continue
        if len({paths[i] for i in idx}) < len(idx):
            sys.exit(f"error: the same input is listed twice (stem '{st}'): "
                     + ", ".join(sorted({sources[i] for i in idx})))
        parents = {i: os.path.dirname(paths[i]).split(os.sep) for i in idx}
        # drop the folders every colliding input shares at the end of its path
        while all(parents[i] for i in idx) and \
                len({parents[i][-1] for i in idx}) == 1:
            for i in idx:
                parents[i] = parents[i][:-1]
        depth = max(len(parents[i]) for i in idx)
        for k in range(1, depth + 1):
            names = {i: "-".join([c for c in parents[i][-k:] if c] + [st])
                     for i in idx}
            if len(set(names.values())) == len(idx):
                break
        else:
            names = {i: st for i in idx}
        for i in idx:
            out[i] = names[i]
        if len(set(names.values())) == len(idx):
            print("note: inputs share the name '" + st + "'; writing them as "
                  + ", ".join(f"{sources[i]} -> {names[i]}" for i in idx),
                  file=sys.stderr)
    seen = {}
    for src, st in zip(sources, out):
        if st in seen:
            sys.exit(f"error: {seen[st]} and {src} would both be written as '{st}' "
                     "(their paths do not tell them apart): rename one of them")
        seen[st] = src
    return out


# =============================================================================
# 3. PEAKS
# =============================================================================
def smooth(y, w=5):
    k = np.ones(w) / w
    ypad = np.concatenate([np.full(w // 2, y[0]), y, np.full(w // 2, y[-1])])
    return np.convolve(ypad, k, mode="valid")


def noise_sigma(y):
    d = np.diff(y)
    # Only adjacent observed samples contribute; never difference across a gap.
    d = d[np.isfinite(d)]
    if not len(d):
        return 0.0
    return 1.4826 * np.median(np.abs(d - np.median(d))) / np.sqrt(2)


def candidate_apexes(ys, sigma, min_prominence):
    """Local maxima of the smoothed trace with prominence >= min_prominence*sigma.
    Returns list of (index, prominence)."""
    n = len(ys)
    is_max = np.zeros(n, bool)
    is_max[1:-1] = (ys[1:-1] > ys[:-2]) & (ys[1:-1] >= ys[2:])
    out = []
    for i in np.flatnonzero(is_max):
        # left: lowest point before the trace first rises above ys[i]
        j = i - 1
        lmin = ys[i]
        while j >= 0 and ys[j] <= ys[i]:
            lmin = min(lmin, ys[j]); j -= 1
        j = i + 1
        rmin = ys[i]
        while j < n and ys[j] <= ys[i]:
            rmin = min(rmin, ys[j]); j += 1
        prom = ys[i] - max(lmin, rmin)
        if prom >= min_prominence * sigma:
            out.append((int(i), float(prom)))
    return out


def snip_baseline(ys, half_window):
    """SNIP baseline (Ryan et al. 1988; Morhac 1997): for k = 1..half_window,
    y[i] <- min(y[i], (y[i-k] + y[i+k]) / 2). Peaks narrower than
    ~2*half_window are clipped away; a slowly drifting baseline (the rise
    after 9 min in LR4, oven ramp) is followed. numpy only."""
    b = ys.astype(float).copy()
    n = len(b)
    for k in range(1, min(half_window, n // 2)):
        avg = np.empty_like(b)
        avg[k:n - k] = 0.5 * (b[:n - 2 * k] + b[2 * k:])
        avg[:k] = b[:k]
        avg[n - k:] = b[n - k:]
        np.minimum(b, avg, out=b)
    return b


def estimate_baseline(t, ys, spec="auto", snip_min=0.6):
    """spec 'auto' -> SNIP with a half-window of snip_min minutes (must
    exceed half of the widest peak INCLUDING its tail: 1-butanol's tail in
    LR4 runs ~0.4 min). spec '2.0,2.7,4.5,...' -> piecewise-linear through
    the smoothed signal at those times -- the hand-picked 'piecewise
    baseline' LR4 itself used. spec 'none' -> zero (an already-corrected
    CSV from `crop --correct`). spec 'flat[:minutes]' -> a constant, see
    below."""
    if spec == "none":
        return np.zeros_like(ys)
    if spec.startswith("flat"):
        # 'flat' or 'flat:0.5': one constant, the median of the first 0.5 min
        # (isothermal, nothing eluted yet). LR4's own method -- the session
        # that produced its Tables 4/5 used the median of the first 300
        # points, ~606 060 counts for group 1. Ignores the post-8 min rise
        # (the oven ramp starts at 8 min), which is why pentanol's h and
        # area come out larger with it than with 'auto'.
        span = float(spec.partition(":")[2] or 0.5)
        return np.full_like(ys, np.median(ys[t <= t[0] + span]))
    if spec == "auto":
        dt = t[1] - t[0]
        b = snip_baseline(ys, max(2, int(round(snip_min / dt))))
        # SNIP clips to the BOTTOM of the noise band; lift it to the middle
        # (median residual -- most of a chromatogram is baseline), or the
        # corrected trace sits a couple of sigma above zero everywhere and
        # no peak ever "returns to baseline" (first version: methanol's
        # window started at 2.21 min).
        return b + np.median(ys - b)
    anchors = sorted(float(v) for v in spec.split(","))
    ay = [ys[int(np.argmin(np.abs(t - a)))] for a in anchors]
    return np.interp(t, anchors, ay)


def _walk(cs, i, step, level, flat_run=3, missing_edge=False):
    """From apex i, walk in direction step (+1/-1) along the baseline-
    corrected smoothed trace cs until it has stayed below `level` (~3 noise
    sigma: back at baseline) for flat_run points, or has risen again by
    more than 2*level above the lowest point passed (a valley between
    overlapping peaks: drop-line split at that lowest point). Returns None
    if it reaches an edge marked as missing before either condition."""
    n = len(cs)
    j = i
    below = 0
    lowest, lowest_j = cs[i], i
    while 0 <= j + step < n:
        j += step
        if cs[j] < lowest:
            lowest, lowest_j = cs[j], j
        if cs[j] - lowest > 2 * level:
            return lowest_j
        below = below + 1 if cs[j] < level else 0
        if below >= flat_run:
            return j
    return None if missing_edge else j


def measure_peak(t, y, ys, base, i, level, missing_left=False, missing_right=False):
    """Everything about one peak whose smoothed apex index is i, measured
    above the segment baseline `base`; None if its window reaches a gap."""
    cs = ys - base
    a = _walk(cs, i, -1, level, missing_edge=missing_left)
    b = _walk(cs, i, +1, level, missing_edge=missing_right)
    if a is None or b is None:
        return None
    # parabolic apex on the smoothed trace
    off = 0.0
    if 0 < i < len(ys) - 1:
        y0, y1, y2 = ys[i - 1], ys[i], ys[i + 1]
        den = y0 - 2 * y1 + y2
        off = 0.5 * (y0 - y2) / den if den else 0.0
    tR = t[i] + off * (t[1] - t[0])
    seg = slice(a, b + 1)
    corr = y[seg] - base[seg]
    area = float(np.trapezoid(np.clip(corr, 0, None), t[seg]))
    lo, hi = max(a, i - 3), min(b, i + 3) + 1
    k_raw = lo + int(np.argmax(y[lo:hi]))
    h = float(y[k_raw] - base[k_raw])
    # w1/2 where the corrected SMOOTHED trace crosses half its apex height
    half = cs[i] / 2
    l = i
    while l > a and cs[l] > half:
        l -= 1
    r = i
    while r < b and cs[r] > half:
        r += 1
    def cross(p, q):
        if not min(cs[p], cs[q]) <= half <= max(cs[p], cs[q]):
            return float("nan")     # a valley/window edge is not a crossing
        return t[p] + (half - cs[p]) * (t[q] - t[p]) / (cs[q] - cs[p]) if cs[q] != cs[p] else t[p]
    w_half = float(cross(r - 1, r) - cross(l, l + 1)) if (l < i < r) else float("nan")
    return {"i": i, "tR": float(tR), "apex_y": float(ys[i]), "h": h,
            "w_half": w_half, "area": area, "tri_area": h * w_half,
            "start": float(t[a]), "end": float(t[b])}


def find_peaks(t, y, min_prominence=20.0, wanted=None, window=0.08, baseline="auto"):
    """Auto mode (wanted=None): every candidate. Manual mode: wanted is a list
    of (tR, name, is_solvent); each takes the candidate CLOSEST in time
    within +/-window (docstring sec. 4)."""
    ok = np.isfinite(t) & np.isfinite(y)   # a cropped CSV may carry nan gaps
    sigma = noise_sigma(np.where(ok, y, np.nan))
    # Keep each contiguous finite run separate throughout smoothing, baseline
    # estimation, candidate detection and integration. Masking out NaNs would
    # join unrelated edges and integrate a straight line across excluded time.
    edges = np.diff(np.r_[False, ok, False].astype(int))
    cands = []
    for start, stop in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
        if stop - start < 3:           # an apex needs neighbours on both sides
            continue
        ts, raw = t[start:stop], y[start:stop]
        segment_sigma = noise_sigma(raw)
        level = 3 * segment_sigma / np.sqrt(5)  # noise of the 5-point-averaged trace
        ys = smooth(raw)
        base = estimate_baseline(ts, ys, baseline)
        for i, _ in candidate_apexes(ys, segment_sigma, min_prominence if wanted is None else 3.0):
            cands.append((ts[i], start, stop, ts, raw, ys, base, i, level))

    def measured(candidate):
        _, start, stop, ts, raw, ys, base, i, level = candidate
        p = measure_peak(ts, raw, ys, base, i, level,
                         missing_left=start > 0, missing_right=stop < len(t))
        if p is not None:
            p["i"] += int(start)       # index in the input, including gaps
        return p

    peaks = []
    if wanted is None:
        for candidate in cands:
            p = measured(candidate)
            if p is None:
                continue
            p.update(name="", solvent=False)
            peaks.append(p)
    else:
        ct = np.array([c[0] for c in cands])
        for want, name, solvent in wanted:
            if not len(ct):
                raise SystemExit("no candidate peaks at all -- is this a chromatogram?")
            j = int(np.argmin(np.abs(ct - want)))
            if abs(ct[j] - want) > window:
                raise SystemExit(f"no peak within {window} min of {want} ({name}); "
                                 f"nearest candidate is at {ct[j]:.3f} min")
            p = measured(cands[j])
            if p is None:
                raise SystemExit(f"peak near {want} ({name}) reaches missing samples; "
                                 "its measurement is unresolved")
            p.update(name=name, solvent=solvent, requested=want)
            peaks.append(p)
    for key, pkey in (("area", "pct"), ("tri_area", "tri_pct")):
        total = sum(p[key] for p in peaks if not p["solvent"] and np.isfinite(p[key]))
        for p in peaks:
            p[pkey] = (100 * p[key] / total
                       if total and not p["solvent"] and np.isfinite(p[key]) else None)
    return peaks, sigma


def parse_peak_spec(spec, solvent=False):
    """'2.84=Methanol,3.02=Ethanol' (or bare '2.84,3.02') -> [(2.84,'Methanol',False),...]"""
    out = []
    for item in filter(None, (s.strip() for s in (spec or "").split(","))):
        tr, _, name = item.partition("=")
        out.append((float(tr), name.strip(), solvent))
    return out


# =============================================================================
# 4. LABELS FOR \chromatogram
# =============================================================================
# Label geometry, ESTIMATED -- used only to avoid collisions and to leave
# headroom, never drawn from. \scriptsize at a 12pt body is 8pt: ~0.14 cm per
# character (STIX Two), ~0.34 cm per line including inner sep. The plot box
# defaults mirror the macro's own (pgfplots width=14.5cm/height=9.5cm include
# the tick labels, so the box is roughly 12.5 x 7.5 cm; a landscape
# peer-share page is ~24 x 15 cm -- pass --plot-size for that).
CHAR_CM, LINE_CM = 0.14, 0.34


def assign_labels(peaks, t_range, y_range, ymax=None, size_cm=(12.5, 7.5),
                  gap_frac=0.02):
    """label_y per peak: apex + gap, raised clear of any label already placed
    that it would overlap (tallest peaks placed first, so the big ones keep
    their natural spot and small crowded ones climb). A peak taller than an
    explicit ymax gets its label pinned just under the top edge.
    Returns ([(peak, label_y, apex_y_clamped)], ymax_suggestion)."""
    width_cm, height_cm = size_cm
    ylo, yhi = y_range
    top_guess = ymax if ymax is not None else yhi
    for _ in range(2):   # label height in data units depends on the final ymax
        span = top_guess - ylo
        per_cm_y = span / height_cm
        per_cm_t = (t_range[1] - t_range[0]) / width_cm
        gap = gap_frac * span
        placed, labels = [], []
        for p in sorted(peaks, key=lambda p: -p["apex_y"]):
            chars = max(len(p["name"]), len(f"{p['tR']:.2f}"))
            half_w = (chars * CHAR_CM / 2 + 0.08) * per_cm_t
            hgt = (2 if p["name"] else 1) * LINE_CM * per_cm_y
            yb = p["apex_y"] + gap
            pinned = ymax is not None and yb + hgt > ymax
            if pinned:
                yb = ymax - hgt - gap
            moved = not pinned
            while moved:
                moved = False
                for (l, r, b0, b1) in placed:
                    if (p["tR"] - half_w < r and p["tR"] + half_w > l
                            and yb < b1 and yb + hgt > b0):
                        yb = b1 + gap / 3
                        moved = True
            placed.append((p["tR"] - half_w, p["tR"] + half_w, yb, yb + hgt))
            labels.append((p, yb, min(p["apex_y"], ymax) if ymax is not None else p["apex_y"]))
        top = max([b1 for *_, b1 in placed] + [yhi])
        if ymax is not None:
            break
        top_guess = top + gap
    labels.sort(key=lambda pl: pl[0]["tR"])
    return labels, (ymax if ymax is not None else top_guess)


def format_peaklist(labels):
    """tR/apex_y/label_y/{Name},... (docstring sec. 5). apex_y is CLAMPED to
    ymax for a peak taller than the axis: the macro draws its leader line up
    to apex_y, and a point tens of millions of counts off-axis (LR4 group 4's
    saturated 7.3e7-count peak against ymax=1.3e6) overflows TeX's largest
    dimension -- "! Dimension too large" -- even though it would be clipped.
    The name is braced so a comma or slash in it can't split the entry."""
    return ",".join(f"{p['tR']:.2f}/{apex:.0f}/{yb:.0f}/{{{latex_escape(p['name'])}}}"
                    for p, yb, apex in labels)


def latex_escape(s):
    """'%' unescaped inside a macro argument starts a comment and truncates
    the call -- the spa_tool.py lesson (tools/CLAUDE.md)."""
    s = s.replace("\\", r"\textbackslash{}")
    for ch, esc in (("%", r"\%"), ("&", r"\&"), ("_", r"\_"), ("#", r"\#"),
                    ("$", r"\$"), ("{", r"\{"), ("}", r"\}")):
        s = s.replace(ch, esc)
    return s


def nice_ceil(v):
    """Round a ymax up to 2-3 significant figures (1 072 119 -> 1 080 000):
    one figure (-> 1 200 000) left a tenth of the plot empty above the
    tallest label."""
    step = 10 ** max(0, int(np.floor(np.log10(abs(v) or 1))) - 2)
    return float(np.ceil(v / step) * step)


# =============================================================================
# 5. OUTPUT TABLES
# =============================================================================
def parse_known(spec):
    """'Methanol=6.67,Ethanol=13.33' -> {'Methanol': 6.67, ...}"""
    out = {}
    for item in filter(None, (s.strip() for s in (spec or "").split(","))):
        k, _, v = item.partition("=")
        out[k.strip()] = float(v)
    return out


def review_table(peaks):
    rows = [f"{'name':<14}{'tR/min':>8}{'start':>8}{'end':>8}{'h/counts':>11}"
            f"{'w1/2/min':>10}{'h*w1/2':>10}{'tri%':>8}{'trapz':>10}{'trapz%':>8}"]
    for p in peaks:
        f = lambda v: "solv." if p["solvent"] else ("" if v is None else f"{v:.2f}")
        rows.append(f"{p['name'] or '-':<14}{p['tR']:>8.3f}{p['start']:>8.3f}{p['end']:>8.3f}"
                    f"{p['h']:>11.0f}{p['w_half']:>10.4f}{p['tri_area']:>10.1f}"
                    f"{f(p['tri_pct']):>8}{p['area']:>10.1f}{f(p['pct']):>8}")
    return rows


def _err(p, known, key):
    k = known.get(p["name"])
    if k is None or p[key] is None:
        return None
    return abs(p[key] - k) / k * 100


def _pipe_table(header, rows, align):
    """An aligned pandoc pipe table whose separator dashes match each
    column's width. Once any row is longer than 72 characters (these always
    are), pandoc gives columns RELATIVE WIDTHS FROM THOSE DASH COUNTS; equal
    dashes squeezed the name column until "1-Propanol" wrapped onto two
    lines in the built PDF."""
    w = [max(len(r[i]) for r in [header] + rows) for i in range(len(header))]
    line = lambda r: "| " + " | ".join(
        c.ljust(w[i]) if align[i] == "l" else c.rjust(w[i]) for i, c in enumerate(r)) + " |"
    sep = "|" + "|".join((":" + "-" * (w[i] + 1)) if align[i] == "l" else ("-" * (w[i] + 1) + ":")
                         for i in range(len(w))) + "|"
    return [line(header), sep] + [line(r) for r in rows]


def markdown_tables(peaks, known=None):
    """Two pandoc pipe tables (the Lua filter makes them booktabs): the
    triangulation table (h, w1/2, A = h*w1/2) and the trapezoidal-integration
    table, each with area % over the analytes and, given --known, the known
    % and the %error -- LR4's Tables 4 and 5, from the same peak windows."""
    known = known or {}
    an = [p for p in peaks if not p["solvent"]]
    kn = bool(known)
    pct = lambda v: "---" if v is None else f"{v:.2f}"

    def extra(p, key):
        if not kn:
            return []
        if p["name"] in known and not p["solvent"]:
            return [f"{known[p['name']]:.2f}", pct(_err(p, known, key))]
        return ["---", "---"]

    def mean_row(key):
        e = [v for v in (_err(p, known, key) for p in an) if v is not None]
        return (["100.00", f"{np.mean(e):.2f}"] if e else ["", ""]) if kn else []

    kh = ["Known, %", "Error, %"] if kn else []
    tri_h = ["Peak", "$t_\\mathrm{R}$, min", "$h$, counts", "$w_{1/2}$, min",
             "$h w_{1/2}$, counts·min", "Found, %"] + kh
    trap_h = ["Peak", "Area, counts·min", "Found, %"] + kh
    tri, trap = [], []
    for p in peaks:
        name = (p["name"] or "---") + (" (solvent)" if p["solvent"] else "")
        tri.append([name, f"{p['tR']:.2f}", f"{p['h']:.0f}", f"{p['w_half']:.4f}",
                    f"{p['tri_area']:.1f}", pct(p["tri_pct"])] + extra(p, "tri_pct"))
        trap.append([name, f"{p['area']:.1f}", pct(p["pct"])] + extra(p, "pct"))
    if len(an) > 1:
        tri.append(["Σ / mean", "", "", "", f"{sum(p['tri_area'] for p in an):.1f}",
                    "100.00"] + mean_row("tri_pct"))
        trap.append(["Σ / mean", f"{sum(p['area'] for p in an):.1f}", "100.00"]
                    + mean_row("pct"))
    return (_pipe_table(tri_h, tri, "l" + "r" * (len(tri_h) - 1)),
            _pipe_table(trap_h, trap, "l" + "r" * (len(trap_h) - 1)))


# =============================================================================
# 6. CROPPING (a trimmed / baseline-corrected / gapped plain CSV)
# =============================================================================
def crop(source, out_path, xmin=None, xmax=None, correct=False, baseline="auto",
         exclude=""):
    """Write a plain CSV for a cropped chromatogram, like LR4's Figure 2:
      --xmin/--xmax      keep only that time window;
      --correct          subtract the baseline (same estimator integrate uses)
                         so the trace sits on zero;
      --exclude a-b,...  blank those time ranges (written as nan: pgfplots
                         draws a GAP there -- `unbounded coords=jump` is in
                         the gc kind's defaults -- rather than a straight line
                         across, so a removed solvent front is visibly
                         removed, not silently flattened).
    Integrate and label from THIS file afterwards, so the peak list's apex
    heights are on the same scale as the plotted curve."""
    t, y, _ = read_any(source)
    y = y.astype(float)
    if correct:
        ok = np.isfinite(y)
        base = np.full_like(y, np.nan)
        base[ok] = estimate_baseline(t[ok], smooth(y[ok]), baseline)
        y = y - base
    for rng in filter(None, (r.strip() for r in exclude.split(","))):
        a, b = (float(v) for v in rng.split("-"))
        y[(t >= a) & (t <= b)] = np.nan
    sel = np.ones_like(t, bool)
    if xmin is not None:
        sel &= t >= xmin
    if xmax is not None:
        sel &= t <= xmax
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("time,signal\n")
        for ti, yi in zip(t[sel], y[sel]):
            f.write(f"{ti:.6f},{'nan' if not np.isfinite(yi) else f'{yi:.1f}'}\n")
    return out_path


# =============================================================================
# 7. ANALYSIS DRIVER, BATCH / PEER-SHARE MARKDOWN
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

# NOT fenced, deliberately -- the opposite of the rule for a macro in a
# report's prose (package CLAUDE.md sec. 4, v1.9.1). pandoc reads the whole
# \begin{landscape}...\end{landscape} as ONE raw LaTeX block and passes it
# through verbatim, so the calls inside are already raw; a ```{=latex}
# fence inside it is itself passed through, and prints as literal
# "```=latex" text on a page of its own (tried first; found by rendering).
# Same template shape as spa_tool.py batch.
CHROMATOGRAM_TEMPLATE = """\\chromatogram
  [width=\\linewidth,height=6.8in,{opts}]
  {{{csv_rel}}}
  {{{peaklist}}}
  {{{title}}}
\\clearpage
"""
LANDSCAPE_PLOT_CM = (23.5, 14.5)


def analyse(source, peaks_spec="", solvent_spec="", min_prominence=20.0,
            window=0.08, ymax=None, xmin=None, xmax=None, baseline="auto",
            plot_size=(12.5, 7.5)):
    t, y, meta = read_any(source)
    wanted = sorted(parse_peak_spec(peaks_spec) + parse_peak_spec(solvent_spec, True))
    peaks, sigma = find_peaks(t, y, min_prominence, wanted or None, window, baseline)
    sel = np.isfinite(y)
    if xmin is not None:
        sel &= t >= xmin
    if xmax is not None:
        sel &= t <= xmax
    visible = [p for p in peaks if (xmin is None or p["tR"] >= xmin)
               and (xmax is None or p["tR"] <= xmax)]
    labels, ysug = assign_labels(visible, (float(t[sel][0]), float(t[sel][-1])),
                                 (float(y[sel].min()), float(y[sel].max())), ymax,
                                 plot_size)
    return {"t": t, "y": y, "meta": meta, "peaks": peaks, "sigma": sigma,
            "labels": labels, "ymax": nice_ceil(ysug) if ymax is None else ymax,
            "ydata_max": float(np.nanmax(y[sel]))}


def macro_opts(res, xmin=None, xmax=None, corrected=False):
    opts = [f"ymax={res['ymax']:.0f}"]
    if res["ydata_max"] > res["ymax"]:
        # A y-crop below the data maximum (a saturated solvent peak): clamp
        # the data to the axis, not just clip it. pgfplots scales its
        # internal y transform from the FULL data range, and with LR4 group
        # 4's 7.3e7-count peak under ymax=1.3e6 every label's axis-cs
        # coordinate then overflows TeX ("! Dimension too large"). The
        # starred key clamps instead of discarding, so the cropped peak still
        # runs up to the top edge exactly as clipping would have drawn it.
        opts.append(f"restrict y to domain*=-{res['ymax']:.0f}:{res['ymax']:.0f}")
    if xmin is not None:
        opts.append(f"xmin={xmin:g}")
    if xmax is not None:
        opts.append(f"xmax={xmax:g}")
    det = res["meta"].get("detector")
    if det:
        opts.append(f"ylabel={{{'Baseline-corrected ' if corrected else ''}{det} signal / counts}}")
    return ",".join(opts)


def batch(manifest, out_dir, md_path):
    """manifest entries: {raw, title, peaks, solvent, ymax, xmin, xmax,
    baseline, min_prominence, window, crop: {xmin, xmax, correct, exclude}}.
    With `crop`, the chromatogram plotted (and labelled) is the cropped CSV
    plain/<stem>_crop.csv instead of the full plain CSV."""
    csv_dir = os.path.join(out_dir, "csv")
    plain_dir = os.path.join(out_dir, "plain")
    md_dir = os.path.dirname(os.path.abspath(md_path))
    body = []
    stems = batch_stems([e["raw"] for e in manifest])
    for e, stem in zip(manifest, stems):
        src = e["raw"]
        r = read_raw(src)
        write_xcalibur_csv(r["time"], r["signal"], os.path.join(csv_dir, stem + ".csv"),
                           os.path.basename(src))
        plot_csv = write_plain_csv(r["time"], r["signal"],
                                   os.path.join(plain_dir, stem + "_plain.csv"))
        c = e.get("crop")
        if c:
            plot_csv = crop(src, os.path.join(plain_dir, stem + "_crop.csv"),
                            c.get("xmin"), c.get("xmax"), c.get("correct", False),
                            e.get("baseline", "auto"), c.get("exclude", ""))
        res = analyse(plot_csv, e.get("peaks", ""), e.get("solvent", ""),
                      e.get("min_prominence", 20.0), e.get("window", 0.08),
                      e.get("ymax"), e.get("xmin"), e.get("xmax"),
                      "none" if (c and c.get("correct")) else e.get("baseline", "auto"),
                      LANDSCAPE_PLOT_CM)
        res["meta"]["detector"] = r["meta"]["detector"]
        print(f"# {stem}  n={len(r['time'])}  peaks={len(res['peaks'])}  "
              f"ymax={res['ymax']:.0f}  -> {plot_csv}")
        for line in review_table(res["peaks"]):
            print("   ", line)
        body.append(CHROMATOGRAM_TEMPLATE.format(
            opts=macro_opts(res, e.get("xmin"), e.get("xmax"), bool(c and c.get("correct"))),
            csv_rel=os.path.relpath(plot_csv, md_dir),
            peaklist=format_peaklist(res["labels"]),
            title=latex_escape(e.get("title") or stem)))
    md = MD_FRONTMATTER + "\n\\begin{landscape}\n\n" + "\n".join(body) + "\n\\end{landscape}\n"
    os.makedirs(os.path.dirname(md_path) or ".", exist_ok=True)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    return md_path


# =============================================================================
# CLI
# =============================================================================
def cmd_info(args):
    r = read_raw(args.raw)
    m = r["meta"]
    dt = (m["t1"] - m["t0"]) / (m["n"] - 1)
    print(f"file        {m['path']}")
    print(f"version     {m['version']}")
    print(f"acquired    {m['acquired']:%Y-%m-%d %H:%M:%S} (UTC, from the file header)")
    print(f"instrument  {m['instrument']}   detector {m['detector']}   "
          f"{m['channel']} ({m['units']})")
    print(f"method      {m['method_file']}")
    print(f"points      {m['n']}   {m['t0']:g}..{m['t1']:.4f} min   "
          f"every {dt * 60:.3f} s ({1 / (dt * 60):.3g} Hz)")
    if not args.brief:
        print()
        print("\n".join(m["method"]))


def cmd_convert(args):
    r = read_raw(args.raw)
    stem = args.out or os.path.splitext(args.raw)[0]
    print("wrote", write_xcalibur_csv(r["time"], r["signal"], stem + ".csv",
                                      os.path.basename(args.raw)))
    print("wrote", write_plain_csv(r["time"], r["signal"], stem + "_plain.csv"))


def cmd_crop(args):
    print("wrote", crop(args.source, args.out, args.xmin, args.xmax, args.correct,
                        args.baseline, args.exclude))


def cmd_integrate(args):
    size = (tuple(float(v) for v in args.plot_size.split(",")) if args.plot_size
            else LANDSCAPE_PLOT_CM if args.landscape else (12.5, 7.5))
    res = analyse(args.source, args.peaks, args.solvent, args.min_prominence,
                  args.window, args.ymax, args.xmin, args.xmax, args.baseline, size)
    mode = "manual" if (args.peaks or args.solvent) else "auto"
    print(f"# {args.source}  mode={mode}  baseline={args.baseline}  "
          f"noise sigma={res['sigma']:.0f}  n_peaks={len(res['peaks'])}")
    for line in review_table(res["peaks"]):
        print("  ", line)
    tri, trap = markdown_tables(res["peaks"], parse_known(args.known))
    print("\ntriangulation table:\n")
    print("\n".join(tri))
    print("\nintegration table:\n")
    print("\n".join(trap))
    print("\n\\chromatogram options:", macro_opts(res, args.xmin, args.xmax))
    print("\\chromatogram peaks:  ", format_peaklist(res["labels"]))


def cmd_verify(args):
    r = read_raw(args.raw)
    t, y, _ = read_any(args.csv)
    ok = len(t) == len(r["time"])
    print(f"points  raw={len(r['time'])}  csv={len(t)}  {'OK' if ok else 'MISMATCH'}")
    if ok:
        ds = np.max(np.abs(y - r["signal"]))
        dtm = np.max(np.abs(t - r["time"]))
        print(f"max |signal diff| = {ds:g}   max |time diff| = {dtm:.2g} min")
        ok = ds == 0 and dtm < 1e-8
    print("VERIFIED" if ok else "NOT VERIFIED -- do not trust this file's reading")
    sys.exit(0 if ok else 1)


def cmd_batch(args):
    if args.manifest:
        with open(args.manifest) as f:
            manifest = json.load(f)
    else:
        if not args.raw:
            sys.exit("batch needs --manifest FILE.json or --raw A.RAW B.RAW ...")
        titles = args.titles.split(",") if args.titles else [None] * len(args.raw)
        if len(titles) != len(args.raw):
            sys.exit("--titles must have exactly one entry per --raw file")
        manifest = [{"raw": s, "title": t} for s, t in zip(args.raw, titles)]
    md = batch(manifest, args.out_dir, args.md)
    print(f"\nwrote {md} ({len(manifest)} chromatograms)")
    print("build it with pdfmd.py -- never bare pandoc (see nulabreport's CLAUDE.md)")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="irspec gc", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("info", help="acquisition details + embedded instrument method")
    p.add_argument("raw")
    p.add_argument("--brief", action="store_true", help="skip the method text")
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("convert", help=".RAW -> archival CSV + plain CSV")
    p.add_argument("raw")
    p.add_argument("--out", default=None, help="output stem (default: input stem)")
    p.set_defaults(func=cmd_convert)

    p = sub.add_parser("crop", help="trimmed / baseline-corrected / gapped plain CSV")
    p.add_argument("source", help=".RAW, Xcalibur CSV export, or plain CSV")
    p.add_argument("--out", required=True)
    p.add_argument("--xmin", type=float, default=None)
    p.add_argument("--xmax", type=float, default=None)
    p.add_argument("--correct", action="store_true", help="subtract the baseline")
    p.add_argument("--baseline", default="auto",
                   help="auto (SNIP), flat[:min], or anchor times '2.0,2.7,...' (docstring sec. 4)")
    p.add_argument("--exclude", default="", help="blank time ranges: '3.23-3.46,11.6-12'")
    p.set_defaults(func=cmd_crop)

    p = sub.add_parser("integrate", help="triangulation + integration tables, peak list")
    p.add_argument("source", help=".RAW, Xcalibur CSV export, or plain/cropped CSV")
    p.add_argument("--peaks", default="", help="manual mode: '2.84=Methanol,3.02=Ethanol,...'")
    p.add_argument("--solvent", default="", help="labelled but excluded from %%: '3.30=Acetone'")
    p.add_argument("--known", default="", help="known %%: 'Methanol=6.67,Ethanol=13.33,...'")
    p.add_argument("--baseline", default="auto",
                   help="auto (SNIP), flat[:min] (median of the run's first 0.5 min -- "
                        "LR4's method), anchor times '2.0,2.7,...', or none (already corrected)")
    p.add_argument("--min-prominence", type=float, default=20.0,
                   help="auto mode: x noise sigma (default 20)")
    p.add_argument("--window", type=float, default=0.08, help="manual mode match window, min")
    p.add_argument("--ymax", type=float, default=None, help="crop the y-axis (e.g. a solvent peak)")
    p.add_argument("--xmin", type=float, default=None)
    p.add_argument("--xmax", type=float, default=None)
    p.add_argument("--landscape", action="store_true",
                   help="size labels for a full landscape page (peer-share)")
    p.add_argument("--plot-size", default=None,
                   help="plot box W,H in cm the labels are sized for (default 12.5,7.5 "
                        "= \\chromatogram's default; a \\chromatogramstack panel is "
                        "much shorter, e.g. 12.5,4)")
    p.set_defaults(func=cmd_integrate)

    p = sub.add_parser("verify", help="check a .RAW reading against an Xcalibur CSV export")
    p.add_argument("raw")
    p.add_argument("csv")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("batch", help="several .RAW -> CSVs + one peer-share markdown")
    p.add_argument("--manifest", default=None, help="JSON list, see batch()'s docstring")
    p.add_argument("--raw", nargs="+", default=None)
    p.add_argument("--titles", default=None)
    p.add_argument("--out-dir", required=True, help="directory for csv/ and plain/")
    p.add_argument("--md", required=True)
    p.set_defaults(func=cmd_batch)

    args = ap.parse_args(argv)
    try:
        args.func(args)
    except RawFormatError as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()

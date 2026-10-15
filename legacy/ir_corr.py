#!/usr/bin/env python3
"""ir_corr.py -- Pearson correlation between two spectra, the way the reports
quote it.

    python3 ir_corr.py a.csv b.csv [c.csv ...] [--lo 700] [--hi 3900] [--step 1]

Every file is a plain two-column CSV with a header row (wavenumber,intensity),
i.e. what spa_tool.py / jdx_tool.py write as the `plain` CSV and what
\\irspectrum reads. With two files it prints one r; with more, the first file
is the reference and each of the others is correlated against it.

Method (stated once in the text of LR4-5 and to be stated the same way in any
report that quotes an r): both traces are linearly interpolated onto one
common wavenumber grid (default 1 cm-1 steps, 700 to 3900 cm-1, the range the
diamond ATR spectra are clean over) and compared by Pearson's correlation
coefficient, numpy.corrcoef. Nothing else: no baseline correction, no
normalisation (r is insensitive to a constant offset or scale anyway), no
derivative.

Why a tool: until 2026-09-26 every r in LR4-5 was an ad hoc snippet run once
and pasted into an HTML comment. The author asked for "that correlation
coefficient a tool" so that each value is reproducible from one script. It
reproduces LR4-5's published values exactly (product vs stock cinnamyl
alcohol 0.9988, vs aldehyde 0.5032; Unknown 7 vs stock aldehyde 0.9961).

What r does and does not show: two runs of the same sample on the same
instrument give r > 0.99; a product against its authentic sample on the same
instrument, likewise. Across techniques it is a poor measure -- an ATR
spectrum of a solid against an old transmission spectrum of the same
compound (LR4-5, benzophenone) gave only 0.35 over 700-3900 and 0.54 over
1400-3900, because the band DEPTHS differ even where the positions agree.
Compare band positions there instead, and use r for like against like.

numpy only (no scipy), so it runs on the author's Mac as installed.
"""
import argparse
import sys

import numpy as np


def load(path):
    """A plain CSV, sorted by wavenumber (np.interp needs increasing x)."""
    d = np.loadtxt(path, delimiter=",", skiprows=1)
    order = np.argsort(d[:, 0])
    return d[order, 0], d[order, 1]


def corr(a, b, lo=700.0, hi=3900.0, step=1.0):
    """Pearson r of spectra a and b ((x, y) pairs) on a common grid."""
    grid = np.arange(lo, hi + step / 2, step)
    ya = np.interp(grid, *a)
    yb = np.interp(grid, *b)
    return float(np.corrcoef(ya, yb)[0, 1])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("files", nargs="+", help="plain CSVs; the first is the reference")
    ap.add_argument("--lo", type=float, default=700.0, help="grid start, cm-1 (700)")
    ap.add_argument("--hi", type=float, default=3900.0, help="grid end, cm-1 (3900)")
    ap.add_argument("--step", type=float, default=1.0, help="grid step, cm-1 (1)")
    args = ap.parse_args()
    if len(args.files) < 2:
        sys.exit("need at least two files")
    ref = load(args.files[0])
    for other in args.files[1:]:
        r = corr(ref, load(other), args.lo, args.hi, args.step)
        print(f"{r:.4f}  {args.files[0]}  ~  {other}")


if __name__ == "__main__":
    main()

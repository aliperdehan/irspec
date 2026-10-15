#!/usr/bin/env python3
"""absorptivity_to_absorbance.py -- NIST QUANT-IR gas-phase .jdx -> true
Absorbance CSVs, for any report.

    python3 absorptivity_to_absorbance.py FILE.jdx --name NAME \\
        --out csv/NAME.csv --plain-out plain/NAME.csv  (--peak-a A | --cl CL)

Self-contained, like this folder's other tools: what a future session needs
is in this docstring.

===============================================================================
1. WHAT THE FILE HOLDS, AND WHAT IT IS NOT
===============================================================================
NIST QUANT-IR gas-phase spectra on the WebBook (##$NIST SOURCE=QUANT-IR, e.g.
1634-04-4-IR.jdx, MTBE, seen 2026-10-06) carry ##YUNITS=(micromol/mol)-1m-1
(base 10): the decadic absorption coefficient per (umol/mol x m), i.e.

        alpha = A / (c * L)        c in umol/mol (mole fraction), L in m

so values are ~1e-3 and are NOT an absorbance. jdx_tool.py reads them as
"Absorbance" (same upward bands, nothing converted) so it can decode the
file, but they cannot go on an axis next to real spectra, and pgfplots stops
with "Dimension too large" at that magnitude.

===============================================================================
2. THE CONVERSION
===============================================================================
Beer-Lambert, linear in concentration x path:

        A = alpha * c * L = alpha * CL,        CL in umol/mol x m

The file does NOT state c or L (it says "Primary Gas Standard" and a multipass
cell, nothing numeric), and this script never invents them. You must give the
product, one of two ways:

  --cl CL        the real c x L, umol/mol x m, if you know it from the
                 source paper/NIST's record (a true absorbance).
  --peak-a A     scale so the strongest band reaches absorbance A (CL =
                 A / max alpha). Peak-normalised: the SHAPE and band ratios
                 are exact (A is linear in alpha), the absolute height is a
                 choice, not a measurement. Say so in the figure caption
                 ("scaled to strongest band A = 1").

Because the conversion is a single multiplier, band ratios, positions and
widths are those of the original; only the y scale changes. The archival
CSV is written too, in Absorbance, through jdx_tool.py's own writers (same
shapes as any other jdx_tool output). Both CSVs are therefore ready for
spa_peaks.py --axis Absorbance and \\irspectrum {Absorbance}.

Then, as for every Absorbance source, run absorbance_to_transmittance.py on
the plain CSV: the house convention is %T only. With --peak-a the %T depth
is as arbitrary as the chosen A, so say so in the caption.

Verified 2026-10-06 on 1634-04-4-IR.jdx: output max = the --peak-a value,
band ratios identical to the input's, plain CSV 650+ cm-1 only.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jdx_tool  # noqa: E402  (decoder and house CSV writers)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("jdx", help="QUANT-IR .jdx with absorptivity y-units")
    ap.add_argument("--name", required=True, help="NAME_WITH_UNDERSCORES (CSV header)")
    ap.add_argument("--out", required=True, help="archival CSV path")
    ap.add_argument("--plain-out", required=True, help="plain CSV path")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--cl", type=float, help="c x L, umol/mol x m (true absorbance)")
    g.add_argument("--peak-a", type=float, help="scale so max band = this absorbance")
    args = ap.parse_args()

    xs, ys, meta = jdx_tool.read_jdx(args.jdx)
    with open(args.jdx, encoding="utf-8", errors="replace") as f:
        if "(MICROMOL/MOL)-1M-1" not in f.read().upper():
            sys.exit(f"{args.jdx}: y-units are not (micromol/mol)-1m-1; nothing to convert")
    top = max(ys)
    if top <= 0:
        sys.exit("no positive band in the spectrum")
    cl = args.cl if args.cl is not None else args.peak_a / top
    ys = [y * cl for y in ys]
    jdx_tool.write_csv(xs, ys, meta, args.out, args.name)
    jdx_tool.write_plain_csv(xs, ys, meta, args.plain_out)
    how = "c x L given" if args.cl is not None else f"peak-normalised, strongest band A = {args.peak_a}"
    print(f"{args.jdx}: A = alpha x {cl:.6g} ({how}); max A {max(ys):.4f} "
          f"-> {args.out}, {args.plain_out}")


if __name__ == "__main__":
    main()

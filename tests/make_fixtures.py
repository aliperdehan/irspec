"""Write the JCAMP-DX test fixtures from the author's own phenacetin spectrum.

    python3 tests/make_fixtures.py

Three .jdx files, all derived from tests/data/golden_plain.csv (the author's
own OMNIC spectrum, diamond ATR), so nothing third-party is published:

  phenacetin_T.jdx        fractional Transmittance (WebBook's native shape)
  phenacetin_A.jdx        Absorbance, A = -log10(T)
  phenacetin_quantir.jdx  NIST QUANT-IR-shaped: absorptivity-like y-units,
                          values = A * 1e-3 (exercises absorptivity_to_absorbance)

Plain ASDF, five points per line, no compression: the one layout jdx_tool.py
decodes.
"""
import csv
import math
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"


def read_plain():
    with open(DATA / "golden_plain.csv", newline="") as f:
        r = csv.reader(f)
        next(r)
        pts = [(float(a), float(b)) for a, b in r]
    pts.sort(key=lambda p: -p[0])           # descending wavenumber
    return pts


def write_jdx(name, title, yunits, ys, xs, extra=()):
    n = len(xs)
    dx = (xs[-1] - xs[0]) / (n - 1)
    out = [f"##TITLE={title}", "##JCAMP-DX=4.24", "##DATA TYPE=INFRARED SPECTRUM",
           "##CAS REGISTRY NO=62-44-2", "##ORIGIN=irspec test fixture (author's own spectrum)",
           *extra, "##XUNITS=1/CM", f"##YUNITS={yunits}", "##XFACTOR=1.0", "##YFACTOR=1.0",
           f"##FIRSTX={xs[0]:.3f}", f"##LASTX={xs[-1]:.3f}", f"##DELTAX={dx:.6f}",
           f"##NPOINTS={n}", "##XYDATA=(X++(Y..Y))"]
    for i in range(0, n, 5):
        out.append(f"{xs[i]:.3f} " + " ".join(f"{y:.8g}" for y in ys[i:i + 5]))
    out.append("##END=")
    (DATA / name).write_text("\n".join(out) + "\n")


pts = read_plain()
xs = [p[0] for p in pts]
T = [p[1] / 100.0 for p in pts]
assert min(T) > 0, "need strictly positive T for -log10"
A = [-math.log10(t) for t in T]
write_jdx("phenacetin_T.jdx", "PHENACETIN CRUDE (TEST FIXTURE)", "TRANSMITTANCE", T, xs)
write_jdx("phenacetin_A.jdx", "PHENACETIN CRUDE (TEST FIXTURE)", "ABSORBANCE", A, xs)
write_jdx("phenacetin_quantir.jdx", "PHENACETIN CRUDE (QUANT-IR-SHAPED TEST FIXTURE)",
          "(micromol/mol)-1m-1 (base 10)", [a * 1e-3 for a in A], xs,
          extra=("##$NIST SOURCE=QUANT-IR",))
print("wrote 3 fixtures,", len(xs), "points each")

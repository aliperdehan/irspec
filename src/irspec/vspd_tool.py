r"""irspec vspd -- Shimadzu UVProbe / LabSolutions UV-Vis spectrum files (.vspd) -> CSV.

USAGE:
    irspec vspd info    SPECTRUM.vspd
    irspec vspd convert SPECTRUM.vspd [--out X.csv] [--decimals 6] [--keep-order]
    irspec vspd verify  SPECTRUM.vspd EXPORT.txt     # the instrument's own text export
    irspec vspd peaks   SPECTRUM.vspd [--xmin 300 --xmax 700]

  info     instrument, date, comment, scan range, stored peak/valley picks, history.
  convert  one CSV per spectrum: `wavelength,absorbance`, ascending (what pgfplots wants), comma and
           decimal point.  Several spectra in one file give X_1.csv, X_2.csv ... (never seen yet).
  peaks    the peak picks the user made in LabSolutions (stored in the file), as the peak list of
           `\labplot[kind=uvvis]` (`x/apex_y/label_y/{}`: an empty name prints the wavelength), with
           the `ymax` that leaves room for the labels.  --xmin/--xmax keep only picks inside the
           window you will plot (the same numbers you give the plot).  Peaks only: a valley pick's
           label would hang over the trace, since the apex label style sits above its point.  The picks
           are the instrument software's, not found here: no pick, no label.
  verify   decodes the .vspd, rounds it the way the export does (3 decimals) and compares it
           with the .txt export row by row.  Exit 0 when every wavelength and every rounded
           absorbance agrees, 1 otherwise.  Run it on every new instrument or software version.

Needs `olefile` (installed with irspec).  Moved here from nulabreport's tools/vspd_tool.py
(2026-11-11); the output is byte for byte what that script wrote.

--------------------------------------------------------------------------------------------
1. THE FORMAT (reverse-engineered 2026-11-05 from ONE file, the author's own scan, now
   tests/data/uvvis.vspd: LabSolutions UV-Vis 1.11, UV-2600, 101 points, 200-700 nm,
   Absorbance).  Not documented by Shimadzu.
--------------------------------------------------------------------------------------------
A .vspd is an OLE2 / Compound File Binary container (the same family as .vqud and old .doc).
The spectrum lives in

    DataStorage1/DataSetGroup/DataSet1/DataSpectrumStorage/Data/X Data.1
    DataStorage1/DataSetGroup/DataSet1/DataSpectrumStorage/Data/Y Data.1
    DataStorage1/DataSetGroup/DataSet1/DataSpectrumStorage/Data/Data Header.1   (u32 n, u32 2)

  * X Data.N / Y Data.N: n little-endian doubles each (808 bytes for 101 points).  The ".1" is
    the spectrum number inside the data set; this tool reads every X/Y Data.N pair it finds.
  * THE ORDER IS DESCENDING (700 -> 200 nm), the scan direction, not the export's order.
    `convert` sorts ascending unless --keep-order.
  * The Y values are float32 numbers widened to doubles (4.399209499359131 is the float32
    4.3992095), so only about 7 significant digits are real.  `convert` writes %.7g by
    default; `--decimals N` writes fixed decimals instead.
  * DataSpectrumStorage/DataHeader/Header Info starts with three doubles: start (700),
    end (200), step (-5), i.e. the scan in the direction it was run.  The remaining bytes
    (flags) and what Data Header's "2" means are NOT decoded.  Only Absorbance has been seen,
    so the CSV header `absorbance` is a default, not something read from the file: if a %T file ever
    arrives, check `verify` against its export before trusting the column name.
  * DataSetHeaderInfo: data-set name ("RawData"), a Windows OLE date (days since 1899-12-30,
    a double), organisation, software, version, maker, instrument, serial number and the
    method file (.vspm) path, as length-prefixed (1 byte) ASCII strings.  `info` lists the
    strings it can read; treat the field names it prints as guesses by position, the values
    as read.
  * DataPeakPick / Header Info also keep the peak and valley picks the user made, as
    `[len]Peak255.000 [len]"2" <double x> <double y>`: label with the wavelength, an index,
    then x and y.  `info` prints them.  (y is again float32: 0.125 at the 375 nm valley.)
  * SummaryInformation (standard OLE property set, code page 1251) carries the user's
    "Comments" field ("test comment text").
  * DataHistoryStorage/DataSetHistory is a log (created, peak pick settings, renamed from ...).

2. THE TEXT EXPORT (`File > Save as text`, CRLF):
        NAME - RawData                <- data-set name
        Wavelength nm.,Abs.           <- column names
        200.0,4.056                   <- ascending, 1 decimal for nm, 3 for Abs
  Verified 2026-11-05: wavelengths identical, and the .vspd's Y rounded to 3 decimals equals
  the export's value on all 101 rows (largest |difference| before rounding 0.00049).
"""
import argparse
import csv
import datetime
import os
import re
import struct
import sys

import olefile

BASE = "DataStorage1/DataSetGroup/DataSet1/"


def read_stream(ole, path):
    try:
        return ole.openstream(path).read()
    except OSError:
        return None


def spectra(ole):
    """[(n, [x...], [y...])] for every X Data.N / Y Data.N pair, in file order (descending nm)."""
    out = []
    pre = BASE + "DataSpectrumStorage/Data/"
    names = sorted("/".join(s) for s in ole.listdir(streams=True, storages=False)
                   if "/".join(s).startswith(pre + "X Data."))
    for p in names:
        n = p.rsplit(".", 1)[1]
        xb, yb = read_stream(ole, p), read_stream(ole, pre + "Y Data." + n)
        if yb is None or len(xb) != len(yb) or len(xb) % 8:
            raise SystemExit(f"X Data.{n}/Y Data.{n}: sizes {len(xb)}/{len(yb or b'')} do not match -- unknown layout")
        k = len(xb) // 8
        hdr = read_stream(ole, pre + "Data Header." + n)
        if hdr and struct.unpack_from("<I", hdr, 0)[0] != k:
            raise SystemExit(f"Data Header.{n} says {struct.unpack_from('<I', hdr, 0)[0]} points, the streams hold {k}")
        out.append((int(n), list(struct.unpack(f"<{k}d", xb)), list(struct.unpack(f"<{k}d", yb))))
    if not out:
        raise SystemExit("no DataSpectrumStorage/Data/X Data.N stream: not a .vspd this tool knows")
    return out


def lp_strings(b, minlen=3):
    """Length-prefixed (1 byte) printable-ASCII strings found in a byte block, in order."""
    out, i = [], 0
    while i < len(b) - 1:
        n = b[i]
        s = b[i + 1:i + 1 + n]
        if n >= minlen and len(s) == n and all(32 <= c < 127 for c in s):
            out.append(s.decode("ascii"))
            i += 1 + n
        else:
            i += 1
    return out


def ole_date(days):
    return datetime.datetime(1899, 12, 30) + datetime.timedelta(days=days)


def picks(ole):
    """Peak/valley picks: [(label, x, y)] from Header Info."""
    b = read_stream(ole, BASE + "DataSpectrumStorage/DataHeader/Header Info") or b""
    out = []
    for m in re.finditer(rb"[\x05-\x20](Peak|Valley)(\d+\.\d+)", b):
        q = m.end()
        n = b[q]                       # the index string ("3"), length-prefixed
        q += 1 + n
        if q + 16 <= len(b):
            x, y = struct.unpack_from("<2d", b, q)
            out.append((m.group(1).decode() + m.group(2).decode(), x, y))
    return out


def cmd_info(path):
    ole = olefile.OleFileIO(path)
    print(f"file: {os.path.basename(path)}")
    meta = ole.get_metadata()
    if meta.comments:
        print("comment:", meta.comments.decode("cp1251", "replace"))
    hdr = read_stream(ole, BASE + "DataSetHeaderInfo") or b""
    if len(hdr) >= 17:
        name = hdr[1:1 + hdr[0]].decode("latin1")
        when = ole_date(struct.unpack_from("<d", hdr, 1 + hdr[0] + 4)[0])
        print(f"data set: {name}   saved {when:%Y-%m-%d %H:%M:%S}")
    for s in lp_strings(hdr[1 + hdr[0] + 12:] if hdr else b""):
        print("  header string:", s)
    for n, xs, ys in spectra(ole):
        lo, hi = min(xs), max(xs)
        step = abs(xs[1] - xs[0]) if len(xs) > 1 else 0
        print(f"spectrum {n}: {len(xs)} points, {lo:g}-{hi:g} nm, step {step:g} nm, "
              f"stored {'descending' if xs[0] > xs[-1] else 'ascending'}, y {min(ys):.4f} .. {max(ys):.4f}")
    for label, x, y in picks(ole):
        print(f"  pick {label}: x={x:g}  y={y:.4f}")
    hist = read_stream(ole, BASE + "DataHistoryStorage/DataSetHistory") or b""
    for s in lp_strings(hist, minlen=8):
        print("  history:", s)


def cmd_convert(path, out, decimals, keep_order):
    ole = olefile.OleFileIO(path)
    base = out or os.path.splitext(os.path.basename(path))[0] + ".csv"
    specs = spectra(ole)
    for n, xs, ys in specs:
        rows = list(zip(xs, ys))
        if not keep_order:
            rows.sort()
        name = base if len(specs) == 1 else f"{os.path.splitext(base)[0]}_{n}.csv"
        fmt = (lambda v: f"{v:.{decimals}f}") if decimals is not None else (lambda v: f"{v:.7g}")
        with open(name, "w", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["wavelength", "absorbance"])
            w.writerows([[f"{x:g}", fmt(y)] for x, y in rows])
        print(f"wrote {name}  ({len(rows)} points, {rows[0][0]:g} -> {rows[-1][0]:g} nm)")


def cmd_peaks(path, xmin, xmax):
    ole = olefile.OleFileIO(path)
    _, xs, ys = spectra(ole)[0]
    lo = xmin if xmin is not None else min(xs)
    hi = xmax if xmax is not None else max(xs)
    win = [y for x, y in zip(xs, ys) if lo <= x <= hi]
    if not win:
        raise SystemExit(f"no data between {lo:g} and {hi:g} nm")
    span = max(win) - min(win)
    off = 0.06 * span                     # label stands this far above the apex, in data units
    chosen = [(l, x, y) for l, x, y in picks(ole) if lo <= x <= hi and l.startswith("Peak")]
    if not chosen:
        print(f"no stored peak pick between {lo:g} and {hi:g} nm", file=sys.stderr)
        return 1
    entries, top = [], max(win)
    for l, x, y in sorted(chosen, key=lambda t: t[1]):
        apex = round(y, 4)
        label = round(y + off, 4)
        entries.append(f"{x:g}/{apex:g}/{label:g}/{{}}")
        top = max(top, label)
    print(",".join(entries))
    print(f"ymax suggestion: {top + 0.08 * (top - min(win)):.2f}   (window {lo:g}-{hi:g} nm, "
          f"data {min(win):.3f} .. {max(win):.3f})", file=sys.stderr)
    return 0


def read_export(path):
    lines = [l.strip() for l in open(path, newline="").read().replace("\r", "").split("\n") if l.strip()]
    rows = []
    for l in lines:
        m = re.fullmatch(r"(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)", l)
        if m:
            rows.append((float(m.group(1)), m.group(2)))
    head = [l for l in lines if not re.fullmatch(r"-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?", l)]
    return head, rows


def cmd_verify(path, txt):
    ole = olefile.OleFileIO(path)
    specs = spectra(ole)
    head, rows = read_export(txt)
    if len(specs) != 1:
        raise SystemExit(f"{len(specs)} spectra in the file; the export format with several is not known")
    _, xs, ys = specs[0]
    mine = sorted(zip(xs, ys))
    theirs = sorted(rows)
    print(f"export header lines: {head}")
    print(f"points: vspd {len(mine)}, export {len(theirs)}")
    if len(mine) != len(theirs):
        print("FAIL: different number of points")
        return 1
    decimals = max(len(v.split(".")[1]) if "." in v else 0 for _, v in theirs)
    bad_x = sum(1 for (x, _), (tx, _) in zip(mine, theirs) if abs(x - tx) > 1e-9)
    # an export that shows 3 decimals is a rounding of the stored float: compare as strings
    bad_y = [(x, y, tv) for (x, y), (_, tv) in zip(mine, theirs) if f"{y:.{decimals}f}" != tv]
    worst = max(abs(y - float(tv)) for (_, y), (_, tv) in zip(mine, theirs))
    print(f"wavelengths differing: {bad_x}")
    print(f"values differing after rounding to {decimals} decimals: {len(bad_y)}   (largest raw |diff| {worst:.6f})")
    for x, y, tv in bad_y[:10]:
        print(f"   {x:g} nm: vspd {y!r} -> {y:.{decimals}f}, export {tv}")
    ok = bad_x == 0 and not bad_y
    print("OK: the .vspd and the export agree" if ok else "FAIL")
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="irspec vspd", description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("info"); a.add_argument("vspd")
    c = sub.add_parser("convert"); c.add_argument("vspd"); c.add_argument("--out")
    c.add_argument("--decimals", type=int, default=None, help="fixed decimals (default: %%.7g, the float32 precision)")
    c.add_argument("--keep-order", action="store_true", help="keep the stored (descending) order")
    v = sub.add_parser("verify"); v.add_argument("vspd"); v.add_argument("txt")
    k = sub.add_parser("peaks"); k.add_argument("vspd")
    k.add_argument("--xmin", type=float); k.add_argument("--xmax", type=float)
    args = ap.parse_args(argv)
    if args.cmd == "info":
        cmd_info(args.vspd)
    elif args.cmd == "convert":
        cmd_convert(args.vspd, args.out, args.decimals, args.keep_order)
    elif args.cmd == "peaks":
        sys.exit(cmd_peaks(args.vspd, args.xmin, args.xmax))
    else:
        sys.exit(cmd_verify(args.vspd, args.txt))


if __name__ == "__main__":
    main()

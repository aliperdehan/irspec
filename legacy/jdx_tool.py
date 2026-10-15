#!/usr/bin/env python3
"""jdx_tool.py -- JCAMP-DX (.jdx) IR spectra -> CSV, for any report.

Self-contained, like this folder's other tools: what a future session
needs to reproduce this decode is here, not only in a report's own chat
history. If you learn something new about the format (a new encoding a
real file actually uses, a convention the author states explicitly), the fix
goes in this docstring, not only in a report folder's notes or in chat.

WHAT THIS IS FOR
    NIST WebBook (and similar) IR spectra are commonly distributed as
    JCAMP-DX (.jdx) text files. Nothing normally reads that format
    directly; this script decodes it to the same CSV shape Spectragryph
    exports (semicolon-delimited, decimal commas, descending wavenumber,
    full range), so a WebBook reference spectrum sits next to and reads
    the same way as this lab's OMNIC-derived ones (see spa_tool.py and its
    own module docstring for that sibling .SPA/.SPG format).

    This script is report-agnostic on purpose -- unlike spa_tool.py it has
    nothing that assumes a particular report's directory layout, because
    the report it was first written for (LR3, comparing IR unknowns
    against WebBook references) needed it as a *cross-report* tool, not a
    one-off script living inside that report's own folder. Any
    report-specific mapping (which CAS number is which compound in THAT
    report) is passed in via --name-map, never hardcoded here -- see
    section 5.

===============================================================================
1. VALIDATED AGAINST A REAL SPECTRAGRYPH EXPORT
===============================================================================
First validated on LR3's literature/webbook/jdx/78-93-3-IR.jdx (2-butanone):
The author had hand-exported that same file from Spectragryph as a CSV
specifically so this script's decode could be diffed against it. Result:
exact match -- every wavenumber to 3 dp, every intensity to 4 dp, all 2700
points, full range (max |Δy| = 1e-10, which is just Spectragryph's own
print rounding for values it displays as `1E-10`). If you change the
decode logic, re-run an equivalent diff before trusting it on anything
else -- see read_jdx() below.

===============================================================================
2. THE FORMAT
===============================================================================
Plain-text JCAMP-DX, LDR ("##KEY=value") header, then one
##XYDATA=(X++(Y..Y)) block:

    450.0 171 260 185 251 263 310 242 380 303 326
    490.0 355 337 262 272 243 194 251 222 322 273
    ...

Each data line's FIRST number is the real X of that line's first Y value
(a checksum, not something to trust blindly -- checked against the running
computed X, see read_jdx() below); every following number on the line is
the next Y at a further +DELTAX step. Header fields used:

    XFACTOR, YFACTOR   encoded value * factor = real value. Every file
                        validated so far has XFACTOR=1 -- if a file ever
                        has XFACTOR != 1, this script applies it to the
                        leading per-line X the same as any other X.
    DELTAX              real cm^-1 (or native-unit) step between points --
                        NOT re-multiplied by XFACTOR (validated: the
                        2-butanone diff above only matches if DELTAX is
                        taken as already real, matching FIRSTX/LASTX which
                        are themselves stated as real values). ITS SIGN IN
                        THE HEADER IS NOT TRUSTED: some producers (seen on
                        two Coblentz Society/DOW files, 91-01-0-IR.jdx
                        benzhydrol and 119-61-9-IR.jdx benzophenone, both
                        2026-09-21) write DELTAX as a bare positive
                        magnitude even though the data actually runs
                        FIRSTX -> LASTX descending. This script derives the
                        real sign from FIRSTX vs LASTX (FIRSTX > LASTX =>
                        negative step) and only takes DELTAX's magnitude
                        from the header. Getting this wrong doesn't just
                        misfire the checksum warning below -- it silently
                        mis-assigns every non-leading Y on each data line to
                        the wrong X, corrupting the whole file, so this is
                        load-bearing, not cosmetic.
    FIRSTX/LASTX/NPOINTS sanity-checked against the parsed data; mismatch
                        is a loud warning, not a silent fix.

A sign may be the only separator between two values ('23130-61334' =
23130, -61334; NIST QUANT-IR, 2026-10-06) -- that is plain JCAMP AFFN, not
ASDF, and _tokens() splits it (never at an exponent's sign: 1E-5). Checked on
1634-04-4-IR.jdx: 3527 points = NPOINTS, max y = ##MAXY.

EVERY FILE VALIDATED SO FAR IS UNCOMPRESSED PLAIN ASCII NUMBERS -- no JCAMP
ASDF letter-encoding (SQZ/DIF/DUP: the A-Z/a-z/@ digit-substitution scheme
other JCAMP files sometimes use for the data table). This script
DELIBERATELY REFUSES to guess at that encoding: if a data-line token isn't
a plain number, read_jdx() raises rather than silently mis-decoding. If a
future file needs it, write and validate a real ASDF decoder first (there
is a public spec -- don't reverse-engineer it from one file).

===============================================================================
3. X-UNITS: CM^-1 IS NOT THE ONLY ONE SEEN
===============================================================================
##XUNITS is "1/CM" or its spelling "CM-1" (both used as-is; "CM-1" seen
2026-10-06 on the NIST QUANT-IR gas-phase file 1634-04-4-IR.jdx) or
"MICROMETERS" (seen on a 2-pentanone WebBook file). Micrometers are converted to wavenumber with the
standard wavenumber[cm^-1] = 10000 / x[um] -- and because that inverts the
ordering (ascending um = descending cm^-1), the row order is reversed
after conversion so every output CSV ends up sorted the same way
(descending wavenumber, matching the OMNIC/Spectragryph convention
spa_tool.py already uses for its archival CSV). Never silently handle a
third XUNITS value -- add and validate it here first (this script raises
on anything else it doesn't recognise).

===============================================================================
4. Y-UNITS: ABSORBANCE VS TRANSMITTANCE -- NEVER CONVERTED BETWEEN
===============================================================================
##YUNITS is "ABSORBANCE" or "TRANSMITTANCE" per file (a real batch has had
both in the same set). NIST QUANT-IR gas-phase files (1634-04-4-IR.jdx, MTBE,
2026-10-06) instead say "(micromol/mol)-1m-1 (base 10)": a decadic absorption
coefficient per (umol/mol)*m, i.e. absorbance normalised by concentration x
path. It is linear in absorbance, bands point up, and values are ~1e-3, so it
is read as Absorbance (axis_label "Absorbance") and left untouched -- it is
NOT a true absorbance and must not be turned into %T with T = 10^-A. Transmittance values are FRACTIONAL (0-1) in every
WebBook file seen so far, not percent -- matches the Spectragryph
reference CSV's own header ("Transmittance", not "Transmittance %") and
its 0-1-range values. This is DIFFERENT from spa_tool.py's OMNIC-derived
CSVs, whose axis_of() auto-labels "Transmittance %" (0-100) because that
is what this lab's own instrument exports. If a report puts a WebBook
curve and an OMNIC-derived curve on the same axes, one is 0-1 and the
other is 0-100 -- rescale explicitly at the report level; this script
never converts one to the other or rescales fractional transmittance to
percent on its own.

===============================================================================
5. OUTPUT CONVENTION, AND NAMING
===============================================================================
write_csv() mirrors the Spectragryph export byte-for-byte in structure
(not necessarily in every number's string formatting -- Spectragryph
switches to scientific notation for very small values; this script always
writes fixed-point, which is a cosmetic difference only, not a data one):

    ;{name};
    Wavenumbers [1/cm];{axis_label};
    {x:.3f};{y:.4f};        <- one row per point, decimal commas, ';' EOL
    ...                        sorted descending by wavenumber

Full range, untouched -- this is the archival-equivalent CSV.

write_plain_csv() (added 2026-09-22, folding in what LR4-5's webbook/ first
did as a one-off script) writes the second half of the house two-CSV
convention spa_tool.py already uses for OMNIC data -- clipped to >=650
cm^-1 AT WRITE TIME, ascending order, comma/decimal-point, no name/axis
header line:

    wavenumber,intensity
    {x:.3f},{y:.4f}         <- one row per point, comma, decimal point,
    ...                        sorted ASCENDING, '\r\n' EOL, x >= 650 only

FRACTIONAL TRANSMITTANCE (0-1, every WebBook Transmittance .jdx seen so
far) IS RESCALED x100 IN THE PLAIN CSV ONLY -- matching this lab's own
OMNIC %T scale (0-100), so a WebBook curve and an OMNIC curve plot
correctly on the same y-axis in a report figure. Absorbance sources are
never rescaled (nothing to rescale to -- Absorbance has no analogous
0-100 house convention). This is NOT the Absorbance<->Transmittance
conversion section 4 above refuses to do -- it is a within-Transmittance
unit change (fraction -> percent), and it ONLY ever touches the plain CSV;
write_csv()'s archival output stays exactly as decoded (fractional, for a
Transmittance source), so the original WebBook values are never lost.
Verified byte-for-byte against LR4-5's own hand-written one-off script
before folding it in here (2026-09-22): both convert 0.7230 at 650.128
cm^-1 (CINNAMALDEHYDE) to 72.3000, and every other point matched exactly.

Any x-axis clipping (e.g. a report-wide 4000-650 cm^-1 convention) beyond
this fixed 650 cm^-1 floor is still a report-time decision, not baked in
here, the same separation of concerns as spa_tool.py's archival-vs-plain
split.

NAMING: a .jdx's own ##TITLE is often an IUPAC-ish name (e.g.
"1-Propanone, 1-phenyl-" for what a report calls "propiophenone"), and
its filename is typically just a CAS number. Priority, highest first:
  1. --name (convert only) -- one-off override.
  2. --name-map FILE.json -- a report's own {"<CAS>": "<name>", ...}
     mapping (e.g. built from that report's own links.md); load once,
     reuse across every file in that report's batch.
  3. ##TITLE from the file itself.
  4. the file's own CAS registry number, if nothing else is available.
Never hardcode a report's compound names into this script -- that
defeats the point of it being a shared, cross-report tool. Keep any such
mapping as a small JSON file inside the report that needs it.

===============================================================================
6. QUICK REFERENCE
===============================================================================
    python3 jdx_tool.py convert sample.jdx --out sample.csv
    python3 jdx_tool.py convert sample.jdx --name "2-BUTANONE"
    python3 jdx_tool.py convert sample.jdx --out csv/X.csv --plain-out plain/X.csv
    python3 jdx_tool.py batch jdx/ --out-dir csv/ --name-map cas_names.json
    python3 jdx_tool.py batch jdx/ --out-dir csv/ --plain-dir plain/ --name-map cas_names.json
"""
import argparse
import json
import math
import os
import re
import sys

SIGN_SPLIT_RE = re.compile(r"(?<![eE])(?=[+-])")


def _tokens(line):
    """Whitespace tokens, further split where a +/- sign butts against the
    previous number (JCAMP lets a sign act as the delimiter: '23130-61334' is
    two values). A sign right after e/E is an exponent's, not a delimiter."""
    out = []
    for tok in line.split():
        out.extend(t for t in SIGN_SPLIT_RE.split(tok) if t)
    return out


NUM_RE = re.compile(r"^[+-]?\d+\.?\d*(?:[eE][+-]?\d+)?$")


def _to_float(tok):
    if not NUM_RE.match(tok):
        raise ValueError(
            f"data token {tok!r} is not a plain decimal number -- this file "
            f"may use JCAMP ASDF letter-compression (SQZ/DIF/DUP), which "
            f"this script does not decode (see module docstring sec. 2). "
            f"Do not guess; write and validate a real ASDF decoder first."
        )
    return float(tok)


def read_jdx(fn):
    """Return (x, y, meta) for one JCAMP-DX IR file. x is wavenumber
    (cm^-1), always descending. y is whatever ##YUNITS says (Absorbance or
    fractional Transmittance), untouched. meta has 'title', 'cas',
    'axis_label'. Validated against a real Spectragryph export -- see
    module docstring sec. 1. Raises loudly on anything this script hasn't
    seen and validated (compressed data, unrecognised XUNITS/YUNITS)."""
    with open(fn, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    header = {}
    data_start = None
    for i, line in enumerate(lines):
        line = line.rstrip("\r\n")
        if line.startswith("##XYDATA"):
            data_start = i + 1
            break
        m = re.match(r"^##([^=]+)=(.*)$", line)
        if m:
            header[m.group(1).strip().upper()] = m.group(2).strip()
    if data_start is None:
        raise ValueError(f"{fn}: no ##XYDATA= block found")

    xunits = header.get("XUNITS", "").upper()
    yunits = header.get("YUNITS", "").upper()
    if xunits not in ("1/CM", "CM-1", "MICROMETERS"):
        raise ValueError(
            f"{fn}: unrecognised XUNITS={xunits!r} -- add and validate "
            f"handling for it (module docstring sec. 3) before trusting "
            f"this script on this file."
        )
    if yunits.startswith("(MICROMOL/MOL)-1M-1"):
        yunits = "ABSORBANCE"  # QUANT-IR absorptivity, see docstring sec. 4
    if yunits not in ("ABSORBANCE", "TRANSMITTANCE"):
        raise ValueError(f"{fn}: unrecognised YUNITS={yunits!r}")

    xfactor = float(header.get("XFACTOR", "1.0"))
    yfactor = float(header.get("YFACTOR", "1.0"))
    deltax = float(header["DELTAX"])
    firstx = float(header["FIRSTX"])
    lastx = float(header["LASTX"])
    npoints = int(header["NPOINTS"])

    # SIGN FIX (2026-09-21, found decoding benzhydrol/benzophenone WebBook
    # files, both Coblentz Society/DOW-sourced): some producers write
    # DELTAX as a bare positive magnitude even when the data actually runs
    # FIRSTX -> LASTX descending (FIRSTX > LASTX) -- confirmed on
    # 119-61-9-IR.jdx (##DELTAX=1, ##FIRSTX=3800, ##LASTX=390, data lines
    # 3800.0, 3795.0, 3790.0, ... i.e. real per-line step is -5x|DELTAX|,
    # not +5x). Taking the header's sign literally there silently
    # mis-assigned each line's interior Y-values to ascending X's while
    # the true sequence descends, corrupting the X/Y pairing everywhere
    # except each line's own leading point (that point IS trusted as-is --
    # sec. above -- only the derived j*deltax offsets were wrong). The
    # 2-butanone file this module was first validated against (sec. 1) is
    # ascending (FIRSTX < LASTX) with a positive DELTAX, so this case
    # never showed up there. Fix: derive the SIGN of the real per-point
    # step from FIRSTX vs LASTX (which this script already sanity-checks
    # the parse against below), and take DELTAX's magnitude only from the
    # header -- never trust its literal sign alone.
    deltax = -abs(deltax) if firstx > lastx else abs(deltax)

    xs, ys = [], []
    running_x = None
    for line in lines[data_start:]:
        line = line.strip()
        if not line or line.startswith("##"):
            break
        toks = _tokens(line)
        x_line = _to_float(toks[0]) * xfactor
        if running_x is not None and abs(x_line - running_x) > 0.05:
            sys.stderr.write(
                f"warning: {fn}: line-leading X {x_line} does not match "
                f"running computed X {running_x:.4f} (checksum drift)\n"
            )
        for j, tok in enumerate(toks[1:]):
            xs.append(x_line + j * deltax)
            ys.append(_to_float(tok) * yfactor)
        running_x = x_line + len(toks[1:]) * deltax

    if len(xs) != npoints:
        sys.stderr.write(
            f"warning: {fn}: parsed {len(xs)} points, header NPOINTS={npoints}\n"
        )
    if abs(xs[0] - firstx) > 0.05 or abs(xs[-1] - lastx) > 0.05:
        sys.stderr.write(
            f"warning: {fn}: parsed X range [{xs[0]:.3f}, {xs[-1]:.3f}] vs "
            f"header FIRSTX/LASTX [{firstx}, {lastx}]\n"
        )

    if xunits == "MICROMETERS":
        xs = [10000.0 / x for x in xs]
        # ascending um -> descending cm^-1; reverse below handles final order

    # House convention: descending wavenumber (matches spa_tool.py archival
    # CSVs and the Spectragryph reference export).
    pairs = sorted(zip(xs, ys), key=lambda p: p[0], reverse=True)
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]

    cas = header.get("CAS REGISTRY NO", "")
    title = header.get("TITLE", "")
    axis_label = "Absorbance" if yunits == "ABSORBANCE" else "Transmittance"
    meta = {"title": title, "cas": cas, "axis_label": axis_label}
    return xs, ys, meta


def resolve_name(meta, name_map=None, override=None):
    """Priority order documented in module docstring sec. 5: explicit
    override, then a report-supplied CAS->name map, then the file's own
    ##TITLE, then its CAS number."""
    if override:
        return override
    if name_map and meta["cas"] in name_map:
        return name_map[meta["cas"]]
    return meta["title"] or meta["cas"] or "spectrum"


def write_csv(xs, ys, meta, out_path, name):
    """Spectragryph-style CSV: ';name;' / 'Wavenumbers [1/cm];axis;' header,
    then '{x:.3f};{y:.4f};' rows, decimal commas, full range (module
    docstring sec. 5)."""
    dec = y_decimals(ys)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f";{name};\r\n")
        f.write(f"Wavenumbers [1/cm];{meta['axis_label']};\r\n")
        for x, y in zip(xs, ys):
            f.write(f"{x:.3f};{y:.{dec}f};\r\n".replace(".", ","))
    return out_path


CLIP_CM = 650.0


def y_decimals(ys):
    """Decimals for the y column: the house 4, unless the whole spectrum is
    smaller than 0.01 (QUANT-IR absorptivity, max ~1e-3: 4 decimals would be
    ~12 distinct levels). Then 4 significant digits of the maximum."""
    peak = max(abs(y) for y in ys)
    if peak == 0 or peak >= 0.01:
        return 4
    return 3 - math.floor(math.log10(peak))


def write_plain_csv(xs, ys, meta, out_path, clip=CLIP_CM):
    """House 'plain' CSV: 'wavenumber,intensity' header, then '{x:.3f},
    {y:.4f}' rows, comma/decimal-point, ascending, clipped to >=clip cm^-1
    AT WRITE TIME (module docstring sec. 5). Fractional Transmittance is
    rescaled x100 here (and ONLY here -- write_csv()'s archival output is
    untouched) to match this lab's own OMNIC %T scale; Absorbance is never
    rescaled. Verified byte-for-byte against the one-off script this
    replaces -- see module docstring sec. 5 for the exact check."""
    scale = 100.0 if meta["axis_label"] == "Transmittance" else 1.0
    dec = y_decimals(ys) if scale == 1.0 else 4
    rows = sorted(zip(xs, ys), key=lambda p: p[0])
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("wavenumber,intensity\r\n")
        for x, y in rows:
            if x < clip:
                continue
            f.write(f"{x:.3f},{y * scale:.{dec}f}\r\n")
    return out_path


def load_name_map(path):
    if not path:
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def cmd_convert(args):
    xs, ys, meta = read_jdx(args.jdx)
    name_map = load_name_map(args.name_map)
    name = resolve_name(meta, name_map, args.name)
    out = args.out or os.path.join(os.path.dirname(args.jdx) or ".", f"{name}.csv")
    write_csv(xs, ys, meta, out, name)
    plain_msg = ""
    if args.plain_out:
        write_plain_csv(xs, ys, meta, args.plain_out)
        plain_msg = f" plain -> {args.plain_out}"
    print(f"{args.jdx}: cas={meta['cas']} name={name} axis={meta['axis_label']} "
          f"n={len(xs)} range=[{xs[-1]:.3f}, {xs[0]:.3f}] -> {out}{plain_msg}")


def cmd_batch(args):
    jdx_dir = args.jdx_dir
    files = sorted(f for f in os.listdir(jdx_dir) if f.lower().endswith(".jdx"))
    if not files:
        sys.exit(f"no .jdx files in {jdx_dir}")
    name_map = load_name_map(args.name_map)
    for fn in files:
        path = os.path.join(jdx_dir, fn)
        xs, ys, meta = read_jdx(path)
        name = resolve_name(meta, name_map)
        out = os.path.join(args.out_dir, f"{name}.csv")
        write_csv(xs, ys, meta, out, name)
        plain_msg = ""
        if args.plain_dir:
            plain_out = os.path.join(args.plain_dir, f"{name}.csv")
            write_plain_csv(xs, ys, meta, plain_out)
            plain_msg = f" plain -> {plain_out}"
        print(f"{fn}: cas={meta['cas']} name={name} axis={meta['axis_label']} "
              f"n={len(xs)} range=[{xs[-1]:.3f}, {xs[0]:.3f}] -> {out}{plain_msg}")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="command", required=True)

    p_conv = sub.add_parser("convert", help="one .jdx -> one CSV [+ plain CSV]")
    p_conv.add_argument("jdx")
    p_conv.add_argument("--out", default=None, help="output archival CSV path (default: alongside input, named per sec. 5)")
    p_conv.add_argument("--plain-out", default=None, help="also write the house 'plain' CSV (clipped >=650, %%-scale Transmittance) to this path")
    p_conv.add_argument("--name", default=None, help="override the compound name used in the CSV header/filename")
    p_conv.add_argument("--name-map", default=None, help="JSON file: {\"<CAS>\": \"<name>\", ...}")
    p_conv.set_defaults(func=cmd_convert)

    p_batch = sub.add_parser("batch", help="every .jdx in a directory -> CSVs [+ plain CSVs]")
    p_batch.add_argument("jdx_dir")
    p_batch.add_argument("--out-dir", required=True)
    p_batch.add_argument("--plain-dir", default=None, help="also write each compound's house 'plain' CSV into this directory")
    p_batch.add_argument("--name-map", default=None, help="JSON file: {\"<CAS>\": \"<name>\", ...}")
    p_batch.set_defaults(func=cmd_batch)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

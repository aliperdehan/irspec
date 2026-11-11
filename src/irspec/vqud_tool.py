"""irspec vqud -- Shimadzu UVProbe/LabSolutions UV-Vis quantitation files -> CSV / readable summary.

USAGE:
    irspec vqud <input.vqud> <output_prefix>      CSVs (the command line of parse_vqud.py)
    irspec vqud info <file.vqud|.vqut|.vqum>      read a file without writing anything

Moved here from nulabreport's tools/parse_vqud.py (2026-11-11); the CSVs are byte for byte what
that script wrote (with its \r\n line ends), with one change: a reading cell is "no reading"
when it is empty or only stars (see "Row IDs" below).

Files this handles (all are OLE2 / Compound File Binary containers, the family of old .doc/.xls):
    .vqud  quantitation DATA: standards + unknowns + the calibration curve
    .vqum  quantitation METHOD / parameters (wavelength, repeats, slit, formula, unit)
    .vqut  quantitation TEMPLATE: a .vqud with the table layout and planned standards but no readings

`<prefix>_...csv` written for whichever tables actually contain readings:
    <prefix>_standard_full.csv      one row per replicate + average (calibration curve)
    <prefix>_standard_summary.csv   one row per group (averages only) + a Block column
                                    separating distinct calibration-curve runs
    <prefix>_sample_full.csv        unknown-sample readings, replicates and average
    <prefix>_sample_summary.csv     one row per unknown-sample group (the average row)
    <prefix>_calibration.csv        K1, K0, r2 refitted from each block of standards, next to
                                    the fit the file itself stores (see 3)

--------------------------------------------------------------------------------------------
1. WHERE THE NUMBERS ARE  (rewritten 2026-11-05; the first version, 2026-09-10, zipped streams)
--------------------------------------------------------------------------------------------
Each table ("Standard Table", "Sample Table") is a folder with two stream families.

  <Table>/Column Configuration/<Column>        <-- THE DATA.  Read this.
      One keyed record per row: [8-byte marker \x01\x00\x00\x00\x03\x00\x00\x00]
      [1-byte len][RowID][1-byte len][value as printed, e.g. "0.162", "*****" for no reading,
      "" for blank] and, for a numeric column, 16 more bytes: two little-endian doubles (the
      full-precision value twice; +-1.797e308 when there is no value).  A genuine
      RowID -> value dictionary, order-independent, complete.  Text columns (Sample Name,
      Type) have no doubles.  The Column Configuration stream begins with the column's
      description and settings; the records follow.

  <Table>/Column Data/<Column>                 <-- a PARTIAL cache.  Do not zip these.
      [u16 column id][u16 0xFFFF][u16 count][value]... with `count` length-prefixed ASCII
      values.  The count is NOT the row count.  Seen in qca7.vqud (24 rows): RowID 24 entries,
      Conc (standards) 24, Result 6, sample WL510.0 6, standard WL510.0 **0**.  The first
      version of this script zipped RowID with the absorbance column by position; that was
      right for the CHEM341L file it was validated on and wrong for any file whose reading
      column is shorter than RowID (the standards' readings were simply missing).  Which rows
      the short streams belong to is not stored; do not guess it, use Column Configuration.
      Re-running the old CHEM341L file (188 standard rows, 24 sample rows) through the new
      reader: standard_summary.csv byte-identical; standard_full.csv differs in ONE cell, where
      the Column Data cache was stale (its 3-decimal string disagreed with the Column
      Configuration string and that string's double); the sample tables now show all 24 rows
      (3 replicates + Avg per group), where the old output showed 6 rows labelled "only reading
      stored": that label was an artefact of the short Column Data stream.

Row IDs: each measurement group is four rows sharing a number N: "N" (rep 1), "N-2" (rep 2),
"N-3" (rep 3), "N-Avg" (the average).  "*****" in a reading cell means no reading (the
unused rows at the bottom of a printed table, or the Result column on a replicate row); such
rows are skipped.  irspec takes any value made only of stars, and an empty one, as no reading:
the anonymised test file tests/data/quant_540nm_blocks.vqud has "******" (six) where a removed
reading had six characters, because a stream there keeps its size.  Any other value counts as a
reading, as it always did.  The method's "Repeat count" (3 in qca7) is how many replicates per group.

Reading column: the one named WL<nm> (e.g. WL540.0, WL510.0), preferring "WL<nm> Modified" when
a file has one (the older CHEM341L files do; its values are the same).  The wavelength in the
CSV header comes from that name.

Concentration: the Conc column of Column Configuration.  Standards: the nominal value typed
into the table (also what the Sample Name carries in older files); an excluded blank
(Type "BLK-*") has none.  Unknowns: back-calculated, stored on the N-Avg row only.

--------------------------------------------------------------------------------------------
2. ROUNDING  ("rounded: ON(3 digits)" in the method; `UseRoundedABS` in the file)
--------------------------------------------------------------------------------------------
With rounding ON the stored doubles ARE the rounded values (0.40800000000000003), and the
printed table shows them.  With it OFF (the 2026-09 CHEM341L files) the doubles keep 6+ digits
and the strings are their 3-decimal rendering.  CSVs carry the printed string,
as before; a string and its double can disagree only if the file was edited by hand.
Do not "explain" an average by re-rounding: three replicates printed 0.382, 0.381, 0.381 can
have an Avg row of 0.381 (mean 0.3813) and a Conc computed from 0.3813, not from a printed value;
nothing is inconsistent (checked on a real file).
The printed report hides the middle replicates (rows N-2, N-3); the file has them.

--------------------------------------------------------------------------------------------
3. THE CALIBRATION  (verified on qca7: 6 standards 0-10 mg/L, A(510 nm))
--------------------------------------------------------------------------------------------
The method's formula is  Concentration = K1 * Absorbance + K0  (concentration regressed on
absorbance), printed under the graph as "x = 5.16493 y + 0.0373612, r2 = 0.99838" (the
printed x is the concentration axis, y the absorbance axis).  The file stores K0 and K1 as two
doubles in `Calibration Curve/Properties` (offsets 14 and 22): 0.037361239293558945 and
5.164931927881811, which round to the printed digits.  r2 is NOT stored; it is recomputed
here from the standards (Avg rows with a concentration, stored double when there is one) and
agrees with the printed 0.99838.  Every one of the 24 printed rows of std.pdf/unk.pdf
(conc and absorbance) was compared with the CSVs: 0 differences.
A .vqut stores the same pair (a template keeps the last fit it was saved with); it is not a
calibration of anything.
CAVEAT: verified on qca7 only.  In the older CHEM341L file the stored pair (0.0625624,
-0.0054158) is NOT any refit of its last block (K1 18.4, K0 -0.26): the file may use the
other direction (absorbance on concentration), another range, or points the user excluded.
The tool says so ("DIFFERS") instead of passing the stored numbers off as the fit; which of
them a report should quote is for the printed report of that file to settle.
`Calibration Curve/Standard/Original Data` repeats the six x (conc) and y (absorbance) values
as doubles, plus six weights (1.0).

--------------------------------------------------------------------------------------------
4. .vqum  (method)
--------------------------------------------------------------------------------------------
`MesurementParameterTextStream` (sic, Shimadzu's spelling) is the readable half: a sequence of
1-byte-length-prefixed strings, a section title in brackets ("[Wavelength]") followed by a
zero byte and key/value pairs until two zero bytes.  The binary half
(`MeasurementParametersStream`) is not decoded.  A .vqud/.vqut embeds the same binary stream
under Method/ and names the .vqum it came from in `File Properties/ParameterFile`.

5. .vqut  (template): same container as a .vqud, with the Standard Table's planned Conc and
RowID columns and no readings.  `info` lists what it plans.

6. qca7.vqud vs qca7_data.vqud (2026-11-05): identical data; they differ in the file-history
log, in the ParameterFile path they name, and in a per-row state flag inside the RowID/Type
configuration streams.  The History (`File Properties/Data`) records "File Name Change" with
the original name, which is how to tell which file was saved from which.
"""
import csv
import struct
import sys

import olefile

MARKER = b'\x01\x00\x00\x00\x03\x00\x00\x00'
SENTINEL = 1.7976931348623157e+308
TABLES = ('Standard Table', 'Sample Table')


# ---------------------------------------------------------------- low-level readers

def read_stream(ole, path):
    try:
        return ole.openstream(path).read()
    except OSError:
        return None


def config_records(ole, table, column, numeric=False):
    """{RowID: (text, double|None)} from <table>/Column Configuration/<column>, in file order."""
    data = read_stream(ole, [table, 'Column Configuration', column])
    out = {}
    if not data:
        return out
    idx = 0
    while True:
        pos = data.find(MARKER, idx)
        if pos == -1:
            break
        p = pos + len(MARKER)
        l1 = data[p]; p += 1
        rowid = data[p:p + l1].decode('latin1'); p += l1
        l2 = data[p]; p += 1
        text = data[p:p + l2].decode('latin1'); p += l2
        num = None
        if numeric and p + 16 <= len(data):
            num = struct.unpack_from('<d', data, p)[0]
            if abs(num) >= SENTINEL:
                num = None
        out[rowid] = (text, num)
        idx = p
    return out


def column_names(ole, table):
    return sorted(s[-1] for s in ole.listdir(streams=True, storages=False)
                  if s[:2] == [table, 'Column Configuration'] and s[-1] != '#ColNodes#')


def reading_column(ole, table):
    """The WL<nm> column to use ('WL<nm> Modified' wins), or None."""
    names = column_names(ole, table)
    wl = [n for n in names if n.startswith('WL')]
    mod = [n for n in wl if n.endswith(' Modified')]
    return (mod or wl or [None])[0]


def wavelength_label(col):
    nm = col.split()[0][2:]
    try:
        return f'{float(nm):g}'
    except ValueError:
        return nm


def has_reading(text):
    """False for an empty cell and for one made only of stars (the instrument writes '*****')."""
    return text.strip('*') != ''


def group_and_rep(rowid):
    if rowid.endswith('-Avg'):
        return rowid[:-4], 'Avg'
    if '-' in rowid:
        base, suf = rowid.split('-', 1)
        return base, f'Rep {suf}'
    return rowid, 'Rep 1'


REP_ORDER = {'Rep 1': 0, 'Rep 2': 1, 'Rep 3': 2, 'Avg': 3}


def build_rows(ole, table):
    """Rows [group, rep, rowid, name, type, conc, absorbance, abs_double] that hold a reading."""
    col = reading_column(ole, table)
    if col is None:
        return [], None
    readings = config_records(ole, table, col, numeric=True)
    names = config_records(ole, table, 'Sample Name')
    types = config_records(ole, table, 'Type')
    concs = config_records(ole, table, 'Conc', numeric=True)
    rows = []
    for rid, (text, num) in readings.items():
        if not has_reading(text):
            continue
        group, rep = group_and_rep(rid)
        rows.append([int(group) if group.isdigit() else group, rep, rid,
                     names.get(rid, ('',))[0], types.get(rid, ('',))[0],
                     concs.get(rid, ('',))[0] if has_reading(concs.get(rid, ('',))[0]) else '',
                     text, num])
    rows.sort(key=lambda r: (r[0] if isinstance(r[0], int) else 9999, REP_ORDER.get(r[1], 9)))
    return rows, col


def add_blocks(avg_rows):
    """Tag each calibration-curve group with a Block number: a new block starts whenever
    concentration resets to 0/blank after a non-zero reading, which is how repeated standard
    curves (one per student group) show up back-to-back in a file the LA kept appending to.
    Rows: [group, name, type, conc, abs, abs_double] -> [block] + row."""
    out, block, prev_conc = [], 1, None
    for r in avg_rows:
        conc = r[3]
        conc_f = float(conc) if conc not in ('', None) else 0.0
        if prev_conc is not None and conc_f == 0.0 and prev_conc != 0.0:
            block += 1
        out.append([block] + r)
        prev_conc = conc_f
    return out


def fit(points):
    """Least squares  conc = K1 * A + K0  and r2, from [(A, conc)]. None when under 2 points."""
    n = len(points)
    if n < 2:
        return None
    sx = sum(a for a, _ in points); sy = sum(c for _, c in points)
    sxx = sum(a * a for a, _ in points); syy = sum(c * c for _, c in points)
    sxy = sum(a * c for a, c in points)
    den = n * sxx - sx * sx
    if den == 0:
        return None
    k1 = (n * sxy - sx * sy) / den
    k0 = (sy - k1 * sx) / n
    r2 = (n * sxy - sx * sy) ** 2 / (den * (n * syy - sy * sy)) if n * syy - sy * sy else float('nan')
    return k1, k0, r2


def fits_agree(refit, stored, rel=1e-4):
    """refit is [block, n, K1, K0, r2]; stored (K1, K0). Same pair to 4 significant digits."""
    return (abs(refit[2] - stored[0]) <= rel * max(1.0, abs(stored[0]))
            and abs(refit[3] - stored[1]) <= rel * max(1.0, abs(stored[1])))


def stored_fit(ole):
    b = read_stream(ole, ['Calibration Curve', 'Properties'])
    if b and len(b) >= 30:
        k0, k1 = struct.unpack_from('<2d', b, 14)
        return k1, k0
    return None


# ---------------------------------------------------------------- .vqum text stream

def vqum_text(ole):
    """[(section, [(key, value)])] from MesurementParameterTextStream."""
    b = read_stream(ole, 'MesurementParameterTextStream')
    if b is None:
        return None
    toks, i = [], 2                      # the first two bytes are not a string (a count)
    while i < len(b):
        n = b[i]; i += 1
        toks.append(None if n == 0 else b[i:i + n].decode('latin1'))
        i += n
    out, j = [], 0
    while j < len(toks):
        t = toks[j]
        if t and t.startswith('['):
            sec, j = [], j + 1
            if j < len(toks) and toks[j] is None:
                j += 1
            while j < len(toks) and toks[j] is not None:
                k = toks[j]
                v = toks[j + 1] if j + 1 < len(toks) and toks[j + 1] is not None else ''
                sec.append((k, v)); j += 2
            out.append((t, sec))
        else:
            j += 1
    return out


# ---------------------------------------------------------------- info

def lp_strings(b, minlen=4):
    out, i = [], 0
    while i < len(b) - 1:
        n = b[i]; s = b[i + 1:i + 1 + n]
        if n >= minlen and len(s) == n and all(32 <= c < 127 for c in s):
            # a printable byte (the last byte of a double: '@') read as a length would swallow the
            # first characters of the real string that follows: if the next byte is a longer valid
            # length, that one is the string
            m = b[i + 1]; t = b[i + 2:i + 2 + m]
            if m >= minlen and len(t) == m and all(32 <= c < 127 for c in t) and i + 2 + m >= i + 1 + n:
                i += 1
                continue
            out.append(s.decode('ascii')); i += 1 + n
        else:
            i += 1
    return out


def info(path):
    ole = olefile.OleFileIO(path)
    print(f'file: {path.rsplit("/", 1)[-1]}')
    txt = vqum_text(ole)
    if txt is not None:
        for sec, kv in txt:
            print(sec)
            for k, v in kv:
                print(f'  {k}: {v}')
        return
    pf = read_stream(ole, ['File Properties', 'ParameterFile'])
    if pf:
        print('parameter file:', pf[1:1 + pf[0]].decode('latin1'))
    hist = read_stream(ole, ['File Properties', 'Data']) or b''
    for s in lp_strings(hist, minlen=8):
        print('  history:', s)
    sf = stored_fit(ole)
    if sf:
        print(f'stored calibration: concentration = {sf[0]:.6g} * A + {sf[1]:.6g}')
    for table in TABLES:
        rows, col = build_rows(ole, table)
        print(f'{table}: reading column {col}, {len(rows)} rows with a reading')
        if not rows:
            planned = config_records(ole, table, 'Conc')
            if planned:
                vals = [t for t, _ in planned.values() if has_reading(t)]
                print(f'  planned Conc column ({len(vals)} entries): {", ".join(vals[:24])}')
            continue
        for r in rows:
            if r[1] == 'Avg':
                print(f'  {r[2]:>7}  {r[3]:<18} {r[4]:<8} conc {r[5]:>7}  A {r[6]}')


# ---------------------------------------------------------------- CSV output

def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) == 2 and argv[0] == 'info':
        info(argv[1]); return
    if len(argv) != 2:
        print(__doc__); sys.exit(1)
    path, prefix = argv
    ole = olefile.OleFileIO(path)

    std_rows, std_col = build_rows(ole, 'Standard Table')
    if std_rows:
        h = f'Absorbance ({wavelength_label(std_col)}nm)'
        header = ['Group', 'Replicate', 'RowID', 'Sample Name', 'Type', 'Conc (mg/L)', h]
        with open(f'{prefix}_standard_full.csv', 'w', newline='') as f:
            w = csv.writer(f); w.writerow(header); w.writerows([r[:7] for r in std_rows])
        std_avg = [r for r in std_rows if r[1] == 'Avg']
        blocked = add_blocks([[r[0], r[3], r[4], r[5], r[6], r[7]] for r in std_avg])
        with open(f'{prefix}_standard_summary.csv', 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['Block', 'Group', 'Sample Name', 'Type', 'Conc (mg/L)', h])
            w.writerows([b[:6] for b in blocked])
        n_blocks = blocked[-1][0] if blocked else 0
        print(f'Standard Table: {len(std_rows)} rows, {len(std_avg)} groups, {n_blocks} calibration-curve blocks')

        stored = stored_fit(ole)
        cal = []
        for blk in range(1, n_blocks + 1):
            pts = [(b[6] if b[6] is not None else float(b[5]), float(b[4]))
                   for b in blocked if b[0] == blk and b[4] != '']
            res = fit(pts)
            if res:
                cal.append([blk, len(pts), *res])
        if cal:
            with open(f'{prefix}_calibration.csv', 'w', newline='') as f:
                w = csv.writer(f)
                w.writerow(['Block', 'Points', 'K1 (mg/L per Abs)', 'K0 (mg/L)', 'r2',
                            'File K1', 'File K0', 'File fit agrees'])
                for c in cal:
                    last_blk = stored and c[0] == n_blocks
                    w.writerow([c[0], c[1], f'{c[2]:.6g}', f'{c[3]:.6g}', f'{c[4]:.5f}',
                                f'{stored[0]:.6g}' if last_blk else '',
                                f'{stored[1]:.6g}' if last_blk else '',
                                ('yes' if fits_agree(c, stored) else 'NO') if last_blk else ''])
            last = cal[-1]
            note = ''
            if stored:
                note = (f'   [file stores K1 {stored[0]:.6g}, K0 {stored[1]:.6g}: '
                        f'{"agrees" if fits_agree(last, stored) else "DIFFERS from this refit"}]')
            print(f'Calibration (last block, {last[1]} points): conc = {last[2]:.6g} * A + {last[3]:.6g}, '
                  f'r2 = {last[4]:.5f}{note}')

    smp_rows, smp_col = build_rows(ole, 'Sample Table')
    if smp_rows:
        h = f'Absorbance ({wavelength_label(smp_col)}nm)'
        header = ['Group', 'Replicate', 'RowID', 'Sample Name', 'Type', 'Conc (mg/L)', h]
        with open(f'{prefix}_sample_full.csv', 'w', newline='') as f:
            w = csv.writer(f); w.writerow(header); w.writerows([r[:7] for r in smp_rows])
        with open(f'{prefix}_sample_summary.csv', 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['Group', 'Sample Name', 'Type', 'Conc (mg/L)', h])
            w.writerows([[r[0], r[3], r[4], r[5], r[6]] for r in smp_rows if r[1] == 'Avg'])
        print(f'Sample Table: {len(smp_rows)} rows, {sum(1 for r in smp_rows if r[1] == "Avg")} groups')
    if not std_rows and not smp_rows:
        print('no readings in this file (a template, or an empty one): nothing written. Try: info')


if __name__ == '__main__':
    main()

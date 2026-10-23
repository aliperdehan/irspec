#!/usr/bin/env python3
"""ir_organize.py -- tidy an IR session folder and build its peer-share PDF.

One command takes a raw instrument dump (OMNIC .SPA/.SPG, JCAMP-DX .jdx,
plus whatever else came off the machine: .TIF screenshots, Spectragryph
.CSV exports, ...) and leaves it in the house layout used by
LR4-5/ir/own-15.09/:

    FOLDER/
      SPA/            every .SPA/.SPG, moved here
      jdx/            every .jdx, moved here (only created if there are any)
      other/          every other loose file, moved here (only if any)
      csv/            archival CSVs   {stem}.csv          (semicolon, decimal comma)
      plain/          plain CSVs      {stem}_plain.csv    (clipped >=650 cm-1)
      manifest.json   per-spectrum title/order/overrides (edit, then re-run)
      ir_<dd-mm>.md   nulabreport peer-share markdown (landscape, 1 per page)
      ir_<dd-mm>.pdf  built by pdfmd.py

It reuses, never re-implements, the validated readers/writers:
spa_tool.py (.SPA parse, CSV pair, peak picking, ymin) and jdx_tool.py /
spa_peaks.py (.jdx parse, Absorbance-aware peak picking).

USAGE
    python3 ir_organize.py                    # current directory
    python3 ir_organize.py ~/Downloads/LR6/ir/own-29.09
    python3 ir_organize.py DIR --dry-run      # show what would move, change nothing
    python3 ir_organize.py DIR --no-pdf       # stop after the .md
    python3 ir_organize.py DIR --title etoac="Ethyl acetate" --title ktoto="Ketone"
    python3 ir_organize.py DIR --sort name    # default: acquisition time (mtime)
    python3 ir_organize.py DIR --md-name session   # -> session.md / session.pdf

RE-RUNNING IS SAFE (idempotent). Files already in SPA/jdx/other stay put;
new loose files are filed and *appended* to the existing manifest.json. To
rename, reorder or drop a spectrum, or to force manual peaks, edit
manifest.json and re-run: titles, order and per-entry overrides are kept.

PEAKS LIVE IN THE MANIFEST. The first run auto-picks peaks and writes them
back as "peaks": [[wavenumber, label_y], ...] -- the exact numbers that go
into \\irspectrum, so edit/add/delete them there and re-run (the .md is
regenerated, never hand-edited). An item may also be a bare wavenumber
(e.g. 1715): it is snapped to the nearest local band and gets an automatic
label_y. Delete the "peaks" key to re-run the auto picker for that entry.
Manifest entries are {"file": "SPA/x.SPA", "title": "...", and optionally
"peaks", "threshold", "prominence", "distance", "ymin", "axis"}. ("spa"/"jdx" keys, as in the old exemplar
manifest, are accepted in place of "file".) A spectrum whose file no longer
exists is dropped from the manifest.

NOT TOUCHED: existing csv/, plain/, *.md, *.pdf, manifest.json, hidden
files. Nothing is ever overwritten when filing: a name clash is reported
and the file is left where it is.

The PDF is built with pdfmd.py (never bare pandoc -- see nulabreport's
CLAUDE.md). Found as --pdfmd, else $PDFMD, else `pdfmd` on the PATH (pip install pdfmd-cli).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys


import numpy as np  # noqa: E402

from . import jdx_tool  # noqa: E402
from . import spa_peaks  # noqa: E402
from . import spa_tool  # noqa: E402

SPA_EXT = (".spa", ".spg")
JDX_EXT = (".jdx", ".dx", ".jcm")
# Directories/files this tool owns or generates; never filed into other/.
OWN_DIRS = {"SPA", "jdx", "other", "csv", "plain"}
GENERATED_EXT = (".md", ".pdf")


# -----------------------------------------------------------------------------
# 1. Filing
# -----------------------------------------------------------------------------
def classify(name):
    ext = os.path.splitext(name)[1].lower()
    if ext in SPA_EXT:
        return "SPA"
    if ext in JDX_EXT:
        return "jdx"
    return "other"


def organize(folder, dry_run=False):
    """Move loose files in `folder` into SPA/ jdx/ other/. Returns a list of
    (src, dst) moves performed (or planned, if dry_run)."""
    moves = []
    for name in sorted(os.listdir(folder)):
        src = os.path.join(folder, name)
        if (not os.path.isfile(src) or name.startswith(".")
                or name == "manifest.json"
                or name.lower().endswith(GENERATED_EXT)):
            continue
        dest_dir = os.path.join(folder, classify(name))
        dst = os.path.join(dest_dir, name)
        if os.path.exists(dst):
            print(f"warning: {dst} already exists; leaving {name} in place",
                  file=sys.stderr)
            continue
        moves.append((src, dst))
        if not dry_run:
            os.makedirs(dest_dir, exist_ok=True)
            shutil.move(src, dst)
    return moves


# -----------------------------------------------------------------------------
# 2. Manifest
# -----------------------------------------------------------------------------
def spectra_on_disk(folder):
    """Relative paths of every spectrum file under SPA/ and jdx/."""
    out = []
    for sub, exts in (("SPA", SPA_EXT), ("jdx", JDX_EXT)):
        d = os.path.join(folder, sub)
        if os.path.isdir(d):
            out += [f"{sub}/{n}" for n in os.listdir(d)
                    if n.lower().endswith(exts) and not n.startswith(".")]
    return out


def entry_file(e):
    return e.get("file") or e.get("spa") or e.get("jdx")


def build_manifest(folder, titles, sort):
    """Merge on-disk spectra with any existing manifest.json: existing
    entries keep their order/titles/overrides, new files are appended in
    `sort` order, vanished files are dropped. Returns the entry list."""
    mpath = os.path.join(folder, "manifest.json")
    old = []
    if os.path.exists(mpath):
        with open(mpath, encoding="utf-8") as f:
            old = json.load(f)

    # A manifest copied from another machine has absolute paths; match on
    # the SPA/name tail so it still works here.
    def rel(p):
        p = p.replace("\\", "/")
        m = re.search(r"(?:^|/)((?:SPA|jdx)/[^/]+)$", p)
        return m.group(1) if m else p

    disk = set(spectra_on_disk(folder))
    entries, seen = [], set()
    for e in old:
        r = rel(entry_file(e) or "")
        if r in disk and r not in seen:
            e = {k: v for k, v in e.items() if k not in ("spa", "jdx")}
            e["file"] = r
            entries.append(e)
            seen.add(r)

    new = sorted(disk - seen)
    if sort == "time":
        new.sort(key=lambda r: (os.path.getmtime(os.path.join(folder, r)), r))
    for r in new:
        stem = spa_tool.clean_stem(r)
        entries.append({"file": r, "title": titles.get(stem, stem)})

    for e in entries:  # --title also retitles existing entries
        stem = spa_tool.clean_stem(entry_file(e))
        if stem in titles:
            e["title"] = titles[stem]
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return entries


# -----------------------------------------------------------------------------
# 3. Per-spectrum processing (CSV pair + peaks)
# -----------------------------------------------------------------------------
def resolve_peaks(x, y, e, axis, absorbance, auto_kwargs, gap):
    """Peaks for one spectrum as [(x, y, label_y)]. Manifest "peaks" wins:
    [x, label_y] pairs are used verbatim, bare numbers are snapped to the
    nearest local band; an empty list means none; no "peaks" key means auto-pick.
    Also (re)writes e["peaks"]."""
    spec = e.get("peaks")
    if isinstance(spec, str):  # legacy comma string
        spec = [float(v) for v in spec.split(",") if v.strip()]
    if spec or isinstance(spec, list):  # [] is "no peaks" (irspec edit peak clear), not "pick"
        sign = 1.0 if absorbance else -1.0
        bare = [float(v) for v in spec if not isinstance(v, (list, tuple))]
        snapped = {}
        for b in bare:  # one at a time so a skipped (no-data) value can't misalign
            hit = spa_tool.find_peaks_manual(x, y, [b], axis)
            if hit:
                snapped[b] = hit[0]
        out = []
        for v in spec:
            if isinstance(v, (list, tuple)):
                px, ly = float(v[0]), float(v[1])
                out.append((px, float(np.interp(px, x[::-1] if x[0] > x[-1] else x,
                                                y[::-1] if x[0] > x[-1] else y)), ly))
            elif float(v) in snapped:
                px, py = snapped[float(v)]
                out.append((px, py, py + sign * gap))
        peaks_xyl = sorted(out)
    else:
        peaks = spa_peaks.find_peaks_auto(x, y, absorbance=absorbance, **auto_kwargs)
        peaks_xyl = spa_peaks.assign_label_y(peaks, gap=gap, step=gap, absorbance=absorbance)
    e["peaks"] = [[round(px, 1), round(ly, 1)] for px, _, ly in peaks_xyl]
    return peaks_xyl


def _finish(e, stem, x, y, axis, absorbance, archival, plain):
    mask = x >= spa_tool.CLIP_CM
    rng = float(y[mask].max() - y[mask].min()) or 1.0
    gap = 0.05 * rng if absorbance else 5.0
    auto = dict(
        threshold_pct=e.get("threshold", 5.0),
        prominence=e.get("prominence", 0.03 * rng if absorbance else 3.0),
        distance_cm=e.get("distance", 8.0))
    peaks_xyl = resolve_peaks(x, y, e, axis, absorbance, auto, gap)
    ymin = e.get("ymin")
    if ymin is None and not absorbance:
        ymin = spa_tool.suggest_bounds(x, y, peaks_xyl).get("ymin", 0)
    return {
        "title": e.get("title") or stem, "stem": stem, "axis_label": axis,
        "axis_md": axis, "peaklist": spa_peaks.format_peaklist(peaks_xyl),
        "ymin": ymin, "n_peaks": len(peaks_xyl),
        "archival_path": archival, "plain_path": plain,
    }


def process_spa(path, e, csv_dir, plain_dir):
    stem = spa_tool.clean_stem(path)
    x, y = spa_tool.read_spa(path)
    axis = e.get("axis") or spa_tool.axis_of(y, x >= spa_tool.CLIP_CM)
    archival = spa_tool.write_archival_csv(x, y, os.path.join(csv_dir, stem), axis)
    plain = spa_tool.write_plain_csv(x, y, os.path.join(plain_dir, stem))
    return _finish(e, stem, x, y, axis, axis.startswith("Absorbance"), archival, plain)


def process_jdx(path, e, csv_dir, plain_dir):
    xs, ys, meta = jdx_tool.read_jdx(path)
    stem = spa_tool.clean_stem(path)
    archival = jdx_tool.write_csv(xs, ys, meta, os.path.join(csv_dir, f"{stem}.csv"), stem)
    # jdx_tool rescales fractional Transmittance x100 in the plain CSV only.
    plain = jdx_tool.write_plain_csv(xs, ys, meta, os.path.join(plain_dir, f"{stem}_plain.csv"))
    x, y = np.array(xs), np.array(ys)
    absorbance = meta["axis_label"] != "Transmittance"
    if not absorbance:
        y = y * 100.0
    axis = e.get("axis") or ("Absorbance" if absorbance else "Transmittance %")
    return _finish(e, stem, x, y, axis, absorbance, archival, plain)


def save_manifest(folder, entries):
    """One key per line; each peak pair on its own line so hand edits diff well."""
    out = []
    for e in entries:
        lines = []
        for k, v in e.items():
            if k == "peaks":
                body = ",\n".join(f"      {json.dumps(p)}" for p in v)
                lines.append(f'    "peaks": [\n{body}\n    ]' if v else '    "peaks": []')
            else:
                lines.append(f"    {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}")
        out.append("  {\n" + ",\n".join(lines) + "\n  }")
    with open(os.path.join(folder, "manifest.json"), "w", encoding="utf-8") as f:
        f.write("[\n" + ",\n".join(out) + "\n]\n")


# -----------------------------------------------------------------------------
# 4. Markdown
# -----------------------------------------------------------------------------
def render_md(results, folder):
    esc = spa_tool.latex_escape
    body = ["\\begin{landscape}"]
    for i, r in enumerate(results):
        opts = "width=\\linewidth,height=6.8in"
        if r["ymin"] is not None:
            opts += f",ymin={r['ymin']}"
        body.append(
            "\\irspectrum\n"
            f"  [{opts}]\n"
            f"  {{{os.path.relpath(r['plain_path'], folder)}}}\n"
            f"  {{{esc(r['axis_md'])}}}\n"
            f"  {{{r['peaklist']}}}\n"
            f"  {{{esc(r['title'])}}}\n"
            "\\clearpage\n")
    body.append("\\end{landscape}")
    return spa_tool.MD_FRONTMATTER + "\n" + "\n".join(body) + "\n"


def default_md_name(folder):
    base = os.path.basename(os.path.abspath(folder))
    m = re.search(r"(\d{1,2})[.\-](\d{2})", base)
    return f"ir_{int(m.group(1)):02d}-{m.group(2)}" if m else f"ir_{base}"


# -----------------------------------------------------------------------------
# 5. PDF
# -----------------------------------------------------------------------------
def find_pdfmd(explicit=None):
    """The pdfmd to build with: --pdfmd, else $PDFMD, else `pdfmd` on the PATH. None if absent."""
    for cand in (explicit, os.environ.get("PDFMD"), shutil.which("pdfmd")):
        if cand and os.path.exists(cand):
            return cand
    return None


def build_pdf(md_path, pdfmd):
    pdfmd = find_pdfmd(pdfmd)
    if not pdfmd:
        sys.exit("pdfmd not found (pip install pdfmd-cli, or use --pdfmd or $PDFMD)")
    folder = os.path.dirname(os.path.abspath(md_path))
    # cwd = folder so the md's relative plain/... paths resolve. A pdfmd.py is run by this
    # interpreter; an installed `pdfmd` command runs as it is.
    cmd = [sys.executable, pdfmd] if pdfmd.endswith(".py") else [pdfmd]
    subprocess.run([*cmd, os.path.basename(md_path)], cwd=folder, check=True)
    pdf = os.path.splitext(md_path)[0] + ".pdf"
    if not os.path.exists(pdf):
        sys.exit(f"pdfmd ran but {pdf} was not produced")
    return pdf


# -----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", nargs="?", default=".")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the planned file moves and exit")
    ap.add_argument("--no-pdf", action="store_true", help="write the .md but skip pdfmd")
    ap.add_argument("--sort", choices=["time", "name"], default="time",
                    help="order for NEW spectra: acquisition time (default) or name")
    ap.add_argument("--title", action="append", default=[], metavar="STEM=TITLE",
                    help="set a spectrum's title (repeatable)")
    ap.add_argument("--md-name", default=None,
                    help="output basename (default: ir_<dd-mm> from the folder name)")
    ap.add_argument("--pdfmd", default=None, help="path to pdfmd (default: $PDFMD, else `pdfmd` on the PATH)")
    args = ap.parse_args()

    folder = os.path.abspath(args.folder)
    if not os.path.isdir(folder):
        sys.exit(f"not a directory: {folder}")
    titles = {}
    for t in args.title:
        if "=" not in t:
            sys.exit(f"--title needs STEM=TITLE, got {t!r}")
        k, v = t.split("=", 1)
        titles[k] = v

    moves = organize(folder, args.dry_run)
    verb = "would move" if args.dry_run else "moved"
    for src, dst in moves:
        print(f"{verb}: {os.path.relpath(src, folder)} -> {os.path.relpath(dst, folder)}")
    if args.dry_run:
        return
    if not moves:
        print("nothing to file")

    entries = build_manifest(folder, titles, args.sort)
    if not entries:
        sys.exit("no .SPA/.SPG/.jdx spectra found")

    csv_dir = os.path.join(folder, "csv")
    plain_dir = os.path.join(folder, "plain")
    os.makedirs(csv_dir, exist_ok=True)
    os.makedirs(plain_dir, exist_ok=True)
    results = []
    for e in entries:
        path = os.path.join(folder, e["file"])
        proc = process_spa if path.lower().endswith(SPA_EXT) else process_jdx
        r = proc(path, e, csv_dir, plain_dir)
        results.append(r)
        print(f"# {r['stem']}: axis={r['axis_label']} peaks={r['n_peaks']} "
              f"ymin={r['ymin']}")

    save_manifest(folder, entries)  # now carries the picked peaks
    md_path = os.path.join(folder, (args.md_name or default_md_name(folder)) + ".md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_md(results, folder))
    print(f"wrote {md_path} ({len(results)} spectra)")

    if not args.no_pdf:
        print(f"wrote {build_pdf(md_path, args.pdfmd)}")


if __name__ == "__main__":
    main()

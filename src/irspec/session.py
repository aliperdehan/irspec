"""irspec session -- one command for a folder of spectra, whatever their source.

    irspec session DIR [--build auto|pdfmd|latex|none] [--sort time|name]
                       [--title STEM=TITLE ...] [--md-name NAME] [--dry-run]
                       [--preview [--width N] [--height N] [--ascii] [--json]]
                       [--formats png,tiff,svg,svg-text] [--dpi 300]

It does for NIST WebBook files and SDBS pictures what ir_organize.py already
did for the instrument's own .SPA files, in the same folder layout:

    DIR/
      SPA/   *.SPA          the instrument's own spectra
      jdx/   *.jdx          JCAMP-DX reference spectra (NIST WebBook, QUANT-IR)
      img/   *.gif|jpg|...  spectra published only as a picture (SDBS)
      csv/   archival CSVs        plain/  the CSVs the figures read (always %T)
      check/ digitiser logs and overlays          manifest.json
      ir_<dd-mm>.md / .tex / .pdf

Loose .SPA/.jdx/other files in DIR are filed first (images are NOT: put them in
img/ yourself, an OMNIC screenshot and an SDBS plot are both "an image").

Naming. An own .SPA spectrum keeps its file's stem: csv/STEM.csv and
plain/STEM_plain.csv. A reference spectrum (jdx/ or img/) gets a name,
csv/NAME.csv and plain/NAME.csv, taken from the manifest entry's "name", else
from DIR/cas_names.json ({"67-56-1": "METHANOL_GAS"}, looked up by the CAS number
a WebBook/SDBS file name starts with), else from the file's stem. Names are
caps with underscores, no spaces.

The manifest is the one place anything is configured. Per-entry keys beyond
the ones ir_organize knows (file, title, peaks, axis, ymin, threshold,
prominence, distance):

    name     the compound name above (written back by the first run)
    peak_a   QUANT-IR gas files only: scale the strongest band to this
             absorbance (the file states neither concentration nor path
             length; say so in the caption). Or "cl": c x L, if known.
    check    images only: the peak table printed under the plot, typed as
             "3490:84,2977:6,...", for ir_digitize's own cross-check
    args     images only: more ir_digitize flags, as a list

What it does to a reference spectrum is exactly what the WebBook/SDBS HOWTO
recipes did by hand, so the CSVs are byte-identical to the ones made that way
(tests/test_session.py, against the LR6 folders):
  .jdx Transmittance   jdx_tool convert
  .jdx Absorbance      jdx_tool convert, then absorbance_to_transmittance
  .jdx QUANT-IR        absorptivity_to_absorbance (needs peak_a or cl), then
                       absorbance_to_transmittance
  image                ir_digitize convert (a failed calibration or redraw
                       check stops the session and names the log)
Every figure is %Transmittance. Peaks are picked (or taken from the manifest,
where you can edit them) and the figure list is written as a Markdown file for
nulabreport's pdfmd and, with --build latex, as a plain .tex built by lualatex
(see texout.py for how that finds the real nulabreport.sty or falls back to the
bundled excerpt).
"""
import argparse
import contextlib
import importlib
import io
import json
import os
import re
import shutil
import subprocess
import sys

import numpy as np

from . import ir_organize as _io
from . import export, jdx_tool, spa_tool, texout
from .figure import FIGURES_NAME, Figure, write_figures

IMG_EXT = (".gif", ".jpg", ".jpeg", ".png", ".bmp")
CAS_RE = re.compile(r"^(\d{2,7}-\d\d-\d)")
KIND_DIRS = (("SPA", _io.SPA_EXT), ("jdx", _io.JDX_EXT), ("img", IMG_EXT))
TRANSMITTANCE = "Transmittance %"


class SessionError(SystemExit):
    """A message for the user, not a traceback."""


def call(module, argv):
    """Run one irspec tool's main() in-process; return (exit code, stdout, stderr)."""
    mod = importlib.import_module(f"irspec.{module}")
    old = sys.argv
    sys.argv = [f"{module}.py", *[str(a) for a in argv]]
    out, err = io.StringIO(), io.StringIO()
    code = 0
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            mod.main()
    except SystemExit as e:
        if isinstance(e.code, int):
            code = e.code
        elif e.code is not None:
            code = 1
            err.write(str(e.code) + "\n")
    finally:
        sys.argv = old
    return code, out.getvalue(), err.getvalue()


def must(module, argv, what):
    code, out, err = call(module, argv)
    if code:
        raise SessionError(f"{what} failed ({module}, exit {code}):\n{(err or out).strip()}")
    return out, err


# -----------------------------------------------------------------------------
# Filing: ir_organize's, minus the files that configure the session
# -----------------------------------------------------------------------------
KEEP_IN_PLACE = {"manifest.json", "cas_names.json", FIGURES_NAME}


def organize(folder, dry_run=False):
    """ir_organize.organize, except manifest.json, cas_names.json and figures.json stay put
    (the original would file the name map into other/ before it is read, and the figure
    list this command wrote on its last run into other/ on the next)."""
    moves = []
    for name in sorted(os.listdir(folder)):
        src = os.path.join(folder, name)
        if (not os.path.isfile(src) or name.startswith(".") or name in KEEP_IN_PLACE
                or name.lower().endswith(_io.GENERATED_EXT)):
            continue
        dst = os.path.join(folder, _io.classify(name), name)
        if os.path.exists(dst):
            print(f"warning: {dst} already exists; leaving {name} in place", file=sys.stderr)
            continue
        moves.append((src, dst))
        if not dry_run:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
    return moves


# -----------------------------------------------------------------------------
# Manifest: ir_organize's, plus img/
# -----------------------------------------------------------------------------
def spectra_on_disk(folder):
    out = []
    for sub, exts in KIND_DIRS:
        d = os.path.join(folder, sub)
        if os.path.isdir(d):
            out += [f"{sub}/{n}" for n in os.listdir(d)
                    if n.lower().endswith(exts) and not n.startswith(".")]
    return out


def default_title(folder, rel, entry=None, path=None):
    """The title a NEW entry starts with (edit it in manifest.json): an own .SPA spectrum has
    its file stem; a reference spectrum has its compound name from cas_names.json
    ("METHYL_CINNAMATE_GAS" -> "Methyl cinnamate gas"), else the title inside the .jdx
    (WebBook's "METHANOL" -> "Methanol"), else the stem. `path` is where the file is now when
    it is not yet at folder/rel (--preview, before filing)."""
    stem = spa_tool.clean_stem(rel)
    if rel.startswith("SPA/"):
        return stem
    name = reference_name(folder, {**(entry or {}), "file": rel})
    if name != stem:
        return name.replace("_", " ").capitalize()
    if rel.lower().endswith(_io.JDX_EXT):
        try:
            title = (jdx_tool.read_jdx(path or os.path.join(folder, rel))[2].get("title")
                     or "").strip()
        except Exception:  # an unreadable file is reported when it is processed, not here
            title = ""
        if title:
            return title.capitalize() if title.isupper() else title
    return stem


def build_manifest(folder, titles, sort, planned=None):
    """ir_organize.build_manifest with img/ added: existing entries keep their
    order, titles and overrides, new files are appended, vanished ones dropped.
    `planned` ({"SPA/x.SPA": current path}) lists files that are not filed yet but will be
    (--preview): they count as on disk, and are read from where they are."""
    planned = planned or {}
    mpath = os.path.join(folder, "manifest.json")
    old = []
    if os.path.exists(mpath):
        with open(mpath, encoding="utf-8") as f:
            old = json.load(f)

    def rel(p):
        p = p.replace("\\", "/")
        m = re.search(r"(?:^|/)((?:SPA|jdx|img)/[^/]+)$", p)
        return m.group(1) if m else p

    disk = set(spectra_on_disk(folder)) | set(planned)
    entries, seen = [], set()
    for e in old:
        r = rel(_io.entry_file(e) or "")
        if r in disk and r not in seen:
            e = {k: v for k, v in e.items() if k not in ("spa", "jdx")}
            e["file"] = r
            if not e.get("title"):  # a hand-written entry (just "file" and "name") gets one too
                e["title"] = default_title(folder, r, e, planned.get(r))
            entries.append(e)
            seen.add(r)
    new = sorted(disk - seen)
    if sort == "time":
        new.sort(key=lambda r: (os.path.getmtime(planned.get(r) or os.path.join(folder, r)), r))
    for r in new:
        stem = spa_tool.clean_stem(r)
        entries.append({"file": r, "title": titles.get(stem)
                        or default_title(folder, r, path=planned.get(r))})
    for e in entries:
        stem = spa_tool.clean_stem(_io.entry_file(e))
        if stem in titles:
            e["title"] = titles[stem]
    return entries


def reference_name(folder, e):
    """The NAME of a jdx/img spectrum: manifest, else cas_names.json, else stem."""
    if e.get("name"):
        return e["name"]
    stem = spa_tool.clean_stem(e["file"])
    cas = CAS_RE.match(stem)
    mp = os.path.join(folder, "cas_names.json")
    if cas and os.path.exists(mp):
        with open(mp, encoding="utf-8") as f:
            names = json.load(f)
        if cas.group(1) in names:
            return names[cas.group(1)]
    return stem


# -----------------------------------------------------------------------------
# Processing, one source kind at a time
# -----------------------------------------------------------------------------
def read_plain(path):
    a = np.genfromtxt(path, delimiter=",", skip_header=1)
    return a[:, 0], a[:, 1]


def _jdx_kind(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        head = f.read(20000).upper()
    m = re.search(r"##YUNITS=\s*(\S+)", head)
    if m and m.group(1).startswith("(MICROMOL/MOL)-1M-1"):
        return "quantir"
    _, _, meta = jdx_tool.read_jdx(path)
    return "absorbance" if meta["axis_label"] == "Absorbance" else "transmittance"


def process_jdx_reference(folder, e, csv_dir, plain_dir):
    path = os.path.join(folder, e["file"])
    name = reference_name(folder, e)
    e["name"] = name
    csv, plain = (os.path.join(csv_dir, f"{name}.csv"), os.path.join(plain_dir, f"{name}.csv"))
    kind = _jdx_kind(path)
    if kind == "quantir":
        if "peak_a" in e:
            scale = ["--peak-a", e["peak_a"]]
        elif "cl" in e:
            scale = ["--cl", e["cl"]]
        else:
            raise SessionError(
                f"{e['file']} is a NIST QUANT-IR gas file (absorptivity, not an absorbance): "
                f"its c x L is not in the file. Put \"peak_a\": 1 in its manifest entry to scale "
                f"the strongest band to A = 1 (and say so in the caption), or \"cl\": <c x L>.")
        must("absorptivity_to_absorbance",
             [path, "--name", name, "--out", csv, "--plain-out", plain, *scale], e["file"])
    else:
        must("jdx_tool", ["convert", path, "--name", name, "--out", csv, "--plain-out", plain],
             e["file"])
    if kind in ("absorbance", "quantir"):
        must("absorbance_to_transmittance", [plain, "--out", plain], f"{e['file']} (A to %T)")
    x, y = read_plain(plain)
    return _io._finish(e, name, x, y, TRANSMITTANCE, False, csv, plain)


def process_image(folder, e, csv_dir, plain_dir):
    path = os.path.join(folder, e["file"])
    name = reference_name(folder, e)
    e["name"] = name
    check_dir = os.path.join(folder, "check")
    os.makedirs(check_dir, exist_ok=True)
    csv, plain = (os.path.join(csv_dir, f"{name}.csv"), os.path.join(plain_dir, f"{name}.csv"))
    argv = ["convert", path, "--name", name, "--out", csv, "--plain-out", plain,
            "--overlay", os.path.join(check_dir, f"{name}_overlay.png")]
    if e.get("check"):
        argv += ["--check", e["check"]]
    argv += [str(a) for a in e.get("args", [])]
    # A book figure (--palleros) prints its band positions under the troughs: with --check they are
    # the peak list the report should label, so ask for it (ir_digitize --peaklist).
    book = "--palleros" in argv and e.get("check") and "--peaklist" not in argv
    if book:
        argv.append("--peaklist")
    code, out, err = call("ir_digitize", argv)
    with open(os.path.join(check_dir, f"{name}.log"), "w", encoding="utf-8") as f:
        f.write(out + err)
    if code:
        raise SessionError(f"{e['file']}: ir_digitize stopped (exit {code}); "
                           f"see check/{name}.log\n{(err or out).strip()[-600:]}")
    printed = re.search(r"^\s*peaklist:\s*(\S+)\s*$", out, re.M)
    if printed and "peaks" not in e:  # the manifest's own "peaks" always wins
        e["peaks"] = [[float(a), float(b)] for a, b in
                      (pair.split("/") for pair in printed.group(1).split(","))]
    x, y = read_plain(plain)
    return _io._finish(e, name, x, y, TRANSMITTANCE, False, csv, plain)


def process(folder, e, csv_dir, plain_dir):
    f = e["file"]
    if f.lower().endswith(_io.SPA_EXT):
        return _io.process_spa(os.path.join(folder, f), e, csv_dir, plain_dir)
    if f.lower().endswith(_io.JDX_EXT):
        return process_jdx_reference(folder, e, csv_dir, plain_dir)
    return process_image(folder, e, csv_dir, plain_dir)


# -----------------------------------------------------------------------------
# Output
# -----------------------------------------------------------------------------
find_pdfmd = _io.find_pdfmd


def nulabreport_installed():
    kp = shutil.which("kpsewhich")
    return bool(kp and subprocess.run([kp, "nulabreport.sty"], capture_output=True,
                                      text=True).stdout.strip())


def build_latex(folder, base, figures):
    """Write BASE.tex (+ the bundled excerpt when the full package is not
    installed) and build it with lualatex. Returns the PDF path."""
    lualatex = shutil.which("lualatex")
    if not lualatex:
        raise SessionError("lualatex not found: install TeX Live or MacTeX, or build the "
                           ".md with pdfmd (--build pdfmd)")
    tex = os.path.join(folder, base + ".tex")
    with open(tex, "w", encoding="utf-8") as f:
        f.write(texout.render_tex(figures))
    if not nulabreport_installed():
        texout.write_excerpt(folder)
    r = subprocess.run([lualatex, "-interaction=nonstopmode", "-halt-on-error", base + ".tex"],
                       cwd=folder, capture_output=True, text=True)
    pdf = os.path.join(folder, base + ".pdf")
    for ext in (".aux", ".log"):
        if r.returncode == 0 and os.path.exists(os.path.join(folder, base + ext)):
            os.remove(os.path.join(folder, base + ext))
    if r.returncode or not os.path.exists(pdf):
        raise SessionError(f"lualatex failed on {tex} (log kept beside it):\n{r.stdout[-800:]}")
    return pdf


def move_line(folder, src, dst, dry_run):
    return (f"{'would move' if dry_run else 'moved'}: "
            f"{os.path.relpath(src, folder)} -> {os.path.relpath(dst, folder)}")


# -----------------------------------------------------------------------------
# --preview: what a run would do with every spectrum, written nowhere
# -----------------------------------------------------------------------------
def _rel(folder, path):
    return os.path.relpath(path, folder).replace(os.sep, "/")


def planned_names(folder, e):
    """(name, csv, plain) a spectrum's CSVs get, relative to the folder, as `process` writes them."""
    if e["file"].startswith("SPA/"):
        stem = spa_tool.clean_stem(e["file"])
        return stem, f"csv/{stem}.csv", f"plain/{stem}_plain.csv"
    name = reference_name(folder, e)
    return name, f"csv/{name}.csv", f"plain/{name}.csv"


def preview_folder(folder, titles, sort, width, height, braille, as_json):
    """The planned moves (as --dry-run prints them), then for every spectrum the preview of
    `irspec preview`, headed by where it will be filed. Writes nothing. Returns the exit status:
    0, or 1 when a spectrum could not be read (the others are still shown); a folder that is not
    one, or has no spectra, exits 2."""
    from . import preview as pv

    def stop(msg):
        print(f"irspec session: {msg}", file=sys.stderr)
        sys.exit(2)

    folder = os.path.abspath(folder)
    if not os.path.isdir(folder):
        stop(f"not a directory: {folder}")
    if width < pv.MIN_WIDTH:
        stop(f"--width must be at least {pv.MIN_WIDTH} (got {width})")
    if height < pv.MIN_HEIGHT:
        stop(f"--height must be at least {pv.MIN_HEIGHT} (got {height})")
    moves = organize(folder, dry_run=True)
    planned = {}
    for src, dst in moves:
        r = _rel(folder, dst)
        if r.startswith(("SPA/", "jdx/")):
            planned[r] = src
    mpath = os.path.join(folder, "manifest.json")
    listed = set()
    try:
        if os.path.exists(mpath):
            with open(mpath, encoding="utf-8") as f:
                listed = {_io.entry_file(e) for e in json.load(f)}
        entries = build_manifest(folder, titles, sort, planned)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as err:
        stop(f"manifest.json cannot be used ({str(err) or type(err).__name__})")
    if not entries:
        stop("no spectra found (SPA/, jdx/ or img/)")

    spectra, images, blocks, failed = [], [], [], False
    for e in entries:
        rel = e["file"]
        name, csv, plain = planned_names(folder, e)
        if rel.lower().endswith(IMG_EXT):
            images.append({"file": rel, "name": name, "csv": csv, "plain": plain,
                           "note": "digitized by `irspec session`, not drawn here"})
            continue
        src = planned.get(rel) or os.path.join(folder, rel)
        head = {"will_be_filed_as": rel, "title": e.get("title"), "csv": csv, "plain": plain}
        try:
            info = pv.work_out_entry(src, e, mpath if rel in listed else None)
            info["file"] = _rel(folder, src)
            record = {**pv.public(info), **head}
            text = "" if as_json else pv.render(info, width, height, braille)
        except pv.PreviewError as err:
            failed = True
            reason = str(err).replace(src, _rel(folder, src))   # not the absolute path
            record = {"file": _rel(folder, src), **head, "error": reason}
            text = f"error:   {reason}\n"
        spectra.append(record)
        where = f"now {_rel(folder, src)}" if rel in planned else "already there"
        blocks.append(f"=== {rel}  ({where}) ===\ntitle:   {head['title']}\n"
                      f"csv:     {csv}\nplain:   {plain}\n\n{text}")
    if as_json:
        print(json.dumps({"moves": [{"from": _rel(folder, a), "to": _rel(folder, b)}
                                    for a, b in moves],
                          "spectra": spectra, "images": images}, ensure_ascii=False))
        return 1 if failed else 0
    for src, dst in moves:
        print(move_line(folder, src, dst, True))
    for b in blocks:
        print(b)
    if images:
        print("=== pictures: digitized by `irspec session`, not drawn here ===")
        for im in images:
            print(f"{im['file']}  ->  {im['csv']}, {im['plain']}")
        print()
    print("preview only: nothing was written.")
    return 1 if failed else 0


def run(folder, build="auto", sort="time", titles=None, md_name=None, dry_run=False, pdfmd=None,
        formats=(), dpi=300):
    """Process one folder; returns the list of Figure. Prints what it does."""
    folder = os.path.abspath(folder)
    if not os.path.isdir(folder):
        raise SessionError(f"not a directory: {folder}")
    moves = organize(folder, dry_run)
    for src, dst in moves:
        print(move_line(folder, src, dst, dry_run))
    if dry_run:
        return []
    entries = build_manifest(folder, titles or {}, sort)
    if not entries:
        raise SessionError("no spectra found (SPA/, jdx/ or img/)")
    csv_dir, plain_dir = os.path.join(folder, "csv"), os.path.join(folder, "plain")
    os.makedirs(csv_dir, exist_ok=True)
    os.makedirs(plain_dir, exist_ok=True)
    results = []
    for e in entries:
        r = process(folder, e, csv_dir, plain_dir)
        results.append(r)
        print(f"# {r['stem']}: axis={r['axis_label']} peaks={r['n_peaks']} ymin={r['ymin']}")
    _io.save_manifest(folder, entries)
    figures = [Figure.from_organize_result(r, folder) for r in results]
    write_figures(figures, os.path.join(folder, FIGURES_NAME))
    base = md_name or _io.default_md_name(folder)
    md = os.path.join(folder, base + ".md")
    with open(md, "w", encoding="utf-8") as f:
        f.write(texout.render_md(figures))
    print(f"wrote {md} ({len(figures)} spectra)")

    if build == "auto":
        build = "pdfmd" if (find_pdfmd(pdfmd) and nulabreport_installed()) else "latex"
    if build in ("pdfmd", "latex"):
        print(f"building the PDF with {'pdfmd (nulabreport)' if build == 'pdfmd' else 'lualatex alone'}")
    if build == "pdfmd":
        exe = find_pdfmd(pdfmd)
        if not exe:
            raise SessionError("pdfmd not found (use --pdfmd or $PDFMD, or --build latex)")
        print(f"wrote {_io.build_pdf(md, exe)}")
    elif build == "latex":
        print(f"wrote {build_latex(folder, base, figures)}")
    if formats:
        pdf = os.path.join(folder, base + ".pdf")
        if not os.path.exists(pdf):
            raise SessionError("--formats needs the PDF: use --build pdfmd or latex")
        for p in export.export_pdf(pdf, formats, os.path.join(folder, "figures"),
                                   export.stems_of(figures), dpi):
            print(f"wrote {p}")
    return figures


def main(argv=None):
    ap = argparse.ArgumentParser(prog="irspec session", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", nargs="?", default=".")
    ap.add_argument("--build", choices=["auto", "pdfmd", "latex", "none"], default="auto",
                    help="how to make the PDF: pdfmd (nulabreport's pipeline, from the .md), "
                         "latex (plain lualatex, from a .tex), none; auto = pdfmd when pdfmd "
                         "and nulabreport are both installed, else latex")
    ap.add_argument("--no-pdf", action="store_true", help="same as --build none")
    ap.add_argument("--sort", choices=["time", "name"], default="time")
    ap.add_argument("--title", action="append", default=[], metavar="STEM=TITLE")
    ap.add_argument("--md-name", default=None, help="output basename (default ir_<dd-mm>)")
    ap.add_argument("--dry-run", action="store_true", help="print the planned file moves, stop")
    ap.add_argument("--preview", action="store_true",
                    help="--dry-run, and then each spectrum drawn as text as `irspec preview` "
                         "does, headed by the name and folder it will get; writes nothing "
                         "(with --dry-run it means the same). Takes --width, --height, --ascii, "
                         "--json; --build, --formats and --dpi are ignored")
    ap.add_argument("--width", type=int, metavar="N", help="--preview: columns (default: the "
                    "terminal's width, or 80 when piped)")
    ap.add_argument("--height", type=int, metavar="N", help="--preview: rows of plot (default 20)")
    ap.add_argument("--ascii", action="store_true", help="--preview: . : * | instead of Braille")
    ap.add_argument("--json", action="store_true", help="--preview: one JSON object "
                    "{moves, spectra, images} on stdout and no plot")
    ap.add_argument("--pdfmd", default=None)
    ap.add_argument("--formats", default="", metavar="LIST",
                    help="also write one picture per spectrum into DIR/figures/, from the PDF: "
                         "comma list of " + ", ".join(export.FORMATS) + " (see irspec export --help)")
    ap.add_argument("--dpi", type=int, default=300, help="resolution of png/tiff (default 300)")
    a = ap.parse_args(argv)
    titles = {}
    for t in a.title:
        if "=" not in t:
            raise SessionError(f"--title needs STEM=TITLE, got {t!r}")
        k, v = t.split("=", 1)
        titles[k] = v
    if a.preview:
        from . import preview as pv
        sys.exit(preview_folder(
            a.folder, titles, a.sort,
            a.width if a.width is not None else pv.default_width(),
            a.height if a.height is not None else pv.DEFAULT_HEIGHT,
            pv.utf8_stdout() and not a.ascii, a.json))
    for flag in ("width", "height", "ascii", "json"):
        if getattr(a, flag) not in (None, False):
            ap.error(f"--{flag} goes with --preview")
    run(a.folder, "none" if a.no_pdf else a.build, a.sort, titles, a.md_name, a.dry_run, a.pdfmd,
        export.parse_formats(a.formats), a.dpi)


if __name__ == "__main__":
    main()

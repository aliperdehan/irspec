"""Picture files from the figure PDF: PNG, TIFF, SVG.

The TeX pipeline's PDF is the one picture irspec draws properly (pgfplots, the
house fonts, peak labels that avoid each other). The other formats are made
from it, one file per page, named after the spectrum:

  png       pdftoppm -png   at --dpi (default 300)              [poppler]
  tiff      pdftoppm -tiff  at --dpi, LZW compressed            [poppler]
  svg       pdftocairo -svg: looks exactly like the PDF anywhere, but the
            text is drawn as outlines, so it cannot be edited as text  [poppler]
  svg-text  mutool draw -F svg -O text=text: the labels stay real <text>
            (editable in Inkscape/Illustrator) with the fonts' names
            ("STIX Two Text"), which must be installed where the file is
            opened; TeX's word spaces are gaps between glyph positions, not
            space characters, so a label reads "Transmittance%" in an editor
            while still drawing correctly         [MuPDF]

One page is one figure: the document is one spectrum per page (a landscape
block with \\clearpage between). `names` are the file stems in page order.
"""
import os
import re
import shutil
import subprocess

FORMATS = ("png", "tiff", "svg", "svg-text")
EXT = {"png": ".png", "tiff": ".tiff", "svg": ".svg", "svg-text": ".svg"}
# Both SVG flavours share an extension; the editable one gets a suffix so the
# two can sit side by side.
SUFFIX = {"svg-text": "_text"}


class ExportError(SystemExit):
    """A message for the user, not a traceback."""


def parse_formats(text, allowed=FORMATS):
    """'png,svg' -> ['png', 'svg'] (order kept, duplicates dropped); errors
    name the allowed values."""
    out = []
    for f in re.split(r"[,\s]+", text.strip().lower()):
        if not f:
            continue
        if f not in allowed:
            raise ExportError(f"unknown format {f!r}; choose from: {', '.join(allowed)}")
        if f not in out:
            out.append(f)
    return out


def page_count(pdf):
    exe = shutil.which("pdfinfo")
    if not exe:
        raise ExportError("pdfinfo (poppler) not found: brew install poppler")
    r = subprocess.run([exe, pdf], capture_output=True, text=True)
    m = re.search(r"^Pages:\s+(\d+)", r.stdout, re.M)
    if r.returncode or not m:
        raise ExportError(f"could not read {pdf}: {r.stderr.strip()[:200]}")
    return int(m.group(1))


def _need(tool, why):
    exe = shutil.which(tool)
    if not exe:
        raise ExportError(f"{tool} not found ({why}); "
                          "poppler: brew install poppler / apt install poppler-utils; "
                          "mutool: brew install mupdf-tools / apt install mupdf-tools")
    return exe


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise ExportError(f"{os.path.basename(cmd[0])} failed: {(r.stderr or r.stdout).strip()[:300]}")


def export_pdf(pdf, formats, outdir, names=None, dpi=300):
    """Write one file per page and format into `outdir`; returns the paths.
    `names`: file stems in page order; when absent or the wrong length the
    pages are called page-1, page-2, ..."""
    n = page_count(pdf)
    if not names or len(names) != n:
        names = [f"page-{i}" for i in range(1, n + 1)]
    os.makedirs(outdir, exist_ok=True)
    written = []
    for fmt in formats:
        if fmt in ("png", "tiff"):
            exe = _need("pdftoppm", f"needed for {fmt}")
        elif fmt == "svg":
            exe = _need("pdftocairo", "needed for svg")
        elif fmt == "svg-text":
            exe = _need("mutool", "needed for svg-text")
        else:
            raise ExportError(f"unknown format {fmt!r}")
        for page, stem in enumerate(names, 1):
            dest = os.path.join(outdir, stem + SUFFIX.get(fmt, "") + EXT[fmt])
            if fmt == "png":
                # -singlefile: exactly `stem`.png, no page-number suffix
                _run([exe, "-r", str(dpi), "-f", str(page), "-l", str(page),
                      "-png", "-singlefile", pdf, dest[:-len(".png")]])
            elif fmt == "tiff":
                _run([exe, "-r", str(dpi), "-f", str(page), "-l", str(page),
                      "-tiff", "-tiffcompression", "lzw", "-singlefile", pdf,
                      dest[:-len(".tiff")]])
                # pdftoppm writes .tif; keep the longer, unambiguous extension
                os.replace(dest[:-len(".tiff")] + ".tif", dest)
            elif fmt == "svg":
                _run([exe, "-svg", "-f", str(page), "-l", str(page), pdf, dest])
            else:
                _run([exe, "draw", "-F", "svg", "-O", "text=text", "-o", dest, pdf, str(page)])
            written.append(dest)
    return written


def stems_of(figures):
    """File stems for figures: the plain CSV's name without `_plain`."""
    out = []
    for f in figures:
        s = os.path.splitext(os.path.basename(f.csv))[0]
        out.append(s[:-len("_plain")] if s.endswith("_plain") else s)
    return out


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="irspec export", description="PNG/TIFF/SVG files from a "
                                 "figure PDF, one per page.\n" + __doc__.split("One page is")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("--formats", default="png", help="comma list of: " + ", ".join(FORMATS))
    ap.add_argument("--out", default=None, help="folder (default: figures/ beside the PDF)")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--names", default=None, help="comma list of file stems, in page order")
    a = ap.parse_args(argv)
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.pdf)), "figures")
    names = [n for n in a.names.split(",") if n] if a.names else None
    for p in export_pdf(a.pdf, parse_formats(a.formats), out, names, a.dpi):
        print(f"wrote {p}")


if __name__ == "__main__":
    main()

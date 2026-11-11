"""irspec plot -- draw a session's figures without TeX, with matplotlib or R.

    irspec plot DIR [--backend matplotlib|r] [--formats png,svg,...] [--out DIR]
                    [--size 10x6.6] [--dpi 300] [--no-caption]

DIR is a session folder (the one `irspec session` wrote, with figures.json in
it) or the figures.json itself. Pictures go to DIR/figures/matplotlib/ or
DIR/figures/r/, so they never overwrite the ones made from the TeX PDF
(DIR/figures/, `irspec session --formats`). The three drawings share their
geometry (layout.py) and agree on everything but the y tick spacing.

  matplotlib   png, tiff, pdf, svg (outlined text), svg-text (editable text)
  r            the same five; pdf and svg need an R with working cairo (macOS:
               XQuartz). Needs R with ggplot2 and jsonlite (ragg, svglite
               recommended). The script is data/irspec.R and runs on its own:
               Rscript irspec.R DIR --formats png   (`--print-r-script` says where)
"""
import argparse
import shutil
import subprocess
import sys
from importlib import resources

from .export import ExportError

BACKENDS = ("matplotlib", "r")


def r_script_path():
    return str(resources.files("irspec").joinpath("data", "irspec.R"))


def r_target(argv):
    """The session folder or figures.json among the R backend's arguments (the first that is not
    an option or an option's value), or None."""
    takes_value = {"--formats", "--out", "--size", "--dpi"}
    skip = False
    for a in argv:
        if skip:
            skip = False
        elif a in takes_value:
            skip = True
        elif not a.startswith("-"):
            return a
    return None


def refuse_other_kinds(argv):
    """The R script draws IR figures only: say so before R starts, for a figure of another kind."""
    import os

    from .figure import FIGURES_NAME, read_figures
    target = r_target(argv)
    if target is None:
        return
    path = os.path.join(target, FIGURES_NAME) if os.path.isdir(target) else target
    if not os.path.exists(path):
        return   # the R script says what is missing
    try:
        figures, _ = read_figures(path)
    except ValueError as e:
        raise ExportError(str(e))
    for f in figures:
        if f.kind != "ir":
            raise ExportError(f"{f.csv} is a {f.kind} figure; the R backend draws IR figures only "
                              f"so far (use the PDF: irspec session)")


def run_r(argv):
    refuse_other_kinds(argv)
    exe = shutil.which("Rscript")
    if not exe:
        raise ExportError("Rscript not found: install R (https://cran.r-project.org) and "
                          'install.packages(c("ggplot2", "jsonlite", "ragg", "svglite"))')
    code = subprocess.run([exe, r_script_path(), *argv]).returncode
    if code:
        raise ExportError(f"the R backend failed (exit {code})")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="irspec plot", description=__doc__, add_help=False,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend", choices=BACKENDS, default="matplotlib")
    ap.add_argument("--print-r-script", action="store_true", help="print the R script's path and stop")
    ap.add_argument("-h", "--help", action="store_true")
    a, rest = ap.parse_known_args(argv)
    if a.print_r_script:
        print(r_script_path())
        return
    if a.help:
        print(__doc__.strip())
        return
    if a.backend == "r":
        run_r(rest)
    else:
        from . import mpl
        mpl.main(rest)


if __name__ == "__main__":
    main()

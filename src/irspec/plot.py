"""irspec plot -- draw a session's figures without TeX, with matplotlib or R.

    irspec plot DIR [--backend matplotlib|r] [--formats png,svg,...] [--out DIR]
                    [--size 10x6.6] [--dpi 300] [--no-caption]

DIR is a session folder (the one `irspec session` wrote, with figures.json in
it) or the figures.json itself. Pictures go to DIR/figures/matplotlib/ or
DIR/figures/r/, so they never overwrite the ones made from the TeX PDF
(DIR/figures/, `irspec session --formats`). The three drawings share their
geometry (layout.py) and agree on everything but the y tick spacing.

  matplotlib   png, tiff, pdf, svg (outlined text), svg-text (editable text)
  r            png, tiff, svg (editable text; svg-text is the same), pdf where
               R has cairo. Needs R with ggplot2 and jsonlite (ragg, svglite
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


def run_r(argv):
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

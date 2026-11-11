"""The standalone R backend allocates the complete output list."""
import contextlib
import io
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from irspec import export, mpl
from irspec.figure import Figure, write_figures

SCRIPT = Path(__file__).resolve().parents[1] / "src/irspec/data/irspec.R"


@unittest.skipUnless(shutil.which("Rscript"), "needs Rscript")
class RNames(unittest.TestCase):
    def test_standalone_r_names_match_python_for_all_figures_and_formats(self):
        ready = subprocess.run(["Rscript", "-e", 'quit(status=!all(sapply(c("jsonlite","ggplot2"), requireNamespace, quietly=TRUE)))'], capture_output=True)
        if ready.returncode:
            self.skipTest("needs R jsonlite and ggplot2")
        for sources in (("plain/A_plain.csv", "plain/A.csv", "plain/B.csv"),
                        ("plain/A.csv", "plain/A_text.csv", "plain/B.csv"),
                        ("one/A.csv", "two/A.csv", "plain/B.csv")):
            with self.subTest(sources=sources), tempfile.TemporaryDirectory() as d:
                figs = [Figure(p, p) for p in sources]
                write_figures(figs, str(Path(d) / "figures.json"))
                out = Path(d) / "out"
                expr = ('args <- commandArgs(TRUE); source(args[1]); '
                        'draw <- function(...) list(); '
                        'pick_font <- function(...) list(family="",note="test"); '
                        'save_as <- function(p,dest,...) writeLines("figure",dest); '
                        'main(c(args[2],"--formats","png,svg,svg-text","--out",args[3]))')
                result = subprocess.run(["Rscript", "-e", expr, str(SCRIPT), d, str(out)],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                with contextlib.redirect_stderr(io.StringIO()):
                    names = export.stems_of(figs)
                    expected = export.filenames(list(sources), names, ["png", "svg", "svg-text"], mpl.EXT, mpl.SUFFIX)
                self.assertEqual(sorted(p.name for p in out.iterdir()), sorted(expected.values()))
                self.assertEqual(len(list(out.iterdir())), 9)
                self.assertIn("name collision:", result.stderr)

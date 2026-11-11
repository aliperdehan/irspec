"""Export names cannot collide with another figure or format."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from irspec import export, mpl
from irspec.figure import Figure


class ExportNames(unittest.TestCase):
    def test_stems_preserve_noncollisions_and_ignore_order(self):
        figs = [Figure(p, p) for p in ("A.csv", "A_plain.csv", "A-2.csv")]
        with contextlib.redirect_stderr(io.StringIO()):
            names = export.stems_of(figs)
            reversed_names = export.stems_of(figs[::-1])
        self.assertEqual(len(set(names)), 3)
        self.assertEqual(names[2], "A-2")
        self.assertEqual(reversed_names, names[::-1])
        with self.assertRaisesRegex(export.ExportError, "same input file twice"):
            export.stems_of([figs[0], figs[0]])

    def test_final_format_matrix_is_unique_before_pdf_writes(self):
        with tempfile.TemporaryDirectory() as d, patch("irspec.export.page_count", return_value=2), patch(
                "irspec.export._need", return_value="tool"), patch("irspec.export._run") as run, contextlib.redirect_stderr(io.StringIO()):
            paths = export.export_pdf("a.pdf", ["svg", "svg-text"], d, ["A", "A_text"])
            self.assertEqual(len(set(paths)), 4)
            self.assertEqual(run.call_count, 4)
            self.assertIn(str(Path(d) / "A.svg"), paths)
            self.assertIn(str(Path(d) / "A_text_text.svg"), paths)

    def test_matplotlib_uses_the_same_complete_plan(self):
        figs = [Figure(p, p, peaks=[]) for p in ("A.csv", "A_text.csv")]
        with tempfile.TemporaryDirectory() as d, patch("irspec.mpl.read_figures", return_value=(figs, d)), patch(
                "irspec.mpl.draw") as draw, contextlib.redirect_stderr(io.StringIO()):
            spec = Path(d) / "figures.json"
            spec.write_text("[]")
            written = mpl.render(str(spec), ["svg", "svg-text"], d)
            self.assertEqual(len(set(written)), 4)
            self.assertEqual(draw.return_value.savefig.call_count, 4)

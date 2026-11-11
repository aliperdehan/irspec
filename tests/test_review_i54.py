"""Matplotlib input errors name the affected file."""
import json
import tempfile
import unittest
from pathlib import Path

from irspec import mpl
from irspec.export import ExportError


class InputErrors(unittest.TestCase):
    def test_bad_figure_files(self):
        with tempfile.TemporaryDirectory(dir=".") as d:
            p = Path(d) / "figures.json"
            for raw in ("{", json.dumps([{"spec": 999, "csv": "x.csv"}])):
                p.write_text(raw)
                with self.subTest(raw=raw), self.assertRaises(ExportError) as error:
                    mpl.render(str(p), ["png"])
                self.assertIn(str(p), str(error.exception))

    def test_missing_csv(self):
        with tempfile.TemporaryDirectory(dir=".") as d:
            p = Path(d) / "figures.json"
            p.write_text(json.dumps([{"csv": "missing.csv"}]))
            with self.assertRaises(ExportError) as error:
                mpl.render(str(p), ["png"])
            self.assertIn("missing.csv", str(error.exception))

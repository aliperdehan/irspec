"""SPA batch Markdown paths are relative to the document."""
import tempfile
import unittest
from pathlib import Path

from irspec import spa_tool


class BatchPaths(unittest.TestCase):
    def test_markdown_beside_and_inside_output_directory(self):
        sample = Path("tests/data/PHENACETIN_CRUDE_LR1-2.SPA").resolve()
        with tempfile.TemporaryDirectory(dir=".") as d:
            root = Path(d).resolve()
            out = root / "share"
            for md in (root / "share.md", out / "nested" / "report.md"):
                spa_tool.batch([{"spa": str(sample)}], str(out), str(md))
                expected = (out / "plain" / (sample.stem + "_plain.csv"))
                import os
                relative = os.path.relpath(expected, md.parent)
                self.assertIn("{" + relative + "}", md.read_text())
                self.assertTrue((md.parent / relative).is_file())

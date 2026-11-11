import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from irspec import ir_organize


class PdfmdRelative(unittest.TestCase):
    def test_relative_override_survives_session_cwd(self):
        with tempfile.TemporaryDirectory(dir=".") as d:
            root = Path(d).resolve()
            tool = root / "pdfmd.py"
            tool.write_text("import pathlib, sys\npathlib.Path(sys.argv[1]).with_suffix('.pdf').touch()\n")
            folder = root / "session"
            folder.mkdir()
            md = folder / "ir.md"
            md.touch()
            rel = os.path.relpath(tool)
            with patch.dict(os.environ, {"PDFMD": rel}):
                for override in (rel, None):
                    self.assertEqual(Path(ir_organize.build_pdf(str(md), override)), folder / "ir.pdf")
                    (folder / "ir.pdf").unlink()

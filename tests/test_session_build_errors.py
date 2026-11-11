import contextlib
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from irspec import export, session


class BuildErrors(unittest.TestCase):
    def test_expected_build_failures_are_reported_as_json(self):
        source = Path(__file__).parent / "data" / "PHENACETIN_CRUDE_LR1-2.SPA"
        for failure in ("pdfmd", "export"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as d:
                folder = Path(d)
                (folder / "SPA").mkdir()
                shutil.copy(source, folder / "SPA")
                pdf = folder / "ir.pdf"
                pdf.touch()
                stdout = io.StringIO()
                error = subprocess.CalledProcessError(1, ["pdfmd"]) if failure == "pdfmd" else export.ExportError("missing export tool")
                target = "irspec.session._io.build_pdf" if failure == "pdfmd" else "irspec.session.export.export_pdf"
                args = [str(folder), "--json", "--md-name", "ir", "--build", "pdfmd" if failure == "pdfmd" else "none"]
                if failure == "export":
                    args += ["--formats", "png"]
                with patch("irspec.session.find_pdfmd", return_value="pdfmd"), patch(target, side_effect=error), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(session.SessionError):
                        session.main(args)
                report = json.loads(stdout.getvalue())
                self.assertFalse(report["build"]["ok"])
                self.assertTrue(report["spectra"])
                self.assertIn("error", report["build"])

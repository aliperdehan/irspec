"""The README and CHANGELOG must keep up with the code they describe."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from irspec import __version__, cli, export, figure  # noqa: E402


class Docs(unittest.TestCase):
    def setUp(self):
        self.readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    def test_every_command_is_documented(self):
        for cmd in cli.COMMANDS:
            self.assertIn(f"`irspec {cmd}", self.readme, f"README does not mention `irspec {cmd}`")

    def test_every_export_format_is_documented(self):
        for fmt in export.FORMATS:
            self.assertIn(f"| `{fmt}` |", self.readme, f"README table lacks format {fmt}")

    def test_spec_version_quoted_correctly(self):
        self.assertRegex(self.readme, rf"now {figure.SPEC_VERSION}\)")

    def test_version_is_semver_and_in_changelog(self):
        self.assertRegex(__version__, r"^\d+\.\d+\.\d+$")
        # An unreleased snapshot is listed in the development-history table;
        # a release has its own heading.
        self.assertTrue(re.search(rf"^\| {re.escape(__version__)} \|", self.changelog, re.M)
                        or re.search(rf"^## {re.escape(__version__)}\b", self.changelog, re.M),
                        f"CHANGELOG has no entry for {__version__}")


if __name__ == "__main__":
    unittest.main()

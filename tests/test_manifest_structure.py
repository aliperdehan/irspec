import json
import tempfile
import unittest
from pathlib import Path

from irspec import session


class ManifestStructure(unittest.TestCase):
    def test_rejects_non_list_and_non_object_entries(self):
        for value in (None, [None], {}, ["spectrum"]):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as d:
                path = Path(d) / "manifest.json"
                original = json.dumps(value)
                path.write_text(original)
                with self.assertRaisesRegex(session.SessionError, "manifest.json cannot be used.*list of entry objects"):
                    session.run(d, build="none")
                self.assertEqual(path.read_text(), original)

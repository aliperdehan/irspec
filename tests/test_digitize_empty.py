"""Empty image traces follow the digitiser failure path."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image
from irspec import session


class EmptyTrace(unittest.TestCase):
    def test_empty_trace_exits_for_all_layouts(self):
        with tempfile.TemporaryDirectory() as d:
            image = Path(d) / "blank.png"
            Image.new("RGB", (20, 20), "white").save(image)
            mask = np.zeros((20, 20), dtype=bool)
            layout = ((0, 0, 19, 19), ([0, 19], [4000, 400]),
                      ([0, 19], [100, 0]), mask, None)
            for name in ("manual", "palleros", "omnic"):
                args = ["convert", str(image), "--name", "BLANK", "--layout", name]
                if name == "manual":
                    args += ["--box", "0,0,19,19", "--x", "0=4000", "--x", "19=400",
                             "--y", "0=100", "--y", "19=0"]
                with self.subTest(layout=name), patch("irspec.ir_digitize.palleros_layout", return_value=layout), \
                     patch("irspec.ir_digitize.omnic_layout", return_value=layout):
                    code, out, _ = session.call("ir_digitize", args)
                self.assertEqual(code, 2)
                self.assertIn("FAIL", out)

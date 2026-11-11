"""Truncated Shimadzu records are reported through normal error paths."""
import io
import struct
import unittest
from unittest.mock import patch

from irspec import uvvis, vqud_tool, vspd_tool
from irspec.session import SessionError


class FakeOle:
    def __init__(self, streams):
        self.streams = streams

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def listdir(self, **kwargs):
        return [key.split("/") for key in self.streams]

    def openstream(self, path):
        key = "/".join(path) if isinstance(path, list) else path
        if key not in self.streams:
            raise OSError(key)
        return io.BytesIO(self.streams[key])


class Truncated(unittest.TestCase):
    def test_short_vspd_header_reaches_session_error(self):
        base = vspd_tool.BASE + "DataSpectrumStorage/Data/"
        ole = FakeOle({base + "X Data.1": struct.pack("<d", 500),
                       base + "Y Data.1": struct.pack("<d", 1),
                       base + "Data Header.1": b"x"})
        with patch("olefile.OleFileIO", return_value=ole):
            with self.assertRaisesRegex(SessionError, "Data Header.1.*truncated"):
                uvvis.process(".", {"file": "bad.vspd"}, ".", ".")

    def test_vqud_truncated_fields_and_cli(self):
        marker = vqud_tool.MARKER
        stream = "Standard Table/Column Configuration/Reading"
        for tail in (b"", b"\x03a", b"\x01a", b"\x01a\x03b"):
            ole = FakeOle({stream: marker + tail})
            with self.subTest(tail=tail):
                with self.assertRaisesRegex(ValueError, "Reading.*truncated"):
                    vqud_tool.config_records(ole, "Standard Table", "Reading")
                with patch.object(vqud_tool, "_main", side_effect=lambda argv: vqud_tool.config_records(
                        ole, "Standard Table", "Reading")):
                    with self.assertRaisesRegex(SystemExit, "Reading.*truncated"):
                        vqud_tool.main([])

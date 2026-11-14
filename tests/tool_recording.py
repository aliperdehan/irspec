"""Record/replay standalone tools on generated inputs, including file hashes."""

import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")


def digest(path):
    """sha256 of a file; for a PNG or JPEG, of its decoded pixels (with mode and size). The
    encoded bytes depend on the Pillow and zlib build (CI's Python 3.9 gets Pillow 11, 3.13 gets
    13; checked 2026-11-15: the PNG bytes differ, the pixels of every image here do not)."""
    if path.suffix.lower() in IMAGE_SUFFIXES:
        from PIL import Image
        with Image.open(path) as im:
            head = f"{im.mode} {im.size[0]}x{im.size[1]} ".encode()
            return "pixels:" + hashlib.sha256(head + im.tobytes()).hexdigest()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(folder):
    return {
        str(p.relative_to(folder)): digest(p)
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }


def run_case(command, argv, prepare):
    with tempfile.TemporaryDirectory() as t:
        folder = Path(t).resolve()
        metadata = prepare(folder) or {}
        before = snapshot(folder)
        env = {
            **os.environ,
            "PYTHONPATH": str(ROOT / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        result = subprocess.run(
            [sys.executable, *command, *argv],
            cwd=folder,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        def normalise(text):
            text = text.replace(str(folder), "<TMP>")
            # An encoded image's size follows the encoder build (see digest), and numpy prints a
            # rounded negative zero as -0.000 on some versions.
            text = re.sub(r"size=[\d.]+ ?KB", "size=<KB>", text)
            text = re.sub(r"-(0\.0+)(?![\d])", r"\1", text)
            if command[0] != "-m":
                text = text.replace(command[0], "<TOOL>")
            text = re.sub(
                r"(?:irspec (?:spectrum|tlc|gel|scan)|(?:spectrum_digitize|tlc_contour|gel_tool|scan_clean)\.py)",
                "<TOOL>",
                text,
            )
            # argparse aligns/wraps usage around prog, whose name changes in this port.
            return re.sub(
                r"(?ms)\Ausage:.*?(?=^<TOOL>: error:)",
                lambda match: " ".join(match.group().split()) + "\n",
                text,
            )

        after = snapshot(folder)
        return {
            **metadata,
            "argv": argv,
            "code": result.returncode,
            "stdout": normalise(result.stdout),
            "stderr": normalise(result.stderr),
            "files": {k: v for k, v in after.items() if before.get(k) != v},
        }


def record(tool, cases, prepare, output):
    first = {
        name: run_case([tool], argv, lambda d: prepare(d, name)) for name, argv in cases
    }
    second = {
        name: run_case([tool], argv, lambda d: prepare(d, name)) for name, argv in cases
    }
    if first != second:
        raise RuntimeError(
            "original output differs between two recordings; inspect before accepting"
        )
    Path(output).write_text(
        json.dumps(first, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print({k: (v["code"], len(v["files"])) for k, v in first.items()})


def replay(test, command, cases, prepare, name):
    expected = cases[name]
    actual = run_case(
        ["-m", "irspec", command], expected["argv"], lambda d: prepare(d, name)
    )
    if actual.get("overlay_font") != expected.get("overlay_font"):
        # Glyphs vary by host; check streams and all non-image files before skipping the hash.
        actual = {
            **actual,
            "overlay_font": None,
            "files": {
                k: v for k, v in actual["files"].items() if not k.endswith(".png")
            },
        }
        expected = {
            **expected,
            "overlay_font": None,
            "files": {
                k: v for k, v in expected["files"].items() if not k.endswith(".png")
            },
        }
        test.assertEqual(actual, expected)
        test.skipTest(
            "overlay image hash needs the recorded host font and Pillow version"
        )
    test.assertEqual(actual, expected)

"""Record the original spectrum_digitize.py twice on generated MS/NMR pictures.

    python3 tests/record_spectrum_digitize.py ~/dev/tex/nulabreport/tools/spectrum_digitize.py tests/data/spectrum_digitize_expected.json

No input picture is copied from a report. The overlay font fingerprint lets the replay
compare image hashes on matching hosts and stable non-image output on other hosts.
"""

import hashlib
from pathlib import Path
import sys
import PIL
from PIL import Image, ImageDraw
from tool_recording import record

OUTPUTS = ["--out", "trace.csv", "--peaks-out", "peaks.csv", "--list-out", "peaks.list"]
MS = ["ms", "input.png", "--x-ticks", "10:10", "--y-ticks", "0:20", *OUTPUTS]
NMR = [
    "nmr",
    "input.png",
    "--x-ticks",
    "10:-1",
    "--no-integrals",
    "--tex-out",
    "plot.tex",
    *OUTPUTS,
]
CASES = [
    ("ms", MS),
    ("ms_labels", [*MS, "--labels", "2", "--label-gap", "7"]),
    ("ms_check", [*MS, "--check", "20,50,80,110", "--labels", "20,50,80,110"]),
    ("nmr", NMR),
    ("nmr_solvent", [*NMR, "--solvent", "0", "--solvent-style", "none"]),
    (
        "nmr_inset_figure",
        [
            *NMR,
            "--inset",
            "80:-2",
            "--inset-layout",
            "figure",
            "--solvent",
            "76",
            "--solvent-style",
            "none",
        ],
    ),
    ("nmr_inset_separate", [*NMR, "--inset", "80:-2", "--inset-layout", "separate"]),
    ("nmr_rulers", ["nmr", "input.png", "--show-rulers"]),
    (
        "ms_bad_ticks",
        [
            "ms",
            "input.png",
            "--x-ticks",
            "0:1",
            "--y-ticks",
            "0:20",
            "--out",
            "trace.csv",
        ],
    ),
]


CASES += [
    ("ms_overlay", [*MS, "--overlay", "check.png"]),
    ("nmr_overlay", [*NMR, "--overlay", "check.png"]),
]


def overlay_font():
    # The original's _font tries these paths, then Pillow's built-in font.
    for name in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        path = Path(name)
        if path.exists():
            return PIL.__version__ + ":" + hashlib.sha256(path.read_bytes()).hexdigest()
    return PIL.__version__ + ":Pillow default"


def prepare(folder, name):
    if name.startswith("ms"):
        image = Image.new("L", (700, 450), 255)
        draw = ImageDraw.Draw(image)
        draw.line((60, 380, 650, 380), fill=0, width=2)
        draw.line((60, 40, 60, 380), fill=0, width=2)
        if name != "ms_bad_ticks":
            for x in range(100, 601, 25):
                draw.line(
                    (x, 380, x, 392 if (x - 100) % 50 == 0 else 385), fill=0, width=2
                )
            for y in range(80, 381, 50):
                draw.line((48, y, 60, y), fill=0, width=2)
            for x, y in [(150, 200), (300, 80), (450, 260), (600, 150)]:
                draw.line((x, 379, x, y), fill=0, width=3)
    else:
        image = Image.new("L", (700, 400), 255)
        draw = ImageDraw.Draw(image)
        draw.line((75, 330, 625, 330), fill=0, width=2)
        for x in range(100, 601, 25):
            draw.line((x, 330, x, 342 if (x - 100) % 50 == 0 else 335), fill=0, width=2)
        draw.line((80, 300, 620, 300), fill=0, width=2)
        draw.line((480, 300, 480, 260), fill=0, width=2)
        draw.line((600, 300, 600, 50), fill=0, width=2)
        if name.startswith("nmr_inset"):
            draw.line((130, 160, 430, 160), fill=0, width=2)
            for x in range(150, 401, 25):
                draw.line(
                    (x, 160, x, 172 if (x - 150) % 50 == 0 else 165), fill=0, width=2
                )
            draw.line((140, 130, 420, 130), fill=0, width=2)
            draw.line((250, 130, 250, 20), fill=0, width=2)
            draw.line((350, 130, 350, 100), fill=0, width=2)
    image.save(folder / "input.png")
    return {"overlay_font": overlay_font()} if name.endswith("_overlay") else None


if __name__ == "__main__":
    record(sys.argv[1], CASES, prepare, sys.argv[2])

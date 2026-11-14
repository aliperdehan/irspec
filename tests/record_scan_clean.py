"""Record the original scan_clean.py twice on synthetic pages, shadows and noise.

python3 tests/record_scan_clean.py ~/dev/tex/nulabreport/tools/scan_clean.py tests/data/scan_clean_expected.json
"""

import sys
import numpy as np
from PIL import Image
from tool_recording import record

OUT = ["page.png", "out.png", "out.jpg"]
CASES = [
    ("page", OUT),
    ("tiny", OUT),
    ("tiny_off", ["page.png", "--no-png", "out.jpg", "--min-paper-frac", "0"]),
    ("flatten", [*OUT, "--flatten"]),
    (
        "flatten_defaults",
        [
            *OUT,
            "--flatten",
            "--flatten-dilate",
            "0.044",
            "--flatten-blur",
            "0.025",
            "--flatten-scale",
            "4",
            "--flatten-floor",
            "60",
            "--flatten-black",
            "0.12",
            "--flatten-white",
            "0.92",
            "--flatten-gamma",
            "1.15",
        ],
    ),
    ("flatten_gamma", [*OUT, "--flatten", "--flatten-gamma", "3"]),
    (
        "flatten_tuned",
        [
            *OUT,
            "--flatten",
            "--flatten-dilate",
            "0.05",
            "--flatten-blur",
            "0.03",
            "--flatten-scale",
            "2",
            "--flatten-floor",
            "80",
            "--flatten-black",
            "0.15",
            "--flatten-white",
            "0.95",
            "--flatten-gamma",
            "0.9",
        ],
    ),
    (
        "budget",
        [
            "page.png",
            "--no-png",
            "out.jpg",
            "--min-paper-frac",
            "0",
            "--target-kb",
            "1",
        ],
    ),
    (
        "bad_levels",
        [*OUT, "--flatten", "--flatten-black", "0.95", "--flatten-white", "0.9"],
    ),
]


def prepare(folder, name):
    if name.startswith("tiny"):
        a = np.full((800, 1000), 80, np.uint8)
        a[500:535, :] = 235
    elif name == "budget":
        a = np.random.default_rng(1).integers(0, 256, (900, 1300), dtype=np.uint8)
    elif name.startswith("flatten"):
        a = (
            np.broadcast_to(np.linspace(235, 105, 1000), (800, 1000))
            .copy()
            .astype(np.uint8)
        )
        for y in range(150, 700, 30):
            a[y : y + 6, 180:840] = 30
    else:
        a = np.full((800, 1000), 60, np.uint8)
        a[80:740, 120:900] = 235
        for y in range(150, 700, 30):
            a[y : y + 6, 180:840] = 30
    Image.fromarray(a).convert("RGB").save(folder / "page.png")


if __name__ == "__main__":
    record(sys.argv[1], CASES, prepare, sys.argv[2])

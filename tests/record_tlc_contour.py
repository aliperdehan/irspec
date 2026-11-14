"""Record the original TLC tool twice on synthetic plates and a deterministic vector PDF.

python3 tests/record_tlc_contour.py ~/dev/tex/nulabreport/tools/tlc_contour.py tests/data/tlc_contour_expected.json
"""

import sys
import numpy as np
from PIL import Image, ImageDraw
from tool_recording import record

CASES = [
    ("image", ["plate.png", "--out", "contour.png"]),
    (
        "crop_lines",
        [
            "plate.png",
            "--out",
            "contour.png",
            "--crop",
            "lines",
            "--margin-frac",
            "0.03",
            "--despeckle-min-px",
            "0",
        ],
    ),
    (
        "budget",
        [
            "plate.png",
            "--out",
            "contour.png",
            "--target-kb",
            "1",
            "--despeckle-min-px",
            "0",
            "--bin-thresh",
            "0.9",
        ],
    ),
    ("pdf_all", ["plates.pdf", "--out-dir", "out", "--dpi", "72"]),
    ("pdf_page", ["plates.pdf", "--out-dir", "out", "--pages", "2", "--dpi", "96"]),
    ("pdf_missing_out", ["plates.pdf"]),
    ("image_missing_out", ["plate.png"]),
]


def make_pdf(path):
    # No PDF producer, timestamps, embedded font or scanned input.
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>",
    ]
    for page, (w, h) in enumerate([(600, 800), (300, 900)]):
        stream = f"1 g 0 0 {w} {h} re f 0 G 2 w 20 100 m {w - 20} 100 l S 20 {h - 100} m {w - 20} {h - 100} l S 40 200 30 20 re S 110 350 40 20 re S".encode(
            "ascii"
        )
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {w} {h}] /Resources << >> /Contents {4 + page * 2} 0 R >>".encode(
                "ascii"
            )
        )
        objects.append(
            b"<< /Length "
            + str(len(stream)).encode("ascii")
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{i} 0 obj\n".encode("ascii") + obj + b"\nendobj\n")
    start = len(data)
    data.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for off in offsets[1:]:
        data.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    data.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode(
            "ascii"
        )
    )
    path.write_bytes(data)


def prepare(folder, name):
    make_pdf(folder / "plates.pdf")
    if name == "budget":
        arr = np.where(
            np.random.default_rng(4).random((900, 1200)) < 0.5, 0, 255
        ).astype(np.uint8)
        image = Image.fromarray(arr)
    else:
        yy, xx = np.mgrid[:900, :700]
        image = Image.fromarray((230 + 20 * xx / 700 - 15 * yy / 900).astype(np.uint8))
        draw = ImageDraw.Draw(image)
        draw.line((40, 120, 660, 120), fill=20, width=4)
        draw.line((40, 780, 660, 780), fill=20, width=4)
        for x, y in [(120, 240), (260, 420), (400, 590), (540, 320)]:
            draw.ellipse((x - 20, y - 9, x + 20, y + 9), outline=30, width=3)
        draw.point((25, 25), fill=0)
    image.save(folder / "plate.png")


if __name__ == "__main__":
    record(sys.argv[1], CASES, prepare, sys.argv[2])

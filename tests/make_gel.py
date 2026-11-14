#!/usr/bin/env python3
"""make_gel.py -- a SYNTHETIC SDS-PAGE gel photo, for the \\gelfigure demo and the smoke test.

NOT REAL DATA. A drawn gel (Coomassie-blue bands, a prestained ladder whose 75 and 25 kDa
reference bands are near-black, a faint ridge at the top of the resolving gel, a blue dye
front) set into a white bench at a slight perspective, so tools/gel_tool.py has the same
jobs as on a phone photo: find the corners, straighten, number the lanes, find origin and
front, assign the ladder, fit. Every band sits EXACTLY on log10(kDa) = A + B * Rf, so the
masses gel_tool.py estimates can be checked against the planted ones (PLANTED below).

    python3 make_gel.py photo.jpg            # ladder in lane 1
    python3 make_gel.py photo.jpg --mirror   # the same gel left to right: ladder in lane 6
    python3 make_gel.py --planted            # print the planted sample masses as JSON

Deterministic (fixed seed). Pillow and numpy only.
"""
import argparse
import json
import math

import numpy as np
from PIL import Image

W, H = 900, 700                  # the gel itself, before it is set into the photo
LANES, PITCH, HALF = 6, 150, 50  # lane centres 75 + 150 k; bands 100 px wide
Y0, YF = 100, 560                # top of the resolving gel, dye front
A, B = 2.4783, -1.1137           # 245 kDa at Rf 0.08, 25 kDa at Rf 0.97
LADDER = [245, 180, 135, 100, 75, 63, 48, 35, 25]
BLACK = {75, 25}                 # the prestained reference bands, near-black
# sample lanes: lane -> [(kDa, OD)]
SAMPLES = {2: [(66, 0.65)], 4: [(78, 0.40), (45, 0.70)], 5: [(150, 0.30), (50, 0.65)]}
PLANTED = {str(n): [m for m, _ in v] for n, v in SAMPLES.items()}
PHOTO = (1200, 1000)
QUAD = [(160, 140), (1060, 126), (1076, 846), (150, 862)]   # TL, TR, BR, BL in the photo


def y_of(kda):
    return Y0 + (math.log10(kda) - A) / B * (YF - Y0)


def solve(src, dst):
    """PIL PERSPECTIVE coefficients mapping src (output) points to dst (input) points."""
    M, v = [], []
    for (u, w), (x, y) in zip(src, dst):
        M.append([u, w, 1, 0, 0, 0, -u * x, -w * x]); v.append(x)
        M.append([0, 0, 0, u, w, 1, -u * y, -w * y]); v.append(y)
    return tuple(np.linalg.solve(np.array(M, float), np.array(v, float)))


def gel(mirror=False):
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    od = np.zeros((3, H, W))
    od[0] += 0.04 * yy / H                                    # a gentle stain gradient
    od[0] += 0.06 * np.exp(-((yy - Y0) / 6) ** 2)             # ridge at the resolving gel's top
    front = np.exp(-((yy - YF) / 11) ** 2)                    # the dye front, across the width
    od += np.array([0.50, 0.25, 0.03])[:, None, None] * front

    def band(lane, kda, h, black):
        c = 75 + PITCH * ((LANES - lane) if mirror else (lane - 1))
        across = 1 / (1 + np.exp((np.abs(xx - c) - HALF) / 3))   # flat across the lane, soft edges
        prof = h * across * np.exp(-((yy - y_of(kda)) / 5) ** 2)
        w = (1.0, 1.0, 0.9) if black else (1.0, 0.5, 0.08)       # Coomassie barely touches blue
        for ch in range(3):
            od[ch] += w[ch] * prof

    for kda in LADDER:
        band(1, kda, 0.9 if kda in BLACK else 0.5, kda in BLACK)
    band(1, 20, 0.4, False)                                   # 20/17/11 compressed, past the front
    for lane, bands in SAMPLES.items():
        for kda, h in bands:
            band(lane, kda, h, False)
    base = np.array([95.0, 150.0, 205.0])[:, None, None]
    rgb = base * 10 ** (-od) + np.random.default_rng(0).normal(0, 1.5, od.shape)
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8).transpose(1, 2, 0))


def photo(mirror=False):
    g = gel(mirror)
    coeffs = solve(QUAD, [(0, 0), (W, 0), (W, H), (0, H)])   # photo pixel -> gel pixel
    warped = g.transform(PHOTO, Image.Transform.PERSPECTIVE, coeffs, resample=Image.Resampling.BICUBIC)
    mask = Image.new("L", (W, H), 255).transform(PHOTO, Image.Transform.PERSPECTIVE, coeffs)
    yy, xx = np.mgrid[0:PHOTO[1], 0:PHOTO[0]]
    vign = 1 - 0.06 * (((xx - 600) / 600) ** 2 + ((yy - 500) / 500) ** 2)
    bench = np.clip(np.array([226.0, 229.0, 232.0])[None, None, :] * vign[..., None], 0, 255).astype(np.uint8)
    out = Image.fromarray(bench)
    out.paste(warped, (0, 0), mask)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("out", nargs="?")
    ap.add_argument("--mirror", action="store_true")
    ap.add_argument("--planted", action="store_true")
    a = ap.parse_args()
    if a.planted:
        planted = PLANTED if not a.mirror else {str(LANES + 1 - int(k)): v for k, v in PLANTED.items()}
        print(json.dumps(planted))
    if a.out:
        photo(a.mirror).save(a.out, quality=92)

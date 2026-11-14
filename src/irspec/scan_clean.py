#!/usr/bin/env python3
"""
Clean up phone/camera photos of paper documents so they look like flatbed scans,
and compress them under a target file size.

Moved here from nulabreport's tools/scan_clean.py (2026-11-14); the output is byte for byte what that script wrote.

Pipeline per image:
  1. Auto-detect skew (paper edge isn't parallel to frame) and rotate to straighten.
  2. Auto-detect the paper's bounding box (vs. desk/table/background around it)
     and crop tightly to it. A box smaller than --min-paper-frac of the frame
     (default 0.30) is not trusted: the tool says so on stderr, naming the box,
     and takes the whole frame instead (v1.31.1). A strong shadow across the
     page did this: the box came out 9 pixels high and the JPEG 3 KB, silently.
  3. Enhance: autocontrast (fixes shadow gradients / off-white balance),
     + brightness/contrast/sharpness bump for a crisp "scanned" look.
     With --flatten (opt-in, v1.31.2) this step is replaced by a division by
     the local paper white, for photos with a shadow across the page (below).
  4. Save a full-resolution lossless PNG, and a resized/quality-tuned JPEG that
     is auto-tuned (width + JPEG quality) to land under --target-kb.

Requires: Pillow, numpy (no OpenCV/ImageMagick needed).

Usage:
    irspec scan IN.png OUT.png OUT.jpg [--target-kb 195] [--min-paper-frac 0.30]
                          [--flatten [--flatten-dilate 0.044] [--flatten-blur 0.025]
                                     [--flatten-scale 4] [--flatten-floor 60]
                                     [--flatten-black 0.12] [--flatten-white 0.92] [--flatten-gamma 1.15]]
    irspec scan IN.png OUT.jpg --no-png ...

  --min-paper-frac F: the smallest share of the (straightened) frame that the
    detected paper box may cover before it is distrusted and the whole frame is
    used (default 0.30, the 30 % the report of the 9-pixel box suggested; a real
    page photo covers 0.8-0.95 of its frame). 0 turns the check off.

  --flatten [--flatten-dilate 0.044] [--flatten-blur 0.025]: for a page with a
    shadow across it. The global autocontrast of step 3 sets one black and one
    white point for the whole page, so text in a shadow goes nearly black with
    the shadow. --flatten estimates the paper's own white at every point instead
    and divides by it, per channel: on a copy 1/--flatten-scale the size, a grey
    dilation (a max filter as wide as --flatten-dilate of the cropped page's
    short side; it removes the ink, which is thinner) and then a Gaussian blur
    (radius --flatten-blur of the short side), scaled back up and never below
    --flatten-floor. The quotient is 1 on paper and below it on ink, wherever
    the shadow falls; the levels --flatten-black/--flatten-white and
    --flatten-gamma then make paper white and keep the ink dark. The defaults
    reproduce the prototype the method was found with (LR9's photos,
    2026-11-10: a 21-pixel max filter and a blur of radius 12 on a quarter-size
    copy of a page about 1900 pixels across). Raise --flatten-dilate if thick
    strokes (a heading, a marker line) come out grey; lower --flatten-blur if a
    sharp shadow edge leaves a halo. The output PNG and JPEG are written as
    without the flag. Off by default: the output without it is byte for byte
    what it was.

    The other five --flatten-* options (v1.31.4) are the prototype's values,
    set by eye on those three LR9 photos and not measured:
      --flatten-scale 4    the paper white is estimated on a copy this many
                           times smaller, for speed (a whole number, 1 or more);
      --flatten-floor 60   the estimate never goes below this (0-255 scale), so
                           a dark corner (the desk) is not divided into white
                           (above 0, at most 255);
      --flatten-black 0.12 a pixel at or below this share of the local paper
                           white prints black ...
      --flatten-white 0.92 ... at or above it white, just under paper white so
                           the paper's texture goes (0 <= black < white <= 1);
      --flatten-gamma 1.15 then a gamma; above 1 darkens the mid-tones a little
                           (above 0).
    Lower --flatten-white (or raise --flatten-black) for more contrast, raise
    --flatten-gamma for darker pencil; the defaults give the LR9 output byte for
    byte.

Tuning knobs (see constants below) if detection goes wrong on a page:
  - THRESH: brightness (0-255) that separates "paper" from "table/background".
    Raise it if a shadow on the desk is still being treated as paper; lower it
    if part of the white paper margin is being cut off.
  - MIN_RUN: how many consecutive bright/dark rows or columns are needed before
    a paper/table transition is trusted. Prevents a single line of text (a thin
    dark streak) from being mistaken for the page edge.
  - MARGIN_FRAC: extra inward safety trim (fraction of image size) applied
    after the paper bbox is found, since the paper photo may still be a little
    rotated even after the deskew step, leaving thin table slivers at corners.
"""
import sys
import io
import math
import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps, ImageEnhance, ImageFilter

THRESH = 170
MIN_RUN = 25
MIN_RUN_SKEW = 15
MARGIN_FRAC = 0.01
MIN_PAPER_FRAC = 0.30    # the default of --min-paper-frac (see the docstring)
# --flatten (v1.31.2; see the docstring). The two sizes are fractions of the cropped page's short side.
FLAT_DILATE_FRAC = 0.044  # default of --flatten-dilate: 21 px on the quarter-size copy of a 1900 px page
FLAT_BLUR_FRAC = 0.025    # default of --flatten-blur: radius 12 there
# The other five are the prototype's values, set by eye on LR9's three photos, not measured; each is an option
# since v1.31.4 (these are the defaults):
FLAT_SCALE = 4            # default of --flatten-scale: the paper white is estimated on a copy this many times smaller
FLAT_BG_FLOOR = 60.0      # default of --flatten-floor: the estimate never goes below this, so a dark corner (desk)
                          # is not divided into white
FLAT_BLACK = 0.12         # default of --flatten-black: quotient (pixel / paper white) at or below this prints black ...
FLAT_WHITE = 0.92         # default of --flatten-white: ... at or above this white: just under paper white, so
                          # paper texture goes
FLAT_GAMMA = 1.15         # default of --flatten-gamma: then a gamma that darkens the mid-tones a little
JPEG_WIDTHS = [1300, 1200, 1100, 1000, 900, 800]
JPEG_QUALITIES = [80, 75, 70, 65, 60, 55, 50, 45]


def find_boundary(means, thresh, min_run, from_start):
    """Walk in from one edge of a 1D brightness profile and return the index
    where a *sustained* run of `min_run` bright samples begins — i.e. the
    paper edge, robust to thin dark text lines that dip below `thresh`."""
    n = len(means)
    idx_range = range(n) if from_start else range(n - 1, -1, -1)
    consecutive_bright = 0
    run_start = None
    for i in idx_range:
        if means[i] > thresh:
            if consecutive_bright == 0:
                run_start = i
            consecutive_bright += 1
            if consecutive_bright >= min_run:
                return run_start
        else:
            consecutive_bright = 0
            run_start = None
    return None


def estimate_skew_angle(gray_arr):
    """Sample the top paper edge at many x positions and fit a line to it to
    get the rotation angle, dropping outliers (e.g. a torn/curled corner)."""
    h, w = gray_arr.shape
    xs = np.linspace(int(w * 0.15), int(w * 0.85), 40).astype(int)
    pts = []
    for x in xs:
        b = find_boundary(gray_arr[:, x], THRESH, MIN_RUN_SKEW, from_start=True)
        if b is not None and b < h * 0.4:
            pts.append((x, b))
    if len(pts) < 8:
        return 0.0
    pts = np.array(pts, dtype=np.float64)
    a, c = np.polyfit(pts[:, 0], pts[:, 1], 1)
    resid = pts[:, 1] - (a * pts[:, 0] + c)
    std = resid.std() + 1e-6
    keep = np.abs(resid) < 2 * std
    if keep.sum() >= 6:
        a, c = np.polyfit(pts[keep, 0], pts[keep, 1], 1)
    return math.degrees(math.atan(a))


def find_paper_bbox(gray_arr):
    h, w = gray_arr.shape
    row_means = gray_arr.mean(axis=1)
    col_means = gray_arr.mean(axis=0)
    top = find_boundary(row_means, THRESH, MIN_RUN, from_start=True) or 0
    bottom = find_boundary(row_means, THRESH, MIN_RUN, from_start=False) or (h - 1)
    left = find_boundary(col_means, THRESH, MIN_RUN, from_start=True) or 0
    right = find_boundary(col_means, THRESH, MIN_RUN, from_start=False) or (w - 1)
    mh, mw = int(h * MARGIN_FRAC), int(w * MARGIN_FRAC)
    top = min(top + mh, h)
    bottom = max(bottom - mh, 0)
    left = min(left + mw, w)
    right = max(right - mw, 0)
    return left, top, right, bottom


def check_paper_bbox(box, size, min_frac, name="scan_clean"):
    """Return `box` (left, top, right, bottom) if it covers at least `min_frac`
    of a frame of `size` (width, height); otherwise warn on stderr, naming the
    box, and return the whole frame. An inverted box counts as empty."""
    left, top, right, bottom = box
    w, h = size
    frac = max(0, right - left) * max(0, bottom - top) / float(w * h)
    if frac >= min_frac:
        return box
    print(f"scan_clean.py: WARNING: {name}: the paper box {left},{top},{right},{bottom} covers "
          f"{100 * frac:.1f} % of the {w}x{h} frame, less than --min-paper-frac {min_frac:g}; "
          f"taking the whole frame instead", file=sys.stderr)
    return 0, 0, w, h


def flatten_paper(im, dilate_frac=FLAT_DILATE_FRAC, blur_frac=FLAT_BLUR_FRAC, scale=FLAT_SCALE,
                  floor=FLAT_BG_FLOOR, black=FLAT_BLACK, white=FLAT_WHITE, gamma=FLAT_GAMMA):
    """Divide an RGB page by an estimate of its local paper white, per channel
    (grey dilation, then a wide blur, on a copy 1/scale the size, never below
    floor), then set the levels (black, white, gamma): paper goes white wherever
    a shadow falls and ink stays dark. The levels are plain Python numbers: a
    NumPy float64 here would turn the float32 arithmetic into float64."""
    W, H = im.size
    short = min(W, H) / scale
    size = max(3, int(round(dilate_frac * short)) | 1)      # a max filter needs an odd size
    radius = blur_frac * short
    small = (max(1, W // scale), max(1, H // scale))
    chans = []
    for c in im.split():
        bg = c.resize(small, Image.BILINEAR).filter(ImageFilter.MaxFilter(size)).filter(ImageFilter.GaussianBlur(radius))
        chans.append(np.maximum(np.array(bg.resize((W, H), Image.BICUBIC), dtype=np.float32), floor))
    a = np.array(im, dtype=np.float32) / np.stack(chans, axis=2)
    a = np.clip((a - black) / (white - black), 0, 1) ** gamma
    return Image.fromarray((a * 255).astype(np.uint8))


def process(path_in, out_png, out_jpg, target_kb=195, min_paper_frac=MIN_PAPER_FRAC,
            flatten=False, flatten_dilate=FLAT_DILATE_FRAC, flatten_blur=FLAT_BLUR_FRAC,
            flatten_scale=FLAT_SCALE, flatten_floor=FLAT_BG_FLOOR, flatten_black=FLAT_BLACK,
            flatten_white=FLAT_WHITE, flatten_gamma=FLAT_GAMMA):
    # A phone photo stores its rotation as an EXIF tag, which neither the paper
    # detection nor the JPEG written below keeps: turn the pixels upright first.
    im = ImageOps.exif_transpose(Image.open(path_in)).convert("RGB")
    gray = np.array(im.convert("L"), dtype=np.float32)

    angle = estimate_skew_angle(gray)
    if abs(angle) > 0.05:
        im = im.rotate(angle, resample=Image.BICUBIC, expand=True, fillcolor=(255, 255, 255))
        gray = np.array(im.convert("L"), dtype=np.float32)

    left, top, right, bottom = check_paper_bbox(find_paper_bbox(gray), im.size, min_paper_frac, path_in)
    cropped = im.crop((left, top, right, bottom))

    if flatten:
        enhanced = flatten_paper(cropped, flatten_dilate, flatten_blur, flatten_scale, flatten_floor,
                                 flatten_black, flatten_white, flatten_gamma)
    else:
        enhanced = ImageOps.autocontrast(cropped, cutoff=1)
        enhanced = ImageEnhance.Brightness(enhanced).enhance(1.08)
        enhanced = ImageEnhance.Contrast(enhanced).enhance(1.15)
        enhanced = ImageEnhance.Sharpness(enhanced).enhance(1.3)
    if out_png:
        enhanced.save(out_png)

    best = None
    width = q = sz_kb = None
    for width in JPEG_WIDTHS:
        w0, h0 = enhanced.size
        resized = enhanced.resize((width, int(h0 * width / w0)), Image.LANCZOS)
        for q in JPEG_QUALITIES:
            buf = io.BytesIO()
            resized.save(buf, "JPEG", quality=q)
            sz_kb = len(buf.getvalue()) / 1024
            if sz_kb <= target_kb:
                best = (width, q, sz_kb, buf.getvalue())
                break
        if best:
            break
    if best is None:
        # the loops end on the smallest width and lowest quality tried
        best = (width, q, sz_kb, buf.getvalue())
        sys.stderr.write(f"warning: {out_jpg}: no width/quality fits the {target_kb:g} KB budget; "
                         f"wrote the smallest tried ({width}px, q={q}, {sz_kb:.0f} KB)\n")
    Path(out_jpg).write_bytes(best[3])
    print(f"{path_in}: skew={angle:.3f}deg bbox={left},{top},{right},{bottom} "
          f"-> {out_jpg} width={best[0]} q={best[1]} size={best[2]:.0f}KB" + (" (flattened)" if flatten else ""))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="irspec scan", )
    ap.add_argument("in_path")
    ap.add_argument("out_png", nargs="?", default=None,
                     help="full-res lossless PNG output (omit with --no-png)")
    ap.add_argument("out_jpg")
    ap.add_argument("--target-kb", type=float, default=195)
    ap.add_argument("--no-png", action="store_true")
    ap.add_argument("--min-paper-frac", type=float, default=MIN_PAPER_FRAC, metavar="F",
                    help="a detected paper box covering less than this share of the frame is "
                         "distrusted: warn and take the whole frame (default %(default)s; 0 = off)")
    ap.add_argument("--flatten", action="store_true",
                    help="divide by the local paper white instead of the global autocontrast: for a page "
                         "with a shadow across it (off by default)")
    ap.add_argument("--flatten-dilate", type=float, default=FLAT_DILATE_FRAC, metavar="F",
                    help="--flatten: width of the max filter that removes the ink, as a fraction of the "
                         "cropped page's short side (default %(default)s)")
    ap.add_argument("--flatten-blur", type=float, default=FLAT_BLUR_FRAC, metavar="F",
                    help="--flatten: radius of the blur that smooths the paper white, as a fraction of "
                         "the short side (default %(default)s)")
    # The next five were set by eye on three LR9 photos (the prototype's values), not measured.
    ap.add_argument("--flatten-scale", type=int, default=FLAT_SCALE, metavar="N",
                    help="--flatten: estimate the paper white on a copy N times smaller, for speed; a whole "
                         "number, 1 or more (default %(default)s; set by eye on three LR9 photos)")
    ap.add_argument("--flatten-floor", type=float, default=FLAT_BG_FLOOR, metavar="V",
                    help="--flatten: the paper-white estimate never goes below V, so a dark corner (the desk) "
                         "is not divided into white; above 0, at most 255 "
                         "(default %(default)s; set by eye on three LR9 photos)")
    ap.add_argument("--flatten-black", type=float, default=FLAT_BLACK, metavar="F",
                    help="--flatten: a pixel at or below this share of the local paper white prints black; "
                         "0 or more, below --flatten-white (default %(default)s; set by eye on three LR9 photos)")
    ap.add_argument("--flatten-white", type=float, default=FLAT_WHITE, metavar="F",
                    help="--flatten: a pixel at or above this share of the local paper white prints white; "
                         "above --flatten-black, at most 1 (default %(default)s; set by eye on three LR9 photos)")
    ap.add_argument("--flatten-gamma", type=float, default=FLAT_GAMMA, metavar="G",
                    help="--flatten: the gamma applied after the levels; above 1 darkens the mid-tones; "
                         "must be above 0 (default %(default)s; set by eye on three LR9 photos)")
    args = ap.parse_args(argv)
    if not 0 <= args.min_paper_frac <= 1:
        ap.error("--min-paper-frac must be between 0 and 1")
    if args.flatten_dilate <= 0 or args.flatten_blur <= 0:
        ap.error("--flatten-dilate and --flatten-blur must be above 0")
    if args.flatten_scale < 1:
        ap.error("--flatten-scale must be a whole number, 1 or more")
    if not 0 < args.flatten_floor <= 255:
        ap.error("--flatten-floor must be above 0 and at most 255")
    if not 0 <= args.flatten_black < args.flatten_white <= 1:
        ap.error("--flatten-black and --flatten-white must satisfy 0 <= black < white <= 1")
    if args.flatten_gamma <= 0:
        ap.error("--flatten-gamma must be above 0")
    out_png = None if args.no_png else args.out_png
    process(args.in_path, out_png, args.out_jpg, args.target_kb, args.min_paper_frac,
            args.flatten, args.flatten_dilate, args.flatten_blur, args.flatten_scale, args.flatten_floor,
            args.flatten_black, args.flatten_white, args.flatten_gamma)


if __name__ == "__main__":
    main()

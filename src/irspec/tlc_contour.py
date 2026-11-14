#!/usr/bin/env python3
"""tlc_contour.py -- turn a photo/scan of a hand-annotated TLC plate into a
small, high-contrast black-line-on-white "contour" PNG for a report figure.

Moved here from nulabreport's tools/tlc_contour.py (2026-11-14); the output is byte for byte what that script wrote.

REVERSE-ENGINEERED, NOT ORIGINAL (written 2026-09-22). The author previously had a
script that did this (crop to the baseline/solvent-front region, binarize
the pencil marks against the plate, compress to a small PNG) but no longer
has it -- only one input/output pair from an earlier report survived:
    LR1-2/photos/tlc_plate_scan.jpg -> tlc_plate_scan_contour.png
This is a fresh implementation built to reproduce that pair as closely as
the pixel evidence supports, NOT a recovered original -- section 2 below
says exactly what was measured versus what was inferred/chosen, so a future
session can tell the difference if a new plate's output looks off.

===============================================================================
1. PIPELINE
===============================================================================
  1. If the input is a PDF, render each page to RGB at --dpi (default 300)
     via `pdftoppm` (poppler-utils; must be on PATH). ONE DPI FOR EVERY PAGE
     -- never a fixed pixel width -- so pages of genuinely different
     physical size (Adobe Scan auto-crops each page to its own detected
     plate) come out at correctly *relative* pixel sizes instead of being
     stretched to match each other. Confirmed this matters concretely for
     plates_scan.pdf (2026-09-22): its third page is a narrower, taller
     plate than the first two (451x792pt vs ~612x650pt) -- one shared DPI
     preserves that; forcing a common output width would not.
  2. --crop none (THE DEFAULT, as of the second pass 2026-09-22 -- see
     section 4 for why the first pass's default was wrong): no vertical
     crop at all, the whole page goes to binarization as-is. --crop lines
     is the ORIGINAL behaviour this script started with: convert to
     grayscale, locate the two long, roughly full-width dark horizontal
     pencil lines (the TLC baseline and solvent front) via a per-row
     "fraction of dark pixels" profile (find_reference_lines()), and crop
     vertically to between them plus a small margin, discarding whatever's
     above the front and below the baseline. That mode reproduces the one
     surviving raw-photo example closely (section 2) -- but "discarding
     whatever's above/below" is exactly backwards for an Adobe-Scan-style
     PDF page that's already cropped to the document: there, real
     annotations (lane labels) routinely sit just past the baseline, and
     get silently cut by this mode. Use --crop lines only for a genuinely
     raw, uncropped photo with real background/margin around the plate,
     matching what it was reverse-engineered from; leave it at "none" for
     an Adobe Scan (or similar) PDF page.
  3. Flatten uneven illumination and binarize: divide the grayscale image by
     a heavily blurred copy of itself (estimates and removes a lighting
     gradient/vignette), then threshold the flattened result at
     --bin-thresh (default 0.90 -- fraction of the flattened white level)
     so only genuinely ink-dark pixels survive as black; paper, gradient,
     and grain/noise all become pure white. This step is the LEAST certain
     part of the reverse-engineering (section 2) -- it reproduces the
     *shape* of the one reference contour closely (see the smoke test this
     script's own module-level TEST section describes running), but was
     never verified byte-for-byte, because there is no original script left
     to diff against.
  4. Save as an 8-bit grayscale ('L' mode) PNG with only 0/255 present
     (confirmed this exactly matches the reference file's own encoding --
     colortype 0, bit depth 8, NOT a true 1-bit-depth PNG despite only two
     values being used -- read directly from its IHDR chunk, section 2),
     searching downward through the WIDTHS list for the largest one whose PNG
     (optimize=True) lands at or under --target-kb (default 25 -- the one
     surviving reference file is 30KB, so this default undercuts it
     slightly on purpose). The widths are tried on the widest page of a PDF
     and every page is scaled by the same factor, so the pages keep their
     relative pixel sizes (step 1); the largest shared scale at which every
     page fits wins. A page narrower than the largest width is also tried
     at its own width. When nothing fits, the smallest is written and a
     warning names the budget and the size.

===============================================================================
2. WHAT WAS ACTUALLY MEASURED FROM THE ONE SURVIVING EXAMPLE
===============================================================================
LR1-2/photos/tlc_plate_scan.jpg (1700x1937, RGB JPEG) ->
LR1-2/photos/tlc_plate_scan_contour.png (1670x1180, 8-bit grayscale PNG).
Measured 2026-09-22:
  - Exactly two pixel values used in the contour: 0 (74342 px, 3.8% of the
    image) and 255 (everything else). Confirmed via np.unique.
  - IHDR: width=1670 height=1180 bitdepth=8 colortype=0 (grayscale) --
    read directly, not inferred from PIL's reported mode.
  - The crop keeps only the region between two long dark horizontal rows in
    the source photo, found at y=614-647 and y=1729-1746 (of 1937) via a
    per-row "fraction of pixels < 100" profile thresholded at >0.12 -- the
    only two places that fraction gets anywhere near that high while
    spanning most of the row; every spot-outline curve, being a
    partial-width stroke, never does. The contour's own height (1180) is
    1180-(1746-614)=48px larger than the bare gap between those two rows,
    i.e. a margin of ~24px (~1.2% of the source's 1937px height) was kept
    on each side, not an exact edge-to-edge crop. This script's
    --margin-frac default (0.012) reproduces that ratio.
  - No deskew/rotate was applied: the two reference lines have the same
    slightly wavy, non-perfectly-horizontal shape in both the source photo
    and the contour PNG. This script does not deskew either.
  - Final size (30356 bytes) is what plain PNG deflate (Pillow's
    `optimize=True`) gets on data this sparse at this resolution --
    reproduced here without needing any extra external compressor
    (pngcrush/optipng); nothing in the file's chunk structure suggests one
    was used (plain IHDR/IDAT/IEND, standard ordering).
  - NOT independently confirmed, because there is no second example to
    triangulate against: the exact binarization method (a global threshold
    picked by hand vs. some adaptive/local scheme vs. something else
    entirely). The source photo's lighting gradient is mild enough that
    more than one method could plausibly produce a similar-looking result.
    The illuminate-flatten-then-threshold approach used here (step 3 above)
    was chosen for being the most robust to a lighting gradient specifically
    -- it is not a recovered detail.

===============================================================================
4. WHY --crop DEFAULTS TO "none" (found applying this to a real batch,
   same day it was written -- 2026-09-22)
===============================================================================
The first version of this script defaulted to what's now --crop lines, and
was run against the actual target (LR4-5/tlc/plates_scan.pdf, 3 Adobe Scan
pages). Two real, confirmed failures, both from the same root cause --
cropping tightly around the two reference lines is only correct when
there's genuine background/margin around the plate to discard, and an
Adobe Scan page doesn't have any (Adobe Scan already cropped it):
  - Page 2: the solvent front was too faint to detect (only the baseline
    was found), so the fallback used the baseline's OWN edge as the crop
    boundary instead of the image's far edge. This cut off real lane
    labels ("l", "s", "n", "b", "de") sitting ~50-150px below the
    baseline -- confirmed by cropping and looking at exactly the region
    that got discarded (LR4-5/tlc/, 2026-09-22): it contained that text
    and nothing else.
  - Page 3: the front line WAS genuinely there (confirmed real, not a
    detection bug, by cropping and looking directly at that row) -- but at
    45.6% of the page's height down, not near the top. Cropping tightly
    between it and the baseline turned a portrait page into a roughly
    square, aggressively-cropped one, discarding the entire top ~46% of
    the page (which the person who took the photo wanted kept, as extra
    context, not trimmed) as well as the label region past the baseline
    (the same failure as page 2).
Conclusion: for this class of input (already cropped to the document by
whatever scanned it), the line-detection crop actively destroys real
content and should not run by default. It's kept as an opt-in
(--crop lines) because it's still exactly right for a raw, uncropped photo
-- the one thing it was originally reverse-engineered from and still
reproduces well (section 2's smoke test).

Also added the same day: despeckle() (--despeckle-min-px, default 6),
because both this batch's renders and the one historical reference have
visible lone-pixel scan/sensor noise surviving binarization. Connected-
component size filtering (scipy.ndimage.label) removes any dark blob
under the threshold; a real stroke is a long connected run of many pixels
and is not affected by a small threshold like the default. Needs scipy;
skipped with a warning (not a hard failure) if it's not installed, since
it's a quality improvement, not something the rest of the pipeline depends
on.

===============================================================================
5. IF A NEW PLATE'S CONTOUR LOOKS WRONG
===============================================================================
  - Whole plate turns black / mostly black: --bin-thresh is too low for
    this image (a less-white plate, or a genuinely under-lit photo) --
    raise it. Also check the printed reference-line rows aren't wildly
    wrong (a bad crop range is the usual first tell of a deeper problem).
  - Real pencil lines vanish, or the plate stays a faint grey instead of
    pure white: --bin-thresh is too high, or --blur-frac (the illumination-
    flattening blur radius, as a fraction of image width) is too small to
    fully remove a strong gradient -- raise --blur-frac first (a much wider
    net than nudging the threshold), then the threshold if that alone
    doesn't fix it.
  - Reference-line detection picks the wrong rows (e.g. latches onto a
    thick spot outline that happens to run most of the width): --line-frac
    (minimum row width-fraction to count as a reference line, default 0.12
    -- deliberately low, since even the full-width reference lines in the
    one measured example only cover 12-28% of the row, not the fully-dark
    row a printed ruling would give)
    is too low for this image -- raise it. --line-dark-thresh (default 100)
    is the per-pixel darkness cutoff that feeds that fraction; lower it if
    the real reference lines are lighter than pure pencil (e.g. a faint
    ruled line) and are being missed entirely.
  - Fewer than two reference-line rows found at all: the script falls back
    to the image's own top/bottom edge (prints a warning) rather than
    guessing further -- don't trust that fallback's crop, fix the detection
    parameters for that image instead.

Usage:
    irspec tlc plates_scan.pdf --out-dir contour/
    irspec tlc plates_scan.pdf --out-dir contour/ --pages 1,3 --dpi 300
    irspec tlc one_photo.jpg --out contour/one_photo_contour.png
"""
import argparse
import io
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageFilter

MARGIN_FRAC = 0.012
LINE_FRAC = 0.12
LINE_DARK_THRESH = 100
BLUR_FRAC = 0.05
BIN_THRESH = 0.90
TARGET_KB = 25
WIDTHS = [1700, 1500, 1300, 1100, 950, 800, 650]
DESPECKLE_MIN_PX = 6
CROP_MODE = "none"


def render_pdf_pages(pdf_path, dpi, pages=None):
    """Render PDF pages to a list of (page_num, PIL.Image), one DPI for
    every page (never a fixed pixel width -- see module docstring sec. 1)
    via `pdftoppm` (must be on PATH)."""
    with tempfile.TemporaryDirectory() as td:
        prefix = os.path.join(td, "pg")
        cmd = ["pdftoppm", "-r", str(dpi), "-png"]
        if pages:
            cmd += ["-f", str(min(pages)), "-l", str(max(pages))]
        cmd += [pdf_path, prefix]
        subprocess.run(cmd, check=True)
        out = []
        for fn in sorted(os.listdir(td)):
            if not fn.endswith(".png"):
                continue
            # pdftoppm names e.g. pg-1.png or pg-01.png depending on page count
            num = int(fn[len("pg-"):-len(".png")].lstrip("0") or "0")
            if pages and num not in pages:
                continue
            out.append((num, Image.open(os.path.join(td, fn)).convert("RGB").copy()))
    return sorted(out, key=lambda t: t[0])


def find_reference_lines(gray, line_frac=LINE_FRAC, dark_thresh=LINE_DARK_THRESH):
    """Return (top_row, bottom_row) of the two long, roughly full-width dark
    horizontal pencil lines (TLC baseline + solvent front) -- module
    docstring sec. 1/2. An Adobe-Scan-style input that's already cropped
    tight to the plate often only shows ONE of the two clearly (the
    solvent front is typically much fainter pencil than the baseline) --
    in that case the found line is used for whichever edge it's actually
    nearest to, and the image's own opposite edge stands in for the other
    (there's nothing wrong to trim there if the source is already tight).
    Only truly finding zero lines falls back to the full image height,
    with a loud warning -- that fallback should not be trusted; fix the
    detection parameters for that image instead."""
    h, w = gray.shape
    frac_dark = (gray < dark_thresh).mean(axis=1)
    rows = np.where(frac_dark > line_frac)[0]
    if len(rows) == 0:
        sys.stderr.write(
            f"warning: no reference lines found (line_frac={line_frac}, "
            f"dark_thresh={dark_thresh}) -- falling back to full image height, "
            f"do not trust this crop\n"
        )
        return 0, h - 1
    groups = []
    start = prev = rows[0]
    for r in rows[1:]:
        if r - prev > 15:
            groups.append((start, prev))
            start = r
        prev = r
    groups.append((start, prev))
    if len(groups) == 1:
        g = groups[0]
        center = (g[0] + g[1]) / 2
        if center < h / 2:
            sys.stderr.write(f"reference lines: only top group {g} found -- using image bottom edge for the other\n")
            return g[0], h - 1
        else:
            sys.stderr.write(f"reference lines: only bottom group {g} found -- using image top edge for the other\n")
            return 0, g[1]
    top = groups[0][0]
    bottom = groups[-1][1]
    sys.stderr.write(f"reference lines: top group {groups[0]}, bottom group {groups[-1]}\n")
    return top, bottom


def flatten_and_binarize(gray, blur_frac=BLUR_FRAC, bin_thresh=BIN_THRESH):
    """Divide by a heavily blurred copy of itself to remove an uneven
    lighting gradient, then threshold to pure 0/255 -- module docstring
    sec. 1 step 3. blur_frac is the blur radius as a fraction of image
    width; bin_thresh is the fraction of the flattened white level below
    which a pixel counts as ink."""
    im = Image.fromarray(gray)
    radius = max(3, int(gray.shape[1] * blur_frac))
    # box blur via numpy cumulative sums (no scipy/opencv dependency)
    bg = np.array(im.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32)
    bg = np.clip(bg, 1.0, 255.0)
    flat = gray.astype(np.float32) / bg
    binary = np.where(flat < bin_thresh, 0, 255).astype(np.uint8)
    return binary


def despeckle(binary_arr, min_px=DESPECKLE_MIN_PX):
    """Remove isolated dark speckles (scan/sensor noise -- a handful of
    lone dark pixels here and there, confirmed present in both the
    Adobe-Scan renders and the one historical reference) while leaving
    real strokes intact, by connected-component size: any dark (ink)
    blob with fewer than min_px connected pixels is cleared to white.
    A real pencil stroke, even a short one, is a long thin run of many
    connected pixels and easily clears a small threshold like the
    default (6px); a lone noise speck from JPEG/sensor grain is usually
    1-3px and does not. Requires scipy (ndimage.label) -- if it isn't
    installed, this is skipped with a warning rather than failing the
    whole run, since it's a quality nice-to-have, not load-bearing."""
    try:
        from scipy import ndimage
    except ImportError:
        sys.stderr.write("note: scipy not installed, skipping despeckle (pip install scipy)\n")
        return binary_arr
    mask = binary_arr == 0
    labeled, n = ndimage.label(mask, structure=np.ones((3, 3)))
    if n == 0:
        return binary_arr
    sizes = ndimage.sum(mask, labeled, index=np.arange(1, n + 1))
    small_labels = np.where(sizes < min_px)[0] + 1
    if len(small_labels) == 0:
        return binary_arr
    out = binary_arr.copy()
    out[np.isin(labeled, small_labels)] = 255
    sys.stderr.write(f"despeckle: removed {len(small_labels)} blob(s) under {min_px}px\n")
    return out


def candidate_widths(w0, widths):
    """Widths to try for an image w0 pixels wide, largest first, never
    upscaling. An image narrower than the largest configured width is
    also tried at its own width, so a small valid image has a candidate."""
    cands = {w for w in widths if w <= w0}
    if not widths or w0 < max(widths):
        cands.add(w0)
    return sorted(cands, reverse=True)


def _encode(im, width):
    w0, h0 = im.size
    resized = im.resize((width, max(1, int(h0 * width / w0))), Image.NEAREST) \
        if width != w0 else im
    buf = io.BytesIO()
    resized.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def save_pages_under_budget(binaries, out_paths, target_kb=TARGET_KB, widths=WIDTHS):
    """Save every page at ONE shared scale, so pages of different physical
    width keep their relative pixel sizes (module docstring sec. 1). The
    candidate widths are tried on the widest page; each page is scaled by
    the same factor. The largest scale at which every page meets the budget
    wins; if none does, the smallest scale is written and each page over
    budget is named in a warning. -> list of (width, size_kb)."""
    # uint8 2-D -> mode "L", as `mode="L"` gave (that parameter is deprecated since Pillow 11.3)
    ims = [Image.fromarray(np.asarray(a, np.uint8)) for a in binaries]
    ref = max(im.size[0] for im in ims)
    cands = candidate_widths(ref, widths)
    if not cands:
        sys.exit(f"no output width to try for a {ref}px-wide image")
    for width in cands:
        scale = width / ref
        sized = [max(1, round(im.size[0] * scale)) for im in ims]
        data = [_encode(im, w) for im, w in zip(ims, sized)]
        if all(len(d) / 1024 <= target_kb for d in data):
            break
    # the loop ends on the smallest candidate when none fits
    result = []
    for path, w, d in zip(out_paths, sized, data):
        kb = len(d) / 1024
        if kb > target_kb:
            sys.stderr.write(f"warning: {path}: no width fits the {target_kb:g} KB budget; "
                             f"wrote the smallest tried ({w}px, {kb:.1f} KB)\n")
        with open(path, "wb") as f:
            f.write(d)
        result.append((w, kb))
    return result


def save_under_budget(binary_arr, out_path, target_kb=TARGET_KB, widths=WIDTHS):
    return save_pages_under_budget([binary_arr], [out_path], target_kb, widths)[0]


def prepare_image(im, crop_mode=CROP_MODE, margin_frac=MARGIN_FRAC,
                   line_frac=LINE_FRAC, line_dark_thresh=LINE_DARK_THRESH,
                   blur_frac=BLUR_FRAC, bin_thresh=BIN_THRESH,
                   despeckle_min_px=DESPECKLE_MIN_PX):
    gray = np.array(im.convert("L"))
    h, w = gray.shape
    if crop_mode == "lines":
        top, bottom = find_reference_lines(gray, line_frac, line_dark_thresh)
        margin = int(h * margin_frac)
        crop_top = max(0, top - margin)
        crop_bottom = min(h, bottom + margin)
    else:
        crop_top, crop_bottom = 0, h
    cropped = gray[crop_top:crop_bottom, :]
    binary = flatten_and_binarize(cropped, blur_frac, bin_thresh)
    if despeckle_min_px > 0:
        binary = despeckle(binary, despeckle_min_px)
    return binary, (crop_top, crop_bottom)


def process_images(items, target_kb=TARGET_KB, widths=WIDTHS, **kw):
    """items: (PIL image, out_path) pairs of one document; one shared scale."""
    prepared = [prepare_image(im, **kw) for im, _ in items]
    paths = [p for _, p in items]
    saved = save_pages_under_budget([b for b, _ in prepared], paths, target_kb, widths)
    for path, (_, crop), (width, sz_kb) in zip(paths, prepared, saved):
        print(f"-> {path}  crop=({crop[0]},{crop[1]})  out_width={width}  size={sz_kb:.1f}KB")


def process_image(im, out_path, **kw):
    process_images([(im, out_path)], **kw)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="irspec tlc", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="a PDF (multi-page) or a single image (jpg/png/...)")
    ap.add_argument("--out-dir", default=None, help="directory for one PNG per page (PDF input)")
    ap.add_argument("--out", default=None, help="output PNG path (single-image input)")
    ap.add_argument("--pages", default=None, help="comma list of 1-based page numbers (PDF input, default: all)")
    ap.add_argument("--dpi", type=int, default=300, help="render DPI, same for every page (module docstring sec. 1)")
    ap.add_argument("--crop", choices=["none", "lines"], default=CROP_MODE,
                     help="'none' (default): no vertical crop, just binarize -- right for an "
                          "already-cropped-to-document source like an Adobe Scan PDF page. "
                          "'lines': crop tightly between the two detected reference lines -- "
                          "only for a raw, uncropped photo with real background/margin around "
                          "the plate (what this was originally reverse-engineered from); on an "
                          "already-tight source it will cut off real content, not background "
                          "-- see module docstring sec. 4")
    ap.add_argument("--margin-frac", type=float, default=MARGIN_FRAC)
    ap.add_argument("--line-frac", type=float, default=LINE_FRAC)
    ap.add_argument("--line-dark-thresh", type=int, default=LINE_DARK_THRESH)
    ap.add_argument("--blur-frac", type=float, default=BLUR_FRAC)
    ap.add_argument("--bin-thresh", type=float, default=BIN_THRESH)
    ap.add_argument("--despeckle-min-px", type=int, default=DESPECKLE_MIN_PX,
                     help="clear any connected dark blob smaller than this many pixels "
                          "(0 disables). Needs scipy -- see module docstring sec. 4")
    ap.add_argument("--target-kb", type=float, default=TARGET_KB)
    args = ap.parse_args(argv)

    opts = dict(crop_mode=args.crop, margin_frac=args.margin_frac, line_frac=args.line_frac,
                line_dark_thresh=args.line_dark_thresh, blur_frac=args.blur_frac,
                bin_thresh=args.bin_thresh, despeckle_min_px=args.despeckle_min_px,
                target_kb=args.target_kb)
    if args.input.lower().endswith(".pdf"):
        if not args.out_dir:
            sys.exit("PDF input needs --out-dir")
        if shutil.which("pdftoppm") is None:
            sys.exit("pdftoppm not found on PATH (poppler-utils)")
        pages = [int(p) for p in args.pages.split(",")] if args.pages else None
        os.makedirs(args.out_dir, exist_ok=True)
        process_images([(im, os.path.join(args.out_dir, f"plate-{num}_contour.png"))
                        for num, im in render_pdf_pages(args.input, args.dpi, pages)], **opts)
    else:
        if not args.out:
            sys.exit("image input needs --out")
        process_image(Image.open(args.input), args.out, **opts)


if __name__ == "__main__":
    main()

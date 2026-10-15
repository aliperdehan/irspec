#!/usr/bin/env python3
"""absorbance_to_transmittance.py -- convert an IR spectrum's y-axis between
Absorbance and %Transmittance for nulabreport figures.

WHY THIS EXISTS
    nulabreport's \\irspectrum / \\irspectrumcompare macros just plot whatever
    y-column a CSV gives them; they do not know or care whether that column
    is Absorbance or %Transmittance. When a report puts several reference
    spectra on comparable axes (this lab's own OMNIC exports are always
    %Transmittance, 0-100), a source that is natively Absorbance has to be
    converted on purpose -- silently mixing the two on one figure, or on
    stacked panels a reader will visually compare, misleads regardless of
    axis labels. This script does that conversion, once, in a place that
    documents the formula, rather than as an unrepeatable one-off snippet
    buried in a chat session.

    Do NOT convert the other direction (Transmittance -> Absorbance) as a
    way to "normalise everything to Absorbance" instead -- this lab's own
    instrument output and house convention are %Transmittance; Absorbance
    sources get converted to match, not the reverse. convert_series() below
    supports both directions for completeness (and because the algebra is
    symmetric), but the CLI defaults to --to transmittance for that reason.

THE FORMULA
    Absorbance and (fractional) Transmittance are related by the
    Beer-Lambert definition A = -log10(T), i.e. T = 10^(-A), where T runs
    0-1. This lab's %Transmittance convention is just T x 100:

        %T = 100 x 10^(-A)
        A  = -log10(%T / 100)

    Both directions are monotonic and well-defined for A >= 0 (equivalently
    0 < %T <= 100); A < 0 (%T > 100) can occur in noisy baseline data and is
    passed through the same formula rather than clipped, so a slightly
    negative-absorbance noise point becomes a slightly-over-100 %T point
    instead of silently disappearing.

INPUT / OUTPUT FORMAT
    Same "plain" CSV convention used everywhere else in this pipeline
    (spa_tool.py's write_plain_csv(), jdx_tool.py's decoded output): a
    one-line header "wavenumber,intensity" followed by comma-delimited
    rows, decimal point (not comma), ascending or descending wavenumber
    order preserved as given -- this script does not resort or resample,
    it only rewrites the intensity column in place.

USAGE
    python3 absorbance_to_transmittance.py IN.csv --out OUT.csv
    python3 absorbance_to_transmittance.py IN.csv --out OUT.csv --to absorbance

    IN.csv and OUT.csv may be the same path (the file is fully read before
    anything is written).

EXAMPLE (this report's actual use, 2026-09-18)
    literature/webbook/plain/PROPIOPHENONE.csv was decoded from the NIST
    Chemistry WebBook's native Absorbance .jdx (see
    literature/webbook/decode_notes.md) and left as Absorbance in an
    earlier pass of this report so as not to silently misrepresent the
    source. Once the report started stacking it directly against
    Transmittance curves in \\irspectrumcompare figures, the honest fix was
    to convert it, not just label it:

        python3 nulabreport/tools/absorbance_to_transmittance.py \\
            literature/webbook/plain/PROPIOPHENONE.csv \\
            --out literature/webbook/plain/PROPIOPHENONE.csv

    The original Absorbance values are not lost: they still live untouched
    in the raw source, literature/webbook/csv/PROPIOPHENONE.csv (semicolon-
    delimited, decimal-comma, as downloaded), which this script never
    reads or writes -- only the derived "plain" CSV is rewritten.
"""

import argparse
import csv
import math


def convert_series(intensities, to="transmittance"):
    """Convert a list of y-values between Absorbance and %Transmittance.

    to="transmittance": treats input as Absorbance, returns %Transmittance
        via %T = 100 * 10**(-A).
    to="absorbance":     treats input as %Transmittance, returns Absorbance
        via A = -log10(%T / 100).
    """
    if to == "transmittance":
        return [100.0 * (10.0 ** (-a)) for a in intensities]
    elif to == "absorbance":
        out = []
        for pct_t in intensities:
            if pct_t <= 0:
                raise ValueError(
                    f"%T value {pct_t!r} is <= 0; cannot take log10 for "
                    "Absorbance conversion"
                )
            out.append(-math.log10(pct_t / 100.0))
        return out
    else:
        raise ValueError(f"unknown --to target: {to!r}")


def read_plain_csv(path):
    with open(path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = [(row[0], float(row[1])) for row in reader if row]
    return header, rows


def write_plain_csv(path, header, wavenumbers, intensities, digits=4):
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for wn, inten in zip(wavenumbers, intensities):
            writer.writerow([wn, f"{inten:.{digits}f}"])


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("csv_in", help="input plain CSV (wavenumber,intensity)")
    ap.add_argument("--out", required=True, help="output CSV path (may equal csv_in)")
    ap.add_argument(
        "--to",
        choices=["transmittance", "absorbance"],
        default="transmittance",
        help="conversion direction (default: transmittance, i.e. input is "
        "treated as Absorbance)",
    )
    ap.add_argument("--digits", type=int, default=4, help="decimal places on output")
    args = ap.parse_args()

    header, rows = read_plain_csv(args.csv_in)
    wavenumbers = [wn for wn, _ in rows]
    intensities = [inten for _, inten in rows]

    converted = convert_series(intensities, to=args.to)

    write_plain_csv(args.out, header, wavenumbers, converted, digits=args.digits)

    label = "%Transmittance" if args.to == "transmittance" else "Absorbance"
    print(f"wrote {len(converted)} points to {args.out} ({label})")


if __name__ == "__main__":
    main()

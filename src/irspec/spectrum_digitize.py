#!/usr/bin/env python3
"""spectrum_digitize.py -- a mass spectrum or an NMR spectrum published only as a
picture -> CSV for \\labplot, plus a peak table.

Moved here from nulabreport's tools/spectrum_digitize.py (2026-11-14); the output is byte for byte what that script wrote.

    irspec spectrum ms  IMAGE --x-ticks FIRST:STEP --y-ticks FIRST:STEP \\
        --out NAME.csv [--peaks-out NAME_peaks.csv] [--list-out NAME.list] \\
        [--check "51,63,77,..."] [--labels N | --labels "51,77,..."] [--overlay check.png]
    irspec spectrum nmr IMAGE --show-rulers --overlay rulers.png
    irspec spectrum nmr IMAGE --x-ticks FIRST:STEP [--inset FIRST:STEP ...] \\
        --out NAME.csv --tex-out NAME.tex [--caption "..."] [--solvent 77.16] \\
        [--mhz 500 --protons 10 [--label-integrals]] [--inset-layout figure|separate] \\
        [--peaks-out NAME_peaks.csv] [--multiplets-out NAME_mult.csv] [--list-out NAME.list] \\
        [--check "167.5,145.0,..."] [--overlay check.png]

QUICK START (NMR), from the report's folder:
  1. --show-rulers --overlay rulers.png: the rulers found, numbered; the
     main one takes --x-ticks, inset n the n-th --inset.
  2. For each ruler type FIRST:STEP: the value of its first MAJOR (long)
     tick from the left, printed or not, and the step between majors. A
     CHECK line tells you when the first major has no number under it.
  3. Run with --out and --tex-out; look at --overlay (the value given to
     each major tick is printed on it); then in the report
         ```{=latex}
         \\input{nmr/NAME.tex}
         ```
     1H: add --mhz (the spectrometer's, for J) and --protons (the H count,
     for integrals as H); --multiplets-out writes the multiplet table.

Self-contained, like this folder's other tools: what a future session needs to
reproduce a conversion is in this docstring, not in a report's notes or in chat.
If you learn something new about an image layout, the fix goes here.

===============================================================================
1. WHAT THIS IS FOR
===============================================================================
Every CHEM212L report so far (LR1-2, LR4-5, LR6) has interpreted the
literature MS and NMR spectra the Palleros manual prints for each experiment.
Until now they were pasted in as PNGs and every number in the report's NMR/MS
tables was read off by hand, pixel by pixel (LR4-5/.notes/nmr_readout.md, the
read-out comments in LR6/parts/70-questions.md). This script does that
read-out from the figure's own axes and writes:

    --out        the trace as CSV for \\labplot:
                 ms:  'mz,intensity' -- one row per stick (integer m/z),
                      relative abundance in % of the y axis.
                 nmr: 'shift,intensity' -- the digitized trace, ppm
                      (descending, left to right as printed), intensity in %
                      of the tallest point of the trace.
                 An inset's trace goes to NAME_inset1.csv, ...
    --peaks-out  the peak table: ms 'mz,intensity,x_px,height_px';
                 nmr 'shift,height,clipped,solvent,axis' (height in % of
                 the tallest peak on its axis; clipped = the line runs off
                 the top of the figure, its height is a lower bound).
    --list-out   the \\labplot peak list, ready to paste (ms: the `apex`
                 form x/apex_y/label_y/name; nmr: the `fan` form, line 1 the
                 ymax it needs); it is printed as well.
    --tex-out    nmr: the whole \\labplot call, insets included, to \\input
                 (sec. 6); nothing to paste.
    --multiplets-out  1H: centre, range, multiplicity, J, integral, lines.
    (with --out, 1H) NAME_integrals.csv: the integral curves, as the book
                 draws them over the multiplets (sec. 4; --no-integral-curves
                 leaves them out).
Draw them with \\labplot[kind=ms]{csv}{list}{caption} or
\\labplot[kind=nmr, ymax=...]{csv}{list}{caption} (nulabreport v1.28.0+; the
inset= key that --tex-out uses, v1.28.2+; integrals=, v1.28.4+).

Input: the clean 1-bit crops palleros_figs.py writes (black ink on white).
Other figures work if they have the same anatomy (below).

===============================================================================
2. CALIBRATION (both kinds): the tick marks, never the printed numbers
===============================================================================
An axis is a line with tick marks hanging off it: below a horizontal axis,
left of a vertical one. A tick is a run of columns (rows) whose ink continues
straight out of the line, at least 3 px long and no wider than --tick-width
(default 16: Fig. 15.5's thick-pen y ticks are 14 px; the scan leaves a 1-3 px
gap between some ticks and their axis, which is bridged).

The tick GRID is found before anything is numbered (regular()): the spacing
and phase that put the most marks within 0.35 of a spacing of a grid line,
refitted by least squares so the scan's jitter does not throw marks off it
(Fig. 22.12a: marks 7-10 px apart for a nominal 8.5). Marks off the grid are
dropped and reported: a label glyph touching the axis (Fig. 15.5's '100'
block), the foot of a thick stick poking through it. Two marks on one grid
line: the closer one is kept. Every tick carries its grid index from then on,
so a tick lost to the scan never shifts the values after it.

Major ticks are found by PERIOD (split_major()): the ticks at every P-th grid
place (P = 2..12, any phase) that are longest on average against the rest, by
at least 3 px. A ruler can have three overlapping lengths -- Fig. 22.5's are
5-6, 8-10 and 11-15 px, every 2, 10 and 20 ppm -- and the labelled ones are
the longest. If none stands out (Fig. 22.12a: one 5-6 px tick per m/z), every
tick is major. Calibration keeps this detected period even when major marks
are missing; gaps between surviving majors can span several periods.

  --x-ticks FIRST:STEP  value of the first (leftmost) MAJOR tick and the change
                        per major tick: 200:-20 for an NMR ruler whose first
                        long tick is 200 ppm, 40:20 or 51:1 for an m/z axis
                        (Fig. 22.12a's '50' stands at the y axis line, which
                        has no tick mark of its own: the first mark is 51.
                        On an axis with a tick per m/z an off-by-one FIRST
                        comes out the same -- the alignment below shifts
                        the other way -- checked: 50:1 and 51:1 give
                        identical sticks.)
  --y-ticks FIRST:STEP  ms: value of the BOTTOM major tick and the change per
                        major tick upwards, e.g. 0:10 or 0:20.

Values are given, never read: the plotter fonts and the JBIG2 scan defeat
OCR (labels come out as black boxes: Fig. 21.10's 100/80/40/0), and labels
can sit offset from their own ticks (Fig. 15.5's '40' is centred ~30 px right
of its tick; the sticks agree with the TICKS, as --check confirms). Look at
the figure, find the first long tick's label (it is often UNLABELLED: the
rulers of Figs. 15.4 and 21.19 start with an unlabelled 180, Fig. 21.22's
with 160), and say it. The overlay draws the value the script gave every major
tick: READ IT BACK -- a wrong FIRST shifts every value by a whole STEP, and
nothing else in the run can tell (2026-10-11: three of nine 13C figures were
first run with 200:-20 and came out exactly 20 or 40 ppm high).

Fit: each tick's value is FIRST + its grid offset from the first major x STEP
/ (grid steps per major), and a straight line value = a*px + b is fitted
through ALL ticks; its rms and largest residual are printed. Over 0.25 of a
tick step is a warning, over 0.4 stops the run (a mis-numbered tick is off by
half a step or more). The crops' non-square pixels (palleros_figs.py, 2.6 %)
do not matter to a per-axis fit.

===============================================================================
3. MS (Palleros Figs. 15.5, 22.12, ...)
===============================================================================
Anatomy: an L (or a box) of axis lines; the x axis is the lowest long row,
the y axis the leftmost long column (sticks can be longer than 40 % of the
height too, so it is the leftmost); a box's right frame line is not a stick.
The figure is levelled on the x axis first (ir_digitize.deskew_by_xaxis).

Sticks are runs of columns with ink straight up from 2 rows above the x axis
line. Where neighbours touch at their feet (Fig. 15.5's thick pen: 42/43/44,
the 80/81 pair, 137/138 are solid blocks 18-20 px wide) the block is split by
raising the height threshold until each piece is stick-wide, and what is left
of the block once the taller piece is taken, if at least 0.35 m/z wide, is
split on its own (the shorter partner of a fused pair). Each stick is then
followed upwards in its own columns (they may move a column at a time; in a
row fused with a neighbour the edge on that side stays put -- else 138 crept
onto 137), bridging scan gaps of up to --max-gap rows (Fig. 22.12a's 51 is
broken twice). It stops where ink runs more than 3 px past the stick and does
not stand on the axis: a label printed touching the stick's top (Fig. 15.5:
'43', '53', '109', '137', '179' all touch), as opposed to a neighbour, whose
columns stay dark for the next 30 rows down. Position: the median centre of
the stick above its foot. Height: the y axis value at its top (Fig. 15.5 draws
its 0 tick 11 px above the axis line; the TICKS are the scale).

Alignment: sticks stand on integer m/z, so the tall sticks' fractional m/z is
the plotter's pen-to-tick offset (Fig. 22.12a: 0.50 m/z = 4 px, half a tick
step). Near 0.5 the direction is ambiguous and --check decides it: the shift
that makes the most printed labels local-maximum sticks. Then scale and offset
are refitted by least squares on the sticks over 20 % (weighted by height)
against their integers, and every stick is re-rounded (Fig. 15.5's sticks are
placed unevenly, +-3 px; the refit moved 180 off 181). The distance of each
stick over 5 % from its integer is printed: over 0.3 is a warning.

--labels N picks the N tallest local maxima (taller than every stick within 3
m/z); --labels "51,77,..." names them. --check "51,63,..." gives the m/z
values PRINTED on the figure: each must be a stick and a local maximum.

===============================================================================
4. NMR (Palleros Units 15, 21, 22: 13C validated; 1H uses the same rulers)
===============================================================================
Anatomy: the trace, then BELOW it and separated from it a ppm ruler (a line
with ticks hanging under it, labels under those). Expansion insets have their
own shorter ruler higher up (Fig. 21.10). No y axis.

Levelling: on the main ruler, the lowest long line (level_by_ruler) -- not on
the row with the most ink, which on an NMR figure can be the noisy baseline.
Even then a scan is not flat, so each ruler's top edge is FOLLOWED column by
column from the middle of its longest run, both ways, a row per column at
most, bridging breaks of up to 60 px (Fig. 21.10's inset ruler drops 3 px over
its length; Fig. 21.16's main ruler rises 3 px in its last 300 px; Figs. 21.4,
21.7, 21.16 have no unbroken run over half their length). The span is every
stretch of 40 px or more on the line, whatever the gap: a span cut short at a
blotted label would renumber every tick. Ticks hang from the line's own
bottom edge. A 1H spectrum's flat baseline is a long line too, but nothing
hangs under it.

--inset FIRST:STEP, one per inset ruler, top to bottom, calibrates each inset
like --x-ticks. An inset ruler found without one is reported and skipped.

Trace: the ink above each ruler, within its span (the main axis leaves out
each inset's box). The biggest blob is the trace (the baseline noise joins it
into one); other blobs join it only when they lie within 8 rows of it in the
same columns -- the top of a thin line the scan broke off -- and not when they
stand further off, as label leaders do (Fig. 21.16's '19.22' leader ends 180
px above its line and was read as a peak at 17.3 ppm before this rule). Text,
arrows and specks are nowhere near the trace. Each column's whole ink extent,
less half a pen at each end, is written as two points (envelope_trace), so a
peak tip is kept and a broken line is bridged.

Peaks: local maxima of the top edge at least --min-height px above the
baseline (default 6 x the noise, at least 8 px), rising at least half that
above the lower side within 25 px (keeps the second line of a close pair).
Baseline = median of the trace's centre; noise = 1.4826 x MAD of its top
edge. POSITION is taken near the line's FOOT, not its apex (follow_down: the
line followed down to 15 % of its height, at least 12 px above the baseline,
its centre held where it merges with a neighbour): scanned lines bend, and the
ruler is just under the baseline. Fig. 21.16's tall camphor lines run x
2015-2017 at the top and 2010-2012 near the baseline; read at the apex they
came out 0.4-0.6 ppm low, at the foot they match the figure's own printed
19.85/19.22 to 0.02. A line whose top reaches the region's top (within 3 px)
is CLIPPED: its height is a lower bound and its position is read from 12 px
below the cut down.

--solvent PPM (e.g. 77.16 for CDCl3 in 13C, 7.26 in 1H; 39.5 / 2.50 for DMSO-d6)
marks as solvent the peaks within --solvent-window (default 0.5 ppm for 13C,
0.05 for 1H) of the line nearest PPM -- centred on the line the figure shows,
not on PPM, because figures are offset (Fig. 21.10 prints CDCl3 at 77.5-77.8)
and a window wide enough for that around 77.16 also took benzhydrol's CH-OH
line at 76.2 (Fig. 21.7) as solvent. Solvent lines stay in the peak table, get
one mark (below) instead of shift labels, and their offset from PPM is printed (REPORTED, never
applied: the read-out notes found TMS/CDCl3 off by up to 0.7 ppm on some
figures).

Labels (the `fan` style of nulabreport.sty's nmr kind): every non-solvent
main-axis peak gets a rotated \\scriptsize label. Labels closer than --pitch
(default 3.8 mm: the label is 9 pt = 3.2 mm across, and at 3.3 mm, the first
release's pitch, a fanned group read as crowded in review) on a --plot-width cm
axis (13.5: \\labplot) are pushed apart as a group, centred on their lines.
--label-style:
    follow (default since v1.28.1, asked for in review "like the IR labels"):
           each group at its own height, 4 % above the highest point of the
           trace under its lines and labels; a lone line's label stands
           straight over it, a group's leaders rise to a knee 2 % above the
           cluster and slant out to labels 4 % higher.
    top    (v1.28.0): all labels on one level 10 % above the tallest line,
           as a spectrometer prints them.
Printed as x/apex_y/knee_y/label_x/label_y/text with the ymax the call needs
(the highest label's foot + 14 %); --list-out writes the options and the list
to a file.

The solvent is marked once, at the centre of its lines (the review of v1.28.0
found the mark missing: the book prints "solvent" with an arrow).
--solvent-style:
    arrow  (default) the book's own mark: the text (--solvent-label, default
           "solvent"; CDCl$_3$ works) upright over an arrow to the line's top.
           The entry's knee_y is empty, which the package draws as a callout.
           Its place is the first of 4-12 mm right of the line, then left,
           where the text clears the trace and every other label and leader;
           else lifted over them (Fig. 21.7: benzhydrol's CH-OH line at 76.5
           stands 0.9 ppm from the solvent's, and the first try sat on its
           label).
    label  a rotated label like the others, fanned with them.
    none   no mark (the line is still drawn and kept in the peak table).
The book does not mark every solvent line, and nothing in the picture says
which it marks: it marks Fig. 21.15's (2 % of the tallest line) and 15.3's
(9 %) and leaves 22.4's (1 %) and 21.3's (2 %) alone. Match the figure with
--solvent-style none (v1.28.3; the 22.4 demo had a mark the book has not).
1H: the line nearest --solvent within 0.04 ppm, not under an integral (Fig.
15.3's reads 7.28 and was missed at 0.02).

--tms (default 0) does the same for the reference line: a TMS line within
0.5 ppm (13C; 0.05 on a 1H axis) of the line nearest 0 is kept in the table,
left out of the labels and its offset printed (Fig. 21.4's reads +0.3).

--check "167.5,145.0,..." takes shifts read or printed elsewhere: each is
matched to the nearest peak (on an inset if one covers it, else the main axis)
and the difference printed; over --check-px (default 3 px, what a hand
read-out is good to) is a miss.

Resolution is the image's: a 13C main ruler of 200 ppm over ~2400 px is
~0.08 ppm per px; two lines closer than ~3 px (0.25 ppm) merge.

1H (v1.28.2). A 1H figure draws an integral curve over each multiplet, and
the curve runs up the multiplet's own lines, so the main axis is read in steps
(integrals are looked for only on a main axis under 30 ppm: a 13C figure has
none, and Fig. 21.16's label bracket was taken for one):
  - find_integrals(): the hook-and-flat style (Figs. 22.4, 21.6, 21.12): thin
    horizontal strokes above the baseline (6 pens clear of it) are hooks
    (free left end) and flats (free right end); a flat pairs with the
    nearest unused hook to its left, at least 15 px lower (an S-curve's top
    curl is a "flat" and a "hook" 5 px apart), that ink joins it to. A thin
    horizontal stroke between them is a plateau: one integral per step.
  - find_curve_integrals(): the rest -- smooth S-curves (Figs. 21.18, 21.21),
    arcs (21.15), integrals that do not touch the trace (21.6's OH: loose
    pieces 15 px+ each way, thin, rising to the right join the search).
    stroke_ends() finds free ends (one arc of ink on a 6-px ring); a lower end
    leaves right/up (-30..80 deg), an upper one left/down (150..262; a line's
    apex leaves at ~270). From each lower end, ink_reach() searches up and
    40 px down; the HIGHEST upper end it reaches is the other end (a line's
    apex beside the curve can look like one), and the way back is the curve.
    A path both straight (< 6 % off its chord) and slanted (< 70 deg) is a
    drawn line, not an integral (Fig. 15.3's "solvent" arrow). An upper end
    left over (its lower end runs into a line: 21.15's arcs) is followed down
    row by row until it widens past two pens.
  - split_plateaus(): a curve that rises in steps is one integral per step
    (21.15's three methyl singlets in one curve; 21.12's aromatic 2.3 | 4.2,
    as the hand read-out split it). Between steps the curve is gentle, not
    level (~1 row a column against 70+); a gentle run of 5+ columns with steep
    ones both sides is a plateau. Not a split if the steps' rises are under
    0.04 ppm apart, or under 20 Hz with --mhz (a doublet's halves: Fig. 21.9's
    PhCH= at 250 MHz rests 20 px between its lines); steps under 15 px merge.
  - strip_integrals(): all of them out of the trace (the path +- pen/2 + 2,
    8 px round a curve's ends, and the slivers left inside its box); a line's
    top above an integral's flat is kept.
  - multiplets(): integrals over the same lines once (the larger); a TMS or
    solvent integral dropped; the lines under each rise (+- 8 px, lines under
    8 % of the group's tallest are noise) are one multiplet, from an inset that
    holds all its main-axis lines (lines just outside that continue its own
    spacing join, unless inside another group's window), else the main axis;
    two clipped "lines" a few px apart are one flat top. 2-4 evenly spaced
    lines (J 2-20 Hz) are d/t/q, one s, none "br s" (Fig. 21.18's COOH), else
    m. Integrals as H with --protons, else relative to the smallest.
  - The 1H solvent: within 0.02 ppm and never under an integral (Fig. 21.6's
    para-H lines at 7.29/7.31 were taken for CHCl3).
  - integral_curves() (v1.28.4): the curves drawn back, as the book draws
    them, to NAME_integrals.csv (the curves one after another, a nan row
    between) and the integrals= key of --tex-out: a hook-and-flat integral
    as its hook (each column's mean row), its rise as strip_integrals
    followed it and its flat; a curve integral as its ink path; each
    simplified to within 0.75 px (Ramer-Douglas-Peucker). Without them the
    main axis misled: the lines under a rise end where the rise starts
    (Fig. 22.4's 3 H group at 7.38 stood lower than the 1 H doublet at 7.71);
    with the rise drawn over them they look as the book's do. Only when no
    axis had integral ink drop_floating took out (Figs. 21.9 and 15.3: the
    curves would be broken pieces; the run says why it leaves them out);
    --no-integral-curves leaves them out anyway. The labels keep clear of
    them (they join the trace the labels are placed over), and ymax covers
    them. Drawn blue on --overlay.
The noise and baseline are read from the FLAT columns only (an inset filled by
one multiplet put the median of all columns half way up its lines).

Validated 2026-10-11 on copies of the nine Palleros 1H figures in the CHEM212L
reports, against the hand read-outs on file (step px; hand in brackets):
    Fig. 22.4 (LR6, 500 MHz)  7.71 d J 15.8 Hz 268 [268], 7.53-7.51 m 566 [567],
        7.39-7.37 m 807 [808], 6.45 d J 16.0 276 [277], 3.82 s 864 [864]: as H
        of 10, 0.96/2.04/2.90/0.99/3.11 [0.96/2.04/2.90/0.99/3.10].
    Fig. 21.6 (500 MHz)  aromatic 654 + 168 = 822 [818, split by area 8.3 : 1.7
        -- here by its plateau, 8.05 : 2.07 H], CH 72 [74], OH 80 [80].
    Fig. 21.12 (500 MHz)  CHO 134, vinyl 141 [138 per H]; aromatic 312 | 597
        [2.3 | 4.2 H at 138 = 317 | 580].
    Fig. 21.9 (250 MHz)  aromatic 788 + 338 = 1126 [1116.5], PhCH= 213 d J 15.4
        [216.8, 16.3], CH2 432 [430.2], OH 278 [287]; =CH reads 394 [225.8]: wrong.
        Its integrals are drawn THROUGH its aromatic and vinyl insets; v1.28.2
        traced them there as solid bars, v1.28.3 drops them (drop_floating:
        thin pieces floating over the spectrum that only rise). Short pieces
        wedged between two close lines still show; the =CH integral's top
        end lies inside the vinyl inset's box, hence its wrong 394.
    No read-out on file: 21.3 (no integrals), 21.15 (methyls 3.24/3.02/3.30 H,
        each CH 0.9-1.1 H, one 1.80 group at 0.46), 21.18 (COOH 1.66 : ArH
        4.34, the figure's own), 21.21 (four ArH 0.91-1.01, NH2 2.13), 15.3
        (NH 0.86, ArH 1.71/1.86, CH2 2.07, CH3 3.14/3.09; a 0.27 H group at 1.97
        on two impurity bumps).
    Redraw check: 9 of 9 pass since v1.28.3 (v1.28.2: 7; 21.9, above, and
    15.3, a dashed piece of its 6.83 integral between 7.07 and 6.90 ppm drawn
    as a bar, failed).
    Fig. 21.18's 8.04 line is drawn no taller than its TMS: the book's
    integral climbs straight up over the line from 20 % to 90 % of the
    height, and the line's top cannot be told from the integral's stroke (a
    try that put the stretch back stretched one line of Fig. 22.4's 6.45
    doublet to its integral's top). Its height is unknown, not small. Since
    v1.28.4 the integral is drawn over it, as in the book.
    Integral curves drawn (v1.28.4): 22.4, 21.6, 21.12, 21.15, 21.18, 21.21;
    not 21.9 and 15.3 (ink left out by drop_floating); 21.3 has none. The
    labels moved by them: 21.6's 2.31 (upright, between its integral and the
    inset over it), 21.18's two and 21.21's 4.00 (over their integrals).

Rulers (--show-rulers numbers them; --inset FIRST:STEP in that order: rows of
insets top to bottom, each row left to right):
  - Two insets side by side are two rulers even where the gap between them is
    bridged like a scan break: at every gap of 12 px+ the ruler is cut where
    the ticks either side differ in spacing (> 10 %) or phase (> 0.3), and,
    above the main ruler, at any gap of 20 px+ (Fig. 21.15's 1.95 and 1.85
    insets share one grid, 28 px apart).
  - A ruler needs 5 regular ticks (Fig. 21.9's insets carry 5). If fewer
    inset rulers than --inset are found, the tool looks again with shorter
    rulers (--ruler-frac down to 0.05: Fig. 22.4's second inset is 14 % of
    the width) and then with as few as 2 ticks (Fig. 21.9's CH2 inset has only
    its 4.4 and 4.3), warning that a 2-tick ruler cannot be checked.
  - label_guard(): CHECK when a ruler's first major tick has no number printed
    under it -- the trap behind four wrong scales (Figs. 21.19, 21.22, 15.4,
    and 22.4's main axis start at an unlabelled 180/160/10).

The drawn trace (--out) is the centreline of near-vertical strokes (hthin():
horizontal runs up to 2 pen + 2 px kept as their middle pixel), so a line
does not come out as a filled block when an inset is drawn full width; peaks
are still read from the unthinned ink (the 13C peak lists did not change).

===============================================================================
5. VERIFICATION printed every run, and what it was validated against
===============================================================================
  a. calibration: tick counts, major spacing, fit residual rms and max (px).
  b. trace (nmr): redraw recall/precision as ir_digitize.py (>= 0.98).
  c. ms: integer-m/z distance of every stick over 5 %.
  d. --check, as above. Exit status 2 if a check fails or the trace check
     does; 1 if calibration fails.
  e. --overlay PATH: the levelled image with the ticks found (blue, major
     ticks labelled with the value assigned), the trace or sticks (red) and
     the peaks (green; solvent orange). LOOK AT IT before trusting a number.

Validated 2026-10-11 on copies of every Palleros MS/13C figure in the CHEM212L
reports (LR1-2, LR4-5, LR6):
    MS  Fig. 22.12a (LR6)  7/7 printed m/z found as local maxima; 58 sticks;
                           heights match the figure (51 74 %, 77 97 %, 103 100 %)
        Fig. 15.5 (LR1-2)  7/7; 87 sticks incl. the fused 80/81 and 137/138
    13C against the hand read-outs on file (|d|, ppm):
        Fig. 22.5  (LR6 nmr-c.csv)      8/8 within 0.11
        Fig. 21.13 (nmr_readout.md)     8/8 within 0.11
        Fig. 21.10 inset                6/6 within 0.02; main 63.5 vs 63.4
        Fig. 21.4                       3 within 0.2; the two clipped lines
                                        +0.24, +0.41
        Fig. 21.7                       4 within 0.26; the two clipped lines
                                        +0.32, +0.37
        Fig. 21.16 printed labels       19.85 -> 19.84, 19.22 -> 19.24
    On clipped lines the figure has no apex to read; the hand read-outs took
    the flat top, this tool the line below the cut. The figure cannot say
    which is right, so it was checked against published benzophenone shifts:
    Xu et al., Molecules 2023, 28, 3031, compound 4f (open access, read
    2026-10-11: https://mdpi-res.com/d_attachment/molecules/molecules-28-03031/
    article_deploy/molecules-28-03031.pdf): 13C (101 MHz, DMSO-d6) 196.6,
    137.4, 132.3, 129.9, 128.1. DMSO-d6, not the figure's CDCl3, so this is
    weak evidence; two RSC supporting-information files that a web search
    said give CDCl3 values (196.7, 137.5, 132.4, 130.0, 128.2) returned 404
    and were NOT read. Against Xu: the tool's unclipped lines read 196.9,
    137.7, 132.5, i.e. the figure runs ~0.2-0.3 high; its clipped lines read
    130.1 and 128.3, the same offset; the flat-top read-outs, 129.7 and
    128.1, are 0.4 and 0.2 under where that offset puts them. So: below the
    cut, kept, and flagged '*' in the table.
    Figs. 21.19, 21.22, 15.4 have no read-out on file.

===============================================================================
6. THE BOOK'S LAYOUT: --tex-out and --inset-layout (v1.28.2)
===============================================================================
--tex-out writes the whole \\labplot call. --inset-layout figure (the
default, at the author's request) draws each inset INSIDE the plot where the
book has it, with nulabreport's inset={csv, box, peaks, options} key:
  - box: the inset ruler's ends, mapped through the MAIN calibration, and its
    bottom on the inset's ruler line, top as high as its own labels need, in
    the main axis' units (ppm across, % of the main axis' tallest line up);
  - options: its own x range (its ruler's ends), y range (ymin puts its
    ruler where the book has it), xtick (its calibrated majors);
  - the plot keeps the figure's proportions: the main axis is --plot-width cm
    wide (scale only axis) and as tall as the same px-to-cm scale makes it,
    capped at 18 cm, so every axis shares one mm scale and label sizes,
    gaps and rises (fan_labels/callout `unit`) are set per axis in mm;
  - a line or multiplet an inset shows is labelled in the inset only; main
    labels clear each inset box and the ~5 mm of tick labels under it, or,
    if a rotated one would not fit under it, go upright just over their line,
    or beside its top on a short arrow (Fig. 21.10's 63.5), or over the inset.
  - label length follows its text (1.4 mm a character + 1 mm): '7.38 (3H)'
    (--label-integrals) is twice a bare number.
--inset-layout separate: the main plot and one \\labplot per inset.
CSV paths in the call are written as given to --out: run from the report's
folder with paths relative to it. The first line of the file is the command.

Needs numpy and Pillow; imports ir_digitize.py (same folder) for the shared
image helpers.
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .ir_digitize import (_runs, components, deskew_by_xaxis, dilate,  # noqa: E402
                         redraw)


class CalibrationError(Exception):
    pass


# ---------------------------------------------------------------------------
# ticks and axes
# ---------------------------------------------------------------------------
def tick_profile(d, edge, lo, hi, outward, maxlen=60, slack=0):
    """Length of the ink run continuing straight out of a horizontal line, per
    column lo..hi. `edge` is the first row past the line on the tick side;
    outward +1 = down (ticks below), -1 = up. With slack > 0 the run may
    start up to that many px past the edge (counted in its length): the scan
    leaves a 1-2 px gap between some of Fig. 15.5's y ticks and their axis."""
    if outward > 0:
        sub = d[edge:edge + maxlen, lo:hi + 1]
    else:
        sub = d[max(edge - maxlen + 1, 0):edge + 1, lo:hi + 1][::-1]
    if sub.shape[0] == 0:
        return np.zeros(hi - lo + 1, int)
    best = np.zeros(sub.shape[1], int)
    for s0 in range(0, slack + 1):
        part = sub[s0:]
        if part.shape[0] == 0:
            break
        L = np.where(part.all(0), part.shape[0], part.argmin(0))
        L = np.where(L > 0, L + s0, 0)
        best = np.maximum(best, L)
    return best


def find_ticks(lens, offset, maxw=12, minlen=3):
    """-> list of (centre px, length) of runs of columns with lens >= minlen
    and no wider than maxw (wider is text, a filled block, or the other axis)."""
    out = []
    for a, b in _runs(np.where(lens >= minlen)[0]):
        if b - a + 1 <= maxw:
            out.append(((a + b) / 2 + offset, int(lens[a:b + 1].max())))
    return out


def split_major(ticks):
    """-> (majors, minors, period). Majors are the ticks at every P-th place on the
    tick grid (ticks carry their grid index, regular()) that stand out
    longest: the period and phase whose ticks are longest on average against
    the rest, by at least 3 px. By period, not by a length cut-off, because a
    ruler can have three lengths that overlap: Fig. 22.5's ppm ruler has
    5-6 px ticks every 2 ppm, 8-10 px every 10 and 11-15 px every 20 (the
    labelled ones). Fig. 22.12a's 5-7 px y ticks are one class: all major."""
    L = np.array([t[1] for t in ticks], float)
    K = np.array([t[2] for t in ticks])
    best = (3.0, None)
    for P in range(2, 13):
        for ph in range(P):
            on = (K - ph) % P == 0
            if on.sum() < 2 or (~on).sum() < 1:
                continue
            diff = L[on].mean() - L[~on].mean()
            # a longer period must beat a shorter one clearly (P=10 over P=5:
            # 7 px against 5.5 on Fig. 22.5)
            if diff > best[0] + 0.5:
                best = (diff, (P, ph))
    if best[1] is None:
        return ticks, [], 1
    P, ph = best[1]
    return ([t for t in ticks if (t[2] - ph) % P == 0],
            [t for t in ticks if (t[2] - ph) % P], P)


def regular(ticks, what, report):
    """Keep the marks on the axis's tick grid; drop the rest. Other ink can
    reach the tick zone: a label glyph touching the axis line (Fig. 15.5's
    '100' block, 34 px above the real 100 tick) or the foot of a thick stick
    poking through the x axis (Fig. 15.5, five of them, 0.3-0.4 of a spacing
    off the grid; they are also only 2 px long, under find_ticks' 3). For
    each candidate spacing and starting mark the grid is refitted (least
    squares through the marks within 0.35 of a spacing of it, three times)
    so a scan's jitter (Fig. 22.12a: marks 7-10 px apart for a nominal 8.5,
    up to 0.3 of a spacing off a straight line) does not throw marks off it.
    Two marks on one grid line: the closer one is kept (Fig. 15.5's '100'
    block sits 0.24 of a spacing from the 100 tick). Score: marks on the grid, less
    half a point per grid line inside their span with no mark (so half the
    true spacing, which would also take the stray marks, scores lower)."""
    if len(ticks) < 4:
        return ticks
    p = np.array([t[0] for t in ticks])
    cand = set()
    for k in (1, 2):
        for v in p[k:] - p[:-k]:
            if v > 3:
                cand.add(round(float(v) * 2) / 2)
    best = None
    for m in sorted(cand):
        for ph in p:
            mm, pp = m, ph
            for _ in range(3):
                r = (p - pp) / mm
                k = np.round(r)
                on = np.abs(r - k) <= 0.35
                if on.sum() >= 3 and len(set(k[on])) >= 2:
                    mm, pp = np.polyfit(k[on], p[on], 1)
            r = (p - pp) / mm
            k = np.round(r)
            on = np.abs(r - k) <= 0.35
            for kk in set(k[on]):
                same = np.where(on & (k == kk))[0]
                if len(same) > 1:
                    keep = same[np.argmin(np.abs(r[same] - kk))]
                    on[same] = False
                    on[keep] = True
            hits = int(on.sum())
            if hits < 2:
                continue
            filled = len(set(k[on].astype(int)))
            lines = int(k[on].max() - k[on].min()) + 1
            score = hits - 0.5 * (lines - filled) - 0.5 * (hits - filled)
            if best is None or score > best[0] + 1e-9:
                best = (score, mm, on, k)
    _, m, on, k = best
    for t, keep in zip(ticks, on):
        if not keep:
            report.append(f"  {what}: mark at {t[0]:.0f} px is off the tick grid ({m:.1f} px), dropped")
    k = k - k[on].min()
    return [(t[0], t[1], int(kk)) for t, keep, kk in zip(ticks, on, k) if keep]


def parse_fs(spec, what):
    try:
        a, b = spec.split(":")
        return float(a), float(b)
    except (ValueError, AttributeError):
        raise CalibrationError(f"{what} expects FIRST:STEP, e.g. 180:-20 (got {spec!r})")


def calibrate(ticks, spec, what, report, reverse=False):
    """ticks: (pos, len) along the axis. spec FIRST:STEP for the majors
    (reverse=True: counted from the END, for a y axis whose first value is
    the bottom tick). Every tick gets the value of its place on the tick grid
    (regular()), and a straight line value = a*px + b is fitted through all
    of them. -> a, b, [(major px, value)], worst residual (px)."""
    first, step = parse_fs(spec, what)
    ticks = regular(sorted(ticks), what, report)
    if len(ticks) < 2:
        raise CalibrationError(f"{what}: found {len(ticks)} ticks (need 2); cannot calibrate")
    if len(ticks[0]) < 3:                       # fewer than 4 marks: no grid fit
        ticks = [(t[0], t[1], i) for i, t in enumerate(ticks)]
    majors, minors, gstep = split_major(ticks)
    if not minors:
        report.append(f"  {what}: all {len(ticks)} ticks are one length ({min(t[1] for t in ticks)}-"
                      f"{max(t[1] for t in ticks)} px): FIRST:STEP applies to EVERY tick")
    if len(majors) < 2:
        raise CalibrationError(f"{what}: found {len(majors)} major ticks (need 2); ticks at "
                               f"{[round(t[0]) for t in ticks]}, lengths {[t[1] for t in ticks]}")
    # Values by place on the grid, not by order: a tick lost to the scan (or
    # dropped as off the grid) must not shift every value after it by a step.
    gk = np.array([t[2] for t in majors])
    # Keep split_major's period: gaps between surviving majors can span
    # several periods when a mark is missing, even with a perfect fit.
    k0 = gk[-1] if reverse else gk[0]
    sub = step / gstep
    allp = np.array([t[0] for t in ticks], float)
    allk = np.array([t[2] for t in ticks], float)
    allv = first + (k0 - allk if reverse else allk - k0) * sub
    a2, b2 = np.polyfit(allp, allv, 1)
    res = (allv - (a2 * allp + b2)) / a2
    worst = float(np.abs(res).max())
    rms = float(np.sqrt(np.mean(res ** 2)))
    mp = np.array([t[0] for t in majors])
    mv = first + (k0 - gk if reverse else gk - k0) * sub
    sp = np.diff(mp)
    report.append(f"  {what}: {len(ticks)} ticks ({len(majors)} major, {gstep - 1} minor between majors), "
                  f"major spacing {sp.mean():.1f} px = {abs(step):g}; "
                  f"{abs(a2):.5f} per px; fit residual rms {rms:.2f}, max {worst:.2f} px")
    # A tick given the wrong value is off by half a step or more; the scan's own
    # jitter (Fig. 22.12a: ticks 7-10 px apart, nominally 8.5) stays near 0.3.
    pxstep = abs(sub / a2)
    if worst > 0.25 * pxstep:
        report.append(f"  WARNING {what}: worst tick {worst:.1f} px off the line "
                      f"({worst / pxstep:.2f} of a step)")
    if worst > 0.4 * pxstep:
        raise CalibrationError(f"{what}: a tick is {worst:.1f} px off the fitted scale "
                               f"({pxstep:.1f} px per tick step) -- a misidentified tick? "
                               f"Look at the overlay.")
    return a2, b2, list(zip(mp, mv)), worst


def long_rows(d, frac):
    """Rows whose longest continuous ink run is at least frac of the width,
    grouped into lines -> [(row_top, row_bottom, col_lo, col_hi)]."""
    h, w = d.shape
    rows = []
    for r in range(h):
        rs = _runs(np.nonzero(d[r])[0])
        if rs:
            a, b = max(rs, key=lambda t: t[1] - t[0])
            if b - a + 1 >= frac * w:
                rows.append((r, a, b))
    out = []
    for r, a, b in rows:
        if out and r - out[-1][1] <= 2 and min(b, out[-1][3]) - max(a, out[-1][2]) > 0.5 * (b - a):
            t, _, lo, hi = out[-1]
            out[-1] = (t, r, min(lo, a), max(hi, b))
        else:
            out.append((r, r, a, b))
    return out


# ---------------------------------------------------------------------------
# overlay
# ---------------------------------------------------------------------------
def _font(size):
    for f in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def fmt(v, nd):
    return f"{v:.{nd}f}".rstrip("0").rstrip(".") if nd else f"{v:.0f}"


# ---------------------------------------------------------------------------
# MS
# ---------------------------------------------------------------------------
def cmd_ms(args):
    if not args.x_ticks:
        raise CalibrationError("ms needs --x-ticks FIRST:STEP")
    report = []
    grey = np.array(Image.open(args.image).convert("L"))
    grey = deskew_by_xaxis(grey, report)
    d = grey < args.threshold
    h, w = d.shape
    rows = _runs(np.where(d.sum(1) > 0.5 * w)[0])
    cols = _runs(np.where(d.sum(0) > 0.4 * h)[0])
    if not rows or not cols:
        raise CalibrationError("no x axis (a row dark over half the width) or y axis (a column over 40%)")
    xt, xb = rows[-1]
    yl, yr = cols[0]
    # the x axis runs from the y axis to its last dark column on that row
    xr = int(np.nonzero(d[(xt + xb) // 2])[0].max())
    report.append(f"axes: x line rows {xt}-{xb} (to col {xr}), y line cols {yl}-{yr}")

    # x ticks below the x axis, clear of the y axis
    lens = tick_profile(d, xb + 1, yr + 4, xr, +1, slack=2)
    xticks = find_ticks(lens, yr + 4, maxw=args.tick_width)
    ax_, bx_, xmaj, xres = calibrate(xticks, args.x_ticks, "x (m/z)", report)
    # y ticks left of the y axis, from the top frame (if any) down to the x axis
    top = rows[0][1] + 3 if len(rows) > 1 else 0
    lens = tick_profile(d.T, yl - 1, top, xt - 1, -1, slack=3)
    yticks = find_ticks(lens, top, maxw=args.tick_width)
    # the x axis itself is the bottom tick when no tick mark is drawn there
    # (Fig. 22.12a); Fig. 15.5 draws its 0 tick 11 px ABOVE the axis line
    if not yticks or yticks[-1][0] < xt - 15:
        L = max(t[1] for t in yticks) if yticks else 8
        yticks.append(((xt + xb) / 2, L))
    ay_, by_, ymaj, yres = calibrate(yticks, args.y_ticks, "y (%)", report, reverse=True)

    # sticks: ink continuing straight up from the top edge of the x axis
    # (stop short of the x axis's right end: a boxed plot's right frame line
    # stands on it like a stick -- Fig. 22.12a read it as m/z 170 at 19 %)
    right = xr - 6
    for lo_, hi_ in cols[1:]:
        if lo_ >= xr - 20:        # a box's right frame line
            right = min(right, lo_ - 3)
    # The x axis line is 3-4 px thick and, after levelling, still wanders by a
    # row: the profile starts 2 rows above its top so the line itself is
    # never counted as the foot of a stick.
    foot = xt - 2
    up = tick_profile(d, foot, yr + 3, right, -1, maxlen=foot + 1)
    base = (xt + xb) / 2
    sticks = []
    # Sticks are runs of columns with ink straight up from the axis. Where
    # neighbouring sticks touch at their feet (Fig. 15.5's thick pen: 42/43/44
    # and the 80/81 cluster are one block at the axis) the block is split by
    # raising the height threshold until each piece is stick-wide.
    off = yr + 3

    # The shorter of two fused sticks is what is left of the block once the
    # taller one's columns are taken (Fig. 15.5: 80 beside 81, 138 beside
    # 137, solid ink 18-20 px wide): a leftover run at least 0.35 m/z wide
    # is split again on its own.
    min_left = max(4, int(0.35 / abs(ax_)))

    def split(a, b, t):
        if b - a + 1 <= args.max_stick_width:
            return [(a, b)]
        seg = up[a:b + 1]
        t = max(t, int(seg.min())) + 1
        if t > seg.max():
            return []
        out = []
        for c, e in _runs(np.where(seg >= t)[0]):
            out += split(a + c, a + e, t)
        if not out:
            return out
        taken = np.zeros(len(seg), bool)
        for x0, x1 in out:
            taken[max(x0 - a - 1, 0):x1 - a + 2] = True
        for c, e in _runs(np.where(~taken)[0]):
            if e - c + 1 >= min_left and seg[c:e + 1].max() >= args.min_stick and seg[c:e + 1].max() > seg.min() + 2:
                out += split(a + c, a + e, int(seg[c:e + 1].min()))
        return out
    pieces = []
    for a, b in _runs(np.where(up >= args.min_stick)[0]):
        got = split(a, b, args.min_stick)
        if not got:
            report.append(f"  note: a {b - a + 1} px wide ink block at cols {a + off}-{b + off} is not a stick "
                          f"(text?), skipped")
        pieces += got
    near = max(10, int(0.03 * (xt - top)))   # rows above the foot where width is not tested
    for a, b in pieces:
        a += off
        b += off
        width = b - a + 1
        # Follow the stick up. The scan's sticks are 1-3 px lines that wander
        # a column either way and have 1-12 px gaps (JBIG2): Fig. 22.12a's
        # m/z 51 is cols 188-190 and broken at rows 693-704 and 366. So: ink
        # in the stick's own columns continues it (its columns follow it a px
        # at a time; a margin reached into the neighbour on Fig. 15.5, where
        # 52 and 53 are 1 px apart), a gap
        # of up to --max-gap rows is bridged, and it stops where that row's ink
        # runs past the stick on both sides (a label touching its top, as on
        # Fig. 15.5) or at a longer gap.
        pl, pr = a, b              # the stick's columns, followed row by row
        r, last, gap, xs = foot, foot + 1, 0, []
        while r >= 0:
            core = np.nonzero(d[r, pl:pr + 1])[0]
            if len(core):
                c0, c1 = core[0] + pl, core[-1] + pl
                while c0 > 0 and d[r, c0 - 1]:
                    c0 -= 1
                while c1 < w - 1 and d[r, c1 + 1]:
                    c1 += 1
                # Ink running more than 3 px past the stick is either a
                # neighbouring stick merging into it (108 and 109 on Fig. 15.5
                # share their lower 60 px) or a label sitting on its top. A
                # neighbour stands on the axis, so its columns stay dark for
                # the next `sup` rows down; a label's glyphs do not.
                if foot - r > near and (c0 < pl - 3 or c1 > pr + 3):
                    sup = min(30, foot - r)
                    def floating(cols_):
                        return len(cols_) > 0 and not any(d[r:r + sup, j].all() for j in cols_)
                    if (c0 < pl - 3 and floating(range(c0, pl - 1))) or \
                       (c1 > pr + 3 and floating(range(pr + 2, c1 + 1))):
                        break
                # follow a wandering stick by a column at most, never wider
                # than it started (a merged neighbour would widen it)
                # (an edge moves only where the ink ends within a column of
                # it: in a row fused with the neighbour the edge on that side
                # stays put -- else 138 crept a column a row onto 137)
                nl = c0 if c0 >= pl - 1 else pl
                nr = c1 if c1 <= pr + 1 else pr
                if nr - nl + 1 <= width + 1:
                    pl, pr = nl, nr
                last, gap = r, 0
                if foot - r > near:
                    xs.append((pl + pr) / 2)
            else:
                # ink only in the column beside the stick is a neighbour's edge
                # (Fig. 15.5: 53 is 1 px from 52 and 54 px taller), not the stick
                gap += 1
                if gap > args.max_gap:
                    break
            r -= 1
        topr = last
        # position: the median ink centre along the stick, not its foot
        xpos = float(np.median(xs)) if xs else (a + b) / 2
        mzf = ax_ * xpos + bx_
        sticks.append(dict(x=xpos, top=topr, height_px=base - topr, mzf=mzf,
                           ab=ay_ * topr + by_))
    if not sticks:
        raise CalibrationError("no sticks found standing on the x axis")
    # Alignment. Sticks stand on integer m/z, so the fractional part of the
    # tall sticks' m/z is the offset between the plotter's ticks and its pen
    # (Fig. 22.12a: 0.47 m/z = 4 px, half a tick spacing; ir_digitize.py
    # --align finds the same kind of offset on the Palleros IR plots). Near
    # 0.5 the direction is ambiguous; the printed labels (--check) decide it:
    # the shift is the one that makes most of them local-maximum sticks.
    tallest = max(s["ab"] for s in sticks)
    tall = [s for s in sticks if s["ab"] > 0.05 * tallest]
    fr = np.array([s["mzf"] - np.floor(s["mzf"]) for s in tall])
    # circular median of the fractional parts
    ang = np.angle(np.mean(np.exp(2j * np.pi * fr))) / (2 * np.pi) % 1.0
    spread = float(np.median(np.abs(((fr - ang) + 0.5) % 1.0 - 0.5)))
    cands = [-ang, 1 - ang] if ang > 0 else [0.0]
    want = [int(float(v)) for v in args.check.replace(" ", "").split(",") if v] if args.check else []

    def assign(shift):
        out = {}
        for s in sticks:
            t = dict(s, mz=int(round(s["mzf"] + shift)), dev=s["mzf"] + shift - round(s["mzf"] + shift))
            if t["mz"] not in out or t["height_px"] > out[t["mz"]]["height_px"]:
                out[t["mz"]] = t   # two sticks on one m/z: a stick split by a scan gap
        return [out[k] for k in sorted(out)]

    def n_ok(sl):
        by = {s["mz"]: s for s in sl}
        return sum(1 for m in want if m in by and
                   all(t["ab"] <= by[m]["ab"] for t in sl if abs(t["mz"] - m) <= 3))
    if len(cands) > 1 and min(ang, 1 - ang) > 0.2:
        if not want:
            raise CalibrationError(f"the sticks sit {ang:.2f} m/z past the ticks: rounding up or down is "
                                   f"ambiguous. Give --check with the m/z values printed on the figure.")
        shift = max(cands, key=lambda c: n_ok(assign(c)))
    else:
        shift = min(cands, key=abs)
    sticks = assign(shift)
    # Refine: the tall sticks (over 20 % of the tallest) fix the scale and
    # offset by least squares, weighted by height, against the integers they
    # were given -- the ticks are a few px off the pen (Fig. 15.5: 108, 109,
    # 137 sit -3, +1, +2 px off a line through 43 and 179), and a small stick
    # 0.3-0.5 m/z off its integer is then rounded the right way more often.
    ref = [s for s in sticks if s["ab"] > 0.2 * tallest]
    if len(ref) >= 3:
        X = np.array([s["x"] for s in ref])
        Y = np.array([s["mz"] for s in ref], float)
        W = np.array([s["ab"] for s in ref])
        a2, b2 = np.polyfit(X, Y, 1, w=np.sqrt(W))
        res = Y - (a2 * X + b2)
        for s in sticks:
            s["mzf"] = a2 * s["x"] + b2
        sticks = assign(0.0)
        report.append(f"  refit on {len(ref)} tall sticks: scale {a2 / ax_:.4f} x the ticks', "
                      f"residual max {np.abs(res).max():.2f} m/z")
    report.append(f"  align: tall sticks sit {ang:.2f} m/z ({ang / ax_:.1f} px) past the ticks "
                  f"(spread {spread:.2f}); m/z shifted by {shift:+.2f}"
                  + (f", chosen by the printed labels ({n_ok(sticks)}/{len(want)} fit)" if len(cands) > 1 and want else ""))
    tallest = max(s["ab"] for s in sticks)
    bad = [s for s in sticks if s["ab"] > 0.05 * tallest and abs(s["dev"]) > 0.3]
    print(f"spectrum_digitize ms: {os.path.basename(args.image)}")
    for line in report:
        print(line)
    print(f"  sticks: {len(sticks)}, m/z {sticks[0]['mz']}-{sticks[-1]['mz']}; tallest {tallest:.1f} %")
    dev = [abs(s["dev"]) for s in sticks if s["ab"] > 0.05 * tallest]
    print(f"  integer-m/z distance (sticks over 5 %): median {np.median(dev):.2f}, max {max(dev):.2f}"
          + ("" if not bad else f"  WARNING: over 0.3 at m/z {[s['mz'] for s in bad]}"))
    status = 0
    # local maxima within +-3 m/z
    def is_max(s):
        return all(t["ab"] <= s["ab"] for t in sticks if abs(t["mz"] - s["mz"]) <= 3)
    if args.check:
        want = [int(float(v)) for v in args.check.replace(" ", "").split(",") if v]
        by = {s["mz"]: s for s in sticks}
        ok = 0
        for m in want:
            s = by.get(m)
            if s is None:
                print(f"  check m/z {m}: NO STICK")
                status = 2
            elif not is_max(s):
                print(f"  check m/z {m}: stick {s['ab']:.1f} %, but not the tallest within 3 m/z")
                status = 2
            else:
                ok += 1
        print(f"  check: {ok}/{len(want)} printed m/z values are sticks and local maxima")
    if args.labels:
        if "," in args.labels or not args.labels.strip().isdigit():
            lab = [int(float(v)) for v in args.labels.replace(" ", "").split(",") if v]
        else:
            n = int(args.labels)
            lab = sorted((s for s in sticks if is_max(s)), key=lambda s: -s["ab"])[:n]
            lab = sorted(s["mz"] for s in lab)
    else:
        lab = []
    by = {s["mz"]: s for s in sticks}
    entries = []
    for m in lab:
        if m in by:
            ab = by[m]["ab"]
            entries.append(f"{m}/{ab:.1f}/{ab + args.label_gap:.1f}/")
    if entries:
        print("  \\labplot peak list (x/apex_y/label_y/name):")
        print("    " + ",".join(entries))
    if args.list_out:
        with open(args.list_out, "w", encoding="utf-8") as f:
            f.write("\n" + ",".join(entries) + "\n")
    print("  sticks (m/z: %):  " + "  ".join(f"{s['mz']}:{s['ab']:.1f}" for s in sticks if s["ab"] >= 1))

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write("mz,intensity\n")
            for s in sticks:
                f.write(f"{s['mz']},{s['ab']:.2f}\n")
    if args.peaks_out:
        with open(args.peaks_out, "w", encoding="utf-8") as f:
            f.write("mz,intensity,x_px,height_px\n")
            for s in sticks:
                f.write(f"{s['mz']},{s['ab']:.2f},{s['x']:.1f},{s['height_px']:.0f}\n")
    if args.overlay:
        im = Image.fromarray(grey).convert("RGB")
        dr = ImageDraw.Draw(im)
        fnt = _font(max(14, h // 45))
        every = max(1, len(xmaj) // 15)
        for i, (p, v) in enumerate(xmaj):
            dr.line([(p, xb + 2), (p, xb + (40 if i % every == 0 else 14))], fill=(0, 90, 255), width=1)
            if i % every == 0:   # the value the tick has after alignment
                dr.text((p + 3, xb + 40), fmt(v + shift, 2), fill=(0, 90, 255), font=fnt)
        for p, v in ymaj:
            dr.line([(yl - 40, p), (yl - 2, p)], fill=(0, 90, 255), width=3)
            dr.text((max(yl - 110, 0), p - 20), fmt(v, 2), fill=(0, 90, 255), font=fnt)
        for s in sticks:   # beside the stick, so the original stays visible
            dr.line([(s["x"] + 3, base), (s["x"] + 3, s["top"])], fill=(230, 0, 0), width=2)
            dr.line([(s["x"] - 3, s["top"]), (s["x"] + 6, s["top"])], fill=(230, 0, 0), width=2)
        for m in lab:
            if m in by:
                s = by[m]
                dr.text((s["x"] + 4, s["top"] - 4), str(m), fill=(0, 150, 0), font=fnt)
        im.save(args.overlay)
    return status


# ---------------------------------------------------------------------------
# NMR
# ---------------------------------------------------------------------------
def level_by_ruler(grey, report):
    """Level an NMR figure on its main ppm ruler, the lowest long horizontal
    line (ir_digitize.deskew_by_xaxis levels on the row with the most ink,
    which on an NMR figure can be the noisy baseline: Fig. 22.5 came out
    with its ruler still 3 px off level, split into three short lines).
    The ruler's top edge is fitted column by column (two passes, dropping
    columns over 2 px off: tick labels, the trace touching it)."""
    d = grey < 128
    h, w = d.shape
    sm = np.convolve(d.sum(1), np.ones(7), "same")
    rows = np.where(sm > 0.3 * w * 4)[0]
    if not len(rows):
        return grey
    r = int(rows.max())
    lo, hi = max(r - 12, 0), min(r + 6, h)
    band = d[lo:hi]
    cols = np.where(band.any(0))[0]
    if len(cols) < 0.3 * w:
        return grey
    top = band[:, cols].argmax(0) + lo
    keep = np.ones(len(cols), bool)
    for _ in range(2):
        k, c = np.polyfit(cols[keep], top[keep], 1)
        keep = np.abs(top - (k * cols + c)) <= 2
    ang = float(np.degrees(np.arctan(k)))
    if abs(ang) < 0.02:
        return grey
    im = Image.fromarray((d * 255).astype(np.uint8)).rotate(ang, resample=Image.BICUBIC, fillcolor=0)
    report.append(f"level: ruler tilted {ang:+.3f} degrees ({k * w:+.1f} px over the width); rotated")
    return np.where(np.array(im) > 127, 0, 255).astype(np.uint8)


def find_rulers(d, args, report):
    """Long horizontal lines with >= 5 regular ticks below -> list of dicts,
    bottom (main) first. Each ruler's top edge is followed column by
    column, because the scan is not flat: after the
    figure is levelled on the main ruler, Fig. 21.10's inset ruler still
    drops 3 px over its 1500 px (rows 1095-1096 at the right, 1098-1099 at
    the left). Its span is every column whose ink lies on that line, gaps of
    up to 60 px bridged (the line is broken by the scan: Figs. 21.4, 21.7,
    21.16 have no unbroken run over half their length), and its ticks hang
    from the line's own bottom edge, column by column."""
    h, w = d.shape
    bands = []
    for top, bot, lo, hi in long_rows(d, args.ruler_frac):
        for bd in bands:
            if top - 4 <= bd[1] and bot + 4 >= bd[0] and lo <= bd[3] + 60 and hi >= bd[2] - 60:
                bd[0], bd[1] = min(bd[0], top), max(bd[1], bot)
                bd[2], bd[3] = min(bd[2], lo), max(bd[3], hi)
                break
        else:
            bands.append([top, bot, lo, hi])
    out = []
    main_top = max((b_[0] for b_ in bands), default=0)
    for top, bot, lo, hi in bands:
        # Follow the line's top edge column by column from the middle of its
        # longest run, both ways: the edge may move a row per column (a bow or
        # a kink in the scan: Fig. 21.16's ruler rises 3 px in its last 300 px,
        # which neither a straight line nor a quadratic followed), and a break
        # of up to 60 px is bridged at the last row seen (+-2 rows to rejoin).
        x0 = (lo + hi) // 2
        col = d[max(top - 2, 0):bot + 3, x0]
        if not col.any():
            hits = [x for x in range(lo, hi + 1) if d[top:bot + 1, x].any()]
            if not hits:
                continue
            x0 = hits[len(hits) // 2]
            col = d[max(top - 2, 0):bot + 3, x0]
        e0 = int(np.argmax(col)) + max(top - 2, 0)
        edge_of = {x0: e0}
        for step in (1, -1):
            e, gap, x = e0, 0, x0 + step
            while 0 <= x < w and gap <= 60:
                tol = 1 if gap == 0 else 2
                seg = d[max(e - tol, 0):e + tol + 1, x]
                if seg.any():
                    t = int(np.argmax(seg)) + max(e - tol, 0)
                    # the top of the ink there must be a line, not a tick or label
                    # hanging from above: the row above it is empty
                    if t == 0 or not d[t - 1, x]:
                        e, gap = t, 0
                        edge_of[x] = e
                        x += step
                        continue
                gap += 1
                x += step
        oncols = np.array(sorted(edge_of))
        segs, cur = [], [oncols[0], oncols[0]]
        for x in oncols[1:]:
            if x - cur[1] <= 1:
                cur[1] = x
            else:
                segs.append(cur)
                cur = [x, x]
        segs.append(cur)
        segs = [m for m in segs if m[1] - m[0] >= 40]
        if not segs:
            continue
        L, H = min(m[0] for m in segs), max(m[1] for m in segs)
        if H - L < args.ruler_frac * w:
            continue
        span = np.arange(L, H + 1)
        known = np.array(sorted(x for x in edge_of if L <= x <= H))
        edge = np.round(np.interp(span, known, [edge_of[x] for x in known])).astype(int)
        # line thickness: the ink run down from the top edge, median over the span
        th = []
        for x, e in zip(span[::7], edge[::7]):
            n = 0
            while e + n < h and d[e + n, x]:
                n += 1
            if n:
                th.append(n)
        thick = int(np.median(th)) if th else 2
        lens = np.zeros(len(span), int)
        for i, (x, e) in enumerate(zip(span, edge)):
            r = e + thick
            n = 0
            while r + n < h and n < 60 and d[r + n, x]:
                n += 1
            lens[i] = n
        ticks_all = find_ticks(lens, L, maxw=args.tick_width)
        # Two expansions side by side are two rulers, though the gap between
        # them is bridged like a scan break (Fig. 21.15 has three in a row,
        # 20-40 px apart). A scan break keeps ONE tick grid across the gap;
        # two rulers each have their own. So at every gap of 12 px or more,
        # cut where the ticks on the two sides differ in spacing (> 10 %) or
        # are out of phase (> 0.3 of a spacing).
        cuts = [L]
        for (_, g0), (g1, _) in zip(segs[:-1], segs[1:]):
            if g1 - g0 < 12:
                continue
            # the right side runs to the next gap of 12 px or more (a 1-3 px
            # scan break inside it is not an end)
            nxt = min([q1 for (_, q0), (q1, _) in zip(segs[:-1], segs[1:]) if q1 > g1 and q1 - q0 >= 12]
                      + [H + 1])
            left = [t[0] for t in ticks_all if cuts[-1] <= t[0] <= g0]
            right = [t[0] for t in ticks_all if g1 <= t[0] < nxt]
            if len(left) < 4 or len(right) < 4:
                continue
            sl, sr = np.median(np.diff(left)), np.median(np.diff(right))
            ph = (right[0] - left[-1]) / sl
            # or, above the main ruler (whose scan breaks reach 60 px), at a
            # gap of 20 px or more: Fig. 21.15's 1.95 and 1.85 insets share one
            # grid, 28 px apart
            if abs(sl - sr) > 0.1 * min(sl, sr) or abs(ph - round(ph)) > 0.3 or \
                    (g1 - g0 >= 20 and top < main_top - 20):
                cuts.append((g0 + g1) // 2)
        cuts.append(H + 1)
        for p0, p1 in zip(cuts[:-1], cuts[1:]):
            on = [x for x in edge_of if p0 <= x < p1]
            if not on:
                continue
            pL, pH = min(on), max(on)
            if pH - pL < args.ruler_frac * w:
                continue
            ticks = [t for t in ticks_all if pL <= t[0] <= pH]
            # 5: Fig. 21.9's inset rulers carry two long and three short ticks;
            # 2 only when asked for (cmd_nmr's retry: more --inset than rulers)
            if len(ticks) < getattr(args, "min_ticks", 5):
                continue
            sp = np.diff([t[0] for t in ticks])
            m = np.median(sp)
            if np.mean(np.abs(sp - m) < 0.2 * m) < 0.6:
                continue
            pe = edge[(span >= pL) & (span <= pH)]
            if any(abs(o["top"] - pe.min()) <= 4 and o["lo"] <= pH and pL <= o["hi"] for o in out):
                continue
            out.append(dict(top=int(pe.min()), bot=int(pe.max()) + thick - 1, lo=int(pL), hi=int(pH),
                            ticks=ticks, thick=thick))
            if pe.max() - pe.min() >= 2:
                report.append(f"  ruler at rows {pe.min()}-{pe.max()}: not level after levelling "
                              f"({pe[-1] - pe[0]:+d} px end to end, {pe.max() - pe.min()} px high); "
                              f"followed column by column")
    out.sort(key=lambda r: -r["bot"])
    return out


def envelope_trace(mask):
    """-> (col, entry, exit) per column with ink, and the pen width. The
    column's whole ink extent (topmost to bottommost pixel) is the trace
    there, less half a pen at each end; a broken peak (two runs in a column)
    is bridged, not cut at its first run (ir_digitize.extract_trace follows
    one run per column). Entry is the end nearer the previous column's exit,
    so a peak is drawn up one side and down the other."""
    h, w = mask.shape
    cols = np.nonzero(mask.any(0))[0]
    tops = np.array([np.argmax(mask[:, c]) for c in cols])
    bots = np.array([h - 1 - np.argmax(mask[::-1, c]) for c in cols])
    ext = bots - tops + 1
    pen = int(np.percentile(ext, 20)) if len(ext) else 1
    trim = (pen - 1) / 2
    pts, prev = [], None
    for c, t, b_ in zip(cols, tops, bots):
        if b_ - t + 1 > pen:
            a_, z = t + trim, b_ - trim
        else:
            a_ = z = (t + b_) / 2
        if prev is not None and abs(z - prev) < abs(a_ - prev):
            a_, z = z, a_
        pts.append((int(c), a_, z))
        prev = z
    return pts, pen, dict(zip(cols.tolist(), tops.tolist()))


def hthin(mask, pen):
    """Each horizontal run of ink no wider than 2 pen + 2 px kept as its middle
    pixel: a near-vertical stroke becomes its centreline, and so does a sharp
    line whose up and down strokes have fused into one 5-6 px bar (Fig.
    22.4's second inset), while the baseline (long runs) is untouched. For the DRAWN trace only: a column's whole ink
    extent is drawn, so a 3-px pen standing on a steep side gives three
    columns of full height, which a plot that enlarges the figure 3-4 times
    (an expansion inset drawn full width: Fig. 22.4's second inset) shows as
    a filled block. Peaks are read from the unthinned ink."""
    out = np.zeros_like(mask)
    for r in np.nonzero(mask.any(1))[0]:
        for a, b in _runs(np.nonzero(mask[r])[0]):
            if b - a + 1 <= 2 * pen + 2:
                out[r, (a + b) // 2] = True
            else:
                out[r, a:b + 1] = True
    return out


def follow_down(mask, c, r0, r1, pen):
    """Follow a line from row r0 down to row r1 starting at column c; -> the
    line's centre column at r1 (or where it was last seen alone). Where it
    merges with a neighbour (the run is wider than pen + 3) the centre is held.
    Why: scanned lines are not straight. Fig. 21.16's tall camphor lines bend
    by 5 px in their lower third (x 2015-2017 at the top, 2010-2012 near the
    baseline), and the ppm ruler sits just under the baseline, so the foot of
    a line, not its apex, is where the ruler's calibration holds."""
    w = mask.shape[1]
    cl = cr = int(round(c))
    cen = c
    for r in range(int(r0), int(r1) + 1):
        row = mask[r]
        hit = np.nonzero(row[max(cl - 1, 0):min(cr + 2, w)])[0]
        if not len(hit):
            continue
        a = hit[0] + max(cl - 1, 0)
        b = hit[-1] + max(cl - 1, 0)
        while a > 0 and row[a - 1]:
            a -= 1
        while b < w - 1 and row[b + 1]:
            b += 1
        if b - a + 1 > pen + 3:
            continue
        cl, cr, cen = a, b, (a + b) / 2
    return cen


def nmr_peaks(pts, tops, mask, region_top, args, pen=3):
    """pts: (col, entry, exit) of one trace; tops: col -> topmost ink row.
    -> peaks (col, apex_row, height_px, clipped), baseline row, noise px."""
    cols = np.array([p[0] for p in pts])
    topr = np.array([min(p[1], p[2]) for p in pts])
    # Baseline and noise from the FLAT columns only (ink no taller than two
    # pens): an inset filled by one multiplet (Fig. 21.6's spans 60 % of its
    # width) put the median of all columns half way up the lines, and its
    # spread read 37 px of "noise", so no line under 222 px counted and 3 of
    # its ~10 lines were found. Too few flat columns: the bottom edges.
    # (The bottom edges alone sit 1-2 px low on a noisy baseline, which let
    # four noise bumps through on Fig. 21.13.)
    mid = np.array([(p[1] + p[2]) / 2 for p in pts])
    bot = np.array([max(p[1], p[2]) for p in pts])
    isflat = (bot - topr) <= 2 * pen
    if isflat.sum() >= 20:
        base = float(np.median(mid[isflat]))
        flat = topr[isflat]
    else:
        base = float(np.median(bot))
        flat = topr
    noise = 1.4826 * float(np.median(np.abs(flat - np.median(flat))))
    minh = args.min_height if args.min_height else max(8.0, 6 * noise)
    hgt = base - topr
    out = []
    i, n = 0, len(cols)
    k = args.peak_window
    while i < n:
        if hgt[i] < minh:
            i += 1
            continue
        j = i
        while j + 1 < n and topr[j + 1] == topr[i] and cols[j + 1] == cols[j] + 1:
            j += 1
        lo, hi = max(i - k, 0), min(j + k + 1, n)
        if topr[i] <= topr[lo:hi].min():
            c = (cols[i] + cols[j]) / 2
            # prominence: the peak must rise minh/2 above the higher-lying of the
            # two lowest points of the top edge within +-25 px (keeps the second
            # line of a close pair, rejects a bump on a peak's flank)
            wl = topr[max(i - 25, 0):i + 1].max() if i else topr[i]
            wr = topr[j:min(j + 26, n)].max()
            if min(wl, wr) - topr[i] >= minh * 0.5 or hgt[i] >= 4 * minh:
                clipped = tops[int(cols[i])] <= region_top + 3
                if clipped:
                    # The figure cut the peak off: its flat top says nothing
                    # about where it is. Take the middle of the line 12 px
                    # below the cut (the flanks of a tall line are steep).
                    r = int(tops[int(cols[i])]) + 12
                    row = mask[r]
                    c0 = c1 = int(round(c))
                    if row[c0]:
                        while c0 > 0 and row[c0 - 1]:
                            c0 -= 1
                        while c1 < len(row) - 1 and row[c1 + 1]:
                            c1 += 1
                        c = (c0 + c1) / 2
                # position at the foot: 15 % of the peak's height above the
                # baseline, at least 12 px above it (clear of the noise)
                foot = base - max(12.0, 0.15 * hgt[i], 2 * noise)
                apex_row = int(tops[int(round(c))]) if int(round(c)) in tops else int(topr[i])
                if foot > apex_row + 4:
                    c = follow_down(mask, c, apex_row + (12 if clipped else 0), foot, pen)
                out.append((c, float(topr[i]), float(hgt[i]), clipped))
        i = j + 1
    return out, base, noise, minh


def fan_labels(peaks, left, right, width_cm, pitch_mm=3.8, mode="top", trace=None, gap=4.0, unit=1.0):
    """Spread rotated labels over the lines of an NMR plot. peaks: (ppm,
    apex %, text), any order; left/right: the axis ends in ppm (left the
    larger). Each label wants to sit over its own line; labels closer than
    pitch_mm (a \\scriptsize rotated label, 7 pt + 2 x 1 pt inner sep = 9 pt
    = 3.2 mm) are pushed apart as a group, centred on their lines, and kept
    inside the axis. width_cm is the plot's width (\\labplot's 14.5 cm picture
    is ~13.5 cm of axis). -> (x, apex_y, knee_y, label_x, label_y, text) per
    peak, label_x in ppm.
    mode "top": every label on one level 10 % above the tallest line, as a
    spectrometer prints them; the leader rises from the line to a knee 4 %
    above the tallest line, then runs straight to its label.
    mode "follow": each group at its own height, like the IR and GC labels:
    gap % above the highest point of the trace (trace: (ppm, %) pairs) under
    the group's lines and labels, so a lone line's label stands just over it
    (a straight leader) and a fanned group's knee clears the whole cluster.
    unit scales every height in % (gaps, rises): 1 for a full \\labplot,
    where 1 % is ~0.67 mm; an inset drawn inside one is shorter, so the same
    millimetres are more of its %."""
    gap = gap * unit
    if not peaks:
        return []
    span = left - right
    mm = width_cm * 10 / span                  # mm per ppm
    pk = sorted(peaks, key=lambda p: -p[0])     # left to right on the page
    want = [(left - p[0]) * mm for p in pk]      # mm from the left end
    groups = [[i] for i in range(len(pk))]

    def place(g):
        c = np.mean([want[i] for i in g])
        start = c - pitch_mm * (len(g) - 1) / 2
        start = min(max(start, 0), width_cm * 10 - pitch_mm * (len(g) - 1))
        return [start + pitch_mm * k for k in range(len(g))]
    pos = {}
    changed = True
    while changed:
        changed = False
        placed = [place(g) for g in groups]
        for k in range(len(groups) - 1):
            if placed[k + 1][0] - placed[k][-1] < pitch_mm - 1e-9:
                groups[k] += groups.pop(k + 1)
                changed = True
                break
    for g in groups:
        for i, u in zip(g, place(g)):
            pos[i] = u
    out = [None] * len(pk)
    if mode == "top":
        top = max(p[1] for p in pk)
        label_y = round(top + 10 * unit)
        for i, (x, a, t) in enumerate(pk):
            out[i] = (x, a, max(top + 4 * unit, a + 2 * unit), left - pos[i] / mm, label_y, t)
        return out
    tr = np.array(trace if trace else [(p[0], p[1]) for p in pk], dtype=float)
    for g in groups:
        ends = [pos[i] for i in g] + [want[i] for i in g]
        hi_ppm = left - (min(ends) - pitch_mm / 2) / mm
        lo_ppm = left - (max(ends) + pitch_mm / 2) / mm
        under = tr[(tr[:, 0] >= lo_ppm) & (tr[:, 0] <= hi_ppm), 1]
        clear = max([pk[i][1] for i in g] + list(under))
        if len(g) == 1:
            # straight up: the knee sits on the label's foot
            ly = round(clear + gap, 1)
            knee = ly
        else:
            # room for the bend: leaders rise to the knee, then slant out
            knee = round(clear + gap / 2, 1)
            ly = round(knee + 4 * unit, 1)
        for i in g:
            x, a, t = pk[i]
            out[i] = (x, a, max(knee, a + 1), left - pos[i] / mm, ly, t)
    return out


def callout(x, a, left, right, width_cm, text, trace, labels=(), pitch_mm=3.8, gap=4.0, rise=8.0,
            char_mm=1.4, label_len=12.0, unit=1.0, obstacles=()):
    """The book's own solvent mark: the text upright, with an arrow from below
    it to the line's top. The tail stands beside the line, rise % above its
    top, raised further until the text (char_mm per \\scriptsize character,
    centred on the tail) clears the trace by gap %. The side and distance are
    the first of 4, 6, ... 12 mm to the right of the line, then the same to
    the left, where the text misses every other label (labels: fan_labels'
    entries; a rotated label is pitch_mm wide and ~label_len % tall); if none
    does, the nearest place on the right, lifted over the labels in the way
    (Fig. 21.7: benzhydrol's 76.5 line stands 0.9 ppm from the solvent's).
    -> (x, a, None, tail_x, tail_y, text): knee None is written empty, which
    \\Lab@fanpeak draws as a callout."""
    gap, rise, label_len = gap * unit, rise * unit, label_len * unit
    mm = width_cm * 10 / (left - right)
    half = (len(text) * char_mm / 2 + 1) / mm  # ppm either side of the tail
    tr = np.array(trace, dtype=float)
    # a rotated label is as long as its text (char_mm a character, + 1 mm);
    # label_len (a 4-character number, in %) gives the % per mm
    pct_mm = label_len / 6.6

    def llen(x_, t_):
        return (len(t_ or f"{x_:g}") * char_mm + 1) * pct_mm
    boxes = [(lx - pitch_mm / 2 / mm, lx + pitch_mm / 2 / mm, ly, ly + llen(x_, t_)) for x_, _, _, lx, ly, t_ in labels]
    # and each leader's rise, which in the `top` style crosses most of the plot
    boxes += [(px - 0.5 / mm, px + 0.5 / mm, pa, ky) for px, pa, ky, _, _, _ in labels if ky is not None]
    # an upright label (a callout itself) and any inset box
    boxes += [(lx - 3 / mm, lx + 3 / mm, ly, ly + label_len / 2) for _, _, ky, lx, ly, _ in labels if ky is None]
    boxes += [(o[0], o[1], o[2], o[3]) for o in obstacles]

    def at(tx):
        under = tr[(tr[:, 0] >= min(tx - half, x)) & (tr[:, 0] <= max(tx + half, x)), 1]
        ty = max(a + rise, (under.max() if len(under) else 0) + gap)
        hit = [b for b in boxes if b[0] < tx + half and b[1] > tx - half and b[2] < ty + 6 and b[3] > ty]
        return ty, hit
    tries = [x - d / mm for d in (4, 6, 8, 10, 12)] + [x + d / mm for d in (4, 6, 8, 10, 12)]
    tries = [t for t in tries if right <= t - half and t + half <= left]
    for tx in tries:
        ty, hit = at(tx)
        if not hit:
            return (x, a, None, tx, round(ty, 1), text)
    tx = tries[0] if tries else x
    ty, hit = at(tx)
    while hit:
        ty = max(b[3] for b in hit) + gap
        hit = [b for b in boxes if b[0] < tx + half and b[1] > tx - half and b[2] < ty + 6 and b[3] > ty]
    return (x, a, None, tx, round(ty, 1), text)


def find_integrals(m, pen=3, k=5, min_gap=1):
    """The integral curves a 1H figure draws over its multiplets: each a thin
    stroke that starts at a hook on the left (a short horizontal stub, free at
    its left end), rises through the multiplet and ends in a flat to the right
    (free at its right end). A thin horizontal stroke is ink with an
    (2k+1)-px horizontal run through it and none pen+2 rows above or below;
    above the baseline band only (the baseline itself is one). Each flat is
    paired with the nearest unused hook to its left that sits lower and ends
    within 80 px of it. -> [(hook, flat)], each a dict x0, x1 (columns), r
    (the stroke's mean row), px (its pixels). The step, hook r - flat r, is the
    integral; on Fig. 22.4 the steps read 267.7, 566.4, 806.9, 276.2, 863.5 px
    against the hand read-out's 268, 567, 808, 277, 864."""
    h, w = m.shape
    cols = np.nonzero(m.any(0))[0]
    if not len(cols):
        return []
    base = int(np.median([np.nonzero(m[:, c])[0].max() for c in cols]))
    run = m.copy()
    for d in range(1, k + 1):
        run[:, :-d] &= m[:, d:]
    H = np.zeros_like(m)
    for d in range(0, k + 1):
        H[:, d:] |= run[:, :w - d]
    H &= m
    H &= ~np.roll(m, pen + 2, axis=0) | ~np.roll(m, -(pen + 2), axis=0)
    # 6 pens above the baseline: a stub between two lines 11 px above it
    # (Fig. 21.21) was taken for a hook and paired with another curve's top
    H[max(base - 6 * pen, 0):, :] = False
    segs = []
    for rr, cc in components(H):
        if cc.max() - cc.min() < 8:
            continue
        x0, x1, r = int(cc.min()), int(cc.max()), float(np.mean(rr))
        rows = slice(max(int(r) - pen - 1, 0), int(r) + pen + 2)
        lfree = not m[rows, max(x0 - 4, 0):max(x0 - 1, 0)].any()
        rfree = not m[rows, x1 + 2:x1 + 5].any()
        segs.append(dict(x0=x0, x1=x1, r=r, lfree=lfree, rfree=rfree, px=(rr, cc)))
    hooks = [g for g in segs if g["lfree"] and not g["rfree"]]
    flats = [g for g in segs if g["rfree"]]
    out = []
    used = set()
    for f in sorted(flats, key=lambda g: g["x0"]):
        # at least 15 px of step: an S-curve's top curl is a flat and a "hook"
        # 5 px apart (Fig. 21.18), which then hid the curve's real end
        cand = [i for i, g in enumerate(hooks) if i not in used and g["r"] > f["r"] + 15
                and g["x1"] <= f["x0"] + 5 and f["x0"] - g["x1"] <= 80]
        # nearest first, and only if ink joins the hook to the flat
        for i in sorted(cand, key=lambda i: -hooks[i]["x1"]):
            g = hooks[i]
            reach = ink_reach(m, (g["r"], g["x0"]), (int(f["r"]) - 6, int(g["r"]) + 6, g["x0"] - 6, f["x1"] + 6))
            if any((int(round(f["r"])) + dy_, f["x1"] - dx_) in reach for dy_ in range(-3, 4) for dx_ in range(0, 4)):
                used.add(i)
                # a thin horizontal stroke between them, 10 px clear of both,
                # is a plateau the curve rests on between two steps (Fig.
                # 21.12's aromatic, 2.3 | 4.2 H): one integral per step
                mids = sorted((q for q in segs if q is not g and q is not f and g["x1"] - 2 <= q["x0"]
                               and q["x1"] <= f["x0"] + 2 and f["r"] + 10 < q["r"] < g["r"] - 10),
                              key=lambda q: -q["r"])
                chain = [g] + mids + [f]
                # a plateau closer than min_gap columns to the last kept one
                # (a doublet's shoulder) is not a split
                keep = [chain[0]]
                for q in chain[1:-1]:
                    if q["x0"] - keep[-1]["x1"] >= min_gap:
                        keep.append(q)
                keep.append(chain[-1])
                for lo_, hi_ in zip(keep[:-1], keep[1:]):
                    out.append((lo_, hi_))
                break
    return out


def stroke_ends(m, top, bottom, ring=6):
    """Free ends of thin strokes in rows top..bottom: ink pixels whose ring of
    24 samples at radius `ring` meets ink in ONE arc of at most 8 samples (a
    stroke passing through meets two arcs, a junction three). Neighbouring
    end pixels are one end. -> [(row, col, angle)], angle (degrees, y up) the
    direction the stroke leaves the end in: an integral's lower end leaves to
    the right or up, its upper end to the left or down, a line's apex
    straight down."""
    h, w = m.shape
    ang = np.linspace(0, 2 * np.pi, 24, endpoint=False)
    dy = np.round(-ring * np.sin(ang)).astype(int)
    dx = np.round(ring * np.cos(ang)).astype(int)
    sub = m.copy()
    sub[:max(top, 0)] = False
    sub[bottom:] = False
    ys, xs = np.nonzero(sub)
    if not len(ys):
        return []
    # padded, not cut: Fig. 21.18's 8.0 ppm integral ends at the top edge
    pad = np.zeros((h + 2 * ring, w + 2 * ring), bool)
    pad[ring:ring + h, ring:ring + w] = m
    samp = np.stack([pad[ys + ring + a, xs + ring + b] for a, b in zip(dy, dx)], axis=1)
    rises = (samp & ~np.roll(samp, 1, axis=1)).sum(1)
    cnt = samp.sum(1)
    sel = (rises == 1) & (cnt <= 8)
    endm = np.zeros_like(m)
    endm[ys[sel], xs[sel]] = True
    dirs = {}
    for y, x, s in zip(ys[sel], xs[sel], samp[sel]):
        dirs[(y, x)] = np.arctan2(np.sin(ang[s]).mean(), np.cos(ang[s]).mean())
    out = []
    for rr, cc in components(endm):
        a = np.array([dirs[(r_, c_)] for r_, c_ in zip(rr, cc)])
        deg = np.degrees(np.arctan2(np.sin(a).mean(), np.cos(a).mean())) % 360
        out.append((float(rr.mean()), float(cc.mean()), float(deg)))
    return out


def ink_reach(m, a, box):
    """8-connected ink reachable from point a (row, col) inside box (r0, r1,
    c0, c1). -> dict pixel -> previous pixel (a breadth-first tree, so the
    way back from any pixel is a shortest ink path), or {}."""
    r0, r1, c0, c1 = box
    r0, c0 = max(r0, 0), max(c0, 0)
    r1, c1 = min(r1, m.shape[0] - 1), min(c1, m.shape[1] - 1)
    sub = m[r0:r1 + 1, c0:c1 + 1]
    ys, xs = np.nonzero(sub)
    if not len(ys):
        return {}
    k = np.argmin((ys - (a[0] - r0)) ** 2 + (xs - (a[1] - c0)) ** 2)
    s = (int(ys[k]) + r0, int(xs[k]) + c0)
    prev = {s: None}
    q = [s]
    i = 0
    while i < len(q):
        y, x = q[i]
        i += 1
        for dy_ in (-1, 0, 1):
            for dx_ in (-1, 0, 1):
                n = (y + dy_, x + dx_)
                if r0 <= n[0] <= r1 and c0 <= n[1] <= c1 and n not in prev and m[n]:
                    prev[n] = (y, x)
                    q.append(n)
    return prev


def split_plateaus(path, min_run=5, steep=8, min_step=15, min_gap=1):
    """One integral curve that rises in steps (Fig. 21.15's three methyl
    singlets, 0.94/0.88/0.81 ppm, in one curve; Fig. 21.12's aromatic, which
    the hand read-out split "at the plateau between the two steps") -> its
    steps. Between steps the curve is not level but gentle: Fig. 21.15's
    climbs ~1 row per column there, against 70+ in a step. A column is steep
    when its own ink spans, or its top moves from the last column's by, more
    than `steep` rows; a run of at least min_run gentle columns with steep
    ones on both sides, and at least min_step px of rise on each side, is a
    plateau; the step boundary is its middle row. Plateaus whose steps' rise
    centres are less than min_gap columns apart are not splits (the caller
    sets min_gap from 0.04 ppm, or 20 Hz with --mhz: a doublet's two halves
    are not two signals). path: (row, col) from the low end to the high end.
    -> [(low row, high row, first col, last col)], low to high, or None."""
    cols = sorted({c for _, c in path})
    if len(cols) < 3 * min_run:
        return None
    rmin = {c: min(r for r, c2 in path if c2 == c) for c in cols}
    rmax = {c: max(r for r, c2 in path if c2 == c) for c in cols}
    st = [rmax[c] - rmin[c] > steep or (k and abs(rmin[c] - rmin[cols[k - 1]]) > steep)
          for k, c in enumerate(cols)]
    lo_r, hi_r = path[0][0], path[-1][0]
    plats, k = [], 0
    while k < len(cols):
        if st[k]:
            k += 1
            continue
        j = k
        while j < len(cols) and not st[j]:
            j += 1
        if j - k >= min_run and any(st[:k]) and any(st[j:]):
            row = float(np.mean([rmin[c] for c in cols[k:j]]))
            if lo_r - row >= min_step and row - hi_r >= min_step:
                plats.append((row, cols[k], cols[j - 1]))
        k = j
    if not plats:
        return None
    bounds = [(lo_r, path[0][1])] + [(r_, (a_ + b_) // 2) for r_, a_, b_ in plats] + [(hi_r, path[-1][1])]
    steps = [(r0, r1, c0, c1) for (r0, c0), (r1, c1) in zip(bounds[:-1], bounds[1:])]
    # steps whose rises are closer than min_gap columns are one signal
    centres = []
    for r0, r1, c0, c1 in steps:
        mid = (r0 + r1) / 2
        cs = [c for r, c in path if min(c0, c1) <= c <= max(c0, c1) and abs(r - mid) <= 0.25 * (r0 - r1)]
        centres.append(np.mean(cs) if cs else (c0 + c1) / 2)
    merged = [list(steps[0])]
    for (r0, r1, c0, c1), cprev, cnow in zip(steps[1:], centres[:-1], centres[1:]):
        if abs(cnow - cprev) < min_gap:
            merged[-1][1], merged[-1][3] = r1, c1
        else:
            merged.append([r0, r1, c0, c1])
    # and a step under min_step px is part of its neighbour
    k = 0
    while len(merged) > 1 and k < len(merged):
        if merged[k][0] - merged[k][1] < min_step:
            if k + 1 < len(merged):
                merged[k + 1][0], merged[k + 1][2] = merged[k][0], merged[k][2]
            else:
                merged[k - 1][1], merged[k - 1][3] = merged[k][1], merged[k][3]
            del merged[k]
        else:
            k += 1
    return [tuple(x) for x in merged] if len(merged) > 1 else None


def min_gap_cols(ppm_px, mhz):
    """Columns two steps of one integral curve must be apart to be two
    signals: 0.04 ppm, or 20 Hz if the spectrometer frequency is known (a
    doublet's halves are a J apart, and 1H J is under 20 Hz)."""
    if not ppm_px:
        return 1
    g = 0.04
    if mhz:
        g = max(g, 20.0 / mhz)
    return g / ppm_px


def straight(path, frac=0.06, steep=70):
    """A drawn line, not an integral: the path never leaves the straight line
    between its ends by more than frac of its length AND that line slants,
    under `steep` degrees from the horizontal. Fig. 15.3's "solvent" arrow:
    4.9 % and 61 deg. Straightness alone would not do: a narrow integral is
    nearly straight too (Fig. 21.21's aromatics, 1.3-4.6 %), but steep
    (85-88 deg); a flat one (Fig. 21.6's OH, 38 deg) curves (11.6 %)."""
    (r0, c0), (r1, c1) = path[0], path[-1]
    L = np.hypot(r1 - r0, c1 - c0)
    if L < 1:
        return True
    pr = np.array(path, float)
    dev = np.abs((c1 - c0) * (pr[:, 0] - r0) - (r1 - r0) * (pr[:, 1] - c0)) / L
    ang = np.degrees(np.arctan2(abs(r1 - r0), abs(c1 - c0)))
    return dev.max() < frac * L and ang < steep


def find_curve_integrals(m, pen, known, base, min_gap=1):
    """The integrals find_integrals() cannot see: smooth S-shaped curves with
    no flat ends (Figs. 21.18, 21.21) or arcs (21.15). Each is a thin stroke
    between two free ends (stroke_ends), the lower one leaving to the right
    or up (-30..80 deg), the upper one to the left or down (150..262 deg),
    above the baseline band. From each lower end the ink it reaches is
    searched (ink_reach: up to it, and right by 30 % of the width); the
    HIGHEST unused upper end in it, right of and 8 px above the lower end, is
    its other end, and the way back through the search is the curve (a
    shortest ink path: the lines it crosses run down out of the box, and
    where it rides a line the line is no shorter). Ends inside an integral
    already found are ignored.
    -> [(hook, flat)] in find_integrals' form: hook x1 / flat x0 = the
    columns where the curve has risen 3 % and 97 % of its step (the
    multiplet under it), hook x0 / flat x1 its ends, r = the end's row; flat["path"] = the curve's
    pixels, for strip_integrals."""
    h, w = m.shape
    ends = stroke_ends(m, 0, int(base - 4 * pen))

    def claimed(r_, c_):
        return any(hk["x0"] - 12 <= c_ <= fl["x1"] + 12 and fl["r"] - 12 <= r_ <= hk["r"] + 12
                   for hk, fl in known)
    lows = sorted([e for e in ends if (-30 <= ((e[2] + 180) % 360) - 180 <= 80) and not claimed(e[0], e[1])],
                  key=lambda e: e[1])
    # 262, not 250: a narrow S's top can leave nearly straight down (Fig.
    # 21.21's first aromatic integral, 259 deg); a line's apex is ~270
    highs = [e for e in ends if 150 <= e[2] <= 262 and not claimed(e[0], e[1])]
    used = set()
    out = []

    def add(hook, flat):
        # a curve that rises in steps is one integral per step
        path_ = flat["path"]
        if path_ and path_[0][0] < path_[-1][0]:
            path_ = path_[::-1]
        st = split_plateaus(path_, min_gap=min_gap)
        if not st:
            out.append((hook, flat))
            return
        for r0, r1, c0, c1 in st:
            sub = [(r_, c_) for r_, c_ in path_ if min(c0, c1) <= c_ <= max(c0, c1)]
            xs = [c_ for r_, c_ in sub if r1 + 0.03 * (r0 - r1) <= r_ <= r0 - 0.03 * (r0 - r1)] or [c0, c1]
            out.append((dict(x0=min(c0, c1), x1=min(xs), r=float(r0), px=hook["px"]),
                        dict(x0=max(xs), x1=max(c0, c1), r=float(r1), px=flat["px"], path=sub)))
    for lo in lows:
        # everything the curve reaches, from its lower end up and to the right;
        # its upper end is the HIGHEST upper end in that set (a line's apex
        # beside the curve can look like one too: Fig. 21.6's at row 519)
        # down to 40 px below the lower end (Fig. 15.3's 7.38 integral first
        # slants 30 px down into its lines), clear of the baseline band
        reach = ink_reach(m, (lo[0], lo[1]), (0, int(min(lo[0] + 40, base - 4 * pen)), int(lo[1]) - 6,
                                              int(lo[1] + 0.3 * w)))
        cand = []
        for i, e in enumerate(highs):
            if i in used or e[1] <= lo[1] + 3 or e[0] >= lo[0] - 8:
                continue
            near = [p_ for p_ in ((int(round(e[0])) + dy_, int(round(e[1])) + dx_)
                                  for dy_ in range(-3, 4) for dx_ in range(-3, 4)) if p_ in reach]
            if near:
                cand.append((e[0], i, e, near[0]))
        if not cand:
            continue
        _, i, hi, p_ = min(cand)
        used.add(i)
        path = []
        while p_ is not None:
            path.append(p_)
            p_ = reach[p_]
        path = path[::-1]
        if straight(path):
            used.discard(i)
            continue
        step = lo[0] - hi[0]
        # the multiplet under it: where the curve has risen 3 % and 97 % of its
        # step (10-90 % cut Fig. 21.6's para lines, the last 17 % of the rise)
        x10 = next((c_ for r_, c_ in path if lo[0] - r_ >= 0.03 * step), int(lo[1]))
        x90 = next((c_ for r_, c_ in path if lo[0] - r_ >= 0.97 * step), int(hi[1]))
        a_, b_ = sorted((x10, x90))
        hook = dict(x0=int(lo[1]), x1=a_, r=lo[0], px=(np.array([], int), np.array([], int)))
        flat = dict(x0=b_, x1=int(hi[1]), r=hi[0], px=(np.array([], int), np.array([], int)), path=path)
        add(hook, flat)
    # An upper end left over is a curve whose lower end runs into a line
    # instead of ending free (Fig. 21.15's arcs at 1.95 and 1.83 ppm). Follow
    # it down from the top, row by row, keeping to the ink nearest the row
    # above, until it widens past two pens (it has met a line, or turned
    # into a hook) or stops; that row is its lower end. Only if it falls at
    # least 15 px and ends left of its top (an integral rises to the right).
    for i, hi in enumerate(highs):
        if i in used:
            continue
        r, c = int(round(hi[0])), int(round(hi[1]))
        path, x, start = [], c, r
        while r < base - 4 * pen:
            lo_c = max(x - 6, 0)
            row = np.nonzero(m[r, lo_c:x + 7])[0]
            if not len(row):
                break
            j = lo_c + int(row[np.argmin(np.abs(row + lo_c - x))])
            a_, b_ = j, j
            while a_ > 0 and m[r, a_ - 1]:
                a_ -= 1
            while b_ < w - 1 and m[r, b_ + 1]:
                b_ += 1
            if b_ - a_ + 1 > 2 * pen + 2 and r - start > 12:
                break
            x = j
            path.append((r, x))
            r += 1
        if len(path) < 15 or path[-1][1] >= c - 2 or straight(path):
            continue
        used.add(i)
        lo_r = path[-1][0]
        step = lo_r - hi[0]
        x10 = next((c_ for r_, c_ in reversed(path) if lo_r - r_ >= 0.03 * step), path[-1][1])
        x90 = next((c_ for r_, c_ in reversed(path) if lo_r - r_ >= 0.97 * step), c)
        a_, b_ = sorted((x10, x90))
        hook = dict(x0=path[-1][1], x1=a_, r=float(lo_r), px=(np.array([], int), np.array([], int)))
        flat = dict(x0=b_, x1=c, r=hi[0], px=(np.array([], int), np.array([], int)), path=path)
        add(hook, flat)
    return out


def strip_integrals(m, ints, pen=3):
    """Remove the integral strokes from the trace mask, so their rises are not
    read as lines. The hook and the flat go with pen rows either side; the
    rise is followed from the flat's left end down to the hook's row, row by
    row, keeping to the ink nearest the previous row's (the rise runs up the
    multiplet's own lines: Fig. 22.4's 7.38 integral rides its tallest line
    for 170 px), and pen/2 + 2 px either side of it are cleared. A line hidden
    under the rise loses that stretch, not its apex unless the apex is under
    the rise too. What the clearing leaves of a slanted rise (1-px slivers up
    to 100 px tall on Fig. 22.4) is dropped: any piece inside an integral's
    columns and rows that does not reach down to the baseline band (a line
    always does), and specks under 12 px anywhere. A piece rising above the
    integral's flat is a line's top, cut off where the rise ran along it
    (Fig. 22.4's 3.82 singlet), and is kept."""
    m = m.copy()
    halfw = pen // 2 + 2
    cols = np.nonzero(m.any(0))[0]
    base = int(np.median([np.nonzero(m[:, c])[0].max() for c in cols]))
    for hook, flat in ints:
        if "path" in flat:
            # a curve integral: clear around the ink path itself, and 8 px
            # round its two ends (an end is the middle of the end pixels, and
            # the stroke's tip beyond it was left as a 15-px stub on Fig. 21.21)
            for r_, c_ in flat["path"]:
                m[max(r_ - halfw, 0):r_ + halfw + 1, max(c_ - halfw, 0):c_ + halfw + 1] = False
            if flat["path"]:
                for r_, c_ in (flat["path"][0], flat["path"][-1]):
                    m[max(r_ - 8, 0):r_ + 9, max(c_ - 8, 0):c_ + 9] = False
            continue
        for g in (hook, flat):
            rr, cc = g["px"]
            for dr in range(-pen, pen + 1):
                m[np.clip(rr + dr, 0, m.shape[0] - 1), cc] = False
        x = flat["x0"]
        rise = []
        for r in range(int(round(flat["r"])) - pen, int(round(hook["r"])) + pen + 1):
            lo = max(x - 6, 0)
            row = np.nonzero(m[r, lo:x + 7])[0]
            if len(row):
                x = lo + int(row[np.argmin(np.abs(row + lo - x))])
            rise.append((r, x))
            m[r, max(x - halfw, 0):x + halfw + 1] = False
        # kept for integral_curves(): the rise as followed, top down
        flat["rise"] = rise
    boxes = [(hook["x0"] - 10, flat["x1"] + 10, flat["r"] - pen - 8) for hook, flat in ints]
    for rr, cc in components(m):
        inside = any(a <= cc.min() and cc.max() <= b and rr.min() >= top for a, b, top in boxes)
        if len(rr) < 12 or (inside and rr.max() < base - 3 * pen):
            m[rr, cc] = False
    return m


def drop_floating(m, pen):
    """Take out integral curves the finders did not pair: in each column the
    lowest ink, and ink stacked on it with gaps of at most 2 pens + 2 px, is
    the spectrum; ink above a wider gap floats. A floating piece is taken
    out when it is wider than 2 pens + 4 px or lies flatter than it stands
    tall (a line's top the scan or the integral strip broke off is narrow
    and upright, and stays), is a thin stroke, AND never falls, left to
    right, by more than 3 pens + 2 px (an integral rises, with a wobble: Fig.
    15.3's dips 10 px; the top of a broad line that an integral passes under
    rises and falls by its height, and stays). Why: a dashed integral, one
    running off the top of the figure
    (Fig. 15.3's 6.83, between 7.07 and 6.90 ppm), and the integrals drawn
    over Fig. 21.9's expansion insets were traced, and a column's whole ink
    extent is the trace there, so each was drawn as a solid bar from the
    curve down to the spectrum. -> (mask, pixels taken out)."""
    m = m.copy()
    cols = np.nonzero(m.any(0))[0]
    if not len(cols):
        return m, 0
    gap = 2 * pen + 2
    fl = np.zeros_like(m)
    for c in cols:
        runs = _runs(np.nonzero(m[:, c])[0])[::-1]
        top = runs[0][0]
        for k, (a, b) in enumerate(runs[1:]):
            if top - b - 1 > gap:
                for a_, b_ in runs[k + 1:]:
                    fl[a_:b_ + 1, c] = True
                break
            top = a
    n = 0
    for rr, cc in components(fl):
        wd, ht = cc.max() - cc.min() + 1, rr.max() - rr.min() + 1
        # narrow: a line's top unless it lies flatter than it stands tall
        # and spans a pen + 4 px (an integral's piece between two lines of a
        # multiplet; Fig. 21.15's 1-3 px apex tips the scan broke off stay)
        if wd <= 2 * pen + 4 and (ht > wd or wd < pen + 4):
            continue
        # a stroke: in most of its columns no taller than 2 pens + 2 px (a
        # tall line leaning over several columns floats there too: Fig.
        # 21.21's TMS, 10 px over 770)
        k_ = cc - cc.min()
        lo_, hi_ = np.full(wd, np.inf), np.full(wd, -np.inf)
        np.minimum.at(lo_, k_, rr)
        np.maximum.at(hi_, k_, rr)
        ext = hi_ - lo_ + 1
        has = np.isfinite(lo_)
        if np.median(ext[has]) > 2 * pen + 2:
            continue
        # Only its thin columns are judged: where a line's flank joins it
        # (Fig. 21.9's 7.4 ppm inset: the integral meets the 7.37 line, which
        # made it "fall" 59 px), the column is the line's. All of it goes
        # (its steep stretches too; what of the line's flank floats with it
        # is a column or two beside a line that stays).
        thin = has & (ext <= 2 * pen + 2)
        mid = ((lo_ + hi_) / 2)[thin]
        # largest fall: a row further down than an earlier column's
        if (mid - np.minimum.accumulate(mid)).max() <= 3 * pen + 2:
            m[rr, cc] = False
            n += len(rr)
    return m, n


def simplify(pts, eps=0.75):
    """Ramer-Douglas-Peucker: the fewest points of a polyline that stay
    within eps px of it (a rise followed row by row is ~900 points, most of
    them on one straight stroke)."""
    if len(pts) < 3:
        return list(pts)
    p_ = np.array(pts, float)
    keep = np.zeros(len(pts), bool)
    keep[[0, -1]] = True
    todo = [(0, len(pts) - 1)]
    while todo:
        i, j = todo.pop()
        if j - i < 2:
            continue
        a, d_ = p_[i], p_[j] - p_[i]
        n_ = np.hypot(*d_)
        seg = p_[i + 1:j]
        dist = (np.abs(d_[0] * (seg[:, 1] - a[1]) - d_[1] * (seg[:, 0] - a[0])) / n_ if n_
                else np.hypot(seg[:, 0] - a[0], seg[:, 1] - a[1]))
        k = int(dist.argmax())
        if dist[k] > eps:
            keep[i + 1 + k] = True
            todo += [(i, i + 1 + k), (i + 1 + k, j)]
    return [pts[k] for k in np.nonzero(keep)[0]]


def integral_curves(ints):
    """The integral curves as the book draws them, for --out's _integrals
    CSV: one polyline (col, row) per integral, from its lower end up. A hook-
    and-flat integral is its hook (each column's mean row), the rise as
    strip_integrals followed it, and its flat; a curve integral is its ink
    path. Where the rise runs up a line, the line's ink is the rise's (the
    book draws them on top of each other)."""
    def stroke(g):
        rr, cc = g["px"]
        return [(c, float(rr[cc == c].mean())) for c in np.unique(cc)]
    out = []
    for hook, flat in ints:
        if "path" in flat:
            p = [(float(c_), float(r_)) for r_, c_ in flat["path"]]
            if p and p[0][1] < p[-1][1]:
                p = p[::-1]
        else:
            lo_r, hi_r = flat["r"], hook["r"]
            rise = [(float(x_), float(r_)) for r_, x_ in reversed(flat.get("rise", [])) if lo_r <= r_ <= hi_r]
            p = stroke(hook) + rise + stroke(flat)
        if len(p) >= 2:
            out.append(simplify(p))
    return out


def multiplets(axes, allpeaks, args):
    """Group the lines of a 1H spectrum by the integrals over them: the lines
    under one integral's rise (main-axis lines within 8 px of its columns) are
    one multiplet. Its lines are read from an inset that covers them when
    there is one (finer: one that holds all the multiplet's main-axis lines),
    else from the main axis. Centre = middle of the outermost lines; 2-4
    evenly spaced lines (spacings within 30 %, J 2-20 Hz) are d,
    t, q with J = mean spacing x --mhz; one line s; anything else m. The
    integral is the step in px, given as H when --protons (the molecule's
    total) is set, else relative to the smallest step."""
    main = axes[0]
    out = []
    # Two integrals over the same lines are one found twice (Fig. 21.15's
    # 1.36 ppm group: by its free ends and again by following its top down):
    # where the multiplet windows overlap by more than half, keep the larger.
    ints = []
    for hk, fl in sorted(main.get("integrals", []), key=lambda hf: -(hf[0]["r"] - hf[1]["r"])):
        a0, a1 = hk["x1"] - 8, fl["x0"] + 8
        if any(min(a1, b1) - max(a0, b0) > 0.5 * min(a1 - a0, b1 - b0) for b0, b1, _, _ in ints):
            continue
        ints.append((a0, a1, hk, fl))
    wins = [sorted(main["a"] * np.array([a0, a1]) + main["b"]) for a0, a1, _, _ in ints]
    for c0, c1, hook, flat in sorted(ints, key=lambda t: t[0]):
        own_win = sorted(main["a"] * np.array([c0, c1]) + main["b"])
        others = [w_ for w_ in wins if not np.allclose(w_, own_win)]
        # lines under 8 % of the group's tallest are noise beside it (Fig.
        # 15.3's 1-3 % bumps beside the 2.15 singlet moved its centre to 2.04);
        # TMS and solvent lines are no multiplet
        if any(p["axis"] == "main" and c0 <= p["col"] <= c1 and (p["ref"] or p["solvent"])
               and p["hpx"] >= 0.5 * max([q["hpx"] for q in allpeaks if q["axis"] == "main"
                                          and c0 <= q["col"] <= c1] + [1])
               for p in allpeaks):
            continue        # the integral of TMS or the solvent
        mp = [p for p in allpeaks if p["axis"] == "main" and c0 <= p["col"] <= c1
              and not p["solvent"] and not p["ref"]]
        if mp:
            top_ = max(p["hpx"] for p in mp)
            mp = [p for p in mp if p["hpx"] >= 0.08 * top_]
        if not mp:
            # no line stands out under it: a broad signal (Fig. 21.18's COOH
            # at 13.2). Its centre is where the integral is half way up.
            cm = (hook["x1"] + flat["x0"]) / 2
            x = main["a"] * cm + main["b"]
            out.append(dict(centre=x, hi=x, lo=x, lines=[], src="main", mult="br s", J=None,
                            step=hook["r"] - flat["r"],
                            main=[dict(ppm=x, hpx=max(1.0, float(np.interp(cm, [p[0] for p in main["pts"]],
                                                                           [main["base"] - min(p[1], p[2])
                                                                            for p in main["pts"]]))),
                                       axis="main")]))
            continue
        # the window: the rise's columns +- 8 px (an integral rises across its
        # whole multiplet), widened to every main-axis line found in it
        lo, hi = sorted(main["a"] * np.array([c0, c1]) + main["b"])
        lo, hi = min([lo] + [p["ppm"] for p in mp]), max([hi] + [p["ppm"] for p in mp])
        tol = 0.0
        src, lines = "main", mp
        for ax in axes[1:]:
            alo, ahi = sorted(ax["a"] * np.array([ax["ruler"]["lo"], ax["ruler"]["hi"]]) + ax["b"])
            # an inset that holds every main-axis line of the multiplet (the
            # window itself may run past the inset's edge: Fig. 21.6)
            if all(alo <= p["ppm"] <= ahi for p in mp):
                inl = sorted((p for p in allpeaks if p["axis"] == ax["name"] and not p["solvent"]
                              and not p["ref"]), key=lambda p: p["ppm"])
                il = [p for p in inl if lo - tol <= p["ppm"] <= hi + tol]
                if il:
                    # lines just outside the window that continue the group's
                    # own spacing (Fig. 15.3's 1.38 of the 1.41 triplet)
                    sp_ = max(np.diff([p["ppm"] for p in il]).max() if len(il) > 1 else 0.0, 0.012)
                    grow = True
                    while grow:
                        grow = False
                        for p in inl:
                            if p not in il and min(abs(p["ppm"] - q["ppm"]) for q in il) <= 1.3 * sp_ \
                                    and not any(w_[0] <= p["ppm"] <= w_[1] for w_ in others):
                                il.append(p)
                                grow = True
                    top_ = max(p["hpx"] for p in il)
                    il = [p for p in il if p["hpx"] >= 0.08 * top_]
                    src, lines = ax["name"], il
                break
        # two clipped "lines" a few px apart are one flat-topped line cut by
        # the inset's frame (Fig. 15.3's 2.15 singlet read as 2.13/2.12)
        lines = sorted(lines, key=lambda p: -p["ppm"])
        merged_ = []
        for p in lines:
            if merged_ and p["clipped"] and merged_[-1]["clipped"] and \
                    abs(merged_[-1]["ppm"] - p["ppm"]) <= 0.02 * (hi - lo + 1e-9) + 0.015:
                merged_[-1] = dict(merged_[-1], ppm=(merged_[-1]["ppm"] + p["ppm"]) / 2)
            else:
                merged_.append(p)
        lines = merged_
        sh = sorted((p["ppm"] for p in lines), reverse=True)
        sp = np.diff(sh[::-1]) if len(sh) > 1 else np.array([])
        if len(sh) == 1:
            mult, J = "s", None
        elif len(sh) <= 4 and sp.max() <= 1.3 * sp.min() and \
                (not args.mhz or 2 <= float(np.mean(sp)) * args.mhz <= 20):
            mult, J = "dtq"[len(sh) - 2], (float(np.mean(sp)) * args.mhz if args.mhz else None)
        else:
            mult, J = "m", None
        out.append(dict(centre=(sh[0] + sh[-1]) / 2, hi=sh[0], lo=sh[-1], lines=sh, src=src, mult=mult, J=J,
                        step=hook["r"] - flat["r"], main=mp))
    if out:
        steps = [m_["step"] for m_ in out]
        for m_ in out:
            m_["int"] = (m_["step"] / sum(steps) * args.protons) if args.protons else m_["step"] / min(steps)
    return out


def label_guard(d, ruler, maj, spec, what, band, report):
    """The trap that cost four figures a wrong scale: FIRST:STEP names the
    first MAJOR tick, printed label or not, and the first major is often
    unlabelled (Figs. 21.19, 21.22, 15.4 begin at 180/160; Fig. 22.4's main
    axis at 10). Without reading the numbers: is there ink under each major
    tick, in the label band below the ruler? If the first major has none and
    the second has, say what the first printed number must then read: the
    tool cannot tell which the FIRST typed was meant to be."""
    if len(maj) < 2:
        return
    sp = abs(maj[1][0] - maj[0][0])
    r0 = ruler["bot"] + max(t[1] for t in ruler["ticks"]) + 2
    r1 = min(ruler["bot"] + band, d.shape[0])
    has = []
    for x, _ in maj:
        c0, c1 = int(max(x - 0.3 * sp, 0)), int(min(x + 0.3 * sp, d.shape[1]))
        has.append(int(d[r0:r1, c0:c1].sum()) >= 15)
    if not has[0] and has[1]:
        first, step = parse_fs(spec, what)
        report.append(f"  CHECK {what}: its first major tick has no number printed under it. With "
                      f"{first:g}:{step:g} that tick is {first:g}, so the first PRINTED number (under "
                      f"the next major) must read {first + step:g}. If it reads {first:g}, use "
                      f"{first - step:g}:{step:g}.")


def write_tex(args, axes, layout, entry, mults, nd):
    """--tex-out: the whole \\labplot call, ready to \\input (in a report's
    markdown: inside a ```{=latex} fence). Layout `figure` (default): one
    \\labplot, each inset drawn inside it where the book has it (its inset=
    key: box in the main axis' units, its own x range, y range and major
    ticks), at the figure's own proportions: the main axis is --plot-width cm
    wide (scale only axis) and as tall as the same px-to-cm scale makes it,
    capped at 18 cm. Layout `separate`: the main plot, then one \\labplot per
    inset. CSV paths are written as given to --out: run from the report's
    folder with paths relative to it."""
    import shlex
    main = axes[0]
    W = args.plot_width
    root, ext = os.path.splitext(args.out)
    # the default names the image, its _ % & # $ escaped (Palleros_Fig22-4_...)
    fn = os.path.basename(args.image)
    for ch in "\\_%&#$":
        fn = fn.replace(ch, "\\" + ch if ch != "\\" else "/")
    cap = args.caption or f"Digitized from \\texttt{{{fn}}}."

    def lst(ax):
        nd_ = nd if ax["name"] == "main" else nd + (0 if mults else 1)
        return ",".join(entry(e, nd_) for e in ax["fan"])
    out = [f"% spectrum_digitize.py {' '.join(shlex.quote(a) for a in sys.argv[1:])}"]
    if layout:
        mcols = main["cols"][1] - main["cols"][0]
        ymin = -2
        H = min(W * (main["ymax"] - ymin) / 100 * main["hm"] / mcols, 18.0)
        opts = ["kind=nmr", "scale only axis", f"width={W:g}cm", f"height={H:.2f}cm",
                f"ymin={ymin}", f"ymax={main['ymax']:g}", "enlarge y limits=false"]
        if main.get("ipath"):
            opts.append(f"integrals={main['ipath']}")
        for ax in axes[1:]:
            xt = ",".join(f"{v:g}" for _, v in ax["maj"])
            opts.append(
                f"inset={{csv={root}_{ax['name']}{ext},\n"
                f"    box={{{ax['box_x'][0]:.4f},{ax['box_bottom']:.2f},{ax['box_x'][1]:.4f},{ax['box_top']:.2f}}},\n"
                f"    peaks={{{lst(ax)}}},\n"
                f"    options={{xmin={ax['xrange'][0]:.4f}, xmax={ax['xrange'][1]:.4f}, "
                f"ymin={ax['ymin']:.2f}, ymax={ax['ymax']:g}, xtick={{{xt}}}}}}}")
        out.append("\\labplot[" + ",\n  ".join(opts) + "]")
        out.append(f"  {{{args.out}}}\n  {{{lst(main)}}}\n  {{{cap}}}")
    else:
        ik = f", integrals={main['ipath']}" if main.get("ipath") else ""
        out.append(f"\\labplot[kind=nmr, ymax={main['ymax']:g}{ik}]\n  {{{args.out}}}\n  {{{lst(main)}}}\n  {{{cap}}}")
        for k, ax in enumerate(axes[1:], 1):
            out.append(f"\\labplot[kind=nmr, height=6cm, ymax={ax['ymax']:g}]\n  {{{root}_{ax['name']}{ext}}}\n"
                       f"  {{{lst(ax)}}}\n  {{Expansion {k}, "
                       f"{ax['xrange'][1]:g}--{ax['xrange'][0]:g} ppm.}}")
    with open(args.tex_out, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print(f"  \\labplot call ({'insets inside, as in the figure' if layout else 'insets as separate plots'}) "
          f"-> {args.tex_out}")


def cmd_nmr(args):
    report = []
    grey = np.array(Image.open(args.image).convert("L"))
    grey = level_by_ruler(grey, report)
    d = grey < args.threshold
    h, w = d.shape
    rulers = find_rulers(d, args, report)
    if not rulers:
        raise CalibrationError("no ppm ruler found (a long line with >= 8 regular ticks below it)")
    # fewer inset rulers than --inset: an expansion's ruler can be short (Fig.
    # 22.4's second is 14 % of the width); look again for shorter ones
    frac0 = args.ruler_frac
    while len(rulers) - 1 < len(args.inset or []) and args.ruler_frac > 0.05:
        args.ruler_frac = round(args.ruler_frac - 0.025, 3)
        rulers = find_rulers(d, args, []) or rulers
    if len(rulers) - 1 < len(args.inset or []):
        # last: a ruler with as few as two ticks (Fig. 21.9's CH2 inset has
        # only its 4.4 and 4.3 marks); two ticks with given values calibrate
        # exactly, so nothing checks them -- look at the overlay
        args.min_ticks = 2
        rulers = find_rulers(d, args, []) or rulers
        report.append("  WARNING: rulers with only 2-4 ticks accepted (more --inset than rulers found); "
                      "a 2-tick ruler's calibration cannot be checked -- look at the overlay")
    if args.ruler_frac != frac0:
        report.append(f"  (looked again for shorter rulers: --ruler-frac {args.ruler_frac:g}, "
                      f"{len(rulers) - 1} inset ruler(s))")
    main = rulers[0]
    insets = rulers[1:]
    report.append(f"rulers: main rows {main['top']}-{main['bot']} cols {main['lo']}-{main['hi']}; "
                  f"{len(insets)} inset(s)" + "".join(f"; inset rows {r['top']}-{r['bot']} cols {r['lo']}-{r['hi']}"
                                                     for r in insets))
    if len(insets) < len(args.inset or []):
        report.append(f"  WARNING: {len(args.inset)} --inset given but only {len(insets)} inset ruler(s) found; "
                      f"an inset ruler shorter than --ruler-frac ({args.ruler_frac:g} of the width) is not "
                      f"looked at (Fig. 22.4's second inset needs 0.1)")
    if len(insets) > len(args.inset or []):
        report.append(f"  WARNING: {len(insets)} inset ruler(s) found but {len(args.inset or [])} --inset given; "
                      f"the uncalibrated ones are skipped (top to bottom order)")
    # reading order: rows of insets top to bottom (rulers within 5 % of the
    # height are one row), each row left to right
    ins_sorted = sorted(insets, key=lambda r: (round(r["bot"] / (0.05 * h)), r["lo"]))
    if args.show_rulers or not args.x_ticks:
        # which ruler is which: the order --inset is read in
        print(f"spectrum_digitize nmr: {os.path.basename(args.image)}")
        for line in report:
            print(line)
        print("  rulers, in the order --x-ticks and then --inset are read (top of the ruler line, "
              "% of the height; columns, % of the width; ticks found):")
        for k, r in enumerate([main] + ins_sorted):
            name = "main (--x-ticks)" if k == 0 else f"inset {k} (--inset no. {k})"
            print(f"    {name}: row {100 * r['top'] / h:.0f} %, columns {100 * r['lo'] / w:.0f}-"
                  f"{100 * r['hi'] / w:.0f} %, {len(r['ticks'])} ticks")
        if args.overlay:
            im = Image.fromarray(grey).convert("RGB")
            dr = ImageDraw.Draw(im)
            fnt = _font(max(28, w // 50))
            for k, r in enumerate([main] + ins_sorted):
                col = (230, 0, 0) if k == 0 else (0, 90, 255)
                dr.line([(r["lo"], r["bot"] + 4), (r["hi"], r["bot"] + 4)], fill=col, width=6)
                dr.text((r["lo"], r["bot"] + 10), "main" if k == 0 else f"inset {k}", fill=col, font=fnt)
            im.save(args.overlay)
            print(f"  numbered rulers drawn on {args.overlay}")
        if not args.x_ticks:
            print("  give --x-ticks FIRST:STEP (and --inset FIRST:STEP per inset, in this order) to read it")
        return 0
    axes = []
    a, b, maj, res = calibrate(main["ticks"], args.x_ticks, "main ruler (ppm)", report)
    label_guard(d, main, maj, args.x_ticks, "main ruler", args.label_band, report)
    axes.append(dict(name="main", ruler=main, a=a, b=b, maj=maj))
    for k, r in enumerate(ins_sorted):
        if args.inset and k < len(args.inset):
            a, b, maj, res = calibrate(r["ticks"], args.inset[k], f"inset {k + 1} ruler (ppm)", report)
            label_guard(d, r, maj, args.inset[k], f"inset {k + 1} ruler", args.label_band, report)
            axes.append(dict(name=f"inset{k + 1}", ruler=r, a=a, b=b, maj=maj))

    # trace regions
    lab_h = args.label_band
    for ax in axes:
        r = ax["ruler"]
        above = [o for o in rulers if o["bot"] < r["top"] and o["hi"] > r["lo"] and o["lo"] < r["hi"]]
        top_lim = max([o["bot"] + lab_h for o in above], default=0) if ax["name"] != "main" else 0
        region = np.zeros_like(d)
        region[top_lim:r["top"] - 2, r["lo"]:r["hi"] + 1] = d[top_lim:r["top"] - 2, r["lo"]:r["hi"] + 1]
        if ax["name"] == "main":
            for o in insets:
                # the inset's whole box: its trace, ruler and labels
                region[:o["bot"] + lab_h, max(o["lo"] - 15, 0):o["hi"] + 16] = False
        comps = [c for c in components(region) if len(c[0]) > 0]
        if not comps:
            raise CalibrationError(f"{ax['name']}: no trace ink above the ruler")
        # The trace is the biggest blob (the baseline noise joins it into one).
        # Other blobs join it only when they sit within 8 rows and 4 columns of it: the top of a thin peak the scan broke off (Fig. 21.16's
        # 9.3 ppm line is in two pieces). Label leader lines stand further off
        # (Fig. 21.16's '19.22' leader ends 180 px above its peak) and text,
        # arrows and specks are not over the trace at all.
        comps.sort(key=lambda c: -len(c[0]))
        keep = np.zeros_like(d)
        keep[comps[0]] = True
        rest = comps[1:]
        grown = True
        while grown and rest:
            grown = False
            near_ = keep.copy()
            for _ in range(8):
                near_[:-1] |= near_[1:]
                near_[1:] |= near_[:-1]
            # and 4 columns sideways: Fig. 21.6's baseline has a 2-px scan
            # break at column 797 that cut the trace in two
            for _ in range(4):
                near_[:, 1:] |= near_[:, :-1].copy()
                near_[:, :-1] |= near_[:, 1:].copy()
            left = []
            for rr, cc in rest:
                if near_[rr, cc].any():
                    keep[rr, cc] = True
                    grown = True
                else:
                    left.append((rr, cc))
            rest = left
        ax["mask"] = keep
        ax["top_lim"] = top_lim
        ax["floating"] = rest

    print(f"spectrum_digitize nmr: {os.path.basename(args.image)}")
    for line in report:
        print(line)
    status = 0
    allpeaks = []
    pen_main = None

    def trace(mask):
        # The 20th percentile of an inset's column extents is no pen when an
        # integral runs over most of its width (Fig. 21.9's insets: 57 and 77
        # px, against 9 on the main axis and a 4-px stroke). When an inset
        # reads more than twice the main axis's pen, its pen is the commonest
        # length of its single vertical runs instead (the integral and the
        # baseline are separate runs there; Fig. 21.9's: 4 and 5 px), at
        # most the main's. Within
        # that, the inset's own (Fig. 21.15: 3 in its insets, 2 on the main).
        pts_, pen_, tops_ = envelope_trace(mask)
        if pen_main is not None and pen_ > 2 * pen_main + 2:
            lens = [b_ - a_ + 1 for c_ in np.nonzero(mask.any(0))[0]
                    for a_, b_ in _runs(np.nonzero(mask[:, c_])[0])]
            pen_ = min(int(np.bincount(lens).argmax()), pen_main)
        return pts_, pen_, tops_
    for ax in axes:
        pts, pen, tops = trace(ax["mask"])
        if not pts:
            raise CalibrationError(f"{ax['name']}: empty trace")
        # main axis only: an expansion inset of a 1H figure carries no
        # integrals of its own, and in one the finders take pieces of the
        # inset's own lines for curves (tried: Figs. 21.3, 21.6, 21.15 lost
        # real lines). Where a figure's integrals run THROUGH its insets (Fig.
        # 21.9) they are dropped from the inset's trace by drop_floating.
        # and 1H only (an axis under 30 ppm): a 13C figure has none, and on
        # Fig. 21.16 the label bracket of 19.85/19.22 was taken for one
        mg = min_gap_cols(abs(ax["a"]), args.mhz)
        span_ = abs(ax["a"]) * (ax["ruler"]["hi"] - ax["ruler"]["lo"])
        look = not args.no_integrals and ax["name"] == "main" and span_ < 30
        ax["integrals"] = find_integrals(ax["mask"], pen, min_gap=mg) if look else []
        if look:
            cols_ = np.nonzero(ax["mask"].any(0))[0]
            base_ = float(np.median([np.nonzero(ax["mask"][:, c])[0].max() for c in cols_]))
            # An integral need not touch the trace: Fig. 21.6's OH integral
            # floats above its broad line. Loose pieces shaped like one -- at
            # least 15 px each way, thin (no more ink than 1.5 pens along its
            # width + height), rising to the right (rows fall as columns grow,
            # correlation < -0.6) -- join the search, not the trace.
            union = ax["mask"].copy()
            for rr, cc in ax.get("floating", []):
                wd, ht = cc.max() - cc.min(), rr.max() - rr.min()
                if wd >= 15 and ht >= 15 and len(rr) <= 1.5 * pen * (wd + ht) and \
                        np.corrcoef(cc, rr)[0, 1] < -0.6:
                    union[rr, cc] = True
            ax["integrals"] += find_curve_integrals(union, pen, ax["integrals"], base_, min_gap=mg)
            ax["integrals"].sort(key=lambda hf: hf[0]["x1"])
        before = ax["mask"]
        if ax["integrals"]:
            ax["mask"] = strip_integrals(ax["mask"], ax["integrals"], pen)
            pts, pen, tops = trace(ax["mask"])
            print(f"  {ax['name']}: {len(ax['integrals'])} integral curve(s) found and taken out of the trace: "
                  + ", ".join(f"{ax['a'] * h_['x1'] + ax['b']:.2f}-{ax['a'] * f_['x0'] + ax['b']:.2f} ppm "
                              f"({h_['r'] - f_['r']:.0f} px)" for h_, f_ in ax["integrals"]))
        # 1H only (13C figures draw no integrals)
        if not args.no_integrals and span_ < 30:
            ax["mask"], nfl = drop_floating(ax["mask"], pen)
            ax["floating_px"] = nfl
            if nfl:
                # the pen stays: read again without the integral it is wider
                pts, _, tops = trace(ax["mask"])
                print(f"  {ax['name']}: {nfl} px of ink floating over the baseline left out of the trace "
                      f"(an integral curve not found as one)")
        rd = redraw(pts, ax["mask"].shape)
        reach = 1 + int(np.ceil((pen - 1) / 2))
        tr = ax["mask"]
        recall = (tr & dilate(rd, reach)).sum() / max(tr.sum(), 1)
        # precision against the ink before the integrals came out (where a rise
        # ran along a line, the line is drawn whole and the figure has ink
        # there), widened 6 px sideways: a tall line leaning a few columns
        # (Fig. 21.21's TMS, 10 px over 770) is drawn as each column's whole
        # extent, a 0.05-ppm wedge the check counted as 12 % of the trace
        side = before.copy()
        for _ in range(6):
            side[:, 1:] |= before[:, :-1]
            side[:, :-1] |= before[:, 1:]
            before = side.copy()
        prec = (rd & dilate(side, reach)).sum() / max(rd.sum(), 1)
        ok = recall >= 0.98 and prec >= 0.98
        if not ok:
            status = 2
        peaks, base, noise, minh = nmr_peaks(pts, tops, tr, max(ax["top_lim"], 0), args, pen)
        if pen_main is None:
            pen_main = pen
        ax.update(pts=pts, base=base, peaks=peaks, draw=envelope_trace(hthin(ax["mask"], pen))[0])
        span = ax["a"] * np.array([ax["ruler"]["lo"], ax["ruler"]["hi"]]) + ax["b"]
        print(f"  {ax['name']}: {span[0]:.2f} -> {span[1]:.2f} ppm, {abs(ax['a']):.4f} ppm/px; trace "
              f"{len(pts)} columns, pen {pen} px, baseline row {base:.0f}, noise {noise:.1f} px, "
              f"peaks >= {minh:.0f} px: {len(peaks)}; redraw recall {recall:.4f}, precision {prec:.4f}"
              f"{'' if ok else '  FAIL (< 0.98)'}")
        tallest = max((p[2] for p in peaks), default=1)
        for c, ar, hp, clip in peaks:
            allpeaks.append(dict(axis=ax["name"], ppm=ax["a"] * c + ax["b"], hpx=hp, col=c, row=ar,
                                 clipped=clip, rel=100 * hp / tallest, solvent=False, ref=False))
    # solvent
    if args.solvent is not None:
        # The window is centred on the line nearest --solvent within twice its
        # width (the figure's own offset: Fig. 21.10 prints CDCl3 at 77.5-77.8),
        # not on --solvent itself: centred on 77.16 a window wide enough for
        # that also took benzhydrol's CH-OH line at 76.2 (Fig. 21.7) as solvent.
        h1 = args.solvent <= 20
        win = args.solvent_window if args.solvent_window is not None else (0.02 if h1 else 0.5)
        # 1H: never a line under an integral: Fig. 21.6's para-H lines at
        # 7.29/7.31 were taken for CHCl3 (residual CHCl3 is a small lone line,
        # Fig. 22.4's at 7.27; Fig. 15.3's, which the book marks, reads 7.28)
        spans = [sorted(axes[0]["a"] * np.array([hk["x0"], fl["x1"]]) + axes[0]["b"])
                 for hk, fl in axes[0].get("integrals", [])] if h1 else []
        cands = [p for p in allpeaks if not any(lo_ <= p["ppm"] <= hi_ for lo_, hi_ in spans)]
        near = [p for p in cands if abs(p["ppm"] - args.solvent) <= 2 * win]
        cen0 = min(near, key=lambda p: abs(p["ppm"] - args.solvent))["ppm"] if near else args.solvent
        sv = [p for p in cands if abs(p["ppm"] - cen0) <= win]
        for p in sv:
            p["solvent"] = True
        if sv:
            main_sv = [p for p in sv if p["axis"] == "main"] or sv
            cen = np.mean([p["ppm"] for p in main_sv])
            print(f"  solvent: {len(sv)} line(s) within {win} ppm of {args.solvent}: "
                  + ", ".join(f"{p['ppm']:.2f}" for p in sv)
                  + f"; centre {cen:.2f} ({cen - args.solvent:+.2f} from {args.solvent}, reported, not applied)")
        else:
            print(f"  solvent: no peak within {win} ppm of {args.solvent}")
    # The reference line (TMS, 0 ppm) is treated like the solvent: in the
    # peak table, out of the labels, its offset reported. Same window rule;
    # the axis's span tells 13C (0.5 ppm) from 1H (0.05).
    if args.tms is not None:
        span = abs(axes[0]["a"]) * (axes[0]["ruler"]["hi"] - axes[0]["ruler"]["lo"])
        win = 0.5 if span > 30 else 0.05
        near = [p for p in allpeaks if p["axis"] == "main" and abs(p["ppm"] - args.tms) <= 2 * win]
        if near:
            ref = min(near, key=lambda p: abs(p["ppm"] - args.tms))
            for p in allpeaks:
                if p["axis"] == "main" and abs(p["ppm"] - ref["ppm"]) <= win and not p["solvent"]:
                    p["ref"] = True
            print(f"  reference: line at {ref['ppm']:.2f} ({ref['ppm'] - args.tms:+.2f} from {args.tms:g}, "
                  f"reported, not applied); left out of the labels")
    nd = args.decimals
    print("  peaks (ppm, height % of the tallest on its axis; * clipped, s solvent, r reference):")
    for ax in axes:
        pk = [p for p in allpeaks if p["axis"] == ax["name"]]
        print(f"    {ax['name']}: " + "  ".join(
            f"{p['ppm']:.{nd}f}({p['rel']:.0f}{'*' if p['clipped'] else ''}{'s' if p['solvent'] else ''}"
            f"{'r' if p['ref'] else ''})"
            for p in sorted(pk, key=lambda p: -p["ppm"])))
    if args.check:
        want = [float(v) for v in args.check.replace(" ", "").split(",") if v]
        ok = 0
        for v in want:
            # prefer an inset that covers v (finer scale), else the main axis
            cand = []
            for ax in axes[::-1]:
                lo_, hi_ = sorted(ax["a"] * np.array([ax["ruler"]["lo"], ax["ruler"]["hi"]]) + ax["b"])
                if lo_ <= v <= hi_:
                    cand = [p for p in allpeaks if p["axis"] == ax["name"]]
                    tol = args.check_px * abs(ax["a"])
                    break
            if not cand:
                print(f"  check {v}: outside every axis")
                status = 2
                continue
            p = min(cand, key=lambda p: abs(p["ppm"] - v))
            dv = p["ppm"] - v
            good = abs(dv) <= tol
            ok += good
            print(f"  check {v:.{nd}f}: {p['axis']} {p['ppm']:.{nd + 1}f} ({dv:+.{nd + 1}f})"
                  + ("" if good else f"  MISS (> {args.check_px:g} px = {tol:.3f})"))
            if not good:
                status = 2
        print(f"  check: {ok}/{len(want)} within {args.check_px:g} px")

    mults = multiplets(axes, allpeaks, args)
    if mults:
        unit = "H" if args.protons else "rel."
        print("  multiplets (one per integral; lines from the inset that covers them, else the main axis):")
        for m_ in mults:
            j = f", J = {m_['J']:.1f} Hz" if m_["J"] is not None else ""
            print(f"    {m_['centre']:.{nd}f}  {m_['mult']}{j}  {m_['int']:.2f} {unit}  "
                  f"({m_['hi']:.{nd + 1}f}-{m_['lo']:.{nd + 1}f}, {len(m_['lines'])} line(s) on {m_['src']}; "
                  f"step {m_['step']:.1f} px)")
        if args.multiplets_out:
            with open(args.multiplets_out, "w", encoding="utf-8") as f:
                f.write("centre,from,to,multiplicity,J_Hz,integral,step_px,lines,source\n")
                for m_ in mults:
                    f.write(f"{m_['centre']:.{nd + 1}f},{m_['hi']:.{nd + 1}f},{m_['lo']:.{nd + 1}f},{m_['mult']},"
                            f"{'' if m_['J'] is None else f'{m_[chr(74)]:.1f}'},{m_['int']:.2f},{m_['step']:.1f},"
                            f"{' '.join(f'{v:.{nd + 1}f}' for v in m_['lines'])},{m_['src']}\n")

    def entry(e, nd_=None):
        x, ay, ky, lx, ly, t = e
        n_ = nd if nd_ is None else nd_
        return f"{x:.{n_}f}/{ay:.1f}/{'' if ky is None else f'{ky:.1f}'}/{lx:.2f}/{ly:g}/{t}"

    def htext(m_):
        if not args.label_integrals:
            return ""
        v = m_["int"]
        return (f"{m_['centre']:.{nd}f} ({v:.0f}H)" if args.protons else f"{m_['centre']:.{nd}f} ({v:.1f})")

    # Geometry of every axis: its trace in % of its own tallest line, its
    # range in ppm, and (an inset) where it sits in the figure.
    W = args.plot_width
    main = axes[0]
    for ax in axes:
        pts_, base_ = ax["pts"], ax["base"]
        ax["hm"] = max(base_ - min(p[1], p[2]) for p in pts_)
        ax["shifts"] = [ax["a"] * p[0] + ax["b"] for p in pts_]
        ax["trace"] = [(ax["a"] * c + ax["b"], 100 * (base_ - min(e, x)) / ax["hm"]) for c, e, x in pts_]
        ax["range"] = (min(ax["shifts"]), max(ax["shifts"]))
        ax["cols"] = (min(p[0] for p in pts_), max(p[0] for p in pts_))
    # The integral curves, drawn back as the book draws them (--out's
    # _integrals CSV, \labplot's integrals= key): taken out of the trace, the
    # lines under a rise end where the rise starts (Fig. 22.4's main axis:
    # 7.38's three protons stood shorter than 7.71's one), and the rise drawn
    # over them hides that as the book's does. Only when every integral's ink
    # was found as one (no drop_floating on any axis): Figs. 21.9 and 15.3
    # would get broken pieces.
    main["icurves"] = []
    if main.get("integrals") and not args.no_integral_curves:
        loose = [f"{a_['name']} {a_['floating_px']} px" for a_ in axes if a_.get("floating_px")]
        if loose:
            print(f"  integral curves not drawn: ink of integrals not found as curves was left out "
                  f"({', '.join(loose)}); drawn, they would be broken pieces")
        else:
            main["icurves"] = [[(main["a"] * c + main["b"], 100 * (main["base"] - r) / main["hm"]) for c, r in poly]
                               for poly in integral_curves(main["integrals"])]
    main["ipath"] = None
    if main["icurves"] and args.out:
        root_, ext_ = os.path.splitext(args.out)
        main["ipath"] = f"{root_}_integrals{ext_}"
    # for the labels: the curves as points one main-axis column apart (the
    # simplified polyline's long flats have no points in their middle)
    ink = []
    for poly in main["icurves"]:
        for (x0, y0), (x1, y1) in zip(poly[:-1], poly[1:]):
            n_ = max(int(abs(x1 - x0) / abs(main["a"])), 1)
            ink += [(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t) for t in np.linspace(0, 1, n_ + 1)]
    layout = args.inset_layout == "figure" and len(axes) > 1
    mcols = main["cols"][1] - main["cols"][0]
    for ax in axes[1:]:
        r = ax["ruler"]
        # the inset's plot rectangle: from its ruler's ends, bottom on its
        # ruler line, in the main axis' units (ppm across, % of the main
        # axis' tallest line up); its own y axis starts at the ruler, below
        # its baseline, so the trace sits in the box where it sits in the book
        ax["box_x"] = (main["a"] * r["lo"] + main["b"], main["a"] * r["hi"] + main["b"])
        ax["box_bottom"] = 100 * (main["base"] - r["top"]) / main["hm"]
        ax["ymin"] = -100 * (r["top"] - ax["base"]) / ax["hm"]
        ax["xrange"] = tuple(sorted(ax["a"] * np.array([r["lo"], r["hi"]]) + ax["b"]))
        ax["width_cm"] = W * (r["hi"] - r["lo"]) / mcols if layout else W

    def covered(x):
        return layout and any(a_[0] - 1e-9 <= x <= a_[1] + 1e-9 for a_ in (ax_["xrange"] for ax_ in axes[1:]))

    def labels_for(ax, extra_trace=(), obstacles=()):
        hm = ax["hm"]
        nd_ax = nd if ax["name"] == "main" or mults else nd + 1
        # 1 % of this axis in mm, against a full \\labplot's ~0.67: in the
        # figure layout the book's own px-to-mm scale holds for every axis
        unit = (100 / hm) * (mcols / (W * 10)) / 1.5 if layout else 1.0

        def lpct(x_, t_):
            # a rotated label's length in % of this axis: 1.4 mm a character
            # + 1 mm (a 4-character number is the old fixed 12 %; '7.38 (3H)'
            # is twice that, and the solvent mark sat on it)
            return (len(t_ or f"{x_:.{nd_ax}f}") * 1.4 + 1) * 1.5 * unit
        on = [p for p in allpeaks if p["axis"] == ax["name"]]
        lines = sorted((p for p in on if not p["solvent"] and not p["ref"]), key=lambda p: -p["ppm"])
        if mults:
            # 1H: one label per multiplet -- on the main axis unless an inset
            # shows it (layout), in an inset for the multiplets inside it
            if ax["name"] == "main":
                ms = [m_ for m_ in mults if not covered(m_["centre"])]
            else:
                ms = [m_ for m_ in mults if ax["xrange"][0] <= m_["centre"] <= ax["xrange"][1]]
            entries = []
            for m_ in ms:
                own = [p for p in on if m_["lo"] - 0.02 <= p["ppm"] <= m_["hi"] + 0.02] or m_["main"]
                src = own if own else m_["main"]
                ap = max(100 * p["hpx"] / (hm if p["axis"] == ax["name"] else main["hm"]) for p in src)
                entries.append((float(f"{m_['centre']:.{nd}f}"), ap, htext(m_)))
        else:
            entries = [(float(f"{p['ppm']:.{nd_ax}f}"), 100 * p["hpx"] / hm, "") for p in lines
                       if ax["name"] != "main" or not covered(p["ppm"])]
        sv = [p for p in on if p["solvent"]]
        arrow = None
        if sv and args.solvent_style != "none" and not (ax["name"] == "main" and covered(np.mean([p["ppm"] for p in sv]))):
            sx = round(float(np.mean([p["ppm"] for p in sv])), nd)
            sa = max(100 * p["hpx"] / hm for p in sv)
            if args.solvent_style == "label":
                entries.append((sx, sa, args.solvent_label))
            else:
                arrow = (sx, sa)
        trace = list(ax["trace"]) + list(extra_trace)
        lo_, hi_ = ax["range"] if ax["name"] == "main" or not layout else ax["xrange"]
        fan = fan_labels(entries, hi_, lo_, ax["width_cm"] if ax["name"] != "main" else W,
                         pitch_mm=args.pitch, mode=args.label_style, trace=trace, unit=unit)
        if obstacles:
            # A label that would run into an inset (Fig. 21.10's 63.5 line
            # stands under its inset's tick labels): upright just over its
            # line if that fits under the inset (an upright number is ~3 mm,
            # a rotated one ~7), else lifted over the inset.
            mm_ = (ax["range"][1] - ax["range"][0]) / (W * 10)
            U, g_ = 4 * unit, 1.5 * unit      # 1 % ~ 0.67 mm x unit
            tr_ = np.array(ax["trace"])
            for k, (x, a, ky, lx, ly, t) in enumerate(fan):
                L = lpct(x, t)
                hit = [o for o in obstacles if o[0] - 2 * mm_ <= lx <= o[1] + 2 * mm_ and ly < o[3] and ly + L > o[2]]
                if not hit:
                    continue
                lo_ob = min(o[2] for o in hit)
                txt = t or f"{x:.{nd_ax}f}"
                half = (len(txt) * 1.4 / 2 + 0.5) * mm_
                # over the line, and over an integral curve drawn across it
                # (Fig. 21.6's 2.31 under its inset: the curve reaches 17 %;
                # over the inset instead, the leader ran up the whole plot)
                floor = max([a] + [y_ for x_, y_ in extra_trace if abs(x_ - x) <= half])
                # not moved sideways by the fan (a float compare: 2.31 came
                # back from mm and ppm as 2.3100000000000005)
                alone = abs(lx - x) < 1e-6
                if floor + g_ + U <= lo_ob and alone:
                    fan[k] = (x, a, None, x, round(floor + g_, 1), txt)
                    continue
                # no room over it: beside its top, the number on a short arrow
                # (Fig. 21.10's 63.5 nearly touches its inset's tick labels)
                for side in (-1, 1):
                    tx = x + side * (2.5 + len(txt) * 0.7) * mm_
                    ty = a - 6 * unit
                    under = tr_[(tr_[:, 0] >= tx - half) & (tr_[:, 0] <= tx + half), 1]
                    if alone and ty > 2 and ty + U <= lo_ob and (not len(under) or under.max() < ty - unit):
                        fan[k] = (x, a, None, round(tx, 4), round(ty, 1), txt)
                        break
                else:
                    top_ = max(o[3] for o in hit) + 4 * unit
                    fan[k] = (x, a, max(ky, top_ - 4 * unit) if ky is not None else ky, lx, round(top_, 1), t)
        if arrow:
            fan.append(callout(*arrow, hi_, lo_, ax["width_cm"] if ax["name"] != "main" else W,
                               args.solvent_label, trace, labels=fan, pitch_mm=args.pitch, unit=unit,
                               obstacles=obstacles))
        # TMS and unmarked solvent peaks still belong to the plotted trace.
        # Keep the existing unlabelled-trace headroom of 10 * unit even
        # when shorter peaks have labels, on the main axis and each inset.
        ymax = round(max([max(y_ for _, y_ in trace) + 10 * unit] +
                         [e[4] + (5 * unit if e[2] is None else lpct(e[0], e[5]) + 2 * unit)
                          for e in fan]))
        return fan, ymax

    # insets first: their boxes are obstacles for the main axis' labels
    for ax in axes[1:]:
        ax["fan"], ax["ymax"] = labels_for(ax)
        r = ax["ruler"]
        top_row = r["top"] - (ax["ymax"] - ax["ymin"]) / 100 * ax["hm"]
        ax["box_top"] = 100 * (main["base"] - top_row) / main["hm"]
    obst = []
    if layout:
        for ax in axes[1:]:
            # the box, and the tick labels drawn under it: a tick and a
            # \\scriptsize number, ~5 mm (the book's own label band, ~3.9 mm,
            # let Fig. 21.10's 63.5 sit on the inset's '132')
            band = 5 * (100 / main["hm"]) * (mcols / (W * 10))
            obst.append((min(ax["box_x"]), max(ax["box_x"]), ax["box_bottom"] - band, ax["box_top"] + 2))
    main["fan"], main["ymax"] = labels_for(main, extra_trace=ink, obstacles=obst)
    if ink:
        main["ymax"] = max(main["ymax"], round(max(y_ for _, y_ in ink) + 3))
    if layout:
        main["ymax"] = max(main["ymax"], round(max(ax["box_top"] for ax in axes[1:]) + 3))
    for ax in axes:
        fan, ymax = ax["fan"], ax["ymax"]
        nd_ = nd if ax["name"] == "main" else nd + (0 if mults else 1)
        if fan:
            print(f"  \\labplot peak list, {ax['name']} (fan: x/apex_y/knee_y/label_x/label_y/text; "
                  f"labels '{args.label_style}', pass ymax={ymax:g}):")
            print("    " + ",".join(entry(e, nd_) for e in fan))
        if args.list_out:
            path = args.list_out
            if ax["name"] != "main":
                root, ext = os.path.splitext(args.list_out)
                path = f"{root}_{ax['name']}{ext}"
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"ymax={ymax:g}\n" if fan else "\n")
                f.write(",".join(entry(e, nd_) for e in fan) + "\n")
    if args.tex_out:
        write_tex(args, axes, layout, entry, mults, nd)
    main_ax = axes[0]
    pts = main_ax["pts"]
    base = main_ax["base"]
    hmax = max(base - min(p[1], p[2]) for p in pts)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write("shift,intensity\n")
            for c, e, x in main_ax["draw"]:
                for r in ((e, x) if e != x else (e,)):
                    f.write(f"{main_ax['a'] * c + main_ax['b']:.4f},{100 * (base - r) / hmax:.2f}\n")
        if main_ax["ipath"]:
            # one curve after another, a nan row between (a gap: the integrals=
            # key draws with unbounded coords=jump)
            with open(main_ax["ipath"], "w", encoding="utf-8") as f:
                f.write("shift,intensity\n")
                for k, poly in enumerate(main_ax["icurves"]):
                    if k:
                        f.write("nan,nan\n")
                    for x_, y_ in poly:
                        f.write(f"{x_:.4f},{y_:.2f}\n")
            print(f"  integral curves ({len(main_ax['icurves'])}) -> {main_ax['ipath']}")
        for ax in axes[1:]:
            root, ext = os.path.splitext(args.out)
            path = f"{root}_{ax['name']}{ext}"
            bx = ax["base"]
            hm = max(bx - min(p[1], p[2]) for p in ax["pts"])
            with open(path, "w", encoding="utf-8") as f:
                f.write("shift,intensity\n")
                for c, e, x in ax["draw"]:
                    for r in ((e, x) if e != x else (e,)):
                        f.write(f"{ax['a'] * c + ax['b']:.4f},{100 * (bx - r) / hm:.2f}\n")
            print(f"  {ax['name']} trace -> {path}")
    if args.peaks_out:
        with open(args.peaks_out, "w", encoding="utf-8") as f:
            f.write("shift,height,clipped,solvent,reference,axis\n")
            for p in sorted(allpeaks, key=lambda p: (p["axis"], -p["ppm"])):
                f.write(f"{p['ppm']:.{nd + 1}f},{p['rel']:.1f},{int(p['clipped'])},{int(p['solvent'])},"
                        f"{int(p['ref'])},{p['axis']}\n")
    if args.overlay:
        im = Image.fromarray(grey).convert("RGB")
        dr = ImageDraw.Draw(im)
        fnt = _font(max(16, w // 90))
        for ax in axes:
            rb = ax["ruler"]["bot"]
            for p, v in ax["maj"]:
                dr.line([(p, rb + 2), (p, rb + 30)], fill=(0, 90, 255), width=3)
                dr.text((p + 4, rb + 28), fmt(v, 2), fill=(0, 90, 255), font=fnt)
            ys, xs = np.nonzero(ax["mask"])
            px = im.load()
            for y, x in zip(ys, xs):
                px[int(x), int(y)] = (230, 0, 0)
            if ax is main_ax:
                # the integral curves to be drawn, in blue
                for poly in integral_curves(ax["integrals"]) if ax["icurves"] else []:
                    dr.line([(c_, r_) for c_, r_ in poly], fill=(0, 90, 255), width=3)
            for p in [q for q in allpeaks if q["axis"] == ax["name"]]:
                col = (0, 150, 0) if not p["solvent"] else (200, 120, 0)
                dr.line([(p["col"], p["row"] - 4), (p["col"], p["row"] - 22)], fill=col, width=3)
                dr.text((p["col"] + 3, p["row"] - 46), f"{p['ppm']:.{nd}f}", fill=col, font=fnt)
        im.save(args.overlay)
    return status


def main(argv=None):
    ap = argparse.ArgumentParser(prog="irspec spectrum", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("image")
    common.add_argument("--x-ticks", help="FIRST:STEP of the major x ticks, left to right (nmr: leave it "
                                           "out, or --show-rulers, to see the rulers first)")
    common.add_argument("--out", help="CSV for \\labplot")
    common.add_argument("--peaks-out", help="peak table CSV")
    common.add_argument("--check", help="comma list of values printed on / read off the figure")
    common.add_argument("--overlay", help="save the levelled image with ticks, trace and peaks drawn")
    common.add_argument("--list-out", help="write the \\labplot peak list to a file: line 1 the extra "
                                           "\\labplot options it needs (nmr: ymax=...), line 2 the list")
    common.add_argument("--threshold", type=int, default=128)
    common.add_argument("--tick-width", type=int, default=16,
                        help="widest run counted as a tick (px; Fig. 15.5's thick-pen y ticks are 14)")
    common.add_argument("--label-gap", type=float, default=4.0,
                        help="label_y = apex + this (y-axis %%) in the printed peak list")
    p = sub.add_parser("ms", parents=[common], help="stick mass spectrum")
    p.add_argument("--y-ticks", required=True, help="FIRST:STEP of the major y ticks, from the bottom up")
    p.add_argument("--labels", help="N (the N tallest local maxima) or a comma list of m/z")
    p.add_argument("--min-stick", type=int, default=3, help="shortest stick (px)")
    p.add_argument("--max-stick-width", type=int, default=14, help="widest stick (px)")
    p.add_argument("--max-gap", type=int, default=14, help="longest scan gap bridged in a stick (rows)")
    p.set_defaults(func=cmd_ms)
    p = sub.add_parser("nmr", parents=[common], help="NMR trace on a ppm ruler")
    p.add_argument("--inset", action="append",
                   help="FIRST:STEP for an inset ruler (repeat, in --show-rulers' order: top to bottom)")
    p.add_argument("--show-rulers", action="store_true",
                   help="list the rulers found, numbered in the order --inset is read, draw them on "
                        "--overlay, and stop")
    p.add_argument("--solvent", type=float, help="solvent shift, e.g. 77.16 (13C CDCl3) or 7.26 (1H)")
    p.add_argument("--solvent-window", type=float,
                   help="ppm either side of the solvent line (default 0.5 for 13C, 0.02 for 1H)")
    p.add_argument("--tms", type=float, default=0.0,
                   help="reference line (default 0, TMS): kept out of the labels, offset reported")
    p.add_argument("--min-height", type=float, help="smallest peak (px above the baseline)")
    p.add_argument("--check-px", type=float, default=3.0,
                   help="--check tolerance in px of the axis (default 3: a hand read-out's own +-2-3 px)")
    p.add_argument("--peak-window", type=int, default=3, help="a peak is the highest within +- this many columns")
    p.add_argument("--blob-frac", type=float, default=0.02)
    p.add_argument("--ruler-frac", type=float, default=0.15, help="shortest ruler, fraction of the width")
    p.add_argument("--label-band", type=int, default=70, help="height of a ruler's tick labels below it (px)")
    p.add_argument("--decimals", type=int, default=1)
    p.add_argument("--plot-width", type=float, default=13.5,
                   help="width of the plot's axis in cm, for spreading the labels (default 13.5: \\labplot)")
    p.add_argument("--label-style", choices=["follow", "top"], default="follow",
                   help="follow: each label (or fanned group) just above its own lines; "
                        "top: all on one level above the tallest line")
    p.add_argument("--pitch", type=float, default=3.8,
                   help="closest two labels may stand, mm (default 3.8: a rotated \\scriptsize label is 3.2)")
    p.add_argument("--solvent-style", choices=["arrow", "label", "none"], default="arrow",
                   help="how the solvent line is marked: arrow (the book's own, upright text and an "
                        "arrow), label (a rotated label like the others), none (the line is still left "
                        "out of the labels; the book does not mark every solvent line: Fig. 22.4's and "
                        "21.3's are unmarked, 21.15's and 15.3's marked, and their heights do not tell "
                        "them apart)")
    p.add_argument("--solvent-label", default="solvent", help="text of the solvent mark (e.g. CDCl$_3$)")
    p.add_argument("--inset-layout", choices=["figure", "separate"], default="figure",
                   help="figure (default): insets drawn inside the plot where the book has them; "
                        "separate: each inset its own plot under the main one")
    p.add_argument("--tex-out", help="write the whole \\labplot call (insets included) to this file, "
                                     "to \\input; needs --out")
    p.add_argument("--caption", help="caption for --tex-out (default: 'Digitized from IMAGE.')")
    p.add_argument("--label-integrals", action="store_true",
                   help="1H: a multiplet's label carries its integral, e.g. '7.71 (1H)' (H with --protons)")
    p.add_argument("--no-integrals", action="store_true",
                   help="do not look for integral curves (1H figures draw them over the multiplets)")
    p.add_argument("--no-integral-curves", action="store_true",
                   help="1H: find and measure the integrals, but do not draw them (no _integrals CSV, "
                        "no integrals= key); by default they are drawn as the book draws them, when "
                        "every one was found whole")
    p.add_argument("--mhz", type=float, help="spectrometer frequency, for J in Hz (Palleros: 500 or 250)")
    p.add_argument("--protons", type=float, help="the molecule's H count: integrals as H (else relative)")
    p.add_argument("--multiplets-out", help="CSV of the multiplets (1H, one per integral)")
    p.set_defaults(func=cmd_nmr)
    args = ap.parse_args(argv)
    try:
        sys.exit(args.func(args))
    except CalibrationError as e:
        print(f"spectrum_digitize: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

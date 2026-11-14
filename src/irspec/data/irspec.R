#!/usr/bin/env Rscript
# irspec.R -- the figure list drawn with ggplot2. No Python, no TeX.
#
#   Rscript irspec.R SESSION_DIR_OR_figures.json [--formats png,svg-text,pdf]
#                    [--out DIR] [--size 10x6.6] [--dpi 300] [--no-caption]
#
# Reads figures.json (what `irspec session` writes beside manifest.json; csv
# paths are relative to that file's folder, text is plain, not LaTeX-escaped)
# and writes one picture per spectrum into DIR/figures/r/ (`--out` to change).
# IR figures, and UV-Vis and GC ones (labels above the band, name over x; a GC
# crop's excluded rows a gap). It draws the same figure as the TeX pipeline and
# the matplotlib backend; the geometry below repeats irspec/layout.py, which
# says where each number was measured, and tests/test_backends.py and
# tests/test_plot_kinds.py check the two agree.
#
# Needs: ggplot2 (>= 3.5) and jsonlite. Optional: ragg (PNG/TIFF; else the
# cairo device), svglite (svg-text). Formats, as in the matplotlib backend:
#   png, tiff (LZW), pdf, svg (text as outlines: draws the same anywhere),
#   svg-text (svglite: labels stay <text>, editable in Inkscape or Illustrator;
#   the font must be installed where the file is opened). pdf and svg need an R
#   with working cairo, which the macOS build has only with XQuartz installed.
# Font: STIX Two Text when installed, else the copies in fonts/ beside this script
# (keep that folder with it), else the default serif.

need <- function(pkg, why) {
  if (!requireNamespace(pkg, quietly = TRUE))
    stop(sprintf("R package '%s' is not installed (%s): install.packages(\"%s\")", pkg, why, pkg),
         call. = FALSE)
}

# ---- the shared geometry (irspec/layout.py) --------------------------------
XLIM <- c(4000, 650); X_MAJOR <- 500; X_MINOR <- 100
LOWER_PAD <- 0.0985; UPPER_PAD <- 0.0017
TRACE_COLOR <- "#B03A2E"; TRACE_PT <- 0.5
TICK_COLOR <- "#ACACAC"; TICK_PT <- 0.4; LEADER_UNITS <- 3
LABEL_PT <- 8; TEXT_PT <- 12; CAPTION_PT <- 10; FRAME_PT <- 0.4
MAJOR_TICK_PT <- 4.2; MINOR_TICK_PT <- 2.1
MAX_Y_INTERVALS <- 12

x_limits <- function(xmin = NULL, xmax = NULL) {
  lim <- c(if (is.null(xmax)) XLIM[1] else xmax, if (is.null(xmin)) XLIM[2] else xmin)
  if (!(lim[2] < lim[1])) stop(sprintf("xmin (%g) must be below xmax (%g)", lim[2], lim[1]), call. = FALSE)
  lim
}

y_limits <- function(y, ymin = NULL, ymax = NULL) {
  top <- if (is.null(ymax)) max(y) else ymax
  base <- if (is.null(ymin)) min(y) else ymin
  if (!(base < top)) stop(sprintf("ymin (%g) must be below ymax (%g)", base, top), call. = FALSE)
  span <- top - base
  c(base - LOWER_PAD * span, top + UPPER_PAD * span)
}

y_step <- function(lo, hi) {
  span <- hi - lo
  k <- if (span > 0) floor(log10(span / MAX_Y_INTERVALS)) else 0
  for (m in c(1, 2, 5, 10, 20, 50)) {
    step <- m * 10^k
    if (span / step <= MAX_Y_INTERVALS + 1e-9) return(step)
  }
  10^(k + 2)
}

y_ticks <- function(lo, hi) {
  step <- y_step(lo, hi)
  first <- ceiling(lo / step - 1e-9); last <- floor(hi / step + 1e-9)
  round(seq(first, last) * step, 10)
}

fmt_number <- function(v, sep = ",") {    # sep: a kind's y_sep (gc: a sixth of an em)
  s <- ifelse(v == round(v), formatC(v, format = "f", digits = 0, big.mark = sep),
              formatC(v, format = "g", big.mark = sep))
  gsub("-", "−", trimws(s), fixed = TRUE)
}

# lwd: R's unit is 1/96 in; the TeX figure's widths are in pt (1/72.27 in).
pt_to_lwd <- function(pt) pt * 96 / 72.27
# ggplot's linewidth is in mm and multiplied by .pt (72.27/25.4) to get lwd.
gg_lw <- function(pt) pt_to_lwd(pt) / ggplot2::.pt
gg_size <- function(pt) pt / ggplot2::.pt          # text `size` aesthetic (mm)

# ---- reading ----------------------------------------------------------------
# Stable qualification by the input path, matching naming.py. Allocate the
# whole list before writing; a qualifier must not take another output's name.
allocate_names <- function(paths, names, extensions = rep("", length(names)), identities = paths) {
  if (anyDuplicated(identities))
    stop(sprintf("same input file twice: %s", paths[duplicated(identities)][1]), call. = FALSE)
  conflicts <- function(result) {
    keys <- paste0(result, extensions)
    which(duplicated(keys) | duplicated(keys, fromLast = TRUE))
  }
  active <- conflicts(names)
  parts <- strsplit(paths, "/", fixed = TRUE)
  shortened <- rep(FALSE, length(paths))
  for (name in unique(names[active])) {
    group <- active[names[active] == name]
    while (length(group) > 1 && all(lengths(parts[group]) > 0) &&
           length(unique(vapply(parts[group], tail, character(1), n = 1))) == 1) {
      for (i in group) { parts[[i]] <- head(parts[[i]], -1); shortened[i] <- TRUE }
    }
  }
  stages <- lapply(seq_along(paths), function(i) {
    components <- parts[[i]]; leaf <- tail(components, 1)
    stem <- if (shortened[i]) leaf else tools::file_path_sans_ext(leaf)
    suffix <- paste0("_", names[i])
    if (endsWith(stem, suffix)) stem <- substr(stem, 1, nchar(stem) - nchar(suffix))
    out <- c(stem, leaf)
    if (length(components) > 1)
      for (depth in 2:length(components)) out <- c(out, paste(tail(components, depth), collapse = "/"))
    out
  })
  levels <- rep(1L, length(paths)); result <- names
  repeat {
    for (i in active) {
      choices <- stages[[i]]; level <- levels[i]
      suffix <- if (level <= length(choices)) choices[level] else
        paste(rep(paths[i], level - length(choices) + 1), collapse = "/")
      encoded <- gsub("%20", " ", URLencode(suffix, reserved = TRUE), fixed = TRUE)
      result[i] <- paste0(names[i], "_", encoded)
    }
    blocked <- intersect(active, conflicts(result))
    if (!length(blocked)) break
    levels[blocked] <- levels[blocked] + 1L
  }
  if (length(active)) {
    ordered <- active[order(paths[active])]
    message("name collision: ", paste(paste(paths[ordered], "->", result[ordered]), collapse = "; "))
  }
  result
}

read_figures <- function(path) {
  if (dir.exists(path)) path <- file.path(path, "figures.json")
  if (!file.exists(path)) stop(sprintf("%s not found: run `irspec session DIR` first", path), call. = FALSE)
  entries <- jsonlite::fromJSON(path, simplifyVector = FALSE)
  folder <- dirname(normalizePath(path))
  figs <- lapply(entries, function(e) {
    if (!is.null(e$spec) && e$spec != 1)
      stop(sprintf("%s: figure spec %s is not the one this script reads (1)", path, e$spec), call. = FALSE)
    kind <- if (is.null(e$kind)) "ir" else e$kind      # absent means ir
    if (!kind %in% names(KINDS))
      stop(sprintf("%s: %s is a %s figure; this script draws %s figures (use the PDF: irspec session)",
                   path, e$csv, kind, paste(names(KINDS), collapse = ", ")), call. = FALSE)
    peaks <- if (length(e$peaks)) do.call(rbind, lapply(e$peaks, function(p) c(p[[1]], p[[2]]))) else
      matrix(numeric(0), ncol = 2)
    list(csv = file.path(folder, e$csv), title = if (is.null(e$title)) "" else e$title,
         axis = if (is.null(e$axis)) KINDS[[kind]]$y_label else e$axis,
         peaks = peaks, ymin = e$ymin, ymax = e$ymax, xmin = e$xmin, xmax = e$xmax, stem = sub("_plain$", "", tools::file_path_sans_ext(basename(e$csv))),
         kind = kind, apex = as.numeric(unlist(e$apex)), names = as.character(unlist(e$names)),
         restrict_y = isTRUE(e$restrict_y))
  })
  stems <- allocate_names(vapply(figs, function(f) f$csv, character(1)),
                          vapply(figs, function(f) f$stem, character(1)))
  for (i in seq_along(figs)) figs[[i]]$stem <- stems[i]
  list(figures = figs, folder = folder)
}

# ---- drawing ----------------------------------------------------------------
script_dir <- function() {
  a <- grep("^--file=", commandArgs(FALSE), value = TRUE)
  if (length(a)) dirname(normalizePath(sub("^--file=", "", a[1]))) else getwd()
}

# STIX Two Text when installed, else the copies in fonts/ beside this script
# (SIL OFL 1.1, fonts/OFL.txt). IRSPEC_BUNDLED_FONTS=1 forces them (for tests).
pick_font <- function() {
  if (requireNamespace("systemfonts", quietly = TRUE)) {
    force <- !(Sys.getenv("IRSPEC_BUNDLED_FONTS") %in% c("", "0"))
    if (!force) {
      p <- systemfonts::match_fonts("STIX Two Text")$path
      if (length(p) && grepl("STIX", p, ignore.case = TRUE))
        return(list(family = "STIX Two Text", note = sprintf("STIX Two Text (%s)", basename(p))))
    }
    d <- file.path(script_dir(), "fonts")
    reg <- file.path(d, "STIXTwoText-Regular.ttf"); ita <- file.path(d, "STIXTwoText-Italic.ttf")
    if (file.exists(reg) && file.exists(ita)) {
      # register_font refuses a name a system font already has: under the forcing
      # test hook the family gets another name, for real use (not installed) it
      # is the real one, so an svg-text file asks for "STIX Two Text".
      fam <- if (force) "STIX Two Text (irspec copy)" else "STIX Two Text"
      systemfonts::register_font(fam, plain = reg, italic = ita, bold = reg, bolditalic = ita)
      return(list(family = fam, note = "STIX Two Text (bundled with irspec)"))
    }
  }
  list(family = "serif", note = "serif (STIX Two Text not found; needs the systemfonts package)")
}

draw <- function(fig, family, caption = TRUE) {
  if (fig$kind != "ir") return(draw_apex(fig, family, caption))
  library(ggplot2)
  d <- read.csv(fig$csv)
  names(d)[1:2] <- c("x", "y")
  d <- d[is.finite(d$y) & d$x >= min(XLIM) & d$x <= max(XLIM), ]
  lim <- y_limits(d$y, fig$ymin, fig$ymax)
  xl <- x_limits(fig$xmin, fig$xmax)
  pk <- as.data.frame(fig$peaks); names(pk) <- c("x", "ly")
  pk <- pk[pk$x >= min(xl) & pk$x <= max(xl), ]
  pk$label <- sprintf("%.1f", pk$x)
  tick_len <- unit(MAJOR_TICK_PT, "pt")
  p <- ggplot(d, aes(x, y)) +
    geom_line(colour = TRACE_COLOR, linewidth = gg_lw(TRACE_PT), lineend = "butt", linejoin = "round")
  if (nrow(pk)) {
    p <- p +
      geom_segment(data = pk, aes(x = x, xend = x, y = ly, yend = ly + LEADER_UNITS),
                   inherit.aes = FALSE, colour = TICK_COLOR, linewidth = gg_lw(TICK_PT), lineend = "butt") +
      geom_label(data = pk, aes(x = x, y = ly, label = label), inherit.aes = FALSE,
                 angle = 90, hjust = 1, vjust = 0.5, size = gg_size(LABEL_PT), family = family,
                 fill = alpha("white", 0.85), border.colour = NA, linewidth = 0,
                 label.padding = unit(1, "pt"), label.r = unit(0, "pt"))
  }
  p <- p +
    scale_x_reverse(limits = xl, oob = scales::oob_keep, breaks = seq(4000, 1000, by = -X_MAJOR),
                    minor_breaks = seq(3900, 700, by = -X_MINOR), labels = fmt_number,
                    expand = c(0, 0), guide = guide_axis(minor.ticks = TRUE)) +
    scale_y_continuous(limits = lim, oob = scales::oob_keep, breaks = y_ticks(lim[1], lim[2]),
                       labels = fmt_number, expand = c(0, 0)) +
    guides(x.sec = guide_axis(minor.ticks = TRUE), y.sec = guide_axis()) +
    labs(x = "Wavenumber / cm⁻¹", y = fig$axis, caption = if (caption && nzchar(fig$title)) fig$title) +
    theme_void(base_family = family, base_size = TEXT_PT) +
    theme(
      panel.border = element_rect(colour = "black", fill = NA, linewidth = gg_lw(FRAME_PT)),
      axis.ticks = element_line(colour = "black", linewidth = gg_lw(0.2)),
      axis.ticks.length = tick_len,
      axis.minor.ticks.length = unit(MINOR_TICK_PT, "pt"),
      axis.text = element_text(colour = "black", size = TEXT_PT),
      axis.text.x.top = element_blank(), axis.text.y.right = element_blank(),   # ticks only, as in TeX
      axis.text.x = element_text(margin = margin(t = 3)), axis.text.y = element_text(margin = margin(r = 3)),
      axis.title.x = element_text(size = TEXT_PT, margin = margin(t = 6)),
      axis.title.y = element_text(size = TEXT_PT, angle = 90, margin = margin(r = 8)),
      plot.caption = element_text(hjust = 0.5, face = "italic", size = CAPTION_PT, margin = margin(t = 10)),
      plot.caption.position = "plot",
      plot.margin = margin(7, 7, 5, 5),
      plot.background = element_rect(fill = "white", colour = NA)
    )
  p
}

# ---- the other kinds: labels above the band (uvvis, gc) ----------------------
# What irspec/kinds.py says of each kind this script draws (tests/test_plot_kinds.py checks x_label,
# x_minor_num and y_sep against it).
KINDS <- list(
  ir = list(x_label = "Wavenumber / cm⁻¹", labels = "trough", y_label = "Transmittance %"),
  uvvis = list(x_label = "Wavelength / nm", labels = "apex", y_label = "Absorbance",
               x_minor_num = 4, y_sep = ","),
  gc = list(x_label = "Retention time / min", labels = "apex", y_label = "Signal / counts",
            x_minor_num = 1, y_sep = "\u2006")
)
MAX_X_INTERVALS <- 25
# The labels' geometry, in bp (irspec/layout.py says how each was measured on the TeX figure)
APEX_GAP_PT <- 1.494; APEX_SEP_PT <- 0.199; APEX_PAD_PT <- 0.996; APEX_LINE_PT <- 9.465
APEX_FILL_ALPHA <- 0.85

# (left, right) of an ascending kind's x axis: the figure's xmin/xmax, else the data's own ends
kind_x_limits <- function(x, xmin = NULL, xmax = NULL) {
  lim <- c(if (is.null(xmin)) min(x) else xmin, if (is.null(xmax)) max(x) else xmax)
  if (!(lim[1] < lim[2])) stop(sprintf("xmin (%g) must be below xmax (%g)", lim[1], lim[2]), call. = FALSE)
  lim
}

# layout.x_ticks for a kind without a tick list: the smallest 1-2-5 step giving at most
# MAX_X_INTERVALS intervals, and x_minor_num minor ticks between two labelled ones
kind_x_ticks <- function(xl, k) {
  lo <- min(xl); hi <- max(xl); span <- hi - lo
  e <- if (span > 0) floor(log10(span / MAX_X_INTERVALS)) else 0
  step <- 10^(e + 1)
  for (m in c(1, 2, 5, 10)) if (span / (m * 10^e) <= MAX_X_INTERVALS + 1e-9) { step <- m * 10^e; break }
  list(major = round(seq(ceiling(lo / step - 1e-9), floor(hi / step + 1e-9)) * step, 10),
       minor = step / (k$x_minor_num + 1))
}

# The frame of a uvvis or gc figure (layout.frame): the x axis on the data's ends, y on the data
# inside the x frame
kind_frame <- function(d, fig) {
  w <- d[is.finite(d$x) & is.finite(d$y), ]
  xl <- kind_x_limits(w$x, fig$xmin, fig$xmax)
  ys <- w$y[w$x >= xl[1] & w$x <= xl[2]]
  if (!length(ys)) stop(sprintf("no data between %g and %g", xl[1], xl[2]), call. = FALSE)
  list(x = xl, y = y_limits(ys, fig$ymin, fig$ymax))
}

# The labels as the TeX peak list types them (layout.apex_labels): GC's x to two decimals and its
# heights in whole counts, another kind's x as %g and its heights to four decimals
apex_labels <- function(fig) {
  n <- min(nrow(fig$peaks), length(fig$apex), if (fig$kind == "gc") length(fig$names) else Inf)
  if (n == 0) return(data.frame(x = numeric(0), apex = numeric(0), ly = numeric(0), text = character(0),
                                name = character(0)))
  i <- seq_len(n)
  if (fig$kind == "gc") {
    xt <- sprintf("%.2f", fig$peaks[i, 1])
    ap <- as.numeric(sprintf("%.0f", fig$apex[i])); ly <- as.numeric(sprintf("%.0f", fig$peaks[i, 2]))
  } else {
    xt <- sprintf("%g", fig$peaks[i, 1])
    ap <- as.numeric(sprintf("%g", round(fig$apex[i], 4))); ly <- as.numeric(sprintf("%g", round(fig$peaks[i, 2], 4)))
  }
  nm <- if (length(fig$names) >= n) fig$names[i] else rep("", n)
  data.frame(x = as.numeric(xt), apex = ap, ly = ly, text = xt, name = nm, stringsAsFactors = FALSE)
}

# The trace cut to the frame (Liang-Barsky, segment by segment), NA between the pieces: the labels
# are drawn unclipped (coord_cartesian(clip = "off"), TeX's clip mode=individual), so the trace is
# clipped here. An empty row of the CSV (a GC crop's excluded range) stays a gap.
clip_trace <- function(x, y, xr, yr) {
  n <- length(x); ox <- oy <- rep(NA_real_, 3 * n); k <- 0; lx <- NA_real_; ly <- NA_real_
  for (i in seq_len(max(0, n - 1))) {
    x0 <- x[i]; y0 <- y[i]; x1 <- x[i + 1]; y1 <- y[i + 1]
    if (!all(is.finite(c(x0, y0, x1, y1)))) next
    dx <- x1 - x0; dy <- y1 - y0; t0 <- 0; t1 <- 1; ok <- TRUE
    for (pq in list(c(-dx, x0 - xr[1]), c(dx, xr[2] - x0), c(-dy, y0 - yr[1]), c(dy, yr[2] - y0))) {
      p <- pq[1]; q <- pq[2]
      if (p == 0) {
        if (q < 0) { ok <- FALSE; break }
      } else {
        r <- q / p
        if (p < 0) { if (r > t1) { ok <- FALSE; break }; if (r > t0) t0 <- r }
        else { if (r < t0) { ok <- FALSE; break }; if (r < t1) t1 <- r }
      }
    }
    if (!ok) next
    # an end the frame does not cut is the data point itself (x0 + 1 * dx need not be x1 exactly)
    sx <- if (t0 == 0) x0 else x0 + t0 * dx; sy <- if (t0 == 0) y0 else y0 + t0 * dy
    if (!(identical(sx, lx) && identical(sy, ly))) {    # a new piece: leave an NA row before it
      if (k > 0) k <- k + 1
      k <- k + 1; ox[k] <- sx; oy[k] <- sy
    }
    lx <- if (t1 == 1) x1 else x0 + t1 * dx; ly <- if (t1 == 1) y1 else y0 + t1 * dy
    k <- k + 1; ox[k] <- lx; oy[k] <- ly
  }
  data.frame(x = ox[seq_len(k)], y = oy[seq_len(k)])
}

# One label: the white box and its lines, in a zero-size viewport at (x, label_y). Units in bp; the
# string units are measured in the label's own font (the box's gp), so the box is TeX's: the widest
# line + 2 x pad, from SEP above label_y to the top line's ink + pad.
label_grob <- function(text, name, family) {
  font <- gpar(fontfamily = family, fontsize = LABEL_PT)
  lines <- if (nzchar(name)) c(name, text) else text        # top to bottom
  n <- length(lines)
  base <- unit(APEX_SEP_PT + APEX_PAD_PT, "bigpts") + unit(1, "strdescent", text)
  top <- base + unit(APEX_LINE_PT * (n - 1) + APEX_PAD_PT, "bigpts") + unit(1, "strascent", lines[1])
  width <- max(unit(rep(1, n), "strwidth", data = as.list(lines))) + unit(2 * APEX_PAD_PT, "bigpts")
  box <- rectGrob(x = unit(0.5, "npc"), y = unit(0.5, "npc") + unit(APEX_SEP_PT, "bigpts"), width = width,
                  height = top - unit(APEX_SEP_PT, "bigpts"), just = c("centre", "bottom"),
                  gp = gpar(fontfamily = family, fontsize = LABEL_PT, col = NA,
                            fill = grDevices::adjustcolor("white", APEX_FILL_ALPHA)))
  texts <- lapply(seq_len(n), function(i)                     # bottom line first, on its baseline
    textGrob(rev(lines)[i], x = unit(0.5, "npc"),
             y = unit(0.5, "npc") + base + unit((i - 1) * APEX_LINE_PT, "bigpts"),
             hjust = 0.5, vjust = 0, gp = font))
  gTree(children = do.call(gList, c(list(box), texts)))
}

draw_apex <- function(fig, family, caption = TRUE) {
  library(ggplot2)
  library(grid)
  k <- KINDS[[fig$kind]]
  d <- read.csv(fig$csv)
  names(d)[1:2] <- c("x", "y")
  d <- d[is.finite(d$x), ]                       # an empty y stays: the trace breaks there
  if (isTRUE(fig$restrict_y) && !is.null(fig$ymax))   # gc_tool's restrict y to domain*=-ymax:ymax
    d$y <- pmax(pmin(d$y, fig$ymax), -fig$ymax)
  fr <- kind_frame(d, fig)
  xt <- kind_x_ticks(fr$x, k)
  tr <- clip_trace(d$x, d$y, fr$x, fr$y)
  p <- ggplot(tr, aes(x, y)) +
    geom_path(colour = TRACE_COLOR, linewidth = gg_lw(TRACE_PT), lineend = "butt", linejoin = "round",
              na.rm = TRUE)
  lab <- apex_labels(fig)
  lab <- lab[lab$x >= fr$x[1] & lab$x <= fr$x[2], ]
  for (i in seq_len(nrow(lab))) {
    leader <- segmentsGrob(x0 = unit(0.5, "npc"), x1 = unit(0.5, "npc"),
                           y0 = unit(0, "npc") + unit(APEX_GAP_PT, "bigpts"), y1 = unit(1, "npc"),
                           gp = gpar(col = TICK_COLOR, lwd = pt_to_lwd(TICK_PT), lineend = "butt"))
    p <- p +
      annotation_custom(leader, xmin = lab$x[i], xmax = lab$x[i], ymin = lab$apex[i], ymax = lab$ly[i]) +
      annotation_custom(label_grob(lab$text[i], lab$name[i], family),
                        xmin = lab$x[i], xmax = lab$x[i], ymin = lab$ly[i], ymax = lab$ly[i])
  }
  minor <- seq(ceiling(fr$x[1] / xt$minor - 1e-9), floor(fr$x[2] / xt$minor + 1e-9)) * xt$minor
  p +
    scale_x_continuous(limits = fr$x, oob = scales::oob_keep, breaks = xt$major, minor_breaks = minor,
                       labels = function(v) fmt_number(v), expand = c(0, 0),
                       guide = guide_axis(minor.ticks = TRUE)) +
    scale_y_continuous(limits = fr$y, oob = scales::oob_keep, breaks = y_ticks(fr$y[1], fr$y[2]),
                       labels = function(v) fmt_number(v, k$y_sep), expand = c(0, 0)) +
    coord_cartesian(clip = "off") +
    guides(x.sec = guide_axis(minor.ticks = TRUE), y.sec = guide_axis()) +
    labs(x = k$x_label, y = fig$axis, caption = if (caption && nzchar(fig$title)) fig$title) +
    theme_void(base_family = family, base_size = TEXT_PT) +
    theme(
      panel.border = element_rect(colour = "black", fill = NA, linewidth = gg_lw(FRAME_PT)),
      axis.ticks = element_line(colour = "black", linewidth = gg_lw(0.2)),
      axis.ticks.length = unit(MAJOR_TICK_PT, "pt"),
      axis.minor.ticks.length = unit(MINOR_TICK_PT, "pt"),
      axis.text = element_text(colour = "black", size = TEXT_PT),
      axis.text.x.top = element_blank(), axis.text.y.right = element_blank(),
      axis.text.x = element_text(margin = margin(t = 3)), axis.text.y = element_text(margin = margin(r = 3)),
      axis.title.x = element_text(size = TEXT_PT, margin = margin(t = 6)),
      axis.title.y = element_text(size = TEXT_PT, angle = 90, margin = margin(r = 8)),
      plot.caption = element_text(hjust = 0.5, face = "italic", size = CAPTION_PT, margin = margin(t = 10)),
      plot.caption.position = "plot",
      plot.margin = margin(7, 7, 5, 5),
      plot.background = element_rect(fill = "white", colour = NA)
    )
}

# ---- output -----------------------------------------------------------------
FORMATS <- c("png", "tiff", "pdf", "svg", "svg-text")
EXT <- c(png = ".png", tiff = ".tiff", pdf = ".pdf", svg = ".svg", "svg-text" = ".svg")
SUFFIX <- c("svg-text" = "_text")

# R's own svg()/cairo_pdf() devices need R built with working cairo, which the
# macOS CRAN build only has with XQuartz installed; so PNG/TIFF go through ragg
# and the editable SVG through svglite, and pdf and the outlined svg are offered
# only where cairo works.
cairo_works <- function() {
  f <- tempfile(fileext = ".pdf")
  ok <- tryCatch({ suppressWarnings(cairo_pdf(f)); dev.off(); TRUE }, error = function(e) FALSE,
                 warning = function(w) FALSE)
  unlink(f); ok
}

need_cairo <- function(fmt) {
  if (!cairo_works()) stop(sprintf("%s needs an R with working cairo (on macOS: brew install --cask xquartz); ", fmt),
                           "use `--formats svg-text` for an SVG, or the matplotlib backend", call. = FALSE)
}

save_as <- function(p, dest, fmt, size, dpi) {
  w <- size[1]; h <- size[2]
  switch(fmt,
    png = {
      if (requireNamespace("ragg", quietly = TRUE)) ragg::agg_png(dest, width = w, height = h, units = "in", res = dpi)
      else png(dest, width = w, height = h, units = "in", res = dpi, type = "cairo")
      print(p); dev.off()
    },
    tiff = {
      if (requireNamespace("ragg", quietly = TRUE)) ragg::agg_tiff(dest, width = w, height = h, units = "in", res = dpi, compression = "lzw")
      else tiff(dest, width = w, height = h, units = "in", res = dpi, compression = "lzw", type = "cairo")
      print(p); dev.off()
    },
    "svg-text" = {
      need("svglite", "SVG with editable text")
      svglite::svglite(dest, width = w, height = h); print(p); dev.off()
    },
    svg = {
      need_cairo("svg")
      svg(dest, width = w, height = h); print(p); dev.off()
    },
    pdf = {
      need_cairo("pdf")
      cairo_pdf(dest, width = w, height = h); print(p); dev.off()
    })
  invisible(dest)
}

USAGE <- paste("usage: Rscript irspec.R SESSION_DIR_OR_figures.json [--formats png,tiff,pdf,svg,svg-text]",
               "[--out DIR] [--size WxH] [--dpi N] [--no-caption]")

parse_args <- function(argv) {
  a <- list(path = NULL, formats = "png", out = NULL, size = c(10, 6.6), dpi = 300,
            caption = TRUE, layout = FALSE)
  i <- 1
  while (i <= length(argv)) {
    k <- argv[i]
    take <- function() { i <<- i + 1; if (i > length(argv)) stop(sprintf("%s needs a value", k), call. = FALSE); argv[i] }
    if (k == "--formats") a$formats <- take()
    else if (k == "--out") a$out <- take()
    else if (k == "--size") {
      s <- suppressWarnings(as.numeric(strsplit(tolower(take()), "x")[[1]]))
      if (length(s) != 2 || any(is.na(s)) || any(s <= 1)) stop("--size needs WIDTHxHEIGHT in inches, e.g. 10x6.6", call. = FALSE)
      a$size <- s
    }
    else if (k == "--dpi") a$dpi <- as.numeric(take())
    else if (k == "--no-caption") a$caption <- FALSE
    else if (k == "--layout") a$layout <- TRUE      # print each figure's limits and ticks, draw nothing
    else if (k %in% c("-h", "--help")) { cat(USAGE, "\n"); quit(status = 0) }
    else if (startsWith(k, "--")) stop(sprintf("unknown option %s", k), call. = FALSE)
    else a$path <- k
    i <- i + 1
  }
  a
}

main <- function(argv = commandArgs(trailingOnly = TRUE)) {
  a <- parse_args(argv)
  if (is.null(a$path)) stop(USAGE, call. = FALSE)
  need("jsonlite", "reads figures.json"); need("ggplot2", "draws the figures")
  formats <- unique(strsplit(tolower(trimws(a$formats)), "[,[:space:]]+")[[1]])
  formats <- formats[nzchar(formats)]
  bad <- setdiff(formats, FORMATS)
  if (length(bad)) stop(sprintf("unknown format '%s'; choose from: %s", bad[1], paste(FORMATS, collapse = ", ")), call. = FALSE)
  r <- read_figures(a$path)
  if (a$layout) {
    # one line a figure: y bottom, y top, y ticks, x left, x right, labelled x ticks, minor x step
    for (f in r$figures) {
      d <- read.csv(f$csv)
      if (f$kind == "ir") {
        d <- d[d[[1]] >= min(XLIM) & d[[1]] <= max(XLIM) & is.finite(d[[2]]), ]
        lim <- y_limits(d[[2]], f$ymin, f$ymax)
        xl <- x_limits(f$xmin, f$xmax)
        xt <- list(major = seq(4000, 1000, by = -X_MAJOR), minor = X_MINOR)
        xt$major <- xt$major[xt$major <= xl[1] & xt$major >= xl[2]]
      } else {
        names(d)[1:2] <- c("x", "y")
        fr <- kind_frame(d, f); lim <- fr$y; xl <- fr$x; xt <- kind_x_ticks(xl, KINDS[[f$kind]])
      }
      cat(sprintf("%.10f %.10f %s %.10f %.10f %s %.10f\n", lim[1], lim[2], paste(y_ticks(lim[1], lim[2]), collapse = ","),
                  xl[1], xl[2], paste(xt$major, collapse = ","), xt$minor))
    }
    return(invisible())
  }
  jobs <- rep(seq_along(r$figures), each = length(formats))
  job_formats <- rep(formats, times = length(r$figures))
  paths <- vapply(r$figures[jobs], function(f) f$csv, character(1))
  stems <- vapply(r$figures[jobs], function(f) f$stem, character(1))
  suffix <- vapply(job_formats, function(fmt) if (fmt %in% names(SUFFIX)) SUFFIX[[fmt]] else "", character(1))
  extensions <- vapply(job_formats, function(fmt) EXT[[fmt]], character(1))
  destinations <- paste0(allocate_names(paths, paste0(stems, suffix), extensions,
                                        paste(paths, job_formats, sep = "::")), extensions)
  out <- if (is.null(a$out)) file.path(r$folder, "figures", "r") else a$out
  dir.create(out, recursive = TRUE, showWarnings = FALSE)
  font <- pick_font()
  cat(sprintf("R %s, ggplot2 %s, font: %s\n", getRversion(), packageVersion("ggplot2"), font$note))
  for (i in seq_along(r$figures)) {
    f <- r$figures[[i]]
    p <- draw(f, font$family, a$caption)
    for (fmt in formats) {
      dest <- file.path(out, destinations[which(jobs == i & job_formats == fmt)])
      save_as(p, dest, fmt, a$size, a$dpi)
      cat(sprintf("wrote %s\n", dest))
    }
  }
}

if (sys.nframe() == 0L) main()

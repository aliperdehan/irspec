#!/usr/bin/env Rscript
# irspec.R -- the figure list drawn with ggplot2. No Python, no TeX.
#
#   Rscript irspec.R SESSION_DIR_OR_figures.json [--formats png,svg-text,pdf]
#                    [--out DIR] [--size 10x6.6] [--dpi 300] [--no-caption]
#
# Reads figures.json (what `irspec session` writes beside manifest.json; csv
# paths are relative to that file's folder, text is plain, not LaTeX-escaped)
# and writes one picture per spectrum into DIR/figures/r/ (`--out` to change).
# It draws the same figure as the TeX pipeline and the matplotlib backend; the
# geometry below repeats irspec/layout.py, which says where each number was
# measured, and tests/test_backends.py checks the two agree.
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

y_limits <- function(y, ymin = NULL) {
  top <- max(y)
  base <- if (is.null(ymin)) min(y) else ymin
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

fmt_number <- function(v) {
  s <- ifelse(v == round(v), formatC(v, format = "f", digits = 0, big.mark = ","),
              formatC(v, format = "g", big.mark = ","))
  gsub("-", "−", trimws(s), fixed = TRUE)
}

# lwd: R's unit is 1/96 in; the TeX figure's widths are in pt (1/72.27 in).
pt_to_lwd <- function(pt) pt * 96 / 72.27
# ggplot's linewidth is in mm and multiplied by .pt (72.27/25.4) to get lwd.
gg_lw <- function(pt) pt_to_lwd(pt) / ggplot2::.pt
gg_size <- function(pt) pt / ggplot2::.pt          # text `size` aesthetic (mm)

# ---- reading ----------------------------------------------------------------
read_figures <- function(path) {
  if (dir.exists(path)) path <- file.path(path, "figures.json")
  if (!file.exists(path)) stop(sprintf("%s not found: run `irspec session DIR` first", path), call. = FALSE)
  entries <- jsonlite::fromJSON(path, simplifyVector = FALSE)
  folder <- dirname(normalizePath(path))
  figs <- lapply(entries, function(e) {
    if (!is.null(e$spec) && e$spec != 1)
      stop(sprintf("%s: figure spec %s is not the one this script reads (1)", path, e$spec), call. = FALSE)
    peaks <- if (length(e$peaks)) do.call(rbind, lapply(e$peaks, function(p) c(p[[1]], p[[2]]))) else
      matrix(numeric(0), ncol = 2)
    list(csv = file.path(folder, e$csv), title = if (is.null(e$title)) "" else e$title,
         axis = if (is.null(e$axis)) "Transmittance %" else e$axis,
         peaks = peaks, ymin = e$ymin, stem = sub("_plain$", "", tools::file_path_sans_ext(basename(e$csv))))
  })
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
  library(ggplot2)
  d <- read.csv(fig$csv)
  names(d)[1:2] <- c("x", "y")
  d <- d[is.finite(d$y) & d$x >= min(XLIM) & d$x <= max(XLIM), ]
  lim <- y_limits(d$y, fig$ymin)
  pk <- as.data.frame(fig$peaks); names(pk) <- c("x", "ly")
  pk <- pk[pk$x >= min(XLIM) & pk$x <= max(XLIM), ]
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
    scale_x_reverse(limits = XLIM, breaks = seq(4000, 1000, by = -X_MAJOR),
                    minor_breaks = seq(3900, 700, by = -X_MINOR), labels = fmt_number,
                    expand = c(0, 0), guide = guide_axis(minor.ticks = TRUE)) +
    scale_y_continuous(limits = lim, breaks = y_ticks(lim[1], lim[2]), labels = fmt_number,
                       expand = c(0, 0)) +
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
    else if (k == "--layout") a$layout <- TRUE      # print each figure's y limits and ticks, draw nothing
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
    for (f in r$figures) {
      d <- read.csv(f$csv); d <- d[d[[1]] >= min(XLIM) & d[[1]] <= max(XLIM) & is.finite(d[[2]]), ]
      lim <- y_limits(d[[2]], f$ymin)
      cat(sprintf("%.10f %.10f %s\n", lim[1], lim[2], paste(y_ticks(lim[1], lim[2]), collapse = ",")))
    }
    return(invisible())
  }
  out <- if (is.null(a$out)) file.path(r$folder, "figures", "r") else a$out
  dir.create(out, recursive = TRUE, showWarnings = FALSE)
  font <- pick_font()
  cat(sprintf("R %s, ggplot2 %s, font: %s\n", getRversion(), packageVersion("ggplot2"), font$note))
  for (f in r$figures) {
    p <- draw(f, font$family, a$caption)
    for (fmt in formats) {
      dest <- file.path(out, paste0(f$stem, if (fmt %in% names(SUFFIX)) SUFFIX[[fmt]] else "", EXT[[fmt]]))
      save_as(p, dest, fmt, a$size, a$dpi)
      cat(sprintf("wrote %s\n", dest))
    }
  }
}

if (sys.nframe() == 0L) main()

"""TeX output: turn a list of Figure into something LaTeX can build.

Two writers, for the two ways a spectrum PDF gets made:

  render_md(figures)   the peer-share Markdown that nulabreport's `pdfmd`
                       builds (frontmatter + one landscape block of
                       \\irspectrum calls). Byte-identical to what
                       ir_organize.py wrote before irspec existed; that is a
                       test, and what nulabreport's own pipeline relies on.

  render_tex(figures)  a complete .tex for plain lualatex, no pandoc. It loads
                       the real nulabreport.sty when TeX can find it and
                       otherwise the bundled excerpt, irspec-ir.sty
                       (write_excerpt copies that file next to the .tex). The
                       two draw the same picture; the excerpt is cut out of
                       nulabreport.sty by a script and may lag behind it.
"""
import os
import shutil
from importlib import resources

from . import spa_tool
from .figure import Figure

EXCERPT_NAME = "irspec-ir.sty"


def _block(f: Figure, esc=spa_tool.latex_escape) -> str:
    opts = f"width={f.width},height={f.height}"
    if f.ymin is not None:
        opts += f",ymin={f.ymin}"
    return ("\\irspectrum\n"
            f"  [{opts}]\n"
            f"  {{{f.csv}}}\n"
            f"  {{{esc(f.axis)}}}\n"
            f"  {{{f.peaklist()}}}\n"
            f"  {{{esc(f.title)}}}\n"
            "\\clearpage\n")


def render_md(figures) -> str:
    body = ["\\begin{landscape}"] + [_block(f) for f in figures] + ["\\end{landscape}"]
    return spa_tool.MD_FRONTMATTER + "\n" + "\n".join(body) + "\n"


# The preamble a markdown report gets from pandoc's template and nulabreport
# section 0, for the case where the full package is absent (see the generated
# excerpt's header): fontspec/unicode-math with STIX Two, British babel,
# microtype. STIX Two is used when installed; otherwise TeX's default fonts.
_FALLBACK_PREAMBLE = r"""\usepackage{amsmath,amssymb}
\usepackage{unicode-math}
\defaultfontfeatures{Scale=MatchLowercase}
\defaultfontfeatures[\rmfamily]{Ligatures=TeX,Scale=1}
\IfFontExistsTF{STIX Two Text}{\setmainfont{STIX Two Text}}{}
\IfFontExistsTF{STIX Two Math}{\setmathfont{STIX Two Math}}{}
\usepackage{microtype}
\setlength{\emergencystretch}{3em}
\usepackage[bidi=basic,shorthands=off,british]{babel}
\usepackage{selnolig}
\usepackage{irspec-ir}"""


def render_tex(figures) -> str:
    body = ["\\begin{landscape}"] + [_block(f) for f in figures] + ["\\end{landscape}"]
    return (
        "% Build with lualatex. Prefers the real nulabreport.sty; falls back to\n"
        f"% {EXCERPT_NAME} (keep that file next to this one).\n"
        "\\documentclass[12pt,a4paper]{article}\n"
        "\\usepackage[margin=0.6in]{geometry}\n"
        "\\IfFileExists{nulabreport.sty}%\n"
        "  {\\usepackage{nulabreport}}%\n"
        "  {" + _FALLBACK_PREAMBLE.replace("\n", "\n   ") + "}\n"
        "\\labsetup{furniture=false, captions=bare}\n"
        "\\begin{document}\n"
        + "\n".join(body) + "\n"
        "\\end{document}\n")


def excerpt_text() -> str:
    return resources.files("irspec").joinpath("data", EXCERPT_NAME).read_text(encoding="utf-8")


def write_excerpt(folder) -> str:
    """Copy the bundled irspec-ir.sty into `folder`; return its path."""
    dest = os.path.join(folder, EXCERPT_NAME)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(excerpt_text())
    return dest

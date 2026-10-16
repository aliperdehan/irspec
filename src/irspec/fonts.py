"""The STIX Two fonts bundled with irspec (SIL Open Font License 1.1, see
data/fonts/OFL.txt): Text Regular and Italic, and Math. Used only where STIX Two
is not installed, so a figure looks the same on a machine that does not have it.

IRSPEC_BUNDLED_FONTS=1 in the environment forces the bundled copies even when
the real ones are installed (how the tests exercise this path).
"""
import os
import shutil
from importlib import resources

TEXT = ("STIXTwoText-Regular.ttf", "STIXTwoText-Italic.ttf")
MATH = "STIXTwoMath-Regular.ttf"
LICENSE = "OFL.txt"
FOLDER = "irspec-fonts"          # where the plain-TeX fallback finds them, beside the .tex


def force_bundled():
    return os.environ.get("IRSPEC_BUNDLED_FONTS", "") not in ("", "0")


def path(name):
    return str(resources.files("irspec").joinpath("data", "fonts", name))


def copy_to(folder):
    """Copy the fonts and their license into folder/irspec-fonts/; return that folder."""
    dest = os.path.join(folder, FOLDER)
    os.makedirs(dest, exist_ok=True)
    for name in (*TEXT, MATH, LICENSE):
        shutil.copyfile(path(name), os.path.join(dest, name))
    return dest

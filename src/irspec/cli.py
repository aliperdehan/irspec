"""The `irspec` command: one entry point over the tools.

    irspec session DIR      a folder of spectra -> CSVs, peaks, figure PDF
    irspec spa ...          OMNIC .SPA -> CSVs, peaks, legacy plots   (spa_tool)
    irspec jdx ...          JCAMP-DX -> CSVs                          (jdx_tool)
    irspec peaks ...        peak-pick a .SPA, .jdx or CSV             (spa_peaks)
    irspec digitize ...     a spectrum published as a picture -> CSVs (ir_digitize)
    irspec a2t ...          Absorbance <-> %Transmittance             (absorbance_to_transmittance)
    irspec absorptivity ... QUANT-IR absorptivity -> Absorbance       (absorptivity_to_absorbance)
    irspec corr ...         Pearson r between spectra                 (ir_corr)

`session` is the command most people want; the others are its steps, for when
one step is all that is needed (`irspec jdx convert X.jdx`). Each takes its
own --help.
"""
import importlib
import sys

from . import __version__

COMMANDS = {
    "session": "session",
    "spa": "spa_tool",
    "jdx": "jdx_tool",
    "peaks": "spa_peaks",
    "digitize": "ir_digitize",
    "a2t": "absorbance_to_transmittance",
    "absorptivity": "absorptivity_to_absorbance",
    "corr": "ir_corr",
}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__.strip())
        return
    if argv[0] in ("-V", "--version"):
        print(f"irspec {__version__}")
        return
    cmd = argv[0]
    if cmd not in COMMANDS:
        sys.exit(f"irspec: unknown command {cmd!r}; choose from: {', '.join(COMMANDS)}")
    mod = importlib.import_module(f"irspec.{COMMANDS[cmd]}")
    sys.argv = [f"irspec {cmd}", *argv[1:]]
    mod.main()


if __name__ == "__main__":
    main()

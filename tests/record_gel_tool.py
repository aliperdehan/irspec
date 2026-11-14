"""Record nulabreport's original gel_tool.py twice on the synthetic demo gel.

python3 tests/record_gel_tool.py ~/dev/tex/nulabreport/tools/gel_tool.py tests/data/gel_tool_expected.json
"""

import json
import sys
from make_gel import photo
from tool_recording import record

CASES = [
    (stage, [stage, "gel.json"])
    for stage in ["straighten", "lanes", "bands", "calibrate", "figure"]
]
CASES += [
    ("all_left", ["all", "gel.json"]),
    ("all_right", ["all", "gel.json"]),
    ("quadratic", ["all", "gel.json"]),
    ("point_to_point", ["all", "gel.json"]),
]


CASES += [
    ("protected_photos", ["straighten", "gel.json"]),
    ("protected_sources", ["straighten", "gel.json"]),
]


def config(mirror=False, fit="linear"):
    lane = 6 if mirror else 1
    names = (
        {"6": "Ladder", "5": "Protein A", "3": "Protein B", "2": "Protein C"}
        if mirror
        else {"1": "Ladder", "2": "Protein A", "4": "Protein B", "5": "Protein C"}
    )
    return {
        "note": "SYNTHETIC gel; not real data",
        "photo": "photo.jpg",
        "out_dir": ".",
        "search_box": [0, 0, 1200, 1000],
        "lanes": {"count": 6, "names": names, "window": 0.6},
        "bands": {"prominence": 0.03, "distance": 0.015},
        "ladder": {
            "lane": lane,
            "sizes": [245, 180, 135, 100, 75, 63, 48, 35, 25, 20, 17, 11],
            "anchors": [75, 25],
            "fit": fit,
            "reference_channel": "red",
        },
        "figure": {
            "target_kb": 120,
            **({} if mirror else {"arrows": [{"lane": 4, "peak": 1, "text": "B2"}]}),
        },
    }


def prepare(folder, name):
    mirror = name == "all_right"
    fit = {"quadratic": "quadratic", "point_to_point": "point-to-point"}.get(
        name, "linear"
    )
    photo(mirror).save(folder / "photo.jpg", quality=92)
    cfg = config(mirror, fit)
    if name.startswith("protected_"):
        cfg["out_dir"] = name.split("_", 1)[1]
    (folder / "gel.json").write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    record(sys.argv[1], CASES, prepare, sys.argv[2])

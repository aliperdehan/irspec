"""Stable names for colliding outputs, qualified by their source paths."""
import os
import sys
from collections import Counter
from urllib.parse import quote


def allocate(paths, names, outputs=None, identities=None):
    """Keep unique names; qualify collisions with the shortest source-path suffix.

    Try the original file stem, then its extension, then successive parents.
    All names are allocated together, so qualification cannot steal another name.
    """
    paths = [os.path.normpath(str(p)) for p in paths]
    identities = paths if identities is None else identities
    if len(set(identities)) != len(identities):
        duplicate = next(p for p, n in Counter(identities).items() if n > 1)
        raise ValueError(f"same input file twice: {duplicate}")
    outputs = outputs or (lambda i, name: [name])
    def conflicting(result):
        keys = [set(outputs(i, name)) for i, name in enumerate(result)]
        counts = Counter(key for group in keys for key in group)
        return {i for i, group in enumerate(keys) if any(counts[k] > 1 for k in group)}
    active = conflicting(names)
    parts = [p.split(os.sep) for p in paths]
    shortened = set()
    for name in set(names[i] for i in active):
        group = [i for i in active if names[i] == name]
        # A shared filename contributes no information: use the differing
        # parent alone, rather than repeating that filename in every output.
        while len(group) > 1 and all(parts[i] for i in group) and len({parts[i][-1] for i in group}) == 1:
            for i in group:
                parts[i].pop()
                shortened.add(i)
    stages = []
    for i, path in enumerate(paths):
        components = parts[i]
        leaf = components[-1]
        stem = leaf if i in shortened else os.path.splitext(leaf)[0]
        if stem.endswith("_" + names[i]):
            stem = stem[:-len(names[i]) - 1]   # only the stripped upload prefix differs
        stages.append([stem, leaf] +
                      [os.sep.join(components[-depth:]) for depth in range(2, len(components) + 1)])
    levels = {i: 0 for i in active}
    result = list(names)
    while active:
        for i in active:
            suffix = stages[i][min(levels[i], len(stages[i]) - 1)]
            # Repeating the full path only matters if a user-chosen name already
            # equals a fully qualified candidate; it never depends on input order.
            if levels[i] >= len(stages[i]):
                suffix = os.sep.join([paths[i]] * (levels[i] - len(stages[i]) + 2))
            result[i] = names[i] + "_" + quote(suffix, safe=" ._-")
        blocked = active & conflicting(result)
        if not blocked:
            break
        for i in blocked:
            levels[i] += 1
    if active:
        pairs = [f"{paths[i]} -> {result[i]}" for i in sorted(active, key=lambda i: paths[i])]
        print("name collision: " + "; ".join(pairs), file=sys.stderr)
    return result

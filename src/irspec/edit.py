"""irspec edit: change one session's manifest.json from the command line.

    irspec edit DIR FILE set KEY=VALUE [KEY=VALUE ...]
    irspec edit DIR FILE unset KEY [KEY ...]
    irspec edit DIR show [FILE] [--json]

DIR is a session folder (the one holding manifest.json). FILE names one
manifest entry: its "file" value (`SPA/PHENACETIN_CRUDE_LR1-2.SPA`), or just
the file name or the stem (`PHENACETIN_CRUDE_LR1-2`) when only one entry has it.

Keys that `set` and `unset` accept:

    title, axis, name                   text
    ymin, ymax, xmin, xmax              numbers (the axis limits)
    threshold, prominence, distance     numbers (peak-picking sensitivity)

xmin, xmax and ymax are stored for the figure code that will read them (roadmap 1a);
today only ymin, title, axis, name and the three peak-picking numbers change a figure.

It changes manifest.json and nothing else; it does not re-run the session, so
run `irspec session DIR` afterwards to redraw (a re-run keeps what is edited).
The write is atomic (a temporary file in the same folder, then a rename), the
order of the entries and of each entry's keys is kept, a new key goes last, and
the file keeps its layout: the layout `irspec session` writes (one key per line,
each peak pair on its own line), or else the file's own indentation. A command
that changes nothing does not touch the file, so running it twice leaves
identical bytes. Nothing is ever asked: a question would be a flag.

Every `set`/`unset` prints what it changed; with --json it prints exactly one
JSON object on stdout, {"file": ..., "changes": [{"key", "old", "new"}, ...]}
("old" is null for a key that was not there, "new" is null after `unset`;
a key whose value does not change is not listed). Errors go to stderr with a
non-zero exit: 2 for a command that cannot be carried out (unknown key, a text
where a number belongs, no such entry), 1 when manifest.json is missing or
unreadable.

`show` prints one entry (or all of them) as text; with --json, the entry as a
JSON object, or all entries as a JSON list, exactly as stored.
"""
import argparse
import json
import math
import os
import re
import sys
import tempfile

NUMERIC_KEYS = ("ymin", "ymax", "xmin", "xmax", "threshold", "prominence", "distance")
TEXT_KEYS = ("title", "axis", "name")
ALLOWED_KEYS = ("title", "axis", "ymin", "ymax", "xmin", "xmax",
                "threshold", "prominence", "distance", "name")

_NUMBER = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")
_INT = re.compile(r"^[+-]?\d+$")


class EditError(Exception):
    """A reason to stop; `code` is the exit status (2: the command, 1: the file)."""

    def __init__(self, message, code=2):
        super().__init__(message)
        self.code = code


# -----------------------------------------------------------------------------
# values and keys
# -----------------------------------------------------------------------------
def check_key(key):
    if key not in ALLOWED_KEYS:
        raise EditError(f"unknown key {key!r}; the keys you can set or unset are: "
                        f"{', '.join(ALLOWED_KEYS)}")


def parse_value(key, text):
    """The JSON value for KEY=text: a number for the numeric keys, else the text."""
    check_key(key)
    if key in TEXT_KEYS:
        return text
    s = text.strip()
    if not _NUMBER.match(s):
        raise EditError(f"{key} needs a number, got {text!r}")
    value = int(s) if _INT.match(s) else float(s)
    if isinstance(value, float) and not math.isfinite(value):
        raise EditError(f"{key} needs a finite number, got {text!r}")
    return value


def parse_assignments(items):
    """['ymin=-5', 'title=X'] -> [('ymin', -5), ('title', 'X')], all checked."""
    out, seen = [], set()
    for item in items:
        key, eq, text = item.partition("=")
        if not eq:
            raise EditError(f"{item!r} is not KEY=VALUE (for example ymin=-5)")
        key = key.strip()
        value = parse_value(key, text)
        if key in seen:
            raise EditError(f"{key} is given twice")
        seen.add(key)
        out.append((key, value))
    if not out:
        raise EditError("set needs at least one KEY=VALUE")
    return out


def parse_unset_keys(keys):
    if not keys:
        raise EditError("unset needs at least one KEY")
    seen = []
    for k in keys:
        check_key(k)
        if k not in seen:
            seen.append(k)
    return seen


# -----------------------------------------------------------------------------
# reading and writing manifest.json
# -----------------------------------------------------------------------------
def manifest_path(folder):
    return os.path.join(folder, "manifest.json")


def read_manifest(folder):
    """(entries, text) of DIR/manifest.json; EditError(code 1) if it cannot be used."""
    path = manifest_path(folder)
    if not os.path.isdir(folder):
        raise EditError(f"{folder}: not a folder", 1)
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except FileNotFoundError:
        raise EditError(f"{path}: no manifest.json here (run `irspec session` on the folder first)", 1)
    except OSError as e:
        raise EditError(f"{path}: {e.strerror or e}", 1)
    try:
        text = raw.decode("utf-8")
        entries = json.loads(text)
    except ValueError as e:
        raise EditError(f"{path}: not valid JSON ({e})", 1)
    if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
        raise EditError(f"{path}: expected a list of entries (objects)", 1)
    return entries, text


def entry_file(e):
    """The file of an entry; "spa"/"jdx" are the old spellings of "file"."""
    return e.get("file") or e.get("spa") or e.get("jdx")


def _session_style(entries, ensure_ascii=False):
    """The layout ir_organize.save_manifest writes: one key per line, one peak pair per line."""
    out = []
    for e in entries:
        lines = []
        for k, v in e.items():
            if k == "peaks" and isinstance(v, list):
                body = ",\n".join(f"      {json.dumps(p, ensure_ascii=ensure_ascii)}" for p in v)
                lines.append(f'    "peaks": [\n{body}\n    ]' if v else '    "peaks": []')
            else:
                lines.append(f"    {json.dumps(k, ensure_ascii=ensure_ascii)}: "
                             f"{json.dumps(v, ensure_ascii=ensure_ascii)}")
        out.append("  {\n" + ",\n".join(lines) + "\n  }" if lines else "  {}")
    return "[\n" + ",\n".join(out) + "\n]\n" if out else "[]\n"


def serialize(entries, original):
    """`entries` as text in the layout of `original` (see the module docstring)."""
    eol = "\r\n" if "\r\n" in original else "\n"
    text = original.replace("\r\n", "\n")
    ascii_only = "\\u" in text and all(ord(c) < 128 for c in text)
    nl = "\n" if text.endswith("\n") else ""
    peaks_per_line = re.search(r'^ {4}"peaks": \[\n {6}[\[\d+-]', text, re.M)
    try:
        exact = _session_style(json.loads(text), ascii_only) == text
    except ValueError:
        exact = False
    if exact or peaks_per_line:
        out = _session_style(entries, ascii_only)
        out = out if nl else out.rstrip("\n")
    else:
        m = re.search(r"^([ \t]+)\S", text, re.M)
        indent = None
        if m:
            indent = "\t" if m.group(1).startswith("\t") else len(m.group(1))
        out = json.dumps(entries, indent=indent, ensure_ascii=ascii_only) + nl
    return out.replace("\n", eol)


def write_atomic(path, text):
    """Write `text` to `path` through a temporary file in the same folder and os.replace."""
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".manifest-", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(text.encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())
        try:
            os.chmod(tmp, os.stat(path).st_mode & 0o7777)
        except OSError:
            pass
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# -----------------------------------------------------------------------------
# choosing the entry
# -----------------------------------------------------------------------------
def _norm(p):
    p = p.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return os.path.normpath(p).replace("\\", "/") if p else p


def find_entry(entries, name):
    """The index of the one entry that `name` means: its "file" value, else a file
    name, else a stem. EditError if there is none or more than one."""
    want = _norm(name)
    files = [_norm(entry_file(e) or "") for e in entries]
    for rule in (lambda f: f == want,
                 lambda f: os.path.basename(f) == want,
                 lambda f: os.path.splitext(os.path.basename(f))[0] == want):
        hits = [i for i, f in enumerate(files) if f and rule(f)]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            raise EditError(f"{name!r} is ambiguous; it matches "
                            f"{', '.join(files[i] for i in hits)}; give the whole path "
                            f"(as listed by `irspec edit DIR show`)")
    listing = ", ".join(f for f in files if f) or "(the manifest is empty)"
    raise EditError(f"no manifest entry for {name!r}; the entries are: {listing}")


# -----------------------------------------------------------------------------
# the operations (pure: they change the entry and return what changed)
# -----------------------------------------------------------------------------
def apply_set(entry, assignments):
    changes = []
    for key, new in assignments:
        old = entry.get(key)
        if key in entry and old == new:  # 5 and 5.0 are the same limit
            continue
        entry[key] = new
        changes.append({"key": key, "old": old, "new": new})
    return changes


def apply_unset(entry, keys):
    changes = []
    for key in keys:
        if key in entry:
            changes.append({"key": key, "old": entry.pop(key), "new": None})
    return changes


# -----------------------------------------------------------------------------
# output
# -----------------------------------------------------------------------------
def _show_value(v):
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)


def _peaks_text(peaks):
    parts = []
    for p in peaks:
        if isinstance(p, (list, tuple)) and p:
            parts.append(str(p[0]))  # the position; the label height is in --json
        else:
            parts.append(str(p))
    return f"{len(peaks)} at " + ", ".join(parts) if parts else "none"


def format_entry(entry, indent="  "):
    lines = []
    for k, v in entry.items():
        if k == "file" or (k in ("spa", "jdx") and v == entry_file(entry)):
            continue
        if k == "peaks" and isinstance(v, list):
            lines.append(f"{indent}peaks: {_peaks_text(v)}")
        else:
            lines.append(f"{indent}{k}: {_show_value(v)}")
    return "\n".join(lines)


def format_changes(file, changes):
    if not changes:
        return f"{file}: no change"
    lines = [file]
    for c in changes:
        old = "(not set)" if c["old"] is None else _show_value(c["old"])
        new = "(removed)" if c["new"] is None else _show_value(c["new"])
        lines.append(f"  {c['key']}: {old} -> {new}")
    return "\n".join(lines)


# -----------------------------------------------------------------------------
# commands
# -----------------------------------------------------------------------------
def edit(folder, name, verb, items):
    """Run `set` or `unset` on the entry `name`. Returns (file, changes); writes only if needed."""
    if verb == "set":
        plan = parse_assignments(items)  # checked before the manifest is even read
    elif verb == "unset":
        plan = parse_unset_keys(items)
    else:
        raise EditError(f"unknown action {verb!r}; use set or unset (or: irspec edit DIR show)")
    entries, text = read_manifest(folder)
    i = find_entry(entries, name)
    entry = entries[i]
    changes = apply_set(entry, plan) if verb == "set" else apply_unset(entry, plan)
    if changes:
        write_atomic(manifest_path(folder), serialize(entries, text))
    return entry_file(entry), changes


def show(folder, name=None):
    """The entry `name`, or the list of all entries."""
    entries, _ = read_manifest(folder)
    return entries[find_entry(entries, name)] if name else entries


def build_parser():
    p = argparse.ArgumentParser(
        prog="irspec edit",
        usage="irspec edit DIR FILE set KEY=VALUE [KEY=VALUE ...]\n"
              "       irspec edit DIR FILE unset KEY [KEY ...]\n"
              "       irspec edit DIR show [FILE] [--json]",
        description="Change or show a session's manifest.json. Keys: " + ", ".join(ALLOWED_KEYS)
                    + ". FILE is an entry's \"file\" value, or its file name or stem if that is "
                      "unambiguous. Changes manifest.json only; run `irspec session DIR` to redraw.",
        epilog="Exit status: 0 done; 2 the command cannot be carried out; 1 manifest.json missing "
               "or unreadable.")
    p.add_argument("dir", metavar="DIR", help="the session folder (holds manifest.json)")
    p.add_argument("rest", nargs="*", metavar="FILE ACTION ...",
                   help="FILE set KEY=VALUE ... | FILE unset KEY ... | show [FILE]")
    p.add_argument("--json", action="store_true",
                   help="print one JSON object (set/unset) or the entries (show) on stdout")
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_intermixed_args(sys.argv[1:] if argv is None else argv)
    rest = args.rest
    try:
        if rest and rest[0] == "show":
            if len(rest) > 2:
                raise EditError("show takes at most one FILE")
            result = show(args.dir, rest[1] if len(rest) == 2 else None)
            if args.json:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            elif isinstance(result, dict):
                print(entry_file(result) or "(no file)")
                body = format_entry(result)
                if body:
                    print(body)
            else:
                for n, e in enumerate(result, 1):
                    print(("" if n == 1 else "\n") + f"[{n}] {entry_file(e) or '(no file)'}")
                    body = format_entry(e)
                    if body:
                        print(body)
                if not result:
                    print("(no entries)")
            return 0
        if len(rest) < 2:
            raise EditError("expected: irspec edit DIR FILE set|unset ...  or  irspec edit DIR show [FILE]")
        file, changes = edit(args.dir, rest[0], rest[1], rest[2:])
        if args.json:
            print(json.dumps({"file": file, "changes": changes}, ensure_ascii=False))
        else:
            print(format_changes(file, changes))
        return 0
    except EditError as e:
        print(f"irspec edit: {e}", file=sys.stderr)
        sys.exit(e.code)


if __name__ == "__main__":
    main()

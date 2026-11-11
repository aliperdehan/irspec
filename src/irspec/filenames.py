"""Keep metadata-derived filenames inside their destination directory."""
import os
from pathlib import PureWindowsPath


def filename_component(name):
    """Validate a single filename component on both POSIX and Windows."""
    if (not isinstance(name, str) or not name or name in (".", "..")
            or any(c in name for c in ("/", "\\", "\0")) or PureWindowsPath(name).drive):
        raise ValueError(f"{name!r} must be a single filename component")
    return name


def contained_path(directory, filename):
    """Join one filename, refusing an existing symlink that points outside."""
    filename_component(filename)
    path = os.path.join(directory, filename)
    root, destination = os.path.realpath(directory), os.path.realpath(path)
    if os.path.commonpath((root, destination)) != root or destination == root:
        raise ValueError(f"{filename!r} resolves outside its destination directory")
    return path

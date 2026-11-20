"""One way for a tool to reach the repository's other tool folders (review finding 54).

    import paths            # with tools/ on the path
    paths.use('bake', 'upk')

puts tools/bake and tools/upk on sys.path, each only if it is not there already, so a function that calls it on every
request or every stage leaves the path as the first call left it. A folder already on the path keeps its place:
which module a name finds never depends on the order the calls ran in, because no two tracked Python files share a
name and none shadows the standard library (tools/repo/tests/test_names.py checks both).

The release's Python (tools/release/make_release.py) lists tools/ and each of its folders in its ._pth, so there
every call finds its folder present and does nothing.
"""
import os
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
FOLDERS = ('viewer', 'editor', 'bake', 'upk', 'lab')


def same(path):
    """A path as the path list is compared here: absolute, normalised, and in one case on Windows."""
    return os.path.normcase(os.path.abspath(path))


def use(*names):
    """Put tools/<name> on sys.path for each name not on it yet, however an earlier insert spelled it (at the front,
    as the tools' own inserts do)."""
    for name in names:
        if name not in FOLDERS:
            raise ValueError('no tool folder %r (paths.FOLDERS: %s)' % (name, ', '.join(FOLDERS)))
        folder = str(TOOLS / name)
        if same(folder) not in {same(p) for p in sys.path if p}:
            sys.path.insert(0, folder)

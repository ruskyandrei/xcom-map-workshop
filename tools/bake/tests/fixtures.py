"""Records the bake tests share with other suites (review finding 58): kept here, not in a test module, so a suite
that needs one (the viewer's manager, play and output-name tests) imports no other suite's tests."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
RECORDS = HERE.parents[1] / 'patch' / 'tests' / 'defaultmaps-records.txt'


def record(name):
    """The game's DefaultMaps.ini record of the map `name` (bar, templeship...), from
    tools/patch/tests/defaultmaps-records.txt."""
    for line in RECORDS.read_bytes().split(b'\n'):
        if line.startswith(name.encode() + b'\t'):
            return line.split(b'\t', 1)[1]
    raise KeyError(name)

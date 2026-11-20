### A malformed record is left out of the build instead of crashing the compiler

Review findings 38 and 62 (its malformed-record test). The contract says a record the compiler can't read is left out
and named, and the rest builds; six shapes crashed the compiler instead, and the build window showed the traceback's
last line (`KeyError: 'from'`, `unhashable type: 'list'`). The page never writes them; a hand edit, a copied project or
a newer editor can.

- [compiler.py](../../tools/editor/compiler.py):
  - an added record whose `template` is not an object (null, a list, a name) is a left-out row (`malformed`), with or
    without a `from`; only an object goes on to the cover and light recipes;
  - a value used as a key is checked first (`keyable`, `target_key`): a cover recipe's version, a light recipe's kind
    or version, a made piece's kind, and the package, level or actor of an override's target or an added record's
    source. A list or an object there names nothing, and the record is left out as malformed;
  - found by a sweep that put odd values in each field of each kind of record and document part: a `buildings` that
    is not a list no longer stops the floor lookup and the groups, a landing zone or mission entry whose kind or id is a
    list is malformed (`valid_zone`, `valid_mission` around spawns.py's and missions.py's checks), and a cleared
    project on an export with no tile grid is the error `cleared-grid` (an export with no tile grid is one the Build
    can't build from) where it was a `KeyError`.
- [build.py](../../tools/editor/build.py) checks the missions list's entries the same way.
- Checked: [test_compiler_malformed.py](../../tools/editor/tests/test_compiler_malformed.py) puts each of the six cases
  beside a copy that builds and checks the report is good, the record left out under its own code and the copy built;
  a mission and a zone with a list kind, and buildings that are no list, are malformed, not a crash. Each failed
  before. The editor suite passes.

### The bake suite works out the bar's unedited relight and an equipped blank map once

Review finding 61, its first step.

- [test_shadows_bounce.py](../../tools/bake/tests/test_shadows_bounce.py) `BarScene`: the floor relit with no edit,
  which three tests read, and the scene with the pool table moved, which two read, are worked out once for the class
  (`shared`; the relight's sampling is seeded, so the same call gives the same result). Run by itself, the class
  went from 114.9 s to 89.4 s.
- [test_shell.py](../../tools/bake/tests/test_shell.py): `TallerGrid` and `AmbientLight` read one blank map equipped
  18 levels high with the runtime fill light (`equipped`, kept for the module), in place of two equips and their
  whole-map writes; the light changes nothing TallerGrid checks. About 2 s, within the noise of a whole run.

Measured: the whole bake suite took 782.7 s before (694 tests, one skipped, with another agent's suite running beside
it) and 799.5 s with the `test_shell` change and the `GroundShapes` trial below, beside the same: the noise of a
shared computer is larger than either. The `BarScene` saving was timed with the class run by itself, before and after
(it took 114.0 s inside the whole run before).

Checked: the whole bake suite passes with the `test_shell` change (694 tests, one skipped), and `BarScene`'s 12 tests
pass with theirs.

Looked at and left:
- `GroundShapes` ([test_frac_walls.py](../../tools/bake/tests/test_frac_walls.py), 86 s) spends about 58 s of its
  relight on the dominant light's shadow maps of its four ground copies, each traced whole from nothing; the trial of
  relighting no receivers beyond those the shapes touch saved about a second, so the class is as it was.
- Most of the other writes are builds whose tests each read a different edit (`NativeCopy`'s 25 tests, 2 to 6 s each,
  the made walls' classes, the effects' lanes); sharing them means one build carrying several edits, which changes
  what each test sees, so it is left for a plan of its own.
- `test_faster_bake`'s `OnTheBar` spends its time building two relight scenes of URB_Bar, not writing; the transplant
  oracle compares three map pairs and `FreshLight`'s real relight reads the receivers near its copies.

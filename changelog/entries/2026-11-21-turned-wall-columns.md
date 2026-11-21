### A made wall turned off the quarter turns has its fracture columns along its own line (KB-8, F-145)

EXP-90's turned wall C1 seemed to break in its middle, away from the grenade. Read offline from the run's package and
the exe copy, the game's blast rule (a grenade damages the columns whose boxes lie within its radius, 288, and meet a
square four tiles wide round the hit, and they break their fragments up to 128 over the hit) gives exactly what the
run saw from above: C1's two lower rows broke from its start, its top band stood where its fragments start over that
height, and the one band fragment that starts lower went. The turned wall's own fault was its columns, cut a tile wide
on the world's x axis: on a slant each listed fragments from much of the wall's length, and the one at world x -1057
to -961 met the blast's square while two fragments it lists, the corner's lower rows, lie 41 and 48 beyond it. They
broke where the same wall on a quarter turn keeps them.

- [frac_walls.py](../../tools/bake/frac_walls.py): `turned` (a made wall upright and turned about the vertical off the
  quarter turns) and `turned_columns` (F0's rule in the wall's own frame: a column a tile along its own line, counted
  from its fragments' lowest corner less one unit, a storey of the level's grid up, listing the fragments on that
  stretch, its box the world box round the stretch across them); `add_walls` uses them for such a wall. A wall on a
  quarter turn, or tilted, keeps the columns on the world's axes.
- [frac-neighbours.md](../../research/native/frac-neighbours.md) section 2.3: the splash's filter box (DealDamage), the
  columns it lets be damaged and the fragments a damaged column passes over, decoded.
- [findings-register.md](../../research/findings-register.md) F-145 (fixed offline, the cause with its numbers),
  [KNOWN-BUGS.md](../../KNOWN-BUGS.md) KB-8's cause (the entry stays until the game rerun passes),
  [EXP-90](../../research/experiments/EXP-90-free-form-pieces.md) check 3's note.

Checked: new bake tests, `test_frac_walls.TurnedColumns` (the rule, its F0 twin at yaw 0 on the wall's own grid, and
C1 at the run's blast by the decoded rule: fragments 0 to 5 and 8 break, as on yaw 0; the columns on the world's axes
broke 10 and 11 too) and `test_free_build.FreeBuild` (the built wall at yaw 5000 has the turned columns); the bake,
editor and repo suites; the Builds' outputs (`build_outputs.py`, the eleven inputs) and the editor suite's compiles
(`compile_record.py`) byte for byte against the commit before. EXP-90's project built again (quick) and C1's columns
read back: 15 along its line; by the decoded rule the run's blast damages the six of its two lower storeys from its
start to 295 along it, breaking fragments 0 to 5 and 8, and the corner's stand. C1 and C2 now list 14 of each other's columns at
their mitred corner, where the larger boxes listed 28.

Gaps: the box round a slanting stretch is larger than the stretch, so a turned wall can still break a fragment further
beyond a blast's square than a wall on a quarter turn (offline, round a 30-degree wall: as far as 174 against 100);
columns half a tile along would halve that, not made. A turned floor's columns are still cells of the world's grid.
The same blast seen from above looks as it did (the game's rule); the rerun reads the wall from the side.

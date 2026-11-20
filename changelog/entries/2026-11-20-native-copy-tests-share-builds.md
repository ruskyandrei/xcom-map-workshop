### The copy tool's tests share builds: NativeCopy makes nine edits in three packages, not nine

Editor refactor, stage T1 (the bake suite's time). No product code changes. `NativeCopy` built and wrote the bar
once per edit, though most of its tests' edits touch different pieces. A build costs a second or more whatever its
edit, much of it the writer's check that decodes the written map again, so building once what the tests built one by
one is where the time is.

- [fixtures.py](../../tools/bake/tests/fixtures.py): `SharedBuild`, one package made from several tests' edits,
  each test reading back its own part in a subtest named for its edit, so every failure names the edit it checks.
  When the shared build fails, each edit is built alone: those that fail fail their own tests, and the others are
  built together again, so one edit's failure is never read as its neighbours'. `native_build` joins the edits'
  arguments for `native_copy.build` (refusing two edits that name one piece, hidden piece or assembly), and
  `NativePart` gives an edit its records of the manifest: its copies' sections, hidden pieces, assemblies, ladders,
  vans, floor listings, and the pieces whose columns list its copies.
- [test_native_copy.py](../../tools/bake/tests/test_native_copy.py), `NativeCopy`: two shared `native_copy` builds,
  one of the ladder moved without its climb, the police car turned, door 6 moved with door 7 deleted, and a corpse
  copied with another deleted; the other of the van copied and the floor strip moved up (the van's copy seeds tiles
  the car's seeds too, as the strip's do the ladder's, so they are in different builds). One shared Grower clones the
  two pieces at a full rotation and the car turned about a tile corner. Nine packages became three.
- Tests that keep a build of their own: those that count the whole map (the level's actors, its rebuild volumes, its
  list's end, its net indices, every wall's columns), those whose edits meet another's (the wall copy and the hidden
  wall: door 6, door 7 and wall 16 are in the door move), another source map (the grown bar), the relight's, and one
  build that makes each kind of edit alone: a copy (the strip at its own height; the car and lamp), a move (the ladder
  with its climb), a delete (the van's 14 parts), break-group links.
- Checked:
  - The same 45 tests by name pass before and after (the runner's logs compared), the count unchanged.
  - Each of the nine shared edits, built alone, gives the same records as its part of the shared build, the new
    exports' indices and names aside (a scratch comparison: no difference).
  - Three test-only breaks of `native_copy.py`, made and taken back, never committed, each fail their own edit's
    test and no other: a copy (the floor strip's copy made a unit higher: `test_a_storey_floor_copy_moved_up...`
    fails, in its shared part and its own build), a move (door 6 moved a tile off its wall:
    `test_a_door_copy_joins_its_walls_columns...` fails), a delete (KAsset_1 left in the level:
    `test_a_physics_prop_is_cloned...` fails). A fourth, the corpse's copy raising, fails that test alone as an edit
    that did not apply; the other three edits of its build are built again together and pass.
  - Times, before and after back to back, while other agents' suites loaded the computer (so noisy):
    - `NativeCopy` alone through the runner, four rounds: 29.7 s before and 23.6 s after, 29.9 and 23.3 s in the two
      quiet rounds; 59.8 and 52.7 s, 64.6 and 44.8 s in the two loaded ones. Its set-up, which makes the three shared
      packages, takes 3.5 to 5 s of that.
    - The whole file through the runner, three rounds: 45, 80 and 44 s before; 68, 41 and 37 s after.
    - The class wrote 23 packages and now writes 17. The baseline at the stage's start, the whole bake suite run
      alone: `NativeCopy` 38.4 s (a whole-suite run reads about twice a file run's seconds for each test).
- Not in this change: `RebuildTemplate`'s two builds of the police station (a door, a car) touch different pieces and
  could share one build. Every package's write decodes the written map again in pure Python to check it (about
  0.6 s a build); that is the writer's, not the tests'.

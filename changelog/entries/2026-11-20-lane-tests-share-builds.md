### The effects' lanes and the police station's copies share builds: six builds made as three

Editor refactor, stage T3 (the bake suite's time). No product code changes.

- [fixtures.py](../../tools/bake/tests/fixtures.py): `lanes_build`, `SharedBuild`'s make for the effects', sounds' and
  flares' lanes, one edit a lane (two edits of one lane are refused), optionally staged from other maps first; and
  `LanesPart`, an edit's part: its lanes' records (and the floors' emitter records with the effects' lane), its lanes
  as built (staged), and the staging's report rows of the maps its copies come from. `SharedPart`, the mixin of a class
  whose tests read one edit of a module's shared build, moves here from test_frac_walls.py.
- [test_native_effects.py](../../tools/bake/tests/test_native_effects.py): two shared builds (`BUILDS`):
  - `bar`: `Lanes` (effects and sounds moved, deleted and copied) and `FlareLanes` (the Bar's two flares moved,
    deleted and copied). The flares' lane lists nothing in the floors' emitter lists `Lanes` reads whole;
  - `foreign`: `ForeignLanes` (URB_PierA's foam and air conditioner) and `ForeignFlares` (AlienBase01's two flares),
    staged from both maps at once. `ForeignLanes` read the report's count of foreign pieces as 2, its one donor's: it
    now reads that the count is the donors' pieces and effects added up, and that its donor's are 2.
- Kept a build of their own: `ValueLanes` (it values a sound `Lanes` moves, and copies where `Lanes`' copies stand),
  each lane with a clear (the two cleared maps: the sounds' lane alone and the flares' lane alone), the refusals, and
  `CarriedEffects` (three edits of one Skyranger and its lights).
- [test_native_copy.py](../../tools/bake/tests/test_native_copy.py), `RebuildTemplate`: the door copied onto the police
  station's back wall and the car copied three tiles on are one build (`fixtures.native_build`, `NativePart`), as T1
  noted they could be.
- Checked:
  - The same tests by name pass before and after: test_native_effects.py's 32 and test_native_copy.py's 45.
  - Each shared edit built alone gives the records of its part of the shared build, the new exports' names aside
    (scratch comparisons: the lanes' records, every building's floor emitter lists, which named actors are listed,
    the staged edit and each donor's report row; the police copies' NativePart records).
  - Test-only breaks of `native_copy.py`, made and taken back, never committed, each failing only its own edit's
    tests: Emitter_45's delete left out (`Lanes`: 2 tests), LensFlareSource_7 moved a tile further (`FlareLanes`: 2),
    one staged foam copy left out (`ForeignLanes`: 2), the staged glow left out (`ForeignFlares`: 2), the door copies
    moved 5 tiles (`RebuildTemplate`'s door test), the car's glass left out (its car test); a flare copy of a piece
    the Bar lacks fails `FlareLanes`' five shared tests as an edit that did not apply while `Lanes` passes.
  - Times through the runner, before and after back to back, six rounds. In the three quiet ones (the processor 2 to
    10% busy before each run): test_native_effects.py 18.0 to 15.2 s (once 19.9 s, one build taking twice its time),
    its four changed classes 12.4 to 9.5 s, `RebuildTemplate` 6.5 to 5.4 s. In three while other agents' runs loaded
    the computer: the file 18.1 to 15.3, 17.9 to 29.0 (the load rose during the after run) and 36.3 to 30.5 s;
    `RebuildTemplate` 6.5 to 5.4, 10.6 to 7.3 and 10.8 to 7.5 s.
- Known gap: the shared lanes build saves less than a build because `Lanes`, reading the Bar after the foreign
  staging, decodes it again (about 0.7 s): the package reader keeps the last four maps decoded, and the staging and
  the script packages push the Bar out (refactor stage T4).

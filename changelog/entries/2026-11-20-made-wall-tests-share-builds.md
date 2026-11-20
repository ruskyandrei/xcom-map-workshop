### The made-wall tests share builds: nine builds of their edits made as four

Editor refactor, stage T2 (the bake suite's time). No product code changes. The made-wall classes of
[test_frac_walls.py](../../tools/bake/tests/test_frac_walls.py) built a package per class, most of them one or two made
walls standing well apart from the others' (about 1.6 s a build of the Bar, 3.6 s a staged build on the police
station). Each class's tests now read their edit's part of a build several classes share.

- [fixtures.py](../../tools/bake/tests/fixtures.py): `ModuleBuilds`, the shared builds several classes of one module
  read, each made when a class first asks for it and kept until the module's tests end (so a class run alone makes only
  its own); `copies_build`, `SharedBuild`'s make when each edit is a list of copies that may copy one piece (made walls
  of one donor), optionally staged from another map first (transplant.stage_edit); and `CopiesPart`, an edit's part
  told apart by where its copies stand in the build: its sections, made pieces' records, door listings, building floors,
  neighbour listings with either side its own, and flags on its copies. Records of the whole map are not in a part.
- [test_frac_walls.py](../../tools/bake/tests/test_frac_walls.py): four shared builds (`BUILDS`), each test in its
  edit's sub-test:
  - `bar_1`: `Built` (the reference, twin and custom wall on the pavement), `JoinedMadeWalls` (the L and the T's stem on
    the Bar's wall 16) and `MadeSlabs` (the roof over a made wall, the turned floor), whose made cursors are the whole
    map's, so bar_1 carries no other slab;
  - `bar_2`: `Broken` and `MadeWallInBuilding` (Broken's pieces stand where MadeSlabs' do and its far roof seeds tiles the
    reference wall seeds; the building's walls seed tiles the joined walls seed and list wall 16, which
    `JoinedMadeWalls` reads);
  - `station`: `StagedDonor` and `StagedDoorInMadeWall`, staged together. StagedDonor's two walls moved 8 tiles north
    (y 0 to 768), off the door's wall that stood in the same place; its checks are relative to where the walls are put;
  - `alley`: `GroundOnStaticMeshActor`'s two blocks (one with flags), both where the donor stands, outside the grid.
- Kept a build of their own: the one made wall with a door (`DoorInMadeWall`) and the one group with a made wall
  (`GroupWithMadeWall`), each alone and both where the reference wall stands; the Bar's own pieces broken in place
  (`MapBroken`, a record of the whole map) and its refusals; the baked build (`BakedLayout`); `GroundOnBackdrop` (the
  only Demolition build); `GroundShapes`, the relight's (section 9 of the refactor). test_frac_wall.py and the openings'
  and mitred ends' other tests (test_made_split.py, test_made_blasts.py, test_made_cursors.py) build no package.
- Checked:
  - The same 51 tests by name pass before and after (the runner's logs compared), the count unchanged.
  - Each shared edit built alone gives the records of its part of the shared build, the new exports' indices aside
    (a scratch comparison: no difference). The builds tried first differed in tile counts (above) and were split.
  - Test-only breaks of `native_copy.py`, made and taken back, never committed, each failing only its own edit's
    tests: the custom wall without its doorway (`Built`), M3 a tile off wall 16 (`JoinedMadeWalls`), the made floor not
    turned (`MadeSlabs`), the far roof not breaking further (`Broken`), the low wall moved out of the building
    (`MadeWallInBuilding`), the along-y wall not turned (`StagedDonor`), the staged door off its doorway
    (`StagedDoorInMadeWall`), each block of the alley (`GroundOnStaticMeshActor`'s two tests); M2 made to raise fails
    `JoinedMadeWalls` as an edit that did not apply while the other two edits of bar_1 are built again and pass.
  - Times of the changed classes through the runner, before and after back to back, three rounds while other agents'
    suites loaded the computer: 21.5 to 11.8 s in the quiet round, 33.5 to 18.9 s and 34.6 to 20.4 s in the loaded
    ones (the file without `GroundShapes`: 32.1 to 22.5 s quiet, 46.5 to 32.3 and 48.0 to 34.9 s loaded).
- Known gap: `MadeWallInBuilding`'s one-storey test reads the floors a wall is listed in, not its CutdownFloor, so a
  full-height wall there passes it too (a first break, the low wall made two storeys, failed nothing).

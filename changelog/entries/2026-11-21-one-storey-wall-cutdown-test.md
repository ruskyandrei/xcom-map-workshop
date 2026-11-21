### The one-storey made wall's test reads its CutdownFloor

Editor follow-ups, stage B2 (item 4.1). `MadeWallInBuilding`'s test that a one-storey made wall in one of the map's
buildings is in the ground floor only ([test_frac_walls.py](../../tools/bake/tests/test_frac_walls.py)) read the
floors the wall is listed on and not its `CutdownFloor`. A wall of the Bar's inside wall's kind (bCutoutMask) is listed
on the lowest floor it reaches alone, whatever its height, so a planted break that made the low wall two storeys
passed it.

- The test now reads both: the low wall is listed on the ground floor with CutdownFloor 1, the upper floor its top
  meets. That is how URB_Bar lists its own three one-storey walls (0 to 214 high: floor 0, CutdownFloor 1; its
  two-storey walls have 2, as the made twin beside it does).
- The planted break (the low wall's `storeys` left out, so two storeys) fails it: listed `[[0, 2]]`, not `[[0, 1]]`.
  The old assertion passed the same break. The break was not committed.

Checked: test_frac_walls' `MadeWallInBuilding` (3 tests) with and without the break; the bake suite at the stage's end.

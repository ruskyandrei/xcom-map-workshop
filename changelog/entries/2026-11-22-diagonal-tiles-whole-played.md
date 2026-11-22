### Whole-written and carried diagonal cover tiles played in the game

Stage C3 for D2 and D3 of the diagonal cover plan. Nothing in the tools changes.

- [findings-register.md](../../research/findings-register.md): F-155 is verified. The run used CSmallScout_Farm
  with the scout's hull chunk moved onto open ground.
  - Soldiers on the six corners the Build wrote read cover 50 with the written flags, the diagonal bit included: two
    at the new place, two on the wall's inner face, and two whole-written at the scout.
  - They walked onto and off each written tile.
  - Both saves hold the tiles as written.

Checked: a hidden game run (LWR) and its two saves read with tools/lab/save_tiles.py.

Known gaps:
- The build played predates the carry rule: the finder decided the moved chunk's tiles, so its inner face was
  written too. The carry rule writes only the outer face, the same tiles and data as were played.
- A piece from another map is not played.

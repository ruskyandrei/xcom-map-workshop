### The game's neighbour links read from the exe and worked out from a map's pieces

Part of stage C2 of the diagonal cover plan: the link step of the game's tile build, so the Build can write a whole
tile. Nothing a Build makes changes yet.

- [neighbour-links.md](../../research/native/neighbour-links.md), new: the reading of `0x905780` and its callees
  (plain links, ClimbOver and ClimbOnto, KickDoor, DropDown, JumpUp and WallClimb), the ladders' part, bits 0x100000
  and 0x200000, the build against the rebuild.
- [tile_links.py](../../tools/bake/tile_links.py), new: the rule (`Map`, `Predictor`), its one home.
- [neighbour-links-check.py](../../research/evidence/neighbour-links-check.py), new, and its record
  [neighbour-links-2026-11-22.json](../../research/evidence/neighbour-links-2026-11-22.json): the rule against the
  install's 96 base maps' bakes.
- [findings-register.md](../../research/findings-register.md): F-154; F-152 points at it.
  [native-code-notes.md](../../research/native-code-notes.md), [ladder-links.md](../../research/native/ladder-links.md)
  and [cover-build.md](../../research/native/cover-build.md): what the reading corrects, marked where they said it.

Checked: the check over the install: 2,139,524 of 2,140,357 baked links, every typed link, both bits exact; the same
counts after the rule moved from the script into tools/bake (URB_Bar and CsmallScout_Farm); the repo suite.

Known gaps: 1,815 diagonal sweeps of 1,111,854 disagree (F-154); the editor's ladder height formula
(tools/viewer/ladders.py) is short of the game's, noted for later.

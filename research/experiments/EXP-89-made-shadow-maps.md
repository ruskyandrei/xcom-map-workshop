# EXP-89: one moon shadow map on a made piece

Date: 21 November 2026. Status: **passed** ([F-144](../findings-register.md)). The editor follow-ups' stage B3 (decision
D1): a made piece copied from an outdoor donor no longer keeps the donor's cloned moon shadow map beside its own. The
change alters the written map, so it was merged only after this unattended run in the lab copy (LWR) with the
game-test skill.

## What was checked

Whether a made piece that lists only its own moon shadow map (B) is drawn as the same piece that lists the donor's map
first and its own after it (A): the shadows cast across a made patch, and the made pieces themselves neither wholly dark
nor wholly lit where they were not before.

## The project

"B3 made shadow maps" (ships as `B3MadeShadowMaps`): EXP-77's made ground on URB_Bar (16 made ground pieces, 14 of
them on outdoor donors) and two made walls on its made patch (x -1152 to -864, y -960 to -672): T, 400 high on an
inside donor, along y -936 from x -1248 to -768; O, on an outdoor donor (Wall Ext CROWN 384G), along x -888 from y -924
to -636. The moon stands nearly overhead, so each wall's shadow is a band about 48 units north and 45 units west of
it, across the patch and on over the map's own asphalt beside it. Two full baked Builds of it: A at the commit before
the change (15 of 18 made pieces list two maps), B with it (each lists one, its own; 15 cloned maps and 14,158,503
bytes of their textures left out).

## The run

The lab copy switched in for the run and the player's copy switched back after it. Each package installed in turn
with `tools/lab/lab_install.py` into the test slot and opened bare (`hidden_game.py --map B3MadeShadowMaps --no-aliens`,
the fog lifted). The brief's free camera kept each run's own starting heading, so B's first shots looked at the walls
from the other side; the two views were then taken again in both with the camera fixed: the patch from straight above
(`SetOverheadCameraParameters 50 1256 -89 | SetCameraYaw 0` at `ViewLocation -1008 -830 0`) and the blocks at the
play angle (`SetOverheadCameraParameters 70 1256 -45 | SetCameraYaw 0` at `ViewLocation -864 -1200 0`).

## What was seen

- **The patch:** in A, wall T runs diagonally across the picture and O meets T's north face; a dark band runs along T's
  north side and O's west side for their whole length, as dark on the patch as on the asphalt, with no break or step
  at the patch's edges. B is the same to the eye. Compared pixel by pixel, the two pictures differ by 0.31 of 255 on
  average and 0.68% of pixels by more than 15, all on a truck's lit edge and a faint shimmer along edges; nothing on
  the patch, the walls or their bands.
- **The blocks:** dark-topped in both, none wholly dark or wholly lit in one and not the other; the pictures differ by
  0.51 on average (swaying trees, the truck, a lamp), nothing on the blocks.
- Not settled: whether A drew the donor's leftover map. Nothing in A looks like it, and at night both look right.

**Result: passed.** B gives up nothing that can be seen, and the change merged. The pictures are kept privately
(the patch and blocks of each, and the patch's difference image).

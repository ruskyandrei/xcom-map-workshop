# EXP-51: a cleared Bar, its landing zones moved and added

Date: 13 November 2026. Step C9 of the Clear map plan: its game runs. Earlier runs
played a whole map hidden by script (EXP-08) and a grown grid (EXP-43). This run adds:
- a map cleared by the Build (clear_level: the pieces, volumes, emitters, decals and lights taken out of the level,
  one rebuild volume over the grid, even cursor storeys);
- the map's own landing moved and turned in the package, with its intro flight moved;
- a landing zone added under Long War;
- Land here.

## What is built (offline)

The project **EXP-51 cleared Bar**, saved in the editor's store, is built by
`python -B tools/editor/examples/exp51_project.py <scratch folder> --store`. It is a quick build: the lighting is not
baked. It took 43 seconds and gave `URB_Bar_X51`, the project's last build in the editor's builds folder.

- **Bar cleared at its own size** (52 by 39 tiles, 12 levels): 964 pieces deleted, the ground too; the landing's
  pieces, the sun and the sky light kept.
- **Two landing zones**, from `clear_bar_project.py`'s:
  1. Bar's own landing, moved four tiles east and turned to face west. StartLoc goes from (720, -1680) to
     (1103, -1681). The Build moved its frame, evac volume, player start, soldier points and grounded Skyranger in
     place (`landing-moves.json`). It moved the intro's flight place (SeqAct_SetLocation_84) from (560, -2683) to
     (100, -1521). A plain install lands here too.
  2. Added on the car park at (-1297, -1681), facing north: under Long War only.
  - The variant's two LZArray lines are the project's, in that order.
- **A field of floor round each zone**: 7 of Bar's own floor pieces copied in place (its ground slabs and two
  pavements), 432 floor tiles. Every soldier tile has floor (no `landing-floor` warning).
- **The shed** (URB_ResearchOutpost's, as in EXP-44: walls, roof, doors, four props, and its two floors as a building
  made from nothing) between the zones, at x 192 to 768 and y -1824 to -1248. The compiler warns that a crate inside
  it covers two floor tiles (`floor-headroom`), as expected.
- Everything else is empty: no floor, so the ground grid shows there.

Picture `EXP-51-overview.png` (not in the repository): overview.

Picture `EXP-51-zone1.png` (not in the repository): zone 1.

Picture `EXP-51-zone2.png` (not in the repository): zone 2.

## What to look at

Open the project **EXP-51 cleared Bar** in the editor (the main editor, port 8768). Click a landing zone, then
**Land here** in its panel: it plays the last build with the squad landing at that zone. The game must be closed
first.

**Run 1, under LWR** (the lab copy):
1. **Zone 1** (mark 1): Land here.
   - The intro flies in to the moved landing.
   - The squad stands on the six tiles drawn, facing west.
   - The grounded Skyranger and the evac zone are where the editor draws them.
   - An evacuation from there works.
2. **Zone 2** (mark 2): Land here. The squad stands on its six tiles, facing north. The evac zone is where it is
   drawn.
3. **The shed** (mark 3): a soldier inside hides its roof, and its walls cut down.
4. **Past the laid floor** (mark 4, the ground grid): what the cursor and a move do there (F-46: a gap was drawn as
   even blue, the cursor could not land, soldiers could still path).
5. On either zone:
   - no smoke, stains, invisible walls or corpses left of the old map;
   - the cursor's storeys work over the grid;
   - where the pods and the Meld are;
   - a save and a reload.
6. Anything odd: a crash on loading, the squad somewhere else, the Skyranger at its old place.

**Run 3, the same build on plain Enemy Within** (the lab's plain copy): Play in game (no zone to choose; the map has
one landing of its own). The squad should land at zone 1's new place and facing, with the Skyranger and the evac
zone there and the intro flying to it. The pods stand where the map has them: that is the spawns plan's.

Later, not in this build: the project made smaller on X and Y and lower (run 2), the Farm (run 4).

Not looked at in these runs:
- baked lighting (quick build; a full build's relight does not see the Skyranger's move, F-98);
- `?SpawnGroup=` on a plain install, which Land here uses for a zone that is one of the map's own;
- the window's **Keep the scenery outside the play area**.

## Result: passed

Played by the user on 13 November 2026: "already did exp 51 it was ok". So a map cleared by the Build, its own landing
moved and turned in the package (its intro's flight with it), a landing zone added under Long War, floor fields of
the map's own pieces copied in place and a building made from nothing all load and play. Which of the looks listed
above were made one by one is not recorded.

Not covered: the looks listed under "Not looked at" (baked lighting, `?SpawnGroup=` on a plain install, the clear
keeping the scenery outside), and runs 2 and 4. The panel's Used by ticks, the zone gizmo, Map grid and a map grown
as it is came after this build; they change what the editor writes, not how the game reads it, and a map grown as it
is has not been played.

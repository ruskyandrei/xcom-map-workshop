# EXP-44: a hut made as a new building

Date: 11 November 2026. Stage B1 of the prefabs and buildings plan (its 5.1 and 5.2):
the Build makes a building from nothing, a building volume and floor volumes with each floor's list of pieces, and
the game is to treat it as one of its own: the roof hides when a soldier or the cursor is inside, and the walls cut
down. The stage is the blank map as [EXP-43](EXP-43-blank-map-stage.md) left it (36 by 36 tiles).

## What is built (offline)

- **The hut** is URB_ResearchOutpost's shed, brought piece by piece from that map and moved as one by whole tiles:
  four walls (`XComDecoFracLevelActor`), the roof (`XComFracLevelActor`), an open freight door, a swing door (leaf
  and frame), two tarped crates, a small generator and a utility box. 12 pieces. None of the shed's own volumes
  come: a piece brought from another map comes without its building.
- **The building** is asked for by the project's new `buildings` list: one building, "Hut", of two floors, one box
  each, the boxes the shed's two floor volumes had at home (six by six tiles; the ground floor 176 units high, the
  upper floor 208).
- **What the Build makes of it** ([buildings.py](../../tools/bake/buildings.py), called by `native_copy.py`):
  - a building volume and two floor volumes, cloned from URB_Bar's (the blank map has none; the Build's shell
    stage stages the two templates, their lists cut) and stretched over the boxes by `DrawScale3D`;
  - `FloorNumber` 1 and 2; the building's `Tag` its class name; no mesh groups;
  - each floor's list by the game editor's own rule (F-87), from each piece's mesh box where it stands.
- **Read back from the built map** (`python -B tools/bake/buildings.py <the built map>`):

  | Floor | Volume | Pieces listed |
  |---|---|---|
  | 0 | `XComFloorVolume_1`, x 384 to 960, y 960 to 1536, z 0 to 176 | the four walls and the freight door with `CutdownFloor` 1; the swing door's leaf and frame, the two crates, the generator and the utility box without; four of the blank map's ground planes |
  | 1 | `XComFloorVolume_2`, the same footprint, z 176 to 384 | the roof |

  This is the listing the shed has on its home map, piece for piece (the rule gives the shed's own list back but
  for a flood light on its outer wall and a puddle outside its door, neither brought here).
- A quick build (lighting not baked: the pieces keep the light of their home map), 12 seconds.
  `CB2_MP_Blank_X44`, in the editor's builds folder as the project's last build.

## Where to look

Picture `EXP-44-overview.png` (not in the repository): the hut on the blank map.

Picture `EXP-44-inside.png` (not in the repository): the hut's doors.

Open the project **EXP-44 hut** in the editor, then Project, Play in game, and choose to play the last build as it
is. (At the time of the run building it again from the editor was refused, the `building` family being off until
the run passed. To rebuild from the script: `python -B tools/editor/examples/exp44_project.py <scratch folder>
--store`.)

What this run adds, all of it new (the pieces themselves, their cover, breaking and doors are EXP-39 to EXP-41's):

1. **The roof hides with a soldier inside.** Walk a soldier in through the open freight door (5). The roof (2)
   should go, and the inside show.
2. **The walls cut down.** With the roof hidden, the four walls (3) and the freight door should drop to low stubs,
   as a house's walls do, so that the inside is seen from any side.
3. **The roof hides for the cursor.** With no soldier inside, move the cursor into the hut on the ground floor:
   the same. Moving the cursor out, or up a floor with the mouse wheel over the hut, should bring the roof back.
4. **Outside, the hut is whole.** With the soldiers and the cursor outside, roof and walls are drawn in full.
5. **The props inside (6)** show once the roof hides, and stay drawn while it is hidden.
6. Anything odd about the hut that a house on a game map doesn't do: a roof that never hides or never comes back,
   walls that vanish whole instead of cutting down, a flicker at the doors, a soldier who can't path inside.

Not looked at in this run: a save and a reload (F-89: saving fails in any Play in game battle), the light (not
baked), LWR's pods (the grid is 36 by 36).

## Known gaps before the run

- The building volume is the union of the floor boxes. The shed's own at home is larger than its floors (it
  reaches a storey below the ground and well past the walls on two sides); whether the smaller one matters is part
  of what the run shows.
- A volume resized by `DrawScale3D` is known to work for the level volume and the cursor volumes (EXP-43 run 3);
  for a building's and a floor's this is the first run.
- The editor does not draw or edit buildings yet (plan B1.5), and its export does not have the cursor volumes
  (B1.2). The project's `buildings` are carried unchanged by a save in the editor.

## Result: passed

Played by hand on 11 November 2026, in the lab copy: good, and a grenade destroyed the walls correctly.
The hut behaves as a building of the game's: the roof and the walls did what the list above
asks, and a grenade broke the walls as it breaks them on their home map. So a building volume and floor volumes
stretched by `DrawScale3D` work, and a building volume that is just the union of its floors is enough for a hut.

The `building` family was switched on after this run: the editor's own Build now makes a project's buildings.

Not covered: a save and a reload (F-89), baked lighting, a building of more than two floors or with several boxes
on a floor (EXP-45), a UFO.

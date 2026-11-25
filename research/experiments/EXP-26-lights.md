# EXP-26: lights in the game

Date: 9 November 2026. Branch `editor-lights`: the editor's lights (L6;
editor-lights-plan.md, sections 4 and 6). The light family was off for every project then,
so run 1's build took `--family light`. Since 9 November it builds for every project (see "The light family switched
on" below).

## Question

The editor now deletes, changes, moves and copies a map's lights, adds the recipe spot light, and takes a glowing
piece's generated lights along with it. All of it is built and read back offline: the writer's values, GUIDs, poses
and lightmap listings, and the relight's relit pieces. What only the game can say, run by run (plan section 6):

1. A full build: do the edited pools show as edited, with no doubled or leftover light, on the floor and on a soldier,
   and after a save and reload?
2. A quick build of the same project: what does the game do with lights whose bake is not redone?
3. to 6. A far-reaching light on Police Station, Temple Ship's stored 580-degree cone, glowing pieces' generated
   lights, and the recipe spot light on Truck Stop.

## Run 1: URB_Bar, one project with every kind of light edit (full build)

Project: [`exp26_projects.py`](../../tools/editor/examples/exp26_projects.py), "EXP-26 lights" (`26a0a0b1-…`),
variant `URB_Bar_Exp26Lights_26a0`. Each edit stands in its own place:

| Mark | Edit |
| --- | --- |
| 1 | `SpotLight_3` deleted (EXP-17 run 8's spot; baked into 25 pieces) |
| 2 | `PointLight_4`, one of the two small purple lights just past the pool table's end (`XComDestructibleActor_491`): 25 units beyond its short edge, 32 over its top, radius 78 (`PointLight_37` beside it, radius 100). Recoloured from purple to warm orange (255, 176, 96) and brightened from 1 to 2 |
| 3 | The lamp post `XComLevelActor_37` and its `SpotLight_53` (baked into 70 pieces) moved together 6 tiles (576 units) along the south street |
| 4 | `SpotLight_32` (a parking-lot lamp's spot) copied to a dark corner by the wrecked sedan, at (911, -1297, 300), with no lamp post under it |
| 5 | `PointLight_15` (warm yellow, radius 709) copied beside the police sedans at (-1297, -800, 170), where the play area is darkest, and the dumpster `XComDestructibleActor_2` (on the far side of the map, out of the new light's reach) copied into its pool at (-1150, -880, 0) |

Marked editor shots, from [EXP-26-run1-shots.json](EXP-26-run1-shots.json) (the editor's Map lighting, an
approximation of the bake): the overview (`EXP-26-run1-overview.png`), inside the bar (`EXP-26-run1-bar.png`: marks 1
and 2), the street (`EXP-26-run1-street.png`: mark 3), beside the police sedans (`EXP-26-run1-west.png`: mark 5) and
the dark corner (`EXP-26-run1-east.png`: mark 4).

**Offline** (full build `URB_Bar_Exp26Lights_26a0-20261109-185440`, revision 2, `--family light`, 353 s):
- The compiler: 1 light deleted, 2 changed, 2 added; the lamp post moved and the dumpster copied, both made in the
  map; no warnings.
- The relight: 244 pieces relit, 4 shadow maps, 3 skipped, 510 not reached; the added, changed and moved lights
  listed in 126 receivers' lightmaps, 5 more in reach without a texture lightmap.
- The variant exported into a scratch cache and compared with the project (`exp26_check.py`, scratch):
  - `PointLight_4` colour (255, 176, 96), brightness 2, baked into 10 pieces;
  - `SpotLight_53` moved 576 units along X, its rotation kept, baked into 83 pieces;
  - the copies `SpotLight_66` at (911, -1297, 300) and `PointLight_62` at (-1297, -800, 170), with their templates'
    values, baked into 82 and 46 pieces;
  - the lamp post's copy `XComLevelActor_469` at its new place and the dumpster's `XComDestructibleActor_528` in the
    new pool;
  - no other light changed; 258 light GUIDs, all unique; buildings as in the original.
- `SpotLight_3` and the lamp post's original are out of the persistent Level's actor list, and every edited and new
  actor is in it (`native_copy.level_actors`). The export still lists the two (T-21).
- An earlier build of revision 1 (dumpster against the police sedan, which the marked shots showed) was rebuilt.

Installed in the lab's test slot (deploy record `URB_Bar_Exp26Lights_26a0-20261109-190221.json`), with the lab copy
switched in (`switch_install.ps1 lab`).

**The look in game (9 November):** good. One screenshot inside the bar, first turn: a soldier behind the bar
counter, the pool table and the arcade machines in view. Not reported: a soldier walked through the pools (item 6), a
save and reload (item 7).
- Mark 2 can't be judged: the shot doesn't tell whether the orange light was over the pool table or off to the side.
  It is off to the side, and small. `PointLight_4` stands 25 units past the table's short end (towards the arcade
  machines, beside the civilian cutout), 123 units above the floor, with a radius of 78. So it never reaches the
  floor, only the table's end rail and the cutout. The relight changed 440 of the table's 3,736 lighting texels,
  all at that end. The broad orange around the bar counter in the screenshot is the bar's own orange spots, unchanged.
  The run 1 note first called it a ceiling light over the table; the bar shot (`EXP-26-run1-bar.png`) now shows where
  it is.
- To test a recolour properly, mark 2 needs a light whose pool can be seen: one with a radius that reaches the floor,
  in a place the camera sees.

**The light family switched on (9 November).** After run 1 light edits were switched on for every project, before
runs 2 to 6, issues to be fixed as they are spotted or reported. The compiler's `light`
family builds (`compiler.FAMILIES`), so the editor no longer warns that light edits wait for this test, and a Build
no longer needs `--family light`. Runs 2 to 6 stay open as checks. A quick build's light wording stays conditional
until run 2 is played.

**In the game** (played by hand; F9 for a shot; the lab copy; the first mission of a new campaign). What is new, mark
by mark, each against the original Bar's look:
1. Mark 1: no pool where `SpotLight_3` was (the floor there darker than in the original), and no seam at the edge of
   the pieces relit around it.
2. Mark 2: a small warm patch on the pool table's end rail and the rug just past it (the light reaches 78 units);
   `PointLight_37` beside it still purple.
3. Mark 3: the lamp post's pool on the pavement under it at its new place; none left where it stood, and no doubled
   light where the two places' pools would have met.
4. Mark 4: a lamp's pool on the road in the dark corner, with no lamp post under it.
5. Mark 5: a warm pool where the map was darkest; the dumpster's copy lit by it, with no seam between it and the
   ground.
6. A soldier walked through pools 2 to 5 takes their light (the edited light, live), and none from where
   `SpotLight_3` was.
7. A save and a reload: the same.

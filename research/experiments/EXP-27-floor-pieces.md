# EXP-27: floor pieces at their levels

Date: 9 November 2026. Branch `floor-brush`, before its merge: the piece list's Floors, Level snap and the Floor
picker's floor height ([viewer README](../../tools/viewer/README.md), piece list and gizmo;
floor-brush-plan.md, "Superseded").

## Question

Level snap and the Floor picker make one kind of edit easy that no run has played yet: a copy of a plain floor piece
(an `XComLevelActor`) at a height where the map has no floor. F-47 found that a script copy of a floor got no floor
tiles (EXP-08 runs 3 and 3b); EXP-24's van copies, made in the map, did get floor tiles, but inside a van's own
building. Does a floor copy made in the map, raised to a new level, get floor tiles in the game? And does a floor copy
at ground level put the walking surface on its top, as the map's own sidewalks do?

Everything else these copies use has passed before (copies made in the map, their tiles seeded and rebuilt, quick
builds, Bar's landing), so it is not asked again.

## Run 1: URB_Bar, two sidewalk copies

Project: [`exp27_projects.py`](../../tools/editor/examples/exp27_projects.py), "EXP-27 floor pieces at their levels"
(`27a0a0b1-…`), variant `URB_Bar_Exp27Floors_27a0`. Both copies are of the sidewalk strip `XComLevelActor_21`
(`SidewalkStrB8x4`, unturned, on the south street, in no building floor; its saved floor 16 units over its pivot),
29 tiles east of it, in the bar's car park beside the grounded Skyranger. One tile from the drop zone, so the
soldiers start next to them.

| Mark | Copy | Pose | As the editor places it |
| --- | --- | --- | --- |
| 1 | `XComLevelActor_21_copy1` | (1055, -1248, 0), tiles x 40..47, y 3..6 | Level snap on the road: the sidewalks' own height, surface 16 |
| 2 | `XComLevelActor_21_copy2` | (1055, -768, 192), tiles x 40..47, y 8..11 | Level snap with floor 2 chosen in the Floor picker: the bar's floor 2 walks at 210, so 3 levels up, surface 208. No floor there in the map |

**Offline** (quick build `URB_Bar_Exp27Floors_27a0-20261109-171008`, seconds):
- The compiler: 2 copies made in the map, no warnings.
- The writer's log: `XComLevelActor_469` at (1055, -1248, 0), tiles `[38, 49, 1, 8, 1, 1]`, 94 seeded, rebuild
  volume 14055; `XComLevelActor_470` at (1055, -768, 192), tiles `[38, 49, 6, 13, 2, 4]`, 273 seeded, rebuild volume
  14060.
- The variant exported into a scratch cache and compared with the project (EXP-25's `check_variant.py`): both copies
  at their poses; ladders 2, collectibles 0, interactive actors 7, destructibles 434, fracturing pieces 42 and
  buildings 7, as in the original. The scratch export's texture diagnostics are its own (the variant read from the
  builds folder, away from the game's texture packages).
- Marked editor shots, from [EXP-27-run1-shots.json](EXP-27-run1-shots.json): the overview (`EXP-27-run1-overview.png`)
  and the two copies (`EXP-27-run1-strips.png`).
- The landing: the install copies Bar's seven landing zones. The one facing east from (1967, -1489) grounds the
  Skyranger across both strips (no place on clear asphalt is outside all seven); if it comes up, restart.

Installed in the lab's test slot (deploy record `URB_Bar_Exp27Floors_27a0-20261109-171417.json`): the first mission of
a new campaign in the lab copy.

**In the game** (played by hand; F9 for a shot; the lab copy). What is new:
1. Mark 1, the ground copy: a soldier moves onto it and stands on its top, as on the map's sidewalks.
2. Mark 2, the raised copy (`ShowCursorLoc` shows the cursor's height): the cursor lands on its top (about 208,
   level 3). If it does, `TeleportToCursor` puts a soldier there, who stands on it and can be moved along it.

**Result (9 November, run by hand):** passed. Three F9 shots (`look-172150`, `-172157`, `-172218`):
the move cursor on the ground copy's top, with a path to it; a soldier standing on the ground copy; a soldier on
the raised copy after `TeleportToCursor`, his move range drawn over its top and a path along it to its far end. So a
floor copy made in the map, raised to a level where the map has no floor, gets floor tiles (F-47's question, for such
copies), and the ground copy's walking surface is its top. The game log (17:21 to 17:22): the variant loaded with its
intro copy, `WorldData: Restarting work queue (was 0, now 9 tiles)` at load, three `TeleportToCursor`, a save, no
`CachedFrag` or `REBUILD PATHING!` lines.
- Black marks showed on both strips, like shadows: a quick build's copies keep their source's baked
  lighting, and `XComLevelActor_21`'s on the south street has shadows baked across it, so both copies show them where
  nothing casts them. A full build relights them (the viewer README's quick-build note): built afterwards offline
  (`URB_Bar_Exp27Floors_27a0-20261109-172355`, 153 s against the quick build's 9), each copy got 3 lighting textures
  of its own (the quick build's had 0, reading the source's), and the relight wrote 36 lighting textures and 15 shadow
  maps into `Lighting_5905541.tfc`. Not installed or looked at in the game; the lab keeps the quick build.
- Not looked at: dropping off the raised strip (the move range drawn covered its top only), cover at its edges.

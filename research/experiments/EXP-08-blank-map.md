# EXP-08: A blank map on URB_Bar (plan)

Status (4 November 2026, 20:30): **runs 1 and 2 work in game, save and reload included, except the hole, whose tiles
can still be walked (F-46). Holes are set aside, and run 3 (the block with two storeys, no hole) is
deployed. Its second floor got no floor tiles (F-47); run 3b, without the ceiling beams, didn't fix it. The second floor is set aside as an open finding.** This was taken as the
next experiment, before the viewer (../viewer-plan.md). Run notes are at the end.

## Goal

Show that a map can start from nothing. Wipe everything URB_Bar places in its play area, ground included. Then lay our
own ground and build a small layout from URB_Bar's own pieces. This is the editor's "start from scratch" mode: the
base map gives the grid and the pieces, and nothing else of it stays.

The result ships as a map of its own, `URB_BarBlank`, beside `URB_Bar` and `URB_BarRemix`, as EXP-07's share package
does (F-42).

## Decisions (4 November 2026)

- **Assets:** only the base map's own pieces. For URB_Bar these are its 324 static meshes, 45 fractured meshes and the
  archetypes it loads (cars, windows, doors). Art from other maps is out of scope for now.
- **Grid:** the base map's grid: 52 × 39 × 12 tiles from (−2784, −1920), 96 units across and 64 up. A map can't grow
  past it.
- **Lighting:** dynamic everywhere. The copies are lit dynamically already. The base map's lights go, and the map gets
  a light of our own.

## What URB_Bar has

From the inventory (`<lab>\exp07\urb_bar-inventory.tsv`, `tools/upk/map_inventory.py`): 1,535 actors, 332 of
them outside the play area. Those 332 are the backdrop: midground buildings and street blocks.

| Kind | Count |
| --- | --- |
| Destructibles (props, windows, cars) | 434 |
| Level actors (walls, floors, roofs, props) | 256 |
| Static mesh actors (ground, backdrop) | 195 |
| Fractured actors (walls) | 60 (42 XComFracLevelActor, 18 XComDecoFracLevelActor) |
| Doors / ladders | 7 / 2 |
| Lights | 62 spot, 54 point, 137 generated area lights, 1 dominant directional (the moon), 1 sky light |
| Emitters / decals / physics actors / ambient sounds | 70 / 38 / 14 / 5 |

**The ground is meshes**, so it can be hidden and copied. It is mostly 49 `AsphaltPlaneFlat` level actors: flat 960 ×
960 planes, 10 × 10 tiles, at z 0. There are also sidewalks (`BoundSidewalk*`, `Sidewalk*`) and the street blocks
outside. There is no terrain, and the level's BSP model is tiny (8 KB).

**Gameplay actors stay where they are** in this experiment (moving them is EXP-06):

| Actor | Tiles |
| --- | --- |
| PlayerStart | (36, 4) |
| 18 soldier spawn points | (34..43, 4..7) and (5..8, 34..37) |
| 5 alien pods | (45, 37), (19, 18), (19, 24), (14, 29), (7, 24). The last four are inside or beside the bar's footprint. |
| 4 Meld spawn points | (14, 31), (14, 23), (40, 29), (15, 7) |
| LWR's 7 landing zones | for example (719, −1681), (−1297, −1681), (1103, 1583) |
| Volumes that block or steer, invisible | 2 path-blocking volumes (39, 17) and (10, 17), 2 cover seeds (18, 27..28), 4 no-spawn volumes, 2 trigger volumes |

## The layout

**Run 1, the blank grid.** Everything in the play area is hidden. 24 asphalt copies (6 × 4 planes of 10 × 10 tiles)
cover it, with a sun light. This is the empty canvas the editor would start from.

**Run 2, a small layout** on that ground:
- the step 3b block (walls, doors, windows, roof, ladder), with its building volume, at a new place;
- a sidewalk ring around it;
- a 4 × 4 hole in the ground, to check that tiles with no ground can't be walked on;
- props as cover near the pods: dumpsters, planters, crates;
- three spawned cars, snapped to the grid.

Draw it first as a plan, `tools/upk/plans/urb_bar-blank.json`, with `tools/upk/map_picture.py`, as for the L and the
U.

## What to build

1. **Hide everything.** One `hide` box over the whole play area, with:
   - the ground hidden too (`KeepGroundHeight` below 0);
   - `bHideLights`, `bHideVolumes` and `bHideFragments`;
   - the cursor volumes kept: without them the cursor can't go up a level (F-21).

   The backdrop outside the play area stays in run 1, as scenery. A variant hides it too, for the bare look.
2. **Ground fill.** One `copy` object places its pieces once, so tiling 24 planes needs 24 objects. Add either a
   `repeat` field (a grid of offsets) or a small spec generator.
3. **A light.** A `sun` object type: XComMapEdSun on its own, which is the photo object's light without its camera and
   UI changes. It takes yaw, pitch, brightness and sky. Start from the photo defaults: sun 1.2, sky 0.5, yaw 138,
   50° down. This is a night map, so the brightness needs a look in the game.
4. **An empty base patch.** patch_bar's cover fixes belong to the old layout. `base` becomes a new, empty `.udk`.
5. **Shipping under the new name in patchtool** (`map.shipAs`). It would:
   - seed a copy named `URB_BarBlank.upk` and leave `URB_Bar.upk` original;
   - write the map record and the landing-zone lines.

   This removes the hand copying EXP-07 needed (see its last note), and it is what the editor's Build will do.
6. **Seeds.** `seed_map.py` plans the tiles from the spec's boxes, for the layout's walls and roof. Ground-level tiles
   were floor in the bake, so the rebuild re-checks them anyway.

## Questions this answers

| | Question |
| --- | --- |
| Q1 | Does the hider's rebuild over the whole map (24,336 tiles) work, and how much load time does it add? |
| Q2 | Does anything invisible stay: path-blocking volumes, cover seeds, no-spawn volumes, Kismet, ambient sounds? |
| Q3 | Do units stand, walk and take cover on copied ground everywhere? Do the hole's tiles stop movement, and does the cursor work there? |
| Q4 | Does the squad land (LWR's landing zones) and do the pods and Meld appear and act on open ground? |
| Q5 | Does dynamic light alone look acceptable on a night map? |
| Q6 | How many copies can the copier make at load (about 24 for the ground plus about 40 for the layout) before load time suffers? |
| Q7 | Does the layout survive a save and reload mid-mission? |

## Runs and checks

**Run 1 (blank grid):**
- an overview shot (photo object) from run 35's angle: nothing of URB_Bar's play area, and ground everywhere;
- the hider's census: every ground-level tile is floor, none is occupied and none gives cover;
- a soldier walked across where the bar stood, and over the old cars' tiles;
- a look for invisible blocks at the path-blocking volumes and the cover seeds;
- the landing, and the pods on open ground.

**Run 2 (layout):**
- the building as in EXP-07: doors, windows, ladder, roof cutaway, the cursor inside;
- the hole's tiles can't be walked on;
- props and cars give cover, and walls block line of sight;
- one pod fought, or the mission won;
- a save and reload mid-mission. Not while WSL2's hypervisor runs, since saving crashes then (EXP-03);
- load time from `Launch.log` timestamps, against `URB_BarRemix`.

## Pass criteria

- Nothing of URB_Bar's play area shows or blocks.
- Units move, see and take cover by the new layout only.
- The mission starts, lands the squad and can be won, and a save and reload keeps the layout.

## Risks

- **Hidden sources.** The copier copies from pieces the hider hides. The copies are new actors and the hider leaves a
  patch's actors alone, but check run 1's log that no copy comes out hidden.
- **Floor heights.** With the baked ground gone, the ground-level floor comes from the copies. Where a copy's top
  differs from the bake (kerbs), floor heights change.
- **Landing zones.** LWR's landing zone can put the squad on objects (F-06, open). Keep the seven landing-zone areas
  clear in run 2.
- **Kismet.** URB_Bar's Kismet may switch hidden things back on (lights, sounds). The hider re-hides what it hid every
  3 s; sounds aren't in its list.

## Lab

- Point the test slot (`DefaultMaps.ini` line 36, now `URB_BarRemix`) at `URB_BarBlank`, and add its landing-zone
  lines.
- Back up first, as patchtool does.
- Switch back to the LWR install when handing over.

## Runs

### Run 1, the blank grid (deployed 4 November 2026, 19:11)

**What was built.** The spec `tools/patch/examples/exp08blank.json` is written by `tools/patch/gen_exp08.py` from
patchtool's inventory of URB_Bar. Rerun the generator after changing it; `--photo` adds the overview view. The patch
`patch_exp08blank` holds:
- **30 ground planes.** Each is a copy object: one copy of `XComLevelActor_242`, a plain `AsphaltPlaneFlat`, 960 ×
  960 at z 0, pivot at its centre. They stand on the tile grid at x −2304..2496 and y −2016..1824, step 960, and
  cover x −2784..2976, y −2496..2304. The first copier also logs the cursor's tile (`bLogCursor`), three A* paths and
  six floor probes:
  - a path across the bar's footprint;
  - a path north to south, west of the bar;
  - a path by `PathBlockingVolume_0`;
  - floors where the bar stood, at the edges, in a corner, and one level up.
- **A sun** (`XComMapEdSun_930`): sun 1.2 from yaw 138, 50° down, and sky 0.5. It is the only light.
- **One hide box** over the play area, x −2784..2208, y −1920..1824, z −64..832. It hides:
  - everything in the box, the ground included (`KeepGroundHeight=-1`);
  - the lights (`bHideLights`, the moon `DominantDirectionalLight_1` and `SkyLight_0` among them);
  - the building and floor volumes, and all wall fragments;
  - 40 actors by name, those that reach in from outside (F-43).

  It keeps the cursor volumes (F-21) and the grounded Skyranger. A probe line goes through the bar's old front wall.
- **An empty base** (`"base": ""`), not `patch_bar`. 33 actors: the spec's 32 and the leading Note.

**Changes from the plan:**
- 30 planes, not 24. The original row north of the play area and column east of it reach 384 and 192 units in,
  so they are hidden and covered as well (F-43).
- A spec generator instead of a `repeat` field. A copier keys everything by source name and copies each source once,
  so a fill needs one copy object per plane. That is what the editor's Build will write anyway.
- The map record patchtool writes is out of rotation (`map.inRotation` false), so the lab campaign doesn't pick a
  blank map. The test slot is how it is played.

**Lab state:**
- `URB_BarBlank.upk` is an unseeded copy of the original. There are no tiles to seed: the copies are all at ground
  level.
- `URB_Bar.upk` and `URB_BarRemix.upk` are untouched.
- `DefaultLZMutator.ini` has URB_Bar's seven landing zones under `URB_BarBlank`.
- `DefaultMaps.ini` has a record `URB_BarBlank (EXP-08 blank map) |0` after URB_Bar's, at line 6. So the test slot
  moved from line 36 to line 38. It now loads `URB_BarBlank` with `patch_exp08blank` (it was `URB_BarRemix` with
  `patch_exp07wing`).

**To check in game** (the list above, under "Runs and checks"):
- an overview: needs a `--photo` build;
- the hider's census and ground rows in `Launch.log`: every ground-level tile floor, none occupied, no cover;
- a soldier walked across where the bar stood and over the old cars' tiles;
- the path-blocking volumes at (39, 17) and (10, 17), and the cover seeds at (18, 27..28);
- the landing, and the pods on open ground;
- the light on a night map (Q5), and the load time (Q1).

**In game (19:16).** The map looks right. A shot from the landing zone shows open asphalt to the edges, lit by
the sun. Three things were left:
- Green corpse-like things were still there. These are URB_Bar's 13 flattened civilian corpses
  (`KAsset`, `CivFlatB`). The hider hid them, actor and mesh, and the game drew them anyway (F-44).
- There was no landing. Every new mission on URB_Bar and URB_BarRemix had the dropship cutscene. The hider had
  switched off two pieces of the landing prefab, which LWR copies to the landing zone (F-45).
- Day or night. URB_Bar's record says night, while the test slot's (Commercial Alley's first-mission slot) says
  day. What `TimeOfDay` does, from the game's scripts and LWR's config:
  - the game picks a map for a mission by it (`XComMapManager.GetRandomMapDisplayName` takes the mission's time);
  - LWR counts night missions by it for its achievements (event 25 with `iParamA=1`, `eMissionTime_Night`);
  - `WorldInfo.m_eTimeOfDay` is read only by a cheat command.

  Nothing found makes the lighting follow it: a map's light is what the map has. So a record should say what the
  map looks like, and the sunlit blank map is a day map.

The log, from the hider:
- **Census (Q1).** At ground level, after the rebuild, all 2,028 tiles are floor (52 × 39), with 9 occupied and no
  cover at all. Before hiding, 606 were occupied and 538 gave cover. The tiles still occupied higher up (49, then
  86) are the grounded Skyranger, which stays.
- **Counts.** 1,052 actors hidden and 25 volumes switched off. It took about 0.02 s to hide (31.64 to 31.66 in the log)
  and about 0.23 s more for the rebuild of the whole map (to 31.89).
- **Ground rows.** The hider's ground rows were all blank, because they are drawn 16 units above the box's floor,
  which is now at z −64, below the world. The census is the reliable count.
- **Landing zones.** LWR found the seven `URB_BarBlank` landing zones and used #1, (−1297, −1681).

### Run 1b (deployed 4 November 2026, 19:29)

- **The hider (F-44, withdrawn later).** A physics actor (`KAsset`, `KActor`) has its physics stopped and its meshes
  detached, which takes them out of the scene.
- **The generator (F-45).** It keeps every piece of the landing prefabs (archetypes `DGN_DropShipSoldierSpawn.*` and
  `VEH_Lv1Skyranger_MOD.Prefabs.*`), 14 actors: the grounded Skyranger, the dropship volume, the drop zone, the player
  start, the spawn points, the Skyranger's effect and sound.
- **Day.** The spec sets `map.timeOfDay: Day`, a new patchtool field. URB_BarBlank's record (`DefaultMaps.ini` line
  6) now says day. The test slot said day already.

To check: the dropship cutscene plays; no corpses; nothing else changed.

**In game (19:33).** No Skyranger landing still. Green corpses again, by the pods: they are made by the AI pods that
spawn there. So F-44 is withdrawn.

The log shows the intro camera moving this time (from (2365, 502, 842), as in URB_Bar's runs), so keeping the
landing prefab mattered. The rest of the cause is in `CIN_DropshipIntros`' Kismet, read with the new
`tools/upk/kismet_links.py`:
- the landing is chosen by the exact map name: `URB_Bar` places the dropship and plays `CIN_PlayDS_03`;
- any other name ends at `CIN_DS_Stop`, so URB_BarRemix had no landing either (F-45).

### Run 1c (deployed 4 November 2026, 19:37)

- **`XComMapEdIntro`**, added by patchtool to any spec with `map.shipAs`. At load it renames `URB_Bar`'s case in the
  intro's map-name switches to `URB_BarBlank`, in the running game only, so URB_Bar's landing plays. It uses a new
  stub of the game's `SeqCond_SwitchString`, and the cooked patch imports the game's class.
- **The hider** is back as it was before run 1b. The corpses come with the pods.

To check:
- the dropship lands at the start of a new mission;
- `Launch.log` has "XComMapEd: XComMapEdIntro_933 intro: ... now plays URB_Bar's case", and no warning.

**In game:** fixed, the intro works correctly now. `XComMapEdIntro_933` renamed `URB_Bar`'s case at
load, on its first try (30.47 s in the log), and the intro started at 48.01 s.

If the landing plays but the dropship comes down away from the squad: the Kismet puts it at URB_Bar's fixed spot,
(560, −2683). How it then reaches LWR's landing zone on URB_Bar hasn't been looked at yet.

### Run 2, the small layout (deployed 4 November 2026, 19:47)

Picture `EXP-08-plan-run2.png` (not in the repository): Run 2 plan.

The plan is `tools/upk/plans/urb_bar-blank.json`, drawn with `tools/upk/map_picture.py`. Its new `blank` mode starts
the after panel from nothing and draws ground, holes, sidewalks and props. `tools/patch/gen_exp08.py` (now `--run 2`
by default; `--run 1` gives the blank grid) writes the spec and the plan from the same numbers. On run 1's ground:
- **The step 3b block**, in the middle of the map: tiles x 20..31, y 13..24, centre (−288, −96). It uses the L
  layout's wing pieces and building floors, turned 90°, with doors copied (`bCopyDoors`). To close the side that was
  open, it adds step 3b's closing copy (yaw 270) and a door for its frame (`XComInteractiveLevelActor_4`). The wing's
  furniture and wood floor come along, moved with the block, and so does the visible ladder on the north wall (at
  (−240, −720), on the north sidewalk). The copier settings are the wing's: `LateRebuild` 4 s, `LadderFootRebuild`
  6 s and `bProbeIndoor`.
- **A sidewalk ring**, 4 tiles wide, tiles x 16..35, y 9..28. It is 16 copies of URB_Bar's own pieces:
  `SidewalkCrnA4x4` (`XComLevelActor_116`), `SidewalkStrA8x4` (`_47`) and `SidewalkStrA2x4` (`_111`). Each side is
  8 + 2 + 2 tiles. The rule, from the bar's own ring: at yaw 0 a piece runs +x from its pivot and 4 tiles −y, with the
  curb on its +y edge. A corner piece has curbs on −x and +y. The copier's yaw is the wanted yaw less the source's.
- **The hole**, tiles x 3..6, y 27..30. The asphalt plane centred at (−2304, 864) is left out. Four copies of it,
  scaled with `CopyScale` (0.3 × 1 twice, 0.4 × 0.3 twice), fill the rest of its square.
- **Cover**, each piece centred on whole tiles:
  - west of the ring: a dumpster (`XComDestructibleActor_2`) on tiles (9..10, 13), a box stack (`_12`) and a trash
    can (`_29`);
  - east: a dumpster on (41..42, 15), a metal fence (`_18`) and a box stack;
  - south: a dumpster on (24..25, 32), a box stack and a trash bag (`_297`).
- **Three cars**, spawned and snapped to the grid (F-41):
  - an SUV east of the ring, along x, about tiles (38..41, 22..23);
  - a compact between the hole and the ring, along x;
  - a compact north of the ring, along y, about tiles (22..23, 4..6), between the two north landing zones' spawn
    points.
- **Probes**, on the first ground copier, which also logs the cursor's tile:
  - A* paths across the hole west to east and north to south, from the north sidewalk into the block, and up the
    ladder;
  - floor tiles at the hole's middle and corner, beside it, on the west sidewalk, inside the block and on its roof.

**The build.** 81 actors, the intro actor among them. 1,285 tiles were planned for seeding, and 868 of them were
seeded in `URB_BarBlank.upk`; the other 417 already had bits set. `URB_Bar.upk` is untouched.

**To check in game:**
- the building as in EXP-07: doors, windows, the ladder, the roof cutaway and the cursor inside;
- the hole's tiles can't be walked on, and the cursor there;
- the props and cars give cover, and the walls block line of sight;
- the sidewalk's curbs face out, with no gaps or overlaps;
- one pod fought, or the mission won;
- a save and reload mid-mission. Not while WSL2's hypervisor runs, since saving crashes then (EXP-03);
- the intro still plays.

**In game (19:58).** It works, save and load included. So the layout passes, and so does Q7 (save and reload). The
hole doesn't pass Q3:
- the gap in the map stood out: it was drawn as an even blue square;
- the cursor can't be put in it, but a path to the far side goes across it.

From the log (the first ground copier's probes):
- **At load,** with the baked data, the A* paths go round the hole or along its edge row.
- **5 s after load,** after the rebuilds:
  - the hole's middle tile (5, 29, 0) is "on floor True, floor z 0", and both paths across it go straight;
  - the path from the north sidewalk into the block takes 9 tiles, through the north door;
  - the path up the ladder to the roof is 2 tiles, (26, 12, 0) to (26, 13, 6), so the climb works;
  - the block's ground floor is at z 16 and its roof at z 402.
- **The cause (F-46):** the rebuild gives every bottom-level tile a floor at the level volume's bottom, ground mesh
  or not. A hole needs its tiles marked as blocked some other way.

Run 1's log also answers part of Q2. URB_Bar's `PathBlockingVolume_0` at (39, 17) steered the path at load, but 5 s
later the path went straight through its tile. Its effect is baked, and the rebuild drops it.

### Run 3, two storeys and no hole (deployed 4 November 2026)

Picture `EXP-08-plan-run3.png` (not in the repository): Run 3 plan.

Next: the holes are left, and another change of this map has the main building two storeys tall with an interior
ladder (or stairs, if the map has any), and no hole.

**What URB_Bar has.** No stairs: its only ways up are two `XComLadder`s, both `LadderMetal.Meshes.LadderMetalA_448`
(z 16..491, up to the roofs). It has no upper-floor slab either. The bar's blocks are one tall storey: walls z 0..400,
the roof slab at z 398..402, the ceiling's I-beams at 362..397. Their building still has two floors below the roof
(floor volumes z 16..208 and 208..400, then the roof at 400..592), so a second floor at z 208 fits inside the shell,
with 192 units (3 levels) to each storey. The one piece at z 208 is the strip over the recessed shop front's porch
(`XComFracLevelActor_17`, `Core_384FloorB`).

`tools/patch/gen_exp08.py --run 3` (now the default) writes run 2's layout without the hole: the asphalt plane at
(−2304, 864) is back, the four scaled pieces go. It adds:
- **The second floor**: two copies of the wing's wood floor (`XComLevelActor_302`, `URB_Bar_384CFloor`, 13 × 13
  tiles) a storey up, at z 209 and 210 (run 3b: 207.5 and 208.5, tops at 209.5 and 210.5). One covers tiles x 21..31, y 13..24, the other x 20..31, y 13..23, so together
  they cover the block but its south-west corner tile (20, 24), the ladder well. Each is scaled close to its own size
  (11/13 by 12/13), so the planks keep their look; a floor cut from thin strips would squeeze them. They reach over the
  porch to the shop front's outer facade, above the porch strip.
- **The cutaway.** A copy takes its source's floor-cache entry, and the wood floor's is the ground floor. The copier's
  new `BuildingFloor` setting puts every copy on one floor of its building instead (cutdown floor 0, as the spawner
  does for the roof car). The two floors and the boxes below use `BuildingFloor=1`, so they are hidden while the
  ground floor is shown.
- **The ladder**, a visible patch ladder in the well at (−816, 432, 16), yaw 0, against the new floor's west edge
  over tile (21, 24). It is URB_Bar's ladder squashed to 0.42 of its height (`DrawScale3D` Z 0.42, about 200 units).
  The game puts the ladder's top point 76 units on and `GetHeight() + 8` up (research/native/ladder-links.md), here
  (−740, 432, 224): tile (21, 24) at level 3, where the new floor's top (z 211) should give a floor. patchtool's
  ladder now takes `loops` (`LoopAnimations`, 4 by default), set to 0 here. The climb plays the full get-on animation
  for ladders 192 units or taller, and it snaps the unit to the top at the end, so a wrong count only looks off.
- **Cover upstairs**: two box stacks (`XComDestructibleActor_12`), on tiles (28, 17) in the east room and (23, 16) in
  the north-west room.
- **Probes**, on the first ground copier:
  - A* paths up the inside ladder, from the north sidewalk into the block, up the outside ladder, and from the second
    floor to the roof;
  - floor tiles on the second floor, in the well, at the ladder's top, inside, on the roof, over the porch and where
    the hole was.

There is no way up from the second floor to the roof, and the walls have no windows upstairs, so the second floor is
closed except for the ladder well. The outside ladder still goes to the roof.

**To check in game:**
- the second floor shows when a unit is upstairs (or the cursor is raised) and hides while the ground floor is shown;
- the inside ladder climbs both ways, and the climb looks right;
- the second floor can be walked, and its box stacks give cover;
- the well can't be stood in on the second floor;
- the old hole's ground looks and walks like the rest;
- the rest as in run 2.

**In game (run 3, 20:15).** The second floor can't be reached: the cursor won't hit that floor, so a soldier can't
even be teleported to it, and the ladder looks unattached to any floor. The shot shows the second floor drawn, with
the soldier below it drawn through it, and the ladder in the well.
- The log: every probe on the second floor is "on floor False", at load and 5 s later. The ladder's top tile
  (21, 24, 3) and the tile below it have no floor, so there was no climb. The roof keeps its floor at z 402.
- The cause (F-47): the ceiling's I-beams collide as one solid box under the whole roof (z 362..397). That left the
  new floor 151 units of headroom, against ComKit's 190, and the game gave it no floor tiles.

### Run 3b, without the ceiling beams (deployed 4 November 2026)

The two-storey block leaves `XComLevelActor_4` (the I-beams) out, and the second floor's pieces go down 1.5 units,
to tops at 209.5 and 210.5: ComKit's second-floor height, with 188 units up to the roof slab's underside. The box
stacks upstairs stand on it. Everything else is as in run 3.

**To check in game:** as run 3; first of all, the cursor on the second floor and the climb up the inside ladder.

**In game (run 3b, 20:25).** The second floor still can't be reached; it is left for now as an open finding, to try
again later. The log is the same as run 3's: no floor at level 3, no climb. Headroom isn't
the cause; F-47 stays open, with the next things to try listed there. The layout without the hole stays as it is.

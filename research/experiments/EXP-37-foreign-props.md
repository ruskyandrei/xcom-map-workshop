# EXP-37: two props from other maps in URB_Bar

Date: 11 November 2026. The first game check of pieces from other maps
(implementation plan, X4's gate). Everything before it was offline:
an object another map holds can be copied into a map by renumbering alone (findings register T-31). What no offline
check can say is whether the game draws such a piece and treats it as one of the map's own.

## What is built (offline)

- The edit: [EXP-37-edit.json](EXP-37-edit.json), a native edit with two foreign copies, each naming its donor map.
  - A lamp post of URB_PoliceStation (`XComLevelActor_15`, `parkLampPost.Meshes.ParkLampPost_B`). It brings its mesh
    and body setup, a material instance whose parent the bar already has, three textures and its two baked textures:
    14 objects, 38 KB.
  - An alien wall panel of CAbductor_Cliffside (`XComLevelActor_106`, `AbductorWalks.Meshes.AbductorWalkWallStrSngl`).
    It brings a base material the bar has no relative of (`GEN_MaterialParents.Master_Materials.ALIEN_Base_NoLMSPC`,
    with its expressions), a material instance, textures, the actor's archetype and its baked textures: 24 objects,
    26 KB. It replaces the plan's first choice, AlienBase01's `Cave1`, which turned out to be a whole cave (51 by 38
    tiles).
- The build, two commands:
  - `python -B tools/bake/transplant.py <LWR cooked>\URB_Bar.upk <out> --edit EXP-37-edit.json` stages both actors
    in a copy of the bar (`<out>\staged\URB_Bar.upk`: under the level, in no actor list) and writes the edit again
    with the staged actors' names;
  - `python -B tools/bake/native_copy.py <out>\staged\URB_Bar.upk <out>\build URB_Bar_X37 --copies
    <out>\native-edit.staged.json` makes the copies as it makes any (a quick build: no relight, so each prop keeps
    the light of its home map), with tile seeds and a rebuild volume each.
- Deployed to the lab copy's test slot with `deploy_fixture.py` (here `<lab>\bake-fixtures\exp37`, record
  `URB_Bar_X37-20261111-130956.json`): the first mission of a new campaign plays `URB_Bar_X37`.
- Offline, the variant was exported by the viewer's exporter and opened in the editor page: both props draw there
  with their own meshes, materials and textures, read from the grown package. The shots below are of that export.

## Where to look

Picture `EXP-37-run1-overview.png` (not in the repository): overview.
Picture `EXP-37-run1-close.png` (not in the repository): close.

Both stand in the car park lane south of the bar's front, between the parked cars and the Skyranger.

## Run 1: passed

What this run adds, and nothing else needs checking:

1. **The map loads.** A crash or a hang at load is the result; `Launch.log` then says which import or export.
2. **Each prop draws with its own material.** The lamp post: dark iron, yellow glass. The wall: a dark alien panel
   with orange lights on the face towards the bar (its other face is not drawn in its home map either). Grey, black,
   checkerboard or missing is the result to report. Both will look lit for another place (too dark or too bright):
   that is the quick build, not a fault.
3. **Each stops a unit and gives cover.** A soldier can't walk through either; beside the wall the shield is full
   (high cover) and it blocks sight; the lamp post gives what a pole gives (low or none).
4. **A save and a reload** bring both back, drawn the same.
5. `Launch.log` after the run: no line naming `URB_Bar_X37` with "Failed to load", "Can't find" or "Missing".

If a prop is grey, missing, or the map doesn't load, the work stops here until the cause is found: the catalogue,
the compiler and the panel are worth nothing without this.

Result (11 November, the lab's test slot played by hand): **everything checks out.** The map loads, both props
draw with their own materials, each stops a unit and gives its cover, and both come back after a save and a reload.

- Not checked: item 5. The `Launch.log` in the game's documents folder is from 3 November (327 lines, no mention of
  the variant), so the run wrote none there; nothing in the play suggested a failed load.
- What it settles: a piece of another map, copied into a map with what it depends on by renumbering alone, is to the
  game a piece of that map. A material instance of a parent the map has, and a base material the map has no
  relative of, both find their shaders in the shared cache; the donors' baked textures are read from the shared
  `Lighting` cache; staged actors that the Level doesn't list do no harm; the tile rebuild takes the copies' meshes
  for cover and blocking as it takes the map's own.
- Not covered by this run, and still ahead: a full build (the foreign piece lit for where it stands, X8), and every
  family but plain props (X9).

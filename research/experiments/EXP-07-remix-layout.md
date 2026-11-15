# EXP-07: Remix the bar into a bigger building

Status (4 November 2026): **running.** Step 1 (inventory) is done; the step 2 hide test is built (`patch_exp07hide`)
and waits for its first in-game run. It follows the EXP-05 fire test. It is
experiment 4 of `research/mission-editor-feasibility-update.md` ("whole-layout overlay"), done on a real map instead
of the blank multiplayer one.

## Question

Can a layer streamed into an existing map (a "remix", like the installed "Redux" maps) replace that map's layout:
remove its building and put up a different, larger one from the same kit pieces, inside the map's play area? For
URB_Bar the play area is 52 × 39 tiles and 12 levels, about 78 × 58 m and 12 m high.

A remix can appear in the campaign as a map of its own: a `DefaultMaps.ini` record with the base map plus our layer,
as the Redux maps do. It shares the base map's name, so LWR's landing zones for it are the base map's (F-06 in
`research/findings-register.md`).

## What it answers

1. Removal: can the base map's own building (fixed architecture with baked lighting and tiles) be hidden cleanly, with
   no collision, cover or line-of-sight blocking left behind?
2. Building from pieces: can walls, floors, roofs, windows and doors from the map's own kit be placed on the tile grid
   as working gameplay objects (collision, cover, line of sight, destruction)?
3. Interior lighting: does a building of dynamically lit pieces look acceptable indoors, with a few lights of our
   own? What does it do to the frame rate?
4. Building systems: roof and floor cutaway when units go inside (building volumes), stairs or ladders in pathing,
   doors.
5. Saves: does a save and reload mid-mission keep it all?

## Steps

1. **Inventory.** List the bar building's actors from the map:
   - walls, floors, roof, windows, doors;
   - building and floor volumes;
   - lights.

   Use `tools/upk/map_layout.py` and the uncooker reference. Note which kit meshes and archetypes URB_Bar loads.
2. **Hide test.** At load, hide the bar building (rendering and collision) and rebuild the tiles over its footprint.
   In game:
   - it is gone;
   - its area can be walked;
   - no cover or line-of-sight blocking is left;
   - no roof cutaway stays behind.
3. **Build.** On the 96 × 64 tile grid, from the same kit, build a larger building:
   - walls on tile edges and a floor per level;
   - a door and windows;
   - a stair or ladder;
   - a building volume for cutaway;
   - a few dynamic lights.

   Placed pieces need a class with collision and cover, unlike `XComMapEdBorrowedMesh`, which is visual only. Lighting
   is as in F-02, names as in F-15.
4. **Check in game:**
   - looks: lighting inside and out;
   - cutaway as units enter and climb;
   - pathing, including the stair;
   - cover inside;
   - line of sight through walls and windows;
   - doors;
   - explosions against walls;
   - frame rate;
   - save and reload.

## Pass criteria

- The original building leaves no trace in play.
- The new building plays like one of the game's own in each check of step 4. Any check that fails gets an entry in
  the findings register.

## Known risks

- Fixed (`bStatic`) map actors may not be removable from script; hiding may need another route.
- Interior lighting may look flat without baked light.
- Performance with hundreds of dynamically lit pieces is unknown.
- Pieces from other maps' kits would need their packages loaded (untested). This test sticks to the bar's own kit.

## Runs

### Step 1: inventory (4 November 2026)

Tool: `tools/upk/map_inventory.py` (new). It lists every actor in the persistent level with its class, archetype,
mesh, world box, tiles and the building volume holding its centre, and writes each building volume's floors, floor
volumes and contents. Output: `<lab>\exp07\urb_bar-inventory.tsv` and `urb_bar-inventory-buildings.txt`.

URB_Bar has 1,535 actors and 7 building volumes. Six of them are small: vans and the dropship. The bar is
**XComBuildingVolume_0**:

- **Box:** x −1859..925, y −157..1411, z −128..640. That is tiles x 9..38, y 18..34 (30 × 17 tiles).
- **Floor volumes:**
  - floor 1: z 16..208;
  - floor 2: z 208..400. This one holds the ceiling decoration, not a storey;
  - floor 3: the roof, z 400..592.

  So the bar is one tall storey, 6 tile levels high inside, with a walkable roof.
- **Contents:** 679 actors with their centre inside, among them 307 destructible props, 113 lightmass area lights,
  38 spot and 18 point lights, 51 level actors, 43 fractured actors, 7 doors and 2 ladders.

**The building kit is modules, not tiles.** The shell is two "core" blocks from `ComKit_Meshes`:

- a 12 × 12-tile block at (−1056, 672);
- a 13 × 13-tile corner block at (96, 672).

Each side of a block is one fractured mesh, a whole wall side 12 tiles long and 384 units (two floor heights) tall:

| Part | Meshes |
| --- | --- |
| Front | `Core_384FacadeA..D` |
| Back | `Core_384BackA..C` |
| Corner-block sides | `Core_384CLeftA..C`, `Core_384CRightA..D` |
| End walls | `Wall_ExtCROWN_384A/G` |
| Inner walls | `URB_BarIntWallA/B` |
| Roof | `Roof_Barrier*` (floor and trim, 12 meshes), at z ≈ 400 |
| Ground floor | `URB_Bar_384Floor` and `URB_Bar_384CFloor`, z 14..18 |
| Upper slabs | `Core_384FloorB` and `Core_384CFloorB` (strips only) |

Other pieces:
- windows from `ComKitWindows` (17 meshes, destructible);
- doors: `DoorSwingSingle_MOD` and `DoorSwingDouble_MOD`, frames plus interactive doors;
- metal ladders to the roof.

The cooked map holds only the pieces it uses: 16 cores, 12 roofing pieces, 2 end walls and 8 bar-specific meshes.
There is no tile-sized wall piece.

What this means for step 3:
- A bigger building from the bar's own kit is a set of core blocks placed side by side, leaving out the sides
  between them. It can't be a free layout of single wall tiles.
- A free layout needs modular wall pieces from other maps' packages, which is untested (risk 4).
- Stretching the core walls with DrawScale would also stretch their windows and doors.
- The other URB maps' kits are a candidate source for more pieces. The `_CNH`, `_EWI` and `_CovExt` overlays may also
  show how Firaxis remixed maps.

### Step 2: hide test (built 4 November 2026)

New script class **`XComMapEdHider`** (`XComMapEd`). It is placed by a patchtool object of the new type `hide`, with
`location`, `half`, `keep`, `alsoHide` and `extra`. At load it does this over its box:

- Hides every placed mesh, fractured actor, door, ladder, physics actor, emitter and decal whose centre is in the box.
  Each one is hidden as an actor and per component (`SetPrimitiveHidden` for level actors) and loses all collision.
- Doors also lose their interaction points (`XComWorldData.RemoveInteractionPoints`).
- Keeps anything lying wholly within 40 units of the box floor: the ground slabs, rugs and sidewalks.
- Keeps the lights; they may light what step 3 builds.
- Takes the building, floor and cursor volumes in the box out of play by removing their collision. A unit is
  "inside" while it touches a floor volume, so this should also stop the cutaway.
- Rebuilds the tile data over the box at once, before the level start places anything.
- Logs a census of the box before and after: floor, occupied, high-cover and low-cover tiles per level. It also logs
  the ground-level tile rows as text, and checks every 3 s for a minute that nothing it hid came back.

The spec is `tools/patch/examples/exp07hide.json`, `patch_bar` plus one hider over the bar volume: (−467, 627, 320),
half (1392, 784, 320). From the inventory it should hide about 406 actors:

| Kind | Count |
| --- | --- |
| Destructible props | 306 |
| Level actors | 18 |
| Fractured actors | 25 |
| Deco fractured actors | 18 |
| Doors | 7 |
| Ladders | 2 |
| KAssets | 4 |
| Emitters | 19 |
| Decals | 7 |

It should keep 34 flat pieces and take 13 volumes out: the building volume, 8 floor volumes and 4 cursor volumes.

Open questions for the first run:
- Does the bStatic shell really hide? XComDecoFracLevelActor has its own native SetHidden, which our call (to Actor's
  final one) bypasses.
- Do its deco and debris meshes stay?
- Does the tile rebuild drop the walls (pathing, cover, line of sight)?
- Do the old lightmap shadows stay on the ground?
- Does the cutaway stay off?

#### Run 1 (10:20, `look-102035.png`)

The hider ran at load (log 25.66) but hid only **10 actors**: 6 decals and 4 KAssets. It reported 190 actors as kept on
the ground and took all 13 volumes out. The census before and after the rebuild was the same.

| Level (Z) | Floor tiles | Occupied | High cover | Low cover (of 510) |
| --- | --- | --- | --- | --- |
| 31 | 440 | 263 | 122 | 92 |
| 415 (roof) | 300 | 171 | 2 | 88 |

- In game, the bar stood with walls, furniture and bar counter, and worked normally on the ground floor. It had no
  roof, though, and an alien pod stood on the roof's tiles. The camera couldn't rise there, and no soldier could go up
  (F-21).
- The hider skipped the 306 destructible props because it wanted the bStatic or bNoDelete flag, which they don't
  have (F-19).
- It also kept the walls and level meshes as "ground", because `GetComponentsBoundingBox` came back empty for them
  (F-20).
- So the missing roof comes from switching the volumes off, not from hiding.

Fixed for run 2: classes alone decide what is hidden, and the box comes from each component's own bounds. Each actor
kept as ground, and any with no bounds, is now logged.

#### Run 2 (10:26, `look-102604.png`, `look-102701.png`)

The hider hid **413 actors** (log 23.53). It kept 37 on the ground: the floor slabs, sidewalks, rugs, puddles, four
low emitters and one decal. No actor lacked bounds. In game, the bar was gone from view down to its floor.

Two problems were left:
- Units still pathed around the old walls, and those walls still gave cover. The user's notes: "the navigation
  still seems to consider the old wall locations"; "also it still counts as cover".
- Some odd lights were left where a sign used to be: "the blue balls on the left".

| Level (Z) | Floor before → after | Occupied before → after | Cover (high/low) before → after |
| --- | --- | --- | --- |
| 31 (ground) | 440 → 440 | 263 → 263 | 122/92 → 122/92 |
| 95 | 14 → 0 | 217 → 217 | 122/92 → 122/92 |
| 223 | 10 → 0 | 255 → 255 | 10/0 → 0/0 |
| 415 (roof) | 300 → 0 | 171 → 171 | 2/88 → 0/0 |

- Floors are traced, so they followed the collision change. Occupancy and ground-level cover did not (F-22).
- The kept floor still carries the building's baked shadows (F-24).
- The hider also hid emitters of another streamed level, most likely the dropship intro, which sits at the origin
  inside the box (F-23).
- The leftover lights are probably the four kept low emitters; they are now hidden whatever their height.

Run 3 changes:
- only base-map and patch actors count;
- emitters and lens flares never count as ground;
- level and fractured actors leave the cover count (`bAlwaysConsiderForCover` off, `bIgnoreForCover` on);
- fractured actors lose all fragments and their columns are marked destroyed;
- the flags left on each class and a probe line through the old front wall are logged (F-22).

#### Run 3 (10:34, `look-103456.png`): the bar is out of play

The hider hid 407 actors and kept 32 on the ground. The six fewer than run 2 are the other level's emitters, now
left alone (F-23). The user's note: "looks good now, no more cover or invisible walls, and the blue dots are gone too".

| Level (Z) | Floor before → after | Occupied before → after | Cover (high/low) before → after |
| --- | --- | --- | --- |
| 31 (ground) | 440 → 510 | 263 → 0 | 122/92 → 0/4 |
| 95 | 14 → 0 | 217 → 25 | 122/92 → 0/4 |
| 159 | 0 → 0 | 243 → 67 | 124/92 → 0/4 |
| 223 | 10 → 0 | 255 → 33 | 10/0 → 0/0 |
| 287 | 0 → 0 | 306 → 69 | 10/0 → 0/0 |
| 351 | 0 → 0 | 389 → 7 | 12/78 → 0/0 |
| 415 (roof) | 300 → 0 | 171 → 7 | 2/88 → 0/0 |

- The ground rows went from the bar's floor plan to all floor. The 4 low-cover tiles sit on column 9, at the box edge
  next to the street.
- The few occupied tiles left on upper levels are probably things at the box edges: street lights, signs, the
  neighbouring buildings. They're not checked yet.
- Probe line (x −1056, y −120 to 400, z 64): before hiding, all three traces hit `XComDecoFracLevelActor_11` at
  y ≈ 184. After hiding, `Trace` hits nothing, but `XComWorldData.WorldTrace` still hits the hidden piece (F-25).
- After hiding, every class has its own and its components' collision off. Only DecalActor is bStatic: the walls
  (XComDecoFracLevelActor) are not. So the known risk that fixed `bStatic` actors can't be removed did not apply to
  this building.
- No rubble or debris was reported from hiding every wall fragment.

What made occupancy clear (F-22) is not split out yet. Run 3 changed three things together:
- `bAlwaysConsiderForCover` off and `bIgnoreForCover` on;
- every fragment hidden;
- every column marked destroyed.

Step 2 is still to check:
- line of sight and shots across where the walls stood (F-25);
- a save and reload with the bar hidden;
- that LWR's spawns behave: pods, Meld and the landing zone in the cleared area.

Run 3, in-game checks (10:38, `look-103810.png`):
- **Line of sight is still blocked** where the walls stood. The user's note: "yes LOS looks off, I should be able to
  see the drone here I think". This matches the probe's `WorldTrace` still hitting the hidden wall (F-25).
- **A soldier at the old door spot is offered "open door"**, with no door there (F-26).

Run 4 fixes:
- hidden level and fractured actors stop blocking line of sight (`VisibilityBlockingData.bBlockUnitVisibility`
  off);
- doors go to `_Inactive` before the rebuild and lose their interaction points again after it.
- **Save and reload (run 3):** the user saved and reloaded, and "things stayed the same". The bar stayed hidden and
  the area stayed walkable without cover after the load. The hider runs again at load, as the patch loads with the
  map.

#### Run 4 (10:44, `look-104403.png`, `look-104416.png`): step 2 passes

- **Line of sight:** the probe's `WorldTrace` now passes the old front wall, after hiding and after the rebuild, so
  the vision flag was the cause (F-25). In game, soldiers see across the cleared area: a squadsight shot at a
  Sectoid 17 tiles away is offered across it.
- **Doors:** the "open door" action is gone (F-26). The user's note: "looks good now, no more door action and I can
  see through everything normally I think".
- **Census:** the same as run 3.
- **Effects coming back:** five of the bar's emitters, those its floor volumes list, were shown again at 61 s and
  74 s, and the hider hid them again. Its check now runs all mission (F-27).

**Step 2 result: the base map's building can be taken out of play completely**, in looks, pathing, cover, line of
sight, doors and saves, and the hide holds across a save and reload. What stays:
- the ground slabs, with the building's baked shadows on them (F-24);
- the bar's lights;
- LWR's spawns use the cleared area normally: in run 3 an alien stood on the old bar floor (`look-103810.png`).

The recipe, per hidden actor:
- hidden, including at component level;
- all collision off;
- for level and fractured actors, out of the cover count (`bAlwaysConsiderForCover` off, `bIgnoreForCover` on) and
  not blocking vision (`bBlockUnitVisibility` off);
- for fractured actors, every fragment hidden and every column destroyed;
- for doors, `_Inactive` and their interaction points removed.

For the building: its volumes lose their collision. Then the tiles are rebuilt over the box at load.

### Step 3 design (4 November 2026)

The user's wish: a shape unlike the old rectangle, so it stands out as new. An L or a U. Also, clear more of the
parking area and its cars, and put cars back in the space left once the building stands.

The kit allows it. Each of the bar's two blocks is a three-sided shell, open where it meets the other block, and
every wall side is a separate mesh. So any outline made of blocks is a matter of where the copies go, how they're
turned (in 90° steps), and which sides are left out.

Two layouts, both covering the old bar floor (so its baked shadows, F-24, end up indoors) and keeping clear of LWR's
seven landing zones at the map edges (F-06):

- **L (3 blocks):** the old footprint (tiles x 11..37, y 20..33) plus a wing north over the street at x 25..37,
  y 8..19.
- **U (5 blocks):** a wider base (x 5..40, y 20..33) plus wings at x 5..16 and x 29..40, y 8..19. This leaves a
  courtyard about 12 × 12 tiles open to the north.

Landing zones in tiles:

| Edge | Landing zones (tile x, tile y) |
| --- | --- |
| North | (36.5, 2.5), (15.5, 2.5) |
| South | (40.5, 36.5), (7.5, 36.5) |
| West | (1.5, 21.5) |
| East | (49.5, 29.5), (49.5, 4.5) |

Order of work:

1. **Copy piece** (new): a script actor that spawns lit, working copies of placed map pieces, moved and turned
   around a pivot. A whole block, all of whose pieces share one pivot, can be copied in one go.
   - Walls and roofs get a dynamically lit `XComFracLevelActor` subclass, with the source's baked fragment
     columns moved along.
   - Floors and other level meshes get a dynamically lit `XComLevelActor` subclass.
   - Windows and props get `XComMapEdDestructible`.
2. **One-wall test:** one wall module copied onto the cleared ground. Check its lighting, blocking, cover, line of
   sight, and that it breaks when shot.
3. **One block**, then the L. Our own building and floor volumes for the cutaway, and a few lights inside the
   wings, which have none.
4. **Street:** the hider's box (or a second hider) also clears the street and parking strip under the wing(s): its
   cars, vans, lamp posts and dumpsters. The EXP-05 spawner then places real cars (glass, fire and saves already
   work) in the space left, away from the landing zones.
5. The U, if the L works.

Picture: `EXP-07-plan-L-U.png`. It shows the map as shipped next to the L and U plans: the new
building, the cleared boxes, new car slots kept away from the landing zones, and the landing zones. It was drawn
from the inventory by `tools/upk/map_picture.py` with the plans in `tools/upk/plans/urb_bar-L.json` and
`urb_bar-U.json`.

### Step 3a: the one-wall test (built 4 November 2026)

New script classes in `XComMapEd`:

| Class | What it does |
| --- | --- |
| `XComMapEdCopier` | Copies named pieces of the base map, moved and turned as one group around a pivot. |
| `XComMapEdWall` | Copy of a fractured piece, lit dynamically, with the source's fragment columns moved along. |
| `XComMapEdLevelPiece` | Copy of a plain level mesh, lit dynamically. |

Windows and props are copied as `XComMapEdDestructible`. The patch tool's new object type is `copy`.

The test patch is `patch_exp07wall` (`tools/patch/examples/exp07wall.json`): run 4's hider plus one copier. The copier
copies the storefront of the bar's west block onto the cleared ground, turned 90° so the wall runs north-south at
about x −780..−660, y 96..1248. The copied pieces:
- `Core_384FacadeA..D` (`XComDecoFracLevelActor_10..13`);
- the storey slab `Core_384FloorB` (`XComFracLevelActor_17`);
- three `ComKitWindows` (`XComDestructibleActor_158`, `_142`, `_161`);
- the door frame (`_30`).

The door is not copied, so its opening stays empty.

To check in game:
- **Looks:** how the copy is lit, compared with how the original looked.
- **Blocking and cover:** it should block movement and give cover along the wall.
- **Vision:** solid parts should block line of sight; windows and the door gap should be seen through, or not, as
  in the game's own walls.
- **Damage:** shooting or a grenade should break fragments and windows, and opened columns should let units
  through.
- **Not checked yet:** saves.

#### Step 3a, run 1 (11:00, `look-110024.png`, `look-110137.png`)

The copier copied all 9 pieces (log 27.18). The five fractured ones took the source's fragment columns:

| Copy | Source | Fragment columns |
| --- | --- | --- |
| `XComMapEdWall_0` | FacadeA | 39 |
| `XComMapEdWall_1` | FacadeB | 22 |
| `XComMapEdWall_2` | FacadeC | 4 |
| `XComMapEdWall_3` | FacadeD | 4 |
| `XComMapEdWall_4` | FloorB slab | 11 |

The windows and door frame went to their turned places. The copier's tile rebuild finished at 27.37, before the
level start placed anything. Then the hider ran.

In game, the user's notes:
- "walls appears, it shows up as cover and affects pathing as expected";
- "threw a grenade and the walls were destroyed as expected". Fragments broke off and fire took on the floor.
- **Line of sight:** couldn't be judged, because the storefront is "full of windows so can see through as normal".
- **Lighting:** the copy is flat black next to the lit floor and fire (F-28).

Run 2 changes:
- the copied walls take the Dynamic lighting channel too, and log their lighting setup;
- the block's solid back wall (`Core_384BackA`, `XComDecoFracLevelActor_7`) is copied too, for a line-of-sight test.
  It lands along the west edge of the cleared area, at about x −1835, y 85..1259.

#### Step 3a, run 2 (11:06, `look-110627.png`)

All 10 pieces were copied, the solid back wall included (`XComMapEdWall_5`, 39 columns). The user's note: "wallls
still seem to be black and I can see the two aliens in the top right through the wall but I shouldn't be able to
from here".
- **Lighting (F-28):** still black, though the logged lighting setup is as intended: environment enabled and
  dynamic, precomputed shadows off, Dynamic channel on, ticking. The Static channel reads False.
- **Line of sight (F-29):** the solid copy doesn't block vision, though it took the source's intact vision flag (the
  copier ran before the hider) and still blocks movement and gives cover.

Run 3 is a diagnostic:
- the same back wall is copied a second time as a plain mesh (`XComMapEdLevelPiece`), next to the fractured copy;
- a movable point light is spawned near the copies;
- 5 s after load, every copy's flags are logged and probe lines are traced through both back-wall copies.

Reading the results:
- plain copy lit, fractured copy black: the problem is the fractured drawing path;
- both black, but both lit by the test light: the wall materials lack light-environment shaders;
- the probes show whether line of sight sees our copies at all.

#### Step 3a, run 3 (11:11 to 11:14, `look-111143.png`, `look-111343.png`, `look-111449.png`)

The copier made the plain-mesh copy (`XComMapEdLevelPiece_0`, x about −1547) beside the fractured one
(`XComMapEdWall_5`, x about −1835). The user's notes:
- "the wall on the left is lit properly": that is the plain-mesh copy; the fractured copy beside it is still black;
- "new wall correctly blocks LOS, can see aliens to top left but not the ones on the right" (`look-111343.png`, the
  soldier in cover behind the lit plain copy).

The log (5 s after load):
- every copy is world geometry, collides and blocks; the walls block vision (the windows and door frame don't);
- the probe lines hit both back-wall copies in all three traces: `XComMapEdWall_5` at x −1836 (line), −1860 (box),
  −1832 (`WorldTrace`); `XComMapEdLevelPiece_0` at −1548, −1572, −1544;
- "could not spawn the test light": `PointLightMovable`, like every `Light`, is `bNoDelete`, and `Spawn` refuses
  those.

So:
- **Lighting (F-28):** the mesh and its materials light correctly when drawn as a plain static mesh with a light
  environment. The black comes from the fractured component's drawing path.
- **Line of sight (F-29):** verified for the plain copy. The fractured copy blocks all three traces too, so run 2's
  sighting most likely went past the wall's end or through the storefront copy's windows.

What the game's own code shows (decompiled from a copy of `Engine.upk`):
- the game's `FracturedStaticMeshActor` never gives its fractured component a light environment. Its
  `LightEnvironment0` is off, and the placed walls draw only with their baked lightmaps;
- the game's fractured component has Firaxis-only settings: vertex-colour destruction
  (`bUseVertexColorDestruction`, `bRequiresVertexColorInit`), destroyed materials (`DestroyedMaterials`, six on the
  source wall), and cutout masks (`bCutoutMask` on the source wall).

Run 4 is one more diagnostic. Five copies of the back wall stand about 3 tiles apart on the cleared ground, west to
east, each running north-south over y about 85..1259:

| # | x | Copy | What it tests |
| --- | --- | --- | --- |
| 1 | −1835 | `XComMapEdWall` with its own light environment, plus a test point light (`XComMapEdLight`, radius 320) at (−1900, 300, 150), by its north end | whether a fresh light environment is enough; whether the fractured copy takes dynamic light at all |
| 2 | −1547 | `XComMapEdLevelPiece`, as in run 3 | the lit reference |
| 3 | −1259 | `XComMapEdWall` without environment shadowing | whether the wall's own collision shadows its light environment |
| 4 | −971 | `XComMapEdWallStaticIB` (static index buffer) | whether the dynamic index buffer path is what draws it black |
| 5 | −683 | `XComMapEdWall` with the lit overlay | the fallback: a plain lit mesh is drawn while the wall is whole; at the first damage the fractured mesh is shown instead |

The copier logs the lighting setup of every copy, the plain one included. `XComMapEdLight` is a plain `Actor` with a
point light component, so it can be spawned.

#### Step 3a, run 4 (11:31 to 11:33, `look-113151.png`, `look-113216.png`, `look-113343.png`)

All five copies were made, and the test light spawned at (−1900, 300, 150) (`XComMapEdLight_0`). Every copy's
lighting setup logs the same: its environment enabled and dynamic, precomputed shadows off, Dynamic channel on,
Static channel off. Wall 5's fractured mesh logs hidden, with its overlay shown.

The user's notes:
- "all walls appear lit now": the four fractured variants as well as the plain copy. **The fix for F-28 is the wall's
  own light environment** (`MyLightEnvironment`, added to `Components`), made like `XComMapEdLevelPiece`'s. The
  inherited `LightEnvironment0` left the fractured copy black, though it logged as enabled and dynamic. Environment
  shadowing and the index buffer made no difference.
- "my guy is able to see through the first one, and is leaning as if there was a gap where he is". The cursor
  readout puts the soldier at tile (21,23), against wall 5's west face (the overlay variant).
- "it's only specifically this tile that allows LOS through the wall, the one my cursor is on does not": from (21,22)
  next to it, the wall blocks.
- The user could not check the other walls: no aliens were near enough.

Tile (21,23) is the 4th row from the wall's north end. In the source wall (`XComDecoFracLevelActor_7`, which runs
east-west along y 1248 on the bar's south side) that point is at about x −1392, tile 14.

Run 5 keeps the five walls and adds logging, so the tile data can be read without aliens nearby:
- every wall copy logs its 39 fragment columns: box, fragments, and the source's destructible and fractured-actor
  links (kept or dropped);
- 5 s after load, for every tile row each wall crosses, the copier logs four tiles (two either side): cover flags
  and occupancy; whether the game counts the two tiles touching the wall as seeing each other
  (`IsAdjacentTileVisible`); and `WorldTrace` across the wall at 80 and 160 units.

#### Step 3a, run 5 (11:41 to 11:43, `look-114112.png`, `look-114300.png`)

The user's notes: "can still see through wall at this point" (the soldier again at tile (21,23) by wall 5, taking a
squadsight shot through it), and "from this positions i should only see 2 aliens but I can see thr drone too"
(cursor at (18,24), by wall 4).

The tile log (5 s after load; level 1, z 64..128, the level a standing unit's tile is in; line of sight is worked out
there) gives, for each wall, the rows where the game counts the two tiles touching the wall as seeing each other
(`IsAdjacentTileVisible` true), leaving out both ends and row 31, where the mesh has an opening (the trace passes
there too):

| Wall | See-through rows | `WorldTrace` across those rows |
| --- | --- | --- |
| 1 (fractured, x −1824) | all, 21 to 30 and 32 | hits the wall |
| 2 (plain mesh, x −1536) | none | hits the wall |
| 3 (fractured, x −1248) | 28 to 30 | hits the wall |
| 4 (static index buffer, x −960) | 23, 24 | hits the wall |
| 5 (overlay, x −672) | 23, 25 | hits the wall |

Both of the user's spots, (21,23) and (18,24), are on see-through rows. So the log predicts them, and in-game
checks for this aren't needed any more.

- A row sees through exactly where level 1 has no occupied tile at the wall; occupancy and line of sight go
  together.
- At ground level (level 0) every wall is occupied along its whole length, wall 1 included. Across the hidden area,
  the copies add 136 occupied tiles at level 0 (0 without them, step 2 run 4), but only 72 at level 1 (25 without
  them, 97 with).
- The 39 fragment columns are the same on every copy, shifted to its place: 13 along the wall by 3 high
  (z −1..191, 191..383, 383..575). The source's destructible and fractured-actor links are all dropped. So the copies
  don't differ in their own data.
- What differs is the ground under them. Checked against the inventory, a level-1 tile by a wall is occupied almost
  exactly where a base-map piece of the hidden bar stood at that height (a facade wall, a window, a door frame):
  wall 1 0 of 24, wall 2 17 of 18, wall 3 13 of 15, wall 4 15 of 16, wall 5 15 of 16. Wall 1 stands where nothing
  was, and is see-through along its whole length. The plain copy only looked solid in run 3 because it stands over
  an old wall of the bar.
- Step 2 run 1 rebuilt tiles over the intact bar and the census didn't change. So a runtime rebuild keeps walls the
  map was baked with.

Reading: above the ground, a runtime tile rebuild re-checks only tiles where the baked data had something. A tile
that was empty stays empty, whatever is placed there now. At ground level every tile has the floor, so it is always
re-checked.

Run 6 tests the game's full build: the hider calls `XComWorldData.BuildWorldData` over the level volume once after
hiding, before its usual rebuild, and logs the census before and after. The five walls and the tile log stay.

#### Step 3a, run 6 (11:51): the full world data build crashes the game

The hider hid the bar, logged the census and called `XComWorldData.BuildWorldData(XComLevelVolume_4)` at 32.24. At
35.87 the game stopped with "Critical error: Fatal error!" (`unreal-v8917-2026.11.04-11.51.45.dmp`). So the full build
can't be run in the game; `bFullWorldBuild` is off again.

Run 7, tile tests compared with run 5's results at the same spots. The game's wall and level-piece classes set the
Firaxis-only `Actor.bStaticCollision`, and its destructibles (such as the cars) don't. So the guess is that a rebuild
skips "static collision" actors on tiles where the baked data had none. `XComMapEdWallNoStatic` turns the flag off.
The flag is declared in the `XComFracLevelActor` stub only so the defaults can be set; script never touches it.

| # | Run 5 see-through rows | Run 7 copy |
| --- | --- | --- |
| 1 | all | `XComMapEdWallNoStatic` (the test light is dropped) |
| 2 | none (plain mesh over an old wall) | unchanged |
| 3 | 28–30 | `XComMapEdWall`, not world geometry (`bWorldGeometry` false) |
| 4 | 23–24 | `XComMapEdWallNoStatic`, not world geometry |
| 5 | 23, 25 | unchanged (does run 5's pattern repeat?) |

Compiling also showed why `LightEnvironment0` left the walls black (F-28): the stub's
`Components(0)=…LightEnvironment0` doesn't resolve ("unresolved reference … Invalid property value in defaults"). So
in our classes the inherited light environment was never in `Components` and never attached.

#### Step 3a, run 7 (11:58): the actor flags make no difference

No crash. Every wall's tile log matched run 5 row for row: wall 1 (`bStaticCollision` off) is still see-through on
every row; wall 3 (`bWorldGeometry` false, logged) on rows 28–30; wall 4 (both) on 23–24; wall 5 on 23 and 25; the
plain copy on none. The census is the same too. So the pattern repeats exactly, and what decides it is the map's
baked per-tile data, not the copies' flags.

Run 8 asks the tile data directly. The tile log adds each tile's visibility-map index and the world's tile counts,
to show whether the hole tiles are stored at all. Wall 1 also tests writing to its tiles: before the rebuild, every
tile it crosses above the ground is marked as water (`XComWorldData.SetIsWaterTile`), so it is no longer empty. 5 s
after load, once logged, the marks are cleared, the tiles are rebuilt again, and they are logged once more 5 s later.
Walls 3 and 4 are back to run 5's classes.

#### Step 3a, run 8 (12:02): the tiles are all stored, and marking them changes nothing

- The world data stores every tile: 52 × 39 × 12 = 24,336, `NumTiles` 24,336. A tile's visibility-map index is its
  plain grid index (x + 52y + 2028z; for example (9,19,1) is 3025), on hole rows as on solid ones.
- `SetIsWaterTile` marked all 168 tiles wall 1 crosses above the ground (each call returned true). Wall 1 stayed
  see-through on every row, both with the marks on and after clearing them and rebuilding.

So the rebuild doesn't skip tiles by anything stored per tile that script can set. The guess for run 9: a rebuild only
goes up each x,y column as far as the baked geometry reached. A column that held only floor is re-checked at level 0
alone, which fits every run so far. The world data has a script-visible `UpdateBuildHeightTiles` switch that no
script uses. Run 9 sets it before the first copier's rebuild, and logs it 5 s later along with `NumRebuilds`.

#### Step 3a, run 9 (12:06): the build-height switch is read but changes nothing

The first copier set `UpdateBuildHeightTiles` (it was False). 5 s later it read False again, so native code took it.
The see-through rows were the same as in runs 5 and 7 on every wall: wall 1 all, walls 3, 4 and 5 their own rows,
the plain copy none.

Run 10 tries another kind of object. Two destructible props of the map are copied onto tiles beside wall 1 that were
empty in the baked data (levels 1 and 2): a moving-van side panel (`XComDestructibleActor_97`, `MovingVanWallF`, 16 ×
206, 214 high) along the tile 8/9 edge over rows 23–25, and a diner oven (`XComDestructibleActor_51`, 96 × 70, 161
high) on tile (8,22). The copier logs their tiles: the panel as a wall (`IsAdjacentTileVisible` across it), and both
tile by tile from level 1 up. Wall 1 is a plain `XComMapEdWall` again.

#### Step 3a, run 10 (12:10): a destructible panel doesn't register either

The van side panel copy (`XComMapEdDestructible_0`) stands along the tile 8/9 edge over rows 23–25, box z 32..248,
and `WorldTrace` hits it at 80 and 160 units. Yet no tile under it is occupied at levels 1 to 3, and
`IsAdjacentTileVisible` across it is true on all three rows. Wall 1 is unchanged (see-through on every row). The
oven's lines hadn't been written yet when the log was read (the game was still running).

So walls, plain meshes and destructible props all behave the same. Geometry added at run time doesn't register
above the ground on tiles that were empty in the map's baked world data; the actor's class and flags don't matter.

Once the log was flushed, the oven (`XComMapEdDestructible_1`, box z 15..179 over tile (8,22)) showed the same: tiles
(8,22) and (9,22) are empty at levels 1 and 2.

#### The cause, from the game's native code (4 November 2026)

`research/native-code-notes.md` has the details. In short: `RebuildTileDataExtents` queues a tile for rebuilding only
if the map's baked static flags for it already have one of the low 12 bits set. Tiles that were empty when the map was
built are never re-checked, so geometry added at run time doesn't block on them, whatever its class. At ground level
every tile has floor flags, which is why the copies give cover and block movement there. No native that script can
call sets those bits (`SetIsWaterTile` uses bit 27; the unit-blocking natives use a separate dynamic store).

Next: seed those bits in the map's baked world data, in a lab copy of `URB_Bar.upk`, on the tiles the new pieces
cross, and let the game's rebuild do the rest.

#### Step 3a, run 11 (built 12:30): the map's baked tile data seeded

`tools/upk/seed_tiles.py` decoded `URB_Bar.upk`'s static tile store and wrote a copy with seed bit `0x1` on 235 tiles
whose low 12 bits were 0: wall 1's line (x 9–10, y 20–33, levels 1–8), the van panel's (x 8–9, y 23–25, levels 1–3)
and the oven's (x 8–9, y 22, levels 1–2). The decoded store matches the run logs tile for tile. The seeded package
(16,965,012 bytes; the container chunk 170,579 → 380,326 compressed) decodes back to exactly the intended bytes.

It replaced `URB_Bar.upk` in the lab copy at 12:30. The original is at
`<lab>\re\worlddata\URB_Bar.upk.lab-original`, logged in `<lab>\re\worlddata\DEPLOYED.txt`. The patch is
run 10's.

Expected: wall 1 blocks on every row (`IsAdjacentTileVisible` false on rows 21–30 and 32), and the panel's and the
oven's tiles are occupied above the ground. Walls 3–5 keep their run 5 holes as the control.

#### Step 3a, run 11 (12:33, `look-123329.png`): seeding works

The game loaded the seeded `URB_Bar.upk` normally. The user's note: "looks promising!". The tile log:

| Copy | See-through rows (whole span, ends included) | Run 5 / run 10 |
| --- | --- | --- |
| Wall 1 (seeded) | 19, 20, 31, 33, 34: its ends and the mesh's opening at row 31 | every row |
| Wall 2 (level-piece copy, not seeded; its tiles already had baked bits) | 19, 20, 31, 33, 34 | the same |
| Wall 3 (not seeded) | adds 28–30 | 28–30 |
| Wall 4 (not seeded) | adds 23–24 | 23–24 |
| Wall 5 (not seeded) | adds 23, 25 | 23, 25 |
| Van panel (seeded) | 26 only, just past its end; occupied at levels 1–3 on rows 23–25 | none occupied |
| Oven (seeded) | occupied at levels 1–2; (8,22) fully occupied at level 1 | none occupied |

The level-1 census in the hidden area went from 97 to 124 occupied tiles.

So seeding the baked static flags on the tiles a new piece crosses makes the game's own rebuild register it above
the ground, whatever kind of piece it is. A copy on seeded tiles now blocks exactly like wall 2, whose tiles the bake had
already marked. The seed covered x 8–10, y 20–33, z 1–8 (235 tiles; manifest
`<lab>\re\worlddata\URB_Bar-seeded.upk.seeded.txt`). F-29 is fixed for seeded tiles.

To do: make seeding part of the patch workflow. Compute the tiles each copy or spawn crosses, from level 1 up, and
seed them in a lab copy of the map along with the patch. The lab copy now has a modified `URB_Bar.upk`; restore it
from `<lab>\re\worlddata\URB_Bar.upk.lab-original` with the rest of the lab clean-up.

#### Step 3a, run 12 (built 12:52): patchtool seeds every copy

The same patch as runs 10 and 11, with `map.name` `URB_Bar` in the spec, so patchtool now does the seeding itself
(`tools/patch/README.md`, "Tile seeds"):
- the plan has 7 boxes and 859 tiles: each wall's two tile columns over rows 20–33, levels 1–6, plus the panel
  (x 8–9, rows 23–25, levels 1–3) and the oven (x 7–9, rows 21–23, levels 1–2);
- 372 of them were empty and got seeded; the other 487 already had baked bits, mostly under walls 2–5, where the
  bar stood;
- `XComMapEdTileSeeds_908`, last in the patch, rebuilds the 7 boxes at load.

The lab's `URB_Bar.upk` is now patchtool's seeded copy (ledger `<lab>\patchtool\seeded.txt`). The hand-seeded
run 11 copy is gone, and the original is kept in `<lab>\patchtool\maps`. Expected: walls 3, 4 and 5 now block on
every solid row too, like wall 1 in run 11.

#### Step 3a, run 12 (12:54, `look-125423.png`): automatic seeding works

`XComMapEdTileSeeds_908` rebuilt its 7 boxes at load (log 23.13), along with the copiers' own rebuilds. The tile log:
all five walls are now see-through only at their ends and the mesh's opening (rows 19, 20, 31, 33, 34), and the van
panel only at row 26, just past its end. In run 11, the unseeded walls 3–5 still had holes at rows 28–30, 23–24
and 23/25.

The user stood a soldier between two walls, with aliens beyond them to the top left. The note: "confirmed LOS blocking
looks normal, aliens are on top left and I can't see them from here".

**Step 3a result:** a copied wall is lit (F-28) and blocks movement, cover and line of sight like the map's own (F-29),
once patchtool seeds its tiles. Damage and saves of copied walls are still to check, in the block test.

### Step 3b: the one-block test (built 4 November 2026, 13:06)

Spec `tools/patch/examples/exp07block.json`, patch `patch_exp07block`, streamed in place of `patch_exp07wall`. The bar
is hidden as before, and the bar's west block (12 × 12 tiles) is rebuilt where the east block stood, centred at
(192, 672) and turned 90°:

| Part | Pieces | How |
| --- | --- | --- |
| Walls | back A–C, front A–D, west end wall, two inner walls (`XComDecoFracLevelActor_7..13, _15..17`) | copied |
| Floors | ground slab `XComLevelActor_91`, upper slab strip `XComFracLevelActor_17`, ceiling beams `XComLevelActor_4` | copied |
| Roof | roof floor and parapets (`XComFracLevelActor_3, _4, _6, _18, _202, _203`) | copied |
| Windows, door frames | `XComDestructibleActor_158, _161, _142`; `_60, _31, _65, _30, _502` | copied |
| Doors | `XComInteractiveLevelActor_26, _6, _5, _7, _4` | **moved** |
| Ladder to the roof | `XComLadder_3` | **moved** |
| Closing wall | the end wall, its parapet and door frame again, turned 270°, on the side that joined the east block | copied |

New this step:
- **Doors and ladders are moved, not copied.** `XComLevelActor` (and so `XComLadder`) and the destructibles are
  neither static nor fixed in place, so the copier moves the map's own actor. It keeps its name, so saves should find
  it (F-15). A door's interaction points at its old place are removed first; the tile rebuild should add them at the
  new place (its "interactions" step). Moved pieces are tagged `XComMapEdMoved`, and the hider leaves them alone.
- **A building of its own.** patchtool writes an `XComBuildingVolume` and four `XComFloorVolume`s, the west block's
  floor volumes `_15` and `_17` (floor 1), `_16` (floor 2) and `_7` (roof) moved and turned like the copies. The
  copier then calls the game's `CacheBuildingVolumeInChildrenFloorVolumes`, `CacheFloorCenterAndExtent` and
  `RebuildCachedActors` on it at load and again 5 s later. It logs each floor's cached actors, and how the base map's
  own baked caches hold the source pieces, to compare.
- **The cursor volumes stay.** In URB_Bar, `XComCursorVolume_1..3` span the whole map, one per storey. Run 1 took them
  out with the bar's volumes, which is the likely cause of F-21 (the cursor couldn't go up a level). The hider now keeps
  cursor volumes unless `bHideCursorVolumes`, and never touches a patch's own volumes.
- Seeds: 30 boxes, 1,014 tiles planned, of which 321 were empty and got seeded.

To check in game:
- **Looks:** the block lit inside and out, roof on, windows and frames in place.
- **Doors:** a soldier walks through each, and it opens; no "open door" left where the bar's doors were.
- **Ladder:** a soldier climbs to the roof and walks on it; the cursor can go up to the roof level.
- **Cutaway:** with a soldier inside, the roof and upper floor cut away as in the game's own buildings.
- **Walls and windows:** cover along the walls, line of sight blocked by walls, through windows as the game does.
- **Damage**, if there is time: a grenade against a wall or window.

#### Step 3b, run 13 (13:11 to 13:12, `look-131115.png`, `look-131217.png`)

The user's notes: "door worked normally, but the ladder cuts out when on a lower zoom, it appears when zooming out but
I can't move a soldier up over this one. also the roof doesn't cut out"; on the other side, "on this side there's no
ladder but I can actually go up. also door is missing and there's a gap in the wall".

- **Moved doors work.** Each of the five has its 6 interaction points (`XGDOOR_Inside01..03`, `Outside01..03`) at
  the new place, and none at the old one. In game, the door opened normally.
- **The moved ladder can't be climbed** (F-30). The map's baked world data holds each ladder as two neighbour links
  between its bottom and top tiles, with the ladder actor as the path object. For `XComLadder_3`, (11, 23, 0) → (12, 23, 6),
  traversal types climb ladder and landing, positions (−1696, 336, 24) and (−1604, 336, 402), and the reverse. The
  runtime rebuild keeps those links where they were baked and makes none for a ladder in a new place. So the hidden
  bar's other ladder (`XComLadder_4`, at (432, 1296), the north side) can still be climbed, unseen, and the moved one
  can't.
- **It also cuts out with the camera:** the bar's baked floor caches still hold it (floor 0, cutdown floor 2).
- **The roof doesn't cut away** (F-31). `RebuildCachedActors` on the patch's building found 1 actor per floor at load
  and none 5 s later, never our copies. The baked caches of the bar show where each source piece belongs: the walls
  on floor 0 with cutdown floor 2, the floor slab and doors on floor 0 with cutdown floor 0, front D with cutdown 1.
- The missing door and the gap are the closing wall's: the block's five doors were all used, and the back return at
  that corner (`XComDecoFracLevelActor_8`, turned 270°) wasn't copied.

#### Step 3b, run 14 (built 13:18): floor caches from the bar's, and the corner

- The copier no longer calls `RebuildCachedActors`. It gives each copy its source's entry from the bar's baked floor
  caches (the same floor index and cutdown floor) in the new building. Moved pieces (the doors and the ladder) leave
  the bar's caches, so the hidden bar's cutaway no longer hides the ladder.
- The closing copy joins the same building (`inBuilding`) and adds the back return `XComDecoFracLevelActor_8` at its
  corner. Its doorway stays open, with a frame: the block's five single doors are all moved already, and the east
  block's only door is a double one.
- The ladder still can't be climbed: its baked links are being decoded (F-30).

#### Step 3b, run 15 (deployed 13:35): the ladder's and doors' baked links move with them

The world data container is now fully decoded (`research/native-code-notes.md`, "The rest of the container: pathing
links"): 9 chunked stores. The floor store holds each floor tile's links, 14,584 in URB_Bar, and 48 of them have a
path object (doors, low walls, the two ladders). `tools/upk/world_links.py` lists them and moves one path object's
links like a copy, keeping the container's size.

patchtool now moves the baked links of every piece a copier moves (doors and ladders, by class, from the inventory).
This happens at deploy, after seeding (`seed-links.tsv`). In run 15 that's the five doors' links (KickDoor, Landing)
and `XComLadder_3`'s, now (34, 20, 0) ↔ (34, 21, 6) through (528, 32, 24) and (528, 124, 402). Run 15 also has run 14's
cache and corner fixes; run 14 was never played.

To check: the ladder can be climbed to the roof, the doors still open (and can be kicked), and the roof cuts away
with a soldier inside. Still there: the hidden bar's other ladder (`XComLadder_4`) keeps its links on the north side.
A later fix should drop the links of pieces the hider hides.

#### Step 3b, run 15 (13:53): no change for the ladder or the roof

The user's note: "no change, new ladder still unclimbale, roof still doesn't cut away. doors work normally. corner gap
is filled but there's an odd lighting mis match between the corner wall bit and the rest of the wall on that side".
- The ladder's links were in the lab map at the new tiles, (34, 20, 0) ↔ (34, 21, 6), and the ladder still can't be
  climbed. So moving baked links isn't enough: most likely the rebuild replaces them, as the agent read in the code.
  But the hidden bar ladder's links survive a rebuild in the same kind of tile, so something re-creates those, from
  the ladder's place at load or another table (F-30, open).
- The new building's floors held all 37 cached entries (25, 1 and 7 for the main copy; 4 more for the closing one),
  each with its source's floor and cutdown floor, and the roof still didn't cut away (F-31, open).
- Being inside comes from touch: a pawn that touches an `XComFloorVolume` adds it to its `IndoorInfo`, whose building
  is the volume's `CachedBuildingVolume` (`XComPawnIndoorOutdoorInfo.ParentTouchedOrUntouched`, decompiled). The
  baked floor tiles also hold a floor volume each: under the new block they still name the bar's `XComFloorVolume_12`
  (ground) and `_11` (roof), which the hider took out.
- The corner return is lit differently from the end wall beside it (F-32).

#### Step 3b, run 16 (deployed 13:59): diagnostic

The same patch, with two probes in the main copier:
- A* paths (`XComWorldData.GetAStarPath`) from each ladder's bottom to its top, at load and 5 s later: the moved
  `XComLadder_3` from (528, 0, 16) to (528, 150, 410), and the hidden `XComLadder_4` from (432, 1330, 16) to
  (432, 1200, 410). A short path means the climb link is there.
- Every pawn's and the cursor's building and floor volumes whenever they change (every 2 s, all mission), and at 5 s
  what touches each of the new building's floor volumes.

What the user does: walk a soldier into the new block and out again, move the cursor over the block and up a level,
and preview a move to the roof by the moved ladder and by the north side.

#### Step 3b, run 16 (14:02, `look-140242.png`): the rebuild wipes the moved ladder's link

The user's note: "the roof is also missing the top bit where the wall gap was".
- **The moved ladder's link is there at load and gone 5 s later.** The A* path from (528, 0, 16) to (528, 150, 410)
  is 1 tile, (34, 21, 6), at load: a direct climb over the moved link. 5 s later, after the tile rebuild, there is no
  path (0 tiles). The hidden `XComLadder_4`'s path is 1 tile both times. So the rebuild does replace the links of the
  tiles it processes, and it re-makes a ladder's links only where the ladder stood when the map loaded (F-30).
- **Soldiers and the cursor register inside the new building.** As they move, their building is
  `XComBuildingVolume_9000` and their floor volumes are `_9001` (ground), `_9003` (upper floor) or `_9004` (roof).
  The moved doors and the ladder touch the floor volumes too. So the indoor state is right, and the missing cutaway
  (F-31) comes later: the level's list of buildings or the native visibility code. Whether the roof cut away in this
  run wasn't noted.
- The roof parapet above the corner return was missing: `XComFracLevelActor_202`, the trim over
  `XComDecoFracLevelActor_8`, which the closing copy didn't include.

#### Step 3b, run 17 (deployed 14:12): the ladder baked into the map

- **New tool:** `tools/upk/bake_actor.py` changes actors' saved Location and Rotation in a copy of a map package.
  - The property sizes stay the same, so no offset in the package moves.
  - Only the changed 128 KB blocks are re-encoded, as literal LZO blocks; later chunks move along and the chunk
    table follows.
  - The result is decoded again and compared byte for byte.
- **patchtool `bake` objects** run it at deploy, after seeding, and move the actor's baked links with it (pivot its
  old place, turned by the change in yaw). A bake can `join` a copy object. That copier then treats the actor as
  already moved (`PrePlaced`): it is tagged, joins the building's caches, and is not moved again.
- **The block's ladder is now the bar's other ladder.** `XComLadder_3` was saved without a Rotation, so its yaw
  can't be changed in place.
  - `XComLadder_4` (yaw −90) is baked at (528, 48, 16) with yaw 90, the same place and facing as run 16's moved
    `XComLadder_3`. Its links move to (34, 20, 0) ↔ (34, 21, 6).
  - `XComLadder_3` goes to z −4000, under the map. Its old links stay at the bar's west end for now, hidden and
    unused.
- The closing copy adds `XComFracLevelActor_202`, the missing parapet piece.
- The path probes stay as in run 16: the new place, (528, 0, 16) → (528, 150, 410), and `XComLadder_4`'s old place,
  which should now give no climb.

To check:
- a soldier can climb the new ladder to the roof;
- the north side of the old bar can no longer be climbed;
- the parapet is whole at the corner;
- with a soldier inside, whether the roof cuts away.

#### Step 3b, run 17 (14:17 and 14:18, `look-141732.png`, `look-141800.png`): the pathing ladders are patch_bar's

The user's notes: "roof should cut away at this point, still doesn't. also ladder on this side still unclimbale"
(a soldier at the block's door); "this side still climable. roof edge is complete" (the north side of the old bar).
- **The parapet is whole.**
- **The baked ladder still can't be climbed.** `XComLadder_4` stood at (528, 48, 16), yaw 90, from load. Its moved
  links gave a 1-tile climb at load and no path 5 s later, as in run 16. So a base-map ladder that stands in its new
  place from load doesn't get links from the rebuild either.
- **The north side is climbed through a ladder of the patch's own.** At 5 s the north probe climbs straight from
  (33, 33, 0) to (33, 32, 6), where `XComLadder_4` no longer stands. The patch is built on the shipped `patch_bar`,
  and `patch_bar` holds two hidden ladders of its own beside the bar's two visible ones:
  - `XComLadder_15` at (436, 1276, 14), yaw −90, beside `XComLadder_4` at (432, 1296, 16);
  - `XComLadder_11` at (−1656, 336, 20), yaw 0, beside `XComLadder_3` at (−1680, 336, 16).
  The hider hides both (the log says so each run). The rebuild makes climb links for these, and the base map's
  ladders only draw. That explains run 13 too: the north side stayed climbable because `XComLadder_15` never moved.
- Not separated yet: the rebuild may take the patch level's ladders, or ladders tagged `XComLadder` (the copier
  re-tags the pieces it moves `XComMapEdMoved`, the visible ladder included).
- **The roof still doesn't cut away** with a soldier at the door (F-31).

#### Step 3b, run 18 (deployed 14:24): a pathing ladder in the patch

- New patchtool object type `ladder`: an `XComLadder` placed in the patch, written as `patch_bar` writes
  `XComLadder_15` (hidden by default, tag `XComLadder`). Its tiles are seeded, and hiders keep it (until run 20).
- `XComLadder_905`, hidden, at (524, 68, 14), yaw 90: `XComLadder_15` moved and turned the way `XComLadder_4` was.
  The visible `XComLadder_4` stays baked at (528, 48, 16).
- Unchanged: `patch_bar`'s `XComLadder_15` and `_11` still stand at the old bar, so its north side stays climbable.
  Taking them out of the patch, or moving them, comes once the new ladder works.

To check: a soldier can climb the block's ladder to the roof.

#### Step 3b, run 18 (14:28, `look-142759.png`): no climb from the patch's ladder; a door kicked twice

The user's note: "still no climbable ladder, no roof cutout and I noticed something odd: when I sent a soldier
through the door, he did his door kick animation twice".
- The patch's hidden `XComLadder_905` touched the new building's upper floor volumes but got no climb: no path from
  (528, 0, 16) to the roof after the rebuild, as before. So neither the patch level nor the `XComLadder` tag is
  enough.
- The A* probe can't tell a ladder climb from an alien one. The baked data also holds JumpUp and WallClimb links
  (no path object) along walls, for example (34, 33, 0) → (34, 32, 6) on the north side, which the probe used at
  load. So the probes only show whether the top tile can be reached at all.
- The double kick was at the moved door `XComInteractiveLevelActor_4` (south wall). Since run 15, deploy moved each
  moved door's baked KickDoor links along, and the rebuild makes kick links from the door's new interaction points
  as well. In run 13, with the rebuild's links alone, the door "worked normally" (F-33).
- The hidden bar's double door (`XComInteractiveLevelActor_0`, `_1`) still has baked KickDoor links at
  (33, 21, 0) ↔ (34, 21, 0) and (33, 22, 0) ↔ (34, 22, 0), inside the new block's ground floor.

#### Step 3b, run 19 (deployed 14:33): doors, and probes for the ladder

- Moved doors no longer take their baked links along; ladders still do.
- The hider removes the interaction points of every door it hides, so the rebuild makes no kick links for them.
- New probes in the main copier, at load and 5 s later:
  - the floor tile and floor height at the new ladder's foot and top, the roof's centre, the north side's foot and
    top, and the old west ladder's top (`FloorProbes`);
  - every `XComLadder` in the world: its level, place, height, tag and flags (`bLogLadders`);
  - A* from the roof's centre to the new ladder's top, and from the ground to the roof's centre.
- Running alongside: a read of the native rebuild code for how it makes ladder links (which ladders, which
  conditions).

To check: a soldier goes through each moved door with one kick.

#### Step 3b, run 19 (14:36): one kick per door; the ladder's top tile loses its floor

The user's note: "tried kicking door, only happened once like it should". F-33 is fixed.

The floor probes, at load and 5 s later (after the rebuild):

| Point | Tile | At load | After the rebuild |
| --- | --- | --- | --- |
| new ladder's foot (528, 32, 24) | (34, 20, 0) | floor, z 16 | floor, z 16 |
| new ladder's top (528, 144, 410) | (34, 21, 6) | floor, z 402 | **no floor** |
| roof centre (192, 672, 410) | (31, 27, 6) | floor, z 402 | floor, z 396.9 |
| north foot (432, 1312, 24) | (33, 33, 0) | floor | floor |
| north top (432, 1200, 410) | (33, 32, 6) | floor, z 402 | floor, z 396.9 |
| old west top (−1584, 336, 410) | (12, 23, 6) | floor | no floor (the bar is hidden) |

- A ladder can't get a climb without a floor at its top, and the new ladder's top tile loses its floor in the rebuild.
  A* from the roof centre to it finds no path after the rebuild.
- The pieces over the two top tiles are the same: the wall and parapet edges cross each by about 12 units (the main
  copy's on the south side, the closing copy's on the north). The difference is the ladder: `XComLadder_905` reaches
  20 units into its top tile (y 86..116 against the tile's 96..192) and keeps its collision, being kept from the
  hider. `XComLadder_15` reaches into its own top tile the same way, but the hider takes its collision off before
  the rebuild.
- The ladder census: all five ladders are in the persistent level once streamed. After the rebuild, `XComLadder_15`
  and `_11` are hidden with no collision and `bAlwaysConsiderForCover` off (the hider's doing); `XComLadder_905` is
  hidden with collision on; the visible `XComLadder_4` (tag `XComMapEdMoved`) collides. All have height 476.9 and
  type Ladder.
- From the ground, A* to the roof centre goes west along the wall to x 24 and climbs to (25, 22, 6), a row inside the
  edge. So other edge tiles may have lost their floor as well; run 20 probes three more.

#### Step 3b, run 20 (deployed 14:39): the patch's ladder without collision

- Hiders no longer keep the patch's own ladders: `XComLadder_905` is hidden the way `XComLadder_15` is (no collision,
  not considered for cover) before the rebuild.
- More floor probes on the south edge row: (432, 144), (624, 144), (144, 144) at the roof's height, and one row in,
  (528, 240).

To check: a soldier can climb the block's ladder to the roof.

#### Step 3b, run 20 (14:43): the whole south edge of the roof has no floor; a door kicked twice again

The user's note: "in run 20 the double door kick happened again. ladder was still unclimbable".
- After the rebuild the south edge row of the roof has no floor anywhere probed: (30, 21, 6), (33, 21, 6),
  (34, 21, 6) and (35, 21, 6). One row in, (34, 22, 6), has floor. So the patch ladder's collision wasn't the cause.
- The roof's floor after the rebuild is at z 396.9 everywhere, the top of the copied ceiling beams
  (`XComLevelActor_4`), not z 402, the roof slab's top as baked. The beams run from y 154 to 1222 in the new block:
  they cover the north edge row's centre (y 1200) and miss the south edge row's (y 144).
- Cause: the copied roof slab (`XComFracLevelActor_3`, an `XComMapEdWall`) isn't taken as floor. `XComFracLevelActor`
  and `XComDestructibleActor` default `bPathColliding` (and the frac class `bCanStepUpOn`) to false; the editor saved
  both as true on the bar's slab, and the copier didn't copy them. `XComLevelActor` defaults `bPathColliding` to
  true, so the beams' copy counts.
- The native code agrees: the rebuild links a ladder whenever its foot and top tiles have a floor and checks nothing
  else about it (`research/native-code-notes.md`, "How ladder links are made").
- The double kick: run 20 changed nothing about doors, so it depends on the route. The hidden double door
  (`XComInteractiveLevelActor_0`, `_1`) stands at (480, 144) and (480, 240), inside the new block's south wall. The
  rebuild gives a door kick links wherever it stands, so removing its interaction points (already done before and
  after the rebuild) doesn't stop them.

#### Step 3b, run 21 (deployed 14:48): copies take bPathColliding; hidden doors and ladders go under the map

- `XComMapEdWall`, `XComMapEdDestructible` and `XComMapEdLevelPiece` take `bPathColliding` and `bCanStepUpOn` from
  their sources.
- The hider moves every door and ladder it hides 4,000 units down, out of every tile, so the rebuild makes no kick
  links or climbs for them. Ladders the patch places (`HideInPlace`, filled by patchtool) are hidden where they stand.
  This also takes away the old north side's climb (`patch_bar`'s `XComLadder_15`) and the west one (`_11`).

To check:
- a soldier can climb the block's ladder to the roof and back down;
- the roof is walkable up to its edges;
- no double kick, whichever way a soldier crosses the block;
- the north side of the old bar can no longer be climbed;
- walls, windows and cover still behave (the flags now match the bar's own pieces).

#### Step 3b, run 21 (14:51, `look-145109.png`): the ladder works

The user's note: "new ladder looks climable, old ladder is not anymore!". The move preview climbs the new ladder to
the roof.
- After the rebuild every probed roof tile has floor at z 402, the slab's top, edges included: (30, 21, 6),
  (33, 21, 6), (34, 21, 6), (35, 21, 6), (34, 22, 6), (33, 32, 6) and the centre. A* from the ladder's foot reaches
  its top directly, and the roof centre reaches the ladder's top.
- The hider moved the hidden double door and `patch_bar`'s two ladders under the map. (The north A* probe still finds
  a 1-tile climb there: an alien wall climb, which soldiers can't use.)

- 14:52, `look-145207.png`: "all roof tiles reachable". A soldier is on the roof, and the move range covers it up
  to the parapet.
- 14:52, `look-145241.png`: "inside still not visible, roof doesn't cut away", with a soldier inside the block (F-31).
  The cutaway's chain (pawn building-vis events, floor components, caches) is being read from the code.

Still to check: climbing down, a double kick on any route, and walls, windows and cover with the new flags. The roof
still doesn't cut away (F-31).

#### Step 3b, run 22 (deployed 15:13): the copies get a floor component

A read of the cutaway code (`research/native-code-notes.md`, "How the building cutaway works") found why nothing
cuts away: a building hides and cuts its pieces only through each piece's own attached `XComFloorComponent`, and the
wall and destructible copies had none. The UDK stubs of `XComFracLevelActor` and `XComDestructibleActor` named
`FloorComponent0` without declaring it, so our subclasses' compiled defaults held None there:

| Class default | Components before | after |
| --- | --- | --- |
| `XComMapEdWall` | None, FracturedStaticMeshComponent0, None, MyLightEnvironment | None, FracturedStaticMeshComponent0, FloorComponent0, MyLightEnvironment |
| `XComMapEdDestructible` | StaticMeshComponent0, None, MyNEWLightEnvironment | StaticMeshComponent0, FloorComponent0, MyNEWLightEnvironment |
| `XComMapEdLevelPiece` | had FloorComponent0 | unchanged |

The stubs now declare it (`unrealscript/XComGame-stubs.diff`).

To check: with a soldier inside, the roof and the floors above the soldier's are hidden. The walls facing the camera
are probably not cut down yet: that also needs `bCutoutMask` on each copy's mesh, which the UDK engine classes don't
know (next step).

#### Step 3b, run 22 (15:17, `look-151655.png`): the roof cuts away; the cursor snaps to the roof

The user's note: "ok roof cuts away so i can see inside now, but my cursor doesn't seem to let me select a tile inside
it just snaps to the roof".
- F-31 fixed: with the floor component attached, the copies hide with their floor. The inside is visible, doors and
  walls included.
- New: the cursor can't pick a tile inside (F-34). The roof has been floor since run 21; the game's own cut-away
  roofs don't catch the cursor. How the cursor's trace picks its hit (`XCom3DCursor.PerformTrace`) is being read.

#### Step 3b, run 23 (deployed 15:28): the cursor and the cut-away roof

How the mouse picks a tile (read from the code; `research/native-code-notes.md`, "How the mouse cursor picks a tile"):
`XComTacticalHUD.GetMousePickActor` traces along the mouse ray with `TraceActors`, which hits hidden, cut-away meshes
too. It skips pieces with `bIgnoreFor3DCursorCollision` (the bar's roof-level pieces have it), steep faces and points
outside the level. A walkable hit outside every listed building wins at once; otherwise a lower hit replaces a higher
one while the higher one is above the requested floor. The HUD and the 3D cursor fill their building lists once, in
`PostBeginPlay`, possibly before our patch level streams in.

Changes:
- `XComMapEdLevelPiece` (both copy paths) and `XComMapEdDestructible` copy `bIgnoreFor3DCursorCollision` (the wall and
  glass copies already did).
- The copier adds the patch building to `XComTacticalHUD.m_arrBuildingVolumes` and every `XCom3DCursor`'s
  `m_arrBuildingVolumes` at load and every 2 s, logging when it had to (new stubs: `XComHUD`, `XComTacticalHUD`,
  `XCom3DCursor`).

To check: with a soldier inside and the roof cut away, the cursor picks tiles inside the block.

#### Step 3b, run 23 (15:30, `look-153008.png`): the cursor picks tiles inside

The user's note: "yup, this looks good now, can see and select tiles inside the building". The log shows the cause:
at load our building was in neither list, and the copier added `XComBuildingVolume_9000` to `XComTacticalHUD_0`'s
and `XCom3DCursorMouseForCursorVolumes_0`'s building lists (8 buildings each). F-34 is fixed.

Step 3b's block now works: walls and windows block and give cover, doors open with one kick, the ladder climbs to a
roof walkable to its edges, the roof cuts away with a soldier inside, and the cursor picks tiles inside. Still open:
walls facing the camera aren't cut down (`bCutoutMask`), F-32 (a corner piece's lighting), F-17 (saves of copies),
and the old bar's ghost links of other hidden pieces (low walls).

#### Step 3b, run 24 (deployed 15:36): walls trimmed down (F-35)

The cutaway trims a wall down at floor height, and cuts it out in front of the camera, only when the wall's main mesh
has `bCutoutMask` (the editor sets it on placed pieces). No script function sets it, and the UDK engine classes don't
know it, so the copies can't take it like their other flags.
- `XComMapEdWall`'s main mesh is now a class of its own, `XComMapEdFracMeshComponent` (a plain subclass of
  `FracturedStaticMeshComponent`), set up as before.
- After copying, the copier runs the game's `set XComMapEdFracMeshComponent bCutoutMask true` console command, which
  finds the property in the game's own class and touches only our copies' meshes, then reattaches them. It logs what
  `get` reads back, since the shipped game may refuse `set` for a property that isn't config.

To check: with a soldier inside, the walls facing the camera are trimmed down; the walls still look lit, block and
give cover.

#### Step 3b, run 24 (15:38 and 15:39, `look-153816.png`, `look-153855.png`): walls trimmed down

The user's notes: "walls appear to cut out normally now"; "LOS still seems to work fine". The log: `set` is accepted
in the shipped game for this property (`get` reads back True), and 17 + 4 wall meshes were reattached. F-35 is fixed
for walls; window and door-frame copies (`XComMapEdDestructible`) get the same next (`XComMapEdMeshComponent`).

- 15:40, `look-154003.png`: "and grenades destroy walls as expected too" (a copied wall blown open, burning).

#### Step 3b, run 25 (deployed 15:42): window and frame trimming; saves of copies (F-17)

- Window and door-frame copies (`XComMapEdDestructible`) get their own main mesh class, `XComMapEdMeshComponent`, and
  the copier's `set` covers it too, so they trim down with the walls.
- Saves: a save keeps only damaged pieces. On load the game rebuilds each saved copy in place, under its saved name,
  from its class defaults and the record (health, state, broken columns), so it comes back without its mesh. The
  copier's reference to it still holds. Now every copy class (`XComMapEdWall`, `XComMapEdDestructible`,
  `XComMapEdLevelPiece`) asks its copier from `PostBeginPlay`, and the copier copies the source onto it again: mesh,
  materials, flags, columns and trimming (`RestoreLoaded`, sharing `FillCopy` with the spawn path). The game then
  applies the saved damage on top. During a normal spawn the copy isn't in the copier's list yet, so nothing happens.
  This is the same pattern that fixed spawned cars in EXP-05 (F-17).

To check: windows and door frames trim with the walls; blow a hole in a copied wall (and break a window), save,
reload: the wall comes back with its hole, the other copies are unchanged, and nothing is doubled or invisible.

#### Step 3b, run 25 (15:46, `look-154636.png`): trimming everywhere; copies survive a save and reload

The user's notes: "windows and door frames trim too"; after a save and reload, "walls still damage and burning as
expected".
- The log of the reload: the game reports each damaged copy "Not Found", rebuilds it in place under its saved name
  ("Recreating actor URB_Bar.TheWorld:PersistentLevel.XComMapEdWall_3"), and the copier restores it from its source
  before the record goes on: walls `_3`, `_4`, `_10` and destructibles `_0` to `_4` ("restored XComMapEdWall_3 from
  XComDecoFracLevelActor_10 after a load"). Copies get the same names on every load (spawned in the same order), which
  this relies on.
- Applying the destructibles' records logs `GotoState (XComMapEdDestructible None): State not found` six times; the
  pieces look right.

F-17 is fixed for copies, and F-35 for walls, windows and frames. Step 3b is done.

### Step 4: the L layout's north wing

The plan (`tools/upk/plans/urb_bar-L.json`) keeps the bar's footprint (tiles x 11..37, y 20..33) and adds a wing over
the street at x 25..36, y 8..19. The bar stays as it is, with its baked lighting, doors and ladders; only the wing is
new. Spec `tools/patch/examples/exp07wing.json`, patch `patch_exp07wing`, streamed into the Commercial Alley Redux
entry of URB_Bar in place of `patch_exp07block`.

#### Step 4, run 26 (deployed 15:58): the wing

- The block tested in step 3b (the bar's west block, turned 90 degrees so its open side faces +y) is copied north of
  the bar's east block, centred at (192, -576): x -384..768, y -1152..0. Its open side meets the bar's north wall
  (`XComDecoFracLevelActor_3`, y -11..11), which closes it, so the closing copy isn't needed. Its east wall lines up
  with the bar's (x 768).
- No doors and no ladder are copied: the copier could only move doors, and the bar keeps its own. The five door frames
  stay open doorways.
- The wing has its own building volume (`XComBuildingVolume_9000`, x -480..864, y -1249..96) with the west block's
  floor volumes moved and turned; they end at y 0, where the bar's start. Being inside follows the floor volumes, so
  the overlap of the two building volumes' margins doesn't matter.
- A hider takes out what stood on the street there (box x -380..800, y -1200..-6): the bar's awning and sign outside
  its north wall, parked cars, street signs, parking blocks, the fog pod and its effects, decals, rubble. It stops
  short of the bar's wall, of what hangs inside it, and of the delivery van west of the wing.
- The map is seeded again from the original for this patch, so the bar's ladders are back where they were.

#### Step 4, run 26 (a screenshot in chat): the wing stands; no doors, a gap at the entrance

The user's note: "Looks ok, but there's no doors in the new wing and the entrance seems to have a weird gap. Either
fill that with walls or a door or something." Also: "could we add some random decoration bits inside (more tables and
vending machines or whatever is in the bar area normally)", and the ground "should match the new layout (e.g. wood
flooring inside, pavement outside etc)", dynamically lit if need be.
- The gap is the bar's front opening. The west block's storefront porch had an open way in at its east end (x -576..-480,
  beside the east block's corner piece). On the wing it lands in the east wall at y -96..0, between the porch's low end
  wall and the bar's north wall, open to the sidewalk, with nothing framing it.
- Inside, the wing's floor is the bar's own floor mesh (`URB_Bar_384Floor`), so it already matches. Outside, the
  parking lot runs up to the wing's walls.

#### Step 4, run 27: doors, an entrance door, props and a sidewalk ring

- **Doors are copied** (`XComMapEdDoor`, the copier's `bCopyDoors`). The copy takes its source's skeletal mesh,
  physics asset, animation sets and tree, interaction points and animation settings, damage and destruction events
  (with its own action objects), toughness and cover flags. The tile rebuild over the copies gives it interaction
  points, as for a moved door. After a load it asks its copier to fill it again, like the other copy classes (F-17).
  The stub `XComInteractiveLevelActor` drops `privatewrite`/`const` from the fields it sets (compiler-only modifiers).
  The wing copies the block's five doors into their frames.
- **The entrance:** a copy of the bar's west door (`XComInteractiveLevelActor_4`) and its frame, turned 180 degrees,
  fills the front opening at (768, -48).
- **Props** from the bar furnish the wing's rooms:
  - the east block's arcade row (claw machine, arcade machine, cigarette machine, ATM) along the south-west room's
    inner wall;
  - the pool table on its rug in the long east room;
  - two diner table sets along the storefront windows;
  - a table set, two trash cans and the west block's cigarette machine in the north-west room.
  They join the wing's building, so they cut away with it.
- **A sidewalk ring** of copied sidewalk pieces (lit dynamically, like every copy) goes round the wing, four tiles
  wide:
  - the bar's east sidewalk continues north to a new north-east corner;
  - the north side meets the far sidewalk;
  - the west side runs down to the bar's north sidewalk.
  - The bar's north-east corner piece gives way to a straight piece.
  - The kit's pieces are 8 tiles long and the sides are 9 to 13 tiles, so some pieces overlap. The upper one is
    raised 1 or 2 units, so they don't flicker.
  - Under the ring, the hiders take out the parking stripes and blocks, a ground decal, the delivery van (with its
    own building and floor volumes), an SUV and a steam emitter.

To check: the doors open and kick once; the entrance door leads in from the east sidewalk; the props stand in the
rooms, block and give cover, and cut away with the wing; the sidewalks line up with the wing's walls and the old
sidewalks, with no flicker; a door opened before a save is still there after a reload.

#### Step 4, run 27 (a screenshot in chat): props fine; doors and the entrance missing

The user's notes: "still missing door or wall at the main entrance gap, most doors still missing (there is one in the
top). Decorations inside look ok and appear to block/provide cover normally." Also: "Could we also add a ladder on the
right side (of this image, on the outside of the new wing)?", with "LADDER HERE" drawn outside the wing's north wall.
- The log: the copier made all six door copies (`XComMapEdDoor_0` to `_5`, each with its mesh, tree and 6 interaction
  points, at the right places). Then the street hider hid `_1` to `_5` and moved them under the map: its class test
  skipped our other copy classes but not the new one (F-36). `_0`, on the west wall, stood outside its box.
- The props block and give cover.

#### Step 4, run 28: the doors kept; a ladder outside the north wall

- Hiders skip `XComMapEdDoor` and anything else of the `XComMapEd` package (F-36).
- The ladder, set up as step 3b's:
  - a copy of the bar's south ladder (`XComLadder_4`) as a plain mesh with no collision, at (240, -1200), outside
    the north wall and east of the north door. The copier's new `bCopyLadders` copies a ladder like this instead of
    moving the bar's own, and patchtool leaves the source's baked links alone for such a copier.
  - a hidden climbing ladder in the patch at (236, -1180), beside it as patch_bar places `XComLadder_15` beside
    `XComLadder_4`. Its top is the roof's first row inside the north wall; its foot is on the north sidewalk.

To check: all six doors are there and open; the entrance door fills the gap; the ladder climbs from the north
sidewalk to the roof; the bar's own ladders still climb.

#### Step 4, run 28 (16:29, `look-162956.png`, and a screenshot in chat): doors in, but nothing new works

The user's notes: "doors are in, but main entrance gap is still there. also new doors and ladder and windows in the
new wing do not work normally (can't open the doors, can't climb the ladder, can't run through the windows). and could
we make the floor wood or something in the top right room of the new wing too ?" Then, on a second screenshot:
"entrance gap isn't just a strip above the door, there is no door, just a gap in the wall going into the new wing
area".
- **The gap** is the bar's own front doorway in its north wall (`XComDecoFracLevelActor_3`, x 480..576): the A*
  probes 5 s after load walk from the bar's north-east entry room into the wing through it, (34, 20) to (34, 19). It
  used to open onto the street. The entrance door copy of run 27 stands at (768, -48), against the solid east wall.
  The east-wall bay read from the block's layout was wrong.
- **Doors:** every probe into the wing goes round through the bar's doors. The door copies are must-destroy (F-37).
- **Ladder:** the foot (north sidewalk, floor z 18) and the roof (floor z 402) both have floor 5 s after load, and
  the hidden climbing ladder stands, hidden in place, as step 3b's did. No probe covered the climb.
- **Windows:** URB_Bar's baked links have no window-break traversals at all (link types: DropDown, WallClimb, JumpUp,
  ClimbOnto, ClimbOver, KickDoor, ClimbLadder). A unit goes through a window as a climb-over of the sill, which the
  rebuild makes from the window actor. The copies take its flags and toughness, so the cause is still open.
- **The floor:** the north-west room was the bar's kitchen, and the copied west-block floor mesh has a tiled section
  there.

#### Step 4, run 29: door copies work out bMustDestroy; the door in the bar's doorway; a wood floor; late rebuilds

- `XComMapEdDoor.CopyFrom` works `bMustDestroy` out after copying the interaction points (F-37), and logs it with
  the door's state.
- The entrance door and frame move into the bar's front doorway at (528, 0), facing along the wall.
- **Floor:** a copy of the east block's floor (`URB_Bar_384CFloor`, 13 x 13 tiles, wood), scaled to 12/13 about its
  pivot (the copier's new `CopyScale`), covers the wing exactly, one unit above the copied west-block floor.
- The wing's copier and the ladder's copier rebuild their tiles again 4 and 4.5 s after load (the copier's new
  `LateRebuild`), once every copy, door and sidewalk stands.
- Probes:
  - from the north sidewalk up the ladder to the roof;
  - through the bar's front doorway;
  - through a copied storefront window;
  - through one of the bar's own windows (between the bar and the wing);
  - through the west door.

To check: the doors open; the bar's doorway has a door; the north-west room has a wood floor; the ladder climbs;
the windows can be run through.

#### Step 4, run 29 (16:47-16:50, `look-164747.png` to `look-164950.png`): the door in, the gaps and the rest not

The user's notes:
- on the bar's doorway: "can we just put a wall to fill this gap please ? it's still there 5 tries later.";
- on the wing's inner wall at x 192, which stops at y -178 short of the bar's north wall: "this should be a full wall too";
- on the wing's doors and windows: "still can't go through doors or windows here";
- on the bar's own: "but we can here";
- "ladder still unusable".

Then, on a screenshot of the ladder's foot: "that V means it's not a walkable tile. normally it should be possible to
put a soldier there".
- **The gap:** the bar's front doorway is two tiles wide (x 480..672). The door copy fills tile 34, and the probe
  through the doorway walks through tile 35, (35, 20) to (35, 19).
- **Doors and windows:** the door copies log "must destroy False", so F-37's fix holds, but also "state
  XComMapEdDoor": the copies are in no state. The game's doors and destructibles start in their auto state
  `_Pristine`; a door can be opened only there (`CanInteract`), and a window broken through only there
  (`BreakWindow` checks `IsInState('_Pristine')`). Our classes are compiled against stubs that declare no states,
  so they never enter it (F-38).
- **Ladder:** the A* probe from the north sidewalk to the roof climbs at tile (30, 7), one tile west of the ladder,
  and walks round its foot tile (31, 7). The user's screenshot shows that tile left out of the walkable area. The
  game makes a ladder's climb only when its foot tile is floor. The foot tile holds the visible ladder, a mesh copy
  (`XComMapEdLevelPiece`, an `XComLevelActor`), where step 3b's visible ladder was the bar's real `XComLadder`
  moved there. The level piece takes the tile, even with its collision off (F-39). The hidden climbing ladder was as
  step 3b's.

#### Step 4, run 30 (deployed 17:05): walls in both gaps, doors and windows in _Pristine, a real ladder

- **Walls:** three copies of the bar's full-height one-tile wall (`XComDecoFracLevelActor_9`, Core_384BackC):
  - one at (624, 0), yaw 90, in the doorway's east tile (35);
  - two at (192, -48) and (192, -144), yaw 0, closing the inner wall's end (y -203..11).
- **Doors and windows:** `XComMapEdDoor.CopyFrom` and `XComMapEdDestructible.CopyFrom` go to `_Pristine` when the copy is in
  no state (F-38). The destructible's `_Pristine` turns ticking off on entry, so this comes before
  `SetTickIsDisabled(false)`. The spawner's cars (EXP-05) go through the same `CopyFrom`, so they now start in
  `_Pristine` too, as the game's own cars do.
- **Ladder:** the mesh copy and the hidden ladder are gone. There is one patch ladder object, visible, at
  (240, -1200, 16), yaw 90: a real `XComLadder` with URB_Bar's ladder mesh, standing 48 units out from the wall like
  `XComLadder_4`. patchtool now puts the patch's visible ladders in each hider's `KeepNames`, and only the hidden
  ones in `HideInPlace` (F-39).
- The wing's copier rebuilds each nearby ladder's foot tile alone, 6 s after load (the copier's new
  `LadderFootRebuild`), after every other rebuild. That makes the climb both ways (native notes). It logs, before and
  after, the foot and top points, their floor and whether they're occupied.
- Probes added:
  - to the ladder's foot tile and up it;
  - through both doorway tiles;
  - across the inner wall's end;
  - floor at the ladder's foot and top.

To check: no gap beside the bar's doorway door, nor at the inner wall's end; the wing's doors open and its windows
can be run through; the ladder's foot tile is walkable and the ladder climbs both ways.

#### Step 4, run 30 (17:07, `look-170659.png`): the ladder and the doors work

The user's note: "ok ladder and doors work now nice". The log agrees:
- every door copy logs "state _Pristine" (F-38);
- the ladder's foot tile (31, 7, 0) has floor, and the A* probe from the north sidewalk climbs at the ladder's own
  tile, (31, 7, 0) to (31, 8, 6) (F-39);
- the probe through the doorway's east tile now goes round through the door in tile 34, and the probes across the
  inner wall's end go round it, so both new walls close their gaps.

The windows are still to check: the run 29 window probe starts on a tile a copied table takes, so it shows nothing.

#### Step 4, run 30 (17:08, `look-170844.png`, and a screenshot in chat): windows still blocked; cars wanted

The user's notes: "windoes still can't be pathed through though", on the wing's east storefront windows; then, on a
screenshot with three places circled: "also can we add some cars in these 3 places (yes, one is on the roof)".
- **Windows:** the bar's working window (`XComDestructibleActor_66`) and the wing's source window
  (`XComDestructibleActor_158`) set the same actor properties; their archetypes differ
  (`ComKitWindows.Archetypes.ARC_ComKitWindow_StandardTripleB` and `..._LongDoubleC`), and both archetypes set
  `bInteractive` and a glass toughness. The copy takes the toughness, but not `bInteractive`, which is `const` in the
  game's class and so was never copied (F-40). The mesh components set nothing else.
- **The three places**, read from the screenshot. The camera looks south-west from the wing's north-east corner; the
  BAR & GRILL sign (`XComLevelActor_25`, (-240, -1681)) and the map's parked SUV (`XComDestructibleActor_14`,
  (1344, -366)) fix the view.
  - the middle of the wing's roof, about (336, -720);
  - the north road just past the north sidewalk's curb, about (430, -1730);
  - the east road beyond the sidewalk ring's north-east corner, about (1900, -1650).
- **Landing zones:** both road places are near one of LWR's landing zones for URB_Bar (`XComLZMutator.ini`):
  - (719, -1681), facing north, whose spawn points lie south of it on the north sidewalk (F-06);
  - (1967, -1489), facing east, whose spawn points lie west of it.

#### Step 4, run 31 (deployed 17:20): window copies interactive, three cars, a cursor log

- `XComMapEdDestructible.CopyFrom` copies `bInteractive` and `bIgnoreForPathing` (the stub drops `const` from both)
  and logs each glass copy with its state (F-40).
- **Cars,** spawned as EXP-05's (the map's own archetypes with their glass partners):
  - a compact car on the roof at (336, -720, 402). The spawner's new `BuildingName`/`BuildingFloor` put it and
    its glass into the wing's roof floor cache (floor 2, cutdown floor 0, as the copied roof pieces), so it should
    cut away with the roof;
  - an SUV along the north road at (432, -1728), clear of the sign and of the north landing zone's spawn points;
  - a compact car on the east road at (1952, -1720), turned like the map's parked compact, north-east of the east
    landing zone's spawn points.
- The wing's copier logs the 3D cursor's position and tile when its tile changes (`bLogCursor`): to move a car, the
  user points the cursor at the spot and presses F9, and the spot is read from the log.
- Probes added: from the east sidewalk through the east storefront windows into the rooms, at y -432, -720 and -912.

To check: the wing's windows can be run through; the three cars stand where the user circled them, lit and solid,
and the roof car cuts away with the roof.

#### Step 4, run 31 (17:2x, a screenshot in chat): windows, cars and the roof car's cutaway work

The user's note: "windows now can be smashed/run through correctly. and cars seems fine though oddly at least the
roof car seems to provide no cover from the front and back (this might just be how this type of car works in the game
normally so not sure it's an issue at all). car on roof also hides correctly when looking inside the building".
- The log: the three glass copies log "interactive True ... state _Pristine" (F-40). The probes from the east
  sidewalk walk straight through the east windows at y -432 and -720. The third probe (y -912) ends on a tile the
  copied G3 table set takes, so it shows nothing.
- The roof car and its glass joined the wing's roof floor cache ("put 2 piece(s) into XComBuildingVolume_9000
  floor 2's cache"). That is why it cuts away with the roof.
- **Open:** no cover at the roof car's nose and tail. A compact car is about 300 units long, a little more than
  three tiles (288), so wherever it stands its ends reach a few units into the next tiles. Whether the map's own
  compacts give cover at their ends is still to check (EXP-05 only checked the long sides).

#### Step 4, run 31 (two more screenshots in chat): car ends block their tiles

The user, on one of the map's own cars in its parking lot: "Here's a compact that's normally part of the level for
example": its cover shields show at its tail. On the roof car: "I think the issue is there's no path to right against
the car, can see the highlight not going near it on the front and back". On the road cars: "the new cars on the ground
seem fine", then "actually not entirely this new one also can't be reached properly from the front" (the north SUV).
- **Cause (F-41):** where a car stands on the tile grid. URB_Bar's own compact (`XComDestructibleActor_20`) has its
  body (bounds x 1623..1927, y -1052..-872) fill tiles x 1632..1920 and y -1056..-864, reaching 7-9 units past them.
  The bodies, worked out from the map's cars:
  - a compact is 294 x 160 units, its pivot 44 units behind the body's centre, so 3 x 2 tiles;
  - an SUV is 384 x 182, so 4 x 2 tiles.

  Our cars stood off that grid. The roof car's nose and tail reached 52 and 36 units into the next tiles, the north
  SUV's 44 units at each end. Those tiles were blocked, so the move range stopped one tile short, out of cover.

#### Step 4, run 32 (deployed 17:32): the three cars on the tile grid

- Each car's body fills whole tiles, as the map's own cars do:
  - roof compact at (384, -764, 402), yaw 0: body x 304..464, y -867..-573;
  - north SUV at (388, -1728), yaw 90: body x 192..576, y -1819..-1637;
  - east compact at (1924, -1728), yaw -90 (was -86): body x 1821..2115, y -1808..-1648.

To check: each car's nose and tail tiles can be reached and give low cover, as its sides do.

#### Step 4, run 33 (deployed 17:39): the spawner snaps cars to the grid; an overview view for a screenshot

The user: snapping to the grid "sounds like a good idea", and "is it possible for you to get me a overview shot of the
map in the editor, zoomed out and well lit ? at a slight angle, from the "front" (where the newly added white car
is)".
- **Snap:** with `bSnapToTiles`, the spawner reads the car's bounds after spawning, rounds each side to whole tiles
  and moves the car and its glass (by up to half a tile) so the body fills them. Across an even count the body's
  centre goes on a tile edge; across an odd count, in a tile's middle. It logs the bounds, the tile counts and the
  shift. The three cars go back to where the user circled them (run 31) and are snapped. Expected:
  - roof compact to (384, -764);
  - north SUV to (388, -1728);
  - east compact to about (1924, -1731), at the map's -86 degrees.
- **Overview:** the authoring UDK can't open URB_Bar (a Firaxis package), so the editor has none of the map; the shot
  has to come from the game. The game's tactical camera keeps its zoom and pitch in code defaults; the copier calls
  the game's `XGCameraView.ChangeOverheadCameraDefaults`, as the cheat `SetOverheadCameraParameters` does (FOV 45,
  distance 7000, pitch 55). It also raises the highlights and mid tones of every post-process volume, 2, 8 and 20 s
  after load. A one-function stub of `XGCameraView` makes the call compile. To be taken out after the shot.

#### Step 4, run 33 (17:41, `look-174155.png`): the snap works; the photo camera is under the map

The user's note: "camera is underground and looking up". The camera change works: the whole map is in view, from
below. The game's pitch is negative downward, so +55 looked up.
- **Snap:** each car moved onto the grid, to within 2 units of the hand-placed run 32 spots.
  - roof compact: by (+47, -45), to (383, -765); bounds 2 x 3 tiles;
  - north SUV: by (-45, -1), to (387, -1729); 4 x 2 tiles;
  - east compact: by (-29, -12), to (1923, -1732); 3 x 2 tiles.
- **Brightness:** URB_Bar has no post-process volumes; only the world's default settings were brightened.

#### Step 4, run 34 (built 17:43; deployed when the game closes): the photo camera looks down

- `PhotoPitch=-55`.
- With `PhotoHighlights`, the copier also lays the brightened settings over the player camera's view each tick
  (`CamPostProcessSettings`, alpha 1, in `TG_PostUpdateWork`). The camera resets that override every frame.

#### Step 4, run 34 (a screenshot in chat): the overview angle works, but it is very dark

The user: "not bad but very dark, would be nice if we could light it up a bit (and ideally disable the UI for this
overview shot)". The camera looks down on the whole map from the front. The log shows the brightened post-process
settings applied three times, with no visible change. The game's renderer doesn't take the tone-curve settings this
way.

#### Step 4, run 35 (deployed 17:50): real light and no UI for the overview

- `XComMapEdSun`, a plain actor (spawnable) with a dynamic directional light and a sky light, both on every lighting
  channel and `LAC_DYNAMIC_AND_STATIC_AFFECTING`, so they should reach the map's static meshes as well as the dynamic
  ones. The copier spawns one when `PhotoSun`/`PhotoSky` is set:
  - sun 1.2 from yaw 138 (behind the camera), 50 degrees down;
  - sky 0.5.
- `bPhotoHideUI`: the copier calls the game's `XComPresentationLayerBase.HideUIForCinematics` (a two-function stub). It
  does this at each photo step, 2, 8 and 20 s after load and then every 10 s.

#### Step 4, run 35 (a screenshot in chat): the overview shot

The user: "this is perfect. let's remember how we did this so we co get other overview shots set up in future". The
shot shows the whole L layout from the front (north-east), lit by the sun light, with no UI. A copy of it is in the
lab folder (`<lab>\looks\overview-exp07-run35.webp`; not in the repo, since it shows game art).

#### Step 4, run 36 (deployed 17:55): the overview view is a patchtool object

- The photo view moved out of the copier into its own class, `XComMapEdPhoto`, placed by patchtool's new `photo`
  object (`{ "type": "photo" }`). Its class defaults are run 35's settings, and each field overrides one. The recipe
  is in `tools/patch/README.md`, "Overview shots".
- This spec has no photo object any more, so normal tests keep the game's camera, lighting and UI. A test build with
  one added compiled and imported (`XComMapEdPhoto_927`), and the field overrides are written to the T3D.

#### Sharing the L layout as a map of its own (4 November 2026, 18:00)

The user asked for a package to share with other modders: "just a few hints should be sufficient". They also asked
whether the remix is "technically a new map, and can be played in game in addition to the original bar&grill map".
- **As built, it is not a map of its own.** It is our patch streamed over URB_Bar.upk, and that file is the seeded
  copy (F-29). A seeded tile that nothing rebuilds at load keeps its seed bit, and the game treats it as blocking
  (`XComMapEdTileSeeds` exists for this reason). So the original record, still streaming `patch_bar` over the same
  seeded file, would have phantom blockers on the 967 seeded tiles north of the bar (F-42).
- **Fix:** ship the seeded map under a name of its own, `URB_BarRemix.upk`, with its own map record streaming
  `patch_exp07wing`. The original URB_Bar.upk then stays untouched. The name is all that changes:
  - the copier finds the bar's pieces by actor name at run time;
  - streaming levels are loaded into any persistent map;
  - LWR's landing zones (`DefaultLZMutator.ini`) and LW's map rule (`DefaultMiniMods.ini`) are keyed to the map name,
    so the readme gives URB_Bar's lines under the new name.
- **The package:** `dist/URB_Bar_L_Remix.zip`, not in the repo, since it holds game files. It contains:
  - `URB_BarRemix.upk`, the seeded URB_Bar, hash `aa7fb1ba...`;
  - `patch_exp07wing.upk`, run 36;
  - a readme with the map record, the landing-zone lines and the Mini Mods rule;
  - the overview shot as a preview.
- **Lab state for the user's comparison shot of the shipped bar:** URB_Bar.upk is the original again (`unseed`),
  `URB_BarRemix.upk` sits beside it, and the test slot (line 36) streams `patch_barphoto` (`examples/barphoto.json`:
  `patch_bar` plus a photo object) on URB_Bar. Next, the slot moves to `URB_BarRemix` with `patch_exp07wing`, to check
  in the game that a renamed map loads.
- **Lab state for the renamed-map test (18:05):**
  - the test slot (line 36) loads `URB_BarRemix` with `patch_exp07wing` (run 36, no photo object);
  - the lab's `DefaultLZMutator.ini` has URB_Bar's seven landing zones under `URB_BarRemix`, as the readme says;
  - URB_Bar.upk is the original.

  A first attempt at that INI edit emptied the file: it was opened for writing before the new text was built. It was
  restored from the backup taken just before, and matches the parked LWR install's copy byte for byte.

#### The renamed map in the game (18:07): it works

The user: "yes loaded in and everything looks good". The log:
- "SeamlessTravel to: URB_BarRemix", then the wing's copier and its copies as usual (six door copies);
- LWR's landing-zone mutator, with "CurMapName = URB_BarRemix", found the seven copied entries ("DataArray.Length =
  7") and picked one at random;
- the two "Failed to load ObjectArchetype ... FracturedSkinnedComponent0" warnings, which earlier runs on URB_Bar
  logged too.

So the share package (`dist/URB_Bar_L_Remix.zip`) works as a map of its own, beside the untouched URB_Bar (F-42).

**Note for later EXP-07 runs:** the test slot now loads `URB_BarRemix.upk`, a copy of run 36's seeded URB_Bar, while
patchtool still seeds `URB_Bar.upk` from the spec's `map.name`. After a run that changes the seed plan, either copy
the seeded URB_Bar over `URB_BarRemix.upk`, or point the slot back at URB_Bar.

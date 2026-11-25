# EXP-43: the game's blank map as a stage for game runs

Date: 11 November 2026. Stage T1 of the prefabs and buildings plan (its 5.10 and 5.11):
the later runs of that plan want an empty map to put a building or a prefab on, and a map made
from scratch is tried first. The game ships one map that is little more than a level and a tile grid,
`CB2_MP_Blank` (a multiplayer map), so that is the shell. Nobody here has started a single-player battle on it.

## What the map holds (read offline)

- 5.8 MB, 1,187 exports (URB_Bar: 16.8 MB, 14,051).
- A level volume with a tile grid of 36 by 36 tiles and 12 levels (four storeys): x -2112 to 1344, y -1344 to 2112,
  z 0 to 768.
- 16 ground planes of the level-design kit's floor (`CFloor_864`, nine tiles across), each with a grass material,
  and six other pieces.
- A player start, 12 `XComSpawnPoint`s, one `XComAlienPod`, one directional light.
- **Not there**: cursor volumes, building or floor volumes, any other volume with a brush, a landing zone (no
  Skyranger, and no `LZArray` lines in LWR's config), a sky light, a backdrop.
- Its record in `DefaultMaps.ini` is live, a multiplayer deathmatch (`eMission_MPDeathmatch`), out of rotation.

## Run 1: the map as the game ships it

Nothing is built or installed. The game is started straight in a battle on the map, as Play in game starts any
map (F-72): in the editor, open **Blank (multiplayer)** from the map browser, then Project, Play in game. The lab
copy is the install the editor plays in.

What this run is to show, all of it new:

1. **Does a battle start?** The map loads and a turn begins, or the game stops, hangs on the loading screen, or
   comes up as a multiplayer match.
2. **The squad**: six soldiers with bodies and weapons, and where they stand (there is no Skyranger to step out of).
3. **Aliens and Meld**: LWR puts its pods and Meld on random floor tiles (F-85); whether any appear, and whether
   the turn passes to them and back.
4. **Moving and the cursor**: soldiers walk and dash over the ground; the cursor follows the mouse over the whole
   map; what the mouse wheel (floor up, floor down) does with no cursor volumes (F-88).
5. **The light**: how the soldiers and the ground look under the one directional light, and how the edge of the
   map and the void beyond it look.
6. **A save and a reload** in the battle.

### Result: a battle starts; saving does not work

Played by hand on 11 November 2026, in the lab copy, with two screenshots and the game's log
(`<lab copy>\XEW\XComGame\Logs\Launch.log`).

1. **A battle starts.** The map loads in about five seconds as a single-player battle ("Neutralize hostile
   targets"), turn 1 begins.
2. **The squad is there but on one tile.** All six soldiers have bodies and weapons and stand on the same tile.
   The log: `FindSpawnGroup: Looking for spawn points with tag: None`, then `Accessed None 'kSpawn'` twelve times
   in `XGPlayer.LoadSquad`. The map's 12 spawn points are not ones the squad's loader takes (F-90).
3. **Aliens: the map's own pod, not LWR's.** Three sectoids stood at the map's edge and the turn passed to them
   and back. LWR's pod mutator gave up (`No player spawn points found`, `Found 0 random locations`, `can't find
   enough spawn locations, skipping`), so the map's one `XComAlienPod` played. Meld: `no need to spawn Meld,
   skipping`.
4. **Moving and the cursor work**: the movement outline and a path show over the ground. The mouse wheel was not
   reported.
5. **The light is enough to see by** in a lit patch, and the rest of the ground is under the fog of war as on any
   map. The ground reads as flat grass with the planes' seams as faint lines; beyond the edge is black. The map's
   six other pieces are a van, a pickup and a wall.
6. **Saving fails.** After Save, the "saving" notice came and went without end. The save was written (`save1`,
   2.76 MB; the log has one checkpoint of 129 actors and one of 8, `Async Work Finished`). Loading it from the
   load menu hung the game with nothing in the log; it was closed with Alt+F4. The load menu also asked for a
   picture the game doesn't have (`UILibrary_MapImages.CB2_MP_Blank`).

**Not known yet: whether the save trouble is this map's or the way the battle was started.** No save has ever
been made in a battle started this way (F-72 lists it as not known): every save in an earlier experiment was in a
campaign, with the variant in the lab's test slot. Run 1b tells them apart.

## Run 1b: a save in a battle started the same way on URB_Bar (control)

Nothing is built. In the editor open URB_Bar's original layout, Play in game, move a soldier, save, then load
that save.

- If it saves and loads: the trouble is the blank map's (F-89), and what it lacks has to be found before the map
  can be a stage.
- If it fails the same way: saving does not work in a battle started without a campaign, on any map. The stage
  is not at fault, and runs that need a save go through the lab's campaign test slot, as EXP-37 to EXP-42 did.

### Result: the same on URB_Bar, so it is the way of starting

Played by hand on 11 November 2026: the same happened on the bar. The log has the same lines as run 1's (both
checkpoints copied, the compression finished, nothing after). The lab copy's 38 kept logs of a start with `-EXEC`
hold no other save or load: saving in a Play in game battle had never been tried, and the saves that worked
earlier that day (EXP-40 to EXP-42) were in a campaign. F-89 is now about Play in game on any map; the blank map
is not at fault.

## Run 2: the map equipped, with pieces of other maps on it

Decided on 11 November 2026: a save in a Play in game battle need not work for now (F-89 stays open), and the
blank map goes ahead as the stage.

### What is built (offline)

- **A new stage of the Build** ([shell.py](../../tools/bake/shell.py), `Build.shell`): a base map that lacks them
  gets, from URB_Bar, six soldier spawn points (set on the blank map's own multiplayer team-one points), URB_Bar's
  four cursor volumes (moved 288 units in y so they cover the blank map's grid: floors 1 to 4 at z 0, 210, 402 and
  594) and a plain volume for the Build to clone rebuild volumes from (staged, not placed). Ten actors join the
  level's list; the map's own 49 stay. Every other map lacks none of the three and is left alone.
- **The project** ([exp43_project.py](../../tools/editor/examples/exp43_project.py)), in the editor's projects as
  "EXP-43 blank map stage":

  | Piece | Home map | Parts |
  |---|---|---|
  | a dry bush | URB_GasStation_EWI | 1 |
  | an abductor wall, three tiles | LAbductor_WindingStream | 1 |
  | an SUV with its doors open | URB_OfficePaper_Terror | 4 |
  | a moving van, with its building volume and two floor volumes | URB_ResearchOutpost_EWI | 14 |

- A quick build, 18 seconds. Read back from the built map (`CB2_MP_Blank_X43`): it lacks nothing; the level lists
  18 spawn points (the map's 12 and the six soldier points), four cursor volumes, the van's building and its two
  floor volumes (floors of 7 and 1 members) and four rebuild volumes. The variant's record is the blank map's own
  (a multiplayer deathmatch, out of rotation).

### Where to look

Picture `EXP-43-run2-overview.png` (not in the repository): the stage.

In the editor open the project **EXP-43 blank map stage**, then Project, Play in game (a quick build is enough).
What this run adds:

1. **The squad starts spread out**, each soldier on a tile of their own (mark 1).
2. **LWR's pods and Meld**: more than the map's one pod of three sectoids, placed about the map.
3. **The pieces stand, give cover and break** as in their home maps: the bush (2), the wall (3), the SUV (4).
4. **The van (5) is a room**: a soldier walks into its box and stands on its floor; with a soldier inside, the roof
   and near walls cut away. This is the first building on the stage.
5. **The cursor's floors**: the mouse wheel goes up and down a floor, and the cursor reaches the van's roof.

A save is not part of this run (F-89).

### Result: passed, but for LWR's pods and Meld

Played by hand on 11 November 2026: fine in game as expected, though only 2 sectoids were on the map and no
meld, not important for now.

- The squad's start, the pieces, the van and the cursor were as expected. The blank map is the stage.
- **Pods and Meld: still the map's own pod.** The log shows LWR's mutator now finds the six soldier points, then
  divides the map into sections and keeps those at least 29 tiles (`PLAYER_PROXIMITY`) from the squad's centre. On
  a grid of 36 by 36 with the squad near the middle no section is that far (`Not enough sections left: 0`, tried up
  to 11 sections), so it places nothing and the map's `XComAlienPod` plays. Meld goes the same way. A larger grid,
  or a squad that starts in a corner, would give it room (F-90).

## Run 3: a grid of a chosen size (54 by 54 tiles)

### What is built (offline)

- **The tile data written anew** ([world_grid.py](../../tools/upk/world_grid.py)): the map's container taken apart
  into tiles and put together for a larger grid, from the same corner. Every tile the map has is kept; a new tile
  gets what bare ground has in the map itself (its static flags by its level and its place across the grid, floor
  data with a link to each tile around it). Checked: the blank map's, URB_Bar's and CSmallScout_Farm's containers
  come back byte for byte when written again unchanged; the two rules for bare ground give the blank map's own
  tiles back everywhere but about its wall, van and pickup (15,242 of 15,552 flags, 1,214 of 1,296 floors).
- **The resize** (`shell.resize`, asked for by a project's `stage: {grid: [nx, ny]}`): 20 clones of the map's
  ground plane laid over the new area; the container 480,504 to 1,092,936 bytes; the world data's `NumX`, `NumY`,
  `NumTiles` and `WorldBounds`; the level volume stretched by `DrawScale3D` (1.5 in x and y); the cursor volumes
  stretched to the grid (1.04 in x, 1.38 in y: URB_Bar's are 52 by 39 tiles); one rebuild volume over the whole
  grid, so the battle works every tile out when it starts.
- **The project** "EXP-43 blank map stage, 54 by 54" (`exp43_project.py --grid`): run 2's pieces, and an abductor
  wall and a bush on the new ground. A quick build, 15 seconds. Read back: the grid is 54 by 54 by 12 from the same
  corner in the level volume, the world data and the container; 2,916 ground tiles each name a ground plane in the
  level's list; the copies on the new ground seeded their tiles there (156).
- Not touched: the level volume's hidden mesh, its brush's own geometry, the movement grid components.

### Where to look

Picture `EXP-43-run3-overview.png` (not in the repository): the larger grid.

The editor still draws the map's own 36 by 36 grid and ground: the two new pieces show past its edge, over
nothing. In the game the ground is there. Open **EXP-43 blank map stage, 54 by 54**, Project, Play in game.
What this run adds:

1. **The map loads**, and the ground reaches the new edges (to the east and the north of the old map).
2. **The camera and the cursor** go to the far corner (mark 4), and the mouse wheel changes floors out there (the
   cursor volumes are stretched ones).
3. **A soldier walks and dashes across the old edge** onto the new ground, and the movement outline crosses it
   without a seam.
4. **The wall (2) and the bush (3) on the new ground** stand on it, give cover and break.
5. **LWR's pods and Meld**: with room now, more than the map's one pod.
6. How long the start of the battle takes (every tile is worked out again): about as before, or noticeably longer.

### Result: passed

Played by hand on 11 November 2026, with a screenshot: it works; more floor pieces were added that way too, and
Meld and aliens spawned in the extended area too.

- The larger grid plays: ground, movement and the pieces on the new ground were as expected, and the floor
  pieces added in the run worked there.
- **LWR's pods and Meld came**, in the new area too (a Meld counter and a pod of three in the shot): on 54 by 54
  its mutator has sections far enough from the squad (F-90).
- So a level volume and cursor volumes stretched by `DrawScale3D` do their work, and tile data written by
  `world_grid.py` is accepted.
- Not reported: the mouse wheel's floors at the far corner, and how long the start took.

### The same on another map

Tried offline on URB_Bar, 52 by 39 to 61 by 48: the tile data, the world data, the level volume and the cursor
volumes all take the new size and read back. What a real map needs beyond that:
- **ground for the new area**: the tool lays clones of the ground piece the map's ground tiles name most, which on
  the blank map is its plane and on URB_Bar is the bar's own floor slab (wrong: the choice has to be the user's);
- **its surroundings**: the scenery, blockers and backdrop a map has around its play area are placed for its size;
- **growing only away from the map's corner** (to the east and north), since tile numbers start there;
- **shrinking** is not built: the tile data would be simple, but everything outside the new grid has to go.
Not played.

## After run 2

- The stage's ground grid is still to choose (the plan's 5.11); the light stays as it is.
- LWR's pods and Meld need a map with room: the squad in a corner, or the larger grid.
- A grid of a chosen size (the plan's T1.5) and stage B1, a building made from nothing, come next.
- The fallback stays a real map with its play area cleared, as EXP-08's blank Bar was (the plan's 5.9).

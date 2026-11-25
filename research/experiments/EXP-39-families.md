# EXP-39: one piece of each family from other maps

Date: 11 November 2026. The one game check of the other families of pieces from other maps
(implementation plan, X9), in place of a check per
family. [EXP-37](EXP-37-foreign-props.md) and [EXP-38](EXP-38-foreign-props-baked.md) settled plain scenery, quick
and baked. Here five more kinds of piece stand in URB_Bar's car park, each from a map the bar shares nothing of the
piece with, in a baked build.

## What is built (offline)

- The project: [exp39_project.py](../../tools/editor/examples/exp39_project.py) writes it and builds it by the Build
  with the families' gates lifted (`Build(foreign=...)`, as `build.py --foreign-family` does). The pieces:

  | # | Family | Piece | Home map | What it brings |
  |---|---|---|---|---|
  | 1 | Destructible prop | a dry bush (`Bush_A_B_Dry`) | URB_GasStation_EWI | 29 objects, 27 KB |
  | 2 | Collectible | an alien nav computer (`AlienNav_CollectableA`) | CLrgScout_TheBarrens | 196 objects, 121 KB; its ambient sound is cut |
  | 3 | Fracturing | an abductor wall, three tiles (`AbductorExtAltWallStrx3_FRACTURED`) | LAbductor_WindingStream | 23 objects, 34 KB; 4 references to its neighbours cut |
  | 4 | Door | an alien door, one tile (`AlienDoor_1Wide_ANIM`) | CSupplyShip_OverlookA | 61 objects, 79 KB (skeletal mesh, animations, sounds) |
  | 5 | Physics prop | a body (`CivFlatC`) | Act2_Pier | 3 objects; the bar has its mesh |

- The wall and the door keep the pose rule: each stands on the bar's tile grid as it stood on its home map's (the
  piece record carries the home grid's corner), moved by whole tiles and storeys.
- The wall's four fracture columns go with it, as a copy's of the bar's own do; what they listed of its home map's
  neighbours is dropped.
- A baked build, 61 seconds: the bush, the nav computer and the wall are lit from nothing (one light of the bar
  each); the door and the body have no baked light (skeletal meshes are lit live); 9 of the bar's own pieces took
  their shadows.
- Installed in the lab copy's test slot with `lab_install.py install` (here `<lab>\bake-fixtures\exp39`, record
  `URB_Bar_X39-20261111-144952.json`): the first mission of a new campaign plays `URB_Bar_X39`.
- Offline, the variant was exported by the viewer's exporter and opened in the editor page: all five draw. The shots
  below are of that export.

## Where to look

Picture `EXP-39-run1-overview.png` (not in the repository): overview.
Picture `EXP-39-run1-close.png` (not in the repository): close.

## Run 1: passed

Played by hand on 11 November 2026: passed. The five families are switched on for every project
(`compiler.FOREIGN_FAMILIES`), and the library was scanned again so its entries say so.

What this run added, and nothing else needed checking:

1. **The map loads**, and all five draw with their own materials (no grey, black or checkerboard).
2. **The bush** gives low cover; a grenade or fire destroys it as it does the bar's own bushes.
3. **The nav computer** gives cover; any damage breaks it.
4. **The wall** gives high cover along its three tiles and blocks sight. A grenade or rocket breaks the part it hits,
   and soldiers then see and walk through the gap; the rest stands.
5. **The door** opens when a soldier walks through it or is told to open it, and closes sight when shut. It stands
   alone (alien doors have no frame); walking round it is expected.
6. **The body** lies on the tarmac and doesn't block the tile.
7. **A save and a reload** after the wall is broken and the door opened bring everything back as it was left.

A piece that fails names its family: that family stays off and the others are switched on.

## Not in this run

- **Cars, doors with a frame and ladders**: built after this run, and in [EXP-40](EXP-40-assemblies.md). Vans can't
  be brought (a van takes its building along).
- **A quick build** of these families: the same pieces without the relight, as EXP-37's props were.

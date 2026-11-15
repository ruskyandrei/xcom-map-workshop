# EXP-42: a van from another map, with the building it takes along

Date: 11 November 2026. The game check of the last family that could not come from another map
(implementation plan, "After X9", step 2). A van is a car with a box
soldiers walk into: besides its parts it has a building volume and floor volumes of its own, which give its box a
floor and a roof and cut them away like a building's. Those volumes are brushes, whose geometry (`Model`, `Polys`)
had no layout.

## What is built (offline)

- **The layouts** ([native_fields.py](../../tools/upk/native_fields.py)): `Model` (a brush's geometry: its owner,
  each surface's material and actor, each zone's actor, its `Polys`), `Polys` (its owner, each polygon's actor,
  material and two names) and `BrushComponent` (cached collision hulls: bytes). Every one of them in URB_Bar,
  TempleShip and URB_PoliceStation reads to its last byte.
- **The transplanter** stages a van's building volume and floor volumes with its parts, in the same call, so the
  building's floors list the staged parts (`transplant.van_volumes`, by the copier's own rule: the building more
  than half of whose residents are the van's parts).
- **The copier needed nothing new**: `native_copy.py` finds the staged building as it finds a van's in the map's
  own, clones it with the parts and edits its lists.
- The project: [exp42_project.py](../../tools/editor/examples/exp42_project.py), built by the Build with the van's
  gate lifted (`--foreign-family van`):

  | Piece | Home map | Parts | What it brings |
  |---|---|---|---|
  | a moving van (`MovingVanCab` and its box) | URB_ResearchOutpost_EWI | 14 pieces, 1 building volume, 2 floor volumes | 126 objects; nothing cut |

- Read back from the built map: the copied building has two floors, each listing only the copy's parts and its own
  floor volume; the building and both floor volumes are in the level's actor list, each with a brush model of its
  own under it. The staged originals are in no actor list.
- A baked build, 133 seconds (the van's 14 pieces are lit from nothing). Installed in the lab copy's test slot
  with `lab_install.py install` (here `<lab>\bake-fixtures\exp42`): the first mission of a new campaign plays
  `URB_Bar_X42`.
- Offline, the variant was exported and opened in the editor page: the van draws whole.

## Where to look

Picture `EXP-42-run1-carpark.png` (not in the repository): the car park.

## Run 1: passed

Played by the user on 11 November 2026: "exp 42 confirmed all looks good". Vans are switched on for every project
(`van` in `compiler.FOREIGN_ASSEMBLIES`), and the library was scanned again.

What this run added, and nothing else needed checking:

1. **The map loads** and the van draws whole, with its own materials.
2. **Its box is a room:** a soldier can be sent inside it by its open side door (the bar's own SUV is parked
   close behind its rear door) and stands on its floor, not on the tarmac under it.
3. **The cutaway:** with a soldier inside, or the camera lowered a level, the roof and the near walls hide as a
   building's do, and come back.
4. **Cover and damage:** the van gives cover from outside; shot or caught in an explosion it burns and blows up
   like the bar's own vans, and its glass breaks.
5. **A save and a reload** with a soldier inside bring everything back as it was left.

## Not in this run

- A copied brush model keeps naming its original's polygon list (`Polys`), as a copied van of the map's own always
  has; the game builds nothing from one.
- Semi-trailers and shipping containers are not vans to the editor (their parts name no partner): their parts
  come one by one, without the volumes that would make them rooms.

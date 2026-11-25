# EXP-41: a linked prop and two prefab pieces from other maps

Date: 11 November 2026. The game check of two ways of bringing a piece that had been refused
(implementation plan, "After X9"). After [EXP-40](EXP-40-assemblies.md)
671 library entries still could not come from another map for one of two reasons, neither of them a limit:

- **243 props list other pieces** (`AffectedChildren`: what a prop takes down when it is destroyed, such as the
  barrels on a pallet or the things on a table). Such a prop now comes alone, with the list emptied.
- **428 pieces are placed by a prefab that also places a building's volumes** (the parts of walk-in vehicles and
  containers: vans, semi-trailers, shipping containers, buses). The piece's archetype lies inside the Prefab asset,
  beside the archetypes of the floor and building volumes, whose brushes can't be brought. The Prefab now comes as
  a shell: itself and the archetypes the brought pieces use, its lists' other entries set to none. The game makes
  nothing from a Prefab at run time.

## What is built (offline)

- The project: [exp41_project.py](../../tools/editor/examples/exp41_project.py), built by the Build with the
  check's gate lifted (`--foreign-family check`). The pieces, in URB_Bar's car park:

  | # | How it comes | Piece | Home map | What it brings |
  |---|---|---|---|---|
  | 1 | List emptied | barrels on a pallet (`BarrelMetalonPalletA`) | URB_MilitaryAmmo | 33 objects, 73 KB; 1 reference cut |
  | 2 | Prefab as a shell | the side wall of a shipping container (`ShipContWallSideA`) | URB_PierA_Terror | 42 objects, 25 KB |
  | 3 | Prefab as a shell | the rear door of a semi-trailer (`SemiTrailerRearDoor`) | URB_Highway1 | 36 objects, 35 KB |

- Read back from the built map: the pallet's copy lists nothing (no entry left pointing at nothing); the two shells
  (`ShippingContainer.Prefab.PRE_ShippingContainerFracture`, `VEH_SemiTrailer_A.Prefab.PRE_SemiTrailer_Car`) are in
  the map with the pieces' archetypes under them and no volume or brush.
- The trailer's door is put 50 units down, on the ground (at home it hangs at the trailer's floor).
- A baked build, 64 seconds. Installed in the lab copy's test slot with `lab_install.py install` (here
  `<lab>\bake-fixtures\exp41`, record `URB_Bar_X41-20261111-160730.json`): the first mission of a new campaign plays
  `URB_Bar_X41`.
- Offline, the variant was exported and opened in the editor page: all three draw.

## Where to look

Picture `EXP-41-run1-carpark.png` (not in the repository): the car park.

## Run 1: passed

Played by hand on 11 November 2026: passed. Both ways are switched on for every project
(`compiler.FOREIGN_UNCHECKED` is empty), and the library was scanned again.

What this run added, and nothing else needed checking:

1. **The map loads**, and all three draw with their own materials.
2. **The barrels on the pallet** give cover and break (or blow up) when shot or caught in an explosion, without an
   error or a hang. Nothing else goes with them.
3. **The container wall** and **the trailer door** give cover, block sight, and break under an explosion.
4. **A save and a reload** after one of them is destroyed bring everything back as it was left.

A piece that fails names its way of coming: that way stays held and the other is switched on.

## Not in this run

- **Whole vans, trailers and containers** with the floor inside them: that needs their building and floor volumes,
  the plan's next step. These pieces come as parts only.

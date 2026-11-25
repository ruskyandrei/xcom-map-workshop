# EXP-13: Destructible props placed by the editor's compiler (plan)

Status (6 November 2026, 14:40): **compiled, not yet built or deployed.** Destructible props
(`XComDestructibleActor`) joined milestone M1: the compiler builds them as it builds static
pieces (EXP-11). This is their in-game check on URB_Bar. The lab's test slot runs one experiment at a time:
[EXP-14](EXP-14-temple-variant.md), the Temple Ship project, goes first.

## Question

Do destructible props that a project copies, moves, turns or deletes stand in the game as the project has them? Do
they give cover, take damage and break like the map's own? Do the places they left open up, with nothing left to
shoot at?

## What changed

- **The compiler** ([`tools/editor/compiler.py`](../../tools/editor/compiler.py)) builds `XComDestructibleActor`. A
  piece that names a partner is refused as milestone M2, whether moved, deleted or copied. On the Bar those are the
  17 car bodies, whose glass (a fracturing piece) is their partner. Temple Ship has none.
- **Nothing changed in the game script.** The copier has copied destructibles since EXP-05 and EXP-07, as
  `XComMapEdDestructible`. A copy takes the source's mesh, materials, toughness, damage and destruction events,
  cover flags, tint and `_Pristine` state. Its absolute-pose mode (EXP-11) refuses only fractured pieces, doors and
  ladders.
  - The hider's exact mode hides a destructible as a level actor, since `XComDestructibleActor` extends
    `XComLevelActor`. It is hidden, its collision is off, it gives no cover and it blocks no line of sight, as
    EXP-07 verified for the bar's furniture and windows.
- **The viewer** marks destructible props as first-build pieces, and a car's body as "Builds from M2".

## The project

`EXP-13 destructible props`, id `d3e1c0a7-13de-4b5a-9c2e-7f1a3b5c8d13`, written by
[`tools/editor/examples/exp13_project.py`](../../tools/editor/examples/exp13_project.py). Revision 1 has 7 added
pieces, 1 moved and 2 deleted. All are in or beside EXP-11's south-west street:

| What | Source | Where (x, y, z) | Rotation |
| --- | --- | --- | --- |
| Dumpster | `XComDestructibleActor_61` (Dumpster_A) | (−1344, −768, 0), a tile corner, as the map's dumpsters stand | 0 |
| Dumpster, turned | the same | (−960, −768, 0) | yaw 45 |
| Trash can, upright | `XComDestructibleActor_29` (Trashcan_E_Closed) | (−1200, −1008, 0), a tile centre | 0 |
| Trash can, knocked over | the same | (−1104, −1200, 23.7), lifted by its radius | roll 90 |
| Box stack | `XComDestructibleActor_292` (BoxStackA) | (−1680, −1008, 0) | yaw 15 |
| Keg | `XComDestructibleActor_13` (Keg_C) | (−1872, −1008, 0) | 0 |
| Trash bag | `XComDestructibleActor_297` (TrashBagA) | (−1488, −1008, 0) | yaw 45 |
| **Moved:** a dumpster | `XComDestructibleActor_62` | one tile north, (−2311, −1341) to (−2311, −1245), inside its fenced lot | turned 90 |
| **Deleted:** a dumpster | `XComDestructibleActor_61`, west of it | (−2691, −1339) | — |
| **Deleted:** a fence section | `XComDestructibleActor_18` (MetalFence) | x −2410 to −2314, y −1437 | — |

- An overlap check against the map's other pieces (their boxes, floors aside) found no collisions. The knocked-over
  can moved from (−1008, −1008) to (−1104, −1200), because the first spot was inside a parked sedan.
- The fence section's neighbours, `XComDestructibleActor_39` (west) and `XComDestructibleActor_89` (east), must stay.
- The dumpster `XComDestructibleActor_61` is the copies' template and is also deleted: a deleted template is still
  copied (sources are read before anything is hidden).
- **Compile:** 1 moved, 2 deleted, 7 added, no errors or warnings. The spec is
  [`tools/patch/examples/exp13destr.json`](../../tools/patch/examples/exp13destr.json). The viewer's preview of it has
  no notes, with 8 copies and 3 hidden.

## Build and deploy (when the game is closed and EXP-14 is done)

The deploy sets everything the test slot needs itself, whatever the previous experiment left there (nothing is put
back after an experiment):
- the first command sets the slot's `Name`, its slot 2 and its time of day. The spec carries `map.timeOfDay` `Day`,
  as the test slot had for EXP-11; EXP-14 leaves Temple's `None`;
- the two `stream` steps set the Bar's slot 0 (`CIN_DropshipIntros`) and slot 1 (`patch_bar`). Slot 5,
  `patch_hide_randomized_objects`, is the same for both maps.

```
pwsh -File tools\patch\patchtool.ps1 all tools\patch\examples\exp13destr.json -Stream 'URB_CommercialAlley_EWI (Commercial Alley Redux) |0' -Slot 2
pwsh -File tools\patch\patchtool.ps1 stream -Map CIN_DropshipIntros -Stream 'URB_CommercialAlley_EWI (Commercial Alley Redux) |0' -Slot 0
pwsh -File tools\patch\patchtool.ps1 stream -Map patch_bar -Stream 'URB_CommercialAlley_EWI (Commercial Alley Redux) |0' -Slot 1
```

## In the game (played by hand, with screenshots taken)

A new campaign; the first mission loads the test slot. Shots (F9):
1. The south-west street from above, with the copies.
2. A soldier beside the copied dumpsters: high cover. Beside the trash can, keg and box stack: low cover, or none.
3. The knocked-over trash can, lying on the ground.
4. The fenced lot: the moved dumpster turned, the deleted one gone, and the gap in the fence with a move path
   through it.
5. A copy shot or blown up: it takes damage and breaks, and its cover goes.
6. Aiming at where the deleted dumpster stood: nothing to hit.

## Pass criteria

1. **The map loads**, with no crash.
2. **The copies stand as posed:** `copied 8 of 8 pieces, each to its own pose`, and at most 0.01 units and 0
   rotation units off, at load and 5 s later.
3. **Exactly the targets are hidden:** `hid 3 of 3 exact targets`, with no warning. The fence's neighbours stay.
4. **Cover and breaking:** the copies give the cover their shapes give, and a copy that is destroyed loses its cover.
5. **Open places:** the deleted dumpster's tiles and the fence gap can be walked through, and give no cover.

## Runs

None yet.

# EXP-11: Static pieces placed by the editor's compiler (plan)

Status (6 November 2026, 14:40): **done; passes.** The user closed it after run 2. Static pieces moved, turned on
all three axes, copied and deleted by the compiler stand exactly as the project has them, and the places they left
open up. Two items were not seen closely (see run 2), and run 2 found F-50: effects the map placed around a moved
piece stay behind. The lab's test slot is back as EXP-10 left it. This is the first in-game check of slice E3 of the
first-editor plan (section 9): a saved project, compiled by
[`tools/editor/compiler.py`](../../tools/editor/compiler.py), built and deployed by patchtool.

## Question

Do static pieces (XComLevelActor, StaticMeshActor) that a project moves, turns on all three axes, copies or deletes
stand in the game exactly as the project has them? Do they block and give cover there, and do the places they left
open up?

## What is new

- **The copier's absolute poses.** Each copy has its own location and full rotator (pitch, yaw and roll). Before,
  copies moved as one group from a pivot, by a yaw in steps of 90 degrees. A source can be copied more than once.
  Each copy's own box is rebuilt.
- **The hider's exact targets.** Only the named base-map actors are hidden, wherever they stand. There is no box, so
  their neighbours stay. Each one's own box is rebuilt.
- **The compiler.** It turns the project into one copier with absolute poses, listed before one exact hider (sources
  are read before anything is hidden). It plans seeds from each copy's box, turned by the full rotation. It refuses
  every piece outside M1 rather than build it partly.

## The project

`EXP-11 static placement`, id `b7f3a2c1-5e11-4c8e-9a3d-2f6e0b1c4d11`, in the projects folder. It is written by
[`tools/editor/examples/exp11_project.py`](../../tools/editor/examples/exp11_project.py), and opens in the viewer like
any other project. Revision 2 has 14 added pieces, 2 moved and 2 deleted:

| What | Source | Where (x, y, z) | Rotation (pitch, yaw, roll) |
| --- | --- | --- | --- |
| Yaw row: 4 street lights | `XComLevelActor_250` (StreetLight_D) | x −1392, −1200, −1008, −816; y −816 | yaw 0, 15, 45, 90 degrees |
| Pitch row: 3 street lights | the same | x −2160, −1680, −1200; y −1488 | pitch 15, 45, 90 |
| Roll row: 3 street lights | the same | x −1872, −1488, −1104; y −1008 | roll 15, 45, 90 |
| Fog pod, off the grid | `XComLevelActor_15` (FogPod) | (−504, −816), 24 units east of a tile centre | 0 |
| Fog pod, off the grid | the same | (−288, −816), 48 units east of a tile centre | 0 |
| Fog pod, floating | the same | (−144, −816), 64 units up | 0 |
| Lamp post, from a deleted template | `XComLevelActor_27` (ParkingLotLightpost_Half) | (−720, −1488) | its own yaw (180) |
| **Moved:** the fog pod | `XComLevelActor_15` | one tile east, (−2067, −621) to (−1971, −621) | unchanged |
| **Moved:** a lamp post | `XComLevelActor_87` | 48 units north, (−2739, −813) to (−2739, −765) | turned 45 degrees |
| **Deleted:** a lamp post | `XComLevelActor_27` | the south-west corner (−2739, −1874) | — |
| **Deleted:** a railing | `StaticMeshActor_60` | the north edge, x −2528 to −1747, y 1824 | — |

- The rows stand on tile centres in the south-west street, between the bar's block and the south curb. They are two
  or more tiles apart, so the lights tipped by 90 degrees lie clear of each other.
- `StaticMeshActor_60`'s neighbours, `StaticMeshActor_61` (west) and `StaticMeshActor_59` (east), overlap it and must
  stay: a box hider would have taken them too.
- The compiler rounds each rotator to whole units (half away from zero): 15 degrees is 2730.667 in the project and
  2731 in the build.

## Build and deploy (6 November, 12:42, game closed)

```
python tools/editor/examples/exp11_project.py
python tools/editor/compiler.py "<projects>\b7f3a2c1-5e11-4c8e-9a3d-2f6e0b1c4d11\project.json" --cache <lab>\viewer-cache --out tools\patch\examples\exp11static.json
pwsh -File tools\patch\patchtool.ps1 all tools\patch\examples\exp11static.json -Stream 'URB_CommercialAlley_EWI (Commercial Alley Redux) |0' -Slot 2
pwsh -File tools\patch\patchtool.ps1 stream -Map patch_bar -Stream 'URB_CommercialAlley_EWI (Commercial Alley Redux) |0' -Slot 1
```

- **Compile:** 2 moved, 2 deleted, 14 added, no errors or warnings. The spec is
  [`tools/patch/examples/exp11static.json`](../../tools/patch/examples/exp11static.json).
- **First build: refused by UDK.** The project's first output names were longer than 30 characters
  (`patch_urb_bar_exp11staticplacement_b7f3`). UDK's Save As then stops at a warning dialog, and the hidden build
  could only wait it out until it timed out (findings register T-09). The names are now kept to 30 characters, and
  the project was saved again as revision 2 with them.
- **Build** took 21 s on the hidden desktop: 4 actors plus the leading Note, saved as `patch_urb_bar_exp11static_b7f3.udk`
  (11,485 bytes).
- **Cook** took 9 s, with only the known `HQSound_MCMusic` error (135,761 bytes).
- **Deploy:**
  - `URB_Bar_EXP11Static_b7f3.upk` is URB_Bar with 310 of the 339 planned tiles seeded; the other 29 already had low
    bits.
  - URB_Bar's 7 landing zones were copied under the new name.
  - The record is at `DefaultMaps.ini` line 6; the test slot is now line 42.
- **Streams:** the record and the test slot both stream 0 `CIN_DropshipIntros`, 1 `patch_bar`,
  5 `patch_hide_randomized_objects` and 2 `patch_urb_bar_exp11static_b7f3`.
- **Backups:** `<lab>\patchtool\backups\DefaultMaps.ini.20261106-124204` (before the record),
  `-124204-2` (before the test slot's slot 2) and `-124246` (before its slot 1); `DefaultLZMutator.ini.20261106-124204`.

## In the game (the user drives, Claude looks)

A new campaign, as in EXP-10. The first mission loads the test slot. Shots (F9):
1. The south-west street from above, with the three rows in view.
2. Close-ups of the tilted street lights (pitch and roll rows) and the floating fog pod.
3. A soldier (not a SHIV) selected, the cursor on a tile beside a fog pod copy: its cover shields.
4. The moved fog pod: its old tile (−2067, −621) is empty, and a move preview can pass through it.
5. The west edge: lamp post `XComLevelActor_87` turned 45 degrees; the south-west corner's lamp post gone.
6. The north edge: the gap where `StaticMeshActor_60` was, with railings left and right of it.

## Pass criteria

1. **The map loads.** `IncrementHistory` names `URB_Bar_EXP11Static_b7f3`, all four streams load, and there is no
   crash.
2. **Every copy stands where the project has it.**
   - The copier logs `copied 16 of 16 pieces, each to its own pose`.
   - At load and 5 s later its pose lines report at most 0.01 units and 0 rotation units from the poses asked for.
3. **Exactly the targets are hidden.** The hider logs `hid 4 of 4 exact targets`, with no WARNING. In the shots, the
   neighbouring railings and lamp posts stay.
4. **The shots match the project.** Each row's lights are turned as listed, the off-grid fog pods sit off the tile
   centres, and one fog pod floats.
5. **Gameplay.**
   - A copied fog pod blocks its tiles and gives cover beside it.
   - The moved fog pod's old tile is open.
   - The deleted lamp post's tile is open.

## Runs

### Run 1 (6 November, 13:15 to 13:17): the added pieces pass; the moves and deletions not yet seen

The user started the mission, took one shot and quit after about two minutes.

- **The shot** (`<lab>\looks\look-131706.png`) shows the south-west street from above:
  - the three rows of street lights, turned, pitched and rolled;
  - the three fog pod copies;
  - a soldier beside them, with cover shields on the tiles next to the pods on the floor.
- **The user's note:** "everything looks right for the added items. the fog pod that is floating above the ground
  has no cover, but that's probably right. not sure if there's a way to indicate this in the editor ?" The viewer now
  marks floating pieces (its changelog, the tile grid); see F-49.
- **The log** (the lab copy's `XEW\XComGame\Logs\Launch.log`, read only):
  - `IncrementHistory` names `URB_Bar_EXP11Static_b7f3`.
  - `CIN_DropshipIntros`, `patch_bar` and `patch_urb_bar_exp11static_b7f3` load with the map. As in EXP-10,
    `patch_hide_randomized_objects` (slot 5) is added a moment later by `AddStreamingMap`.
  - No crash; the game was quit normally at 127 s.
  - The copier logs `copied 16 of 16 pieces, each to its own pose`. Its pose lines report `at most 0.0000 units and 0
    rotation units from the poses asked for`, both at load and 5 s later.
  - The rotators as built: yaw 2731, 8192 and 16384; pitch and roll the same values.
  - The hider logs `hid 4 of 4 exact targets`, with no warning: `StaticMeshActor_60`, `XComLevelActor_15`, `_27` and
    `_87`.
  - The tile rebuilds around the 16 copies, the 4 hidden targets and the 14 seeded boxes (339 planned tiles) all
    finished at 24.40 s.
  - The only warnings are the two known "Failed to load ObjectArchetype ... FracturedSkinnedComponent0" lines
    (EXP-07).

| Criterion | Run 1 |
| --- | --- |
| 1. The map loads | **Pass** |
| 2. Every copy stands where the project has it | **Pass** (0.0000 units, 0 rotation units, at load and 5 s later) |
| 3. Exactly the targets are hidden | **Pass in the log**; the neighbours (railings 59 and 61, the other lamp posts) are not in the shot |
| 4. The shots match the project | **Pass** for what the shot shows: the rows turned as listed, the pods off the tile centres, one floating |
| 5. Gameplay | **Partly.** The copied pods on the floor give cover; the floating pod gives none (F-49). The moved pod's old tile and the deleted lamp post's tile are not checked |

**Still to see** (shots 4 to 6 of the list above):
- the moved fog pod's old tile, (-2067, -621);
- the west edge: lamp post `XComLevelActor_87` turned 45 degrees, and the south-west corner's lamp post gone;
- the north edge: the gap where `StaticMeshActor_60` was, with the railings either side.

### Run 2 (6 November, 14:16 to 14:18 and 14:33 to 14:37): the moves and deletions; the experiment closed

Two short sessions, 8 shots. For the second, the user found the game's cursor readout, `Cursor @ (x, y, z)` with the
tile `(x, y, level)`. It is in the map's grid: tile x is (x + 2784) / 96, tile y is (y + 1920) / 96, and the level is
z / 64, rounded down. So the spots were given to them as tiles.

- **Both logs** pass as run 1 did:
  - `IncrementHistory` names `URB_Bar_EXP11Static_b7f3`;
  - `copied 16 of 16 pieces, each to its own pose`;
  - the poses are at most 0.0000 units and 0 rotation units off, at load and 5 s later;
  - the hider logs `hid 4 of 4 exact targets`, with no warning, and the three tile rebuilds finish.
- **The first session's shots** (`look-141717` to `look-141748`) show the added pieces again: the rows, the pods
  with cover shields beside the two on the floor, and a move path past the knocked-over street light.
- **The moved fog pod's old tile** (`look-143622`, cursor at tile (7, 15)): the pod stands one tile east. The user's
  note: "can path through but there's some green smoke emitter still going". The smoke is not the pod's:
  - The map placed it as separate actors around the pod: five emitters `Emitter_39`, `_43`, `_48`, `_49` and `_50`
    from `PRE_Pod_Smoke` (with `PrefabInstance_12`), the point light `PointLight_8`, and the decals `DecalActor_6`,
    `_8` and `_10`.
  - The project moved only the pod's mesh actor. The export has no emitters or decals, so neither the viewer nor the
    compiler links them to the pod. This is F-50.
- **The south-west corner** (`look-143649`, cursor at tile (0, 0)): no lamp post, and the move path reaches the
  tile.
- **The north railing** (`look-143725`, cursor at tile (5, 36)): the low wall `StaticMeshActor_59` (east) stands,
  and the gap where `StaticMeshActor_60` was runs from it towards the trash enclosure.
- **Not seen closely:**
  - Lamp post `XComLevelActor_87`, turned 45 degrees at tile (0, 12). `look-143637` shows that edge but does not
    single it out; its pose is confirmed by the log.
  - The west railing end, `StaticMeshActor_61`, behind the trash enclosure.

| Criterion | Result (runs 1 and 2) |
| --- | --- |
| 1. The map loads | **Pass** |
| 2. Every copy stands where the project has it | **Pass** (0.0000 units, 0 rotation units, in all three sessions) |
| 3. Exactly the targets are hidden | **Pass**: the log, and the railing's east neighbour in the shot. The west end piece was not seen |
| 4. The shots match the project | **Pass** |
| 5. Gameplay | **Pass:** the pods on the floor give cover, the floating one none (F-49). The moved pod's old tile and the deleted lamp post's tile are open. The pod's smoke stays behind (F-50) |

**Afterwards:** the lab's test slot (`DefaultMaps.ini` line 42) is back as EXP-10 left it: `URB_BarBlank`, with
`patch_exp08blank`. Its line was taken from the backup `DefaultMaps.ini.20261106-124204-2`, after the current file
was backed up as `DefaultMaps.ini.20261106-143952-before-exp11-restore`; only that line changed. The variant's record
(line 6) and `URB_Bar_EXP11Static_b7f3.upk` stay. The record is not in rotation.

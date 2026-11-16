# EXP-60: Temple Ship's arches with Mouse picks it on

Date: 16 November 2026. The piece flags plan's first in-game probe (P7, its run 2: the Temple Ship), played by the
user: the editor's **Mouse picks it** flag turned on for pieces Firaxis saved it off on, so the mouse can send a
soldier onto them. It is F-102's fix made through the editor's Flags instead of
[cursor_pick.py](../../tools/upk/cursor_pick.py), and the first play of any flag ([F-114](../findings-register.md)).

## The build (offline)

The user's project `temple_improved` (TempleShip, revision 17, in the editor's project store), a quick build from
branch `piece-flags` (`TempleShip_TempleIm_2001-20261116-152422`, the variant's SHA-256 starting `5d4f061056de`). Besides
its other edits (33 pieces added, 7 deleted), it turns Mouse picks it on for 68 of the map's level actors, nothing
else of their flags changed:

| Mesh | Pieces |
| --- | --- |
| `knuckleWorm_Open` (the arches) | 40 |
| `alienKnuckleDiagnol` | 22 |
| `AlienBase_RampD` | 6 |

The compiler took all 68 with no warning (mouse only: no tile changes, no floor or ladder check). The Build's writer
changed `bIgnoreFor3DCursorCollision` from true to false on each actor itself (they save it true; a same-size change),
read all 68 back from the written map with a fresh reader, and did no tile work, as the mouse changes no tile. The
map's export (export 27) has 1,315 components with the mouse off; the project turns it on for these 68 only.

## Run 1

**Passed for what it shows** (16 November 2026, played by the user): "tested the temple arches with mouse picking on
and they seem to work well".

The user's shot (`EXP-60-arch-top.webp`) shows a soldier standing on top of an arch, with the move path running along
the arch's top to the cursor's box at its far end, and the move's area outlined on the arch's top. So the cursor lands on an arch with the flag on, and a soldier can be sent onto it and along it,
which the map as shipped doesn't allow (F-102: the pick skips the arches and lands on what is under them).

Against the plan's list for this run, not told by run 1:
- **Mouse off at the same place.** Taken as the map's own behaviour, from the report behind F-102; not played side by
  side in this build.
- **The floor under an arch.** Whether a tile under an arch can still be clicked where the arch's top lies in the same
  cursor storey (F-102's reading: there the arch wins, which is likely why Firaxis turned the arches off).
- **The cursor's height on the arches' curves**, and an arch cut away by the camera.

What it decides: the mouse checkbox works on the arches in the game, which is the condition the plan sets for
retiring `cursor_pick.py` (P8), with the floor-under-an-arch case left to note if it shows up in play.

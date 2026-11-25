# EXP-92: terror civilians on a map with its UFO deleted, and the copied floor's patch, in the game

Date: 22 November 2026. Status: **played: on the build without the fix 2 of 18 civilians started in the air (one at
the deleted UFO's roof, 421 over the ground, one at its low wing's height beside the helipad); on the fixed build
none of 36 in two battles, and the copied floor south of the helipad shows no dark patch** ([F-157](../findings-register.md),
[F-158](../findings-register.md)). Played unattended in the lab copy (the game-test skill), one pass of each check
and at most one second take.

## The questions

1. Do terror civilians still start where the deleted UFO's floors were (F-157), with the Build writing the tiles near
   its changes as the battle's rebuild will leave them?
2. Does the copied rubble floor still show the black patch south of the helipad (F-158), with the relight lighting a
   copy's texels buried only where its original stands?

## The maps

The reported user's project (a variant of CLrgScout_City: the crashed UFO deleted, an EXALT helipad copied onto its
place, 166 copies; kept in `private/reports/`, a user's work), built twice the same day from the same project:
"A" by main before the fix (a quick build: its tiles are a full build's), "B" by the fix's branch with the bake.
Each staged in the lab copy in turn by Play in game on a test server with `--dry-play` and the lab copy as its
install (the folder Steam ran held a campaign copy, never touched), its Terror mission (the record out
of rotation, five Sectoid pods, the test squad, the civilians' looks line), then started hidden with that play file.
LWR 2.06 in the lab copy. The lab copy's test slot held an earlier staging's record and was reset first.

## Runs

Each: the battle to turn 1 after the intro; `getall XComCivilian Location` (a civilian's place is the middle of its
pawn, 64 over its feet: `getall CylinderComponent CollisionHeight` is 64 for every one); a picture of each civilian
read as in the air.

| Battle | Build | Civilians read | In the air | On the helipad's top | Elsewhere |
| --- | --- | --- | --- | --- | --- |
| A1 | before the fix | 18 | 2 | 0 | 16 on the ground |
| B1 | fixed | 18 | 0 | 1 (feet 69) | 17: 12 on the ground, 2 on low steps, 2 on a building's upper storey far from the UFO's place (feet 391, its floor at about 388), 1 inside a broken low-walled room on its rubble |
| B2 | fixed | 18 | 0 | 0 | 18: 17 on the ground, 1 on that upper storey |

- A1's two: one at (538, 6011), feet 421: the deleted UFO's roof (its stored cover points stood at 414 to 451). The
  picture shows him drawn far larger than the civilians on the roof below, nearer the camera, with nothing under
  him. The other at (1487, 6387), feet 64 exactly (every civilian on the ground reads a fractional height), south of
  the helipad, where the UFO's low wings had their floor: the pictures, one second take included, could not show
  whether she stands on anything, so she counts in the air by her height alone.
- B1, a picture of the rubble floor south of the helipad, west of an AC unit (where the user's picture showed a dark
  rectangle): lit like the floor round it, no patch.

## What it shows

- F-157: the stored tiles of the deleted UFO put terror civilians in the air, as read offline; with the Build
  writing the tiles near its changes they start on real floors only, the helipad's top among them.
- F-158: the copy's patch is gone in the game too, as the rebuilt map's lightmap reads.
- Not looked at: the pods' other aliens (placed from the same stored tiles), and plain Enemy Within.

# EXP-91: a map with copies sized to what they read, in the game

Date: 22 November 2026. Status: **played: the map built with the fix loads, its copies look as the build from before
the change shows them, near and at the far zoom, and the game holds 275 MiB less in textures and about 300 MiB less
private memory; a quicksave crashes the game on this project's map in both builds ([F-156](../findings-register.md),
KB-17), not on the game's own map**. The smaller built maps plan's stage S4 ([F-151](../findings-register.md)).
Played unattended in the lab copy (the game-test skill), one pass of each check and at most one second take.

## The questions

1. Does a map whose copies have lightmaps and shadow maps of their own size (hundreds of small NeverStream textures
   inside the map) load and play?
2. Do the copies look lit as before? A copy's top mip holds its source's bake texel for texel (checked offline); its
   lower mips are now made from its own texels, where they were the atlas's, so a difference would show at the far
   zoom.
3. How much texture memory and private memory does the game hold, against the same project built before the change?
4. Does a soldier walk among the copies, and does a save load?

## The maps

The reported user's project (a variant of CLrgScout_City: 166 copies, 119 of them pieces of other maps, light edits;
kept in `private/`, a user's work), built twice with the same code but for this change, the same day: "A" on branch
smaller-maps (55.8 MB, lightmaps inside the map 23.6 MB), "B" on main before it (340.8 MB, 306 MB). Each staged in the
lab copy in turn (`lab_install.install` with the lab copy named: the folder Steam ran held the user's own campaign
copy, which was playing, and was never touched). LWR 2.06 in the lab copy, `--map SkyscraperTerror --no-aliens
--saving`, the test squad.

## Runs

Each: the battle to turn 1; the fog lifted; four places where the copies stand thickest (world units (1536, 5376),
(768, 5376), (1536, 6144), (0, 5376)), each with `ViewLocation` and a yaw of 45 at the play camera's distance and
again pulled back to 3,000 at -60; `ListTextures`; the game's private memory at turn 1 and after the tour.

| | A (fixed) | B (before) |
| --- | --- | --- |
| LoadMap to the level up | 0.95 s (0.44 s bringing it up) | 1.25 s (0.48 s) |
| Private memory at turn 1 / after the tour | 1,191 / 1,213 MiB | 1,491 / 1,468 MiB |
| All textures in memory (`ListTextures`) | 220 MiB of 2,613 | 495 MiB of 2,613 |
| The map's own textures in memory | 34.8 MB of 641 (22.5 MB NeverStream) | 308.9 MB of 641 |

- **Pictures.** At every place, near and far, A and B show the same scene: the same pieces, shading, shadows and
  colours, nothing black, pink, blotchy or blocky. Under 1% of the pixels outside the interface differ by more than
  48 levels (fires, smoke, a drone's glow). The whole picture's brightness moves by up to about 8 levels between the
  runs, both ways from place to place (A brighter at two places, B at the others), over the map's own ground too, whose
  lightmaps are byte for byte the same in both builds; two shots of one place in one game differ by as much (the
  fires' light flickers). No difference at the far zoom, where the copies' new lower mips would show.
- Two sharp-edged dark patches of ground beside the helipad are in both builds alike: the project's, not the change's.
- **Walk.** A soldier put among the copies walked two tiles ("stands on").
- **Save.** A quicksave crashed the game 0.2 s after F10, in the checkpoint's serialisation, in A twice and in B once
  (`XComEW.exe+0xa0ff2b`, the same stack each time), right after turn 1 with nothing moved. The game's own
  CLrgScout_City in the same session setup saved and loaded. Not the change's: [F-156](../findings-register.md).

The hidden run's `send`, `aim` and `goto` read the log of the folder Steam runs unless given `--game` too (the skill
names it on the start command only): with the user's copy there, they printed its log (only read) until given it.

## What it settled

F-151's fix plays: the map loads, its copies look as before, and the battle holds 275 MiB less in textures. F-151 is
verified. Saving this project's map crashes the game whatever the change: F-156, open.

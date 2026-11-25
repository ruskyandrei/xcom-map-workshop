# EXP-91: a map with copies sized to what they read, in the game

Date: 22 November 2026. Status: **played: the map built with the fix loads, its copies look as the build from before
the change shows them, near and at the far zoom, and the game holds 275 MiB less in textures and about 300 MiB less
private memory; a quicksave crashed the game on this project's map in both builds, not on the game's own map: the
map's tiles named actors the Build took out of the level ([F-156](../findings-register.md)), and with the Build
clearing them the map saves, loads and saves again**. The smaller built maps plan's stage S4 ([F-151](../findings-register.md)).
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
lab copy in turn (`lab_install.install` with the lab copy named: the folder Steam ran held a campaign
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
names it on the start command only): with the campaign copy there, they printed its log (only read) until given it.

## The save crash (F-156), the same day

The crash site is `UObject::IsA` given freed memory, called by the save archive's writer of an actor reference.
Read offline, the built map's tile data named actors the Build had taken out of the level: the deleted building's
two floor volumes (1,233 tiles) and deleted floor pieces (3,102 tiles), some outside every rebuild volume, and 66
interact points of deleted interactive pieces. No tile of the install's 96 maps names anything outside its level.

| Run | Map | Quicksave |
| --- | --- | --- |
| control | the game's own CLrgScout_City | saved and loaded |
| B save | the project built on main before F-151's fix | crashed (`+0xa0ff2b`) |
| quick | a quick build of the project | crashed (`+0xa0ff2b`) |
| quick, tiles cleared | the same with every such tile reference set to none, nothing else | saved and loaded |
| full, fixed | a full build with the Build's own clearing (F-156's fix) and F-151's | saved, loaded, saved again |

After the fixed build's load the helipad looked as before the save, near the copies at the first place. The saves'
thumbnails in the load list are the game's badge, where the control's is a picture of the map: the game has no
picture for the variant's name.

## What it settled

F-151's fix plays: the map loads, its copies look as before, and the battle holds 275 MiB less in textures. F-151 is
verified. The save crash was the tiles naming actors the Build took out of the level, in every build of a project
that deletes such pieces, with or without F-151's fix; the Build clears them now and the map saves: F-156 is
verified.

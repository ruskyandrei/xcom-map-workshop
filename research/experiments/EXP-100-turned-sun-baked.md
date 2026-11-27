# EXP-100: a turned sun built with baking, in the game

Date: 27 November 2026. Status: **played: five checks passed, one failed** ([F-203](../findings-register.md), open;
[F-202](../findings-register.md) accepted). Played unattended in the lab copy (the game-test skill), with a control
run on a map as the game ships it.

## The questions

The game-likeness plan's stage T-S5 (the sun plan's S5) shows in the game what stage T-S4's baker makes of a turned
sun, and T-S6's sky choice:

1. Do the map's baked shadows fall from the new side: on the ground, and of buildings on each other?
2. Does a soldier walking in and out of a building's new shadow darken in it (the light's map of the level and the
   lighting samples' marks, made again)?
3. What happens to a breakable piece's shadow when it breaks?
4. Does the chosen sky show, and does the copy under the map (F-202) show anything odd?

## The map

URB_Bar built with baking by [exp99_project.py](../../tools/editor/examples/exp99_project.py) (`--time 08:00 --heading
223 --sky day --full`) from an export 45 of Bar, read from the lab copy, under its own name URB_Bar_Sun_100a (the lab
copy's test slot held EXP-99's name): the sun (255, 161, 72) at 1.0, 20.7 degrees up, travelling toward game (+0.89,
-0.27), where Bar's moon stood 80.7 degrees up toward -X, +Y. The Build took 58.7 s: 714 shadow maps of the sun traced
again, the light's map of the level made again, 600 lighting samples' marks changed, 9 pieces given shadow maps of their
own (F-198), Bar's two night-sky domes replaced by copies of URB_TruckStop_EWI's noon dome. Staged with
`lab_install.install(..., game=<the lab copy>)` (the slot's record took Day); the folder Steam ran held the user's LWR
v3 copy, whose game was open the whole time and never touched. LWR 2.06 in the lab copy.

## Runs

1. **The map loads**: turn 1, the squad on the east car park; the game reads the light's new Rotation, colour and
   brightness. Passed.
2. **The buildings' shadows on the ground**: from the three likeness cameras and straight down, where EXP-99 had a band
   about a tile wide under the bar's wall, its shadow now covers the whole pavement and most of the road toward +X, its
   side edge along the sun's direction; cars, lamp posts and bushes all throw long shadows the same way. The edge runs
   at least about 700 units on the ground (the bar's top storey about 390 up predicts about 1,000; the far end is lost on
   the dark road). Passed.
3. **Shadows on each other**: the tall blocks to the -X side shade the bar's west roof and wall, with sunlit stripes
   where the sun passes between them; rooftop units and the parapet cast onto the sunlit roof. Passed.
4. **A soldier in and out of a building's shadow**: not darker in the shadow. Failed. With one soldier moved only by
   TeleportToCursor, the same facing and camera, between a tile in the bar's new shadow and one in the sun: torso armour
   (85, 123, 133) against (78, 116, 126), the near shoulder pad (114, 147, 150) against (111, 139, 142), while the
   ground under him goes from grey (81, 70, 72) to orange (102, 64, 60). The soldier shows no orange from the sun on the
   sunlit tile either. He still casts a composite shadow of his own onto the shaded pavement.
   - **Control on URB_CommercialStreet as the game ships it** (its sun 39.4 degrees up), the same way: the soldier is
     clearly darker in a building's shadow: his blue armour (63, 100, 141) against (86, 139, 169) in the sun, shoulder
     pads (73, 108, 164) against (112, 174, 211). So the game's own maps darken moving things in shade, and the failure
     is the Build's.
   - **What the Build wrote there** (read offline): at the shade tile the light's new map of the level says shadow at 16,
     64 and 128 units up and the four nearest lighting samples are marked shadowed; at the sun tile, lit and unmarked:
     the same pattern as URB_CommercialStreet's own data at its two tiles. The game holds the new map's header
     (`getall` read the new direction, box and size). Bar's Long War patch levels hold no lighting samples.
5. **A breakable piece's shadow**: it stays as baked. An HE grenade turned an SUV into a burnt wreck with the ground
   along the sun's direction unchanged; three concrete parking blocks a grenade broke each left a dark block-shaped
   mark on the asphalt. The game's own maps keep baked shadows the same way.
6. **The sky**: a light blue day sky with thin white clouds where Bar had its night sky (the top of the frame toward the
   sun about (219, 235, 246)). Passed.
7. **F-202**: nothing odd. The game holds the two copies (upright and turned over, both the noon dome's full size) and
   none of Bar's domes; from far and high on four sides everything below the horizon is one flat colour, the map's fog
   (the curve's low-sun fog), up to a sharp line where the sky starts, and from below the map the fog's colour alone.

## Follow-up runs (F-203)

- **A red sun, quick Builds**: URB_Bar and URB_CommercialStreet built quick with the sun pure red at brightness 2, each
  in its own direction, and the units-only sky light at 0. On Commercial Street the soldier is lit red in the sun
  (a shoulder pad (65, 59, 75) against (51, 80, 123) in a building's shadow). On Bar the ground, walls and vehicles in
  the sun turn red, but the soldier was lit red on no tile (one faint red first shot aside), standing on red pavement.
- **Indoors and outdoors**: in a later session of the same red Bar the soldier was lit red at every place tried (the
  open car park, the pavement, inside the bar under its roof), one light environment throughout with the same
  readable settings; only the pawn's CurrentBuildingVolume changed indoors. Commercial Street the same: one light
  environment indoors and out.

So on Bar the sun's shadows never darken units, with or without the bake, and whether its light reaches them at all
differs between sessions. The cause is not settled.

## What it settles

A turned sun built with baking shows in the game on the map itself: its shadows on the ground and on the buildings, and
the sky chosen. Moving things are not darkened in its shadows on Bar (F-203), but neither are they in a quick Build
that keeps the moon's direction: it is how Bar's units take its sun, not the bake. What decides it is not settled.

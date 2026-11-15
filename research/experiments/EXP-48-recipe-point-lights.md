# EXP-48: point lights made from the editor's recipe

Date: 12 November 2026. Stage L1.3 of the prefabs and buildings plan: one look in the
game at a recipe point light. Every light of a prefab is a recipe light since stage P, so the recipe is looked at
before more is built on it. The recipe is in [spot-light-recipe.md](../spot-light-recipe.md), section 5. (EXP-46 and
EXP-47 are the plan's names for later runs.)

The stage is the blank map, which has no point or spot light of its own: nothing here could be a copy.

## What is built (offline)

- [exp48_project.py](../../tools/editor/examples/exp48_project.py): EXP-44's hut as it was, and three lights, each
  with every value saved:

  | | Light | Where (x, y, z) | Colour | Radius | Brightness |
  |---|---|---|---|---|---|
  | 2 | point, recipe 1 | -96, 864, 160: over open ground, north of the squad | green (80, 255, 120) | 520 | 2 |
  | 4 | point, recipe 1 | 672, 1248, 128: inside the hut, the middle of the room | warm (255, 170, 80) | 420 | 2 |
  | 3 | spot, recipe 1, pointing down | -96, 1440, 256 | blue (90, 150, 255) | 640 | 2 |

  The spot is the known case (EXP-26), there to compare the point lights with.
- **A full build, the lighting baked**, 22 seconds: `CB2_MP_Blank_X48`, in the editor's builds folder as the
  project's last build. The lights are listed in 21 receivers' lightmaps; one piece in reach has no texture
  lightmap.
- **Read back from the built map**: `PointLight_0` and `PointLight_1`, class `PointLight`, static, at the places,
  radii, brightness and colours above, each component with the archetype
  `Engine.Default__PointLight.PointLightComponent0` and a `LightSourceRadius` of 32; `SpotLight_0` likewise with the
  spot's. The build made eight imports (the two kinds' classes, default objects and component archetypes): the map
  had none of them.
- The bake took each light's source radius as 32, the value the light saves (F-91, fixed before this build).

## Where to look

Picture `EXP-48-overview.png` (not in the repository): the three lights on the blank map.

Picture `EXP-48-hut.png` (not in the repository): inside the hut.

Open the project **EXP-48 point lights** in the editor, then Project, Play in game. (To rebuild from the script:
`python -B tools/editor/examples/exp48_project.py <scratch folder> --store`.)

What this run adds:

1. **The map loads** with the two point lights in it (the log is read afterwards for missing imports or objects).
2. **The green point light (2) lights the ground** where the editor shows it: a round pool, brightest under the
   light, fading out about five tiles away. Lit once, not doubled.
3. **A soldier walking through the green pool is lit green**, and not when well outside it.
4. **The warm point light (4) lights the inside of the hut**: the floor, the walls' insides, the crates, a soldier
   standing inside.
5. **Beside the blue spot (3)**, do the point lights look like the same kind of light: as bright for their values,
   no flicker, no hard square edge to the pool, no light where there should be none.
6. Anything odd.

## Result: passed (12 November 2026)

Played by the user in the lab copy: "yes everything checks out", of the six points above. No look was taken with
F9, so there is no picture of the run.

The game's log of the run (`<lab copy>\XEW\XComGame\Logs\Launch.log`, closed 00:47): `CB2_MP_Blank_X48` loaded
and came up for play, with no "Bad import", no failed load and no missing object that names a light, a light's
class or its archetype. What it does warn of is not the lights': the three shed walls' collision cooked at load
(the hut's fracturing pieces), the menu's `XComUIShell` package not loaded (a battle started straight on a map
has no menu), and 20 lines of `Texture None.undefined` from the battle's interface as it starts.

Stage L1.3 is done, and with it stage L1: a prefab's lights can be built on.

Not looked at in this run: a build without baking (a recipe point light follows the spot's contract there: EXP-26),
a save and a reload (F-89), a prefab placed from the library (stage X).

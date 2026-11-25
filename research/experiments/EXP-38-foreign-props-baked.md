# EXP-38: the two props from other maps, their lighting baked

Date: 11 November 2026. The game check of a full build with pieces from other maps
(implementation plan, X8's gate). [EXP-37](EXP-37-foreign-props.md)
showed that the game takes such a piece as one of the map's own; there each prop kept the light of its home map.
Here each is lit from nothing for where it stands. What no offline check can say is whether that light looks right
beside the map's own baked pieces.

## What is built (offline)

- The same edit as EXP-37, [EXP-37-edit.json](EXP-37-edit.json): the lamp post of URB_PoliceStation and the alien
  wall panel of CAbductor_Cliffside, at the same two places in the bar's car park.
- The build, two commands:
  - `python -B tools/bake/transplant.py <LWR cooked>\URB_Bar.upk <out> --edit EXP-37-edit.json`, as in EXP-37;
  - `python -B tools/bake/native_copy.py <out>\staged\URB_Bar.upk <out>\build URB_Bar_X38 --copies
    <out>\native-edit.staged.json --bake --cache Lighting_3800001 --receivers-near 600`: the copies made, then the
    relight (`relight.py --foreign-copy`).
- What the bake did to the two props (from `<out>\build\URB_Bar_X38.relight.json`):
  - **Their light lists.** The lamp post's lightmap listed 3 lights of the police station and the wall's 30 of
    the alien ship. Each now lists one: the bar's one point light that reaches it there.
  - **Their lightmaps.** Each is our light on it where it stands (that light, the car park's area lights, one
    bounce). The lamp post's flat light goes from a median of 0.13 (its home's) to 0.29, the wall's from 1.60 (the
    alien ship's) to 0.21. A piece of the bar's own beside them (`XComLevelActor_30`) has 0.21.
  - **The wall's shadow map** named the alien ship's dominant light; it now names the bar's, and holds the whole
    field of the bar's moonlight on it (1,361 texels: 1,179 on the shadow side, 182 lit). The lamp post had no
    shadow map in its home map and has none here.
  - **Their shadows on the map's own pieces:** 12 pieces of the bar around them relit and 6 of their shadow maps,
    as for any copy.
  - The staged pieces (in the package, in no level) are left out of both scenes.
- Deployed to the lab copy's test slot with `deploy_fixture.py` (here `<lab>\bake-fixtures\exp38`, record
  `URB_Bar_X38-20261111-141532.json`): the first mission of a new campaign plays `URB_Bar_X38`.
- Offline, the variant was exported by the viewer's exporter and opened in the editor page: both props draw. The
  shots below are of that export; the editor doesn't draw baked light, so they show where to look, not the result.

## Where to look

Picture `EXP-38-run1-overview.png` (not in the repository): overview.
Picture `EXP-38-run1-close.png` (not in the repository): close.

## Run 1: passed

What this run adds to EXP-37, and nothing else needs checking:

1. **The lamp post** is lit as the cars and the kerb around it: not a dark shape, not glowing.
2. **The alien wall** has the car park's dim light, darker on the side away from the moon. No bright patch left
   from the alien ship, no black patch, no hard-edged blotch on its face.
3. **The ground between them** carries each prop's shadow, as it carries the cars'.
4. If either prop stands out from the map's own pieces, a screenshot of it beside a car is the result. The plan's
   fallback is then to light pieces from other maps live, decided with that shot.

Result (11 November, the lab's test slot played by hand, with a screenshot): **passed.** In the shot the
alien wall is as dark as the cars beside it, with no bright patch from the alien ship and no black one, and the lamp
post stands lit as the car park is.

- What it settles: a piece of another map can be lit from nothing by our bake and sit beside the map's own baked
  pieces. The fallback (lighting such pieces live) is not needed for plain props.
- Not looked at closely: each prop's shadow on the ground (item 3); nothing in the shot or the report says it is
  wrong.

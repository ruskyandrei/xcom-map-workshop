# EXP-21: the light model across a whole room (baker step L5)

Date: **7 November 2026**. Status: **offline findings 1–9; run 1 passed (a large remix relit as a change shows no
seams in the game): L5 done for maps with an original bake**. Design:
standalone baker, section 13, step L5. Tool:
[`room_match.py`](../../tools/bake/room_match.py).

## Question

An edit is relit as a change on the original bake, so small edits look right even where our model is off. A remix
that changes most of a room needs the model itself to match Lightmass. EXP-17 run 7 relit the whole bar room and
matched too poorly to try in the game. What does our model get wrong, and what fixes it?

L5 is done when a whole-room checkerboard (EXP-17 run 7's 192-unit cubes, ours against the original) shows no
squares in the game. Offline that means most texels in groups within 10%; run 6's floor, which showed no squares,
had 69% of its texels within 10%.

## The yardstick

`room_match.py` relights components absolutely, writes nothing, and compares with the original bake at every texel
the relight would write. The bar room is [`bar-room-components.txt`](../../tools/bake/examples/bar-room-components.txt),
178 components. `--parts` splits our light into its sources, `--texels` saves every texel for fitting offline.

**Baseline** (the relight as it is: shadows, the emissive surfaces' generated stand-in lights, one bounce with spot
cones doubled for bounce sources, the environment at 0.266):

| Surfaces | Lit texels | Within 10% | Within 40% | Ours / original |
|---|---|---|---|---|
| All | 310,823 | 23.7% | 43.5% | 0.77 |
| Floors | 89,606 | 58.9% | 78.7% | 0.97 |
| Walls | 191,963 | 9.8% | 28.1% | 0.61 |
| Ceilings and undersides | 29,254 | 7.9% | 36.6% | 0.75 |

Checkerboard: 24.6% of texels in groups within 10%. These are run 7's figures.

## Findings so far

1. **The texels that bounce lights are the problem.** By the source that gives most of our light at a texel:
   direct 32% of lit texels (58.5% within 10%, ours 0.98), emissive stand-ins 10% (12.6%, 0.81), bounce 49%
   (6.8%, 0.57), environment 10% (6.0%, 0.52).
2. **Scales don't fix it.** The best scale per source over the room gives 33.2% (bounce ×1.72, environment ×2.5);
   per facing 36.0%; one scale per component 35.4%. Bounce split by the kind of light it starts from, the best
   scales are spots ×1.5, points ×1.5–2.4, the emissive stand-ins ×3.2–3.6, and the room still reaches only 34%
   (walls 22%).
3. **Our walls have the wrong shape.** After the best scales, walls are too bright near the floor and too dark near
   the ceiling: median log2(ours / original) +0.38 at 0–64 units, −0.28 at 320–384. Undersides lower than 16 units
   (the bottoms of things standing on the floor) get about 1/25 of the original's light.
4. **A photon map's estimate doesn't explain it.** EW's `XComLightmass.ini` estimates bounce sources from photons
   (`NumIrradianceCalculationPhotons` 400, `DirectPhotonSearchDistance` 200, `PhotonSearchAngleThreshold` 0.5).
   [`bounce.SourceIrradiance`](../../tools/bake/bounce.py) with the photon map's own estimate (`estimate='density'`:
   the light over the disc's whole area, so it falls where the surface ends) at 200 units: 23.1%, and walls worse at
   the foot (+0.59).
5. **The bounce sources' samples were wrong in a way that hid this.** Samples spread over every triangle include
   floor under walls and crates and faces sunk into others, all dark. At one wall's gather hits the source gave 0.75
   of the exact light. Buried samples are now dropped (`bounce.buried_texels`), and it gives 0.92. A box limits the
   samples to the room: the bar map's triangles cover 4.2 billion square units, mostly far terrain, which left
   8,700 samples in the bar.
6. **A second bounce adds little.** Two bounces through the sources raise one bar wall from 0.50 to 0.54 of the
   original.
7. **Our albedos may be too dark.** The bar's biggest surfaces take their albedo from their diffuse texture: brick
   (0.22, 0.07, 0.05), the wood floor (0.35, 0.13, 0.01), the pub wall kit (0.045, 0.027, 0.02). Their parents
   (`BLDG_Enterable`, `BLDG_Floors`, `PROP_Objects`) also take a `Diffuse_Mod` texture and switches like
   `DualDiffuse`, and the cooked game keeps no expressions to say how they combine. Lightmass reflects light by the
   material's whole diffuse output.

8. **Fitting albedos helps, but not enough, and leaves the shape.** The gather now splits the bounce by the material
   it bounced off (`bounce.gather(groups=...)`, `room_match.py --bounce-by-material`). One multiplier per material
   (the 30-odd that carry 0.2% of the bounce or more, the rest together), plus the stand-ins and the environment,
   fitted on half the components (lightly held towards 1) and judged on the other half:
   - fitted half: 29.1% → 40.5% within 10%;
   - judged half: 12.3% → 22.6% (walls 9.2% → 21.6%, ceilings 5.5% → 18.3%, floors 33.1% → 30.5%);
   - the wood floor ×1.66, the brick ×2.09, the sidewalk ×2.21, the environment ×2.31; the bar counter ×0.55;
     a few small props ×3–8;
   - the walls' gradient stays: +0.42 at the foot, −0.44 at the top.
9. **The stand-ins aren't the lamp shades.** Of the 137 generated stand-ins, 83 are in the bar: 39 point up from
   36–41 units above the floor (by the arcade and claw machines), 42 point sideways (56–283 units up, along the
   walls), and only 2 point down from 342 units. Each is owned by the WorldInfo, so the meshes they stand for aren't
   linked. Lightmass lights from the emissive surfaces themselves (mesh area lights), which these single spots
   approximate only roughly.

## Where this leaves L5

Our direct light matches (texels mostly lit directly: 58.5% within 10%, ours 0.98). Everything Lightmass computes
indirectly is off in strength (×1.5–3) and in shape, and no fit of strengths gets a judged half past about 23%.
Matching it would need Lightmass's own indirect model: its photon map and irradiance cache, its mesh area lights,
and each material's true diffuse output, none of which the cooked game states. Ways on:
- **Calibrate in UDK:** bakes of a closed room lit by downward spots and of an emissive panel, compared texel by
  texel (`udk_calib_scene.py`, `udk_bake.ps1`, `udk_bounce_check.py`), to pin what Lightmass does indoors. A material
  can't be made in a T3D, so the emissive bake needs an emissive material UDK already has.
- **Keep relighting as a change:** a big remix relit as a change on the original bake, as every Build does now, where
  our model's error scales with what the remix changes rather than with the room's whole light. One game test of a
  large remix built so would show whether that is good enough, and L5's absolute match could wait for maps with no
  original bake (blank maps).

The user chose the second (7 November): a large remix relit as a change, in the game, and a stop before L6.

## Run 1: a large bar remix, relit as a change (built 7 November)

**The project:** `Large remix` (`35e92af8-3c2b-4792-975b-85d42cec3851`, revision 1), only plain pieces. Glowing
props (the arcade and claw machines, the neon signs, the TVs) stay where they are: their baked glow is lights of the
map, and moving lights is L6.
- **The pool table** (`XComDestructibleActor_491`) with its glass (`_45`) to EXP-20 run 8's place, on the open floor
  by the island counter's corner nearest the street windows, a quarter turn; its rug (`XComLevelActor_29`) turned
  with it, under it.
- **The back booth** (tables `_200` and `_201`, their tops `_27` and `_278`, chairs `_110`, `_58` and `_53`) moved
  as a group from its corner by the back wall into the pool table's old place.
- **The low railing** round the pool area deleted: `_22`, `_23`, `_248`, `_253`, `_258`, `_318`, `_320`, `_323`,
  `_324`.
- **Five stools** along the island counter's long side deleted: `_100`, `_185`, `_471`, `_472`, `_377`.

The editor's Build relights it as every Build does: the original bake plus our model's light after the edit minus
before, on the receivers within reach.

**The build** (283 s): 24 pieces taken out of the map (14 deleted, 10 moved), their 10 copies made in the map,
481 receivers within 1024 units of the edit, of which the reach test kept 283: 166 lightmaps written, 116 unchanged,
25 skipped. The lab watcher installed it at 22:08: the test slot plays `URB_Bar_LargeRemix_35e9` with no patch,
streaming its own landing intro.

**What to look at** (a new campaign, the first mission; F9 at each):
1. The whole bar room from above, as level as the camera allows: does any area look lighter or darker than its
   surroundings, with an edge where the relit floor and walls meet the untouched ones?
2. Where the railing stood (the line between the pool area and the counter): no leftover shadow strips on the floor.
3. Where the stools stood, along the island counter's long side: no shadow rings left.
4. The pool table at the front corner: its shadow under it, the rug flat under it.
5. The booth in the pool table's old place: shadows under its tables and chairs, and none of the pool table's left.
6. The back corner where the booth stood: plain floor, no leftover shadows.
7. If you like: walk a soldier through where the railing was (its tiles should be open), and a grenade on the booth.

**Result: passed** (22:10–22:13, F9 shots `look-221035`, `-221055`, `-221100`, `-221302`). The user: "seemed ok".
- `look-221035`, top-down over the bar: the lamp pools run across the floor with no edge between relit and
  untouched floor; the pool table at the front corner, the booth's two tables beside the side windows, left of the
  dark rug that stayed.
- `look-221055` and `-221100`, angled: the pool table by the street windows with a soft shadow under it, the island
  counter, the floor where the railing stood plain.
- `look-221302`, top-down again: the booth shows only its tables' four-legged bases. Its two table tops, separate
  pieces about 142 units up, are not drawn, most likely hidden by the camera's cutaway at that moment. Not
  followed up.

So a large remix relit as a change shows no seams in the game, though our model's indirect light is off as findings
1–9 say. That settles L5 for remixes of maps with an original bake. The absolute match waits for maps without one
(blank maps).

# EXP-17: fixed-size lighting edits in the game (baker stage 1: C0, C1, C2)

Date: **6 November 2026**. Status: **run 1 passed (C0, C1, colour); run 2 played (the value is not linear,
exponent about 2–2.5); run 3 played (power about 2.2; the three channels are directional weights, not colours, and
red and green weigh the same on flat ground); run 4 played (all three channels weigh the same, and they add: a grey
19/31 in every channel lights like one channel at full value); run 5 passed (the pool-table floor relit by our own
encoder from the map's lamps renders correctly and matches the original where nothing blocks the light; shadows,
bounce and emissive light are still missing); run 6 passed (with shadows and bounce, no checkerboard against the
original on the floor); run 7 built offline only (the whole room matches too poorly for a checkerboard); run 8
passed (an edit relit as a change on the original bake: the switched-off spot's pool is gone, the rest of the room
unchanged, no artifacts); run 9 passed (the pool table deleted in the editor: gone, its cover gone, and the rug
under it evenly lit, with no shadow of it left); run 10 passed (the pool table moved in the editor: its shadow baked
into the floor at the new place, and its cover working from the seeds in the relit map); run 11 passed (a piece added
from nothing, built by the editor's Build and installed by the lab installer: it stands lit, with the floor around
its base darkened, and nothing else changed)**.
Design: standalone baker, sections 4.8 and 5. Branch `standalone-baker`.

## Question

Can we change a map's baked lighting without UDK and without growing the package?

- **C0:** does the game load a map whose middle chunks were re-encoded, so every later chunk moved in the file?
  ([`package_edit.py`](../../tools/upk/package_edit.py); seeded maps only ever grew the last chunk.)
- **C1:** does it read a lightmap texture's top mips from a new cache file, `Lighting_7000.tfc`, found by a cache name
  that differs only in its FName number (`Lighting` + number 7001)? The texture's cache GUID is left as it was.
- **C2:** which quantities does the shader use? Run 1 changes one colour texture inside one receiver's rectangle and one
  directional scale on another receiver.

## Run 1: `URB_BarLight` (built and deployed 6 November, 21:11)

Built by [`lighting_fixture.py`](../../tools/bake/lighting_fixture.py) from the lab's own `URB_Bar.upk` (SHA-256
`a3ae5a73…`, identical to the snapshot) into `<lab>\bake-fixtures\c1c2\`:

```powershell
python -B tools/bake/lighting_fixture.py <lab>\uncooker-input\CookedPCConsole\URB_Bar.upk `
  <lab>\bake-fixtures\c1c2 URB_BarLight --cache Lighting_7000 `
  --paint TheWorld.PersistentLevel.XComLevelActor_302.StaticMeshComponent_7 0 1 0 0 `
  --scale TheWorld.PersistentLevel.XComLevelActor_91.StaticMeshComponent_6 1 4
```

| Edit | Receiver | Change |
| --- | --- | --- |
| Paint | East half of the bar's floor, `XComLevelActor_302` (`URB_Bar_384CFloor`, at (96, 672)) | Its rectangle in `NormalizedAverageColor0_5` filled with pure red in every mip: 74 × 74 whole blocks at 1024², down to the inline 32² mip |
| Redirect | `NormalizedAverageColor0_5`, shared by about a hundred receivers | Its four cached mips (1024² to 128²) moved to `Lighting_7000.tfc`; the painted mips as literal LZO, the others as the original bytes |
| Scale | West half of the bar's floor, `XComLevelActor_91` (`URB_Bar_384Floor`, at (−1056, 672)) | `DirectionalMaxComponent` slot scale × 4: (1.33, 1.22, 1.00) → (5.33, 4.87, 4.00) |

Two chunks re-encoded (4 and 18), the file 163,205 bytes larger; decoded back and compared by the tool. The fixture
manifest `URB_BarLight.fixture.json` lists every edit with its old and new bytes.

**Deployed** with [`deploy_fixture.py`](../../tools/bake/deploy_fixture.py) (game closed, lab active):

- `URB_BarLight.upk` and `Lighting_7000.tfc` copied into the lab's `XEW\XComGame\CookedPCConsole`;
- URB_Bar's 7 landing zones copied under `URB_BarLight` in `DefaultLZMutator.ini`;
- **the test slot (`DefaultMaps.ini` line 42) now plays `URB_BarLight`** with URB_Bar's streams and night time. It held
  EXP-14 run 14 (Temple, not yet played). Restore it before EXP-14 continues, because patchtool's `-Stream` only
  resets the slot's Name and slot 2, not Temple's slots 0 and 1:

  ```powershell
  python -B tools/bake/deploy_fixture.py restore <lab>\bake-fixtures\deploys\URB_BarLight-20261106-211142.json
  ```

  It puts line 42 back byte for byte and removes the landing-zone lines (dry run checked). Backups of both INI files
  are in `<lab>\bake-fixtures\backups\` (`.20261106-211142`).

### What to look at (the user drives, F9 at each)

New campaign, Ironman, tutorial and autosave off; the first mission is the test slot. There is no dropship landing
cutscene: the intro picks it by map name and `URB_BarLight` is not one it knows (F-45). That is expected here.

1. **The mission loads at all.** If the game crashes or hangs while loading, C0 or C1 failed; the next run splits them
   (`<lab>\bake-fixtures\c0\URB_BarC0.upk` is C0 alone, already built).
2. **Inside the bar, roof cut away, looking at the floor.** Expected if the colour texture is what its name says:
   the east half of the floor lit red, keeping its texture's detail, ending at its edges; the west half clearly
   brighter than before. Note how much brighter: four times, or more (that would point to squaring or gamma).
3. **The rest of the atlas looks normal:** the rug in the bar (`XComLevelActor_95`, at (−208, 344)), two ceiling air
   ducts (`_72`, `_73`), a sidewalk slab (`_132`, at (576, 1248)) and the asphalt planes `_275` and `_244` (around
   (−1341, −96) and (−1342, −1056)) all read their lighting from the new cache now. Black, noisy or blocky patches there mean C1 is reading wrong data.
4. Anything else that looks wrong, anywhere on the map.

Claude then reads the lab's `Launch.log` (read only) for texture-cache warnings.

### Result (21:16, first shots)

- **C0 passes:** the mission loaded and started normally on `URB_BarLight` (squad down in the parking lot, turn 1;
  `look-211624.png`). The game reads a map whose middle chunks were re-encoded and whose later chunks moved.
- **C1 passes so far:** the painted texels exist only in `Lighting_7000.tfc`, and they show (below), so the game found
  the cache by the renamed FName and did not reject the unchanged cache GUID. The rugs and other surfaces in view
  that share the atlas show no black, noisy or blocky patches.
- **C2, colour:** inside the bar (`look-211632.png`) the floor is lit **red**, keeping its plank detail and its light
  and shadow pattern (bright pools and dark corners stay where they were). So `NormalizedAverageColor` is a colour
  that multiplies the light, and the brightness pattern comes from elsewhere (the directional texture and its scale),
  as the EXP-16 run 2 reading predicted. The red stops at the rectangle's edges with a slightly ragged border, from
  painting whole 4×4 blocks only.
- The wider view (`look-211701.png`) shows the red floor is the half of the bar room around the central counter;
  the other half, behind the brick partition, is warm orange wood. Walls, rugs, the counter and the street outside
  look normal.
- **Log:** `Launch.log` shows `URB_BarLight` loading (11.7 s to 23.4 s) and coming up for play, with no message about
  `Lighting_7000`, texture caches or bulk data. The only warnings near the load are three "Cooking Convex" lines for
  brick-pile debris.
- Open: the orange half should be the × 4 one (`XComLevelActor_91`), but it is not obviously blown out, and no shot of
  the unedited bar interior exists to compare (EXP-10's shots are all outdoors). The scale's effect needs a controlled
  run: a matched before/after view, or known solid values painted into `DirectionalMaxComponent`.

## Run 2: `URB_BarLight2`, how brightness is stored (deployed 21:24)

Run 1 showed `NormalizedAverageColor` is the light's colour. Run 2 asks how `DirectionalMaxComponent` and its slot scale
turn into brightness, using a comparison that does not depend on the screen's own response curve: two stripes that
should look the same if the texture value and the scale simply multiply.

Built from [`exp17-run2.json`](../../tools/bake/examples/exp17-run2.json) (cache `Lighting_7001.tfc`; both textures of
atlas pair `0_5` redirected):

| Receiver | Colour texture | `DirectionalMaxComponent`, stripes along atlas U (all three channels equal) | Slot scale |
| --- | --- | --- | --- |
| East floor `_302` (around the counter) | white | 28/31, 14/31, 7/31, 0 | set to (1, 1, 1) |
| West floor `_91` (behind the partition) | white | 14/31, 7/31, 28/31, 0 | set to (2, 2, 2) |
| Rug `_95` (at (−208, 344)) | white | one channel each: (1, 0, 0), (0, 1, 0), (0, 0, 1) | set to (1, 1, 1) |

(Green uses the 6-bit levels 56, 28, 14 of 63, so each stripe pair is exactly 2:1 in every channel. Both floors use the
same `FloorWood_BNatural` material, and both have planar lightmap UVs, so the stripes run straight across them.)

Expected:
- **If value × scale is linear:** the east floor's brightest stripe looks the same as the west floor's medium one
  (28/31 × 1 = 14/31 × 2), and the east medium the same as the west dim one. The west floor's brightest stripe is twice
  the east's brightest.
- **If the value is squared (or gamma-encoded):** each west stripe looks about half as bright as its east partner.
- **The black stripes** show whether any light reaches the floor apart from the lightmap.
- **The rug:** if the three channels are three directions arranged evenly around the surface normal, the three stripes
  are equally bright on the flat rug and differ only in how the rug's bumps catch light. A stripe much brighter than
  the others means that channel leans towards the normal.

The deploy recorded run 1's as `previous`, so one restore of run 2's record returns line 42 to EXP-14 (dry run
checked: both steps apply):

```powershell
python -B tools/bake/deploy_fixture.py restore <lab>\bake-fixtures\deploys\URB_BarLight2-20261106-212443.json
```

### What to look at (the user drives, F9 at each)

New campaign as before (the map is `URB_BarLight2`; still no landing cutscene).
1. The whole bar room from above, roof cut away, with both floor halves in view.
2. Closer, each floor half on its own, looking straight down if the camera allows.
3. The rug by the counter, close.

### Result (21:57; three shots pasted into the chat)

The map loaded again, with both floors white-lit and striped; every stripe edge is straight, where the UV mapping
put it. Stripe positions in the world come from fitting each floor's lightmap UVs to its top-face vertices
(residual under 0.4 units):
- East floor, stripes along world Y: 28/31 at y −59…258 (by the south wall), 14/31, 7/31, and black at y 928…1245
  (by the arcades).
- West floor, stripes along world X from the partition westward: 14/31, 7/31, 28/31, black.

Median brightness of plain-wood patches (40 × 40 px, sRGB decoded with a 2.2 power, Rec. 709 weights):

| Stripe | Value × scale | Brightness | Minus black (0.0032) |
| --- | --- | ---: | ---: |
| West s3 | 28/31 × 2 | 0.349, 0.401 | ≈ 0.37 |
| East s1 | 28/31 × 1 | 0.198 | 0.195 |
| West s1 | 14/31 × 2 | 0.075, 0.053 (patches clip a dark edge) | ≈ 0.07 |
| East s2 | 14/31 × 1 | 0.039, 0.037 | 0.035 |
| West s2 | 7/31 × 2 | 0.025 | 0.022 |
| East s3 | 7/31 × 1 | 0.004 | ≈ 0.001 |
| Both black stripes | 0 | 0.0032 (dark blue: light that is not from the lightmap) | 0 |

- **Value × scale is not linear.** West s1 (14/31 × 2) should have matched east s1 (28/31 × 1) if it were; it is
  about a third as bright.
- **The scale is linear.** West s3 / east s1, the same value at twice the scale, is 1.9.
- **The stored value enters raised to a power of about 2 to 2.5.** West s1 / east s1 = 0.36 gives 2.5, and east
  s2 / east s1 = 0.18 gives 2.5. The noisier west pair (s1 / s2) gives 1.7–2. The screen's own response and
  tone mapping could bias these. Reading the texture as sRGB (the engine's default when `SRGB` is not saved,
  as EXP-16 found) would give about 2.2; a shader that squares it would give 2. Run 3 separates the two.
- **The rug test is inconclusive:** the dark-red rug in the shots could not be matched with certainty to
  `XComLevelActor_95`, and its brightness was flat and near black. Run 3 replaces it with a test that marks itself.

## Run 3: `URB_BarLight3`, which power, and the three channels (deployed 22:05)

Built from [`exp17-run3.json`](../../tools/bake/examples/exp17-run3.json) (cache `Lighting_7002.tfc`).

**The power, as a null test.** The east floor is one uniform patch at 28/31 with scale 1. The west floor has scale 16
and five stripes, 7/31 to 11/31 (green 14/63 to 22/63), going west from the partition. The stripe that matches the
east floor's brightness gives the power g, since 16 × v^g = (28/31)^g there:

| West stripe (from the partition) | x | Matches the east floor if g is about |
| --- | --- | --- |
| 1: 7/31 | −686…−451 | 2.0 (the shader squares the value) |
| 2: 8/31 | −921…−686 | 2.2 (sRGB-like decoding) |
| 3: 9/31 | −1156…−921 | 2.45 |
| 4: 10/31 | −1391…−1156 | 2.7 |
| 5: 11/31 | −1626…−1391 | 3.0 |

The match sits right at the partition, so the screen's response cannot bias it; stripes darker and brighter than the
match bracket it.

**The three channels.** The asphalt plane `XComLevelActor_275` outside the bar's south-west corner (colour white,
scale 1) has four stripes along world X, running north–south. From the west: red channel only (x −1806…−1563),
green only (−1563…−1341), blue only (−1341…−1119), and black (−1119…−876) as a marker. The south part of each
stripe (y −557…114) is clear of the bar. On a flat surface, three directions spread evenly around the normal would
light the three stripes equally; a much brighter stripe means that channel points closer to the normal.

The restore chain now covers runs 3, 2 and 1 (dry run checked):

```powershell
python -B tools/bake/deploy_fixture.py restore <lab>\bake-fixtures\deploys\URB_BarLight3-20261106-220531.json
```

### What to look at

New campaign as before (map `URB_BarLight3`).
1. The partition between the two floor halves from above, with the uniform east floor and the first two or three west
   stripes in one view.
2. The whole west floor, all five stripes.
3. Outside, the asphalt at the bar's south-west corner: four stripes, the easternmost black. `ShowCursorLoc` helps
   to confirm the place (around x −1340, y −200).

### Result (22:08, F9 shots `look-220816`, `-220825`, `-220829`; the asphalt at 22:18, `look-221805`)

Screen positions were tied to the world with landmarks (the counter between the long blue rugs `Rug_B` at y 344
and 907, the pool table at (528, 670)). In these top-down views screen right is world −X (the kitchen side), screen up
is world +Y, at about 1.5 px per unit. The counter covers the line between the two floors, so the west stripes start at
its kitchen-side edge.

Median brightness of plain-wood patches (50 × 50 px, as in run 2):

| Where | Value × scale | Brightness |
| --- | --- | --- |
| East floor, near the screen centre | 28/31 × 1 | 0.215, 0.234, 0.189 |
| East floor, near the top edge | 28/31 × 1 | 0.154 |
| West stripe 1 | 7/31 × 16 | 0.147, 0.143, 0.156, 0.159 (`-220825`); 0.134, 0.174 (`-220829`) |
| West stripe 2 | 8/31 × 16 | 0.203, 0.219 |
| West stripe 3 | 9/31 × 16 | 0.279 (0.416 where a sheen shows) |
| West stripes 4, 5 (towards the screen edge) | 10/31, 11/31 × 16 | 0.235, 0.250 (0.37–0.41 with sheen) |

- **Stripe 2 (8/31) matches the east floor; stripe 1 (7/31) is about 30% darker.** The power is about **2.2**, which
  fits the texture being decoded as sRGB (`SRGB` is not saved, so the class default applies). Squaring (power 2) would
  have made stripe 1 match. Stripe 3 is 1.33× the east floor, as a power of 2.2 predicts (1.32).
- Stripes 4 and 5 rise less than predicted (1.1–1.2× instead of 1.7–2×). They lie towards the screen edge, and the
  uniform east floor itself varies about ±20% with screen position (0.154 near the top edge, 0.234 near the centre).
  So only the near-centre comparisons are relied on.
- A view-dependent sheen (specular from lights that are not in the lightmap) brightens planks near the bottom of
  `-220829`; patches with it were left out.

**The asphalt** (`look-221805`; the user's note in the shot: the asphalt under the police car seems to change colour
suddenly). An earlier shot (`look-221650`) showed only sidewalk at the planned spot:
- Only a strip of `XComLevelActor_275` is visible. The plane spans y −576…384, but the sidewalk covers everything
  north of the kerb (y −308). The visible strip is 268 units wide and holds the police car (y −533…−411). Its outer
  edge is the seam with the next plane, `_244`, which keeps its original bake: that seam is the sudden change the
  user saw.
- Positions come from the sidewalk joints. The slab joints at x = −1056 to −1728, 96 units apart, were found along a
  slab row next to the kerb. The lamp post (x −1792) sits between the −1728 and −1824 joints, as it should. The kerb
  line and the strip's outer edge meet at one vanishing point and the joints at another, and both points lie on one
  horizon (screen y about −1370), which checks the reading.
- Median brightness (sRGB decoded with a 2.2 power, Rec. 709 weights) in 96-unit cells, a band along the kerb and a
  band along the outer edge:

| x | Stripe | Along the kerb | Along the outer edge | Car's baked shadow (kerb / edge) |
| --- | --- | ---: | ---: | --- |
| −1824…−1728 | red | 0.0199 | 0.0141 (corner, partly off the plane) | none |
| −1728…−1632 | red | 0.0220 | 0.0248 | none |
| −1632…−1536 | red, then green | 0.0245 | 0.0268 | none |
| −1536…−1440 | green | 0.0230 | 0.0254 | none |
| −1440…−1344 | green | 0.0209 | 0.0243 | 0.88 / 0.79 |
| −1344…−1248 | blue | 0.0186 | 0.0180 | 0.88 / 0.72 |
| −1248…−1152 | blue | 0.0153 | 0.0154 | 0.98 / 0.58 |
| −1152…−1056 | blue, then black | 0.0075 | (car) | 1.0 / 0.42 |
| −1056…−864 | black | 0.0072–0.0075 | 0.0086–0.0087 | none |

- **The black stripe is dark** (0.0075: the light that does not come from the lightmap); the lit stripes are 2 to
  3.5 times brighter.
- **Red and green match within about 5%.** Blue reads 10–35% lower, but only beside the car. The asphalt's
  dominant-light shadow map (`ShadowMap2D_4284`, which the edit does not touch) holds the car's shadow exactly
  there: factors 0.42–0.88 for x −1440…−1056, and 1.0 everywhere else on the strip (last column).
- **No stripe is tinted.** Every lit cell keeps the same colour balance (sRGB about 38 : 40 : 78, the night grade);
  only the brightness changes.

Reading: the three channels are not colours. Each is a separate weight, and on flat ground red and green weigh the
same, as three directions spread evenly around the normal, at equal angles to it, would. Blue's lower reading may
come from the car; run 4 moves blue away from it. Which channel points which way along the surface cannot show on
flat ground. The UDK Lightmass calibration (design, section 4.7) is the planned route to that.

## Side note: the brown X-braced border along the bar's inner walls

The user asked (22:15, with a screenshot) about the darker, crate-like boards in a one-tile border along the bar's
inner walls, also seen on copied buildings in the editor's Bar variants. They are part of the original floor meshes:
- `URB_Bar_384CFloor` and `URB_Bar_384Floor` each have a material section `URB_Bar_FRAC.Materials.M_FloorWoodEdgeA`;
- it is a horizontal strip around each floor's outer edge, about 96 units (one tile) wide (359,424 and 221,184
  square units of horizontal area);
- the main `FloorWood_BNatural` section is inset by that tile.

Nothing in the lighting edits or the editor's copies changes geometry or materials, so the unedited map draws the same
strip. It stands out more in these runs, because their flat painted lightmap removes the darkening the original bake
puts along the walls. Dynamically lit copies lack that darkening too.

## Run 4: `URB_BarLight4`, symmetry and additivity (deployed 22:34)

Run 3 left blue unmeasured away from obstructions, and it did not ask how the channels combine. Built from
[`exp17-run4.json`](../../tools/bake/examples/exp17-run4.json) (cache `Lighting_7003.tfc`):

| Receiver | Colour texture | `DirectionalMaxComponent`, stripes along atlas U | Slot scale |
| --- | --- | --- | --- |
| East floor `_302` (pool-table side, x −461…817) | white | seven bands, each about 180 units, from the street wall (y −59) to the arcades (y 1245): red, green, blue, black, blue, green, red (single channels at full value) | (1, 1, 1) |
| West floor `_91` (kitchen side, x −1626…−451) | white | three greys from the counter outwards: 19/31 (x −837…−451), 24/31 (−1240…−837), 15/31 (−1626…−1240); green 38, 48 and 30 of 63 | (1, 1, 1) |
| Asphalt `_275` | white | blue, green, red, black: blue now by the lamp corner, red beside the car | (1, 1, 1) |

Expected:
- **Symmetry.** The east bands mirror about the black one, so an even gradient across the floor pushes a channel's
  two bands in opposite directions. If the channels weigh the same, the six lit bands match.
- **Additivity.** If the decoder combines the channels linearly with equal weights (a sum or a mean, each channel
  decoded with run 3's power of 2.2), grey 19/31 gives 3 × (19/31)^2.2 ≈ 1.01 times one channel at full value. The
  grey band next to the counter then matches the east floor's lit bands, 24/31 is 1.7 times brighter and 15/31 0.6
  times. If the decoder took the largest channel instead, all three greys would be darker than the east bands
  (0.34, 0.57 and 0.20 of them).
- **Asphalt.** If the car caused blue's low reading in run 3, the low reading moves to red, now beside the car. If
  it belongs to blue, blue stays low by the lamp corner.

The deploy recorded run 3's as `previous`, so one restore of run 4's record goes back through runs 3, 2 and 1 to
EXP-14 (dry run checked):

```powershell
python -B tools/bake/deploy_fixture.py restore <lab>\bake-fixtures\deploys\URB_BarLight4-20261106-223453.json
```

### What to look at

New campaign as before (map `URB_BarLight4`).
1. The counter from above, with the pool-table floor's bands and the kitchen side's first grey band in one view.
2. The whole pool-table floor: a dark band at about the pool table with three lit bands on each side.
3. The whole kitchen-side floor: three greys, medium by the counter, brighter in the middle, darker at the far end.
4. The asphalt strip by the police car, from the same spot as `look-221805`.

### Result (22:54, F9 shots `look-225404`, `-225417`, `-225422`, `-225428`)

The map loaded; every band sits where the UV fit put it (the red rugs at x −843 fall on the line between the first
two greys). Screen positions were tied to the floor with the rugs and the pool table (about 1.5 px per unit in these
top-down views). Brightness is the median of plain-wood patches (sRGB decoded with a 2.2 power, Rec. 709 weights;
patches darker than 0.04 dropped as rugs, props and table tops):

| Shot | Band (pool-table floor, street wall to arcades; then kitchen side) | Brightness |
| --- | --- | --- |
| `-225417` (whole pool-table floor) | green, blue, black, blue, green, red | 0.075, 0.094, 0.003, 0.079, 0.099, 0.073 (red at the screen's top edge; the first red off screen) |
| `-225404` (the counter) | green, blue, black, blue, green, red | 0.059 (screen edge), 0.082, 0.003, 0.072, 0.084, 0.073 |
| `-225404` | kitchen side, grey 19/31 and 24/31 | 0.083, 0.144 |
| `-225422` (kitchen side, y 380…680) | grey 19/31, 24/31, 15/31 | 0.076, 0.136, 0.045 |
| `-225428` (asphalt, a band just below the kerb) | black, red, green, blue | 0.006–0.007, 0.022, 0.022, 0.0215 |

- **The three channels weigh the same.** On the pool-table floor blue averages 0.087 over its two bands and green
  0.087; red (0.073) was only seen at the screen's top edge, where run 3 also found the floor dimmer. On the asphalt,
  with blue now by the lamp corner, red, green and blue match within 5% along the kerb. Run 3's low blue came from the
  car's baked shadow.
- **The channels add.** Grey 19/31 in all three channels matches one channel at full value (0.076–0.083 against
  0.072–0.099), as 3 × (19/31)^2.2 ≈ 1.01 predicts. The other greys follow the same rule: 24/31 is 1.79 times 19/31
  (predicted 1.67) and 15/31 is 0.59 times (predicted 0.60). Taking the largest channel instead would have made all
  three greys darker than the single channels.
- The kitchen's tiled floor covers the far end of the kitchen-side floor (y above about 700); patches there were
  first taken by mistake and read the tiles, so the greys were measured below it.

**Decoder so far:** on a flat receiver the light is `NormalizedAverageColor` (the colour) times the sum over the three
`DirectionalMaxComponent` channels of value^2.2 × that channel's slot scale, each channel weighing the same. How the
weights change with the surface's bumps (the direction of each channel along the surface) is left to the UDK
calibration.

## Run 5: `URB_BarLight5`, the pool-table floor relit by our own encoder (deployed 7 November, 00:00)

Runs 1–4 painted test patterns. Run 5 asks whether the encoder EXP-18 fitted to UDK Lightmass reproduces EW's own
bake when it relights a real floor from the map's real lamps. [`relight.py`](../../tools/bake/relight.py) rebuilt the
pool-table floor `XComLevelActor_302` (both textures, every texel, mips down to 16 texels, and the directional slot
scale) from the 52 lights its lightmap lists (36 spot and 16 point lights, all with Lightmass source radius 32):
direct light only, **no shadows and no bounce light**. Everything else, the kitchen-side floor across the counter
included, keeps the original bake (cache `Lighting_7004.tfc`; record
`<lab>\bake-fixtures\run5\URB_BarLight5.relight.json`).

Offline, against the original bake on the same texels (light a flat surface gets: colour times the summed
directional values):
- where the original is brightest (the six warm pools under the lamps, nothing in the way) the relit floor is 0.97–0.99
  of it; across the middle half of the brightness range 0.94;
- the relit floor is brighter where the original has shadows: under the bar's top fixture (a black rectangle in the
  original), around the pool table (a dark outline) and in dark patches at the edges; the median over the floor is
  0.84 against 0.59, correlation 0.88;
- the relit colour in the pools is a little warmer, (1, 0.65, 0.41) against (1, 0.69, 0.53): the original's bounce
  light from the walls is missing;
- a blue glow on the floor near the arcades in the original is missing: no listed light reaches it (the nearby purple
  point lights have radii of 78 and 100 units and hang 107 units up), so it is probably an emissive surface that
  Lightmass baked as a mesh area light, which the light list does not name;
- the slot scale changed from (2.41, 2.14, 2.38) to (1.51, 1.54, 1.49);
- 12 texels outside the floor's rectangle changed (black padding, by at most 8/255), from merging the edge blocks.

The deploy recorded run 4's as `previous`; one restore of run 5's record undoes the chain:

```powershell
python -B tools/bake/deploy_fixture.py restore <lab>\bake-fixtures\deploys\URB_BarLight5-20261107-000010.json
```

### What to look at

New campaign as before (map `URB_BarLight5`).
1. The pool-table floor from above, all of it: the warm pools under the lamps should look as they did in the
   original map, and the floor's wood grain should show the same bump shading.
2. The counter, with both floors in one view: across the counter the relit floor (pool-table side) and the original
   (kitchen side) should meet without a step in brightness where both are lit.
3. The pool table and the bar's top fixture close up: the shadows around them are gone in this run (expected).
4. The floor near the arcades where the original had a blue glow (expected missing).

### Result (00:04–00:05, F9 shots `look-000420`, `-000429`, `-000448`, `-000453`, `-000500`)

The map loaded and the relit floor renders normally: the warm pools under the lamps, the wood grain shaded as on the
rest of the floor, no blocks, seams or noise from the encoding. The game shows our bake, not the original: the floor
around the pool table, which the original lights with a grey-white glow, is nearly black in the top-down shot
`-000420`, as the relit textures predict.

Mapped top-down in world space, relit against original:
- 51% of the floor's lit texels agree within 10%, mostly the open floor under the lamps;
- the relit floor is brighter only where the floor cannot be seen: under the square counter, the pool table and the
  arcade machines (those objects' baked shadows);
- it is darker (by up to 4 times) around the pool table, along the arcades and along the street wall. The bar's
  emissive surfaces light those places in the original: the arcade machines' screens, neon signs on the street
  wall, and two large warm panels just past it (Lightmass's generated area lights 440 and 441, radius 640, pointing
  down). Lightmass bakes emissive surfaces as mesh area lights without listing them among the lightmap's lights.

Adding the map's 137 generated area lights (the dynamic-light stand-ins Lightmass made for those surfaces) as
unshadowed spot lights overshoots: around the pool table the relit floor goes from 0.88 to 1.40 times the original,
since without shadows the panels behind the street wall light the floor at full strength. Emissive light needs the
shadow step.

**Run 5 passed:** the encoder's output works in the game, and where nothing blocks the light it matches EW's own
bake. What remains is what the encoder does not model yet: shadows, bounce light and emissive surfaces.

## Run 6: `URB_BarLight6`, shadows and bounce light, as a checkerboard against the original (deployed 7 November, 00:43)

Run 5's relight had no shadows. [`relight.py`](../../tools/bake/relight.py) now adds them:
- soft shadows from the map's 817 shadow-casting meshes (356,600 triangles, traced with Embree by
  [`shadows.py`](../../tools/bake/shadows.py));
- the emissive surfaces' light, through the 137 area lights Lightmass generated for them;
- one bounce of indirect light with each surface's albedo and the map's environment colour
  ([`bounce.py`](../../tools/bake/bounce.py), [`albedo.py`](../../tools/bake/albedo.py)).

Run 6 relights the same pool-table floor, `XComLevelActor_302`, as a checkerboard against EW's own bake:
- squares of 192 units (two tiles), with corners at world x and y multiples of 192;
- in alternate squares the floor keeps the original bake, re-encoded under the same slot scale as our light, and in
  the rest it carries our light;
- where the two agree no pattern can show, and where they disagree it shows as squares.

Cache `Lighting_7005.tfc`; record `<lab>\bake-fixtures\run6\URB_BarLight6.relight.json`.

Offline, against the original on lit texels:
- the whole floor relit (no checkerboard): 64% of texels within 10% (run 5: 51%), median light 0.57 against 0.59,
  correlation 0.98;
- the original's squares after re-encoding: median 0.98 of the original;
- our squares, each square's median against the original:
  - 0.93–1.02 on the open floor under the lamps;
  - darker in the dim floor around the pool table: 0.78 at the corner toward the light switches and the neon sign,
    0.85 on the side toward the bar counter;
  - 0.51 in one dim square by the ATM, where the original's light is about a fifth of a lamp pool's;
- 96 black padding texels outside the floor's rectangle changed colour (by up to 33/255), from merging the edge
  blocks. Their directional value is 0, so they give no light.

The deploy recorded run 5's as `previous`; one restore of run 6's record undoes the chain:

```powershell
python -B tools/bake/deploy_fixture.py restore <lab>\bake-fixtures\deploys\URB_BarLight6-20261107-004306.json
```

### What to look at (the user drives, F9 at each)

New campaign as before (map `URB_BarLight6`).
1. The open floor under the lamps, between the bar counter and the pool table, from above: no checkerboard should
   show. If it does, the squares are two tiles wide and alternate like a chessboard.
2. Around the pool table, close up: on the side toward the bar counter and at the corner toward the light switches,
   squares two tiles wide may look a little darker.
3. The floor by the ATM: one square may be darker, but that floor is dim anyway.
4. The shadows of the pool table and the counter on the floor: soft-edged as in the original, without noise or
   bands, and continuing across square edges without a step.

### Result (00:47, F9 shots `look-004739`, `-004745`, `-004750`, `-004756`, `-004759`)

Three top-down shots over the pool table, the counter and the arcade corner, and two angled views of the room:
- **No checkerboard shows** at normal viewing. The lamp pools, the soft shadows of the pool table, the counter and
  the railings, and the wood's shading run across the square edges without a step. Our squares and the original's
  look like one bake.
- With contrast stretched (the shot blurred to remove the planks, then mapped onto the floor from the red rug beside
  the pool table), the only steps at square edges are in the darkest floor, for example beside the railing just
  below that rug. There the game is a little darker in our square, as predicted: our light is 0.2–0.4 of the
  original's, but both are only about 4% of the floor's median.

That pointed to a gap the offline comparison had hidden, because it counted only texels brighter than 0.05. By the
original's brightness:

| Original's flat light | Share of the floor | Relit / original (median) |
|---|---|---|
| 0.01–0.05 | 5% | 0.38 |
| 0.05–0.1 | 6% | 0.46 |
| 0.1–0.2 | 6% | 0.83 |
| 0.2–0.5 | 13% | 0.94 |
| 0.5 and up | 54% | 0.95–0.98 |

(The remaining 16% is black in both: under the counter and the pool table.) Where little direct light reaches, the
floor is lit mostly by bounce light, and ours is too weak: it is 0.9% of the floor's light. Scaling only the bounce
by π (the environment colour left as it is) brings those bands to 0.86, 0.74, 0.98 and 1.01, with 70% of the floor
within 10% (64% now).

The cause is not a factor of π: UDK bounce calibrations ([EXP-18](EXP-18-udk-lightmass-calibration.md),
BakeCalib8–11) show our one bounce matching Lightmass's for directional and point lights, with Lightmass's albedo
sRGB-decoded as ours. The difference is in spot lights. Lightmass bounces 3.5–8 times our light from them, spread
wider than their cones, probably because few photons fall on each lit patch and its irradiance estimate smears them.
The ceiling pieces over the floor showed it too: their original light is 2–4 times what our direct light and bounce
give them, and they are what the floor's dark zones see.

With spot cones doubled for bounce sources ([`bounce.py`](../../tools/bake/bounce.py)), the floor's bands become:

| Original's flat light | Relit / original (median) |
|---|---|
| 0.01–0.05 | 1.62 |
| 0.05–0.1 | 0.80 |
| 0.1–0.2 | 0.99 |
| 0.2–0.5 | 1.00 |
| 0.5 and up | 0.97–0.99 |

69% of the floor is within 10%, and the log error falls from 0.65 to 0.48.

**Run 6 passed:** the shadowed, bounced relight matches EW's own bake closely enough that the game shows no
checkerboard where light is above the darkest level, and its seams against the original bake are invisible. The
remaining error was the bounce from spot lights in dark areas, since modelled as above (not yet in the game).

## Run 7: the whole bar room relit as a checkerboard (built 7 November, not deployed)

Run 7 extended run 6 to the whole bar room: 178 components listed by hand (floor, walls, ceiling, counter, furniture,
signs, the sidewalk in front), relit with
[`relight.py --component-list`](../../tools/bake/relight.py) as 3D cubes of 192 units against the original. Offline
it matched too poorly to be worth a look in the game, so it was not deployed.

| Step | Lit texels within 10% of the original |
|---|---|
| First build | 22.7% (floor 68%, rugs 85%, walls 3–18%, the corner column 0%) |
| Texels inside geometry left out (`bounce.buried_texels`) | 24.6% |

What came out of it:
- **Buried texels.** About a fifth of the room's texels lie inside other geometry: floor under the walls' feet and
  the stools' bases, fracture pieces' interior faces, wall pieces sunk into each other. Our trace makes them black,
  Lightmass left them lit. They are invisible until something breaks. The relight now leaves them out: their
  unburied neighbours' light spreads into those at the edges, and the rest keep the original bake.
- **The corner column** (`XComFracLevelActor_5`) was black in ours. It stands inside the corner of the wall pieces
  and shows once they break; it is the map's one component with `StaticLightingHiddenByDefault`, and Lightmass lit
  it as if the walls weren't there. It keeps its bake.
- **The environment light** was about 4 times too bright on the roof and the sidewalk.
  [EXP-18](EXP-18-udk-lightmass-calibration.md)'s BakeCalib12 measured Lightmass's environment at 0.266 of what we
  assumed; with that, our roof deck gives 0.49 against the original's 0.44.
- **Walls, ceilings and undersides stay off.** Most of their light is indirect, and EW's Lightmass settings are
  UDK's (the game's `XEW\XComGame\Config\XComLightmass.ini` differs from UDK's `BaseLightmass.ini` only in the
  emissive threshold for mesh area lights, 0.5 against 0.01). By facing, on a sample of every fourth texel each way:
  - the facade of the street wall: 1.50 in the original, 0.85 ours (most of it from the neon signs, which Lightmass
    lights as area emitters and we only through its point-like stand-ins);
  - the wall's face toward the room: 0.37 against 0.20;
  - undersides just above the floor (the counter's overhang, the walls' lintels and feet): 0.3–0.6 against 0.02–0.13.
- **Scales do not fix it.** Fitted multipliers per source (bounce of the lamps 1.4, bounce of the emissive stand-ins
  3.3) raise the room from 24% to 32% of texels within 10%. Smoothing the bounce sources' light over discs of 25–200
  units, as Lightmass's photon search does, makes it worse (the discs average in shadowed floor). Most of the error
  is texel by texel within components: log₂ error 1.59 overall, 1.34 after giving each component its own scale.
- **As a checkerboard** (192-unit cubes, the cube's median light against the original's, per component and facing):
  27% of texels are in cubes within 10%, 43% within 40%; with the fitted multipliers 35% and 74%, the median cube
  off by ×1.24. Run 6's floor squares were within a few percent, so the game would show a checkerboard on the walls.

So matching Lightmass absolutely, room-wide, needs more of Lightmass's own model (its photon map, its emissive area
lights) than the relight has. For editing a map it isn't needed: run 8 relights an edit as a change on top of the
original bake.

## Run 8: `URB_BarLight8`, an edit relit as a change on the original bake

An edit is relit as a delta ([`relight.py`](../../tools/bake/relight.py) `--remove-caster`, `--remove-light`): each
texel gets the original bake changed by what the edit changes in our model.
- Light added adds.
- Light removed scales the original by our after/before where our model accounts for most of the original's light,
  and is subtracted where it accounts for little (weighted by before/original), never below the scaled value.
- The change spreads from our texels into chart gutters and buried edges, which keep their own original light.
- Our sampling is now the same for the same point and light whatever else is traced (`shadows.point_turns`,
  `shadows.light_seed`), so before and after agree exactly where the edit does not reach. Components it does not
  reach are not written at all.

Offline, on the pool-table floor, three earlier rules showed what to avoid:
- plain subtraction left black dots along the counter where our model puts more of the spot's light than Lightmass
  did;
- spreading the relit values (not the change) into buried texels blurred the counter's contact shadow into its
  footprint;
- subtraction where most of a bright pool goes left the original's compression error in the small remainder, a
  crosshatch.

The final rule leaves the floor identical to the original outside the removed spot's pool and the pool table's
surroundings.

The test edit, chosen to be easy to see while the objects stay in place:
- the pool table (`XComDestructibleActor_491`) casts no shadow and reflects no light; its own lightmap is left alone;
- the ceiling spot `SpotLight_3` is off. It hangs between the island bar counter and the street windows, above the
  counter's corner nearest the pool table (by the stools on the street side).

Relit: the room's 178 components as a delta; cache `Lighting_7007`; record
`<lab>\bake-fixtures\run8\URB_BarLight8.relight.json`. Deployed 7 November, 03:02.

Offline:
- the edit reaches 122 components, which are written; 54 it does not reach keep their bake untouched; the pool table
  and the corner column are skipped;
- the floor: 9,430 of its 61,579 texels change. Under the switched-off spot the brightest floor goes from 5.1 to
  0.75; elsewhere the floor is the original (86% of its lit texels within 10%, the rest being the pool and the
  pool table's surroundings);
- the rug under the spot: median 2.25 → 0.88;
- the walls, ceiling, ducts, windows and counter around it lose a few to 20 percent (the spot's bounce);
- no component outside the 122 changes, and the texels changed outside their rectangles are padding in shared
  compression blocks, as in runs 5 and 6.

Restore (undoes runs 8 and 6 in one go):

```powershell
python -B tools/bake/deploy_fixture.py restore <lab>\bake-fixtures\deploys\URB_BarLight8-20261107-030236.json
```

### What to look at (the user drives, F9 at each)

New campaign as before (map `URB_BarLight8`).
1. The floor between the island bar counter and the street windows, at the counter's corner nearest the pool table
   (in front of the stools on the street side): the lamp's pool of light there should be gone, the floor dim, while
   the other lamps' pools look as before. The lamp itself may still glow.
2. The rug in front of the counter on the street side: much darker than the other rug behind the counter.
3. The pool table: no shadow from it on the floor around and under its edges; the floor there evenly lit by its
   lamps. The table itself looks as before.
4. Everywhere else in the room: exactly as in the original map, with no squares, seams or blotches, in particular
   along the counter's foot and around the stools.

### Result (09:07–09:08, F9 shots `look-090711` to `-090759`)

Eight shots: two top-down over the counter and the pool table, the street side with the doors and the street-side
rug, the sidewalk, the back room, two angled views of the room, and the street outside.
- **No artifacts.** No squares, seams or blotches anywhere, including along the counter's foot and around the
  stools, where earlier offline rules had left dots and smears.
- **The spot is off, and nothing else changed.** `look-090711` and run 6's `look-004739` have the same zoom, 77 by
  33 pixels apart. Shifted onto each other, their brightness ratio shows:
  - one darker disc, exactly where the spot hangs: below the counter's street-side corner nearest the pool table.
    The floor there is 38% darker on screen (mean 75 → 46);
  - the back rug and the open floor unchanged (36.7 → 35.5);
  - outlines from the small change of viewpoint, and run 6's checkerboard squares in the dimmest floor (run 6 had
    our light there, a little darker than the original; run 8 has the original).
- **The street-side rug** is darker than the back rug, where before the two looked alike.
- **The pool table's shadow** barely shows from above: the floor right beside the table is 0–4% brighter. As
  offline, almost all of its shadow falls under the table itself.

**Run 8 passed:** an edit relit as a change on EW's own bake shows in the game where the model says, and leaves the
rest of the room exactly as it was. That is the relight the editor needs for moved or deleted pieces and lights.

## Run 9: `URB_BarLight9`, a deletion made in the editor, relit

The first edit made in the editor and relit as it plays:
- **The project:** `EXP-17 pool table deleted` (id `7a1f0e17-0917-4c0d-8e5a-3b2d1c9f0a17`, revision 2, written by
  [`exp17_delete_project.py`](../../tools/editor/examples/exp17_delete_project.py)). It deletes the pool table
  `XComDestructibleActor_491` and the short glass on its edge, `XComDestructibleActor_45`, which would float without
  it.
- **The patch:** compiled with `--stream-only` ([`exp17pooldel.json`](../../tools/patch/examples/exp17pooldel.json)):
  one exact hider, `XComMapEdHider_900`, and no map copy of its own, since the relit variant ships the map. patchtool
  built, cooked and deployed it as `patch_urb_bar_exp17pool_7a1f`.
- **The light:** [`relight.py`](../../tools/bake/relight.py) over the room's 178 components
  ([`bar-room-components.txt`](../../tools/bake/examples/bar-room-components.txt)), with `--remove-caster` for both
  pieces. All lights are on: run 8's spot is back.
- **The slot:** [`deploy_fixture.py`](../../tools/bake/deploy_fixture.py) `--stream` plays `URB_BarLight9` in the test
  slot with the patch in `StreamingMaps[2]`, after the base record's slots 0, 1 and 5. Deployed 7 November, 09:46.

```powershell
python -B tools/editor/examples/exp17_delete_project.py
python -B tools/editor/compiler.py "$env:USERPROFILE\Documents\XCOM Map Workshop\projects\7a1f0e17-0917-4c0d-8e5a-3b2d1c9f0a17\project.json" --cache <lab>\viewer-cache --out tools\patch\examples\exp17pooldel.json --stream-only
pwsh -File tools\patch\patchtool.ps1 all tools\patch\examples\exp17pooldel.json
python -B tools/bake/relight.py <lab>\uncooker-input\CookedPCConsole\URB_Bar.upk <lab>\bake-fixtures\run9 URB_BarLight9 --cache Lighting_7009 --component-list tools/bake/examples/bar-room-components.txt --remove-caster XComDestructibleActor_491 --remove-caster XComDestructibleActor_45
python -B tools/bake/deploy_fixture.py deploy <lab>\bake-fixtures\run9\URB_BarLight9.fixture.json --stream patch_urb_bar_exp17pool_7a1f
```

What the first build turned up:
- **A red rug lies under the table** (`XComLevelActor_29`, `RugRedPlane`, 156 by 238 units against the table's 120
  by 218). The table's shadow sits on the rug, not on the floor: in the original bake it is a dark rectangle with
  darker spots under the legs. The floor under the rug is black (the rug covers it), so the floor needs no change.
- **Texels inside a removed piece:** a texel now counts as buried only if it is buried both before and after the
  edit, so the floor inside a piece that stood solid on it is relit. The table stands on legs, so it opens nothing.
  Removing one of the island counter's sections opens more than 100 floor texels (a new test). The first build also
  set those texels' light before the edit to zero. That threw 54 borderline texels of a wall 180 units away to a
  change of 0.16. Their light before is now computed like any other, and it comes out near zero by itself inside a
  piece (shadow and gather rays hit back faces); the wall's change is 0.027.
- **Two guesses checked and dropped.**
  - Lightmass might leave a light that a piece hides completely out of a lightmap's light list. If so, a deletion
    could never bring that light back. But the lights missing from the rug's list are spots whose cones never reach
    it.
  - Our model might be too dark there, so that a deletion adds too little light. But on the rug's texels the edit
    leaves alone, the original is 1.05 times ours.

Offline:
- The edit reaches 26 components, which are written. 149 keep their bake untouched. Skipped: the corner column and
  the two removed pieces.
- **The rug:** 203 of its 598 texels change. Inside the table's footprint (20 units in from its edges) the median
  goes from 0.028 to 0.076, and the leg spots go. The rug's rim outside the table stays as it was (76% within 5%;
  the rest is the table's edge shadow, taken away too). The relit rug is brighter toward the street windows, which
  light that side. The preview, original left and relit right as flat light, is in the lab, not the repo, since it
  shows the map's own bake: `<lab>\bake-fixtures\run9\URB_BarLight9-XComLevelActor_29.png`.
- Walls, windows and pictures nearby change by at most 0.06 (the table's bounce and the light it blocked).

Restore (undoes runs 9, 8 and 6 in one go; the patch stays in the lab, harmless until a slot names it):

```powershell
python -B tools/bake/deploy_fixture.py restore <lab>\bake-fixtures\deploys\URB_BarLight9-20261107-094653.json
```

### What to look at (the user drives, F9 at each)

New campaign as before (map `URB_BarLight9`).
1. The red rug where the pool table stood, near the street windows: the table and the glass on its edge are gone.
   The rug should be evenly lit, a little brighter toward the windows, with no dark table-shaped rectangle and no
   dark spots where the legs stood.
2. If convenient, a soldier moved onto the rug: the tiles should be open, with no cover from the table.
3. Run 8's switched-off spot is on again: its pool by the island counter's corner nearest the rug is back.
4. Everywhere else in the room: as in the original map, with no squares, seams or blotches.

### Result (10:03–10:04, F9 shots `look-100320` to `-100408`)

Six shots:
- three top-down: the room with the counter and both rugs by the street windows, the counter and the back room,
  and the street front;
- an angled view of the room;
- two angled views after a soldier moved five tiles onto the rug's edge.

Which rug is which was checked from the export: the pool table's rug, `XComLevelActor_29`, lies where the table
stood in run 8's shot. `XComLevelActor_42`, the same rug turned a quarter turn, lies beside it toward the counter.
- **The deletion works.** The table and the glass on its edge are gone, with nothing floating. The soldier stands on
  the tile beside where the table stood with no cover (shield 0), so the hider took out the table's cover as well.
  This is the first time a deleted destructible prop has been played in the game (EXP-13 never was).
- **No table shadow is left.** The pool table's rug is evenly lit: no dark rectangle, and no spots where the legs
  stood.
  - In `look-100320` it is 17.1–18.0 in luminance (the screen's black is about 8, the counter top).
  - It is brighter on the street-window side (18.0, falling to 17.1 across), as the relight predicted.
  - Along its length there is no dip where the table's middle was (17.3–17.6).
  - It is dark, as its bake says: the rug beside it has four times its light (0.39 against 0.094) and shows 20.7.
    The lift the relight gives its middle (0.028 to 0.076) is therefore a small step on screen. In an unrelit map
    the middle would be about one to two levels darker than the rim (estimated from the two rugs).
- **The spot is back, and nothing else changed.** `look-100320`, scaled by 1.18 onto run 8's `look-090711`, gives a
  brightness ratio with:
  - the floor at the counter's street-side corner nearest the rug 32% brighter (33.2 → 43.9): the spot's pool, back;
  - the rug beside it unchanged (20.7 and 20.7), and the open floor unchanged;
  - the pool table's rug inside its footprint unchanged (17.5 → 17.4, the table's dark top against the relit rug);
  - outlines elsewhere from the change of viewpoint (tall walls), and the counter's top drawn dark by the cutaway in
    run 9's shot.
- **No artifacts:** no squares, seams or blotches in any shot.

**Run 9 passed:** a piece deleted in the editor plays with its baked shadow gone, from one project, with the patch
and the relit map built from it and deployed together. Pieces a patch adds or moves are still lit live.

## Run 10: `URB_BarLight10`, a piece moved in the editor, its shadow baked at the new place

A copy that a patch places is lit live, and its light environment casts no shadow (`bCastShadows` false, inherited
from `XComDestructibleActor`). So on the map's baked floors it stood without any shadow. Now the relight adds each
copy as a shadow caster at its pose, as it removes the hidden originals, and takes the whole edit from the editor's
compiled spec (`relight.py --edit-spec`).
- **The project:** `EXP-17 pool table moved` (id `7a1f0e17-1010-4d0e-9b6c-5e4f3a2b1c10`, written by
  [`exp17_move_project.py`](../../tools/editor/examples/exp17_move_project.py)).
  - The pool table moves from beside the street windows to (−48, 240), turned a quarter turn. That is the open floor
    under the ceiling spot `SpotLight_3`, by the island counter's corner nearest the street windows: the brightest
    open floor in the room that fits the table (floor light 6.45 under it, against 0.09 at its old place). The
    table's new footprint overlaps the edge of the big rug in front of the counter by about 36 units.
  - The glass on its edge moves and turns with it.
- **The patch:** [`exp17poolmove.json`](../../tools/patch/examples/exp17poolmove.json), compiled with
  `--stream-only`: a copier with the two copies at their poses, an exact hider for the originals, and the tile seeds'
  rebuild actor.
  - With `map.seedExternally`, patchtool planned 9 tiles in 2 boxes and seeded no lab map.
  - `deploy_fixture.py --seed-plan` seeded the relit variant with that plan instead: 7 tiles, 2 already had low
    bits. So the table should block and give cover at its new place.
- **The light:** `relight.py --edit-spec` with the same spec: the two originals removed, their copies added (1,348
  and 54 triangles; the glass lets light through).
- Deployed 7 November, 10:26.

```powershell
python -B tools/editor/examples/exp17_move_project.py
python -B tools/editor/compiler.py "$env:USERPROFILE\Documents\XCOM Map Workshop\projects\7a1f0e17-1010-4d0e-9b6c-5e4f3a2b1c10\project.json" --cache <lab>\viewer-cache --out tools\patch\examples\exp17poolmove.json --stream-only
pwsh -File tools\patch\patchtool.ps1 all tools\patch\examples\exp17poolmove.json
python -B tools/bake/relight.py <lab>\uncooker-input\CookedPCConsole\URB_Bar.upk <lab>\bake-fixtures\run10 URB_BarLight10 --cache Lighting_7010 --component-list tools/bake/examples/bar-room-components.txt --edit-spec tools/patch/examples/exp17poolmove.json
python -B tools/bake/deploy_fixture.py deploy <lab>\bake-fixtures\run10\URB_BarLight10.fixture.json --stream patch_urb_bar_exp17move_7a1f --seed-plan <lab>\patchtool\patch_urb_bar_exp17move_7a1f\seed-plan-built.tsv
```

Offline:
- The edit reaches 104 components, which are written; 71 keep their bake untouched.
- **Under the table at its new place** (10 units in from its edges), the floor goes from a median of 6.76 to 0.033,
  close to black. That matches what the original bake had under the table at its old place (0.028). The big rug's
  edge under it goes from 5.85 to 0.25. Within 90 units around the table the floor's median goes from 3.13 to 0.92:
  the other ceiling spots throw the table's shadow out sideways. In the floor's preview
  (`<lab>\bake-fixtures\run10\URB_BarLight10-XComLevelActor_302.png`, in the lab) the shadow is a dark
  rectangle in the spot's pool, with soft edges.
- **The old place** is as in run 9: the rug's middle goes from 0.028 to 0.076.
- The walls, ceiling, ducts and windows around the counter change by up to 0.15: the table's bounce, now from its
  new place.
- Checks offline:
  - removing the table and adding its copy back at its own pose changes at most 5 floor texels, since the triangles
    are the same;
  - seeding a relit variant changes only the world data chunk, exactly as seeding the original does (EXP-11's plan:
    310 of 339 tiles, the same bytes changed in both).

Restore (undoes runs 10, 9, 8 and 6 in one go; the patches stay in the lab, harmless until a slot names them):

```powershell
python -B tools/bake/deploy_fixture.py restore <lab>\bake-fixtures\deploys\URB_BarLight10-20261107-102655.json
```

### What to look at (the user drives, F9 at each)

New campaign as before (map `URB_BarLight10`).
1. The pool table at its new place: on the floor by the island counter's corner nearest the street windows, under
   that ceiling lamp, turned a quarter turn, with the glass on its edge. The floor right around its base and between
   its legs should be dark, its shadow, inside the bright pool of the lamp. Before, nothing there cast any shadow.
2. Its old place by the windows: the red rug evenly lit, as in run 9.
3. A soldier beside the table at its new place: low cover, and the table's tiles blocked.
4. Everywhere else in the room: as in the original map, with no squares, seams or blotches.

### Result (10:33–10:34, F9 shots `look-103325` to `-103421`)

Nine shots:
- top-down: the room around the counter (two), the counter and the back room, and the street front;
- angled: two views of the room;
- the cursor beside the table, and a soldier moved next to it (seventeen tiles).
- **The table stands at its new place with a shadow.** In the angled shots (brightened crops in the lab:
  `<lab>\bake-fixtures\run10\game-103344-table-lifted.png` and `-103348-`), the floor under the table is dark,
  and a soft shadow spreads from its base across the planks and the rug's edge, inside the lamp's bright pool. The
  glass stands on its corner, moved and turned with it.
- **Measured against run 9.** Run 9's top-down `look-100320` and run 10's `look-103325` are both fitted onto run 8's
  `look-090711` (scale 1.18 and 1.00; mean differences 7.2 and 3.0), and compared there.
  - The floor between the table and the counter is 25% darker (39.4 → 29.6): the table's shadow, cast toward the
    counter.
  - The lamp's pool beyond it is 3% darker (43.2 → 41.8).
  - The open floor (41.0 → 40.8), the rug beside the old place (20.7 → 20.6) and the old place's rug (17.3 → 17.4)
    are unchanged.
  - The table itself and the floor under it lie just outside that frame.
- **The seeds work in the relit map.**
  - With the cursor by the table, cover shields show on all its sides, and the dash path goes around it.
  - The soldier beside it has a cover value of 30, where run 9's soldier in the open had 0.
- **No artifacts:** no squares, seams or blotches in any shot.

**Run 10 passed:** a piece moved in the editor stands at its new place with its shadow baked into the floor, its old
place clean, and its cover working. The patch, the relit map and the seeds all come from one project.

## Run 11: `URB_Bar_EXP17Add_7a1f`, a piece added from nothing, built and installed by the new tools

Runs 9 and 10 took five hand-typed commands each. Now the editor builds a project into a variant package (Project
menu, Build), and the lab installer puts the package in the test slot. This run checks both, with an edit not tried
yet in the game: a piece added from nothing, whose original stays where it is.
- **The project:** `EXP-17 claw machine added` (id `7a1f0e17-1111-4e0f-8c6d-2b3a4c5d6e11`, written by
  [`exp17_add_project.py`](../../tools/editor/examples/exp17_add_project.py)). A copy of the bar's claw machine
  (`XComDestructibleActor_316`, which stays against the back wall) stands at (−48, 1008), facing as the original
  does. That is the open floor under the ceiling spot `SpotLight_8`, at the island counter's far corner from the
  street windows: the brightest open floor in the room that fits it (floor light 7.37 under it).
- **The build** ([`tools/editor/build.py`](../../tools/editor/build.py)): compiled with `--stream-only`, patch built
  and cooked, the copy added as a caster (`relight.py --edit-spec --receivers-near 1024`), the patch's 18 planned
  tiles seeded into the relit map (17 written; one had low bits already).
  - The first build, from the command line, relit all 357 components within 1024 units in one process: 12.5
    minutes, 118 changed.
  - The second, from the editor's Build on a test server, used the quick reach test and 16 workers: 2 minutes 35
    seconds in all (patch build and cook 32 s). The quick test kept 137 components; 67 changed and are written. This
    is the package installed.
- **The install:** `lab_install.py install`, over run 10's deploy (its record chains back). Installed 7 November,
  11:21.

```powershell
python -B tools/editor/examples/exp17_add_project.py
# in the editor: open the project, Project menu > Build (Ctrl+B); or from the command line:
python -B tools/editor/build.py 7a1f0e17-1111-4e0f-8c6d-2b3a4c5d6e11
python -B tools/lab/lab_install.py install
```

Offline (the floor `XComLevelActor_302`, relit before and after the edit with 32 samples):
- under the copy (8 units in from its edges), the floor's light goes from a median of 7.37 to 0.022, near black;
- within 90 units around it, from 3.98 to 2.07: the other ceiling spots throw its shadow out sideways;
- more than 600 units away, the floor changes by at most 0.003.

Restore (undoes runs 11, 10, 9, 8 and 6 in one go):

```powershell
python -B tools/lab/lab_install.py uninstall <lab>\bake-fixtures\deploys\URB_Bar_EXP17Add_7a1f-20261107-112119.json
```

### What to look at (the user drives, F9 at each)

New campaign as before (the first mission plays `URB_Bar_EXP17Add_7a1f`).
1. The new claw machine: on the open floor under the ceiling lamp at the island counter's far corner from the street
   windows, facing as the original does. The floor right around its base should be dark, its shadow, inside the
   lamp's bright pool.
2. The original claw machine, still against the back wall beside the arcade machine.
3. The cursor or a soldier beside the new one: cover, and its tiles blocked.
4. Everywhere else in the room, including where run 10's moved table stood (this build starts from the original
   map, so the pool table is back by the street windows): as in the original map, with no squares, seams or
   blotches.

### Result (11:29–11:30, F9 shots `look-112959` to `-113022`)

Seven shots: three angled views of the room from the back wall's side, two top-down views around the counter, one
of the counter's other side and one of the back room. The user: "looks good".
- **The copy stands where the project put it**: at the island counter's far corner from the street windows, on the
  edge of the big rug, facing as the original does, its glass and lights lit live like the original's.
- **The original stays** against the back wall beside the arcade machine (angled shots `112959`, `113020`, `113022`).
- **Its shadow.** The lamp is almost straight above the copy, so most of its baked shadow lies under it, out of
  sight. In a brightened crop of `113020` (`<lab>\bake-fixtures\run11\game-113020-claws-lifted.png`, in the lab),
  the planks around its base are darker than the lamp's pool beside it. The darkening is softer than the original's
  contact shadow against the wall, as the offline numbers have it (the floor within 90 units roughly halves).
  The shots don't allow a measured comparison with run 10: the best fit of a run 10 top-down shot overlaps only at
  its edge.
- **The pool table** is back at its own place by the street windows (`113022`): the build starts from the original
  map, as it should.
- **No artifacts:** no squares, seams or blotches in any shot.
- Not shown: the cover beside the copy (no shot has the cursor or a soldier next to it). Its tiles were seeded as in
  run 10, where cover worked.

**Run 11 passed:** a piece added from nothing, built in the editor and installed by the lab installer, plays with
its shadow baked into the floor and the rest of the room unchanged. The build took 2 minutes 35 seconds.

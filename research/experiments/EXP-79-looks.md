# EXP-79: looks from any piece (custom geometry plan, M4, run D)

Date: 18 November 2026. Status: **played** (run D: the walls passed, their faces on five rows the other way round by the script's placing; on the floors map the ground was drawn black and the blocks could not be stood on, fixed offline as F-132 and F-133, and one slab look read its texture wrongly, F-134; the eyedropper passed). The custom geometry plan's stage M4 (branch `fracturing-wall-poc`):
walls, floors, roofs and ground shapes made from numbers in the look of any of the game's pieces of that kind, named
by their donor (`look: {mesh, measure}`), with recipes from the checked-in catalogues (tools/bake/looks/: 344 walls,
55 floors and roofs, 193 ground looks). Run D takes a sample spread over the catalogues' verdicts and settings, each
made piece beside a copy of its donor in the same light. Played unattended in the lab copy (the hidden game, the
game-test skill), checking only what is new. The look is for the user's eye as well: the shots are for them.

## What is new

- Walls made in the look of eleven other maps' walls and one of the bar's (shop interiors, brick, concrete, the pier's
  metal panels, two UFOs, an office, the police station, the research outpost): their outlines, slots, textures and
  heights measured from the donor, two of them lowered from a donor standing over its pivot (the plant's concrete 64,
  the abductor's 192).
- Floors and roofs in six looks: a flat floor, a flat roof, a pitched roof and a thick roof made flat (D13), a
  three-slot floor and a one-slot roof.
- Ground shapes in eight looks, painted ones in their donor's commonest colour (D14), one from a donor placed at 0.6
  and made at scale 1 (M4b item 5).
- Donors from maps never opened in the editor, brought through the library (M4b item 4).
- Pieces drawn with the eyedropper: a wall in the look of the bar's own facade wall, and a slab in the look of another
  map's floor copied into the map.

## The projects

All three are in a test server's scratch store and built with the lighting baked
([exp79_project.py](../../tools/editor/examples/exp79_project.py)).

### `EXP-79 walls` (map `EXP79Walls`)

On the blank map (`CB2_MP_Blank`), its grid made 56 by 54 tiles from its corner (-2112, -1344, 0); the map's own cars
and the floor-corner wall deleted. Tile centres are at x -2064 + 96 i, y -1296 + 96 j. Each row runs east along its
y: a copy of the donor as it stands in its map (turned and moved whole tiles and storeys), its made twin two tiles
on, of the donor's length, and a longer made wall three tiles on, four tiles longer, with a doorway in its middle tile.
Twin and longer wall stand level with the donor's copy.

| Row | Look (donor's map) | y | Donor x | Twin x | Longer wall x (doorway) | Height |
| --- | --- | --- | --- | --- | --- | --- |
| W00 | shop interior (convenience store) | -960 | -1740 to -1256 | -1048 to -580 | -184 to 760 | 0 to 400 |
| W01 | shop interior, two colours (commercial alley) | -576 | -1720 to -680 | -472 to 552 | 872 to 2296 | -16 to 320 |
| W02 | brick shopfront (the bar's facade) | -192 | -1728 to -576 | -288 to 864 | 1152 to 2688 | 0 to 400 |
| W03 | brick over concrete (commercial alley) | 192 | -1739 to -565 | -299 to 897 | 1237 to 2891 | -16 to 256 |
| W04 | concrete (the slaughterhouse plant) | 576 | -1736 to -1448 | -1240 to -968 | -664 to -8 | 0 to 384 |
| W05 | pier warehouse, metal over cinder block | 960 | -1736 to -856 | -584 to 312 | 664 to 2024 | 0 to 395 |
| W06 | pier office, painted metal | 1347 | -1746 to -846 | -594 to 342 | 654 to 2034 | -16 to 262 |
| W07 | UFO, supply ship | 1728 | -1728 to -1152 | -864 to -288 | 0 to 960 | 0 to 192 |
| W08 | UFO, abductor | 2112 | -1728 to -864 | -576 to 288 | 576 to 1824 | 1 to 191 |
| W09 | office interior | 2496 | -1720 to -1436 | -1144 to -876 | -568 to 88 | 0 to 272 |
| W10 | police station | 2880 | -1720 to -1160 | -952 to -408 | -88 to 856 | -16 to 192 |
| W11 | striped brick, stucco inside (research outpost) | 3264 | -1740 to -564 | -300 to 900 | 1236 to 2892 | -16 to 448 |

The longer walls of W02 and W03, W05 and W06, W07 and W08, and W09 and W10 overlap along x, so one grenade between
the two rows reaches both: at about (1700, 0), (1300, 1150), (770, 1920) and (0, 2690).

### `EXP-79 floors and ground` (map `EXP79FloorsAndGround`)

On the blank map, its grid 68 by 66 tiles, the same pieces deleted. The made slabs stand with their tops level with
their donors' copies; each ground look's block (three tiles square, 64 high) and patch stand on a copy of the donor's
plane where it is one, else beside the donor.

| Piece | Donor (map) | Donor's copy | Made |
| --- | --- | --- | --- |
| Flat floor | Core_384CFloorB (EWI_MeldTutorial) | x -1728 to -1352, y -960 to -680, top 400 | x -1152 to -768, y -960 to -672, top 400 |
| Flat roof | URBMilAmmoSubRoof (URB_MilitaryAmmo) | x -480 to 96, y -960 to -576, top 194 | x 288 to 864, same y, top 194 |
| Pitched roof, made flat | ROShedRoof (URB_ResearchOutpost) | x 1136 to 1744, y -980 to -364, 112 to 233 | x 2016 to 2592, y -1056 to -480, top 233 |
| Thick roof, made flat | SubwayCarRoof (URB_TrainStation) | x -1727 to -1441, y 24 to 1800, 294 to 327 | x -1248 to -960, y 0 to 1536, top 327 |
| Three-slot floor | TS_FloorDeck (URB_TruckStop) | x -672 to -288, y 0 to 768, top 210 | x -96 to 288, same y, top 210 |
| One-slot roof | URBSmCemShedRoof (URB_SmallCemetery) | x 576 to 960, y 0 to 672, top 258 | x 1152 to 1536, same y, top 258 |
| Asphalt | Asphalt VP (URB_CommercialAlley) | plane x -1728 to -768, y 2112 to 3072, top 4 | block x -1632 to -1344, y 2208 to 2496; patch x -1248 to -960 |
| Dirt blend (painted) | URB_GasStation_EWI | plane x -384 to 576, y 2112 to 3072 | block x -384 to -96, y 2112 to 2400; patch x 0 to 288 |
| Grass | URB_Demolition_EWI | plane x 864 to 1824, y 2112 to 3072 | block x 960 to 1248, y 2208 to 2496; patch x 1344 to 1632 |
| Snow | EWI_ChryssalidHive | plane x 2208 to 3168, y 2112 to 3072 | block x 2304 to 2592, y 2208 to 2496; patch x 2688 to 2976 |
| Concrete, donor at 0.6 | URB_StreetOverpass_EWI | plane x -1728 to -1152, y 3456 to 4032 | block x -864 to -576, y 3456 to 3744; patch x -480 to -192 |
| Sidewalk | URB_Boulevard | plane x 48 to 816, y 3504 to 4272 | block x 96 to 384, y 3552 to 3840; patch x 480 to 768 |
| Red stone | DLC1_1_LowFriends | x 1132 to 1452, y 3436 to 3764 (a stone, 76 high) | block x 1728 to 2016, y 3360 to 3648; patch x 2112 to 2400 |
| Sandstone | URB_SmallCemetery (donor at 1.01) | x 2686 to 3074, y 3453 to 4132 | block x 3360 to 3648, y 3360 to 3648; patch x 3744 to 4032 |

The asphalt and sidewalk donors are StaticMeshActors: since F-130's fix their shapes' copies are XComLevelActors.

### `EXP-79 eyedropper` (map `EXP79Eyedropper`)

On URB_Bar's parking lot: a copy of URB_TruckStop's floor deck (x -1728 to -1344, y -1440 to -672, top 210); a slab
drawn in the deck's look with the eyedropper (x -1248 to -960, y -768 to -576, top 194); and a wall drawn in the look
of the bar's own facade wall (Core_384FacadeB) with the eyedropper, four tiles along y -1056 from x -1248. Tile centres
are at x -2737 + 96 i, y -1873 + 96 j.

## Run D (hidden game)

`EXP-79 walls`:
1. **Load**: no crash, no error naming a made piece.
2. **The look**, a shot of each row (two rows a shot where they fit) from the default camera and one low: the twin and
   the longer wall in the donor's materials and colours, as tall as the donor, lit like it (not black), the longer
   wall's doorway open.
3. **Breaks**: a grenade at each of the four points between paired rows, and as many of the other longer walls (W00,
   W01, W04, W11) as grenades last: each breaks a fragment at a time near the blast, and nothing far from it goes.
4. **Doorways**: a soldier walks through the doorway of W07's and W05's longer walls.

`EXP-79 floors and ground`:
5. **Load**.
6. **The look**: a shot of each slab pair and of each ground look (block and patch on or beside their donor): the
   made piece in its donor's material and colour; the pitched and thick roofs flat at their top; the concrete block a
   full three tiles (not 0.6 of it).
7. **Standing**: the cursor on the top of the asphalt block (a StaticMeshActor donor, F-130's fix) and of the grass
   block, and a soldier walks onto each: he stands at about 68 + 67 (the block's top) and the cursor reads its top.

`EXP-79 eyedropper`:
8. **Load**, and shots of the facade-look wall beside the bar's own facade, and of the deck-look slab beside the deck
   copy.

## Result

### `EXP-79 walls` (18 November 2026)

Played unattended in the lab copy with saving on (the blank map has no dropship intro: the session waited on the
mission's start). Pictures are in `<lab>\hidden-runs\exp79-runD-walls`.

1. **Load: passed.** The map loaded and the mission started in 11 seconds, with no crash; the made pieces appear only
   in the routine "Cooking Convex" lines.
2. **The look: lit and heights passed; each face's look passed, but on five rows the faces stand the other way round
   from the donor's, by the script's placing.**
   - Every made wall is lit (none black), stands level with its donor and as tall as it (the lowered donors W04 at 64
     and W08 at 192 too), and every longer wall's doorway is open.
   - W00, W02, W04, W05, W07, W09 and W10 look like their donors from both sides (W07's twin a little greener).
   - On W01, W06, W08 and W11 (and most likely W03) the twin's south face shows what the donor shows to the north,
     and the other way round. On W01, for one, the donor shows blue-white plaster to the south and a brick lattice to
     the north, and both made walls the brick lattice to the south (the two pictures from either side show it).
   - Why: each of those donors stands turned in its own map, W03, W06, W08 and W11 a half turn and W01 (a mesh
     measured turned) a quarter turn, and its copy keeps that turn. The made walls stand unturned. The catalogue's
     twin check passes for all twelve: each side of the made wall shows the slot and texture the donor's same side
     shows in the donor's own frame. So the faces are the donor's, turned. In the editor "Flip sides" swaps them.
3. **Breaks: passed at the four points between paired rows.** Each high-explosive grenade broke both walls near the
   blast (a gap of two or three tiles, or an arched hole through the lower part), with the rest of both standing and
   nothing far off broken. The needle grenade broke nothing (it does no damage to the world). W00, W01, W04 and W11
   were not tried: the squad had four high-explosive grenades and no rocket.
4. **Doorways: passed.** A soldier walked through W07's longer wall's doorway (3 tiles, where going round is 10 or
   more) and through W05's.

### `EXP-79 floors and ground` (18 November 2026)

Pictures are in `<lab>\hidden-runs\exp79-runD-floors`.

5. **Load: passed.**
6. **The look: the slabs passed but for two looks; the ground failed, drawn black.**
   - Every made slab is lit. The flat floor, the flat roof and the one-slot roof look like their donors.
   - The pitched roof is made flat at its eaves in its donor's green planks, which run across the donor's: the donor
     stands a quarter turn round in its own map and its copy keeps the turn, as on the walls map.
   - The thick roof (the subway car's) showed the car's white side panel over half its top, where the donor shows
     its tread: the made slab read its donor's texture from its own corner. [F-134](../findings-register.md), fixed
     offline.
   - The three-slot floor has the donor's blue-grey tile without its rust-coloured third: that is the donor's second
     top material, which a made slab doesn't make (the catalogue warns of it).
   - Every made block and patch was black, and so was every copy of another map's ground plane but the two
     StaticMeshActors: on the blank map they listed none of its lights. [F-132](../findings-register.md), fixed
     offline.
   - The concrete block on its 0.6-scale donor is a full three tiles.
7. **Standing: failed on both blocks, by their donors' flags.**
   - The asphalt block's top is picked by the cursor (132, its top 68), and soldiers beside it take cover from it, but
     soldiers ordered onto it from beside it did not move, twice.
   - The grass block's top is not picked (the cursor reads the ground), and a soldier walked into it and stood sunk
     inside.
   - Why: the grass plane saves `bWorldGeometry` off and the asphalt `bCanStepUpOn` off, and the copies kept them.
     [F-133](../findings-register.md), fixed offline.

### `EXP-79 eyedropper` (18 November 2026)

Pictures are in `<lab>\hidden-runs\exp79-runD-eye`.

8. **Load: passed. The deck-look slab passed; the facade-look wall passed on a second reading.**
   - The deck-look slab is the deck copy's blue-grey tile, lit alike, without its rust third (as on the floors map).
   - The facade-look wall shows the dark wood panelling and cap of the piece it was picked from, the bar's
     `XComDecoFracLevelActor_11`: a `Core_384FacadeB`, the pub's ground storey with its window openings, 198 high. The
     run compared it with a shot of the bar where a brick upper storey stands on that piece; the brick is the other
     piece's. Its far face was in shade.

### The EXP-78 re-check (18 November 2026)

Played on the rebuilt `EXP78FarmGround` (the copy of a StaticMeshActor made an XComLevelActor, F-130; the deleted
plane's rebuild volume, F-131). Pictures are in `<lab>\hidden-runs\exp78-runF2`.

- **The block's top: passed.** The cursor read 64 (its top at 0) on all four of the block's tiles (run F part 2 read
  the crater, -64), and a soldier sent from the crater onto (815, -2737) moved 4 tiles and stood on the top at z 67.
- **The old mound's tile (1871, -3025): passed, read from a save.** The baked map had floor there only on level 3 (the
  mound's top); a quicksave from the run has no floor on level 3 and a floor on level 2, at about 0: the tile was
  rebuilt. The block's four tiles lost the crater's and the mound's baked floors and have floor on level 2, the
  block's top.
- [F-130](../findings-register.md) and [F-131](../findings-register.md) are verified.

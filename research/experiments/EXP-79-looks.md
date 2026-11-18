# EXP-79: looks from any piece (custom geometry plan, M4, run D)

Date: 18 November 2026. Status: **prepared**. The custom geometry plan's stage M4 (branch `fracturing-wall-poc`):
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

Not played yet.

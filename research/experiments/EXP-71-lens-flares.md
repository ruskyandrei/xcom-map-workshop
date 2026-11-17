# EXP-71: lens flares

Date: 17 November 2026. The effects and sounds plan's game check after stage FX6b (the flare part of its EXP-F,
section 7.2), in one project on URB_Bar, under Long War (the lab copy). Plain EW is not played in this run. Lens
flares moved, deleted, copied and brought from another map wait for this run: their family (`flare`) is off in the
compiler, and this project's build lifts it (`--family flare`). **Prepared, not played.**

## What the offline checks settled

Read back from the built map (`URB_Bar_X71`, a quick build: a flare changes no baked light) with a fresh reader, as
export 28 reads a map, so the run doesn't need to show them:
- a lens flare is two exports, the `LensFlareSource` actor and the `LensFlareComponent` it owns (`LensFlareComp`);
  the component names the flare's template (a `LensFlare` asset) itself, or its archetype does (Bar's two are made
  from `FX_Lens_Flares.Archetypes.ARC_LF_XCom_Base_C`), and saves the colour. Nothing else of the map names either;
- the moved one is the same export at its new place, still in the level's actor list; the deleted one is out of the
  list with its export kept;
- each copy is an actor and a component of its own in the level's list, at its place and turned as its original is,
  with its original's template, colour and archetype; the originals' bytes are as they were;
- the two flares of AlienBase01 were staged once each (the beacon's glare is copied twice from one staged actor) with
  20 objects brought (65 KB) and 20 reused, no reference cut, and the staged actors are outside the level's list.

What only the game can show: whether a flare draws at all where it is put, whether a copy draws as its original
does, whether a flare of a template the map lacked draws (its materials and textures came with it), whether the
camera's line to a flare hides it as the game's own are hidden, and whether all of it comes back after a load.

## The project

`EXP-71 lens flares` (URB_Bar, [exp71_project.py](../../tools/editor/examples/exp71_project.py)), a quick build. It
compiles with no warning and no note. Marked shots: `EXP-71-street.png`, `EXP-71-row.png`
([EXP-71-shots.json](EXP-71-shots.json)).

Bar's own two flares stand at the two heads of the street lamp by the bar's front corner, 63 units apart: (995,
-221, 344) and (995, -284, 344). Both show `LF_XCom_Base_C` in white at strength 0.03, so they are faint: look at
that lamp in the unedited map first, to know what one of them looks like.

| No. | What | Where (x, y, z) | The prediction |
| --- | --- | --- | --- |
| 1 | Bar's flare `LensFlareSource_7`, moved | (-300, -1200, 150), over the car park | the lamp's glare here, as faint as at the lamp |
| 2 | Bar's flare `LensFlareSource_8`, deleted | it was at (995, -284, 344) | no glare at that lamp any more (1 left it too) |
| 3 | a copy of `LensFlareSource_7` | (-600, -1200, 150) | the same glare as 1 |
| 4 | the hyperwave beacon's glare, AlienBase01's `LensFlareSource_0` (`LF_Hyperwave_Beacon`, colour 2, 0.5, 0.2) | (0, -1200, 150), in the open | an orange glare, as AlienBase01 shows it at its beacon |
| 5 | an alien ambient glow, AlienBase01's `LensFlareSource_3` (`LF_Alien_Ambient_A`, colour 3, 0.5, 0.2) | (300, -1200, 150), in the open | an orange-red glow |
| 6 | the beacon's glare again (the same staged actor, a second copy) | (200, 600, 100), inside the bar's ground floor | drawn only where the camera sees the spot: hidden behind the bar's walls and upper floor, shown through a door or with the floors cut away |

The row 3, 1, 4, 5 stands along y -1200, 300 units apart, 150 up, over the parked cars between the bar and the
street.

## Run 1

What the run adds (Play in game from the editor, on the project; or the hidden game with `URB_Bar_X71` installed):
1. **The lamp (2):** in the unedited URB_Bar, what do the lamp's two flares look like from the tactical camera? In
   this map, are both gone from it?
2. **The row (1, 3, 4, 5):** does each draw where it stands? Are 1 and 3 alike, and like the lamp's in the unedited
   map? Are 4 and 5 orange and orange-red, and is anything drawn as a grey or chequered square? The game's console
   holds each (`getall LensFlareSource Location`, `getall LensFlareComponent Template`,
   `getall LensFlareComponent SourceColor`): six flares, at the places above, each with its template.
3. **Occlusion (6, and 4 for comparison):** with the camera turned so that a building stands between it and 4, does
   4 go? With the bar's roof and upper floor drawn, is 6 hidden, and does it show with the camera's line through the
   front door or with the floors cut away (a flare is in no floor's list, so a cutaway doesn't hide it by a list)?
4. **Save and reload** once: all as before, each flare once (the deleted one still gone, the moved one still over
   the car park, no second copy of any).
5. Anything odd: an error box, a line about lens flares in the log.

Not played yet. When it passes, the `flare` family is switched on in `compiler.FAMILIES` and `flare` joins
`FOREIGN_FAMILIES` (items 4 to 6 are the foreign ones); what fails stays off and is written up here.

## How to build it

`python tools/editor/examples/exp71_project.py <out>` builds it under `<out>` (a scratch folder), `--store` saves it
in the editor's own project store and builds it into the editor's builds folder for Play in game. The cache's
library must be scanned at index 10 (`python tools/viewer/viewer.py library scan`, about half a minute, or the Add
panel's All maps), or `--library <cache>` names a cache whose library is. The build of 17 November (offline, a
scratch folder, read back as above) took four seconds.

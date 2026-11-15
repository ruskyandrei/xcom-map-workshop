# Enemy Unknown's maps as EW/LWR maps

Date: **7 November 2026**. Status: **findings and a plan; nothing built**. The user asked whether the four maps in the
Extra Maps mod (Nexus 686, version 1.0) can be made proper EW/LWR maps, and fixed on the way: a community member saw
black patches on the ground in its Gas Station.

## What the mod is

The zip (`Extra Maps 686 1.0.zip`, extracted read-only to
`<lab>\downloads\extra-maps-686`) holds `URB_Demolition`, `URB_GasStation`, `URB_Museum`, `URB_Museum_Euro` and
a `DefaultMaps.ini`.
- They are **Enemy Unknown's own maps**. Every install has the originals in `XComGame\CookedPCConsole` (the EU side,
  beside EW's `XEW`), compressed, 17 to 21 MB each, with EU's texture caches.
- The mod's copies have the same package GUIDs and name, import and export counts as EU's: the same maps,
  decompressed (165 to 194 MB). The difference is their textures: the mipmaps EU kept in its `Textures.tfc` and
  `Lighting.tfc` are stored in the packages, since EW's caches of those names hold other data.
  - What's left in a cache: 49 to 123 small lightmaps and shadow maps per map still name `Lighting`, but all their
    mips are in the package (in EU's original too), so the name is never read. Five or six shared textures
    (`FX_Shared`, `UI_Cover`, `MarcPackage`) still name `Textures`; EW has its own copies of those.
- The packages are EU's: licensee 59 (EW's are 64), the same engine (8916) and cooker (721031). EW's game loads
  them (the community plays them).
- The mod's records stream three packages the zip doesn't have: `EU2EW_Textures`, `patch_hideroofs` and (Museum)
  `patch_museum_multi`.

## What EW has and these maps lack

- **EW's redux of two of them**: `URB_GasStation_EWI` and `URB_Demolition_EWI` (with small `_CNH` streams). Against
  EU's Gas Station, the redux adds four `XComMeldContainerSpawnPoint`s (EW's Meld canisters), a pod, ladders, 87
  destructibles and 13 merged actors; EU's original has 78 plain `SpotLight`s, a sky light and camera-blocking
  volumes the redux doesn't. Museum has no EW version.
- **No landing intro.** EW's `CIN_DropshipIntros` knows only the redux names. EU's own knows all four:
  `URB_GasStation` at (2421, −2086, 196), `URB_Demolition` at (2536, −2064, 0), `URB_Museum` at (3932, 1264, 448),
  `URB_Museum_Euro` at (4442.6, 1408.2, 448). The redux moved Gas Station's landing to (−4146.3, −581.1, 0), so EW's
  entries can't stand in.
- **LWR knows them, switched off.** LWR's `DefaultLZMutator.ini` has 13 landing zones for the EU names, and its
  `DefaultMaps.ini` has their records commented out (lines 55 to 60).

## The black patches

The community member's shot shows black L-shaped and rectangular patches on Gas Station's forecourt.
- **Not the lighting.** Every lightmap in the mod's map is in the package, and those of the patch pieces checked
  (`AsphaltPatch_*`) are byte-identical to EU's original bake, and lit. A rebake would redo lighting that is right.
- **Likely the asphalt patch pieces**: `XComLevelActor`s 1 unit above the ground, meshes `StreetSet.Meshes.
  AsphaltPatch_LShape`, `_LgRect`, `_SmRect`, `_Square`, `_Circle`, material `StreetSet.Materials.Asphalt_Patch` (masked,
  instances `_R`, `_G`, `_B` picking a channel of `Asphalt_Patch_MASK`). The shapes match; nobody has looked in the
  game yet.
  - Their textures decode the same as EU's.
  - EW's own maps (URB_Bar, URB_GasStation_EWI) have a material of that path and size, but cooked apart: another
    `LightingGuid` and 8 other bytes in its native data. A guess: EW's shader cache doesn't match the EU copy, so the
    pieces don't draw right. Unproven.
- Possible fixes, once the game shows the cause: hide the patch pieces (the Build takes pieces out of a map
  natively since EXP-20 run 8), or give them EW's copy of the material.

## The plan

Make each EU map a base map of our own pipeline, so the Build turns it into an EW/LWR variant package as it does
URB_Bar: from the player's own install, not the mod's files.

1. **Baseline in the lab** (small): the mod's Gas Station in the test slot as it is, to see each problem in the game
   (the patches, the roofs `patch_hideroofs` would hide, no landing, no Meld) before fixing any.
2. **Read EU maps** (small to moderate):
   - accept licensee 59 in `tools/viewer/package.py` (a scratch export of Demolition and Gas Station worked so);
   - check the bake tools on one (native copies, relight, the fixture writer), with tests on EU's originals;
   - export the four into the viewer library with EU's caches linked (`tfc-folder.txt`), so the editor opens them.
     The scratch exports have no play area or tile grid yet (`playableBounds`, `tileGrid` empty): find why.
3. **Textures** (moderate): the Build copies every mip an EU map keeps in EU's caches into the variant's own caches
   (`Textures_<n>.tfc` beside `Lighting_<n>.tfc`), as `lighting_fixture`'s redirect does for lightmaps; it needs
   the same for plain textures and for uncompressed packages.
4. **The landing** (small): the per-variant intro copy (`intro_copy.py`, F-45) renames an EW entry to the variant and
   sets its `SeqAct_SetLocation`'s location to EU's landing; the remote event it fires picks the flight, to match
   EU's where possible.
5. **EW's gameplay pieces** (moderate): Meld spawn points, four per map, made as new actors in the map (as the Build
   makes rebuild volumes, retyped through new imports), placed in the editor as a new kind of piece.
6. **Fixes** from the baseline: the asphalt patches, the roofs, anything else.
7. **Records and landing zones**: LWR's own commented records and its 13 landing zones, renamed to the variant as the
   Build does for any map; rotation stays the player's choice.

Risks: EU-only materials or shaders EW can't draw (the patches may be one); EU classes EW changed; Museum has no EW
redux to compare with.

## Tools used (scratch, not in the repo)

A wrapper that lets the repo's readers take licensee 59 as 64, and scripts for the counts above. They read only:
the mod's files, EU's and EW's installs.

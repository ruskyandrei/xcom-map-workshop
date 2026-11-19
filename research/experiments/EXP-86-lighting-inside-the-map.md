# EXP-86: a built map's baked lighting inside the map file

Date: 19 November 2026. Status: **passed** (LWR map packs; [F-140](../findings-register.md)). A built map whose own
lighting cache is moved inside the map file
([inline_lighting.py](../../tools/bake/inline_lighting.py)) is drawn exactly as with its cache, on LWR 3.00.00 beta
15 from a pack's folder and on LWR 2.x installed the classic way. It costs a little load time and keeps the build's
lightmaps in texture memory for the whole battle. Export map pack now writes every packed map this way, so a pack
has no `.tfc` beside its folder, and since run B every baked build does it itself.

Played unattended (`hidden_game.py`; the beta 15 copy where it stands, `--game`; the LWR 2.x lab copy switched in),
with the game's private memory logged every 2 s and `ListTextures` at the end of each run.

## What was moved

Each texture that names the build's own cache gets every mip inline and uncompressed, NeverStream True and no
cache name, as the game's own `URB_StreetOverpass.ShadowMapTexture2D_173` is kept. The textures of the game's shared
`Lighting.tfc` are left as they are.

| Build | Textures | Mips moved | Bytes moved | Map file |
| --- | --- | --- | --- | --- |
| `Pinkbar` | 2 lightmaps of 1024 | 8 | 1.4 MB | 19.6 MB to 22.0 MB |
| `URB_Bar_X62` | 39 (28 lightmaps, 11 shadow maps, all 1024) | 156 | 29.9 MB | 18.9 MB to 50.1 MB |
| `URB_Demoliti_HoverU_9c4b` | 192 (154 lightmaps, 38 shadow maps) | 745 | 135.2 MB | 23.4 MB to 160.8 MB |

The largest took 3 s to write. A 1024 shadow map with all its mips is one export of 1.4 MB, more than a 1 MB chunk:
the writer cuts chunks only where an export starts (T-14), and every load went through.

## Runs

Each run: the map opened with Play in game's commands and the test squad, no aliens; after the intro, fog lifted,
four or five fixed camera places (`ViewLocation`, `SetOverheadCameraParameters`, `SetCameraYaw 45`) with a shot
each, then `ListTextures`. "Ref" has the build's cache in `CookedPCConsole` itself; "inline" has the inline map
and no cache anywhere.

### LWR 3 beta 15, the map in a pack's folder

| Run | LoadMap to world up | To intro done | Private memory, peak / median after | The build's textures in memory | All textures |
| --- | --- | --- | --- | --- | --- |
| Bar ref 1-3 | 0.33-0.34 s | 18.5 s | 1293-1301 / 1248-1254 MB | 25.5-29.3 of 29.3 MB, streamed | 263-275 MB |
| Bar inline 1-3 | 0.36-0.37 s | 18.5 s | 1294-1296 / 1233-1250 MB | 29.3 MB, resident | 256-267 MB |
| Hover ref 1-2 | 0.38-0.39 s | 10.6-10.8 s | 1356-1386 / 1322-1351 MB | 108 of 132 MB, streamed | 296 MB |
| Hover inline 1-2 | 0.52-0.55 s | 10.5 s | 1352-1356 / 1328-1340 MB | 132 MB, resident | 320 MB |

- **Drawn the same.** Bar: the made floor and the baked light as with the cache; the pictures differ only where the
  soldiers, the movement outline and the interface do. Hover: from ref 1, inline 1 differs no more than ref 2 does
  (0.0-0.7% of pixels by more than 16 of 255, the same shots).
- **Load time.** The map file is read whole, with its lightmaps: about 0.03 s more for 30 MB, 0.15 s more for
  135 MB. The time to the end of the intro does not change.
- **Memory.** A NeverStream texture is resident while the map is loaded. On the bar the camera tour had streamed in
  nearly all of the build's lightmaps anyway; on the large map it had streamed 108 of 132 MB, so the inline map held
  24 MB more in textures at the end (320 against 296 MB, 8%). Before a camera has been everywhere the difference is
  larger, at most the cache's size. The game's private memory showed no difference beyond run to run.

### LWR 2.x, the classic route

`Workshop test pack` exported twice from the same three builds on a test server: v1 by the code before (the caches
beside the folder) and v2 by the code now (`Pinkbar` and `URB_Bar_X62` with their lighting inside, no `.tfc` in the
zip). v2's two maps are byte for byte the ones played on beta 15 above. On the LWR 2.x lab copy, which has no card
reader, `pack.ps1 install` took the classic route for each: the files flat in `CookedPCConsole`, the records added
and URB_Bar's own record commented out for the Replace map.

| Run | LoadMap to world up | To intro done | Private memory, peak / median after | The build's textures in memory |
| --- | --- | --- | --- | --- |
| v1 (caches flat) 1-2 | 0.34 s | 18.4 s | 1283-1288 / 1239-1241 MB | 29.3 of 29.3 MB, streamed |
| v2 (inside) 1-2 | 0.37 s | 18.3 s | 1286 / 1226-1241 MB | 29.3 MB, resident |

- Drawn the same: between v1 and v2 only the movement outline, the ability bar (another soldier selected first) and
  plants in the wind differ; between v1's two runs nothing does. As on beta 15, the landing differs between layouts
  from run timing, not from the lighting.
- `Uninstall` took v1 out (8 files, the two caches among them; `DefaultMaps.ini is exactly as it was before the
  pack`), and v2 after its runs (6 files; the same words). Nothing of either pack is left in the lab copy.
- The logs' warnings are the same set in every layout (only the tile work queue's timing lines differ): nothing about
  a texture or a cache.

## What the runs settle

- The game draws a map's lightmaps from inside the map file: whole mips inline, uncompressed, NeverStream.
- So a pack needs no `.tfc`: on LWR 3 it is one folder under `CookedPCConsole`; the classic route copies no cache.
- The cost is a fraction of a second of loading and the build's lightmaps resident (up to the cache's size in
  texture memory, 132 MB on the largest build there is), with no change in private memory.

## Run B: a map the Build itself made

Since the runs above the Build puts the lightmaps inside the map as its package's last change
([build.py](../../tools/editor/build.py) `lighting_inside`), so no new package has a `.tfc`. `pinkbar` (URB_Bar with
one light changed) was built in full with that code into a scratch builds folder (20 s; stage `inside`: 2 textures,
8 mips, 1.4 MB from `Pinkbar_Lighting.tfc`); the package held `Pinkbar.upk` (20,832,346 bytes, the size Export map
pack made of the same edit's earlier build) and its intro copy, no cache. A test server's manager installed it for
campaigns into the LWR 2.x lab copy (the map and the intro copy flat in `CookedPCConsole`, its record added: no
`.tfc`), and it was played with the four fixed camera places above; then the project's earlier build (its
`Pinkbar_Lighting.tfc` beside the map) was installed the same way and played the same.

| Run | Bring-up | The two moved lightmaps | Pictures against the other run |
| --- | --- | --- | --- |
| B1 inside | 0.20 s | `NormalizedAverageColor0_4`, `DirectionalMaxComponent0_4`: 1024, resident (NO) | centre 0.02%, east 0.51%, west 0.00%, close 0.00% of pixels differ by more than 16 |
| B2 cache beside | 0.20 s | streamed from the cache | |

Drawn the same: the build's own map with its lighting inside is the map EXP-86 played.

Left in the beta 15 copy (no restore after experiments): the folders `Workshop_test_pack` (the inline `Pinkbar` and
`URB_Bar_X62`) and `Workshop_hover_pack` (the inline large map, card 9327); no build's cache is in its
`CookedPCConsole`.

Shots (in `private/shots/EXP-86`): the bar's centre and close-up, ref and inline; the large map's centre and north
east, ref and inline; on LWR 2.x, v1 and v2's centre, east and close-up; run B's four places, inside and cache beside.

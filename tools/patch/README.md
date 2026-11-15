# patchtool: place objects in a tactical map as a streamed patch

`patchtool.ps1` turns a small JSON spec of objects into a cooked streaming patch map and deploys it into the lab copy
of the game, unattended. It automates what EXP-04 did by hand (`research/experiments/EXP-04-place-one-object.md`).

```
pwsh -File tools\patch\patchtool.ps1 all    tools\patch\examples\exp04b.json
pwsh -File tools\patch\patchtool.ps1 t3d    tools\patch\examples\exp04.json
pwsh -File tools\patch\patchtool.ps1 deploy -Map patch_exp04b -Stream 'URB_CommercialAlley_EWI (Commercial Alley Redux) |0'
pwsh -File tools\patch\patchtool.ps1 stream -Map patch_exp04  -Stream 'URB_CommercialAlley_EWI (Commercial Alley Redux) |0'
```

Folders come from the settings (`tools\lab\LabSettings.ps1`, set with `python tools\viewer\viewer.py settings`) unless
given: `-Udk` is the `udk` setting, `-Work` is `<lab>\patchtool` (`<lab>` being the `lab` setting, our lab's working
folder) and `-Game`, the lab copy, is `XCom-Enemy-Unknown` in the Steam library the `lwr` setting names. The editor's
Build passes its own `-Udk`, `-Work` and `-Lwr`.

## Steps

| Step | What it does |
|---|---|
| `t3d` | Writes `<Work>\<name>\<name>-add.t3d`; no editor. |
| `build` | Runs `t3d`, then builds `<name>.udk` in the authoring UDK's `Content\Maps\patches` (details below). |
| `cook` | Runs a PC cook of `<name>`. |
| `deploy` | Copies the cooked map into the lab copy as `XEW\XComGame\CookedPCConsole\<name>.upk`. With `-Stream`, it also edits `DefaultMaps.ini`. |
| `stream` | Only the `DefaultMaps.ini` edit. |
| `unseed` | Puts the original base map back in the lab copy, if it is seeded for this patch (`-Map` or a spec). |
| `all` | `t3d`, `build`, `cook` and `deploy`; with `-Stream`, the INI edit as well. |

- `t3d`, `build` and `all` take a spec. `cook`, `deploy` and `stream` take a spec or `-Map <name>`.
- Exit code 0 on success, 1 on failure. Every step logs to `<Work>\<name>\logs\` and ends with a
  summary.

### `build`

0. Compiles the scripts (`UDK.com make`, windowless, on your desktop) when any package in `UDKGame\Script` is older
   than one of its `.uc` sources. Otherwise the editor would stop at its "scripts are out of date" prompt, which on the
   hidden desktop nobody sees, and the build would fail as "the editor did not open". Its log is
   `<Work>\make-<time>.log`.
1. Copies the base patch to `<name>.udk`.
2. Opens it in the editor through `tools\lab\udk_editor_try.ps1`.
3. Imports the T3D with `MAP IMPORTADD` through the command box. patchtool has its own copy of
   `tools\lab\udk_editor_cmd.ps1`'s sender, which presses Enter once (see the notes below). It checks that the
   import ran exactly once.
4. Runs `ACTOR SELECT ALL` + `EDIT COPY` and checks the copy, which is kept as `editcopy-<time>.t3d`:
   - each new actor is listed under its own name, with the right class, mesh and location;
   - no other new `XComLevelActor` or volume has appeared.
5. Saves through `tools\lab\udk_editor_saveas.ps1`, then checks that the file was rewritten, grew, and lists the new
   actors in its export table.
6. Kills the editor it started.

#### Hidden desktop

The build step, on its own or within `all`, runs on a private Windows desktop, `XComLab-UDK`, which is never shown on
your monitors. The editor and its Save As dialogs can't take your focus, so you can keep playing or working while a
patch builds. `-Visible` runs on your own desktop instead, as before.

- **How it works.** patchtool starts itself again on that desktop as the build step, with the same parameters,
  through `HiddenRun.exe` in the `bin` folder beside `<Work>` (`<lab>\bin` for the lab's own builds). The whole build moves
  there because window lookups and window messages only reach windows on their own desktop. `HiddenRun.exe` is
  compiled from `tools\lab\HiddenRun.cs` when it is missing or older than its source.
- **The cook stays on your desktop, without a window.** The cooker (`UDK.com` or `UDK.exe CookPackages`) exits within
  a second on the hidden desktop, with code 3 and no log; on the normal desktop the same command cooks in 8 s. So
  `all` builds on the hidden desktop, then cooks and deploys in the original run. The cook shares the console of
  whatever runs patchtool and opens no window of its own.
- **Don't give it a new console.** On Windows 11, a new console window is opened by Windows Terminal on your own
  desktop, whatever desktop the program runs on. That is why some empty `UDK.com` terminal windows appeared on
  3 November, during a test that gave the cooker its own console; HiddenRun no longer does that.
- **DirectX 11.** On that desktop the editor runs with `-dx11`. Its DirectX 9 renderer finds no hardware on a desktop
  that is not displayed, and stops at a "does not support floating point render targets" box.
- **Same output.** On 3 November 2026 the `patch_exp05cars` builds were compared, hidden with DirectX 11 against
  visible with DirectX 9: the `.udk` files were the same size and differed only in 53 bytes (package GUIDs and
  stamps), and the `EDIT COPY` texts differed only in `CreationTime`.
- **Speed.** A hidden build takes about 19 s.
- **Clipboard.** The clipboard is shared with your desktop, so the save-and-restore below still applies.
- **Stopping.** Ending patchtool (or `HiddenRun`) ends everything it started there, through a job object.

### `cook`

- Runs `UDK.com CookPackages -platform=PC <name> -unattended -nopause -LanguageForCooking=INT`.
- The cook passes when `CookedPC\Maps\patches\<name>.udk` is fresh and the only error in the summary is the known
  `HQSound_MCMusic` one.
- The cook can delete `CookedPC\HQSound_MCMusic_SF.upk`. If it does, the step restores it from the copy it keeps in
  `<Work>\keep\`, or else from `<lab>\upstream\iiiLiQuiDiii-UDK\UDK-2011-09\UDKGame\CookedPC\`.

### `-Stream <DisplayName> [-Slot 1]`

- Finds the one uncommented `Maps=(...)` line with that exact `DisplayName`.
- Sets the `MapName` of its `StreamingMaps[Slot]` to the patch, or adds that entry if the line has none.
- With `map.shipAs` (see Shipping under a new name), also sets that line's `Name` to the shipped map.
- Backs up `DefaultMaps.ini` to `<Work>\backups\` first.
- Rewrites the file byte for byte (no BOM, CRLF kept) and checks that only that one line changed.

## Safety

- **Running UDK.** The tool will not start if a UDK process is already running. It only kills the editor it started
  itself, and it kills the cook only if the cook times out.
- **Overwriting.** These are refused unless you pass `-Force`, and the old file is backed up first:
  - overwriting an existing `<name>.udk`;
  - overwriting a `CookedPCConsole\<name>.upk` that this tool did not deploy (the ledger is
    `<Work>\deployed.txt`).

  So the hand-made `patch_exp04` and the shipped patches are protected.
- **Game folder.** The tool touches the game folder only when `tools\lab\switch_install.ps1 status` says `active=lab`,
  the `XComLab-copy.txt` marker is present and XCOM is not running.
- **Clipboard.** The clipboard (text, image or file list) is saved before `EDIT COPY` and put back afterwards.
- **Timeouts.** Every wait has one: `-OpenTimeout 90` per editor try (3 tries), 60 s for the window and for the
  clipboard, `-SaveTimeout 180` and `-CookTimeout 900`. The hidden run as a whole is ended after all of these
  together plus 10 minutes.

## Spec

```json
{
  "name": "patch_exp04b",
  "base": "patch_bar",
  "map": { "origin": [-2784, -1920], "tileSize": 96, "groundZ": 3.999993 },
  "nameBase": 900,
  "objects": [
    { "mesh": "CoverPatch.High2x2", "tile": [2, 10], "cover": "Low" },
    { "mesh": "CoverPatch.High2x2", "location": [-2592, -768], "yaw": 90, "cover": "High" },
    { "type": "volume", "tile": [5, 5], "anchor": "center", "half": [200, 100, 128] }
  ]
}
```

### Top-level fields

| Field | Default | Meaning |
|---|---|---|
| `name` | required | Package and file name of the new patch: letters, digits and `_`. Use `patch_...`. It must be unique in the UDK content. |
| `base` | `patch_bar` | The patch to start from: a name in `Content\Maps\patches` or a path to a `.udk` (see below). |
| `map.origin` | `[0, 0]` | World X/Y of the corner of tile (0, 0). |
| `map.tileSize` | 96 | Tile size in world units. |
| `map.groundZ` | 3.999993 | Z used when an object gives none. It is the Z the editor stored for the shipped floor-standing cover patches. |
| `map.name` | | The base map the patch streams into, for example `URB_Bar`. With it, the patch's tiles are seeded (see below). |
| `map.shipAs` | | Ships the base map under a name of its own, for example `URB_BarBlank` (see Shipping under a new name). Needs `map.name`. |
| `map.displayName` | `<shipAs> (patchtool <name>) \|0` | With `shipAs`: the `DisplayName` of the map's own record. |
| `map.inRotation` | `false` | With `shipAs`: `bInRotation` of that record. |
| `map.intro` | `true` | With `shipAs`: add an `XComMapEdIntro`, which gives the shipped map its base map's dropship intro (see Shipping under a new name). |
| `map.timeOfDay` | the base map's | With `shipAs`: `Day`, `Night` or `None` (Temple Ship's), the `TimeOfDay` of that record and of the `-Stream` slot. For a map lit differently from its base map, or a test slot playing a map whose record has another (EXP-14). The game picks maps for a mission by it, and LWR counts night missions by it. |
| `map.streamSlot` | 1 | With `shipAs`: the `StreamingMaps` slot of that record that streams the patch. A number from 0 to 100: a slot the base map's record has gets the patch in place of its map (1 is `patch_bar` in URB_Bar's record), and a slot it lacks is added. `"free"`: the lowest slot the base map's record does not use, added, so that all its streams stay (2 for URB_Bar and TempleShip). Use `"free"` for a patch built on an empty base (see Shipping under a new name). |
| `map.seedExternally` | `false` | The map that streams the patch is shipped by another tool, which applies the seed plan: the relit variant of the base map (`tools/bake/deploy_fixture.py --seed-plan`, EXP-17). `t3d` and `build` plan the seeds and add the rebuild actor as usual; `deploy` seeds no map in the lab (and puts back one seeded for this patch before). Not with `shipAs`, moved ladders or `bake` objects. The editor's compiler writes it with `--stream-only`. |
| `seed` | `true` | `false` turns tile seeding off for the whole patch. An object with `"seed": false` is left out of it. |
| `nameBase` | 900 | Object *i* gets the suffix `nameBase + i`. If any name clashes with an object in the base package, the suffix goes up in steps of 100. |

`base` can also be `""` (an empty map).

- With no map, the editor opens its `Template_MidDay` map: a floor, a sky sphere, a light, fog, a PlayerStart and a
  cube. `build` deletes all of those (`ACTOR SELECT ALL`, `DELETE`) before the import, and fails if anything except
  the spec's actors is left.
- When the first object is a script actor, the T3D leads with a Note (see Leading Note below); the Note stays in the
  map, and the check allows it.
- Tested on 3 November 2026 for `build` only (one block gave a 15 KB map with just its 2 actors). Built and cooked on
  4 November for EXP-08 (`examples/exp08blank.json`: 32 actors and the Note, 20 KB, cooked 128 KB); in game, to
  check.

### Per-object fields

| Field | Default | Meaning |
|---|---|---|
| `type` | `actor` | `actor` places an `XComLevelActor`. `volume` places only an `XComRebuildWorldDataVolume`. `borrow`, `spawn`, `hide`, `copy` and `sun` place script actors (see below). `bake` moves a base-map actor in the lab's copy of the map (see Tile seeds). `ladder` places an `XComLadder` (see below). `photo` sets up the overview view for screenshots (see Overview shots). |
| `location` | | `[x, y]` or `[x, y, z]` in world coordinates. |
| `tile` | | `[tx, ty]` instead of `location`. |
| `anchor` | `corner` | With `tile`: `corner` is origin + 96·t, `center` is origin + 96·t + 48. |
| `z` | `map.groundZ` | Overrides Z. |
| `mesh` | required for actors | `Package.Name`, for example `CoverPatch.High2x2`. |
| `yaw` | 0 | Degrees; written as `Rotation=(Yaw=deg·65536/360)`. |
| `cover` | `Default` | `Default`, `High` or `Low` (`CoverForceFlag`). |
| `collision` | `BlockAllButWeapons` | `BlockAllButWeapons` (as in the shipped cover patches: pawns blocked, shots pass) or `BlockAll`. |
| `hidden` | `false` | `true` writes `bHidden=True`, as the shipped invisible cover patches have. |
| `scale` | | A number (`DrawScale`) or `[x, y, z]` (`DrawScale3D`). |
| `extra` | | Raw `Property=Value` lines added to the actor, for example `"bCanClimbOver=True"`. |
| `volume` | `true` | The rebuild volume for this actor; see below. |
| `half` | 128 | Volume half-sizes, for `type: volume`. |

The `volume` field takes these forms:

- `true`: a ±128 cube at the object's location + (0, 0, 12), rounded to whole units. This is EXP-04's volume, which
  covers a 2×2-tile block with margin.
- `{ "half": n or [x, y, z], "offset": [dx, dy, dz] }` or `{ ..., "location": [x, y, z] }`: a box of your own.
- `false`: no volume.

The tool does not know mesh sizes, so size the volume yourself for anything bigger than 2×2 tiles.

### Ladders

`{ "type": "ladder", "location": [x, y, z], "yaw": 90 }` places an `XComLadder` in the patch, written as the shipped
`patch_bar` writes its own two. It is hidden by default (`"hidden": false` shows it); `mesh` defaults to
`LadderMetal.Meshes.LadderMetalA_448`. `loops` sets `LoopAnimations`, the climb's half loops between getting on and
off (4 by default, for that 477-unit ladder). A shorter ladder can be the same mesh squashed with
`"extra": ["DrawScale3D=(X=1.0,Y=1.0,Z=0.42)"]`: the game takes the climb's top from the mesh's bounds (EXP-08 run 3,
one storey). Its tiles are seeded and rebuilt. A hider whose box holds a hidden one hides it
where it stands (`HideInPlace`), and keeps a visible one (`KeepNames`); other doors and ladders a hider hides go under
the map, so the rebuild gives them no kick links or climbs. The climb needs a floor at the ladder's foot and top after
the rebuild. For a ladder that is both seen and climbed, use one visible ladder object, not a `bCopyLadders` mesh
copy: the mesh takes the foot tile, and there is no climb (F-39).

The tile rebuild gives every ladder in the world a climb when the tiles at its foot and top have a floor, whatever
the ladder's level, visibility or tag (`research/native-code-notes.md`, "How ladder links are made"). `patch_bar` has
a hidden ladder beside each of URB_Bar's ladders, and since our patches are built on `patch_bar`, its two ladders
(`XComLadder_15`, `XComLadder_11`) are in every patch too.

### Overview shots

The authoring UDK can't open a Firaxis map such as URB_Bar, so it never shows the map itself, only our patch's
actors. An overview of a patched map is taken in the game, with a `photo` object in the spec:

```json
{ "type": "photo" }
```

It places an `XComMapEdPhoto`, which, 2, 8 and 20 s after load and then every 10 s:
- pulls the overhead camera out through the game's own `XGCameraView.ChangeOverheadCameraDefaults` (what the cheat
  `SetOverheadCameraParameters` calls): `fov` 45, `distance` 7000, `pitch` -55. A negative pitch looks down; +55 put
  the camera under the map, looking up;
- lights the whole map with an `XComMapEdSun`, a dynamic directional light (`sun` 1.2, from `sunYaw` 138, `sunPitch`
  50 degrees down) and a sky light (`sky` 0.5), both on every lighting channel. A night map otherwise stays dark;
- hides the game's UI as for a cinematic (`hideUI`, true);
- also raises the post-process highlights and mid tones (`highlights` 1.6, `midTones` 1.5). On their own these did
  nothing visible (EXP-07 run 34), but they were on for the shot below.

Those defaults gave EXP-07 run 35's overview of URB_Bar's L layout, which the user called "perfect": from the front
(the north-east, where the east road's white car stands), the whole map in view, well lit, no UI.

Each field overrides one default, for example `{ "type": "photo", "distance": 9000, "sunYaw": 48 }`. A `location` is
optional; the light shines over the whole map wherever the actor stands. To take a shot:
1. Add the object to the spec and run `all` (with the game closed).
2. Start a new mission and wait about 20 s.
3. Turn the camera to the side wanted (the light comes from `sunYaw`; keep it behind the camera) and press F9.
4. Take the object out again and redeploy: it keeps the camera, light and UI that way for the whole mission.

For a shot of a map as shipped, `examples/barphoto.json` is `patch_bar` plus a photo object. Stream it in place of
`patch_bar` (`-Stream`), on the original, unseeded map (`unseed` the patch that seeded it).

## Notes and limits

- **URB_Bar grid.** Tile corners are at multiples of 96, so the origin is (−2784, −1920). The shipped `patch_bar`
  blocks and EXP-04 sit there. The in-game cursor reads one unit lower, for example −2545 for the centre −2544.
- **Cover-patch pivots.** `CoverPatch.High2x2`'s pivot is its centre, which sits on a tile corner. Its footprint is
  the 2×2 tiles around `tile` with `anchor: corner`.
- **Meshes.** `CoverPatch` holds `High2x2`, `High3`, `highcover`, `HalfCover`, `Cover2x4`, `Wall`, `Floor*`,
  `SmallCar` and others. Only `High2x2` has been tested in game (EXP-04).
- **Brushes.** Box brushes are written the way the editor writes its cube brush. The polygon list matches the shipped
  350×250×150 volume line for line. The import warns "unresolved reference to Model'Model_N'"; that is normal.
- **Other collision types.** Collision types other than the two above need component flags that have not been
  checked, so they are refused. Use `extra` if you need one.
- **Do not run the same T3D twice.** `MAP IMPORTADD` renames clashing actors, and the editor does not tell you.
  `build` catches this.
- **`tools\lab\udk_editor_cmd.ps1` runs slow commands twice.**
  - It posts both WM_KEYDOWN and WM_CHAR for Enter. The editor's message loop makes a second WM_CHAR from the
    key-down.
  - A slow command such as `MAP IMPORTADD` pumps messages while it runs, so the extra Enter runs it again. Tested
    3 November 2026: two imports with both messages, one with either alone.
  - The hand-made `patch_exp04.udk` was imported this way and holds the block twice:
    - `XComLevelActor_900` and `XComRebuildWorldDataVolume_900`;
    - `XComLevelActor_0` and `XComRebuildWorldDataVolume_2`, whose components are still named `_900`.
  - Quick commands (`ACTOR SELECT ...`, `EDIT COPY`) are not affected.

## Tile seeds

The game's runtime tile rebuild only re-checks a tile whose baked flags in the map already have something there
(findings register F-29, `research/native-code-notes.md`). So anything a patch adds above the ground, where the map
had nothing, blocks neither line of sight nor movement, however it is placed. When the spec has `map.name`:

- `t3d` runs `tools/upk/seed_map.py plan`, which lists the tiles each `copy` piece, `spawn` and `actor` crosses,
  from tile level 1 up, in `<Work>\<name>\seed-plan.tsv`.
  - Copies use the source piece's box from the map inventory, moved and turned like the copy, plus a quarter tile.
  - Spawns use their `rebuildExtent` box; actors use their rebuild volume.
- `t3d` adds an `XComMapEdTileSeeds` actor, last, which rebuilds every planned box at load. A seeded tile that is
  never rebuilt would keep the seed bit, so this doesn't rely on what the other actors rebuild.
- `build` marks that plan as the one built (`seed-plan-built.tsv`).
- `deploy` writes the original map with bit `0x1` set on the planned tiles that are empty (`seed_map.py apply`,
  which re-encodes and verifies the package), and puts it into the lab as `<map>.upk`.
  - The original comes from the LWR install, read only, once, and is kept in `<Work>\maps`.
  - The lab's map is replaced only when it is the original or the copy patchtool last wrote (ledger
    `<Work>\seeded.txt`); otherwise `-Force` backs it up first.
  - Only one patch's seeds per map: deploying another seeding patch for the same map replaces them, with a warning.
- `unseed -Map <patch>` puts the original back. So does a deploy of the same patch once it seeds nothing.
- Pieces a copier moves (doors and ladders) also take their baked pathing links along (F-30): `t3d` lists them in
  `seed-links.tsv`, and `deploy` moves their links in the seeded map with `tools/upk/world_links.py move`.

- A `bake` object puts a base-map actor somewhere else in the lab's copy of the map itself, so it stands there from
  load. Ladders need this: the rebuild re-makes a ladder's climb links only where it stood at load (F-30).
  - Fields: `actor` (its name in the base map), `location`, `yaw` (degrees, optional), `links` (default `true`:
    move its baked links too), `join` (the index of a copy object).
  - `t3d` lists bakes in `seed-bakes.tsv`. `deploy` runs `tools/upk/bake_actor.py` on the seeded map, then moves the
    links from the actor's old place (from the inventory), turned by the change in yaw.
  - With `join`, that copier lists the actor in `PrePlaced`: it is treated as moved (tag, building caches, logs) but
    not moved again.
  - Only values the map saved can change: an actor saved without a Rotation can't take a new yaw.

Verified on 4 November 2026 (EXP-07 runs 11 and 12): the game loads the seeded map, and copies on seeded tiles block
like the map's own walls.

## Shipping under a new name

A seeded base map can't be shared with the original map's record: its seeded tiles block wherever nothing rebuilds
them (F-42). With `map.shipAs`, a patch ships the base map as a map of its own instead, as the editor's Build will:

```json
"map": { "name": "URB_Bar", "origin": [-2784, -1920], "shipAs": "URB_BarBlank", "displayName": "URB_BarBlank (EXP-08 blank map) |0" }
```

- `t3d` writes `ship.json`, and `build` marks it as built (`ship-built.json`), so that `deploy -Map` knows it too.
- `deploy` puts the base map into the lab as `<shipAs>.upk`: seeded and baked as above, or a plain copy of the
  original when the patch seeds nothing. `<map>.upk` is left as it is; if it was seeded for this same patch before,
  the original goes back.
  - The lab's `<shipAs>.upk` is replaced only when it is missing or is the copy patchtool last shipped there (ledger
    `<Work>\seeded.txt`, under the new name); otherwise `-Force` backs it up first.
- It copies the base map's landing zones in LWR's `DefaultLZMutator.ini` under the new name, after the base map's
  lines, with a comment. If lines for the new name are there already, it leaves them (with a warning if they differ).
- It adds a map record to `DefaultMaps.ini`, after the base map's first record: that record with the new `Name`, the
  `displayName`, `bInRotation` from `map.inRotation` (off by default, so the lab campaign doesn't pick it) and the
  patch in the slot `map.streamSlot` chooses. It is found again by its `DisplayName` and updated if it differs.
- The slot (`map.streamSlot`):
  - **1, the default:** the patch takes `StreamingMaps[1]`, in place of `patch_bar` in URB_Bar's record, as before.
    That suits a patch built on `patch_bar` (the default `base`), which carries `patch_bar`'s actors itself.
  - **`"free"`:** the patch goes into the lowest slot the base record does not use, so the record keeps every stream
    the base map's record has. URB_Bar's record streams slots 0, 1 and 5 (`CIN_DropshipIntros`, `patch_bar`,
    `patch_hide_randomized_objects`), so the patch gets slot 2. This is for a patch built on an empty base (`base`
    `""`), the editor's way (`private/plans/done/first-editor-plan.md`, section 7). Checked in the game on URB_Bar (EXP-10 run 1,
    6 November 2026).
  - **Another number:** that slot, replaced if the record has it, added if not.
  - A slot the record lacks is added at the end of the record, as `-Stream` adds one:
    `StreamingMaps[k]=( MapName="<patch>", Loc=( X=0, Y=0, Z=0 ), Rot=( Pitch=0, Yaw=0, Roll=0 ) )`. LWR's own
    records list slots out of order too (URB_LiquorStore: 0, 5, 2).
  - Replacing a map that is not a patch (its name doesn't start with `patch_`) logs a warning. Temple Ship's slot 1,
    for example, is its arrival cinematic `CIN_TP12A_ArriveTempleShip` (findings register T-08); `"free"` keeps it.
  - Ship files written before `map.streamSlot` (`ship-built.json`) stream the patch in slot 1.
- With `map.timeOfDay`, the record's `TimeOfDay` is set to it instead of the base map's.
- `t3d` adds an `XComMapEdIntro` (unless `map.intro` is false). The dropship intro's Kismet, in the streamed
  `CIN_DropshipIntros`, picks its landing by the exact map name, and a name it doesn't know gets no landing (F-45).
  At load, the actor renames the base map's case in those switches to the shipped map's name, so the base map's
  landing plays. It logs the cases it renamed, or a warning after 30 s. `tools/upk/kismet_links.py` prints a map's
  Kismet links, for checking a base map other than URB_Bar.
- With `-Stream`, the line it edits (the test slot) also gets `Name=<shipAs>`, so the slot loads the shipped map,
  and `map.timeOfDay` if given.
  - `-Stream` still edits only `StreamingMaps[-Slot]` of the test slot (1 by default), not `map.streamSlot`. With
    `"free"`, pass the slot the record got (`-Slot 2` for URB_Bar), and set the test slot's other streams to the
    record's with the `stream` step, so the test slot streams what the record does (EXP-10 gives the commands).
- Both INI files are backed up first, written in one go, and checked: only the planned lines may differ.
- `unseed` makes `<shipAs>.upk` a plain copy of the original. It does not take out the record or the landing zones.

Tested on 4 November 2026 (EXP-08 run 1): `URB_BarBlank.upk` shipped, 7 landing zones and the record written, the
test slot pointed at it; a second deploy changed nothing.

The record rewrite is checked without the game by `tools\patch\tests\test_ship_record.ps1`. It takes the functions
from `patchtool.ps1` and runs them on real record lines (`tests\defaultmaps-records.txt`, copied from LWR's
`DefaultMaps.ini`). For example, slot 1 still gives EXP-08's record byte for byte. With
`-Config <a Config folder>`, it also runs `Set-ShipConfig` on temporary copies of that folder's `DefaultMaps.ini`
and `DefaultLZMutator.ini`, and only reads the originals:

```
pwsh -NoProfile -File tools\patch\tests\test_ship_record.ps1 -Config "<LWR install>\XEW\XComGame\Config"
```

## Script actors (package XComMapEd)

Seven object types use script classes compiled into the authoring UDK's `XComMapEd` package
(`Development\Src\XComMapEd\Classes`), which each patch then carries. What a spawned object needs in order to behave
like the game's own (lighting, tiles, glass, fire, saves, landing zones) is tracked in
[`research/findings-register.md`](../../research/findings-register.md).

| Type | Class | What it does in game |
|---|---|---|
| `borrow` | `XComMapEdBorrowedMesh` | Shows a mesh already in memory, normally from the base map. Fields: `copyFrom` (an actor or archetype whose mesh and materials to copy), `meshPath`, `materials`, placeholder `mesh`, `yaw`, `scale`. Visual only: no collision or cover. Firaxis puts materials on components, so a bare `meshPath` renders flat grey; use `copyFrom` or `materials`. |
| `spawn` | `XComMapEdSpawner` | Spawns the game's own actor from an archetype in memory, for example a car body (`XComDestructibleActor`) plus its glass as `partner`. Fields: `archetype`, `partner`, `partnerOffset`, `tint` [r, g, b], `rebuildExtent`, `yaw`. The spawned actors have the archetype's collision, cover and destruction. With `BuildingName=<building volume>` and `BuildingFloor=<n>` in `extra`, the spawned pieces join that floor of the building in its floor caches, so the cutaway hides them with it (a car on a copied roof). With `bSnapToTiles=True` the spawner moves the pieces (up to half a tile) so the body fills whole tiles, as the map's own cars stand; off the grid a car's ends block their tiles and give no cover (F-41). The spawned pieces leave out a units-only sky light as copies do (`bKeepSkyLight=True` opts out). |
| `sun` | `XComMapEdSun` | A light over the whole map, all dynamic: a directional light (`sun`, brightness 1.2) from `yaw` 138, `pitch` 50 degrees down, and a sky light (`sky` 0.5), on every lighting channel. The photo object's light on its own, without its camera and UI changes; for a map whose own lights a hider took out (EXP-08). A `location` is optional. |
| `photo` | `XComMapEdPhoto` | The overview view for screenshots (see Overview shots): camera pulled out, a sun and sky light over the map, the UI hidden. Fields: `fov`, `distance`, `pitch`, `sun`, `sky`, `sunYaw`, `sunPitch`, `highlights`, `midTones`, `hideUI`, `extra`; `location` optional. |
| `hide` | `XComMapEdHider` | Takes the base map's actors in a box out of play at load (EXP-07): every placed mesh, fractured actor, door, ladder, physics actor, emitter and decal whose centre is in the box is hidden and loses its collision, the building, floor and cursor volumes there lose theirs, and the tile data over the box is rebuilt. Fields: `location` (the box centre, with z), `half` [x, y, z], `keep` and `alsoHide` (actor names in the base map), `extra` (for example `bHideLights=True`, `bHideFragments=True`, `KeepGroundHeight=40`). Anything lying wholly within `KeepGroundHeight` of the box floor stays (the ground). It logs a tile census of the box before and after. It keeps cursor volumes (they can span the whole map; `bHideCursorVolumes=True` takes them too), a patch's own volumes, and pieces a copier moved. |
| `copy` | `XComMapEdCopier` | Copies pieces the base map placed to a new place at load (EXP-07): walls and roofs (fractured actors) as `XComMapEdWall` with their fragment columns moved along, windows and props as `XComMapEdDestructible`, plain level meshes as `XComMapEdLevelPiece`, all lit dynamically. Doors and ladders are moved instead: the base map's own actor goes to its new place, keeping its name (each can be used once). With `bCopyDoors=True` in `extra`, doors are copied instead (`XComMapEdDoor`), so the base map keeps its own. With `bCopyLadders=True`, ladders are copied as plain meshes with no collision, and the source keeps its baked links. Don't use it for a ladder to climb: the mesh takes the ladder's foot tile (F-39). Use a visible `ladder` object instead. `LadderFootRebuild=<seconds>` rebuilds the foot tile of each ladder near the copies once more, last, and logs its floor (the climb is made from the foot tile). `bLogCursor=True` logs the 3D cursor's position and tile whenever its tile changes: point at a spot in the game and read it back from the log. `LateRebuild=<seconds>` rebuilds the tiles over the copies once more after load, when everything else stands; `CopyScale=(X=..,Y=..,Z=..)` scales each copy. Copies of baked pieces (not doors) leave out a sky light that lights units only but reaches light environments, as Temple Ship's does: `XComMapEdSkyFree` switches it off and lights the units with a copy of it on Gameplay_1 only, the units' channel, as most maps' sky lights (F-52; EXP-14 run 12). The map's doors and debris lose it too. On other maps the sky lights stay as they are. `bKeepSkyLight=True` opts out. `CopyLights(<i>)=(Mode=1,bBooleanShadow=True)` sets destructible copy i's light environment for trials: mode 1 is the game's door setting (an SH light), `bBooleanShadow` shadows the map's lights by the static world. Fields: `from` (the pieces' names in the base map), `pivot` [x, y, z] (the point of the sources that lands on `location`), `location`, `yaw` (a multiple of 90), `building`, `inBuilding` (the index of an earlier copy object whose building these copies join), `extra` (for example `bLogTiles=False`). With `inBuilding`, `BuildingFloor=<n>` in `extra` puts every copy on that floor of the building in its floor caches (cutdown floor 0) instead of the floor its source's entry gives: a floor slab copied up a storey (EXP-08 run 3). `building` is `{ "floors": [[floor volume names], ...] }`: the base map's floor volumes per floor, moved and turned like the copies, inside a new `XComBuildingVolume` (`margin`, `below`, `above` size it around them; needs `map.name`). The copier rebuilds that building's floor caches once the copies exist, for the cutaway. Rebuilds the tile data over the copies. Put copy objects before any `hide` object. A copy rebuilt by a load (a save keeps damaged pieces) asks its copier to fill it again (F-17). **Break groups** (the editor's groups that break together): `breakGroups` gives a group number per name in `from` (0 for none), and `breakOriginals` lists the base map's own pieces, left in place, that break with a group (`[{ "name": "XComDestructibleActor_61", "group": 1 }]`). At load the copier links each group's destructible pieces: when one is damaged or destroyed, the others are put in the same state (a copy passes it on from its own hits; a base-map piece through the game's `AffectedChildren`). |

- **Leading Note.** `MAP IMPORTADD` silently drops the first actor of a file when it is non-static, so `t3d` puts
  a `Note` first when the first object is a `borrow`, `spawn`, `hide` or `copy`.
- **Archetype paths.** Find them in the base map with `python tools/upk/upkinfo.py <map>.upk exports`, for example
  the `...Prefab.PRE_*_ArcN` objects.
- **Actor names and building volumes.** `python tools/upk/map_inventory.py <map>.upk <out>` lists every actor with
  its class, mesh, box, tiles and building volume, and each building's floors and contents (for `hide`).
- **Free space.** `python tools/upk/map_layout.py <map>.upk <out> --window 0 52 0 39` draws the map's
  ground-level occupancy.

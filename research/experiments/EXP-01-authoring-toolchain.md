# EXP-01: authoring toolchain (record)

This file is the record for EXP-01 in the investigation plan. Supporting files are in [`EXP-01/`](EXP-01/).

**Status (3 November 2026, 18:50): pass.**

- **The editor works.** The authoring UDK, with the LiQuiD911 project merged in, compiles, opens `patch_bar` and saves and reopens a map.
- **The cook reproduces the shipped patch.** A **PC** cook of `patch_bar` matches the `patch_bar.upk` shipped in this LWR install except for one GUID.
- **One config fix was needed.** The project's config freezes the editor; a two-line fix resolves it.

## Set-up

| Item | Value |
|---|---|
| UDK | September 2011 (`UDKInstall-2011-09-BETA.exe`), installed by the user to `<lab>\author\UDK-2011-09` (no version subfolder). Engine 8916, changelist 1009027. |
| Untouched copy | `<lab>\snapshots\UDK-2011-09-pristine` |
| Project | `<lab>\upstream\iiiLiQuiDiii-UDK`, at `80be6f4c21b665e0c261bee224429cb36c3fc217` |
| Build snapshot | `<lab>\builds\exp01-merged-2026-11-03`: compiled `Script\`, the project's `Config\` as shipped, original `build.properties` |
| Cook outputs | `<lab>\builds\exp01-cook-2026-11-03`: `PC\patch_bar.udk`, `PCConsole\patch_bar.upk`, cook logs |
| Logs | `<lab>\logs\exp01-*` and `udk-try-*.log` |

## Step 1: stock UDK

- **Compile.** `Binaries\Win32\UDK.com make -unattended -nopause` reports "No scripts need recompiling", 0 errors.
- **Editor.** Both `Binaries\Win32\UDK.exe editor` and `Binaries\Win64\UDK.exe editor` reach the main window (`Untitled - Unreal Development Kit (32-bit, DX9)` and 64-bit), with the viewport rendering. Screenshot: `<lab>\logs\exp01-stock-editor-Win32.png`.
- **Saving a tiny map in the stock editor was not done.** Map save and reopen were checked after the merge instead (step 4).

## Step 2: merge

- **Copy.** Robocopy of the project's `UDK-2011-09` tree onto the install: 1,652 files. The full list is [`EXP-01/merge-files.txt`](EXP-01/merge-files.txt).
- **Overlapping files.** 1,290 have identical content to stock. **10 replace stock files:**
  - **Core and Engine scripts:** `Core\Classes\Object.uc` and `Engine\Classes\{Actor, AmbientSound, Engine, KAsset, LevelStreaming, PlayerStart, WorldInfo}.uc`. These add XCOM enums and structs, drop some `const`/`editconst`, and add `native function ForceDestroy` to `KAsset`.
  - **Config:** `UDKGame\Config\DefaultEngine.ini` and `UDKEngine.ini`.
- **352 new files:**
  - **Script sources:** `XComGame` (147 stubs), `XComUDK` (40), `XComMapCleaner` (14), `XComModMusicOverride` (1) and 4 Engine files.
  - **Content:** about 40 content packages, 102 maps under `Content\Maps`, and `CookedPC\HQSound_MCMusic_SF.upk`.
- **Package list.** The merged config drops `UTGame`/`UTGameContent` and adds `XComGame`, `XComUDK`, `XComModMusicOverride` and `XComMapCleaner` to the edit packages.

## Step 3: script compile

`UDK.com make -unattended -nopause` (Win32), log `<lab>\logs\exp01-merged-make.out`:

- **Result:** **Success, 0 errors, 433 warnings**, in 29 s. All 15 packages saved, including `XComGame.u` and `XComUDK.u`.
- **Where the warnings are:** 475 of the 483 warning lines are in `XComGame`. Almost all are "Invalid property value in defaults" for assets the stubs refer to but the UDK doesn't have (force-feedback waveforms, `XComFloorComponent`, light environments, static meshes). The rest are config/localized properties listed in defaults.
- **No missing classes, native-layout errors or shader errors.**

## Step 4: open `patch_bar`, save a copy, reopen

### The editor froze while loading `Engine.u`

- **Symptom.** With the project's config, the editor (32- and 64-bit, and on 2 cores) spun one core at the splash screen "Loading file: Engine.u". The last log line was `Waited … for async package '..\..\UDKGame\Script\Core.u'`. It froze in 7 of 7 tries.
- **Prior report.** LiQuiD911 reported the same freeze in 2015 and needed about ten restarts.
- **Bisection:**

  | Config | Result |
  |---|---|
  | Merged scripts + stock config | opens in 2 s |
  | Stock config + the project's `[Engine.ScriptPackages]` | freezes |
  | The same section without its `NativePackages=Core` and `NativePackages=Engine` | opens in 3 s |

- **Cause.** The project's `DefaultEngine.ini` adds `+NativePackages=Core` and `+NativePackages=Engine`. The stock base config already loads both as `EngineNativePackages`, and the duplicate entries make the startup loader spin.
- **Fix applied.** Both lines are commented out in `DefaultEngine.ini` and removed from `UDKEngine.ini`; see [`EXP-01/fix-duplicate-native-packages.diff`](EXP-01/fix-duplicate-native-packages.diff). `XComGame` stays native, as the project ships it.
- **Encoding pitfall.** Rewriting the INI with a UTF-8 byte-order mark hid its first `[Configuration]` section. That section holds `BasedOn=`, so the editor regenerated a broken `UDKEngine.ini` and asked to rebuild the scripts. The INIs must stay without a BOM.

### Result

- **The editor opens `patch_bar` in 6 s.** There are no load failures. The only log warnings are the stock "Can't find edit package `OnlineSubsystemGameSpy`/`OnlineSubsystemLive`" and "Duplicate class names … `SeqAct_ToggleHidden`".
- **What it shows.** The ladder mesh, volumes, a light and the player start are visible. The scene is dark because lighting isn't built. Screenshot: `<lab>\logs\exp01-patch_bar-editor.png`.
- **Save and reopen.** `UDK.com ResavePackages -PACKAGE=patch_bar_exp01` on a renamed copy reported "Correctly saved", 0 errors, as package version 845, licensee 0. A fresh editor then reopened `patch_bar_exp01` with the same clean log.
- **Not yet looked at in the GUI:** the Kismet links and actor properties. The log shows every class and object resolving.

**Helper:** `tools\lab\udk_editor_try.ps1 -Map <map> [-Bits Win64] [-Cores N] [-Tries N] [-Close]`. It starts the editor with `-forcelogflush`, waits for the map to finish loading and kills a frozen editor. It keeps each try's log.

## Steps 5–6: cooking and package checks

### Target: the shipped `patch_bar.upk`

| Field | Value |
|---|---|
| Package version / licensee | 845 / 0 |
| Engine / cooker | 8916 / 135 |
| Compression | LZO (flags 2) |
| Package flags | `0x28a0009` |
| Contents | 251 exports, 142 imports, 320 names |
| XCOM actors | 15 `XComLevelActor`, 15 `XComFloorComponent`, 8 `XComRebuildWorldDataVolume` |
| Other | Kismet, plus embedded `XComUDK` helper classes |

### PCConsole cook

- **Command:** `UDK.com CookPackages -platform=PCConsole patch_bar -unattended -nopause -LanguageForCooking=INT` → `UDKGame\CookedPCConsole\patch_bar.upk`.
- **Header:** the same version, cooker and flags.
- **Content:** different (221 exports). The cooker merged the 3 static point lights into a `StaticLightCollectionActor`, dropped 4 brushes and stripped the helper classes' script text. All XCOM actors, Kismet and helper classes match. See [`EXP-01/patch_bar-shipped-vs-cooked.txt`](EXP-01/patch_bar-shipped-vs-cooked.txt).

### PC cook: reproduces the shipped file

- **Command:** `UDK.com CookPackages -platform=PC patch_bar -unattended -nopause -LanguageForCooking=INT` → `UDKGame\CookedPC\Maps\patches\patch_bar.udk`.
- **Match:**
  - **Headers:** identical.
  - **Names, imports and exports:** identical name tables, and the same 251 exports and 142 imports by class and object path.
  - **Size:** the same file size (67,907 bytes).
  - **Data:** **all 251 exports byte-identical** after decompression.
- **The only difference:** 16 bytes, the GUID of the embedded `XComUDK` package export. Shipped is `b30a92b1…`; ours is new because our `XComUDK.u` was compiled separately. See [`EXP-01/patch_bar-shipped-vs-cooked-PC.txt`](EXP-01/patch_bar-shipped-vs-cooked-PC.txt).
- **So:**
  - LWR's patch maps are **PC** cooks of this project's maps.
  - For the game, rename `.udk` → `.upk`.
  - The plan's PCConsole suggestion and the `UDK=1` change in `Binaries\build.properties` are not needed for the commandlet. `build.properties` was put back.

### XComUDK builds in the shipped patches

Of the 90 shipped `patch_*.upk`, 76 embed `XComUDK`, from 8 different builds:
- 59 have GUID `b30a92b1…`;
- 17 have one of the 7 other builds;
- the other 14 embed none.

See [`EXP-01/shipped-patch-xcomudk-guids.txt`](EXP-01/shipped-patch-xcomudk-guids.txt). The live game already loads patches built from several XComUDK compiles, so a recooked patch with a new GUID is not unusual. Whether two different builds can share one mission is still EXP-03's question.

### Cooker quirks

- **A spurious error from the always-cook list.** Both cooks end "Failure - 1 error(s)", only because `[Engine.PackagesToAlwaysCook]` lists `HQSound_MCMusic`, whose source isn't in the project (only the pre-cooked `_SF` file is). The map still cooks. Removing the three music entries would give clean exit codes; not done yet.
- **The PC cook can delete a project file.** When the PC cook finds its cooker data out of date, it clears `CookedPC`. That deleted the project's `CookedPC\HQSound_MCMusic_SF.upk`, which was restored from the upstream checkout. Recheck after every fresh PC cook.
- **UDK caches.** Cooking also writes UDK's own `Textures.tfc`, `CharTextures.tfc` and shader caches next to the map. **Never copy those into the game.** Only the map file goes into a runtime copy.

## Next

- **EXP-03.** Swap the recooked `patch_bar` into the lab copy, then compare the LoS, cover and ladder checks with the shipped file. Hash and back up the shipped file first.
- **Optional GUI look at Kismet in `patch_bar`.** Kismet nodes may sit at (0, 0) after cooking, which is cosmetic.

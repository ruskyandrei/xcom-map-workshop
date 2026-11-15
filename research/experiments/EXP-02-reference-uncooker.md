# EXP-02: reference UDK and Uncooker (record)

This file is the record for EXP-02 in the investigation plan.

**Status (3 November 2026, 19:10): viewing works.**

- **What works.** The Uncooker converted LWR's cooked content: 6,988 packages, 13 GiB. That needed one repair to its input copy and a pseudo-console wrapper. The reference editor opens `URB_Bar`, `CB2_MP_Blank` and the bomb stream `URB_CemeteryGrand_Bomb` with art, XCOM actors, volumes and Kismet.
- **Open issue.** The optional asset database crashes.
- **Not done yet.** Plan steps 3–5 (recording transforms and Kismet, comparing with property dumps, transferring an arrangement) haven't started.

## Set-up

| Item | Value |
|---|---|
| Reference UDK | `<lab>\reference\UDK-2011-09`: a robocopy of the user's fresh UDK install, never launched before the setup |
| Untouched copy | `<lab>\snapshots\UDK-2011-09-pristine` |
| Uncooker | v1.1.0 release, `<lab>\tools\xcom-uncooker-v1.1.0` (SHA-256 in `<lab>\downloads\SHA256SUMS.txt`). Needs .NET 8, which is installed (8.0.26). |
| Input | `<lab>\uncooker-input\CookedPCConsole`: a robocopy of the lab copy's `XEW\XComGame\CookedPCConsole` (5,073 files, 7.61 GB). The game installs are never read by the Uncooker. |
| Output | `<lab>\reference\UDK-2011-09\UDKGame\Content` |

### UDK setup installer (run by the user, 18:40)

`xcom-uncooker-udk-setup.exe` is an Inno Setup wizard. Its [script](https://github.com/chrishayesmu/XCOM-Uncooker/blob/v1.1.0/InnoSetup/create-installer.iss) has no licence page. It can't run silently, because the UDK folder is chosen on a custom page.

What the setup changed in the reference UDK:
- **Deleted:**
  - the `Development\Src\Core`, `Engine`, `UTEditor`, `UTGame` and `UTGameContent` sources;
  - the `UDKGame\Content\Maps`, `Mobile`, `Shared`, `Showcases`, `TestPackages` and `UT3` folders;
  - the SM5/OpenGL shader caches;
  - `UTEditor.u`, `UTGame.u` and `UTGameContent.u`.
- **Copied in:**
  - **Config:** `UDKGame\Config\DefaultEditor.ini`, `DefaultEngine.ini` and `DefaultEngineUDK.ini`.
  - **Script sources:** its own `Core` (10 files) and `Engine` (1,306), plus `XComGame` (1,123) and `XComStrategyGame` (241).
- **Shortcuts:**
  - "Open UDK Editor": `Binaries\Win64\UDK.exe editor`;
  - "Update Asset Database": `Binaries\Win64\UDK.exe CheckpointGameAssetDatabase -verbose`.

### Running the Uncooker unattended

- **Arguments.** `XCOM-Uncooker.exe <CookedPCConsole> <output>` takes both paths on the command line (Program.cs).
- **What it reads.** It skips `patch_*`, shader caches and `GlobalPersistentCookerData`. Its shader-cache writing code is compiled out (`#if false`), so it only reads its input.
- **It needs a real console.** It sets `Console.CursorVisible`, so with redirected output it crashes at once with "The handle is invalid". `winpty -Xallow-non-tty` fails too (no terminal size).
- **The workaround.** `tools\lab\ConPtyRun.cs` (built to `<lab>\bin\ConPtyRun.exe`) runs it inside a Windows pseudo console and logs everything to `<lab>\logs\exp02-uncooker.vt`, raw with escape sequences. The child must be started with `STARTF_USESTDHANDLES` and null handles, or it writes to the parent's redirected pipes instead.

## Uncooking runs

### Run 1 (18:44): crashed loading LWR's patched script packages

- **The crash.** After about 1 minute of loading archives, it threw `System.OverflowException` in `FArchive.SerializeDependsMap` (`FArchive.cs:1076`) inside its parallel loader. The exception doesn't name the package.
- **Leftovers.** It left `%TEMP%\XComUncooker_ttjwmtmo.t5g`: 4,666 decompressed files, 4.85 GiB on C:. Its own cleanup failed on a locked file, and the folder was deleted by hand.
- **Diagnosis.** `tools\upk\check_depends.py <CookedPCConsole>` reads every package the Uncooker loads. Results: 4,654 are compressed; 281 are uncompressed, and three of those are LWR-patched script packages whose depends map has **fewer entries than exports**:

  | Package | Exports | Entries | Exports without an entry |
  |---|---|---|---|
  | `Engine.upk` | 27,500 | 27,496 | `Camera.DoUpdateCamera.UW_LocalPlayer`, `UW_ViewportSize`, `UW_FOVRatio`, `UW_MapName` |
  | `XComGame.upk` | 56,775 | 56,771 | `XComInputBase.ConvertUIPointToScreenCoordinate.UW_*` (4) |
  | `XComStrategyGame.upk` | 22,627 | 22,619 | 8 locals and properties in `XGInterception` / `XGInterceptionEngagement` |

- **Why the Uncooker overflows.** The missing objects are exports appended by a patching tool. The same `UW_*` objects cause the game's own "duplicate NetIndex" log errors. Each map ends exactly where the first export's data begins, so a reader that takes `ExportCount` entries reads export data as counts. The game doesn't use the map for cooked packages.
- **The 12 fully LZO-wrapped packages** (`Core`, `GameFramework`, `Startup*` and others) also fail the simple header read, but the Uncooker decompresses those itself.

### Repair, in the Uncooker's input copy only

- **What it does.** `tools\upk\repair_depends.py` copies each map to the end of the file, adds a zero-count entry for every missing export, and rewrites the summary's `DependsOffset`. No other bytes move, so export and bulk-data offsets stay valid.
- **The three files:**

  | Package | Entries added | SHA-256 before → after (prefix) |
  |---|---|---|
  | `Engine.upk` | 4 | `1acf57b4…` → `112ceab1…` |
  | `XComGame.upk` | 4 | `27b98aa4…` → `6d89e174…` |
  | `XComStrategyGame.upk` | 8 | `e84c4661…` → `b81d7a1d…` |

- **The lab copy's originals are unchanged.**

### Run 2 (18:47): repaired input; crashed in the console display

- **Loading worked.** Loading and deserialization worked (4,666 of 4,947 archives decompressed to temp). It assigned 1,311,702 objects to 7,009 packages.
- **Then it crashed.** `Konsole.Window` threw `ArgumentOutOfRangeException` (cursor row 50) because the pseudo console was only 200×50.
- **The fix.** `ConPtyRun.exe` now takes `--size=<cols>x<rows>`, so the next run used `--size=240x400`.

### Run 3 (18:50–18:58): success

- **Command:** `<lab>\bin\ConPtyRun.exe --size=240x400 <lab>\logs\exp02-uncooker-3.vt XCOM-Uncooker.exe <input> <output>`. The text log is `<lab>\logs\exp02-uncooker-3.txt`.
- **Run:**
  - **Timing.** 8 minutes in total: about 1.7 to load, 2 to plan and 4.3 to write.
  - **Output.** "After filtering, will serialize 6988 archives". It wrote **6,726 `.upk` and 265 `.udk` maps, 13.05 GiB**, all under `Content\XComGame` (for example `Maps\URB_Bar.udk`, 49.9 MB, and `Maps\CB2_MP_Blank.udk`).
  - **Warnings.** None logged; 967,750 repeated objects were skipped as duplicates.
- **Disk.** Temp peaked at 4.85 GiB on C: and was removed. The plan's 80–120 GiB allowance is far more than needed.

### Replacement packages (README step 5)

- **The copy.** `replacement-packages\XComGame` (23 files, 97 MB) was copied onto `Content\XComGame`. 19 replaced existing files, which shows the location is right. The replaced uncooker outputs are kept in `<lab>\snapshots\reference-uncooked-originals-replaced`.
- **A layout mismatch.** 4 replacements were left as duplicates, because v1.1.0 puts these packages in subfolders while the replacement set uses the older flat layout: `FX_CHA_FloaterSoldier` and `FX_CHA_Thinman` (`Packages\FX\Characters`), `FX_Destruction` (`…\Destruction`) and `FX_Environmental` (`…\Environmental`). The corrected versions were moved into the subfolders, the uncooked ones kept in the same snapshot folder, and no duplicate package names remain.

### Scripts and asset database (README step 6)

- **Compile.** `Binaries\Win64\UDK.com make -unattended -nopause` reports 0 errors and 116 warnings in 13 s, and compiles `Core`, `Engine` and the rest up to `XComGame.u` and `XComStrategyGame.u`. 140 of the warning lines are in `XComGame` and 26 in `Engine`.
- **Asset database: crashes (open).** `Binaries\Win64\UDK.com CheckpointGameAssetDatabase -verbose -unattended -nopause` fails about 6 s in, with exit `0xC0000005`:
  - **The assertion:** `Assertion failed: i>=0 && (i<ArrayNum…) [Array.h:575]`, in `FGameAssetDatabase::GatherAssetsFromPackageLinker` → `LoadObject<UClass>` (it found 7,030 packages).
  - **What it last logged:** with `DevAssetDataBase` unsuppressed, the last lines are NetIndex errors for `SimpleShapes`, `gfxInterfaceMgr` and `EXT_PROP_Powerlines` (`SkeletalMesh … SM_PROP_Powerline with invalid NetIndex 3 (max: 2)`). The failing package isn't named. Unsuppressing `DevLoad` added nothing.
  - **Config left unchanged:** the reference `UDKEngine.ini` was restored after each diagnostic run (backup `<lab>\logs\reference-UDKEngine.ini.bak`).
  - **Impact:** the database is optional. Without it the Content Browser doesn't list all assets at once, but packages and maps open normally.
  - **To identify the package:** bisect by temporarily moving package folders out of `Content`, or trace file access.

## Viewing results (19:01–19:09)

All with `tools\lab\udk_editor_try.ps1 -Udk <lab>\reference\UDK-2011-09 -Bits Win64 -Map <map>`:

| Map | Open time | Log | Notes |
|---|---|---|---|
| `URB_Bar` (49.9 MB) | 28 s (787 MB RAM) | 0 critical. 6 failed loads, all stock UDK objects absent from this install (`UDK_APEXDamageMap`, `UI_Fonts_Final` HUD fonts, `A_Interface` radio chirps). About 17 material instances on `BLDG_Floors` failed to compile. 4 NetIndex errors on destructible-archetype `StaticMeshCue`s. | Textured art renders: the bar front and sign, brick, awnings, kegs and the street. Some objects show the red/white default-material squares. Screenshot: `<lab>\logs\exp02-URB_Bar-reference-editor.png`. |
| `CB2_MP_Blank` | 6 s | 0 critical; the same 6 failed loads; 0 material failures | |
| `URB_CemeteryGrand_Bomb` (bomb stream) | 7 s | 0 critical; the same 6 failed loads; 0 material failures | **Mission structure is intact.** Kismet includes 178 `SeqVar_Named`, 87 `SeqCond_CompareBool`, 36 `SeqEvent_RemoteEvent`, 16 `SequenceFrame`, 15 `SeqAct_ShowWaypoint`, 10 `SeqAct_SpawnAlien` and 10 `SeqAct_ActivateNarrative`. Also 20 `TriggerVolume`, 11 `XComRebuildWorldDataVolume`, 10 `XComSpawnPoint_Alien` and 11 `XComInteractiveLevelActor`. |

- **Mission streams available:** the converted maps include 8 `*_Terror` streams, 1 `*_Rescue` and 1 `*_Bomb`. `URB_Bar` has `URB_Bar_Terror` (37 MB).
- **Firewall prompt.** The first editor launch raised a Windows Firewall prompt for `udk.exe`. The editor needs no network access; the user was asked to choose Cancel.

## Next (plan steps 3–5)

- **Step 3: record a map in the GUI.** In the reference editor, record `URB_Bar`'s actor transforms, volumes, spawn groups and Kismet links. Kismet node positions may be at (0, 0).
- **Step 4: check against the property dump.** Compare several transforms and world bounds (cover object, ladder, landing zone, objective volume) with `tools\upk` property dumps of the cooked map.
- **Step 5: transfer.** Try moving a small arrangement into the authoring UDK with its coordinates preserved.
- **Asset database.** Find the package that crashes it.

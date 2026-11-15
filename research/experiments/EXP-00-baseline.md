# EXP-00: baseline and isolation (record)

This file is the record and resume ledger for EXP-00 in the investigation plan.

**Status (3 November 2026, 18:10): done.**

- **The lab copy reaches the main menu through Steam.** It runs with `-nohomedir`, so its settings, saves and logs stay inside the copy. The shared profile is untouched.
- **Layout.** The lab copy and the live LWR install sit side by side in `steamapps\common`. `tools\lab\switch_install.ps1` renames whichever is wanted to `XCom-Enemy-Unknown`; see [Side-by-side layout](#side-by-side-layout-1740).
- **Why every earlier copy launch quit.** A `steam_appid*` file stood next to `XComEW.exe`: first the `steam_appid.txt` we added as a redirect guard, later the same file renamed to `.off`. See [Cause found](#cause-found-steam_appid-files-make-xcomew-quit-1755-1805). The CEG hypothesis further down is wrong.
- **Current state.** LWR is active and verified against the baseline. The lab copy is parked as `XCom-Enemy-Unknown.Lab`.

The sections below keep the history in order.

## Done

### 1. The live game was left untouched

Nothing was changed in `<Steam common>\XCom-Enemy-Unknown`.

Key hashes, taken from the full manifest:

| File | SHA-256 (prefix) | Bytes |
|---|---|---|
| `XEW/Binaries/Win32/XComEW.exe` | `51d4cdbc1e3ba998…` (matches `evidence/executable-pattern-audit.json`) | 27,793,464 |
| `XEW/Binaries/Win32/XCOMLauncher.exe` | `e18f28a37408fab6…` | 1,189,888 |
| `Binaries/Win32/XComGame.exe` (EU) | `aa8e82a9d0c2aab3…` | 28,430,904 |
| `XEW/XComGame/CookedPCConsole/XComGame.upk` | `27b98aa43d5482df…` | 13,296,301 |
| `XEW/XComGame/CookedPCConsole/Engine.upk` | `1acf57b4d2df2aef…` | 4,730,157 |
| `…/Engine.upk.renamethistoenableconsole` | `236dcde3edc0b3ba…` | 4,731,025 |
| `…/LWRebalance.u` (dated 31 October 2026) | `cfc9644e32d6d0ed…` | 9,013,564 |
| `XEW/XComGame/Config/DefaultMaps.ini` | `9a6629bcbff839a4…` | 163,644 |
| `XEW/XComGame/Config/DefaultMutatorLoader.ini` | `fe6f006e90db8299…` | 1,106 |
| `XEW/XComGame/Config/DefaultLZMutator.ini` | `7f7fb51a8022dfea…` | 58,796 |

### 2. The game was copied

- `<lab>\runtime\XCom-Enemy-Unknown`: an ordinary robocopy, made with `/COPY:DAT /DCOPY:DAT`. It has 10,013 files and 21,007,290,005 bytes.
- Every file's SHA-256 matches the original, with **0 differences**.
- The manifest is `<lab>\snapshots\runtime-baseline-2026-11-03.sha256` (format: hash, bytes, path). Compare against it to see exactly what an experiment changed in the copy.
- The copy keeps the original timestamps. The INI version stamps are therefore identical, and launching the copy unmodified should not make the game rebuild the shared `My Games` settings.

### 3. The user profile was backed up

The backups are of `Documents\My Games\XCOM - Enemy Within`:

- `<lab>\snapshots\my-games-2026-11-03-1650`: taken before the resolution fix (1920×1200).
- `<lab>\snapshots\my-games-2026-11-03-working-2560x1440`: the known-good state after the fix. Restore from this one.

The resolution fix itself: `XComEngine.ini [SystemSettings]` `ResX`/`ResY` were changed from 1920/1200 to 2560/1440. The 1920×1200 values were left over and put the main menu off-screen. The game now works.

### 4. Tools were downloaded and verified

Archives are in `<lab>\downloads`, with hashes in `SHA256SUMS.txt`. Each one was unpacked into its own new folder under `<lab>\tools`.

| Download | Check | Unpacked to |
|---|---|---|
| `UDKInstall-2011-09-BETA.exe` (1,663,581,640 bytes) | Authenticode **valid**, signed by "Epic Games Inc." (VeriSign, timestamped) | Not run. The user must run it, because it shows Epic's licence. |
| `xcom-uncooker-v1.1.0.zip` | Size matches; no publisher digest | `tools\xcom-uncooker-v1.1.0`. Contains `xcom-uncooker-udk-setup.exe` (unsigned), `xcom-uncooker\` and `replacement-packages\`. |
| `ue-explorer-1.6.2-net48-portable.7z` | SHA-256 **matches the publisher digest** | `tools\ue-explorer-1.6.2`. .NET Framework 4.8.1 is present (release 533509). |
| `UPKUtils73.7z` | Size matches; no publisher digest | `tools\UPKUtils-7.3` |

### 5. Pinned sources were checked out

`<lab>\upstream\iiiLiQuiDiii-UDK` is a git clone checked out (detached) at `80be6f4c21b665e0c261bee224429cb36c3fc217` ("patch pack 3", 6 July 2015). It has 1,653 tracked files, 91 MB, and no LFS.

### 6. The copy's launch was prepared

- **DPI flag.** The copy's `XComEW.exe` was given the same per-user `HIGHDPIAWARE` compatibility flag as the Steam exe (HKCU `AppCompatFlags\Layers`). Without it, the 125% Windows scaling would push the window past the screen.
- **Launch script.** `tools\lab\launch_copy.ps1` launches only the copy and refuses a Steam-library path. It needs Steam to be running and the game closed, and it waits for the game to exit. It then reports:
  - which `Launch.log` was written, with its `Base directory` and `Command line` lines;
  - every file added or changed in the shared `My Games` profile.
- **Not yet added:** `steam_appid.txt`. It goes into the copy only if the first launch shows Steam redirecting to its own install.

## Launch runs (3 November 2026)

Every run used `tools\lab\launch_copy.ps1`, with Steam running and Cloud off.

### Run 1, 17:03: no `steam_appid.txt`, `-nohomedir`

**What happened**
- **The copy quit straight away.** Its `XComEW.exe` exited within 5 s and wrote a 0-byte log.
- **Steam relaunched the game itself.** Steamworks' restart check had Steam start **the Steam install's `Binaries\Win32\XComGame.exe` (Enemy Unknown)** with our arguments. Steam's `gameprocess_log.txt` shows this at 17:03:25.
- **Enemy Unknown wrote into the Steam folder.** Because it received `-nohomedir`, it created 14 generated INIs, `Launch.log` and `profile.bin` under the Steam root `XComGame\`, plus two `Engine\Localization\INT` files. It also rewrote 3 EU localization files: `XComGame.int`, `XComStrategyGame.int` and `XComUIShell.int`.
- **The LWR side (`XEW`) was untouched.**

**How it was repaired**
- **Closed the game.** The stray Enemy Unknown window got a normal close.
- **Moved the strays out.** The 18 new files went to `<lab>\snapshots\steam-install-strays-2026-11-03-1703`, and the two empty folders they had created were removed.
- **Restored the originals.** The 3 changed files were copied back from the lab copy.
- **Verified the result.** `tools\lab\verify_tree.py` reports 0 new, 0 missing and 0 changed files across all 10,013.
- **Added a guard.** The launch script now refuses to start without `steam_appid.txt`. It also closes any process that starts from the Steam install, and re-verifies the Steam tree after every run.

### Runs 2–5, 17:06–17:12: with `steam_appid.txt` (200510)

**What worked**
- **No more redirects.** Steam never restarted the game again.
- **The copy runs from its own folder.** `Base directory` is `<lab>\runtime\…`.
- **`-nohomedir` works.** Settings (`XEW\XComGame\Config`, 8 generated INIs) and `XEW\XComGame\Logs\Launch.log` stay inside the copy. The shared profile was untouched apart from `steam_autocloud.vdf`, which Steam rewrites with the same content on every launch.

**What failed:** every run exits after about 1.1–1.4 s with exit code 1. The exit always comes right after `WinSock: I am …`, where a working launch would initialize XAudio2. It happened in every variant:
- direct launch with `-nohomedir`;
- direct launch without it, using the shared profile, which only wrote `Launch.log` and its backup;
- direct launch with `SteamAppId`/`SteamGameId` set;
- through the copy's `XCOMLauncher.exe`. The script clicked "Enemy Within" with a real mouse click, because the image buttons ignore posted window messages. The launcher started `XComEW.exe -FROMLAUNCHER -nostartupmovies -nohomedir -LANGUAGE=INT`.

**Likely cause (not yet verified):**
- **A Steam DRM check fails.** The exe contains `STEAM_DRM_IPC` and `SteamAPI_RestartAppIfNecessary`. Steam's own launch provides the DRM environment, and our launches do not.
- **Steamworks itself is fine.** Steam tracked the copy's process as AppID 200510.

**Steam Cloud:** `cloud_log.txt` shows `Starting sync (AC Exit,Sync Disabled,)` on each exit, so nothing is uploaded.

### Options for a working launch (user decision)

- **A. Steam launch-option wrapper.**
  - **Setting:** XCOM: Enemy Unknown's launch options become `"<wrapper>" %command%`.
  - **Behaviour:** if `<lab>\LAB_MODE` exists, the wrapper starts the copy under Steam's environment; otherwise it runs Steam's original command unchanged.
  - **Cost:** one Steam setting the user makes, and no file changes in the Steam folder.
  - **Untested:** whether a copy started under Steam's environment passes the check.
- **B. Folder swap around test sessions.**
  - **Mechanism:** a script renames the Steam install aside and links the copy into its path. The user starts XCOM from Steam, then the script swaps back.
  - **Certainty:** certain to pass Steam's checks.
  - **Cost:** the Steam folder is renamed during sessions. Restoring after a crash must be scripted, and Steam must not update the game during a swap.

### Option A chosen: the Steam launch-option wrapper (17:20)

**The wrapper**
- **Files:** `<lab>\bin\XComLabWrapper.exe` (7,680 bytes), built from `tools\lab\XComLabWrapper.cs` with the .NET Framework 4 `csc` (`/target:winexe /platform:x86`).
- **Normal mode:** it passes Steam's command through unchanged and waits for it.
- **Lab mode** (when `<lab>\LAB_MODE` exists): it starts the copy's `ew`, `launcher` or `eu` target with `-nohomedir`. It never falls back to the Steam install.
- **Log:** every run goes to `<lab>\logs\wrapper.log`, including whether `STEAM_DRM_IPC` is present.
- **Dry runs** (`XCOMLAB_WRAPPER_DRYRUN=1`) checked both modes:
  - command and exit-code pass-through (exit 7 came back as 7);
  - quoted paths with spaces;
  - all three lab targets.

**Supporting changes**
- **`tools\lab\lab_mode.ps1 on|off|status`** toggles the flag. `off` re-verifies the Steam install against the baseline.
- **Second `steam_appid.txt`:** added to the copy's root `Binaries\Win32` as well, for the `eu` target.

**The Steam setting**
- **Current value:** the user's XCOM launch options are `-nostartupmovies` (`localconfig.vdf`).
- **New value:** `"<lab>\bin\XComLabWrapper.exe" %command% -nostartupmovies`
- **Precedent:** another game on this machine already uses `cmd /c start "" %command%`, so `%command%` works with this Steam client.
- **Undo:** put the launch options back to `-nostartupmovies`.

**Still to test (after the user sets the option):**
1. Lab mode off: start XCOM from Steam. LWR must start as before, and `wrapper.log` should show `mode: normal`.
2. `lab_mode.ps1 on`: start XCOM from Steam. Check that the copy reaches the main menu.
3. Check `wrapper.log` (is `STEAM_DRM_IPC` present?), the copy's `XEW\XComGame\Logs\Launch.log`, the shared profile, and finally `lab_mode.ps1 off`.

### Wrapper tests through Steam (17:26–17:31)

The user set the launch options to `"<lab>\bin\XComLabWrapper.exe" %command% -nostartupmovies`.

**What Steam does**
- **The command it passes:** `<Steam library>\…\Binaries\Win32\XComGame.exe -nostartupmovies`.
- **The environment:** `SteamAppId=200510` is set and `STEAM_DRM_IPC` is absent, even for Steam's own launches.

**Lab mode off: works.** The chain is wrapper → EU `XComGame.exe` (which exits 0) → Steam `XCOMLauncher.exe`, which waits for the "Enemy Within" click. That click starts `XComEW.exe -FROMLAUNCHER -nostartupmovies -LANGUAGE=INT` from the Steam install, which reached the shell (`Initial startup: 3.30s`). The wrapper doesn't change normal play.

**Lab mode on, target `ew`: still quits.** Steam tracked the copy's `XComEW.exe`, but it exits after 1.1 s with code 1. Variants tried, all with the same exit:
- `steam_appid.txt` removed from the copy (renamed to `.off`). There was no restart redirect, because Steam's launch satisfies the restart check.
- The copy run through a junction at `<Steam common>\XCom-Lab`, launched directly. Its `Base directory` showed the junction path. The junction was removed afterwards.

**Ruled out as the missing piece:**
- the launcher (a .NET program that simply runs `Binaries\Win32\XComEW.exe -FROMLAUNCHER … -LANGUAGE=…`);
- Steam's environment;
- `steam_appid.txt`;
- `-nohomedir`;
- the folder being inside `steamapps\common`.

**Remaining hypothesis:** both game exes link Valve's CEG library (`ceglib`), and CEG validates the game only when it runs from the app's registered install folder, `…\steamapps\common\XCom-Enemy-Unknown`.

> **Correction (18:05).** This hypothesis is wrong, and so is "`steam_appid.txt` ruled out" above. Every one of these runs had a `steam_appid.txt` or `steam_appid.txt.off` next to the copy's `XComEW.exe`, and that file alone makes the game quit at this point. See [Cause found](#cause-found-steam_appid-files-make-xcomew-quit-1755-1805). These runs therefore never tested whether a copy outside `steamapps\common` works. Run 1 (no `steam_appid` file) was redirected by Steam's restart check instead.

**Next test:** the folder swap (option B). It renames the live install, so it needs the user's approval.

**Safety:**
- **Steam install:** verified identical to the baseline after every run.
- **Shared profile:** only `steam_autocloud.vdf` was rewritten, by Steam.
- **Loop guard:** the wrapper now refuses a second lab launch within 20 s (`<lab>\logs\last-lab-launch.txt`), so a Steam restart can't loop. (Removed in the 17:40 rewrite: the wrapper no longer starts anything except Steam's own command.)
- **Lab mode is off.**

### Side-by-side layout (17:40)

The user asked to keep both installs in `steamapps\common` and switch them by renaming. This replaced option B's linking and the `LAB_MODE` flag.

**Folders.** All are in `<Steam common>`:
- `XCom-Enemy-Unknown`: the active install, the one Steam runs.
- `XCom-Enemy-Unknown.LWR`: the live install while it is parked.
- `XCom-Enemy-Unknown.Lab`: the lab copy while it is parked. It was moved here from `<lab>\runtime`, which no longer exists.

**The marker.** `XComLab-copy.txt` in the lab copy's root identifies it. A line `nohomedir=false` in it turns off the wrapper's `-nohomedir`.

**`tools\lab\switch_install.ps1 status|lab|lwr`:**
- **Renames.** Does two renames, undoing the first if the second fails, and finishes a half-done switch.
- **Refusals.** Refuses to run while XCOM or the wrapper is running, or when the folders are mislabelled.
- **Logging and checks.** Logs to `<lab>\logs\switch.log`. After `lwr` it verifies the active folder against the baseline manifest.

**The wrapper (rewritten).**
- **Lab copy active** (marker found by walking up from the launched exe): it runs Steam's command with `-nohomedir` added.
- **Otherwise:** it runs the command unchanged.
- **Warning:** it logs a warning when a `steam_appid*` file is next to `XComEW.exe`.
- **Steam setting:** unchanged, `"<lab>\bin\XComLabWrapper.exe" %command% -nostartupmovies`. It stays set permanently; for LWR it is a pass-through.

**Helpers.**
- **`tools\lab\steam_launch_test.ps1`** starts XCOM through `steam://rungameid/200510`, clicks Enemy Within and lets the shell load. It closes the game normally, then reports:
  - the wrapper and Steam process logs;
  - the game log lines;
  - changes in the shared profile;
  - LWR against the baseline.
- **`tools\lab\click_launcher.ps1`** does the launcher click.
- **Removed:** `launch_copy.ps1` and `lab_mode.ps1`. They belonged to the old layout, and `launch_copy.ps1` insisted on `steam_appid.txt`.

### Runs at the Steam path (17:43–18:08)

| Time | Lab copy state | `-nohomedir` | Result |
|---|---|---|---|
| 17:43 | marker, both `steam_appid.txt.off`, INIs/logs from earlier runs | yes | exit 1 at 1.31 s |
| 17:52 | same | no (marker `nohomedir=false`) | exit 1 at 1.16 s |
| 17:55 | generated INIs and logs moved to `<lab>\snapshots\lab-copy-generated-2026-11-03` | no | exit 1 at 1.12 s |
| 17:57 | as 17:55, plus `XComEW.exe` hard-linked to the live install's exe | no | exit 1 at 1.13 s |
| 18:00 | as 17:57, plus marker, both `.off` files and the empty `Logs` folder moved aside: names identical to LWR | no | **main menu** (`Initial startup: 3.35s`) |
| 18:01 | as 18:00 but with the copy's own `XComEW.exe` again (hard link removed) | no | **main menu** |
| 18:02 | as 18:01 plus the marker | no | **main menu** |
| 18:02 | as 18:02 plus `XEW\Binaries\Win32\steam_appid.txt.off` | no | **exit 1 at 1.16 s** |
| 18:05 | `.off` removed; marker without `nohomedir=false` | **yes** | **main menu** (`Initial startup: 4.18s`), log in the copy |
| 18:08 | switched back to LWR | no | LWR main menu, LWR verified |

What the table shows:
- **Same files, different result.** Contents, timestamps, attributes, ACLs and alternate streams of the copy matched the live install all along (checked on the main exes and DLLs; contents for all 10,013 files).
- **Exe identity doesn't matter.** The copy runs with its own `XComEW.exe`, so a distinct file ID is fine.
- **The hard-link test.** The live exe had a second name only from 17:57 to 18:01. Its content never changed, and `fsutil hardlink list` shows one name again.

### Cause found: `steam_appid` files make `XComEW` quit (17:55–18:05)

- **The trigger.** `XComEW.exe` quits about 1.1 s after start, with exit code 1, right after `WinSock: I am …`. Nothing explains it in the log. This happens whenever a file whose name begins with `steam_appid` is in `XEW\Binaries\Win32`. `steam_appid.txt.off` is enough.
- **Probable mechanism.** An anti-piracy check, since cracked copies use `steam_appid.txt`. It evidently matches more than the exact file name.
- **Rule.** Never put a `steam_appid*` file next to `XComEW.exe`. The wrapper logs a warning if one appears.
- **Run 1's redirect.** That (no file, launched directly) is Steamworks' normal restart check for a game not started by Steam. Launching through Steam avoids it.

### Isolation result (18:05)

- **What `-nohomedir` keeps inside the lab copy.** These folders under `XEW\XComGame` are created on first use:
  - `Config` (8 generated `XCom*.ini`);
  - `Logs`;
  - `SaveData\profile.bin` (79 bytes on first start).
- **The shared profile.** Compared with `my-games-2026-11-03-before-shared-lab-run`, settings and saves are byte-identical (39 non-log files). Only logs from the non-`-nohomedir` test runs were added under `My Games\…\Logs`.
- **Lab display settings.** The copy's generated `XComEngine.ini` started at 1440×900, fullscreen, vsync on. It was set to the known-good values: `ResX=2560`, `ResY=1440`, `Fullscreen=False`, `BorderlessWindow=True`, `UseVsync=False`.
- **Compatibility flags.** `HIGHDPIAWARE` already applies at the Steam path, so it covers whichever folder is active. The stale entry for `<lab>\runtime\…\XComEW.exe` was removed.
- **Launcher drawn as a grid (found 3 November 2026, 20:00).**
  - **The flag.** HKCU `Layers` also holds `<Steam common>\XCom-Enemy-Unknown\Binaries\Win32\XComGame.exe = HIGHDPIAWARE`, on the EU stub. It wasn't there at 16:45. It was there at 18:07, and no command in this session wrote it, so its origin is unknown.
  - **How it spreads.** Windows passes the layer down to child processes: the running `XComEW.exe` had `__COMPAT_LAYER=HighDpiAware ElevateCreateProcess`.
  - **What it does to the launcher.** `XCOMLauncher.exe` (WinForms) becomes DPI-aware. At 125% scaling WinForms enlarges the form but not its background image, which then repeats as a grid of orange-framed hangar panels.
  - **Fix.** Remove that one value; `XComEW.exe` keeps its own flag.

### Launcher click fix (17:52)

- **What went wrong.** Two automated clicks landed on Discord, which was on top at that spot. `SetForegroundWindow` is refused from a background script. Both clicks hit plain message text, with no effect.
- **The fix.** `click_launcher.ps1` now:
  - makes the launcher topmost for the click;
  - checks with `WindowFromPoint` that the launcher is the window under the cursor;
  - refuses to click otherwise.
- **Result.** Every click since then has worked.

### UDK installed by the user (17:23)

- **The install:** `<lab>\author\UDK-2011-09`, with no version subfolder; 4,817 files, 3.13 GiB.
- **Copies:** robocopied to `<lab>\snapshots\UDK-2011-09-pristine` (untouched snapshot) and `<lab>\reference\UDK-2011-09` (for the Uncooker). Both are 4,817 files.
- **Ready:** EXP-01 and EXP-02 can start; they don't need the game to launch.

### UDK silent install: blocked (superseded)

Running `UDKInstall-2011-09-BETA.exe -progressonly`, which installs silently and so accepts Epic's licence without showing it, was refused by Claude Code's auto-mode safety check: accepting a licence must be done by the user.

**Installer facts** (from its strings, not from running it):
- **Native wrapper switches:** `-progressonly`, `-skipdependencies`, `-runonce`, `-forcenetinstall`, `-skipnetcheck`.
- **Managed `UnSetup.exe` switches:** `/ProgressOnly`, `/SkipDependencies` and `/language=`.
- **No install-folder switch was found.** The GUI's default is under `C:\UDK\`.
- **Prerequisites:** it installs a "UE3Redist" of prerequisites, which may need elevation.

## Next steps

Steps 1, 2 and 4 of the earlier list are done: Cloud off, isolation, and UDK installed.

1. **Gameplay check (plan steps 6–7).** Run `switch_install.ps1 lab` and start a non-Ironman test campaign in the copy. Play one mission, save and reload, and keep checkpoints. Then prove rollback: change one harmless config, restore it, and compare its hash with the manifest. Finish with `switch_install.ps1 lwr`.
2. **EXP-01 and EXP-02.** These are the authoring UDK with LiQuiD911's stubs, and the Uncooker in the reference UDK. They don't need the game.
3. **Open question.** Does a copy outside `steamapps\common` run when launched through the wrapper without any `steam_appid` file? The earlier runs never tested it. It no longer matters for the chosen layout.

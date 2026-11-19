# Hidden game runs: everything needed to set them up and use them

This file is for a Claude agent (or any coding agent) that has to make the `game-test` skill work: run XCOM by
itself, off screen, with nobody at the keyboard, play a battle by commands, and come back with pictures and log lines
that answer a question. It covers what the pieces are, how they work, the one-time setup of a new computer, a first
run that proves the setup, the way a test is run and reported, and what to do when something goes wrong.

[SKILL.md](SKILL.md), beside this file, is the day-to-day how-to for playing a test (every command and trick). This
file is what has to be true before SKILL.md works, and why it works. Read this one first on a computer where hidden
runs have never been made; after that, SKILL.md is enough.

Paths in this file are relative to the root of this repository unless they start with a placeholder (section 1).
No folder of any one computer appears here: where a folder differs between computers, a placeholder stands for it.

## 1. Words and placeholders used here

### Placeholders

Every `<...>` in a path or a command stands for something you fill in. Never type the angle brackets.

| Placeholder | What it stands for | How to find it on a computer |
| --- | --- | --- |
| `<repo>` | The root folder of this repository's checkout (where `AGENTS.md` is). Run every command from there. | Your working directory. |
| `<Documents>` | The user's Documents folder, as Windows reports it (it can be moved off the C: drive). | `[Environment]::GetFolderPath('MyDocuments')` in PowerShell. |
| `<lab>` | The **lab folder**: our own working folder for experiments, outside the repository (it holds big and private things). Hidden runs keep their compiled helpers, DXVK, the stand-in DLL and their out folders there. | The `lab` setting (section 4.1). On a new computer the user picks it: any folder on a drive with a few GB free. |
| `<Steam common>` | The `steamapps\common` folder of the Steam library that holds XCOM. All copies of the game sit in it side by side. | Steam: Library, right-click XCOM: Enemy Unknown, Manage, Browse local files; that opens `<Steam common>\XCom-Enemy-Unknown`. |
| `<game>` | The **active game folder**: always `<Steam common>\XCom-Enemy-Unknown`, the one folder Steam runs. Which copy it holds depends on the last switch (section 4.4). | `pwsh -File tools\lab\switch_install.ps1 status` says which copy is active. |
| `<out>` | The **out folder** of one hidden run: its pictures, logs, steps and (for a session) its inbox. | You choose it with `--out`; the default is `<lab>\hidden-runs\<date-time>`. Use `<lab>\hidden-runs\<name>`. |
| `<name>` | A short name you make up (a run's folder, a picture's file name). | Yours. Letters, digits, `-` and `_`. |
| `<Map>` | A map's package name, without `.upk`: the file name of the map in `<game>\XEW\XComGame\CookedPCConsole`. Example: `URB_Bar` (a small bar, the map most checks so far used). | The editor's map list, or the `.upk` names in that folder. |
| `<x> <y> <z>` | A place in the map in **world units** (below). | `getall` readbacks in the game (section 7), or the editor's view. |
| `<LLVM bin>` | The `bin` folder of an LLVM install (the folder holding `clang-cl.exe`, `lld-link.exe` and `llvm-dlltool.exe`). | Where LLVM was installed, e.g. by the official LLVM Windows installer. Only needed for section 4.6. |
| `<version>` | The version folder of an unpacked DXVK release, such as `dxvk-3.1.1`. | The name of the folder the release unpacks to. |

### Words

- **XCOM, EW.** XCOM: Enemy Within, the 2013 expansion of XCOM: Enemy Unknown (Firaxis, Unreal Engine 3). On Steam it
  is started through Enemy Unknown, whose **Steam app id is 200510**. Its program is
  `<game>\XEW\Binaries\Win32\XComEW.exe` (32-bit). "Plain EW" means the game without mods.
- **LWR.** Long War Rebalance, the mod the user plays. It is installed over the game's own files, so an install
  either has it or not. Its squad items and rules differ from plain EW's, which matters for the squad file (below).
- **The live install.** The copy of the game the user plays. Hidden runs never touch it.
- **The lab copy.** A full copy of the game folder (with LWR in it) kept for experiments. It is recognised by a
  **marker file**, `XComLab-copy.txt`, in its root folder. `hidden_game.py` refuses to run any folder without the
  marker. A third copy (LWR v3 beta, marker line `copy=lwr3`) may exist; it is used only when the user asks.
- **Active, parked, switching.** Steam always runs the folder named `XCom-Enemy-Unknown`. The other copies wait beside
  it under other names (`XCom-Enemy-Unknown.LWR`, `.Lab`, `.LWR3`): they are **parked**. Switching renames the
  folders so that another copy becomes the active one (section 4.4).
- **Unreal console.** The game's one-line command prompt, opened with the backslash key `\` in this game. It takes
  Unreal Engine 3 commands: `getall <Class> <Property>` prints a property of every object of a class to the log,
  `set` changes one, `exec <file>` runs a file of commands, `open <Map>` loads a map, and the cheat commands
  (`DropSectoid`, `ToggleFOW`, `EndTurn`, ...).
- **Commands file, `-EXEC`.** A text file of console commands, one a line, in `<game>\XEW\Binaries`. Started with
  `-EXEC=<file>`, the game runs it as soon as it is up. `open <Map>` in it starts a battle on that map straight away,
  with no campaign behind it.
- **`Launch.log`.** The game's log, `<game>\XEW\XComGame\Logs\Launch.log`. Console answers, the combat log and errors
  all land there. `-forcelogflush` makes the game write it line by line, so it can be read while the game runs.
- **`-nohomedir`.** A game argument that keeps its settings (`Config`), logs and saves inside the game folder instead
  of `<Documents>\My Games\XCOM - Enemy Within`, so the user's own profile is never touched.
- **Hidden desktop (private desktop).** Windows can hold several desktops in one session; only one is ever shown on
  the monitors. A program started on another desktop draws its windows there: nothing appears on the user's screen,
  it never takes the keyboard focus, and the user's mouse and keyboard never reach it. The hidden runs use one named
  `XComLab-Game`.
- **Direct3D 9, DXVK.** XCOM draws with Direct3D 9. On a hidden desktop Direct3D 9 finds no graphics hardware and the
  game hangs at start. **DXVK** (github.com/doitsujin/dxvk) is an open-source `d3d9.dll` that does Direct3D 9 over
  Vulkan, and Vulkan works there. Put beside `XComEW.exe`, it is loaded instead of Windows' own.
- **Stand-in input DLL.** Our own `dinput8.dll` (DirectInput), built from `tools/lab/StandInInput.c`. The game asks
  DirectInput for the system mouse as it starts and crashes if Windows has none (a mouse switched to another
  computer, asleep or unplugged). The stand-in gives it a still mouse and keyboard in that case.
- **Steps.** The little command language `GameRemote.exe` understands: `wait`, `waitlog`, `console`, `key`, `shot`,
  `type`, `serve`, `quit` (section 7).
- **Session.** A hidden run kept open (`--serve`) that takes further steps while the game stays up, so a test can go
  back and forth: ask, read the answer, decide the next step.
- **Inbox.** `<out>\inbox`, the folder a session watches for step files. It appears when the session is ready.
- **World units, tiles, storeys.** Places in a map are in Unreal units. A tile is 96 units wide; tile centres are 96
  apart. Heights are `z`. A **storey** (floor) is a level a unit can stand on: 0 is the ground and the ground floor
  inside buildings, higher numbers the upper floors and roofs.
- **Active soldier.** The soldier the game has selected; moves and shots are his. `key TAB` selects the next one.
- **Squad file.** A text file holding the squad to land, in the form the console's `set XComOnlineProfileSettings
  m_aSoldiers` takes. `tools/viewer/tests/squad_default_lwr.txt` is the test squad for LWR.
- **The editor, the main server, test servers.** This repository's map editor runs as a local web server
  (`python tools/viewer/viewer.py serve`). The user's own one is on port 8768: never start a second one there.
  Checks use **test servers** on ports 8790 to 8799, started for the check and stopped after it.
- **Play in game.** The editor's command (Project menu) that copies a project's built map into a game folder, writes
  its records and a commands file, and starts a battle on it. A test server started with `--dry-play` does all of that
  but starts no game, which is how a hidden run gets a project's map (section 6).
- **Requester, test agent.** The requester is the agent (or person) who wants something checked in the game. The test
  agent is the subagent that runs the game and reports (section 8).
- **Findings register, IDs.** `research/findings-register.md` records what was found out, each finding under an ID:
  `T-nn` for findings about our tools and test rigs, `F-nn` for findings about the game and the objects we put in it.
  `EXP-nn` are experiments, written up in `research/experiments/`. The entries this file leans on are **T-43** (the
  game on a hidden desktop), **T-44**, **T-45** (no mouse), **T-46** (DXVK's texture budget), **F-73**, **F-84** and
  **F-89** (saving).
- **Change ledger.** `CHANGELOG.md`: every change to the tools and documents gets an entry, in the same commit.

## 2. What a hidden run can and cannot do

It can:

- start the lab copy's game on a hidden desktop, silent, with no window, sound or focus taken from the user;
- open a battle on any map in the lab copy (a game map, or a project's map staged there), with a chosen squad and
  with or without aliens, or a mission of a particular kind staged by the editor;
- type console commands and read their answers from `Launch.log`;
- press keys (menus, abilities, Tab, Escape, Enter, quicksave);
- take the game's own screenshots and save them as PNG files;
- walk the active soldier to any reachable tile, up ladders and onto roofs; teleport soldiers; drop aliens; shoot;
  throw grenades; end turns; save and load (with `--saving`);
- list the sounds the game is playing at a place;
- stay open as a session for a long series of checks.

It cannot:

- use a mouse: no clicking on the interface, no dragging, no hovering (Windows refuses cursor calls on a hidden
  desktop). Everything goes by keys, console commands and the camera trick of section 3.4;
- record sound: it lists what plays and how loud, not how it sounds;
- run the live install, or two games at once;
- save or load without `--saving`.

Not tried yet: stairs inside a building, climbing down, plain EW, the LWR v3 copy.

## 3. How it works

### 3.1 The pieces

| File | Role |
| --- | --- |
| [tools/lab/hidden_game.py](../../../tools/lab/hidden_game.py) | The one command you run. Checks, prepares the lab copy, runs the two helpers, puts everything back. Also the `send`, `goto`, `aim` and `listen` commands for a session. |
| [tools/lab/HiddenRun.cs](../../../tools/lab/HiddenRun.cs) | `HiddenRun.exe`: creates the hidden desktop and starts a program on it, inside a Windows job that kills everything when it ends or times out. |
| [tools/lab/GameRemote.cs](../../../tools/lab/GameRemote.cs) | `GameRemote.exe`: runs on the hidden desktop, starts the game there, finds its window, mutes it, and works through the steps (keys as window messages, console commands, shots, log waits, the session inbox). |
| [tools/lab/StandInInput.c](../../../tools/lab/StandInInput.c) | The stand-in `dinput8.dll` (mouse and keyboard where Windows has none; crash log). |
| [tools/lab/build_stand_in_input.py](../../../tools/lab/build_stand_in_input.py) | Builds that DLL with LLVM into `<lab>\bin`. |
| [tools/lab/switch_install.ps1](../../../tools/lab/switch_install.ps1) | Switches which copy is active (renames folders). |
| [tools/lab/labpaths.py](../../../tools/lab/labpaths.py), [tools/viewer/settings.py](../../../tools/viewer/settings.py) | Read the folders from the settings file (section 4.1). |
| [tools/viewer/gamelaunch.py](../../../tools/viewer/gamelaunch.py) | Writes the commands file that opens a battle (`play_text`) and the start file for saving (`start_text`). |
| [tools/lab/tests/test_hidden_game.py](../../../tools/lab/tests/test_hidden_game.py) | The offline tests (the `lab` suite). |

`HiddenRun.exe` and `GameRemote.exe` are compiled by `hidden_game.py` itself, into `<lab>\bin`, with the C# compiler
that comes with Windows (.NET Framework 4: `%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe`), whenever they
are missing or older than their source. You never build them by hand.

### 3.2 One run, start to end

1. `hidden_game.py` checks the steps, that Steam is running (the game quits at once without it), and that the game is
   not already running. It counts the mice and keyboards Windows sees.
2. It checks `<game>` holds the lab marker and `XComEW.exe`, then **prepares the copy**:
   - copies DXVK's `d3d9.dll` beside `XComEW.exe` (in `<game>\XEW\Binaries\Win32`), and the stand-in `dinput8.dll`
     too when a device is missing or when `--stand-in-input` or `--crash-log` asks for it;
   - remembers every `.ini` in `<game>\XEW\XComGame\Config` byte for byte (the console's `set` makes the game rewrite
     its config, F-73), and with `--saving` every file in `<game>\XEW\XComGame\SaveData` too;
   - writes the battle's commands file, `<game>\XEW\Binaries\XComMapWorkshop-hidden.txt` (with `--saving`, also
     `XComMapWorkshop-hidden-start.txt`, section 3.6).
3. It writes `<out>\steps.txt` and `<out>\dxvk.conf` (DXVK's settings: `d3d9.textureMemory = 0`, T-46) and starts:

   ```
   <lab>\bin\HiddenRun.exe --desktop XComLab-Game --timeout <s> -- <lab>\bin\GameRemote.exe
       <game>\XEW\Binaries\Win32\XComEW.exe <out>\steps.txt <out> <game>\XEW\XComGame\Logs\Launch.log
       -FROMLAUNCHER -EXEC=XComMapWorkshop-hidden.txt -nostartupmovies -nohomedir -forcelogflush -windowed
       -ResX=1280 -ResY=720
   ```

   with these in the environment: `SteamAppId=200510` and `SteamGameId=200510` (without them a game started by hand,
   not by Steam, quits, F-84), `DXVK_LOG_PATH=<out>`, `DXVK_CONFIG_FILE=<out>\dxvk.conf`, and for the stand-in
   `XCOM_STAND_IN_INPUT_LOG=<out>\input.log`. `-FROMLAUNCHER` is what the game's own launcher passes after its
   click; starting `XComEW.exe` directly with it skips the launcher window.
4. `HiddenRun.exe` creates the desktop and starts `GameRemote.exe` on it. `GameRemote.exe` starts the game (which
   inherits the desktop), waits for its window (window class `LaunchUnrealUWindowsClient`), mutes the game's audio
   session in Windows, and runs the steps.
5. At the end (the last step, a `quit`, a failed step or the idle limit of a session) `GameRemote.exe` unmutes the
   game, kills it and deletes its own command files. `hidden_game.py` then puts back every config file (and save) the
   run changed, deletes the commands files, takes the DLLs away (retrying for 20 seconds, since a game that has just
   ended may still hold them), copies `Launch.log` into `<out>` and writes `<out>\run.log`.

A battle reaches turn 1 about 75 seconds after the start.

### 3.3 Keys, console commands, pictures and answers

- **Keys.** Window messages reach only windows on the sender's own desktop, so the driver must run on the hidden
  desktop beside the game; that is why `GameRemote.exe` starts the game itself. It posts `WM_KEYDOWN` and `WM_KEYUP`
  to the game's window. `SendInput` (simulated hardware input) reaches nothing there. The game does not need to be
  the window in front.
- **Console commands.** Only keys without Shift can be posted reliably, and many commands need `_` or `(`. So a
  `console <command>` step writes the command to a small file (`xmwh<n>.txt` in `<game>\XEW\Binaries`) and types
  `\`, `exec xmwh<n>.txt`, Enter. Several commands joined by ` | ` go into one file and run in one frame.
- **Pictures.** A capture of the window from outside is black on a hidden desktop. The `shot <name>` step types the
  game's own `shot` command; the game writes `ScreenShotNNNNN.bmp` to `<game>\XEW\XComGame\Screenshots\PCConsole` at
  the render size, and `GameRemote.exe` converts it to `<out>\<name>.png` and deletes the `.bmp`.
- **Answers.** Console answers go to `Launch.log`. `waitlog <s> <text>` waits until the log holds a text. In a
  session, `hidden_game.py send` prints the log lines that appeared while its steps ran, so a `getall` answer comes
  back to you as text.

### 3.4 Pointing without a mouse

On a hidden desktop the game's mouse never moves: it stays at the top left corner of the picture, and every frame the
game puts its 3D cursor (the tile marker that orders go to) on the tile under that corner. So the tools move the
camera instead of the mouse:

- The camera looks straight down at the active soldier (`SetOverheadCameraParameters <fov> 1256 -89`: field of view,
  distance, pitch). The tile under the corner then lies `1440 × tan(fov / 2)` world units from the soldier, in the
  direction of the camera's yaw plus 72 degrees (`SetCameraYaw <yaw>`). Both numbers were measured (T-43).
- `hidden_game.aim_camera(soldier, target)` gives the field of view and yaw for a target tile. `aim` sets them, reads
  the cursor back (`getall XCom3DCursor Location`) and corrects up to six times, since a roof or a prop under the
  corner can move the pick.
- `goto` then runs the console functions `Right_Mouse_Button_Press` and `Right_Mouse_Button_Release` (the game's
  own right-click handlers, which order the move), polls the soldier's place until he stops, and puts the camera back
  (`SetOverheadCameraParameters 70 1256 -45`, the normal play camera).
- The storey the cursor picks on is the mouse wheel's count (`XCom3DCursor.m_iRequestedFloor`), changed one step at a
  time by `Mouse_Scroll_Up` and `Mouse_Scroll_Down`; `--floor <n>` does that first.
- A look-at (`ViewLocation`) hides the cursor and stops paths being built: use it only to photograph a place, and
  always `RemoveLookAt` after.

### 3.5 Sessions

`--serve <idle s>` as the last step keeps the game running. `GameRemote.exe` creates `<out>\inbox` and watches it:

- `hidden_game.py send <out> "<step>" ...` writes the steps to `<out>\inbox\<time>.part`, renames it to `.txt` (so it
  is never read half written), and waits for `<time>.done`, which holds `ok` or `FAIL: <why>`. A failed step does
  not end the session; the game goes on.
- `goto`, `aim` and `listen` are built on `send`.
- The session ends at `send <out> quit`, or after `<idle s>` without a step file, or at `--timeout`.

### 3.6 Saving

A battle opened by `-EXEC` cannot be saved: the game has not logged in to its online profile yet, so a save never
finishes and a load hangs (F-89). With `--saving` the game is started with a file that only binds F5 to the battle's
commands (`setbind F5 exec XComMapWorkshop-hidden.txt`); the game stays at its main menu and logs in, and the run's
first steps wait for the log's `Obtained steam user stats` and press F5. Saves made in the run, and the profile, are
put back when it ends, so no save outlives it.

## 4. One-time setup of a computer

Do these in order. Each says how to check it. Several need the user: copying the game (21 GB), downloading DXVK and
switching which copy is active are theirs to approve, so ask first and say what you will do.

### 4.1 What the computer needs

| Need | Why | Check |
| --- | --- | --- |
| Windows 10 or 11 | Hidden desktops, window messages, Core Audio. | `winver`. |
| A graphics card and driver with Vulkan | DXVK draws over Vulkan. | DXVK's log in a run's `<out>` says `Creating device` with the card's name. |
| Steam, logged in, with XCOM: Enemy Unknown and Enemy Within | The game needs Steam running even when started by hand. | `tasklist /FI "IMAGENAME eq steam.exe"`. |
| LWR installed in the game (for the default squad file) | The test squad's items are LWR's. Plain EW is untried (section 9). | `<game>\XEW\XComGame\CookedPCConsole` holds LWR's packages. |
| Python 3.12 | `hidden_game.py` uses only the standard library; staging a project's map needs the editor's packages too (`pip install -r tools/viewer/requirements.txt`). | `python --version`. |
| .NET Framework 4 C# compiler | Builds `HiddenRun.exe` and `GameRemote.exe` on first use. Part of Windows. | `%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe` exists. |
| PowerShell 7 (`pwsh`) | `switch_install.ps1`. | `pwsh --version`. |
| LLVM 15 or later (optional) | Only to build the stand-in input DLL (section 4.6). | `<LLVM bin>\clang-cl.exe --version`. |
| About 25 GB free on the Steam library's drive | The lab copy is a full copy of the game folder (about 21 GB). | Explorer. |

### 4.2 The settings

The tools take every folder from the settings file, `<Documents>\XCOM Map Workshop\settings.json` (the environment
variable `XCOM_MAP_WORKSHOP_SETTINGS` can name another file). Nothing checked in names a folder. Show them:

```
python tools/viewer/viewer.py settings
```

Hidden runs need two:

- `lab`: the lab folder, `<lab>`. Set it with `python tools/viewer/viewer.py settings --lab <lab>`.
- `game`: where the game is. Set it to `<Steam common>` (the folder holding the game folders, not one game folder):
  `python tools/viewer/viewer.py settings --game "<Steam common>"`. The editor then finds the live install among
  them whichever copy is active (it never takes a folder with the lab marker for it), and the lab tools find
  `<game>` as `<Steam common>\XCom-Enemy-Unknown`. (The setting was once called `lwr`; old files with that name still
  work.)

For staging a project's map into the lab copy (section 6) the `install` setting, the folder Play in game installs
into, should be the active folder: `python tools/viewer/viewer.py settings --install "<Steam common>\XCom-Enemy-Unknown"`.
A test server can also be given `--install` for one check instead.

If the user already has settings, read them and change nothing that is already set; ask before changing `game` or
`install`, since the editor they use reads them too.

### 4.3 The lab folder

Create `<lab>` if it does not exist. The tools fill it:

```
<lab>\bin\              HiddenRun.exe, GameRemote.exe (compiled on first run), dinput8.dll (section 4.6)
<lab>\dxvk\<version>\   an unpacked DXVK release (section 4.5)
<lab>\hidden-runs\      the out folders of the runs
<lab>\logs\switch.log   what switch_install.ps1 did
<lab>\snapshots\        the live install's checksum list (section 4.4)
```

Nothing in `<lab>` is ever committed: it is outside the repository.

### 4.4 The lab copy

Skip this when `pwsh -File tools\lab\switch_install.ps1 status` already shows a lab copy (`active=lab` or
`parked.Lab=lab`).

1. **Ask the user**: the copy takes about 21 GB and a while to make; the game and Steam's own updates must not run
   meanwhile. The game must be closed.
2. **Write a checksum list of the live install** first, while it is untouched. `switch_install.ps1 lwr` checks the
   live install against it after every switch back. The script looks for exactly
   `<lab>\snapshots\runtime-baseline-2026-11-03.sha256`; lines are `<sha256>  <bytes>  <path relative to the game
   folder, with forward slashes>`, two spaces between. A short Python snippet writes it (run it with the live install
   active):

   ```python
   import hashlib, os, pathlib, sys
   root, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])     # <game>, <lab>\snapshots\runtime-baseline-2026-11-03.sha256
   out.parent.mkdir(parents=True, exist_ok=True)
   with open(out, 'w', encoding='utf-8', newline='\n') as f:
       for p in sorted(q for q in root.rglob('*') if q.is_file()):
           h = hashlib.sha256()
           with open(p, 'rb') as s:
               for block in iter(lambda: s.read(1 << 22), b''): h.update(block)
           f.write(f'{h.hexdigest()}  {p.stat().st_size}  {p.relative_to(root).as_posix()}\n')
   ```

   Without the file the switch itself works, but its check fails and warns that the live install differs.
3. **Copy the game folder** to its parked lab name, keeping timestamps:

   ```
   robocopy "<Steam common>\XCom-Enemy-Unknown" "<Steam common>\XCom-Enemy-Unknown.Lab" /E /COPY:DAT /DCOPY:DAT
   ```

   (robocopy's exit codes 0 to 7 mean success.)
4. **Put the marker in its root**: a file `<Steam common>\XCom-Enemy-Unknown.Lab\XComLab-copy.txt`. Its presence is
   what matters; a line of text saying what it is will do. Do **not** put a `copy=` line in it (that marks the other
   copies). Optional lines are read only by the Steam wrapper of earlier experiments, not by hidden runs.
5. **Never put any file whose name starts with `steam_appid` next to `XComEW.exe`**, not even `steam_appid.txt.off`:
   the game then quits about 1.1 seconds after start with exit code 1 and nothing useful in its log (an
   anti-piracy check matches the name).
6. **Never let Steam "verify integrity of game files"**: it rewrites whatever folder is active, wiping LWR or the lab
   copy's changes.

**Switching.** With the game closed:

```
pwsh -File tools\lab\switch_install.ps1 status    # which copy is active, which are parked
pwsh -File tools\lab\switch_install.ps1 lab       # the lab copy becomes <game>
pwsh -File tools\lab\switch_install.ps1 lwr       # the live install becomes <game> again (and is checked)
```

It refuses while XCOM runs or when the folders are mislabelled, and finishes a half-done switch. Hidden runs need the
lab copy active. Switching is the user's decision: ask before you switch, and ask which copy they want active when
you are done (they may want to play).

### 4.5 DXVK

1. **Ask the user** before downloading. Then get a release archive from github.com/doitsujin/dxvk (Releases,
   `dxvk-<version>.tar.gz`). The version verified here is 3.1.1; a newer one is likely fine, but a run with it is the
   check.
2. Unpack it so that `<lab>\dxvk\<version>\x32\d3d9.dll` exists (`tar -xzf dxvk-<version>.tar.gz -C <lab>\dxvk`).
   Only the 32-bit `x32\d3d9.dll` is used. With several versions there, the highest version number is used.
3. Do not copy it into the game yourself: each run puts it beside `XComEW.exe` and takes it away after. A
   `d3d9.dll` that is already there and is the same file is left alone; a different one stops the run until it is
   removed.

### 4.6 The stand-in input DLL (needed when the computer may have no mouse)

If the user's mouse and keyboard can be switched to another computer, sleep, or be unplugged while tests run, build
it; without it a run refuses to start when Windows sees no mouse. It also gives the crash log of `--crash-log`. It
needs LLVM (no Visual Studio, no Windows SDK):

```
python tools/lab/build_stand_in_input.py --llvm "<LLVM bin>"
```

It writes `<lab>\bin\dinput8.dll` (32-bit) and checks its exports. Check it outside the game with the `lab` suite
(section 4.7): its `StandInDll` test loads it in a 32-bit process and skips when it is not built.

Each run decides by itself: with a mouse and keyboard in Windows the DLL stays out (unless `--stand-in-input` or
`--crash-log`); with one missing it goes beside the game for the run and `<out>\input.log` says what the game got.

### 4.7 The offline tests

```
python -B tools/run_tests.py lab
```

`run_tests.py` prints each failure with its traceback and keeps full logs. The `lab` suite includes
`test_hidden_game.py` (preparing and restoring a copy, the pointing maths, reading answers, the input plan, the
DXVK settings). `-k <part of a test name>` runs some of them.

## 5. The first run: proving the setup

With the lab copy active, Steam running and the game closed:

```
python tools/lab/hidden_game.py --map URB_Bar --squad tools/viewer/tests/squad_default_lwr.txt \
    --out <lab>\hidden-runs\first --timeout 600 \
    --step "waitlog 240 m_bTacticalIntroDone" --step "wait 50" --step "shot start"
```

`m_bTacticalIntroDone` is a line the game logs when the landing's intro is over. What a working setup prints (times
vary):

```
[   0.0] started XComEW.exe -FROMLAUNCHER -EXEC=XComMapWorkshop-hidden.txt ...
[   ...] window 0x..., client ...x...
[   1.5] sound muted
[  ~21 ] log has "m_bTacticalIntroDone"
[  ~73 ] shot start: 1280x720 <out>\start.png
[  ~73 ] steps done
[  ~73 ] sound unmuted (1 session)
put back: XComContent.ini, ...
done: <out>
```

Then:

1. Look at `<out>\start.png` (Read it: agents can see PNG files). It should show URB_Bar at turn 1 with the squad and
   the interface drawn.
2. Check nothing is left behind: `tasklist /FI "IMAGENAME eq XComEW.exe"` finds nothing, and no `d3d9.dll` (or
   `dinput8.dll`) is in `<game>\XEW\Binaries\Win32`.
3. Prove a session: start one in the background (section 7.1), wait for `<out>\inbox`, then
   `python tools/lab/hidden_game.py send <out> "console getall XGUnit Location"` (every unit's place should print),
   a `goto` two tiles from a soldier (it should answer "stands on"), and `send <out> quit`.

If any of this fails, section 10 lists what each failure has meant so far.

## 6. Getting the map to test into the lab copy

- **A game map as it is**: nothing to do. `--map <Map>` writes the commands to open it (`set XComContentManager
  bAllowJITLoad True`, the aliens, the squad, `open <Map>`).
- **A project's map, or a mission of a particular kind** (an EXALT mission, a UFO, terror, a Council mission, a
  project's variant): let the editor stage it, then play its commands file.
  1. Build the project in the editor (its Build panel), so it has a package.
  2. Start a test server on a free port from 8790 to 8799, with `--dry-play` (and `--install "<game>"` if the
     `install` setting does not already name the active folder):
     `python -B tools/viewer/viewer.py serve --port 8791 --no-open --dry-play`
  3. Run Play in game there: in the browser pane, or by its HTTP call,
     `POST http://127.0.0.1:8791/play/start` with `{"project": "<project id>"}` (add `"mission": <index or kind>`
     and `"saving": true` as needed; `{"map": "<map id>"}` plays a game map's own record). It copies the map's
     packages and records into the lab copy and writes `<game>\XEW\Binaries\XComMapWorkshop-play.txt` (and
     `XComMapWorkshop-start.txt` when saving is on) without starting the game.
  4. Stop the test server (by its port; a Python server started from Bash can outlive its shell).
  5. Start the run with `--play-file "<game>\XEW\Binaries\XComMapWorkshop-play.txt"` instead of `--map` (plus
     `--saving` when the start file was staged).
- `tools/lab/lab_install.py` is an older way, through the game's intro-mission slot; prefer Play in game.

## 7. Using it

SKILL.md has the full playing guide. The essentials:

### 7.1 Starting

A session for a test (start it in the background; it is ready when `<out>\inbox` exists, about two minutes in):

```
python tools/lab/hidden_game.py --map <Map> --squad tools/viewer/tests/squad_default_lwr.txt \
    --out <lab>\hidden-runs\<name> --timeout 3400 \
    --step "waitlog 240 m_bTacticalIntroDone" --step "wait 50" --serve 1800
```

- **Always give `--squad`.** The game's own squad on this path cannot walk (their animation trees lack the movement
  node), and the first move order then hangs the game and its console.
- `--no-aliens` for an empty map; `--saving` for a test that saves or loads; `--play-file <file>` instead of
  `--map`; `--res <w>x<h>` for another render size (default 1280x720).
- `--timeout` is the whole run's limit in seconds, `--serve` the session's idle limit.
- A battle that never logs `m_bTacticalIntroDone` (some mission kinds) starts fine with
  `--step "waitlog 240 Mission Started" --step "wait 60"`.
- In the Bash tool, run it with `run_in_background`; wait for the inbox with a polling loop rather than a long sleep.
  Use forward slashes in paths in Bash (Python takes them), or quote backslash paths.
- One game at a time.

Exit codes: 0 done; 1 the game ended by itself (a crash) or opened no window; 2 the run could not start (the message
says why); 3 a `waitlog` or `shot` ran out of time; 124 the `--timeout` ended it.

### 7.2 Steps

| Step | Does |
| --- | --- |
| `wait <s>` | Waits. |
| `waitlog <s> <text>` | Waits until `Launch.log` holds the text (any case); fails after `<s>`. |
| `console <command>` | Runs console commands, several joined by ` \| `. Any character is allowed. |
| `key <name> [count]` | A key: `A`-`Z`, `0`-`9`, `F1`-`F12`, `RETURN`, `ESCAPE`, `SPACE`, `TAB`, `BACK`, `LEFT`/`UP`/`RIGHT`/`DOWN`, `HOME`, `END`, `PAGEUP`, `PAGEDOWN`, `BACKSLASH`, `TILDE`, or `0x<hex>`. |
| `shot <name>` | The game's own screenshot, saved as `<out>\<name>.png`. |
| `type <text>` | Types into the console directly (letters, digits, space, `-`, `.` only); `console` is usually better. |
| `serve <s>` | Becomes a session (`--serve` adds it). |
| `quit` | Ends the run. |

### 7.3 Talking to a session

| Want | Command |
| --- | --- |
| Run steps, see the log's answer | `python tools/lab/hidden_game.py send <out> "<step>" "<step>" ...` |
| Walk the active soldier to a tile | `python tools/lab/hidden_game.py goto <out> <x> <y> [--floor <n>]` |
| Put the cursor on a tile and do steps there | `python tools/lab/hidden_game.py aim <out> <x> <y> [--floor <n>] "<step>" ...` |
| List the sounds playing at a place | `python tools/lab/hidden_game.py listen <out> <x> <y> <z> [--distance <d>]` |
| End the session | `python tools/lab/hidden_game.py send <out> quit` |

`send` waits up to 300 seconds for its steps; give the Bash tool a timeout longer than that (the tool's default is
two minutes). Readbacks that answer most questions: `console getall XGUnit Location`, `getall
XComTacticalController m_kActiveUnit`, `getall XGUnit m_bInCover`, `getall XGUnit m_iCurrentCoverValue`, `getall
XCom3DCursor Location`; an array property prints nothing. Read every picture you take.

## 8. How a test is run and reported (the skill's protocol)

The skill splits the work between two agents, so that the one who asked can go on with its own work:

- **The requester** writes a brief and starts the **test agent** as a background subagent: the Agent tool with
  `model: "opus"` and `effort: "high"`.
- **The brief** names: the map and how it gets into the lab copy (section 6); each check, with what counts as passed
  and what as failed; the tiles or objects involved, in world units; the out folder; the skill's name (`game-test`);
  that each check gets one pass and at most one second take; and the pause protocol (below).
- **The test agent** starts one session and keeps it open, does every asked check once (the plainest way: what the
  log and one or two pictures show), then gives a second take only to checks that came out unclear, changing one
  thing that could settle it. Each check ends **passed**, **failed** or **unclear**, with its evidence in a line or
  two. No retakes for a better-framed picture, no confirming by a second method what the first showed, no chasing
  side observations (a line in the report instead).
- **Reporting while it runs.** After every check the test agent appends to `<out>\report.md`: the commands, the log
  lines that answer, each picture's file and what it shows in words. It ends its turn with a report, **leaving the
  game running**, and names the out folder.
- **More tests** go to the same test agent with the SendMessage tool (load it with ToolSearch first if it is listed
  as deferred), addressed to the agent's id from the Agent call's result; it continues in the same game. A new Agent
  call would start from nothing.
- **Ending.** The test agent sends `quit` only when the requester says the tests are over (or before the session
  would idle out), and says in its last report that the game is closed. Then it checks that no `XComEW.exe` runs and
  no `d3d9.dll` is left beside the game.
- **Checking the report.** The requester reads the pictures and log lines in `<out>` before telling the user that
  something is verified: the test agent's words are a report, not proof.
- **The pause protocol** (for usage limits): on a pause instruction or a usage-limit error, the test agent finishes
  the step in hand, sends `quit`, and writes in `report.md` where it stood and what is left.

A brief, in outline:

```
Use the game-test skill (.claude/skills/game-test/SKILL.md). Map: <how it gets into the lab copy>.
Out folder: <lab>\hidden-runs\<name>. Start one session with --squad and --serve 1800 and keep it open.
Checks:
1. <what to do> at <x>,<y> (storey <n>). Passed if <...>; failed if <...>.
2. ...
One pass for every check, then at most one second take for the unclear ones. One picture per item.
After each check append to <out>\report.md. End your turn with a report, leaving the game running.
On a usage limit or a pause instruction: finish the step in hand, send quit, write where you stood in report.md.
```

## 9. Rules

- **Only the lab copy.** The tool refuses a folder without the marker; never work around that.
- **Ask first** before closing a game the user has open, switching which copy is active, copying the game,
  or downloading anything.
- **One game at a time**, and end every session with `send <out> quit`, not by killing it: `quit` unmutes the
  game's sound. A run killed from outside (or ended by `--timeout`) leaves the game muted in Windows for the user's
  next play until a run ends by itself or the volume mixer is used; say so in the report if it happens.
- **After a run**, check no `XComEW.exe` is running and no `d3d9.dll` or `dinput8.dll` is left in
  `<game>\XEW\Binaries\Win32`.
- **Pictures and run files stay in `<lab>`.** This repository is public: nothing from a run is committed. A note or a
  finding says in words what a picture showed; a picture a check's record needs goes into `private/shots/` (ignored
  by Git).
- **Findings** go into the findings register (a new ID, what, cause, fix, how verified); a change to the tools goes
  into the change ledger in the same commit.
- **Plain EW**: the test squad file has LWR's item numbers. On plain EW a squad file made for that install would be
  needed (the editor's squad records, `tools/viewer/squadrecords.py`, make them per install); not tried yet.

## 10. When something goes wrong

| What you see | What it has meant | What to do |
| --- | --- | --- |
| The game ends about 1.1 s in, exit code 1, nothing useful in `Launch.log`. | A file named `steam_appid*` is beside `XComEW.exe`; or Steam is not running. | Remove the file (any name starting `steam_appid`); start Steam. |
| The game stands for minutes; the log says `Failed to get Caps bits info from the D3D Object` and compatibility level 0. | Direct3D 9 found no hardware: DXVK's `d3d9.dll` was not beside the game. | Check `<lab>\dxvk\<version>\x32\d3d9.dll` exists. (`-dx11` is no way out: the game has no DirectX 11 shaders.) |
| The game crashes about 3 s in; the log ends `XAudio2Device initialized` then `Critical error ... Address = 0x11fb6b8`. | Windows had no mouse (T-45). | Build the stand-in (section 4.6), or wake or connect the mouse. |
| "Windows sees no mouse ... build the stand-in" and the run does not start. | The same, caught before the start. | As above. |
| A load of a save with aliens crashes about 1.4 s after `LoadingFromShell=1`. | DXVK's texture budget (T-46). Fixed by `<out>\dxvk.conf`. | Check DXVK's log in `<out>` says `Found config file`. |
| The run ends by itself with exit code -1073741819 and nothing in `Launch.log`. | A crash on one of the game's own threads. | Run again with `--crash-log`; the module, offset, registers and stack are in `<out>\input.log` and printed at the end. |
| After a move order the console stops answering. | No `--squad`: the game's own squad cannot walk. | Quit, start again with `--squad`. |
| `goto` says "did not move". | No path: the tile holds a prop, is out of reach, is on another storey, or a look-at is up. | Another tile, `--floor`, or `console RemoveLookAt`. |
| `aim` fails: "too far to point at" or the correction runs off. | The target is too far from the active soldier (roofs need about 10 tiles or fewer). | Teleport a soldier nearer (`aim ... "console TeleportToCursor"`, then `key TAB` round to him), or pick a nearer one. |
| `send` says "No run is serving". | The session is not ready yet (no inbox) or has ended (idle limit, quit, crash). | Wait for the inbox; read `<out>\run.log` for how it ended. |
| A save never finishes, a load hangs. | No `--saving` (F-89). | Start the run with `--saving`. |
| A save crashes with `Address = 0x0`. | Seen once on this project when a Windows hypervisor (WSL2, virtualisation-based security) was on: the exe's copy-protection CPU check fails under it. | Tell the user; it is their system setting. Never patch the exe. |
| An EXALT Data recovery battle stays on its loading screen. | A SHIV first in the squad (T-44); the editor now puts a soldier first. | Put a soldier first in the squad. |
| "the game still holds d3d9.dll" at the end. | The game had not let go of the DLL in 20 s. | Once no `XComEW.exe` runs, delete the DLL from `<game>\XEW\Binaries\Win32`. |
| "is another d3d9.dll than ..." and the run does not start. | A different `d3d9.dll` is beside the game (from something else). | Ask the user before removing it. |
| A picture is black. | A capture from outside the game; only the game's own `shot` works there. | Use the `shot` step. |
| The game stops at "Please Reconnect Controller". | The console command `UseController` was used. | Never use it; quit and start again. |

When a run behaves in a way none of this explains, read the T-43 entry of the findings register in full: it holds
every observation the hidden runs were built on.

## 11. Doing the same for another game

The techniques carry over to other Windows games:

- **A hidden desktop** (`CreateDesktop`, then `CreateProcess` with `STARTUPINFO.lpDesktop` set to it) keeps a game
  off the user's screen and out of their input. Put the program and its driver in a job object with
  kill-on-job-close so nothing outlives a timeout.
- **Direct3D 9 finds no hardware there**; DXVK's `d3d9.dll` beside the exe makes it draw. (Direct3D 10/11 games
  would need DXVK's `d3d11.dll`/`dxgi.dll` likewise; not tried here.)
- **Input**: window messages (`PostMessage` with `WM_KEYDOWN`/`WM_KEYUP`) work only from the same desktop, so the
  driver must start the game itself there. `SendInput`, `SetCursorPos` and `GetCursorPos` do not work there, and
  mouse messages were ignored by this game. A game's own console, fed through files it can `exec`, avoids typing
  characters that need Shift.
- **Pictures** come from the game's own screenshot command; `PrintWindow` and screen captures are black.
- **Answers** come from the game's log, written line by line (`-forcelogflush` here) and read while it runs.
- **Sessions** need only a folder protocol: step files written as `.part` and renamed, a `.done` file for each.
- **Sound** is muted per process through Core Audio (`IAudioSessionManager2`, the session of the game's process,
  `ISimpleAudioVolume.SetMute`); unmute before ending the game, since Windows remembers an application's mute.
- **A game that insists on a mouse** at start can be given a stand-in DirectInput DLL beside it.
- **Put back everything** a run changes in the game folder (config, saves, DLLs), so runs leave no trace.

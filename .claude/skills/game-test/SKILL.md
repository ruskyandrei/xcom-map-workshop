---
name: game-test
description: Run an unattended game test - start the lab copy's XCOM on a hidden desktop with tools/lab/hidden_game.py, play it by console, keys and tile moves (walk soldiers to tiles, climb, go indoors, drop aliens, shoot, throw grenades, end turns), read answers from the game's log and its own screenshots, and report. The test is run by an Opus 5.5 agent at high effort that keeps the game open, reports while it runs and takes further tests from whoever asked. Use when a change needs a look or a check in the real game and nobody has to play it by hand - a map loads, a piece gives cover, a tile can be walked, a ladder climbs, an effect shows - or when the user asks for an unattended, hidden, off-screen or automatic game test.
---

# Unattended game tests

[hidden_game.py](../../../tools/lab/hidden_game.py) runs the lab copy's game on a private Windows desktop: nothing
shows on the user's screen and no keyboard or mouse is taken. [GameRemote.cs](../../../tools/lab/GameRemote.cs) drives
it there. What was found out about it is in the findings register, T-43; read that entry when something here does not
behave as written.

## Who runs it

- **The test is run by a subagent on Opus 5.5 at high effort**: the Agent tool with `model: "opus"` and
  `effort: "high"`, started in the background. The session that wants the test (the requester) writes the brief and
  goes on with its own work.
- **The requester gets feedback while the game runs, and can ask for more.** The agent:
  - starts one session and keeps it open (`--serve 1800`) until the requester says the tests are over;
  - after every test, appends what it did and saw to `<out>\report.md` (commands, the log lines that answer, the shot
    files and what each shows in words), so the requester can read progress at any time;
  - ends its turn with a report when the asked tests are done or when it needs a decision, **leaving the game
    running**, and names the out folder;
  - takes further tests by `SendMessage` to the same agent, which continues in the same game; a new Agent call would
    start from nothing;
  - sends `quit` only when the requester says so, or when the session would otherwise idle out, and says in its last
    report that the game is closed.
- The requester checks the report against the shots and log in the out folder before telling the user a thing is
  verified: the agent's words are a report, not proof.
- The brief says: the map and how it gets into the lab copy, each thing to check and what would count as passed or
  failed, the tiles or objects involved (world units, from the project or the viewer), the out folder, this skill's
  name, that each check gets one pass and at most one second take (below), and the pause protocol (on a usage limit: finish the step in hand, `send <out> quit`, write where it stood in
  `report.md`).

## How far to take each check

The agent's job is an honest first reading of everything it was asked, not a perfect one of each thing.

- **First pass: every asked check once.** Do each in the plainest way, note what the log and one or two shots show,
  and move on to the next, whatever the outcome. Nothing gets a second try until every check has had its first.
- **Second take: only for what was unclear, and only once.** A check is unclear when its first pass could not tell
  pass from fail (the shot does not show the thing, the readback was empty, the soldier ended on another tile).
  Change one thing that could settle it (another camera, another tile, another readback) and try again.
- **Still unclear after that: report it as unclear and go on.** Say what was tried both times, what was seen, and
  what would settle it. That is a complete answer; the requester decides whether to ask for more.
- **Then end the run's turn**: write the report and hand back. Do not keep the game busy polishing.

What this rules out:

- retaking a shot because it could be better framed, lit or zoomed, when it already shows what was asked;
- confirming by a second method something the first already showed;
- chasing a side observation nobody asked about (note it in a line instead);
- calling a check passed that was not seen: "unclear" and "not seen" are results, and better than a pass that
  took ten tries to produce.

Each check ends as **passed**, **failed** or **unclear**, with the evidence in a line or two.

## Before a run

- Only the lab copy: the folder Steam runs must hold `XComLab-copy.txt` (`tools/lab/switch_install.ps1 lab`). The tool
  refuses anything else. Steam must be running; the lab copy's game must not be.
- The user may be playing another copy meanwhile (their game is started with `<lab>\bin\XComSideBySide.exe`, which
  lets it run beside a hidden run: T-52, SETUP.md section 9). Never close or touch that game or its copy; tell it
  from the run's by the exe's folder. While their copy is the one Steam runs, name the lab copy with `--game`, on
  the start command and on every `send`, `aim`, `goto` and `listen` too: without it they read the log of the folder
  Steam runs, the user's game's (EXP-91). If the tool says another copy's game holds the one-instance mutex, ask the
  user to start it with `XComSideBySide.exe`.
  Staging a map refuses only while the lab copy's own game is open: it tells games apart by the exe's folder too.
  But `lab_install.py` and `deploy_fixture.py` stage into the folder Steam runs, and take any copy with an
  `XComLab-copy.txt` for the lab copy, the user's LWR3 copy too: while another copy is the one Steam runs, stage with
  `lab_install.install(<package folder>, game=<the lab copy's folder>)` from Python, never the command line.
- Which copy: the lab copy (`XCom-Enemy-Unknown.Lab`, LWR 2.x, a marker without a `copy=` line) unless the check is
  of LWR v3; then the LWR v3 lab copy, `XCom-Enemy-Unknown.Lab3` (LWR v3.00.00 beta 17; its marker has
  `copy=lab3`), named with `--game` on every command. Both are lab copies: stage, deploy and play there freely.
- `XCom-Enemy-Unknown.LWR3` (its marker has `copy=lwr3`) is the user's own LWR v3 copy, with their campaign: never
  run, stage into or change it unless the user asks. It is often the folder Steam runs.
- DXVK unpacked at `<lab>\dxvk\<version>\x32\d3d9.dll`. The tool puts the DLL beside the game for the run and takes
  it out after, and puts back every config file the run changed.
- The map must be in the lab copy: a game map as it is, or the project's map staged there the way its experiment
  does (the editor's Build and Play in game, or `tools/lab/lab_install.py`).
- No mouse or keyboard in Windows is fine once the stand-in is built. The game asks DirectInput for the system mouse
  as it starts, and with none (the mouse and keyboard switched to another computer, asleep or unplugged) it crashed
  about 3 seconds in (T-45). The tool then puts the stand-in `dinput8.dll` beside the game for the run (a still mouse
  and keyboard where Windows has none; what the game got is in `<out>\input.log`). Build it once with
  `python tools/lab/build_stand_in_input.py --llvm <LLVM bin folder>` (clang-cl, lld-link, llvm-dlltool) into
  `<lab>\bin`. Without it the tool refuses to start with no mouse; then ask the user to connect or wake the mouse.
- A mission of a kind (EXALT's, a UFO, terror, a Council mission, a project's variant) is played from the editor's
  own commands: stage it with Play in game on a test server started with `--dry-play` (it writes everything and
  starts no game), then start with `--play-file <game>\XEW\Binaries\XComMapWorkshop-play.txt` (with `--saving` when
  the play staged `XComMapWorkshop-start.txt` too). `--map` opens the map bare: the squad and Sectoid pods, none of
  the mission's commands.
- One hidden game at a time. A run takes about 75 seconds to reach turn 1.

## Starting

```
python tools/lab/hidden_game.py --map <Map> --squad tools/viewer/tests/squad_default_lwr.txt \
    --out <lab>\hidden-runs\<name> --timeout 3400 \
    --step "waitlog 240 m_bTacticalIntroDone" --step "wait 50" --serve 1800
```

Run it in the background; it is ready when `<out>\inbox` exists. Always give `--squad`: the game's own squad for this
start cannot walk, and a move order then hangs the game. `--no-aliens` gives an empty map; `--play-file` takes a
commands file of your own instead of `--map`.

A check that needs no back and forth can be one call without `--serve`: the steps, then the game closes.

**A test that saves or loads needs `--saving`** on that command. The game then starts at its main menu, logs in, and
the tool presses the key that opens the battle (the editor's Enable saving, done for you); everything else is the
same. Without it a save never finishes and a load hangs the game.

## Talking to the session

| Want | Command |
| --- | --- |
| Steps, with the log's answer printed | `hidden_game.py send <out> "<step>" "<step>" ...` |
| The active soldier walks to a tile | `hidden_game.py goto <out> <x> <y> [--floor <n>]` |
| The cursor on a tile, steps done there | `hidden_game.py aim <out> <x> <y> [--floor <n>] "<step>" ...` |
| End the game | `hidden_game.py send <out> quit` |

Steps: `wait <s>`, `waitlog <s> <text>`, `console <command>` (several with ` | ` between), `key <name> [count]`,
`shot <name>` (the game's own picture, saved as `<out>\<name>.png`), `type <text>`.

Places are world units; a tile is 96 wide and tile centres sit 96 apart (read real ones first, below).

### Reading the game

- `console getall <Class> <Property>` prints to the log and `send` shows it: `XGUnit Location`,
  `XComTacticalController m_kActiveUnit`, `XGUnit m_bInCover`, `XGUnit m_iCurrentCoverValue`,
  `XGUnit CurrentCoverPointFlags`, `XComLadder Location`, `XComFloorVolume Location`, `XCom3DCursor Location`.
  An array (`m_arrVisibleEnemies`) prints nothing: for line of sight open the shot view (key 1) and read the picture.
- `console ShowCursorLoc` puts the cursor's place, its tile and `PathActionEmpty` at the bottom of every shot.
- The combat log is in the game log (`Combat Log Message`): moves, shots, damage, turns.
- Look at every shot you take (Read the PNG). To photograph a place: `console ViewLocation <x> <y> <z>`, wait 4, shot,
  `console RemoveLookAt`. Never leave a look-at up: it hides the cursor and no path is built.
- `console ToggleFOW` lifts the fog; `key E` / `key Q` turn the camera, `key G` / `key T` pull it back and in.

### Playing

- **Move**: `goto`. It answers "stands on" or "did not move". No move means no path: the tile holds a prop, is out of
  reach, or is on another storey than the one picked. After a move the game goes on to the next soldier; one without
  moves left is no longer in Tab's round.
- **Storeys**: `--floor 0` is the ground and the inside of a building (its roof is cut away for the pick); roofs and
  upper storeys need a higher one, and the game takes the ladder or stairs by itself. Read the height `aim` reports
  to see which storey a number is on that map. Aim at an upper storey from within about ten tiles.
- **Put a soldier somewhere at once**: `aim <out> <x> <y> "console TeleportToCursor"`, then `key TAB` round to him
  again (his paths are stale until he is reselected).
- **Aliens**: `aim <out> <x> <y> "console DropSectoid"` (also DropMuton, DropThinMan, DropFloater and the rest of
  the cheat manager's Drop list). `console ToggleInvincibility` and `console killaliens 1` exist too.
- **Shoot**: `key 1` (the shot view), `shot`, `key RETURN`.
- **Grenade**: its ability key (see the bar in a shot), then, while the view is open, set the camera by hand so the
  aim falls on the target: `console SetOverheadCameraParameters <fov> 1256 -89 | SetCameraYaw <yaw>` with the values
  of `hidden_game.aim_camera(thrower, target)`; shot to see "Targets"; `key RETURN`, and once more if a box asks
  about a friendly unit. Put the camera back: `console SetOverheadCameraParameters 70 1256 -45`.
- **Next soldier**: `key TAB`. **End the turn**: `console EndTurn`, then wait about 25 seconds.
- Menus go by the arrow keys and Enter, `key ESCAPE` backs out.
- **Save** (a `--saving` session): `key F10` is the quicksave; wait 8. **Load**: `key ESCAPE` (the pause menu),
  `key DOWN 2`, `key RETURN` (Load Game: the newest save is first and selected; take a shot to be sure),
  `key RETURN`, `key RETURN` again for the box that asks, then wait 60 for the map. Read the units again after a
  load. The run's saves and the profile are put back when the session ends, so no save outlives it.
- A move ordered onto a tile with a prop ends on a tile beside it: `goto` then says where he is.

### Sounds

- `hidden_game.py listen <out> <x> <y> <z> [--distance <d>]` puts the camera `<d>` world units from that place and
  prints what the game is playing there: volume, wave, the actor it belongs to (the console's `ListWaves`).
- **The game hears from the camera, not from the place it looks at.** The play camera stands 1256 from its target,
  farther than most ambient sounds reach, so "is it heard here" is asked with a `--distance` a player's zoom would
  give, or one inside the sound's reach to prove it plays at all.
- A sound's reach and wave: `console getall SoundNodeAmbient RadiusMin | getall SoundNodeAmbient RadiusMax | getall
  SoundNodeAmbient SoundSlots`; its place: `getall AmbientSoundSimple Location`. Full volume inside RadiusMin, none
  beyond RadiusMax; a full ambient sound lists at 0.60.
- A sound that plays once (a shot, a voice) is in the list only while it sounds: ask right after what causes it.
- The run is silent: the tool mutes the game in Windows' mixer while it runs and unmutes it at the end, and the
  list is not touched by that. If a run was ended from outside (a timeout, a killed process) the game may stay muted
  for the user's own next play: say so in the report; the next run that ends by itself takes the mute off.
- This is the engine's own list, not a recording: it says a sound plays and how loud, not how it sounds.

## When the game crashes

A run that ends by itself (exit code -1073741819, an access violation) with nothing in `Launch.log` crashed on a
thread of the game's own. Run it again with `--crash-log`: the stand-in DLL then logs the fault to `<out>\input.log`
(module and offset, what it touched, registers, the module addresses on that thread's stack) and the run prints it.
DXVK's settings for every run are in `<out>\dxvk.conf`; its texture budget is off because loads of battles with
aliens crashed with it (T-46).

## What it cannot do

- No real mouse: no clicking on the interface, no dragging. Controller mode stops the game at a reconnect box.
- Without `--saving` the battle cannot be saved or loaded.
- Not tried: stairs inside a building, a climb down, plain Enemy Within, the LWR install.

## Afterwards

- The pictures stay in the out folder under `<lab>`; a note or a finding says in words what a picture showed (copy
  one to `private/shots/` only when the check's record needs it). Nothing from a run is committed.
- A finding goes into the findings register, a tool change into the change ledger, as for any check.
- End a session with `send <out> quit`, not by killing it, so the game's sound is unmuted again.
- Check that no game is left running (`tasklist` for `XComEW.exe`) and that no `d3d9.dll` stays beside the game.

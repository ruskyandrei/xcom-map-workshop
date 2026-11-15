# EXP-57: Enable saving, F5 at the main menu

Date: 15 November 2026. Status: **runs 2 and 4 passed** (12:43: F5 at the main menu opened the battle, and Long
War's save and reload went through, but with Sectoid pods, F-112; 14:32: the same with EXALT pods); runs 1 and 3 not
run. Findings: F-89 (saving in a test play), F-109 (Long War's EXALT missions), F-112 (EXALT missions' pods).

## What it checks

The editor's **Enable saving** (built on 15 November at the user's design, after
[EXP-56](EXP-56-save-after-login.md) showed a battle opened after the main menu's login saves and loads):
- With it on, a play starts the game with `XComMapWorkshop-start.txt` (in `XEW\Binaries`), whose one line is
  `setbind F5 exec XComMapWorkshop-play.txt`. Nothing is opened, so the game stays at its main menu and logs in. F5
  there runs the play's commands and the battle opens.
- Not yet seen: whether F5 reaches its binding on the main menu (XCOM's menu could take the key first), and whether
  `setbind` works that early (it runs as the engine finishes starting, before the menu is up). If F5 does nothing,
  `~` and `exec XComMapWorkshop-play.txt` does the same.
- Long War's EXALT missions always have it on: their save and reload as they start (F-109) should now go through.
- Once the game has closed, the editor puts back `XComInput.ini` (the binding) and `profile.bin` (the logged-in game
  writes the play's test squad into the profile) as they were before the play.

## Setup

- The lab copy, as every run. XCOM closed. The main editor (port 8768), restarted after this change.
- No new build: maps of the game, no project.
- Claude reads `Launch.log`, the save folder and the ledger after each run.

## Runs

**Run 1: an abduction, saved and loaded.**
1. Open `URB_Bar` from the map browser with no project. Play in game: the window has **Enable saving**, off. Tick it
   (the line under it says what happens) and Play.
2. XCOM opens at its main menu. Press **F5** there. Does the battle start?
3. Pause menu, **Save Game**, a new slot. Does "SAVING..." go away?
4. Move a soldier, then **Load Game** and load that save. Does the battle come back as saved?
5. Pause menu, **Exit to Main Menu**, then **F5** again. Does the battle start again?
6. Close the game.

**Run 2: a data recovery, Long War's save and reload.**
1. Open `URB_PoliceStation` with no project. Play in game, the mission **Data recovery**: Enable saving is ticked and
   greyed, its tooltip says why. Play.
2. At the main menu press **F5**. The battle starts, "Mission Briefing: Please Wait" shows. Does the briefing finish
   (Long War saves, loads the save and goes on) and the battle start with the covert operative?
3. Close the game.

**Run 3 (optional): Build and test with saving on.** In the prefab builder, Build and test with Enable saving ticked;
at the main menu F5 starts the test.

**Run 4 (added after run 2): EXALT's pods.** Run 2 again, on any map with a data recovery. Are the enemies EXALT
(operatives, with heavies or snipers), and does the battle play as before?

## Result

**Run 2 passed, 15 November 12:43** (the lab copy's `Launch.log` of 12:43:18; the user: "that works"). A data recovery
on URB_OfficePaper_EWI:
- 4.9 s the start screen; 5.1 s `Execing ..\..\Binaries\XComMapWorkshop-start.txt` (the binding, no map); 5.6 s the
  login ("Obtained steam user stats").
- 7.2 s `Execing ..\..\Binaries\XComMapWorkshop-play.txt`: F5 reached its binding on the main menu, and the battle
  opened (`URB_OfficePaper_EWI?CapturePoints=1?RadarArrays=1`, `FIXDEPLOYMENT ... (Capture and Hold)`).
- 11.6 s Long War's save (`SAVING CHECKPOINT`, `General Checkpoint Async Work Finished` at 11.65 s); 29.9 s its load
  (`LoadingFromShell=1`), and `XGBattle_SP.PostLoadSaveGame` at 31.3 s: the briefing finished and the battle went on.
  The user played it to 240 s and closed the game.
- No save was left behind: Long War deletes its reload save after the load (`RebalanceMutator`, `DeleteSaveGame`).
- The enemies were Sectoids, not EXALT (the user: "there was no exalt, everything was sectoids"). A play set the
  profile's pod type to Sectoids for every kind; plays of EXALT's missions now set an EXALT operative (F-112). Run 4
  checks it.

**Run 4 passed, 15 November 14:32** (the lab copy's `Launch.log` of 14:32:12; the user: "57 is confirmed"). A data
recovery on a project's build of Demolition (`URB_Demoliti_HoverU_9c4b`, built 14 November):
- 3.2 s the start file; 8.4 s F5 ran the play's commands, and the battle opened
  (`URB_Demoliti_HoverU_9c4b?CapturePoints=1?RadarArrays=1`).
- 9.45 s to 9.51 s the EXALT operative's and heavy's units and weapons loaded when first needed (`JIT Loading
  Unit_ExaltOperative`, `Unit_ExaltHeavy`, `Weapon_ExaltAssaultRifle`, `Weapon_ExaltHeavyMG`), with their looks
  (`ApplySkin: ePawnType_ExaltOperative CharSkins_Exalt.ExaltSoldiers_Red_DIF`, the heavies green).
- 16.2 s Long War's save; 34.5 s its load (`LoadingFromShell=1`). The reloaded battle had 4 pods: 8 EXALT operatives
  and 4 EXALT heavies (two operatives and a heavy each; the game picks a sniper or a heavy once for the whole battle,
  `GetSupportAlien`'s alternative, so another play may have snipers), 7 soldiers (the squad and the covert operative).
- One Sectoid and one Chryssalid are listed beside them, outside the pods, and the user saw neither. Every play's
  battle lists one Chryssalid (run 2's log, the 11:57 abduction's), so they look like units the game keeps aside
  [inferred; which player holds them isn't read].
- The game closed normally at 97.9 s.

So F5 works on the main menu and `setbind` works that early, F-109 is fixed for data recovery, and F-112's EXALT pods
load and play. Covert extraction and the EXALT raid take the same path and haven't been played. Runs 1 and 3 weren't
run (EXP-56 run 1 already saved and loaded an abduction opened after the login).

# EXP-56: saving and loading in a test play once the game has logged in

Date: 15 November 2026. Status: **run 1 passed** (11:57; two tries before it skipped steps, see Result). Finding: F-89 (saving does not work in a battle started
without a campaign), and F-109 (Long War's EXALT missions wait on it).

## What it checks

F-89's cause, as read on 15 November from the game's scripts (`XComOnlineEventMgr`, the start screen's `UIShell`,
the Steam subsystem's `OnlineSubsystemCommonImpl`):
- On PC the start screen logs in by itself: `UIShell.OnInit` sets a 0.1-second timer for `DelayedLogin`, which calls
  `BeginShellLogin(0)`. An ordinary start's log shows it about half a second after the start screen loads ("Using
  cached profile data instead of reading", "Obtained steam user stats").
- The login is what readies saving: `InitializeDelegates` hands the Steam content interface the event manager's
  callbacks for a save written, read, deleted and the save list read (its `ContentCache[0]`); the storage device is
  selected (`bHasStorageDevice`, which `HasValidLoginAndStorage` asks before the game lets a save start); and the save
  list is read (the slot numbers).
- A test play runs its `open` line from `-EXEC` 0.1 seconds after the start screen loads, before its interface is up,
  so none of that happens. Then a save is written with nobody told when it ends (the "SAVING..." notice stays, and
  `CheckpointIsWritingToDisk` never clears), a load waits for a read that never reports back, and a save goes to slot
  1 whatever saves there are (EXP-53's EXALT runs wrote the lab copy's `save1` when the game closed).
- A test battle left for the main menu does get the login (the log of 12 November's run on the prefab stage).

So the same battle started after a login should save and load. This run starts one that way, by hand.

## Setup

- The lab copy, as every run. XCOM closed. The main editor (port 8768).
- No new build: any map of the game, no project.
- Claude reads `Launch.log` after the run.

## Runs

**Run 1: an abduction, saved and loaded.**
1. Open a map from the map browser with no project (for example `URB_Bar`), the header's mission Abduction, and
   **Play in game**. The battle starts.
2. Escape for the pause menu, **Exit to Main Menu** (not Quit to Desktop), and wait for the main menu. This step is
   the run: the main menu is where the game logs in. Saving before it is the failure F-89 already records.
3. Open the console (`~`) and type `exec XComMapWorkshop-play.txt`, then Enter. The same battle starts again, now
   after the login. (The file stays in `XEW\Binaries` while the game runs.)
4. Pause menu, **Save Game**, a new slot. Does "SAVING..." go away after a few seconds?
5. Move a soldier, then pause menu, **Load Game**, and load that save. Does the battle come back as it was saved?
6. Close the game.

**Run 2 (if run 1 passes): a data recovery, Long War's save and reload.**
1. Open `URB_PoliceStation` with no project, the header's mission Data recovery, and **Play in game**. The battle stops
   at "Mission Briefing: Please Wait" (F-109).
2. Try the pause menu (Escape). If it comes, leave for the main menu and run `exec XComMapWorkshop-play.txt` as in
   run 1: the briefing should finish (Long War saves, loads the save and goes on), and the battle should start with
   the operative. If the pause menu doesn't come, close the game; that writes the stuck save as the lab copy's
   `save1`.

## If it passes

A play would have to open the battle after the start screen's login, with nothing typed. The ways seen so far:
- **A loader map**: the commands file opens a small map of the editor's with the start screen's game class
  (`?game=XComUIShell.XComShell`), whose interface logs in as the start screen's does; the map's Kismet then waits
  and runs `exec` on a second commands file with the battle's `open` line. Automatic, and on plain Enemy Within too;
  it needs that map made and installed with plays.
- **The editor sending the `exec` line** to the game once its log shows the login: no new map, but it types into
  whatever window has the focus.
- **Filling in the callbacks with `set`** before the `open` (the Steam subsystem's `ContentCache` is a plain script
  property): no login at all, but no storage device and no save list either, so it would cover less.

## Result

**Run 1 passed, 15 November 11:57** (the lab copy's `Launch.log` of 11:57:49). An abduction on URB_OfficePaper_EWI:
- 3.3 s the play's battle opened; 8.7 s Exit to Main Menu (`Browse: XComShell?closed`), and the login ran
  ("Obtained steam user stats" at 9.5 s).
- 15.0 s `Execing ..\..\Binaries\XComMapWorkshop-play.txt` from the console, and the same battle opened again.
- 22.9 s Save: both checkpoints copied and `General Checkpoint Async Work Finished` at 23.0 s, and the notice went
  away. The game named it save21, one past the highest save there (save20), with save1 and save6 free: a new save
  takes the highest number plus one (F-89's open naming question, answered). The file is whole: its compressed data
  at byte 1024, 697,656 bytes.
- 29.1 s Load of that save (`LoadingFromShell=1 ... LoadingSave`): the level came up (`Finished loading level`) and
  the battle came back. The game was closed at 33.8 s.
- Once the game had closed, the editor moved save21 to save999 (a whole play save) and had set the 10:45 play's
  broken save999 aside before the play (`XCOM Map Workshop\broken saves\20261115-115747-1-save999`).

F-89's cause is confirmed: a battle opened after the start screen's login saves and loads. Run 2 (Long War's EXALT
reload) wasn't run; by the same cause it should go through. Next: a play that logs in by itself
(play-login-plan.md).

The tries before it:

**A try, 15 November 10:43 to 10:45** (the lab copy's logs `Launch-backup-2026.11.15-10.45.08.log` and
`Launch.log`): two plays, EWI_ExaltHQAssault and an abduction on URB_SlaughterhouseA (`?Meld=1`). Each log has the
start screen's `Browse: XComShell` once and then the battle's, and no second start screen: the battle was not left
for the main menu, so the steps from 2 on were not done. In the abduction the save was tried from the battle (both
checkpoints copied, `General Checkpoint Async Work Finished` at 19.4 s) and the game was closed at 30 s. Saving was
still stuck, and loading didn't work. That is F-89 as recorded, and says nothing of the login. A play's save is never
to take a campaign's slot: the editor now moves a play's saves to save999 and down once the game closes and puts back
a save they replaced (F-89, "Until fixed"). The save was then said to have been made from the main menu. The game
writes its log as it goes, and a trip to the title screen shows in it (12 November's run on
the prefab stage: `Browse: XComShell?closed` at 53 s, then the login's "Obtained steam user stats"); neither of these
two logs has one, nor a second `Execing` of the commands file. Most likely the pause menu was meant.

**A second try, 15 November 11:32** (the lab copy's `Launch.log` of 11:32:33 and the crash dump beside it): a play of
URB_OfficePaper_EWI (abduction), the battle opened at 3.4 s; Exit to Main Menu at 13.9 s, and the login ran (14.1 to
14.6 s: "Using cached profile data instead of reading", "Obtained steam user stats"). At 15.6 s the load screen read
the save list, and at 17.5 s the old Slaughterhouse save loaded from it (save999: the stuck save the 10:45 play left,
which the editor had moved out of slot 1). The map started loading and the game crashed 5 seconds in.
No `exec` of the commands file and no save after the login, so steps 3 and 4 were not done.
- What it shows: after the login the load screen lists the saves and a load starts (before it, a load from the
  battle's menu hung with nothing logged, EXP-43). The crash is that file's: a divide by zero in the compressed-data
  reader, on a file that is 670 copies of the save header and then the data (F-89, "The save a play leaves is
  broken"). It says nothing yet of a save made after the login.
- The editor now takes such broken saves out of the game's folders (F-89); the next play sets this save999 aside.
- Still to run: steps 3 to 5 (exec the commands file from the title screen, a new save, and a load of that save).

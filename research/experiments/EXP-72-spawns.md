# EXP-72: spawn points and mission objects

Date: 18 November 2026. The editor spawns plan's game checks (implementation plan, stages SP3 to SP9), under Long War
in the lab copy, each run in the hidden game (`tools/lab/hidden_game.py`, the game-test skill) on a map staged by the
editor's dry Play in game. Plain EW is not played in these runs. One run a stage that needs the game; what offline
checks settle is not played again.

## Run 1: a moved bomb takes its helper point (SP3, F-124)

**Played 18 November 2026: passed on the log; the shot of the arrow was not clear.**

The project `Bomb helper test` on URB_SlaughterhouseA (variant `BombHelperTest`, a quick build), its council bomb
record picked, moves the bomb's group three tiles across: from (-528, 1872, 68) to (-240, 1872, 68). Export 33 puts
the stream's `PointInSpace_0` (2.5 units from the bomb across, 204.5 above it) in the bomb's group, so the project's
eleven overrides on `URB_Slaughterhouse_Stream` include it at (-239, 1874, 273). Without that the mutator would count
ten actors near the bomb and place nothing (F-124).

What the run adds: does Long War's bomb mutator find the moved bomb and place it and the nodes?

- The log's `XComBombMutator: locating the bomb` lists twelve actors found, `PointInSpace_0` among them, then
  `found 8 nodes`, `moving the bomb`, the bomb `XComLevelActor_11` at (-625, 2063, 64) with its button, floor marker,
  emitters, rebuild volume and visible point there, and `ArrPoints[0] PointInSpace_0` at (-625, 2063, 270): 206 above
  the bomb, the mutator's own offset. Then `moving nodes` with a place for each of the eight. No "can't find" line.
- The shot meant for the arrow over the bomb (`bomb.png`, and `bomb_fow.png` with the fog lifted) showed the street
  under fog with neither the bomb nor an arrow told apart; not retaken (the log answers the question).

So the helper moves with the bomb and the mutator places a moved bomb again: F-124's fix is verified.

## Run 2: an added bomb placed on a map of its own (SP4)

**Played 18 November 2026: passed (the mutator's lines, a node used); the bomb itself was not seen.**

The project `EXP-72 added bomb placed` ([exp72_project.py](../../tools/editor/examples/exp72_project.py)) is
EXP-54's cleared URB_Bar played as an added council bomb only (variant `URB_Bar_X72`, a quick build). An added bomb
streams `URB_Slaughterhouse_Stream`; export 33 gives the map its objects as `donors`, and the page shows them in the
Spawns view to be moved. The script moves the bomb's group and each power node's group whole onto ground floor
tiles of the cleared map that stay, at least five tiles apart, each part keeping its height over the floor it stood
on:

| Group | Main object | Place (x, y, z) |
| --- | --- | --- |
| the bomb (with `PointInSpace_0` 204.5 above) | `XComLevelActor_11` | (-1777, -1489, 4) |
| node | `XComLevelActor_10` | (-1489, -1873, 16) |
| node | `XComLevelActor_3` | (-1105, -913, 16) |
| node | `XComLevelActor_4` | (-241, -1873, 16) |
| node | `XComLevelActor_5` | (143, -1105, 16) |
| node | `XComLevelActor_6` | (623, -1393, 8) |
| node | `XComLevelActor_7` | (1007, -625, 16) |
| node | `XComLevelActor_8` | (1391, -1009, 8) |
| node | `XComLevelActor_9` | (1679, -625, 0) |

It compiles with one warning (the project's second landing zone plays under Long War only) and two notes (the bomb
mission streams the Slaughterhouse stream; five drop-in points and three pods of that stream stand over no floor of
this map). No `mission-donor-place` warning: every bomb and node stands on floor. The build writes the moves into
the variant's own copy of the stream (`URB_Slaughterhouse_Stream_URB_Bar_X72`), which replaces the stream in the
added record.

What the run adds:
1. **The mutator's lines:** does it find the bomb at its new place, and does it move the bomb and the nodes or fall
   back to where the project put them? Where do the game's buttons stand?
2. **A node used:** with a soldier beside one node's button, is its interact ability offered and taken?
3. **The bomb seen** at the place the log names.

What the run showed (the hidden game, out folder `<lab>\hidden-runs\sp4-added-bomb`):
1. **The mutator's lines: passed.** `locating the bomb` lists the bomb, its rebuild volume, `PointInSpace_0`, its
   button, visible point, emitters and floor marker; `found 8 nodes`; then `moving the bomb`: the bomb, its button,
   floor marker and visible point at (1679, 815, 0) and `ArrPoints[0] PointInSpace_0` at (1679, 815, 206), and
   `moving nodes` with a place for each of the eight (z 0 or 16). No "can't find" line. The live places
   (`getall XComInteractiveLevelActor Location`, `getall PointInSpace Location`) match those lines, all in the level
   `URB_Slaughterhouse_Stream_URB_Bar_X72` (the variant's copy of the stream), all inside the grid; none at a
   Slaughterhouse place. So Long War found the added bomb where the project put it and placed it and the nodes
   itself: the project's places are the fallback, as the page says, and were not played.
2. **A node used: passed.** A soldier stood on the tile east of node `XComLevelActor_4`'s button at (-1489, -625, 0)
   (a straight side: a diagonal tile gives no interaction point). On PC the use is the in-world prompt by the node,
   not an ability of the bar; the run pressed it with `console V_Key_Press` and `V_Key_Release`. The log shows the
   button going to its inactive state; the shot after it (`node_use1.png`) shows "Turns until bomb is fully charged"
   at 6 where it was 4, the used node's green glow gone and the nodes farther off still glowing.
3. **The bomb seen: not seen.** Two shots looking at (1679, 815, 0) with the fog lifted showed only the empty
   background. The game reads the bomb and its floor marker with `bHidden = True` and a node with False: the bomb
   is likely hidden until the squad finds it ("Find the bomb"), which the run didn't do. Run 1's shot didn't show it
   either.

Side observations, not followed: one pod stood at z 457 on this cleared map (Long War's pod mutator places pods
on the game's floor tiles); the mutator's lines appear twice in the log, a second pass 0.8 seconds after the first
with the same places.

## Run 3: scripted drop-ins as Long War plays them (SP8, the baseline)

**Played 18 November 2026: passed, after one console change that let a drop-in fire at all.**

The project `EXP-72 Pier A drop-ins as Long War` on URB_PierA (variant `URB_PierA_X72L`, Council rescue: "Escort
Sgt. Carlock to the Skyranger"), with no spawn rule; its one edit (an emitter deleted) only makes it a build. The
question: where does a scripted drop-in (a `SeqAct_SpawnAlien` of `URB_PierA_Stream`) land under Long War's drop-in
mutator?

What the run showed (out folder `<lab>\hidden-runs\sp8-dropins-lw`):
- Four turns ended and four trigger volumes walked into: no drop-in. Read offline (`tools/upk/kismet_links.py`): each
  of the stream's six `SeqAct_SpawnAlien` runs at the end of the alien turn while the VIP isn't saved and a pod flag
  is set; a trigger volume sets its flag only while the Kismet's AlienCap (the roaming-alien count less 2) is at least
  1. This start read AlienCap -2, so no drop-in could be armed. Whether a real campaign's Council rescue gives the
  map roaming aliens wasn't looked at.
- Second take: AlienCap set to 5 by console (`set URB_PierA_Stream.TheWorld:PersistentLevel.Main_Sequence.SeqVar_Int_32
  IntValue 5`), a soldier walked into `TriggerVolume_4` at (552, 1176). At the end of the alien turn the log reads
  `XComSpawnAlienMutator: found obj SeqAct_SpawnAlien_12`, "Found good unit" for four soldiers, 55 "Found good cover
  point" lines and `SpawnLoc = -427.56,431.44,0.00`. The new unit `XGUnit_18` stands at (-433, 431, 58): 14 and 16
  tiles from the action's own two points, (523, 1681) and (-530, 1778), 11 tiles from the nearest soldier. The shot
  (`dropin_unit18.png`) shows Sectoids by the containers there.

So Long War's mutator puts a scripted drop-in at a cover point of its own choosing near the squad, not at the
action's points: what the rule is for.

## Run 4: scripted drop-ins land where placed (SP8)

**Played 18 November 2026: passed.**

The project `EXP-72 Pier A drop-ins placed` (variant `URB_PierA_X72P`), the same map and mission with
`spawnRules: {"dropIns": "placed"}`. Play in game wrote its line into the lab copy's `DefaultRandomSpawns.ini`,
section `[XComLZMutator.XComSpawnAlienMutator]`: `ExcludeMaps = "URB_PierA_X72P"`, under a comment line of the
editor's. Run 3's steps were repeated (AlienCap 5, a soldier into `TriggerVolume_4`, end of turn).

What the run showed (out folder `<lab>\hidden-runs\sp8-dropins-placed`):
- The game rewrote its generated `XComRandomSpawns.ini` with the new ExcludeMaps entry at the start: the Default
  file alone is enough.
- At the end of the alien turn, for `SeqAct_SpawnAlien_12` and for `SeqAct_SpawnAlien_61` (another drop-in AlienCap
  armed), the log reads `XComSpawnAlienMutator: current map(URB_PierA_X72P) found in ExcludeMaps list, skipping to
  defaults.`, with no "Found good unit", cover point or SpawnLoc line. (The mutator writes "found obj …" before it
  reads the list, so that line shows on an excluded map too.)
- The new units stand on their actions' own points: `XGUnit_17` at (523, 1681, 67) on `SeqAct_SpawnAlien_12`'s
  (523, 1681), `XGUnit_18` at (-1198, 3316, 67) on `SeqAct_SpawnAlien_61`'s, 4.4 tiles from a soldier (the mutator
  never drops closer than 7). The shot (`dropin_unit17.png`) shows a Thin Man by a crate there.

So the rule's line is read by Long War and the drop-ins land where the map (or the project) placed them.

## Run 5: a wave's places moved (SP9)

**Played 18 November 2026: unclear at first (the battle never started); played again the same day after T-44's and
T-46's fixes: passed.**

The project `EXP-72 Police Station wave moved` on URB_PoliceStation (variant `URB_PoliceS_X72W`, Data recovery,
EXALT's capture and hold), started with saving on (Long War saves EXALT missions as they start): the nine destination
points of `XComWaveSystem_0`'s set 1, wave 1, group 1 in `URB_PoliceStation_CNH`, moved 7 tiles east together.

What the run showed (out folder `<lab>\hidden-runs\sp9-wave`, three starts): the map and the variant's copy of the
stream load, Long War's landing mutator stands aside for the mission type, the units and EXALT's content load and
`LWRVERSION label added` comes about 9 seconds in. Then the log repeats two lines of Long War Rebalance's (an
achievement loader with `why=PostLevelLoaded`, a native lookup) every 0.39 seconds, "Mission Started" never comes,
and the game takes no console command (no shot, no exec). The same on all three starts, the third with RETURN and
ESCAPE pressed by key at 52 and 57 seconds. Read offline, the stream's Kismet only listens for the wave system's own
events; set 1 comes by turns and set 2 takes over when the transmitter is captured, so ending turns would have been
enough.

Run 10 started the plain URB_PoliceStation's Data recovery the same way and hung the same way: the hang is the hidden
game's saving start on this mission, not the variant (T-44). The moved wave places were not checked in game then.

**Played again** (out folder `<lab>\hidden-runs\sp9-wave-run5`), staged with Play in game on a `--dry-play` test
server (the project's build, Data recovery, saving on; Iron Fist, a MEC trooper, first, T-44) and started with
`--play-file ... --saving`:
- Long War saved and reloaded (`LoadingFromShell=1` at 34.6 seconds) and the battle went on: "Mission Started" at 16.1
  and again at 37.8 seconds, `LWRMISSION ... waves=0/5 ... aliens=12 xcom=6`. No crash (T-46's fix).
- **The points**: `getall XComSpawnPoint_Alien Location` read the nine in the variant's copy of the stream
  (`URB_PoliceStation_CNH_URB_PoliceS_X72W`) at their moved places, every one, at Z 32; none at an original place.
- **The wave**: invincibility on, turns ended. At the alien turn 2 (211.96 seconds) the log shows the wave system
  (`XComWaveSystem::OnEndTurn`, `UpdateWaveSpawning`, `SpawnWave`, `SpawnGroup`) making three drop-ins
  (`XGAISpawnMethod_DropIn_0` to `_2`), and Long War's count went to `waves=1/5` (227.89), then 15 aliens. The three
  new units, read as they dropped (230.75) and again at the squad's turn 3 (268.12, their pawns' places the same at
  279.90):

  | unit | what | place (x, y, z) | nearest moved point | nearest original |
  |---|---|---|---|---|
  | XGUnit_22 | EXALT operative | -924, 720, 224 | 17 (-908, 720), 16 off | 672 off |
  | XGUnit_23 | EXALT sniper | -716, 1008, 82 | 46 (-716, 1008), on it | 672 off |
  | XGUnit_24 | EXALT operative | -812, 528, 82 | 48 (-812, 528), on it | 672 off |

  XGUnit_22 stands 140 units higher than the others, by moved point 17 (on a car there, as the shot suggests).
  The shot `wave1.png` (fog lifted, the camera over the moved points) shows the parking lot with three EXALT markers
  by the cars, two operatives and a marksman, and the HUD's "Active: 3".

So a wave's destination points moved by the project are where its units drop in: the Build's stream move holds for
the wave system, and Long War's drop-in mutator, which moves the scripted actions' drop-ins (run 3), leaves the wave
system's alone.

## Runs 6 to 8: the base map's pods and Meld points edited, copied and deleted (SP6, SP7)

**Played 18 November 2026: passed.**

URB_Bar's Abduction, with Long War's pod and Meld mutators (`XComPodSpawnMutator`, `XComMeldSpawnMutator`) commented
out of the lab copy's `DefaultMutatorLoader.ini` for these three runs, so the map's own points play as plain Enemy
Within plays them (the loader put back byte for byte afterwards). No mutator line of either in any run's log. Each
run read the points in the game (`getall XComAlienPod_Abduction Location`, `PodIndex`, `bCommanderPod`, `getall
XComMeldContainerSpawnPoint m_eDifficulty`, `m_iDestroyedOnTurn`, `m_iSpawnGroup`, the canisters
`XComMeldContainerActor` with `m_iTurnsUntilDestroyed`) and the units at turn 1.

The game moves every pod onto a tile when the battle starts: the readbacks are those settled places (the map's pod 0
at (1599, 1642) stood at (1615, 1679)), and some pods' yaws change from game to game.

- **Run 6, the map as it is** (out folder `<lab>\hidden-runs\sp6-bar-base`): pods 0 to 4 with indices 0 to 4, no
  commander; the Meld points as the map has them (0 and 1 hard, turn 8; 2 and 3 easy, turn 4; all group 0); one
  canister on point 0, countdown 8. Aliens stood by pods 1, 2 and 3 (within 1.3 tiles) and 5.5 to 6 tiles from pod 0.
- **Run 7, the SP6 build** (`URB_Bar_X72S`, `sp6-bar-edited`): pod 0 at (1679, 1679) facing yaw 0 (moved a tile
  and turned a quarter in the project; settled 64 east of run 6's place); pod 1 `bCommanderPod = True`; Meld point 2
  hard, destroyed on turn 6; Meld point 3 in spawn group 1; every other point as in run 6. Three aliens stood within
  1.1 tiles of pod 0's new place; one canister, on point 1.
- **Run 8, the SP7 build** (`URB_Bar_X72C`, `sp7-bar-copies`): the game has pods 0, 1, 2, 3, 5 and 6 and no pod 4;
  pod 5 at (-1105, 239) with index 5 and pod 6 at (-1585, 719) with index 6 (the copies' places, settled); Meld
  point 4 at (912, 720, 17), hard, destroyed on turn 4. Three aliens deployed at each copy; none stood within 5 tiles
  of pod 4's old place. Two canisters, on points 0 and 3.

So the game reads the edited points, their values, the copies with their own indices and the delete as the Build
wrote them, and deploys aliens at the moved pod and the copies.

## Run 9: the copies' build under Long War as installed (SP7)

**Played 18 November 2026: passed.**

`URB_Bar_X72C` (run 8's build: two pod copies, a Meld copy, a pod deleted) with the lab loader put back as installed
(out folder `<lab>\hidden-runs\sp7-bar-lw`). "Mission Started" at 24 seconds, Long War's mutators' lines
(`XComMeldSpawnMutator: NumContainers = 3`, `XComPodSpawnMutator: NumPods = 4`, `Found 5 random locations`), turn 1
with no error, one turn ended and the alien turn passed. Long War replaced every pod and Meld point of the map with
its own, the copies among them (no pod of index 5 or 6, no Meld point 4 left), as the panel says it does when it finds
enough places; the aliens stood by its four pods.

## Run 10: plain Police Station's Data recovery with saving on (run 5's question)

**Played 18 November 2026: the same hang as run 5.**

URB_PoliceStation as the install has it, Data recovery, started as run 5 (`--saving`), out folder
`<lab>\hidden-runs\sp9-police-plain`: `LoadMap: URB_PoliceStation`, the landing mutator standing aside for
`eMission_CaptureAndHold`, `LWRVERSION label added` at 9 seconds, then 613 lines of `LWR Ach: loaded 531 definitions
... why=PostLevelLoaded` with no "Mission Started" in 240 seconds. So run 5's hang is the start of this mission, not
the variant's moved wave places (T-44).

Read again the same day: saving was on in both runs. They lacked the mission's open-line options, which the two data
recovery starts that began (EXP-57 runs 2 and 4) had, but run 11 ruled that out (T-44).

## Run 11: plain Police Station's Data recovery with the mission's options (T-44)

**Played 18 November 2026: failed; the battle never began with the options either.**

Staged with Play in game on a `--dry-play` test server: the commands set EXALT's pods and the test squad and end `open
URB_PoliceStation?CapturePoints=1?RadarArrays=1`; saving on (the start file binds F5). Started as run 10. Two first
starts (out folders `<lab>\hidden-runs\sp9-police-options` and `...-2`) crashed before the main menu because Windows
had no mouse (T-45). The third (`...-3`), with the mouse back: `LoadMap: URB_PoliceStation?...?CapturePoints=1?
RadarArrays=1` at 7.1 seconds, EXALT's operative and heavy loaded, then the same 613 `why=PostLevelLoaded` lines to
247 seconds, no `--- SAVING CHECKPOINT ---`, no reload, no "Mission Started"; the loading movie never stopped. So the
options aren't what this mission lacks on this path. Read from the logs instead: the covert operative's pawn is missing
when the battle makes it (`Accessed None 'm_kPawn'` in `CreateDebugCovertOperative`, then a female operative loaded),
where the starts that began made a male one without a warning (T-44).

## Run 12: Police Station's Data recovery with a soldier first (T-44's fix)

**Played 18 November 2026: the battle began; then the game crashed in Long War's reload (T-46, since fixed).**

Staged with the editor's Play in game after the fix: the squad in the order Iron Fist (a soldier), Tracks (the SHIV),
Gren, Sky, Long; saving on. Out folder `<lab>\hidden-runs\sp9-police-soldier-first`. Windows had no mouse or keyboard
at the time, so the stand-in mouse was used (`input.log`); the keyboard was Windows' own. No `Accessed None 'm_kPawn'`
and no content of id 0; `JIT Loading Soldier_MaleCovertOps` with Iron Fist's head and hair; the loading movie stopped
at 8.3 seconds, `--- SAVING CHECKPOINT ---` at 15.0, "Mission Started" at 16.4. Long War's reload began at 33.3
seconds (`LoadingFromShell=1`) and the game ended with an access violation about 1.4 seconds later.

## Run 13: the same with six soldiers and no SHIV

**Played 18 November 2026: the same.** The default six soldiers (`<lab>\hidden-runs\sp9-police-six-soldiers`): the
operative took Tom Alpha's looks, the battle began ("Mission Started" at 16.0 seconds), and the game crashed 1.4
seconds into Long War's reload. So the SHIV wasn't the reload's crash.

## Run 14: URB_Bar, a quicksave loaded, with the stand-in mouse

**Played 18 November 2026: the load crashed too (T-46).** `<lab>\hidden-runs\standin-bar-reload`: the quicksave was
written (F10, `--- SAVING CHECKPOINT ---`), the Load Game menu showed it first, and the game crashed 1.4 seconds
after its `LoadMap ... LoadingFromShell=1`. A rerun with the stand-in's trace on (`standin-reload-trace`) showed only
the per-frame polls of the stand-in mouse up to the crash. Every load that worked before had a real mouse, which
pointed at the mouse; runs 15 and 16 showed otherwise.

## Run 15: the same load with the mouse there, and without aliens (T-46)

**Played 18 November 2026: the mouse was not it; aliens were.**

- With the mouse and keyboard in Windows and no stand-in (`<lab>\hidden-runs\reload-real-mouse`): the load crashed
  as in run 14, 1.3 seconds after `LoadingFromShell=1`.
- The 17 November loads that went through were all of battles without aliens (EXP-71: "no aliens"); every one that
  crashed had aliens, and Long War's pod mutator's four pods (`XComPodSpawnMutator: NumPods = 4`, which it logs only
  when the battle lists pods). The same Bar quicksave and load with `--no-aliens` (`reload-no-aliens`) went through:
  the squad stood on the Bar 30 seconds after the load.
- With `--crash-log` (`reload-crash-log`) the stand-in DLL logged the fault: a thread of the game's own read
  0x61300001 at `XComEW.exe+0xf1331`, a block of memory no longer there.

## Run 16: DXVK's texture budget off (T-46's fix)

**Played 18 November 2026: passed.** The run 15 load with aliens, with DXVK's `d3d9.textureMemory = 0`: given from
outside (`reload-notexmem`), the load went through and the shot showed the squad on the Bar with a Meld canister
beside them; then through hidden_game.py's own `<out>\dxvk.conf` (`reload-fixed`), the same, with 18 units read back
after the load. Run 5 can now be played.

## Run 17: edited no-spawn volumes, and pods copied from a deleted pod (the clear-spawns work, export 34)

**Played 18 November 2026: passed** (out folder `<lab>\hidden-runs\x72-volumes`; F-125).

`X72Volumes`, a build of URB_Bar staged by a dry Play in game (an Abduction, the test squad), with Long War's pod and
Meld mutators commented out of the lab loader as in runs 6 to 8 (no line of either in the log; the loader put back
byte for byte afterwards). The project, made in the editor:

- the map's five pods deleted, as Clear map deletes them;
- four copies of pod 1, made before it was deleted (the copies-of-a-deleted-pod case the writer used to refuse),
  each moved onto one of the map's pod places: pod 5 on pod 1's (-912, -144), pod 6 on pod 2's (-912, 432), pod 7 on
  pod 3's (-1392, 912), pod 8 on pod 4's (-2064, 432);
- `XComNoSpawnVolume_0` stretched from the van to 7 by 7 tiles round pod 5 (x -1248 to -576, y -480 to 192);
- a copy of `XComNoSpawnVolume_2`, 7 by 7 tiles round pod 7 (x -1728 to -1056, y 576 to 1248);
- a copy of `XComNoSpawnVolume_3`, 5 by 5 tiles round pod 6 (x -1152 to -672, y 192 to 672), Keeps aliens out off;
- pod 8 in no volume (the control).

The build read back offline as made. In the game:

- **The pods.** Only pods 5 to 8 exist, with indices 5 to 8 and 2, 3, 2 and 2 aliens. `AlienNoSpawnZone` reads
  False on the copy round pod 6 and True on every other volume.
- **Where the aliens were put** (`getall XComSpawnPoint_Alien Location`, the places `GetSpawnPoint` worked out, in
  pod order):

  | Pod | Volume | Alien 0 | Alien 1 | Alien 2 |
  | --- | --- | --- | --- | --- |
  | 5 | stretched, keeps aliens out | on the pod | (-529, -145): 4 tiles, the first tile past the east edge | |
  | 6 | copy, aliens off | on the pod | 1 tile, inside | 1 tile, inside |
  | 7 | copy, keeps aliens out | on the pod | (-1297, 527): 4.1 tiles, the first tile past the south edge | |
  | 8 | none | on the pod | 1 tile | |

  Without the volumes the second aliens of pods 5 and 7 would have stood a tile off, as run 6's did on those places.
- **Turn 1 is not the evidence.** Before XCOM's first turn the game revealed all four pods one after another and
  their aliens moved to cover (four "Pod Revealed" lines, then "Enemy Contact: Off Guard (x1) (9 active aliens)"), so
  at turn 1 even the control pod's aliens stood 5 and 7.6 tiles away. The three shots with the fog lifted show those
  places after the moves, not the rule.
- **The battle goes on.** Alien turn 1 played out and XCOM turn 2 came with no crash.

So the game honours a stretched volume, a copied one and the aliens switch as the Build writes them, and deploys
aliens at pods copied from a deleted pod. Civilians (`CivilianNoSpawnZone`) were not played.

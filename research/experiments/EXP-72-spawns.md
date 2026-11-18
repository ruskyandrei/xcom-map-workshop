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

# Known bugs

Bugs in the editor or its builds that are known and not fixed yet: what a user sees, how to work round it, and where
the cause is written up. A bug is added here when it is found and left (a game check that fails, a report, a review),
and taken out, with a line in the change ledger, when its fix is merged.

Each entry: an id (`KB-<n>`, never reused), what happens, since when, a workaround if there is one, the cause in a
line, and its finding in the [findings register](research/findings-register.md) where the evidence is.

## Open

### KB-1: A cover block grouped with a made wall keeps its cover when the wall is destroyed

- **What happens.** A made wall and an invisible cover block in one group (Break together), with no prop in the
  group: when the wall is blown up, the block stays. Units beside its tile still get high cover from an empty tile,
  and it still stops them walking there.
- **Since.** The version after 0.6.0. Before it, such a group stopped the Build ("a cover block and no breakable
  piece", review finding 36); now it builds and plays, with this left.
- **Workaround.** Keep the cover block out of the made wall's group, or add a breakable prop to the group standing
  by the wall part next to the block: when that part breaks, the prop goes and takes the block with it (a block that
  breaks with its group goes when a prop of the group is destroyed; the props of a group with a made wall went with
  their wall parts in the same game check). Or delete the block by hand where the wall is meant to go.
- **Cause.** A block that breaks with its group takes no damage of its own and goes only when a prop of its group is
  destroyed; a made wall passes its destruction on by damaging the pieces its parts list, which the block ignores.
  Letting the block take that damage would let ordinary shots break it too.
- **Finding.** [F-143](research/findings-register.md) (found in
  [EXP-88](research/experiments/EXP-88-review-fixes-in-game.md), check 1), which also names a fix to try: a hidden
  helper prop with no collision in the wall's group that takes the block with it.

### KB-2: A baked Build of a map whose only change is a larger grid stops

- **What happens.** A project that only grows the map's grid (Map grid), built with **Bake the lighting** on, stops
  in the lighting with `relight.py: error: --receivers-near needs an edit`. The same project built without baking
  is made.
- **Since.** 0.5.0, which added Map grid (found 16 November 2026).
- **Workaround.** Build it without baking (the default): a grown grid alone changes no light. Or bake it with any
  other change in the project, such as a cover block or a moved piece.
- **Cause.** The Build sends a project that changes nothing in the map but its size to the relight, which has no
  edit to relight and refuses; a grown grid with other changes takes the route that keeps the map's own lightmaps.
- **Finding.** [T-37](research/findings-register.md), which names the likely fix: a resize alone takes that route too.

### KB-3: A moved or deleted piece leaves its separate light and decals behind

- **What happens.** Some maps place a piece's light and decals as actors of their own around it. Moving or deleting
  the piece leaves them where it stood: URB_Bar's fog pod, moved, leaves its glow light and its three decals at the
  old place. Its smoke goes with it since 0.6.0.
- **Since.** Every version.
- **Workaround.** Move or delete the light yourself in the Lights view. The decals can't be picked in the editor and
  stay.
- **Cause.** The export reads pieces, lights, effects and sounds, but not decals, and carries with a piece only the
  effects placed with it; its lights are separate actors to the editor.
- **Finding.** [F-50](research/findings-register.md) (EXP-11 run 2; the smoke's part fixed for export 30).

### KB-4: A pasted invisible floor wider than a tile sits by the ground under its first tile

- **What happens.** An invisible floor of more than one tile, pasted or placed on uneven ground, takes its height
  from the ground under its first tile alone, so it can stand above or under the ground elsewhere.
- **Since.** 0.4.0, which added invisible floors (recorded 16 November 2026).
- **Workaround.** **Fit to ground** in the piece panel fits it to all of its tiles; the panel shows the range.
- **Cause.** Placing measures the ground at the centre of the tile under the floor's pivot.
- **Finding.** None in the register; the change ledger's 16 November entry on placing invisible floors.

### KB-5: A made ground Block a storey high can be climbed onto from its side

- **What happens.** A ground **Block** 96 units high (one storey) does not stop units: a soldier ordered onto its
  top steps up from beside it, without using a ramp.
- **Since.** 0.6.0, which added made ground.
- **Workaround.** None known for certain. A block taller than a storey may stop units; not tried.
- **Cause.** Not found. Stepping up is not it (a 64-high block with stepping up off is not climbed, F-133), so the
  climb comes from another part of the game's path building.
- **Finding.** [F-129](research/findings-register.md) ([EXP-77](research/experiments/EXP-77-ground.md) run F).

### KB-6: A soldier on a map roof that breaks away under them stays at roof height

- **What happens.** On a map's roof set to **Breaks further in battle**, a soldier standing on a part that a blast
  breaks away stays in the air at roof height through the aliens' turn, and drops only when ordered to move.
- **Since.** 0.6.0, which added Breaks further in battle.
- **Workaround.** Order the soldier to move: they drop to the ground then.
- **Cause.** Not found. On a made floor the game drops the soldier at once (EXP-76 run E); a map roof's broken
  fragments don't.
- **Finding.** [T-47](research/findings-register.md) ([EXP-83](research/experiments/EXP-83-kept-roofs.md) run A).

### KB-7: A game started from a renamed copy of its exe is not seen as running

- **What happens.** If XCOM runs from a copy of `XComEW.exe` renamed `XCOMLauncher.exe` (a way some players skip the
  launcher), the editor does not see it running or closing: Game maps and Play in game allow installs and Undo while
  it runs, and a play's kept config can be put back too early.
- **Since.** Every version.
- **Workaround.** Start the game the usual way (Steam or its own launcher), or close it before using Game maps or
  Play in game.
- **Cause.** The editor looks for `XComEW.exe` in the process list.
- **Finding.** [F-84](research/findings-register.md).

### KB-16: A map pack made by 0.6.0 or before names folders of the computer that made it

- **What happens.** In the pack's zip, `packages\<map>\manifest.json` is the build's manifest as it was: it names the
  project file's folder (under the Windows user folder, so with the account name), the game install, the build's work
  folder and the files each stage read. Whoever gets the pack can read them.
- **Since.** Every version that exports map packs, up to 0.6.0. Fixed on main since 20 November 2026 (the pack writes a
  manifest of public fields, every text scrubbed of the editor's folders) and since 22 November with a guard for any
  other folder; in no release yet.
- **Workaround.** Delete `packages\<map>\manifest.json` from the zip before sharing it (nothing reads it: Install.cmd
  and the game use `pack.json` and the map files), or export the pack again with a version after 0.6.0.
- **Cause.** The pack export copied each build's manifest whole.
- **Finding.** None in the register: the editor review's finding 14, and the smaller built maps plan's P1 to P3.

### KB-25: A blended ground look shows one of its textures in the editor, not the game's mix

- **What happens.** A piece in a material that blends textures by vertex colour (the forest and terrain grounds,
  river banks, vertex-painted asphalt) is drawn in the editor in one of its textures, often not the one the game
  shows. A made ground in Rocks River Vert Paint is grey-brown rock in the editor and green grass in the game; the
  river bank pieces it comes from (COverseer_TheBarrens) are rock all over in the editor and, by the game's shader, a
  mix of grass, mud and dirt in the game.
- **Since.** Always: the editor has drawn one texture per material from the first.
- **Workaround.** None in the editor: see the look in the game (Play in game), or on the map the piece comes from.
- **Cause.** The editor draws one colour texture per material, picked by name, and no vertex colours; the game's
  shader mixes the layers by them. [F-167](research/findings-register.md).

### KB-22: A diagonal cover mark inside a patch level's rebuild volume gets no cover in the game

- **What happens.** A mark on a tile that one of the map's streamed patch levels reworks at the battle's start (for
  CSmallScout_Farm, `patch_farm`'s eight volumes: around tiles (42..48, 24..30), (59..65, 37..43) and six more) is
  written by the Build and then worked out again by the game, which never writes diagonal cover back: no cover there,
  in every mission. The Diagonal cover view puts a warning triangle on such a mark (picked: the area dashed, the
  reason in its panel) and the Build warns of it, but the mark still gives no cover there.
- **Since.** The branch that places diagonal cover by hand (23 November 2026); the map's own marks are not affected
  (their makers kept the patch volumes off them).
- **Workaround.** Move a mark with the warning triangle off the area its panel names (drawn dashed when it is
  picked). A cleared map is free of it: its build streams none of the map's patch levels.
- **Cause.** The Build's reading of the battle's rebuild (`native_copy.rebuild_order`) takes the base level's volumes
  only, and the export counts a patch level's volumes without their places; with them added, the rule matches every
  tile EXP-95's save shows reworked bar one, a meld container's.
- **Finding.** [F-162](research/findings-register.md) (EXP-95's save read tile by tile).

### KB-27: An LWR 3 campaign's UFO crash site can crash at its start; a built map with a large start-up rebuild makes it certain

- **What happens.** A campaign's Crashed Raider mission under LWR 3.00.00 beta 17 crashes the game a few seconds
  after the map comes up. With a drop-in pack's `RaiderDeepWoodsFixed` (a variant of `CLrgScout_DeepWoods`, builds of
  0.6.0 and 0.7.0) it crashed every time (4 of 4); with no pack, on the game's own `CLrgScout_DeepWoods`, the same
  save started the mission once and crashed the next time. A battle opened directly (Play in game, no campaign) never
  crashes: it makes no mission-start save.
- **Since.** Seen 25 November 2026. The race is LWR's; our builds make it far more likely.
- **Workaround.** With a pack map: take the pack's folder out of `CookedPCConsole` for that mission and put it back
  afterwards. On the game's own map it is a matter of timing: load the save and launch again (an Ironman campaign
  always makes the mission-start save; others make it only with Autosave on). A copy of LWR's `LWRebalance.u` whose
  `RebalanceMutator.UFOFogLiftStart` returns before starting its fog timer (the 19-byte `SetTimer` statement replaced
  by a return and no-ops of the same size) adds no fog viewers, so nothing races: a crash site played through to turn
  2 with it in a hidden run on the LWR v3 lab copy. The cost is that the UFO no longer shows through the fog.
- **Cause.** The campaign's mission-start save writes the world data's per-viewer sight maps on a worker thread, and
  LWR's UFO fog adds its viewers about 0.2 s after the save begins, which moves those maps under it. On the UFO
  missions that worked the save finished 0.03 to 0.10 s before the fog. A built map whose rebuild volumes make the
  battle's start-up rebuild big (11,771 to 14,216 tiles against the game map's 1,386 to 1,528) keeps the save from
  finishing first every time. Reported to LWR's developers (a guard on `SaveInProgress()` before adding viewers);
  the Build's start rebuilds reach several times past what the changes need (plan written, not built).
- **Finding.** [F-171](research/findings-register.md).

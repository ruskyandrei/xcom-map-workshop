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

### KB-8: The Map grid's panel opens under the Selected piece panel

- **What happens.** With a piece selected, opening **Map grid** from the rail puts its panel in the same place as
  the Selected piece panel, which covers it: the grid panel's **Done** can't be clicked.
- **Since.** 0.5.0, which added Map grid (found 21 November 2026).
- **Workaround.** Clear the selection before opening Map grid, or press Esc to close the grid tool.
- **Cause.** Both panels open at the same place on the right and the grid tool leaves the selection as it is.
- **Finding.** None in the register; found by the browser checks (a check left a piece selected before the Map grid
  check).

### KB-10: A save can fail while another program holds the file for a moment

- **What happens.** Saving a project, a prefab's picture, the library or a build record can stop with "could not be
  written" if another program (a virus scanner, a backup or search indexer) holds the file at that moment. Saving
  again a moment later works.
- **Since.** Every version (found 21 November 2026 by reading the code; not reported).
- **Workaround.** Save again.
- **Cause.** Only the game install's records retry when Windows refuses a file that is briefly held; the project and
  library writers try once.
- **Finding.** None in the register; found by a review of the code the refactor left as it was (21 November 2026).

### KB-11: A hand-edited map record with spaces around "=" is not replaced by a Replace build

- **What happens.** If the game's `DefaultMaps.ini` holds a map record written by hand with spaces around `=`
  (`MapName = "..."`), installing a Build that replaces that map adds the editor's record but leaves the hand-written
  one in place, so the game can still load the original.
- **Since.** 0.5.3, where Replace began taking out only the records the Build has its own for (found 21 November
  2026 by reading the code; not reported).
- **Workaround.** Write the record without spaces around `=`, as the game's own records are, or remove it by hand.
- **Cause.** The editor reads the records' fields in two ways: the one that finds the map allows the spaces, the one
  that lists what a Replace takes out does not.
- **Finding.** None in the register; found by a review of the code the refactor left as it was (21 November 2026).

### KB-12: A prefab's Test in game fails when the builds folder's path is long

- **What happens.** **Test in game** in the prefab builder stops in its Build with a `FileNotFoundError` naming a
  file that ends in `.upk.grow-tmp`, when the builds folder sits deep in folders. A project's own Build from the same
  folder works.
- **Since.** 0.5.3, which added Test in game (found 21 November 2026).
- **Workaround.** Keep the builds folder (Setup, the output folder) on a short path, such as the default in
  Documents.
- **Cause.** A prefab test's Build works in folders of its own under the builds folder (a test's id, its artifacts,
  the Build's work folder, the lit copy), which add about 190 characters, so the grown map's temporary file passes
  Windows' 260-character path limit.
- **Finding.** None in the register; found by the exploratory test after the refactor (old: the version before it
  does the same).

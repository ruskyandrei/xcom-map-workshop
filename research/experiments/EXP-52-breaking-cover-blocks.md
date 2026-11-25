# EXP-52: cover blocks that break with their group

Date: 13 November 2026. An invisible cover block put over a piece stays as an invisible wall when the piece
is destroyed; could it go with the piece, through the group option Break together?
Plan: breaking-cover-blocks-plan.md. Finding: F-101.

## What was read (offline)

- The game's link between pieces that break together, `AffectedChildren`, is an array of `XComDestructibleActor`:
  a cover block, a hidden `XComLevelActor`, can't be named in it and has no damage states to follow with.
- `XComDestructibleActor` extends `XComLevelActor`, so a prop has the block's cover properties.
- A destroyed prop keeps its mesh and collision unless one of its `DestroyedEvents` takes them. URB_Bar has 116
  placed props whose one event is an `XComDestructibleActor_Action_Hide`. Its native `Activate` (`0x99EF00`) calls
  the actor's `SetStaticMesh(none)` and `GotoState('Dead')`; `SetStaticMesh` (`0xAD86E0`) with no mesh calls
  `DisableCollision` and hands the component's old bounds to the world data.
- `ApplyDamageToMe` returns at once for a toughness with `bInvincible`; `_Destroyed.BeginDestroyed` damages what
  stands at the prop's place unless `bDestroysSurroundingArea` is off.

## What changed (offline)

- A cover block (high or low) in a group with Break together on is built as a hidden prop
  (`cover_blocks.BREAKING`): an `XComDestructibleActor` with no archetype on the block's box mesh, one destroyed
  event (a Hide action under it), a toughness of its own with `bInvincible`, and `bDestroysSurroundingArea` off.
- Each breakable piece of the group lists the block in its `AffectedChildren`; the block lists nothing.
- One breakable piece and a block are enough for a group, and the piece may be the map's own, left in place.
- Blocks outside such a group, and invisible floors, are built as before.

Checked offline: the tests of the recipe against URB_Bar's own props (the state frame, the events array, the
action's and the toughness's data), the compiler's groups, and the project below built and read back.

## The project

`EXP-52 cover blocks that break` (URB_Bar, [exp52_project.py](../../tools/editor/examples/exp52_project.py)), a
quick build, on the pavement in front of the bar (the marked shot (`EXP-52-overview.png`)):

| Place | What stands there | Built as |
| --- | --- | --- |
| A | a low block over the map's own trash cans `XComDestructibleActor_183` and `_184`, grouped with `_183` | `XComDestructibleActor_529`, listed by `_183` |
| B | a high block over a copy of a trash can (`XComDestructibleActor_528`), grouped with it | `XComDestructibleActor_530`, listed by `_528` |
| C | a high block over the map's cans `XComDestructibleActor_0` and `_1`, in no group | `XComLevelActor_469`, as before |

## Run 1

What the run adds over the offline checks:
1. The map loads (a prop with no archetype, its action and toughness).
2. Before anything breaks: A gives low cover and B and C high cover, and none can be walked through.
3. **A:** destroy the cans (a grenade or a rocket). The low cover should go and the tile should be free to walk.
4. **B:** destroy the copied can. The high cover should go, the tile should be free and seen through.
5. **C:** destroy its cans. The block should stay: high cover and no way through, as today.
6. **A blast that leaves a can standing:** if a can of A or B survives a hit, its block should still be there.
7. A save and a load after 3 to 5: the blocks that went are still gone, C still stands.
8. Anything odd: a crash, a visible box, a sound or debris from a block.

## Result: passed, bar the save and load

Played by hand on 13 November 2026 through the editor's Play in game: a save and reload is not possible when
launching maps from the editor, but the rest checks out. So the map loads with the blocks made as props with no archetype; the
grouped blocks at A and B give their cover and go with their cans, cover and wall alike; the block at C, in no group,
stays. Which of the looks were made one by one is not recorded.

Not covered: a save and a load after the blocks went (step 7). A battle started by Play in game can't be saved, so
this needs a build installed in a campaign.

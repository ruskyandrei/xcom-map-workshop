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

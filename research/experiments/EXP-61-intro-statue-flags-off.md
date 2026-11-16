# EXP-61: a statue with every flag off (Act1_IntroLevel)

Date: 16 November 2026. A piece flags plan probe (P7, run 1's cases A and B on another map: the user's "ethereal"
piece, edited where it stands), played by the user: a visible, colliding statue with all its flags turned off,
which no run had tried before ([F-114](../findings-register.md): "walking off on a visible, colliding piece is not
played").

## The build (offline)

The user's project `intro+` (Act1_IntroLevel, revision 9, in the editor's project store), a quick build from branch
`piece-flags` (`Act1_IntroLe_Intro_5001-20261116-151931`, the variant's SHA-256 starting `b63e84fab52c`). Besides its
other edits (one piece moved, two added, one deleted), two of the map's pieces, where they stand, one on the other:

| Piece | Mesh | Before | Asked |
| --- | --- | --- | --- |
| `XComLevelActor_210`, the statue (at about −1621, −95, 149) | `UrbanStatue_A` | walking, cover, sight, mouse on; floor off | walking, cover, sight, mouse off |
| `XComLevelActor_93`, its plinth (at about −1631, −95, 23) | `MarbleFlowerPot_Base` | every flag on | every flag off |

Both collide and have simple collision (export 27's `collides`, `bodySetup`). The Build's writer added on each actor
`bAlwaysConsiderForCover` false, `bIgnoreForCover` true, a `VisibilityBlockingData` struct with
`bBlockUnitVisibility` false, `bIgnoreFor3DCursorCollision` true, and on the plinth `bPathColliding` false; it read
both back with a fresh reader. Their tiles were seeded and rebuilt by one volume (tiles 36 to 41 across, 9 to 14
along, levels 1 to 8 over the ground's own: 153 seeded, 130 already marked).

## Run 1

**Passed** (16 November 2026, played by the user): "I toggled all flags off for a statue, and it correctly became
fully no-clip, soldier could walk through and cursor did not select it".

What it shows: with walking, cover, sight and floor off, a soldier walks through the statue and its plinth, which
are still drawn; with the mouse off, the cursor passes them. So Blocks walking off frees the tiles of a visible,
colliding piece, its occupancy included, and the rebuilt tiles do it in the game, not only in the saved settings.

Not told apart by run 1: cover and sight on their own (whether a soldier beside the statue gets no shield toward it,
and whether units see through it), and each flag alone (the plan's case C); whether the plinth's top is still offered
as a place to stand (Floor off); damage to the statue (case H); a save and reload (case J).

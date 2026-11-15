# EXP-58: blockers (cover blocks with Cover set to None)

Date: 15 November 2026. Discord feedback S6: "something you can use to disable walking in an area
without making it provide cover/be stood upon" (the Discord feedback list, kept locally).

## What was read (offline)

From [native-code-notes.md](../native-code-notes.md), the tile rebuild:
- Occupancy (`0xA58810`) counts an actor with the cover interface whose `ConsiderForOccupancy` is true (for an
  XComLevelActor `bAlwaysConsiderForCover`, true by default) and whose mesh has a BodySetup. It doesn't read
  `CoverForceFlag` or `bIgnoreForCover`. So a block ignored for cover still fills its tiles.
- The cover trace (`0xA0A2B0`) skips an actor whose `ShouldIgnoreForCover` is true (`bIgnoreForCover`; F-82, where an
  invisible floor stopped giving the tile below it cover). So no unit beside such a block gets cover from it.

## What changed (offline)

- Cover block recipe version 2 ([cover_blocks.py](../../tools/bake/cover_blocks.py)): version 1 and one kind more,
  `block`. It is the high block's hidden box with no `CoverForceFlag`, `bIgnoreForCover` True, `bCanClimbOnto` and
  `bIsValidDestination` False, and low cover's `VisibilityBlockingData` (units see past it). Breaking with a group, it
  is a hidden prop that saves `bIgnoreForCover` too.
- In the editor it is a cover block with **Cover: None (blocks walking)**, drawn purple, named a blocker in its panel.
  There is no separate Add panel entry (the user: no point in a separate item).
- Checked offline:
  - recipe 1's digests are unchanged, and a version 1 block builds to the same file by either version;
  - the blockers built in URB_Bar read back with the properties above;
  - the compiler takes `block` from version 2 only;
  - the browser smoke's cover check passes;
  - the project below built and read back (`XComLevelActor_469`: `bIgnoreForCover` True, no `CoverForceFlag`; the
    control `XComLevelActor_470`: `CoverForce_High`).

## The project

`EXP-58 blockers` (URB_Bar, [exp58_project.py](../../tools/editor/examples/exp58_project.py), in the editor's project
store), a quick build. It is on the pavement in front of the bar (the marked shot (`EXP-58-overview.png`)), one row
south of EXP-52's places:

| Place | What stands there | Built as |
| --- | --- | --- |
| A | a blocker, 1 × 1 tile, corner (-576, -96, 16) | `XComLevelActor_469` |
| B | the control: a high cover block, 1 × 1, corner (-288, -96, 16) | `XComLevelActor_470` |
| C | a blocker over a copy of the trash can `XComDestructibleActor_0`, grouped with it (Break together), corner (-96, -96, 16) | `XComDestructibleActor_529`, listed by the can's copy `XComDestructibleActor_528` |

To play it: open `EXP-58 blockers` in the editor (its last build is in place) and use Play in game.

## Run 1

What the run adds over the offline checks:
1. **A, walking:** pick a soldier and point at A's tile. It shouldn't be a destination, and a path past it should go
   round it.
2. **A, cover:** put a soldier on a tile beside A. There should be no shield toward A. For comparison, a soldier
   beside B should get the full shield toward B.
3. **A, standing on it:** no move should end on top of A, and no climb should go onto it.
4. **A, sight:** with A between a soldier and an alien, it should neither block the view nor stop a shot. The aim
   should count no cover from A.
5. **C:** at first it blocks its tile as A does. Destroy the can (a grenade or a rocket), and C's tile should then
   be free to walk into.
6. Anything odd: a crash, a visible box, a sound or debris from a blocker.

## Result

**Sight seen** (15 November 2026, the user's own test alongside EXP-59): a blocker 4 × 6 tiles, which units
"could definitely see through and shoot through". That is as built (item 4): the blocker saves low cover's
`VisibilityBlockingData`, so it doesn't block sight, as Discord S6 asked (stop walking, give no cover). Items 1 to 3
and 5 (walking, cover, standing on it, C breaking with its can) are not reported yet.

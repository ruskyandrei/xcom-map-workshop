### A known bug entered: a door in a slanted wall gives diagonal cover against its jambs (KB-20)

A user reported cover shields on both sides of a UFO's inner door in a built map, where the game's own maps give
none. Nothing in the tools changes here; the bug is written down and its fix planned.

- [KNOWN-BUGS.md](../../KNOWN-BUGS.md) has it as KB-20: what a user sees, since 0.7.0, the cause (the Build's finder
  takes a door jamb for a slanted corner) and that there is no workaround in the editor.
- [The findings register](../../research/findings-register.md)'s F-153 says what the 111 unmarked tiles the finder
  takes on the game's own maps are, by kind (25 door openings, 31 further wall tiles, 52 columns, 3 odd ones), and
  what tells a door opening from a marked tile. The counts are from F-153's own record
  ([diagonal-finder-2026-11-22.json](../../research/evidence/diagonal-finder-2026-11-22.json)); no map was read again.
- The docstrings of [tile_rule.py](../../tools/bake/tile_rule.py) and [tile_world.py](../../tools/bake/tile_world.py)
  name the first diagonal cover plan where it now is (built, so among the plans done).

Checked: the `repo` suite. Not checked: which of the Build's two ways made the reported tile (the finder, or a mark
carried with a moved piece); the reporter's build record will say.

Known gap: the bug stays until the planned change, which takes the finder out of the Build and has diagonal cover
placed by hand in a view of its own.

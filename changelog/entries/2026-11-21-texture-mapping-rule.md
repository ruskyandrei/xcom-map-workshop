### The texture mapping's rule, one module for every generator

How a made piece's surface takes its texture when its look's own mapping is replaced (the custom geometry improvements
plan, section 5) is written once, for the wall, slab and ground generators to call when stage 4 builds the controls:
size per repeat, a count of repeats or one fit across the whole surface (each axis its own mode if asked), a turn,
flips and offsets in repeats, applied in that order; world alignment from the piece frame's place in the world; and the
half-float rebase that keeps a face's coordinates near 0 with the pattern's phase kept.

- [uv_mapping.py](../../tools/bake/uv_mapping.py) (new): `check`, `surface_of`, `uv`, `rebased`, `half_float_room`.
- The free form's mapping takes `modeV` (the mode along v): [made_edits.py](../../tools/editor/made_edits.py)
  `mapping_valid`, [research/editor-contracts.md](../../research/editor-contracts.md).
- [ARCHITECTURE.md](../../ARCHITECTURE.md) names the made pieces' Build modules.

Checked: [test_uv_mapping.py](../../tools/bake/tests/test_uv_mapping.py) (new: each mode at sample points, a longer wall
keeping its bricks, three repeats staying three, tile along and fit up, flip-turn-offset order, world-aligned pieces
lining up, the rebase, the shapes); the editor suite.

Known gaps: no generator calls it yet (stage 4, after the generators' free form lands and the Texture mapping section's
design is chosen).

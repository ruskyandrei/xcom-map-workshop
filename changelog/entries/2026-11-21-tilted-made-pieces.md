### Tilted or turned made floors, roofs and ground build as drawn, with what is not made for them said

A made floor, roof or ground shape pitched or rolled builds as drawn (the custom geometry improvements plan, decision
D6, its default) and the Build warns once per piece of what is not made for it: a floor's or roof's cursor floor is the
box round it, so the cursor may not land on it where it slopes; past about 10 degrees a unit on it gets no cover (F-81),
past 45 it is no floor to stand on. A floor or roof turned about the vertical off the quarter turns is warned that its
cursor floor is the box round it, so at its corners the cursor may land beside it. A free-form piece no longer gets its
template's off-grid warning: it is drawn to stand anywhere at any angle, and the Build seeds and rebuilds the tiles
over its box and makes its fracture columns where it stands.

- [made_edits.py](../../tools/editor/made_edits.py) `made_tilted`, run by [compiler.py](../../tools/editor/compiler.py)
  after the cursor floors; `add` leaves a free-form piece out of `single_grid_rule`.

Checked: [test_compiler_free.py](../../tools/editor/tests/test_compiler_free.py) (a pitched slab, a slab turned off
the quarter turns, one on a quarter turn, a rolled block; no off-grid warning for free-form pieces) and the editor suite.

Known gaps: a turned slab's own turned cursor volume (the plan's first try, 4.6) needs a game run; until then its cursor
floor is its box, as the warning says.

### The prefab builder's Build menu draws made pieces

The Build menu's tools (Wall, Room, Room with a roof, Floor, Roof, Patch, Block, Ramp, Rock) did nothing in the
prefab builder: clicking one left no tool drawing, since the start of a drawing refused the builder outright. A
prefab keeps a made piece as a map does (its records and its stamping already carried them), so the refusal is gone
and the builder draws them as a map does.

- [made_drawing.js](../../tools/viewer/web/made_drawing.js): `startBuild` no longer returns in the builder.
- [browser_builder.py](../../tools/viewer/tests/browser_builder.py): the builder check draws a wall from the Build
  menu (as the user does), a floor and a block, saves the prefab and opens it again with the three made pieces.

Checked: `browser_builder.py` on a test server (every part passes, the new one included), and the browser smoke
checks `made-prefab` and `prefab-test`; drawn in `?prefab=new` by hand script too: a wall, a floor, a block and a
room with a roof (its five pieces), no page errors.

### The texture handles show alone while a made piece's Texture mapping fold is open

With the Texture mapping fold open on a made wall, floor or ground shape, the size handles stepped aside but the move
and turn gizmo stayed, over the texture handles. Now every other control steps aside while the fold is open on the
piece handled: the gizmo is held aside (in move and turn mode alike), and a rock's picked corner is let go with its
arrows. They come back once the fold is shut or another piece is picked.

- [gizmo.js](../../tools/viewer/web/gizmo.js): `hold(on, who)` keeps each holder apart, so the fold's hold and a
  placing or a rock corner's never release each other.
- [made_mapping_wiring.js](../../tools/viewer/web/made_mapping_wiring.js): `syncPicked` holds the gizmo aside while
  a surface is picked.
- [made_handles.js](../../tools/viewer/web/made_handles.js): a rock's picked corner is let go when its fold opens.
- [browser_walls.py](../../tools/viewer/tests/browser_walls.py): the texture-mapping check asserts the gizmo aside
  with the fold open (after R too, and on a floor picked with the fold still open) and back once it is shut.

Checked: the browser smoke checks texture-mapping, walls, made-break, rock-corner and free-handles on the police
station, adding and copy-drag on the bar; a headless picture of a made wall with the fold shut (gizmo and size
handles) and open (the texture handles alone).

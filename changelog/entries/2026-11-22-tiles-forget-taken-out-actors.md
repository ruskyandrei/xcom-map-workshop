### A built map no longer crashes the game on saving when its tiles named deleted pieces (F-156 verified, KB-17 out)

A quicksave on the reported city project's built map crashed the game, in every build of it. The map's tile data
names actors by their place in the package: each floor tile its floor piece and floor volume, each link its path
object, each interact point its actor. A Build that deletes a piece takes it out of the level's actor list and the
tiles still named it; the game frees such an actor after loading, and where the battle's rebuild does not work the
tile out again, saving followed the tile into freed memory
([F-156](../../research/findings-register.md), [EXP-91](../../research/experiments/EXP-91-smaller-built-maps.md)).

- [world_grid.py](../../tools/upk/world_grid.py) `forget`: the tile model with no tile naming an actor of a set: a
  floor piece or floor volume becomes none, a link through a path object among them is dropped, as an interact point
  of one (a tile left with none saves none).
- [world_links.py](../../tools/upk/world_links.py): `encode_floor` and `encode_interact`, a floor and an interact
  element written from their fields ([diagonal_keep.py](../../tools/bake/diagonal_keep.py) uses `encode_floor`).
- [native_copy.py](../../tools/bake/native_copy.py): `taken_out` (the exports under the level not in its list) and
  `forget_taken_out`, run on the written map after the diagonal tiles, in quick and baked builds alike; the native
  record's `tilesForgot` and a log line say what it cleared.
- [ARCHITECTURE.md](../../ARCHITECTURE.md): a row for it. [KNOWN-BUGS.md](../../KNOWN-BUGS.md): KB-17 out.

Checked: across the install's 96 maps no tile names anything outside its level (so the step changes no map but a
Build's); the upk suite (`test_world_grid` `Forget`: the elements encode back to their bytes on URB_Bar, nothing
gone changes nothing, a floor piece and volume become none, a link and a door's interact points dropped) and the bake
suite (`test_native_copy`: no tile of the shared bar builds names an actor taken out, the record says what was
cleared). In the game (EXP-91, hidden runs): the project's quick build crashed; the same with those references set
to none saved and loaded; the full build with the fix saved, loaded and saved again.

Known gaps: a tile outside every rebuild volume whose floor piece was deleted keeps its floor, now naming no piece
(the rebuild volumes decide which tiles the battle works out again, as before). The rewritten tile data is appended
and the old bytes stay in the package (3.3 MB in that map), as for the diagonal tiles.

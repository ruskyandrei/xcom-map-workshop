### The Build writes a building's own cursor floors

The Build's cursor floors stage ([native_copy.py](../../tools/bake/native_copy.py) `floors_and_cursors`) now takes the
native edit's buildings with `cursorFloors` ([made_cursors.py](../../tools/bake/made_cursors.py) `build_areas`) beside
the made floors and roofs, and writes them with the same writer (`apply`): the map's cursor volumes over such a
building are taken out of the level's list and stand again round it as clones, and its own floors are laid over it
as clones of a plain volume, each with its floor number and box. The build manifest's `madeCursors` names the
building of each volume it laid for one (`building`); the Build's log counts them apart from the made slabs'. The
written map is read back as before (`verify`). [ARCHITECTURE.md](../../ARCHITECTURE.md)'s line for the stage says so.

Checked: [test_buildings.py](../../tools/bake/tests/test_buildings.py) `CursorFloors` writes a three-floor building
of uneven floors (the top one over half of it) into URB_Bar of the install, reads the map back and finds its listed
cursor volumes to be the floors `made_cursors.storeys` gives (the compiler's rule): the bar's four volumes stand again
round it, its own floors start 2 under its boxes; a building without the tick brings none. `bake -k made_cursors`.

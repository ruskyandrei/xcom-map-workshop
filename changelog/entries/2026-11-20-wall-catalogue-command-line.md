### The wall catalogue's command line and install like the slab and ground catalogues'

[wall_catalogue.py](../../tools/bake/wall_catalogue.py) now reads `build [--out] [--only ...] [--audit] [--check]`,
as [slab_catalogue.py](../../tools/bake/slab_catalogue.py) and [ground_catalogue.py](../../tools/bake/ground_catalogue.py)
do: `--check` builds again and says whether the file is the same, writing nothing. The old `check` action still works
for one release (it says it is now `build --check`). The maps are read from the game install the settings name
(`library.cooked_of` of the settings' game, as the other two find theirs), in place of the lab's path helper; the
tool no longer puts `tools/lab` on its path. `build` takes the install as an argument (`game`, the settings' when
none). The frozen list of 344 walls and the file's format are unchanged (the refactor plan's D10 default), and so are
the wall measurer's numbers (D1).

Checked: `build --check` on this install reports the checked-in `walls.json` the same bytes; the bake suite's
catalogue tests (`CatalogueFile`, `CatalogueBuild`, `Files`, `Fresh`, `Rebuilt`) pass.

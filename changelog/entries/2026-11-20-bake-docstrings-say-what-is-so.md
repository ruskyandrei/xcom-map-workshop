### The package and bake tools' docstrings say what is so

Review finding 64, its items in tools/bake and tools/upk. Comments only; no code changed.

- [package_grow.py](../../tools/upk/package_grow.py): the game reads tables after the export data (gate C6 passed),
  and every Build that adds an actor, a name or an import writes this way; the texture clone that fixes inline bulk
  offsets is `lightmap_textures.clone_texture` now.
- [native_sounds.py](../../tools/bake/native_sounds.py): a clear takes the map's own ambient sounds out (since 18
  November), but those the project moves or copies and, in a clear that keeps the scenery outside, those outside it.
- [bounce.py](../../tools/bake/bounce.py): the environment colour is decoded with `codec.GAMMA` (a plain power of
  2.2), not the sRGB curve, in both places that said so.
- package_edit.py, seed_tiles.py and kismet_links.py, which called shipped writers untried or packages
  "uncompressed", were put right with the changes that made them so (the package toolkit and product-code moves of
  the same day).

Checked: the files compile.

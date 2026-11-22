### A reported 336 MB built map traced to its copies' cloned lightmap atlases (F-151, KB-15)

A user's map pack held a large-city variant whose map file was 336 MB (the game's own map is 13 MB). Read offline
from the pack: 304 MB of it are lightmaps the Build moved inside the map, and 290 MB of those are clones made for
copies: each copy gets every lightmap and shadow-map texture its source uses, a whole 1024 atlas though it uses a
small rectangle, and the map holds every mip uncompressed.

- [findings-register.md](../../research/findings-register.md): F-151, the counts and the cause, with ways to fix it.
- [KNOWN-BUGS.md](../../KNOWN-BUGS.md): KB-15, what a user sees and a workaround.

Checked: the pack's manifest (`lightingInside`) and a count of the built map's lightmap and shadow-map textures
against the game's map (`lighting_records`), and the code that clones them
([native_copy.py](../../tools/bake/native_copy.py) `clone_assembly`,
[lightmap_textures.py](../../tools/bake/lightmap_textures.py) `clone_texture`,
[inline_lighting.py](../../tools/bake/inline_lighting.py)); the repo suite.

Known gaps: not fixed; the map was not played, so its texture memory in the game is not measured.

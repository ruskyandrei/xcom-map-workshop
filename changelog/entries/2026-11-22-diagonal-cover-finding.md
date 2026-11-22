### A built map's lost diagonal cover: the cause found and recorded (F-149, KB-14)

A user reported that maps saved in the editor lose diagonal cover (a unit in the corner of a slanted wall, on the UFO
maps). The cause: the game writes that cover flag only in a map's full build, from its cover seed actors, and the tile
rebuild a battle runs for each rebuild volume clears a tile and never reads the seeds; a build's rebuild volumes reach
every tile of a grown map and a few tiles round every other edit. Nothing in the tools changes here: the fix is not
built.

- [findings-register.md](../../research/findings-register.md): F-149, with where the game has diagonal cover, which
  edits take it, what the game showed and a fix to try.
- [KNOWN-BUGS.md](../../KNOWN-BUGS.md): KB-14.
- [diagonal-cover.py](../../research/evidence/diagonal-cover.py): a read-only script. `maps` lists a map's cover
  seeds, its baked diagonal tiles and the rebuild volumes that reach them; `save` sets a tactical save's static and
  cover flags beside the map's bake.
  [diagonal-cover-2026-11-22.json](../../research/evidence/diagonal-cover-2026-11-22.json) is its reading of the 26
  maps of the install that hold a cover seed.
- [cover-build.md](../../research/native/cover-build.md) and
  [cover-and-sight.md](../../research/native/cover-and-sight.md): a rebuilt diagonal tile got no cover in the game,
  where the reading expected straight cover.

Checked: the script run over the 26 maps, two builds of CSmallScout_Farm and two saves; a hidden game run of a grown
CSmallScout_Farm (LWR), whose save at turn 1 has none of the map's 8 diagonal tiles with any cover, and a soldier
put on two of them (teleported, then walked there) read no cover. The `repo` suite.

Known gaps: why the rebuild's straight cover test finds nothing on those tiles is not read; plain Enemy Within was
not played (the code read is the exe both share).

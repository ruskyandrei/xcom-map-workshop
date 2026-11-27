### Textures handed to the GPU as the game stores them

Stage A-S3b of the game-likeness plan: a block-compressed texture (DXT1, DXT3, DXT5, BC5) is now exported as a DDS
file holding every live mip as the game stores it, and the page hands those blocks to the GPU without decoding
them. Built before A-S3 so the materials' extra textures don't cost PNG memory first; the export version is raised
with A-S3.

- [texture.py](../../tools/viewer/texture.py): `export_texture(..., container="auto")` writes the DDS (every live
  mip from the largest down while each halves the one before, each read from the package or its texture cache and
  unpacked); other formats, and a caller that asks for a picture (the map picture), stay PNG. The record says which
  (`container`, `levels`). `dds_png` gives a DDS file's largest level as PNG.
- [export.py](../../tools/viewer/export.py) says which it asks for (`Exporter.texture_container`): PNG until the
  export version that carries the materials' programs (A-S3) switches DDS on, so that maps export again once; a PNG
  texture's record is as it was. The bake's albedo reads textures itself and is unchanged.
- [texture_file.js](../../tools/viewer/web/texture_file.js) (pure) reads a DDS file's levels and says which WebGL
  extension a format needs (S3TC, its sRGB form for colour textures, RGTC for BC5);
  [scene_pieces.js](../../tools/viewer/web/scene_pieces.js)' `texture` makes a compressed texture from it, or asks
  the server for the file's PNG (`<file>.dds.png`, made on first ask and kept beside it:
  [viewer.py](../../tools/viewer/viewer.py)) where the GPU lacks the extension. `?texfallback=s3tc,srgb,rgtc` or
  `all` in the page's address treats those as missing, for the checks.
- [perf_probe.py](../../tools/viewer/perf_probe.py) now prints the shader programs, the textures and their memory on
  the GPU, and takes the page's address flags (`--flag`).
- Measured (this PC; the same map exported both ways):

  | Map | Export | Textures on disk | Texture memory on the GPU | Frame (shadow pass / none) | First open | Draw calls | Programs |
  | --- | --- | --- | --- | --- | --- | --- | --- |
  | URB_Bar, PNG | 21.2 s | 145.3 MB | 372.6 MB | 5.9 / 5.0 ms | 3.2 s | 1,220 | 28 |
  | URB_Bar, DDS | 10.3 s | 177.0 MB | 77.6 MB | 6.3 / 5.3 ms | 3.1 s | 1,220 | 28 |
  | CSmallScout_DirtRoad, PNG | 12.2 s | 92.8 MB | | | | | |
  | CSmallScout_DirtRoad, DDS | 6.6 s | 87.5 MB | | | | | |

  Export about twice as fast, texture memory about a fifth, the cache within a quarter either way, frames the same
  within the probe's noise.
- Checked: [test_texture_dds.py](../../tools/viewer/tests/test_texture_dds.py) (a 2048 by 2048 DXT1 texture written
  with 12 levels and the right length, non-square DXT5 and BC5, a broken chain of mips cut where it breaks, other
  formats and asked-for pictures as PNG, the server's PNG of a DDS), [texture_file_test.mjs](../../tools/viewer/tests/texture_file_test.mjs);
  in Edge, the Bar drawn from DDS and with `texfallback=all` (from the PNGs) at the three likeness cameras: mean
  differences of 0.5 to 0.6 (CIELAB), the game's own mips against the GPU's.
- Known gaps: PNGs of DDS files are made only on demand, so a GPU without S3TC waits for each on first open.

### One DXT1 decoder: the lightmaps' top mips are read by dxt1.py (editor refactor, stage B3)

[lightmap_textures](../../tools/bake/lightmap_textures.py) decoded a lightmap's top mip, the original bake every relight
reads the light before the edit from, through Pillow's DDS decoder, while the relight's encoder and its tests use
[dxt1.py](../../tools/bake/dxt1.py)'s (review finding 52: two decoders). `top_mip_rgb` and `top_mip_rect` now decode
with `dxt1.decode_image` and `dxt1.decode_region`. Pillow's decoder rounds a block's two in-between palette colours
down to whole 255ths; dxt1.py keeps them exact. Over every DXT1 lightmap of URB_Bar (180) and TempleShip (316), 15.4%
and 14.1% of the texel channels decode a third or two thirds of a 255th higher than before, the rest the same.

That changes what Builds make:
- **Baked Builds:** the relight's pieces start from the new decoding. Two real baked Builds with the code before and
  after: the Bar's pieces, 671 of its 673 relit pieces' lightmap images changed, 3,208,034 of 9,605,144 texels moved
  (3,127,280 by one 255th, 76,630 by two, 3,507 by three, 617 by four to six); the Bar's made pieces, 350 of 351
  changed, 1,816,217 of 5,327,672 texels moved (1,781,306 by one, 34,187 by two, 724 by three or four). The shadow
  maps (11 and 62 images) are the same. The variant map, its relit texture cache and the relight's record follow.
- **Quick Builds with made walls:** a made wall's even light (`frac_walls.even_light`, the texel of the nearest lit
  piece whose light is nearest that piece's median) is taken from the new decoding, so it is often another texel of
  the same piece, its light within 0.0065 (a box at every 25th actor of the Bar: 36 of 62 another texel, none another
  piece). Of the ten Builds (`build_outputs.py`), the four with made walls (the Bar's made pieces, its wall groups, its
  flags, the police station) make another map.
- **The relight's piece cache:** its key hashes the code of the files the images depend on (`TOOL_FILES`, which hold
  lightmap_textures.py and dxt1.py), so it is raised by this change: a project's next baked Build relights its kept
  pieces once.

Checked: [test_dxt1.py](../../tools/bake/tests/test_dxt1.py) gains a test that the lightmap reader decodes whole and by
rectangle exactly as dxt1.py does (it fails on the code before); the bake tests of DXT1, the relight, room matching
and the lightmap reader; the bake suite (695 tests, 1 skipped: XCOM_TRANSPLANT_RING; its one failure, the piece
cache key's test missing native_fields, came from the LOD reader before its key fix, and passes with it); the ten
Builds and the two real baked Builds, compared as above.

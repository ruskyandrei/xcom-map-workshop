### Export 44: each piece's baked light as the game stores it

Stage B1 of the game-likeness plan. Each of the map's own lightmapped pieces, and its streamed levels', carries its
baked light in the export:

- `lightmap`: its two DXT1 atlases (the colour, and the three direction values), each exported once as stored (a DDS
  file read through sRGB). With them come the slots' scales, the piece's rectangle of the atlas (UV scale and bias) and
  the mesh's lightmap UV channel.
- `sunShadow`: its shadow map of the map's dominant light (an 8-bit distance field), with its own UV scale and bias.

A piece of another map (the library's) carries neither: it is lit live where it is put. The library's piece version
is unchanged.

- Where: [baked_light.py](../../tools/viewer/baked_light.py) (new: `lightmap`, `sun_shadow`, `dominant_guid`), and
  [export.py](../../tools/viewer/export.py) (`Exporter.baked`, the `lightmaps` option; `EXPORT_VERSION` 44). The form
  is in [research/editor-contracts.md](../../research/editor-contracts.md) section 11.
- Checked: [test_baked_light.py](../../tools/viewer/tests/test_baked_light.py) on URB_Bar of the install. URB_Bar's
  export 44 has 1,039 of its 1,078 pieces lightmapped and 708 with a shadow map of the moon, in 180 lightmap atlases and
  53 shadow map atlases. It takes 14.2 s to make and 20 MB more than export 43.

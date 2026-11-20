### Export 37: what nothing read is no longer written, and each mission says its kind

Review findings 63 (written into every export and read by nothing; the piece study) and 55 (the council mission
kind). One version bump, so every map is exported again once, on its first open
([export.py](../../tools/viewer/export.py) `EXPORT_VERSION` 37).

**No longer written** (each searched for across the repository first: the page, the server, the compiler, the tests,
the browser checks and `take_shots.py`):
- the map's own `content` (every level actor and Kismet record). A streamed or previewed layer still reads its own,
  for the stream's count of rebuild volumes and a preview's `inheritedPatches`;
- `effectsMetadata`;
- a material's `render.compiledTextures` (the compiled shader's textures are still read for the colour, and the
  diagnostic still names them);
- `scenes.json` (previews open by address, `?scene=preview-<n>.json`).

**No longer worked out:** a streamed package's buildings, van buildings, playable bounds, tile grid and tactical data,
which `stream_layers` dropped (it keeps the stream's pieces, lights, effects and level records).

**The piece study is gone:** the `sample` scope and its three URB_Bar actor names; `viewer.py export --scope` takes
`map` only ([viewer.py](../../tools/viewer/viewer.py)). An earlier export's study is still read by the cache's pruning,
but [catalogue.py](../../tools/viewer/catalogue.py) no longer opens one, not even as an exact generation.
`Exporter.effects` takes no scope.

**Each mission says its kind** (`missions[].kind`, `missions.kind_key`: `Special/Bomb` for a council bomb...).
[missions.py](../../tools/viewer/missions.py) `kind_of_export` and the page's
[missions.js](../../tools/viewer/web/missions.js) `kindKey` read it, and fall back to the label for an older export,
so rewording a council label no longer turns its missions into plain special ones.

**[audit_clear.py](../../tools/upk/audit_clear.py)**, the clear survey, which read `content` from the export, reads
the level's records from the package instead (`level_content`; on URB_Bar the same 1,557 records the export had).

Measured (exported into a scratch cache before and after; compact `scene.json`):

| Map | Export 36 | Export 37 | Less |
| --- | --- | --- | --- |
| URB_Bar | 3,779,847 bytes | 3,507,314 bytes | 272,533 (7.2%) |
| TempleShip, the largest in the cache | 8,712,902 bytes | 8,031,251 bytes | 681,651 (7.8%) |

Both scenes are otherwise the same, key for key, once the dropped fields, the new `kind`, the version and the
package's path are set aside. The export took as long (22 and 17 seconds).

Checked:
- the viewer tests that read the export (`test_streams`, `test_material_rules`, `test_effects_metadata`,
  `test_damaged_inputs`, `test_catalogue`, `test_prune`, `test_composition`, `test_precache`, `test_play`), now
  checking the compiled shader's colour by the material's texture and diagnostic, a layer's guarded level records, each
  mission's kind and the refused piece study;
- `missions_test.mjs`;
- the export 37 Bar on a test server: `browser_smoke.py --only zoom,spawns,effects` passed with no errors.

Known gap: `browser_smoke.py`'s full run still fetches `scenes.json` to list a map's previews (the browser checks'
owner changes that). The contracts' and the viewer README's mentions are updated.

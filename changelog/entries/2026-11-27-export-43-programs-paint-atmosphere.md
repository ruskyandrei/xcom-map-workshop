### Export 43: materials' programs, painted colours, textures as stored, and the map's atmosphere

Stages A-S3 and C1 of the game-likeness plan, released with A-S3b in one export version (43) and one piece version
(13), so maps and other maps' pieces export again once.

- **Materials' programs** ([material_programs.py](../../tools/viewer/material_programs.py), called by
  [export.py](../../tools/viewer/export.py)'s `Exporter.material`): each material's shader map found by the
  survey's rule (moved here; [audit_shaders.py](../../tools/upk/audit_shaders.py) takes it from here), its slice
  made with the material's values, and every texture the program samples exported; the record gains `program`
  (research/editor-contracts.md section 9) and keeps every field it had. A material whose colour doesn't slice is
  drawn as before, with the reason in the export's diagnostics; the guesses' own warnings (layered materials,
  colours by kind, alien energy) are said only for those. Programs are made only where the exporter is told to
  (`Exporter.programs`: the map export and the library's pieces), so the bake's albedo, which resolves materials
  through the exporter, never opens the shader cache.
- **The shader cache kept**: [shader_cache.py](../../tools/upk/shader_cache.py)'s `open_cache(keep=)` keeps the
  decompressed package in the editor's cache folder, named by the file's SHA-256 (one copy for every install that
  has the same file): opening it then takes 0.2 s in place of 4.6 s, in every export process.
- **Painted colours**: a placed piece whose component carries its own vertex colours (LOD 0's, painted in the
  level editor) gets `paint`, a file of RGBA bytes in its mesh's vertex order (`material_programs.painted_colours`).
- **Textures as stored**: A-S3b's DDS files switched on.
- **The atmosphere** ([atmosphere.py](../../tools/viewer/atmosphere.py), C1): `scene.json`'s `atmosphere` gives the
  WorldInfo's height fog and post-process settings (grade, bloom, depth of field, fog-of-war colours) with every
  member filled, the map's saved ones over the class default object's over the struct's own, which
  [atmosphere_defaults.json](../../tools/viewer/atmosphere_defaults.json) holds (made from the script packages:
  `python -B tools/viewer/atmosphere.py defaults <CookedPCConsole> --write`), the members the map itself saves, the
  environment colour, and each PostProcessVolume's box, priority and saved settings
  ([editor-contracts.md](../../research/editor-contracts.md) section 10).
- The versions: `EXPORT_VERSION` 43 with its line; `library.PIECE_VERSION` 13
  ([library.py](../../tools/viewer/library.py)), its fingerprints written again
  ([piece_fingerprints.json](../../tools/viewer/tests/piece_fingerprints.json)). Making them showed the slice named
  its registers and reported its reasons in the order of a set, which Python's string hashing changes from process
  to process: both now follow the instructions' order.
- What else reads a material record was gone over and keeps reading the fields it read: the area-light matcher
  (`area_light_bindings.py`, the emissive parameters), the look catalogue's tools and the look picker (`diffuse`,
  `vectors`), effects_draw.py's mesh emitters (their textures by `exporter.texture`), and the bake's albedo
  (`diffuse`, through its own resolver).
- Measured on URB_Bar: an export takes 13.2 s (21.2 s with PNG textures and no programs, 10.3 s with DDS and no
  programs); 193 of its 209 materials get a program; 214 placed pieces carry painted colours; 513 textures (482).
- Checked: [test_material_programs.py](../../tools/viewer/tests/test_material_programs.py) (the matching rule, no
  cache meaning no programs, an unlit material's colour being its glow, the kept cache reading the same; an export
  of COverseer_TheBarrens: RocksRiver_VertPaint's program samples Dirt, Grass and Leaves, never Rock, every texture
  exported, its painted pieces' colour files four bytes a vertex), [test_atmosphere.py](../../tools/viewer/tests/test_atmosphere.py)
  (a made-up WorldInfo, the defaults file against the script packages, the Bar's grade and Dirt Road's four fog
  members and its volume, as F-168 lists them), [test_albedo_kept.py](../../tools/bake/tests/test_albedo_kept.py)
  (four of the Bar's materials keep the albedo main gives them), the program case file both sides read
  ([material_program_cases.json](../../tools/viewer/tests/material_program_cases.json), made by
  [material_program_cases.py](../../tools/viewer/tests/material_program_cases.py); `test_shader_slice.py` holds
  shader_eval and the slice to it); the viewer, upk, repo and node suites.
- Known gaps: nothing draws the programs, the paint or the atmosphere yet (A-S4, C2, C3); the look picker's and Add
  panel's pictures are drawn again with A-S4, when what they show changes.

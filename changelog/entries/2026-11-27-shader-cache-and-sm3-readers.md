### The game's compiled shaders read: the RefShaderCache index and an SM3 decoder

The first stage of the game-likeness plan's track A (A-S1): two readers in `tools/upk` that the later stages build
on to draw materials as the game's shaders draw them.

- [shader_cache.py](../../tools/upk/shader_cache.py) indexes the install's `RefShaderCache-PC-D3D-SM3.upk`: its
  68,841 shaders by ID (type, bytecode) and its 4,801 material shader maps by base material and switch values; a
  map's shaders by vertex factory and shader type, the material's ID and name, and its uniform expressions in their
  six lists, each a small tree (parameters, constants, time, sines, folded maths, appends, the game's own colour
  slots, flip books). Every read is bounded by the record's offsets: an unreadable map is refused alone.
- [sm3.py](../../tools/upk/sm3.py) decodes SM2/SM3 bytecode (the constant table, declarations, `def` constants,
  instructions with masks, swizzles, modifiers, predicates and relative addressing) and lists it back in the form
  Windows' D3DCompiler_47 disassembles it. The DLL is only the tests' oracle (`oracle`); nothing that ships needs it.
- Layout facts found while writing them, beyond F-168's: a map's body starts with the material's own shader list
  (empty in all 4,801), then the mesh shader maps (shader lists each closed by their vertex factory); a shader
  reference whose type is `None` is a type the cooker left without a shader; `XComVectorParameter` is one byte (the
  colour slot) and `FlipBookTextureParameter` a texture index, both in the vector list.
- Where it is described: [ARCHITECTURE.md](../../ARCHITECTURE.md) section 2's new row; the tests' install file can be
  pointed elsewhere by `XCOM_SHADER_CACHE_UPK` ([run_tests.py](../../tools/run_tests.py)).
- Checked: [test_sm3.py](../../tools/upk/tests/test_sm3.py) and
  [test_shader_cache.py](../../tools/upk/tests/test_shader_cache.py) (a hand-made shader decoded and listed back and
  agreeing with the DLL, bad bytes refused, a made-up cache of two shaders and one map, a damaged one refused, an
  unknown expression spoiling only its map; on the install the counts, every map's uniforms read, ENV_ForestGround's
  three maps with 35 shaders each and their uniform names, and a fixed sample of 500 shaders listed exactly as the
  DLL lists them). Outside the suite all 68,841 shaders were listed and compared: every one equal.
- Known gaps: the package takes about 4.5 s to open, once a process; nothing is kept on disk yet (A-S3 decides from
  how often exports open it).

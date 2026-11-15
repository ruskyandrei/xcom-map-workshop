# EXP-15: cooked lighting data and dynamic-lighting feasibility

Date: **6 November 2026**. Status: **read-only audit complete; A/B rendering fixes untested by this experiment**.
The [research report](../map-lighting-research.md) assesses rebaking and whole-map dynamic lighting separately.

## Inputs and method

Ran [audit_lighting.py](../../tools/upk/audit_lighting.py) against `URB_Bar.upk` and `TempleShip.upk` in
`<lab>\uncooker-input\CookedPCConsole`, with `Engine.upk` and `XComGame.upk` for explicit default-object values.
The Temple variant spec supplied four probe query points. Inputs and script are hashed in the
[evidence JSON](../evidence/lighting-audit-2026-11-06.json).

```powershell
python -B tools/upk/audit_lighting.py `
  <lab>\uncooker-input\CookedPCConsole\URB_Bar.upk `
  <lab>\uncooker-input\CookedPCConsole\TempleShip.upk `
  --points-spec tools/patch/examples/templeimproved.json `
  --defaults <lab>\uncooker-input\CookedPCConsole\Engine.upk `
             <lab>\uncooker-input\CookedPCConsole\XComGame.upk `
  --out research/evidence/lighting-audit-2026-11-06.json
```

`--points-spec` and `--defaults` are optional. The spec is a local editor-work artifact, not introduced by this
research. No UPK/TFC payload, decoded image, game executable or script bytecode is written into the repository.

## Measurements

| Measurement | Bar | Temple |
| --- | ---: | ---: |
| Placed static/fractured component records parsed | 968 | 1,707 |
| LOD-0 texture / vertex lightmaps | 930 / 0 | 1,651 / 4 |
| LOD-0 no lightmap / no LOD data | 13 / 25 | 11 / 41 |
| Components with LOD-0 shadow-map references | 627 | 272 |
| Lightmap / shadow texture exports | 180 / 54 | 316 / 27 |
| Volume sample count | 1,743 | 8,941 |
| Samples with nonzero encoded indirect RGB | 1,714 | 7,997 |
| Unique referenced meshes with decoded LOD-0 UVs | 256 | 161 |

- Every checked 2D lightmap's first two texture references are `NormalizedAverageColor` and
  `DirectionalMaxComponent` families, with a null third slot. The shader coefficient decoder is not established.
- All lightmap textures are DXT1, shadow textures G8. Cache ranges were validated. One high mip per texture class
  per map was decompressed and image-decoded in memory, with compressed/decompressed range hashes recorded.
- All sampled static-component native data was consumed. Fractured components retain an explicitly unparsed
  subclass tail. Mesh-swap lightmap records are read separately from normal LOD records.
- Most meshes have a saved lightmap coordinate index of 1 and at least two UV channels: 250 Bar, 156 Temple.
  The evidence records absent/out-of-range saved indices; those are not certified for baking.
- All four current Temple copy pivots have sample spheres geometrically covering them (32, 34, 27, 34). Nearest
  distances are approximately 76.78, 111.00, 121.21 and 82.71 units respectively. These are pivot queries, not the
  actual DLE bounds/interpolation or measured received illumination.
- Actual game defaults distinguish doors' SH-only synthesis from the default directional synthesis. Temple's
  sky overrides disable BSP/Static/Dynamic but omit CompositeDynamic; the game's base light default enables it.

## Validation boundary and a useful decoder correction

The level decoder recognizes a unique complete volume suffix ending at the exact export boundary, followed by
73 zero bytes representing the observed empty visibility/distance-field records. It does not parse the preceding
physics/native Level content and rejects nonempty/unknown suffixes.

The serialized fields occupy **33 bytes per sample**, even though the consulted C# declaration has a
`FixedSize(35)` annotation. Both maps' counts/boundaries and all finite position/radius/shadow fields validate with
33. Sample spacing is zero in both. Temple has 278 sample centers outside the stored volume bounds; requiring all
centers inside that box incorrectly rejects its otherwise consistent record. The audit records this rather than
imposing an unsupported invariant. A general-purpose volume writer is not implemented.

Radiance remains encoded BGRA bytes; no linear brightness or color inference is made from those bytes. All
properties labelled overrides exclude unresolved imported defaults. Raw field presence does not prove actual
runtime light influence. The current EXP-14 run-5 visual observations/settings tests remain separate evidence.

Inputs were rehashed after the audit; they were unchanged. The audit reported zero parsing errors for both maps.
No gameplay or visual-equivalence test was performed here. Findings register: F-55.

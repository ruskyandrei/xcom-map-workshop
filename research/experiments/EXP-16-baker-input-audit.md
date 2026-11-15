# EXP-16: standalone baker inputs, workload and light identifiers

Date: **6 November 2026**. Status: **read-only measurements complete; no bake or runtime test**.
See the baker design for the proposed system and implementation order.

## Method

[audit_baker_inputs.py](../../tools/upk/audit_baker_inputs.py) reuses the EXP-15 native component/texture readers
and the viewer's LOD-0 mesh decoder. It inspects the Bar/Temple cooked snapshots, records bounded metadata and
hashes inputs before/after. The [evidence JSON](../evidence/baker-input-audit-2026-11-06.json) contains no game payloads.

```powershell
python -B tools/upk/audit_baker_inputs.py `
  <lab>\uncooker-input\CookedPCConsole\URB_Bar.upk `
  <lab>\uncooker-input\CookedPCConsole\TempleShip.upk `
  --out research/evidence/baker-input-audit-2026-11-06.json
```

## Results

| Measurement | Bar | Temple |
| --- | ---: | ---: |
| Static/fractured component records | 968 | 1,707 |
| Those resolving a local mesh through current reader | 948 | 1,668 |
| Unique meshes | 256 | 161 |
| Unique LOD-0 triangles | 147,135 | 119,840 |
| LOD-0 instance triangle sum | 367,877 | 1,038,248 |
| LOD-0 texture-mapped receivers | 930 | 1,651 |
| Sum of mapped rectangle areas | 6,773,096 | 7,263,372 |
| Unique baked-light GUIDs, all matching `LightmapGuid` | 116 | 119 |
| Unique shadow GUIDs, all matching `LightGuid` | 2 | 1 |
| All 2D LOD records | 935 | 1,651 |
| Those with non-unit directional slot scale | 131 | 213 |
| Directional scale maximum | 5.8265089989 | 16 |

No inspected lightmap-contribution GUID matched `LightGuid`; no inspected shadow GUID matched `LightmapGuid`.
No contributing-light GUID was unresolved against the map's light components. This differentiates the two native
associations but is not a full description of the runtime's light selection rules.

Both bound lighting textures had identical dimensions for every LOD-0 pair inspected. Common rectangle dimensions
are 14×14, 30×30 and 62×62. The rectangle measure is the component UV scale multiplied by the largest available
texture mip dimensions. It does not establish actual triangle occupancy, unique nonoverlapping coverage or a
padding convention.

The audit also retains three Bar structural candidates without shadow-map references, all ordinary static actors
using `ConcreteWallUnderPass1`. They are **not** certified visible/playable test objects; choose a fixture after
checking its placement and material. Temple yielded none under that deliberately narrow selection rule.

## Limits

- Source triangle counts include hidden/auxiliary geometry and whole source fragment meshes; no final visibility
  or fragment mask is applied. Other geometry families and streamed maps are excluded.
- The 20 Bar and 39 Temple components without a resolved local mesh are not treated as empty scene geometry.
  A production extractor must diagnose/resolve them or explicitly exclude them with evidence.
- Rectangle areas omit padding, other LODs, shadow/probe work and streams, and overcount uncovered UV regions.
  The derived sampling-work examples in the design are arithmetic, not performance benchmarks.
- Non-unit scales demonstrate the need for range handling; they do not identify the directional basis or gamma.
- All lightmap textures omit the selected explicit SRGB/compression/streaming flags. Native defaults and shader
  sampling still need qualification; omission is not proof of either linear or sRGB decoding.

Zero audit errors were reported and package input hashes were unchanged. No scene was exported for baking, no
shader was decoded, no new textures/components were injected, and no game/UDK process was launched.

## Run 2: lightmap pair statistics (6 November, design review)

[lightmap_stats.py](../../tools/bake/lightmap_stats.py) summarises the three slot scales of every LOD-0 2D lightmap
record, then decodes the top mip of the three busiest atlas pairs per map and samples each receiver rectangle in them
(2 texels in from the edge; texels whose `DirectionalMaxComponent` is below 0.02 in every channel skipped).
[Metadata](../evidence/lightmap-pair-stats-2026-11-06.json); no texture data exported.

```powershell
python -B tools/bake/lightmap_stats.py `
  <lab>\uncooker-input\CookedPCConsole\URB_Bar.upk `
  <lab>\uncooker-input\CookedPCConsole\TempleShip.upk `
  --out research/evidence/lightmap-pair-stats-2026-11-06.json
```

| Measurement | Bar | Temple |
| --- | --- | --- |
| Texels sampled (3 pairs) | 932,711 | 1,041,108 |
| Slot 0 scale | (1, 1, 1) in all 930 | (1, 1, 1) in all 1,651 |
| Slot 1 scale | 129 distinct, max (5.83, 4.50, 4.26) | 201 distinct, max (16, 16, 16) |
| Slot-1 scales differing between channels | 128 | 199 |
| Slot 2 scale (null texture) | (2, 2, 2) everywhere | (2, 2, 2) everywhere |
| `NormalizedAverageColor` max channel, percentiles 1/10/50 | 0.61 / 0.85 / 1.0 | 0.68 / 0.81 / 1.0 |
| Share of texels with max channel at least 0.94 | 80.7% | 69.6% |
| `DirectionalMaxComponent` channel correlation | 0.70–0.82 | 0.69–0.73 |
| Its median (max − min) / max per texel | 0.41 | 0.50 |

Reading: the colour texture looks normalised to a largest channel of 1; the directional texture's three channels
vary separately and carry their own scales, consistent with one intensity per basis direction. The
design (section 2) states the resulting hypothesis and what remains open.

Limits: three pairs per map, top mip only, DXT1-decoded values (block error included), no gutter detection beyond the
inset, no link yet between channels and surface orientation or light positions. Input hashes unchanged.

Findings register: F-55, baker follow-up.

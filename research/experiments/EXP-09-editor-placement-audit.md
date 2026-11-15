# EXP-09: placement audit for the first editor

Date: 5 November 2026. Baseline: `75a8c4e`.

**Scope:** read-only source-map and current-tool inspection, using existing game-run findings. No new game run,
package build or deployment was performed. This informs the first-editor plan.

## Questions

Must every piece's pivot be on the grid? Are arbitrary rotations impossible in game, or currently unsupported by
our tools? Which preparation steps need extending before the editor can produce playable variants?

## Inputs and method

Original EW v845/licensee-64 packages in `<lab>\uncooker-input\CookedPCConsole`, inspected through the checked
v11 exports in `<lab>\viewer-cache`:

| Map | Source package SHA-256 | Generation |
| --- | --- | --- |
| URB_Bar | `a3ae5a73457c3c3f3e490fde9e1ad935f667c4843792fc8d140abc66878e09b5` | `a3ae5a73457c3c3f-v11-map` |
| TempleShip | `029bedcaea20c9a8d1d577fd9bd7dc733ce3976fb33b0b3f716f640caeaf4d2e` | `029bedcaea20c9a8-v11-map` |

Count unique source actor paths, excluding source-hidden components and suppressed environment geometry, before
the viewer's optional interior filtering. This includes scenery/backdrop, not just known gameplay pieces.

- Off-corner: an XY pivot lies more than one game unit from the closest 96-unit tile edge in either axis, measured
  against that map's exported grid origin. Tile-centred pivots also qualify as off-corner; this is intentional.
- Non-cardinal yaw: its distance from a multiple of 16,384 native rotator units is greater than 16 units
  (approximately 0.088 degrees). Pitch/roll is measured modulo 65,536 with the same tolerance around zero.
- These are properties of authored source placements, not evidence that every patch transformation preserves
  navigation, cover, destruction or interactions.

## Results

| Map | Visible actors | XY pivot off a tile corner | Non-cardinal yaw | Nonzero pitch or roll |
| --- | ---: | ---: | ---: | ---: |
| URB_Bar | 966 | 822 | 169 | 28 |
| TempleShip | 1,667 | 1,121 | 93 | 234 |

Examples: Bar's `KAsset_1` has yaw about 49.92 degrees; `XComDestructibleActor_204` has roll about -5.62 degrees.
Temple's `XComLevelActor_115` has yaw 45 degrees; `XComLevelActor_1084` has pitch 45 and roll -45 degrees.

The source data rejects a universal rule that actor pivots must sit on tile corners or that all rotations are
cardinal. It does not establish the useful collision footprint or gameplay suitability of those examples.

Existing F-41 game evidence explains the practical alignment requirement: the compact car's pivot is offset from
its body centre, and an off-grid body can intrude into adjacent tiles and prevent approaching the ends for cover.
The spawner uses body bounds, odd/even footprint parity and a near-cardinal eligibility test; it does not just
round the actor origin. Existing F-39 evidence requires actual supported floor tiles at a ladder's endpoints.

## Current tool restrictions and gaps

| Source | Observation | Consequence |
| --- | --- | --- |
| [patchtool.ps1](../../tools/patch/patchtool.ps1), `Read-Spec` copy branch | Copy yaw is explicitly rejected unless divisible by 90. Most placement T3D writes yaw with pitch/roll zero. | Tool policy, not a universal native transform restriction; full-axis editing needs backend changes. |
| [XComMapEdCopier.CopyOne](../../unrealscript/XComMapEd/Classes/XComMapEdCopier.uc) | Rotates source offsets by yaw and adds yaw to the original rotator. | Extend real 3D transform composition, not just validation. |
| [seed_map.py](../../tools/upk/seed_map.py), `turn` | Rounds yaw to a quarter turn for coverage calculations. | Free-angle support must update seeding bounds too. |
| [world_links.py](../../tools/upk/world_links.py), `transform`/`tile_mover` | Rejects non-cardinal rotation and mappings that do not preserve tile centres. | Interaction links need verified endpoint reconstruction/regeneration, not blind rounding. |
| [bake_actor.py](../../tools/upk/bake_actor.py) | Rewrites existing fixed-size properties; cannot insert an absent Rotation property. | Extending identity-preserving edits requires a checked writer or alternate recipe. |
| [XComMapEdSpawner.SnapToTiles](../../unrealscript/XComMapEd/Classes/XComMapEdSpawner.uc) | Bounds-based car snap is eligible within about 10 degrees of a cardinal orientation. | Treat that range as the current snapping algorithm's scope, not a ban on other rotations. |

The first editor should support free XYZ authoring and optional recipe-aware snapping, with runtime experiments
qualifying each placement recipe. A successful preview is insufficient. See F-48.

## Build integration issue found

`Set-ShipConfig` currently replaces `StreamingMaps[1]` when registering a renamed map. The recorded Temple Ship
configuration lists `TempleShip_Stream`, `CIN_TP12A_ArriveTempleShip`, then `patch_hide_randomized_objects`.
Using that rule on this configuration would replace the arrival cinematic with the edit patch. No deployment was
attempted. Fix stream selection/ownership and qualify a no-op Temple variant before edited final-mission use (T-08).

Also, base seeding/baking and config changes currently run inside `Step-Deploy`, after copying the patch. The editor
needs staged preparation plus an explicit install transaction, so a failed build cannot partially install a revision.
There is no standalone complete clean/uninstall step; `unseed` retains map and landing-zone records.

## Follow-up

Run the transform, footprint, interaction and map-integration matrix in the new plan. Record actual runtime results
here or in subsequent experiment notes, and update F-48/T-08 only when the corresponding checks have been performed.

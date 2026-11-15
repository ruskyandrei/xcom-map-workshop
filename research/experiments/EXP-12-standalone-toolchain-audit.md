# EXP-12: standalone toolchain feasibility audit

Date: **6 November 2026**. Status: **read-only structural audit complete; replacement builder not implemented or
tested in game**. See the [assessment and implementation recommendation](../dependency-replacement-feasibility.md).

## Question

Can the ordinary map-editing workflow avoid installed UDK/Uncooker/package utilities, and what is the smallest
package-writing problem that would make that possible?

## Method

- Inspected the current workspace's viewer, editor compiler, patchtool, Python package/LZO readers and writers,
  helper UnrealScript, setup instructions and EXP-01/02/11 records. Existing uncommitted work was included as found.
- Read the existing `patch_bar` and `patch_urb_bar_exp11static_b7f3` source/cooked pairs under
  `<lab>\author\UDK-2011-09\UDKGame`, using `tools/viewer/package.py` and its underlying readers.
- Recorded file hashes, version markers, class counts, compiled class paths and the placed helper properties.
  For array properties, compared count and serialized size, not every element. Compared decoded scalar values.
- Reviewed current primary-source documentation and repositories linked in the assessment.
- Wrote only this research record, its JSON evidence, the assessment, and ledger/findings entries. Did not launch
  UDK or XCOM, change a package, deploy anything, or restart a viewer server.

The [audit JSON](../evidence/dependency-replacement-audit-2026-11-06.json) includes input SHA-256 values and hashes of
the relevant workspace implementations. It contains metadata rather than copied game packages or bytecode.

## Results

| Package | Stage | Bytes | Names | Imports | Exports |
| --- | --- | ---: | ---: | ---: | ---: |
| `patch_bar` | Source | 136,945 | 201 | 55 | 155 |
| `patch_bar` | Cooked | 67,907 | 320 | 142 | 251 |
| `patch_urb_bar_exp11static_b7f3` | Source | 11,485 | 103 | 26 | 15 |
| `patch_urb_bar_exp11static_b7f3` | Cooked | 135,761 | 782 | 410 | 815 |

All four files are version 845/licensee 0, engine 8916. Cooked files use cooker 135 and LZO flags 2; source files
have cooker/compression zero. EXP-01, rather than this audit, establishes the shipped patch comparison.

EXP-11's cooked patch has 14 `Class` exports, 107 `Function` exports and four placed helper actors:

| Helper | Serialized bytes | Bytes after tagged properties |
| --- | ---: | ---: |
| `XComMapEdCopier_900` | 1,245 | 0 |
| `XComMapEdHider_901` | 336 | 0 |
| `XComMapEdIntro_903` | 146 | 0 |
| `XComMapEdTileSeeds_902` | 516 | 0 |

The helpers total 2,243 bytes. The source/cooked property names, kinds, array counts/sizes and scalar values match.
Cooking changes the helper class references from negative import indices to positive embedded-export indices.
The patch contains no `StaticMesh`, `SkeletalMesh`, `FracturedStaticMesh` or base `Material` exports. It does contain
mesh components and a `Texture2D`, `MapTemplates.lut.LUT_Daytime`; it is not a pure script-only distribution artifact.

## Interpretation

Reusing compiled code and serializing a few instance settings is a narrower first goal than recreating UDK. Our
existing Python handles supported cooked map reading, fixed-size actor edits and tile seeding. A general growing
property writer, dependency-aware relocation and in-game validation remain necessary.

No native tail on these **instances** says nothing about the embedded classes/functions, level, components,
textures or other objects. Those still contain specialized data and references. Keeping their indices stable is
a design proposal, not a proof that arbitrary file relocation is safe.

The available EXP-11 build was marked deployed but not run in game at the time of this audit. Its existence proves
UDK serialization, not current static-edit gameplay parity. Template certification must start from a qualified
baseline. This audit does not replace any EXP-11 pass criterion.

## Recheck

Use `python -B tools/upk/upkinfo.py <path> summary` on each source/cooked path recorded in the JSON for the header
and export-class census. For helper records, load `Package(path)`, select paths beginning
`TheWorld.PersistentLevel.XComMapEd`, and call `properties(index)`. Subtract the returned property-end position
from `export['off'] + export['size']` for the native-tail size. Decode the initial signed 32-bit count of raw
`ArrayProperty` values. Rehash inputs before comparing with this record.

Findings register: **T-10**, open pending a standalone build and runtime qualification.

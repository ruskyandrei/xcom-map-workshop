# Replacing the external map toolchain

Research date: **6 November 2026**. Target: this repository's Enemy Within + Long War Rebalance workflow.

**Assessment: a standalone builder for supported edits to existing maps is feasible enough to prototype.** Most
reading and several writing operations already use our own code. The best first replacement for UDK is a writer
that changes the settings in a reusable cooked patch. A complete replacement for UDK's compiler, asset cooker and
map-building facilities is a much larger research project.

This is a feasibility assessment, not a delivered replacement. The [structural audit](experiments/EXP-12-standalone-toolchain-audit.md)
reads existing source/cooked packages; it does not establish that a newly written package loads in the game.

## What we actually depend on

| Dependency or operation | Role today | Replacement assessment |
| --- | --- | --- |
| Reference UDK + XCOM Uncooker + .NET 8 | Earlier reference inspection in EXP-02 | Already avoidable for the viewer's supported maps. Our viewer reads cooked game packages directly. Full UDK asset/Kismet inspection is broader than that support. |
| UDK 2011-09 editor + XComGame stubs | Imports generated T3D and saves a patch map | Replaceable for a defined set of patch actors and properties. Requires a package writer and runtime qualification. |
| `UDK.com CookPackages -platform=PC` | Resolves dependencies, embeds helper code/content and writes the cooked patch | Bypass for supported edits by preserving a cooked template and rewriting its data. General asset cooking remains a separate problem. |
| `UDK.com make` | Compiles changed XComMapEd UnrealScript | Avoid during map builds by distributing a versioned, precompiled helper/template. Updating that helper still needs UDK initially. |
| UPKUtils / XComLZO | Useful earlier research/reference utilities | No executable calls found in the current viewer/editor/patch build path. Our Python already reads LZO blocks and rewrites supported package regions. |
| UModel / UE Explorer | Potential inspection tools | Not required by the active path inspected. Our viewer handles supported mesh/texture extraction. They remain useful independent references. |
| PowerShell 7, hidden-desktop launcher, C# compiler | Drives the UDK editor, cooking and deployment | Remove the editor automation with the new backend; port the remaining configuration/copy/backup operations to the application's backend. |
| Python, Pillow, three.js | Current viewer/exporter/server | Bundle these with the application; rewriting them adds little value. No separate user installation need remain. |
| EW/LWR files and the game runtime | Assets, base world data, gameplay and validation | Still required. Read assets from the user's matching installation. |

Evidence: [patchtool](../tools/patch/patchtool.ps1), [viewer documentation](../tools/viewer/README.md),
[package reader](../tools/viewer/package.py), [texture reader](../tools/viewer/texture.py),
[requirements](../tools/viewer/requirements.txt), [renderer setup](../tools/viewer/setup_vendor.py).
The folder named `uncooker-input` in viewer examples contains **cooked input files**, not the Uncooker's output.

The general reader is not complete: it accepts v845/licensee 0 or 64; the supported viewer scenes have been
checked on Bar and Temple Ship. Outer-LZO startup/core packages are handled separately for header inspection in
`audit_install.py`, not universally by `Package`. LZX texture bulk data is explicitly unsupported. Broader map
support needs validation, bounds checks and additional serializers; removing an installer does not add coverage.

## Why bypassing full uncooking is the better fit

Uncooking reconstructs editor packages, including object references and approximations of missing editor data.
It cannot simply restore information discarded during cooking. The XCOM Uncooker documents stripped world data
and incomplete material reconstruction. Our editor can instead inspect runtime geometry, textures and placements
directly, preserving the original cooked assets for gameplay. [XCOM Uncooker](https://github.com/chrishayesmu/XCOM-Uncooker#readme)

Our direct readers already export static/fractured geometry, skeletal reference poses, material approximations,
texture-cache payloads and placed actors. They do not reproduce every material, animation, particle effect or
Kismet editor. Extend those readers only as the supported editing features require them.

## The strongest evidence: the current static-edit patch

The fresh audit of `patch_urb_bar_exp11static_b7f3` found:

| Measurement | Source map | Cooked patch |
| --- | ---: | ---: |
| Bytes on disk | 11,485 | 135,761 |
| Exports | 15 | 815 |
| Names / imports | 103 / 26 | 782 / 410 |
| Placed XComMapEd helpers | 4 | 4 |

The cooked file embeds **14 classes and 107 functions**. Its four placed helpers are the copier, hider, intro and
tile rebuilder, totaling **2,243 serialized bytes**. Each ends at its tagged-property terminator, with **no native
tail**. Their property shapes, array counts/sizes and scalar values match between source and cook; this check did
not compare every array element. Class references change from imports to embedded exports during cooking.

That makes a small, data-driven patch generator plausible: retain the compiled code, change the instance settings.
It does **not** mean that cooking is compression alone. The package grows because UDK incorporates dependencies.
Epic also describes cooking as resource processing and dependency packaging. [Epic's cooking documentation](https://docs.unrealengine.com/udk/Three/ContentCooking.html)

Earlier [EXP-01](experiments/EXP-01-authoring-toolchain.md) reproduced the shipped `patch_bar` PC cook apart from
one embedded package GUID. Existing [actor edits](../tools/upk/bake_actor.py) and
[tile seeding](../tools/upk/seed_tiles.py) already rewrite cooked data without UDK. Their current restrictions matter:
actor edits preserve property sizes and cannot add a missing rotation; the tile writer has container/chunk
constraints. Neither is a general package writer.

## Recommended implementation

1. **Keep the current project format and compiler.** Add a second build backend after the patch specification.
   Keep the UDK backend as a comparison tool while qualifying the new one.
2. **Create a small, versioned cooked template** containing the helper code and required actors. Initially build
   this with UDK, then reuse it for many layouts. The current EXP-11 file is useful evidence, but is not yet a
   certified distribution template: its gameplay check is still pending, and it includes `MapTemplates.lut.LUT_Daytime`.
3. **Write supported helper properties directly:** source actor names, target locations and full rotations, hide
   lists, intro map name and tile-rebuild boxes. Keep existing name/import/export indices stable wherever possible;
   append new entries rather than renumber compiled code. Start with a fixed helper actor set.
4. **Handle variable-size data properly.** Growing arrays and strings requires export size/offset updates and a
   deliberate layout strategy. Preserve flags, object identity, archetypes, level actor order, dependencies and
   generation/NetIndex information. Audit any bulk payload or native absolute offset before moving it. Rebuild
   compressed chunks and validate the final package. Do not treat all integers as interchangeable references.
5. **Reuse the existing base-map preparation:** copy the correct base map, seed tiles, perform supported baked
   actor/link changes and write the variant's configuration records. Preserve the original streams, landing zones
   and source-hash checks. Copy before hide and rebuild before mission placement must remain true at runtime.
6. **Package the application and libraries together.** Ship local renderer files and a private Python runtime with
   Pillow, and remove runtime downloads and separate PowerShell requirements from this backend. Python supports
   this deployment model. [Python embedding documentation](https://docs.python.org/3/using/windows.html#the-embeddable-package)

An alternative is a reusable helper that reads per-map INI configuration, further reducing package writing. This
would first require changing and compiling the helper: the current copier/hider expose `var()` instance settings,
not a ready-made config loader. Map selection, config loading, array limits, naming collisions and save/reload
behavior would need their own experiment. Do not assume XCOM can read our JSON project at runtime.

**Dependency boundary:** this approach can remove UDK from a map creator's machine and from ordinary layout builds.
It retains a UDK-built template as an input. Rebuilding every helper from source with no UDK anywhere requires
an additional UnrealScript compiler and linker effort.

## What needs separate research

| Capability | Main unresolved work | Relative effort / confidence |
| --- | --- | --- |
| Supported static copies, moves and hides using resident assets | Template writer, relocation, identity and in-game parity | Moderate; strongest candidate |
| Doors, ladders, destructibles and fractured pieces | Per-family native state, collision, destruction, links and persistence | High; existing runtime findings still apply |
| Assets borrowed from another map | Seekfree dependency closure and material/texture/shader availability | High; an object path alone is insufficient |
| New meshes with existing game materials | Mesh format, collision/physics data, bounds, LODs and runtime validation | Separate substantial project |
| New materials and fully rebuilt lighting | EW shader compatibility, caches and lightmap generation/association | Very high; no complete solution established here |
| Completely new terrain, grid bounds and navigation | Firaxis world-data generation plus gameplay integration | Very high; existing tile seeding/rebuilds are not a complete offline baker |
| Arbitrary new UnrealScript without UDK | Frontend, bytecode, class/default-object serialization, native bindings and linking | High; avoid in the first milestone |

These are engineering judgments, not schedule commitments. Known findings survive a backend replacement:
F-24's baked shadows, F-31's building cutaway, F-46's stale floor tiles and F-47's missing upper-floor tiles are not
fixed by writing the same patch differently. EXP-11's full-axis placement still needs its recorded game test.
The Uncooker's material/runtime-compilation limitations are relevant to custom content, not evidence against our
already demonstrated streamed-patch approach. [Upstream explanation](https://github.com/chrishayesmu/XCOM-Uncooker#faqs)

## Existing code worth studying

| Project | Relevant value | Important boundary |
| --- | --- | --- |
| [UPKUtils](https://github.com/wghost/UPKUtils) | XCOM-oriented cooked package editing and texture tooling | GPL-2.0 project; not a full map cooker. Our active path already covers several of its jobs. |
| [UE Viewer](https://github.com/gildor2/UEViewer) | Mature asset serialization/export examples | Exporter, not a map builder. The repository's current [license](https://github.com/gildor2/UEViewer/blob/master/LICENSE.txt) is MIT, despite older website text. |
| [UELib](https://github.com/EliotVU/Unreal-Library) | Package and UnrealScript analysis; MIT | Primarily reading/decompilation; not an established EW build pipeline. |
| [Legendary Explorer](https://github.com/ME3Tweaks/LegendaryExplorer) | Independent UE3 package editing and an [UnrealScript compiler](https://github.com/ME3Tweaks/LegendaryExplorer/blob/master/LegendaryExplorer/LegendaryExplorerCore/UnrealScript/UnrealScriptCompiler.cs) | Mass Effect toolset, GPL-3.0. Its [UDK writer](https://github.com/ME3Tweaks/LegendaryExplorer/blob/master/LegendaryExplorer/LegendaryExplorerCore/Packages/UDKPackage.cs) permits saving version 868; our files are 845. Requires adaptation, not direct substitution. |
| [XCOM Uncooker](https://github.com/chrishayesmu/XCOM-Uncooker) | Detailed Firaxis-aware serializers and reconstruction research | Different output goal. No top-level license was visible in the reviewed tree; do not assume source availability is a reuse grant. |

Choose any reused code with its actual license and notices. A distributable cooked template also needs an inventory
of what it embeds; the current template's LUT illustrates why compiling our scripts does not imply every embedded
object is ours. Keep game-derived files local, as the repository already requires.

## First proof and acceptance gates

The next useful experiment is a **UDK-free build of one supported static-edit patch**, tested against a known-good
UDK build. Use the existing UDK only to produce the baseline/template.

1. Establish the baseline in game; then make a no-change template round trip and a single placement edit.
2. Test a larger and smaller source/pose list, a previously absent actor name, a new output package name and
   multiple variants. These exercise the missing writer work instead of merely overwriting fixed-size coordinates.
3. Compare normalized object graphs and properties; require untouched code/content payloads to remain unchanged
   where the chosen layout allows it. Validate every index, count, offset and compression block independently.
4. Verify loading, exact transforms, cover, line of sight, movement, destruction where applicable, save/reload and
   consecutive missions. Include coexistence with inherited patch maps and consistent helper versions.
5. On a clean machine with EW/LWR and the packaged application, import a supported map and build a different
   layout offline, without UDK, Uncooker, UPKUtils or separately installed Python/PowerShell.

Until these pass, describe the standalone builder as proposed. Keep the installed UDK for reference and validation.

# Editor contracts (E0)

Written 6 November 2026 for slice E0 of the first-editor plan (section 9), alongside the
first implementation of E1 (projects). It fixes what an edit refers to, how a pose is recorded, and the project file
format. The viewer ([project.js](../tools/viewer/web/project.js), [app.js](../tools/viewer/web/app.js)) and the
server ([projects.py](../tools/viewer/projects.py)) implement it. Later slices (the compiler, E3; packaging, E4) read
the same document.

What E0 still lacks is listed at the end.

## 1. Piece identity

A piece is identified by its **source package, level, actor and component**, all as the export records them:

| Field | Export field | Example |
| --- | --- | --- |
| package | `sourcePackage` | `URB_Bar` |
| level | `layer` | `base` (the map itself) or `inherited` (a patch a preview layout streams) |
| actor | `actor`, the full path | `TheWorld.PersistentLevel.XComDestructibleActor_20` |
| component | `component`, the full path | `TheWorld.PersistentLevel.XComDestructibleActor_20.StaticMeshComponent_12` |

- Edits to originals are per **actor**: (package, level, actor). Moving or deleting an actor takes all its components;
  the viewer's selection already works on whole actors.
- Added pieces name their **template** by actor and list the template's components.
- The key is unique and stable:
  - **Unique:** no duplicate (package, level, actor, component) on the Bar (1,078 components in 969 actors) or the
    Temple Ship (1,678 in 1,678).
  - **Stable:** every key of a test project saved on the Bar's version 12 export resolves in its version 10 and 11
    exports, which share the same source SHA-256. Re-exporting therefore loses no edits.
- **Not identity:**
  - **Short names.** `XComLevelActor_44` exists in both the base level and `patch_bar`; EXP-07 found one hider
    removing both.
  - **Export ids** (`2545:8364`): they belong to one export.
  - The viewer's render ids for copies (`added:<uuid>`).
- **The map** is identified by the SHA-256 of its source package. A project records it. A project opened on another
  package with the same name still shows its edits where keys match, but says so: building must be blocked until the
  project is rebound (E4).

## 2. Assemblies (linked pieces)

Actors placed by one prefab instance are one assembly: a car's body, glass and light bar, or a moving van's 14 parts.
So are actors that name each other through `HidingPartner` (export field `partner`).

- **Grouping:** the viewer groups actors with the same `prefab` within one package and level, and actors linked by a
  partner that is present. The grouping runs in one pass ([gizmo.js](../tools/viewer/web/gizmo.js) `linkFinder`).
  Two actors naming the same *missing* partner stay apart.
- **Copies keep their links inside the copy:**
  - a copied part's `prefab` becomes `copy<serial>:<source prefab>`; each set of linked pieces in one paste gets a
    serial of its own (12 November 2026), so two copies of one car pasted together are two assemblies;
  - the copies of an assembly whose pieces share no prefab (a door's leaf and frame, 8 November 2026) share
    `copy<serial>:<the assembly's pivot>`, the leaf's actor name;
  - its `partner` becomes the output name of its partner's copy, made in the same paste, or nothing.
  - So a copied car moves as one car, apart from the original.
- **Pivot:** an assembly's pivot is the actor the user picked. In the piece list it is the largest part (a car's body).
- **The map's assemblies** (8 November 2026, the cars, doors and ladders plan 3.3): the
  compiler's `assemblies()` joins a car's parts, a van's, a door's leaf and its frame, and gives a ladder one of its
  own. The server serves them (`/maps/<id>/families.json`), and the editor moves their pieces together always, with
  Linked pieces on or off, so it never makes an edit the Build refuses as `assembly-split`.

**The user's groups** (6 November 2026) are assemblies the user makes: two or more pieces, originals or added, locked
together in the editor and saved in the project (`groups`, section 4).
- **No unlocking** (11 November 2026). The editor has Group and Ungroup only: every group selects and moves as one,
  the editor writes `locked: true`, and a group saved unlocked before is opened as a group like any other. What the
  next points say of locked and unlocked groups is how it was until then; `locked` stays in the document for older
  files.
- **Lights and buildings are members** (11 November 2026; prefab plan 5.4a). A light is a member as a piece is: an
  original by `{ "package", "level", "actor" }`, an added one by `{ "added": actor }`. One of the project's buildings
  is `{ "building": id }`, its key `building|<id>`, and stands for all of its boxes. In the editor they move, turn,
  copy and go with the group whether drawn or not (outside the Buildings view, where each box is on its own); a
  selection with a building moves by whole tiles and levels and turns by quarter turns about the vertical. A copy
  of the group has copies of its lights and a new building with the same floors. A member naming a building that
  is gone is dropped on save. The compiler takes `{building}`, warns of one that is not the project's
  (`group-member`) and passes over lights and buildings in break together.
- **Groups nest** (11 November 2026; prefab plan 5.4): a member can be another group, `{ "group": id }`. A group is
  a member of one group at most and never inside itself; the compiler notes it otherwise (`group-nesting`, a note
  since 20 November 2026: nothing of nesting reaches the game, so the groups build as they are), and the editor
  carries such a group unapplied. A piece picked selects the outermost locked group it is in; Unlock and
  Ungroup act on that one, so they peel one level; Ctrl+G on pieces and whole groups makes a group that holds the
  groups as members. A group left with fewer than two members ends and its last member takes its place in the group
  it was in (`pruneGroups`). Breaking together is over a group's own pieces: a member that is a group is skipped.
- **Locked:** the group selects and moves as one, whether linked pieces are on or off (`linkFinder` joins a locked
  group's actors always, the map's links only with linked pieces on). **Unlocked:** the group and its options stay,
  and its pieces move one by one. A piece is in one group at most; locking pieces into a new group takes them out of
  their old one, and a group left with fewer than two pieces ends.
- **A deleted member** stays in the group while the editor runs (undo brings it back); a save keeps only the members
  on the map, and drops a group left with fewer than two.
- **Copies:** pasting two or more pieces of a group makes a new group of their copies, with the same lock and options.
- **Options:** `breakTogether`, for the game: the compiler numbers each such group with two or more breakable pieces
  (destructible props and collectibles), and the copier links its copies and the base map's own pieces of it left in
  place (`breakGroups`, `breakOriginals`; tools/patch/README.md). The editor's Build makes a group's copies in the
  map itself and links them there with that same `AffectedChildren`, each member listing every other, the map's own
  pieces left in place included (`native_edit.native_split`, `native_copy.link_children`). A group with a collectible's
  copy stays the copier's whole. In the game a copy that is damaged or destroyed puts
  the rest of its group in the same state. A base-map piece left in place does it through the game's own one-way link,
  `AffectedChildren`. A group whose breakable pieces are all the map's own, left in place, isn't linked yet (the
  compiler warns), unless it holds a cover block.
- **Cover blocks in a group that breaks together** (13 November 2026): a high or low cover block of such a group goes
  when a breakable piece of the group is destroyed, so it leaves no invisible wall where the piece stood. The
  compiler gives the block the group's number (`breakGroup` in the spec's `covers`), and the Build makes it as a
  hidden prop instead of a level actor (`cover_blocks.BREAKING`), listed in each breakable member's
  `AffectedChildren`; the block lists nothing and takes no damage of its own. With a block, one breakable piece is
  enough, and it may be the map's own, left in place (the spec's `breakOriginals` object carries it when the project
  has no copy). An invisible floor in such a group stays (`group-unbreakable`). The piece list's assemblies are the map's own: user groups are not entries there.

## 3. Transforms

- **Space:** game space, as the game stores it. Units are Unreal units, with X and Y horizontal and Z up; a floor tile
  is 96 × 96 and a tile level is 64 high.
  - The viewer draws in three.js's basis (x, z, y) and converts only at the rendering boundary.
  - Its inspector shows game axes and degrees.
- **An actor's pose** is its `location` [X, Y, Z] and `rotation` [pitch, yaw, roll]:
  - The rotation is an Unreal `FRotator` in native units, 65,536 to a turn.
  - It turns the actor as `export_math.transform` and the viewer's `actorMatrix` do: yaw about Z, pitch, then roll.
- **Rotators, not quaternions.** The plan (section 3) suggested quaternions internally; the document stores rotators
  instead:
  - A rotator is what the game stores and what the builder writes.
  - It is unambiguous under that convention.
  - It keeps an untouched rotation bit-exact.
  - The viewer's gizmo works on matrices and converts once.
  - Straight up or down (pitch ±90°), yaw and roll coincide, and the inspector reports the turn as yaw.
- **What is kept:**
  - Scale and component offsets stay the source's. A component follows its actor:
    `render = actorMatrix(new pose) × actorMatrix(source pose)⁻¹ × source render matrix`.
  - Scale editing is outside this slice.
- **Precision:**
  - Locations to 1/10,000 unit.
  - Rotators to 1/1,000 native unit, made whole when within 1/1,000 of a whole number.
  - **A piece that was moved without being turned keeps its source rotator exactly** (for example 70,000 stays
    70,000, not 4,464).
  - The compiler (E3) rounds to the game's integers and must use the same rounding everywhere (plan section 2).
- **One pose per actor.** A pose is never recovered from a mesh: the viewer computes it from the actor's render matrix
  against its own source record, and the document holds only poses.
- **The tile grid** (16 November 2026, private/plans/done/game-grid-plan.md; the export's `tileGrid` since export 26,
  from the map's own record, scene_metadata.game_grid) has two corners, a unit apart on every axis:
  - `origin`, the level volume's box's low corner. The maps' own pieces stand on whole tiles from it, and the editor
    places by it: tile snap, the lines it draws, the turn pivot, the grid rule. Every pose a project or prefab saves
    is on it, as before export 26.
  - `tiles`, the corner the game counts its tiles from (its world data's `WorldBounds`). Which tile a point is in
    counts from it, as the game counts it: a ladder's ends, a mission object's tile, a soldier's spot, the floor under
    a piece being placed. An export older than 26 has no `tiles`: the tools take a unit under `origin`, as on every
    installed map.
  - `dimensions` are the tile data's counts; `source` is `world-data`, or `level-volume` for a map that saves no
    record of its own.
  - The rules for boxes keep `origin`, as they were played: the floor a flat piece gives, the cover block panel's
    tiles, the Build's seeds and rebuild volumes.

## 4. The project document (schema 5)

A JSON file, named after the project (`Bar remix.json`, section 5). The server ([projects.py](../tools/viewer/projects.py)) refuses any other `schema` or
`schemaVersion`, with a message naming the version. Schema 2 (16 November 2026; piece flags plan) adds pieces' `flags`;
the page, the server and the compiler read schema 1 and 2, and the page writes 2. The server refuses a **save** of
schema 1: only a page older than the server writes one, and it would drop the flags of a newer document ("Not saved:
This page is older than the editor's server…"). Prefab files are schema 2 the same way, and a prefab imported at 1
is stored as 2.
Schema 3 (17 November 2026; the effects and sounds plan, stage FX3) adds effects' and sounds' records (the rows
`overrides[]` and `added[]` of effects and sounds below): the page, the server and the compiler read 1, 2 and 3, and
the page writes 3; the server refuses a save of 1 or 2 as it did of 1.
Schema 4 (18 November 2026; the editor spawns plan, stage SP8) adds `spawnRules` (below), and the base map's spawn
points' records (stages SP6 and SP7) under the same number: the page, the server and the compiler read 1 to 4, the
page writes 4, and the server refuses a save of 1 to 3.
Schema 5 (22 November 2026) adds `backgroundSound` and `clearKeepsTriggers` (below): the page, the server and the
compiler read 1 to 5, the page writes 5, and the server refuses a save of 1 to 4. A cleared project of schema 1 to 4
has no `clearKeepsTriggers`, so its next Build takes the map's triggers out (F-159).
Schema 6 (23 November 2026) adds `lwrMapInfo` (below): the page, the server and the compiler read 1 to 6, the page
writes 6, and the server refuses a save of 1 to 5.
Schema 7 (23 November 2026) adds `diagonalCover` (below): the page, the server and the compiler read 1 to 7, the page
writes 7, and the server refuses a save of 1 to 6. The Build no longer finds diagonal cover by itself (KB-20), so a
project of schema 1 to 6 with a made wall or a cover block at 45 degrees builds without the corners 0.7.0 found there
until they are marked.
Schema 8 (23 November 2026) adds a building's `cursorFloors` (below, `buildings`): the page, the server and the
compiler read 1 to 8, the page writes 8, and the server refuses a save of 1 to 7. A project of schema 7 builds as it
did.
Schema 9 (24 November 2026; private/plans/done/modular-clear-plan.md) makes `cleared` the parts of the map the project
cleared (below): the page, the server and the compiler read 1 to 9, the page writes 9, and the server refuses a save
of 1 to 8. `cleared: true` of schema 1 to 8 is read as every part, so such a project builds as it did, and the page
saves it in the new form, without `clearKeepsOutside` and `clearKeepsTriggers`.
Schema 10 (27 November 2026; the game-likeness plan, stages C5 and T-S1) adds `atmosphere` and `sun` (below): the page,
the server and the compiler read 1 to 10, the page writes 10, and the server refuses a save of 1 to 9. A project of
schema 9 builds as it did.
Prefab files are schema 3 since stage FX6a (17 November 2026): a piece with a `kind` is a copy of a map's effect or
ambient sound, `{actor, kind: effect | sound, from: {package, level: base, actor}, location, rotation}` with the
values object of its kind at most (`effect` or `sound`, as an added record of a project has it), a member of the
prefab's groups by its `actor` as any piece is, its map among the `donors`. It has no components, partner, link or
recipe. The server reads prefab schema 1, 2 and 3 and stores 3; an editor before this stage refuses a schema 3 file
by its number ("A newer editor is needed to open it"). Since stage FX6b (17 November 2026) a piece may be a copy of
a map's lens flare, `{actor, kind: flare, from, location, rotation}`, never with a values object; the schema number
stays 3, and an editor of stage FX6a refuses such a file by the piece ("of a kind this editor doesn't know"). The
summary counts `effects`, `sounds` and `flares`.
Prefab files are schema 4 since 20 November 2026 (review finding 6): a copied piece keeps what a project's added
record keeps of it, a piece made from numbers (`generated`: a drawn wall, floor or roof, or ground shape, its own
`blasts` inside it) and a broken copy of a map's fracturing piece (`blasts`, `breaksFurther`), so a selection saved as a
prefab and placed again, and Test in game, make those pieces as the project has them, not as their donors. The page
converts a piece's record one way everywhere (`tools/viewer/web/piece_records.js`: the clipboard, a project, a prefab
saved and placed, the builder). The server reads prefab schema 1 to 4 and stores 4; it checks a made piece's numbers
as data only (its kind, and numbers, words and short texts, bounded), and the compiler checks what they mean.
Prefab schema 5 (23 November 2026; the building cursor floors plan) lets a prefab's building carry `cursorFloors`
(true or false), as a project's does; the server reads 1 to 5 and stores 5, and an editor of before it says such a
prefab is newer.
Only a save is refused at an older number (it comes from a page older than the server). Opening and placing a prefab
read it at any number the server reads, `POST /prefabs/size` and `POST /prefabs/recover-sources` included, and the file
keeps its number until it is saved again; before 24 November 2026 those two refused it as a stale page's save, so a
prefab saved by an earlier editor couldn't be placed until it was saved again in the builder.
Since 21 November 2026 a made piece's `generated` may be in the free form: `fracWall` version 5, `fracSlab` version 4,
`ground` version 5, whose numbers carry `free: 1` and say everything in fields: the extents at any size in the piece's
own frame (`x0`..`x1`, `y0`..`y1`, `z0`..`z1`: a wall's ends, faces and bottom and top; a slab's footprint and plate; a
ground shape's footprint and plate or body), a wall's `tall` (`repeat` or `stretch`), openings or holes anywhere
inside, `look` absent (the kind's default), a look id or a donor look with `plain: true` beside it when none was
chosen, a rock's `points`, and a texture `mapping` (`{surfaces: {faces | top | underside | sides: {mode: size | fit |
count, modeV, u, v, turn, flipU, flipV, offsetU, offsetV, world}}}`, `modeV` the mode along v when it differs:
`tools/bake/uv_mapping.py` says what each means). The compiler checks them (`tools/editor/made_edits.py`
`free_valid`) and hands them to the Build as its own free version of the kind (walls 4, slabs and ground 3), less
`plain`, with `mappingOrigin` added where a surface is aligned to the world (`world: true`): `{role: place}`, where
the piece's frame stands in the world, worked out from the record's location and rotation (`made_edits.mapping_origin`;
the page's mesh requests carry the same, `made_mapping.js` `mappingOrigin`, with the cases both read in
`tools/editor/tests/mapping_origin_cases.json`; `tools/bake/uv_mapping.py` `origin_of` reads it): for a wall's faces
`[a0, b0]`, the location along the piece's x (its yaw's rounded step) and its z; for a top or underside, along its x
and along its y; for a ground shape's sides `[x, y, z]`, along its x, along its y and z (a side along x reads x, one
along y reads y); each to a millionth. A three-number place is the Build's for any surface, and the sides take only
that. A record need not carry it, and one it carries is accepted (as `uv_mapping.check_origin` takes it) and not taken:
the Build's is worked out again from the pose. An editor from before refuses these
versions by their number; older versions are read and built as they were, and the page upgrades a piece to the free
form when a size or its texture mapping is edited (`tools/viewer/web/made_free.js`).

```json
{
  "schema": "xcom-map-workshop/project",
  "schemaVersion": 4,
  "id": "5005037f-f7ac-4287-97f6-d1cab95360f9",
  "name": "Bar remix",
  "mode": "edit",
  "revision": 3,
  "created": "2026-11-06T11:24:10Z",
  "savedAt": "2026-11-06T12:02:41Z",
  "source": { "map": "URB_Bar", "package": "URB_Bar.upk",
              "sha256": "a3ae5a73457c3c3f3e490fde9e1ad935f667c4843792fc8d140abc66878e09b5", "exporterVersion": 12 },
  "output": { "shipAs": "BarRemix", "patch": "patch_barremix" },
  "overrides": [
    { "target": { "package": "URB_Bar", "level": "base", "actor": "TheWorld.PersistentLevel.KAsset_6" },
      "location": [-269, 632.9999, 19], "rotation": [0, 5461.333, 0] },
    { "target": { "package": "URB_Bar", "level": "base", "actor": "TheWorld.PersistentLevel.StaticMeshActor_105" },
      "deleted": true },
    { "target": { "package": "URB_Bar", "level": "base", "actor": "TheWorld.PersistentLevel.XComDestructibleActor_470" },
      "flags": { "walking": false } }
  ],
  "added": [
    { "id": "5c2561b9-029a-4dd6-97d1-61e19bfeb31d",
      "actor": "TheWorld.PersistentLevel.XComDestructibleActor_101_copy1",
      "from": { "package": "URB_Bar", "level": "base", "actor": "TheWorld.PersistentLevel.XComDestructibleActor_101" },
      "components": ["TheWorld.PersistentLevel.XComDestructibleActor_101.StaticMeshComponent_139"],
      "location": [-1986.0074, -1140.0933, 181.7296], "rotation": [0, 32768, 0],
      "prefab": "copy1:PrefabInstance_1", "partner": "TheWorld.PersistentLevel.XComFracLevelActor_15_copy1" }
  ],
  "nextSerial": 1,
  "view": { "camera": [0, 0, 0], "target": [0, 0, 0] }
}
```

| Field | Meaning |
| --- | --- |
| `id` | The project's UUID: what the routes, builds and the local state (`.workshop\<id>`) know it by, whatever its file is called. |
| `name` | 1 to 120 characters. |
| `mode` | `edit` only. `blank` is reserved for the later blank-map preset. |
| `revision`, `savedAt`, `created` | Set by the server on each save. |
| `source` | The base map: catalogue id, package file, SHA-256 and the exporter version it was edited on. |
| `output` | The variant's map and edit-patch names. Fixed at the project's first save: the server gives a new project its name as one word, at most 24 characters, numbered when another project, build or package of the game installs has it (`patch_<map in lower case>` for the patch), and refuses a later save that changes them (tools/viewer/outputnames.py, projects.py). Save as under a new name makes a new project with names of its own; replacing a project keeps its own. Projects saved before 16 November 2026 keep theirs (the base map's, the project's and four digits of the id; up to 30 characters). The Build and the installs check them again against everything that holds names, and refuse what another project holds. |
| `overrides` | Originals moved (`location`, `rotation`) or deleted (`deleted: true`), one record per actor, sorted by key. An actor not listed is as exported. |
| `added` | Added actors, sorted by output name. `id` is the entity's UUID. `actor` is its output name: `<template actor>_copy<serial>`, kept once given. `from` and `components` name the template. Optional `tinted: true` for a tinted spawn's copy (preview layouts only). |
| `nextSerial` | The highest copy serial used. A new copy never reuses an output name, even one whose piece was deleted. |
| `view` | The camera at the last save, in the viewer's basis. A convenience only: it never hides or changes pieces. |
| `overrides[].flags`, `added[].flags` | Optional (schema 2, 16 November 2026; piece flags plan): the settings the game reads for a piece, as the user asked for them, only those asked: `walking` (blocks walking), `cover` (gives cover), `sight` (blocks sight), `floor` and `mouse` (the mouse picks it), each strictly `true` or `false`; never empty. An override may be flags alone, with no pose (the piece stays where the map has it), or flags with a pose. A deleted piece's flags are kept for an undo and not built (a note). A cover block, an invisible floor or a light has no flags (refused); a role the piece's class doesn't have is noted and left out. The compiler plans each request against the piece's settings as export 27 has them (`pieceFlags`; [piece_flags.py](../tools/viewer/piece_flags.py)): a flags-only override goes into the spec's `pieceFlags` object, written on the map's own actor by the Build ([native_copy.py](../tools/bake/native_copy.py) `set_roles`); a copy carries its flags to its clone. What each role writes, the prop's pathing gate (opening it writes the roles not asked for so they stay as they were, the companions) and what a role does not decide are in [research/native/piece-flags.md](native/piece-flags.md). |
| `overrides[].target` in a stream | Optional (15 November 2026; mission types plan, Part E): `{ "package": "<stream>", "level": "stream", "actor": ... }` names one of a mission stream's objects (the export's `streams[<stream>].missionObjects`). Its `location` and `rotation` move it in place in the variant's copy of the stream (`<Stream>_<Variant>.upk`), which that mission's records stream instead of the original; the page moves an object with its group, one record per part. `deleted: true` takes it out of the copy, with a warning. A target in a stream that is no mission object is an error. |
| `overrides[].light` | Optional (editor lights, 9 November 2026): a light's changed values, only the keys that differ from the export's: `color` (bytes 0 to 255), `brightness`, `radius`, `falloffExponent`, `innerConeAngle`, `outerConeAngle` (the stored values; the editor shows the effective cones) and `enabled`. A light override can also move, turn or delete the light as a piece's does. See the editor lights plan, sections 3 and 9.4. |
| `added[]` lights | A copied light has `from` and `components` like a piece, and optional `light`. A light made from the editor's recipe has `template: { "kind": "spot", "version": 1 }` and `light` in place of `from` and `components`; its output name is `TheWorld.PersistentLevel.SpotLight_copy<serial>`. |
| `overrides[]` of effects and sounds | Schema 3 (17 November 2026; effects and sounds plan, FX3): an effect's or a sound's actor (the export's `effects`, `sounds`) moved (`location`, `rotation`, the actor's own pose) or deleted (`deleted: true`), as a piece's is. Optional `effect` or `sound`, never both: the effect's or sound's own values, only keys that differ (`effect`: `scale`, `startsOn`, `parameters`, `follow`; `sound`: `radiusMin`, `radiusMax`, `volume`, `pitch`, `startsOn`). `effect.follow`: `"none"` keeps an effect a piece carries where the map has it (or where its own pose puts it) when the piece moves, is copied or deleted, `"auto"` lets it follow (the default, never saved). The other keys are stage FX5's (17 November 2026), built while the `effect-values` and `sound-values` families build (an experiment's build lifts them with `--family`; refused with code `family` otherwise): an effect's `scale` (a multiplier of 1/64 to 64 on the size the map gives it: the Build multiplies the actor's `DrawScale`, its `DrawScale3D` kept), `startsOn` (its component's `bAutoActivate`) and `parameters` (`[{name, value}]`: a number, `[x, y, z]` or a colour `[r, g, b, a]` each 0 to 1, in the type the effect saves that name in, or, for a name it doesn't save, the kind its system's distribution has; a random or untyped entry, a name read as both kinds and a name the system lacks are refused); a sound's `radiusMin`, `radiusMax` (0 to 65,536, inner not beyond outer as the sound then has them), `volume` and `pitch` (`[least, most]`: 0 to 16, 1/16 to 16) and `startsOn` (the actor's `bAutoPlay`), set on its own node, so only where the export's `can.values` (a simple sound's private cue and node). An override may be values alone, with no pose; a deleted one's values are not built. A lens flare and a stream's are view only: the compiler refuses an edit of one. |
| `added[]` effects and sounds | Schema 3: a copy of an effect or a sound has `kind` (`effect`, `sound`; since stage FX6b `flare`, a lens flare's copy, which has no values object and builds where the `flare` family does), `from` (the original's target), `location`, `rotation` and optional `effect` or `sound` values (the same keys as an override's, of its own kind only); no `components`, `template`, `light`, `cover`, `flags`, `prefab`, `partner` or `tinted`. Its output name is `<original actor>_copy<serial>` like a piece's. A copy of an effect a piece carries is its own actor: it follows nothing. Since stage FX4 (17 November 2026) `from` may name another base map's effect or sound (`package` another map, `level` `base`): the library's (section 8). |
| `areaLightBindings` | Optional: the generated area lights' glowing pieces as the project sets them, sorted: `{ "target": <the area light's target>, "owner": { "target": <a base-level piece's target>, "component": <its component> } }`, or `"owner": null` to keep the light where it is. A light not listed follows the export's verified association (`emitterAttachment`). |
| `buildings` | Optional (11 November 2026; prefab plan 5.1, stage B1). Buildings the Build makes from nothing: `{ "id": string, "name": string, "kind": "building" or "ufo", "cursorFloors"?: boolean, "floors": [{ "boxes": [[x0, y0, z0, x1, y1, z1]] }] }`, floor 0 first, the boxes in game units and unturned, at least one box a floor, at most 10 floors (8 until 14 November 2026). Which pieces each floor lists is not saved: the Build works it out from where the pieces stand (tools/bake/buildings.py). The compiler warns of a box outside the tile grid, and of one that overlaps a box of another floor or building (a refusal until 13 November 2026: warn, don't block). The page makes and fits their boxes in the Buildings view (Shift+B); a building it can't read is carried unchanged. Built since EXP-44 passed (11 November 2026). **`cursorFloors`** (23 November 2026, schema 8; the building cursor floors plan): `true` makes the building's floors the cursor's over its boxes, so the mouse wheel stops once a floor there: the Build takes the map's cursor volumes out over its footprint, stands them again round it, and lays one for each floor over each part of it, starting 2 under the bottom of that floor's box there and ending where the next floor starts (the last at its box's top), numbered as the building's floor (tools/bake/made_cursors.py). Absent or false: as before. Read on a building made from nothing only; the map's own (`replaces`) bring none. **The map's own buildings** (13 November 2026; map buildings plan, section 2): one the project changed is saved here too, with `replaces`, the map's building volume as a piece's target (`{ "package": "URB_Bar", "level": "base", "actor": "TheWorld.PersistentLevel.XComBuildingVolume_2" }`), and its id made from the actor (`map:PersistentLevel.XComBuildingVolume_2`), the same each time the map is opened, so a group's `{ "building": id }` holds for it with or without a record; each of its floors has `volumes` beside `boxes`, as long and sorted with them: the floor volume (short name) each box came from, `null` for a new box. A deleted one is `{ "id", "replaces", "deleted": true }`, with no floors. A map building with no record is the map's, as exported; the page saves only the ones whose floors, name or kind differ from the export (every box within 0.01 of its volume's), and the deleted ones. Its `name` starts as the actor's short name, its `kind` as `ufo` where the map's has `IsUfo`. A prefab never carries `replaces` or `volumes`: a building saved into one, or copied, is a new one. The buildings of streamed levels, vans' buildings and buildings with a floor that has no floor volume stay fixed (export 21's `van` and floors). |
| `stage` | Optional (11 November 2026; prefab plan 5.11), on any map (13 November 2026: before then the blank map or a cleared project alone): `{ "grid": [tiles across, tiles deep], "ground": false }` or `{ "grid": [tiles across, tiles deep, levels] }`, the tile grid made that large from its own corner and, with the third number, that many levels from its own bottom (1 to 128 tiles, 1 to 30 levels: 18 until 14 November 2026; over 18, the tallest of the game's own maps, the compiler warns `stage-levels-tall`: not played, and the Build gives the grid a cursor storey for each 192 units, ten at 30 levels). A map as it is, the blank map among them, may only grow, across and up (a map other than the blank map grown as it is is warned of: not played; with more levels, the Build adds even cursor storeys over the whole grid above the map's own cursor volumes, and stretches those reaching the old far X or Y side to the new one: shell.py grow_cursors); a cleared project's may also be smaller in any of the three (13 November 2026, Clear map plan, section 6): the corner and the bottom never move. `ground` false lays no ground over the new area (the Build lays the map's ground where it is laid as planes); `lines` and `hideGround` are the blank map's. |
| `cleared` | Optional (13 November 2026; Clear map plan, section 6; parts since 24 November 2026, schema 9: the clear-by-parts plan): the parts of the map the project cleared, `{ "pieces"?: {}, "lights"?: {}, "effects"?: {}, "triggers"?: {} }`, each `{}` or `{ "keepOutside": true }` (that part's clear kept the scenery outside the play area: the page did not delete what of that part lies wholly outside it, and the Build leaves what of it stands outside it; the play area is the map's level volume and the grid as the project has it together, across: the compiler's `outside_box`, the page's `outsideBox`). For each part the Build's clear_level takes out what the editor never showed (native_copy.py `CLEAR_PARTS`; never an actor of the landing's prefabs): **pieces**, building, floor and cursor volumes, path-blocking, camera-blocking, damage, camera and hide volumes, cover seeds, stains (decals) and the bake's area lights; **lights**, the point and spot lights the editor cannot edit; **effects**, emitters, lens flares and ambient sounds; **triggers**, trigger volumes (touch and water) and sight points, the events of a touch volume switched off (F-159). With the pieces it also puts the grid's cursor volumes and one rebuild volume over the whole grid, lets the grid shrink, lays no ground and streams none of Long War's patch levels (KB-23); without them none of these. It deletes no piece, light the editor edits, spawn point or landing zone: those a clear takes are `deleted` overrides and the project's `landingZones`, as hand edits make them, so the page shows what the Build leaves. `true` (schema 1 to 8) is every part, `clearKeepsOutside` on each and the triggers left out with `clearKeepsTriggers`. Absent, false or `{}`: nothing cleared. A part the compiler can't read is left out (`cleared-shape`), and the others cleared. |
| `clearKeepsOutside` | Schema 1 to 8 only (13 November 2026, the Clear map window's "Keep the scenery outside the play area"): `true` with `cleared: true` says the clear kept the scenery outside the play area, read as `keepOutside` on every part. Schema 9 says it per part in `cleared`, and the page no longer writes it. |
| `clearKeepsTriggers` | Schema 5 to 8 only (22 November 2026; the Clear map window's "Keep the map's triggers and scripts"): `true` with `cleared: true` says the clear kept the map's triggers, read as every part but `triggers`. Schema 9 leaves the part out of `cleared`, and the page no longer writes it. |
| `backgroundSound` | Optional (22 November 2026; schema 5): the map's background sound, the sound bed its script starts when the level loads (export 39's `backgroundSound`): `{ "cue": <a cue's path> \| null, "volume"?: number }`. `cue` is the map's own or one of the game's beds the editor offers ([background_sounds.json](../tools/viewer/background_sounds.json), 26 rows, each with the base map that plays it); `null` plays none; `volume` (0 to 4) is the sound's VolumeMultiplier. The Build brings a bed of another map from that map (transplant.stage_edit, its cue with its nodes and waves) and points the map's level-loaded `SeqAct_PlaySound` at it (`native_sounds.background`, read back); the manifest's `backgroundSound` says `{ cue, volume?, from? }`. Left out, with the map's own sound kept: another shape (`background-sound-shape`), an export older than 39 (`background-sound-export`), a map that starts no background sound (`background-sound-none`, 9 of the install's 97 base maps), a cue the list doesn't hold (`background-sound-cue`). The map's own cue at its own volume changes nothing (a note). Absent: the map's own. |
| `landingZones` | Optional (13 November 2026; Clear map plan, section 4): the whole list of landing zones, in order: `{ "id": string, "location": [x, y, z], "direction": "north" \| "east" \| "south" \| "west", "kind": "normal" \| "inside" \| "alternate" \| "noEvac" \| "default", "missionType"?, "councilType"?, "alternate"?: { "location": [x, y, z], "direction" }, "lwr"?: false, "ew"?: true, "other"?: string }`. `location` is an LZArray line's `StartLoc` (the zone's ground is 64 under it), `direction` its `StartDir`, `kind` its `ESpawnLoc` (no line of the install uses the last three), `missionType` and `councilType` the mission it is kept for, as written, `alternate` its `AltSpawnLoc` and `AltSpawnDir`; `lwr` false writes no line for it; `ew` true (13 November 2026, the panel's Plain EW) makes it one of the map's own landings for plain EW; `other` keeps a line's fields the editor does not know, as written. The Build writes every zone with no `lwr: false` as one of the variant's LZArray lines, and the zones marked `ew: true`, in order, as the map's own landings moved in place, one for each landing the map has (the first marked zone is the first landing; marked zones beyond the map's count play under LWR only, a warning). A list with no zone marked goes by order: the first zones that name no mission. An empty list is no zone at all (a warning). Absent: the base map's lines are copied and its own landings left as they are, as before. A malformed zone is carried in its place, and the Build leaves it out, and a zone whose id an earlier one has; a value that is no list, or whose zones are all left out, builds as an absent list (20 November 2026; a refusal before). |
| `missions` | Optional (15 November 2026; mission types plan, Part D): the missions the variant serves, a list of at least one: `{ "record": i }` for the base map's record `i` (the export's `missions` order, its `DefaultMaps.ini` records in file order), or `{ "kind": "Abduction" \| "TerrorSite" \| "Special/Bomb" \| "Crash" \| "LandedUFO", "ship"?: "eShip_UFO..." }` for a kind a record alone gives the map (`missions.ADDED_KINDS`: made from the base map's abduction record; `ship` the UFO type, for the two UFO kinds only). The Build writes a record for each (base records in file order, then the added kinds), and nothing else; Play in game plays one of them. Absent: every record of the base map, as before. An entry the Build can't write is left out, and a value that is no list, an empty list or one with no entry it can write builds as an absent list: every record (20 November 2026; an error before). A project whose one change is its list builds: its records are a change of their own. |
| `lwrMapInfo` | Optional (23 November 2026; schema 6): what Long War Rebalance is told of the map, the Map settings window's Long War Rebalance section: `{ "alienDensity"?: "Light" \| "Moderate" \| "Heavy" \| "Swarming", "holdTheLine"?: "No" \| "Yes" }`. LWR 3.00.00 beta 17 reads map info by a map's file name (its `DefaultMaps.ini`, section `[XComMutator.LWRMapInfo]`, and a map pack's block or card): `AlienDensity` is the largest abduction the map suits (a larger one is moved to another map), `HoldTheLine` `No` keeps Hold the Line off the map; a key a map has no line for is Unknown (any abduction size, Hold the Line can happen; a pack map that takes a vanilla map's place then uses that map's value). The keys and values are one table on each side ([missions.py](../tools/viewer/missions.py) `MAP_INFO`, [missions.js](../tools/viewer/web/missions.js), pinned by `twin_constants.json`). The compiler reads it into its report's `lwrMapInfo` (the spec is the same without it: nothing in the map changes); the Build writes the variant's lines into the manifest's `config.mapInfo` (`MapInfo=(Map="<variant>", Key="AlienDensity", Value="Moderate")`) and the README; a map pack's card carries them in its `MapInfo` array ([pack_card.py](../tools/upk/pack_card.py): still card format 1, written only when a map has a line; an older LWR passes over the field), and `pack.json` and the pack's READMEs say them. A campaign install made by the editor writes `DefaultMaps.ini`'s records alone and says in its warnings that the map info is not written. The info alone is work: a project with nothing else builds the map unchanged with it. The page's checkbox writes `No` or leaves `holdTheLine` out; a `Yes` written by hand is kept. Absent, null or empty: no line. A key or value this editor doesn't know is left out whole (`lwr-map-info`); the page carries it as saved. |
| `atmosphere` | Optional (27 November 2026; schema 10; the Map settings window's Fog and colour section): the map's height fog and post-process settings the project changes, `{ "fog"?: {member: value}, "postProcess"?: {member: value} }`, only the members whose value differs from the map's own (the page's atmosphere_rules.js `tidyAtmosphere`), in the export's form (tools/viewer/atmosphere.py): a number, true or false, a colour as four numbers from 0 to 1, a vector as three numbers, an enum member's name. `fog`'s members are XComHeightFogParameters' (bEnabled, FogDensity, FogHeight, FogHeightFalloff, FogMaxOpacity, StartDistance, LightTerminatorAngle, the two colours and their brightnesses), `postProcess`'s PostProcessSettings' (the grade's Scene_Colorize, Scene_Shadows, Scene_MidTones, Scene_HighLights and Scene_Desaturation; the bloom's members; and the rest the struct declares, the LUT, objects and arrays excepted). The page's Game look draws them over the map's own at once; "Take the look of" writes another map's values (/atmospheres.json: tools/viewer/atmospheres.json, made by `atmosphere.py catalogue`). The compiler (atmosphere_edits.py) holds each value to its member's kind (atmosphere_defaults.json `kinds`): one it can't take is left out (`atmosphere-value`), a record of another shape whole (`atmosphere-shape`), and a changed post-process member a volume of the map overrides is warned of (`atmosphere-volume`). It hands the Build `atmosphere`, which writes the map's WorldInfo's `XComHeightFog` and `DefaultPostProcessSettings` again from the members the map saves with these over them, each post-process member with its override flag (tools/bake/native_world.py; F-173). Absent or null: the map's own fog and colour. |
| `sun` | Optional (27 November 2026; schema 10; the game-likeness plan's T-S1, the Map settings window's Sun, moon and sky section): the map's time of day, `{ "time", "heading", "timeOfDay", "light": { "rotation", "color", "brightness" }, "sky"?: { "color", "brightness", "lowerColor", "lowerBrightness" }, "custom"?, "atmosphere"?, "dome"? }`. `time` is the bar's hour (0 to under 24) and `heading` the dial's side in degrees (the side the light stands at its highest, from the game's +X toward its +Y); `timeOfDay` is the game's (`auto`: night while the moon is up by tools/viewer/sun_curve.json's changes, day while the sun is; or `day`, `night`); `light` is the dominant light's rotation (pitch, yaw, roll in the game's units), colour (bytes 0 to 255) and brightness, and `sky` the first sky light's, absent on a map with none. These are the values the project ended with, so a later change of the curve never changes a saved project. `custom` names the values set by hand (`color`, `brightness`, `skyColor`, `skyBrightness`), which the bar leaves as they are; `atmosphere` holds the fog and grade members the time set (`fog.LightInscatteringColor`, `fog.OppositeLightColor`, `postProcess.Scene_Colorize`, `postProcess.Scene_Shadows`, in the form of the project's `atmosphere`), which the project's own `atmosphere` carries while they are not changed by hand. `dome` (stage T-S6, the section's Sky row) is the sky behind the map: `{ "map", "actor" }` names the sky dome of one of the game's maps (the pieces whose mesh is `Skybox.Meshes.SkyDome`; the page offers the curve's `domes`, grouped as day, low sun and night, from T-S0's survey), `"follows": true` beside them when the time of day picks it (the first sky of the group the bar's time is in: night while the moon is up, low sun while the sun is under the curve's `lowSun` degrees, day above), or `{ "follows": true }` alone where the time's pick is a sky the map's own domes show already; absent, the map's own sky. A dome of the map itself is the map's own sky (none). The page saves only a record that differs from the map's own (the page's sun_rules.js `tidySun`). The compiler (light_edits.sun_mark, stage T-S2) checks its shape (sun_curve.py `problem`, the page's validSun on the shared tools/viewer/tests/sun_record_cases.json): one of another shape is left out (`sun-shape`); on a map with no dominant directional light in its base level it is passed over with a warning (`sun-no-light`). Else it hands the Build the native edit's `sun` lane: `{ "actor", "component", "rotation", "color", "brightness", "directionChanged", "sky": { "actor", "component", "color", "brightness", "lowerColor", "lowerBrightness" } or null }`, the lights named by their names in the persistent level (`DominantDirectionalLight_1`, `DominantDirectionalLight_1.DominantDirectionalLightComponent_0`), `rotation` the record's (the map's own where it is within 2 units of it on each of pitch, yaw and roll, the page's rule; `directionChanged` false then), `sky` null where the map has no sky light (warned of: `sun-no-sky`) or the record has none. The Build sets them in place on the map's lights, which keep their names and GUIDs: the DominantDirectionalLight's `Rotation` where the direction changed, its component's `LightColor` and `Brightness`, the SkyLight component's `LightColor`, `Brightness`, `LowerColor` and `LowerBrightness`, each where it differs from the map's (tools/bake/native_lights.py `apply_sun`, read back by `verify_sun`); the dominant light's shadow map of the level and the map's shadow maps stay the old light's, unless a Build with baking finds `directionChanged`: it passes the copy tool `--sun-turned`, which first gives each piece listing the light on its IrrelevantLights that the new direction reaches a shadow map of its own and takes the light off the list (F-198), and the relight traces every shadow map of the light on a piece the level lists again from nothing, and makes the light's map of the level and the lighting samples' marks again for its new direction (relight.py `--sun-turned`, tools/bake/sun_bake.py; the game-likeness plan's T-S4, F-195 to F-198). The report's `sun` (`{ "time", "timeOfDay": "eMissionTime_Day" or "eMissionTime_Night", "directionChanged", "sky" }`, `auto` resolved by sun_curve.py `game_time`, the page's gameTime on the same case file) gives the TimeOfDay the Build writes in each of the variant's records (build.py `config_lines`, through mapsini.py), which Play in game, the campaign install and map packs carry with the records. A quick Build that turns the light adds a warning to its report (`sun-shadows-stale`: the old shadows stay until a Build with baking makes new ones), and a second directional light of the map is warned of (`sun-second-light`: left as it is). The sky (`light_edits.dome_mark`): each of the map's own shown domes is taken out (an exact hide; the Build gives a piece that collides with nothing no rebuild volume, F-201) and a copy of the chosen dome made where it stood, at its rotation, in the chosen dome's own scale, as a piece of another map is copied (the library asked for it as a sky; the Build's transplant stage brings it), named `SkyDome_time<n>` in the report; the report's `sun.dome` says `{ "map", "actor", "replaced", "copies" }`. A dome that can't be had is left out on the record `sun.dome` (`no-library`, `donor-missing`, `sun-dome-shape`, ...) and the map keeps its own sky; a map with no dome of its own (`sun-dome-none`) or a dome of the map itself (`sun-dome-own`) changes nothing (notes). Absent or null: the map's own sun or moon, sky light and time of day. |
| `diagonalCover` | Optional (23 November 2026; schema 7; the Diagonal cover view): the diagonal cover the project marks, `{ "marks": [{ "at": [x, y, z], "toward": [[sx, sy], ...], "low"?: [[sx, sy], ...], "from"?: [x, y, z], "by"?: string }], "removed": [[x, y, z], ...] }`. Each place is a tile's middle in the world, the level's middle in height; the game's tile corner (the export's `tileGrid.tiles`) counts the tiles, so a grid grown by whole tiles leaves it on its tile. A mark gives its tile diagonal cover toward one to four corners, each `[sx, sy]` with 1 or -1 (game axes: the diagonal table's N `[-1, 1]`, S `[1, -1]`, E `[-1, -1]`, W `[1, 1]`), in place of whatever the map has there; `low` names the corners of `toward` that are half cover (the panel's Cover; the game's low bit for each corner), the others full; `from` names the map's marked tile it was (one of the map's marks moved or turned), which loses its own; `by` names the piece a mark follows (a map's mark carried with its moved or copied piece, or with a copy of a piece of another map that gives it at home: saved for the Build, worked out again by the page when the project opens); such a record says `moves: true` when its piece's move takes the map's mark from its home (its `from`), and `gone: true` when its piece is deleted (the home loses its mark, and `at` and `toward` are the home's). `removed` names the map's marked tiles (`tactical.diagonalCover`) the project takes the diagonal cover from. The compiler (diagonal_edits.py) hands the Build `{ marks: [{ at, toward, low? }], removed: [at], pageCarries }`, `pageCarries` for a project of schema 7 or later (the page carried the marks: the Build carries none of its own; an older project's Build still carries the map's marks with copies of their pieces): the Build gives a mark what the game's build gives a seeded tile along the marked corners only, each corner full or half as `low` says (no climb over full cover), a marked corner with no wall cover as marked (its height, no step-outs, no climb), and a removed tile what the game's build gives it without its seed. Absent: the map's own diagonal cover as it is. |
| `spawnRules` | Optional (18 November 2026; schema 4; the editor spawns plan, SP8): `{ "dropIns": "placed" }`, the Spawns flyout's "Scripted drop-ins land where placed". The Build then adds the variant to Long War's drop-in mutator's `ExcludeMaps` list (`DefaultRandomSpawns.ini`, section `[XComLZMutator.XComSpawnAlienMutator]`, after its ExcludeMaps lines, under a comment naming the editor and the project), so every scripted drop-in of every mission of the variant lands at its own point, with none of the mutator's overwatch and reveal; wave systems' drop-ins are never moved by Long War. The manifest's `config.dropInExclusion` says `{ file, section, line }` (and `why` where the build's install can't take it); Play in game and the campaign install plan the line again against the install (ledger keys `playExclusions` and `dropInExclusions`) and take it out only where it stands as written; nothing is written on plain Enemy Within, which plays them where placed already. The rule alone is work: a project with nothing else builds the map unchanged with it. Absent or null: the install's behaviour. Any other value is left out (`spawn-rules`; refused until 20 November 2026): the install's behaviour; the page carries it as saved. |
| `groups` | Optional (6 November 2026; a project without it has none). The user's groups, sorted by `id`: `{ "id": uuid, "locked": true, "breakTogether": false, "members": [...] }`, two or more members, each an original's target `{ "package", "level", "actor" }` (an effect's or a sound's too, since schema 3), an added piece's output name `{ "added": "TheWorld.PersistentLevel.XComDestructibleActor_60_copy9" }` or another group `{ "group": id }`, sorted. See section 2. A group placed from a prefab also has `prefab: { "id", "name", "revision" }` (12 November 2026): a label only, which the Build passes over. Prefab files themselves are described in [tools/viewer/prefabs.py](../tools/viewer/prefabs.py) and the prefab plan, 5.6. |

- A deleted original is only `deleted`. Its pose before deletion is not kept, and restoring it brings it back as
  exported.
- **Records the export lacks are kept.** A record whose target or template is not in the opened export is carried
  unchanged and saved back. The import notes count such records. It is never matched by short name.
- **Malformed records** (wrong shape or non-finite numbers) are carried in the same way, not dropped.
- **Light records** naming a light the opened export lacks, and bindings naming an area light it lacks, are carried the same way.
- **A group** naming a piece the opened export (or the project's own records) lacks is carried whole, unchanged, as is
  a malformed group.

## 5. Storage, saving and recovery

- **Location.** Projects live in the **projects folder**: a setting, by default `Documents\XCOM Map Workshop\projects`.
  Each project is one file, so sharing a project is sending its file (8 November 2026; before, each had a folder named
  by its id):

  | File | Holds |
  | --- | --- |
  | `<name>.json` | the saved document |
  | `.workshop\<id>\project.prev.json` | the revision before it |
  | `.workshop\<id>\recovery-<owner>.json` | unsaved state of one page session (`owner`: the id the page makes as it loads); removed when that page saves or discards, or when another page restores or discards it |
  | `.workshop\<id>\recovery.json` | the same, kept before drafts had owners (20 November 2026) |

  - **The file name** is the project's name with the characters Windows forbids (`<>:"/\|?*` and control characters)
    replaced by `_`, no leading or trailing dots or spaces, and `_` before a device name (`CON`, `NUL`, `COM1`...).
    When another project's file has that name, ` (2)`, ` (3)`... is added.
  - **A save** writes the file the name gives and removes the one before, so a new name (or only a new case)
    renames the file.
  - **Any file ending `.json`** in the folder is read; the `id` inside it identifies the project. So a file renamed by
    hand, or shared and dropped in, is found. Its next save names it after the project again.
  - **Two files with one id** (a copy made beside it): the one with the highest revision, then the newest `savedAt`,
    then the one named after its project, is the project. The other is listed as a copy and cannot be opened.
  - **Other files** ending `.json` are listed as unreadable. A project of another schema version is found by its id,
    so opening it says which version, and listed with that error. So is a project whose shape the editor can't
    read (`projects.shape_problem`: its name not text, no base map and SHA-256, edits that are not lists of
    records, a revision that is not a whole number), with the reason; opening and building it are refused with
    the same words, and a copy that can be read is the project before one that can't (20 November 2026).
  - **`.workshop`** (hidden on Windows) keeps what stays on this computer, by id, so renaming a file keeps its backup
    and recovery.
- **Saving is atomic:** a temporary file, flushed, then replaced, with the previous revision copied aside first.
- **Each save names the revision it was based on.** A save based on an older revision is refused (409, with the
  current revision); the viewer offers to overwrite it or open the saved one. Two tabs therefore cannot silently
  overwrite each other.
- **Recovery:**
  - The viewer keeps unsaved changes a second after each change, in a draft of its own page session. It never does so
    in the middle of a drag. A draft based on an older revision than the saved one (another tab saved meanwhile) is
    kept too, answered as stale, and the page says so once. A draft write that fails is said in the page.
  - A page deletes only its own draft (on saving, discarding or leaving) and a draft it showed: two tabs never delete
    each other's (review finding 3, 20 November 2026).
  - On opening, it offers back the newest draft ("Restore them", "Discard them"), saying when it was kept, the
    revision it was based on when that is older, and how many more are kept. Restoring makes it this page's own;
    Discard deletes it while it is still the one shown, and offers the next.
  - Undo history is not saved. Opening or restoring starts a fresh history.
- **Routes** (in [viewer.py](../tools/viewer/viewer.py)):

  | Route | Does |
  | --- | --- |
  | `GET /projects.json` | lists the projects |
  | `GET /projects/<id>/project.json` | opens one |
  | `PUT /projects/<id>/project.json` with `{expectedRevision, document}` | saves |
  | `PUT /projects/<id>/project.json` also takes `owner` | the page session saving: its draft goes |
  | `GET /projects/<id>/recovery.json` | the newest draft (`owner`, `others`), or null |
  | `PUT /projects/<id>/recovery.json` with `{owner, baseRevision, ...}` | keeps that page's draft: `{revision, stale}` |
  | `DELETE /projects/<id>/recovery.json?owner=<id>[&savedAt=<time>]` | that draft alone (a blank owner: the owner-less one), with `savedAt` only while it is still that one: `{dropped}` |
- **Safety of changes.** Changes are accepted only with JSON bodies and only from the viewer's own page: a loopback
  `Host` and a matching `Origin` when the browser sends one. Ids must be UUIDs, and file names come from the
  sanitised project name inside the folder, so no path can leave the projects folder.
- **Settings.** `viewer.py settings` shows and sets the folders: projects, builds, the LWR install, UDK 2011-09 and the
  optional lab copy. `viewer.py doctor` checks each prerequisite:
  - the projects and builds folders are writable;
  - Python 3.10 or later and PowerShell 7 are installed;
  - the LWR install is set, is not the lab copy, and its map packages match the exports' SHA-256. The setting names
    the game folder, or a folder holding game folders (`steamapps\common`). In a folder, the one without
    `XComLab-copy.txt` is taken, preferring Steam's `XCom-Enemy-Unknown`, then `XCom-Enemy-Unknown.LWR`, so it
    follows `switch_install`;
  - UDK has `UDK.com`, the XComGame stubs and a compiled `XComMapEd`.

### Prefab builder documents (12 November 2026, stage W)

`?prefab=new` or `?prefab=<id>` opens the editor on an empty synthetic scene. Its snapping origin stays `[0,0,0]`,
tile size `[96,96,64]`; drawing bounds expand independently. Negative X/Y and temporarily unsupported contents
remain editable. `/families.json` supplies common families and recipes with empty map assemblies and light rules.

Selection and complete builder saves use [prefab_document.js](../tools/viewer/web/prefab_document.js) for
normalization and the same supported-size policy. A builder save reads every live piece/light/box and every kept
unreadable record regardless of selection, visibility or cutaway. Actor, building and group ids, partners,
assembly tags, recipe metadata and donor hashes survive editing; deliberate deletion reconciles references.
Groups in the file carry no stamp provenance. Floor-box-only documents are valid.

Saves record `{key, name}` for a readable source recipe, with an optional `member` key for a member of a linked
assembly. `POST /prefabs/recover-sources {document}` checks the current sources and proposes replacements from
exact catalogue matches. It returns `{document, repaired, unresolved}` and writes no prefab file. Opening or
placing a prefab tries this when a source with a saved recipe can't be read. The builder applies the replacements
as one undoable edit after any pending restore-or-discard choice. Placement uses the replacements in its clip.
Both warn about unresolved pieces. The actor IDs, poses, groups, partners and floor boxes stay with the prefab.
Assemblies require a complete, unambiguous member match. A donor hash changes only when every reference left to
that donor is compatible with the updated hash.

The saved horizontal origin is the footprint's lowest tile corner. One offset applies to all pieces, including
unreadable ones, and every box; it never moves the working scene. Builder z stays zero. A map selection instead
uses the level at or below its lowest physical content. Missing geometry keeps its prior horizontal envelope
in working coordinates, enlarged by new content, never shrunk from visible geometry alone.

When a copied piece and the floor boxes have the same translation and quarter turn from a source building,
the editor and compiler use that source's authored floor entries, including cutdown floors and omissions.
Matching works with existing prefabs and allows the overlapping boxes found in buildings such as the Farm scout.
Independently edited pieces and floor layouts use the spatial membership rule.

The size a map can hold is **256 by 256 tiles (96 units each; 128 before 16 November 2026), z −192 through 2,112**,
with **0.5 unit** boundary tolerance (prefab plan 5.6b; 30 levels since 14 November 2026, 18 before). Height 0 is the builder's drawn grid; the
tile grid is 0 to 1,920 (30 levels of 64; the game's own maps go to 18, and over 1,152 `measure` says `tall`: not
played), and anything may stick out 192 units under or over it, where it has no tiles. A selection is saved with
its map's grid bottom at 0. `measure` also lists what reaches out of the grid (`outside`).
**The limits warn and refuse nothing** (14 November 2026): a prefab over them is saved and placed, `measure` gives
`warnings` (its `errors` is always empty and `supported` always true, kept for older callers), the builder's size
line and the prefab's card say so, and a prefab placed where it reaches out of the map's grid gets a banner.
The test stage is as tall as the prefab needs, from 18 levels to 30 (`prefab_stage.stage_levels`), and warns of a
piece of a grid family or a cover block whose pivot is outside the stage's grid.
Bounds include transformed mesh vertices, cover recipe boxes, building boxes and light positions, excluding light
influence radii and editor markers. [prefab_bounds.py](../tools/viewer/prefab_bounds.py) resolves the library's
geometry on supported saves and `POST /prefabs/size {document}`. Declared size cannot authorize a larger resolved
object. Missing sources are unknown; unreadable records can be preserved with size unverified. Placement compares
the prefab with the destination grid and warns.

**Fields this editor doesn't know** (14 November 2026): a prefab file may carry a field of a newer editor in the
document, a piece, a group, a building, a floor or a map entry when its value is small (a number, true or false,
null, a string of up to 200 characters, or a list of up to 16 such values; at most 8 in one record, the name a
plain word). It is kept through a save, `validate` gives the names, and the prefab's card says "Newer fields".
Anything larger or nested is refused, and so is any unknown field in a source (`from`), a `template`, a `recipe`,
a light's values or a cover's, which the compiler takes exactly.

Schema-1 reading/import/export retains its 512-tile safety bound. Old unsupported files open for repair; recovery
retains over-limit work. Client/server boundary fixtures are in
[prefab_size_cases.json](../tools/viewer/tests/prefab_size_cases.json), and the limits both sides share in
[limits.json](../tools/viewer/tests/limits.json). Ten building floors are the format limit (eight until
14 November 2026); a floor need not be 192 units high, and roofs count inside the physical height limit.

Save writes the next revision under a revision check. Save as normally allocates a new id; it may explicitly
replace a different prefab after confirmation, keeping that target's id and leaving the original unchanged.
It cannot replace the open prefab itself. A conflict offers overwrite or open saved. Dirty state uses stable
working content, not normalized coordinates or newly allocated identities.

`GET`, `PUT` and `DELETE /prefabs/<id>/recovery.json` keep drafts as projects do, one per page session. PUT accepts
`{owner, baseRevision, document, envelope, nextSerial}`: the complete document in working coordinates, the
conservative missing-geometry envelope (or null), and allocation state. Validation checks the full reference graph;
a stale base revision is kept and answered as stale (refused until 20 November 2026), a newer one refused. Client writes are ordered, and saves/discards wait for pending writes before clearing
recovery. Opening a map, project or prefab asks Save/Discard/Cancel; failed, conflicting or cancelled saves retain
the current scene. Approved navigation suppresses the browser's duplicate prompt; reload/tab close still use it.
New unnamed prefabs acquire recovery after their first save.

The T2 [stage converter](../tools/editor/prefab_stage.py) follows the Build's rules (14 November 2026;
plan, part R). A piece it can't build is **left out** and
named, and the test builds the rest: an unresolved actor, component or recipe, a piece the compiler leaves out
(the report's `leftOut`), a piece whose geometry can't be read. A donor map that is not the file the prefab was
saved from (another SHA-256) has its pieces matched by their recipes, with a warning. A pose off the grid and a
grid piece's pivot outside the stage's grid are warnings (a rotation that rounds is said nowhere since 14 November
2026). What it lists (`issues`: the pieces left out first, then the warnings, each with its piece's name) the test's
window shows before Launch, and `POST /prefab-tests/check {snapshot}` answers the same without building (the
builder's Problems chip).

**What refuses a build** (20 November 2026). A Build is refused only when there is nothing to build from: the
document's schema or mode, its source map or a source that doesn't match the export, its output names, an export
without the light data or the tile grid the edit needs, a family switched off; and when the project changes
nothing. Its own missions list and a map picture are changes, so a project that only narrows its missions or only
gives its map a picture builds. Every other part the compiler can't read or build is left out, named in the
report's `leftOut` (and the Build's window and manifest), and the rest builds: a piece's record, an area-light
binding, a group, a building record, the map size (`stage`: the map keeps its own), the spawn rule, `cleared` or a
part of it, `clearKeepsOutside`, a landing zone, and the missions list or an entry of it. A group's nesting is a note. A map
picture that can't be found or written is a note, and the map is built without one.

**Warnings and notes** (14 November 2026: warnings only for what can cause a problem in the game).
The compiler's report keeps `warnings` for what can (a piece that can't be walked on, climbed, covered behind or
hidden as it should, a landing on nothing, a mission script acting on the wrong actor) and `notes`
for what can't (loot counts, how a piece looks, an ignored field, an edit that changes nothing, a building box past
the grid, a piece that can't break with its group). The editor and the prefab test show the warnings only.

**Pieces of a kind the Build has not made before** (14 November 2026: build, don't leave out;
16 November: no message says a thing is untried). What only the editor's own gates held back is built, in a
project's Build and in the prefab test alike, with a warning only where the game shows something odd:

- a move or a copy of a class with no family of its own (`SkeletalMeshActor`, `FracturedStaticMeshActor` and the
  like): made in the map as any copy, with no warning;
- a part of a car, van, door or other assembly edited on its own (`assembly-split`): each part built as a piece
  of its own, the rest of the assembly left where it is;
- a tinted copy (`tint-dropped`: built without its tint) and a copy naming a partner that is not in the edit
  (`partner-dropped`);
- a piece of another map the library holds back as hidden, linked, of a kind not switched on, or waiting for a
  game test (`foreign-held`, a warning only for what shows in the game; the library panel tags such a piece by what
  shows, and lets it be placed).

The compiler marks these copies internally (the spec's copy object carries an `untried` list beside `labels`;
`native_split` passes it on and makes every such copy in the map). When the transplant or copy stage fails with
such copies in the edit, the Build takes out the ones the failure names, with the hide of a moved one (it stays
where the map has it), and runs the stages again: its `leftout` stage and the manifest's `leftOut` name them
(`untried-failed`). A failure that names none of them is the build's own, as before. Still left out by the compiler,
because nothing can be built from them: a piece missing from the export or whose donor map is missing, a broken
record, a piece of a streamed level, an unknown recipe, a piece whose closure can't be brought into another map,
and a volume (`not-a-piece`: the level volume holds the map's tile data). The view-only lights stay view only.

The stage converter still
refuses what is the stage's own: no blank map or a changed one, a prefab that leaves the squad no room on the
256 by 256 stage (`MAX_TILES`), an error of the document's, nothing left to build. It takes the blank map's actual squad positions, reserves their
tiles and a one-tile border, and fits the whole prefab footprint using a single tile-aligned translation.
The ground stays at the blank map's own level and the grid can grow from 36 by 36 to at most 256 by 256.
A footprint can satisfy the prefab size limit and still leave too little room for the squad.

The converter generates an ordinary project and a compiler report with test-local identities. The builder's
Test in game action submits the complete document to [prefab_tests.py](../tools/viewer/prefab_tests.py).
`POST /prefab-tests` accepts `{snapshot, requestId, quick?, unsaved?}`, where request IDs are UUIDs and
quick defaults to false. The same ID and payload return the same test. The server pins the base and donor
hashes, settings and exporter version, and shares the map export and project build runners.

`GET /prefab-tests/<id>.json` returns preparation, build, launch and cleanup status. The private snapshot,
compiled project, reports and artifacts stay under `<builds>/.prefab-tests/<id>/`. Cancellation uses
`POST /prefab-tests/<id>/cancel {}`. Launch uses `POST /prefab-tests/<id>/play {buildId, attemptId}`.
The server checks the immutable snapshot, exact package and live install before each launch. Launch attempts
are recorded before installing the test. A repeat request returns the recorded result. Reloading can follow
a test and offer launch for a ready build. Only the page that submitted a build can follow it into its first
launch automatically. Prefab rows offer Edit to open the builder.

The existing game watch restores the test install when XCOM closes. An interrupted test is reconciled on
restart before its files can be pruned. Inactive tests are kept for up to seven days, up to the newest 20.

## 6. Recipe matrix for M1

The plan's recipe qualification (section 6) applies. Each family's status, now:

| Family | Viewer (draw, move, copy, delete, save) | Build milestone | In game |
| --- | --- | --- | --- |
| Static scenery and props (`XComLevelActor`, `StaticMeshActor`) | Works | M1 | EXP-11 passes (runs 1 and 2). Effects placed around a piece stay behind when it moves (F-50) |
| Destructible props (`XComDestructibleActor` naming no partner) | Works | M1 (since 6 November 2026) | EXP-13 prepared; EXP-14 run 1: laser barrier copies give cover |
| Collectibles (`XComCollectible`, e.g. Temple Ship's power cores) | Works | M1 (since 6 November 2026), as destructible props. Since 7 November the editor's Build makes a copy as a collectible, which counts as mission loot as its original does; a deleted original no longer counts, and a moved one counts once. An option to mark a copy as not loot is for later | EXP-25 run 2 (CLrgScout_ForestTrench, 8 November): a power core copied out of the UFO; the mission ended, and three cores counted as loot where the map has two |
| Cars (a destructible body naming its glass as partner) | Works; car assemblies copy as one, with the recipe snap (Police Station's standalone light bars with their sedans, export 16) | Build since 8 November 2026 (brought forward from M2): body, glass and parts made in the map as one assembly, the glass's fragment columns carried with it | EXP-24 runs 1 (Bar: a moved sedan, a turned police car copy, a deleted SUV) and 2 (Police Station: a sedan with its standalone light bar, a police car copied half round, a crashed car copied, a save and reload with wrecks) |
| Vans (a car with a building of its own: its `XComBuildingVolume` and two floor volumes list its parts) | Works; a van's parts copy as one, with the recipe snap | Build since 8 November 2026 (brought forward from M2): the parts as a car's, and the van's building and floor volumes cloned with them, carried by the move, so its roof cuts away over a soldier inside (F-65) | EXP-24 runs 3 (Bar: a delivery van copied a quarter turn round, a short moving van moved, a moving van deleted, a save and reload with a soldier inside) and 4 (Police Station: delivery vans copied, moved and deleted) |
| Doors and windows (`XComInteractiveLevelActor`) | Works (reference pose); a leaf and its frame select as one, with the recipe snap | Framed doors build as assemblies. The native door recipe also builds frameless doors. | EXP-23 runs 1–3 pass for framed doors. EXP-39 passed for a cross-map alien door. The Farm scout door was checked in an offline prefab build. |
| Ladders | Works, with the recipe snap and its climb's ends marked (8 November 2026) | Build since 8 November 2026 (brought forward from M2): the Build makes them in the map (a small rebuild volume over the top tile first; the patch's helper hidden in a copy of the patch); a ladder whose foot or top has no floor is warned of (`ladder-climb`, a refusal until 13 November 2026) and built with no climb of its own; the floors counted are the map's, the project's flat pieces and invisible floors, on the grid's levels as the project has them | EXP-22 runs 1 (Bar) and 2 (CSmallScout_Farm) pass: routes up, none at a moved one's old place, the same after a save and reload |
| Fractured walls and floors (`XComFracLevelActor`, `XComDecoFracLevelActor` that are no car's glass) | Works (unfractured mesh), with the recipe snap: whole tiles, whole storeys and quarter turns from the original | Build since 9 November 2026, switched on before a game run: made in the map, each copy's fragment columns carried with it (`move_columns`), still listing the pieces and neighbouring walls copied with it by the same move and dropping the rest; a hidden wall leaves its neighbours' columns; a door's copy joins a wall copy's columns (F-69) | [EXP-28](experiments/EXP-28-fracturing-physics.md) run 1 passed (9 November, Bar: a wall copied with its doors, broken, saved and reloaded; a counter section moved; a wall deleted). A storey floor's copy got floor on the tiles with standing room over them only (F-71). Not played: a copy against other walls, a storey move |
| Skeletal physics props (`KAsset`) | Works (reference pose), any pose | Build since 9 November 2026, with the fracturing pieces: cloned in the map with its skeletal mesh component and light environment | EXP-28 run 1 (9 November, Bar): the map's corpses show in the game, and a copied, a moved and a deleted one seemed right when played by hand, without detail (F-70) |
| Mission-linked pieces | Works; from export 15 the inspector marks a piece the map's Kismet names (**Mission script**) | Copied, moved or deleted; moved or deleted, the compiler warns (`mission-linked`; a refusal from 8 to 13 November 2026), since the script acts on the hidden original, not on the copy. On Bar and Police Station these are the landing's grounded Skyranger and drop zone | Not tested in the game |
| Landing-zone pieces (archetype in `DGN_DropShipSoldierSpawn.*` or `VEH_Lv1Skyranger_MOD.Prefabs.*`, F-45) | Works; the inspector marks them **Landing zone** (served in `families.json` as `landing`) | Copied, moved or deleted; moved or deleted, the compiler warns (`landing-zone`; a refusal from 9 to 13 November 2026), since LWR's landing-zone mutator spawns the landing from the originals, so the dropship's landing breaks (F-45). On every cached map one to six pieces; some are also mission-linked | Not tested in the game |
| Hidden helpers, volumes | Inspect only; cannot be copied or deleted | Never built (`not-a-piece`) | — |
| Classes with no family of their own (`SkeletalMeshActor`, `FracturedStaticMeshActor`, ...) | Works | Built since 14 November 2026, left out by the Build only if it can't make them (`untried-failed`) | Offline: a moved and a copied `FracturedStaticMeshActor` of LSupplyShip_ForestGrove built in a quick build |

"Works" means the viewer draws, moves, copies, deletes and saves it. The last column says what was seen of the
kind in the game; the experiment notes and the [findings register](findings-register.md) hold the runs.

## 7. Streams and the variant record

The variant ships the base map under its own name and record. That record keeps the base map's streams and adds the
edit patch in a free slot (plan section 7). The full inventory, and the in-game check that such a record loads, are
in [EXP-10](experiments/EXP-10-variant-stream-slot.md). The check passed in the lab on 6 November: the travel loaded
slots 0 to 2, slot 5 came after the load, and `patch_bar`'s actors loaded once beside the edit patch.

**The base records** (LWR v2.06.03 `DefaultMaps.ini`, read only):

| Record | Line | Streams |
| --- | --- | --- |
| URB_Bar | 4 | 0 `CIN_DropshipIntros`, 1 `patch_bar`, 5 `patch_hide_randomized_objects` |
| TempleShip | 175 | 0 `TempleShip_Stream`, 1 `CIN_TP12A_ArriveTempleShip`, 5 `patch_hide_randomized_objects` |

**Across all 188 records:**
- 120 have gaps between their slots.
- No record uses a slot above 5.
- Slot 1 is not a patch in 47 records.

**The rule.** patchtool's `map.streamSlot "free"` puts the edit patch in the lowest slot the base record does not use:
slot 2 for both maps. A numbered slot replaces what is there, which is the old behaviour (slot 1, as EXP-07 and EXP-08
used). It now warns when the stream it replaces is not a patch (T-08).

**Choosing the base record.** The editor must choose the base record by `DisplayName`, not just by `Name`: 65 map
names have several records, and for 38 of them the free slot differs.

## 8. Effects, sounds and lens flares in the export (export 28; draw data: export 29)

**The background sound and the triggers counted (export 39).** The scene's `backgroundSound` is the map's sound bed
([background_sound.py](../tools/viewer/background_sound.py)): `{ event, op, cue, volume, fadeIn }`, the first
`SeqAct_PlaySound` with no target that a `SeqEvent_LevelLoaded` of the level leads to (within six links), with full
paths, or null where the map has none. `triggerCounts` is `{ volumes, water, sight }`: the level's listed
`TriggerVolume`s, those of them that are water (`bWaterVolume`), and its sight points: what a clear takes out
unless it keeps them. Both are absent for a streamed or previewed package. Nothing else of a map's Kismet is
exported.

Written 17 November 2026 for stage FX1 of the effects and sounds plan, when the export carried them for the page's
Effects view (Shift+X) to show only. The editing stages since (FX3 on) record them as `effect` and `sound` values
objects on overrides and added records (project and prefab schema 3): moved, copied, deleted and grouped with pieces,
and other maps' added, as the rows below say. [effects_metadata.py](../tools/viewer/effects_metadata.py) builds the
records; [test_effects_metadata.py](../tools/viewer/tests/test_effects_metadata.py) pins them to actors of the install.

**Where.** The map's own are the scene's `effects`, `sounds` and `flares` (sorted by actor). A mission stream's own are
its layer's (`streams[<name>].effects`, `.sounds`, `.flares`), with `layer: "stream"` and `stream` its name; the
cinematic streams (`CIN_`) are not read, as for pieces. `effectSystems` and `soundWaves` are keyed
`<package>|<object path>` and hold every system and wave the map's and its streams' records name. (Exports 28 to
36 also wrote `effectsMetadata`, whether class defaults came from the game's script packages or the module's
`CLASS_DEFAULTS`; nothing read it, and export 37 dropped it.)

**Every record:**

| Field | Meaning |
| --- | --- |
| `kind` | `effect` (an `Emitter`), `sound` (`AmbientSound` and its kin) or `flare` (a `LensFlareSource`) |
| `id` | `<prefix><kind>:<export index>`, as a light's `<prefix>light:<index>`; a stream's prefix is `stream-<name>-` |
| `sourcePackage`, `layer`, `actor`, `actorClass`, `component` | Its identity: package, `base` or `stream`, actor path, class, and its particle, audio or flare component's path |
| `location`, `rotation`, `scale`, `drawScale`, `drawScale3D` | Its pose: game units, rotator units, and its scale both as the product and as the two saved values |
| `listed` | Whether its level's actor list holds it (the game loads only those) |
| `prefab` | The prefab instance that placed it (short name), or null |
| `referencedBy` | What of its package's Kismet names it (`scene_metadata.kismet_references`, the reader lights and buildings use) |
| `attachedTo` | `{ actor, actorClass, bone }` from its saved `Base` / `BaseSkelComponent` / `BaseBoneName`, or null |
| `landingRole`, `landingActor` | Export 22's role where a landing names it (the grounded Skyranger's `emitter` and `sound`); whether a clear keeps it as the landing's (native_copy.landing_actor's archetype rule) |
| `carriedBy`, `carriedHow` | The mesh piece that carries it (export 23's place rule, `place`), or null; always null for sounds and flares in this stage |
| `can`, `why` | What the editor may do with it by its own data (`move`, `copy`, `delete`, `values`; a sound also `audition`) and, for each it may not, why in words. A stream's actor, an actor its level doesn't list and one that rides on another may do none of the first four; hearing a wave changes nothing, so `audition` depends only on the wave |

**Where a value comes from** (`startsOnFrom`, `valuesFrom`, `parametersFrom`): `actor` (saved by the actor or its own
component or node), `cue` (saved by a node of the cue asset a sound plays), `archetype` (an archetype the map holds),
`class` (the class's default in the game's script packages, or the type's zero where none saves it), `table`
(`CLASS_DEFAULTS`, where those packages can't be read), `unresolved` (an archetype in a package the map doesn't hold).

**An effect** adds `template` (its particle system's path, or null), `system` (its `effectSystems` key), `hidden`,
`floors` (every building floor whose `m_aCachedEmitters` names it: `{ building, floor }`, the building as
`buildings[].id`), `lit` (a light environment of its own), `componentPose` (`{ translation, rotation, scale }` of its
particle component), `startsOn` (its component's `bAutoActivate`: the class default is true) and `parameters`: the
`InstanceParameters` it saves (or its archetype does), each `{ name, type (its PSPT_ value), the fields it saves
(scalar, scalarLow, vector, vectorLow, colour, actor, material), offered }`, `offered` being `yes` (the system has a
parameter distribution of that name and kind), `otherKind` (of that name, the other kind), `no` or `unknown`.

**A system** (`effectSystems`): `path`, `name`, `package`, `fingerprint` (SHA-256 of everything under it, first 16
digits), `objects`, `bytes`, `lodLevels`, `fixedBox` (`{ used, min, max, valid }` or null), `emitters` (each its first
LOD level as read: `kind` sprite, mesh, ribbon, beam or trail, `lods`, `cookedOut`, `material`, `loops`, `duration`,
`delay`, `bursts`, `lifetime` [least, most] of its lifetime table) and `offers` (each particle parameter distribution:
`name`, `kind` scalar or vector, the `module` and `property` that read it, `modes`, `constant`, `input` and `output`
ranges, `colour`: whether it feeds a particle's start colour or colour over life). No "looping" or "plays once" is made
from `loops` (the plan's 2.2): the page says nothing of how long an effect lasts.

**An emitter's `draw`** (export 29, draw version 4 since export 31, 5 since export 32,
[effects_draw.py](../tools/viewer/effects_draw.py); the system's `drawVersion`): what the page draws its likeness from,
or `null` with `why` (a ribbon, no level of detail left, a mesh or material in another package, nothing spawns it, or
"it only sends events: nothing is seen": the engine's default particle material on an emitter with an event generator,
each fire's last emitter). `kind` sprite or mesh; `blend`, `lit`, `twoSided`,
`material`; a sprite's `textures` (`key` into the scene's `textures`, `name`, `parameter`, `alpha`, and the texture's
traits from its pixels, `texture_traits`: `grey`, `shape` (its alpha holds a shape), `packed` (pictures in its channels,
not a colour: no blue with red and green unrelated, or mostly blue to pink), `redShare`, `bright`); the colour and the
shape come from different textures (`pick_textures`): `picture` (the colour: the first texture with colour; an added
particle's first grey one; a see-through one's grey one only where it holds no shape and no packed one shapes; or null:
the particle's own colour), `opacity` (what of the picture shapes it: `alpha` where its alpha holds a shape,
`brightness`, or `none`), `mask` (the shape: beside a picture whose alpha holds its shape, only a texture named Mask,
Alpha or Gradient; else such a texture, then a grey one, one with an alpha shape, a packed one; with no picture, one
with an alpha shape, a packed one, a grey one) and
`maskFrom` (`brightness`, `alpha` or `red`: a packed texture's red channel, its brightness where its red is all but
empty); a normal map, distortion or reflection is neither. `colours`: the material's own colour parameters (vector
parameters named Color, Colour or Tint, not specular ones, through its parents: `{ name: [r, g, b] }`), which tint a
see-through particle with no picture (the night smoke's are all but black). Draw version 3's `opacity` `channel` (the
picture a packed texture: its red channel the opacity, no colour) is still read so by the page. A mesh emitter's
`mesh` (a key into `meshes`) and `materials`, with the same texture fields for the material it is drawn with; `facing` (`ScreenAlignment`), `subImages` [across, down], `interp`, `localSpace`,
`duration`, `loops`, `delay`; `rate`, `rateScale` and each followed module of `modules` (`cls` without
`ParticleModule`, then its properties) as numbers, flags and **distributions**; `bursts` (`count`, `countLow`,
`time`); `ignored`: the classes of its modules the drawing doesn't follow.

**Draw version 6** (export 46, the game-likeness plan's stage E1): a sprite emitter's `program` is its material's
program (section 9) sliced from its shaders for the particle vertex factory it draws with (`shaders.factory`: the
SubUV one for an emitter that steps through sub-images with an interpolation, the DynamicParameter one for one with a
dynamic parameter module, else the first of the others the material has), with `values` (the material's own vectors
and scalars) where a constant moves with time. A mesh emitter's `programs` holds one a drawn section (in `materials`'
order, null for one that can't be made), sliced from the local factory's shaders as a particle's. An emitter with a
program is drawn by it; the textures' roles above stay on the record for one without. The dynamic parameter module is
followed: its module record's `DynamicParams` lists its four values, each `{ value (a distribution), spawnOnly,
emitterTime, method (EDPV_UserSet, EDPV_VelocityX, ...Y, ...Z, ...Mag), scaleVelocity }`.

**A distribution** is one of:
- a table, `{ op, lock, per, chunk, scale, start, min, max, entries }`: the game's baked lookup table. An entry is
  `chunk` floats: the value (`op` 1), or its least then its most (`op` 2 random between them, 3 one or the other).
  The entry at a time is `(time - start) * scale`, blended to the next and held at the last; `lock` ties a vector's
  axes to one random number (4: all three). A cooked struct saves only its difference from the module class's
  default, so the shape is read through the archetype chain (`Defaults.chain`);
- a particle parameter, `{ parameter, kind, modes, constant, input, output }`: the value is the effect's saved
  instance parameter of that name, else `constant`;
- `{ unread: why }`: a curve the cook kept as an object, or a table of another shape; the page uses the module's
  neutral value.

**A sound** adds `startsOn` (`bAutoPlay`: true for `AmbientSound` and `AmbientSoundSimple`, false for the toggleable
one, unless saved), `cue` (`{ path, private: whether it is the sound's own, under the actor, sharedBy: how many other
sounds of the package play it }`), `node` (`{ path, nodeClass }` of its `SoundNodeInstance`), `nodes` (the classes of
its cue's nodes, counted), `waves` (`soundWaves` keys), `noSound` (why it reaches no wave, or null: "a sound slot names
no wave" and "its node has no sound slots" are the silent actors Firaxis left in) and `values` with `valuesFrom`
(`radiusMin`, `radiusMax`, `volumeMin`, `volumeMax`, `pitchMin`, `pitchMax`, `attenuate`, `spatialize`,
`distanceModel`, `lowPass`, `lowPassMin`, `lowPassMax`) from its own ambient node, or from the one attenuation node of
a cue asset (no volume or pitch then), `valuesNode` naming the node. `can.values` holds only for a simple sound whose
cue and node are its own.

**A wave** (`soundWaves`): `path`, `name`, `package`, `seconds`, `channels`, `rate`, `size`, `ogg` (the Ogg stream's
bytes) and `playable`: its PC bulk record (the second of five, read by its header) is in the export, uncompressed
(flags 0, element count equal to its size) and starts as an Ogg stream; otherwise `why` says what it is.
Since stage FX2 the page plays a playable wave through `GET`/`HEAD /maps/<id>/wave.ogg?id=<soundWaves key>`
([audio.py](../tools/viewer/audio.py)): the key's package is the map's own (its file checked against `source.sha256`)
or one of its `streams`; any other key is 404. The stream is checked as Ogg Vorbis before it is sent (a refusal is 422
with why) and answered as `audio/ogg` with its length, an ETag and single byte ranges.

**A flare** adds `template`, `colour` (its component's `SourceColor`, RGBA) and `hidden`; `can.values` is false (its
template and colour aren't edited in this plan). `can.copy` is false for one that names no template, and all of
`can` for one that rides on another actor.

**Lens flares edited** (stage FX6b, 17 November 2026). A flare's override (`target`, then `location` and `rotation`, or
`deleted: true`) and its copy (an added record of `kind: flare`) are checked as an effect's are and never carry a
values object (`flare`, `effect` or `sound` on one is malformed). The family is `flare` (it builds for every project since EXP-71 passed, 17 November 2026; before, `--family
flare`), the spec's and the native edit's object is `flares` (`moves`, `deletes`, `copies`, an always empty
`values`), and the Build's writer is [native_flares.py](../tools/bake/native_flares.py): a LensFlareSource owns its
LensFlareComponent alone, so a copy is those two exports, the flare template (the component's `Template`, or its
archetype's) shared; a flare is in no floor's list; a cleared map loses its flares but for one the project moves
itself, and copies are made after the clear. The library lists the base maps' flares as entries of `family` `flare`
(index 10: `kind` "Lens flare", `flare` the template's path, `colour`; recipe: class, template, colour, scale), a
copy of one names its map in `from` and is staged by the transplanter as an effect's is (the donor row's `flares`
counts them among its `effects`), and the compiler's foreign gate (`FOREIGN_FAMILIES`) lists no flare until the game
check.

**Edited** (stage FX3, 17 November 2026). The project records of section 4 (schema 3) name the effects and sounds by
their actors. The compiler ([effect_edits.py](../tools/editor/effect_edits.py) `effect_override`, `effect_add`) checks
each against the export (`can`, `why`: an edit the export says no to is an error with its reason; a stream's
too) and the family table (`effect`, `sound`: on since EXP-68 passed, 17 November 2026; held back, the Build takes them
only with `--family`, which `serve --family` passes on), and writes the spec's `effects` and `sounds`
objects: `moves` (`name`, `actorClass`, `location`, `rotation`, `before`), `deletes` (`name`, `actorClass`, `location`)
and `copies` (`id`, `name`, `source`, `actorClass`, `location`, `rotation`). A carried effect whose piece is moved,
copied or deleted goes with it (`carriedEffects`, export 23) unless its own record moves it, deletes it or says
`follow: none`. The Build ([native_effects.py](../tools/bake/native_effects.py), [native_sounds.py](../tools/bake/native_sounds.py),
after the carried pairs) writes a move into the actor's own pose, takes a deleted one out of the level's actor list
(its export stays: what names it still resolves), and clones a copy's actor with everything under it, references
remapped (a sound its own cue and node, so the copy's values are its own). Then every building's floors list the
effects anew in `m_aCachedEmitters` (what hides an effect with its floor): an effect no lane touches keeps its
listings; a moved one leaves its old ones and, like a copy, joins each upper floor (index 1 and up) whose box holds its
place within 2 units; a deleted one leaves; floor 0 never lists. The manifest's `nativeCopies` records each lane's
rows (`effects`, `sounds`: `how` moved, deleted or copied, a copy's export name) and each listing changed
(`floorEmitters`: `effect`, `building`, `floor`, `how` joined or left).

**From other maps** (stage FX4, 17 November 2026). The library's index (version 10 since stage FX6b's lens flares;
[library.py](../tools/viewer/library.py)) lists each base map's effects and ambient sounds as entries of `family`
`effect` or `sound`: `kind` the Add panel's ([effects_library.py](../tools/viewer/effects_library.py) `kind_of`, from
the system's or first wave's path), `recipe` and `key` (effects_library's: the fields that make two placed actors the
same thing to place), `system`, `emitters`, `lit`, `startsOn`, `scripted`, `waves`, `seconds`, `cue`, `sharedCue`, no
`mesh` or `size`, with `source`, `placed`, `closure` as a piece's. `blocked` is `unavailable` for one the editor can't
bring (effects_library `blocked`: a stream's, a landing's, one its export says can't be copied), `closure` for one
whose closure the transplant refuses or that names another actor of its map, `family` while the compiler's
`FOREIGN_FAMILIES` doesn't list its kind (it lists effects and sounds since EXP-69). `library.effect` gives one as a
template: its export 28 record (as this section describes, read from the donor), its system or waves, the donor's SHA-256 and its recipe key. An added record
whose `from` names another base map goes through `foreign_effect`: the library must have been scanned from the file
the install has (`donor-changed` otherwise), the record's key must be an entry of the right family, and an entry
`unavailable` or `closure` is refused (`not-placeable`); the record's own checks are a copy's (starts off, named by its
map's script, a landing's). Its copy in the lane carries `donor` {`package`, `sha256`}, and the report's `donors` lists
it. The Build stages each donor actor once in the map (transplant `stage_edit`, with the lanes' copies: alone, its
system, material or wave reused where the map has the same path, `sizes` noting one of another size), outside the
level's actor list, and rewrites the copies' `source` to the staged actor with `staged: true` and `donor.actor`; the
lane clones it as it clones one of the map's own (`lane_actor` takes a staged source only outside the list). The
manifest says `foreignEffects`, and each donor row its `effects`.

## 9. A material's program (game-likeness plan, track A; program version 1)

What a material's compiled shaders draw, sliced out of the game's SM3 bytecode by
[shader_slice.py](../tools/viewer/shader_slice.py) (`slice_material`) and run on numbers by
[shader_eval.py](../tools/viewer/shader_eval.py). The page carries out the same operations in its shader. A JSON
object:

- `version` (1), `shaders` (the shader types and IDs it was sliced from: `base`, `light`, `lightmap`), `ends`
  (`diffuse`: the form of the colour's mark, `mad` or `mul`), `unlit` (true when the base pass has no colour end:
  the material's whole colour is its glow), `distortion` (true when the game also draws it in its distortion pass,
  which bends what is behind it: the editor doesn't draw such a see-through material).
- `inputs`: {name: four component sources, null for a component not read}. A source is `{"kind": "uv", "channel",
  "component", "scale", "bias"}` (a mesh UV channel), `{"kind": "color", "component", "scale", "bias"}` (the
  vertex colour; the game gives white where a mesh has none), `{"kind": "const", "value"}` (with `"fog": true` for
  the vertex shader's height fog, given as none: the editor draws the map's fog itself),
  `{"kind": "cameraVector", "component"}` (the tangent-space vector to the camera, as the game's vertex shader makes
  it), `{"kind": "worldPosition", "component"}` (the position less the camera's, in game units: the game's
  translated world space; add `cameraWorldPos` for the absolute one), `{"kind": "worldTangent" | "worldBinormal" |
  "worldNormal", "component"}` (the tangent frame in the world, game axes), `{"kind": "tangentSign"}`,
  `{"kind": "vFace" | "vPos", "component"}`. A source may carry `"scale": -1`.
- `constants`: {name: {"value": [four numbers]}}: a literal, or the material's own value with `"uniform"` naming it
  (a parameter's name, or `scalars<n>` for four packed scalars): the page sets these per material, so instances of
  one material share one program. `"vector"` (an expression tree) or `"scalars"` (four trees or nulls) when the value
  moves with time (worked out again each frame); `"engine"` when the page sets it (`cameraWorldPos`,
  `objectWorldPos`, `twoSidedSign`, `screenPositionScaleBias`).
- `textures`: {name: {"parameter" (the texture parameter's name, absent for a texture the material samples by
  itself), "index" (the material resource's texture list: the default)}}. The export adds the texture it resolved.
- `code`: rows `{"op", "d" (the register written), "m" (its write mask), "s": [sources], "sat": 1?, "texld":
  "project" | "bias"?}`; a source is `{"r" (a register, input, constant or texture name), "w" (a four-letter
  swizzle), "n": 1? (negated), "a": 1? (absolute)}`. The operations are SM3's (`shader_slice.SUPPORTED`), one for one.
- `outputs`: {"diffuse", "specular", "power", "normal" (tangent space), "glow", "mask" (a cut-out: a pixel is cut
  where any component is below zero), "opacity"}: each `{"r", "m"}` (a register and the components it gives) or
  `{"value": [...]}` when it folds to constants. A glow of zero is left out.
- `refused`: {output: why} for each output the slice could not give (a short code, then what it found).

**A particle's program** (export 46, stage E1; effects_draw.py's `program` and `programs`): the same form, sliced from
the base pass alone (no `specular`, `power` or `normal`), with `shaders.factory` naming the vertex factory read. Its
inputs may also be `{"kind": "particleColor" | "dynamic" | "clipPosition", "component", "scale"?, "bias"?}` (the
particle's colour as the game gives it, its dynamic parameter, its clip-space position: what the page's particle shader
writes) and `{"kind": "subImageLerp", ...}` (the blend from its first sub-image to its second, whose UVs are UV
channels 0 and 1). A mesh particle's own colour and dynamic parameter, which reach its material as the vector
parameters MeshEmitterVertexColor and MeshEmitterDynamicParameter, are given as those inputs too. A texture may be
`{"engine": "sceneDepth"}`: the scene's depth behind the pixel (UE3's SceneColorTexture, of which only the alpha is
read), which the page gives as 1 / the distance in its alpha; the constant `{"engine": "minZMaxZRatio"}` is (-1, 1, 0,
0), so the shader's own sum turns that alpha into the distance. A `texld` row may say `"texld": "lod"` (read at the
level its coordinate's w names).

**On the export (export 43).** A material record's `program` is the form above, its textures resolved: each gains
`texture` (the export's texture key) and `srgb`, and the program `map` (`base`, `switches`, `matched`: exact or
values, `by`: instance or root). A material whose colour doesn't slice has no `program` and a diagnostic with the
reason; its other fields are as before (`diffuse` and the rest stay on every record). An object whose component
carries its own painted vertex colours names them in `paint`: a file beside the scene of four bytes a vertex, RGBA,
in its mesh's vertex order.

## 10. The map's atmosphere in the export (export 43)

`scene.json`'s `atmosphere` ([atmosphere.py](../tools/viewer/atmosphere.py) `read`; absent on a streamed level's
records, null where the WorldInfo can't be read): `world` holds `fog` (XComHeightFogParameters: `bEnabled`,
`FogDensity`, `FogHeight`, `FogHeightFalloff`, `FogMaxOpacity`, `StartDistance`, `LightTerminatorAngle`,
`OppositeLightBrightness`, `OppositeLightColor`, `LightInscatteringBrightness`, `LightInscatteringColor`) and
`postProcess` (PostProcessSettings: the bloom, the scene grade `Scene_*`, depth of field, the fog of war's colours,
the rim shader, each `bOverride_` flag), every member given: the map's saved value over the class default object's
over the struct's own (atmosphere_defaults.json); `saved` names the members the map itself saves; `class` the
WorldInfo's class; `environmentColor` its material parameters' environment colour. `volumes` lists each
PostProcessVolume: `name`, `box` (`min`, `max`, game units), `priority`, `enabled`, `unbound`, and `settings` (only
the members it saves, its `bOverride_` flags among them; the rest are Default__PostProcessVolume's, in the defaults
file's `volume`). Colours are 0 to 1 (a `Color` member's bytes over 255).

## 11. A piece's baked light in the export (exports 44 and 45)

Each of the map's own lightmapped pieces (and its streamed levels'; never a piece of another map, which is lit where it
is put) carries ([baked_light.py](../tools/viewer/baked_light.py); F-180, F-181):

- `lightmap`: `{colour, directions, scale0, scale1, uvScale, uvBias, channel}`. `colour` and `directions` name the two
  DXT1 atlases in `textures` (DDS files with their mips, read through sRGB), `scale0` and `scale1` the slots' `[r, g,
  b]` scales, `uvScale` and `uvBias` the piece's rectangle of the atlas, `channel` the mesh's lightmap UV channel. The
  light at a texel is colour x scale0 x dot(directions x scale1, b), b the squared saturated cosines of the material's
  tangent-space normal with UE3's three basis vectors (a third each for a flat normal).
- `sunShadow`: `{texture, uvScale, uvBias, factor}`, its shadow map of the map's dominant directional light: an 8-bit
  distance field (`factor` false) or a plain shadow factor, at the same lightmap UVs with its own scale and bias.
- `sunIrrelevant`: `true` in place of `sunShadow` (export 45) where the dominant light is on the component's
  `IrrelevantLights`: Lightmass found the piece wholly in its shadow, and the game draws none of that light on it
  (F-184). On the four maps of track H every lightmapped piece without a sun shadow map has it.

A piece with a vertex lightmap or none has none of these. The page packs the atlases into one colour and one direction atlas
(baked_rules.js) and lights each lightmapped piece by them in the Game look (baked_light.js): the sun's shadow from
its shadow map read as a distance field (B3), none of the sun where `sunIrrelevant`, the live shadow map otherwise.
A piece the project moved, deleted or relit (its lightmap names, in a light's `bakedInto`, a light the project moved,
changed or deleted), and every added piece, is lit live instead, its local lights scaled by the map's factor (the
lightmaps against the live lights at the lightmapped pieces' vertices, worked out as they load) and no sky light (B4).

**A baked Build's own light** (B4, 27 November 2026). A baked Build's manifest (one that relit the map: not quick, its
lighting changed; [build.py](../tools/editor/build.py) `built_actors`) adds:

- `builtActors`: the project's name for each piece the Build made as a new actor of the map, a moved original's actor
  or an added piece's output name (`added[].actor`), to the built actor's path; for a made piece the compiler cut into
  parts, the parts' actors in order. A copy keeps its components' names under its new actor (native_copy.py
  `clone_assembly`, transplant.py), so a piece's built component is the built actor's path with its component's last
  name.
- `relitComponents`: the components whose lightmap or sun shadow map the relight wrote (a moved original's copy and an
  added piece's among them).
- `asBuilt`: the project document as the Build read it.

GET `/projects/<id>/build-light.json` ([builds.py](../tools/viewer/builds.py), [build_light.py](../tools/viewer/build_light.py))
exports the light of the project's last package, where it is such a Build, into the cache the first time it is asked
for (`<cache>/builds/<buildId>/`: `light.json` and the atlases; the variant's older Builds' folders go), with export 45's
reader on the built package: each mesh component of every built actor `builtActors` names alone, and every relit one;
the textures the Build did not write are read from the game install's maps, where the base map's caches are. It
answers `{buildId, builtAt, revision, map, actors, project, pieces, textures, base}`: `actors` and `project` the
manifest's `builtActors` and `asBuilt`, `pieces` each built component's `lightmap` and `sunShadow` or `sunIrrelevant`
as above, `textures` the atlases' records (keys `build-<n>`, each with its texture's `name`), whose files are served
from `base` (`/cache-builds/<buildId>/`). 404: a quick Build, one that relit nothing, or no package. A relit atlas is
the map's own texture written again (lightmap_writer.py), so it carries the map's texture's name. The package
summary of `/projects/<id>/build.json` says `light: true` for such a Build.

The page asks for it once the Game look has been on, with a project open whose last package has it, on its map
([build_light.js](../tools/viewer/web/build_light.js)), and packs its atlases with the map's, one carrying a map
texture's name in that texture's place ([baked_light.js](../tools/viewer/web/baked_light.js) `setBuild`). A piece is as
built where its record now is the one `asBuilt` has, numbers within a thousandth and its flags, prefab, partner and
recipe left aside ([build_light_rules.js](../tools/viewer/web/build_light_rules.js) `sameRecord`); records are matched
by the groups' keys (`orig|<package>|<level>|<actor>`, `added|<actor>`). Each lightmapped piece as built is marked 5
to 7 (1 to 3 plus 4) and lit by: one of the map's left where the map has it, its own component's record in `pieces`
where the Build relit it, else the map's; a moved original or an added piece, its built component's record (none:
lit live). A piece changed since is lit live, and so are the pieces a light changed since reaches: its bake's pieces
(`bakedInto`) for one of the map's, and every piece its sphere meets where it stands now and where it stood as built.
Such a light's record carries `sinceBuild`, and lighting.js draws it live on the pieces as built; every other static
light is in their lightmaps (its fourth texel's third value). A made piece (drawn whole from its numbers) and a cover
block stay live. View options says, under the look, "Lit by the Build of <time> · <n> pieces changed since" (or
"nothing changed since"), in the Game look.

## What E0 still lacks

- **Resolver discrepancy fixtures.** Test cases capturing the known differences between the preview resolver and the
  builder (plan section 6, item 8): hide half-size 128 against the builder's 512, implicit ground Z 0 against about 4,
  copy rotations and classes the builder rejects, moved-door scaling and `BuildingFloor=-1`. They belong with E3,
  where the compiler replaces those paths.
- **Placement experiments for M1's static pieces** (plan section 10): specified in the plan, not yet run.

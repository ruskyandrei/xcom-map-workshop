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
- **No unlocking** (the user, 11 November 2026: "remove the lock/unlock/select stuff, just leave it to
  group/ungroup"). The editor has Group and Ungroup only: every group selects and moves as one, the editor writes
  `locked: true`, and a group saved unlocked before is opened as a group like any other. What the next points say of
  locked and unlocked groups is how it was until then; `locked` stays in the document for older files.
- **Lights and buildings are members** (11 November 2026; prefab plan 5.4a). A light is a member as a piece is: an
  original by `{ "package", "level", "actor" }`, an added one by `{ "added": actor }`. One of the project's buildings
  is `{ "building": id }`, its key `building|<id>`, and stands for all of its boxes. In the editor they move, turn,
  copy and go with the group whether drawn or not (outside the Buildings view, where each box is on its own); a
  selection with a building moves by whole tiles and levels and turns by quarter turns about the vertical. A copy
  of the group has copies of its lights and a new building with the same floors. A member naming a building that
  is gone is dropped on save. The compiler takes `{building}`, warns of one that is not the project's
  (`group-member`) and passes over lights and buildings in break together.
- **Groups nest** (11 November 2026; prefab plan 5.4): a member can be another group, `{ "group": id }`. A group is
  a member of one group at most and never inside itself; the compiler refuses otherwise (`group-nesting`), and the
  editor carries such a group unapplied. A piece picked selects the outermost locked group it is in; Unlock and
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
  pieces left in place included (`compiler.native_split`, `native_copy.link_children`). A group with a collectible's
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

## 4. The project document (schema 4)

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
Prefab files are schema 3 since stage FX6a (17 November 2026): a piece with a `kind` is a copy of a map's effect or
ambient sound, `{actor, kind: effect | sound, from: {package, level: base, actor}, location, rotation}` with the
values object of its kind at most (`effect` or `sound`, as an added record of a project has it), a member of the
prefab's groups by its `actor` as any piece is, its map among the `donors`. It has no components, partner, link or
recipe. The server reads prefab schema 1, 2 and 3 and stores 3; an editor before this stage refuses a schema 3 file
by its number ("A newer editor is needed to open it"). Since stage FX6b (17 November 2026) a piece may be a copy of
a map's lens flare, `{actor, kind: flare, from, location, rotation}`, never with a values object; the schema number
stays 3, and an editor of stage FX6a refuses such a file by the piece ("of a kind this editor doesn't know"). The
summary counts `effects`, `sounds` and `flares`.

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
| `buildings` | Optional (11 November 2026; prefab plan 5.1, stage B1). Buildings the Build makes from nothing: `{ "id": string, "name": string, "kind": "building" or "ufo", "floors": [{ "boxes": [[x0, y0, z0, x1, y1, z1]] }] }`, floor 0 first, the boxes in game units and unturned, at least one box a floor, at most 10 floors (8 until 14 November 2026). Which pieces each floor lists is not saved: the Build works it out from where the pieces stand (tools/bake/buildings.py). The compiler warns of a box outside the tile grid, and of one that overlaps a box of another floor or building (a refusal until 13 November 2026: warn, don't block). The page makes and fits their boxes in the Buildings view (Shift+B); a building it can't read is carried unchanged. Built since EXP-44 passed (11 November 2026). **The map's own buildings** (13 November 2026; map buildings plan, section 2): one the project changed is saved here too, with `replaces`, the map's building volume as a piece's target (`{ "package": "URB_Bar", "level": "base", "actor": "TheWorld.PersistentLevel.XComBuildingVolume_2" }`), and its id made from the actor (`map:PersistentLevel.XComBuildingVolume_2`), the same each time the map is opened, so a group's `{ "building": id }` holds for it with or without a record; each of its floors has `volumes` beside `boxes`, as long and sorted with them: the floor volume (short name) each box came from, `null` for a new box. A deleted one is `{ "id", "replaces", "deleted": true }`, with no floors. A map building with no record is the map's, as exported; the page saves only the ones whose floors, name or kind differ from the export (every box within 0.01 of its volume's), and the deleted ones. Its `name` starts as the actor's short name, its `kind` as `ufo` where the map's has `IsUfo`. A prefab never carries `replaces` or `volumes`: a building saved into one, or copied, is a new one. The buildings of streamed levels, vans' buildings and buildings with a floor that has no floor volume stay fixed (export 21's `van` and floors). |
| `stage` | Optional (11 November 2026; prefab plan 5.11), on any map (13 November 2026: before then the blank map or a cleared project alone): `{ "grid": [tiles across, tiles deep], "ground": false }` or `{ "grid": [tiles across, tiles deep, levels] }`, the tile grid made that large from its own corner and, with the third number, that many levels from its own bottom (1 to 128 tiles, 1 to 30 levels: 18 until 14 November 2026; over 18, the tallest of the game's own maps, the compiler warns `stage-levels-tall`: not played, and the Build gives the grid a cursor storey for each 192 units, ten at 30 levels). A map as it is, the blank map among them, may only grow, across and up (a map other than the blank map grown as it is is warned of: not played; with more levels, the Build adds even cursor storeys over the whole grid above the map's own cursor volumes, and stretches those reaching the old far X or Y side to the new one: shell.py grow_cursors); a cleared project's may also be smaller in any of the three (13 November 2026, Clear map plan, section 6): the corner and the bottom never move. `ground` false lays no ground over the new area (the Build lays the map's ground where it is laid as planes); `lines` and `hideGround` are the blank map's. |
| `cleared` | Optional (13 November 2026; Clear map plan, section 6): `true` says the map was cleared. The Build then takes out what the editor never showed (building, floor and cursor volumes, emitters, decals, lens flares, path-blocking, camera-blocking and damage volumes, the lights the editor cannot edit; never an actor of the landing's prefabs), puts the grid's cursor volumes and one rebuild volume over the whole grid, and a size may be set on any map. It deletes no piece: the cleared pieces are `deleted` overrides, as a hand delete makes them, so the page shows what the Build leaves. Absent or false: not cleared. |
| `clearKeepsOutside` | Optional (13 November 2026, the Clear map window's "Keep the scenery outside the play area"): `true` with `cleared` says the clear kept the scenery outside the play area. The page did not delete the pieces whose every part's box lies outside it, nor the lights placed outside it. The Build's clear_level then also leaves the lights, emitters, decals and lens flares whose Location is outside it. The play area here is the map's level volume and the grid as the project has it together, across (the compiler's `outside_box`, the page's `outsideBox`). Volumes and cover seeds go wherever they stand. Absent or false: everything goes. Without `cleared` it says nothing. |
| `landingZones` | Optional (13 November 2026; Clear map plan, section 4): the whole list of landing zones, in order: `{ "id": string, "location": [x, y, z], "direction": "north" \| "east" \| "south" \| "west", "kind": "normal" \| "inside" \| "alternate" \| "noEvac" \| "default", "missionType"?, "councilType"?, "alternate"?: { "location": [x, y, z], "direction" }, "lwr"?: false, "ew"?: true, "other"?: string }`. `location` is an LZArray line's `StartLoc` (the zone's ground is 64 under it), `direction` its `StartDir`, `kind` its `ESpawnLoc` (no line of the install uses the last three), `missionType` and `councilType` the mission it is kept for, as written, `alternate` its `AltSpawnLoc` and `AltSpawnDir`; `lwr` false writes no line for it; `ew` true (13 November 2026, the panel's Plain EW) makes it one of the map's own landings for plain EW; `other` keeps a line's fields the editor does not know, as written. The Build writes every zone with no `lwr: false` as one of the variant's LZArray lines, and the zones marked `ew: true`, in order, as the map's own landings moved in place, one for each landing the map has (the first marked zone is the first landing; marked zones beyond the map's count play under LWR only, a warning). A list with no zone marked goes by order: the first zones that name no mission. An empty list is no zone at all (a warning). Absent: the base map's lines are copied and its own landings left as they are, as before. A malformed zone is carried in its place. |
| `missions` | Optional (15 November 2026; mission types plan, Part D): the missions the variant serves, a list of at least one: `{ "record": i }` for the base map's record `i` (the export's `missions` order, its `DefaultMaps.ini` records in file order), or `{ "kind": "Abduction" \| "TerrorSite" \| "Special/Bomb" \| "Crash" \| "LandedUFO", "ship"?: "eShip_UFO..." }` for a kind a record alone gives the map (`missions.ADDED_KINDS`: made from the base map's abduction record; `ship` the UFO type, for the two UFO kinds only). The Build writes a record for each (base records in file order, then the added kinds), and nothing else; Play in game plays one of them. Absent: every record of the base map, as before. A list the Build can't write is an error. |
| `spawnRules` | Optional (18 November 2026; schema 4; the editor spawns plan, SP8): `{ "dropIns": "placed" }`, the Spawns flyout's "Scripted drop-ins land where placed". The Build then adds the variant to Long War's drop-in mutator's `ExcludeMaps` list (`DefaultRandomSpawns.ini`, section `[XComLZMutator.XComSpawnAlienMutator]`, after its ExcludeMaps lines, under a comment naming the editor and the project), so every scripted drop-in of every mission of the variant lands at its own point, with none of the mutator's overwatch and reveal; wave systems' drop-ins are never moved by Long War. The manifest's `config.dropInExclusion` says `{ file, section, line }` (and `why` where the build's install can't take it); Play in game and the campaign install plan the line again against the install (ledger keys `playExclusions` and `dropInExclusions`) and take it out only where it stands as written; nothing is written on plain Enemy Within, which plays them where placed already. The rule alone is work: a project with nothing else builds the map unchanged with it. Absent or null: the install's behaviour. Any other value is refused (`spawn-rules`); the page carries it as saved. |
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
    so opening it says which version, and listed with that error.
  - **`.workshop`** (hidden on Windows) keeps what stays on this computer, by id, so renaming a file keeps its backup
    and recovery.
  - **The earlier layout** (`<id>\project.json`, `project.prev.json`, `recovery.json`) is moved to this one the first
    time the server reads the folder. The id folder goes once empty; other files in it stay.
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

The size a map can hold is **128 by 128 tiles (96 units each), z −192 through 2,112**, with **0.5 unit** boundary
tolerance (prefab plan 5.6b; 30 levels since 14 November 2026, 18 before). Height 0 is the builder's drawn grid; the
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

**Warnings and notes** (14 November 2026, the user's word: warnings only for what can cause a problem in the game).
The compiler's report keeps `warnings` for what can (a piece that can't be walked on, climbed, covered behind or
hidden as it should, a landing on nothing, a mission script acting on the wrong actor, an untried piece) and `notes`
for what can't (loot counts, how a piece looks, an ignored field, an edit that changes nothing, a building box past
the grid, a piece that can't break with its group). The editor and the prefab test show the warnings only.

**Untried pieces** (14 November 2026, at the user's word: warn and build). What only the editor's own gates held
back is built with a warning, in a project's Build and in the prefab test alike:

- a move or a copy of a class with no family of its own (`class-untried`; `SkeletalMeshActor`,
  `FracturedStaticMeshActor` and the like): made in the map as any copy;
- a part of a car, van, door or other assembly edited on its own (`assembly-split`): each part built as a piece
  of its own, the rest of the assembly left where it is;
- a tinted copy (`tint-dropped`: built without its tint) and a copy naming a partner that is not in the edit
  (`partner-dropped`);
- a piece of another map the library holds back as hidden, linked, of a kind not switched on, or waiting for its
  game test (`foreign-untried`; the library panel shows it with an **Untried** tag and lets it be placed).

The compiler marks these copies `untried` (the spec's copy object carries an `untried` list beside `labels`;
`native_split` passes it on and makes every untried copy in the map). When the transplant or copy stage fails
with untried copies in the edit, the Build takes them out, with the hide of a moved one (it stays where the map
has it), and runs the stages again: its `leftout` stage and the manifest's `leftOut` name them
(`untried-failed`). A failure with no untried copy is the build's own, as before. Still left out by the compiler,
because nothing can be built from them: a piece missing from the export or whose donor map is missing, a broken
record, a piece of a streamed level, an unknown recipe, a piece whose closure can't be brought into another map,
and a volume (`not-a-piece`: the level volume holds the map's tile data). The view-only lights stay view only.

The stage converter still
refuses what is the stage's own: no blank map or a changed one, a prefab that leaves the squad no room on the
128 by 128 stage, an error of the document's, nothing left to build. It takes the blank map's actual squad positions, reserves their
tiles and a one-tile border, and fits the whole prefab footprint using a single tile-aligned translation.
The ground stays at the blank map's own level and the grid can grow from 36 by 36 to at most 128 by 128.
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
| Fractured walls and floors (`XComFracLevelActor`, `XComDecoFracLevelActor` that are no car's glass) | Works (unfractured mesh), with the recipe snap: whole tiles, whole storeys and quarter turns from the original | Build since 9 November 2026, switched on at the user's word before a game run: made in the map, each copy's fragment columns carried with it (`move_columns`), still listing the pieces and neighbouring walls copied with it by the same move and dropping the rest; a hidden wall leaves its neighbours' columns; a door's copy joins a wall copy's columns (F-69) | [EXP-28](experiments/EXP-28-fracturing-physics.md) run 1 passed (9 November, Bar: a wall copied with its doors, broken, saved and reloaded; a counter section moved; a wall deleted). A storey floor's copy got floor on the tiles with standing room over them only (F-71). Not played: a copy against other walls, a storey move |
| Skeletal physics props (`KAsset`) | Works (reference pose), any pose | Build since 9 November 2026, with the fracturing pieces: cloned in the map with its skeletal mesh component and light environment | EXP-28 run 1 (9 November, Bar): the map's corpses show in the game, and a copied, a moved and a deleted one "seemed ok" to the user, without detail (F-70) |
| Mission-linked pieces | Works; from export 15 the inspector marks a piece the map's Kismet names (**Mission script**) | Copied, moved or deleted; moved or deleted, the compiler warns (`mission-linked`; a refusal from 8 to 13 November 2026), since the script acts on the hidden original, not on the copy. On Bar and Police Station these are the landing's grounded Skyranger and drop zone | Not tested in the game |
| Landing-zone pieces (archetype in `DGN_DropShipSoldierSpawn.*` or `VEH_Lv1Skyranger_MOD.Prefabs.*`, F-45) | Works; the inspector marks them **Landing zone** (served in `families.json` as `landing`) | Copied, moved or deleted; moved or deleted, the compiler warns (`landing-zone`; a refusal from 9 to 13 November 2026), since LWR's landing-zone mutator spawns the landing from the originals, so the dropship's landing breaks (F-45). On every cached map one to six pieces; some are also mission-linked | Not tested in the game |
| Hidden helpers, volumes | Inspect only; cannot be copied or deleted | Never built (`not-a-piece`) | — |
| Classes with no family of their own (`SkeletalMeshActor`, `FracturedStaticMeshActor`, ...) | Works; the inspector's chip says **Untried** | Built untried since 14 November 2026 (`class-untried`), left out by the Build only if it can't make them | Not played. Offline: a moved and a copied `FracturedStaticMeshActor` of LSupplyShip_ForestGrove built in a quick build |

"Works" means the viewer draws, moves, copies, deletes and saves it. That says nothing about gameplay, collision,
cover or tile data: no edited piece has been built or tested in the game yet.

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

Written 17 November 2026 for stage FX1 of the effects and sounds plan. The export carries them for the page's
Effects view (Shift+X), which shows them and edits nothing. No project record names them yet: the records the editing
stages add (`effect` and `sound` values objects on overrides and added records, project and prefab schema 3) are the
plan's Part C and come with its stage FX3. [effects_metadata.py](../tools/viewer/effects_metadata.py) builds the
records; [test_effects_metadata.py](../tools/viewer/tests/test_effects_metadata.py) pins them to actors of the install.

**Where.** The map's own are the scene's `effects`, `sounds` and `flares` (sorted by actor). A mission stream's own are
its layer's (`streams[<name>].effects`, `.sounds`, `.flares`), with `layer: "stream"` and `stream` its name; the
cinematic streams (`CIN_`) are not read, as for pieces. `effectSystems` and `soundWaves` are keyed
`<package>|<object path>` and hold every system and wave the map's and its streams' records name. `effectsMetadata`
is `{ version: 1, defaults: "script" | "table" }`: whether class defaults came from the game's script packages or,
where those can't be read, from the module's `CLASS_DEFAULTS`.

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
their actors. The compiler ([compiler.py](../tools/editor/compiler.py) `effect_override`, `effect_add`) checks each
against the export (`can`, `why`: an edit the export says no to is an error with its reason; a stream's
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

## What E0 still lacks

- **Resolver discrepancy fixtures.** Test cases capturing the known differences between the preview resolver and the
  builder (plan section 6, item 8): hide half-size 128 against the builder's 512, implicit ground Z 0 against about 4,
  copy rotations and classes the builder rejects, moved-door scaling and `BuildingFloor=-1`. They belong with E3,
  where the compiler replaces those paths.
- **Placement experiments for M1's static pieces** (plan section 10): specified in the plan, not yet run.

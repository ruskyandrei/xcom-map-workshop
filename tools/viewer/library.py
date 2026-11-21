"""The library of pieces across the game's maps (private/plans/done/cross-map-assets-implementation-plan.md, X5).

Every Firaxis-cooked base map and stream the install's DefaultMaps.ini names is a donor: a piece any of them has
placed can be placed in another map (tools/bake/transplant.py brings it and what it depends on).

  scan(game, cache)            read every donor's placed pieces and write <cache>/library/index.json
  load_index(cache)            the index, or None
  piece(cache, game, source)   one piece as a template: its scene objects, meshes, materials and textures, exported
                               into <cache>/library/pieces/<donor>/<sha16>-v<exporter>/ on first request
  effect(cache, game, source)  one effect, ambient sound or lens flare as a template: its export 28 record, its
                               particle system or waves (the donor's described once, effects-v<n>.json in the same folder)
  load_state(), save_state()   the user's favourites and recently used pieces: library.json beside settings.json
  LibraryRunner                the scan as the server runs it: one at a time, with its progress

  python tools/viewer/viewer.py library scan [--cache <cache>] [--game <install>] [--jobs 6] [--only MAP ...]
  python tools/viewer/viewer.py library piece <donor map> <actor> [--cache <cache>] [--game <install>]

The index (version 1):

  { version, exporterVersion, scannedAt, seconds, floorKinds,
    donors:  [ {package, role: base | stream, sha256, size, mtime, pieces} ],
    entries: [ {key, name, family, kind, actorClass, mesh, recipe, size: [x, y, z], hidden,
                source: {kind: 'map', package, level: 'base', actor},
                placed: {maps, count, in: [donor numbers]}, floorMaps?: [donor numbers],
                placeable, reason, cuts: [classes], closure: {objects, bytes} | null} ] }

- An entry is one recipe: a placed actor's class, archetype, tint and, per mesh component, its mesh and the
  materials it overrides, all by object path, so the same piece in two maps is one entry. `key` is the recipe's hash.
- `source` is the exemplar to bring it from: of the maps that place it, the one whose copy brings the fewest bytes
  into a map that has none of it (`closure`), the map's and the actor's names breaking ties.
- `placeable` is the first release's scope: plain scenery (the compiler's scenery family) that is drawn in its map,
  has no partner, and whose closure the transplanter can bring. Anything else is listed with the `reason`.
- An entry is one actor, or one assembly (the compiler's: a car's body, glass and parts; a door's leaf and frame; a
  van's parts): `assembly` {family, members: how many}, `source` its pivot (the body, the leaf), `family` the
  assembly's. Its parts are not entries of their own. A van's closure counts its building and floor volumes.
- The base maps' effects (Emitter actors) and ambient sounds are entries too (the effects and sounds plan, Part E,
  stage FX4): `family` effect or sound, `kind` the panel's (effects_library.kind_of: Fire, Engines, ...), `recipe`
  effects_library's (so an effect placed the same way in two maps is one entry), no mesh or size; `system`,
  `emitters` (its emitters' kinds), `lit`, `startsOn`, `scripted` for an effect, `waves`, `seconds`, `cue`,
  `sharedCue` for a sound. One the editor can't bring (a landing's actor, one that rides on another, one that plays
  nothing) is listed `blocked` 'unavailable' with the reason. A stream's are a mission's own and are not scanned.
- The base maps' lens flares (LensFlareSource actors) are entries the same way since stage FX6b (index 10): `family`
  flare, `kind` effects_library.FLARE_KIND, `flare` its template's path and `colour` its colour; no system, no waves.
"""
import contextlib
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import threading
import time
import uuid

HERE = Path(__file__).resolve().parent
for folder in (HERE.parent / 'upk', HERE.parent / 'bake', HERE.parent / 'editor'):
    if str(folder) not in sys.path:
        sys.path.append(str(folder))

import atomic_files  # noqa: E402
from export_math import multiply, transform  # noqa: E402
from projects import ProjectError  # noqa: E402
from settings import resolve_game, settings_path  # noqa: E402

INDEX_VERSION = 10      # 2: an entry says what blocks it (`blocked`), and the family gate is the compiler's;
                        # 3: scanned with the families EXP-39 switched on, and assemblies are one entry each;
                        # 4: with cars and framed doors switched on (EXP-40 run 1); 5: and ladders (run 2);
                        # 6: an entry says how it is brought when that waits for a check (`held`);
                        # 7: vans come with their buildings, and EXP-41's two ways are switched on;
                        # 8: vans switched on (EXP-42); 9: the base maps' effects and ambient sounds (FX4: the
                        # number itself stayed 8 until FX6b); 10: the base maps' lens flares (FX6b)
PIECE_VERSION = 10      # 8: recipe identity for each member of a piece or assembly; 9: each member's own piece flags
                        # (export 27's pieceFlags) and its meshes' collision facts; 10: those flags really written (the
                        # exporter had left them out of every prefixed export, the library's too, 19 November 2026)
# the assemblies that are one entry (compiler.assemblies' families with more than one piece)
GROUPED = ('car', 'van', 'door')
STATE_SCHEMA = 'xcom-map-workshop/library-state'
STATE_VERSION = 1
RECENT = 30
STATE_WAIT = 10.0       # seconds a save of the favourites waits for another one to finish
LEVEL = 'TheWorld.PersistentLevel'
NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_-]*')
KEY = re.compile(r'[0-9a-f]{16}')
KINDS = {'XComDestructibleActor': 'Destructible', 'XComLevelActor': 'Scenery', 'StaticMeshActor': 'Scenery',
         'XComOpacityFadeLevelActor': 'Scenery',
         'XComFracLevelActor': 'Fracturing', 'XComDecoFracLevelActor': 'Fracturing',
         'XComInteractiveLevelActor': 'Door', 'KAsset': 'Physics', 'XComLadder': 'Ladder',
         'XComCollectible': 'Collectible'}
# the families a foreign piece can be of in the first release (the compiler's table names them)
# a reference cut to one of these is a link to another piece (a car's glass, a swap partner): an assembly's part
LINKED = ('XComDestructibleActor', 'XComFracLevelActor', 'XComDecoFracLevelActor', 'XComInteractiveLevelActor',
          'XComCollectible', 'XComLevelActor', 'StaticMeshActor', 'KAsset')
# properties whose cut references to other pieces leave a piece whole: the list of what it takes down with it
LOOSE_LINKS = ('AffectedChildren',)
# classes that are a map's own fixtures, not pieces
LEFT_OUT = ('XComLevelVolume', 'XComBuildingVolume', 'XComFloorVolume')
# the entries that are effects, ambient sounds and lens flares (no mesh: effect(), not piece(), reads them)
EFFECT_FAMILIES = ('effect', 'sound', 'flare')
# what an effect, sound or flare entry says of itself beside the mesh entries' fields
EFFECT_FIELDS = ('system', 'emitters', 'lit', 'startsOn', 'scripted', 'waves', 'seconds', 'cue', 'sharedCue', 'flare',
                 'colour')
EFFECTS_VERSION = 1     # a donor's effects record (effect_records)
THUMB_LIMIT = 512 << 10
PICTURE_LIMIT = 2 << 20     # a look picker's picture (the look picker plan, P0): a PNG of up to 512 by 384
PNG = b'\x89PNG\r\n\x1a\n'


def now():
    return datetime.datetime.now().isoformat(timespec='seconds')


def sha256(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def cooked_of(game):
    return Path(game) / 'XEW' / 'XComGame' / 'CookedPCConsole'


# ---------------------------------------------------------------------------------------------------- the donors
def donors(game):
    """[(name, role, path)] of the install's donor maps: the base maps and streams the map records the editor lists
    name (maplist.records), less what
    the editor installed there, that Firaxis cooked (licensee 64: Long War's own packages are another format's)."""
    import installs
    import maplist
    # kept for the install as it stands (the maps list's text and the cooked folder's listing): a prefab's pieces ask
    # one by one, and listing opens every map
    text = installs.maps_text(game)
    try:
        with os.scandir(cooked_of(game)) as found:
            listing = tuple(sorted((e.name, e.stat().st_size, e.stat().st_mtime_ns) for e in found
                                   if e.name.lower().endswith('.upk')))
    except OSError:
        listing = ()
    key = (str(game), hashlib.sha256(text.encode('utf-8', 'replace')).hexdigest(), hash(listing))
    kept = _DONORS.get(str(game))
    if kept and kept[0] == key:
        return list(kept[1])
    out = _list_donors(game, text)
    _DONORS[str(game)] = (key, out)
    return list(out)


def _list_donors(game, text):
    import maplist
    import mapsini
    base, streams = set(), set()
    # the records the editor works from: the live ones, and the tutorial map's, which the file comments out
    # (maplist.SWITCHED_OFF): a map that can be opened is a map whose pieces can be taken
    for line in maplist.records(text):
        name = mapsini.field(line, 'Name')
        if name:
            base.add(name)
        streams.update(mapsini.slot_streams(line))
    files = {p.stem.lower(): p for p in cooked_of(game).glob('*.upk')}
    out = []
    for name in sorted({n.lower() for n in base | streams}):
        path = files.get(name)
        if path is None or not NAME.fullmatch(path.stem):
            continue
        with path.open('rb') as f:
            head = f.read(8)
        if len(head) == 8 and struct.unpack_from('<HH', head, 4) == (845, 64):
            out.append((path.stem, 'base' if name in {n.lower() for n in base} else 'stream', path))
    return out


class _Nowhere:
    """A destination that has nothing: a closure against it is everything a piece needs."""
    assets = {}


def recipe_key(recipe):
    return hashlib.sha256(json.dumps(recipe, sort_keys=True, separators=(',', ':')).encode()).hexdigest()[:16]


_SCHEMAS = {}


def describe(p, actor, with_box=False):
    """What the scan records of the placed actor `actor` (an export of the package `p`'s level): dict(recipe, key,
    name, size, hidden, partner), with an optional world-space box. None for actors without a mesh or the sky."""
    parts, size, hidden = [], [0.0, 0.0, 0.0], bool(p.effective(actor, 'bHidden', False))
    scale = [v * p.effective(actor, 'DrawScale', 1) for v in p.effective(actor, 'DrawScale3D', [1, 1, 1])]
    box = None
    if with_box:
        actor_matrix = transform(p.effective(actor, 'Location', [0, 0, 0]),
                                 p.effective(actor, 'Rotation', [0, 0, 0]), scale)
    for c in p.children.get(actor, []):
        if 'MeshComponent' not in p.cls(c):
            continue
        mesh = p.effective(c, 'StaticMesh', 0) or p.effective(c, 'SkeletalMesh', 0)
        if mesh <= 0 or p.cls(mesh) not in ('StaticMesh', 'FracturedStaticMesh', 'SkeletalMesh'):
            continue
        overrides = [p.name(m) for m in p.refs(p.effective(c, 'Materials'))]
        parts.append(dict(mesh=p.name(mesh), materials=overrides))
        hidden = hidden or bool(p.effective(c, 'HiddenGame', False))
        bounds = p.native(mesh).unpack('7f')        # the mesh's bounds, read inside its export
        size = [max(a, abs(2 * e * s)) for a, e, s in zip(size, bounds[3:6], scale)]
        if with_box:
            component_scale = [v * p.effective(c, 'Scale', 1) for v in p.effective(c, 'Scale3D', [1, 1, 1])]
            component_matrix = transform(p.effective(c, 'Translation', [0, 0, 0]),
                                         p.effective(c, 'Rotation', [0, 0, 0]), component_scale)
            matrix = multiply(actor_matrix, component_matrix)[:3]
            centre = [row[3] + sum(v * b for v, b in zip(row, bounds[:3])) for row in matrix]
            half = [sum(abs(v * b) for v, b in zip(row, bounds[3:6])) for row in matrix]
            lo = [c - h for c, h in zip(centre, half)]
            hi = [c + h for c, h in zip(centre, half)]
            box = lo + hi if box is None else (
                [min(v, w) for v, w in zip(box[:3], lo)] + [max(v, w) for v, w in zip(box[3:], hi)])
    if not parts or parts[0]['mesh'].startswith('Skybox.'):
        return None
    parts.sort(key=lambda part: (part['mesh'], part['materials']))
    tint = p.effective(actor, 'TintColor', None)
    recipe = dict(actorClass=p.cls(actor), archetype=p.name(p.exports[actor - 1]['arch']), parts=parts,
                  tint=[round(float(v), 4) for v in tint] if tint else None)
    return dict(recipe=recipe, key=recipe_key(recipe), name=parts[0]['mesh'].rsplit('.', 1)[-1],
                size=[round(v, 1) for v in size], hidden=hidden, partner=p.effective(actor, 'HidingPartner', 0) > 0,
                **({'box': box} if with_box else {}))


def floor_piece_actors(p):
    """Use the same saved tile ownership and flat/decorative rules as the editor's floors.js."""
    from scene_metadata import saved_floor_tiles
    container = next((i for i in range(1, len(p.exports) + 1) if p.cls(i) == 'XComWorldDataContainer'), None)
    if container is None:
        return set()
    try:
        owners = {p.by_name.get(t['actor']) for t in saved_floor_tiles(p, container)}
    except (ValueError, IndexError, struct.error):
        return set()
    flat = {}
    for actor in sorted(owners - {None}):
        try:
            info = describe(p, actor, with_box=True)
        except (ValueError, IndexError, struct.error):
            continue
        if info and not info['hidden'] and info['box'][5] - info['box'][2] <= 48:
            flat[actor] = info
    floors = set()
    for actor, info in flat.items():
        x0, y0, z0, x1, y1, z1 = info['box']
        if len(info['recipe']['parts']) != 1 or info['partner']:
            continue
        x, y = (x0 + x1) / 2, (y0 + y1) / 2
        neighbours = (piece['box'] for other, piece in flat.items() if other != actor)
        decoration = z1 - z0 <= 8 and any(
            b[0] <= x <= b[3] and b[1] <= y <= b[4] and abs(b[5] - z0) <= 12 for b in neighbours)
        if not decoration:
            floors.add(actor)
    return floors


def level_assemblies(p):
    """The assemblies of a donor's level, as the compiler finds a map's (compiler.assemblies, from what an export says
    of each piece: its prefab, its partner, what its fragment columns break, its door frame, its building), read from
    the package without exporting it: {actor path: assembly}."""
    import compiler
    from scene_metadata import building_metadata, fragment_breaks, prefab_members
    level = p.by_name.get(LEVEL)
    drawn = []
    for actor in p.children.get(level, []) if level else []:
        for c in p.children.get(actor, []):
            if 'MeshComponent' not in p.cls(c):
                continue
            mesh = p.effective(c, 'StaticMesh', 0)
            if mesh <= 0:
                mesh = p.effective(c, 'SkeletalMesh', 0)
            if mesh > 0:
                drawn.append((actor, mesh))
                break
    prefabs = prefab_members(p)
    breaks = fragment_breaks(p, [a for a, _ in drawn])
    objects, meshes = [], {}
    for actor, mesh in drawn:
        partner = p.effective(actor, 'HidingPartner', 0)
        objects.append(dict(sourcePackage=p.path.stem, layer='base', actor=p.name(actor), actorClass=p.cls(actor),
                            location=p.effective(actor, 'Location', [0, 0, 0]), prefab=prefabs.get(actor),
                            partner=p.name(partner) if partner > 0 else None,
                            breaks=[p.name(v) for v in breaks.get(actor, [])], mesh=p.name(mesh)))
        meshes[p.name(mesh)] = dict(name=p.name(mesh))
    scene = dict(objects=objects, meshes=meshes)
    scene['buildings'] = building_metadata(p, objects)
    return compiler.assemblies(scene, p.path.stem)


def grouped(assembly):
    return bool(assembly) and assembly['family'] in GROUPED and len(assembly['members']) > 1


def describe_assembly(p, assembly):
    """describe() for an assembly: its pivot's, with the recipe of every part (so two cars with other parts are two
    entries), the size of the largest. None when a part draws nothing."""
    parts = {a: describe(p, p.by_name[a]) for a in assembly['members']}
    if any(v is None for v in parts.values()):
        return None
    head = parts[assembly['pivot']]
    recipe = dict(head['recipe'], assembly=assembly['family'],
                  members=sorted((parts[a]['recipe'] for a in assembly['members'] if a != assembly['pivot']),
                                 key=lambda r: json.dumps(r, sort_keys=True)))
    return dict(recipe=recipe, key=recipe_key(recipe), name=head['name'],
                size=[max(v['size'][k] for v in parts.values()) for k in range(3)],
                hidden=head['hidden'], partner=False)


def cut_links(p, plan):
    """The properties that hold a piece's cut references to other pieces (LINKED classes), by name: what reason_of
    judges a linked piece by. '?' for one that isn't found among the object's properties."""
    names = set()
    for by, ref in plan.cut:
        if p.cls(ref) not in LINKED or not by:
            continue
        found, raw = None, struct.pack('<i', ref)
        try:
            for (name, _), prop in p.properties(by)[0].items():
                value = prop.get('value')
                if value == ref or (isinstance(value, (bytes, bytearray)) and len(value) % 4 == 0
                                    and any(value[k:k + 4] == raw for k in range(4, len(value), 4))):
                    found = name
                    break
        except Exception:  # noqa: BLE001
            pass
        names.add(found or '?')
    return sorted(names)


def scan_donor(job):
    """One donor's placed pieces: dict(package, role, sha256, size, mtime, pieces [dict(actor, key, recipe, name,
    actorClass, size, hidden, partner, closure, refused, cuts)]) or dict(package, error)."""
    name, role, path = job
    path = Path(path)
    try:
        import schema as schema_module
        import transplant
        folder = str(path.parent)
        if folder not in _SCHEMAS:
            _SCHEMAS[folder] = schema_module.Schema(schema_module.build(path.parent))
        donor = transplant.Donor(path, _SCHEMAS[folder])
        p = donor.p
        stat = path.stat()
        pieces, closures = [], {}
        floor_actors = floor_piece_actors(p)
        try:
            assemblies = level_assemblies(p)
        except Exception:  # noqa: BLE001 (a map whose links can't be read lists its pieces one by one)
            assemblies = {}
        for actor in p.children.get(donor.level, []) if donor.level else []:
            cls = p.cls(actor)
            if cls in LEFT_OUT:
                continue
            assembly = assemblies.get(p.name(actor))
            what = describe_assembly(p, assembly) if grouped(assembly) else None
            if what is not None:
                if p.name(actor) != assembly['pivot']:
                    continue                    # a part: its assembly is the entry
                roots = [p.by_name[a] for a in assembly['members']]
                what['assembly'] = dict(family=assembly['family'], members=len(roots))
                if assembly['family'] == 'van':     # with its building and floor volumes
                    roots = roots + transplant.van_volumes(p, roots)
            else:
                what, roots = describe(p, actor), [actor]
            if what is None:
                continue
            key = what['key']
            if key not in closures:
                try:
                    plan = transplant.closure(donor, roots, _Nowhere)
                    closures[key] = dict(objects=len(plan.bring),
                                         bytes=sum(p.exports[i - 1]['size'] for i in plan.bring),
                                         cuts=sorted({p.cls(ref) for _, ref in plan.cut}), refused=None,
                                         links=cut_links(p, plan), shelled=False)
                    if plan.shelled:
                        # held for the check only where the whole Prefab could not come (a brush under it): the
                        # pieces that came with theirs before EXP-41 stay as they were for the user
                        try:
                            transplant.closure(donor, roots, _Nowhere, shells=False)
                        except (transplant.Refused, ValueError):
                            closures[key]['shelled'] = True
                except transplant.Refused as error:
                    closures[key] = dict(objects=None, bytes=None, cuts=[], refused=str(error))
                except ValueError as error:
                    closures[key] = dict(objects=None, bytes=None, cuts=[], refused='could not be read: %s' % error)
            closures[key].setdefault('links', [])
            closures[key].setdefault('shelled', False)
            found = closures[key]
            pieces.append(dict(what, actor=p.exports[actor - 1]['name'], actorClass=cls,
                               floor=actor in floor_actors and not what.get('assembly'),
                               closure=None if found['objects'] is None else dict(objects=found['objects'],
                                                                                 bytes=found['bytes']),
                               refused=found['refused'], cuts=found['cuts'], links=found['links'],
                               shelled=found['shelled']))
        # a stream's effects are a mission's own (plan Part E): the base maps' only
        effects = scan_effects(donor) if role == 'base' else []
        return dict(package=name, role=role, sha256=sha256(path), size=stat.st_size, mtime=int(stat.st_mtime),
                    pieces=pieces, effects=effects)
    except Exception as error:  # noqa: BLE001 (one unreadable donor must not stop the scan)
        return dict(package=name, role=role, error='%s: %s' % (type(error).__name__, error))


def scan_effects(donor):
    """A base donor's effects, ambient sounds and lens flares as library pieces (effects_library.py; the effects and
    sounds plan, Part E; flares since FX6b): [dict(kind, actor, key, recipe, name, actorClass, group, system, emitters,
    lit, startsOn, scripted, waves, seconds, cue, sharedCue, flare, colour, closure, refused, cuts, reason)]. `reason`: why one can't be brought
    (effects_library.blocked), with no closure worked out for it; `closure` what one copy brings into a map that has
    none of it, worked out once per recipe."""
    import effects_library
    import effects_metadata
    import transplant
    p = donor.p
    described = effects_metadata.describe(p)
    systems, waves = described['systems'], described['waves']
    out, closures = [], {}
    for record in described['effects'] + described['sounds'] + described['flares']:
        actor = p.by_name.get(record['actor'])
        if actor is None:
            continue
        key = effects_library.recipe_key(record)
        reason = effects_library.blocked(record)
        if reason is None and key not in closures:
            try:
                plan = transplant.closure(donor, [actor], _Nowhere)
                closures[key] = dict(closure=dict(objects=len(plan.bring),
                                                  bytes=sum(p.exports[i - 1]['size'] for i in plan.bring)),
                                     cuts=sorted({p.cls(ref) for _, ref in plan.cut}), refused=None)
            except transplant.Refused as error:
                closures[key] = dict(closure=None, cuts=[], refused=str(error))
            except ValueError as error:
                closures[key] = dict(closure=None, cuts=[], refused='could not be read: %s' % error)
        found = closures.get(key) if reason is None else None
        system = systems.get(record.get('system') or '') or {}
        heard = [waves[w] for w in record.get('waves') or [] if w in waves]
        cue = record.get('cue') or {}
        out.append(dict(kind=record['kind'], actor=p.exports[actor - 1]['name'], key=key,
                        recipe=effects_library.recipe(record), name=effects_library.name_of(record),
                        actorClass=record['actorClass'],
                        group=effects_library.kind_of(record['kind'], effects_library.kind_path(record)),
                        system=record.get('template') if record['kind'] == 'effect' else None,
                        flare=record.get('template') if record['kind'] == 'flare' else None,
                        colour=record.get('colour') if record['kind'] == 'flare' else None,
                        emitters=sorted({e['kind'] for e in system.get('emitters') or [] if e.get('kind')}),
                        lit=bool(record.get('lit')), startsOn=record.get('startsOn'),
                        scripted=bool(record.get('referencedBy')), waves=[w['path'] for w in heard],
                        seconds=max((w['seconds'] or 0 for w in heard), default=None) if heard else None,
                        cue=cue.get('path'), sharedCue=bool(cue) and not cue.get('private'),
                        **(found or dict(closure=None, cuts=[], refused=None)), reason=reason))
    return out


def effect_reason(piece, families, placeable=None):
    """reason_of for an effect, sound or lens flare: 'unavailable' (the editor can't bring it: its own map's data says why),
    'closure' (something it needs can't be brought, or it names something of its map that doesn't come with it) or
    'family' (the compiler's gate, FOREIGN_FAMILIES or `placeable`, which an experiment's build lifts)."""
    if placeable is None:
        import compiler
        placeable = compiler.FOREIGN_FAMILIES
    if piece.get('reason'):
        return 'unavailable', 'It can\'t be brought into another map: %s.' % piece['reason']
    if piece.get('refused'):
        m = (re.search(r': an? ([A-Za-z0-9_]+) has \d+ bytes of native data', piece['refused'])
             or re.search(r'\(([A-Za-z0-9_]+)\)', piece['refused']))
        return 'closure', ('It needs %s, which can\'t be brought into another map yet.'
                           % ('an object of class ' + m.group(1) if m else 'an object'))
    if piece.get('cuts'):
        return 'closure', ('It names %s of its own map, which doesn\'t come with it.'
                           % ' and '.join(piece['cuts']))
    family = piece['kind']
    if family not in placeable or not families.get(family, {}).get('builds'):
        what = families.get(family, {}).get('what') or 'a kind with no build recipe'
        return 'family', 'It is %s: these come from other maps with a later step.' % what
    return None, None


def reason_of(piece, family, families, placeable=None):
    """Why a piece can't be placed in another map yet: (what blocks it, the sentence), or (None, None). What blocks
    it is 'assembly' (it is linked to other pieces), 'hidden', 'closure' (something it needs can't be brought), or
    'family': nothing but the compiler's gate (FOREIGN_FAMILIES, or FOREIGN_ASSEMBLIES for an assembly; `placeable`
    in its place), which an experiment's build can lift."""
    whole = piece.get('assembly')
    if placeable is None:
        import compiler
        placeable = compiler.FOREIGN_ASSEMBLIES if whole else compiler.FOREIGN_FAMILIES
    # (a fracturing piece's cut references are its columns' lists of the pieces beside it, which the Build drops and
    # rebuilds for where the copy stands: no assembly; a whole assembly's are its glass's lists of its neighbours)
    # (a prop's list of the pieces it takes down with it, AffectedChildren, is emptied: it stands and breaks alone)
    loose = bool(piece.get('links')) and set(piece['links']) <= set(LOOSE_LINKS)
    if not whole and (piece['partner'] or (family != 'fracturing' and not loose and set(piece['cuts']) & set(LINKED))):
        return 'assembly', ('It is linked to other pieces (a car\'s body and its glass, a prop and what it turns '
                            'into): assemblies from other maps come with a later step.')
    if piece['hidden']:
        return 'hidden', 'It is hidden in its own map (a helper, not something to see).'
    if piece['refused']:
        m = (re.search(r': an? ([A-Za-z0-9_]+) has \d+ bytes of native data', piece['refused'])
             or re.search(r'\(([A-Za-z0-9_]+)\)', piece['refused']))
        return 'closure', ('It needs %s, which can\'t be brought into another map yet.'
                           % ('an object of class ' + m.group(1) if m else 'an object'))
    if family not in placeable or not families.get(family, {}).get('builds'):
        what = families.get(family, {}).get('what') or 'a piece of a kind with no build recipe'
        return 'family', 'It is %s: pieces of this kind from other maps come with a later step.' % what
    import compiler
    if set(held_by(piece, family)) & set(compiler.FOREIGN_UNCHECKED):
        return 'check', 'Pieces brought this way wait for their game test.'
    return None, None


def held_by(piece, family='', whole=None):
    """The ways a piece is brought that the compiler may hold for a game check (compiler.FOREIGN_UNCHECKED): 'links'
    (its list of other pieces is emptied), 'prefab' (its Prefab comes as a shell)."""
    out = []
    if not piece.get('assembly') and family != 'fracturing' and set(piece['cuts']) & set(LINKED) and piece.get('links'):
        out.append('links')
    if piece.get('shelled'):
        out.append('prefab')
    return out


def build_index(results, seconds=None):
    """The index from scan_donor's results."""
    import compiler
    from export import EXPORT_VERSION
    listed, failed, entries = [], [], {}
    for r in sorted(results, key=lambda r: r['package'].lower()):
        if 'error' in r:
            failed.append(dict(package=r['package'], role=r['role'], error=r['error']))
            continue
        number = len(listed)
        listed.append(dict(package=r['package'], role=r['role'], sha256=r['sha256'], size=r['size'],
                           mtime=r['mtime'], pieces=len(r['pieces']), effects=len(r.get('effects') or [])))
        for piece in r['pieces']:
            whole = piece.get('assembly')
            family = whole['family'] if whole else compiler.CLASS_FAMILY.get(piece['actorClass'], 'other')
            blocked, reason = reason_of(piece, family, compiler.FAMILIES)
            e = entries.setdefault(piece['key'], dict(
                key=piece['key'], name=piece['name'], family=family,
                kind={'car': 'Car', 'van': 'Van', 'door': 'Door'}[family] if whole
                else KINDS.get(piece['actorClass'], 'Other'), **({'assembly': whole} if whole else {}),
                actorClass=piece['actorClass'], mesh=piece['recipe']['parts'][0]['mesh'], recipe=piece['recipe'],
                size=piece['size'], hidden=piece['hidden'], count=0, donors=set(), floorMaps=set(), best=None))
            e['count'] += 1
            e['donors'].add(number)
            if piece.get('floor'):
                e['floorMaps'].add(number)
            # the exemplar: a placeable one before any other (then one only the family gate holds back), then the
            # fewest bytes brought, then by name
            closure = piece['closure']
            rank = ((None, 'family').index(blocked) if blocked in (None, 'family') else 2,
                    closure['bytes'] if closure else 1 << 62, r['package'].lower(), piece['actor'])
            if e['best'] is None or rank < e['best'][0]:
                e['best'] = (rank, r['package'], piece, reason, blocked)
        for piece in r.get('effects') or []:
            # an effect, sound or flare (scan_effects): one entry per recipe, its exemplar ranked as a piece's is
            blocked, reason = effect_reason(piece, compiler.FAMILIES)
            e = entries.setdefault(piece['key'], dict(
                key=piece['key'], name=piece['name'], family=piece['kind'], kind=piece['group'],
                actorClass=piece['actorClass'], recipe=piece['recipe'], **{k: piece.get(k) for k in EFFECT_FIELDS},
                count=0, donors=set(), floorMaps=set(), best=None))
            e['count'] += 1
            e['donors'].add(number)
            closure = piece['closure']
            rank = ((None, 'family').index(blocked) if blocked in (None, 'family') else 2,
                    closure['bytes'] if closure else 1 << 62, r['package'].lower(), piece['actor'])
            if e['best'] is None or rank < e['best'][0]:
                e['best'] = (rank, r['package'], piece, reason, blocked)
    out = []
    for e in entries.values():
        _, package, piece, reason, blocked = e.pop('best')
        count, where = e.pop('count'), sorted(e.pop('donors'))
        floor_maps = sorted(e.pop('floorMaps'))
        out.append(dict(e, source=dict(kind='map', package=package, level='base', actor=piece['actor']),
                        placed={'maps': len(where), 'count': count, 'in': where},
                        placeable=reason is None, reason=reason, blocked=blocked, cuts=piece['cuts'],
                        **({'floorMaps': floor_maps} if floor_maps else {}),
                        **({'held': held_by(piece, e['family'])} if held_by(piece, e['family']) else {}),
                        closure=piece['closure']))
    out.sort(key=lambda e: (e['name'].lower(), e['key']))
    return dict(version=INDEX_VERSION, exporterVersion=EXPORT_VERSION, scannedAt=now(), seconds=seconds, floorKinds=1,
                donors=listed, failed=failed, entries=out)


def index_path(cache):
    return Path(cache) / 'library' / 'index.json'


def scan(game, cache, jobs=None, progress=None, only=None):
    """Scan the install's donors (`only`: these map names) and write the index. progress(done, total, name).
    Returns the index."""
    import multiprocessing
    started = time.monotonic()
    wanted = donors(game)
    if only:
        names = {n.lower() for n in only}
        wanted = [d for d in wanted if d[0].lower() in names]
    if not wanted:
        raise ValueError('no donor maps were found in %s' % game)
    results = []
    if progress:
        progress(0, len(wanted), '')
    jobs = max(1, min(jobs or 6, os.cpu_count() or 1, len(wanted)))
    work = [(name, role, str(path)) for name, role, path in wanted]
    if jobs == 1:
        stream = map(scan_donor, work)
        pool = None
    else:
        pool = multiprocessing.get_context('spawn').Pool(jobs)
        stream = pool.imap_unordered(scan_donor, work)
    try:
        for r in stream:
            results.append(r)
            if progress:
                progress(len(results), len(wanted), r['package'])
    finally:
        if pool:
            pool.terminate()
            pool.join()
    index = build_index(results, round(time.monotonic() - started, 1))
    path = index_path(cache)
    path.parent.mkdir(parents=True, exist_ok=True)
    # (a temporary file of its own: two scans, the server's and the cache job's, never share one)
    atomic_files.write_text(path, json.dumps(index, separators=(',', ':')) + '\n', temp=part_of(path))
    return index


def load_index(cache):
    path = index_path(cache)
    if not path.is_file():
        return None
    try:
        index = json.loads(path.read_text(encoding='utf-8'))
    except ValueError:
        return None
    if index.get('version') != INDEX_VERSION:
        return None
    # Closure and link checks in a cached scan still apply when a family is enabled.
    import compiler
    for entry in index['entries']:
        if entry.get('actorClass') == 'XComOpacityFadeLevelActor' and not entry.get('assembly'):
            entry.update(family='scenery', kind='Scenery')
        if entry.get('blocked') == 'family':
            family = entry['family']
            allowed = compiler.FOREIGN_ASSEMBLIES if entry.get('assembly') else compiler.FOREIGN_FAMILIES
            if family in allowed and compiler.FAMILIES[family]['builds']:
                entry.update(placeable=True, blocked=None, reason=None)
    return index


def summary(index):
    entries = index['entries']
    return dict(scannedAt=index['scannedAt'], seconds=index.get('seconds'), donors=len(index['donors']),
                failed=index.get('failed') or [], entries=len(entries),
                placeable=sum(1 for e in entries if e['placeable']),
                pieces=sum(d['pieces'] for d in index['donors']), exporterVersion=index['exporterVersion'])


def stale(index, game):
    """The donors of the index that the install no longer has as scanned (by size and time), and the install's
    donors the index lacks: (changed, missing)."""
    have = {name.lower(): path for name, _, path in donors(game)}
    changed = []
    for d in index['donors']:
        path = have.pop(d['package'].lower(), None)
        if path is None:
            changed.append(d['package'])
            continue
        stat = path.stat()
        if (stat.st_size, int(stat.st_mtime)) != (d['size'], d['mtime']):
            changed.append(d['package'])
    return changed, sorted(p.stem for p in have.values())


# ---------------------------------------------------------------------------------------------------- one piece
def pieces_root(cache):
    return Path(cache) / 'library' / 'pieces'


def grid_origin(p):
    """The corner of a map's tile grid, [x, y, z] (its level volume's; tiles are 96 by 96 by 64 from there), or None.
    A piece that keeps the pose rule stands in another map as it stood on its own grid."""
    try:
        import native_copy
        g = native_copy.level_grid(p)
        return [round(float(g[k]), 4) for k in ('ox', 'oy', 'oz')]
    except Exception:  # noqa: BLE001 (a map without one level volume has no grid to go by)
        return None


_DIGESTS = {}
_DONORS = {}        # donors(): game folder -> (what the install looked like, the list)


def digest_of(path):
    """A map's SHA-256, worked out once for the file as it is (its size and time): every piece read asks for it."""
    stat = Path(path).stat()
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    if key not in _DIGESTS:
        _DIGESTS[key] = sha256(path)
    return _DIGESTS[key]


def pieces(cache, game, sources):
    """Many pieces exported at once (a prefab's first use): each as piece() does it, with the install's maps listed
    once and each map opened once. Gives, for each source, None or why it could not be had."""
    return [error.message if error else None for _, error in read_pieces(cache, game, sources)]


def read_pieces(cache, game, sources):
    """Yield (record, error) for each requested source, sharing the donor packages across the batch."""
    shared = {}
    for source in sources:
        try:
            yield piece(cache, game, source, shared), None
        except ProjectError as error:
            yield None, error
        except (OSError, ValueError, KeyError, struct.error) as error:
            yield None, ProjectError(422, 'it could not be read (%s)' % error, code='piece-unreadable')


def donor_area_lights(cache, folder, path, digest):
    """Index verified emitters and unresolved candidates once per donor package and matcher version."""
    from area_light_bindings import MATCHER_VERSION, export_records
    from compiler import ExportMissing, find_export

    index = folder / f'area-lights-v{MATCHER_VERSION}.json'
    if index.is_file():
        try:
            data = json.loads(index.read_text(encoding='utf-8'))
            if data.get('sha256') == digest:
                return data['owners']
        except (ValueError, KeyError):
            pass
    try:
        _, scene = find_export(cache, dict(source=dict(map=path.stem, sha256=digest)))
    except ExportMissing:
        scene = {}
    if (scene.get('lightMetadata') or {}).get('areaMatcher') != MATCHER_VERSION:
        with tempfile.TemporaryDirectory(prefix='area-lights-', dir=folder) as scratch:
            _, scene = export_records(path, scratch)
        if (scene.get('lightMetadata') or {}).get('areaMatcher') != MATCHER_VERSION:
            raise ValueError(f'{path.stem}: could not match generated area lights')
    owners = {}
    for light in scene.get('lights', []):
        if light.get('role') != 'area' or light.get('layer') != 'base':
            continue
        att = light.get('emitterAttachment') or {}
        if att.get('status') == 'verified':
            owner = att['owner']
            actor = owner['target']['actor']
            info = owners.setdefault(actor, dict(lights=[], unresolved=[]))
            fields = ('actor', 'actorClass', 'location', 'rotation', 'kind', 'role', 'radius', 'falloffExponent',
                      'innerConeAngle', 'outerConeAngle', 'color', 'brightness', 'enabled')
            info['lights'].append(dict({k: light[k] for k in fields if k in light}, component=owner['component']))
        elif att.get('status') in ('ambiguous', 'unmatched'):
            for actor in {c['actor'] for c in att.get('candidates', [])}:
                info = owners.setdefault(actor, dict(lights=[], unresolved=[]))
                info['unresolved'].append(light['actor'])
    atomic_files.write_text(index, json.dumps(dict(sha256=digest, owners=owners)), temp=part_of(index))
    return owners


def piece(cache, game, source, shared=None):
    """The piece `source` ({package, level, actor}) as a template (plan 4.3): dict(version, key, grid, source, base, objects,
    meshes, materials, textures, diagnostics). `grid` is its home map's tile grid origin (grid_origin). `key` is its recipe's, the index's entry key. `base` is the URL prefix of its folder; a mesh's and a texture's `url`
    are file names in it. Written on first request, read back after. `shared`: a dict a caller reading many pieces
    keeps between them (pieces()), for the install's map list and the packages opened."""
    from export import EXPORT_VERSION
    package, actor = str(source.get('package') or ''), str(source.get('actor') or '')
    if not NAME.fullmatch(package) or not NAME.fullmatch(actor):
        raise ProjectError(400, 'A piece is named by its map and its actor.')
    if (source.get('level') or 'base') != 'base':
        raise ProjectError(400, 'Only pieces of a map\'s own level can be taken.')
    shared = {} if shared is None else shared
    if 'donors' not in shared:
        shared['donors'] = donors(game)
    path = next((p for name, _, p in shared['donors'] if name.lower() == package.lower()), None)
    if path is None:
        raise ProjectError(404, 'The map %s, which the piece comes from, is not in the game install.' % package,
                           code='donor-missing')
    digest = digest_of(path)
    generation = '%s-v%d' % (digest[:16], EXPORT_VERSION)
    folder = pieces_root(cache) / path.stem / generation
    record = folder / (actor + '.json')
    kept = kept_piece(record)
    if kept is not None:
        return kept
    # written under the donor's lock (another process, the cache job, may be writing the same files): read again once
    # it is held, as it may have been written meanwhile
    with donor_lock(cache, path.stem):
        return kept_piece(record) or _make_piece(cache, actor, shared, path, digest, generation, folder, record)


PIECE_WAIT = 120.0      # seconds a piece waits for another process writing the same donor's pieces


@contextlib.contextmanager
def donor_lock(cache, package, wait=PIECE_WAIT):
    """The lock on a donor map's piece folders (<cache>/library/locks/<map>.lock, the operating system's: it holds
    across the server and the cache job's processes; review finding 48). ProjectError 409 when another holds it for
    longer than `wait` seconds."""
    from publication import FileLock
    lock = FileLock(Path(cache) / 'library' / 'locks' / ('%s.lock' % str(package).lower()))
    if not lock.acquire(wait):
        raise ProjectError(409, 'The pieces of %s are being written by another process (Cache everything); try again '
                                'in a moment.' % package, code='piece-busy')
    try:
        yield
    finally:
        lock.release()


def kept_piece(record):
    """The piece record kept at `record` when it is of this version, else None."""
    if record.is_file():
        try:
            kept = json.loads(record.read_text(encoding='utf-8'))
            if kept.get('version') == PIECE_VERSION:
                return kept
        except ValueError:
            pass
    return None


def part_of(path):
    """A temporary file beside `path`, of its own name (two writers never share one)."""
    return path.with_name('%s.%s.part' % (path.name, uuid.uuid4().hex[:8]))


def _make_piece(cache, actor, shared, path, digest, generation, folder, record):
    """piece()'s export of a piece not kept yet, with its donor's lock held."""
    from export import EXPORT_VERSION, Exporter
    from package import Package
    p = shared.setdefault('packages', {}).get(str(path))
    if p is None:
        p = shared['packages'][str(path)] = Package(path)
    index = p.by_name.get(LEVEL + '.' + actor)
    if index is None:
        raise ProjectError(404, '%s has no piece called %s.' % (path.stem, actor), code='piece-missing')
    folder.mkdir(parents=True, exist_ok=True)
    exporter = Exporter(p, folder, namespace='lib-' + path.stem)
    # an assembly's part gives the whole assembly: every part's components, with the links the page and the compiler
    # keep them together by (prefab, partner, what the glass's columns break)
    try:
        found = shared.setdefault('assemblies', {})
        if str(path) not in found:
            found[str(path)] = level_assemblies(p)
        assembly = found[str(path)].get(p.name(index))
    except Exception:  # noqa: BLE001
        assembly = None
    what = describe_assembly(p, assembly) if grouped(assembly) else None
    members = [p.by_name[a] for a in assembly['members']] if what else [index]
    if what:
        from scene_metadata import fragment_breaks, prefab_members
        exporter.prefabs = prefab_members(p)
        exporter.breaks = fragment_breaks(p, members)
    else:
        what = describe(p, index) or {}
    objects = []
    for member in members:
        for c in p.children.get(member, []):
            if 'MeshComponent' not in p.cls(c):
                continue
            try:
                obj = exporter.component(member, c)
            except (ValueError, OSError, struct.error) as error:
                exporter.warn(p.name(c), error)
                continue
            if obj:
                objects.append(obj)
    if not objects:
        raise ProjectError(422, '%s in %s has nothing to draw.' % (actor, path.stem))
    from area_light_bindings import component_settings
    area = {}
    if any(component_settings(p, p.by_name[o['component']]).get('bUseEmissiveForStaticLighting') for o in objects):
        known = shared.setdefault('area_lights', {})
        if path not in known:
            known[path] = donor_area_lights(cache, folder, path, digest)
        area = {p.name(member): known[path][p.name(member)] for member in members if p.name(member) in known[path]}
    from scene_metadata import building_metadata
    floor_metadata = shared.setdefault('floor_metadata', {})
    if path not in floor_metadata:
        source_buildings = []
        listings = {}
        for building in building_metadata(p, []):
            source_buildings.append(dict(id=building['id'], floors=[dict(boxes=f['boxes']) for f in building['floors']]))
            for floor in building['floors']:
                for member in floor['members']:
                    listings.setdefault(member['actor'], []).append(dict(building=building['id'], floor=floor['index'],
                                                                        cutdownFloor=member['cutdownFloor']))
        floor_metadata[path] = source_buildings, listings
    source_buildings, listings = floor_metadata[path]
    for obj in objects:
        obj['floors'] = listings.get(obj['actor'], [])
    # Builder ground readings need the same collision as a map's own pieces.
    from collision import line_collision
    collision = {}
    for key, mesh in exporter.meshes.items():
        index = p.by_name.get(mesh['name'])
        if index and p.cls(index) == 'StaticMesh':
            try: collision[key] = line_collision(p, index)
            except (ValueError, KeyError, struct.error): pass
    recipes = {}
    if what.get('key'):
        for member in members:
            recipe = dict(key=what['key'], name=what['name'][:200])
            if len(members) > 1:
                recipe['member'] = describe(p, member)['key']
            recipes[p.name(member)] = recipe
    out = dict(version=PIECE_VERSION, exporterVersion=EXPORT_VERSION, key=what.get('key'), recipes=recipes,
               grid=grid_origin(p),
               **({'assembly': dict(family=assembly['family'], members=assembly['members'], pivot=assembly['pivot'],
                                    leaves=assembly['leaves'])} if len(members) > 1 else {}),
               source=dict(kind='map', package=path.stem, level='base', actor=actor, sha256=digest),
               base='/cache-library/%s/%s/' % (path.stem, generation), objects=objects, meshes=exporter.meshes,
               materials=exporter.materials, textures={k: v for k, v in exporter.textures.items() if v},
               diagnostics=exporter.diagnostics, collision=collision, buildings=source_buildings, areaLights=area)
    atomic_files.write_text(record, json.dumps(out) + '\n', temp=part_of(record))
    return out


# ---------------------------------------------------------------------------------------------------- effects and sounds
def donor_path(game, package, shared):
    """The install's file of the donor map `package` (ProjectError 404 donor-missing when it has none)."""
    if 'donors' not in shared:
        shared['donors'] = donors(game)
    path = next((p for name, _, p in shared['donors'] if name.lower() == str(package).lower()), None)
    if path is None:
        raise ProjectError(404, 'The map %s, which the effect comes from, is not in the game install.' % package,
                           code='donor-missing')
    return path


def effect_records(cache, game, package, shared=None):
    """A donor map's effects, ambient sounds and lens flares as export 28 describes a map's (effects_metadata.describe), kept in
    its pieces folder (<cache>/library/pieces/<donor>/<generation>/effects-v<n>.json) once read: dict(version,
    metadata, source {kind 'map', package, level, sha256}, effects, sounds, flares, systems, waves). `shared` as
    piece()'s."""
    import effects_metadata
    from export import EXPORT_VERSION
    from package import Package
    shared = {} if shared is None else shared
    path = donor_path(game, package, shared)
    digest = digest_of(path)
    folder = pieces_root(cache) / path.stem / ('%s-v%d' % (digest[:16], EXPORT_VERSION))
    record = folder / ('effects-v%d.json' % EFFECTS_VERSION)
    known = shared.setdefault('effects', {})
    if str(record) in known:
        return known[str(record)]
    if record.is_file():
        try:
            kept = json.loads(record.read_text(encoding='utf-8'))
            if (kept.get('version') == EFFECTS_VERSION and kept.get('metadata') == effects_metadata.METADATA_VERSION
                    and kept['source']['sha256'] == digest):
                known[str(record)] = kept
                return kept
        except (ValueError, KeyError, TypeError):
            pass
    p = shared.setdefault('packages', {}).get(str(path))
    if p is None:
        p = shared['packages'][str(path)] = Package(path)
    out = dict(version=EFFECTS_VERSION, metadata=effects_metadata.METADATA_VERSION,
               source=dict(kind='map', package=path.stem, level='base', sha256=digest), **effects_metadata.describe(p))
    with donor_lock(cache, path.stem):
        folder.mkdir(parents=True, exist_ok=True)
        atomic_files.write_text(record, json.dumps(out) + '\n', temp=part_of(record))
    known[str(record)] = out
    return out


def effect_draw(cache, game, package, system, shared=None):
    """What the page draws a donor map's particle system from (the effects and sounds plan, Part J1; export 29's
    effects_draw): its record with `draw` on each emitter, and the textures, meshes and materials the drawing names,
    written into the donor's pieces folder as a piece's are: dict(version, system, base, meshes, materials,
    textures). Kept beside them once read (draw-v<n>-<the system's fingerprint>.json). `system` is its record as
    effect_records gives it."""
    import copy
    import effects_draw
    import effects_metadata
    from export import EXPORT_VERSION, Exporter, compiled_textures
    from package import Package
    shared = {} if shared is None else shared
    path = donor_path(game, package, shared)
    digest = digest_of(path)
    generation = '%s-v%d' % (digest[:16], EXPORT_VERSION)
    folder = pieces_root(cache) / path.stem / generation
    record = folder / ('draw-v%d-%s.json' % (effects_draw.DRAW_VERSION, system['fingerprint']))
    if record.is_file():
        try:
            kept = json.loads(record.read_text(encoding='utf-8'))
            if kept.get('version') == effects_draw.DRAW_VERSION:
                return kept
        except ValueError:
            pass
    p = shared.setdefault('packages', {}).get(str(path))
    if p is None:
        p = shared['packages'][str(path)] = Package(path)
    defaults = shared.setdefault('effect_defaults', {}).get(str(path))
    if defaults is None:
        defaults = shared['effect_defaults'][str(path)] = effects_metadata.Defaults(p)
    with donor_lock(cache, path.stem):      # its textures and meshes go into the donor's piece folder
        folder.mkdir(parents=True, exist_ok=True)
        exporter = Exporter(p, folder, namespace='lib-' + path.stem)
        drawn = copy.deepcopy(system)
        effects_draw.attach(p, defaults, {'one': drawn}, exporter, compiled_textures, effects_draw.RULES, exporter.warn)
        out = dict(version=effects_draw.DRAW_VERSION, system=drawn, base='/cache-library/%s/%s/' % (path.stem, generation),
                   meshes=exporter.meshes, materials=exporter.materials,
                   textures={k: v for k, v in exporter.textures.items() if v})
        atomic_files.write_text(record, json.dumps(out) + '\n', temp=part_of(record))
    return out


def effect(cache, game, source, shared=None):
    """One effect, ambient sound or lens flare of a donor map, `source` ({package, level, actor}), as a template for the page
    and the compiler (the effects and sounds plan, Part E): dict(version, kind, key, source {kind 'map', package,
    level, actor, sha256}, record (export 28's, as effects_metadata gives it), systems {id: its particle system},
    waves {id: each wave it reaches}). `key` is its recipe's (effects_library.recipe_key), the index's entry key.
    An effect's system comes with its draw data (effect_draw), and `draw`: dict(base, meshes, materials, textures),
    what that drawing names. A lens flare's template has its record alone (no system, no waves, no drawing)."""
    import effects_library
    package, actor = str(source.get('package') or ''), str(source.get('actor') or '')
    if not NAME.fullmatch(package) or not NAME.fullmatch(actor):
        raise ProjectError(400, 'An effect is named by its map and its actor.')
    if (source.get('level') or 'base') != 'base':
        raise ProjectError(400, 'Only the effects, sounds and lens flares of a map\'s own level can be taken.')
    records = effect_records(cache, game, package, shared)
    want = LEVEL + '.' + actor
    record = next((r for r in records['effects'] + records['sounds'] + (records.get('flares') or [])
                   if r['actor'] == want), None)
    if record is None:
        raise ProjectError(404, '%s has no effect, ambient sound or lens flare called %s.' % (records['source']['package'], actor),
                           code='effect-missing')
    systems = records.get('systems') or {}
    waves = records.get('waves') or {}
    one, draw = {}, None
    if systems.get(record.get('system')):
        one = {record['system']: systems[record['system']]}
        try:
            drawn = effect_draw(cache, game, package, systems[record['system']], shared)
            one = {record['system']: drawn['system']}
            draw = {k: drawn[k] for k in ('base', 'meshes', 'materials', 'textures')}
        except (OSError, ValueError, KeyError, IndexError, struct.error):
            pass                # its marker and its values without a likeness
    return dict(version=EFFECTS_VERSION, kind=record['kind'], key=effects_library.recipe_key(record),
                source=dict(records['source'], actor=actor), record=record, systems=one, draw=draw,
                waves={w: waves[w] for w in record.get('waves') or [] if w in waves})


def read_effects(cache, game, sources):
    """Yield (template, error) for each requested effect or sound, the donors read once for the batch."""
    shared = {}
    for source in sources:
        try:
            yield effect(cache, game, source, shared), None
        except ProjectError as error:
            yield None, error
        except (OSError, ValueError, KeyError, struct.error) as error:
            yield None, ProjectError(422, 'it could not be read (%s)' % error, code='effect-unreadable')


# ---------------------------------------------------------------------------------------------------- every piece ahead
# The cache filled ahead of use (precache.py, the page's Settings menu): every piece the index lists, exported as
# piece() exports one on first use, a donor map to a worker.
_RECORD_HEAD = re.compile(rb'\{"version": (\d+)')
_QUEUE = None


def record_kept(record):
    """Whether a piece's record is in the cache as this version writes it (its first bytes say)."""
    try:
        with open(record, 'rb') as f:
            m = _RECORD_HEAD.match(f.read(40))
    except OSError:
        return False
    return bool(m) and int(m.group(1)) == PIECE_VERSION


def piece_plan(cache, game, index):
    """What of the index's pieces the cache holds, by donor map as the install has it now:
    [dict(package, path, folder, actors, missing)], `actors` the index's pieces of the map and `missing` those with
    no record in the map's current generation. A donor the install lacks is left out."""
    from export import EXPORT_VERSION
    have = {name.lower(): path for name, _, path in donors(game)}
    scanned = {d['package'].lower(): d for d in index['donors']}
    by = {}
    for entry in index['entries']:
        if entry.get('family') in EFFECT_FAMILIES:
            continue        # nothing to export ahead: effect() reads the donor's records on first use
        source = entry['source']
        by.setdefault(source['package'], []).append(source['actor'])
    plan = []
    for package, actors in sorted(by.items()):
        path = have.get(package.lower())
        if path is None:
            continue
        stat, known = path.stat(), scanned.get(package.lower())
        same = known and (stat.st_size, int(stat.st_mtime)) == (known['size'], known['mtime'])
        digest = known['sha256'] if same else digest_of(path)
        folder = pieces_root(cache) / path.stem / ('%s-v%d' % (digest[:16], EXPORT_VERSION))
        actors = sorted(set(actors))
        plan.append(dict(package=path.stem, path=path, folder=folder, actors=actors,
                         missing=[a for a in actors if not record_kept(folder / (a + '.json'))]))
    return plan


def _precache_queue(queue):
    global _QUEUE
    _QUEUE = queue


def precache_donor(job):
    """A worker's: one donor's missing pieces written to the cache. (package, [(actor, why it failed)])."""
    cache, game, package, actors, stop = job
    shared, failed = {}, []
    for actor in actors:
        if stop and os.path.exists(stop):
            break       # asked to stop: between pieces, so no file of the cache is left half written
        try:
            piece(cache, game, dict(package=package, level='base', actor=actor), shared)
        except ProjectError as error:
            failed.append((actor, error.message))
        except Exception as error:  # noqa: BLE001 (one piece that can't be read doesn't stop the map's others)
            failed.append((actor, '%s: %s' % (type(error).__name__, error)))
        if _QUEUE is not None:
            _QUEUE.put(1)
    return package, failed


def precache(game, cache, jobs=None, progress=None, stop=None):
    """Every piece of the index not in the cache yet, written to it; then each donor's older generations (another
    file of the map, or an older exporter's) deleted. progress(done, total). Returns dict(pieces, kept, made, failed
    [{package, actor, error}], pruned, seconds, stopped). The index must be there (scan()). `stop`: a file whose
    appearing stops the work after the pieces in hand (`stopped`: True; nothing is deleted then)."""
    import multiprocessing
    import queue as queues
    import shutil
    started = time.monotonic()
    index = load_index(cache)
    if index is None:
        raise ValueError('the library has not been scanned')
    plan = piece_plan(cache, game, index)
    work = sorted(((str(cache), str(game), d['package'], d['missing'], str(stop) if stop else None)
                   for d in plan if d['missing']), key=lambda job: -len(job[3]))
    total, done, failed = sum(len(job[3]) for job in work), 0, []
    if progress:
        progress(0, total)
    jobs = max(1, min(jobs or 6, os.cpu_count() or 1, len(work) or 1))
    if work and jobs == 1:
        for job in work:
            failed += [dict(package=job[2], actor=a, error=why) for a, why in precache_donor(job)[1]]
            done += len(job[3])
            if progress:
                progress(done, total)
    elif work:
        context = multiprocessing.get_context('spawn')
        counted = context.Queue()
        pool = context.Pool(jobs, initializer=_precache_queue, initargs=(counted,))
        try:
            result = pool.map_async(precache_donor, work, chunksize=1)
            while True:
                try:
                    counted.get(timeout=0.5)
                    done += 1
                    while True:
                        counted.get_nowait()
                        done += 1
                except queues.Empty:
                    pass
                if progress:
                    progress(min(done, total), total)
                if result.ready():
                    break
            for package, missed in result.get():
                failed += [dict(package=package, actor=a, error=why) for a, why in missed]
            if progress and not (stop and os.path.exists(stop)):
                progress(total, total)
        finally:
            pool.terminate()
            pool.join()
    stopped = bool(stop and os.path.exists(stop))
    pruned = 0
    # each donor's older generations of the same file go (prune.py's rule); another file's, such as the other install's
    # copy of the map, stay as its own (review finding 18: switching installs exported them all again)
    from prune import PIECES
    for d in ([] if stopped else plan):
        current = PIECES.match(d['folder'].name)
        for old in (d['folder'].parent.iterdir() if d['folder'].parent.is_dir() else ()):
            m = PIECES.match(old.name)
            if (old.is_dir() and old != d['folder'] and m and current and m.group('digest') == current.group('digest')
                    and int(m.group('version')) < int(current.group('version'))):
                shutil.rmtree(old, ignore_errors=True)
                pruned += 1
    pieces = sum(len(d['actors']) for d in plan)
    made = (done if stopped else total) - len(failed)
    return dict(pieces=pieces, kept=pieces - total, made=max(made, 0), failed=failed, pruned=pruned, stopped=stopped,
                seconds=round(time.monotonic() - started, 1))


# ---------------------------------------------------------------------------------------------------- the user's state
def state_path():
    return settings_path().parent / 'library.json'


def empty_state():
    return dict(schema=STATE_SCHEMA, schemaVersion=STATE_VERSION, revision=0, favourites=[], recent=[])


def load_state(path=None):
    """The user's favourites and recently used pieces (plan 4.7). No file is the empty state; a file that can't be
    read is an error, and is left alone."""
    path = Path(path) if path else state_path()
    if not path.is_file():
        return empty_state()
    try:
        doc = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(doc, dict) or doc.get('schema') != STATE_SCHEMA or doc.get('schemaVersion') != STATE_VERSION:
            raise ValueError('not a library state of this version')
        _check_state(doc)
        if not isinstance(doc.get('revision'), int):
            raise ValueError('no revision')
        return doc
    except (OSError, ValueError) as error:
        raise ProjectError(500, 'The favourites file %s can\'t be read (%s). It is left as it is.' % (path, error))


def _items(doc, field, stamp):
    items = doc.get(field)
    if not isinstance(items, list):
        raise ValueError('%s must be a list' % field)
    out, seen = [], set()
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get('key'), str) or not KEY.fullmatch(item['key']):
            raise ValueError('an entry of %s has no key' % field)
        if item['key'] in seen:
            continue
        seen.add(item['key'])
        out.append({'key': item['key'], 'name': str(item.get('name') or '')[:120],
                    stamp: str(item.get(stamp) or now())[:40]})
    return out


def _check_state(doc):
    return dict(favourites=_items(doc, 'favourites', 'addedAt'), recent=_items(doc, 'recent', 'usedAt')[:RECENT])


def save_state(document, expected, path=None):
    """Write the state `document` ({favourites, recent}) when `expected` is the revision on disk (0 for no file);
    else 409 with the revision there. Returns the state as written."""
    path = Path(path) if path else state_path()
    if not isinstance(document, dict):
        raise ProjectError(400, 'Send {expectedRevision, document: {favourites, recent}}.')
    try:
        body = _check_state(document)
    except ValueError as error:
        raise ProjectError(400, 'Not a list of favourites: %s.' % error)
    # the revision checked and the file replaced as one step (review finding 21): two windows saving at once each get
    # their own revision or a 409, never both the same one with the first's change lost. The lock is the operating
    # system's on a file beside it, so it holds across threads and across servers.
    from publication import FileLock
    lock = FileLock(path.with_name(path.name + '.lock'))
    if not lock.acquire(STATE_WAIT):
        raise ProjectError(409, 'The favourites are being saved by another window; try again.', code='state-busy')
    try:
        current = load_state(path)
        if expected != current['revision']:
            raise ProjectError(409, 'The favourites were changed in another window.', revision=current['revision'])
        out = dict(schema=STATE_SCHEMA, schemaVersion=STATE_VERSION, revision=current['revision'] + 1, **body)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_files.write_text(path, json.dumps(out, indent=1) + '\n', temp=part_of(path))
        return out
    finally:
        lock.release()


# ---------------------------------------------------------------------------------------------------- the server's side
class LibraryRunner:
    """The library as the server serves it: the index, one scan at a time (`viewer.py library scan` in the
    background), pieces exported on request, the page's thumbnails."""

    def __init__(self, cache, game, command=None, state=None):
        """cache: the cache root; game: the game setting (a game folder or one holding it, or None); command(game)
        gives the scan's command line and state the favourites file (tests give both)."""
        self.cache, self.game, self.state_file = Path(cache), game, state
        self.command = command or (lambda game: [sys.executable, '-B', '-u', str(HERE / 'viewer.py'), 'library',
                                                 'scan', '--cache', str(self.cache), '--game', str(game)])
        self.lock = threading.Lock()
        self.piece_lock = threading.Lock()
        self.job = None
        self._index = None          # (mtime, index, its JSON bytes)

    def install(self):
        if self.game is None:
            raise ProjectError(409, 'The game install is not set: choose it in the editor.')
        game, note = resolve_game(self.game)
        if game is None:
            raise ProjectError(409, 'The game install was not found: %s' % note)
        return game

    def index(self):
        """(index, its JSON bytes) or (None, None), read again when the file changes."""
        path = index_path(self.cache)
        try:
            mtime = path.stat().st_mtime_ns
        except OSError:
            return None, None
        with self.lock:
            if self._index is None or self._index[0] != mtime:
                index = load_index(self.cache)
                self._index = (mtime, index, json.dumps(index, separators=(',', ':')).encode() if index else None)
            return self._index[1], self._index[2]

    def _job(self):
        job = self.job
        if not job:
            return dict(state='idle', seconds=None, progress=None, error=None, lines=[])
        seconds = round(time.monotonic() - job['started'], 1) if job['state'] == 'running' else job['seconds']
        return dict(state=job['state'], seconds=seconds, progress=job['progress'], error=job['error'],
                    lines=job['lines'][-20:], startedAt=job['startedAt'])

    def status(self):
        """The scan's state and the index's summary: dict(scan, ready, summary, stale {changed, missing} | None)."""
        index, _ = self.index()
        out = dict(ready=index is not None, summary=summary(index) if index else None, stale=None)
        if index:
            try:
                changed, missing = stale(index, self.install())
                out['stale'] = dict(changed=changed, missing=missing) if changed or missing else None
            except (ProjectError, OSError, ValueError):
                pass
        with self.lock:
            out['scan'] = self._job()
        return out

    def start(self):
        game = self.install()
        with self.lock:
            if self.job and self.job['state'] == 'running':
                return self._job()
            job = dict(state='running', startedAt=now(), started=time.monotonic(), seconds=0, lines=[], error=None,
                       progress=None)
            # a contained process tree, as a build is (procs.py; review finding 48): the scan's workers end with it,
            # and it ends with the server
            import procs
            try:
                tree = procs.launch(self.command(game), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                    encoding='utf-8', errors='replace', creationflags=procs.CREATE_NO_WINDOW)
            except OSError as error:
                raise ProjectError(500, 'The scan of the game\'s maps did not start (%s).' % error)
            self.job = job
            threading.Thread(target=self._follow, args=(job, tree), daemon=True).start()
            return self._job()

    def running(self):
        """Whether a scan runs."""
        with self.lock:
            return bool(self.job and self.job['state'] == 'running')

    def _follow(self, job, tree):
        from builds import PROGRESS
        proc = tree.proc
        lines = []
        for raw in proc.stdout:
            line = raw.rstrip()
            m = PROGRESS.match(line.strip())
            if m and m.group(2):
                done, total = int(m.group(2)), int(m.group(3))
                with self.lock:
                    job['progress'] = dict(what=m.group(1), done=done, total=total,
                                           fraction=round(done / max(total, 1), 3))
                continue
            lines.append(line)
            with self.lock:
                job['lines'] = (job['lines'] + [line])[-200:]
        proc.stdout.close()
        code = proc.wait()
        tree.drain(timeout=30, kill_after=5)
        tree.close()
        with self.lock:
            job['seconds'] = round(time.monotonic() - job['started'], 1)
            if code:
                job['error'] = next((l for l in reversed(lines) if l.strip()), 'the scan stopped (exit %d)' % code)
            job['state'] = 'failed' if code else 'ready'

    def piece(self, source):
        with self.piece_lock:       # one export at a time: two requests for one donor would write the same files
            return piece(self.cache, self.install(), source)

    def pieces(self, sources):
        with self.piece_lock:
            return pieces(self.cache, self.install(), sources)

    def records(self, sources):
        """Many pieces' records in one answer (a prefab's opening): [{record} or {error}], in the order asked."""
        with self.piece_lock:
            return [dict(error=error.message) if error else dict(record=record)
                    for record, error in read_pieces(self.cache, self.install(), sources)]

    def effect(self, source):
        with self.piece_lock:
            return effect(self.cache, self.install(), source)

    def effects(self, sources):
        """Many effects' and sounds' templates in one answer (a project's opening): [{record} or {error}]."""
        with self.piece_lock:
            return [dict(error=error.message) if error else dict(record=record)
                    for record, error in read_effects(self.cache, self.install(), sources)]

    def wave_scene(self, package):
        """(the donor's file, its records as an export's: what viewer.py's WaveCache reads a wave by) for the Wave
        preview of an effect or sound from the map `package`."""
        with self.piece_lock:
            game, shared = self.install(), {}
            records = effect_records(self.cache, game, package, shared)
            path = donor_path(game, package, shared)
        return path, dict(name=records['source']['package'], soundWaves=records.get('waves') or {}, streams={},
                          source=dict(file=str(path), sha256=records['source']['sha256']))

    def recover_prefab(self, document):
        from prefabs import recover_sources
        index, _ = self.index()
        with self.piece_lock:
            game, shared = self.install(), {}
            return recover_sources(document, index, lambda source: piece(self.cache, game, source, shared))

    def thumb(self, key, folder='thumbs'):
        if not KEY.fullmatch(key):
            raise ProjectError(400, 'Not a piece\'s key.')
        return self.cache / 'library' / folder / (key + '.png')

    def thumbs(self, folder='thumbs'):
        """The keys of the pieces whose thumbnail is kept (`folder` 'pictures': the look picker's pictures)."""
        folder = self.cache / 'library' / folder
        return sorted(p.stem for p in folder.glob('*.png')) if folder.is_dir() else []

    def save_thumb(self, key, data, folder='thumbs'):
        limit = PICTURE_LIMIT if folder == 'pictures' else THUMB_LIMIT
        if not data.startswith(PNG) or len(data) > limit:
            raise ProjectError(400, 'A picture is a PNG of at most %d KB.' % (limit >> 10))
        path = self.thumb(key, folder)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_files.write_bytes(path, data, temp=part_of(path))
        return dict(ok=True)

    def load_state(self):
        return load_state(self.state_file)

    def save_state(self, document, expected):
        return save_state(document, expected, self.state_file)

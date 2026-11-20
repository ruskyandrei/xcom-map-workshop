"""Compile a complete builder snapshot into a project on the game's blank test stage.

The test follows the Build's rules (plan "sturdier prefabs, faster editor", part R): what the Build warns about, the
test warns about, and a piece that can't be built is left out and named, not the test refused. What still stops a
test is the stage's own: the blank map missing or changed, a prefab that leaves the squad no room on the 256 by 256
stage (MAX_TILES), a document the compiler can't read, or nothing left to build."""
from base64 import b32encode
from copy import deepcopy
import math
from pathlib import Path
import struct
import sys
from uuid import UUID, uuid5

TOOLS = Path(__file__).resolve().parents[1]
for folder in (TOOLS / 'viewer', TOOLS / 'bake', TOOLS / 'upk'):
    if str(folder) not in sys.path:
        sys.path.append(str(folder))

import compiler  # noqa: E402
from build import lwr_file  # noqa: E402
from export import EXPORT_VERSION  # noqa: E402
import library as piece_library  # noqa: E402
from library import LEVEL, digest_of, read_pieces  # noqa: E402
from lights import storable_cone  # noqa: E402
from package import Package  # noqa: E402
from prefab_bounds import GRID_LEVELS, MAX_TILES, PLAYED_LEVELS, SLACK, TILE, footprint, measure  # noqa: E402
from prefab_bounds import LEVEL as LEVEL_HEIGHT  # noqa: E402
from prefabs import recover_sources, validate  # noqa: E402
from projects import ID, SCHEMA, SCHEMA_VERSION, ProjectError, now  # noqa: E402
from shell import DONOR as SHELL_DONOR, squad_places  # noqa: E402

MAP = 'CB2_MP_Blank'
# the blank map's own tile grid; a test grows it to the height its prefab needs: at least PLAYED_LEVELS (18, the
# tallest of the game's maps: prefab plan 5.6b), at most GRID_LEVELS (30)
OWN_GRID = [36, 36, 12]
# a piece record's fields the compiler reads; a newer editor's field a prefab carries stays out of the test's project
PIECE_FIELDS = ('actor', 'from', 'components', 'location', 'rotation', 'prefab', 'partner', 'tinted', 'recipe',
                'template', 'light', 'cover', 'flags', 'kind', 'effect', 'sound')
# The backdrop (prefab plan 5.11): URB_TruckStop_EWI's sky dome (Skybox.Meshes.SkyDome with the noon sky, a hemisphere
# 127,000 units across), centred on the stage at its ground, and the same dome turned over under it, so what shows
# past the hidden ground is sky, not black.
SKY = dict(package='URB_TruckStop_EWI', level='base', actor=LEVEL + '.XComLevelActor_46')
SKY_TURNS = ([0, 0, 0], [0, 0, 32768])
# The stock wall, pickup and van. Keep the floor planes, level volume and directional light.
STOCK_PROPS = {LEVEL + '.' + name for name in (
    'XComDecoFracLevelActor_0', 'XComDestructibleActor_0', 'XComDestructibleActor_1',
    'XComFracLevelActor_0', 'XComFracLevelActor_1',
)}


def issue(code, message, **where):
    return dict(code=code, message=message, **where)


def left(code, message, **where):
    """A piece left out of the test: an issue the test's window lists first."""
    return dict(code=code, message='Left out: ' + message, leftOut=True, **where)


def refuse(issues, **details):
    raise ProjectError(422, issues[0]['message'], code=issues[0]['code'], issues=issues, **details)


def stage_levels(bounds):
    """How many levels the test's stage gets for a prefab whose measured bounds are `bounds` (from its ground)."""
    return min(GRID_LEVELS, max(PLAYED_LEVELS, math.ceil((bounds[5] - SLACK) / LEVEL_HEIGHT)))


def without(snapshot, names):
    """The snapshot less the pieces called `names`: a partner that went is named no more, and a group keeps the
    members it has left (one with fewer than two goes, its members to the group that held it)."""
    names = set(names)
    if not names:
        return snapshot
    pieces = [dict(p, partner=None) if p.get('partner') in names else p
              for p in snapshot['pieces'] if p['actor'] not in names]
    groups = {g['id']: dict(g, members=[m for m in g['members'] if m.get('added') not in names])
              for g in snapshot.get('groups', [])}
    changed = True
    while changed:
        changed = False
        for gid, group in list(groups.items()):
            group['members'] = [m for m in group['members'] if 'group' not in m or m['group'] in groups]
            if len(group['members']) >= 2:
                continue
            del groups[gid]
            changed = True
            for parent in groups.values():
                parent['members'] = [x for m in parent['members']
                                     for x in (group['members'] if m.get('group') == gid else [m])]
    used = {p['from']['package'].casefold() for p in pieces if p.get('from')}
    return dict(snapshot, pieces=pieces, groups=list(groups.values()),
                donors=[d for d in snapshot.get('donors', []) if d['package'].casefold() in used])


def validate_snapshot(snapshot):
    try:
        prefab_id = snapshot.get('id') if isinstance(snapshot, dict) else None
        if not isinstance(prefab_id, str) or not ID.fullmatch(prefab_id):
            raise ProjectError(422, 'A test needs a complete prefab builder snapshot with a document ID.')
        validate(snapshot, prefab_id)
    except ProjectError as error:
        refuse([issue('snapshot-schema', error.message)])
    if not snapshot['pieces'] and not snapshot.get('buildings'):
        refuse([issue('snapshot-empty', 'Add a piece, light or building floor box before testing.')])


def match_changed_donors(snapshot, cache, game):
    """(snapshot, notes): a prefab whose donor map is not the file its pieces were saved from (another SHA-256) has
    those pieces matched by their recipes, as placing does (prefabs.recover_sources), with a warning naming the map.
    A piece with no match is left out."""
    expected = {d['package'].casefold(): d['sha256'] for d in snapshot.get('donors', []) if 'sha256' in d}
    packages = {p['from']['package'] for p in snapshot['pieces'] if p.get('from')}
    if not expected or game is None:
        return snapshot, []
    changed = []
    for package in sorted(packages):
        path = next((p for name, _, p in piece_library.donors(game) if name.casefold() == package.casefold()), None)
        if path is not None and expected.get(package.casefold()) not in (None, digest_of(path)):
            changed.append(package)
    if not changed:
        return snapshot, []
    notes = [issue('donor-changed', f'{package} is not the file this prefab was saved from: its pieces were matched '
                   'by their recipes.', package=package) for package in changed]
    index, shared = piece_library.load_index(cache), {}

    def read(source):
        return piece_library.piece(cache, game, source, shared)
    # (a piece with no recipe to match by would hold its map's other pieces to the old file: it goes first)
    result = recover_sources(snapshot, index, read)
    gone = {u['actor']: u['reason'] for u in result['unresolved']}
    if gone:
        result = recover_sources(without(snapshot, gone), index, read)
        gone.update({u['actor']: u['reason'] for u in result['unresolved']})
    notes.extend(left('donor-changed', f'{actor} could not be matched in the changed map. {reason}', actor=actor)
                 for actor, reason in sorted(gone.items()))
    return without(result['document'], gone), notes


def resolve_sources(snapshot, cache, game):
    """(snapshot, records, targets, donors, notes): the pieces of other maps read. A piece whose source can't be
    had is left out of the snapshot and named in `notes`."""
    snapshot, notes = match_changed_donors(snapshot, cache, game)
    sources = {}
    for piece in snapshot['pieces']:
        source = piece.get('from')
        if source and 'kind' not in piece:
            key = source['package'], source['actor']
            sources[key] = dict(source, actor=compiler.short(source['actor']))
    resolved = dict(zip(sources, read_pieces(cache, game, sources.values())))
    shared = {}
    expected = {donor['package'].casefold(): donor['sha256']
                for donor in snapshot.get('donors', []) if 'sha256' in donor}
    donors, records, targets, gone = {}, {}, {}, []
    for piece in snapshot['pieces']:
        source = piece.get('from')
        if not source:
            template = piece['template']
            kind, version = template['kind'], template['version']
            known = (piece['cover']['type'] in compiler.COVER_RECIPES.get(version, {}).get('heights', ())
                     if kind == 'cover'
                     else version in compiler.LIGHT_RECIPES.get(kind, {}))
            if not known:
                gone.append(left('recipe-unsupported', f'{piece["actor"]} uses an unsupported {kind} recipe.',
                                 actor=piece['actor'], template=template))
            continue
        where = dict(actor=piece['actor'], source=source)
        if 'kind' in piece:
            # an effect, a sound (the effects and sounds plan, stage FX6a) or a lens flare (FX6b): read from its map
            # as a project's copy is
            try:
                template = piece_library.effect(cache, game, dict(source, actor=compiler.short(source['actor'])), shared)
            except ProjectError as error:
                gone.append(left(error.extra.get('code', 'piece-unreadable'), f'{piece["actor"]}: {error.message}', **where))
                continue
            package, sha = template['source']['package'], template['source']['sha256']
            if template['kind'] != piece['kind']:
                gone.append(left('piece-missing', f'{piece["actor"]}: {compiler.short(source["actor"])} of {package} is '
                                 f'not {compiler.EFFECT_WORDS.get(piece["kind"], "of that kind")}.', **where))
                continue
            if expected.get(package.casefold(), sha) != sha or donors.get(package, sha) != sha:
                gone.append(left('donor-changed', f'{piece["actor"]}: {package} is not the file this prefab was saved '
                                 'from.', **where))
                continue
            donors[package] = sha
            targets[piece['actor']] = dict(package=package, level='base', actor=LEVEL + '.' + compiler.short(source['actor']))
            continue
        key = source['package'], source['actor']
        record, error = resolved[key]
        if error:
            gone.append(left(error.extra.get('code', 'piece-unreadable'), f'{piece["actor"]}: {error.message}', **where))
            continue
        donor = record['source']
        package, sha = donor['package'], donor['sha256']
        if expected.get(package.casefold(), sha) != sha or donors.get(package, sha) != sha:
            gone.append(left('donor-changed', f'{piece["actor"]}: {package} changed while its pieces were being '
                             'read.', **where))
            continue
        actor = LEVEL + '.' + compiler.short(source['actor'])
        components = {o['component'] for o in record['objects'] if o['actor'] == actor}
        if source['actor'] not in (actor, compiler.short(actor)) or not components:
            gone.append(left('piece-missing', f'{piece["actor"]}: {package} has no piece called {source["actor"]}.',
                             **where))
            continue
        if components != set(piece['components']):
            gone.append(left('template-changed', f'{piece["actor"]}: the components of {actor} in {package} do not '
                             'match the prefab\'s.', expected=piece['components'], found=sorted(components), **where))
            continue
        donors[package] = sha
        records[key] = record
        targets[piece['actor']] = dict(package=package, level='base', actor=actor)
    return without(snapshot, {g['actor'] for g in gone}), records, targets, donors, notes + gone


def place(bounds, grid, spawns):
    """Fit the full footprint in the least stage area, then as close to the squad as possible."""
    origin = grid['origin']
    own_x, own_y = grid['dimensions'][:2]
    corner, (width, depth) = footprint(bounds)
    tiles = [[math.floor((p[k] - origin[k]) / TILE) for k in range(2)] for p in spawns]
    # A single disjoint rectangle leaves an open way from this border to the opposite edge of the stage.
    lo_x, lo_y = [min(p[k] for p in tiles) - 1 for k in range(2)]
    hi_x, hi_y = [max(p[k] for p in tiles) + 2 for k in range(2)]
    centre_x, centre_y = [sum(p[k] + 0.5 for p in tiles) / len(tiles) for k in range(2)]
    best = None
    for x in range(MAX_TILES - width + 1):
        nx = max(own_x, x + width)
        for y in range(MAX_TILES - depth + 1):
            if x < hi_x and x + width > lo_x and y < hi_y and y + depth > lo_y:
                continue
            ny = max(own_y, y + depth)
            dx = max(x - centre_x, 0, centre_x - x - width)
            dy = max(y - centre_y, 0, centre_y - y - depth)
            rank = (nx * ny, dx * dx + dy * dy, x, y)
            if best is None or rank < best:
                best = rank
    if best is None:
        refuse([issue('squad-room', f'The {width} by {depth} tile prefab is too large to test: it leaves no room '
                      f'for the squad on the {MAX_TILES} by {MAX_TILES} tile stage. It can still be placed in a '
                      'map.')])
    _, _, x, y = best
    shift = [origin[0] + x * TILE - corner[0], origin[1] + y * TILE - corner[1], origin[2]]
    return dict(grid=[max(own_x, x + width), max(own_y, y + depth)], tile=[x, y], translation=shift,
                bounds=translate(bounds, shift), squad=spawns, reservedTiles=[lo_x, lo_y, hi_x, hi_y])


def translate(values, shift):
    return [compiler.tidy(value + shift[k % 3]) for k, value in enumerate(values)]


def stock_overrides(scene):
    package = scene['name']
    own = {o['actor'] for o in scene['objects'] if o['layer'] == 'base' and o['sourcePackage'] == package}
    if missing := STOCK_PROPS - own:
        refuse([issue('stage-props', 'The blank map export is missing its expected stock props.',
                      actors=sorted(missing))])
    assemblies = compiler.assemblies(scene, package)
    actors = STOCK_PROPS | {member for actor in STOCK_PROPS if actor in assemblies
                            for member in assemblies[actor]['members']}
    return [dict(target=dict(package=package, level='base', actor=actor), deleted=True) for actor in sorted(actors)]


def make_project(snapshot, scene, placement, targets, test_id, levels=PLAYED_LEVELS):
    namespace = UUID(test_id)
    package_code = b32encode(namespace.bytes).decode('ascii').rstrip('=').lower()
    actors = {p['actor']: LEVEL + f'.PrefabTest_copy{k}' for k, p in enumerate(snapshot['pieces'], 1)}
    ids = dict(added=actors,
               group={g['id']: str(uuid5(namespace, 'group:' + g['id'])) for g in snapshot.get('groups', [])},
               building={b['id']: str(uuid5(namespace, 'building:' + b['id'])) for b in snapshot.get('buildings', [])})
    shift = placement['translation']
    added = []
    for p in snapshot['pieces']:
        source = p['actor']
        actor = actors[source]
        record = dict(deepcopy({k: v for k, v in p.items() if k in PIECE_FIELDS}),
                      id=str(uuid5(namespace, 'actor:' + source)), actor=actor, location=translate(p['location'], shift))
        kind = record.get('kind')
        if kind and isinstance(record.get(kind), dict) and not compiler.FAMILIES.get(kind + '-values', {}).get('builds'):
            # its values are built where their family builds: until then the test plays it as its map has it
            kept = {k: v for k, v in record[kind].items() if k == 'follow'}
            if kept: record[kind] = kept
            else: del record[kind]
        if 'from' in record:
            record['from'] = targets[source]
            record.pop('recipe', None)
            if record.get('partner'):
                record['partner'] = actors.get(record['partner'])
            if record.get('prefab'):
                record['prefab'] = str(uuid5(namespace, 'assembly:' + record['prefab']))
        light = record.get('light')
        if isinstance(light, dict) and 'innerConeAngle' in light and 'outerConeAngle' in light:
            # a prefab saved before the page capped them may hold a map light's wide cone (a stored 100): the made
            # light takes the cone it lights as, which the compiler's ranges take
            light['innerConeAngle'], light['outerConeAngle'] = storable_cone(light['innerConeAngle'], light['outerConeAngle'])
        added.append(record)
    groups = [dict(id=ids['group'][g['id']], members=[{k: ids[k][v] for k, v in m.items()} for m in g['members']],
                   **{k: g[k] for k in ('breakTogether', 'locked') if k in g})
              for g in snapshot.get('groups', [])]
    buildings = [dict(id=ids['building'][b['id']],
                      floors=[dict(boxes=[translate(box, shift) for box in f['boxes']]) for f in b['floors']],
                      **{k: b[k] for k in ('name', 'kind') if k in b})
                 for b in snapshot.get('buildings', [])]
    project = dict(schema=SCHEMA, schemaVersion=SCHEMA_VERSION, id=test_id, name=snapshot['name'],
                   revision=1, savedAt=now(), mode='edit', nextSerial=len(added) + 1,
                   source=dict(map=MAP, package=MAP + '.upk', sha256=scene['source']['sha256'],
                               exporterVersion=scene['exporterVersion']),
                   output=dict(shipAs='pt_' + package_code, patch='pp_' + package_code),
                   overrides=stock_overrides(scene), added=added, groups=groups, buildings=buildings)
    # the stage is as tall as the prefab needs (stage_levels: the tallest map's 18 levels, more for a taller prefab),
    # upward from its own ground (prefab plan 5.6b), its ground planes hidden: stood on, not drawn (5.11; the game
    # draws its tile grid under the cursor)
    project['stage'] = dict(grid=placement['grid'] + [levels], ground=True, hideGround=True)
    return project, ids


def add_sky(project, ids, placement, grid, cache, game, donors):
    """The stage's backdrop (SKY) added to the project: two copies of the sky dome around the stage's centre, at its
    ground, one turned over. Labelled "(stage sky n)" among the test's pieces."""
    (record, error), = read_pieces(cache, game, [dict(SKY, actor=compiler.short(SKY['actor']))])
    if error:
        refuse([issue('stage-sky', f'The stage\'s sky ({SKY["package"]} {compiler.short(SKY["actor"])}) could not be '
                      f'read: {error.message}')])
    donor = record['source']
    package, sha = donor['package'], donor['sha256']
    if donors.get(package, sha) != sha:
        refuse([issue('stage-sky', f'{package} changed while the stage was being prepared.')])
    components = sorted({o['component'] for o in record['objects'] if o['actor'] == SKY['actor']})
    if not components:
        refuse([issue('stage-sky', f'{package} has no {compiler.short(SKY["actor"])}, the stage\'s sky.')])
    donors[package] = sha
    origin, namespace = grid['origin'], UUID(project['id'])
    centre = [compiler.tidy(origin[k] + placement['grid'][k] * TILE / 2) for k in range(2)] + [origin[2]]
    for k, rotation in enumerate(SKY_TURNS, 1):
        actor = LEVEL + f'.PrefabTest_sky{k}'
        project['added'].append(dict(id=str(uuid5(namespace, f'sky:{k}')), actor=actor,
                                     **{'from': dict(package=package, level='base', actor=SKY['actor'])},
                                     components=components, location=list(centre), rotation=list(rotation),
                                     prefab=None, partner=None))
        ids['added'][f'(stage sky {k})'] = actor
    project['nextSerial'] = len(project['added']) + 1


def compile_stage(project, scene, library, ids, donors):
    """(report, errors, issues): the compiler's report of the stage's project; `errors` stop the test (the
    document's own, the stage's); `issues` are what the test's window lists and builds all the same: the pieces left
    out first, then the warnings, each with its piece's name in the prefab (`actor`)."""
    spec, report = compiler.compile_project(project, scene, library=library)
    labels = {v: k for k, v in ids['added'].items()}

    def named(row):
        # (with the piece's name in the prefab, in the message too: the stage's own names mean nothing to the user)
        if row.get('entity') not in labels:
            return dict(row)
        label = labels[row['entity']]
        return dict(row, actor=label, message=row['message'].replace(compiler.short(row['entity']), compiler.short(label)))
    errors = [named(e) for e in report['errors']]
    gone = [dict(named(e), leftOut=True) for e in report['leftOut']]
    for row in gone:
        row['message'] = 'Left out: %s%s' % ('%s: ' % row['actor'] if row.get('actor') else '', row['message'])
    said, warnings = set(), []
    # (a piece of a grid family can be warned about from two checks; the test says it once, with the piece's name)
    for warning in sorted(report['warnings'], key=lambda w: labels.get(w.get('entity')) is None):
        if warning['code'] == 'off-grid' and warning['message'] in said:
            continue
        said.add(warning['message'])
        warnings.append(named(warning))
    ground = ((scene.get('tileGrid') or {}).get('origin') or [0, 0, 0])[2]
    top = project['stage']['grid'][2] * LEVEL_HEIGHT
    # (a rotation rounded to whole rotation units, a 65,536th of a turn, is said nowhere: it changes nothing in the
    # game; the compiler's notes aren't listed either, only its warnings: the user, 14 November 2026)
    for entity in report['entities']:
        # what the map saves per tile for a piece of a grid family or a cover block needs its tile in the grid: only
        # the rest may stick out into the allowance (prefab plan 5.6b)
        family = entity.get('family') or compiler.CLASS_FAMILY.get(entity.get('actorClass'), 'other')
        if (entity.get('entity') in labels and entity.get('kind') == 'add' and entity.get('location')
                and ('cover' in entity or compiler.FAMILIES.get(family, {}).get('grid'))):
            z = entity['location'][2] - ground
            if not -SLACK <= z < top:
                warnings.append(issue('pivot-outside-grid', f'{labels[entity["entity"]]} stands at height {z:g}, outside '
                                      f'the tile grid (0 to {top}): a {"cover block" if "cover" in entity else family} '
                                      'has its tile in the grid, so there it gives no cover and can\'t be stood on.',
                                      actor=labels[entity['entity']]))
    if spec is not None:
        actors = {e['entity'] for e in report['entities'] if e['kind'] == 'add' or e.get('op') == 'add'}
        buildings = sorted(b['id'] for b in report['buildings'])
        deleted = sorted(e['target'] for e in report['entities'] if e['kind'] == 'delete')
        # a piece the compiler left out is accounted for; one that went with its assembly is named here
        told = {e.get('entity') for e in report['leftOut']}
        for actor in sorted(set(labels) - actors - told):
            gone.append(left('left-out', f'{labels[actor]} is not built: the rest of its assembly was left out.',
                             actor=labels[actor]))
        if (actors - set(labels) or buildings != sorted(ids['building'].values()) or
                deleted != sorted(row['target']['actor'] for row in project['overrides'])):
            errors.append(issue('compile-count', 'The compiler did not account for every piece, light, building and '
                                'stock prop in this test.'))
        if any(donors.get(d['package']) != d['sha256'] for d in report['donors']):
            errors.append(issue('donor-changed', 'A source map changed while the stage was being compiled.'))
    return report, errors, gone + warnings


def prepare(snapshot, test_id, cache, game):
    """Return the project, placement and real compiler report, or a structured ProjectError."""
    validate_snapshot(snapshot)
    base = lwr_file(game, 'CookedPCConsole', MAP + '.upk')
    if not base.is_file():
        refuse([issue('stage-missing', f'The game install has no {MAP}.upk.')])
    sha = digest_of(base)
    binding = dict(source=dict(map=MAP, sha256=sha, exporterVersion=EXPORT_VERSION))
    try:
        _, scene = compiler.find_export(cache, binding, minimum=EXPORT_VERSION)
    except compiler.ExportMissing:
        refuse([issue('stage-unprepared', f'{MAP} needs an export before this test can build.')])
    grid = scene.get('tileGrid') or {}
    if grid.get('size') != [TILE, TILE, 64] or grid.get('dimensions') != OWN_GRID:
        refuse([issue('stage-grid', 'The blank map does not have the expected tile grid.')])
    snapshot, records, targets, donors, notes = resolve_sources(snapshot, cache, game)
    library = compiler.Library(cache, game)
    size = measure(snapshot, library, resolved=records)
    if size['unknown']:
        notes.extend(left('piece-geometry', f'The geometry of {actor} could not be read.', actor=actor)
                     for actor in size['unknown'])
        snapshot = without(snapshot, size['unknown'])
        size = measure(snapshot, library, resolved=records)
    if not snapshot['pieces'] and not snapshot.get('buildings'):
        refuse([issue('snapshot-empty', 'Nothing of this prefab can be built: every piece was left out.')] + notes,
               size=size)
    notes.extend(issue('size-large', message) for message in size['warnings'])
    try:
        spawns = squad_places(Package(base))
    except (OSError, ValueError, struct.error) as error:
        refuse([issue('stage-squad', f'The squad positions in {MAP} could not be read. {error}')])
    placement = place(size['bounds'], grid, spawns)
    project, ids = make_project(snapshot, scene, placement, targets, test_id, stage_levels(size['bounds']))
    add_sky(project, ids, placement, grid, cache, game, donors)
    report, errors, issues = compile_stage(project, scene, library, ids, donors)
    if digest_of(base) != sha or donors.get(scene['name'], sha) != sha:
        errors.append(issue('stage-changed', 'The blank map changed during test preparation.'))
    issues = notes + issues
    issues.sort(key=lambda row: not row.get('leftOut'))
    if errors:
        refuse(errors, size=size, placement=placement, report=report, notes=issues)
    return dict(project=project, placement=placement, size=size, report=report, identities=ids, donors=donors,
                issues=issues, leftOut=[row for row in issues if row.get('leftOut')])

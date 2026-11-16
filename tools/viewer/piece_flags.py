"""Piece flags: the five settings of a placed piece that decide how the game's tile build and its mouse use it, read
from a map package, and the property writes that set them (piece flags plan, research/native/piece-flags.md).

  Blocks walking   bAlwaysConsiderForCover (the cover interface's ConsiderForOccupancy)
  Gives cover      bIgnoreForCover, the other way round
  Blocks sight     VisibilityBlockingData.bBlockUnitVisibility
  Floor            bPathColliding and bCanStepUpOn
  Mouse picks it   bIgnoreFor3DCursorCollision, the other way round

These are settings, the inputs the game's filters read (research/native/cover-build.md, sections 2, 4 and 5); they are
not a prediction of the finished tiles. Geometry, collision, other pieces and the special traces still count:
- a prop (XComDestructibleActor and its children, doors among them) with bIgnoreForPathing is skipped by every world
  trace (the pathing, cover and sight sweeps) but not by the occupancy step: its walking can be half on, and turning
  any of those three on opens that gate, which can turn the others on too (`plan` keeps them as they were);
- a prop's sight has two routes: the world trace (gated) and, on a tile it is the floor of, the floor actor's own
  flag (not gated);
- a ladder is left out of occupancy and of the normal cover sweep by its class; the height test (trace type 2) counts
  a ladder, a door and a sturdy prop whatever their cover flag says;
- StaticMeshActor and KAsset are never counted for walking, cover or sight, and the mouse never picks them (they have
  no mouse interface); they can still be a floor;
- a door's mouse is never read (the pick tests XComInteractiveLevelActor apart); an open door never blocks, and a
  shut one with walking and sight off is walked and seen through (EXP-62);
- a piece that reaches less than 60 over the bottom of its level (`low_piece`) leaves its tiles only partly occupied
  and stays under the crossing sweep, so Blocks walking on it stops no one (EXP-62's hedge).

The class defaults are the game's own, read from its script packages (XComGame.upk, Engine.upk) beside the map when
they are there, else from CLASS_DEFAULTS, which holds what those packages save (read 16 November 2026).

`resolve` reads a placed actor's settings with where each came from (the actor, an archetype, the class, or assumed
where an archetype in another package can't be read). `roles` turns settings into the five roles' states, `plan` a
sparse request into the property writes (with the companion writes that keep the other roles as they were), and
`contract` is what the editor page needs to do the same (web/piece_flags.js mirrors `roles` and `plan`; the parity
cases in tests/piece_flag_cases.json hold both to one answer).
"""
import math
from pathlib import Path
import threading

ROLES = ('walking', 'cover', 'sight', 'floor', 'mouse')
TILE_ROLES = ('walking', 'cover', 'sight', 'floor')
LABELS = dict(walking='Blocks walking', cover='Gives cover', sight='Blocks sight', floor='Floor', mouse='Mouse picks it')

# The raw properties the roles read. bBlockUnitVisibility is a field of the struct VisibilityBlockingData.
PROPS = ('bAlwaysConsiderForCover', 'bIgnoreForCover', 'bBlockUnitVisibility', 'bPathColliding', 'bCanStepUpOn',
         'bIgnoreFor3DCursorCollision', 'bIgnoreForPathing', 'bInteractive', 'bIsValidDestination')
STRUCT_FIELDS = {'bBlockUnitVisibility': ('VisibilityBlockingData', 'VisibilityBlocking')}

# Each class the flags apply to, by the way the game reads them (research/native/piece-flags.md, section 2)
CLASSES = {'XComLevelActor': 'level', 'XComOpacityFadeLevelActor': 'level',
           'XComDestructibleActor': 'prop', 'XComCollectible': 'prop',
           'XComInteractiveLevelActor': 'door',
           'XComFracLevelActor': 'frac', 'XComDecoFracLevelActor': 'frac',
           'XComLadder': 'ladder',
           'StaticMeshActor': 'plain', 'KAsset': 'plain'}
# the properties each family reads (the export carries these)
FAMILY_PROPS = {
    'level': ('bAlwaysConsiderForCover', 'bIgnoreForCover', 'bBlockUnitVisibility', 'bPathColliding', 'bCanStepUpOn',
              'bIgnoreFor3DCursorCollision', 'bIsValidDestination'),
    'frac': ('bAlwaysConsiderForCover', 'bIgnoreForCover', 'bBlockUnitVisibility', 'bPathColliding', 'bCanStepUpOn',
             'bIgnoreFor3DCursorCollision', 'bIsValidDestination'),
    'ladder': ('bAlwaysConsiderForCover', 'bBlockUnitVisibility', 'bPathColliding', 'bCanStepUpOn',
               'bIgnoreFor3DCursorCollision', 'bIsValidDestination'),
    'prop': ('bAlwaysConsiderForCover', 'bIgnoreForCover', 'bBlockUnitVisibility', 'bPathColliding', 'bCanStepUpOn',
             'bIgnoreFor3DCursorCollision', 'bIgnoreForPathing', 'bInteractive', 'bIsValidDestination'),
    'door': ('bAlwaysConsiderForCover', 'bIgnoreForCover', 'bBlockUnitVisibility', 'bPathColliding', 'bCanStepUpOn',
             'bIgnoreForPathing', 'bIsValidDestination'),
    'plain': ('bPathColliding', 'bCanStepUpOn'),
}
GATED = ('prop', 'door')        # bIgnoreForPathing closes every world trace

_LEVEL = dict(bAlwaysConsiderForCover=True, bIgnoreForCover=False, bBlockUnitVisibility=True, bPathColliding=True,
              bCanStepUpOn=True, bIgnoreFor3DCursorCollision=False, bIsValidDestination=True)
_PROP = dict(_LEVEL, bPathColliding=False, bIgnoreForPathing=False, bInteractive=False)
# The class defaults as the game's script packages save them (XComGame.upk's Default__XCom..., Engine.upk's
# Default__Actor, Default__StaticMeshActor, Default__KAsset; read 16 November 2026), each with what it takes from
# its parent classes
CLASS_DEFAULTS = {
    'XComLevelActor': dict(_LEVEL),
    'XComOpacityFadeLevelActor': dict(_LEVEL),
    'XComDestructibleActor': dict(_PROP),
    'XComCollectible': dict(_PROP),
    'XComInteractiveLevelActor': dict(_PROP, bInteractive=True),
    'XComLadder': dict(_LEVEL, bPathColliding=False),
    'XComFracLevelActor': dict(_LEVEL, bPathColliding=False, bCanStepUpOn=False),
    'XComDecoFracLevelActor': dict(_LEVEL, bPathColliding=False, bCanStepUpOn=False),
    'StaticMeshActor': dict(bPathColliding=False, bCanStepUpOn=True),
    'KAsset': dict(bPathColliding=False, bCanStepUpOn=True),
}
SCRIPT_PACKAGES = ('XComGame', 'Engine', 'Core')

# Why a role is not a setting of a class (the panel greys the row with it)
NOT_READ = {
    ('plain', 'walking'): 'the game never counts a %s for walking: its tile build reads only XCOM\'s level pieces',
    ('plain', 'cover'): 'the game never counts a %s for cover: its tile build reads only XCOM\'s level pieces',
    ('plain', 'sight'): 'the game never counts a %s for sight: its tile build reads only XCOM\'s level pieces',
    ('plain', 'mouse'): 'the mouse never picks a %s: it has no mouse interface',
    ('door', 'mouse'): 'the mouse never reads this setting on a door: it tests doors apart, for using them',
    ('ladder', 'cover'): 'a ladder never gives cover by the game\'s normal cover test, whatever this says; its height '
                         'test counts a ladder all the same',
}
# Limits the panel names under a row that is a setting (what the setting does not decide)
LIMITS = {
    'ladder-occupancy': 'a ladder never occupies a tile: this sets only whether the pathing sweep meets it',
    'door-state': 'an open door never blocks; with this off it doesn\'t block when shut either',
    'height-test': 'the cover height test still counts a door or a sturdy prop whatever this says',
    'stops-floor': 'it saves bCanStepUpOn off: the floor search stops at it and finds no floor there',
    'sight-floor': 'on a tile it is the floor of, the floor\'s own flag still blocks sight upward',
    'interactive': 'an interactive prop is never cover by the game\'s normal test (it saves bInteractive)',
    'gate': 'it saves bIgnoreForPathing: every pathing, cover and sight sweep passes it by; the occupancy step does not',
    'no-collision': 'it collides with nothing, so no trace meets it: the setting takes effect only if it gets collision',
    'no-body-setup': 'its mesh has no simple collision (BodySetup): the pathing, cover and sight sweeps pass through it',
    'destination': 'it saves bIsValidDestination off: a unit may not end its move on it',
    'assumed': 'part of it comes from an archetype in another package that could not be read: the class default is '
               'assumed',
    'low': 'it is too low to stop anyone: it reaches less than 60 over the bottom of its level, so its tiles are only '
           'partly occupied and units walk into them',
}
# How high a piece must reach to stop units (research/native/cover-build.md, the occupancy step; EXP-62): the tile
# build's upper occupancy box starts 60 over the bottom of a level (64 high, counted from the tiles' corner). A piece
# reaching less leaves its tile partly occupied with its floor kept, and stays under the crossing sweep (64 over the
# floor), so units walk in. A piece's level is the one its bottom (plus a little, for a mesh sunk into the floor) is in.
LEVEL = 64.0
STOPS_FROM = 60.0


def low_piece(box, corner_z):
    """Whether a piece with the world box [x0, x1, y0, y1, z0, z1] is too low to stop units on a map whose tiles are
    counted from the height corner_z (compiler.tile_corner); None when either is unknown. web/piece_flags.js lowPiece
    is the twin."""
    if not box or corner_z is None:
        return None
    bottom = corner_z + LEVEL * math.floor((box[4] + 8 - corner_z) / LEVEL)
    return box[5] - bottom < STOPS_FROM


def family_of(cls):
    """The family a class reads its flags by, or None for a class the flags don't apply to (a volume, a light)."""
    return CLASSES.get(cls)


def kind_words(cls):
    return {'StaticMeshActor': 'static mesh actor', 'KAsset': 'physics prop (KAsset)'}.get(cls, cls)


# ---------------------------------------------------------------- roles

def _bool(raw, prop):
    v = raw.get(prop)
    return None if v is None else bool(v)


def roles(cls, raw, facts=None):
    """{role: dict(state, value, why?, limits?)} for a class and its settings `raw` ({property: True/False/None}, None
    unknown). state is 'on', 'off', 'partial' (the routes a role has disagree: a prop's occupancy on and its pathing
    sweep off), 'unknown' (an input is unknown) or 'n/a' (the class has no such setting: `why` says so). value is
    True/False, None for partial, unknown and n/a. `facts` (optional): dict(collides, bodySetup, assumed: [property])
    adds the limits that geometry and provenance put on a role, and low (low_piece) the low piece's on walking."""
    family = family_of(cls)
    facts = facts or {}
    out = {}
    if family is None:
        return {r: dict(state='n/a', value=None, why='the flags are not a setting of a %s' % cls) for r in ROLES}

    def state(v):
        return 'unknown' if v is None else ('on' if v else 'off')

    gate = _bool(raw, 'bIgnoreForPathing') if family in GATED else False
    occupancy = _bool(raw, 'bAlwaysConsiderForCover')
    floor_flag, step = _bool(raw, 'bPathColliding'), _bool(raw, 'bCanStepUpOn')
    floor = None if floor_flag is None or (floor_flag and step is None) else bool(floor_flag and step)
    for role in ROLES:
        if (family, role) in NOT_READ:
            out[role] = dict(state='n/a', value=None, why=NOT_READ[family, role] % kind_words(cls)
                             if '%s' in NOT_READ[family, role] else NOT_READ[family, role])
    if family == 'prop' and _bool(raw, 'bInteractive'):
        # (read from the prop's ShouldIgnoreForCover variant; which field it tests is taken from the field order)
        out['cover'] = dict(state='n/a', value=None, why=LIMITS['interactive'])
    if 'walking' not in out:
        if family in GATED:
            if occupancy is False:
                v = False
            elif occupancy is None or gate is None:
                v = None
            else:
                v = 'partial' if gate else True
        else:
            v = occupancy
        out['walking'] = dict(state='partial', value=None) if v == 'partial' else dict(state=state(v), value=v)
    if 'cover' not in out:
        ignore = _bool(raw, 'bIgnoreForCover')
        v = None if ignore is None else not ignore
        if family in GATED and v and gate is not False:
            v = None if gate is None else False
        out['cover'] = dict(state=state(v), value=v)
    if 'sight' not in out:
        block = _bool(raw, 'bBlockUnitVisibility')
        v = block
        if family in GATED and block:
            if gate is None:
                v = None
            elif gate:
                # the world trace passes it; the floor route (its own tile's upward bit) still reads the flag
                v = None if floor is None else ('partial' if floor else False)
        out['sight'] = dict(state='partial', value=None) if v == 'partial' else dict(state=state(v), value=v)
    out['floor'] = dict(state=state(floor), value=floor)
    if 'mouse' not in out:
        ignore = _bool(raw, 'bIgnoreFor3DCursorCollision')
        out['mouse'] = dict(state=state(None if ignore is None else not ignore),
                            value=None if ignore is None else not ignore)
    # the limits a setting leaves to other things
    limits = {r: [] for r in ROLES}
    if family == 'ladder':
        limits['walking'].append('ladder-occupancy')
    if family == 'door':
        for r in TILE_ROLES:
            limits[r].append('door-state')
        limits['cover'].append('height-test')
    if family == 'prop':
        limits['cover'].append('height-test')
    if family in GATED and gate:
        for r in ('walking', 'cover', 'sight'):
            limits[r].append('gate')
        if out['sight']['state'] == 'partial':
            limits['sight'].append('sight-floor')
    if floor_flag and step is False:
        limits['floor'].append('stops-floor')
    if out['floor']['value'] and raw.get('bIsValidDestination') is False:
        limits['floor'].append('destination')
    if facts.get('collides') is False:
        for r in ROLES:
            limits[r].append('no-collision')
    else:
        if facts.get('bodySetup') is False:
            for r in ('walking', 'cover', 'sight'):
                limits[r].append('no-body-setup')
        if facts.get('low') and out['walking']['state'] in ('on', 'partial'):
            limits['walking'].append('low')
    assumed = set(facts.get('assumed') or ())
    for r in ROLES:
        if out[r]['state'] != 'n/a' and assumed & set(ROLE_INPUTS[r]):
            limits[r].append('assumed')
        if limits[r] and out[r]['state'] != 'n/a':
            out[r]['limits'] = limits[r]
    return out


# what each role's value is read from (for provenance: a role is assumed when one of these is)
ROLE_INPUTS = dict(walking=('bAlwaysConsiderForCover', 'bIgnoreForPathing'),
                   cover=('bIgnoreForCover', 'bIgnoreForPathing', 'bInteractive'),
                   sight=('bBlockUnitVisibility', 'bIgnoreForPathing', 'bPathColliding', 'bCanStepUpOn'),
                   floor=('bPathColliding', 'bCanStepUpOn'),
                   mouse=('bIgnoreFor3DCursorCollision',))


def states(cls, raw):
    """{role: state} (roles' short form)."""
    return {r: v['state'] for r, v in roles(cls, raw).items()}


# ---------------------------------------------------------------- writes

def primary_writes(role, want):
    """The property writes that set one role (before any companion): [(property, value)]."""
    if role == 'walking':
        return [('bAlwaysConsiderForCover', bool(want))]
    if role == 'cover':
        return [('bIgnoreForCover', not want)]
    if role == 'sight':
        return [('bBlockUnitVisibility', bool(want))]
    if role == 'floor':
        return [('bPathColliding', True), ('bCanStepUpOn', True)] if want else [('bPathColliding', False)]
    if role == 'mouse':
        return [('bIgnoreFor3DCursorCollision', not want)]
    raise ValueError('no role %r' % role)


def plan(cls, raw, request, assumed=()):
    """What a sparse request ({role: bool}) does to a piece of class `cls` with settings `raw`: dict(
      after: {role: state} once written,
      before: {role: state},
      writes: [(property, value)], the properties to write, in PROPS order (only those that change, or that are
              assumed and so written to make them certain),
      companions: [role], the roles not asked for that are written so they stay as they were (a prop's gate opened),
      unsupported: {role: why} asked of a role the class doesn't have (nothing written for it),
      conflicts: {role: why} roles that opening a prop's gate would change and that can't be kept: the request needs
              an explicit value for each before it can be made (nothing is written while there is one),
      unmet: {role: why} asked for and not reached (an unknown input),
      tiles: whether the tiles change (any of walking, cover, sight, floor changes state; the mouse alone doesn't))."""
    family = family_of(cls)
    before = states(cls, raw)
    out = dict(before=before, after=dict(before), writes=[], companions=[], effects=[], unsupported={}, conflicts={},
               unmet={}, tiles=False)
    if family is None:
        out['unsupported'] = {r: 'the flags are not a setting of a %s' % cls for r in request}
        return out
    asked = {}
    described = None
    for role, want in request.items():
        if role not in ROLES or not isinstance(want, bool):
            out['unsupported'][role] = 'not a setting of a piece'
        elif before[role] == 'n/a':
            described = described or roles(cls, raw)
            out['unsupported'][role] = described[role]['why']
        else:
            asked[role] = want
    writes = {}
    for role, want in asked.items():
        for prop, value in primary_writes(role, want):
            writes[prop] = value
    gate = raw.get('bIgnoreForPathing') if family in GATED else False
    opened = family in GATED and gate is not False and any(asked.get(r) for r in ('walking', 'cover', 'sight'))
    if opened:
        writes['bIgnoreForPathing'] = False
    # the roles not asked for that the writes change: kept as they were by a companion write where one keeps them
    # (cover and sight have a flag of their own each, independent of the rest; a half-on role has none)
    for role in ROLES:
        if role in asked:
            continue
        now = states(cls, dict(raw, **writes))[role]
        if now != before[role] and before[role] in ('on', 'off') and role in ('cover', 'sight'):
            for prop, value in primary_writes(role, before[role] == 'on'):
                writes[prop] = value
            out['companions'].append(role)
    after = states(cls, dict(raw, **writes))
    for role in ROLES:
        if role in asked or after[role] == before[role]:
            continue
        if role == 'sight' and not opened and 'floor' in asked:
            # a gated prop's sight is then its floor's own flag alone (no world trace meets it): it follows the floor
            out['effects'].append(role)
            continue
        out['conflicts'][role] = '%s is %s now, and %s opens the prop\'s pathing gate (bIgnoreForPathing), which turns ' \
                                 'it %s: set %s too' % (LABELS[role], 'partly on' if before[role] == 'partial' else before[role],
                                                        ' and '.join(LABELS[r] for r in asked if asked[r] and r in TILE_ROLES),
                                                        after[role], LABELS[role])
    if out['conflicts']:
        return out
    for role, want in asked.items():
        if after[role] != ('on' if want else 'off'):
            out['unmet'][role] = '%s is %s after the writes (an input is unknown)' % (LABELS[role], after[role])
    assumed = set(assumed)
    out['writes'] = [(prop, writes[prop]) for prop in PROPS
                     if prop in writes and (raw.get(prop) is None or bool(raw.get(prop)) != writes[prop] or prop in assumed)]
    out['after'] = after
    out['tiles'] = any(after[r] != before[r] for r in TILE_ROLES)
    return out


def normalize(cls, raw, request, baseline_assumed=(), collides=True):
    """The smallest part of a request that makes the same after-state (what a project saves): a role asked for its
    present known value is dropped unless the after-state needs it (a companion that keeps it as it was); one whose
    value is assumed is kept (it is written to make it certain), and so is an explicit Floor off on a piece that
    collides with nothing (the Build's automatic floor for low scenery, F-100, must not turn it on)."""
    full = plan(cls, raw, request, baseline_assumed)
    if full['conflicts'] or full['unsupported']:
        return dict(request)
    keep = dict(request)
    before = states(cls, raw)
    assumed = set(baseline_assumed)
    for role in list(request):
        if before[role] != ('on' if request[role] else 'off') or assumed & set(ROLE_INPUTS[role]):
            continue
        if role == 'floor' and request[role] is False and collides is False:
            continue
        trial = {r: v for r, v in keep.items() if r != role}
        p = plan(cls, raw, trial, baseline_assumed)
        if not p['conflicts'] and p['after'] == full['after']:
            keep = trial
    return keep


# ---------------------------------------------------------------- reading a package

class ScriptDefaults:
    """The game's class defaults, from its script packages in the folder a map is in (CookedPCConsole), loaded once per
    folder: {class: {property: value}} for the properties of PROPS, with what each class takes from its parents."""
    _lock = threading.Lock()
    _done = {}

    @classmethod
    def of(cls, folder):
        folder = Path(folder)
        with cls._lock:
            if folder not in cls._done:
                cls._done[folder] = cls._read(folder)
            return cls._done[folder]

    @staticmethod
    def _read(folder):
        from package import Package, FormatError
        packages = {}
        for name in SCRIPT_PACKAGES:
            path = folder / (name + '.upk')
            if not path.is_file():
                return None
            try:
                packages[name] = Package(path)
            except (OSError, ValueError, FormatError):
                return None
        return packages


def _struct_field(p, raw, field):
    """(found, value) of a bool field in a struct's tagged bytes."""
    from package import Reader, FormatError
    if not isinstance(raw, (bytes, bytearray)):
        return False, None
    try:
        tags = p.tagged(Reader(bytes(raw)))
    except (FormatError, ValueError, IndexError):
        return True, None       # saved, but can't be read: unknown
    item = tags.get((field, 0))
    return (True, bool(item['value'])) if item is not None else (False, None)


def _own(p, index, prop):
    """(found, value) of one of PROPS saved by an export itself (a struct's field only where the struct saves it)."""
    if prop in STRUCT_FIELDS:
        struct_name = STRUCT_FIELDS[prop][0]
        item = p.properties(index)[0].get((struct_name, 0))
        if item is None:
            return False, None
        return _struct_field(p, item['value'], prop)
    item = p.properties(index)[0].get((prop, 0))
    if item is None:
        return False, None
    return True, bool(item['value'])


def _script_chain(packages, path):
    """[(package, export)] of a Default__ object and the defaults it takes from (its archetypes), in the script
    packages; [] when it isn't there."""
    out, seen = [], set()
    while path:
        pkg, _, rest = path.partition('.')
        p = packages.get(pkg)
        index = p.by_name.get(rest) if p else None
        if not index or (pkg, index) in seen:
            break
        seen.add((pkg, index))
        out.append((p, index))
        arch = p.exports[index - 1]['arch']
        if not arch:
            break
        name = p.name(arch)
        path = name if arch < 0 else '%s.%s' % (pkg, name)
    return out


def resolve(p, actor):
    """A placed actor's settings: dict(cls, family, raw: {property: value or None}, source: {property: where it came
    from}) for the family's properties (FAMILY_PROPS). source is 'actor' (saved by the actor), 'archetype' (an
    archetype in the map), 'class' (the class's default, read from the game's script packages), 'table' (the class's
    default as CLASS_DEFAULTS holds it, where the script packages can't be read), or 'assumed' (an archetype in another
    package that the map doesn't carry: the class's default is assumed). A value is None where none can be found."""
    cls = p.cls(actor)
    family = family_of(cls)
    out = dict(cls=cls, family=family, raw={}, source={})
    if family is None:
        return out
    wanted = list(FAMILY_PROPS[family])
    found = {}
    unresolved = False
    index, seen = actor, set()
    chain = []
    while index > 0 and index not in seen:
        seen.add(index)
        chain.append(index)
        index = p.exports[index - 1]['arch']
    for k, i in enumerate(chain):
        for prop in wanted:
            if prop in found:
                continue
            ok, value = _own(p, i, prop)
            if ok:
                found[prop] = (value, 'actor' if k == 0 else 'archetype')
    # the rest from the class defaults: an import archetype of the script packages (Default__X), else the class
    scripts = ScriptDefaults.of(Path(p.path).parent)
    tail = index if index < 0 else 0
    default_path = None
    if tail < 0:
        name = p.name(tail)
        if name.split('.')[0] in SCRIPT_PACKAGES and name.split('.')[-1].startswith('Default__'):
            default_path = name
        else:
            unresolved = True
    last_cls = p.cls(chain[-1]) if chain else cls
    if default_path is None:
        package = 'Engine' if last_cls in ('StaticMeshActor', 'KAsset') else 'XComGame'
        default_path = '%s.Default__%s' % (package, last_cls)
    missing = [prop for prop in wanted if prop not in found]
    if missing and scripts:
        for sp, si in _script_chain(scripts, default_path):
            for prop in list(missing):
                ok, value = _own(sp, si, prop)
                if ok:
                    found[prop] = (value, 'assumed' if unresolved else 'class')
                    missing.remove(prop)
        # a property no default saves keeps its type's zero (a bool: false)
        for prop in missing:
            found[prop] = (False, 'assumed' if unresolved else 'class')
        missing = []
    table = CLASS_DEFAULTS.get(last_cls) or CLASS_DEFAULTS.get(cls) or {}
    for prop in missing:
        found[prop] = (table.get(prop, False), 'assumed' if unresolved else 'table')
    for prop in wanted:
        value, source = found[prop]
        out['raw'][prop] = value
        out['source'][prop] = source
    return out


def collides(p, actor):
    """Whether an actor collides: bCollideActors, and CollideActors on one of the mesh components under it (as
    export.collides and the Build's native_copy.collides)."""
    if p.effective(actor, 'bCollideActors', True) is False:
        return False

    def under(i):
        for c in p.children.get(i, []):
            yield c
            yield from under(c)
    return any(p.effective(c, 'CollideActors', True) is not False for c in under(actor)
               if (p.cls(c) == 'SkeletalMeshComponent' and (p.effective(c, 'SkeletalMesh', 0) or 0) > 0)
               or (p.cls(c) in ('StaticMeshComponent', 'FracturedStaticMeshComponent', 'XComMapEdMeshComponent')
                   and (p.effective(c, 'StaticMesh', 0) or 0) > 0))


def body_setup(p, actor):
    """Whether the actor's static meshes have simple collision (a BodySetup): True when every one has, False when one
    hasn't, None for an actor with no static mesh (a skeletal one: its collision is read another way) or a mesh in
    another package."""
    import collision
    seen = None

    def under(i):
        for c in p.children.get(i, []):
            yield c
            yield from under(c)
    for c in under(actor):
        if p.cls(c) not in ('StaticMeshComponent', 'FracturedStaticMeshComponent', 'XComMapEdMeshComponent'):
            continue
        mesh = p.effective(c, 'StaticMesh', 0) or 0
        if mesh < 0:
            return None
        if mesh == 0:
            continue
        try:
            has = bool(collision.body_setup(p, mesh))
        except (ValueError, IndexError):
            return None
        if not has:
            return False
        seen = True
    return seen


def describe(p, actor):
    """What the export carries of an actor's flags (each of its components carries the same): dict(family, raw:
    {property: [value, source]}, roles: {role: state}, collides, bodySetup), or None for a class the flags don't apply
    to. Only the family's properties are listed."""
    r = resolve(p, actor)
    if r['family'] is None:
        return None
    facts = dict(collides=collides(p, actor), bodySetup=body_setup(p, actor),
                 assumed=[k for k, v in r['source'].items() if v == 'assumed'])
    rs = roles(r['cls'], r['raw'], facts)
    return dict(family=r['family'], raw={k: [r['raw'][k], r['source'][k]] for k in FAMILY_PROPS[r['family']]},
                roles={k: v['state'] for k, v in rs.items()}, collides=facts['collides'], bodySetup=facts['bodySetup'])


def raw_of(record):
    """(raw values, assumed properties) from an export's record (describe's)."""
    raw = {k: v[0] for k, v in (record.get('raw') or {}).items()}
    assumed = [k for k, v in (record.get('raw') or {}).items() if v[1] == 'assumed']
    return raw, assumed


def contract():
    """What the editor page needs to read and plan flags as this module does (web/piece_flags.js)."""
    return dict(version=CONTRACT_VERSION, roles=list(ROLES), tileRoles=list(TILE_ROLES), labels=LABELS,
                classes=CLASSES, familyProps={k: list(v) for k, v in FAMILY_PROPS.items()}, gated=list(GATED),
                notRead={'%s|%s' % k: v for k, v in NOT_READ.items()}, limits=LIMITS,
                roleInputs={k: list(v) for k, v in ROLE_INPUTS.items()}, props=list(PROPS),
                kindWords={'StaticMeshActor': 'static mesh actor', 'KAsset': 'physics prop (KAsset)'},
                level=LEVEL, stopsFrom=STOPS_FROM)


CONTRACT_VERSION = 1

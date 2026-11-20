"""Landing zones (private/plans/done/clear-map-plan.md, section 4): LWR's LZArray lines read and written back, and
where a zone puts the landing's actors.

LWR's landing-zone mutator (XComLZMutator, decompiled in the lab's reference folder) picks one of the map's lines at
random when a battle loads and spawns the landing there from the map's own landing actors, found by archetype (one of
each; a second is hidden and destroyed): the drop zone's frame, the evac volume, the player start, a PointInSpace and
six soldier points. Each goes to the line's StartLoc plus a fixed offset turned by StartDir (CalcLocations); the frame
takes StartDir's turn, the others their own yaw turned as the frame's is (AdjRotation), and the soldier points face a
quarter turn on (FaceRot). An "inside" line (ESL_Inside) puts the six points 288 units further back (AdjustOffsets).
A plain Enemy Within install plays the map's own landings where they stand; the Build moves them by the same offsets
(tools/bake/native_spawns.py), so one list of zones gives the same landing both ways.

A zone, as the project saves it (research/editor-contracts.md, `landingZones`):
  {id, location: [x, y, z] (StartLoc), direction: north | east | south | west (StartDir), kind (ESpawnLoc),
   missionType?, councilType?, alternate?: {location, direction} (AltSpawnLoc, AltSpawnDir), lwr?: false, other?}
The web page has the same rules in web/spawns.js.

  python -B tools/viewer/spawns.py check <DefaultLZMutator.ini>   every line parsed and written back byte for byte
"""
import math
import re
import sys

DIRECTIONS = ('north', 'east', 'south', 'west')      # ELZD_North.. : StartDir's turn is its index times 16384
# ESpawnLoc: the kinds a zone can be (ESL_Default: the map's own landing, the mutator does nothing)
KINDS = {'normal': 'ESL_Normal', 'inside': 'ESL_Inside', 'alternate': 'ESL_Alternate', 'noEvac': 'ESL_NoEvacZone',
         'default': 'ESL_Default'}
KIND_OF = {v: k for k, v in KINDS.items()}
QUARTER = 16384
# XComLZMutator's defaultproperties: each actor's offset from StartLoc, before StartDir's turn
OFFSETS = {
    'playerStart': (8.0, 189.0, 16.0),       # dps
    'volume': (0.0, -47.0, 32.0),            # dbv: the evac zone's building volume
    'frame': (0.0, 0.0, -64.0),              # dla: the drop zone's frame (SoldierSpawns_DrpshipVol_12Arc0)
    'point': (-240.0, 432.0, -64.0),         # DP: the PointInSpace
}
SOLDIERS = ((192.0, 384.0, -16.0), (0.0, 480.0, -16.0), (192.0, 192.0, -16.0),     # dsp1..dsp6
            (0.0, 288.0, -16.0), (-192.0, 384.0, -16.0), (-192.0, 192.0, -16.0))
INSIDE_BACK = 288.0          # AdjustOffsets: an inside (or alternate, or no-evac) zone's points this much back in y
GROUND = 64.0                # a zone's ground is this far under its StartLoc (the frame stands there)
# the archetype names the mutator finds the landing's actors by (FindLZObjectsByArchetype), and what each is
ARCHETYPES = {
    'SoldierSpawns_DrpshipVol_12Arc0': 'frame', 'SoldierSpawns_DrpshipVol_Arc0': 'volume',
    'SoldierSpawns_DrpshipVol_2Arc0': 'playerStart', 'SoldierSpawns_DrpshipVol_12Arc1': 'point',
    'SoldierSpawns_DrpshipVol_Arc1': 'soldier1', 'SoldierSpawns_DrpshipVol_Arc2': 'soldier2',
    'SoldierSpawns_DrpshipVol_Arc3': 'soldier3', 'SoldierSpawns_DrpshipVol_Arc4': 'soldier4',
    'SoldierSpawns_DrpshipVol_Arc5': 'soldier5', 'SoldierSpawns_DrpshipVol_7Arc0': 'soldier6',
}
# the evac zone's building volume, as the landing prefab has it: 5 by 3 tiles, 192 high, about its actor
EVAC_SIZE = (480.0, 288.0, 192.0)

_LINE = re.compile(r'^LZArray=\((?P<body>.*)\)$')
_VECTOR = re.compile(r'^\(X=(-?\d+(?:\.\d+)?),Y=(-?\d+(?:\.\d+)?),Z=(-?\d+(?:\.\d+)?)\)$')


def _fields(body):
    """[(name, value)] of a struct's text, splitting at the commas outside parentheses and quotes."""
    out, depth, quoted, start = [], 0, False, 0
    for k, ch in enumerate(body + ','):
        if ch == '"':
            quoted = not quoted
        elif not quoted and ch == '(':
            depth += 1
        elif not quoted and ch == ')':
            depth -= 1
        elif not quoted and depth == 0 and ch == ',':
            part = body[start:k]
            if '=' not in part:
                raise ValueError('not a field: %r' % part)
            name, value = part.split('=', 1)
            out.append((name, value))
            start = k + 1
    if depth or quoted:
        raise ValueError('unbalanced: %r' % body)
    return out


def _number(text):
    v = float(text)
    return int(v) if v == int(v) and '.' not in text else v


def _vector(text):
    m = _VECTOR.match(text)
    if not m:
        raise ValueError('not a vector: %r' % text)
    return [_number(m.group(k)) for k in (1, 2, 3)]


def _direction(text):
    if not text.startswith('ELZD_') or text[5:].lower() not in DIRECTIONS:
        raise ValueError('not a direction: %r' % text)
    return text[5:].lower()


def parse_line(line):
    """(map name, zone without an id) of an LZArray line, or None for a line that isn't one (a comment, another key).
    Fields the editor does not know are kept in the zone's `other`, as written. Raises ValueError for a line that
    says LZArray but can't be read."""
    m = _LINE.match(line.strip())
    if not m:
        return None
    fields = _fields(m.group('body'))
    zone, other, name = {}, [], None
    for key, value in fields:
        if key == 'MapName' and value.startswith('"') and value.endswith('"') and name is None:
            name = value[1:-1]
        elif key == 'MissionType':
            zone['missionType'] = value
        elif key == 'CouncilType':
            zone['councilType'] = value
        elif key == 'ESpawnLoc' and value in KIND_OF:
            zone['kind'] = KIND_OF[value]
        elif key == 'StartLoc':
            zone['location'] = _vector(value)
        elif key == 'StartDir':
            zone['direction'] = _direction(value)
        elif key == 'AltSpawnLoc':
            zone.setdefault('alternate', {})['location'] = _vector(value)
        elif key == 'AltSpawnDir':
            zone.setdefault('alternate', {})['direction'] = _direction(value)
        else:
            other.append('%s=%s' % (key, value))
    if name is None or 'location' not in zone:
        raise ValueError('an LZArray line with no MapName or StartLoc: %r' % line)
    zone.setdefault('direction', 'north')
    zone.setdefault('kind', 'default')
    if 'alternate' in zone:
        zone['alternate'].setdefault('location', [0, 0, 0])
        zone['alternate'].setdefault('direction', 'north')
    order = [k for k, _ in fields]
    if order != _order(zone, other):
        # written in another order than write_line writes: keep the whole line's fields as written
        zone['other'] = m.group('body')
        zone['verbatim'] = True
    elif other:
        zone['other'] = ','.join(other)
    return name, zone


def _order(zone, other):
    return (['MapName'] + (['MissionType'] if 'missionType' in zone else []) + (['CouncilType'] if 'councilType' in zone else [])
            + ['ESpawnLoc', 'StartLoc', 'StartDir'] + (['AltSpawnLoc', 'AltSpawnDir'] if 'alternate' in zone else [])
            + [o.split('=', 1)[0] for o in other])


def _num(v):
    v = float(v)
    if v == int(v):
        return str(int(v))
    return ('%.4f' % v).rstrip('0').rstrip('.')


def _vec(v):
    return '(X=%s,Y=%s,Z=%s)' % tuple(_num(x) for x in v)


def write_line(map_name, zone):
    """The LZArray line (without its line ending) for a zone of the variant `map_name`. Raises ValueError for an
    `other` that would not stay on its line (plain_other)."""
    if not plain_other(zone.get('other', '')):
        raise ValueError('a landing zone\'s other fields hold a line break or a control character')
    if zone.get('verbatim'):
        body = re.sub(r'MapName="[^"]*"', 'MapName="%s"' % map_name, zone['other'], count=1)
        return 'LZArray=(%s)' % body
    parts = ['MapName="%s"' % map_name]
    if zone.get('missionType'):
        parts.append('MissionType=%s' % zone['missionType'])
    if zone.get('councilType'):
        parts.append('CouncilType=%s' % zone['councilType'])
    parts += ['ESpawnLoc=%s' % KINDS[zone.get('kind') or 'normal'], 'StartLoc=%s' % _vec(zone['location']),
              'StartDir=ELZD_%s' % zone['direction'].capitalize()]
    alt = zone.get('alternate')
    if alt:
        parts += ['AltSpawnLoc=%s' % _vec(alt['location']), 'AltSpawnDir=ELZD_%s' % alt['direction'].capitalize()]
    if zone.get('other'):
        parts.append(zone['other'])
    return 'LZArray=(%s)' % ','.join(parts)


def map_lines(text, map_name):
    """The zones (in order, no ids) of an LZMutator ini's live lines for one map (names compared without case, as the
    mutator's ~= does)."""
    out = []
    for line in text.splitlines():
        try:
            got = parse_line(line)
        except ValueError:
            continue
        if got and got[0].casefold() == map_name.casefold():
            out.append(got[1])
    return out


# ---------------------------------------------------------------- where a zone puts the landing
def turn(v, yaw):
    """A vector (x, y, z) turned by a yaw in rotation units, as `v >> Rotator(0, yaw, 0)` turns it."""
    a = yaw * math.pi / 32768.0
    c, s = math.cos(a), math.sin(a)
    if yaw % QUARTER == 0:           # exact for quarter turns
        c, s = [(1, 0), (0, 1), (-1, 0), (0, -1)][(yaw // QUARTER) % 4]
    return (v[0] * c - v[1] * s, v[0] * s + v[1] * c, v[2])


def yaw_of(direction):
    return DIRECTIONS.index(direction) * QUARTER


def place(zone):
    """Where the zone puts each of the landing's actors: {frame, volume, playerStart, point: (location, yaw)} and
    soldiers: [(location, yaw)] * 6. The yaw of the volume, the player start and the point is the turn they take on
    top of their own (AdjRotation: their own yaw less the frame's, plus StartDir's); the frame's is StartDir's;
    the soldier points face a quarter turn on from where the points start (FaceRot)."""
    start = [float(v) for v in zone['location']]
    yaw = yaw_of(zone['direction'])
    out = {}
    for name, d in OFFSETS.items():
        o = turn(d, yaw)
        out[name] = ([start[k] + o[k] for k in range(3)], yaw)
    kind = zone.get('kind') or 'normal'
    base, base_yaw = start, yaw
    if kind == 'alternate' and zone.get('alternate'):
        base, base_yaw = [float(v) for v in zone['alternate']['location']], yaw_of(zone['alternate']['direction'])
    back = INSIDE_BACK if kind in ('inside', 'alternate', 'noEvac') else 0.0
    face = (base_yaw + QUARTER) % 65536
    out['soldiers'] = []
    for d in SOLDIERS:
        o = turn((d[0], d[1] - back, d[2]), base_yaw)
        out['soldiers'].append(([base[k] + o[k] for k in range(3)], face))
    return out


def ground(zone):
    """The height of the zone's ground (its frame's)."""
    return float(zone['location'][2]) - GROUND


def evac_box(zone):
    """The evac zone's box [x0, y0, z0, x1, y1, z1] (its building volume about its place, turned by StartDir)."""
    (x, y, z), yaw = place(zone)['volume']
    hx, hy = EVAC_SIZE[0] / 2, EVAC_SIZE[1] / 2
    if (yaw // QUARTER) % 2:
        hx, hy = hy, hx
    return [x - hx, y - hy, z - EVAC_SIZE[2] / 2, x + hx, y + hy, z + EVAC_SIZE[2] / 2]


def zone_of_frame(location, yaw):
    """The zone (no id) whose frame stands at `location` turned by `yaw`: the map's own landing as a zone."""
    turns = int(round(yaw / QUARTER)) % 4
    return dict(location=[float(location[0]), float(location[1]), float(location[2]) + GROUND],
                direction=DIRECTIONS[turns], kind='normal')


def _half_up(v):
    """v rounded to a whole number, halves up (web/spawns.js does the same: Math.floor(v + 0.5))."""
    return float(math.floor(v + 0.5))


LEVEL = 64.0     # a level of the tile grid


def fit_zone(actors, bottom=None):
    """The zone (no id) that best fits a landing with no drop zone frame (the tutorial's Act1_IntroLevel, TempleShip,
    the alien bases, DEMO_SonOfFacemelt): of the four directions, the one whose soldier offsets (SOLDIERS turned)
    leave the least worst distance across from the six points' mean place, ties to the first; the place whole units,
    halves up. Its ground (64 under StartLoc) is the lowest of each soldier point's height less 48 and the
    PointInSpace's height, whole units: a standard landing's points stand 48 over its ground and its PointInSpace on
    it, and the tutorial's points float 94 over the road (its PointInSpace at 48, the road at 18). Given the tile
    grid's `bottom`, that ground goes down to the start of its level (as every LWR line's ground is on a level's
    start: the zone's gizmo moves it by whole levels from there): the tutorial's to 0, its road's level. None without
    soldier points. web/spawns.js fitZone is the twin."""
    by = {a['role']: a for a in actors or []}
    points = [by['soldier%d' % n]['location'] for n in range(1, 7) if 'soldier%d' % n in by]
    offsets = [SOLDIERS[n - 1] for n in range(1, 7) if 'soldier%d' % n in by]
    if not points:
        return None
    best = None
    for direction in DIRECTIONS:
        yaw = yaw_of(direction)
        offs = [turn(d, yaw) for d in offsets]
        start = [sum(p[k] - o[k] for p, o in zip(points, offs)) / len(points) for k in (0, 1)]
        worst = max(max(abs(p[k] - start[k] - o[k]) for k in (0, 1)) for p, o in zip(points, offs))
        if best is None or worst < best[0]:
            best = (worst, direction, start)
    lows = [p[2] - (GROUND - 16.0) for p in points] + ([by['point']['location'][2]] if 'point' in by else [])
    ground = min(lows)
    if bottom is not None:
        ground = bottom + math.floor((ground - bottom + 2.0) / LEVEL) * LEVEL
    return dict(location=[_half_up(best[2][0]), _half_up(best[2][1]), _half_up(ground) + GROUND], direction=best[1],
                kind='normal')


def frame_of(landing, bottom=None):
    """The landing's frame as (location, yaw): its drop zone frame's, or for a landing with none, where the fitted
    zone (fit_zone, on a grid whose bottom is `bottom`) would put one. None for a landing with neither."""
    frame = next((a for a in landing.get('actors') or [] if a.get('role') == 'frame'), None)
    if frame:
        return list(frame['location']), frame['rotation'][1]
    zone = fit_zone(landing.get('actors'), bottom)
    if zone is None:
        return None
    location, yaw = place(zone)['frame']
    return location, yaw


def at_own_place(zone, own):
    """Whether `zone` stands where the map's own landing `own` (an own_landings record) has it: the same direction
    and place within half a unit."""
    return bool(own) and zone['direction'] == own['zone']['direction'] and \
        all(abs(float(zone['location'][k]) - float(own['zone']['location'][k])) < 0.5 for k in range(3))


def soldier_spots(zone, own=None):
    """Where the squad stands for `zone`: [(location, yaw)], the six points place() gives, or, for a landing with no
    frame (`own` fitted) whose zone has not moved, the landing's own points as the map has them (their layout is not
    always the mutator's: the tutorial's is its own). web/spawns.js soldierSpots is the twin."""
    if own and own.get('fitted') and at_own_place(zone, own):
        by = {a['role']: a for a in own.get('actors') or []}
        return [(list(by['soldier%d' % n]['location']), by['soldier%d' % n]['rotation'][1])
                for n in range(1, 7) if 'soldier%d' % n in by]
    return place(zone)['soldiers']


def same_place(a, b, slack=2.0):
    """Whether two zones are the same place and direction, within `slack` units (Bar's first line is its own landing
    within two units)."""
    return a['direction'] == b['direction'] and all(abs(float(a['location'][k]) - float(b['location'][k])) <= slack
                                                    for k in range(3))


ZONE_KEYS = ('id', 'location', 'direction', 'kind', 'missionType', 'councilType', 'alternate', 'lwr', 'ew', 'other')
# (matched whole, fullmatch: `$` would take a name ending in a line break, which writes a line of its own)
_TYPE = re.compile(r'[A-Za-z0-9_]+')
# A zone's `other` goes into the game's ini as written, so it must stay on its line: no line break of any kind and no
# control character but a tab, and no longer than a line of the ini is likely to be (web/project.js has the twin)
_OTHER = re.compile(r'[^\x00-\x08\x0a-\x1f\x7f\x85\u2028\u2029]{0,4000}\Z')


def plain_other(text):
    """Whether a zone's `other` can be written into an ini line as it is."""
    return isinstance(text, str) and _OTHER.match(text) is not None


def _finite3(v):
    return isinstance(v, list) and len(v) == 3 and all(isinstance(x, (int, float)) and not isinstance(x, bool)
                                                       and math.isfinite(x) for x in v)


def valid_zone(z):
    """Whether a project's landing zone has the shape research/editor-contracts.md gives it (web/project.js
    validLandingZone is the twin; tests/zone_cases.json holds the cases both pass). A field given is one of its
    kind: null is no value of any of them."""
    if not isinstance(z, dict) or not isinstance(z.get('id'), str) or not z['id'] or set(z) - set(ZONE_KEYS):
        return False
    if not _finite3(z.get('location')) or z.get('direction') not in DIRECTIONS or z.get('kind', 'normal') not in KINDS:
        return False
    if any(k in z and not (isinstance(z[k], str) and _TYPE.fullmatch(z[k])) for k in ('missionType', 'councilType')):
        return False
    alt = z.get('alternate')
    if 'alternate' in z and not (isinstance(alt, dict) and set(alt) == {'location', 'direction'} and _finite3(alt['location'])
                                 and alt['direction'] in DIRECTIONS):
        return False
    return z.get('lwr', False) is False and z.get('ew', True) is True and plain_other(z.get('other', ''))


def kept_for_mission(zone):
    """Whether a zone is kept for one mission or council mission (a landing of the map's own can't be)."""
    return bool(zone.get('missionType') or zone.get('councilType'))


def explicit(zones):
    """Whether the list says which zones plain EW plays (`ew: true` on them: the panel's Plain EW, since 13 November
    2026) rather than by their order."""
    return any('ew' in z for z in zones)


def own_slots(zones, own_count):
    """The indices of the zones that are also the map's own landings, in order, one for each landing the map has: the
    zones marked `ew: true`, the first own_count of them. A list with no zone marked (a project saved before the mark)
    goes by order: the first zones that name no mission (rule 2 of the plan's "One list of landing zones")."""
    if explicit(zones):
        return [k for k, z in enumerate(zones) if z.get('ew') is True][:own_count]
    out = []
    for k, z in enumerate(zones):
        if len(out) >= own_count:
            break
        if not kept_for_mission(z):
            out.append(k)
    return out


def frame_archetype(archetype):
    """Whether an archetype path is the drop zone's frame's (the landing actor every landing has one of)."""
    return str(archetype or '').split('.')[-1] == 'SoldierSpawns_DrpshipVol_12Arc0'


def own_landings(scene):
    """The map's own landings as zones, in order: export 22's `landings` (each with its group and actors), else the
    drop zone frames among the export's pieces (no group, ordered by actor name). Each: dict(zone, group, frame
    (actor path), actors (export 22's list or None)); a landing with no frame (fit_zone) has frame None and
    fitted True."""
    found = []
    bottom = ((scene.get('tileGrid') or {}).get('origin') or [None, None, None])[2]
    for landing in scene.get('landings') or []:
        frame = next((a for a in landing.get('actors') or [] if a.get('role') == 'frame'), None)
        if frame:
            found.append(dict(zone=zone_of_frame(frame['location'], frame['rotation'][1]), group=landing.get('group'),
                              frame=frame['path'], actors=landing.get('actors')))
        else:
            zone = fit_zone(landing.get('actors'), bottom)
            if zone:
                found.append(dict(zone=zone, group=landing.get('group'), frame=None, actors=landing.get('actors'),
                                  fitted=True))
    if found or scene.get('landings') is not None:
        return found
    frames = sorted((o for o in scene.get('objects') or [] if o.get('layer') == 'base' and frame_archetype(o.get('archetype'))),
                    key=lambda o: o['actor'])
    seen = set()
    for o in frames:
        if o['actor'] in seen:
            continue
        seen.add(o['actor'])
        found.append(dict(zone=zone_of_frame(o['location'], o['rotation'][1]), group=None, frame=o['actor'], actors=None))
    return found


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2 or argv[0] != 'check':
        print(__doc__)
        return 2
    with open(argv[1], encoding='latin-1', newline='') as f:
        text = f.read()
    lines = [l for l in text.splitlines() if l.startswith('LZArray=')]
    bad = []
    for line in lines:
        name, zone = parse_line(line)
        if write_line(name, zone) != line:
            bad.append(line)
    print('%d lines, %d written back byte for byte, %d differ' % (len(lines), len(lines) - len(bad), len(bad)))
    for line in bad[:10]:
        print('  ' + line)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())

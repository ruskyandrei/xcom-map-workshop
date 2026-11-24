"""The project's buildings, for the compiler: buildings made from nothing, and the map's own buildings changed or
deleted (the prefab plan, 5.1, and the map buildings plan, sections 2 and 3).

The project's `buildings` records are read once (building_records, building_well_formed: each record that can't be
read, or names a building an earlier one names, is left out), and so are the map's own buildings and why one stays
fixed (map_buildings); the compiler's groups and floors read both. buildings() checks them: a building made from
nothing goes into `new_buildings` (new_building), with what the copies whose source building it comes from carry along
(source_floor_match, from the sources the compiler's add and foreign_piece record in `floor_sources` and
`donor_buildings`); a map building changed or deleted goes into `edits` (moved_whole says whether it moved whole).
They are the spec's `buildings` and `buildingEdits` objects, which compiler.native_split hands to the Build's writer
(tools/bake/buildings.py). The warnings are for a box outside the tile grid, two floors that meet and a floor away from
the cursor's floors.

This family was moved out of compiler.Compiler as SpawnEdits was (review finding 23). A BuildingEdits works for one
Compiler: it reads the map, the scene, the document, the copies, the larger grid and the building floors from it, asks
it whether a family builds (builds) and its floor family for the cursor's floors (cursor_storeys), and says what it
finds through its error, leave_out, warn and note, so the report and the pieces left out are the compiler's as
before.

Its own tables and helpers (BUILDING_SHAPE, BUILDING_KINDS, BUILDING_FLOORS_MAX, BUILDING_SAME, source_floor_match,
moved_whole and the others) are here, and the compiler names again those that others read through it
(compiler.BUILDING_FLOORS_MAX, compiler.source_floor_match, compiler.moved_whole). What the family shares with the
compiler (FAMILIES, MADE_KINDS, QUARTER, POSE_SLACK, map_building_id, short, tidy, turned and the others it imports)
it takes from compiler_tables, so it never imports the compiler.
"""
import math

from compiler_tables import (FAMILIES, MADE_KINDS, POSE_SLACK, QUARTER, game_round, keyable, map_building_id, short,
                             tidy, turned)

# The cursor's floors (the export's cursorVolumes, export 20; the floor family's cursor_storeys): a building's floor
# should start within CURSOR_NEAR of where one starts.
CURSOR_NEAR = 32.0
# a project's buildings made from nothing (buildings): the kinds, the most floors (a CutdownFloor is a byte;
# the game's own buildings have at most 5), and how far two boxes may reach into each other before they overlap
BUILDING_KINDS = ('building', 'ufo')
BUILDING_FLOORS_MAX = 10    # (ten floors of three levels fill a 30-level grid)
BUILDING_OVERLAP = 0.5
# a map building's box is unchanged when every coordinate is within this of its volume's box in the export (the page
# rounds a box to three decimals; the export does not): web/project.js BUILDING_SAME and buildings.SAME are the twins
BUILDING_SAME = 0.01


BUILDING_SHAPE = ('each building is {"id", "name", "kind": "building" or "ufo", "floors": [{"boxes": [[x0, y0, z0, x1, '
                  'y1, z1]]}]}, each floor with at least one box that has room in it, and may have "cursorFloors": true '
                  'or false; one of the map\'s has "replaces": '
                  '{"package", "level", "actor"} and each floor "volumes" as long as its boxes, or is {"id", "replaces", '
                  '"deleted": true}')


def building_well_formed(b):
    """Whether a `buildings` record has the shape BUILDING_SHAPE says."""
    def number(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
    if not isinstance(b, dict) or not isinstance(b.get('id'), str) or not b['id'] \
            or not isinstance(b.get('name', ''), str):
        return False
    rep = b.get('replaces')
    if rep is not None and not (isinstance(rep, dict) and set(rep) == {'package', 'level', 'actor'}
                                and all(isinstance(v, str) for v in rep.values())):
        return False
    if 'cursorFloors' in b and not isinstance(b['cursorFloors'], bool):
        return False
    if 'deleted' in b:
        return b['deleted'] is True and rep is not None and 'floors' not in b
    if not keyable(b.get('kind', 'building')) or b.get('kind', 'building') not in BUILDING_KINDS:
        return False
    floors = b.get('floors')
    if not isinstance(floors, list) or not 1 <= len(floors) <= BUILDING_FLOORS_MAX:
        return False
    for f in floors:
        boxes = f.get('boxes') if isinstance(f, dict) else None
        if not isinstance(boxes, list) or not boxes:
            return False
        for x in boxes:
            if not (isinstance(x, list) and len(x) == 6 and all(number(v) for v in x)
                    and all(x[k + 3] - x[k] >= 1 for k in range(3))):
                return False
        volumes = f.get('volumes')
        if rep is None and volumes is not None:
            return False
        if rep is not None and not (isinstance(volumes, list) and len(volumes) == len(boxes) and all(
                v is None or (isinstance(v, str) and v) for v in volumes)):
            return False
    return True


def source_floor_match(buildings, floors, before, location, rotation):
    """The source building a building of the project comes from, as seen from one piece taken from that source: the
    source's buildings (an export's: floors with boxes {min, max}) carried by the piece's move (from its source pose
    `before` {location, rotation} to `location`, `rotation`, a whole number of quarter turns), each floor paired with
    the project floor its boxes overlap most. `floors`: the project building's ([{boxes: [[x0, y0, z0, x1, y1, z1]]}]).
    The source building chosen is the one that overlaps the project building most, and it must pair its floors with
    distinct project floors (one at least). Returns dict(building, floor_map: [project floor or None per source floor],
    moved: the source's floors carried, [[[x0, y0, z0, x1, y1, z1]]]) or None. The boxes may have been edited since:
    the piece keeps what its map saved where the rule agrees (buildings.carried). web/floors.js sourceFloorMatch is
    the twin; both pass tests/source_floor_match_cases.json."""
    pitch, yaw, roll = [(a - b + 32768) % 65536 - 32768 for a, b in zip(rotation, before['rotation'])]
    turns = game_round(yaw / QUARTER)
    if max(abs(pitch), abs(roll), abs(yaw - turns * QUARTER)) > POSE_SLACK:
        return None
    origin = [*turned(before['location'][:2], turns), before['location'][2]]
    shift = [v - origin[k] for k, v in enumerate(location)]

    def move(point):
        return [v + shift[k] for k, v in enumerate((*turned(point[:2], turns), point[2]))]

    def carry(box):
        a, b = move(box['min']), move(box['max'])
        return [min(v, w) for v, w in zip(a, b)] + [max(v, w) for v, w in zip(a, b)]

    def meet(p, q):
        n = 1.0
        for j in range(3):
            n *= max(0.0, min(p[j + 3], q[j + 3]) - max(p[j], q[j]))
        return n

    best = None
    for b in buildings:
        if not b.get('floors'):
            continue
        moved = [[carry(x) for x in f.get('boxes') or []] for f in b['floors']]
        floor_map, used, total, fine = [], set(), 0.0, True
        for boxes in moved:
            pick, most = None, 0.0
            for j, g in enumerate(floors):
                got = sum(meet(x, y) for x in boxes for y in g['boxes'])
                if got > most:
                    pick, most = j, got
            if pick is not None and pick in used:
                fine = False
            if pick is not None:
                used.add(pick)
            floor_map.append(pick)
            total += most
        if not fine or not used or (best and total <= best[0]):
            continue
        best = (total, dict(building=b, floor_map=floor_map, moved=moved))
    return best[1] if best else None


def moved_whole(old, floors):
    """Whether a map building's floors (dict(boxes, volumes)) are its old ones (dict(volume, box) each) moved
    together: every old volume kept on its floor, every box its old one carried by one move of whole quarter turns
    and a translation that is not nothing. A building moved whole leaves its visibility groups behind."""
    if len(old) != len(floors):
        return False
    pairs = []
    for f, o in zip(floors, old):
        boxes = {v['volume']: v['box'] for v in o}
        if len(f['volumes']) != len(o) or set(f['volumes']) != set(boxes):
            return False
        pairs += [(boxes[v], x) for v, x in zip(f['volumes'], f['boxes'])]
    for turns in range(4):
        def carried(box):
            corners = [turned((box[i], box[j]), turns) for i in (0, 3) for j in (1, 4)]
            return [min(c[0] for c in corners), min(c[1] for c in corners), box[2],
                    max(c[0] for c in corners), max(c[1] for c in corners), box[5]]
        first = carried(pairs[0][0])
        shift = [pairs[0][1][j] - first[j] for j in range(3)]
        if all(all(abs(x[j] - (carried(b)[j] + shift[j % 3])) <= BUILDING_SAME for j in range(6)) for b, x in pairs):
            return turns != 0 or any(abs(v) > BUILDING_SAME for v in shift)
    return False


class BuildingEdits:
    def __init__(self, compiler):
        self.c = compiler
        self.new_buildings = []      # buildings made from nothing: the spec's `buildings` object (buildings())
        self.edits = []              # the map's own buildings changed or deleted: the spec's `buildingEdits` object
        # the source of each copy (add) and the buildings of each other map a piece comes from (the compiler's
        # foreign_piece), which new_building matches a building's floors against
        self.floor_sources = {}
        self.donor_buildings = {}
        # made the first time each is asked for (map_buildings, building_records), then kept: the groups, the floors
        # and buildings() all read them
        self._map_buildings = None
        self._building_records = None

    def map_buildings(self):
        """The export's own buildings (export 21 has their actors): {actor path: (record, why it stays fixed or None)}.
        Fixed: a building with no floors, a van's (it goes with the van), one with a floor that has no floor volume
        or a volume without a box (F-86, F-95), and a patch's. Older exports have none."""
        if self._map_buildings is not None:
            return self._map_buildings
        out = {}
        for b in self.c.scene.get('buildings') or [] if (self.c.scene.get('exporterVersion') or 0) >= 21 else []:
            if not isinstance(b, dict) or not b.get('actor') or not isinstance(b.get('name'), str):
                continue
            floors = b.get('floors') or []
            why = None
            if not floors:
                why = 'it has no floors'
            elif b.get('van'):
                why = "it is a van's own building, which goes with the van"
            elif any(not f.get('volumes') for f in floors):
                why = 'a floor of it has no floor volume'
            elif any(len(f.get('boxes') or []) != len(f['volumes']) for f in floors):
                why = 'a floor volume of it has no box'
            elif not str(b.get('id')).isdigit():
                why = "it is a patch's"
            out[b['name']] = (b, why)
        self._map_buildings = out
        return out

    def building_records(self):
        """The project's `buildings` records this compiler can read: (the records, in order, [(where, why) of each one
        left out]): one that is malformed (building_well_formed), one whose id an earlier record has, or the whole
        value when it is no list. The groups, the floors a copy stands in and buildings() all read these."""
        if self._building_records is None:
            items, kept, dropped, ids = self.c.doc.get('buildings'), [], [], set()
            if items and not isinstance(items, list):
                dropped.append((dict(record='buildings'), '"buildings" is no list'))
            for k, b in enumerate(items if isinstance(items, list) else []):
                where = dict(record='buildings[%d]' % k, **({'building': b['id']} if isinstance(b, dict) and isinstance(b.get('id'), str) else {}))
                if not building_well_formed(b):
                    dropped.append((where, 'building record %d can\'t be read' % (k + 1)))
                elif b['id'] in ids:
                    dropped.append((where, 'building record %d has the id of an earlier one (%s)' % (k + 1, b['id'])))
                else:
                    ids.add(b['id'])
                    kept.append(b)
            self._building_records = (kept, dropped)
        return self._building_records

    def buildings(self):
        """The project's `buildings` (optional; prefab plan 5.1; map buildings plan, sections 2 and 3).
        - Buildings made from nothing, each {id, name, kind: 'building' | 'ufo', floors: [{boxes: [[x0, y0, z0, x1,
          y1, z1]]}]}, floor 0 first, the boxes in world units and unturned. The Build makes a building volume and a
          floor volume for each box, and lists in each floor the pieces standing in it (tools/bake/buildings.py).
          A copied actor whose source building the building comes from (source_floor_match: the source's floors
          carried by the copy's move overlap the building's, their boxes edited or not) keeps what its map saved
          where the rule agrees with the source's boxes and with the building's (`carry`, buildings.carried): the
          map's hand-made inclusion and exclusion lists come along (a UFO's roof listed on its roof floor only).
        - The map's own buildings changed (`replaces` the map's building volume, each floor's `volumes` beside its
          boxes) or deleted (`deleted`): the Build edits them in place (buildings.edit). One the compiler can't use is
          passed over with a warning (building-replaces) and stays as exported; one unchanged (every box within
          BUILDING_SAME of its volume's, the same kind) builds nothing.
        Nothing here stops a Build but an export with no tile grid: a record that can't be read, or that names a
        building an earlier one names, is left out (building-shape, building_records); a box outside the tile grid,
        two floors that meet, a floor away from the cursor's floors are warnings, and for the map's buildings only
        where a box changed (the map's own overlaps, as exported, are not reported).
        - A building made from nothing with `cursorFloors` (the building cursor floors plan) has the cursor's floors of
          its own over its boxes (made_cursors.py; FloorEdits.cursor_areas, cursor_storeys): it is not checked against
          the map's (building-cursor) but for a floor that starts at or under the one before it somewhere
          (building-cursor-order) and for a stair or turned cursor volume of the map under it (building-cursor-volume);
          a note says where its floors start (building-cursor-floors)."""
        items, dropped = self.building_records()
        for where, why in dropped:
            self.c.leave_out('building-shape', '%s, so it is left out (a building of the map\'s stays as the map has it): %s'
                           % (why, BUILDING_SHAPE), **where)
        if not items:
            return
        if not self.c.builds('building'):
            self.c.error('family', 'the project has %s. %s' % (FAMILIES['building']['what'], FAMILIES['building']['note']),
                       family='building')
            return
        grid = self.c.scene.get('tileGrid') or {}
        dims, origin, size = grid.get('dimensions'), grid.get('origin'), grid.get('size')
        if not (dims and origin and size):
            self.c.error('building-grid', 'the export of %s has no tile grid, which a building needs' % self.c.map)
            return
        count = list(self.c.mission_edits.stage_grid or dims[:3])
        lo = [float(v) for v in origin[:3]]
        hi = [lo[k] + count[k] * size[k] for k in range(3)]
        storeys = self.c.floor_edits.cursor_storeys()
        own_cursor = {a['id'] for a in self.cursor_floors()}

        def meet(a, b):
            return all(min(a[k + 3], b[k + 3]) - max(a[k], b[k]) > BUILDING_OVERLAP for k in range(3))

        # every box after the edit: dict(building id, label, floor, box, changed, own: the map's, authored)
        boxes, replaced, gone = [], set(), set()
        exported = self.map_buildings()
        for b in items:
            if b.get('replaces') is None:
                self.new_building(b, boxes)
                continue
            rep = b['replaces']
            where = dict(building=b['id'])
            found = exported.get(rep['actor']) if rep['package'].casefold() == self.c.map.casefold() and rep['level'] == 'base' else None
            why = found[1] if found else ('the export of %s has no buildings\' actors (export 21): prepare it again'
                                          % self.c.map if (self.c.scene.get('exporterVersion') or 0) < 21
                                          else 'it is not one of the map\'s buildings')
            if not why and rep['actor'] in replaced:
                why = 'an earlier record names it'
            if why:
                self.c.warn('building-replaces', 'the record for the map\'s building %s is passed over: %s; the building '
                          'stays as the map has it' % (short(rep['actor']), why), **where)
                continue
            replaced.add(rep['actor'])
            e = found[0]
            label = b.get('name') or e['actor']
            old = [[dict(volume=short(v), box=list(x['min']) + list(x['max'])) for v, x in zip(f['volumes'], f['boxes'])]
                   for f in e['floors']]
            if b.get('deleted'):
                gone.add(rep['actor'])
                if e.get('referencedBy'):
                    self.c.warn('mission-linked', "the map's building %s is named by the map's Kismet (%s): deleted, its "
                              "script acts on a volume out of the level" % (label, '; '.join(e['referencedBy'])), **where)
                self.edits.append(dict(id=b['id'], actor=e['actor'], name=label, deleted=True, old=old,
                                                kind='ufo' if e.get('isUfo') else 'building', moved=False))
                continue
            own_volumes = {v['volume']: v['box'] for f in old for v in f}
            floors, used = [], set()
            for k, f in enumerate(b['floors']):
                vols = []
                for v in f['volumes']:
                    if v is not None and (v not in own_volumes or v in used):
                        self.c.warn('building-replaces', 'floor %d of the map\'s building %s names the floor volume %s, '
                                  'which is %s: its box gets a new volume' % (
                                      k + 1, label, v, 'named twice' if v in used else 'not one of the building\'s'), **where)
                        v = None
                    if v is not None:
                        used.add(v)
                    vols.append(v)
                floors.append(dict(boxes=[[tidy(float(x), 3) for x in box] for box in f['boxes']], volumes=vols))
            same_box = lambda box, v: v is not None and all(abs(box[j] - own_volumes[v][j]) <= BUILDING_SAME for j in range(6))
            unchanged = (len(floors) == len(old) and (b.get('kind', 'building') == 'ufo') == bool(e.get('isUfo'))
                         and all(sorted(filter(None, f['volumes'])) == sorted(v['volume'] for v in o) and len(f['volumes']) == len(o)
                                 and all(same_box(x, v) for x, v in zip(f['boxes'], f['volumes'])) for f, o in zip(floors, old)))
            for k, f in enumerate(floors):
                for x, v in zip(f['boxes'], f['volumes']):
                    boxes.append(dict(building=b['id'], label=label, floor=k, box=x, own=True, authored=False,
                                      changed=not same_box(x, v),
                                      bottom=own_volumes[v][2] if v is not None else None))
            if unchanged:
                continue
            if e.get('referencedBy'):
                self.c.warn('mission-linked', "the map's building %s is named by the map's Kismet (%s): it is edited in "
                          "place, so the script still finds it, but moved or resized it may act differently"
                          % (label, '; '.join(e['referencedBy'])), **where)
            self.edits.append(dict(id=b['id'], actor=e['actor'], name=label, deleted=False,
                                            kind=b.get('kind', 'building'), floors=floors, old=old,
                                            moved=moved_whole(old, floors)))
        # the map's buildings left as exported (fixed ones too), and the ones of no record
        for path, (e, why) in exported.items():
            if path in replaced:
                continue
            for k, f in enumerate(e.get('floors') or []):
                for x in f.get('boxes') or []:
                    boxes.append(dict(building=map_building_id(e), label=e['actor'], floor=k, own=True, authored=False,
                                      box=list(x['min']) + list(x['max']), changed=False))
        if (self.c.scene.get('exporterVersion') or 0) < 21:
            # an older export: the map's floor volumes by building name (export 15)
            for name, index, xs in self.c.floor_boxes or []:
                for x in xs:
                    boxes.append(dict(building='map|' + name, label=short(name), floor=index, own=True, authored=False,
                                      box=list(x['min']) + list(x['max']) if isinstance(x, dict) else list(x), changed=False))
        # the warnings, for each changed or new box
        said = set()
        for n, item in enumerate(boxes):
            if not item['changed']:
                continue
            x, k, label = item['box'], item['floor'], item['label']
            where = dict(building=item['building'], floor=k, box=x)
            if any(x[j] < lo[j] - 0.5 or x[j + 3] > hi[j] + 0.5 for j in range(3)):
                self.c.note('building-outside', 'floor %d of the building %s reaches outside the map\'s tile grid: the '
                          'game has no tiles there' % (k + 1, label), **where)
            for m, other in enumerate(boxes):
                if m == n or (other['building'] == item['building'] and (other['floor'] == k or item['authored'])):
                    continue
                if (min(m, n), max(m, n)) in said or not meet(x, other['box']):
                    continue
                said.add((min(m, n), max(m, n)))
                whose = ('the same building' if other['building'] == item['building'] else
                         "the map's own building %s" % other['label'] if other['own'] and not other['changed']
                         else 'the building %s' % other['label'])
                self.c.warn('building-overlap', 'floor %d of the building %s overlaps floor %d of %s: a piece in both is '
                          'listed by both, and a unit there may see either floor cut away' % (k + 1, label, other['floor'] + 1, whose),
                          **where)
            if item['building'] in own_cursor:
                continue
            starts = sorted({round(c[2], 2) for _, c in storeys or []
                             if min(c[3], x[3]) - max(c[0], x[0]) > 0 and min(c[4], x[4]) - max(c[1], x[1]) > 0})
            # (a map box at its volume's own height, moved sideways or stretched across, is as the map had it)
            same_height = item.get('bottom') is not None and abs(item['bottom'] - x[2]) <= BUILDING_SAME
            if starts and not same_height and not any(abs(x[2] - z) <= CURSOR_NEAR for z in starts):
                self.c.warn('building-cursor', 'floor %d of the building %s starts at %g, away from where the cursor\'s '
                          'floors start there (%s): the mouse wheel would not stop at this storey'
                          % (k + 1, label, x[2], ', '.join('%g' % z for z in starts)), starts=starts, **where)
        if self.c.errors:
            self.new_buildings, self.edits = [], []

    def cursor_floors(self):
        """The buildings whose floors are the cursor's (FloorEdits.cursor_areas), checked once: each one's floors left
        out somewhere for starting at or under the one before (building-cursor-order), a stair or turned cursor volume
        of the map under it (building-cursor-volume), and where its floors start (building-cursor-floors, a note).
        Returns the areas."""
        areas = self.c.floor_edits.cursor_areas()
        if getattr(self, '_cursor_said', False) or not areas:
            return areas
        self._cursor_said = True
        import made_cursors
        volumes = [dict(key=v.get('name') or str(k), floor=v.get('floor'), box=list(v['box']['min']) + list(v['box']['max']),
                        stair=bool(v.get('stair')))
                   for k, v in enumerate(self.c.scene.get('cursorVolumes') or []) if v.get('box')] \
            if not self.c.mission_edits.pieces_cleared else []
        crossed = {}
        for c in made_cursors.split(volumes, [], None, areas)['crossed']:
            crossed.setdefault(c['building'], set()).add('%s (%s)' % (short(str(c['volume'])), "a stair's" if c['why'] == 'stair' else 'turned'))
        for a in areas:
            where = dict(building=a['id'])
            starts = []
            for k, boxes in enumerate(a['floors']):
                starts.append('%d from %g' % (k + 1, min(x[2] for x in boxes)))
            self.c.note('building-cursor-floors', "the cursor's floors over the building %s are its own: floor %s (each a "
                        "little under its box's bottom, up to the next floor's)" % (a['label'], ', '.join(starts)), **where)
            late = made_cursors.unordered(a)
            if late:
                self.c.warn('building-cursor-order', 'floor %s of the building %s starts at or under the floor before it '
                            'over part of the building, so the mouse wheel does not stop at %s there: raise %s box'
                            % (' and '.join(str(f) for f in late), a['label'], 'it' if len(late) == 1 else 'them',
                               'its' if len(late) == 1 else 'their'), floors=late, **where)
            names = crossed.get(a['label'])
            if names:
                self.c.warn('building-cursor-volume', "the building %s is over the map's cursor %s %s, which the Build leaves "
                            "as %s over it: the cursor may keep to %s floor there rather than the building's" % (
                                a['label'], 'volume' if len(names) == 1 else 'volumes', ', '.join(sorted(names)),
                                'it is' if len(names) == 1 else 'they are', 'its' if len(names) == 1 else 'their'), **where)
        return areas

    def new_building(self, b, boxes):
        """A building made from nothing (buildings()): into self.new_buildings, with `carry` {copy label: dict(saved:
        [[floor, CutdownFloor]] as its map saved them, floors: its source building's boxes carried by the copy's move,
        floor_map: the building's floor for each of those)} for the copies whose source building it comes from
        (source_floor_match); its boxes into `boxes`."""
        label = b.get('name') or b['id']
        carry = {}
        for copy in self.c.copies:
            source = self.floor_sources.get(copy['label'])
            # (a wall made from numbers is not its donor: the rule lists it by its own box, custom geometry plan M3)
            if source is None or (copy.get('generated') or {}).get('kind') in MADE_KINDS + ('ground',):
                continue
            donor = copy.get('donor')
            originals = self.donor_buildings.get(donor['package'].casefold(), []) if donor else (self.c.scene.get('buildings') or [])
            before = dict(location=source.get('floorLocation', source['location']), rotation=source['rotation'])
            match = source_floor_match(originals, b['floors'], before, copy['location'], copy['rotation'])
            if match:
                carry[copy['label']] = dict(
                    saved=[[f['floor'], f['cutdownFloor']] for f in source.get('floors', []) if f['building'] == match['building']['id']],
                    floors=[[[tidy(v, 3) for v in x] for x in f] for f in match['moved']], floor_map=match['floor_map'])
        for k, f in enumerate(b['floors']):
            for x in f['boxes']:
                boxes.append(dict(building=b['id'], label=label, floor=k, box=[float(v) for v in x], own=False,
                                  authored=bool(carry), changed=True))
        self.new_buildings.append(dict(id=b['id'], name=b.get('name') or '', kind=b.get('kind', 'building'),
                                       **({'carry': carry} if carry else {}),
                                       **({'cursorFloors': True} if b.get('cursorFloors') is True else {}),
                                       floors=[dict(boxes=[[tidy(float(v), 3) for v in x] for x in f['boxes']])
                                               for f in b['floors']]))

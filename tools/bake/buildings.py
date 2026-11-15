"""Buildings made from nothing in a map: a building volume, a floor volume for each box of each floor, and each floor's
list of the pieces standing in it, so that the roof and the upper floors hide and the walls cut down as in a building
of the game's own (private/plans/done/prefab-library-plan.md, 5.1 and 5.2; findings register F-86 and F-87).

A building of the native edit: {id, name, kind: 'building' | 'ufo', floors: [{boxes: [[x0, y0, z0, x1, y1, z1]]}]},
floor 0 first, boxes in world units, unturned.

  make(g, p, buildings, pieces)        called by native_copy.py after its copies are made
  edit(g, p, edits, pieces, ...)       the map's own buildings changed or deleted, edited in place (map buildings plan)
  python -B tools/bake/buildings.py <map.upk> [building]     what a map's buildings save, read back (survey)

What is made, each a clone of a template the map has (templates): the map's own, or one the Build's shell stage staged
(shell.py):
- the building volume: its brush stretched over the union of the floors' boxes (Location and DrawScale3D), its Tag
  the class's name (a template's may be one LWR's randomiser acts on), no mesh groups;
- the floor volumes: one for each box, stretched over it, FloorNumber its floor's index plus one;
- Floors: an entry for each floor, naming its floor volumes and its pieces.

Which pieces a floor lists is the game editor's own rule (F-87; audit_buildings.touched and listing): a piece counts
for every floor one of whose boxes it touches with its bottom more than 20 units under that box's top; a piece with
bCutoutMask on its main mesh component is listed on the lowest of them only, with the highest as its CutdownFloor; any
other piece on each. A piece's box is its main mesh's, at its pose, and comes within SLACK units of a box to touch it
(the game goes by collision, a little larger than the mesh); a piece that collides with nothing touches no floor (rule).
`pieces` are the candidates: the map's own placed pieces that are not hidden, and the copies. The compiler supplies a
`carry` by copy label for the copies whose source building a building comes from (compiler.source_floor_match): such a
copy keeps what its map saved, the map's hand-made inclusion and exclusion lists with it, where the rule agrees
(carried; members).
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'upk'))
import audit_buildings  # noqa: E402
import native_copy  # noqa: E402
import native_lights  # noqa: E402
import props as legacy_props  # noqa: E402

PL = native_copy.PL
SLACK = 2.0
# a box of a map building is unchanged when every coordinate is within this of its volume's (compiler.BUILDING_SAME)
SAME = 0.01
# the classes the game's buildings list (F-86); a StaticMeshActor has no floor component and never hides
LISTED = ('XComLevelActor', 'XComOpacityFadeLevelActor', 'XComDestructibleActor', 'XComFracLevelActor', 'XComDecoFracLevelActor',
          'XComInteractiveLevelActor', 'XComLadder', 'XComCollectible', 'KAsset')
KINDS = ('building', 'ufo')


def start_of(p, index):
    e = p.exports[index - 1]
    return legacy_props.props_start(p.data, e, p.names) - e['off']


def level_actors(p, cls):
    level = p.by_name['TheWorld.PersistentLevel']
    return [i for i in p.children.get(level, []) if p.cls(i) == cls]


def building_template(p, walker):
    """A building volume to clone: a plain volume (an actor, a brush component, a model) of the level, with no
    archetype and no mesh groups, whose floors hold a floor entry with a CutdownFloor and one without (the two shapes
    an entry is written in). Returns dict(actor, floor: a floor element's bytes with only its two lists, plain and cut:
    an entry of each shape (struct_entries'), none: the eight bytes that close a struct) or None."""
    for i in sorted(level_actors(p, 'XComBuildingVolume'), key=lambda i: -p.exports[i - 1]['size']):
        if not native_copy.plain_volume(p, i) or p.exports[i - 1]['arch'] or p.own(i, 'ExternalMeshGroups') is not None:
            continue
        b = bytes(p.data[p.exports[i - 1]['off']:p.exports[i - 1]['off'] + p.exports[i - 1]['size']])
        found = native_copy.find_prop(walker, b, start_of(p, i), len(b), 'Floors[0]')
        if found is None:
            continue
        plain = cut = floor = None
        for s, e in native_copy.struct_elements(walker, b, found[2], found[3]):
            volumes = native_copy.find_prop(walker, b, s, e, 'FloorVolumes[0]')
            field = native_copy.find_prop(walker, b, s, e, 'm_aCachedActors[0]')
            if volumes is None or field is None:
                continue
            floor = floor or (s, e)
            for entry in native_copy.struct_entries(walker, b, field, 'ResidentActor'):
                if entry['actorAt'] is None:
                    continue
                if entry['cutdownAt'] is not None:
                    cut = cut or entry
                elif entry['minZAt'] is None:
                    plain = plain or entry
        if plain and cut and floor:
            return dict(actor=i, bytes=b, floors=found, floor=floor, plain=plain, cut=cut, none=b[floor[1] - 8:floor[1]])
    return None


def floor_template(p):
    """A floor volume to clone: a plain volume of the level that saves a FloorNumber and neither an inclusion nor an
    exclusion list, the largest first (it is stretched less)."""
    def size(i):
        _, extent = native_copy.brush_bounds(p, i)
        return extent[0] * extent[1] * extent[2]
    found = [i for i in level_actors(p, 'XComFloorVolume')
             if native_copy.plain_volume(p, i) and p.own(i, 'FloorNumber') is not None and p.own(i, 'Brush', 0) > 0
             and p.own(i, 'm_aInclusionActors') is None and p.own(i, 'm_aExclusionActors') is None
             and not any(p.own(i, 'Rotation', [0, 0, 0]))]
    return max(found, key=size) if found else None


def templates(p, walker=None):
    """(building template, floor volume template), either None when the map has none to clone."""
    return building_template(p, walker or native_copy.Walker(p)), floor_template(p)


def clone_volume(g, p, walker, template, box, tag, edit=None):
    """The plain volume `template` cloned and stretched over `box` ([x0, y0, z0, x1, y1, z1], world): its actor and
    its brush component, the actor's Location and DrawScale3D set, its Tag the name `tag`. `edit(data, start)` changes
    the actor's bytes further before they are written. Returns the new actor's export index."""
    ti = template
    tc = p.own(ti, 'BrushComponent', 0)
    origin, extent = native_copy.brush_bounds(p, ti)
    half = [(box[k + 3] - box[k]) / 2 for k in range(3)]
    centre = [(box[k + 3] + box[k]) / 2 for k in range(3)]
    scale = [half[k] / extent[k] for k in range(3)]
    location = [centre[k] - scale[k] * origin[k] for k in range(3)]
    first = len(g.entries) + 1
    mapping = {ti: first, tc: first + 1}
    for old in (ti, tc):
        e = p.exports[old - 1]
        data = bytearray(p.data[e['off']:e['off'] + e['size']])
        start = start_of(p, old)
        for _, at in walker.refs(bytes(data), start, len(data)):
            value = struct.unpack_from('<i', data, at)[0]
            if value in mapping:
                struct.pack_into('<i', data, at, mapping[value])
        g.fresh_net_index(old, data, at=start - 4)
        if old == ti:
            at = walker.value(bytes(data), start, len(data), 'Tag[0]')
            if at is not None:
                struct.pack_into('<ii', data, at, g.name(tag), 0)
            # the caller's changes first; they and these can add a property whose name is new to the map (DrawScale3D
            # on the blank map, IsUfo for a UFO), which a walker knowing the map's own names only cannot walk past, so
            # these walk with the names the package has by now (the grower's: the map's, then the ones added)
            if edit:
                data = edit(bytearray(data), start)
            grown = native_copy.Walker(p)
            grown.names = g.names
            data = native_copy.set_vector(grown, g, data, start, 'Location', location)
            data = native_copy.set_vector(grown, g, data, start, 'DrawScale3D', scale)
            new = g.add_export(old, bytes(data), number=g.unused_number(g.entries[old - 1].name_index))
        else:
            new = g.add_export(old, bytes(data), number=g.entries[old - 1].name_number)
            g.entries[new - 1].put('<i', 8, mapping[ti])
        if new != mapping[old]:
            raise ValueError('the volume clones did not get the planned indices')
    return mapping[ti]


def main_mesh(p, actor):
    return next((k for k in p.children.get(actor, []) if 'MeshComponent' in p.cls(k)), None)


def piece_box(p, piece, meshes):
    """A candidate's world box [x0, x1, y0, y1, z0, z1] from its main mesh at its pose, or None when it has no mesh
    that reads. `piece`: dict(source: the export whose mesh it has, location, rotation: its pose, None for the
    source's own)."""
    source = piece['source']
    if source not in meshes:
        # the box at the piece's own pose, once for each source: a copy's is that box carried by its move
        try:
            meshes[source] = native_copy.piece_box(p, source, p.own(source, 'Location', [0.0, 0.0, 0.0]),
                                                   p.own(source, 'Rotation', [0, 0, 0]))
        except Exception:  # noqa: BLE001  a mesh the reader does not take is no member
            meshes[source] = None
    if meshes[source] is None or piece.get('location') is None:
        return meshes[source]
    try:
        return native_copy.piece_box(p, source, piece['location'], piece.get('rotation') or p.own(source, 'Rotation', [0, 0, 0]))
    except Exception:  # noqa: BLE001
        return None


def rule(p, source, box, floors):
    """The game editor's rule for a piece whose mesh and flags are export `source`'s, with world box `box`, against
    `floors` ([[box]]): [(floor, CutdownFloor)] (audit_buildings.touched and listing). None ([]) for a piece that
    collides with nothing: the game lists the actors that touch a floor volume, and only one that collides does (F-87;
    over the install's maps this alone takes the rule from 65% to 83% right on the pieces near a building it doesn't
    list, the listed ones as before)."""
    if not native_copy.collides(p, source):
        return []
    mesh = main_mesh(p, source)
    mask = bool(mesh and p.effective(mesh, 'bCutoutMask', False))
    return audit_buildings.listing(audit_buildings.touched(box, floors, slack=SLACK), mask)


def members(p, floors, pieces, meshes=None, carry=None):
    """Each floor's entries by the game editor's rule: [[(piece, CutdownFloor)]] for `floors` ([[box]]) and the
    candidates `pieces` ([dict(actor: the export a floor is to name, source, location, rotation, label)]); and the
    pieces with no box. `carry` {label: dict(saved, floors, floor_map)} (the compiler's): a copy whose source
    building this one comes from keeps what its map saved where the rule gives the same with the source's boxes
    (`floors`, carried by the copy's move) as with these (carried()); one with no box keeps it outright."""
    meshes = {} if meshes is None else meshes
    carry = carry or {}
    out, unread = [[] for _ in floors], []
    for piece in pieces:
        if p.cls(piece['source']) not in LISTED:
            continue
        box = piece_box(p, piece, meshes)
        c = carry.get(piece.get('label'))
        if c is not None:
            old, new = (rule(p, piece['source'], box, c['floors']), rule(p, piece['source'], box, floors)) if box else ([], [])
            entries, _ = carried([tuple(x) for x in c['saved']], old, new, dict(enumerate(c['floor_map'])))
            for k, cut in entries:
                out[k].append((piece, cut))
            continue
        if box is None:
            unread.append(piece)
            continue
        for k, cut in rule(p, piece['source'], box, floors):
            out[k].append((piece, cut))
    return out, unread


def floor_bytes(g, walker, t, volumes, entries):
    """A Floors element: the template's floor with only its two lists, FloorVolumes naming `volumes` (export indices)
    and m_aCachedActors holding `entries` ([(export index, CutdownFloor)])."""
    raw = []
    for actor, cut in entries:
        e = bytearray(native_copy.entry_for(t['cut'] if cut else t['plain'], actor))
        if cut:
            e[t['cut']['cutdownAt']] = cut
        raw.append(bytes(e))
    payloads = {'FloorVolumes[0]': struct.pack('<i', len(volumes)) + b''.join(struct.pack('<i', v) for v in volumes),
                'm_aCachedActors[0]': struct.pack('<i', len(raw)) + b''.join(raw)}
    b, (s, e) = t['bytes'], t['floor']
    out = []
    for prop, kind, sub, at, size in walker.walk(b, s, e):
        if prop in payloads:
            tag = bytearray(b[at - 24:at])
            struct.pack_into('<i', tag, 16, len(payloads[prop]))
            out.append(bytes(tag) + payloads[prop])
    if len(out) != 2:
        raise ValueError('the building template\'s floor does not save both lists')
    return b''.join(out) + t['none']


def check(buildings):
    """The shape of the native edit's buildings; raises ValueError."""
    for b in buildings:
        if b.get('kind', 'building') not in KINDS or not b.get('floors'):
            raise ValueError('building %s: a kind of %s and at least one floor' % (b.get('name') or b.get('id'), KINDS))
        for floor in b['floors']:
            boxes = floor.get('boxes') or []
            if not boxes or any(len(x) != 6 or not all(x[k + 3] - x[k] >= 1 for k in range(3)) for x in boxes):
                raise ValueError('building %s: each floor needs boxes [x0, y0, z0, x1, y1, z1] with room in them'
                                 % (b.get('name') or b.get('id')))


def make(g, p, buildings, pieces):
    """The buildings made in the map `g` grows. Returns (the new actors for the level's list, the report: [dict(id,
    name, kind, building, box, floors: [dict(volumes, boxes, members: [dict(actor, cutdown)])], unread)])."""
    check(buildings)
    walker = native_copy.Walker(p)
    bt, ft = templates(p, walker)
    if bt is None or ft is None:
        raise ValueError('the map has no %s to clone a new building from' % ' and no '.join(
            n for n, t in (('building volume with floors', bt), ('plain floor volume', ft)) if t is None))
    actors, report, meshes = [], [], {}
    number_at = None
    for b in buildings:
        floors = [[list(map(float, x)) for x in f['boxes']] for f in b['floors']]
        listed, unread = members(p, floors, pieces, meshes, b.get('carry'))
        volumes = []
        for k, boxes in enumerate(floors):
            made = []
            for box in boxes:
                def numbered(data, start, k=k):
                    return native_lights.set_property(walker, g, data, start, 'FloorNumber', 'IntProperty', None,
                                                      struct.pack('<i', k + 1))
                made.append(clone_volume(g, p, walker, ft, box, 'XComFloorVolume', numbered))
            volumes.append(made)
        every = [x for boxes in floors for x in boxes]
        union = [min(x[k] for x in every) for k in range(3)] + [max(x[k + 3] for x in every) for k in range(3)]
        elements = [floor_bytes(g, walker, bt, volumes[k], [(piece['actor'], cut) for piece, cut in listed[k]])
                    for k in range(len(floors))]

        def edit(data, start, elements=elements, kind=b.get('kind', 'building')):
            found = native_copy.find_prop(walker, bytes(data), start, len(data), 'Floors[0]')
            data = bytearray(native_copy.rebuilt(bytes(data), found, elements))
            vis = native_copy.find_prop(walker, bytes(data), start, len(data), 'VisGroupIdxToHideWhenOccluding[0]')
            if vis is not None:
                _, tag, at, size = vis
                data = bytearray(data[:at]) + struct.pack('<i', 0) + bytes(data[at + size:])
                struct.pack_into('<i', data, tag + 16, 4)
            if kind == 'ufo':
                data = native_lights.set_property(walker, g, data, start, 'IsUfo', 'BoolProperty', None, b'\x01')
            return data
        building = clone_volume(g, p, walker, bt['actor'], union, 'XComBuildingVolume', edit)
        actors += [building] + [v for made in volumes for v in made]
        report.append(dict(id=b.get('id'), name=b.get('name'), kind=b.get('kind', 'building'), building=building,
                           box=union, floors=[dict(volumes=volumes[k], boxes=floors[k],
                                                   members=[dict(actor=piece['actor'], name=piece.get('name'), cutdown=cut)
                                                            for piece, cut in listed[k]])
                                              for k in range(len(floors))],
                           unread=[piece.get('name') for piece in unread]))
    return actors, report



# ---------------------------------------------------------------- the map's own buildings edited in place
def carried(saved, old_rule, new_rule, floor_map):
    """A piece's entries in an edited building (map buildings plan, section 3): the rule (listing()) worked out with
    the old boxes at its old pose (`old_rule`, old floor indices) and with the new boxes at its new pose (`new_rule`,
    new indices). Where the two agree, once the old floors are carried to the new by `floor_map` ({old index: new
    index or None}, floors compared by their volumes), the piece keeps what the map saved (`saved`: [(floor,
    CutdownFloor)], old indices, carried the same way); else the new rule's answer is used. Returns (entries, kept).
    web/floors.js carriedListing is the twin; both pass tests/carried_listing_cases.json."""
    def mapped(entries):
        out = []
        for k, cut in entries:
            if floor_map.get(k) is None or (cut and floor_map.get(cut) is None):
                return None
            out.append((floor_map[k], floor_map[cut] if cut else 0))
        return sorted(out)
    old = mapped(old_rule)
    if old is not None and old == sorted(new_rule):
        kept = mapped(saved)
        if kept is not None:
            return kept, True
    return sorted(new_rule), False


def floor_map(old_volumes, new_volumes):
    """{old floor index: the new floor that holds one of its volumes (the lowest), or None}: old_volumes [[name]] and
    new_volumes [[name or None]] per floor."""
    where = {}
    for j, names in enumerate(new_volumes):
        for v in names:
            if v is not None and v not in where:
                where[v] = j
    return {k: min((where[v] for v in names if v in where), default=None) for k, names in enumerate(old_volumes)}


def grown_walker(p, g):
    """A walker of the package as it grows: the names `g` added after the map's own."""
    w = native_copy.Walker(p)
    w.names = g.names
    return w


def placed(p, volume, box):
    """(Location, DrawScale3D) that put a plain volume's brush over `box` ([x0, y0, z0, x1, y1, z1]), as
    clone_volume works them out; DrawScale is kept."""
    origin, extent = native_copy.brush_bounds(p, volume)
    d = p.own(volume, 'DrawScale', 1.0) or 1.0
    half = [(box[k + 3] - box[k]) / 2 for k in range(3)]
    centre = [(box[k + 3] + box[k]) / 2 for k in range(3)]
    scale = [half[k] / (extent[k] * d) for k in range(3)]
    return [centre[k] - scale[k] * d * origin[k] for k in range(3)], scale


def world_box(p, volume):
    import scene_metadata
    b = scene_metadata.volume_bounds(p, volume)
    return list(b['min']) + list(b['max']) if b else None


def same_box(a, b):
    return a is not None and b is not None and all(abs(a[k] - b[k]) <= SAME for k in range(6))


def put_volume(g, p, volume, box, number=None):
    """A floor volume of the map moved and stretched in place over `box`: its Location, and DrawScale3D when its size
    changed (or it saves one), and its FloorNumber when `number` is given. Returns what changed: 'moved', 'stretched',
    'renumbered' or None."""
    w = grown_walker(p, g)
    old = world_box(p, volume)
    e = p.exports[volume - 1]
    start = start_of(p, volume)
    data = bytearray(g.export_data(volume))
    what = None
    if not same_box(old, box):
        location, scale = placed(p, volume, box)
        stretched = any(abs((box[k + 3] - box[k]) - (old[k + 3] - old[k])) > SAME for k in range(3))
        data = native_copy.set_vector(w, g, data, start, 'Location', location)
        if stretched or p.own(volume, 'DrawScale3D') is not None:
            data = native_copy.set_vector(w, g, data, start, 'DrawScale3D', scale)
        what = 'stretched' if stretched else 'moved'
    if number is not None and p.own(volume, 'FloorNumber') != number:
        data = native_lights.set_property(w, g, data, start, 'FloorNumber', 'IntProperty', None, struct.pack('<i', number))
        what = what or 'renumbered'
    if what:
        g.relocate(volume, bytes(data))
    del e
    return what


def edit(g, p, edits, pieces, gone=(), copies=None):
    """The map's own buildings changed or deleted (the compiler's buildingEdits: id, actor, name, kind, deleted,
    moved, floors: [dict(boxes, volumes)]), edited in place in the map `g` grows (map buildings plan, section 4).
    `pieces`: the candidates as make() takes them (the map's placed pieces not hidden, and the copies with their
    source); `gone`: the hidden pieces (export indices); `copies`: {original: its copy} of the pieces moved.
    - Floor volumes: a box that has not changed keeps its volume (FloorNumber set where its floor's number did); one
      moved or stretched keeps its volume with Location and DrawScale3D set, unless it is stretched and not a plain
      box (its notches would stretch: a plain clone takes its place); a new box gets a clone of the plain template; a
      volume no box keeps is taken out of the level.
    - Floors rewritten: each floor names its volumes and lists its pieces by carried() (the map's saved entries where
      the rule's answer did not change); its other properties are the old floor's it comes from; saved emitters stay
      on a floor whose boxes still hold them. The building volume's box follows the union of the boxes,
      VisGroupIdxToHideWhenOccluding is emptied when the building moved whole, ExternalMeshGroups point at the copies
      of pieces moved, IsUfo follows the kind.
    - A deleted building: the building volume and its floor volumes taken out of the level; its pieces stay.
    Returns (the new actors for the level's list, the actors to take out of it, the report)."""
    import scene_metadata
    copies = copies or {}
    gone = set(gone)
    walker = native_copy.Walker(p)
    t = building_template(p, walker)
    ft = None
    actors, slots, report = [], set(), []
    meshes = {}
    for ed in edits:
        i = p.by_name.get(PL + ed['actor'])
        if i is None or p.cls(i) != 'XComBuildingVolume':
            raise ValueError('the map has no building volume %s to edit' % ed['actor'])
        b = g.export_data(i)
        start = start_of(p, i)
        found = native_copy.find_prop(walker, b, start, len(b), 'Floors[0]')
        old = []        # per old floor: dict(element, volumes: [export], names, boxes, field, entries, emitters)
        for s0, e0 in native_copy.struct_elements(walker, b, found[2], found[3]) if found else []:
            vols = native_copy.find_prop(walker, b, s0, e0, 'FloorVolumes[0]')
            refs = [r for r in struct.unpack_from('<%di' % struct.unpack_from('<i', b, vols[2])[0], b, vols[2] + 4)
                    if r > 0] if vols else []
            field = native_copy.find_prop(walker, b, s0, e0, 'm_aCachedActors[0]')
            emitters = native_copy.object_array(walker, b[s0:e0], 0, 'm_aCachedEmitters')
            old.append(dict(element=(s0, e0), volumes=refs, names=[p.name(r).split('.')[-1] for r in refs],
                            boxes=[world_box(p, r) for r in refs], field=field,
                            entries=native_copy.struct_entries(walker, b, field, 'ResidentActor'), emitters=emitters))
        every = [v for f in old for v in f['volumes']]
        if ed.get('deleted'):
            slots |= {i, *every}
            report.append(dict(id=ed['id'], actor=ed['actor'], deleted=True,
                               volumes=[p.name(v).split('.')[-1] for v in every]))
            continue
        by_name = {p.name(v).split('.')[-1]: v for v in every}
        new_floors = [[[float(x) for x in box] for box in f['boxes']] for f in ed['floors']]
        new_names = [list(f['volumes']) for f in ed['floors']]
        record = dict(kept=[], moved=[], stretched=[], replaced=[], made=[], removed=[])
        volumes = []    # per new floor: export indices
        for j, (boxes, names) in enumerate(zip(new_floors, new_names)):
            made = []
            for box, name in zip(boxes, names):
                v = by_name.get(name) if name else None
                if v is not None:
                    was = world_box(p, v)
                    stretched = any(abs((box[k + 3] - box[k]) - (was[k + 3] - was[k])) > SAME for k in range(3))
                    if stretched and scene_metadata.plain_box(p, v) is False:
                        record['replaced'].append(name)
                        slots.add(v)
                        v = None
                if v is None:
                    if ft is None:
                        ft = floor_template(p)
                        if ft is None:
                            raise ValueError('the map has no plain floor volume to clone a new box from')

                    def numbered(data, start, j=j):
                        return native_lights.set_property(grown_walker(p, g), g, data, start, 'FloorNumber',
                                                          'IntProperty', None, struct.pack('<i', j + 1))
                    v = clone_volume(g, p, walker, ft, box, 'XComFloorVolume', numbered)
                    actors.append(v)
                    record['made'].append(v)
                else:
                    what = put_volume(g, p, v, box, j + 1)
                    record['moved' if what == 'moved' else 'stretched' if what == 'stretched' else 'kept'].append(name)
                made.append(v)
            volumes.append(made)
        kept_volumes = {v for f in volumes for v in f}
        for v in every:
            if v not in kept_volumes:
                slots.add(v)
                if p.name(v).split('.')[-1] not in record['replaced']:
                    record['removed'].append(p.name(v).split('.')[-1])
        # the listing carried over (section 3)
        fmap = floor_map([f['names'] for f in old], new_names)
        old_boxes = [f['boxes'] for f in old]
        saved = {}      # actor -> [(old floor, cut, entry)]
        order = {}      # id(entry) -> where the map saved it: kept entries stay in the map's order, new ones follow
        for k, f in enumerate(old):
            for n, x in enumerate(f['entries']):
                order[id(x)] = (0, k, n)
                if x['actor'] > 0:
                    cut = x['raw'][x['cutdownAt']] if x['cutdownAt'] is not None else 0
                    saved.setdefault(x['actor'], []).append((k, cut, x))
        lists = [[] for _ in new_floors]
        counted = dict(kept=0, rule=0, unread=0, dropped=0)
        sources = {c['source'] for c in pieces}
        for piece in pieces:
            source = piece['source']
            if p.cls(source) not in LISTED:
                continue
            mine = saved.get(source, [])
            before = piece_box(p, dict(source=source), meshes)
            after = piece_box(p, piece, meshes)
            if before is None or after is None:
                # no box to put through the rule: what the map saved, carried, where its floors are still there
                entries = [(fmap.get(k), fmap.get(cut) if cut else 0, x) for k, cut, x in mine]
                for k, cut, x in entries:
                    if k is not None and cut is not None:
                        lists[k].append((order[id(x)], entry_for_cut(x, piece['actor'], cut)))
                counted['unread'] += bool(mine)
                continue
            old_rule = rule(p, source, before, old_boxes)
            new_rule = rule(p, source, after, new_floors)
            entries, kept = carried([(k, cut) for k, cut, _ in mine], old_rule, new_rule, fmap)
            if not entries:
                continue
            counted['kept' if kept else 'rule'] += 1
            dz = after[4] - before[4]
            raws = {}
            for k, cut, x in mine:
                raws.setdefault((fmap.get(k), fmap.get(cut) if cut else 0), x)
            for k, cut in entries:
                x = raws.get((k, cut)) if kept else None
                lists[k].append((order[id(x)], entry_for_cut(x, piece['actor'], cut, dz)) if x else
                                ((1, len(lists[k]), 0), rule_entry(t, old, piece['actor'], cut)))
        # what the map saved of actors that are no candidate (not a placed piece of a listed class) and not hidden
        for actor, rows in saved.items():
            if actor in gone:
                counted['dropped'] += 1     # a hidden original: off the lists (F-58's fix); its copy is listed as a piece
                continue
            if actor in sources:
                continue
            for k, cut, x in rows:
                if fmap.get(k) is not None and (not cut or fmap.get(cut) is not None):
                    lists[fmap[k]].append((order[id(x)], entry_for_cut(x, actor, fmap[cut] if cut else 0)))
        lists = [[raw for _, raw in sorted(entries, key=lambda e: e[0])] for entries in lists]
        # each new floor's element: the old floor it comes from with its lists replaced, else the template's
        comes = {}
        for k, j in sorted(fmap.items()):
            if j is not None:
                comes.setdefault(j, k)
        dropped_emitters = []
        elements = []
        for j, boxes in enumerate(new_floors):
            k = comes.get(j)
            if k is None:
                if t is None:
                    raise ValueError('the map has no building with floors to take a new floor\'s shape from')
                elements.append(floor_bytes(g, walker, t, volumes[j], []))
                elements[-1] = with_lists(g, grown_walker(p, g), elements[-1], volumes[j], lists[j], None)
                continue
            f = old[k]
            keep = []
            def holds(floor, at):
                return any(x and all(x[a] - SLACK <= at[a] <= x[a + 3] + SLACK for a in range(3)) for x in floor)
            for em in f['emitters']:
                at = p.own(em, 'Location', None) if em > 0 else None
                # dropped only from a floor whose boxes held it and no longer do (one the map saved outside them stays)
                if at is not None and holds(f['boxes'], at) and not holds(boxes, at):
                    dropped_emitters.append(p.name(em).split('.')[-1])
                else:
                    keep.append(em)
            element = bytes(b[f['element'][0]:f['element'][1]])
            elements.append(with_lists(g, grown_walker(p, g), element, volumes[j], lists[j],
                                       keep if f['emitters'] else None))
        every_box = [x for boxes in new_floors for x in boxes]
        union = [min(x[k] for x in every_box) for k in range(3)] + [max(x[k + 3] for x in every_box) for k in range(3)]
        w = grown_walker(p, g)
        data = bytearray(native_copy.rebuilt(bytes(b), found, elements))
        groups = dict(emptied=False, repointed=[])
        old_every = [x for f in old for x in f['boxes'] if x]
        old_union = ([min(x[k] for x in old_every) for k in range(3)] + [max(x[k + 3] for x in old_every) for k in range(3)]
                     if old_every else None)
        # the building volume's box follows the floors' union only when that changed (the map's own is often larger)
        if not same_box(old_union, union):
            location, scale = placed(p, i, union)
            data = native_copy.set_vector(w, g, data, start, 'Location', location)
            data = native_copy.set_vector(w, g, data, start, 'DrawScale3D', scale)
        if ed.get('moved'):
            vis = native_copy.find_prop(w, bytes(data), start, len(data), 'VisGroupIdxToHideWhenOccluding[0]')
            if vis is not None:
                _, tag, at, size = vis
                data = bytearray(data[:at]) + struct.pack('<i', 0) + bytes(data[at + size:])
                struct.pack_into('<i', data, tag + 16, 4)
                groups['emptied'] = True
        mesh_groups = native_copy.find_prop(w, bytes(data), start, len(data), 'ExternalMeshGroups[0]')
        for s_, e_ in native_copy.struct_elements(w, bytes(data), mesh_groups[2], mesh_groups[3]) if mesh_groups else []:
            listed = native_copy.find_prop(w, bytes(data), s_, e_, 'm_aActors[0]')
            if not listed:
                continue
            n = struct.unpack_from('<i', data, listed[2])[0]
            for q in range(n):
                at = listed[2] + 4 + 4 * q
                v = struct.unpack_from('<i', data, at)[0]
                if v in copies:
                    struct.pack_into('<i', data, at, copies[v])
                    groups['repointed'].append(p.name(v).split('.')[-1])
        ufo = ed.get('kind') == 'ufo'
        if ufo or p.own(i, 'IsUfo') is not None:
            data = native_lights.set_property(w, g, data, start, 'IsUfo', 'BoolProperty', None, b'\x01' if ufo else b'\x00')
        g.relocate(i, bytes(data))
        report.append(dict(id=ed['id'], actor=ed['actor'], deleted=False, moved=bool(ed.get('moved')), box=union,
                           volumes=record, floors=[dict(volumes=volumes[j], pieces=len(lists[j])) for j in range(len(new_floors))],
                           pieces=counted, emittersDropped=dropped_emitters, visGroupsEmptied=groups['emptied'],
                           meshGroupsRepointed=groups['repointed']))
    return actors, slots, report


def entry_for_cut(entry, actor, cut, dz=0.0):
    """A copy of a saved entry naming `actor`, its CutdownFloor `cut` where it saves one, its MinZ raised by `dz`."""
    raw = bytearray(native_copy.entry_for(entry, actor, dz))
    if entry['cutdownAt'] is not None:
        raw[entry['cutdownAt']] = max(0, min(255, cut))
    return bytes(raw)


def rule_entry(t, old, actor, cut):
    """An entry for `actor` by the rule: the template building's two shapes (with and without a CutdownFloor), else
    one of the edited building's own entries of that shape."""
    shape = (t['cut'] if cut else t['plain']) if t else next(
        (x for f in old for x in f['entries'] if x['actorAt'] is not None and (x['cutdownAt'] is not None) == bool(cut)
         and (cut or x['minZAt'] is None)), None)
    if shape is None:
        raise ValueError('no floor entry of the right shape to list %s with' % actor)
    return entry_for_cut(shape, actor, cut)


def with_lists(g, walker, element, volumes, entries, emitters):
    """A Floors element (its bytes alone) with FloorVolumes naming `volumes`, m_aCachedActors holding `entries` and,
    when `emitters` is not None, m_aCachedEmitters naming them."""
    lists = [('FloorVolumes', [struct.pack('<i', v) for v in volumes]), ('m_aCachedActors', entries)]
    if emitters is not None:
        lists.append(('m_aCachedEmitters', [struct.pack('<i', v) for v in emitters]))
    for name, items in lists:
        field = native_copy.find_prop(walker, element, 0, len(element), name + '[0]')
        element = native_copy.with_array(g, element, (0, len(element)), field, name, items)
    return element

def survey(p, only=None):
    """What the level's listed building volumes save, read back: [dict(name, box, tag, flags, floors: [dict(volumes:
    [dict(name, box, number, listed)], members: [dict(actor, cls, cutdown, mask, floorComponent, listed)])])]. `listed`
    says whether the level's actor list has the actor (a staged template's is not)."""
    import scene_metadata
    live = set(native_copy.level_actors(p))

    def flat(box):
        return [round(v, 3) for v in box['min'] + box['max']] if box else None
    out = []
    for i in level_actors(p, 'XComBuildingVolume'):
        name = p.name(i).split('.')[-1]
        if i not in live or (only and name != only):
            continue
        floors = []
        for row in p.structs(p.effective(i, 'Floors')):
            def value(key, row=row):
                return row.get((key, 0), {}).get('value')
            volumes = [dict(name=p.name(r).split('.')[-1], box=flat(scene_metadata.volume_bounds(p, r)),
                            number=p.effective(r, 'FloorNumber'), listed=r in live)
                       for r in p.refs(value('FloorVolumes')) if r > 0]
            members = []
            for e in p.structs(value('m_aCachedActors')):
                ref = e.get(('ResidentActor', 0), {}).get('value', 0)
                if ref <= 0:
                    continue
                mesh = main_mesh(p, ref)
                members.append(dict(actor=p.name(ref).split('.')[-1], cls=p.cls(ref),
                                    cutdown=e.get(('CutdownFloor', 0), {}).get('value', 0),
                                    mask=bool(mesh and p.effective(mesh, 'bCutoutMask', False)),
                                    floorComponent=any(p.cls(k) == 'XComFloorComponent' for k in p.children.get(ref, []))
                                    or (p.effective(ref, 'FloorComponent', 0) or 0) != 0,
                                    listed=ref in live))
            floors.append(dict(volumes=volumes, members=members))
        out.append(dict(name=name, box=flat(scene_metadata.volume_bounds(p, i)), tag=str(p.effective(i, 'Tag')),
                        flags={k: p.own(i, k) for k in ('IsUfo', 'm_bIsInternalBuilding') if p.own(i, k) is not None},
                        groups=[k for k in ('ExternalMeshGroups', 'VisGroupIdxToHideWhenOccluding')
                                if p.own(i, k) not in (None, b'', bytes(4))],
                        floors=floors))
    return out


def main():
    import audit_lighting
    p = audit_lighting.Package(Path(sys.argv[1]))
    for b in survey(p, sys.argv[2] if len(sys.argv) > 2 else None):
        print('%s: box %s, tag %s%s%s' % (b['name'], b['box'], b['tag'], ', %s' % b['flags'] if b['flags'] else '',
                                          ', saves %s' % ', '.join(b['groups']) if b['groups'] else ''))
        for k, f in enumerate(b['floors']):
            for v in f['volumes']:
                print('  floor %d: %s box %s, FloorNumber %s%s' % (k, v['name'], v['box'], v['number'],
                                                                 '' if v['listed'] else ', NOT in the level list'))
            for m in f['members']:
                print('    %-34s %-26s %s%s%s' % (m['actor'], m['cls'], 'cuts down to %d' % m['cutdown'] if m['cutdown'] else '-',
                                                 ', mask' if m['mask'] else '',
                                                 '' if m['listed'] else ', NOT in the level list'))


if __name__ == '__main__':
    main()

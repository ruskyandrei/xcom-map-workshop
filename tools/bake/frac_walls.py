"""Generated fracturing walls in the variant map (private/plans/todo/custom-geometry-implementation-plan.md, section 0,
stage F3): a copy of one of the map's fracturing walls (the donor) whose mesh and fragment columns are made from
numbers (frac_wall.py), everything else the donor's.

A copy that carries `generated` (native_copy.build's copies) is cloned as any fracturing copy is (clone_assembly, its
columns moved by move_columns), then add_walls changes it:

  kind 'fracWall'  dict(kind, version 1, wall: frac_wall's numbers): a FracturedStaticMesh of the wall under a
                   forced-export package of our own (PACKAGE), its RB_BodySetup (one convex box for each of the wall's
                   solids, cover_blocks' hull layout) and on the clone:
                   - the component: its StaticMesh the new mesh; FragmentBoundsMinZ and MaxZ the fragments' lowest and
                     highest world heights and NumResourceIndices the mesh's index count, as every placed wall of the
                     game saves them (research/evidence/frac-wall-audit.py, F0); its painted vertex colours (the
                     donor's LOD 0 overrides the mesh's, which the blend materials read) one for each new vertex, each
                     the colour of the donor's nearest vertex of the same slot;
                   - the actor: its FragmentColumns written by F0's rule: one column for each tile of the game's grid
                     along the wall and each storey it reaches; a column lists the fragments whose box overlaps its
                     box (the tile along the wall, the storey, the wall's thickness), each with its lowest corner's
                     height (MinZ), lowest first; its box is the tile (cut to the wall's ends), the storey, and across
                     the wall the listed fragments' boxes together. Its lists of the pieces that go with it and of the
                     neighbouring walls' columns are empty (the plan's known limits);
  kind 'relit'     the copy's mesh is the donor's, unchanged: it only goes to the relight lit from nothing, as a
                   generated wall is (a reference beside one, in the same light).

The relight lights both kinds from nothing (relight.py --fresh-copy), and their tiles are seeded and rebuilt over the
generated wall's box (wall_box)."""
import hashlib
import struct
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'upk'))
sys.path.insert(0, str(HERE.parent / 'viewer'))
sys.path.insert(0, str(HERE))
import cover_blocks  # noqa: E402
import frac_wall  # noqa: E402
import gen_mesh  # noqa: E402
import light_factory  # noqa: E402
import props as legacy_props  # noqa: E402

PACKAGE = 'XComMapEdGeo'
KINDS = ('fracWall', 'relit')
TILE, STOREY = 96.0, 192.0
# the shortest wall (its tile edges' distance): a solid of 24 between its ends' insets
MIN_LENGTH = 24 + 2 * int(frac_wall.RECIPE['endInset'])
FORCED_EXPORT = 0x1


def check(generated):
    """The copy's `generated` request, checked: dict(kind, version, wall) or ValueError."""
    if not isinstance(generated, dict) or generated.get('kind') not in KINDS:
        raise ValueError('a generated piece of an unknown kind: %r' % (generated,))
    if generated.get('version', 1) != frac_wall.RECIPE['version']:
        raise ValueError('generated wall recipe version %r (this Build knows %d)'
                         % (generated.get('version'), frac_wall.RECIPE['version']))
    if generated['kind'] == 'relit':
        return generated
    wall = generated.get('wall')
    if not isinstance(wall, dict) or not all(isinstance(wall.get(k), (int, float)) for k in ('x0', 'x1')):
        raise ValueError('a generated wall needs its ends, x0 and x1')
    if wall['x1'] - wall['x0'] < MIN_LENGTH:
        raise ValueError('a generated wall shorter than %d units (its solid %d, its ends stopping %d short)'
                         % (MIN_LENGTH, MIN_LENGTH - 2 * frac_wall.RECIPE['endInset'], frac_wall.RECIPE['endInset']))
    for o in wall.get('openings') or []:
        if not all(isinstance(o.get(k), (int, float)) for k in ('x0', 'x1', 'z0', 'z1')) \
                or not (wall['x0'] <= o['x0'] < o['x1'] <= wall['x1']) or not o['z0'] < o['z1']:
            raise ValueError('an opening outside its wall or of no size: %r' % (o,))
    return generated


def local_box(wall):
    """The box the wall's solid stands in, in its mesh's frame (its ends in from its tile edges: frac_wall.solid_wall)."""
    h = max(y for y, _, _ in frac_wall.RECIPE['section'])
    solid = frac_wall.solid_wall(wall)
    return [solid['x0'], solid['x1'], -h, h, frac_wall.RECIPE['bottom'], frac_wall.RECIPE['top']]


def world_box(box, matrix):
    """The world box [x0, x1, y0, y1, z0, z1] of the local box `box` under the 4 x 4 `matrix`."""
    corners = np.array([[x, y, z, 1.0] for x in box[0:2] for y in box[2:4] for z in box[4:6]]) @ np.asarray(matrix).T
    return [float(v) for k in range(3) for v in (corners[:, k].min(), corners[:, k].max())]


def wall_box(p, actor, location, rotation, generated):
    """The world box a generated copy stands in (its tiles are seeded and rebuilt over it): the generated wall's,
    or for 'relit' the donor's own box at the copy's pose (None: let the caller work it out as for any copy)."""
    import lightmap_texels
    if generated.get('kind') != 'fracWall':
        return None
    comp = p.own(actor, 'FracturedStaticMeshComponent')
    return world_box(local_box(generated['wall']), lightmap_texels.world_matrix(p, comp, location, rotation))


# ---------------------------------------------------------------------------------------------------- columns
def columns(frag_boxes, grid):
    """The fragment columns of a wall whose fragments have the world boxes `frag_boxes` ([x0, x1, y0, y1, z0, z1]),
    by F0's rule on the game's tile grid (grid: native_copy.level_grid's; the tiles counted from its corner tx, ty,
    tz): [dict(box, frags: [(fragment, minZ)] lowest first)], along the wall then up."""
    lo = [min(b[2 * k] for b in frag_boxes) for k in range(3)]
    hi = [max(b[2 * k + 1] for b in frag_boxes) for k in range(3)]
    along = 0 if hi[0] - lo[0] >= hi[1] - lo[1] else 1
    across = 1 - along
    corner = (grid['tx'], grid['ty'])[along]
    first = int(np.floor((lo[along] - corner) / TILE + 1e-6))
    last = int(np.ceil((hi[along] - corner) / TILE - 1e-6))
    zfirst = int(np.floor((lo[2] - grid['tz']) / STOREY + 1e-6))
    zlast = int(np.ceil((hi[2] - grid['tz']) / STOREY - 1e-6))
    out = []
    for i in range(first, last):
        a0, a1 = max(corner + TILE * i, lo[along]), min(corner + TILE * (i + 1), hi[along])
        if a1 - a0 < 1e-3:
            continue
        for s in range(zfirst, zlast):
            z0, z1 = grid['tz'] + STOREY * s, grid['tz'] + STOREY * (s + 1)
            probe = [0.0] * 6
            probe[2 * along:2 * along + 2] = [a0, a1]
            probe[2 * across:2 * across + 2] = [lo[across], hi[across]]
            probe[4:6] = [z0, z1]
            listed = [f for f, b in enumerate(frag_boxes)
                      if all(min(b[2 * k + 1], probe[2 * k + 1]) - max(b[2 * k], probe[2 * k]) > 0 for k in range(3))]
            if not listed:
                continue
            box = list(probe)
            box[2 * across] = min(frag_boxes[f][2 * across] for f in listed)
            box[2 * across + 1] = max(frag_boxes[f][2 * across + 1] for f in listed)
            frags = sorted(((f, frag_boxes[f][4]) for f in listed), key=lambda x: (x[1], x[0]))
            out.append(dict(box=box, frags=frags))
    return out


def _tag(g, name, kind, size, struct_name=None):
    out = struct.pack('<iiiiii', g.name(name), 0, g.name(kind), 0, size, 0)
    return out + (struct.pack('<ii', g.name(struct_name), 0) if struct_name else b'')


def _none(g):
    return struct.pack('<ii', g.name('None'), 0)


def column_element(g, walker, template, column):
    """A FragmentColumns element from the struct bytes `template` (one of the donor's columns): its Bounds and
    FragCache set to `column`'s, its DestructibleCache and FracActorCache emptied."""
    import native_copy
    b = bytearray(template)
    bounds = native_copy.find_prop(walker, b, 0, len(b), 'Bounds[0]')
    box = column['box']
    struct.pack_into('<6fB', b, bounds[2], box[0], box[2], box[4], box[1], box[3], box[5], 1)
    entries = [_tag(g, 'FragIndex', 'IntProperty', 4) + struct.pack('<i', f)
               + _tag(g, 'MinZ', 'FloatProperty', 4) + struct.pack('<f', z) + _none(g) for f, z in column['frags']]
    b = native_copy.with_array(g, b, (0, len(b)), native_copy.find_prop(walker, b, 0, len(b), 'FragCache[0]'),
                               'FragCache', entries)
    for name in ('DestructibleCache', 'FracActorCache'):
        field = native_copy.find_prop(walker, b, 0, len(b), name + '[0]')
        if field is not None:
            b = native_copy.with_array(g, b, (0, len(b)), field, name, [])
    return bytes(b)


# ---------------------------------------------------------------------------------------------------- the component
def _lod_colours(data, at):
    """Where LOD 0's painted vertex colours lie in a mesh component's native data data[at:]: (the flag's offset, the
    end of the colour array), as audit_lighting.lod_record reads the record."""
    pos = at
    count = struct.unpack_from('<i', data, pos)[0]
    if count < 1:
        raise ValueError('a component with no LOD record')
    pos += 4
    for _ in range(2):                                  # shadow maps, shadow vertex buffers
        n = struct.unpack_from('<i', data, pos)[0]
        pos += 4 + 4 * n
    kind = struct.unpack_from('<i', data, pos)[0]
    pos += 4
    if kind == 2:
        n = struct.unpack_from('<i', data, pos)[0]
        pos += 4 + 16 * n + 3 * (4 + 12) + 16
    elif kind != 0:
        raise ValueError('a vertex-lit component (lightmap type %d) can\'t take a generated mesh' % kind)
    flag = pos
    if data[pos]:
        stride, n = struct.unpack_from('<2I', data, pos + 1)
        end = pos + 9
        if n:
            s2, n2 = struct.unpack_from('<2i', data, end)
            end += 8 + s2 * n2
    else:
        end = pos + 1
    return flag, end


def painted(donor, built):
    """One painted colour for each vertex of the generated mesh: the donor's override at its nearest vertex of the
    same slot (`donor`: dict(positions, colours, slots), the donor mesh's and its component's)."""
    out = []
    lod = built['mesh']['lods'][0]
    pos = np.array(lod['positions'], float)
    slot_of = np.zeros(len(pos), int)
    for s in lod['sections']:
        for v in set(lod['indices'][1][s['first']:s['first'] + 3 * s['triangles']]):
            slot_of[v] = s['slot']
    dpos, dslot = donor['positions'], donor['slots']
    for k in range(len(pos)):
        same = dslot == slot_of[k]
        cand = np.flatnonzero(same) if same.any() else np.arange(len(dpos))
        j = cand[np.argmin(((dpos[cand] - pos[k]) ** 2).sum(1))]
        out.append(donor['colours'][j])
    return out


def donor_paint(p, comp, mesh_dict):
    """The donor component's painted colours with the donor mesh's vertices and their slots, or None when it paints
    none."""
    e = p.exports[comp - 1]
    at = p.properties(comp)[1]
    flag, end = _lod_colours(p.data, at)
    if not p.data[flag]:
        return None
    stride, n = struct.unpack_from('<2I', p.data, flag + 1)
    if not n:
        return None
    raw = p.data[flag + 17:end]
    colours = [bytes(raw[4 * k:4 * k + 4]) for k in range(n)]
    lod = mesh_dict['lods'][0]
    slots = np.zeros(len(lod['positions']), int)
    for s in lod['sections']:
        for v in set(lod['indices'][1][s['first']:s['first'] + 3 * s['triangles']]):
            slots[v] = s['slot']
    if len(colours) < len(lod['positions']):
        return None
    return dict(positions=np.array(lod['positions'], float), colours=colours, slots=slots)


def component_data(g, walker, p, old, new, mesh_index, built, paint, matrix):
    """The clone component's bytes with the generated mesh: StaticMesh, FragmentBoundsMinZ and MaxZ,
    NumResourceIndices, and LOD 0's painted colours one for each new vertex (or none, when the donor paints none)."""
    e = p.exports[old - 1]
    start = legacy_props.props_start(p.data, e, p.names) - e['off']
    data = bytearray(g.export_data(new))
    lod = built['mesh']['lods'][0]
    pos = np.array(lod['positions'], float)
    wz = (np.c_[pos, np.ones(len(pos))] @ np.asarray(matrix).T)[:, 2]
    for name, fmt, value in (('StaticMesh[0]', '<i', mesh_index), ('FragmentBoundsMinZ[0]', '<f', float(wz.min())),
                             ('FragmentBoundsMaxZ[0]', '<f', float(wz.max())),
                             ('NumResourceIndices[0]', '<i', len(lod['indices'][1]))):
        at = walker.value(bytes(data), start, len(data), name)
        if at is None:
            raise ValueError('%s saves no %s' % (p.name(old), name))
        struct.pack_into(fmt, data, at, value)
    end_props = native_props_end(walker, data, start)
    flag, end = _lod_colours(data, end_props)
    if paint is None:
        block = b'\0'
    else:
        colours = painted(paint, built)
        block = b'\x01' + struct.pack('<2I', 4, len(colours)) + struct.pack('<2i', 4, len(colours)) + b''.join(colours)
    return bytes(data[:flag] + block + data[end:])


def native_props_end(walker, data, start):
    """Where the tagged properties from `start` end (after their None)."""
    gen = walker.walk(bytes(data), start, len(data))
    try:
        while True:
            next(gen)
    except StopIteration as done:
        return done.value


# ---------------------------------------------------------------------------------------------------- the exports
def body_setup_boxes(g, boxes, spec):
    """An RB_BodySetup's tagged properties with one convex element for each box (lo, hi) (cover_blocks'
    convex_hull and layout, an element for each)."""
    def array(name, fmt, items):
        payload = struct.pack('<i', len(items)) + b''.join(struct.pack('<' + fmt, *(x if isinstance(x, list) else [x]))
                                                           for x in items)
        return _tag(g, name, 'ArrayProperty', len(payload)) + payload
    elems = b''
    for lo, hi in boxes:
        h = cover_blocks.convex_hull(lo, hi, spec)
        box = struct.pack('<6fB', *h['ElemBox'][0], *h['ElemBox'][1], h['ElemBox'][2])
        elems += (array('VertexData', '3f', h['VertexData']) + array('PermutedVertexData', '4f', h['PermutedVertexData'])
                  + array('FaceTriData', 'i', h['FaceTriData']) + array('EdgeDirections', '3f', h['EdgeDirections'])
                  + array('FaceNormalDirections', '3f', h['FaceNormalDirections'])
                  + array('FacePlaneData', '4f', h['FacePlaneData'])
                  + _tag(g, 'ElemBox', 'StructProperty', len(box), 'Box') + box + _none(g))
    convex = struct.pack('<i', len(boxes)) + elems
    agg = _tag(g, 'ConvexElems', 'ArrayProperty', len(convex)) + convex + _none(g)
    return (_tag(g, 'PreCachedPhysDataVersion', 'IntProperty', 4) + struct.pack('<i', spec['version'])
            + _tag(g, 'AggGeom', 'StructProperty', len(agg), 'KAggregateGeom') + agg + _none(g))


def mesh_properties(g, p, donor_mesh, body):
    """The generated mesh's tagged properties: the donor mesh's, its BodySetup the new one."""
    out = _tag(g, 'BodySetup', 'ObjectProperty', 4) + struct.pack('<i', body)
    for name in ('LightMapCoordinateIndex', 'LightMapResolution'):
        value = p.own(donor_mesh, name)
        if value is not None:
            out += _tag(g, name, 'IntProperty', 4) + struct.pack('<i', int(value))
    for name in ('UseSimpleRigidBodyCollision', 'UseSimpleLineCollision', 'UseSimpleBoxCollision'):
        value = p.own(donor_mesh, name)
        if value is not None:
            out += _tag(g, name, 'BoolProperty', 0) + bytes([1 if value else 0])
    return out + _none(g)


def _package(g, p, names):
    """Our forced-export package (PACKAGE), its entry copied from one of the map's own, counting net objects for its
    meshes and their body setups, a GUID from its contents."""
    data = struct.pack('<i', -1) + _none(g)
    index = g.add_export(cover_blocks._template(g, p, 'Package', outer=0), data, number=0, name_index=g.name(PACKAGE))
    e = g.entries[index - 1]
    if e.get('<I', 44) != 1:
        raise ValueError('the map\'s forced-export packages count net objects for more than one generation')
    e.put('<I', 48, 2 * len(names) + 1)
    e.data[52:68] = hashlib.md5(('%s|%s' % (PACKAGE, ','.join(names))).encode()).digest()
    return index


def add_walls(g, p, items, grid):
    """The generated copies `items` ([dict(original: the donor actor's export, info: clone_assembly's dict for the
    copy, generated, location, rotation, label)]) made in the map being grown: returns a record for each (dict(kind,
    copy, mesh, bodySetup, fragments, columns, vertices, triangles, box))."""
    import lightmap_texels
    import native_copy
    walker = native_copy.Walker(p)
    built, records = [], []
    for item in items:
        gen = check(item['generated'])
        original = item['original']
        comp_old = p.own(original, 'FracturedStaticMeshComponent')
        if not comp_old or p.cls(original) not in native_copy.FRACTURING:
            raise ValueError('%s is no fracturing piece: a generated wall copies one' % p.name(original))
        donor_mesh = p.own(comp_old, 'StaticMesh')
        if gen['kind'] == 'relit':
            records.append(dict(kind='relit', copy=item['info']['actor'], label=item.get('label')))
            continue
        template = gen_mesh.read(p, donor_mesh)
        out = frac_wall.build(gen['wall'], template)
        built.append((item, comp_old, donor_mesh, template, out, frac_wall.mesh_name(gen['wall'])))
    if not built:
        return records
    names = sorted({b[5] for b in built})
    package = _package(g, p, names)
    spec = cover_blocks.RECIPES[1]['bodySetup']
    made = {}
    for net, name in enumerate(names, 1):
        item, comp_old, donor_mesh, template, out, _ = next(b for b in built if b[5] == name)
        body_old = p.own(donor_mesh, 'BodySetup') or gen_mesh.read(p, donor_mesh)['bodySetup']
        index = len(g.entries) + 1
        mesh = dict(out['mesh'], bodySetup=index + 1)
        head = struct.pack('<i', net) + mesh_properties(g, p, donor_mesh, index + 1)
        data = head + gen_mesh.write(mesh, g.next_offset() + len(head))
        if g.add_export(donor_mesh, data, number=0, name_index=g.name(name)) != index:
            raise RuntimeError('the generated mesh did not get the planned index')
        g.entries[index - 1].put('<i', 8, package)
        body = (struct.pack('<i', len(names) + net) + body_setup_boxes(g, out['solids'], spec) + struct.pack('<i', 0))
        if g.add_export(body_old, body, number=spec['number'], name_index=g.name(spec['name'])) != index + 1:
            raise RuntimeError("the generated mesh's body setup did not get the planned index")
        g.entries[index].put('<i', 8, index)
        made[name] = index
    for item, comp_old, donor_mesh, template, out, name in built:
        info = item['info']
        comp_new = info['mapping'][comp_old]
        matrix = lightmap_texels.world_matrix(p, comp_old, item['location'], item['rotation'])
        paint = donor_paint(p, comp_old, template)
        g.relocate(comp_new, component_data(g, walker, p, comp_old, comp_new, made[name], out, paint, matrix))
        # the fragments' world boxes, and the columns by F0's rule
        boxes = [world_box(f['box'], matrix) for f in out['fragments']]
        cols = columns(boxes, grid)
        actor = info['actor']
        e = p.exports[item['original'] - 1]
        start = legacy_props.props_start(p.data, e, p.names) - e['off']
        b = bytearray(g.export_data(actor))
        parsed = native_copy.fragment_columns(walker, b, start)
        if parsed is None:
            raise ValueError('%s saves no fragment columns to write over' % p.name(item['original']))
        field, old = parsed
        s0, e0 = old[0]['element']
        template_col = bytes(b[s0:e0])
        pieces = [column_element(g, walker, template_col, c) for c in cols]
        g.relocate(actor, native_copy.rebuilt(b, field, pieces))
        lo = [min(x[2 * k] for x in boxes) for k in range(3)]
        hi = [max(x[2 * k + 1] for x in boxes) for k in range(3)]
        records.append(dict(kind='fracWall', copy=actor, label=item.get('label'), mesh=made[name], meshName=name,
                            bodySetup=made[name] + 1, fragments=out['counts']['fragments'],
                            vertices=out['counts']['vertices'], triangles=out['counts']['triangles'],
                            solids=len(out['solids']), columns=len(cols), painted=paint is not None,
                            box=[v for k in range(3) for v in (lo[k], hi[k])]))
    return records

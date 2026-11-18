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
                   - its lightmap (custom geometry plan, M2): in a baked Build, the rectangle of its own cloned atlas is
                     the mesh's lightmap rectangle (frac_wall's `lightmapRect`, at the donor's density) at the donor
                     rectangle's corner (or the atlas's, where it doesn't fit), which the relight then fills; in a
                     Build without baking (D9), one texel of the lightmap of the map's nearest lit piece, the one
                     nearest its median light, for the whole wall (a coordinate scale of 0): one even light, the
                     map's near it, in place of the donor's bake laid out for another shape (even_light);
                   - the map's dominant light (M2 item 2): in a baked Build, a shadow map of its own (a clone of one of
                     the map's ShadowMap2D of that light and of its distance-field texture, its rectangle the
                     lightmap's size at the clone's corner), which the relight fills as a piece of another map's, and
                     the light taken off the component's IrrelevantLights (the donor, an inside wall, lists the Bar's
                     moon there); without baking, the shadow map of the piece the even light comes from, at the same
                     texel (a scale of 0), or, where that piece has none, the light listed irrelevant, as that piece
                     and the game's inside pieces have it (dominant_shadow);
                   - the actor: its FragmentColumns written by F0's rule: one column for each tile of the game's grid
                     along the wall and each storey it reaches; a column lists the fragments whose box overlaps its
                     box (the tile along the wall, the storey, the wall's thickness), each with its lowest corner's
                     height (MinZ), lowest first; its box is the tile (cut to the wall's ends), the storey, and across
                     the wall the listed fragments' boxes together. Its list of the pieces that go with it starts empty
                     (door_columns and group_columns fill it); its neighbours' columns, by the game's rule
                     (neighbour_columns);
  kind 'fracSlab'  dict(kind, version 1, slab: frac_slab's numbers): a floor or roof slab (custom geometry plan,
                   M5), made as a wall is (its mesh by frac_slab.build, its body setup, its component, light and shadow
                   map), on a copy of one of the game's slabs (which keeps its floor flags, bPathColliding and
                   bCanStepUpOn, and its component's), the donor's painted-out fragments (EditorPaintedVisibleFragments)
                   dropped; its FragmentColumns by the slabs' rule (slab_columns: the piece's own 96 x 96 x 192 grid
                   from its lowest corner less one unit, a column for every cell, research/evidence/slab-audit.py);
  kind 'ground'    dict(kind, version 1, ground: ground.py's numbers): a patch, block or ramp (custom geometry plan,
                   M6) on a copy of one of the game's plain pieces (GROUND_CLASSES: a StaticMeshComponent, its
                   material the ground's): its mesh a plain static mesh by ground.build, its body setup (a box or a
                   ramp's wedge, hulls.py), its lightmap and shadow map as a wall's; no columns (it doesn't break);
  kind 'relit'     the copy's mesh is the donor's, unchanged: it only goes to the relight lit from nothing, as a
                   generated wall is (a reference beside one, in the same light).

The relight lights both kinds from nothing (relight.py --fresh-copy), and their tiles are seeded and rebuilt over the
generated wall's box (wall_box).

A door standing in a made wall's opening goes when the wall round it breaks (custom geometry plan, M3 item 4): a door
copied from one of the map's own walls is listed in the made wall's columns where its original's listing lands
(native_copy.edit_columns); one that nothing lists yet (a door of another map, or one that stood in no wall) is listed
by door_columns in the wall's columns within a tile of it along the wall, on every storey, as the game's walls list
their doors (URB_Bar's door 7 in four tiles' columns, both storeys). The props and cover blocks of a group that breaks
together with a made wall are listed by group_columns in the columns they stand by (M3 item 4, F-101's limit), so they
go when that part of the wall breaks.

A made wall's columns and the fracturing pieces it touches list each other's columns (M3 item 3: neighbour_columns),
by the rule the game's own lists follow (research/native/frac-neighbours.md, F-69): a column lists another piece's
column when its box touches or overlaps that column's box cut to that piece's own bounds grown by one unit. A listing
passes a break on one step in the game (the damaged column's damage, up to its height, to each listed column), so
joined made walls, a made wall against one of the map's walls, and a wall on a storey floor break together where they
meet, as the game's do."""
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
import frac_slab  # noqa: E402
import frac_wall  # noqa: E402
import ground  # noqa: E402
import gen_mesh  # noqa: E402
import light_factory  # noqa: E402
import props as legacy_props  # noqa: E402

PACKAGE = 'XComMapEdGeo'
KINDS = ('fracWall', 'fracSlab', 'ground', 'relit')
MADE = ('fracWall', 'fracSlab')     # the fracturing kinds made from numbers (their own mesh and columns)
# the classes a ground shape copies (plain pieces with a StaticMeshComponent, which the editor copies natively)
GROUND_CLASSES = ('XComLevelActor', 'StaticMeshActor', 'XComOpacityFadeLevelActor')
# the request's versions: 1, a wall's numbers; 2 (custom geometry plan, M3 item 2 and M4 item 1), with its end styles
# (`ends`), which the compiler works out from where the project's made walls meet, and its look (`look`, one of
# frac_wall.LOOKS); version 1 reads as two free ends in the Bar's inside wall
VERSIONS = (1, 2)
TILE, STOREY = 96.0, 192.0
# the shortest wall (its tile edges' distance): a solid of 24 between its ends' insets
MIN_LENGTH = 24 + 2 * int(frac_wall.RECIPE['endInset'])
FORCED_EXPORT = 0x1


def check(generated):
    """The copy's `generated` request, checked: dict(kind, version, wall) or ValueError."""
    if not isinstance(generated, dict) or generated.get('kind') not in KINDS:
        raise ValueError('a generated piece of an unknown kind: %r' % (generated,))
    if generated.get('version', 1) not in VERSIONS:
        raise ValueError('generated wall request version %r (this Build knows %s)'
                         % (generated.get('version'), ' and '.join(map(str, VERSIONS))))
    if generated['kind'] == 'relit':
        return generated
    if generated['kind'] in ('fracSlab', 'ground'):
        if generated.get('version', 1) != 1:
            raise ValueError('generated %s request version %r (this Build knows 1)' % (generated['kind'], generated.get('version')))
        if generated['kind'] == 'fracSlab':
            frac_slab.check(generated.get('slab'))
        else:
            ground.check(generated.get('ground'))
        return generated
    wall = generated.get('wall')
    if not isinstance(wall, dict) or not all(isinstance(wall.get(k), (int, float)) for k in ('x0', 'x1')):
        raise ValueError('a generated wall needs its ends, x0 and x1')
    if wall['x1'] - wall['x0'] < MIN_LENGTH:
        raise ValueError('a generated wall shorter than %d units (its solid %d, its ends stopping %d short)'
                         % (MIN_LENGTH, MIN_LENGTH - 2 * frac_wall.RECIPE['endInset'], frac_wall.RECIPE['endInset']))
    if wall.get('storeys', 2) not in frac_wall.STOREYS:
        raise ValueError('a generated wall of %r storeys (it has 1 or 2)' % (wall.get('storeys'),))
    for key, what in (('ends', 'end styles'), ('look', 'look')):
        if key in wall and generated.get('version', 1) < 2:
            raise ValueError("a generated wall's %s come%s with request version 2" % (what, '' if key == 'ends' else 's'))
    frac_wall.ends_of(wall)
    frac_wall.look_of(wall)
    for o in wall.get('openings') or []:
        if not all(isinstance(o.get(k), (int, float)) for k in ('x0', 'x1', 'z0', 'z1')) \
                or not (wall['x0'] <= o['x0'] < o['x1'] <= wall['x1']) or not o['z0'] < o['z1']:
            raise ValueError('an opening outside its wall or of no size: %r' % (o,))
    return generated


def local_box(wall):
    """The box the wall's solid stands in, in its mesh's frame (its ends in from its tile edges: frac_wall.solid_wall)."""
    h = max(y for y, _, _ in frac_wall.RECIPE['section'])
    solid = frac_wall.solid_wall(wall)
    return [solid['x0'], solid['x1'], -h, h, frac_wall.RECIPE['bottom'], frac_wall.shaped(wall)['top']]


def world_box(box, matrix):
    """The world box [x0, x1, y0, y1, z0, z1] of the local box `box` under the 4 x 4 `matrix`."""
    corners = np.array([[x, y, z, 1.0] for x in box[0:2] for y in box[2:4] for z in box[4:6]]) @ np.asarray(matrix).T
    return [float(v) for k in range(3) for v in (corners[:, k].min(), corners[:, k].max())]


def wall_box(p, actor, location, rotation, generated):
    """The world box a generated copy stands in (its tiles are seeded and rebuilt over it): the generated wall's,
    or for 'relit' the donor's own box at the copy's pose (None: let the caller work it out as for any copy)."""
    import lightmap_texels
    kind = generated.get('kind')
    if kind not in MADE and kind != 'ground':
        return None
    comp = mesh_component(p, actor)
    box = (local_box(generated['wall']) if kind == 'fracWall' else frac_slab.local_box(generated['slab']) if kind == 'fracSlab'
           else ground.local_box(generated['ground']))
    return world_box(box, lightmap_texels.world_matrix(p, comp, location, rotation))


def mesh_component(p, actor):
    """The actor's mesh component: its FracturedStaticMeshComponent, or a plain piece's StaticMeshComponent."""
    return p.own(actor, 'FracturedStaticMeshComponent') or p.own(actor, 'StaticMeshComponent')


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


def slab_columns(frag_boxes):
    """The fragment columns of a slab whose fragments have the world boxes `frag_boxes`, by the slabs' rule (custom
    geometry plan, M5; research/evidence/slab-audit.py rule_columns, 97% of the game's roof columns): cells of 96 x 96 x
    192 counted from the slab's lowest corner less one unit; a column for every cell its box reaches, empty ones
    included, in x, then y, then up; it lists the fragments whose box meets the cell (touching counts, as UE3's
    FBox::Intersect), each with its lowest corner's height, lowest first; its box the cell cut across to the listed
    fragments' boxes (the cell's whole height; an empty column the whole cell)."""
    lo = [min(b[2 * k] for b in frag_boxes) for k in range(3)]
    hi = [max(b[2 * k + 1] for b in frag_boxes) for k in range(3)]
    step = (TILE, TILE, STOREY)
    anchor = [v - 1.0 for v in lo]
    n = [max(1, int(np.ceil((hi[k] - anchor[k]) / step[k] - 1e-6))) for k in range(3)]
    out = []
    for i in range(n[0]):
        for j in range(n[1]):
            for s in range(n[2]):
                cell = [anchor[0] + step[0] * i, anchor[0] + step[0] * (i + 1), anchor[1] + step[1] * j,
                        anchor[1] + step[1] * (j + 1), anchor[2] + step[2] * s, anchor[2] + step[2] * (s + 1)]
                listed = [f for f, b in enumerate(frag_boxes)
                          if all(min(b[2 * q + 1], cell[2 * q + 1]) - max(b[2 * q], cell[2 * q]) >= 0 for q in range(3))]
                box = list(cell)
                for k in range(2):
                    if listed:
                        box[2 * k] = max(cell[2 * k], min(frag_boxes[f][2 * k] for f in listed))
                        box[2 * k + 1] = min(cell[2 * k + 1], max(frag_boxes[f][2 * k + 1] for f in listed))
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


def lightmap_offsets(data, at):
    """Where LOD 0's texture lightmap lies in a mesh component's native data data[at:] (audit_lighting.lightmap's
    layout): dict(slots [(texture offset, scale offset)] for its three slots, scale, bias (the offsets of its
    coordinate scale and bias)), or None for a component with no texture lightmap."""
    pos = at
    if struct.unpack_from('<i', data, pos)[0] < 1:
        return None
    pos += 4
    for _ in range(2):                                  # shadow maps, shadow vertex buffers
        n = struct.unpack_from('<i', data, pos)[0]
        pos += 4 + 4 * n
    kind = struct.unpack_from('<i', data, pos)[0]
    if kind != 2:
        return None
    n = struct.unpack_from('<i', data, pos + 4)[0]
    pos += 8 + 16 * n
    return dict(slots=[(pos + 16 * k, pos + 16 * k + 4) for k in range(3)], scale=pos + 48, bias=pos + 56)


def set_light(data, at, light):
    """`data` with LOD 0's texture lightmap set as `light` says: dict(kind 'rect', rect (w, h), atlas (w, h)) puts
    the rectangle (w by h texels) at the corner the record has (down to a whole block), or at the atlas's corner where
    it doesn't fit; dict(kind
    'even', textures [3], scales [3 x 3], bias (u, v)) points every vertex at one texel of those textures."""
    if not light:
        return data
    o = lightmap_offsets(data, at)
    if o is None:
        return data
    data = bytearray(data)
    if light['kind'] == 'rect':
        (w, h), (aw, ah) = light['rect'], light['atlas']
        bu, bv = struct.unpack_from('<2f', data, o['bias'])
        x0, y0 = 4 * (int(round(bu * aw)) // 4), 4 * (int(round(bv * ah)) // 4)      # on whole DXT1 blocks
        if x0 + w > aw:
            x0 = 0
        if y0 + h > ah:
            y0 = 0
        struct.pack_into('<2f', data, o['scale'], w / aw, h / ah)
        struct.pack_into('<2f', data, o['bias'], x0 / aw, y0 / ah)
    else:
        for (tex, scale), index, value in zip(o['slots'], light['textures'], light['scales']):
            struct.pack_into('<i', data, tex, index)
            struct.pack_into('<3f', data, scale, *value)
        struct.pack_into('<2f', data, o['scale'], 0.0, 0.0)
        struct.pack_into('<2f', data, o['bias'], *light['bias'])
    return bytes(data)


def atlas_size(p, comp):
    """(width, height) of the atlas a component's LOD-0 texture lightmap is in, or None."""
    import lightmap_fields
    lods = lightmap_fields.component_fields(p, comp)['lods']
    if not lods or lods[0]['lightmap'].get('type') != 2:
        return None
    tex = lods[0]['lightmap']['slots'][0]['index']
    return (int(p.own(tex, 'SizeX')), int(p.own(tex, 'SizeY'))) if tex > 0 else None


def even_light(p, box, skip=(), near=1500.0):
    """An even light for a made wall standing in the world box `box` in a Build without baking (D9): dict(kind
    'even', textures, scales, bias, piece) from the lightmap of the map's lit piece nearest the box (a level actor's
    mesh component with a texture lightmap, within `near` of it; not one of `skip`'s actors): its texel whose light
    (what a flat surface gets: colour times its summed directional values) is nearest the median of its lit texels.
    None when no piece is near."""
    import lightmap_encode as codec
    import lightmap_fields
    import native_copy
    from lightmap_stats import top_mip_rect
    centre = np.array([(box[0] + box[1]) / 2, (box[2] + box[3]) / 2, (box[4] + box[5]) / 2])
    found = []
    for actor in native_copy.level_actors(p):
        if actor in skip:
            continue
        location = np.array(p.own(actor, 'Location', [0.0, 0.0, 0.0]), float)
        d = float(np.linalg.norm(location - centre))
        if d <= near:
            found.append((d, actor))
    for _, actor in sorted(found):
        for ci in p.children.get(actor, []):
            if not p.cls(ci).endswith('StaticMeshComponent'):
                continue
            try:
                lods = lightmap_fields.component_fields(p, ci)['lods']
            except Exception:       # a component the reader doesn't take: the next
                continue
            if not lods or lods[0]['lightmap'].get('type') != 2:
                continue
            lm = lods[0]['lightmap']
            nac, dmc = lm['slots'][0]['index'], lm['slots'][1]['index']
            if nac <= 0 or dmc <= 0:
                continue
            w, h = int(p.own(nac, 'SizeX')), int(p.own(nac, 'SizeY'))
            x0, y0 = int(np.floor(lm['coordinateBias'][0] * w + 1e-6)), int(np.floor(lm['coordinateBias'][1] * h + 1e-6))
            x1 = int(np.ceil((lm['coordinateBias'][0] + lm['coordinateScale'][0]) * w - 1e-6))
            y1 = int(np.ceil((lm['coordinateBias'][1] + lm['coordinateScale'][1]) * h - 1e-6))
            try:
                a, b = top_mip_rect(p, nac, x0, y0, x1, y1), top_mip_rect(p, dmc, x0, y0, x1, y1)
            except Exception:       # mips the reader can't reach: the next piece
                continue
            if not a.size or a.shape != b.shape:
                continue
            colour, directional = codec.decode(a, b, lm['slots'][1]['scale'])
            flat = (colour * directional.sum(-1, keepdims=True)).mean(-1)
            lit = flat > 1e-3
            if lit.sum() < 4:
                continue
            median = float(np.median(flat[lit]))
            ty, tx = np.unravel_index(int(np.argmin(np.where(lit, np.abs(flat - median), np.inf))), flat.shape)
            return dict(kind='even', textures=[s['index'] for s in lm['slots']], scales=[s['scale'] for s in lm['slots']],
                        bias=((x0 + tx + 0.5) / w, (y0 + ty + 0.5) / h), piece=p.name(ci), light=median,
                        texel=(int(tx), int(ty), int(flat.shape[1]), int(flat.shape[0])))
    return None


def dominant_shadow(p):
    """dict(guid (16 bytes), source (a ShadowMap2D of it, shadowmaps.shadow_maps' dict, on a 1,024-texel square
    where the map has one, else its largest)) for the map's dominant light, or None for a map without one."""
    import native_copy
    import shadowmaps
    guid = native_copy.dominant_guid(p)
    if guid is None:
        return None
    lights = {g: l for g, l in shadowmaps.dominant_lights(p).items() if g == guid.hex()}
    best = None
    for _, _, sm, _ in shadowmaps.dominant_receivers(p, lights):
        size = (p.own(sm['texture'], 'SizeX'), p.own(sm['texture'], 'SizeY'))
        if size == (1024, 1024):
            return dict(guid=guid, source=sm)
        if best is None or size[0] * size[1] > best[1]:
            best = (sm, size[0] * size[1])
    return dict(guid=guid, source=best[0] if best else None)


def piece_shadow(p, piece, guid, light):
    """The shadow map of the dominant light `guid` on component `piece` (the even light's piece), at the texel the
    even light `light` took (the same place in its rectangle: the maps' shadow maps share their lightmap's layout), as
    a dict(source, scale (0, 0), bias), or None where it has none."""
    import shadowmaps
    ci = p.by_name[piece]
    maps = [sm for sm in shadowmaps.shadow_maps(p, ci) if sm['guid'] == guid.hex() and not sm['factor']]
    if not maps or not light.get('texel'):
        return None
    sm = maps[0]
    w, h = p.own(sm['texture'], 'SizeX'), p.own(sm['texture'], 'SizeY')
    tx, ty, rw, rh = light['texel']
    sx, sy = sm['scale'][0] * w, sm['scale'][1] * h
    x0, y0 = int(np.floor(sm['bias'][0] * w + 1e-6)), int(np.floor(sm['bias'][1] * h + 1e-6))
    x = x0 + min(int(sx) - 1, int((tx + 0.5) / rw * sx)) if sx >= 1 else x0
    y = y0 + min(int(sy) - 1, int((ty + 0.5) / rh * sy)) if sy >= 1 else y0
    return dict(source=sm, scale=(0.0, 0.0), bias=((x + 0.5) / w, (y + 0.5) / h))


def shadow_map_export(g, p, walker, component, shadow):
    """A new ShadowMap2D under `component` (an export index of the grown map) for the dominant light: a clone of
    `shadow['source']` (shadowmaps' dict) with its coordinate scale and bias `shadow`'s, and its texture a clone of
    the source's own (`shadow['clone']` true: the relight writes it) or the source's (false). Returns its index."""
    import grow_fixture
    import native_copy
    src = shadow['source']['export']
    texture = shadow['source']['texture']
    if shadow.get('clone'):
        texture = grow_fixture.clone_texture(g, p, texture)
    e = p.exports[src - 1]
    data = bytearray(p.data[e['off']:e['off'] + e['size']])
    start = legacy_props.props_start(p.data, e, p.names) - e['off']
    at = walker.value(bytes(data), start, len(data), 'Texture[0]')
    if at is None:
        raise ValueError('%s saves no texture' % p.name(src))
    struct.pack_into('<i', data, at, texture)
    data = native_copy.set_struct(walker, g, data, start, 'CoordinateScale', 'Vector2D', '<2f', shadow['scale'])
    data = native_copy.set_struct(walker, g, data, start, 'CoordinateBias', 'Vector2D', '<2f', shadow['bias'])
    g.fresh_net_index(src, data, at=start - 4)
    new = g.add_export(src, bytes(data))
    g.entries[new - 1].put('<i', 8, component)
    return new


def irrelevant(walker, g, data, start, guid, listed):
    """`data` (a component's bytes, tagged properties from `start`) with the light `guid` (16 bytes) on its
    IrrelevantLights (`listed` true) or off it."""
    import native_lights
    raw = walker.value(bytes(data), start, len(data), 'IrrelevantLights[0]')
    guids = []
    if raw is not None:
        n = struct.unpack_from('<i', data, raw)[0]
        guids = [bytes(data[raw + 4 + 16 * k:raw + 20 + 16 * k]) for k in range(n)]
    kept = [x for x in guids if x != guid] + ([guid] if listed else [])
    if kept == guids:
        return data
    return native_lights.set_property(walker, g, data, start, 'IrrelevantLights', 'ArrayProperty', None,
                                      struct.pack('<i', len(kept)) + b''.join(kept))


def add_shadow_ref(data, at, index):
    """`data` (a component's bytes, its native data from `at`) with shadow map export `index` added to LOD 0's
    ShadowMaps."""
    if struct.unpack_from('<i', data, at)[0] < 1:
        raise ValueError('a component with no LOD record')
    n = struct.unpack_from('<i', data, at + 4)[0]
    return data[:at + 4] + struct.pack('<i', n + 1) + data[at + 8:at + 8 + 4 * n] + struct.pack('<i', index) + \
        data[at + 8 + 4 * n:]


def component_data(g, walker, p, old, new, mesh_index, built, paint, matrix, light=None, shadow=None, plain=False):
    """The clone component's bytes with the generated mesh: StaticMesh, FragmentBoundsMinZ and MaxZ,
    NumResourceIndices, LOD 0's painted colours one for each new vertex (or none, when the donor paints none), and
    its texture lightmap as `light` says (set_light); `shadow` dict(guid, export (a ShadowMap2D made for it, or None))
    gives it that shadow map of the dominant light and takes the light off its IrrelevantLights, or with no export
    lists it there."""
    e = p.exports[old - 1]
    start = legacy_props.props_start(p.data, e, p.names) - e['off']
    data = bytearray(g.export_data(new))
    lod = built['mesh']['lods'][0]
    pos = np.array(lod['positions'], float)
    wz = (np.c_[pos, np.ones(len(pos))] @ np.asarray(matrix).T)[:, 2]
    fields = (('StaticMesh[0]', '<i', mesh_index),) if plain else (
        ('StaticMesh[0]', '<i', mesh_index), ('FragmentBoundsMinZ[0]', '<f', float(wz.min())),
        ('FragmentBoundsMaxZ[0]', '<f', float(wz.max())), ('NumResourceIndices[0]', '<i', len(lod['indices'][1])))
    for name, fmt, value in fields:
        at = walker.value(bytes(data), start, len(data), name)
        if at is None and plain and name == 'StaticMesh[0]':
            # a plain piece that has its archetype's mesh saves none: the copy's is written at the properties' start
            data = bytearray(data[:start] + _tag(g, 'StaticMesh', 'ObjectProperty', 4) + struct.pack('<i', value) + data[start:])
            continue
        if at is None:
            raise ValueError('%s saves no %s' % (p.name(old), name))
        struct.pack_into(fmt, data, at, value)
    if shadow:
        data = bytearray(irrelevant(walker, g, data, start, shadow['guid'], shadow['export'] is None))
    end_props = native_props_end(walker, data, start)
    data = bytearray(set_light(bytes(data), end_props, light))
    flag, end = _lod_colours(data, end_props)
    if paint is None:
        block = b'\0'
    else:
        colours = painted(paint, built)
        block = b'\x01' + struct.pack('<2I', 4, len(colours)) + struct.pack('<2i', 4, len(colours)) + b''.join(colours)
    data = bytes(data[:flag] + block + data[end:])
    if shadow and shadow['export'] is not None:
        data = add_shadow_ref(data, end_props, shadow['export'])
    # the donor's painted-out fragments (a list of the donor's own) say nothing of the made mesh's: dropped
    import native_copy
    found = native_copy.find_prop(walker, data, start, len(data), 'EditorPaintedVisibleFragments[0]')
    if found is not None:
        _, tag, at, size = found
        data = data[:tag] + data[at + size:]
    return data


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
    convex_hull and layout, an element for each), or for each hull element given whole (hulls.hull_element's fields:
    a ramp's wedge, ground.py)."""
    def array(name, fmt, items):
        payload = struct.pack('<i', len(items)) + b''.join(struct.pack('<' + fmt, *(x if isinstance(x, list) else [x]))
                                                           for x in items)
        return _tag(g, name, 'ArrayProperty', len(payload)) + payload
    elems = b''
    for item in boxes:
        h = item if isinstance(item, dict) else cover_blocks.convex_hull(item[0], item[1], spec)
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


def door_columns(g, p, walls, doors, pad=TILE):
    """Each door copy that stands in a made wall's opening and that the wall's columns don't list yet, listed in the
    wall's columns within `pad` of it along the wall, on every storey (the game lists URB_Bar's door 7 in its wall's
    columns over four tiles, both storeys). `walls`: add_walls' records; `doors`: [(copy export, world box, its
    original's export)] of the door families' copies (leaf and frame). A door stands in an opening when their boxes meet by more than 8 along the
    wall and up, and at all across it (the compiler's overlaps_by). Each entry is a copy of one of the map's own
    entries for a piece of the same class (its MinZ the door's lowest point less one, as URB_Bar's frames save it).
    Returns [dict(wall, door, columns)] for each door listed."""
    if not doors:
        return []

    def pick(w, columns, along):
        out = []
        for door, dbox, original in doors:
            if any(x['actor'] == door for c in columns for x in c['entries']):
                continue                # listed already (edit_columns)
            if not any(overlaps_by(dbox, hole, 8.0) for hole in w['openings']):
                continue
            lo, hi = dbox[2 * along] - pad, dbox[2 * along + 1] + pad
            hit = [k for k, c in enumerate(columns) if min(hi, c['box'][2 * along + 1]) - max(lo, c['box'][2 * along]) > 1.0]
            if hit:
                out.append((door, dbox, original, hit))
        return out
    return [dict(wall=r['wall'], door=r['piece'], original=r['original'], columns=r['columns'])
            for r in _list_in_columns(g, p, walls, pick)]


def group_columns(g, p, walls, groups, pad=24.0):
    """The props and cover blocks of each group that breaks together with a made wall, listed in that wall's columns
    they stand by: each column whose box meets the piece's box grown by `pad` (a picture hangs a unit off the wall's
    face), or the nearest one when none does, so a piece always goes with some part of its wall. `walls`: add_walls'
    records, each with `group` (the break group it is in, or none); `groups`: {group: [(export, world box, the export
    whose class its entry copies)]}, the group's breakable pieces. Returns [dict(wall, piece, original, columns)]."""
    def pick(w, columns, along):
        out = []
        for piece, box, original in groups.get(w.get('group'), ()):
            if any(x['actor'] == piece for c in columns for x in c['entries']):
                continue
            grown = [v + (-pad if k % 2 == 0 else pad) for k, v in enumerate(box)]
            hit = [k for k, c in enumerate(columns)
                   if all(min(grown[2 * a + 1], c['box'][2 * a + 1]) - max(grown[2 * a], c['box'][2 * a]) > 0 for a in range(3))]
            if not hit and columns:
                def apart(c):
                    return sum(max(0.0, c['box'][2 * a] - box[2 * a + 1], box[2 * a] - c['box'][2 * a + 1]) ** 2 for a in range(3))
                hit = [min(range(len(columns)), key=lambda k: apart(columns[k]))]
            if hit:
                out.append((piece, box, original, hit))
        return out
    return _list_in_columns(g, p, [w for w in walls if w.get('group')], pick)


def _list_in_columns(g, p, walls, pick):
    """Pieces listed in made walls' columns: for each made wall of `walls` (add_walls' records), pick(wall, its
    columns (native_copy.fragment_columns'), the axis along it) gives [(piece export, its world box, the export whose
    class its entry copies, column indices)]; each gets a copy of one of the map's own DestructibleCache entries for a
    piece of that class (its MinZ the piece's lowest point less one, as the game's frames save it; its CutdownFloor 0,
    as a door's) in those columns. Returns [dict(wall, piece, original, columns)]."""
    import native_copy
    walker = native_copy.Walker(p)
    level = p.by_name['TheWorld.PersistentLevel']
    templates = {}
    for i in range(1, len(p.exports) + 1):
        if p.cls(i) in native_copy.FRACTURING and p.exports[i - 1]['outer'] == level:
            e = p.exports[i - 1]
            start = legacy_props.props_start(p.data, e, p.names) - e['off']
            parsed = native_copy.fragment_columns(walker, p.data[e['off']:e['off'] + e['size']], start)
            for c in (parsed[1] if parsed else []):
                for x in c['entries']:
                    if x['actor'] > 0 and x['actorAt'] is not None:
                        templates.setdefault(p.cls(x['actor']), x)
    if not templates:
        return []
    out = []
    for w in walls:
        if w.get('kind') != 'fracWall':
            continue
        e = p.exports[w['original'] - 1]
        start = legacy_props.props_start(p.data, e, p.names) - e['off']
        b = bytearray(g.export_data(w['copy']))
        parsed = native_copy.fragment_columns(walker, b, start)
        if parsed is None:
            continue
        field, columns = parsed
        box = w['box']
        along = 0 if box[1] - box[0] >= box[3] - box[2] else 1
        lists = [[x['raw'] for x in c['entries']] for c in columns]
        picked = pick(w, columns, along)
        for piece, pbox, original, hit in picked:
            template = templates.get(p.cls(original)) or next(iter(templates.values()))
            raw = bytearray(native_copy.entry_for(template, piece))
            if template['minZAt'] is not None:
                struct.pack_into('<f', raw, template['minZAt'], float(pbox[4]) - 1.0)
            if template['cutdownAt'] is not None:
                raw[template['cutdownAt']] = 0
            for k in hit:
                lists[k].append(bytes(raw))
            out.append(dict(wall=w['copy'], piece=piece, original=original, columns=hit))
        if picked:
            parts = [native_copy.column_with(g, walker, b, c, new) for c, new in zip(columns, lists)]
            g.relocate(w['copy'], native_copy.rebuilt(b, field, parts))
    return out


# ---------------------------------------------------------------------------------------------------- neighbours
NEIGHBOUR_GROW = 1.0            # the other piece's bounds, grown by this, cut its column's box (the game's rule)
NEIGHBOUR_SLACK = 0.01          # boxes this close count as touching (the game compares closed boxes)


def lists_column(box, other, bounds):
    """Whether a column whose box is `box` lists another piece's column `other` (boxes [x0, x1, y0, y1, z0, z1]): it
    touches or overlaps `other` cut to that piece's `bounds` (a box, or None for no cut on an axis: [lo or None, hi or
    None] x 3) grown by NEIGHBOUR_GROW."""
    cut = list(other)
    for k in range(3):
        lo, hi = bounds[2 * k], bounds[2 * k + 1]
        if lo is not None:
            cut[2 * k] = max(cut[2 * k], lo - NEIGHBOUR_GROW)
        if hi is not None:
            cut[2 * k + 1] = min(cut[2 * k + 1], hi + NEIGHBOUR_GROW)
        if cut[2 * k] > cut[2 * k + 1]:
            return False
    return all(box[2 * k] <= cut[2 * k + 1] + NEIGHBOUR_SLACK and cut[2 * k] <= box[2 * k + 1] + NEIGHBOUR_SLACK
               for k in range(3))


def neighbour_columns(g, p, walls, pieces):
    """The made walls of `walls` (add_walls' records) and every fracturing piece they touch list each other's columns
    by the game's rule (lists_column), in their FracActorCache. `pieces`: the level's other fracturing pieces as they
    stand in the grown map, [dict(export, original (the export whose layout its bytes keep: itself, or a copy's
    original), bounds (its vertices' box, None on an axis not known: the game's columns are already cut to it across
    and along, so the heights are what matter: FragmentBoundsMinZ and MaxZ))]. A made wall's bounds are its box.
    Listings between two of the map's own pieces are the map's, left as they are. Returns [dict(wall, other, lists (the
    wall's listings of the other's columns), listed (the other's of the wall's))]."""
    import native_copy
    walker = native_copy.Walker(p)
    made = [dict(export=w['copy'], original=w['original'], bounds=list(w['box']), made=True)
            for w in walls if w.get('kind') in MADE]
    if not made:
        return []
    every = made + [dict(x, made=False) for x in pieces if x['export'] not in {m['export'] for m in made}]
    for x in every:
        e = p.exports[x['original'] - 1]
        x['start'] = legacy_props.props_start(p.data, e, p.names) - e['off']
        x['bytes'] = bytearray(g.export_data(x['export']))
        parsed = native_copy.fragment_columns(walker, x['bytes'], x['start'])
        x['field'], x['columns'] = parsed if parsed else (None, [])
        lo = [min(c['box'][2 * k] for c in x['columns']) for k in range(3)] if x['columns'] else None
        hi = [max(c['box'][2 * k + 1] for c in x['columns']) for k in range(3)] if x['columns'] else None
        x['span'] = [v for k in range(3) for v in (lo[k], hi[k])] if lo else None
        x['new'] = [[] for _ in x['columns']]
    out = []
    for a in made:
        for b in every:
            if b is a or not b['columns'] or not a['columns'] or (b['made'] and b['export'] < a['export']):
                continue
            # (pieces far apart: nothing to test)
            if any(a['span'][2 * k] > b['span'][2 * k + 1] + 2 or b['span'][2 * k] > a['span'][2 * k + 1] + 2 for k in range(3)):
                continue
            lists = listed = 0
            for i, ca in enumerate(a['columns']):
                for n, cb in enumerate(b['columns']):
                    if lists_column(ca['box'], cb['box'], b['bounds']):
                        a['new'][i].append((b['export'], n))
                        lists += 1
                    if lists_column(cb['box'], ca['box'], a['bounds']):
                        b['new'][n].append((a['export'], i))
                        listed += 1
            if lists or listed:
                out.append(dict(wall=a['export'], other=b['export'], lists=lists, listed=listed))
    for x in every:
        if not any(x['new']):
            continue
        parts = []
        for c, new in zip(x['columns'], x['new']):
            have = set()
            for n in c['neighbours']:
                at = native_copy.find_prop(walker, n['raw'], 0, len(n['raw']), 'ColumnIndex[0]')
                have.add((n['actor'], struct.unpack_from('<i', n['raw'], at[2])[0] if at else 0))
            raws = [n['raw'] for n in c['neighbours']]
            for actor, index in new:
                if (actor, index) not in have:
                    have.add((actor, index))
                    # (an index of 0 is left out, as the game saves a struct's default values)
                    raws.append(_tag(g, 'FracActor', 'ObjectProperty', 4) + struct.pack('<i', actor)
                                + (_tag(g, 'ColumnIndex', 'IntProperty', 4) + struct.pack('<i', index) if index else b'')
                                + _none(g))
            parts.append(native_copy.column_with(g, walker, x['bytes'], c, [e['raw'] for e in c['entries']], raws))
        g.relocate(x['export'], native_copy.rebuilt(x['bytes'], x['field'], parts))
    return out


def overlaps_by(a, b, least):
    """Whether the boxes a and b ([x0, x1, y0, y1, z0, z1]) meet by more than `least` along b's longer side and up,
    and at all across it (the compiler's overlaps_by, the page's boxesMeet)."""
    along = 0 if b[1] - b[0] >= b[3] - b[2] else 1
    over = [min(a[2 * k + 1], b[2 * k + 1]) - max(a[2 * k], b[2 * k]) for k in range(3)]
    return over[along] > least and over[2] > least and over[1 - along] > 0


def add_walls(g, p, items, grid, bake=True):
    """The generated copies `items` ([dict(original: the donor actor's export, info: clone_assembly's dict for the
    copy, generated, location, rotation, label)]) made in the map being grown: returns a record for each (dict(kind,
    copy, mesh, bodySetup, fragments, columns, vertices, triangles, box, light)). `bake`: the Build bakes the lighting
    (each wall's lightmap its own rectangle, which the relight fills); without, each wall gets an even light."""
    import lightmap_texels
    import native_copy
    walker = native_copy.Walker(p)
    built, records = [], []
    dominant = None
    for item in items:
        gen = check(item['generated'])
        original = item['original']
        if gen['kind'] == 'ground':
            comp_old = p.own(original, 'StaticMeshComponent')
            if not comp_old or p.cls(original) not in GROUND_CLASSES:
                raise ValueError('%s is no plain piece: a ground shape copies one (%s)' % (p.name(original), ', '.join(GROUND_CLASSES)))
        else:
            comp_old = p.own(original, 'FracturedStaticMeshComponent')
            if not comp_old or p.cls(original) not in native_copy.FRACTURING:
                raise ValueError('%s is no fracturing piece: a generated wall copies one' % p.name(original))
        # (a plain piece placed from an archetype may save no mesh of its own: it has its archetype's)
        donor_mesh = p.own(comp_old, 'StaticMesh') or p.effective(comp_old, 'StaticMesh', None)
        if gen['kind'] == 'relit':
            records.append(dict(kind='relit', copy=item['info']['actor'], label=item.get('label')))
            continue
        template = gen_mesh.read(p, donor_mesh)
        if gen['kind'] == 'ground':
            # (its vertices take the donor's commonest painted colour: the ground's blend materials read them)
            paint = donor_paint(p, comp_old, template)
            out = ground.build(gen['ground'], template, colour=ground.dominant_colour(paint['colours']) if paint else None)
            built.append((item, comp_old, donor_mesh, template, out, ground.mesh_name(gen['ground'])))
            continue
        if gen['kind'] == 'fracSlab':
            out = frac_slab.build(gen['slab'], template)
            built.append((item, comp_old, donor_mesh, template, out, frac_slab.mesh_name(gen['slab'])))
            continue
        out = frac_wall.build(gen['wall'], template)
        built.append((item, comp_old, donor_mesh, template, out, frac_wall.mesh_name(gen['wall'])))
    if not built:
        return records
    dominant = dominant_shadow(p)
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
        plain = item['generated']['kind'] == 'ground'
        paint = None if plain else donor_paint(p, comp_old, template)
        # the fragments' world boxes, and the columns by F0's rule
        boxes = [world_box(f['box'], matrix) for f in out['fragments']]
        lo = [min(x[2 * k] for x in boxes) for k in range(3)]
        hi = [max(x[2 * k + 1] for x in boxes) for k in range(3)]
        wall_box = [v for k in range(3) for v in (lo[k], hi[k])]
        shadow, sm = None, None
        if bake:
            atlas = atlas_size(p, comp_old)
            light = dict(kind='rect', rect=out['lightmapRect'], atlas=atlas) if atlas else None
            if dominant and dominant['source']:
                t = dominant['source']['texture']
                w, h = p.own(t, 'SizeX'), p.own(t, 'SizeY')
                rw, rh = out['lightmapRect']
                if rw <= w and rh <= h:
                    sm = dict(source=dominant['source'], scale=(rw / w, rh / h), bias=(0.0, 0.0), clone=True)
        else:
            light = even_light(p, wall_box)
            if dominant and light:
                sm = piece_shadow(p, light['piece'], dominant['guid'], light)
        if dominant:
            shadow = dict(guid=dominant['guid'], export=shadow_map_export(g, p, walker, comp_new, sm) if sm else None)
        g.relocate(comp_new, component_data(g, walker, p, comp_old, comp_new, made[name], out, paint, matrix, light,
                                            shadow, plain=plain))
        if plain:
            records.append(dict(kind='ground', copy=info['actor'], original=item['original'], openings=[], group=0,
                                label=item.get('label'), mesh=made[name], meshName=name, bodySetup=made[name] + 1,
                                fragments=0, vertices=out['counts']['vertices'], triangles=out['counts']['triangles'],
                                solids=len(out['solids']), columns=0, painted=False, box=wall_box,
                                lightmapRect=out['lightmapRect'],
                                light=(None if light is None else dict(kind='rect', rect=light['rect']) if light['kind'] == 'rect'
                                       else dict(kind='even', piece=light['piece'], light=round(light['light'], 4))),
                                shadowMap=(None if shadow is None else
                                           dict(export=shadow['export'], own=bool(sm and sm.get('clone')),
                                                source=sm['source']['path'] if sm else None,
                                                irrelevant=shadow['export'] is None))))
            continue
        slab = item['generated']['kind'] == 'fracSlab'
        cols = slab_columns(boxes) if slab else columns(boxes, grid)
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
        h = max(y for y, _, _ in frac_wall.RECIPE['section'])
        holes = [] if slab else [world_box([o['x0'], o['x1'], -h, h, o['z0'], o['z1']], matrix)
                                 for o in item['generated']['wall'].get('openings') or []]
        records.append(dict(kind=item['generated']['kind'], copy=actor, original=item['original'], openings=holes,
                            group=item.get('wallGroup') or 0,
                            label=item.get('label'), mesh=made[name], meshName=name,
                            bodySetup=made[name] + 1, fragments=out['counts']['fragments'],
                            vertices=out['counts']['vertices'], triangles=out['counts']['triangles'],
                            solids=len(out['solids']), columns=len(cols), painted=paint is not None,
                            box=wall_box, lightmapRect=out['lightmapRect'],
                            light=(None if light is None else dict(kind='rect', rect=light['rect']) if light['kind'] == 'rect'
                                   else dict(kind='even', piece=light['piece'], light=round(light['light'], 4))),
                            shadowMap=(None if shadow is None else
                                       dict(export=shadow['export'], own=bool(sm and sm.get('clone')),
                                            source=sm['source']['path'] if sm else None,
                                            irrelevant=shadow['export'] is None))))
    return records

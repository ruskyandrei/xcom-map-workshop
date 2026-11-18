"""Measures one of the game's fracturing floors or roofs (a slab) for tools/bake/frac_slab.py (custom geometry plan,
M4a item 2; grown from research/evidence/slab-audit.py, which found the 55 slab meshes of the install).

  measure(package, what) -> entry     what: an actor (XComFracLevelActor, XComDecoFracLevelActor) or a mesh path
                                      placed in the map `package` (a tools/upk Package)
  twin(recipe) -> dict(ok, rows)      the slab built at the donor's size and measured again

An entry is dict(recipe, warnings, facts). The recipe is what frac_slab builds a slab from (a look given as a dict,
`{'mesh', 'measure', 'recipe'}`), in the donor mesh's frame in world units (its placing's scale applied: a made slab
stands at scale 1, as the editor draws it and the Build copies it, frac_walls.unscale):

  role, kind    'floor' or 'roof' (by the mesh's name, as the audit); 'flat', 'thick' (a flat top over a deeper body)
                or 'pitched' (a roof whose top slopes): the audit's classify
  bottom, top   the made plate's underside and top: a flat or thick slab's from the main level of its level faces down
                and up (the most area within half a unit); a pitched roof's made flat (D13) at its eaves (the lowest
                corner of its top), PITCHED_PLATE thick
  slots         the donor's material slots for the made faces: top (the slot with the most area facing up), underside
                (the most facing down, the top's when it has none), edge (the most upright area on the mesh's outline,
                else the top's); the made mesh has the donor's `sections`, in slot order, a slot it makes nothing in
                left empty (the donor's beams, trims or a second top material: a warning names them)
  interior      the donor's interior index (the slot of the faces inside it, seen once a fragment goes);
                insideFaces whether the donor draws any there (the made slab then has them on its fragments' shared
                edges, as a wall's)
  uv            the texture's planar maps (measure_common.planar_map, per world unit, offsets modulo 1): top and
                underside over x and y, [[a, b, c], [d, e, f]] for u = a x + b y + c, v = d x + e y + f; edge
                {x: map over x and z for the edges along x, y: over y and z}
  collision     the heights of its simple collision, within the plate (the plate's when it has none)
  tile, split, long   the made fragments (frac_slab.fragments): split, a tile's share cut into two halves on a diagonal
                (the donor's share of fragments of half tiles, at most a half), long, a tile's share joined with its
                neighbour, set so the made slab has about the donor's fragments a tile
  colours       outside: the commonest colour of the donor's top; interior: of its inside faces (frac_slab paints a
                made slab from the donor mesh's own colours when the Build gives it the donor: these are for a build
                without it)
  lightmap      density: texels a unit as the placing's lightmap has it (measure_common.density), else DEFAULT_DENSITY;
                margin 2, interiorDensity 1, block 4 (as today's looks)
  measured      what the twin check compares with: the donor's size, triangles, fragments a tile and kind

Warnings say in plain words what a made slab lacks. Facts: role, kind, thickness, layout (the audit's slot layout), size,
placings' scale, triangles, fragments, repeats. Nothing is written."""
import math
import re

import numpy as np

import measure_common as mc

VERSION = 1
FRACTURING = ('XComDecoFracLevelActor', 'XComFracLevelActor')
TILE = 96.0
NAMED = re.compile(r'floor|roof|slab|deck|balcon|ceiling', re.I)
WIDE, FLAT, THICK = 80.0, 24.0, 80.0
UP = 0.3            # a face facing up: its outward normal's z at least this (down: at most -UP)
LEVEL_UP = 0.98     # a level face
PITCHED_PLATE = 4.0
DEFAULT_DENSITY = 0.2
PIECEWISE = 0.02    # a texture whose vertices lie further than this (of a repeat) from one planar map is piecewise
LIGHTMAP = dict(margin=2, interiorDensity=1.0, block=4)


def classify(name, size, level, cover):
    """(kind, why): 'flat', 'thick', 'pitched' or None (not a slab) with the reason (research/evidence/slab-audit.py's
    rule; `level` the share of its up area that is level, `cover` the share of its box its top covers)."""
    sx, sy, sz = size
    named = bool(NAMED.search(name.rsplit('.', 1)[-1]))
    if min(sx, sy) < WIDE:
        return None, 'narrow (%.0f): a trim, parapet or cover' % min(sx, sy)
    if sz <= FLAT:
        return 'flat', None
    if not named:
        return None, 'not named for a floor or roof and %.0f thick' % sz
    if sz <= THICK and level >= 0.8 and sz < 0.25 * min(sx, sy):
        return 'thick', None
    if 'roof' in name.lower() and level < 0.5 and cover >= 0.85 and min(sx, sy) >= 150:
        return 'pitched', None
    return None, '%.0f thick, %.0f%% of its top level' % (sz, 100 * level)


def _cover(T, up):
    """The share of the mesh's xy box its up faces cover (rasterised at 4 units, as the audit)."""
    pos = T.pos
    lo, hi = pos[:, :2].min(0), pos[:, :2].max(0)
    cell = 4.0
    nx, ny = max(1, int(math.ceil((hi[0] - lo[0]) / cell))), max(1, int(math.ceil((hi[1] - lo[1]) / cell)))
    grid = np.zeros((ny, nx), bool)
    xs = lo[0] + (np.arange(nx) + 0.5) * cell
    ys = lo[1] + (np.arange(ny) + 0.5) * cell
    for t in T.tris[up]:
        p = pos[t][:, :2]
        i0, i1 = np.searchsorted(xs, p[:, 0].min() - 1e-6), np.searchsorted(xs, p[:, 0].max() + 1e-6)
        j0, j1 = np.searchsorted(ys, p[:, 1].min() - 1e-6), np.searchsorted(ys, p[:, 1].max() + 1e-6)
        if i1 <= i0 or j1 <= j0:
            continue
        gx, gy = np.meshgrid(xs[i0:i1], ys[j0:j1])
        d = (p[1, 1] - p[2, 1]) * (p[0, 0] - p[2, 0]) + (p[2, 0] - p[1, 0]) * (p[0, 1] - p[2, 1])
        if abs(d) < 1e-9:
            continue
        l1 = ((p[1, 1] - p[2, 1]) * (gx - p[2, 0]) + (p[2, 0] - p[1, 0]) * (gy - p[2, 1])) / d
        l2 = ((p[2, 1] - p[0, 1]) * (gx - p[2, 0]) + (p[0, 0] - p[2, 0]) * (gy - p[2, 1])) / d
        grid[j0:j1, i0:i1] |= (l1 >= -1e-6) & (l2 >= -1e-6) & (1 - l1 - l2 >= -1e-6)
    return float(grid.mean())


def classify_mesh(m, name):
    """(kind, why) of the decoded mesh `m` named `name` (classify, on its size, the level share of its up faces and,
    for one thicker than a flat slab, its top's cover)."""
    T = mc.Tris(m)
    if not len(T.tris):
        return None, 'no triangles'
    nz = T.normal[:, 2]
    up = nz >= UP
    size = [float(v) for v in T.pos.max(0) - T.pos.min(0)]
    level = float(T.area[nz >= LEVEL_UP].sum() / max(T.area[up].sum(), 1e-9))
    cover = _cover(T, up) if up.any() and size[2] > FLAT else 0.0
    return classify(name, size, level, cover)


def _main_level(T, sel):
    """The height of the triangles `sel` holding the most area (binned by half units; the area-weighted mean height of
    that bin's), or None."""
    if not sel.any():
        return None
    cz = T.pos[T.tris[sel]].mean(1)[:, 2]
    w = T.area[sel]
    keys = np.round(cz * 2) / 2
    bins = {}
    for z, a in zip(keys, w):
        bins[float(z)] = bins.get(float(z), 0.0) + float(a)
    best = max(sorted(bins), key=lambda z: bins[z])
    pick = keys == best
    return float((cz[pick] * w[pick]).sum() / max(w[pick].sum(), 1e-12))


def _faces_word(T, slot, interior, on_box):
    """The audit's words for a slot's faces: 'inside', or top, underside and edges (upright on the outline) or sides."""
    sel = T.slot == slot
    if slot == interior:
        return 'inside'
    nz = T.normal[:, 2]
    a = dict(up=float(T.area[sel & (nz >= UP)].sum()), down=float(T.area[sel & (nz <= -UP)].sum()),
             side=float(T.area[sel & (np.abs(nz) < UP)].sum()), box=float(T.area[sel & (np.abs(nz) < UP) & on_box].sum()))
    total = max(a['up'] + a['down'] + a['side'], 1.0)
    out = []
    if a['up'] / total > 0.05:
        out.append('top')
    if a['down'] / total > 0.05:
        out.append('underside')
    if a['side'] / total > 0.002:
        out.append('edges' if a['box'] >= 0.5 * a['side'] else 'sides')
    return '+'.join(out)


_TABLE = []


def made_per_tile(split, long_):
    """The fragments a tile frac_slab.fragments makes at these shares (a 10 by 10 tile slab, seeds 1 to 3)."""
    import frac_slab
    look = dict(mesh='(shares)', measure=VERSION, recipe=dict(tile=TILE, split=split, long=long_))
    return sum(len(frac_slab.fragments(dict(x0=0.0, x1=960.0, y0=0.0, y1=960.0, seed=seed, look=look)))
               for seed in (1, 2, 3)) / 300.0


def shares(per, halves):
    """(split, long, the made fragments a tile) nearest the donor's `per` fragments a tile, its share of fragments of
    half tiles `halves` kept where that costs nothing: the grid of shares a twentieth apart, each made (made_per_tile),
    the nearest by the ratio of fragments a tile, then by the halves' share."""
    if not _TABLE:
        _TABLE.extend((s / 20.0, l / 20.0, made_per_tile(s / 20.0, l / 20.0)) for s in range(21) for l in range(21))
    return min(_TABLE, key=lambda r: (round(abs(math.log(r[2] / per)) + 0.1 * abs(r[0] - min(0.5, halves)), 3),
                                      r[0], r[1]))


def _round(v, digits=2):
    return round(float(v), digits) + 0.0


def measure_mesh(m, name, light=None, collision=None, lm_channel=1, scale=(1.0, 1.0, 1.0)):
    """The entry (see the module's words) of the decoded slab mesh `m` (gen_mesh's form) named `name`, with its
    placing's lightmap (`light`: dict(rect) from measure_common.component_light) and simple collision (`collision`:
    boxes [x0, x1, y0, y1, z0, z1] in the mesh's frame, None for none), its lightmap in channel `lm_channel`, placed
    at `scale` (the recipe is in world units: a made slab stands at scale 1)."""
    T = mc.Tris(m, scale, lm_channel)
    if collision:
        collision = [[v for k in range(3) for v in sorted((b[2 * k] * scale[k], b[2 * k + 1] * scale[k]))]
                     for b in collision]
    if not len(T.tris):
        raise ValueError('%s has no triangles' % name)
    nz = T.normal[:, 2]
    pos = T.pos
    lo, hi = pos.min(0), pos.max(0)
    size = [float(v) for v in hi - lo]
    interior = m['fractured']['interior'] if m.get('fractured') else T.sections
    up, down = nz >= UP, nz <= -UP
    level_up, level_down = nz >= LEVEL_UP, nz <= -LEVEL_UP
    side = np.abs(nz) < UP
    centre = pos[T.tris].mean(1)
    on_box = ((np.abs(centre[:, 0] - lo[0]) < 0.6) | (np.abs(centre[:, 0] - hi[0]) < 0.6)
              | (np.abs(centre[:, 1] - lo[1]) < 0.6) | (np.abs(centre[:, 1] - hi[1]) < 0.6))
    live = T.slot != interior
    level = float(T.area[level_up].sum() / max(T.area[up].sum(), 1e-9))
    cover = _cover(T, up) if up.any() else 0.0
    kind, why = classify(name, size, level, cover)
    role = 'roof' if 'roof' in name.lower() else 'floor'
    warnings = []
    if kind is None:
        warnings.append('not one of the game\'s floors or roofs (%s): made as a flat slab of its top' % why)
        kind = 'flat'

    def most(sel):
        areas = {}
        for s, a in zip(T.slot[sel], T.area[sel]):
            areas[int(s)] = areas.get(int(s), 0.0) + float(a)
        return max(sorted(areas), key=lambda s: areas[s]) if areas else None
    top_slot = most(live & (level_up if level_up.any() and kind != 'pitched' else up))
    if top_slot is None:
        top_slot = most(live)
    under_slot = most(live & down)
    if under_slot is None:
        under_slot = top_slot
    edge_slot = most(live & side & on_box)
    if edge_slot is None:
        edge_slot = top_slot
    slots = dict(top=top_slot, underside=under_slot, edge=edge_slot)
    inside = bool(interior < T.sections and (T.slot == interior).any())
    # the plate's heights
    if kind == 'pitched':
        top_faces = (T.slot == top_slot) & up
        top = float(pos[T.verts(top_faces), 2].min())
        bottom = top - PITCHED_PLATE
        z = pos[T.verts(top_faces), 2]
        warnings.append('a pitched roof (its top slopes from %g to %g): made flat at its eaves, %g thick, in its top\'s '
                        'material' % (_round(z.min()), _round(z.max()), PITCHED_PLATE))
    else:
        top = _main_level(T, (T.slot == top_slot) & level_up)
        if top is None:
            top = float(hi[2])
        bottom = _main_level(T, (T.slot == under_slot) & level_down)
        if bottom is None or bottom >= top - 0.25:
            bottom = float(lo[2]) if lo[2] < top - 0.25 else top - PITCHED_PLATE
        if kind == 'thick':
            warnings.append('a thick roof (%g deep): made as a plain plate from its top to its underside (%g thick), in '
                            'its top\'s material' % (_round(size[2]), _round(top - bottom)))
    top, bottom = _round(top), _round(bottom)
    # the texture's maps
    maps, words = {}, {}
    under = (T.slot == under_slot) & level_down
    for key, sel in (('top', (T.slot == top_slot) & (level_up if kind != 'pitched' else up)),
                     ('underside', under if under.any() and kind != 'pitched' else (T.slot == under_slot) & down)):
        found = mc.planar_map(T, sel, (0, 1))
        if found is None:
            found = dict(u=[1 / 192.0, 0.0, 0.0], v=[0.0, 1 / 192.0, 0.0], spread=[0.0, 0.0], repeat=[192.0, 192.0],
                         axis=['+x', '+y'])
            if key == 'underside':
                warnings.append('it has no underside: the made slab\'s is laid as its top\'s')
                found = dict(maps['top_raw'])
        maps[key + '_raw'] = found
        maps[key] = mc.rounded_map(found)
        words[key] = dict(repeat=[_round(r, 1) if r else None for r in found['repeat']], axis=found['axis'],
                          spread=[_round(s, 3) for s in found['spread']])
        if max(found['spread']) > PIECEWISE and kind != 'pitched':
            warnings.append('its %s\'s texture is laid out piece by piece (no one repeat across it): made with one even '
                            'repeat' % key)
    edge = {}
    for along, axes in (('x', (0, 2)), ('y', (1, 2))):
        normal_axis = 1 if along == 'x' else 0
        sel = (T.slot == edge_slot) & side & on_box & (np.abs(T.normal[:, normal_axis]) > 0.9)
        found = mc.planar_map(T, sel, axes)
        edge[along] = (mc.rounded_map(found) if found else
                       [[maps['top'][0][0] if along == 'x' else maps['top'][0][1], 0.0, 0.0],
                        [0.0, round(1 / 192.0, 7), 0.0]])
    # the collision, within the plate
    if collision:
        z0 = max(bottom, min(b[4] for b in collision))
        z1 = min(top, max(b[5] for b in collision))
        coll = [_round(z0), _round(z1)] if z1 > z0 + 0.05 else [bottom, top]
    else:
        coll = [bottom, top]
    # the fragments
    frags = m['fractured']['fragments'] if m.get('fractured') else []
    tiles = max(size[0] * size[1] / TILE ** 2, 1.0)
    per = len(frags) / tiles if frags else 1.0
    halves, counted = 0, 0
    for f in sorted(set(T.frag.tolist()) - {-1}):
        a = float(T.area[(T.frag == f) & level_up].sum()) / TILE ** 2
        if a > 0.2:
            counted += 1
            halves += abs(a - round(a)) > 0.25
    split, long_, made = shares(per, halves / counted if counted else 0.0)
    if made > 1.5 * per:
        warnings.append('its fragments are bigger than a made slab\'s (%.2f a tile; a made slab has at least %.2f)'
                        % (per, made))
    elif made < per / 1.5:
        warnings.append('its fragments are smaller than a made slab\'s (%.2f a tile; a made slab has at most %.2f)'
                        % (per, made))
    # colours
    outside = T.commonest_colour(T.slot == top_slot) or 'ffffffff'
    inner = T.commonest_colour(T.slot == interior) if inside else None
    # the lightmap
    rect = (light or {}).get('rect')
    dens = mc.density(rect, T.lightmap_area(), float(T.area.sum()))
    # slots the made slab leaves empty
    layout = ' | '.join('%d:%s' % (s, _faces_word(T, s, interior, on_box)) for s in sorted(set(T.slot.tolist())))
    for s in sorted(set(T.slot.tolist())):
        if s == interior or s in slots.values():
            continue
        warnings.append('its material slot %d (%s: beams, trims or a second top material) isn\'t made: the made slab '
                        'leaves it empty' % (s, _faces_word(T, s, interior, on_box).replace('+', ', ') or 'faces'))
    if any(abs(v / TILE - round(v / TILE)) * TILE > 12 for v in size[:2]):
        warnings.append('its footprint (%g x %g) isn\'t whole tiles: a made slab is whole tiles' % (_round(size[0], 1),
                                                                                                  _round(size[1], 1)))
    recipe = dict(
        role=role, kind=kind, bottom=bottom, top=top, slots=slots, sections=T.sections, interior=int(interior),
        insideFaces=inside, uv=dict(top=maps['top'], underside=maps['underside'], edge=edge), collision=coll,
        tile=TILE, split=_round(split), long=_round(long_),
        colours=dict(outside=outside, interior=inner or outside),
        lightmap=dict(density=_round(dens, 4) if dens else DEFAULT_DENSITY, **LIGHTMAP),
        measured=dict(size=[_round(v, 1) for v in size], triangles=int(len(T.tris)), fragments=len(frags),
                      perTile=_round(per, 3), kind=kind,
                      # the box's centre in the mesh's frame: a made slab's centre reads the maps here (frac_slab)
                      centre=[_round(float(lo[0] + hi[0]) / 2, 2), _round(float(lo[1] + hi[1]) / 2, 2)]))
    facts = dict(role=role, kind=kind, thickness=_round(size[2]), layout=layout, size=[_round(v, 1) for v in size],
                 triangles=int(len(T.tris)), fragments=len(frags), repeats=words,
                 lightmap=dict(rect=rect, density=_round(dens, 4) if dens else None))
    return dict(recipe=recipe, warnings=warnings, facts=facts)


def collision_boxes(p, mesh):
    """The mesh's simple collision as boxes [x0, x1, y0, y1, z0, z1] (tools/viewer/collision.py), or None."""
    import collision
    try:
        c = collision.line_collision(p, mesh)
    except (ValueError, KeyError):
        return None
    if not c.get('simple') or not c.get('elements'):
        return None
    out = []
    for e in c['elements']:
        q = np.array(e, float).reshape(-1, 3)
        out.append([float(v) for k in range(3) for v in (q[:, k].min(), q[:, k].max())])
    return out


def measure(package, what):
    """The entry of the slab `what` (an actor or a mesh path) placed in the map `package`."""
    import gen_mesh
    p = package
    actor, comp, mesh = mc.find_placing(p, what, FRACTURING, 'FracturedStaticMeshComponent')
    if p.cls(mesh) != 'FracturedStaticMesh':
        raise ValueError('%s is no fracturing mesh' % p.name(mesh))
    m = gen_mesh.read(p, mesh)
    scale = mc.scale_of(p, actor, comp)
    entry = measure_mesh(m, p.name(mesh), mc.light_of(p, comp), collision_boxes(p, mesh),
                         int(p.effective(mesh, 'LightMapCoordinateIndex', 1) or 1), scale)
    entry['facts'].update(mesh=p.name(mesh), actor=p.name(actor).split('.')[-1], scale=[_round(v, 4) for v in scale])
    return entry


def twin_slab(recipe):
    """The slab numbers of the donor's size (whole tiles, at most frac_slab.MAX_TILES each way) in the recipe's frame:
    round the donor box's centre (`measured.centre`), so the twin stands where the donor does and its maps are the
    donor's at the same points; from the frame's corner for a recipe without one."""
    import frac_slab
    sx, sy = recipe['measured']['size'][:2]
    t = recipe['tile']
    nx = min(frac_slab.MAX_TILES, max(1, int(round(sx / t))))
    ny = min(frac_slab.MAX_TILES, max(1, int(round(sy / t))))
    centre = recipe['measured'].get('centre')
    if not centre:
        return dict(x0=0.0, x1=nx * t, y0=0.0, y1=ny * t, seed=1)
    cx, cy = centre
    return dict(x0=cx - nx * t / 2, x1=cx + nx * t / 2, y0=cy - ny * t / 2, y1=cy + ny * t / 2, seed=1)


def twin(recipe, template=None):
    """The twin check: the slab built in `recipe` at the donor's size (twin_slab; on the donor's decoded mesh
    `template` when given) and measured again: dict(ok, rows [dict(key, donor, twin, ok)], built (the slab's numbers)).
    It compares what makes the look: the heights, the slots and sections, the texture's maps, the collision, the
    colours, the lightmap's density (within a fifth), the fragments a tile (within half again) and the triangles a
    tile (within a tenth, against the donor's: a soft row, told but not failing the check, as a made slab's
    fragments are cut another way), and the footprint (within an eighth of a tile). On the donor's mesh the colours are
    the donor's own (frac_slab.Paint): the made top's are among those of the donor's faces up."""
    import frac_slab
    slab = twin_slab(recipe)
    slab['look'] = dict(mesh='(twin)', measure=VERSION, recipe=recipe)
    out = frac_slab.build(slab, template)
    boxes = [[b[0][0], b[1][0], b[0][1], b[1][1], b[0][2], b[1][2]] for b in out['solids']]
    m = out['mesh']
    # the built slab's lightmap: its rectangle as the Build gives it
    name = 'Twin_Roof' if recipe.get('role') == 'roof' else 'Twin_Floor'
    again = measure_mesh(m, name, dict(rect=list(out['lightmapRect'])), boxes)['recipe']
    rows = []

    def row(key, a, b, ok, soft=False):
        rows.append(dict(key=key, donor=a, twin=b, ok=bool(ok), soft=soft))
    size = recipe['measured']['size']
    built = [slab['x1'] - slab['x0'], slab['y1'] - slab['y0']]
    # (whole tiles within an eighth of a tile; a donor wider than a made slab can be is built at the most it can)
    row('footprint', size[:2], built, all(abs(a - TILE * round(a / TILE)) <= TILE / 8 for a in size[:2]))
    row('kind', recipe['kind'], again['kind'], recipe['kind'] == again['kind'])
    for key in ('bottom', 'top'):
        row(key, recipe[key], again[key], abs(recipe[key] - again[key]) <= 0.05)
    row('collision', recipe['collision'], again['collision'],
        all(abs(a - b) <= 0.05 for a, b in zip(recipe['collision'], again['collision'])))
    row('sections', recipe['sections'], again['sections'], recipe['sections'] == again['sections'])
    for key in ('top', 'underside', 'edge'):
        a, b = recipe['slots'][key], again['slots'][key]
        row('slot of the ' + key, a, b, a == b)
    row('inside faces', recipe['insideFaces'], again['insideFaces'], recipe['insideFaces'] == again['insideFaces'])
    for key in ('top', 'underside'):
        a, b = recipe['uv'][key], again['uv'][key]
        row('texture on the ' + key, a, b, not mc.map_differs(a, b))
    if template is None:
        row('colour', recipe['colours']['outside'], again['colours']['outside'],
            recipe['colours']['outside'] == again['colours']['outside'])
    else:
        # painted from the donor's own colours (frac_slab.Paint: its faces up, whatever their slot): the made top's
        # are among them
        lod, B = template['lods'][0], mc.Tris(m)
        theirs = ({bytes(c).hex() for c, v in zip(lod['colours'], lod['vertices']) if (v[1][2] - 127.5) / 127.5 > 0.7}
                  if lod.get('colours') else {recipe['colours']['outside']})
        ours = {B.colours[v].hex() for v in B.verts((B.slot == recipe['slots']['top']) & (B.normal[:, 2] >= UP))}
        row('colours', len(theirs), len(ours), ours <= theirs)
    da, db = recipe['lightmap']['density'], again['lightmap']['density']
    row('lightmap density', da, db, abs(db - da) <= 0.2 * da)
    pa, pb = recipe['measured']['perTile'], again['measured']['perTile']
    row('fragments a tile', pa, pb, pb <= 1.5 * pa and pa <= 1.5 * pb)
    ta = recipe['measured']['triangles'] / max(size[0] * size[1] / TILE ** 2, 1.0)
    tb = again['measured']['triangles'] / max(built[0] * built[1] / TILE ** 2, 1.0)
    row('triangles a tile', _round(ta), _round(tb), abs(tb - ta) <= 0.1 * ta, soft=True)
    return dict(ok=all(r['ok'] for r in rows if not r['soft']), rows=rows,
                built=dict((k, v) for k, v in slab.items() if k != 'look'))


def verdict(result):
    """A twin result in a catalogue's words: 'ok', or what differs ('kind pitched, made flat; ...')."""
    if result['ok']:
        return 'ok'
    return '; '.join('%s %s, made %s' % (r['key'], _words(r['donor']), _words(r['twin'])) for r in result['rows']
                     if not r['ok'] and not r['soft'])


def _words(v):
    if isinstance(v, float):
        return '%g' % v
    if isinstance(v, list) and v and isinstance(v[0], list):
        return 'another layout'
    if isinstance(v, list):
        return ' x '.join('%g' % x if isinstance(x, (int, float)) else str(x) for x in v)
    return str(v)

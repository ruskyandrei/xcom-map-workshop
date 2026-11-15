# Inventory of a cooked XCOM map's persistent level: every actor, with its place, mesh and the building it belongs to.
#
#   python tools/upk/map_inventory.py <map.upk> <out prefix> [--origin X Y] [--tile 96] [--floor 64]
#
# Writes <prefix>.tsv (one row per actor) and <prefix>-buildings.txt (each XComBuildingVolume: its box in world units
# and tiles, its floors with their floor volumes, and the actors whose centre is inside it, counted by class and mesh).
#
# Per actor: class, archetype, Location, Rotation (yaw), scale, mesh (own StaticMeshComponent, else the archetype's),
# the world box from the mesh bounds (or, for volumes and brushes, the brush model's bounds), bStatic/bHidden flags as
# saved, Layer, light radius and brightness, and the building volume holding its centre. A box is an approximation
# from bounds, not the game's own tile data. Building and floor volumes are read from their Floors and
# m_aInclusionActors/m_aExclusionActors arrays as well.
import sys, os, math, struct, argparse, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import upkinfo as U, props as P

ap = argparse.ArgumentParser()
ap.add_argument('map'); ap.add_argument('out')
ap.add_argument('--origin', nargs=2, type=float, default=[-2784.0, -1920.0])
ap.add_argument('--tile', type=float, default=96.0)
ap.add_argument('--floor', type=float, default=64.0)
a = ap.parse_args()

b, h = U.load(a.map); names, imps, exps = U.tables(b, h)
full = [U.objname(n + 1, imps, exps) for n in range(len(exps))]
cls = [U.clsname(e['cls'], imps, exps) for e in exps]
children = collections.defaultdict(list)
for n, e in enumerate(exps):
    if e['outer'] > 0: children[e['outer'] - 1].append(n)
name_to_idx = {f: n + 1 for n, f in enumerate(full)}


def nm_at(o):
    i, n = struct.unpack_from('<ii', b, o)
    s = names[i] if 0 <= i < len(names) else '?%d' % i
    return s if n == 0 else '%s_%d' % (s, n - 1)


def raw_props(off, end):
    """Tagged properties from off: {name: [(type, index, data offset, size, struct/enum name)]}, and the end offset."""
    d = collections.defaultdict(list)
    o = off
    while o + 8 <= end:
        pname = nm_at(o); o += 8
        if pname == 'None': break
        ptype = nm_at(o); o += 8
        size, idx = struct.unpack_from('<ii', b, o); o += 8
        sub = None
        if ptype == 'BoolProperty':
            d[pname].append((ptype, idx, o, 1, None)); o += 1; continue
        if ptype in ('StructProperty', 'ByteProperty'):
            sub = nm_at(o); o += 8
        d[pname].append((ptype, idx, o, size, sub)); o += size
    return d, o


def export_props(n):
    e = exps[n]
    try:
        return raw_props(P.props_start(b, e, names), e['off'] + e['size'])
    except Exception:
        return {}, None


def first(d, k):
    return d[k][0] if k in d and d[k] else None


def vec_of(d, k):
    p = first(d, k)
    if not p or p[3] != 12: return None
    return list(struct.unpack_from('<3f', b, p[2]))


def rot_of(d, k):
    p = first(d, k)
    if not p or p[3] != 12: return None
    return list(struct.unpack_from('<3i', b, p[2]))


def float_of(d, k, dflt=None):
    p = first(d, k)
    return struct.unpack_from('<f', b, p[2])[0] if p else dflt


def bool_of(d, k, dflt=None):
    p = first(d, k)
    return b[p[2]] != 0 if p else dflt


def obj_of(d, k):
    p = first(d, k)
    if not p: return None
    i = struct.unpack_from('<i', b, p[2])[0]
    return U.objname(i, imps, exps) if i else None


def name_of(d, k):
    p = first(d, k)
    return nm_at(p[2]) if p else None


def obj_array(d, k):
    p = first(d, k)
    if not p: return []
    cnt = struct.unpack_from('<i', b, p[2])[0]
    return [U.objname(struct.unpack_from('<i', b, p[2] + 4 + 4 * j)[0], imps, exps) for j in range(cnt)]


def struct_array(d, k):
    """Elements of an array of structs, each as a raw property dict."""
    p = first(d, k)
    if not p: return []
    cnt = struct.unpack_from('<i', b, p[2])[0]
    o = p[2] + 4; end = p[2] + p[3]; out = []
    for _ in range(cnt):
        e, o = raw_props(o, end); out.append(e)
    return out


bounds_cache = {}
def native_bounds(idx):
    """(origin, extent) from FBoxSphereBounds at the start of a StaticMesh's or Model's native data."""
    if idx in bounds_cache: return bounds_cache[idx]
    r = None
    if idx and idx > 0 and cls[idx - 1] in ('StaticMesh', 'FracturedStaticMesh', 'Model'):
        e = exps[idx - 1]
        try:
            _, endo = raw_props(P.props_start(b, e, names), e['off'] + e['size'])
            v = struct.unpack_from('<7f', b, endo)
            r = (v[0:3], v[3:6])
        except Exception:
            r = None
    bounds_cache[idx] = r
    return r


def mesh_of_component(n, depth=0):
    d, _ = export_props(n)
    m = obj_of(d, 'StaticMesh')
    if m: return name_to_idx.get(m)
    arch = exps[n]['arch']
    if depth < 6 and arch > 0 and cls[arch - 1].endswith('MeshComponent'):
        return mesh_of_component(arch - 1, depth + 1)
    return None


MESHCOMP = ('StaticMeshComponent', 'FracturedStaticMeshComponent', 'XComFracturedStaticMeshComponent',
            'InstancedStaticMeshComponent')
def actor_mesh(n, depth=0):
    for c in children[n]:
        if cls[c] in MESHCOMP:
            m = mesh_of_component(c)
            if m: return m
    arch = exps[n]['arch']
    if depth < 6 and arch > 0 and arch - 1 != n:
        return actor_mesh(arch - 1, depth + 1)
    return None


def light_of(n):
    """(radius, brightness, colour) of the actor's light component, if any."""
    for c in children[n]:
        if 'LightComponent' in cls[c]:
            d, _ = export_props(c)
            col = first(d, 'LightColor')
            colour = None
            if col and col[3] == 4:
                bb_, g_, r_, a_ = b[col[2]:col[2] + 4]; colour = '%d,%d,%d' % (r_, g_, bb_)
            return float_of(d, 'Radius'), float_of(d, 'Brightness', 1.0), colour, bool_of(d, 'bEnabled', True), \
                bool_of(d, 'CastDynamicShadows', None), cls[c]
    return None


level = 'TheWorld.PersistentLevel.'
T, ox, oy, FH = a.tile, a.origin[0], a.origin[1], a.floor
actors = {}
for n, f in enumerate(full):
    if not f.startswith(level) or f.count('.') != 2: continue
    c = cls[n]
    d, _ = export_props(n)
    loc = vec_of(d, 'Location')
    if loc is None: continue
    rot = rot_of(d, 'Rotation') or [0, 0, 0]
    yaw = rot[1] * 2 * math.pi / 65536
    sc = vec_of(d, 'DrawScale3D') or [1.0, 1.0, 1.0]
    ds = float_of(d, 'DrawScale', 1.0)
    sc = [s * ds for s in sc]
    brush = obj_of(d, 'Brush')
    mi = name_to_idx.get(brush) if brush else actor_mesh(n)
    bb = native_bounds(mi) if mi else None
    box = None
    if bb:
        bo, be = bb
        cs, sn = math.cos(yaw), math.sin(yaw)
        xs, ys = [], []
        for sx in (-1, 1):
            for sy in (-1, 1):
                lx = (bo[0] + sx * be[0]) * sc[0]; ly = (bo[1] + sy * be[1]) * sc[1]
                xs.append(loc[0] + lx * cs - ly * sn); ys.append(loc[1] + lx * sn + ly * cs)
        z0 = loc[2] + (bo[2] - be[2]) * sc[2]; z1 = loc[2] + (bo[2] + be[2]) * sc[2]
        box = (min(xs), max(xs), min(ys), max(ys), min(z0, z1), max(z0, z1))
    arch = exps[n]['arch']
    actors[f.split('.')[-1]] = dict(
        n=n, cls=c, arch=full[arch - 1] if arch > 0 else '', loc=loc, yaw=math.degrees(yaw), sc=sc,
        mesh=(full[mi - 1] if mi and not brush else ''), box=box, d=d,
        hidden=bool_of(d, 'bHidden'), layer=name_of(d, 'Layer') or '', light=light_of(n))


def tiles(box):
    x0, x1, y0, y1, z0, z1 = box
    return (math.floor((x0 - ox) / T + 1e-3), math.ceil((x1 - ox) / T - 1e-3) - 1,
            math.floor((y0 - oy) / T + 1e-3), math.ceil((y1 - oy) / T - 1e-3) - 1,
            math.floor(z0 / FH + 1e-3), math.ceil(z1 / FH - 1e-3) - 1)


def inside(p, box, pad=0.0):
    return box[0] - pad <= p[0] <= box[1] + pad and box[2] - pad <= p[1] <= box[3] + pad and box[4] - pad <= p[2] <= box[5] + pad


def centre(A):
    if A['box']:
        x0, x1, y0, y1, z0, z1 = A['box']; return ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    return A['loc']


buildings = {k: A for k, A in actors.items() if A['cls'] == 'XComBuildingVolume' and A['box']}
for k, A in actors.items():
    A['building'] = ''
    if A['cls'] in ('XComBuildingVolume',): continue
    c = centre(A)
    best = None
    for bk, B in buildings.items():
        if inside(c, B['box'], 8.0):
            vol = (B['box'][1] - B['box'][0]) * (B['box'][3] - B['box'][2])
            if best is None or vol < best[0]: best = (vol, bk)
    if best: A['building'] = best[1]

with open(a.out + '.tsv', 'w') as f:
    f.write('name\tclass\tarchetype\tmesh\tbuilding\tx\ty\tz\tyaw\tscale\tbox x\tbox y\tbox z\ttiles x\ttiles y\tlevels\thidden\tlayer\tlight\n')
    for k in sorted(actors, key=lambda k: (actors[k]['cls'], k)):
        A = actors[k]
        bx = A['box']
        t = tiles(bx) if bx else None
        lt = A['light']
        f.write('\t'.join([k, A['cls'], A['arch'], A['mesh'], A['building'],
                           '%.0f' % A['loc'][0], '%.0f' % A['loc'][1], '%.0f' % A['loc'][2], '%.0f' % A['yaw'],
                           ','.join('%g' % s for s in A['sc']),
                           ('%.0f..%.0f' % bx[0:2]) if bx else '', ('%.0f..%.0f' % bx[2:4]) if bx else '',
                           ('%.0f..%.0f' % bx[4:6]) if bx else '',
                           ('%d..%d' % t[0:2]) if t else '', ('%d..%d' % t[2:4]) if t else '', ('%d..%d' % t[4:6]) if t else '',
                           '' if A['hidden'] is None else str(int(A['hidden'])), A['layer'],
                           ('%s r=%s b=%.2f c=%s%s' % (lt[5], ('%.0f' % lt[0]) if lt[0] else '-', lt[1] or 0, lt[2], '' if lt[3] else ' off')) if lt else '']) + '\n')

with open(a.out + '-buildings.txt', 'w') as f:
    for bk in sorted(buildings):
        B = buildings[bk]; bx = B['box']; t = tiles(bx)
        f.write('%s  x %.0f..%.0f  y %.0f..%.0f  z %.0f..%.0f   tiles x %d..%d  y %d..%d  levels %d..%d (%d x %d tiles)\n' % (
            (bk,) + bx + t + (t[1] - t[0] + 1, t[3] - t[2] + 1)))
        d = B['d']
        for fl in ('IsInside', 'IsUfo', 'IsDropShip', 'm_bAllowBuildingReveal', 'm_bIsInternalBuilding'):
            v = bool_of(d, fl)
            if v is not None: f.write('  %s = %d\n' % (fl, v))
        for i, F in enumerate(struct_array(d, 'Floors')):
            fv = [x.split('.')[-1] for x in obj_array(F, 'FloorVolumes')]
            groups = []
            p = first(F, 'ExternalMeshGroupNames')
            if p:
                cnt = struct.unpack_from('<i', b, p[2])[0]; o = p[2] + 4
                for _ in range(cnt):
                    rr = U.R(b, o); groups.append(rr.fstr()); o = rr.o
            f.write('  floor %d: volumes %s%s\n' % (i, ', '.join(fv) or '-', ('  groups ' + ', '.join(groups)) if groups else ''))
            for v in fv:
                V = actors.get(v)
                if not V: continue
                vd = V['d']
                vt = tiles(V['box']) if V['box'] else None
                f.write('    %s FloorNumber %s type %s  z %s  tiles %s%s%s\n' % (
                    v, struct.unpack_from('<i', b, first(vd, 'FloorNumber')[2])[0] if first(vd, 'FloorNumber') else 0,
                    nm_at(first(vd, 'm_FloorVolumeType')[2]) if first(vd, 'm_FloorVolumeType') and first(vd, 'm_FloorVolumeType')[3] == 8 else '-',
                    ('%.0f..%.0f' % V['box'][4:6]) if V['box'] else '?',
                    ('x %d..%d y %d..%d' % vt[0:4]) if vt else '?',
                    ('  include ' + ' '.join(x.split('.')[-1] for x in obj_array(vd, 'm_aInclusionActors'))) if obj_array(vd, 'm_aInclusionActors') else '',
                    ('  exclude ' + ' '.join(x.split('.')[-1] for x in obj_array(vd, 'm_aExclusionActors'))) if obj_array(vd, 'm_aExclusionActors') else ''))
        for i, G in enumerate(struct_array(d, 'ExternalMeshGroups')):
            p = first(G, 'GroupName'); gn = U.R(b, p[2]).fstr() if p else ''
            f.write('  external group %r: %s\n' % (gn, ' '.join(x.split('.')[-1] for x in obj_array(G, 'm_aActors'))))
        members = [A for A in actors.values() if A['building'] == bk]
        byc = collections.Counter(A['cls'] for A in members)
        f.write('  actors inside: %d  (%s)\n' % (len(members), ', '.join('%s %d' % kv for kv in byc.most_common())))
        bym = collections.Counter((A['cls'], A['mesh'] or A['arch']) for A in members if A['cls'] not in ('XComFloorVolume',))
        for (c, m), cnt in sorted(bym.items(), key=lambda kv: (-kv[1], kv[0])):
            f.write('    %3d  %-28s %s\n' % (cnt, c, m))
        f.write('\n')
print('%d actors, %d building volumes; wrote %s.tsv and %s-buildings.txt' % (len(actors), len(buildings), a.out, a.out))

# Ground-level layout of a cooked XCOM map: which tiles hold something solid at standing height.
#
#   python tools/upk/map_layout.py <map.upk> <out prefix> [--origin X Y] [--tile 96] [--ground Z]
#
# For every actor in the persistent level it takes Location, Rotation (yaw), DrawScale/DrawScale3D and the static mesh
# (its own StaticMeshComponent, else the archetype's), reads the mesh's bounds from its native data, and marks the
# tiles its rotated box covers where the box spans standing height (ground + 20 .. ground + 150). Flat floors,
# overhead parts, volumes, lights and effects are skipped. Writes <prefix>.png (10 px per tile, labels every 10
# tiles), <prefix>.txt (ASCII, '#' solid, '.' free, ' ' outside everything) and <prefix>-actors.tsv.
# This is an approximation from bounding boxes, not the game's own tile data.
import sys, os, math, struct, argparse, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import upkinfo as U, props as P

ap = argparse.ArgumentParser()
ap.add_argument('map'); ap.add_argument('out')
ap.add_argument('--origin', nargs=2, type=float, default=[-2784.0, -1920.0])
ap.add_argument('--tile', type=float, default=96.0)
ap.add_argument('--ground', type=float, default=0.0)
ap.add_argument('--window', nargs=4, type=int, metavar=('TX0', 'TX1', 'TY0', 'TY1'),
                help='only draw these tiles (backdrop meshes far outside the play area stretch the map otherwise)')
a = ap.parse_args()

b, h = U.load(a.map); names, imps, exps = U.tables(b, h)
full = [U.objname(n + 1, imps, exps) for n in range(len(exps))]
cls = [U.clsname(e['cls'], imps, exps) for e in exps]
children = collections.defaultdict(list)
for n, e in enumerate(exps):
    if e['outer'] > 0: children[e['outer'] - 1].append(n)

def props(n):
    e = exps[n]
    try:
        lines, _ = P.read_props(b, P.props_start(b, e, names), e['off'] + e['size'], names, imps, exps)
    except Exception:
        return {}
    d = {}
    for l in lines:
        k, _, v = l.strip().partition(' = ')
        d[k.split('[')[0]] = (k, v)
    return d

bounds_cache = {}
def mesh_bounds(idx):
    """(origin, extent) of a StaticMesh export, from FBoxSphereBounds at the start of its native data."""
    if idx in bounds_cache: return bounds_cache[idx]
    r = None
    if idx > 0 and cls[idx - 1] in ('StaticMesh', 'FracturedStaticMesh'):
        e = exps[idx - 1]
        try:
            _, endo = P.read_props(b, P.props_start(b, e, names), e['off'] + e['size'], names, imps, exps)
            v = struct.unpack_from('<7f', b, endo)
            r = (v[0:3], v[3:6])
        except Exception:
            r = None
    bounds_cache[idx] = r
    return r

name_to_idx = {f: n + 1 for n, f in enumerate(full)}
def mesh_of_component(n):
    d = props(n)
    if 'StaticMesh' in d:
        return name_to_idx.get(d['StaticMesh'][1])
    arch = exps[n]['arch']
    if arch > 0 and cls[arch - 1].endswith('MeshComponent'):
        return mesh_of_component(arch - 1)
    return None

def actor_mesh(n):
    for c in children[n]:
        if cls[c] in ('StaticMeshComponent', 'FracturedStaticMeshComponent', 'XComFracturedStaticMeshComponent'):
            m = mesh_of_component(c)
            if m: return m
    arch = exps[n]['arch']
    if arch > 0 and arch - 1 != n:
        return actor_mesh(arch - 1)
    return None

def vec(s):
    s = s[s.index('(') + 1:s.rindex(')')]
    return [float(x) for x in s.split(',')]

SKIP = ('Volume', 'Light', 'Emitter', 'Decal', 'Note', 'PlayerStart', 'SpawnPoint', 'PathNode', 'Brush', 'Info',
        'Sound', 'Camera', 'Trigger', 'Sequence', 'PointInSpace', 'Prefab', 'Pylon', 'Fog', 'Matinee', 'Cover')
level = 'TheWorld.PersistentLevel.'
actors = []
for n, f in enumerate(full):
    if not f.startswith(level) or f.count('.') != 2: continue
    c = cls[n]
    if any(s in c for s in SKIP): continue
    d = props(n)
    if 'Location' not in d: continue
    if d.get('bHidden', ('', '0'))[1] == '1': continue
    m = actor_mesh(n)
    if not m: continue
    bb = mesh_bounds(m)
    if not bb: continue
    loc = vec(d['Location'][1])
    yaw = 0.0
    if 'Rotation' in d: yaw = vec(d['Rotation'][1])[1] * 2 * math.pi / 65536
    sc = [1.0, 1.0, 1.0]
    if 'DrawScale3D' in d: sc = vec(d['DrawScale3D'][1])
    ds = float(d['DrawScale'][1]) if 'DrawScale' in d else 1.0
    sc = [s * ds for s in sc]
    actors.append((f.split('.')[-1], c, full[m - 1], loc, yaw, sc, bb))

T, ox, oy, g = a.tile, a.origin[0], a.origin[1], a.ground
solid = set(); seen = set(); rows = []
for (nm, c, mesh, loc, yaw, sc, (bo, be)) in actors:
    zmin = loc[2] + (bo[2] - be[2]) * sc[2]; zmax = loc[2] + (bo[2] + be[2]) * sc[2]
    cs, sn = math.cos(yaw), math.sin(yaw)
    corners = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            lx = (bo[0] + sx * be[0]) * sc[0]; ly = (bo[1] + sy * be[1]) * sc[1]
            corners.append((loc[0] + lx * cs - ly * sn, loc[1] + lx * sn + ly * cs))
    x0 = min(p[0] for p in corners); x1 = max(p[0] for p in corners)
    y0 = min(p[1] for p in corners); y1 = max(p[1] for p in corners)
    standing = zmax > g + 20 and zmin < g + 150
    flat = zmax <= g + 20
    tiles = [(tx, ty) for tx in range(math.floor((x0 - ox) / T), math.ceil((x1 - ox) / T))
                      for ty in range(math.floor((y0 - oy) / T), math.ceil((y1 - oy) / T))]
    if len(tiles) > 4000: standing = False   # huge pieces (whole buildings' shells, skyboxes) are not useful here
    for t in tiles:
        if standing: solid.add(t)
        elif flat or zmin < g + 150: seen.add(t)
    rows.append('%s\t%s\t%s\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f..%.0f\t%.0f..%.0f\t%.0f..%.0f\t%s' % (
        nm, c, mesh, loc[0], loc[1], loc[2], math.degrees(yaw), x0, x1, y0, y1, zmin, zmax, 'solid' if standing else ''))

allt = solid | seen
if a.window:
    tx0, tx1, ty0, ty1 = a.window
    allt = {t for t in allt if tx0 <= t[0] <= tx1 and ty0 <= t[1] <= ty1}
else:
    tx0 = min(t[0] for t in allt); tx1 = max(t[0] for t in allt); ty0 = min(t[1] for t in allt); ty1 = max(t[1] for t in allt)
with open(a.out + '.txt', 'w') as f:
    f.write('tiles x %d..%d (columns), y %d..%d (rows); tile (tx, ty) spans x %g+%g*tx.., y %g+%g*ty..\n' % (tx0, tx1, ty0, ty1, ox, T, oy, T))
    f.write('     ' + ''.join(str((tx // 10) % 10) if tx % 10 == 0 else ' ' for tx in range(tx0, tx1 + 1)) + '\n')
    for ty in range(ty0, ty1 + 1):
        f.write('%4d ' % ty + ''.join('#' if (tx, ty) in solid else '.' if (tx, ty) in seen else ' ' for tx in range(tx0, tx1 + 1)) + '\n')
with open(a.out + '-actors.tsv', 'w') as f:
    f.write('name\tclass\tmesh\tx\ty\tz\tyaw\tx range\ty range\tz range\tstanding\n' + '\n'.join(rows) + '\n')
try:
    from PIL import Image, ImageDraw
    px = 10
    W, H = (tx1 - tx0 + 1) * px, (ty1 - ty0 + 1) * px
    im = Image.new('RGB', (W + 40, H + 40), (255, 255, 255)); dr = ImageDraw.Draw(im)
    for (tx, ty) in allt:
        x, y = 40 + (tx - tx0) * px, 40 + (ty - ty0) * px
        dr.rectangle([x, y, x + px - 1, y + px - 1], fill=(60, 60, 70) if (tx, ty) in solid else (215, 220, 205))
    for tx in range(tx0, tx1 + 1):
        if tx % 10 == 0:
            x = 40 + (tx - tx0) * px; dr.line([x, 40, x, H + 40], fill=(230, 80, 80)); dr.text((x + 2, 2), str(tx), fill=(200, 0, 0))
    for ty in range(ty0, ty1 + 1):
        if ty % 10 == 0:
            y = 40 + (ty - ty0) * px; dr.line([40, y, W + 40, y], fill=(230, 80, 80)); dr.text((2, y + 2), str(ty), fill=(200, 0, 0))
    im.save(a.out + '.png')
except ImportError:
    pass
print('%d actors with meshes, %d solid tiles, %d other tiles; tiles x %d..%d, y %d..%d; wrote %s.png/.txt/-actors.tsv'
      % (len(actors), len(solid), len(seen), tx0, tx1, ty0, ty1, a.out))

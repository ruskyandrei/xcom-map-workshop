"""A research tool (not shipped): stage D5 of the game-likeness plan, what of a level's drawn geometry the map's export
does not read, over the install. The export draws each mesh component of the level's actors once, at the component's
place (export.py `Exporter.component`); three kinds of geometry would be missed by it:

- BSP: the level's model, which the game draws through the level's model components (each element a material and the
  BSP nodes it draws). A node whose surface is invisible or a portal draws nothing.
- Terrain (and Landscape, and the other world-geometry classes of the engine: SpeedTree, foliage, spline meshes,
  fluid surfaces), none of which is a mesh component the export reads.
- Instanced meshes: a component that draws one mesh at many places (its per-instance transforms). The export reads
  such a component as one mesh at the component's own place. Enemy Within's toggled kind (a fracturing wall's
  decoration and debris, `ToggleableInstancedStaticMeshComponent`) draws only the instances whose entry in
  `PerInstanceBitfield` holds the class's `INSTANCE_Visibility` bit, unless its wall says to show them all
  (`bForceDecoVisible`, `bForceDebrisVisible`); the game sets the bit as the wall's fragments break.

  python -B tools/upk/audit_world_geometry.py survey [--game <folder>] [--maps <map> ...] [--output <json>]
      every map the install's records name and each package its records stream (the export's streams), each with its
      BSP, terrain and instanced meshes, and the totals; with what of each the game draws as the level loads
  python -B tools/upk/audit_world_geometry.py package <package file>
      one package's record, printed

The readers below follow the engine's layouts as this install saves them: a model's (native_fields._model walks the
same layout for its references), a model component's (its model, its zone, its elements, each a lightmap, its
component, its material, its nodes, its shadow maps and irrelevant lights; then its index and nodes) and an instanced
mesh component's (a mesh component's LOD records, then its instances: a bulk array of 80-byte records, a 4x4
transform and the lightmap's and shadow map's UV biases). Each read is bounded by its export and must end on its
last byte. Read only: the install is never written. --game defaults to the configured LWR install (labpaths).
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
for folder in ('viewer', 'lab', 'bake'):
    sys.path.insert(0, str(TOOLS / folder))
sys.path.insert(0, str(HERE))
import native_fields  # noqa: E402
from package import Package, FormatError, Reader  # noqa: E402

AUDIT_VERSION = 1
LEVEL = 'TheWorld.PersistentLevel.'
# EPolyFlags of a BSP surface that draw nothing: an invisible surface and a portal
PF_INVISIBLE, PF_PORTAL = 0x00000001, 0x04000000
NODE_SIZE, VERT_SIZE, INSTANCE_SIZE = 64, 24, 80
# a BSP node (FBspNode, 64 bytes): its plane (16), the first of its vertices in the model's vertex pool, its surface,
# ..., and its vertex count as the byte at 54
NODE_VERT_POOL, NODE_SURF, NODE_COMPONENT, NODE_VERTICES = 16, 20, 28, 54
TERRAIN_WORDS = ('Terrain', 'Landscape')
OTHER_GEOMETRY = ('SpeedTreeComponent', 'FoliageComponent', 'InteractiveFoliageComponent', 'SplineMeshComponent',
                  'FluidSurfaceComponent', 'InstancedFoliageActor')
INSTANCED = 'InstancedStaticMeshComponent'
TOGGLED = 'ToggleableInstancedStaticMeshComponent'
UNREADABLE = (FormatError, native_fields.NativeError, ValueError, IndexError, KeyError, struct.error, OSError)


class GeometryError(ValueError):
    """Native data that doesn't read as its layout."""


def _ref(r, p):
    value = r.i32()
    try:
        p.name(value)
    except FormatError:
        raise GeometryError('no object %d at %d' % (value, r.pos - 4)) from None
    return value


def _count(r, size, what):
    n = r.count()
    if n < 0 or n * size > r.end - r.pos:
        raise GeometryError('%d %s of %d bytes past the export' % (n, what, size))
    return n


def _sized(r, size, what):
    """A bulk-serialized array: its element size (which must be `size`), then a counted array: the bytes."""
    got = r.i32()
    if got != size:
        raise GeometryError('%s of %d bytes, not %d' % (what, got, size))
    return r.take(size * _count(r, size, what))


def model_values(p, index):
    """A UModel's geometry: dict(nodes [dict(surf, vertPool, vertices, component)], surfaces [dict(material, flags,
    actor)], verts [the point index of each], points [(x, y, z)]). The rest of the layout is passed over."""
    r = p.native(index)
    r.take(28)                                  # bounds
    _sized(r, 12, 'vectors')
    raw_points = _sized(r, 12, 'points')
    raw_nodes = _sized(r, NODE_SIZE, 'nodes')
    _ref(r, p)                                  # owner
    surfaces = []
    for _ in range(_count(r, 60, 'surfaces')):
        material = _ref(r, p)
        flags = r.u32()
        r.take(20)                              # base, normal, texture U and V, the brush polygon
        actor = _ref(r, p)
        r.take(28)                              # plane, shadow map scale, lighting channels, Lightmass index
        surfaces.append(dict(material=material, flags=flags, actor=actor))
    raw_verts = _sized(r, VERT_SIZE, 'vertices')
    nodes = []
    for k in range(0, len(raw_nodes), NODE_SIZE):
        pool, surf = struct.unpack_from('<ii', raw_nodes, k + NODE_VERT_POOL)
        component = struct.unpack_from('<H', raw_nodes, k + NODE_COMPONENT)[0]
        nodes.append(dict(surf=surf, vertPool=pool, vertices=raw_nodes[k + NODE_VERTICES], component=component))
    verts = [struct.unpack_from('<i', raw_verts, k)[0] for k in range(0, len(raw_verts), VERT_SIZE)]
    points = [struct.unpack_from('<3f', raw_points, k) for k in range(0, len(raw_points), 12)]
    for n in nodes:
        if not (0 <= n['surf'] < len(surfaces) and 0 <= n['vertPool'] <= n['vertPool'] + n['vertices'] <= len(verts)):
            raise GeometryError('a node outside the model: surface %d of %d, vertices %d+%d of %d'
                                % (n['surf'], len(surfaces), n['vertPool'], n['vertices'], len(verts)))
    if any(not 0 <= v < len(points) for v in verts):
        raise GeometryError('a vertex names no point')
    return dict(nodes=nodes, surfaces=surfaces, verts=verts, points=points)


def _words(r, what):
    n = _count(r, 2, what)
    return list(r.unpack('%dH' % n)) if n else []


def model_component(p, index):
    """A UModelComponent's native data: dict(model, zone, elements [dict(lightmap (its type), component, material,
    nodes, shadowMaps, irrelevantLights)], componentIndex, nodes)."""
    r = p.native(index)
    out = dict(model=_ref(r, p), zone=r.i32(), elements=[])
    for _ in range(_count(r, 20, 'elements')):
        lightmap = native_fields.lightmap_record(r, p)['type']
        element = dict(lightmap=lightmap, component=_ref(r, p), material=_ref(r, p), nodes=_words(r, 'nodes'))
        element['shadowMaps'] = [_ref(r, p) for _ in range(_count(r, 4, 'shadow maps'))]
        element['irrelevantLights'] = len([r.take(16) for _ in range(_count(r, 16, 'irrelevant lights'))])
        out['elements'].append(element)
    out['componentIndex'] = r.unpack('H')[0]
    out['nodes'] = _words(r, 'nodes')
    if r.pos != r.end:
        raise GeometryError('%d bytes after a model component' % (r.end - r.pos))
    return out


def instances(p, index):
    """An instanced static mesh component's instances: [dict(matrix (16 numbers, rows), lightmapBias, shadowBias)],
    after the mesh component's LOD records (native_fields.mesh_lods)."""
    r = p.native(index)
    native_fields.mesh_lods(r, p)
    raw = _sized(r, INSTANCE_SIZE, 'instances')
    if r.pos != r.end:
        raise GeometryError('%d bytes after the instances' % (r.end - r.pos))
    out = []
    for k in range(0, len(raw), INSTANCE_SIZE):
        values = struct.unpack_from('<20f', raw, k)
        out.append(dict(matrix=list(values[:16]), lightmapBias=list(values[16:18]), shadowBias=list(values[18:20])))
    return out


# ---------------------------------------------------------------------------------------------------------------
# The classes, from the game's script packages

class Classes:
    """Each component class's chain of super classes, read from XComGame.upk and Engine.upk of the cooked folder (the
    export table's super index), and the toggled kind's visibility bit (the class constant's text)."""

    def __init__(self, cooked):
        self.packages = [Package(Path(cooked) / name) for name in ('XComGame.upk', 'Engine.upk')
                         if (Path(cooked) / name).exists()]
        self.chains = {}
        self.visibility = self.constant(TOGGLED + '.INSTANCE_Visibility')

    def chain(self, name):
        """[the class, its super, ...] by name, as far as the script packages say (an import ends it)."""
        if name not in self.chains:
            out = [name]
            for q in self.packages:
                i = q.by_name.get(name)
                if i and q.cls(i) == 'Class':
                    while True:
                        sup = q.exports[i - 1]['sup']
                        if not sup:
                            break
                        out.append(q.name(sup).rsplit('.', 1)[-1])
                        if sup < 0:
                            out.extend(c for c in self.chain(out[-1])[1:] if c not in out)
                            break
                        i = sup
                    break
            self.chains[name] = out
        return self.chains[name]

    def constant(self, path):
        """A script constant's value as a number (its text, after the field's next pointer: 0x... or decimal)."""
        for q in self.packages:
            i = q.by_name.get(path)
            if i:
                r = q.native(i)
                r.take(4)
                size = r.i32()
                text = bytes(r.take(size)).rstrip(b'\0').decode('latin-1')
                return int(text, 0)
        return None

    def instanced(self, name):
        return INSTANCED in self.chain(name)

    def toggled(self, name):
        return TOGGLED in self.chain(name)


# ---------------------------------------------------------------------------------------------------------------
# A package's record

def _bitfield(p, index):
    raw = p.effective(index, 'PerInstanceBitfield')
    if raw is None:
        return []
    n = struct.unpack_from('<i', raw)[0]
    if len(raw) != 4 + 4 * n:
        raise GeometryError('a bitfield of %d bytes for %d entries' % (len(raw), n))
    return list(struct.unpack_from('<%di' % n, raw, 4))


def visible_fragments(p, component, count):
    """A fracturing mesh component's fragments as the map saves them: [bool] (EditorPaintedVisibleFragments, one int
    or one byte a fragment; all visible where it saves none)."""
    raw = p.effective(component, 'EditorPaintedVisibleFragments')
    if raw is None:
        return [True] * count
    n = struct.unpack_from('<i', raw)[0]
    if len(raw) == 4 + n:
        return [bool(v) for v in raw[4:]]
    if len(raw) == 4 + 4 * n:
        return [bool(v) for v in struct.unpack_from('<%di' % n, raw, 4)]
    raise GeometryError('a fragment mask of %d bytes for %d fragments' % (len(raw), n))


def fragment_rule(p, index, bits, visibility, debris, kept):
    """Each entry of a toggled component's bitfield (its low 16 bits the fragment it belongs to, the visibility bit
    whether it is drawn) against a rule read from the data: a decoration chunk is drawn where its fragment is there
    and a fragment across one of its faces is not (a broken edge); a debris pile where its fragment is gone. Counts
    of 'saved/rule' pairs (True or False), and 'out of range' for a fragment the mesh doesn't have. `kept`: the
    fracturing meshes' fragments read so far, by export."""
    import gen_mesh
    fsmc = p.own(index, 'm_FracturedStaticMeshComponent', 0)
    mesh = p.effective(fsmc, 'StaticMesh', 0) if fsmc > 0 else 0
    if mesh <= 0:
        return dict(unread='its wall\'s mesh is not in the package')
    if mesh not in kept:
        kept[mesh] = gen_mesh.read(p, mesh)['fractured']['fragments']
    frags = kept[mesh]
    there = visible_fragments(p, fsmc, len(frags))
    out = Counter()
    for b in bits:
        uid, saved = b & 0xFFFF, bool(b & visibility)
        if uid >= len(frags) or len(there) != len(frags):
            out['out of range'] += 1
            continue
        if debris:
            guess = not there[uid]
        else:
            guess = there[uid] and any(k >= 0 and not there[k] for k in frags[uid]['neighbours'])
        out['%s/%s' % (saved, guess)] += 1
    return dict(out)


def bsp(p):
    """The level's BSP as the game draws it: its model components' elements and the nodes they draw."""
    comps = [i for i in range(1, len(p.exports) + 1) if p.cls(i) == 'ModelComponent' and p.paths[i - 1].startswith(LEVEL)
             and 'Default__' not in p.paths[i - 1]]
    models = [i for i in range(1, len(p.exports) + 1) if p.cls(i) == 'Model' and p.paths[i - 1].startswith(LEVEL)
              and p.paths[i - 1].count('.') == 2]
    out = dict(models=len(models), modelNodes=0, modelSurfaces=0, components=len(comps), elements=0, elementNodes=0,
               drawnNodes=0, drawnTriangles=0, materials=Counter(), flags=Counter(), box=None, problems=[])
    values = {}
    for m in models:
        try:
            values[m] = model_values(p, m)
            out['modelNodes'] += len(values[m]['nodes'])
            out['modelSurfaces'] += len(values[m]['surfaces'])
        except UNREADABLE as error:
            out['problems'].append('%s: %s' % (p.paths[m - 1], error))
    lo, hi = [float('inf')] * 3, [float('-inf')] * 3
    for c in comps:
        try:
            mc = model_component(p, c)
        except UNREADABLE as error:
            out['problems'].append('%s: %s' % (p.paths[c - 1], error))
            continue
        model = values.get(mc['model'])
        for e in mc['elements']:
            out['elements'] += 1
            out['elementNodes'] += len(e['nodes'])
            if model is None:
                out['problems'].append('%s: its model %s not read' % (p.paths[c - 1], p.name(mc['model'])))
                continue
            for k in e['nodes']:
                if not 0 <= k < len(model['nodes']):
                    out['problems'].append('%s: node %d of %d' % (p.paths[c - 1], k, len(model['nodes'])))
                    continue
                node = model['nodes'][k]
                surf = model['surfaces'][node['surf']]
                out['flags']['0x%08x' % surf['flags']] += 1
                if surf['flags'] & (PF_INVISIBLE | PF_PORTAL) or node['vertices'] < 3:
                    continue
                out['drawnNodes'] += 1
                out['drawnTriangles'] += node['vertices'] - 2
                out['materials'][p.name(e['material'])] += 1
                for v in model['verts'][node['vertPool']:node['vertPool'] + node['vertices']]:
                    point = model['points'][v]
                    lo = [min(a, b) for a, b in zip(lo, point)]
                    hi = [max(a, b) for a, b in zip(hi, point)]
    if out['drawnNodes']:
        out['box'] = dict(min=[round(v, 1) for v in lo], max=[round(v, 1) for v in hi])
    out['materials'] = dict(out['materials'])
    out['flags'] = dict(out['flags'])
    return out


def instanced(p, classes):
    """Every instanced mesh component of the level's actors (its class's chain reaches InstancedStaticMeshComponent),
    with its instances and how many of them the game draws as the level loads. A toggled one's `rule` sets each
    entry's saved bit against fragment_rule's guess."""
    out, fragments = [], {}
    for i in range(1, len(p.exports) + 1):
        path = p.paths[i - 1]
        if not path.startswith(LEVEL) or 'Default__' in path or not classes.instanced(p.cls(i)):
            continue
        owner = p.exports[i - 1]['outer']
        mesh = p.effective(i, 'StaticMesh', 0)
        row = dict(component=path, cls=p.cls(i), owner=p.cls(owner) if owner > 0 else None,
                   archetype=p.name(p.exports[i - 1]['arch']).rsplit('.', 1)[-1],
                   mesh=p.name(mesh) if mesh else None, hidden=bool(p.effective(i, 'HiddenGame', False)))
        try:
            row['instances'] = len(instances(p, i))
        except UNREADABLE as error:
            row['instances'], row['problem'] = None, str(error)
            out.append(row)
            continue
        if classes.toggled(p.cls(i)):
            bits = _bitfield(p, i)
            parent = p.own(i, 'm_DecoFracParent', 0)
            debris = 'Debris' in p.cls(i)
            force = 'bForceDebrisVisible' if debris else 'bForceDecoVisible'
            row.update(entries=len(bits), shownBits=sum(1 for b in bits if b & (classes.visibility or 0)),
                       forced=bool(parent > 0 and p.effective(parent, force, False)),
                       enabled=bool(parent <= 0 or p.effective(parent, 'bEnableDebrisMeshes' if debris
                                                               else 'bEnableDecoMeshes', True)))
            try:
                row['rule'] = fragment_rule(p, i, bits, classes.visibility, debris, fragments)
            except UNREADABLE as error:
                row['rule'] = dict(unread=str(error))
            shown = row['instances'] if row['forced'] else min(row['shownBits'], row['instances'])
        else:
            shown = row['instances']
        row['drawnAtLoad'] = 0 if row['hidden'] or not row['mesh'] or not row.get('enabled', True) else shown
        out.append(row)
    return out


def package_record(path, classes):
    p = Package(path)
    rec = dict(package=Path(path).stem, bsp=bsp(p), instanced=instanced(p, classes), terrain={}, otherGeometry={})
    for i in range(1, len(p.exports) + 1):
        if not p.paths[i - 1].startswith('TheWorld.') or 'Default__' in p.paths[i - 1]:
            continue
        cls = p.cls(i)
        if any(w in cls for w in TERRAIN_WORDS):
            rec['terrain'][cls] = rec['terrain'].get(cls, 0) + 1
        if any(c in classes.chain(cls) for c in OTHER_GEOMETRY):
            rec['otherGeometry'][cls] = rec['otherGeometry'].get(cls, 0) + 1
    return rec


# ---------------------------------------------------------------------------------------------------------------
# The survey

def packages(game, names=None):
    """{stem: path}: each map the install's records name (or `names`) and each package its records stream."""
    import export
    import maplist
    found = maplist.lwr_maps(game)
    out = {}
    for name, entry in sorted(found.items()):
        if names and name not in names or not entry['package']:
            continue
        out.setdefault(entry['package'].stem, dict(path=entry['package'], role='map', maps=[]))['maps'].append(name)
        for record in export.map_records(entry['package']):
            for stream in record['streams']:
                spath = export.stream_package(entry['package'], stream)
                if spath:
                    out.setdefault(spath.stem, dict(path=spath, role='stream', maps=[]))
                    if name not in out[spath.stem]['maps']:
                        out[spath.stem]['maps'].append(name)
    return out


def summarise(records):
    totals = Counter()
    for rec in records:
        b = rec['bsp']
        totals['packages'] += 1
        totals['bsp components'] += b['components']
        totals['bsp drawn nodes'] += b['drawnNodes']
        totals['packages with drawn bsp'] += bool(b['drawnNodes'])
        totals['terrain objects'] += sum(rec['terrain'].values())
        totals['other geometry objects'] += sum(rec['otherGeometry'].values())
        for row in rec['instanced']:
            totals['instanced components'] += 1
            totals['instances'] += row['instances'] or 0
            totals['instanced components with more than one instance'] += (row['instances'] or 0) > 1
            totals['instances drawn at load'] += row.get('drawnAtLoad') or 0
            totals['instanced components unread'] += row['instances'] is None
    kinds = {}
    for rec in records:
        for row in rec['instanced']:
            key = '%s on %s (%s)' % (row['cls'], row['owner'], row['archetype'] if row['cls'] == INSTANCED else 'placed')
            k = kinds.setdefault(key, Counter())
            k['components'] += 1
            k['instances'] += row['instances'] or 0
            k['with a mesh'] += bool(row['mesh'])
            k['hidden'] += row['hidden']
            k['drawn at load'] += row.get('drawnAtLoad') or 0
            k['shown bits'] += row.get('shownBits') or 0
            k['forced'] += row.get('forced') or 0
            for pair, n in (row.get('rule') or {}).items():
                if pair != 'unread':
                    k['saved/rule ' + pair] += n
                else:
                    k['rule unread'] += 1
    return dict(totals=dict(totals), kinds={k: dict(v) for k, v in sorted(kinds.items())})


def survey(game, names=None, progress=print):
    import settings
    classes = Classes(settings.game_cooked(game))
    found = packages(game, names)
    records = []
    for stem, entry in sorted(found.items(), key=lambda kv: kv[0].lower()):
        try:
            rec = package_record(entry['path'], classes)
        except UNREADABLE as error:
            rec = dict(package=stem, error=str(error), bsp=dict(components=0, drawnNodes=0), instanced=[], terrain={},
                       otherGeometry={})
        rec.update(role=entry['role'], maps=entry['maps'])
        records.append(rec)
        if progress and (rec['bsp'].get('drawnNodes') or rec['terrain'] or rec['otherGeometry']
                         or any(r.get('drawnAtLoad') for r in rec['instanced']) or rec.get('error')):
            progress('%s: bsp %s, terrain %s, other %s, instances drawn %d%s' % (
                stem, rec['bsp'].get('drawnNodes'), rec['terrain'], rec['otherGeometry'],
                sum(r.get('drawnAtLoad') or 0 for r in rec['instanced']), ' ERROR ' + rec['error'] if rec.get('error') else ''))
    out = dict(audit='world-geometry', auditVersion=AUDIT_VERSION, visibilityBit=classes.visibility, **summarise(records),
               packages=records)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='command', required=True)
    s = sub.add_parser('survey')
    s.add_argument('--game', type=Path, help='the game folder (default: the configured LWR install)')
    s.add_argument('--maps', nargs='*')
    s.add_argument('--output', type=Path)
    k = sub.add_parser('package')
    k.add_argument('package', type=Path)
    args = ap.parse_args(argv)
    if args.command == 'package':
        print(json.dumps(package_record(args.package, Classes(args.package.parent)), indent=1))
        return 0
    import labpaths
    game = args.game or labpaths.lwr_game()
    got = survey(game, args.maps)
    print(json.dumps(dict(totals=got['totals'], kinds=got['kinds']), indent=1))
    if args.output:
        args.output.write_text(json.dumps(got, indent=1) + '\n', encoding='utf-8', newline='\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())

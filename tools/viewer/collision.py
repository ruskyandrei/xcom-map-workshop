"""The game's collision for its line checks, per static mesh, for the editor page's ground readings (EXP-32 run 2):
GET /maps/<id>/collision.json?mesh=<id>&mesh=<id>...

The tile rebuild finds a tile's floor with a zero-extent line check down through the tile's centre. A line check meets
a static mesh's simple collision (its BodySetup's convex hulls) when the mesh uses simple line collision, which cooked
meshes do unless they save UseSimpleLineCollision False; its triangles when it doesn't; and nothing when it uses simple
collision but has no BodySetup (research/native-code-notes.md, "Simple or per-triangle collision"). A hull stands over
the drawn surface wherever that dips: on CSmallScout_Farm's ramp up to 5 units, so an invisible floor placed 1 unit
over the drawn ramp was inside the hull, the game found the ramp, and its tile stayed sloped (EXP-32 run 2).

Each answer is the mesh's own: its hull triangles in the mesh's frame, game axes, for the page to place with the
piece's matrix as it places the drawn mesh. Only the map's own package is read (meshes of streamed patches are left
out: the page measures those from the drawn mesh)."""
import hashlib
from pathlib import Path
import struct
import threading

from package import Package, Reader, FormatError


def _vectors(raw, width):
    """A tagged array of `width`-float structs (VertexData: 3), as tuples."""
    r = Reader(raw)
    n = r.count()
    return [r.unpack('%df' % width) for _ in range(n)]


def _ints(raw):
    r = Reader(raw)
    n = r.count()
    return list(r.unpack('%di' % n))


def _box_triangles(elem):
    """A KBoxElem's 12 triangles: X, Y, Z are its full lengths along its TM's axes (UE3's FKBoxElem). The TM is four
    planes (its X, Y and Z axes and its origin), each saved W first, as these packages save every Plane."""
    tm = elem.get(('TM', 0), {}).get('value')
    m = struct.unpack('<16f', tm) if isinstance(tm, (bytes, bytearray)) and len(tm) == 64 else \
        (0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 1, 0, 0, 0)
    axes = [m[4 * row + 1:4 * row + 4] for row in range(4)]       # X, Y, Z, origin: (x, y, z) after each W
    half = [elem.get((k, 0), {}).get('value', 1.0) / 2 for k in ('X', 'Y', 'Z')]
    corner = [[sx * half[0], sy * half[1], sz * half[2]] for sz in (-1, 1) for sy in (-1, 1) for sx in (-1, 1)]
    pts = [tuple(p[0] * axes[0][k] + p[1] * axes[1][k] + p[2] * axes[2][k] + axes[3][k] for k in range(3)) for p in corner]
    faces = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1),
             (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]
    return [pts[i] for f in faces for i in f]


def body_setup(p, mesh):
    """The mesh's BodySetup export (0 when none): a property, or the reference after its bounds in its native data."""
    ref = p.own(mesh, 'BodySetup')
    if ref is None:
        r = p.native(mesh)
        r.unpack('7f')
        ref = r.i32()
    return ref if ref and ref > 0 else 0


def line_collision(p, mesh):
    """What a zero-extent line check meets of static mesh export `mesh`: dict(simple=False) for its triangles (the
    drawn mesh stands for them); dict(simple=True, elements=[[x, y, z, ...], ...]) for its simple collision, each
    convex hull or box a list of its triangles' corners in the mesh's frame (kept apart, as each is a solid: a line
    starting inside one meets its far side first), none when it has no BodySetup (the check passes through); and
    `skipped`, how many sphere and capsule elements were left out."""
    if p.own(mesh, 'UseSimpleLineCollision', True) is False:
        return dict(simple=False)
    bs = body_setup(p, mesh)
    if not bs:
        return dict(simple=True, elements=[], skipped=0)
    agg = p.own(bs, 'AggGeom')
    if not isinstance(agg, (bytes, bytearray)):
        return dict(simple=True, elements=[], skipped=0)
    geom = p.tagged(Reader(agg))
    elements, skipped = [], 0
    for elem in p.structs(geom.get(('ConvexElems', 0), {}).get('value')):
        verts = _vectors(elem[('VertexData', 0)]['value'], 3)
        elements.append([verts[i] for i in _ints(elem[('FaceTriData', 0)]['value'])])
    for elem in p.structs(geom.get(('BoxElems', 0), {}).get('value')):
        elements.append(_box_triangles(elem))
    for key in ('SphereElems', 'SphylElems'):
        skipped += len(p.structs(geom.get((key, 0), {}).get('value')))
    return dict(simple=True, elements=[[round(v, 3) for pt in e for v in pt] for e in elements if e], skipped=skipped)


def mesh_export(p, mesh_id):
    """The StaticMesh export a scene mesh id names in the map's own package ('9792', or '1914-284e324d95f9' for a
    variant of export 1914), or None (a streamed patch's mesh, or anything else)."""
    head = str(mesh_id).split('-')[0]
    if not head.isdigit():
        return None
    index = int(head)
    if not 0 < index <= len(p.exports) or p.cls(index) != 'StaticMesh':
        return None
    return index


class CollisionCache:
    """Each exported map's package read once, the first time the page asks, and each mesh's answer kept (a map's
    export doesn't change under a running server)."""

    def __init__(self):
        self.lock = threading.Lock()
        self.packages = {}
        self.answers = {}

    def package(self, root, scene, find):
        """The map's package for the export at `root`: `find()` gives its path in the install; it must be the file the
        map was exported from (its SHA-256), since the scene's mesh ids are its export indices."""
        if root not in self.packages:
            path = Path(find())
            data = path.read_bytes()
            want = (scene.get('source') or {}).get('sha256')
            if want and hashlib.sha256(data).hexdigest() != want:
                raise FormatError(f'{path.name} in the install is not the file this map was exported from')
            self.packages[root] = Package(path)
        return self.packages[root]

    def get(self, root, scene, find, ids):
        """{mesh id: line_collision() or None} for the scene mesh ids `ids` (None: not one of the map's own meshes)."""
        with self.lock:
            p = self.package(root, scene, find)
            out = {}
            for mesh_id in ids:
                key = (root, mesh_id)
                if key not in self.answers:
                    index = mesh_export(p, mesh_id)
                    try:
                        self.answers[key] = line_collision(p, index) if index else None
                    except (FormatError, KeyError, struct.error):
                        self.answers[key] = None
                out[mesh_id] = self.answers[key]
            return out

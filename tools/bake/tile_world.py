"""A map's pieces as the game's tile build traces them (private/plans/todo/diagonal-cover-plan.md, stage C1):
their collision in world space and the flags the traces filter on, with a box sweep and a line check against them.
research/native/cover-build.md is the reading of the exe this follows; its section numbers are cited.

  World(p)                    the persistent level's listed actors: each mesh component's collision, placed
  world.trace(start, end, extent, kind, ignore)
                              the nearest hit of a sweep (a zero extent: a line) among the pieces `kind` takes:
                                'cover'   the world trace's type 1 (section 4, "The world trace"): XComLevelActor and
                                          its children but ladders, XComFracLevelActor; not CollisionType 1, not
                                          ignored for cover; a destructible saved bIgnoreForPathing never
                                'height'  type 2: as 'cover', with ladders, every interactive piece, and a
                                          destructible with a Toughness that is not fragile
                                'pathing' type 3: a cover piece that ConsiderForOccupancy (bAlwaysConsiderForCover),
                                          ladders among them
                                'sight'   type 4: a cover piece that blocks sight (bBlockUnitVisibility)
                                'engine'  UWorld's SingleLineCheck (flags 0x860C0, level geometry and no others): the
                                          colliding meshes of actors that are bWorldGeometry, by their components'
                                          BlockZeroExtent and BlockNonZeroExtent, whatever the class

What a check meets of a mesh (section 4, the world trace's last item): with an extent, its simple collision (its
BodySetup's convex hulls and boxes) when it saves UseSimpleBoxCollision true, else its triangles; with none, the same
by UseSimpleLineCollision. The world trace meets only a mesh with a BodySetup; a piece with
bUseRigidBodyCollisionForCover takes its simple collision for both. Sphere and capsule elements are not read
(skipped, counted).

A sweep's box is axis-aligned in the world. Against a convex element it is the separating-axis sweep over the
element's saved face normals, the world axes and their crosses with the element's saved edge directions (UE3's
FKConvexElem keeps those two lists for this); a triangle is a convex element of its normal and three edges, met from
its front only. A sweep that starts inside an element hits it at time 0 (`inside` on the hit): the exe's answer there
is not read (cover-build.md section 9, item 1).

Not read here (named where they would matter): pieces of streamed levels, pawns, PathBlockingVolumes, terrain and
BSP, fragments a fracturing piece has lost."""
import math
import struct
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'viewer'))
sys.path.insert(0, str(HERE.parent / 'upk'))
sys.path.insert(0, str(HERE))
import collision  # noqa: E402
import piece_flags  # noqa: E402
from package import Reader  # noqa: E402

# A check that starts inside a convex solid (read off the bake's blocking bits and floor records on occupied tiles,
# F-152; the exe was not read for it): a box sweep meets it at once when the solid's face behind it is nearer than
# the face ahead (it moves deeper), its normal the face behind's, and passes through moving out; a line meets it at
# once whichever way, its normal straight back along the line, but passes through a box element (KBoxElem, a routine
# of its own) it starts inside: right on most maps (98.3% of tiles), wrong on the highway maps, whose floors stand at
# the line's start inside box elements (unexplained; F-152).
INSIDE = 'deeper'
MESH_COMPONENTS = ('StaticMeshComponent', 'FracturedStaticMeshComponent', 'XComMapEdMeshComponent')
LEVEL_FAMILY = ('XComLevelActor', 'XComOpacityFadeLevelActor', 'XComDestructibleActor', 'XComCollectible',
                'XComInteractiveLevelActor', 'XComLadder', 'XComMergedLevelActor')
FRAC_FAMILY = ('XComFracLevelActor', 'XComDecoFracLevelActor')
COVER_CLASSES = LEVEL_FAMILY + FRAC_FAMILY        # the classes with the cover interface the traces read
CELL = 128.0                                    # the spatial index's cell, in x and y
EPS = 1e-6
FORCE = {None: 0, 0: 0, 1: 1, 2: 2, 'CoverForce_Default': 0, 'CoverForce_High': 1, 'CoverForce_Low': 2}


class Element:
    """One convex solid in world space: its vertices (n by 3), its separating axes for a box sweep (face normals,
    the world axes, edges crossed with the world axes) and for a line (face normals), its bounds."""
    __slots__ = ('verts', 'faces', 'edges', 'lo', 'hi', 'piece', 'tris', 'box')

    def __init__(self, verts, faces, edges, piece, box=False):
        self.box = box          # a KBoxElem (its own check routine) rather than a convex hull
        self.verts = verts
        self.faces = faces
        self.edges = edges
        self.lo, self.hi = verts.min(0), verts.max(0)
        self.piece = piece
        self.tris = None


class Triangles:
    """A mesh's triangles in world space (t by 3 by 3), met from their front, with their bounds."""
    __slots__ = ('tri', 'normal', 'lo', 'hi', 'piece')

    def __init__(self, tri, piece):
        self.tri = tri
        n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        length = np.linalg.norm(n, axis=1)
        keep = length > EPS
        self.tri, n, length = tri[keep], n[keep], length[keep]
        self.normal = n / length[:, None]
        self.lo, self.hi = self.tri.reshape(-1, 3).min(0), self.tri.reshape(-1, 3).max(0)
        self.piece = piece


def script_defaults(p, folder=None):
    """The game's script packages (piece_flags.ScriptDefaults) for a package: from `folder`, else the package's own
    folder (a map of the install), else the configured install's cooked folder (a package a Build wrote elsewhere).
    Raises ValueError when none can be read: without them every class default would read as missing."""
    tried = [Path(folder)] if folder else []
    tried.append(Path(p.path).parent)
    try:
        import settings
        game, _ = settings.game_install(settings.load_settings())
        if game is not None:
            tried.append(settings.game_cooked(game))
    except (OSError, ValueError, KeyError):
        pass
    for f in tried:
        found = piece_flags.ScriptDefaults.of(f)
        if found:
            return found
    raise ValueError('the game\'s script packages (XComGame, Engine, Core) are in none of %s' % [str(f) for f in tried])


class Resolver:
    """Any property of an export as the game loads it: the export's own value, else its archetypes' in the map, then
    in the game's script packages (an archetype there, or the class's default object, with what that takes from its
    parents). An archetype in another package the map does not carry gives way to its class's default, and the export
    is counted as `assumed`."""

    def __init__(self, p, scripts=None):
        self.p = p
        self.scripts = script_defaults(p, scripts)
        self.chains = {}
        self.assumed = set()

    def chain(self, index):
        if index in self.chains:
            return self.chains[index]
        p, out, seen, cls = self.p, [], set(), self.p.cls(index)
        start = index
        while index > 0 and index not in seen:
            seen.add(index)
            out.append((p, index))
            cls = p.cls(index)
            index = p.exports[index - 1]['arch']
        tail = []
        if index < 0 and self.scripts:
            tail = piece_flags._script_chain(self.scripts, p.name(index))
            if not tail:
                self.assumed.add(start)
        out += tail
        if self.scripts:
            last = tail[-1] if tail else None
            ends = last[0].exports[last[1] - 1]['arch'] if last else 0
            if not ends:
                c = last[0].cls(last[1]) if last else cls
                for pkg in piece_flags.SCRIPT_PACKAGES:
                    more = piece_flags._script_chain(self.scripts, '%s.Default__%s' % (pkg, c))
                    if more:
                        out += [m for m in more if m not in out]
                        break
        self.chains[start] = out
        return out

    def value(self, index, key, default=None):
        for pk, i in self.chain(index):
            item = pk.properties(i)[0].get((key, 0))
            if item is not None:
                return item['value']
        return default

    def struct_bool(self, index, struct, field, default=False):
        """A bool field of a struct property, from the first export of the chain whose saved struct holds it."""
        for pk, i in self.chain(index):
            item = pk.properties(i)[0].get((struct, 0))
            if item is None:
                continue
            found, value = piece_flags._struct_field(pk, item['value'], field)
            if found and value is not None:
                return value
        return default


class Piece:
    """A placed actor's part in the traces: its class and flags, and per check kind the elements it is met by."""
    __slots__ = ('actor', 'name', 'cls', 'flags', 'force', 'ignore_flag', 'box_solids', 'line_solids', 'engine_box',
                 'engine_line', 'traced', 'skipped', 'bounds', 'occupancy')

    def __init__(self, actor, name, cls):
        self.actor, self.name, self.cls = actor, name, cls
        self.flags = {}
        self.force = self.ignore_flag = 0
        self.box_solids, self.line_solids = [], []     # what the world trace meets, by extent
        self.engine_box, self.engine_line = [], []     # what an engine trace meets, by extent
        self.traced = False
        self.skipped = 0
        self.bounds = []        # each colliding component's world box (lo, hi), for the octree query
        self.occupancy = []     # the components the occupancy step's PointCheck tests, as element lists


# ---------------------------------------------------------------- reading a mesh's collision (local space)

def _vec(raw, width):
    r = Reader(raw)
    n = r.count()
    return np.array([r.unpack('%df' % width) for _ in range(n)], float).reshape(-1, width)


def _box_elem(elem):
    """A KBoxElem's corners, face normals and edges in the mesh's frame (its TM: four planes saved W first)."""
    tm = elem.get(('TM', 0), {}).get('value')
    m = struct.unpack('<16f', tm) if isinstance(tm, (bytes, bytearray)) and len(tm) == 64 else \
        (0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 1, 0, 0, 0)
    axes = np.array([m[4 * row + 1:4 * row + 4] for row in range(4)], float)
    half = [elem.get((k, 0), {}).get('value', 1.0) / 2 for k in ('X', 'Y', 'Z')]
    corners = np.array([[sx * half[0], sy * half[1], sz * half[2]] for sz in (-1, 1) for sy in (-1, 1)
                        for sx in (-1, 1)], float)
    pts = corners @ axes[:3] + axes[3]
    return pts, axes[:3].copy(), axes[:3].copy()


class MeshCollision:
    """A static mesh's simple collision in its own frame: [(vertices, face normals, edge directions)], how many
    sphere and capsule elements were skipped, and its flags."""

    def __init__(self, p, mesh):
        self.mesh = mesh
        self.simple_box = p.own(mesh, 'UseSimpleBoxCollision', True) is not False
        self.simple_line = p.own(mesh, 'UseSimpleLineCollision', True) is not False
        self.body_setup = collision.body_setup(p, mesh)
        self.solids, self.skipped = [], 0
        if not self.body_setup:
            return
        agg = p.own(self.body_setup, 'AggGeom')
        if not isinstance(agg, (bytes, bytearray)):
            return
        geom = p.tagged(Reader(agg))
        for elem in p.structs(geom.get(('ConvexElems', 0), {}).get('value')):
            verts = _vec(elem[('VertexData', 0)]['value'], 3)
            faces = _vec(elem[('FaceNormalDirections', 0)]['value'], 3) if ('FaceNormalDirections', 0) in elem \
                else np.zeros((0, 3))
            edges = _vec(elem[('EdgeDirections', 0)]['value'], 3) if ('EdgeDirections', 0) in elem \
                else np.zeros((0, 3))
            if len(verts) >= 4:
                self.solids.append((verts, faces, edges, False))
        for elem in p.structs(geom.get(('BoxElems', 0), {}).get('value')):
            self.solids.append(_box_elem(elem) + (True,))
        for key in ('SphereElems', 'SphylElems'):
            self.skipped += len(p.structs(geom.get((key, 0), {}).get('value')))


# ---------------------------------------------------------------- the world

class World:
    """The persistent level's listed actors as the traces meet them. `include` (optional) narrows the actors read
    (a predicate on the export index); `scripts`, the folder of the game's script packages (script_defaults)."""

    def __init__(self, p, include=None, scripts=None):
        import lightmap_texels
        import native_copy
        self.p = p
        self.resolver = Resolver(p, scripts)
        self.pieces = []
        self.cells = {}
        self.meshes = {}
        self.counts = dict(actors=0, components=0, noBodySetup=0, perTriangle=0, skippedElements=0, unreadable=0)
        self.blocking_volumes = []      # PathBlockingVolumes' world boxes (lo, hi): the occupancy step's first test
        for a in native_copy.level_actors(p):
            if a <= 0 or (include and not include(a)):
                continue
            cls = p.cls(a)
            if cls == 'PathBlockingVolume':
                try:
                    lo, hi = native_copy.brush_box(p, a)
                    self.blocking_volumes.append((np.array(lo, float), np.array(hi, float)))
                except ValueError:
                    self.counts['unreadable'] += 1
                continue
            if cls.endswith('Volume') or cls in ('WorldInfo',):
                continue
            comps = [c for c in self._components(a)]
            if not comps:
                continue
            piece = self._piece(a, cls)
            self.counts['actors'] += 1
            for c in comps:
                try:
                    m = lightmap_texels.world_matrix(p, c)
                except (ValueError, KeyError, IndexError):
                    self.counts['unreadable'] += 1
                    continue
                self._place(piece, c, m)
            if piece.box_solids or piece.line_solids or piece.engine_box or piece.engine_line or piece.bounds:
                self.pieces.append(piece)
                self._index(piece)

    @classmethod
    def empty(cls, p=None):
        """A world with no pieces (a test's, or one a Build fills with pieces of its own: add)."""
        w = cls.__new__(cls)
        w.p, w.resolver, w.pieces, w.cells, w.meshes, w.blocking_volumes = p, None, [], {}, {}, []
        w.counts = dict(actors=0, components=0, noBodySetup=0, perTriangle=0, skippedElements=0, unreadable=0)
        return w

    def add(self, piece):
        """Put a piece made elsewhere into the world (its elements already placed)."""
        self.pieces.append(piece)
        self._index(piece)
        return piece

    def _components(self, actor):
        p = self.p
        stack = list(p.children.get(actor, []))
        while stack:
            c = stack.pop()
            stack.extend(p.children.get(c, []))
            if p.cls(c) in MESH_COMPONENTS and (p.effective(c, 'StaticMesh', 0) or 0) > 0:
                yield c

    ACTOR_FLAGS = ('bCollideActors', 'bWorldGeometry', 'bBlockActors', 'bIgnoreForCover', 'bIsValidDestination',
                   'bIgnoreForPathing', 'bInteractive', 'bPathColliding', 'bCanStepUpOn', 'bAlwaysConsiderForCover',
                   'bUseRigidBodyCollisionForCover', 'bCanClimbOver', 'bCanClimbOnto')

    def _piece(self, a, cls):
        p, rv = self.p, self.resolver
        piece = Piece(a, p.name(a).split('.')[-1], cls)
        piece.flags = {k: bool(rv.value(a, k, False)) for k in self.ACTOR_FLAGS}
        piece.flags['CollisionType'] = rv.value(a, 'CollisionType', 0)
        piece.flags['bBlockUnitVisibility'] = bool(rv.struct_bool(a, 'VisibilityBlockingData', 'bBlockUnitVisibility',
                                                                  True))
        piece.force = FORCE.get(rv.value(a, 'CoverForceFlag', 0), 0)
        piece.ignore_flag = FORCE.get(rv.value(a, 'CoverIgnoreFlag', 0), 0)
        if cls == 'XComDestructibleActor':
            tough = rv.value(a, 'Toughness', 0) or 0
            piece.flags['toughness'] = bool(tough)
            # (an archetype in another package: taken as not fragile)
            piece.flags['fragile'] = bool(tough > 0 and rv.value(tough, 'bFragile', False))
        piece.traced = cls in COVER_CLASSES
        return piece

    def _mesh(self, mi):
        if mi not in self.meshes:
            self.meshes[mi] = MeshCollision(self.p, mi)
        return self.meshes[mi]

    def _triangles(self, c, m, piece):
        import lightmap_texels
        mesh = lightmap_texels.component_mesh(self.p, c)
        pos = mesh['positions'] @ m[:3, :3].T + m[:3, 3]
        tri = pos[mesh['triangles']]
        if np.linalg.det(m[:3, :3]) < 0:        # a mirrored piece keeps its triangles' fronts
            tri = tri[:, ::-1]
        return Triangles(tri, piece)

    def _place(self, piece, c, m):
        p = self.p
        mi = p.effective(c, 'StaticMesh', 0)
        mc = self._mesh(mi)
        self.counts['components'] += 1
        rv = self.resolver
        # in the collision octree: the actor collides and so does the component (UE3's collision hash)
        if not piece.flags['bCollideActors'] or not rv.value(c, 'CollideActors', False):
            return
        rot = m[:3, :3]
        inv = np.linalg.inv(rot)
        solids = []
        for verts, faces, edges, is_box in mc.solids:
            w = verts @ rot.T + m[:3, 3]
            f = faces @ inv if len(faces) else _faces_of(w)
            f = f / np.maximum(np.linalg.norm(f, axis=1), EPS)[:, None]
            e = edges @ rot.T if len(edges) else np.zeros((0, 3))
            solids.append(Element(w, f, e, piece, box=is_box))
        self.counts['skippedElements'] += mc.skipped
        piece.skipped += mc.skipped
        tris = None

        def triangles():
            nonlocal tris
            if tris is None:
                self.counts['perTriangle'] += 1
                tris = self._triangles(c, m, piece)
            return tris
        rigid = piece.flags.get('bUseRigidBodyCollisionForCover')
        # the octree's box of the component: its mesh's bounds box moved with it (UE3's FBoxSphereBounds::TransformBy)
        ox, oy, oz, ex, ey, ez, _ = p.native(mi).unpack('7f')
        corners = np.array([[ox + sx * ex, oy + sy * ey, oz + sz * ez] for sx in (-1, 1) for sy in (-1, 1)
                            for sz in (-1, 1)]) @ rot.T + m[:3, 3]
        lo, hi = corners.min(0), corners.max(0)
        piece.bounds.append((lo, hi))
        # the occupancy step's PointCheck (section 2): a cover piece but a ladder, with a BodySetup, whose bounds'
        # half-sizes are all 2 or more (or 192 or more in x or y)
        half = (hi - lo) / 2
        if piece.traced and piece.cls != 'XComLadder' and mc.body_setup and                 ((half >= 2.0).all() or half[0] >= 192.0 or half[1] >= 192.0):
            piece.occupancy += solids if mc.simple_box else [triangles()]
        # the world trace: a mesh with a BodySetup only (section 4)
        if piece.traced:
            if not mc.body_setup:
                self.counts['noBodySetup'] += 1
            else:
                piece.box_solids += solids if (mc.simple_box or rigid) else [triangles()]
                piece.line_solids += solids if (mc.simple_line or rigid) else [triangles()]
        # an engine trace (flags 0x860C0: level geometry, no others): an actor that is world geometry, through its
        # components that block a check of that extent
        if piece.flags['bWorldGeometry']:
            if rv.value(c, 'BlockNonZeroExtent', False):
                piece.engine_box += solids if mc.simple_box else [triangles()]
            if rv.value(c, 'BlockZeroExtent', False):
                piece.engine_line += solids if mc.simple_line else [triangles()]

    def _index(self, piece):
        seen = set()
        for el in piece.box_solids + piece.line_solids + piece.engine_box + piece.engine_line + piece.occupancy:
            if id(el) in seen:
                continue
            seen.add(id(el))
            for cx in range(int(math.floor(el.lo[0] / CELL)), int(math.floor(el.hi[0] / CELL)) + 1):
                for cy in range(int(math.floor(el.lo[1] / CELL)), int(math.floor(el.hi[1] / CELL)) + 1):
                    self.cells.setdefault((cx, cy), []).append(el)

    # ------------------------------------------------------------ queries

    def near(self, lo, hi):
        """The elements whose bounds meet the box lo..hi (each once)."""
        out, seen = [], set()
        for cx in range(int(math.floor(lo[0] / CELL)), int(math.floor(hi[0] / CELL)) + 1):
            for cy in range(int(math.floor(lo[1] / CELL)), int(math.floor(hi[1] / CELL)) + 1):
                for el in self.cells.get((cx, cy), ()):
                    if id(el) in seen:
                        continue
                    seen.add(id(el))
                    if (el.lo <= hi).all() and (el.hi >= lo).all():
                        out.append(el)
        return out

    def trace_all(self, start, end, extent=(0.0, 0.0, 0.0), kind='engine'):
        """Every piece a sweep meets, nearest first, each once (its first contact): a MultiLineCheck."""
        start, end, ext = np.asarray(start, float), np.asarray(end, float), np.asarray(extent, float)
        box = bool(ext.any())
        lo, hi = np.minimum(start, end) - ext - 0.01, np.maximum(start, end) + ext + 0.01
        best = {}
        for el in self.near(lo, hi):
            piece = el.piece
            if not _takes(piece, el, kind, box):
                continue
            hit = _sweep(el, start, end - start, ext) if box else _line(el, start, end - start)
            if hit is not None and (id(piece) not in best or hit[0] < best[id(piece)][0]):
                best[id(piece)] = hit + (piece,)
        out = []
        for t, normal, inside, piece in sorted(best.values(), key=lambda h: h[0]):
            out.append(dict(time=t, location=start + (end - start) * t, normal=normal, piece=piece, inside=inside))
        return out

    def trace(self, start, end, extent=(0.0, 0.0, 0.0), kind='cover', ignore=None, skip=None):
        """The nearest hit of a sweep from `start` to `end` (a box of half-size `extent`; zeros: a line) among the
        pieces check `kind` takes ('cover', 'height', 'engine'), or None: dict(time (0 to 1), location (the box's
        centre at contact), normal (unit, against the sweep), piece, inside (it started inside)). `ignore`: a piece
        skipped; `skip(piece)`: True for pieces to pass by as well."""
        start, end, ext = np.asarray(start, float), np.asarray(end, float), np.asarray(extent, float)
        box = bool(ext.any())
        lo, hi = np.minimum(start, end) - ext - 0.01, np.maximum(start, end) + ext + 0.01
        best = None
        for el in self.near(lo, hi):
            piece = el.piece
            if piece is ignore or not _takes(piece, el, kind, box) or (skip and skip(piece)):
                continue
            hit = _sweep(el, start, end - start, ext) if box else _line(el, start, end - start)
            if hit is not None and (best is None or hit[0] < best[0]):
                best = hit + (piece,)
        if best is None:
            return None
        t, normal, inside, piece = best
        return dict(time=t, location=start + (end - start) * t, normal=normal, piece=piece, inside=inside)


    def overlaps(self, centre, extent, kind):
        """The pieces whose elements a box (centre, half-size) overlaps, among those check `kind` takes: 'occupancy'
        (a PointCheck of the tile build's occupancy step: section 2) or 'engine'. [(piece, element)], the nearest
        first is not implied."""
        centre, ext = np.asarray(centre, float), np.asarray(extent, float)
        out = []
        for el in self.near(centre - ext - 0.01, centre + ext + 0.01):
            piece = el.piece
            pool = piece.engine_box if kind == 'engine' else piece.occupancy
            if not any(el is e for e in pool):
                continue
            if _overlap(el, centre, ext):
                out.append((piece, el))
        return out

    def bounds_near(self, point, radius):
        """The pieces whose components' bounds come within `radius` of `point` (an octree query of the collision
        hash: the box of each colliding component's mesh bounds, as UE3 places it)."""
        out = []
        for piece in self.pieces:
            for lo, hi in piece.bounds:
                d = np.maximum(np.maximum(lo - point, 0.0), point - hi)
                if float(d @ d) < radius * radius:
                    out.append(piece)
                    break
        return out


def _overlap(el, centre, ext):
    """Whether a still box overlaps element `el` (a separating-axis test; a triangle mesh: any of its triangles)."""
    if isinstance(el, Triangles):
        lo, hi = centre - ext, centre + ext
        tlo, thi = el.tri.min(1), el.tri.max(1)
        for i in np.nonzero((tlo <= hi).all(1) & (thi >= lo).all(1))[0]:
            v = el.tri[i]
            e = np.diff(np.vstack([v, v[:1]]), axis=0)
            c = np.cross(e[:, None, :], _WORLD[None, :, :]).reshape(-1, 3)
            n = np.linalg.norm(c, axis=1)
            a = np.vstack([el.normal[i][None, :], _WORLD, c[n > 1e-6] / n[n > 1e-6][:, None]])
            if _sat(v, a, centre, np.zeros(3), ext) is not None:
                return True
        return False
    return _sat(el.verts, _axes(el, True), centre, np.zeros(3), ext) is not None


def solid_piece(name, cls, solids, flags=None, force=0, ignore_flag=0, world_geometry=True):
    """A piece of convex solids [(vertices, face normals or None, edge directions or None)] in world space, met by
    every check of its class as a mesh with simple collision is (a test's piece, or a Build's own). Its flags are
    the class's defaults with `flags` over them."""
    piece = Piece(0, name, cls)
    piece.flags = dict(bCollideActors=True, bWorldGeometry=world_geometry, bBlockActors=True, bIgnoreForCover=False,
                       bIsValidDestination=True, bIgnoreForPathing=False, bInteractive=False, bPathColliding=True,
                       bCanStepUpOn=True, bAlwaysConsiderForCover=True, bUseRigidBodyCollisionForCover=False,
                       bCanClimbOver=False, bCanClimbOnto=cls == 'XComLevelActor', CollisionType=0)
    piece.flags.update(flags or {})
    piece.force, piece.ignore_flag = force, ignore_flag
    piece.traced = cls in COVER_CLASSES
    for verts, faces, edges in solids:
        verts = np.asarray(verts, float)
        faces = _faces_of(verts) if faces is None else np.asarray(faces, float)
        faces = faces / np.maximum(np.linalg.norm(faces, axis=1), EPS)[:, None]
        edges = _edges_of(verts) if edges is None else np.asarray(edges, float)
        el = Element(verts, faces, edges, piece)
        if piece.traced:
            piece.box_solids.append(el)
            piece.line_solids.append(el)
        if world_geometry:
            piece.engine_box.append(el)
            piece.engine_line.append(el)
        if piece.traced and cls != 'XComLadder':
            piece.occupancy.append(el)
        piece.bounds.append((el.lo, el.hi))
    return piece


def _edges_of(verts):
    """A convex solid's edge directions, from its hull's triangles (directions within a degree kept once)."""
    from scipy.spatial import ConvexHull
    h = ConvexHull(verts)
    out = []
    for simplex, eq in zip(h.simplices, h.equations):
        for i in range(3):
            e = verts[simplex[(i + 1) % 3]] - verts[simplex[i]]
            n = np.linalg.norm(e)
            if n < EPS:
                continue
            e = e / n
            # an edge inside a face (between two of its coplanar triangles) adds nothing but is harmless
            if not any(abs(float(e @ o)) > 0.99985 for o in out):
                out.append(e)
    return np.array(out).reshape(-1, 3)


def _faces_of(verts):
    from scipy.spatial import ConvexHull
    h = ConvexHull(verts)
    return h.equations[:, :3]


def _takes(piece, el, kind, box):
    """Whether check `kind` (with an extent: `box`) meets element `el` of `piece`."""
    if kind == 'engine':
        return any(el is e for e in (piece.engine_box if box else piece.engine_line))
    if not piece.traced or not any(el is e for e in (piece.box_solids if box else piece.line_solids)):
        return False
    f = piece.flags
    if f.get('CollisionType') in (1, 'COLLIDE_NoCollision'):
        return False
    if piece.cls == 'XComDestructibleActor' and f.get('bIgnoreForPathing'):
        return False
    if kind == 'pathing':
        return bool(f.get('bAlwaysConsiderForCover', True))
    if kind == 'sight':
        return bool(f.get('bBlockUnitVisibility', True))
    if kind == 'height' and (piece.cls in ('XComLadder', 'XComInteractiveLevelActor')
                             or piece.cls == 'XComDestructibleActor' and f.get('toughness') and not f.get('fragile')):
        return True
    if piece.cls == 'XComLadder':
        return False
    return not ignored_for_cover(piece)


def ignored_for_cover(piece):
    """ShouldIgnoreForCover: bIgnoreForCover, and for a prop also bInteractive (piece_flags' reading)."""
    f = piece.flags
    if f.get('bIgnoreForCover'):
        return True
    return piece.cls in ('XComDestructibleActor', 'XComCollectible') and bool(f.get('bInteractive'))


# ---------------------------------------------------------------- the sweeps

_WORLD = np.eye(3)


def _sat(verts, axes, start, move, ext):
    """(entry time, exit time, the entry axis) of a box of half-size `ext` moving from `start` by `move` against the
    convex set `verts`, over the separating axes `axes` (unit), or None when an axis separates for good."""
    proj = verts @ axes.T
    emin, emax = proj.min(0), proj.max(0)
    s0, v, r = axes @ start, axes @ move, np.abs(axes) @ ext
    lo, hi = emin - r - s0, emax + r - s0
    still = np.abs(v) < 1e-9
    if (still & ((lo > 0) | (hi < 0))).any():
        return None
    with np.errstate(divide='ignore', invalid='ignore'):
        t1, t2 = lo / v, hi / v
    enter = np.where(still, -np.inf, np.minimum(t1, t2))
    leave = np.where(still, np.inf, np.maximum(t1, t2))
    k = int(np.argmax(enter))
    return enter[k], leave.min(), k


def _inside(axes, k, enter, leave, move):
    """A check that started inside a convex solid (INSIDE): (0, the face behind's normal, True) when it moves deeper
    (the face behind, at time `enter` < 0, nearer than the face ahead, at `leave`), else None."""
    if INSIDE == 'deeper' and -enter <= leave:
        n = axes[k] if axes[k] @ move < 0 else -axes[k]
        return 0.0, n, True
    if INSIDE == 'start':
        return 0.0, -move / max(np.linalg.norm(move), EPS), True
    return None


def _axes(el, box):
    if not box:
        return el.faces
    if el.edges is not None and len(el.edges):
        cross = np.cross(el.edges[:, None, :], _WORLD[None, :, :]).reshape(-1, 3)
        n = np.linalg.norm(cross, axis=1)
        cross = cross[n > 1e-6] / n[n > 1e-6][:, None]
        return np.vstack([el.faces, _WORLD, cross])
    return np.vstack([el.faces, _WORLD])


def _sweep(el, start, move, ext):
    """(time, normal, inside) of a box sweep's first contact with element `el`, or None."""
    if isinstance(el, Triangles):
        return _sweep_tris(el, start, move, ext)
    axes = _axes(el, True)
    got = _sat(el.verts, axes, start, move, ext)
    if got is None:
        return None
    enter, leave, k = got
    if enter > leave or enter > 1.0 or leave < 0.0:
        return None
    if enter < 0.0:
        return _inside(axes, k, enter, leave, move)
    n = axes[k] if axes[k] @ move < 0 else -axes[k]
    return float(enter), n, False


def _line(el, start, move):
    """(time, normal, inside) of a line's first contact with element `el`, or None."""
    if isinstance(el, Triangles):
        return _sweep_tris(el, start, move, np.zeros(3))
    got = _sat(el.verts, el.faces, start, move, np.zeros(3))
    if got is None:
        return None
    enter, leave, k = got
    if enter > leave or enter > 1.0 or leave < 0.0:
        return None
    if enter < 0.0:
        return None if el.box else (0.0, -move / max(np.linalg.norm(move), EPS), True)
    n = el.faces[k] if el.faces[k] @ move < 0 else -el.faces[k]
    return float(enter), n, False


def _sweep_tris(tr, start, move, ext):
    """The first front-facing triangle a box (or a line) meets: (time, normal, False), or None."""
    lo = np.minimum(start, start + move) - ext - 0.01
    hi = np.maximum(start, start + move) + ext + 0.01
    tlo, thi = tr.tri.min(1), tr.tri.max(1)
    near = np.nonzero((tlo <= hi).all(1) & (thi >= lo).all(1) & (tr.normal @ move < 0))[0]
    best = None
    for i in near:
        v = tr.tri[i]
        e = np.diff(np.vstack([v, v[:1]]), axis=0)
        axes = [tr.normal[i][None, :]]
        if ext.any():
            c = np.cross(e[:, None, :], _WORLD[None, :, :]).reshape(-1, 3)
            n = np.linalg.norm(c, axis=1)
            axes += [_WORLD, c[n > 1e-6] / n[n > 1e-6][:, None]]
        else:
            # a line against a triangle: the in-plane edge normals keep it inside
            c = np.cross(e, tr.normal[i])
            axes.append(c / np.maximum(np.linalg.norm(c, axis=1), EPS)[:, None])
        a = np.vstack(axes)
        got = _sat(v, a, start, move, ext)
        if got is None:
            continue
        enter, leave, k = got
        if enter > leave or enter > 1.0 or leave < 0.0 or enter < 0.0:
            continue
        if best is None or enter < best[0]:
            best = (float(enter), tr.normal[i], False)
    return best

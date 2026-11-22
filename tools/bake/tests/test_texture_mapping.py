"""A made piece's texture mapping applied by its generator (custom geometry improvements plan, section 5, stage 4;
the rule is uv_mapping.py's): a free wall's two faces (frac_wall.py), a free slab's top and underside (frac_slab.py), a
free ground shape's top and sides (ground.py).

Each mapped face's texture coordinates are checked at its corners against the values worked out here by hand for each
mode (size, fit, count, a mode of its own along v, a 30-degree turn, flips, a half-repeat offset, world-aligned with
the frame's place in the world), whole repeats aside (each face's are held near 0), and inside each triangle exactly
(the rate the pattern runs at); the faces' signs (side B and the underside the mirror of side A and the top); a
resized piece keeping its repeats' size or their count; a split wall's and slab's pieces reading the whole's frame and
extent, so the pattern goes on across the cuts; a gap or a hole leaving the pattern where it was; the tangents
following a turned mapping; nothing but the listed surfaces' texture coordinates changing; and free numbers without a
mapping building byte for byte as on the commit stage 4 started from (dd6f094)."""
import hashlib
import json
import math
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import fixtures  # noqa: E402
import frac_slab  # noqa: E402
import frac_wall  # noqa: E402
import free_form  # noqa: E402
from free_form import NumbersError  # noqa: E402
import gen_mesh  # noqa: E402
import ground  # noqa: E402
import looks  # noqa: E402
import made_split  # noqa: E402

C30, S30 = math.cos(math.radians(30.0)), math.sin(math.radians(30.0))
# a Bar-look wall (its faces at y -8 and 8, from z -16 to 384) with a doorway
WALL = dict(free=1, x0=10.0, x1=394.0, seed=2, openings=[dict(x0=150.0, x1=246.0, z0=-16.0, z1=200.0)])
SLAB = dict(free=1, x0=10.5, x1=500.25, y0=-30.0, y1=260.75, z0=-2.0, z1=2.0, seed=4,
            holes=[dict(x0=100.0, x1=180.0, y0=50.0, y1=80.0)])
BLOCK = dict(free=1, shape='block', x0=10.0, x1=150.0, y0=-20.0, y1=70.0, z0=0.0, z1=60.0)


def size(u, v, **more):
    return dict(mode='size', u=float(u), v=float(v), **more)


def turned(a, b, degrees):
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    return a * c - b * s, a * s + b * c


def counted(counts, extent, degrees):
    """want(a, b) of a count (`counts` (cu, cv); a fit's (1, 1)) turned `degrees` over a surface of `extent` (a0, a1,
    b0, b1): the point turned, then counted over the run of the surface's turned corners along each axis."""
    pts = [turned(a, b, degrees) for a in extent[:2] for b in extent[2:]]
    (u0, u1), (v0, v1) = [(min(p[k] for p in pts), max(p[k] for p in pts)) for k in (0, 1)]

    def want(a, b):
        qu, qv = turned(a, b, degrees)
        return counts[0] * (qu - u0) / (u1 - u0), counts[1] * (qv - v0) / (v1 - v0)
    return want


def mapped(numbers, origin=None, **surfaces):
    out = dict(numbers, mapping=dict(surfaces=surfaces))
    if origin is not None:
        out['mappingOrigin'] = origin
    return out


def unpacked(b):
    return tuple((c - 127.5) / 127.5 for c in b[:3])


def corners(out):
    """[(position, normal, tangent, uv0, the lightmap's uv)] of a built piece's LOD 0 vertices."""
    lod = out['mesh']['lods'][0]
    return [(p, unpacked(v[1]), unpacked(v[0]), tuple(v[2][0]), tuple(v[2][1]))
            for p, v in zip(lod['positions'], lod['vertices'])]


def triangles(out):
    idx = out['mesh']['lods'][0]['indices'][1]
    return [idx[k:k + 3] for k in range(0, len(idx), 3)]


def gradient(places, uvs):
    """((du/ds, du/dt), (dv/ds, dv/dt)) of a triangle whose corners stand at `places` [(s, t)] with coordinates
    `uvs`."""
    (s0, t0), (s1, t1), (s2, t2) = places
    ds1, dt1, ds2, dt2 = s1 - s0, t1 - t0, s2 - s0, t2 - t0
    det = ds1 * dt2 - ds2 * dt1
    out = []
    for c in range(2):
        d1, d2 = uvs[1][c] - uvs[0][c], uvs[2][c] - uvs[0][c]
        out.append(((d1 * dt2 - d2 * dt1) / det, (ds1 * d2 - ds2 * d1) / det))
    return out


def wall_digest(out):
    """OldNumbers' digest of a built wall (test_frac_wall.py's): its mesh written, its collision, fragment boxes,
    lightmap rectangle, counts and whole."""
    mesh = gen_mesh.write(dict(out['mesh'], bodySetup=0), 0)
    rest = repr((out['solids'], out['fragments'], out['lightmapRect'], out['counts'], out.get('whole')))
    return hashlib.sha256(mesh + rest.encode()).hexdigest()


def bar_storeys(wall):
    return 2, True


def bar_heights(wall):
    R = frac_wall.shaped(wall)
    return R['bottom'], R['top']


class Checks:
    """The checks of a mapped surface (a mixin): `faces(out)` the mapped face kinds' corners, each kind (place (s, t)
    on the surface's own axes, the signs its texture is written with); `want(s, t)` the rule's (U, V) there, worked
    out by hand."""

    def check_surface(self, out, keep, place, signs, want, least=4):
        """Every corner of `out` that `keep(position, normal)` holds has signs * want(place(position)) as its texture
        coordinates, whole repeats aside; every triangle of three such corners has want's rate exactly. Returns how
        many corners were checked."""
        # (the positions are written as 32-bit floats, a ten-thousandth of a unit off where they are a thousand out, and
        # the coordinates worked out from the places before: the tolerances hold that and nothing a wrong rule gives)
        rows = corners(out)
        chosen = {i for i, (p, n, _, _, _) in enumerate(rows) if keep(p, n)}
        for i in chosen:
            p, _, _, uv, _ = rows[i]
            U, V = want(*place(p))
            for got, w in ((uv[0], signs[0] * U), (uv[1], signs[1] * V)):
                self.assertLess(abs((got - w) - round(got - w)), 1e-5, (p, uv, (signs[0] * U, signs[1] * V)))
        rate = None
        tris = 0
        for tri in triangles(out):
            if not all(i in chosen for i in tri):
                continue
            places = [place(rows[i][0]) for i in tri]
            if abs((places[1][0] - places[0][0]) * (places[2][1] - places[0][1])
                   - (places[2][0] - places[0][0]) * (places[1][1] - places[0][1])) < 4.0:
                continue
            got = gradient(places, [rows[i][3] for i in tri])
            if rate is None:
                s, t = 37.0, 11.0
                U0, V0 = want(s, t)
                Ua, Va = want(s + 1.0, t)
                Ub, Vb = want(s, t + 1.0)
                rate = ((signs[0] * (Ua - U0), signs[0] * (Ub - U0)), (signs[1] * (Va - V0), signs[1] * (Vb - V0)))
            for g, r in zip(got, rate):
                self.assertAlmostEqual(g[0], r[0], delta=1e-6)
                self.assertAlmostEqual(g[1], r[1], delta=1e-6)
            tris += 1
        self.assertGreaterEqual(len(chosen), least)
        self.assertGreater(tris, 0)
        return len(chosen)

    # ---- a wall's faces: side A on its +y face's plane facing +y, side B on its -y face's facing -y; a along x, b up
    def check_wall(self, wall, want, dx=0.0, dz=0.0, faces=(8.0, -8.0)):
        out = frac_wall.build(wall)
        ya, yb = faces
        for y, side, signs in ((ya, 1, (1.0, -1.0)), (yb, -1, (-1.0, -1.0))):
            self.check_surface(out, lambda p, n, y=y, side=side: side * n[1] > 0.99 and abs(p[1] - y) < 1e-3,
                               lambda p: (p[0] + dx, p[2] + dz), signs, want)
        return out

    # ---- a slab's top (facing up at z1) and underside (facing down at z0); a along x, b along y
    def check_slab(self, slab, role, want, dx=0.0, dy=0.0):
        out = frac_slab.build(slab)
        z, up, signs = (slab['z1'], 1, (1.0, 1.0)) if role == 'top' else (slab['z0'], -1, (-1.0, 1.0))
        self.check_surface(out, lambda p, n: up * n[2] > 0.99 and abs(p[2] - z) < 1e-3,
                           lambda p: (p[0] + dx, p[1] + dy), signs, want)
        return out


class WallFaces(Checks, unittest.TestCase):
    CASES = {
        'size': (size(96, 48), lambda a, b: (a / 96.0, b / 48.0)),
        'fit': (dict(mode='fit', u=1.0, v=1.0), lambda a, b: ((a - 10.0) / 384.0, (b + 16.0) / 400.0)),
        'count': (dict(mode='count', u=3.0, v=1.5), lambda a, b: (3.0 * (a - 10.0) / 384.0, 1.5 * (b + 16.0) / 400.0)),
        'along by size, up fit': (dict(mode='size', modeV='fit', u=64.0, v=1.0),
                                  lambda a, b: (a / 64.0, (b + 16.0) / 400.0)),
        'turn 30': (size(100, 100, turn=30.0), lambda a, b: ((a * C30 - b * S30) / 100.0, (a * S30 + b * C30) / 100.0)),
        # (a repeat 96 along the pattern's u and 48 along its v, turned whole)
        'turn 30, bricks': (size(96, 48, turn=30.0),
                            lambda a, b: ((a * C30 - b * S30) / 96.0, (a * S30 + b * C30) / 48.0)),
        # turned a quarter, (a, b) -> (-b, a): three repeats up the wall (-b runs -384..16), two along it (a 10..394)
        'count turned a quarter': (dict(mode='count', u=3.0, v=2.0, turn=90.0),
                                   lambda a, b: (3.0 * (384.0 - b) / 400.0, 2.0 * (a - 10.0) / 384.0)),
        'flips': (size(96, 96, flipU=True, flipV=True), lambda a, b: (-a / 96.0, -b / 96.0)),
        # turned a quarter, scaled, mirrored, then slid: (a, b) -> (-b, a) / 100 -> (b, a) / 100 -> + (0.25, -0.5)
        'turn, flip, slide': (size(100, 100, flipU=True, turn=90.0, offsetU=0.25, offsetV=-0.5),
                              lambda a, b: (b / 100.0 + 0.25, a / 100.0 - 0.5)),
        'half-repeat offset': (size(96, 96, offsetU=0.5, offsetV=0.5), lambda a, b: (a / 96.0 + 0.5, b / 96.0 + 0.5)),
    }

    def test_each_mode_at_its_corners(self):
        for name, (surface, want) in self.CASES.items():
            with self.subTest(name):
                self.check_wall(mapped(WALL, faces=surface), want)

    def test_world_aligned_from_the_frames_place(self):
        surface = size(96, 64, world=True)
        for origin in ([1000.0, 50.0], [1000.0, -333.0, 50.0]):
            with self.subTest(origin=origin):
                self.check_wall(mapped(WALL, origin=dict(faces=origin), faces=surface),
                                lambda a, b: ((a + 1000.0) / 96.0, (b + 50.0) / 64.0))
        # two walls end to end (their ends on the line between them), the second framed 384 further on in the world:
        # where they meet, the same places in the pattern at every height
        line = dict(WALL, x0=0.0, x1=384.0, openings=[], ends=['line', 'line'])
        meet = []
        for x, place in ((384.0, 0.0), (0.0, 384.0)):
            out = frac_wall.build(mapped(line, origin=dict(faces=[place, 0.0]), faces=surface))
            meet.append({round(p[2], 3): uv for p, n, _, uv, _ in corners(out)
                         if n[1] > 0.99 and abs(p[1] - 8.0) < 1e-3 and abs(p[0] - x) < 1e-3})
        self.assertGreater(len(set(meet[0]) & set(meet[1])), 2)
        for z in set(meet[0]) & set(meet[1]):
            for got, want in zip(meet[1][z], meet[0][z]):
                self.assertLess(abs((got - want) - round(got - want)), 1e-6, z)

    def test_side_b_is_side_a_through_the_wall(self):
        out = frac_wall.build(mapped(WALL, faces=size(100, 70, turn=30.0, offsetU=0.3)))
        a, b = {}, {}
        for p, n, _, uv, _ in corners(out):
            if abs(n[1]) > 0.99 and abs(abs(p[1]) - 8.0) < 1e-3:
                (a if n[1] > 0 else b)[round(p[0], 3), round(p[2], 3)] = uv
        self.assertGreater(len(set(a) & set(b)), 20)
        for key in set(a) & set(b):
            for got, want in ((b[key][0], -a[key][0]), (b[key][1], a[key][1])):
                self.assertLess(abs((got - want) - round(got - want)), 1e-6, key)

    def test_a_resized_wall_keeps_its_repeats_size_or_their_count(self):
        for x1 in (394.0, 778.0, 211.5):
            length = x1 - 10.0
            with self.subTest(x1=x1):
                self.check_wall(mapped(dict(WALL, x1=x1, openings=[]), faces=size(96, 96)),
                                lambda a, b: (a / 96.0, b / 96.0))
                self.check_wall(mapped(dict(WALL, x1=x1, openings=[]), faces=dict(mode='count', u=3.0, v=1.0)),
                                lambda a, b, L=length: (3.0 * (a - 10.0) / L, (b + 16.0) / 400.0))

    def test_a_split_walls_pieces_read_the_whole(self):
        count = dict(mode='count', u=5.0, v=3.0, turn=30.0)
        for tall, z1 in (('repeat', 900.0), ('stretch', 1200.0)):
            whole = mapped(dict(free=1, x0=-30.0, x1=2000.0, z0=-16.0, z1=z1, seed=5, tall=tall,
                                openings=[dict(x0=1500.0, x1=1600.0, z0=-16.0, z1=200.0)]), faces=count)
            pieces = made_split.free_wall_pieces(whole, bar_storeys, bar_heights)
            self.assertGreater(len({dx for dx, _, _ in pieces}), 1, tall)
            self.assertGreater(len({dz for _, dz, _ in pieces}), 1, tall)
            want = counted((5.0, 3.0), (-30.0, 2000.0, -16.0, z1), 30.0)
            for dx, dz, piece in pieces:
                with self.subTest(tall=tall, dx=dx, dz=dz):
                    self.assertEqual(piece['mapping'], whole['mapping'])
                    # (the piece's frame starts dx along from the whole's x0, dz up from its floor)
                    self.check_wall(piece, want, dx=dx - 30.0, dz=dz)

    def test_a_gap_leaves_the_pattern_where_it_was(self):
        # the wall with its doorway and without it read one pattern, the corners round the doorway too
        want = lambda a, b: ((a * C30 - b * S30) / 96.0, (a * S30 + b * C30) / 48.0)      # noqa: E731
        self.check_wall(mapped(dict(WALL, openings=[]), faces=size(96, 48, turn=30.0)), want)
        out = self.check_wall(mapped(WALL, faces=size(96, 48, turn=30.0)), want)
        sides = [p for p, n, _, _, _ in corners(out)
                 if n[1] > 0.99 and abs(p[1] - 8.0) < 1e-3 and min(abs(p[0] - 150.0), abs(p[0] - 246.0)) < 1e-3]
        self.assertGreater(len(sides), 2)

    def test_a_leaning_ends_corners_read_the_pattern_where_they_moved(self):
        wall = mapped(dict(free=1, x0=0.0, x1=600.0, seed=6, ends=['free', dict(inset=0.0, lean=1.0)],
                           openings=[dict(x0=200.0, x1=300.0, z0=-16.0, z1=160.0)]), faces=size(90, 70))
        out = self.check_wall(wall, lambda a, b: (a / 90.0, b / 70.0))
        moved = [p for p, n, _, _, _ in corners(out) if n[1] > 0.99 and abs(p[1] - 8.0) < 1e-3 and p[0] > 600.0]
        self.assertGreater(len(moved), 2)           # (side A's end leans out past 600 by 8)

    def test_a_thick_wall_and_a_measured_look(self):
        thick = mapped(dict(free=1, x0=13.25, x1=157.5, y0=-20.0, y1=5.0, z0=0.0, z1=217.25, seed=3),
                       faces=size(50, 40))
        self.check_wall(thick, lambda a, b: (a / 50.0, b / 40.0), faces=(5.0, -20.0))
        look = looks.resolve('wall', dict(mesh='BLDG_RoadHouse.Meshes.RHWallEast_FRACTURED', measure=1))
        measured = mapped(dict(free=1, x0=0.0, x1=480.0, z0=0.0, z1=300.0, y0=-10.0, y1=6.0, look=look, seed=5),
                          faces=dict(mode='count', u=2.0, v=1.0))
        R = frac_wall.shaped(measured)
        out = frac_wall.build(measured)
        checked = 0
        for X, side, signs in (('A', 1, (1.0, -1.0)), ('B', -1, (-1.0, -1.0))):
            # (its faces' planes: the y of its strips that are faces, outward on each side)
            ys = {R['profile'][X][k][0] for k, s in enumerate(R['strips'][X]) if s.get('face')}
            self.assertTrue(ys, X)
            for face_y in ys:
                checked += self.check_surface(
                    out, lambda p, n, fy=face_y, side=side: side * n[1] > 0.99 and abs(side * p[1] - fy) < 1e-3,
                    lambda p: (p[0], p[2]), signs, lambda a, b: (2.0 * a / 480.0, b / 300.0), least=1)
        self.assertGreater(checked, 8)

    def test_a_look_without_faces_keeps_its_texture(self):
        # a UFO's wall is one unwrap of its whole outline (no strip of it a face, wall_measure.py): nothing to map
        look = looks.resolve('wall', dict(mesh='AbductorExtWall.Meshes.AbductorExtWallA_FRACTURED', measure=1))
        wall = dict(free=1, x0=0.0, x1=480.0, look=look, seed=5)
        a, b = frac_wall.build(wall), frac_wall.build(mapped(wall, faces=size(64, 64)))
        self.assertEqual(a['mesh']['lods'][0]['vertices'], b['mesh']['lods'][0]['vertices'])

    def test_the_tangents_follow_the_mapping(self):
        for surface, want_a in ((size(100, 100), (1.0, 0.0, 0.0)), (size(100, 100, turn=30.0), (C30, 0.0, -S30)),
                                (size(100, 100, turn=-90.0), (0.0, 0.0, 1.0))):
            with self.subTest(turn=surface.get('turn', 0.0)):
                out = frac_wall.build(mapped(WALL, faces=surface))
                found = 0
                for p, n, t, _, _ in corners(out):
                    if abs(n[1]) > 0.99 and abs(abs(p[1]) - 8.0) < 1e-3:
                        want = want_a if n[1] > 0 else (-want_a[0], 0.0, -want_a[2])
                        for got, w in zip(t, want):
                            self.assertAlmostEqual(got, w, delta=0.01)
                        found += 1
                self.assertGreater(found, 20)

    def test_only_the_faces_texture_changes(self):
        plain, out = frac_wall.build(WALL), frac_wall.build(mapped(WALL, faces=size(64, 64, turn=45.0)))
        a, b = plain['mesh']['lods'][0], out['mesh']['lods'][0]
        self.assertEqual((a['positions'], a['indices'][1], a['colours']),
                         (b['positions'], b['indices'][1], b['colours']))
        self.assertEqual(plain['lightmapRect'], out['lightmapRect'])
        changed = 0
        for (p, n, t, uv, lm), (_, n2, t2, uv2, lm2) in zip(corners(plain), corners(out)):
            self.assertEqual((n, lm), (n2, lm2))
            face = abs(n[1]) > 0.99 and abs(abs(p[1]) - 8.0) < 1e-3
            if face:
                changed += uv != uv2
            else:
                # trims (the cornice's upright at 12 among them), caps, ends, the doorway's sides, the faces inside
                self.assertEqual((uv, t), (uv2, t2), p)
        self.assertGreater(changed, 20)
        self.assertNotEqual(frac_wall.mesh_name(mapped(WALL, faces=size(64, 64))), frac_wall.mesh_name(WALL))

    def test_too_small_a_repeat_is_refused_for_the_half_floats(self):
        with self.assertRaises(NumbersError) as e:
            frac_wall.build(mapped(WALL, faces=size(0.05, 96)))
        self.assertEqual(e.exception.code, 'half-floats')


class SlabFaces(Checks, unittest.TestCase):
    def test_top_and_underside_at_their_corners(self):
        cases = {
            'size': (size(96, 64), lambda a, b: (a / 96.0, b / 64.0)),
            'count': (dict(mode='count', u=4.0, v=2.5),
                      lambda a, b: (4.0 * (a - 10.5) / 489.75, 2.5 * (b + 30.0) / 290.75)),
            'fit': (dict(mode='fit', u=1.0, v=1.0), lambda a, b: ((a - 10.5) / 489.75, (b + 30.0) / 290.75)),
            'turn 30': (size(80, 80, turn=30.0), lambda a, b: ((a * C30 - b * S30) / 80.0, (a * S30 + b * C30) / 80.0)),
            'flips and offsets': (size(96, 96, flipV=True, offsetU=0.5, offsetV=0.5),
                                  lambda a, b: (a / 96.0 + 0.5, -b / 96.0 + 0.5)),
        }
        for name, (surface, want) in cases.items():
            for role in ('top', 'underside'):
                with self.subTest(name, role=role):
                    self.check_slab(mapped(SLAB, **{role: surface}), role, want)

    def test_world_aligned_from_the_frames_place(self):
        for origin in ([5000.0, -300.0], [5000.0, -300.0, 77.0]):
            with self.subTest(origin=origin):
                self.check_slab(mapped(SLAB, origin=dict(top=origin), top=size(96, 96, world=True)), 'top',
                                lambda a, b: ((a + 5000.0) / 96.0, (b - 300.0) / 96.0))

    def test_each_surface_alone(self):
        # the top mapped, the underside and the edges as the look has them
        plain, out = frac_slab.build(SLAB), frac_slab.build(mapped(SLAB, top=size(50, 50, turn=20.0)))
        self.assertEqual(out['mesh']['lods'][0]['positions'], plain['mesh']['lods'][0]['positions'])
        self.assertEqual(out['mesh']['lods'][0]['colours'], plain['mesh']['lods'][0]['colours'])
        changed = 0
        for (p, n, t, uv, lm), (_, n2, t2, uv2, lm2) in zip(corners(plain), corners(out)):
            self.assertEqual((n, lm), (n2, lm2))
            if n[2] > 0.99:
                changed += uv != uv2
            else:
                self.assertEqual((uv, t), (uv2, t2), p)
        self.assertGreater(changed, 8)

    def test_a_split_slabs_pieces_read_the_whole(self):
        surface = dict(mode='count', u=6.0, v=1.5, turn=30.0)
        whole = dict(free=1, x0=-40.0, x1=1700.0, y0=10.0, y1=1800.0, z0=-2.0, z1=2.0, seed=3,
                     holes=[dict(x0=1400.0, x1=1500.0, y0=100.0, y1=200.0)], mapping=dict(surfaces=dict(top=surface,
                                                                                                underside=surface)))
        pieces = made_split.free_slab_pieces(whole)
        self.assertGreater(len(pieces), 3)
        want = counted((6.0, 1.5), (-40.0, 1700.0, 10.0, 1800.0), 30.0)
        for dx, dy, piece in pieces:
            for role in ('top', 'underside'):
                with self.subTest(dx=dx, dy=dy, role=role):
                    self.check_slab(piece, role, want, dx=dx - 40.0, dy=dy + 10.0)

    def test_the_tangents_follow_the_mapping(self):
        for surface, want in ((size(100, 100), (1.0, 0.0, 0.0)), (size(100, 100, turn=30.0), (C30, -S30, 0.0))):
            out = frac_slab.build(mapped(SLAB, top=surface))
            found = 0
            for p, n, t, _, _ in corners(out):
                if n[2] > 0.99:
                    for got, w in zip(t, want):
                        self.assertAlmostEqual(got, w, delta=0.01)
                    found += 1
            self.assertGreater(found, 8)

    def test_a_measured_look(self):
        recipe = dict(role='roof', kind='flat', bottom=10.0, top=16.0, slots=dict(top=1, underside=1, edge=1),
                      sections=3, interior=2, insideFaces=True,
                      uv=dict(top=[[0.0, 1 / 300.0, 0.25], [-1 / 300.0, 0.0, 0.5]],
                              underside=[[-1 / 150.0, 0.0, 0.0], [0.0, 1 / 150.0, 0.125]],
                              edge=dict(x=[[1 / 300.0, 0.0, 0.0], [0.0, 1 / 64.0, 0.0]],
                                        y=[[1 / 300.0, 0.0, 0.0], [0.0, 1 / 64.0, 0.0]])),
                      collision=[10.0, 14.0], tile=96.0, split=0.2, long=0.4,
                      colours=dict(outside='00ffffff', interior='ffffffff'),
                      lightmap=dict(density=0.2, margin=2, interiorDensity=1.0, block=4),
                      measured=dict(size=[384.0, 288.0, 6.0], triangles=100, fragments=12, perTile=1.0, kind='flat',
                                    centre=[150.0, 40.0]))
        slab = dict(SLAB, z0=0.0, z1=6.0, look=dict(mesh='Pkg.Group.Some_FRACTURED', measure=1, recipe=recipe))
        self.check_slab(mapped(slab, underside=size(70, 90)), 'underside', lambda a, b: (a / 70.0, b / 90.0))


class GroundFaces(Checks, unittest.TestCase):
    # a side's kind: (its normal's test, its a's axis, its signs)
    SIDES = {'+y': (lambda n: n[1] > 0.99, 0, (1.0, -1.0)), '-y': (lambda n: n[1] < -0.99, 0, (-1.0, -1.0)),
             '+x': (lambda n: n[0] > 0.99, 1, (-1.0, -1.0)), '-x': (lambda n: n[0] < -0.99, 1, (1.0, -1.0))}

    def check_sides(self, shape, want_along_x, want_along_y):
        out = ground.build(shape)
        for name, (facing, along, signs) in self.SIDES.items():
            with self.subTest(side=name):
                self.check_surface(out, lambda p, n, facing=facing: facing(n), lambda p, along=along: (p[along], p[2]),
                                   signs, want_along_x if along == 0 else want_along_y, least=4)
        return out

    def test_the_sides_at_their_corners(self):
        self.check_sides(mapped(BLOCK, sides=dict(mode='count', u=2.0, v=1.0)),
                         lambda a, b: (2.0 * (a - 10.0) / 140.0, b / 60.0),
                         lambda a, b: (2.0 * (a + 20.0) / 90.0, b / 60.0))
        self.check_sides(mapped(BLOCK, sides=size(32, 24, turn=30.0)),
                         *[lambda a, b: ((a * C30 - b * S30) / 32.0, (a * S30 + b * C30) / 24.0)] * 2)

    def test_world_aligned_sides_read_their_own_axis(self):
        self.check_sides(mapped(BLOCK, origin=dict(sides=[100.0, 200.0, 5.0]), sides=size(40, 40, world=True)),
                         lambda a, b: ((a + 100.0) / 40.0, (b + 5.0) / 40.0),
                         lambda a, b: ((a + 200.0) / 40.0, (b + 5.0) / 40.0))
        with self.assertRaises(NumbersError) as e:
            ground.check(mapped(BLOCK, origin=dict(sides=[100.0, 5.0]), sides=size(40, 40, world=True)))
        self.assertEqual(e.exception.code, 'mapping')

    def test_the_top_a_patchs_and_a_ramps_slope(self):
        patch = dict(free=1, shape='patch', x0=10.5, x1=300.0, y0=-20.0, y1=150.25, z0=-5.0, z1=3.0)
        ramp = dict(free=1, shape='ramp', x0=0.0, x1=300.0, y0=-40.0, y1=60.0, z0=0.0, z1=100.0)
        slope = math.hypot(300.0, 100.0)
        for shape, extent, place in ((patch, (10.5, 300.0, -20.0, 150.25), lambda p: (p[0], p[1])),
                                     (BLOCK, (10.0, 150.0, -20.0, 70.0), lambda p: (p[0], p[1])),
                                     # (a ramp's slope in its own plane: a along it, its length the extent's)
                                     (ramp, (0.0, slope, -40.0, 60.0), lambda p: (p[0] * slope / 300.0, p[1]))):
            with self.subTest(shape['shape']):
                out = ground.build(mapped(shape, top=dict(mode='fit', u=1.0, v=1.0, turn=30.0)))
                self.check_surface(out, lambda p, n: n[2] > 0.5, place, (1.0, 1.0), counted((1.0, 1.0), extent, 30.0), least=4)
        # a repeat of 50 up the slope is 50 along it, not 50 across the ground: its high edge is slope / 50 repeats up
        out = ground.build(mapped(ramp, top=size(50, 50)))
        self.check_surface(out, lambda p, n: n[2] > 0.5, lambda p: (p[0] * slope / 300.0, p[1]), (1.0, 1.0),
                           lambda a, b: (a / 50.0, b / 50.0), least=4)

    def test_a_ramps_slope_as_the_page_has_it(self):
        # (slope_mapping_cases.json: made_mapping.js surfacePlane, surfaceAt and surfaceExtent are its twins on the page,
        # shared_cases_test.mjs): the places, the extent and the rule's coordinates; the built slope's corners take them
        import uv_mapping
        cases = json.loads((HERE / 'slope_mapping_cases.json').read_text(encoding='utf-8'))['cases']
        self.assertGreaterEqual(len(cases), 4)
        for c in cases:
            with self.subTest(c['case']):
                r = c['ramp']
                box = [r[k] for k in ('x0', 'x1', 'y0', 'y1', 'z0', 'z1')]
                extent = uv_mapping.slope_extent(*box)
                self.assertTrue(all(abs(g - w) < 1e-6 for g, w in zip(extent, c['extent'])), (extent, c['extent']))
                for p, ab, want in zip(c['points'], c['places'], c['uv']):
                    place = (uv_mapping.along_slope(p[0], box[0], box[1], box[4], box[5]), p[1])
                    got = uv_mapping.uv(c['surface'], *place, extent, c.get('origin') or (0.0, 0.0))
                    self.assertTrue(all(abs(g - w) < 1e-6 for g, w in zip(place + got, ab + want)), (p, place, got))
                numbers = mapped(r, top=c['surface'], origin=dict(top=c['origin']) if c.get('origin') else None)
                wanted = {tuple(round(v, 3) for v in p): want for p, want in zip(c['points'][:4], c['uv'][:4])}
                seen = 0
                for p, n, _, uv, _ in corners(ground.build(numbers)):
                    want = wanted.get(tuple(round(v, 3) for v in p))
                    if n[2] > 0.5 and want:
                        seen += 1
                        for g, w in zip(uv, want):
                            self.assertLess(abs((g - w) - round(g - w)), 1e-4, (p, uv, want))     # (whole repeats aside)
                self.assertEqual(seen, 4)
        self.check_surface(ground.build(mapped(BLOCK, origin=dict(top=[-1000.0, 30.0]), top=size(64, 64, world=True))),
                           lambda p, n: n[2] > 0.5, lambda p: (p[0], p[1]), (1.0, 1.0),
                           lambda a, b: ((a - 1000.0) / 64.0, (b + 30.0) / 64.0))

    def test_the_tangents_follow_the_mapping(self):
        out = ground.build(mapped(BLOCK, top=size(100, 100, turn=30.0)))
        tops = [t for p, n, t, _, _ in corners(out) if n[2] > 0.99]
        self.assertEqual(len(tops), 4)
        for t in tops:
            for got, w in zip(t, (C30, -S30, 0.0)):
                self.assertAlmostEqual(got, w, delta=0.01)

    def test_each_surface_alone(self):
        plain, out = ground.build(BLOCK), ground.build(mapped(BLOCK, sides=size(30, 30)))
        changed = 0
        for (p, n, t, uv, lm), (p2, n2, t2, uv2, lm2) in zip(corners(plain), corners(out)):
            self.assertEqual((p, n, lm), (p2, n2, lm2))
            if abs(n[2]) > 0.5:
                self.assertEqual((uv, t), (uv2, t2), p)
            else:
                changed += uv != uv2
        self.assertEqual(changed, 16)


class Numbers(unittest.TestCase):
    """The mapping's numbers checked by every generator, and free numbers without one built as they were."""
    # digests recorded on dd6f094, before the generators read a mapping (test_frac_wall.py's OldNumbers' form for the
    # walls, fixtures.made_digest for the slabs and ground shapes)
    WALLS = {
        'fractional': (dict(free=1, x0=13.25, x1=157.5, y0=-20.0, y1=5.0, z0=0.0, z1=217.25, seed=3,
                            openings=[dict(x0=50.75, x1=88.5, z0=0.0, z1=150.0)]),
                       '48b7b0bfcb483328a8d7d02cf9b3fe4e4dfb2840df012f16dfa815e277c2ce54'),
        'band': (dict(free=1, x0=0.0, x1=500.0, z0=-16.0, z1=1184.0, band=[384.0, 784.0], seed=4, tall='stretch'),
                 '62e31c6809d184fd24dfebdf0eee019b7911b8ab3fcaa566e03be08f87c1d7c7'),
        'piece': (dict(free=1, x0=0.0, x1=500.0, seed=7, whole=[450.0, 1050.0, 400.0, 800.0, -50.0]),
                  '7ae26907b3cc355bece16d049cae6b2aa70010c5e9d6dfad1645b1ae667c733f'),
        'measured mitre': ('measured', 'cbdeb59ee79dd0c3e4f49c0230f272d79cfd2215d2a075feef48174876ad5a52'),
    }
    SLABS = {
        'partial': (dict(free=1, x0=10.5, x1=500.25, y0=-30.0, y1=260.75, z0=-2.0, z1=2.0, seed=4,
                         holes=[dict(x0=100.0, x1=180.0, y0=50.0, y1=80.0),
                                dict(x0=300.0, x1=330.0, y0=-30.0, y1=0.0)]),
                    '8739f206c7ea7460774e7a701a450b01a5d613e2ca80684a533b43344e5c2109'),
        'piece': (dict(free=1, x0=0.0, x1=700.5, y0=0.0, y1=500.0, z0=-2.0, z1=2.0, seed=3,
                       whole=[1200.25, 960.0, 3000.0, 2000.0, -10.0, 5.0]),
                  'ef270d2904734bc80dee8b1589a7e2f8c1370f04c5c1c5b047295e01a67860bd'),
        'floor': (dict(free=1, x0=3.25, x1=40.0, y0=-7.0, y1=20.5, z0=190.0, z1=194.0, look='floor'),
                  '2fed028616855421e0bc8a396c935cc06b5b30649f706dbc3e2571f910f5dedb'),
    }
    GROUND = {
        'patch': (dict(free=1, shape='patch', x0=10.5, x1=300.0, y0=-20.0, y1=150.25, z0=-5.0, z1=3.0),
                  '52564df8c73e04524ecec4420527314df10efd7e4f599b989bd3472f7311e3d9'),
        'block': (dict(free=1, shape='block', x0=0.0, x1=150.0, y0=0.0, y1=90.0, z0=0.0, z1=70.5),
                  '0829fc98034daec81519b99f0eb62ef7a91dbc8f4f546cb2fea132263d51a5f9'),
        'ramp': (dict(free=1, shape='ramp', x0=0.0, x1=300.0, y0=-40.0, y1=60.0, z0=0.0, z1=100.0),
                 '40eb2bde6fdd3b07973383c2343d14386da47d60610588f6a05d7b592c1c0556'),
        'rock': (dict(free=1, shape='rock', x0=0.0, x1=200.0, y0=0.0, y1=120.0, z0=0.0, z1=90.0, seed=11),
                 '8942e877b68c17d30f112bd092b56ebdf8719606e1e3ff24c65aca8735b24921'),
    }

    def test_free_numbers_without_a_mapping_build_byte_for_byte(self):
        look = looks.resolve('wall', dict(mesh='AbductorExtWall.Meshes.AbductorExtWallA_FRACTURED', measure=1))
        measured = dict(free=1, x0=0.0, x1=480.0, look=look, seed=5, ends=[dict(inset=-3.0, lean=0.4142), 'line'])
        for name, (wall, digest) in self.WALLS.items():
            with self.subTest(wall=name):
                self.assertEqual(wall_digest(frac_wall.build(measured if wall == 'measured' else wall)), digest)
        for name, (slab, digest) in self.SLABS.items():
            with self.subTest(slab=name):
                self.assertEqual(fixtures.made_digest(frac_slab.build(slab), frac_slab.mesh_name(slab)), digest)
        for name, (shape, digest) in self.GROUND.items():
            with self.subTest(ground=name):
                self.assertEqual(fixtures.made_digest(ground.build(shape), ground.mesh_name(shape)), digest)

    def test_a_surface_the_piece_has_not_changes_nothing_of_its_mesh(self):
        # (its name and its tail's guid are its numbers': another request, another mesh to the game)
        other = size(50, 50, turn=10.0)
        for build, numbers, surfaces in ((frac_wall.build, WALL, dict(top=other, underside=other, sides=other)),
                                         (frac_slab.build, SLAB, dict(faces=other, sides=other)),
                                         (ground.build, BLOCK, dict(faces=other, underside=other))):
            a, b = build(numbers)['mesh']['lods'][0], build(mapped(numbers, **surfaces))['mesh']['lods'][0]
            for key in ('positions', 'vertices', 'indices', 'colours'):
                self.assertEqual(a[key], b[key], (numbers.get('shape'), key))

    def test_bad_mappings_and_origins_are_refused(self):
        for bad in (dict(mapping=dict(surfaces=dict(roof=size(1, 1)))),
                    dict(mapping=dict(surfaces=dict(top=dict(mode='tile', u=1, v=1)))),
                    dict(mapping=dict(surfaces=dict(top=size(0, 1)))), dict(mapping=dict(other=1)),
                    dict(mappingOrigin=[0.0, 0.0]), dict(mappingOrigin=dict(roof=[0.0, 0.0])),
                    dict(mappingOrigin=dict(top=[0.0])), dict(mappingOrigin=dict(top=[0.0, float('nan')])),
                    dict(mappingOrigin=dict(sides=[1.0, 2.0])), dict(mappingOrigin=dict(faces=[1.0, True]))):
            with self.subTest(bad=bad):
                with self.assertRaises(NumbersError) as e:
                    free_form.mapping(bad, 'a piece')
                self.assertEqual(e.exception.code, 'mapping')
                for check, numbers in ((frac_wall.check_free, WALL), (frac_slab.check_free, SLAB),
                                       (ground.check_free, BLOCK)):
                    with self.assertRaises(NumbersError) as e:
                        check(dict(numbers, **bad))
                    self.assertEqual(e.exception.code, 'mapping')
        free_form.mapping(dict(mapping=dict(surfaces=dict(faces=size(1, 1))),
                               mappingOrigin=dict(faces=[1.0, 2.0], sides=[1.0, 2.0, 3.0])), 'a piece')


if __name__ == '__main__':
    unittest.main()

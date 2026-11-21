"""Slabs in any look (frac_slab.py; custom geometry plan, M4): the named looks build byte for byte as before, and a
look given whole (a dict with a measured recipe) builds any of the game's layouts: the donor's sections in slot order
(a slot it makes nothing in left empty), top, underside and edges each in their slot, planar texture maps, faces
inside where the donor has them; its mesh's name follows the look, not the spelling of its recipe.

The free form (custom geometry improvements plan, section 10.2): old numbers build byte for byte as on the commit it
started from; free numbers build a slab of any footprint, holes anywhere, the plate between z0 and z1, its texture
coordinates held near 0, its mapping taken and not read; a piece past the splitter's chunk is refused."""
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
import gen_mesh  # noqa: E402
from free_form import NumbersError  # noqa: E402

ROOF = dict(x0=0.0, x1=384.0, y0=0.0, y1=288.0, seed=4, holes=[dict(x0=96.0, x1=192.0, y0=96.0, y1=192.0)])
FLOOR = dict(x0=0.0, x1=288.0, y0=480.0, y1=672.0, seed=5, look='floor')
# a measured recipe of another layout: three sections, top, underside and edges all in slot 1, slot 0 left empty, the
# faces inside in slot 2; the top's texture turned a quarter (u along y), the underside's at another repeat
RECIPE = dict(role='roof', kind='flat', bottom=10.0, top=16.0, slots=dict(top=1, underside=1, edge=1), sections=3,
              interior=2, insideFaces=True,
              uv=dict(top=[[0.0, 1 / 300.0, 0.25], [-1 / 300.0, 0.0, 0.5]],
                      underside=[[-1 / 150.0, 0.0, 0.0], [0.0, 1 / 150.0, 0.125]],
                      edge=dict(x=[[1 / 300.0, 0.0, 0.0], [0.0, 1 / 64.0, 0.0]], y=[[1 / 300.0, 0.0, 0.0], [0.0, 1 / 64.0, 0.0]])),
              collision=[10.0, 14.0], tile=96.0, split=0.2, long=0.4,
              colours=dict(outside='00ffffff', interior='ffffffff'),
              lightmap=dict(density=0.2, margin=2, interiorDensity=1.0, block=4),
              measured=dict(size=[384.0, 288.0, 6.0], triangles=100, fragments=12, perTile=1.0, kind='flat'))


def look(recipe=RECIPE, mesh='Pkg.Group.Some_FRACTURED'):
    return dict(mesh=mesh, measure=1, recipe=recipe)


def slots_of(out):
    lod = out['mesh']['lods'][0]
    idx = lod['indices'][1]
    return {s['slot']: [idx[s['first'] + k:s['first'] + k + 3] for k in range(0, 3 * s['triangles'], 3)]
            for s in lod['sections']}


class NamedLooks(unittest.TestCase):
    def test_they_build_byte_for_byte_as_before(self):
        # (the hashes of the mesh as frac_slab built it before looks could be given whole)
        for slab, digest, name in ((ROOF, 'b06a7cd22dd99f6ab6c51a8cedae5ce633ac1444ee75177539b645a0b25cfb0b',
                                    'FracSlab_4x3_9d1e5ea4a0'),
                                   (FLOOR, '8de42f751d7839cf2ec4e58300fbfafd6b12eabf80560422c606dbe7f10ee35b',
                                    'FracSlab_3x2_16eb263a97')):
            out = frac_slab.build(slab)
            self.assertEqual(hashlib.sha256(gen_mesh.write(out['mesh'], 0)).hexdigest(), digest)
            self.assertEqual(frac_slab.mesh_name(slab), name)


class GivenLooks(unittest.TestCase):
    S = dict(x0=0.0, x1=384.0, y0=0.0, y1=288.0, seed=2, holes=[dict(x0=96.0, x1=192.0, y0=96.0, y1=192.0)])

    def setUp(self):
        self.slab = dict(self.S, look=look())
        self.out = frac_slab.build(self.slab)

    def test_the_donors_sections_in_slot_order_an_unused_one_empty(self):
        lod = self.out['mesh']['lods'][0]
        self.assertEqual([s['slot'] for s in lod['sections']], [0, 1, 2])
        self.assertEqual(lod['sections'][0]['triangles'], 0)
        self.assertGreater(lod['sections'][1]['triangles'], 0)
        self.assertGreater(lod['sections'][2]['triangles'], 0)
        self.assertEqual(self.out['mesh']['fractured']['interior'], 2)
        self.assertTrue(gen_mesh.write(self.out['mesh'], 0))

    def test_the_plate_stands_between_the_recipes_heights(self):
        zs = sorted({round(p[2], 3) for p in self.out['mesh']['lods'][0]['positions']})
        self.assertEqual(zs, [10.0, 16.0])
        self.assertEqual(frac_slab.local_box(self.slab)[4:], [10.0, 16.0])
        self.assertEqual({(b[0][2], b[1][2]) for b in self.out['solids']}, {(10.0, 14.0)})

    def test_the_faces_inside_stand_on_the_shared_edges_in_the_interior_slot(self):
        lod = self.out['mesh']['lods'][0]
        inner = slots_of(self.out)[2]
        for tri in inner:
            self.assertTrue(all(abs((lod['vertices'][v][1][2] - 127.5) / 127.5) < 0.05 for v in tri))   # upright
        # every fragment shares edges, so each has faces inside; none on the outline (x 0 or 384, y 0 or 288)
        for tri in inner:
            pts = [lod['positions'][v] for v in tri]
            self.assertFalse(all(abs(p[0]) < 1e-3 for p in pts) or all(abs(p[0] - 384) < 1e-3 for p in pts))
            self.assertFalse(all(abs(p[1]) < 1e-3 for p in pts) or all(abs(p[1] - 288) < 1e-3 for p in pts))

    def test_the_texture_follows_the_recipes_maps(self):
        lod = self.out['mesh']['lods'][0]
        seen = 0
        for p, (_, n, uvs) in zip(lod['positions'], lod['vertices']):
            if n[2] > 250:          # the top: u = y / 300 + 0.25, v = -x / 300 + 0.5
                self.assertAlmostEqual(uvs[0][0], p[1] / 300 + 0.25, 2)
                self.assertAlmostEqual(uvs[0][1], -p[0] / 300 + 0.5, 2)
                seen += 1
            elif n[2] < 5:          # the underside: u = -x / 150, v = y / 150 + 0.125
                self.assertAlmostEqual(uvs[0][0], -p[0] / 150, 2)
                self.assertAlmostEqual(uvs[0][1], p[1] / 150 + 0.125, 2)
        self.assertGreater(seen, 0)

    def test_the_name_follows_the_look_not_its_spelling(self):
        name = frac_slab.mesh_name(self.slab)
        reordered = json.loads(json.dumps(RECIPE, sort_keys=True))
        self.assertEqual(frac_slab.mesh_name(dict(self.S, look=look(reordered))), name)
        self.assertNotEqual(frac_slab.mesh_name(dict(self.S, look=look(dict(RECIPE, top=18.0)))), name)
        self.assertNotEqual(frac_slab.mesh_name(dict(self.S, look=look(mesh='Pkg.Group.Other'))), name)
        # the same mesh whatever the recipe's spelling
        again = frac_slab.build(dict(self.S, look=look(reordered)))
        self.assertEqual(gen_mesh.write(again['mesh'], 0), gen_mesh.write(self.out['mesh'], 0))

    def test_a_look_without_its_recipe_is_refused(self):
        for bad in (dict(mesh='Pkg.A', measure=1), dict(measure=1, recipe=RECIPE), 7):
            with self.assertRaises(ValueError):
                frac_slab.check(dict(self.S, look=bad))

    def test_one_slot_for_everything(self):
        one = dict(RECIPE, slots=dict(top=0, underside=0, edge=0), sections=1, interior=1, insideFaces=False)
        out = frac_slab.build(dict(self.S, look=look(one)))
        self.assertEqual([s['slot'] for s in out['mesh']['lods'][0]['sections']], [0])
        self.assertEqual(out['mesh']['fractured']['interior'], 1)


# old numbers of every path (named looks, a given look with faces inside, holes, a piece of a split slab with its
# `whole`), each build's digest (fixtures.made_digest) recorded on the commit the free form started from
CENTRED = dict(RECIPE, measured=dict(RECIPE['measured'], centre=[150.0, 40.0]))
OLD = {
    'roof-holes': (dict(x0=0.0, x1=384.0, y0=0.0, y1=288.0, seed=4, holes=[dict(x0=96.0, x1=192.0, y0=96.0, y1=192.0)]),
                   'c7d54c1c12ca203b76ca6fc3d075c376e106195683ca1733ad4e5c41584b8ef3'),
    'floor-offset': (dict(x0=0.0, x1=288.0, y0=480.0, y1=672.0, seed=5, look='floor'),
                     '1d4d5ef6defdad67866e9499f01614ba619f83ef26eeaaec7ef71f86aa265a50'),
    'roof-big': (dict(x0=0.0, x1=1536.0, y0=0.0, y1=960.0, seed=77,
                      holes=[dict(x0=192.0, x1=480.0, y0=96.0, y1=288.0), dict(x0=960.0, x1=1056.0, y0=576.0, y1=864.0)]),
                 '54c2873c779a8c14c6cc4b6f3ac5263c7c46076ab3c974dbc81b2502a859bcd4'),
    'given-inside': (dict(x0=0.0, x1=384.0, y0=0.0, y1=288.0, seed=2, look=look(CENTRED),
                          holes=[dict(x0=96.0, x1=192.0, y0=96.0, y1=192.0)]),
                     'ed608f25c067a328c45c0159842cf7db772cb20264666916ae102c4042b3e797'),
    'split-piece': (dict(x0=0.0, x1=480.0, y0=0.0, y1=384.0, seed=31, holes=[dict(x0=0.0, x1=96.0, y0=0.0, y1=96.0)],
                         whole=[1536.0, 768.0, 2016.0, 1152.0]),
                    'c79bd94199ad5312ba49ee22052a1d0ea7f6cd41daa485f5289485abb3a0701d'),
    'given-split': (dict(x0=0.0, x1=288.0, y0=0.0, y1=192.0, seed=9, look=look(CENTRED), whole=[1536.0, 0.0, 1824.0, 192.0]),
                    '81dcaaf4a9084525c7eea95f741b31273076f839478a4bf4ca14594d8b15f4e2'),
}
PARTIAL = dict(free=1, x0=10.5, x1=500.25, y0=-30.0, y1=260.75, z0=-2.0, z1=2.0, seed=4,
               holes=[dict(x0=150.0, x1=230.0, y0=40.0, y1=70.0), dict(x0=300.0, x1=330.0, y0=120.0, y1=150.0)])


def areas(out):
    """The mesh's area by its faces' facing: (up, down, sideways), outside faces only (not the interior slot)."""
    m = out['mesh']
    lod = m['lods'][0]
    idx, pos = lod['indices'][1], lod['positions']
    inner = (m['fractured'] or {}).get('interior')
    up = down = side = 0.0
    for s in lod['sections']:
        if s['slot'] == inner:
            continue
        for k in range(s['first'], s['first'] + 3 * s['triangles'], 3):
            a, b, c = (pos[v] for v in idx[k:k + 3])
            n = [(b[1] - a[1]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[1] - a[1]),
                 (b[2] - a[2]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[2] - a[2]),
                 (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])]
            ar = 0.5 * math.sqrt(sum(v * v for v in n))
            nz = (lod['vertices'][idx[k]][1][2] - 127.5) / 127.5
            if nz > 0.7:
                up += ar
            elif nz < -0.7:
                down += ar
            else:
                side += ar
    return up, down, side


class OldNumbers(unittest.TestCase):
    def test_they_build_byte_for_byte_as_before_the_free_form(self):
        for key, (slab, digest) in OLD.items():
            with self.subTest(key):
                self.assertEqual(fixtures.made_digest(frac_slab.build(slab), frac_slab.mesh_name(slab)), digest)


class FreeSlabs(unittest.TestCase):
    def test_a_partial_slab_builds_its_solid_area_and_no_more(self):
        out = frac_slab.build(PARTIAL)
        self.assertTrue(gen_mesh.write(out['mesh'], 0))
        solid = (500.25 - 10.5) * (260.75 + 30.0) - 80.0 * 30.0 - 30.0 * 30.0
        perimeter = 2 * (500.25 - 10.5) + 2 * (260.75 + 30.0) + 2 * (80.0 + 30.0) + 4 * 30.0
        up, down, side = areas(out)
        self.assertAlmostEqual(up, solid, 1)
        self.assertAlmostEqual(down, solid, 1)
        self.assertAlmostEqual(side, perimeter * 4.0, 1)          # the edges: the outline's and the holes', 4 high
        self.assertEqual(sorted({round(p[2], 4) for p in out['mesh']['lods'][0]['positions']}), [-2.0, 2.0])
        self.assertAlmostEqual(sum((b[1][0] - b[0][0]) * (b[1][1] - b[0][1]) for b in out['solids']), solid, 6)
        self.assertEqual(frac_slab.local_box(PARTIAL), [10.5, 500.25, -30.0, 260.75, -2.0, 2.0])
        self.assertEqual(frac_slab.check_free(PARTIAL), [10.5, 500.25, -30.0, 260.75, -2.0, 2.0])
        self.assertEqual(frac_slab.check(PARTIAL), frac_slab.check_free(PARTIAL))
        # each fragment's record lists the fragments across its inside edges, and they it
        frags = out['mesh']['fractured']['fragments']
        self.assertEqual(len(frags), out['counts']['fragments'])
        for f, rec in enumerate(frags):
            for g in rec['neighbours']:
                if g >= 0:
                    self.assertIn(f, frags[g]['neighbours'])

    def test_a_thick_slab_and_one_under_a_tile(self):
        thick = dict(PARTIAL, z0=-40.0, z1=2.0)
        out = frac_slab.build(thick)
        self.assertEqual({(b[0][2], b[1][2]) for b in out['solids']}, {(-40.0, 0.0)})
        self.assertEqual(sorted({round(p[2], 4) for p in out['mesh']['lods'][0]['positions']}), [-40.0, 2.0])
        small = dict(free=1, x0=3.25, x1=40.0, y0=-7.0, y1=20.5, z0=190.0, z1=194.0, look='floor')
        out = frac_slab.build(small)
        self.assertEqual(out['counts']['fragments'], 1)
        self.assertAlmostEqual(areas(out)[0], 36.75 * 27.5, 2)
        self.assertEqual(out['solids'], [((3.25, -7.0, 190.0), (40.0, 20.5, 194.0))])

    def test_the_texture_is_world_planar_held_near_0_in_whole_repeats(self):
        # a piece far along a split slab: its texture is the whole's, its coordinates near 0, each place's phase kept
        piece = dict(free=1, x0=0.0, x1=700.5, y0=0.0, y1=500.0, z0=-2.0, z1=2.0, seed=3, whole=[12000.25, 9600.0, 13000.0, 10000.0])
        out = frac_slab.build(piece)
        R = frac_slab.look_of(piece)
        su, sv, du, dv = R['topUV']
        lod = out['mesh']['lods'][0]
        tops = 0
        for p, (_, n, uvs) in zip(lod['positions'], lod['vertices']):
            u, v = uvs[0]
            self.assertLess(abs(u), 8.0)
            self.assertLess(abs(v), 8.0)
            if n[2] > 250:
                want = (su * (p[0] + 12000.25) / R['repeat'] + du, sv * (p[1] + 9600.0) / R['repeat'] + dv)
                # (the half float's step near 4 is 1/256)
                self.assertLess(abs(((u - want[0]) + 0.5) % 1.0 - 0.5), 1 / 256)
                self.assertLess(abs(((v - want[1]) + 0.5) % 1.0 - 0.5), 1 / 256)
                tops += 1
        self.assertGreater(tops, 0)

    def test_a_measured_look_with_faces_inside(self):
        slab = dict(PARTIAL, look=look(), z0=0.0, z1=6.0, holes=[dict(x0=40.0, x1=96.0, y0=40.0, y1=96.0)])
        out = frac_slab.build(slab)
        self.assertTrue(gen_mesh.write(out['mesh'], 0))
        self.assertEqual({(b[0][2], b[1][2]) for b in out['solids']}, {(0.0, 4.0)})   # [10, 14] of the plate 10..16
        lod = out['mesh']['lods'][0]
        inner = [s for s in lod['sections'] if s['slot'] == 2][0]
        self.assertGreater(inner['triangles'], 0)
        # the L the hole leaves of its cell is one fragment: no face inside it on the edge its two faces share
        frags = frac_slab.fragments(slab)
        (corner,) = [f for f in frags if len(f) == 2]
        shared = set(corner[0]) & set(corner[1])
        idx, pos = lod['indices'][1], lod['positions']
        for k in range(inner['first'], inner['first'] + 3 * inner['triangles'], 3):
            pts = [pos[v] for v in idx[k:k + 3]]
            xy = {(round(p[0], 3), round(p[1], 3)) for p in pts}
            self.assertFalse(xy <= {(round(x, 3), round(y, 3)) for x, y in shared}, xy)

    def test_the_mapping_and_plain_are_taken_and_not_read(self):
        plain = frac_slab.build(PARTIAL)
        mapped = dict(PARTIAL, plain=True, mapping=dict(surfaces=dict(top=dict(mode='size', u=96.0, v=96.0))))
        out = frac_slab.build(mapped)
        a, b = plain['mesh']['lods'][0], out['mesh']['lods'][0]
        for key in ('positions', 'vertices', 'indices', 'colours'):
            self.assertEqual(a[key], b[key], key)
        self.assertEqual(plain['solids'], out['solids'])
        self.assertNotEqual(frac_slab.mesh_name(mapped), frac_slab.mesh_name(PARTIAL))

    def test_one_piece_is_at_most_the_splitters_chunk(self):
        most = frac_slab.CHUNK * 96.0
        frac_slab.check_free(dict(PARTIAL, x0=0.0, x1=most, holes=[]))
        for change in (dict(x0=0.0, x1=most + 0.5), dict(y0=-most, y1=1.0)):
            with self.assertRaises(NumbersError) as e:
                frac_slab.check(dict(PARTIAL, holes=[], **change))
            self.assertEqual(e.exception.code, 'chunk')

    def test_check_free_takes_free_numbers_only(self):
        with self.assertRaises(NumbersError) as e:
            frac_slab.check_free(OLD['roof-holes'][0])
        self.assertEqual(e.exception.code, 'free')
        with self.assertRaises(ValueError):
            frac_slab.check_free(dict(PARTIAL, free=2))
        with self.assertRaises(ValueError):
            frac_slab.check_free(dict(PARTIAL, look='marble'))


if __name__ == '__main__':
    unittest.main()

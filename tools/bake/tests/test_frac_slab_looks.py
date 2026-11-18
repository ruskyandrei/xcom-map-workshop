"""Slabs in any look (frac_slab.py; custom geometry plan, M4): the named looks build byte for byte as before, and a
look given whole (a dict with a measured recipe) builds any of the game's layouts: the donor's sections in slot order
(a slot it makes nothing in left empty), top, underside and edges each in their slot, planar texture maps, faces
inside where the donor has them; its mesh's name follows the look, not the spelling of its recipe."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import frac_slab  # noqa: E402
import gen_mesh  # noqa: E402

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


if __name__ == '__main__':
    unittest.main()

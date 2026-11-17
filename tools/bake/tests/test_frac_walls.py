"""Fracturing walls made from numbers in the variant map (frac_walls.py; custom geometry plan, section 0, stage F3).

The columns rule and the request's checks on their own; then, with the configured install (tools/viewer/settings.py),
the proof of concept's build on the bar (no bake): three copies of URB_BarIntWallB_FRACTURED on the pavement, the
reference ('relit', its mesh the donor's), the twin (the donor's size) and the custom wall (four tiles with a doorway),
read back with a fresh reader: the new meshes written whole under XComMapEdGeo, each component's numbers as the
game's walls save them (F0), one painted colour for each new vertex, the columns by F0's rule, the tiles seeded over
the wall's own box."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(TOOLS / 'upk'))
sys.path.insert(0, str(TOOLS / 'viewer'))
sys.path.insert(0, str(TOOLS / 'lab'))
import frac_wall  # noqa: E402
import frac_walls  # noqa: E402
import gen_mesh  # noqa: E402
import labpaths  # noqa: E402
import lightmap_texels  # noqa: E402

BAR, NO_BAR = labpaths.test_file('XCOM_BAR_UPK', labpaths.lwr_cooked('URB_Bar.upk'), 'URB_Bar.upk')
PL = 'TheWorld.PersistentLevel.'
DONOR = 'XComDecoFracLevelActor_17'
DOOR = dict(x0=96.0, x1=192.0, z0=-16.0, z1=160.0)
COPIES = [
    dict(actor=DONOR, location=[-1344.0, -192.0, 16.0], rotation=[0, 0, 0], label='Reference',
         generated=dict(kind='relit', version=1)),
    dict(actor=DONOR, location=[-576.0, -192.0, 16.0], rotation=[0, 0, 0], label='Twin',
         generated=dict(kind='fracWall', version=1, wall=dict(x0=-376.0, x1=184.0, openings=[], seed=1))),
    dict(actor=DONOR, location=[-192.0, -192.0, 16.0], rotation=[0, 0, 0], label='Custom',
         generated=dict(kind='fracWall', version=1, wall=dict(x0=0.0, x1=384.0, openings=[DOOR], seed=2))),
]


def overlap(a, b):
    return all(min(a[2 * k + 1], b[2 * k + 1]) - max(a[2 * k], b[2 * k]) > 0 for k in range(3))


class Columns(unittest.TestCase):
    GRID = dict(tx=-1.0, ty=-1.0, tz=-1.0)

    def test_a_column_for_each_tile_and_storey_listing_the_fragments_over_it(self):
        # four fragments a tile wide each, the first two a storey tall, the others two storeys
        boxes = [[96.0 * k - 1, 96.0 * k + 95, -12.0, 12.0, -1.0, 191.0 if k < 2 else 383.0] for k in range(4)]
        cols = frac_walls.columns(boxes, self.GRID)
        self.assertEqual(len(cols), 6)
        for c in cols:
            listed = [f for f, _ in c['frags']]
            self.assertEqual(listed, [f for f, b in enumerate(boxes) if overlap(b, c['box'])])
            self.assertEqual([z for _, z in c['frags']], sorted(z for _, z in c['frags']))
            self.assertAlmostEqual(c['box'][5] - c['box'][4], frac_walls.STOREY)
            self.assertEqual(c['box'][2:4], [-12.0, 12.0])
        # cut to the wall's ends: the last column stops at the last fragment's end
        self.assertAlmostEqual(max(c['box'][1] for c in cols), boxes[-1][1])

    def test_a_wall_along_y_is_cut_along_y(self):
        boxes = [[-8.0, 8.0, 96.0 * k - 1, 96.0 * k + 95, -1.0, 191.0] for k in range(3)]
        cols = frac_walls.columns(boxes, self.GRID)
        self.assertEqual(len(cols), 3)
        self.assertTrue(all(c['box'][:2] == [-8.0, 8.0] for c in cols))

    def test_requests_are_checked(self):
        ok = dict(kind='fracWall', version=1, wall=dict(x0=0, x1=96, openings=[]))
        self.assertIs(frac_walls.check(ok), ok)
        self.assertEqual(frac_walls.check(dict(kind='relit', version=1))['kind'], 'relit')
        for bad in (None, dict(kind='wall'), dict(kind='fracWall', version=2, wall=ok['wall']),
                    dict(kind='fracWall', version=1, wall=dict(x0=0, x1=12)),
                    dict(kind='fracWall', version=1, wall=dict(x0=0, x1=96, openings=[dict(x0=90, x1=120, z0=0, z1=10)]))):
            with self.assertRaises(ValueError):
                frac_walls.check(bad)

    def test_a_walls_local_box_is_its_ends_and_the_recipes_section(self):
        self.assertEqual(frac_walls.local_box(dict(x0=0.0, x1=384.0)), [0.0, 384.0, -12.0, 12.0, -16.0, 384.0])


@unittest.skipUnless(BAR.exists(), NO_BAR)
class Built(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import native_copy
        from package import Package
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name)
        cls.m = native_copy.build(BAR, out, 'FracPoc', [dict(c) for c in COPIES])
        cls.q = Package(out / 'FracPoc.upk')
        cls.p = Package(BAR)
        cls.walls = cls.m['nativeCopies']['generatedWalls']
        # (the manifest lists the copies in the order asked)
        cls.copies = dict(zip((c['label'] for c in COPIES), cls.m['nativeCopies']['copies']))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def made(self):
        return [w for w in self.walls if w['kind'] == 'fracWall']

    def test_the_manifest_names_each_wall(self):
        self.assertEqual([(w['kind'], w['label']) for w in self.walls],
                         [('relit', 'Reference'), ('fracWall', 'Twin'), ('fracWall', 'Custom')])
        twin, custom = self.made()
        self.assertEqual((twin['fragments'], twin['solids'], custom['fragments'], custom['solids']), (30, 1, 27, 3))
        self.assertTrue(twin['painted'] and custom['painted'])
        self.assertEqual([c.get('generated') for c in self.m['nativeCopies']['copies']], ['relit', 'fracWall', 'fracWall'])

    def test_the_reference_keeps_the_donors_mesh(self):
        q = self.q
        actor = q.by_name[PL + self.walls[0]['copy']]
        comp = q.own(actor, 'FracturedStaticMeshComponent')
        self.assertEqual(q.name(q.own(comp, 'StaticMesh')), frac_wall.RECIPE['donor'])

    def test_the_new_meshes_are_written_whole_under_our_package(self):
        q = self.q
        for w in self.made():
            mesh = q.by_name[w['mesh']]
            self.assertEqual(q.cls(mesh), 'FracturedStaticMesh')
            self.assertTrue(w['mesh'].startswith(frac_walls.PACKAGE + '.FracWall_'))
            m = gen_mesh.read(q, mesh)
            e = q.exports[mesh - 1]
            self.assertEqual(gen_mesh.write(m, m['at']), bytes(q.data[m['at']:e['off'] + e['size']]))
            self.assertEqual(q.cls(m['bodySetup']), 'RB_BodySetup')
            self.assertEqual(len(m['fractured']['fragments']), w['fragments'])

    def test_each_component_saves_its_numbers_as_the_games_walls_do(self):
        q = self.q
        for w in self.made():
            actor = q.by_name[PL + w['copy']]
            comp = q.own(actor, 'FracturedStaticMeshComponent')
            mesh = q.own(comp, 'StaticMesh')
            self.assertEqual(q.name(mesh), w['mesh'])
            m = gen_mesh.read(q, mesh)
            lod = m['lods'][0]
            self.assertEqual(q.own(comp, 'NumResourceIndices'), len(lod['indices'][1]))
            world = lightmap_texels.world_matrix(q, comp)
            pos = np.array(lod['positions'], float)
            z = (np.c_[pos, np.ones(len(pos))] @ world.T)[:, 2]
            self.assertAlmostEqual(q.own(comp, 'FragmentBoundsMinZ'), z.min(), 3)
            self.assertAlmostEqual(q.own(comp, 'FragmentBoundsMaxZ'), z.max(), 3)
            # one painted colour for each new vertex
            flag, _ = frac_walls._lod_colours(q.data, q.properties(comp)[1])
            self.assertEqual(q.data[flag], 1)
            self.assertEqual(struct.unpack_from('<2I', q.data, flag + 1), (4, len(pos)))

    def test_the_columns_list_the_fragments_over_them(self):
        q = self.q
        for w in self.made():
            actor = q.by_name[PL + w['copy']]
            comp = q.own(actor, 'FracturedStaticMeshComponent')
            m = gen_mesh.read(q, q.own(comp, 'StaticMesh'))
            world = lightmap_texels.world_matrix(q, comp)
            lod = m['lods'][0]
            pos = np.array(lod['positions'], float)
            wpos = (np.c_[pos, np.ones(len(pos))] @ world.T)[:, :3]
            idx = lod['indices'][1]
            points = {}
            for s in lod['sections']:
                for f, (first, n) in enumerate(s['fragments']):
                    points.setdefault(f, set()).update(idx[first:first + 3 * n])
            fbox = {f: [v for k in range(3) for v in (wpos[sorted(vs), k].min(), wpos[sorted(vs), k].max())]
                    for f, vs in points.items() if vs}
            cols = q.structs(q.own(actor, 'FragmentColumns'))
            self.assertEqual(len(cols), w['columns'])
            for c in cols:
                b = struct.unpack('<6fB', c[('Bounds', 0)]['value'])
                box = [b[0], b[3], b[1], b[4], b[2], b[5]]
                saved = [(it.get(('FragIndex', 0), {}).get('value', 0), it.get(('MinZ', 0), {}).get('value', 0.0))
                         for it in q.structs(c.get(('FragCache', 0), {}).get('value'))]
                self.assertEqual({f for f, _ in saved}, {f for f, fb in fbox.items() if overlap(fb, box)})
                self.assertEqual([z for _, z in saved], sorted(z for _, z in saved))
                for f, z in saved:
                    self.assertAlmostEqual(z, fbox[f][4], 3)
                self.assertEqual(q.structs(c.get(('DestructibleCache', 0), {}).get('value')), [])

    def test_the_tiles_are_seeded_over_each_walls_own_box(self):
        ref, twin, custom = (self.copies[k]['tiles']['tiles'] for k in ('Reference', 'Twin', 'Custom'))
        self.assertEqual(twin[0] - ref[0], 8)               # the twin is the reference's box, eight tiles east
        self.assertEqual(twin[1] - twin[0], ref[1] - ref[0])
        self.assertLess(custom[1] - custom[0], twin[1] - twin[0])   # the custom wall is shorter than the donor


if __name__ == '__main__':
    unittest.main()

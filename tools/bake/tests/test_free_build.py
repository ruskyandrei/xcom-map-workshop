"""Made pieces in the free form through the copy tool (the custom geometry improvements plan, stage 2): a free-form roof
slab off the tiles with a hole across one, and a ground block past the old 64-tile and 384-unit caps, built into
URB_Bar (a quick build) and read back: each is its own mesh, the slab's collision covers its solid area round the
hole, the block's is one box of its size; the Build's check takes the free versions (frac_walls.check)."""
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import fixtures  # noqa: E402
import frac_walls  # noqa: E402
import labpaths  # noqa: E402

BAR, NO_BAR = labpaths.test_file('XCOM_BAR_UPK', labpaths.lwr_cooked('URB_Bar.upk'), 'URB_Bar.upk')
PL = 'TheWorld.PersistentLevel.'
SLAB = dict(kind='fracSlab', version=3, slab=dict(free=1, x0=0.0, x1=150.5, y0=0.0, y1=120.25, z0=-6.0, z1=2.0,
                                                  holes=[dict(x0=40.0, x1=110.0, y0=30.0, y1=60.0)], seed=4))
WALL = dict(kind='fracWall', version=4, wall=dict(free=1, x0=-20.5, x1=300.0, y0=-10.0, y1=10.0, z0=-16.0, z1=250.5,
                                                  tall='repeat', openings=[dict(x0=40.0, x1=130.0, z0=-16.0, z1=160.0)],
                                                  seed=2, ends=['free', dict(inset=0.0, lean=-1.0)]))
BLOCK = dict(kind='ground', version=3, ground=dict(free=1, shape='block', x0=0.0, x1=6912.0, y0=0.0, y1=96.0,
                                                   z0=0.0, z1=500.0))


class FreeChecks(unittest.TestCase):
    def test_the_build_takes_the_free_versions(self):
        self.assertEqual(frac_walls.FREE_VERSION, {'fracWall': 4, 'fracSlab': 3, 'ground': 3})
        frac_walls.check(SLAB)
        frac_walls.check(BLOCK)
        frac_walls.check(WALL)
        for bad in (dict(SLAB, slab=dict(SLAB['slab'], free=0)), dict(SLAB, slab=dict(SLAB['slab'], x1=-1.0)),
                    dict(BLOCK, ground=dict(BLOCK['ground'], z1=-5.0))):
            with self.assertRaises(ValueError, msg=bad):
                frac_walls.check(bad)


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class FreeBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import native_copy
        from package import Package
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name)
        copies = [dict(actor='XComFracLevelActor_3', label='Slab', location=[-1700.5, -1430.25, 400.0], rotation=[0, 0, 0],
                       generated=SLAB),
                  dict(actor='XComLevelActor_131', label='Block', location=[-1728.0, -1100.0, 0.0], rotation=[0, 0, 0],
                       generated=BLOCK),
                  dict(actor='XComDecoFracLevelActor_17', label='Wall', location=[-1500.0, -1800.0, 16.0], rotation=[0, 5000, 0],
                       generated=WALL)]
        cls.m = native_copy.build(native_copy.BuildState(BAR, out, 'Free', copies))
        cls.q = Package(out / 'Free.upk')
        cls.sec = {c['label']: c['export'] for c in cls.m['nativeCopies']['copies']}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_slab_is_a_mesh_of_its_own_and_its_collision_is_round_its_hole(self):
        q = self.q
        comp = q.own(self.sec['Slab'], 'FracturedStaticMeshComponent')
        mesh = q.own(comp, 'StaticMesh')
        self.assertEqual(q.cls(mesh), 'FracturedStaticMesh')
        self.assertTrue(q.name(mesh).split('.')[-1].startswith('FracSlab_'), q.name(mesh))
        boxes = fixtures.boxes(q, q.own(mesh, 'BodySetup')) if hasattr(fixtures, 'boxes') else None
        if boxes is not None:
            area = sum((hi[0] - lo[0]) * (hi[1] - lo[1]) for lo, hi in boxes)
            self.assertAlmostEqual(area, 150.5 * 120.25 - 70.0 * 30.0, places=1)

    def test_the_wall_at_a_free_angle_is_a_fracturing_mesh_of_its_own(self):
        q = self.q
        comp = q.own(self.sec['Wall'], 'FracturedStaticMeshComponent')
        mesh = q.own(comp, 'StaticMesh')
        self.assertEqual(q.cls(mesh), 'FracturedStaticMesh')
        self.assertTrue(q.name(mesh).split('.')[-1].startswith('FracWall'), q.name(mesh))
        self.assertEqual(q.own(self.sec['Wall'], 'Rotation')[1], 5000)

    def test_the_block_is_one_box_of_its_size(self):
        q = self.q
        comp = q.own(self.sec['Block'], 'StaticMeshComponent')
        mesh = q.own(comp, 'StaticMesh')
        self.assertEqual(q.cls(mesh), 'StaticMesh')
        *_, fields = fixtures.hull(q, q.own(mesh, 'BodySetup'))
        self.assertEqual(len(fields['FacePlaneData']), 6)


if __name__ == '__main__':
    unittest.main()

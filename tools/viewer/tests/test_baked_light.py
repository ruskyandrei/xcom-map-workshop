"""A piece's baked light read for the export (baked_light.py; game-likeness plan, B1, export 44): on URB_Bar of the
configured install, a lightmapped piece's two atlases, scales, UV rectangle and channel, and its shadow map of the
map's dominant light (skipped without it)."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import baked_light  # noqa: E402
from package import Package  # noqa: E402

sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402

BAR, NO_BAR = labpaths.test_file('XCOM_BAR_UPK', labpaths.lwr_cooked('URB_Bar.upk'), 'URB_Bar.upk')


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class OnTheInstall(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = Package(BAR)
        cls.guid = baked_light.dominant_guid(cls.p)
        cls.pieces = [i for i in range(1, len(cls.p.exports) + 1) if cls.p.cls(i) == 'StaticMeshComponent'
                      and cls.p.name(i).startswith('TheWorld.PersistentLevel.')]

    def test_the_dominant_light(self):
        self.assertRegex(self.guid or '', r'^[0-9a-f]{32}$')

    def test_lightmaps_and_sun_shadows(self):
        found = shadows = 0
        for ci in self.pieces[:300]:
            mesh = self.p.effective(ci, 'StaticMesh', 0)
            lm = baked_light.lightmap(self.p, ci, mesh)
            if lm:
                found += 1
                self.assertTrue(lm['colour'] > 0 and lm['directions'] > 0 and lm['colour'] != lm['directions'])
                self.assertEqual(self.p.cls(lm['colour']), 'LightMapTexture2D')
                self.assertEqual((len(lm['scale0']), len(lm['scale1']), len(lm['uvScale']), len(lm['uvBias'])), (3, 3, 2, 2))
                self.assertTrue(0 < lm['uvScale'][0] <= 1 and 0 <= lm['uvBias'][0] < 1, lm)
                self.assertIn(lm['channel'], (0, 1, 2, 3))
            sm = baked_light.sun_shadow(self.p, ci, self.guid)
            if sm:
                shadows += 1
                self.assertEqual(self.p.cls(sm['texture']), 'ShadowMapTexture2D')
                self.assertFalse(sm['factor'])
        self.assertGreater(found, 100)
        self.assertGreater(shadows, 50)
        # a light that names no shadow map gives none
        self.assertIsNone(baked_light.sun_shadow(self.p, self.pieces[0], '0' * 32))
        self.assertIsNone(baked_light.sun_shadow(self.p, self.pieces[0], None))


if __name__ == '__main__':
    unittest.main()

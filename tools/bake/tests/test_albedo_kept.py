"""The bounce light's colours stay as they were when materials gained their programs (game-likeness plan A-S3,
decision M4): the bake's albedo resolves materials through a subclass of the viewer's exporter, which makes no
programs, so four of the Bar's materials keep the albedo they had before (worked out on main the day the programs
came in, 27 November 2026)."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'viewer'))
sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402

BAR, NO_BAR = labpaths.test_file('XCOM_BAR_UPK', labpaths.lwr_cooked('URB_Bar.upk'), 'URB_Bar.upk')
KEPT = {
    'SidewalkAtlased.Materials.SidewalkAtlased': [0.308756, 0.289968, 0.253642],
    'TexLibrary_Roof.Materials.Roof_Asphalt-Gravel_BLEND': [0.029212, 0.027907, 0.018683],
    'TexLibrary_Floor.Materials.Floor_ButcherTileB': [0.050073, 0.046764, 0.040969],
    'MidgroundBuilding.Materials.MidgroundBuildingIndusB': [0.34034, 0.269116, 0.180674],
}


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class AlbedoKept(unittest.TestCase):
    def test_four_materials_keep_their_albedo(self):
        import albedo
        from package import Package
        p = Package(BAR)
        a = albedo.Albedo(p)
        self.assertIsNone(a.resolver.programs)
        for name, value in KEPT.items():
            got = [round(float(x), 6) for x in a(p.by_name[name])]
            self.assertEqual(got, value, name)
            record = a.resolver.materials[a.resolver.material(p.by_name[name])]
            self.assertNotIn('program', record)


if __name__ == '__main__':
    unittest.main()

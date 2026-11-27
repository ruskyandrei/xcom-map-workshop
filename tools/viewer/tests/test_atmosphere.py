"""A map's atmosphere (atmosphere.py, export 43): a made-up WorldInfo's saved members over the defaults; on the
install, the defaults file as the script packages give it, and the values F-168 lists (the Bar's colour grade, Dirt
Road's four fog members and its post-process volume)."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import atmosphere  # noqa: E402
from package import Package  # noqa: E402

sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402

COOKED = labpaths.lwr_cooked()
ENGINE, NO_ENGINE = labpaths.test_file('XCOM_ENGINE_UPK', labpaths.lwr_cooked('Engine.upk'), 'Engine.upk')
BAR, NO_BAR = labpaths.test_file('XCOM_BAR_UPK', labpaths.lwr_cooked('URB_Bar.upk'), 'URB_Bar.upk')
ROAD, NO_ROAD = labpaths.test_file('XCOM_DIRTROAD_UPK', labpaths.lwr_cooked('CSmallScout_DirtRoad.upk'),
                                   'CSmallScout_DirtRoad.upk')


class Fake:
    """A package of one WorldInfo whose fog saves two members."""
    paths = ['TheWorld.PersistentLevel.WorldInfo_0']
    exports = [{}]

    def cls(self, index):
        return 'WorldInfo'

    def own(self, index, key, default=None):
        return {'XComHeightFog': b'fog'}.get(key, default)

    def effective(self, index, key, default=None):
        return default

    def tagged(self, reader):
        assert bytes(reader.data) == b'fog'
        return {('bEnabled', 0): {'kind': 'BoolProperty', 'value': True},
                ('OppositeLightColor', 0): {'kind': 'StructProperty', 'value': [0.2, 0.25, 0.4, 1.0]}}

    def name(self, index):
        return 'x'


class MadeUp(unittest.TestCase):
    def test_saved_members_over_the_defaults(self):
        defaults = {'world': {'fog': {'bEnabled': False, 'FogDensity': 0.02, 'OppositeLightColor': [0, 0, 0, 0]},
                              'postProcess': {'Scene_Colorize': [1, 1, 1]}}}
        out = atmosphere.read(Fake(), defaults)['world']
        self.assertEqual(out['fog'], {'bEnabled': True, 'FogDensity': 0.02, 'OppositeLightColor': [0.2, 0.25, 0.4, 1.0]})
        self.assertEqual(out['saved'], {'fog': ['OppositeLightColor', 'bEnabled'], 'postProcess': []})
        self.assertEqual(out['postProcess'], {'Scene_Colorize': [1, 1, 1]})


class Defaults(unittest.TestCase):
    def test_the_file_reads(self):
        d = atmosphere.load_defaults()
        self.assertEqual(d['structs']['postProcess']['Scene_Colorize'], [1.0, 1.0, 1.0])
        self.assertEqual(d['world']['fog']['FogHeight'], 1000.0)          # Default__WorldInfo's, over the struct's 0

    @unittest.skipUnless(ENGINE and ENGINE.exists(), NO_ENGINE)
    def test_the_file_is_what_the_script_packages_say(self):
        self.assertEqual(atmosphere.make_defaults(ENGINE.parent), atmosphere.load_defaults())


class Install(unittest.TestCase):
    @unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
    def test_the_bars_grade(self):
        world = atmosphere.read(Package(BAR))['world']
        self.assertEqual(world['postProcess']['Scene_Colorize'], [1.0, 1.0, 1.2])
        self.assertIn('Scene_Colorize', world['saved']['postProcess'])

    @unittest.skipUnless(ROAD and ROAD.exists(), NO_ROAD)
    def test_dirt_roads_fog_and_volume(self):
        out = atmosphere.read(Package(ROAD))
        self.assertEqual(out['world']['saved']['fog'],
                         ['FogHeightFalloff', 'LightInscatteringColor', 'OppositeLightColor', 'bEnabled'])
        self.assertTrue(out['world']['fog']['bEnabled'])
        volume, = out['volumes']
        self.assertEqual(volume['settings']['Scene_Colorize'], [1.2, 1.2, 1.2])
        self.assertEqual(volume['settings']['Bloom_Scale'], 0.5)
        self.assertLess(volume['box']['min'][0], volume['box']['max'][0])


class Catalogue(unittest.TestCase):
    """atmospheres.json (the Map settings window's "Take the look of"): made by `atmosphere.py catalogue` from the
    install; each look a set of values its maps share, every map in one look."""

    def test_the_file_reads(self):
        looks = atmosphere.load_catalogue()['looks']
        maps = [m['map'] for look in looks for m in look['maps']]
        self.assertGreater(len(looks), 10)
        self.assertEqual(len(maps), len(set(maps)))
        for look in looks:
            self.assertEqual(set(look['postProcess']), set(atmosphere.LOOK_POST))
            self.assertTrue({'FogDensity', 'OppositeLightColor', 'bEnabled'} <= set(look['fog']))

    @unittest.skipUnless(BAR and BAR.exists() and ROAD and ROAD.exists(), NO_BAR or NO_ROAD)
    def test_a_maps_look_is_what_its_package_says(self):
        # (the whole file takes a minute to make again: two maps' looks are read again here)
        looks = atmosphere.load_catalogue()['looks']
        for name, path in (('URB_Bar', BAR), ('CSmallScout_DirtRoad', ROAD)):
            look = next(l for l in looks if any(m['map'] == name for m in l['maps']))
            world = atmosphere.read(Package(path))['world']
            self.assertEqual(look['fog'], world['fog'], name)
            self.assertEqual(look['postProcess'], {k: world['postProcess'][k] for k in atmosphere.LOOK_POST}, name)


if __name__ == '__main__':
    unittest.main()

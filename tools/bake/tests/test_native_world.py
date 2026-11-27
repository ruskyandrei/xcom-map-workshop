"""The map's atmosphere written on its WorldInfo (native_world.py; game-likeness plan, C5): the members a project changes
of the height fog and the post-process settings put over those the map saves, the rest left to the defaults; read back
by the export's reader (tools/viewer/atmosphere.py). On CSmallScout_DirtRoad of the configured install, whose fog saves
four members and no density (skipped without it)."""
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(TOOLS / 'upk'))
sys.path.insert(0, str(TOOLS / 'viewer'))
sys.path.insert(0, str(TOOLS / 'lab'))
import labpaths  # noqa: E402
import atmosphere  # noqa: E402
import lighting_records as lighting  # noqa: E402
import native_world  # noqa: E402
import package_grow  # noqa: E402
from package import Package  # noqa: E402

ROAD, NO_ROAD = labpaths.install_map('CSmallScout_DirtRoad')
LANE = {'fog': {'FogDensity': 0.6, 'OppositeLightColor': [0.85, 0.08, 0.06, 1.0], 'bEnabled': True},
        'postProcess': {'Scene_Colorize': [0.6, 1.4, 0.6], 'Scene_Desaturation': 0.25, 'bEnableBloom': False}}


class Rules(unittest.TestCase):
    def test_a_member_goes_with_its_override_flag(self):
        kinds = native_world.member_kinds()['postProcess']
        self.assertEqual(atmosphere.override_flag('Scene_Colorize', kinds), 'bOverride_Scene_Colorize')
        self.assertEqual(atmosphere.override_flag('bEnableBloom', kinds), 'bOverride_EnableBloom')
        self.assertEqual(atmosphere.override_flag('XComFogOfWarColor', kinds), 'bOverrideXComFOWColor')
        self.assertIsNone(atmosphere.override_flag('bOverride_Scene_Colorize', kinds))

    def test_values_in_the_export_form_become_the_saved_bytes(self):
        class G:
            names = ['None', 'EFocusType', 'FOCUS_Distance']

            def name(self, text):
                return self.names.index(text)
        g = G()
        self.assertEqual(native_world.value_bytes(g, 'C', 'StructProperty', 'Color', [1.0, 0.5, 0.0, 1.0])[2],
                         bytes([0, 128, 255, 255]))                              # B G R A
        self.assertEqual(len(native_world.value_bytes(g, 'V', 'StructProperty', 'Vector', [1, 2, 3])[2]), 12)
        self.assertEqual(len(native_world.value_bytes(g, 'L', 'StructProperty', 'LinearColor', [1, 2, 3, 4])[2]), 16)
        self.assertEqual(native_world.value_bytes(g, 'b', 'BoolProperty', None, True)[2], b'\x01')
        self.assertEqual(native_world.value_bytes(g, 'DOF_FocusType', 'ByteProperty', None, 'FOCUS_Distance')[1], 'EFocusType')
        for bad in (('f', 'FloatProperty', None, 'x'), ('f', 'FloatProperty', None, float('nan')),
                    ('b', 'BoolProperty', None, 1), ('v', 'StructProperty', 'Vector', [1, 2]),
                    ('o', 'ObjectProperty', None, 3)):
            with self.assertRaises(native_world.AtmosphereError):
                native_world.value_bytes(g, *bad)

    def test_no_lane_writes_nothing(self):
        self.assertIsNone(native_world.apply(None, None, None))
        self.assertIsNone(native_world.apply(None, None, {'fog': {}}))


@unittest.skipUnless(ROAD and ROAD.exists(), NO_ROAD)
class OnTheInstall(unittest.TestCase):
    def write(self, lane):
        p = lighting.Package(ROAD)
        g = package_grow.Grower(str(ROAD))
        record = native_world.apply(g, p, lane)
        out = Path(self.tmp.name) / 'road.upk'
        g.write(str(out))
        return record, Package(out)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_changed_members_over_the_saved_and_the_rest_as_before(self):
        before = atmosphere.read(Package(ROAD))['world']
        record, q = self.write(LANE)
        native_world.read_back(q, record, LANE)
        after = atmosphere.read(q)['world']
        # the fog: the density added (the map saved none), the colour changed in place, the map's other members kept
        self.assertEqual(record['fog']['added'], ['FogDensity'])
        self.assertAlmostEqual(after['fog']['FogDensity'], 0.6, places=5)
        self.assertEqual(after['fog']['FogHeightFalloff'], before['fog']['FogHeightFalloff'])
        self.assertEqual(after['fog']['LightInscatteringColor'], before['fog']['LightInscatteringColor'])
        self.assertEqual(sorted(set(after['saved']['fog']) - set(before['saved']['fog'])), ['FogDensity'])
        # the post-process settings: each member with its flag on; what the project left alone is the map's
        pp = after['postProcess']
        self.assertEqual(pp['Scene_Colorize'], [0.6, 1.4, 0.6])
        self.assertTrue(pp['bOverride_Scene_Colorize'] and pp['bOverride_Scene_Desaturation'] and pp['bOverride_EnableBloom'])
        self.assertFalse(pp['bEnableBloom'])
        for name in ('Scene_Shadows', 'Bloom_Scale', 'DOF_BlurBloomKernelSize', 'XComFogOfWarColor'):
            self.assertEqual(pp[name], before['postProcess'][name], name)
        # nothing else of the map: its volumes as they were
        self.assertEqual(atmosphere.read(q)['volumes'], atmosphere.read(Package(ROAD))['volumes'])

    def test_a_member_the_struct_lacks_changes_nothing(self):
        p = lighting.Package(ROAD)
        g = package_grow.Grower(str(ROAD))
        wi = native_world.world_info(p)
        data = bytes(g.export_data(wi))
        with self.assertRaises(native_world.AtmosphereError):
            native_world.apply(g, p, {'fog': {'FogDensity': 0.5, 'Nonsense': 1.0}})
        self.assertEqual(bytes(g.export_data(wi)), data)


if __name__ == '__main__':
    unittest.main()

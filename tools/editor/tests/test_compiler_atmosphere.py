"""The map's fog and post-process members a project changes, in the compiler (game-likeness plan, C5;
atmosphere_edits.py): held to their members' kinds (tools/viewer/atmosphere_defaults.json), the rest left out; the
native edit's `atmosphere` lane; a warning where a post-process volume of the map overrides a changed member. A made-up
scene: no install needed."""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from compiler import compile_project, native_split, stream_only  # noqa: E402
from editor_fixtures import document, scene  # noqa: E402

RED = [0.85, 0.08, 0.06, 1.0]


def codes(entries):
    return sorted(e['code'] for e in entries)


class Atmosphere(unittest.TestCase):
    def build(self, atmosphere, volumes=None):
        s = scene()
        s['atmosphere'] = dict(world=dict(fog={}, postProcess={}), volumes=volumes or [])
        spec, report = compile_project(document([], atmosphere=atmosphere), s)
        native = native_split(stream_only(spec))[1] if spec else None
        return report, native

    def test_the_members_go_to_the_lane(self):
        record = dict(fog=dict(FogDensity=0.6, OppositeLightColor=RED, bEnabled=True),
                      postProcess=dict(Scene_Colorize=[0.6, 1.4, 0.6], DOF_FocusType='FOCUS_Distance'))
        report, native = self.build(record)
        self.assertTrue(report['ok'], report['errors'])
        self.assertEqual(native['atmosphere'], dict(fog=dict(FogDensity=0.6, OppositeLightColor=RED, bEnabled=True),
                                                   postProcess=dict(Scene_Colorize=[0.6, 1.4, 0.6],
                                                                    DOF_FocusType='FOCUS_Distance')))
        self.assertEqual(report['atmosphere'], dict(fog=3, postProcess=2))
        self.assertEqual(report['leftOut'], [])

    def test_what_cant_be_had_is_left_out_and_the_rest_builds(self):
        record = dict(fog=dict(FogDensity='thick', FogHeight=500, Nonsense=1, OppositeLightColor=[2, 0, 0, 1]),
                      postProcess=dict(ColorGrading_LookupTable=None, Scene_Shadows=[0, 0], bEnableBloom=1,
                                       Bloom_Scale=0.25))
        report, native = self.build(record)
        self.assertTrue(report['ok'], report['errors'])
        self.assertEqual(native['atmosphere'], dict(fog=dict(FogHeight=500.0), postProcess=dict(Bloom_Scale=0.25)))
        self.assertEqual(codes(report['leftOut']), ['atmosphere-value'] * 6)
        self.assertIn('fog.Nonsense', {e.get('member') for e in report['leftOut']})

    def test_a_record_of_another_shape_is_left_out(self):
        for bad in ([1], dict(fog=[1]), dict(sky={})):
            report, native = self.build(bad)
            self.assertEqual(codes(report['leftOut']), ['atmosphere-shape'], bad)
            self.assertNotIn('atmosphere', native or {})

    def test_nothing_changed_is_no_lane(self):
        report, native = self.build(dict(fog={}, postProcess={}))
        self.assertNotIn('atmosphere', native or {})
        self.assertNotIn('atmosphere', report)

    def test_a_volume_that_overrides_a_changed_member_is_warned_of(self):
        volumes = [dict(name='PostProcessVolume_1', enabled=True, settings=dict(bOverride_Scene_Colorize=True,
                                                                               Scene_Colorize=[1.2, 1.2, 1.2])),
                   dict(name='PostProcessVolume_2', enabled=False, settings=dict(bOverride_Scene_Colorize=True)),
                   dict(name='PostProcessVolume_3', enabled=True, settings=dict(Scene_Colorize=[2, 2, 2]))]
        report, native = self.build(dict(postProcess=dict(Scene_Colorize=[0.6, 1.4, 0.6])), volumes)
        self.assertEqual(codes(report['warnings']), ['atmosphere-volume'])
        self.assertEqual(report['warnings'][0]['volume'], 'PostProcessVolume_1')
        self.assertIn('atmosphere', native)          # (a warning, never a refusal)


if __name__ == '__main__':
    unittest.main()

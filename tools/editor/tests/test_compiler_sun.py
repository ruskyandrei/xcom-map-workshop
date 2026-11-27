"""The project's time of day (`sun`, schema 10; the game-likeness plan, T-S1 and T-S2) in the compiler
(light_edits.sun_mark): its shape (tools/viewer/sun_curve.py's `problem`, on the record cases the page's node test
reads too), the native edit's `sun` lane (the dominant light and sky light by their short names, the record's values,
whether the direction changed), the report's `sun` (the records' TimeOfDay), the warnings (a map with no sun or moon,
no sky light, a second directional light) and the quick Build's (light_edits.stale_sun); a record of another shape is
left out. A made-up scene: no install needed."""
import copy
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from compiler import compile_project, light_rule, native_split, stale_sun, stream_only  # noqa: E402
from editor_fixtures import PL, document, scene  # noqa: E402

CASES = HERE.parents[1] / 'viewer' / 'tests' / 'sun_record_cases.json'
# URB_Bar's moon and sky light as its export has them
SUN = dict(id='light:634', actor=PL + 'DominantDirectionalLight_1',
           component=PL + 'DominantDirectionalLight_1.DominantDirectionalLightComponent_0',
           actorClass='DominantDirectionalLight', componentClass='DominantDirectionalLightComponent', layer='base',
           kind='directional', role='dominant', rotation=[-14697, -41323, -27675],
           color=[66 / 255, 69 / 255, 136 / 255], brightness=1.1, lightmapGuid='d' * 32, bakedInto=[])
SKY = dict(id='light:8435', actor=PL + 'SkyLight_0', component=PL + 'SkyLight_0.SkyLightComponent_263',
           actorClass='SkyLight', componentClass='SkyLightComponent', layer='base', kind='sky', role='sky',
           rotation=[0, 0, 0], color=[89 / 255, 107 / 255, 160 / 255], brightness=0.75,
           lowerColor=[1.0, 203 / 255, 162 / 255], lowerBrightness=0.01, lightmapGuid='e' * 32, bakedInto=[])
SECOND = dict(SUN, id='light:9', actor=PL + 'DirectionalLight_0',
              component=PL + 'DirectionalLight_0.DirectionalLightComponent_0', actorClass='DirectionalLight',
              componentClass='DirectionalLightComponent', role='static')
# noon on Bar: the curve's 13:00, the sun turned (sun_record_cases.json's first record)
NOON = dict(time=13, heading=313.02, timeOfDay='auto',
            light=dict(rotation=[-10194, 24213, -27675], color=[255, 245, 215], brightness=1.1),
            sky=dict(color=[150, 150, 170], brightness=0.6, lowerColor=[255, 224, 173], lowerBrightness=0.01))


def codes(entries):
    return sorted(e['code'] for e in entries)


def lit(*lights):
    s = scene()
    s['lights'] = [copy.deepcopy(l) for l in lights]
    return s


class Sun(unittest.TestCase):
    def build(self, sun, *lights):
        spec, report = compile_project(document([], schemaVersion=10, sun=sun), lit(*lights) if lights else scene())
        native = native_split(stream_only(spec))[1] if spec else None
        return spec, report, native

    def test_the_record_cases(self):
        for case in json.loads(CASES.read_text(encoding='utf-8'))['cases']:
            with self.subTest(case['why']):
                spec, report, native = self.build(case['record'], SUN, SKY)
                self.assertTrue(report['ok'], report['errors'])
                if case['valid']:
                    self.assertEqual(report['leftOut'], [])
                    self.assertIn('sun', native)
                    self.assertEqual(report['sun']['directionChanged'], native['sun']['directionChanged'])
                else:
                    self.assertEqual(codes(report['leftOut']), ['sun-shape'])
                    self.assertNotIn('sun', spec or {})
                    self.assertNotIn('sun', native or {})
                    self.assertNotIn('sun', report)

    def test_the_lane_has_the_lights_and_the_records_values(self):
        spec, report, native = self.build(NOON, SUN, SKY)
        self.assertEqual(native['sun'], dict(
            actor='DominantDirectionalLight_1', component='DominantDirectionalLight_1.DominantDirectionalLightComponent_0',
            rotation=[-10194, 24213, -27675], color=[255, 245, 215], brightness=1.1, directionChanged=True,
            sky=dict(actor='SkyLight_0', component='SkyLight_0.SkyLightComponent_263', color=[150, 150, 170],
                     brightness=0.6, lowerColor=[255, 224, 173], lowerBrightness=0.01)))
        self.assertEqual(report['sun'], dict(time='13:00', timeOfDay='eMissionTime_Day', directionChanged=True, sky=True))
        # nothing to warn of on a map with one sun or moon and a sky light; the compiler does not know the Build's kind
        self.assertEqual(report['warnings'], [])
        self.assertEqual(report['notes'], [])
        # the spec's own key, which native_split takes out of what a patch would do
        self.assertIn('sun', spec)
        self.assertNotIn('sun', native_split(stream_only(spec))[0])

    def test_the_maps_own_direction_is_kept(self):
        """A rotation within two units of the map's own is its own (the page's rule): written as the map has it."""
        record = copy.deepcopy(NOON)
        record['light']['rotation'] = [-14697 + 2, -41323 + 65536 - 1, -27675]
        spec, report, native = self.build(record, SUN, SKY)
        self.assertEqual(native['sun']['rotation'], [-14697, -41323, -27675])
        self.assertFalse(native['sun']['directionChanged'])
        self.assertFalse(report['sun']['directionChanged'])
        record['light']['rotation'] = [-14697 + 3, -41323, -27675]
        self.assertTrue(self.build(record, SUN, SKY)[2]['sun']['directionChanged'])

    def test_the_game_time(self):
        """auto follows the light (night while the moon is up), day and night are as set: the records' TimeOfDay."""
        for time, of_day, want in ((13, 'auto', 'eMissionTime_Day'), (1, 'auto', 'eMissionTime_Night'),
                                   (21, 'auto', 'eMissionTime_Night'), (13, 'night', 'eMissionTime_Night'),
                                   (1, 'day', 'eMissionTime_Day')):
            with self.subTest(time=time, timeOfDay=of_day):
                record = dict(NOON, time=time, timeOfDay=of_day)
                self.assertEqual(self.build(record, SUN, SKY)[1]['sun']['timeOfDay'], want)

    def test_a_map_with_no_sun_or_moon_passes_the_record_over(self):
        spec, report, native = self.build(NOON, SKY)
        self.assertEqual(codes(report['warnings']), ['sun-no-light'])
        self.assertIn('13:00', report['warnings'][0]['message'])
        self.assertNotIn('sun', native)
        self.assertNotIn('sun', report)
        # (a streamed level's dominant light is not the map's: the Build writes the base map)
        streamed = dict(SUN, layer='inherited')
        self.assertEqual(codes(self.build(NOON, streamed, SKY)[1]['warnings']), ['sun-no-light'])

    def test_a_map_without_a_sky_light_sets_the_sun_alone(self):
        spec, report, native = self.build(NOON, SUN)
        self.assertEqual(codes(report['warnings']), ['sun-no-sky'])
        self.assertIsNone(native['sun']['sky'])
        self.assertFalse(report['sun']['sky'])
        # a record without a sky light on a map with one: the map's sky light stays
        record = {k: v for k, v in NOON.items() if k != 'sky'}
        spec, report, native = self.build(record, SUN, SKY)
        self.assertIsNone(native['sun']['sky'])
        self.assertEqual(report['warnings'], [])

    def test_a_second_directional_light_is_left_as_it_is(self):
        spec, report, native = self.build(NOON, SECOND, SUN, SKY)
        self.assertEqual(codes(report['warnings']), ['sun-second-light'])
        self.assertEqual(report['warnings'][0]['lights'], ['DirectionalLight_0'])
        self.assertEqual(native['sun']['actor'], 'DominantDirectionalLight_1')

    def test_a_quick_builds_warning_for_a_turned_sun(self):
        spec, report, native = self.build(NOON, SUN, SKY)
        stale_sun(report)
        self.assertEqual(codes(report['warnings']), ['sun-shadows-stale'])
        self.assertEqual(report['counts']['warnings'], 1)
        self.assertIn('13:00', report['warnings'][0]['message'])
        # the direction kept: nothing to say
        record = copy.deepcopy(NOON)
        record['light']['rotation'] = list(SUN['rotation'])
        report = self.build(record, SUN, SKY)[1]
        self.assertEqual(stale_sun(report)['warnings'], [])
        # no time of day at all
        report = self.build(None, SUN, SKY)[1]
        self.assertEqual(stale_sun(report)['warnings'], [])

    def test_no_record_says_nothing(self):
        spec, report, native = self.build(None, SUN, SKY)
        self.assertNotIn('sun', native or {})
        self.assertNotIn('sun', report)
        self.assertEqual(report['leftOut'], [])

    def test_the_lights_verdicts_name_the_time_of_day(self):
        for light in (SUN, SKY):
            self.assertIn('Sun, moon and sky', light_rule(light))
        self.assertIn('leaves it', light_rule(SECOND))


if __name__ == '__main__':
    unittest.main()

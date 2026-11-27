"""The time of day's curve (sun_curve.json, sun_curve.py; the game-likeness plan, T-S1): its shape; each row taken from
a map of T-S0's survey is that map's light, sky light, fog and grade (research/evidence/sun-audit-2026-11-27.json,
F-175); the shape of the project's `sun` as the page reads it and the game's time of day a record says
(sun_record_cases.json, which sun_rules_test.mjs reads too); and the server's /sun-curve.json."""
from functools import partial
import json
import sys
import threading
import unittest
from pathlib import Path
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import sun_curve  # noqa: E402

SURVEY = HERE.parents[2] / 'research' / 'evidence' / 'sun-audit-2026-11-27.json'


class Curve(unittest.TestCase):
    def setUp(self):
        self.curve = sun_curve.load()

    def test_its_shape(self):
        c = self.curve
        self.assertEqual(sorted(ch['light'] for ch in c['changes']), ['moon', 'sun'])
        times = [r['time'] for r in c['rows']]
        self.assertEqual(times, sorted(times))
        self.assertTrue(all(0 <= t < 24 for t in times))
        for row in c['rows']:
            with self.subTest(time=row['time']):
                self.assertIn(row['light'], ('sun', 'moon'))
                for colour in (row['color'], row['sky']['color'], row['sky']['lowerColor'], *row['fog'].values()):
                    self.assertTrue(len(colour) == 3 and all(isinstance(v, int) and 0 <= v <= 255 for v in colour), colour)
                self.assertEqual(sorted(row['fog']), ['LightInscatteringColor', 'OppositeLightColor'])
                self.assertEqual(sorted(row['grade']), ['Scene_Colorize', 'Scene_Shadows'])
                self.assertTrue(0 < row['height'] <= 90 and 0 < row['brightness'] <= c['limits']['brightness'][1])
                # no sun higher than the survey's highest outdoors (55.9 degrees, F-175)
                if row['light'] == 'sun':
                    self.assertLessEqual(row['height'], 56)
        # each row lies in its light's time up (the sun from its change to the moon's)
        sun = next(ch['time'] for ch in c['changes'] if ch['light'] == 'sun')
        moon = next(ch['time'] for ch in c['changes'] if ch['light'] == 'moon')
        for row in c['rows']:
            self.assertEqual(row['light'], 'sun' if sun <= row['time'] < moon else 'moon', row['time'])

    @unittest.skipUnless(SURVEY.is_file(), 'the T-S0 survey evidence is not in this checkout')
    def test_rows_are_the_survey_maps(self):
        survey = {r['map']: r for r in json.loads(SURVEY.read_text(encoding='utf-8'))['maps']['summary']['rows']}
        checked = 0
        for row in self.curve['rows']:
            name = row['from'].split(':')[0].split(',')[0].strip()
            if name not in survey:
                continue
            m = survey[name]
            with self.subTest(time=row['time'], map=name):
                self.assertEqual(row['color'], m['light']['colour'])
                self.assertAlmostEqual(row['brightness'], m['light']['brightness'], places=4)
                self.assertAlmostEqual(row['height'], m['light']['height'], delta=0.01)
                sky, = m['sky']
                self.assertEqual((row['sky']['color'], row['sky']['brightness'], row['sky']['lowerColor']),
                                 (sky['colour'], sky['brightness'], sky['lower']))
                self.assertEqual(row['fog'], dict(LightInscatteringColor=m['fog']['inscattering'],
                                                  OppositeLightColor=m['fog']['opposite']))
                self.assertEqual(row['grade'], dict(Scene_Colorize=m['grade']['colorize'], Scene_Shadows=m['grade']['shadows']))
                checked += 1
        self.assertGreaterEqual(checked, 6)

    def test_the_skies_shape(self):
        domes = self.curve['domes']
        self.assertEqual([g['id'] for g in domes['groups']], ['day', 'low', 'night'])
        self.assertTrue(0 < domes['lowSun'] < 90)
        for g in domes['groups']:
            self.assertTrue(any(d['group'] == g['id'] for d in domes['list']), g)
        keys = [(d['map'], d['actor']) for d in domes['list']]
        self.assertEqual(len(keys), len(set(keys)))
        for d in domes['list']:
            self.assertTrue(sun_curve.dome_shape(dict(map=d['map'], actor=d['actor'])), d)
            self.assertTrue(d['material'].startswith('Skybox.Materials.') and d['label'], d)

    @unittest.skipUnless(SURVEY.is_file(), 'the T-S0 survey evidence is not in this checkout')
    def test_the_skies_are_the_survey_maps_domes(self):
        """Each sky the section offers is a shown sky dome of its map in T-S0's survey, drawn with its material."""
        maps = {m['map']: m for m in json.loads(SURVEY.read_text(encoding='utf-8'))['maps']['maps']}
        for d in self.curve['domes']['list']:
            with self.subTest(map=d['map'], actor=d['actor']):
                dome = next(s for s in maps[d['map']]['skyDomes'] if s['actor'] == d['actor'])
                self.assertEqual((dome['mesh'], dome['materials'], dome['hidden']), ('Skybox.Meshes.SkyDome', [d['material']], False))

    def test_the_records_shape(self):
        cases = json.loads((HERE / 'sun_record_cases.json').read_text(encoding='utf-8'))['cases']
        for case in cases:
            with self.subTest(case['why']):
                why = sun_curve.problem(case['record'], self.curve)
                self.assertEqual(why is None, case['valid'], why)

    def test_the_game_time_a_record_says(self):
        """auto follows the light (night while the moon is up), day and night are as set: the cases the page's
        sun_rules_test.mjs reads too (gameTime), which the Build writes as the records' TimeOfDay."""
        cases = json.loads((HERE / 'sun_record_cases.json').read_text(encoding='utf-8'))['gameTimes']
        for case in cases:
            with self.subTest(time=case['time'], timeOfDay=case['timeOfDay']):
                self.assertEqual(sun_curve.game_time(dict(time=case['time'], timeOfDay=case['timeOfDay']), self.curve),
                                 case['gameTime'])

    def test_the_route(self):
        from viewer import Handler, LocalServer
        server = LocalServer(('127.0.0.1', 0), partial(Handler, catalogue=dict(defaultMap=None, maps={})))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with urlopen(f'http://127.0.0.1:{server.server_port}/sun-curve.json') as r:
                self.assertEqual(r.status, 200)
                self.assertEqual(json.loads(r.read()), self.curve)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    unittest.main()

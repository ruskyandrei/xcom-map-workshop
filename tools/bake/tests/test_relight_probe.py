"""The relight probe (relight_probe.py, a research tool): its usage, and its report and replay on made-up records."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import relight_probe  # noqa: E402

PL = 'TheWorld.PersistentLevel.'


def rec(fn, wall, job=None, inside=(), **more):
    return dict(fn=fn, wall=wall, cpu=wall, job=job, inside=list(inside), pid=1, **more)


class Usage(unittest.TestCase):
    def test_help_prints_the_usage_of_its_three_commands(self):
        out = subprocess.run([sys.executable, '-B', str(HERE.parent / 'relight_probe.py'), '--help'],
                             capture_output=True, text=True, timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr)
        for line in ('relight_probe.py run --log <folder> -- <relight.py\'s arguments>',
                     'relight_probe.py report <folder>', 'relight_probe.py replay <folder>'):
            self.assertIn(line, out.stdout)

    def test_run_wants_the_relights_arguments(self):
        with self.assertRaises(SystemExit) as stop:
            relight_probe.main(['run', '--log', 'unused'])
        self.assertEqual(stop.exception.code, 2)


class ReportAndReplay(unittest.TestCase):
    """A made-up run: two workers, one piece whole, and a made piece's two shadow maps of the moon, the donor's on a
    large rectangle (slow) and its own on a small one."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = Path(self.tmp.name)
        own = dict(kind='shadow', path='XComLevelActor_474', fresh=True, copy=False, shadowMap='ShadowMap2D_7609')
        donor = dict(own, shadowMap='ShadowMap2D_4317')
        whole = dict(kind='whole', path='XComLevelActor_9', band=None, fresh=False, copy=False)
        worker1 = [rec('worker_start (map + both scenes)', 4.0),
                   rec('signed_distance', 7.0, donor, ['shadow_map_job', 'fresh_shadow_map']),
                   rec('fresh_shadow_map', 8.0, donor, ['shadow_map_job'], path='XComLevelActor_474',
                       shadowMap='ShadowMap2D_4317', rect=[1, 513, 183, 695], texels=182 * 182),
                   rec('shadow_map_job', 8.1, donor),
                   rec('JOB', 8.2, donor, reusedPrepared=False, error=None),
                   rec('MAIN', 12.0, exit=0)]
        worker2 = [rec('worker_start (map + both scenes)', 4.5),
                   rec('fresh_shadow_map', 0.3, own, ['shadow_map_job'], path='XComLevelActor_474',
                       shadowMap='ShadowMap2D_7609', rect=[0, 0, 128, 16], texels=128 * 16),
                   rec('JOB', 0.4, own, reusedPrepared=False, error=None),
                   rec('prepare_component', 1.0, whole, ['relight_component'], path='XComLevelActor_9', texels=100,
                       rect=120, mode='change'),
                   rec('relight_component', 2.0, whole, path='XComLevelActor_9'),
                   rec('JOB', 2.1, whole, reusedPrepared=False, error=None)]
        for pid, records in (('1', worker1), ('2', worker2)):
            (self.log / f'{pid}.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in records), encoding='utf-8')
        light = PL + 'DominantDirectionalLight_1.DominantDirectionalLightComponent_0'
        piece = PL + 'XComLevelActor_474.StaticMeshComponent_414'
        self.relit = dict(shadowMaps=[
            dict(component=piece, shadowMap=piece + '.ShadowMap2D_4317', light=light, rect=[1, 513, 183, 695],
                 fresh=True),
            dict(component=piece, shadowMap=piece + '.ShadowMap2D_7609', light=light, rect=[0, 0, 128, 16],
                 fresh=True)])

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_report_lists_each_shadow_map_with_its_seconds_slowest_first(self):
        s = relight_probe.summary(relight_probe.load(self.log))
        self.assertEqual([(m['path'], m['shadowMap'], m['texels']) for m in s['shadowMaps']],
                         [('XComLevelActor_474', 'ShadowMap2D_4317', 182 * 182),
                          ('XComLevelActor_474', 'ShadowMap2D_7609', 128 * 16)])
        self.assertEqual(s['shadowSummary']['maps'], 2)
        self.assertEqual(s['shadowSummary']['distanceCpu'], 7.0)
        self.assertEqual(s['jobs']['shadow']['count'], 2)
        self.assertEqual(s['workerStarts']['count'], 2)
        self.assertEqual(s['main']['exit'], 0)
        self.assertEqual(s['prepare'][0]['path'], 'XComLevelActor_9')
        self.assertTrue(any('ShadowMap2D_4317' in line for line in relight_probe.report_lines(s)))

    def test_replay_leaves_out_a_pieces_second_map_of_one_light(self):
        self.assertEqual(relight_probe.second_maps(self.relit), {('XComLevelActor_474', 'ShadowMap2D_4317')})
        r = relight_probe.replay(relight_probe.load(self.log), workers=1, relit=self.relit)
        self.assertEqual(r['asRun'], 10.7)
        self.assertEqual(r['noSecondMaps'], 2.5)
        self.assertEqual(r['secondMapsSummed'], 8.2)
        self.assertEqual(r['distance4x'], round(10.7 - 7.0 + 7.0 / 4, 1))
        self.assertNotIn('noSecondMaps', relight_probe.replay(relight_probe.load(self.log), workers=1))


if __name__ == '__main__':
    unittest.main()

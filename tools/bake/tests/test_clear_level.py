"""A cleared map in the Build (private/plans/done/clear-map-plan.md, section 7): the shell stage's cursor storeys in
place of the map's own (shell.py --clear) and native_copy.clear_level. Read on the configured install's URB_Bar; they
skip without it."""
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
import native_copy  # noqa: E402
import package_grow  # noqa: E402
import scene_metadata  # noqa: E402
import shell  # noqa: E402
from package import Package  # noqa: E402

BAR, NO_BAR = labpaths.install_map('URB_Bar')


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class ClearedCursors(unittest.TestCase):
    """URB_Bar cleared and made 48 by 35 tiles and 9 levels: its own four cursor volumes out of the level's list, the
    donor's brought as three even storeys over the grid."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.report = shell.equip(BAR, cls.tmp.name, grid=(48, 35), levels=9, ground=False, clear=True)
        cls.p = Package(Path(cls.tmp.name) / Path(BAR).name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_maps_own_are_out_and_three_storeys_cover_the_grid(self):
        own = Package(BAR)
        before = sorted(own.name(i).rsplit('.', 1)[-1] for i in shell.actors(own, 'XComCursorVolume') if i in shell.listed(own))
        self.assertEqual(self.report['clearedCursors'], before)
        live = shell.listed(self.p)
        listed = [i for i in shell.actors(self.p, 'XComCursorVolume') if i in live]
        names = {self.p.name(i).rsplit('.', 1)[-1] for i in listed}
        self.assertFalse(names & set(before))
        grid = native_copy.level_grid(self.p)
        floors = sorted((self.p.effective(i, 'm_iFloorNumber'), scene_metadata.volume_bounds(self.p, i)) for i in listed)
        self.assertEqual([(round(b['min'][2] - grid['oz']), round(b['max'][2] - grid['oz'])) for _, b in floors],
                         [(0, 192), (192, 384), (384, 576)])
        for _, b in floors:
            self.assertTrue(b['min'][0] <= grid['ox'] + 0.01 and b['max'][0] >= grid['ox'] + 96 * 48 - 0.01)
            self.assertTrue(b['min'][1] <= grid['oy'] + 0.01 and b['max'][1] >= grid['oy'] + 96 * 35 - 0.01)
        self.assertEqual(self.report['resized']['planesLaid'], 0)


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class ClearLevel(unittest.TestCase):
    """clear_level on URB_Bar as it is: what it takes out, what it leaves, and its one rebuild volume."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.p = Package(BAR)
        g = package_grow.Grower(str(BAR))
        cls.report, cls.volume = native_copy.clear_level(g, cls.p)
        native_copy.add_to_level(g, cls.p, [cls.volume])
        out = Path(cls.tmp.name) / Path(BAR).name
        g.write(str(out))
        cls.q = Package(out)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_what_goes_and_what_stays(self):
        out = self.report['out']
        for cls in ('XComBuildingVolume', 'XComFloorVolume', 'Emitter', 'DecalActor', 'PathBlockingVolume'):
            self.assertIn(cls, out)
        live = set(native_copy.level_actors(self.q))
        for i in range(1, len(self.q.exports) + 1):
            cls = self.q.cls(i)
            if i in live and self.q.exports[i - 1]['outer'] == self.q.by_name['TheWorld.PersistentLevel']:
                if cls in native_copy.CLEAR_OUT:
                    # only the landing's actors of those classes stay: its evac volume and its frame's prefab's
                    self.assertTrue(native_copy.landing_actor(self.q, i), self.q.name(i))
        # the sun and the sky light stay; the evac volume (a building volume of the landing's prefab) stays
        kept = self.report['kept']
        # the cursor volumes are the shell stage's (shell.py --clear)
        self.assertEqual(kept.get('XComCursorVolume'), 4)
        self.assertEqual(kept.get('DominantDirectionalLight'), 1)
        self.assertEqual(kept.get('SkyLight'), 1)
        evac = [i for i in live if i > 0 and self.q.cls(i) == 'XComBuildingVolume']
        self.assertEqual(len(evac), 1)
        self.assertTrue(native_copy.archetype_path(self.q, evac[0]).endswith('SoldierSpawns_DrpshipVol_Arc0'))
        self.assertIn('XComLevelActor_6', self.report['landing'])          # the drop zone's frame
        self.assertIn('XComLevelActor_138', self.report['landing'])        # the grounded Skyranger
        # its lights, dust and sound stay with it; the map's own ambient sounds go (18 November 2026)
        for name in ('Emitter_78', 'Emitter_0', 'AmbientSoundSimpleToggleable_0'):
            self.assertIn(name, self.report['landing'])
        self.assertEqual(out.get('AmbientSoundSimple'), 5)
        self.assertNotIn('AmbientSoundSimple', kept)
        print('\nclear_level on URB_Bar:', out, '\n  kept:', kept, '\n  odd:', {k: len(v) for k, v in self.report['odd'].items()})

    def test_one_rebuild_volume_over_the_whole_grid(self):
        grid = native_copy.level_grid(self.p)
        b = scene_metadata.volume_bounds(self.q, self.volume)
        self.assertEqual([round(v) for v in b['min'][:2] + b['max'][:2]],
                         [round(grid['ox']), round(grid['oy']), round(grid['ox'] + 96 * grid['nx']),
                          round(grid['oy'] + 96 * grid['ny'])])
        self.assertGreaterEqual(b['max'][2], grid['oz'] + 64 * grid['nz'] - 0.5)


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class ClearLevelKeepingOutside(unittest.TestCase):
    """clear_level on URB_Bar with the play area given (a clear that keeps the scenery outside it): the lights,
    emitters, decals and lens flares placed outside it stay in the list, those inside go, and volumes go wherever
    they stand."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.p = Package(BAR)
        grid = native_copy.level_grid(cls.p)
        cls.box = [grid['ox'], grid['oy'], grid['ox'] + 96 * grid['nx'], grid['oy'] + 96 * grid['ny']]
        g = package_grow.Grower(str(BAR))
        cls.report, volume = native_copy.clear_level(g, cls.p, outside=cls.box)
        native_copy.add_to_level(g, cls.p, [volume])
        out = Path(cls.tmp.name) / Path(BAR).name
        g.write(str(out))
        cls.q = Package(out)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_what_stands_outside_stays(self):
        live, level = set(native_copy.level_actors(self.q)), self.q.by_name['TheWorld.PersistentLevel']
        was = set(native_copy.level_actors(self.p))
        x0, y0, x1, y1 = self.box
        stayed = {}
        for i in sorted(was):
            if i <= 0 or self.p.exports[i - 1]['outer'] != level or native_copy.landing_actor(self.p, i):
                continue
            cls = self.p.cls(i)
            if cls not in native_copy.CLEAR_OUT:
                continue
            x, y = self.p.own(i, 'Location', [0.0, 0.0, 0.0])[:2]
            beyond = x < x0 or x > x1 or y < y0 or y > y1
            self.assertEqual(i in live, beyond and cls in native_copy.KEEP_OUTSIDE, (self.p.name(i), cls, x, y))
            if i in live:
                stayed[cls] = stayed.get(cls, 0) + 1
        self.assertEqual(self.report['outside'], dict(sorted(stayed.items())))
        print('\nclear_level on URB_Bar, keeping what stands outside the grid:', self.report['outside'])


if __name__ == '__main__':
    unittest.main()

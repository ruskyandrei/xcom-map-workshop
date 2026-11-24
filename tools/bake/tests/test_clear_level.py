"""A cleared map in the Build (private/plans/done/clear-map-plan.md, section 7): the shell stage's cursor storeys in
place of the map's own (shell.py --clear) and native_copy.clear_level, its triggers among what it takes (F-159), and
each part of a clear alone (private/plans/todo/modular-clear-plan.md, section 4). Read on the configured install's
URB_Bar and CSmallScout_Roadhouse; they skip without them."""
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
ROADHOUSE, NO_ROADHOUSE = labpaths.install_map('CSmallScout_Roadhouse')


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
        cls.report, volume = native_copy.clear_level(g, cls.p, parts={k: cls.box for k in native_copy.CLEAR_PARTS})
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



@unittest.skipUnless(ROADHOUSE and ROADHOUSE.exists(), NO_ROADHOUSE)
class ClearLevelTriggers(unittest.TestCase):
    """clear_level on CSmallScout_Roadhouse (F-159): its trigger volumes (eight water volumes, the UFO's entry and a
    hologram's touch triggers, three empty ones) and its sight point out of the level's list, the touch triggers' events
    switched off and the map's other events left; with keep_triggers they all stay."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.p = Package(ROADHOUSE)
        cls.built = {}
        for keep in (False, True):
            g = package_grow.Grower(str(ROADHOUSE))
            report, volume = native_copy.clear_level(
                g, cls.p, parts={k: None for k in native_copy.CLEAR_PARTS if not (keep and k == 'triggers')})
            native_copy.add_to_level(g, cls.p, [volume])
            out = Path(cls.tmp.name) / ('kept' if keep else 'taken') / Path(ROADHOUSE).name
            out.parent.mkdir()
            g.write(str(out))
            cls.built[keep] = (report, Package(out))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def placed(self, q, cls):
        level = q.by_name['TheWorld.PersistentLevel']
        return [i for i in range(1, len(q.exports) + 1) if q.cls(i) == cls and q.exports[i - 1]['outer'] == level]

    def events(self, q, volumes):
        return {q.name(i).rsplit('.', 1)[-1]: q.own(i, 'bEnabled')
                for i in range(1, len(q.exports) + 1) if q.cls(i).startswith('SeqEvent') and q.own(i, 'Originator') in volumes}

    def test_taken_out_with_their_events_off(self):
        report, q = self.built[False]
        live, volumes = set(native_copy.level_actors(q)), self.placed(q, 'TriggerVolume')
        self.assertEqual(report['out'].get('TriggerVolume'), 13)
        self.assertEqual(report['out'].get('XComSquadVisiblePoint'), 1)
        self.assertFalse(live & set(volumes + self.placed(q, 'XComSquadVisiblePoint')))
        # the two touch triggers' events, off; every other event of the map as it was
        events = self.events(q, set(volumes))
        self.assertEqual(sorted(events), report['eventsOff'])
        self.assertEqual(len(events), 2)
        self.assertTrue(all(v is False for v in events.values()), events)
        for i in range(1, len(self.p.exports) + 1):
            if self.p.cls(i).startswith('SeqEvent') and self.p.own(i, 'Originator') not in set(volumes):
                a, b = self.p.exports[i - 1], q.exports[i - 1]
                self.assertEqual(q.data[b['off']:b['off'] + b['size']], self.p.data[a['off']:a['off'] + a['size']], self.p.name(i))

    def test_kept_when_the_project_keeps_them(self):
        report, q = self.built[True]
        live = set(native_copy.level_actors(q))
        self.assertNotIn('TriggerVolume', report['out'])
        self.assertEqual((report['kept'].get('TriggerVolume'), report['kept'].get('XComSquadVisiblePoint')), (13, 1))
        self.assertEqual(report['eventsOff'], [])
        self.assertTrue(set(self.placed(q, 'TriggerVolume')) <= live)


class PartsAlone(unittest.TestCase):
    """clear_level with each part alone (the clear-by-parts plan, section 4) on URB_Bar and CSmallScout_Roadhouse: the
    part's classes out of the level's list (but the landing's), every other listed actor still listed, no export added
    without the pieces (their rebuild volume is the Pieces part's), and the parts together the whole clear."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.built = {}
        for path in (BAR, ROADHOUSE):
            if not (path and path.exists()):
                continue
            p = Package(path)
            for part in list(native_copy.CLEAR_PARTS) + [None]:
                g = package_grow.Grower(str(path))
                report, volume = native_copy.clear_level(g, p, parts=None if part is None else {part: None})
                if volume:
                    native_copy.add_to_level(g, p, [volume])
                out = Path(cls.tmp.name) / (part or 'all') / Path(path).name
                out.parent.mkdir(exist_ok=True)
                g.write(str(out))
                cls.built[path.stem, part] = (p, report, volume, Package(out))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_each_part_takes_its_classes_and_nothing_else(self):
        if not self.built:
            self.skipTest(NO_BAR)
        for (name, part), (p, report, volume, q) in sorted(self.built.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
            if part is None:
                continue
            with self.subTest(map=name, part=part):
                classes = set(native_copy.CLEAR_PARTS[part])
                self.assertEqual(report['parts'], [part])
                self.assertTrue(set(report['out']) <= classes, report['out'])
                level = p.by_name['TheWorld.PersistentLevel']
                was, live = set(native_copy.level_actors(p)), set(native_copy.level_actors(q))
                for i in was:
                    if i <= 0 or p.exports[i - 1]['outer'] != level:
                        continue
                    goes = p.cls(i) in classes and not native_copy.landing_actor(p, i)
                    self.assertEqual(i in live, not goes, (p.name(i), p.cls(i)))
                if part == 'pieces':
                    self.assertTrue(volume and 'rebuildVolume' in report and 'odd' in report)
                else:
                    self.assertIsNone(volume)
                    self.assertNotIn('rebuildVolume', report)
                    self.assertEqual(len(q.exports), len(p.exports))
                # only the triggers switch events off (Bar's two rats, Roadhouse's UFO entry and hologram)
                self.assertEqual(len(report['eventsOff']), 2 if part == 'triggers' else 0)

    def test_the_parts_together_are_the_whole_clear(self):
        if not self.built:
            self.skipTest(NO_BAR)
        for name in sorted({n for n, _ in self.built}):
            whole = self.built[name, None][1]
            taken = sorted(t for part in native_copy.CLEAR_PARTS for t in self.built[name, part][1]['taken'])
            self.assertEqual(taken, whole['taken'], name)
            self.assertEqual(sorted(e for part in native_copy.CLEAR_PARTS for e in self.built[name, part][1]['eventsOff']),
                             whole['eventsOff'], name)
            self.assertEqual(whole['parts'], list(native_copy.CLEAR_PARTS))


if __name__ == '__main__':
    unittest.main()

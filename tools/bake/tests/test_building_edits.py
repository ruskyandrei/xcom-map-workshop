"""The map's own buildings edited in place (buildings.edit, buildings.carried; private/plans/todo/
map-buildings-editable-plan.md, sections 3 and 4).

The readbacks build URB_Bar of the configured install (tools/viewer/settings.py, or the folder XCOM_COOKED names) with
native_copy.build, unbaked and without tiles, and skip without it. URB_Bar's buildings: XComBuildingVolume_0 the bar
(three floors, eight floor volumes, five of them notched), XComBuildingVolume_2 a small building of two floors (one
plain volume each: XComFloorVolume_8 and _6, listing XComLevelActor_20, _23 and _25), the others vans'."""
import json
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
import buildings  # noqa: E402
import native_copy  # noqa: E402
import package_grow  # noqa: E402
import audit_lighting as lighting  # noqa: E402

BAR, NO_BAR = labpaths.install_map('URB_Bar')
PL = 'TheWorld.PersistentLevel.'


class Carried(unittest.TestCase):
    def test_the_shared_cases(self):
        # web/floors.js carriedListing passes the same file (tools/viewer/tests/map_buildings_test.mjs)
        for c in json.loads((HERE / 'carried_listing_cases.json').read_text(encoding='utf-8')):
            fmap = {int(k): v for k, v in c['floorMap'].items()}
            entries, kept = buildings.carried([tuple(x) for x in c['saved']], [tuple(x) for x in c['oldRule']],
                                              [tuple(x) for x in c['newRule']], fmap)
            self.assertEqual(([list(x) for x in entries], kept), (c['entries'], c['kept']), c['name'])

    def test_floor_map_by_volumes(self):
        self.assertEqual(buildings.floor_map([['a'], ['b']], [[None], ['a'], ['b']]), {0: 1, 1: 2})
        self.assertEqual(buildings.floor_map([['a', 'c'], ['b']], [['a'], [None]]), {0: 0, 1: None})


def shift(box, dx=0.0, dy=0.0, dz=0.0):
    return [box[0] + dx, box[1] + dy, box[2] + dz, box[3] + dx, box[4] + dy, box[5] + dz]


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class Bar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.p = lighting.Package(BAR)
        cls.before = {b['name']: b for b in buildings.survey(cls.p)}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def edit_of(self, name, change=None, **more):
        b = self.before[name]
        floors = [dict(boxes=[list(v['box']) for v in f['volumes']], volumes=[v['name'] for v in f['volumes']])
                  for f in b['floors']]
        if change:
            change(floors)
        return dict(dict(id='map:PersistentLevel.' + name, actor=name, name=name, kind='building', deleted=False,
                         moved=False, floors=floors), **more)

    def built(self, variant, edits, copies=(), hides=()):
        out = Path(self.tmp.name) / variant
        m = native_copy.build(BAR, out, variant, list(copies), tiles=False, hides=list(hides), building_edits=edits)
        q = lighting.Package(out / ('%s.upk' % variant))
        return q, {b['name']: b for b in buildings.survey(q)}, m['nativeCopies']['buildingEdits']

    def same_export(self, q, name):
        a, b = q.by_name[PL + name], self.p.by_name[PL + name]
        ea, eb = q.exports[a - 1], self.p.exports[b - 1]
        return bytes(q.data[ea['off']:ea['off'] + ea['size']]) == bytes(self.p.data[eb['off']:eb['off'] + eb['size']])

    def test_a_box_stretched_a_tile(self):
        def wider(floors):
            floors[0]['boxes'][0][3] += 96
        q, after, report = self.built('Stretched', [self.edit_of('XComBuildingVolume_2', wider)])
        b = after['XComBuildingVolume_2']
        self.assertEqual([v['name'] for f in b['floors'] for v in f['volumes']], ['XComFloorVolume_8', 'XComFloorVolume_6'])
        self.assertEqual(b['floors'][0]['volumes'][0]['box'][3], self.before['XComBuildingVolume_2']['floors'][0]['volumes'][0]['box'][3] + 96)
        self.assertEqual(b['floors'][1]['volumes'][0]['box'], self.before['XComBuildingVolume_2']['floors'][1]['volumes'][0]['box'])
        self.assertEqual(report[0]['volumes']['stretched'], ['XComFloorVolume_8'])
        # the pieces whose answer did not change keep what the map saved; the other buildings are byte for byte
        self.assertEqual([[(m['actor'], m['cutdown']) for m in f['members']] for f in b['floors']][1],
                         [(m['actor'], m['cutdown']) for m in self.before['XComBuildingVolume_2']['floors'][1]['members']])
        for name in ('XComBuildingVolume_0', 'XComBuildingVolume_1', 'XComBuildingVolume_3'):
            self.assertTrue(self.same_export(q, name), name)
        self.assertTrue(self.same_export(q, 'XComFloorVolume_6'))

    def test_a_notched_volume_stretched_gets_a_plain_one_in_its_place(self):
        def longer(floors):
            k = floors[0]['volumes'].index('XComFloorVolume_15')
            floors[0]['boxes'][k][0] -= 96
        q, after, report = self.built('Notched', [self.edit_of('XComBuildingVolume_0', longer)])
        self.assertEqual(report[0]['volumes']['replaced'], ['XComFloorVolume_15'])
        names = [v['name'] for v in after['XComBuildingVolume_0']['floors'][0]['volumes']]
        self.assertNotIn('XComFloorVolume_15', names)
        self.assertEqual(len(names), 4)
        made = after['XComBuildingVolume_0']['floors'][0]['volumes'][names.index(report[0]['volumes']['made'][0])]
        self.assertTrue(made['listed'])
        self.assertEqual((made['number'], made['box'][0]), (1, -1632.0 - 96))
        level = native_copy.level_actors(q)
        self.assertNotIn(q.by_name[PL + 'XComFloorVolume_15'], level)
        # the bar's pieces: nearly all keep what the map saved
        self.assertGreater(report[0]['pieces']['kept'], 380)

    def test_a_floor_added_on_top(self):
        def roof(floors):
            floors.append(dict(boxes=[shift(floors[1]['boxes'][0], dz=496)], volumes=[None]))
        q, after, report = self.built('Storey', [self.edit_of('XComBuildingVolume_2', roof)])
        b = after['XComBuildingVolume_2']
        self.assertEqual(len(b['floors']), 3)
        self.assertEqual((b['floors'][2]['volumes'][0]['number'], b['floors'][2]['volumes'][0]['listed']), (3, True))
        self.assertEqual(report[0]['volumes']['made'], [b['floors'][2]['volumes'][0]['name']])

    def test_moved_whole_with_its_pieces(self):
        pieces = ['XComLevelActor_20', 'XComLevelActor_23', 'XComLevelActor_25']
        p = self.p
        copies = [dict(actor=n, location=shift(list(p.own(p.by_name[PL + n], 'Location')) * 2, 192)[:3],
                       rotation=list(p.own(p.by_name[PL + n], 'Rotation', [0, 0, 0])), label='move:' + n) for n in pieces]

        def moved(floors):
            for f in floors:
                f['boxes'] = [shift(x, 192) for x in f['boxes']]
        q, after, report = self.built('Moved', [self.edit_of('XComBuildingVolume_2', moved, moved=True)], copies,
                                      [dict(name=n, box=None) for n in pieces])
        b = after['XComBuildingVolume_2']
        # its volumes are the map's own, at the new place; its lists name the copies, as the map saved the originals
        self.assertEqual([v['name'] for f in b['floors'] for v in f['volumes']], ['XComFloorVolume_8', 'XComFloorVolume_6'])
        self.assertEqual(b['floors'][0]['volumes'][0]['box'], shift(self.before['XComBuildingVolume_2']['floors'][0]['volumes'][0]['box'], 192))
        listed = {m['actor'] for f in b['floors'] for m in f['members']}
        self.assertFalse(listed & set(pieces))
        self.assertEqual(len({a for a in listed if PL + a not in self.p.by_name}), 3)
        # (at the new place the grounded Skyranger, XComLevelActor_138, stands in its boxes: listed by the rule)
        self.assertEqual((report[0]['pieces']['kept'], report[0]['pieces']['dropped']), (3, 3))
        self.assertEqual(listed - {a for a in listed if PL + a not in self.p.by_name}, {'XComLevelActor_138'})
        self.assertTrue(report[0]['moved'])

    def test_deleted(self):
        q, after, report = self.built('Deleted', [dict(id='x', actor='XComBuildingVolume_2', deleted=True)])
        level = set(native_copy.level_actors(q))
        for name in ('XComBuildingVolume_2', 'XComFloorVolume_8', 'XComFloorVolume_6'):
            self.assertNotIn(q.by_name[PL + name], level, name)
        self.assertEqual(report[0]['volumes'], ['XComFloorVolume_8', 'XComFloorVolume_6'])
        # its pieces stay
        for name in ('XComLevelActor_20', 'XComLevelActor_23', 'XComLevelActor_25'):
            self.assertIn(q.by_name[PL + name], level)

    def test_unchanged_is_byte_for_byte(self):
        g = package_grow.Grower(str(BAR))
        level = self.p.by_name['TheWorld.PersistentLevel']
        pieces = [dict(actor=i, source=i) for i in native_copy.level_actors(self.p)
                  if i > 0 and self.p.exports[i - 1]['outer'] == level and not self.p.effective(i, 'bHidden', False)]
        actors, slots, _ = buildings.edit(g, self.p, [self.edit_of('XComBuildingVolume_0'), self.edit_of('XComBuildingVolume_2')], pieces)
        self.assertEqual((actors, slots), ([], set()))
        changed = [k for k in range(1, len(self.p.exports) + 1)
                   if g.export_data(k) != bytes(self.p.data[self.p.exports[k - 1]['off']:self.p.exports[k - 1]['off'] + self.p.exports[k - 1]['size']])]
        self.assertEqual(changed, [])


if __name__ == '__main__':
    unittest.main()

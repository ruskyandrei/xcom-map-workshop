"""Buildings made from nothing (buildings.py; private/plans/done/prefab-library-plan.md 5.1 and 5.2, EXP-44).

The checks read URB_ResearchOutpost and URB_Bar of the configured install (tools/viewer/settings.py, or the folder
XCOM_COOKED names) and skip without it. The outpost's shed is the building of EXP-44: here a second building is made
over the shed's own two floors, in the outpost itself, and its lists are compared with the ones the map saves."""
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
import lighting_records as lighting  # noqa: E402

OUTPOST, NO_OUTPOST = labpaths.install_map('URB_ResearchOutpost')
BAR, NO_BAR = labpaths.install_map('URB_Bar')
# the shed's two floor volumes (XComFloorVolume_51 and _45 of XComBuildingVolume_2)
FLOORS = [[-192.0, -1536.0, 0.0, 384.0, -960.0, 176.0], [-192.0, -1536.0, 176.0, 384.0, -960.0, 384.0]]
HUT = dict(id='hut', name='Hut', kind='building', floors=[dict(boxes=[box]) for box in FLOORS])


class Shape(unittest.TestCase):
    def test_a_floor_needs_a_box_with_room(self):
        for bad in (dict(HUT, floors=[]), dict(HUT, floors=[dict(boxes=[])]), dict(HUT, kind='shed'),
                    dict(HUT, floors=[dict(boxes=[[0, 0, 0, 96, 96, 0]])]), dict(HUT, floors=[dict(boxes=[[0, 0, 0, 96]])])):
            with self.assertRaises(ValueError):
                buildings.check([bad])
        buildings.check([HUT])


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class Templates(unittest.TestCase):
    def test_the_bar_has_both_templates(self):
        p = lighting.Package(BAR)
        bt, ft = buildings.templates(p)
        self.assertEqual(p.cls(bt['actor']), 'XComBuildingVolume')
        self.assertEqual(p.cls(ft), 'XComFloorVolume')
        self.assertIsNone(bt['plain']['cutdownAt'])
        self.assertIsNotNone(bt['cut']['cutdownAt'])


@unittest.skipUnless(OUTPOST and OUTPOST.exists(), NO_OUTPOST)
class Shed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        p = lighting.Package(OUTPOST)
        g = package_grow.Grower(str(OUTPOST))
        level = p.by_name['TheWorld.PersistentLevel']
        pieces = [dict(actor=i, source=i, name=p.name(i).split('.')[-1]) for i in native_copy.level_actors(p)
                  if i > 0 and p.exports[i - 1]['outer'] == level and not p.effective(i, 'bHidden', False)]
        actors, cls.report = buildings.make(g, p, [HUT], pieces)
        native_copy.add_to_level(g, p, actors)
        out = Path(cls.tmp.name) / Path(OUTPOST).name
        g.write(str(out))
        lighting.link_caches(out.parent, Path(OUTPOST).parent)
        found = {b['name']: b for b in buildings.survey(lighting.Package(out))}
        cls.own = found['XComBuildingVolume_2']
        cls.new = next(b for name, b in found.items() if name not in
                       {x['name'] for x in buildings.survey(p)})

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_volumes_are_the_boxes_asked_for(self):
        self.assertEqual(self.new['tag'], 'XComBuildingVolume')
        for k, (floor, box) in enumerate(zip(self.new['floors'], FLOORS)):
            self.assertEqual(len(floor['volumes']), 1)
            volume = floor['volumes'][0]
            self.assertTrue(volume['listed'])
            self.assertEqual(volume['number'], k + 1)
            for got, want in zip(volume['box'], box):
                self.assertAlmostEqual(got, want, delta=0.01)
        for got, want in zip(self.new['box'], FLOORS[0][:3] + FLOORS[1][3:]):
            self.assertAlmostEqual(got, want, delta=0.01)
        self.assertEqual(self.new['groups'], [])

    def test_the_walls_cut_down_and_the_roof_is_upstairs(self):
        ground = {m['actor']: m['cutdown'] for m in self.new['floors'][0]['members']}
        above = {m['actor']: m['cutdown'] for m in self.new['floors'][1]['members']}
        for wall in ('XComDecoFracLevelActor_98', 'XComDecoFracLevelActor_99', 'XComDecoFracLevelActor_100',
                     'XComDecoFracLevelActor_101', 'XComDestructibleActor_159'):
            self.assertEqual(ground.get(wall), 1, wall)
            self.assertNotIn(wall, above)
        for door in ('XComInteractiveLevelActor_17', 'XComDestructibleActor_270'):
            self.assertEqual(ground.get(door), 0, door)
        self.assertEqual(above.get('XComFracLevelActor_55'), 0)
        self.assertNotIn('XComFracLevelActor_55', ground)

    def test_the_lists_are_nearly_the_maps_own(self):
        """The game's editor went by collision; the rule from mesh boxes gives the shed's own list but for two pieces
        (a flood light on the outer wall and a puddle outside the door)."""
        for k in range(2):
            own = {(m['actor'], m['cutdown']) for m in self.own['floors'][k]['members']}
            new = {(m['actor'], m['cutdown']) for m in self.new['floors'][k]['members']}
            self.assertLessEqual(len(own - new), 1, own - new)
            # what the rule adds: pieces of other buildings and of none that reach into the shed's floors
            self.assertTrue(all(cut == 0 or k == 0 for _, cut in new - own))

    def test_the_report_names_what_it_made(self):
        b = self.report[0]
        self.assertEqual((b['id'], b['kind'], len(b['floors'])), ('hut', 'building', 2))
        # the map has pieces whose mesh gives no box (not the shed's): they are named, and listed nowhere
        self.assertNotIn('XComFracLevelActor_55', b['unread'])


if __name__ == '__main__':
    unittest.main()

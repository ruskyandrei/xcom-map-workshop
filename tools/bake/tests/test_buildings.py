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

    def test_the_templates_brushes_are_boxes(self):
        # the bar's largest plain floor volume (XComFloorVolume_12) is notched: a box one is taken (F-170)
        p = lighting.Package(BAR)
        bt, ft = buildings.templates(p)
        self.assertTrue(buildings.box_brush(p, ft), p.name(ft))
        self.assertTrue(buildings.box_brush(p, bt['actor']), p.name(bt['actor']))
        self.assertEqual(buildings.box_source(p, ft), ft)


class MadeShapes:
    """A building of two floors made on a map whose volumes to clone are not boxes (F-170): every volume made is a
    box over the box asked for, and its brush component holds a box's collision. The subclass names the map."""
    MAP = None
    BOXES = None

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.p = p = lighting.Package(cls.MAP)
        g = package_grow.Grower(str(cls.MAP))
        building = dict(id='made', name='Made', kind='building', floors=[dict(boxes=[box]) for box in cls.BOXES])
        actors, cls.report = buildings.make(g, p, [building], [])
        native_copy.add_to_level(g, p, actors)
        out = Path(cls.tmp.name) / Path(cls.MAP).name
        g.write(str(out))
        cls.q = lighting.Package(out)
        r = cls.report[0]
        cls.made = [r['building']] + [v for f in r['floors'] for v in f['volumes']]
        cls.want = [cls.BOXES[0][:3] + cls.BOXES[-1][3:]] + list(cls.BOXES)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_each_volume_is_a_box_over_its_box(self):
        import scene_metadata
        for v, want in zip(self.made, self.want):
            self.assertTrue(buildings.box_brush(self.q, v), self.q.name(v))
            b = scene_metadata.volume_bounds(self.q, v)
            for got, w in zip(b['min'] + b['max'], want):
                self.assertAlmostEqual(got, w, delta=0.01)

    def test_each_component_holds_a_box_collision(self):
        w = native_copy.Walker(self.q)
        for v in self.made:
            tc = self.q.own(v, 'BrushComponent', 0)
            model = self.q.own(v, 'Brush', 0)
            self.assertEqual(self.q.own(tc, 'Brush', 0), model)
            source = next(i for i in range(1, len(self.p.exports) + 1) if self.p.cls(i) != 'Model' and
                          self.p.own(i, 'Brush', 0) == model and self.p.cls(i) != 'BrushComponent')
            mine, theirs = (bytes(q.data[q.exports[c - 1]['off']:q.exports[c - 1]['off'] + q.exports[c - 1]['size']])
                            for q, c in ((self.q, tc), (self.p, self.p.own(source, 'BrushComponent', 0))))

            def agg(b, q, c):
                f = native_copy.find_prop(w, b, buildings.start_of(q, c), len(b), 'BrushAggGeom[0]')
                return b[f[2]:f[2] + f[3]] if f else None
            self.assertEqual(agg(mine, self.q, tc), agg(theirs, self.p, self.p.own(source, 'BrushComponent', 0)))


HIVE, NO_HIVE = labpaths.install_map('EWI_ChryssalidHive')
TRAINYARD, NO_TRAINYARD = labpaths.install_map('URB_Trainyard')


@unittest.skipUnless(HIVE and HIVE.exists(), NO_HIVE)
class HiveShapes(MadeShapes, unittest.TestCase):
    """EWI_ChryssalidHive: its largest plain floor volume (XComFloorVolume_71) is a pointed prism and its building
    template had a notched brush; a boat's three floors made there."""
    MAP = HIVE
    BOXES = [[-6240.0, 1344.0, -192.0, -1632.0, 3648.0, 192.0], [-6240.0, 1344.0, 192.0, -1632.0, 3648.0, 576.0],
             [-6240.0, 1344.0, 576.0, -1632.0, 3648.0, 1152.0]]

    def test_the_templates_are_its_box_volumes(self):
        bt, ft = buildings.templates(self.p)
        self.assertTrue(buildings.box_brush(self.p, ft))
        self.assertTrue(buildings.box_brush(self.p, bt['actor']))


@unittest.skipUnless(TRAINYARD and TRAINYARD.exists(), NO_TRAINYARD)
class TrainyardShapes(MadeShapes, unittest.TestCase):
    """URB_Trainyard: none of its floor volumes of the kind cloned has a box brush, so the floor volumes take the box
    model and collision of another of its volumes."""
    MAP = TRAINYARD
    BOXES = [[0.0, 0.0, 0.0, 768.0, 576.0, 192.0], [0.0, 0.0, 192.0, 768.0, 576.0, 384.0]]

    def test_the_floor_template_borrows_a_box(self):
        ft = buildings.floor_template(self.p)
        self.assertFalse(buildings.box_brush(self.p, ft))
        source = buildings.box_source(self.p, ft)
        self.assertNotEqual(source, ft)
        self.assertTrue(buildings.box_brush(self.p, source))


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


@unittest.skipUnless(BAR, NO_BAR)
class CursorFloors(unittest.TestCase):
    """A building whose floors are the cursor's (the building cursor floors plan) written into URB_Bar by the Build's
    writer (made_cursors.apply, as native_copy.floors_and_cursors calls it): the bar's four map-wide cursor volumes
    stand again round it, its own three floors of uneven heights over it; read back, the map's listed cursor volumes
    are the floors the compiler's rule gives (made_cursors.storeys)."""
    # a three-floor building on the bar's lot: floors 0 to 160, 160 to 352 and 352 to 448, the top one over half of it
    AREA = dict(label='Tower', floors=[[[-1728.0, -1056.0, 0.0, -1344.0, -768.0, 160.0]],
                                       [[-1728.0, -1056.0, 160.0, -1344.0, -768.0, 352.0]],
                                       [[-1728.0, -1056.0, 352.0, -1536.0, -768.0, 448.0]]])

    @classmethod
    def setUpClass(cls):
        import made_cursors
        import shell
        cls.tmp = tempfile.TemporaryDirectory()
        p = lighting.Package(BAR)
        g = package_grow.Grower(str(BAR))
        live = shell.listed(p)
        cls.before = [dict(key=i, floor=p.effective(i, 'm_iFloorNumber') or 0,
                           box=list(native_copy.brush_box(p, i)[0]) + list(native_copy.brush_box(p, i)[1]),
                           stair=bool(p.effective(i, 'm_bTreatAsStair')))
                      for i in shell.actors(p, 'XComCursorVolume') if i in live]
        cls.areas = made_cursors.build_areas([dict(name='Tower', cursorFloors=True,
                                                   floors=[dict(boxes=f) for f in cls.AREA['floors']]),
                                              dict(name='Plain', floors=[dict(boxes=[[0, 0, 0, 96, 96, 192]])])])
        cls.record, clones = made_cursors.apply(g, p, [], cls.areas)
        native_copy.add_to_level(g, p, clones)
        out = Path(cls.tmp.name) / Path(BAR).name
        g.write(str(out))
        lighting.link_caches(out.parent, Path(BAR).parent)
        cls.q = lighting.Package(out)
        cls.want = made_cursors.storeys(cls.before, [], shell.grid_box(p), cls.areas)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_only_the_ticked_building_is_an_area(self):
        self.assertEqual([a['label'] for a in self.areas], ['Tower'])

    def test_written_and_read_back_as_the_rule_gives(self):
        import made_cursors
        import shell
        made_cursors.verify(self.q, self.record)
        live = shell.listed(self.q)
        got = sorted((self.q.effective(i, 'm_iFloorNumber') or 0,
                      tuple(round(v, 1) for v in list(native_copy.brush_box(self.q, i)[0]) + list(native_copy.brush_box(self.q, i)[1])))
                     for i in shell.actors(self.q, 'XComCursorVolume') if i in live
                     and not self.q.effective(i, 'm_bTreatAsStair'))
        self.assertEqual(got, sorted((f, tuple(round(v, 1) for v in b)) for f, b in self.want))

    def test_over_the_building_its_floors_off_it_the_bars(self):
        own = [a for a in self.record['added'] if a.get('building') == 'Tower']
        at = lambda x, y: sorted((round(a['box'][2]), round(a['box'][5]), a['floor']) for a in own  # noqa: E731
                                 if a['box'][0] <= x <= a['box'][3] and a['box'][1] <= y <= a['box'][4])
        self.assertEqual(at(-1600, -900), [(-2, 158, 1), (158, 350, 2), (350, 448, 3)])
        self.assertEqual(at(-1400, -900), [(-2, 158, 1), (158, 352, 2)])
        self.assertEqual(len(self.record['hidden']), 4)
        self.assertTrue(all(a['floor'] in (1, 2, 3, 4) for a in self.record['added'] if 'building' not in a))


if __name__ == '__main__':
    unittest.main()

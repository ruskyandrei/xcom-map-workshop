"""The slab measurer (slab_measure.py; custom geometry plan, M4 work order B): a made slab measured again gives its
recipe back; on the install, the Bar's roof and upper floor measure as today's looks were written, the same every
time; donors of other layouts (one slot for everything, faces inside, the top in its second slot, a pitched roof, a
thick one) measure into recipes frac_slab builds, with their warnings; and the twin check."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
for folder in ('viewer', 'upk', 'lab'):
    sys.path.insert(0, str(HERE.parents[1] / folder))
sys.path.insert(0, str(HERE.parent))
import frac_slab  # noqa: E402
import gen_mesh  # noqa: E402
import labpaths  # noqa: E402
import measure_common as mc  # noqa: E402
import slab_measure  # noqa: E402

BAR, NO_BAR = labpaths.test_file('XCOM_BAR_UPK', labpaths.lwr_cooked('URB_Bar.upk'), 'URB_Bar.upk')
RECIPE = dict(role='roof', kind='flat', bottom=10.0, top=16.0, slots=dict(top=1, underside=1, edge=1), sections=3,
              interior=2, insideFaces=True,
              uv=dict(top=[[0.0, round(1 / 300.0, 7), 0.25], [round(-1 / 300.0, 7), 0.0, 0.5]],
                      underside=[[round(-1 / 150.0, 7), 0.0, 0.0], [0.0, round(1 / 150.0, 7), 0.125]],
                      edge=dict(x=[[round(1 / 300.0, 7), 0.0, 0.0], [0.0, 0.015625, 0.0]],
                                y=[[round(1 / 300.0, 7), 0.0, 0.0], [0.0, 0.015625, 0.0]])),
              collision=[10.0, 14.0], tile=96.0, split=0.0, long=0.6,
              colours=dict(outside='ffffffff', interior='ffffffff'),
              lightmap=dict(density=0.2, margin=2, interiorDensity=1.0, block=4),
              measured=dict(size=[384.0, 288.0, 6.0], triangles=0, fragments=0, perTile=0.0, kind='flat'))
PL = 'TheWorld.PersistentLevel.'


def boxes(out):
    return [[b[0][0], b[1][0], b[0][1], b[1][1], b[0][2], b[1][2]] for b in out['solids']]


class MadeAndMeasured(unittest.TestCase):
    """A slab made in a recipe and measured again gives the recipe's look back."""

    def test_the_recipe_comes_back(self):
        slab = dict(x0=0.0, x1=384.0, y0=0.0, y1=288.0, seed=1, look=dict(mesh='P.G.M', measure=1, recipe=RECIPE))
        out = frac_slab.build(slab)
        got = slab_measure.measure_mesh(out['mesh'], 'Some_Roof', dict(rect=out['lightmapRect']), boxes(out))
        R = got['recipe']
        for key in ('role', 'kind', 'bottom', 'top', 'slots', 'sections', 'interior', 'insideFaces', 'collision'):
            self.assertEqual(R[key], RECIPE[key], key)
        for key in ('top', 'underside'):
            self.assertFalse(mc.map_differs(R['uv'][key], RECIPE['uv'][key]), (key, R['uv'][key]))
        self.assertEqual(got['facts']['layout'], '1:top+underside+edges | 2:inside')
        # nothing in slot 0 to warn of: the made slab leaves it empty, as its recipe says
        self.assertEqual(got['warnings'], [])

    def test_the_twin_check_passes_on_its_own_recipe(self):
        slab = dict(x0=0.0, x1=384.0, y0=0.0, y1=288.0, seed=1, look=dict(mesh='P.G.M', measure=1, recipe=RECIPE))
        out = frac_slab.build(slab)
        R = slab_measure.measure_mesh(out['mesh'], 'Some_Roof', dict(rect=out['lightmapRect']), boxes(out))['recipe']
        result = slab_measure.twin(R)
        self.assertTrue(result['ok'], slab_measure.verdict(result))
        self.assertEqual(slab_measure.verdict(result), 'ok')
        self.assertEqual(result['built'], dict(x0=0.0, x1=384.0, y0=0.0, y1=288.0, seed=1))

    def test_the_shares_give_about_the_donors_fragments_a_tile(self):
        for per in (0.62, 0.8, 1.0, 1.4):
            split, long_, made = slab_measure.shares(per, 0.3)
            self.assertLess(abs(made - per) / per, 0.1, per)
            self.assertAlmostEqual(slab_measure.made_per_tile(split, long_), made)


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class BarSlabs(unittest.TestCase):
    """URB_Bar's roof (XComFracLevelActor_3) and upper floor (XComFracLevelActor_17), today's two looks' donors."""

    @classmethod
    def setUpClass(cls):
        from package import Package
        cls.p = Package(BAR)
        cls.roof = slab_measure.measure(cls.p, 'XComFracLevelActor_3')
        cls.floor = slab_measure.measure(cls.p, 'XComFracLevelActor_17')

    def test_they_measure_as_todays_looks_were_written(self):
        for entry, name in ((self.roof, 'roof'), (self.floor, 'floor')):
            R, old = entry['recipe'], frac_slab.LOOKS[name]['recipe']
            self.assertEqual(entry['warnings'], [])
            self.assertEqual((R['bottom'], R['top'], R['collision']), (old['bottom'], old['top'], old['collision']))
            self.assertEqual((R['slots']['top'], R['slots']['underside'], R['slots']['edge']), (0, 1, 0))
            self.assertEqual((R['sections'], R['interior'], R['insideFaces']), (old['sections'], old['interior'], False))
            self.assertEqual(R['role'], name)
            # today's u = s x / repeat + du, v = t y / repeat + dv, as planar maps
            for key, coef in (('top', old['topUV']), ('underside', old['undersideUV'])):
                want = [[coef[0] / old['repeat'], 0.0, coef[2]], [0.0, coef[1] / old['repeat'], coef[3]]]
                self.assertFalse(mc.map_differs(R['uv'][key], want), (name, key, R['uv'][key]))
            self.assertEqual(entry['facts']['layout'], '0:top+edges | 1:underside')
        self.assertEqual(self.roof['facts']['mesh'], frac_slab.LOOKS['roof']['donor'])

    def test_the_same_every_time_by_actor_or_by_mesh(self):
        self.assertEqual(slab_measure.measure(self.p, 'XComFracLevelActor_3'), self.roof)
        by_mesh = slab_measure.measure(self.p, frac_slab.LOOKS['roof']['donor'])
        self.assertEqual(by_mesh['recipe'], self.roof['recipe'])

    def test_the_twin_check_passes_with_and_without_the_donors_mesh(self):
        for entry, actor in ((self.roof, 'XComFracLevelActor_3'), (self.floor, 'XComFracLevelActor_17')):
            _, _, mesh = mc.find_placing(self.p, actor, slab_measure.FRACTURING, 'FracturedStaticMeshComponent')
            for template in (None, gen_mesh.read(self.p, mesh)):
                result = slab_measure.twin(entry['recipe'], template)
                self.assertTrue(result['ok'], slab_measure.verdict(result))

    def test_a_placing_that_is_no_slab_is_refused(self):
        with self.assertRaises(ValueError):
            slab_measure.measure(self.p, 'XComLevelActor_131')
        with self.assertRaises(ValueError):
            slab_measure.measure(self.p, 'Nothing.Placed.Here')


class Layouts(unittest.TestCase):
    """Donors of other layouts, each from its map (skipped where the install lacks it)."""

    def measured(self, map_name, mesh):
        from package import Package
        path, why = labpaths.install_map(map_name)
        if not (path and path.exists()):
            self.skipTest(why)
        p = Package(path)
        entry = slab_measure.measure(p, mesh)
        _, _, index = mc.find_placing(p, mesh, slab_measure.FRACTURING, 'FracturedStaticMeshComponent')
        template = gen_mesh.read(p, index)
        result = slab_measure.twin(entry['recipe'], template)
        # it builds, with the donor's sections in slot order
        built = frac_slab.build(dict(result['built'], look=dict(mesh=mesh, measure=1, recipe=entry['recipe'])), template)
        self.assertEqual([s['slot'] for s in built['mesh']['lods'][0]['sections']],
                         list(range(entry['recipe']['sections'])))
        return entry, result, built

    def test_one_slot_for_everything(self):
        entry, result, _ = self.measured('URB_SmallCemetery', 'URB_SmallCemetery_FRAC.Meshes.URBSmCemShedRoof_FRACTURED')
        R = entry['recipe']
        self.assertEqual((R['slots'], R['sections']), (dict(top=0, underside=0, edge=0), 1))
        self.assertTrue(result['ok'], slab_measure.verdict(result))

    def test_faces_inside(self):
        entry, result, built = self.measured('URB_TrainStation', 'SubwayTrain.Meshes.SubwayCarRoof_FRACTURED')
        R = entry['recipe']
        self.assertTrue(R['insideFaces'])
        self.assertEqual((R['interior'], R['sections'], R['kind']), (1, 2, 'thick'))
        self.assertTrue(any('thick roof' in w for w in entry['warnings']), entry['warnings'])
        self.assertGreater(built['mesh']['lods'][0]['sections'][1]['triangles'], 0)
        self.assertIn('kind thick, made flat', slab_measure.verdict(result))

    def test_the_top_in_its_second_slot(self):
        entry, result, built = self.measured('URB_TruckStop', 'URB_TruckStop_FRAC.Meshes.TS_FloorDeck_FRACTURED')
        R = entry['recipe']
        self.assertEqual((R['slots']['top'], R['slots']['underside'], R['sections']), (1, 2, 3))
        self.assertTrue(any('material slot 0' in w for w in entry['warnings']), entry['warnings'])
        self.assertEqual(built['mesh']['lods'][0]['sections'][0]['triangles'], 0)
        self.assertTrue(result['ok'], slab_measure.verdict(result))

    def test_a_pitched_roof_is_made_flat_at_its_eaves(self):
        entry, result, built = self.measured('URB_OfficePaper', 'URB_OfficePaper_FRAC.Meshes.OPWarehouseRoofSouth_FRACTURED')
        R = entry['recipe']
        self.assertEqual(R['kind'], 'pitched')
        self.assertTrue(any(w.startswith('a pitched roof') for w in entry['warnings']), entry['warnings'])
        self.assertEqual(R['top'] - R['bottom'], slab_measure.PITCHED_PLATE)
        zs = {round(p[2], 2) for p in built['mesh']['lods'][0]['positions']}
        self.assertEqual(zs, {R['bottom'], R['top']})
        self.assertIn('kind pitched, made flat', slab_measure.verdict(result))

    def test_a_thick_roof_is_its_plate(self):
        entry, result, _ = self.measured('URB_ResearchOutpost', 'URB_ResearchOutpost_FRAC.Meshes.ROBetaRoof_FRACTURED')
        R = entry['recipe']
        self.assertEqual((R['kind'], R['slots']['top'], R['slots']['underside'], R['sections']), ('thick', 0, 2, 4))
        self.assertEqual(slab_measure.verdict(result), 'kind thick, made flat')


class BuiltInAMap(unittest.TestCase):
    """A slab in a look given whole, made by the Build on a copy of its donor: URB_TruckStop's deck (three sections,
    the top in slot 1, slot 0 left empty)."""
    MESH = 'URB_TruckStop_FRAC.Meshes.TS_FloorDeck_FRACTURED'

    def test_the_copy_has_the_made_mesh_with_the_donors_sections(self):
        import tempfile
        import native_copy
        from package import Package
        path, why = labpaths.install_map('URB_TruckStop')
        if not (path and path.exists()):
            self.skipTest(why)
        p = Package(path)
        entry = slab_measure.measure(p, self.MESH)
        actor, _, _ = mc.find_placing(p, self.MESH, slab_measure.FRACTURING, 'FracturedStaticMeshComponent')
        slab = dict(x0=0.0, x1=288.0, y0=0.0, y1=192.0, seed=3,
                    look=dict(mesh=self.MESH, measure=slab_measure.VERSION, recipe=entry['recipe']))
        location = list(p.effective(actor, 'Location', [0.0, 0.0, 0.0]))
        with tempfile.TemporaryDirectory() as tmp:
            m = native_copy.build(path, Path(tmp), 'Deck', [dict(
                actor=p.name(actor).split('.')[-1], label='Deck', location=location, rotation=[0, 0, 0],
                generated=dict(kind='fracSlab', version=2, slab=slab))], bake=False)
            q = Package(Path(tmp) / 'Deck.upk')
            copy = {c['label']: c['export'] for c in m['nativeCopies']['copies']}['Deck']
            made = q.own(q.own(copy, 'FracturedStaticMeshComponent'), 'StaticMesh')
            self.assertEqual(q.name(made).split('.')[-1], frac_slab.mesh_name(slab))
            lod = gen_mesh.read(q, made)['lods'][0]
            self.assertEqual([s['slot'] for s in lod['sections']], [0, 1, 2])
            self.assertEqual(lod['sections'][0]['triangles'], 0)
            rec = {r['label']: r for r in m['nativeCopies']['generatedWalls']}['Deck']
            self.assertEqual(rec['kind'], 'fracSlab')
            self.assertEqual(rec['columns'], 4 * 3)        # 3 by 2 tiles: a column a cell, the last row and column 1 wide
            self.assertAlmostEqual(rec['box'][5] - rec['box'][4], entry['recipe']['top'] - entry['recipe']['bottom'], 2)


if __name__ == '__main__':
    unittest.main()

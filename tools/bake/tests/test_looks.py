"""Looks named by their donor (looks.py; custom geometry plan, M4): a catalogued look's recipe, a look measured on its
donor when no catalogue holds it (once per process), a measurer of another version refused, requests with a look id
left alone, and the page's listing without the Build's recipe numbers."""
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import looks  # noqa: E402

WALL = {'mesh': 'Pkg.Meshes.WallA_FRACTURED', 'map': 'MapA', 'actor': 'XComFracLevelActor_3', 'maps': {'MapA': 2},
        'name': 'Wall A', 'setting': 'brick', 'lwrOnly': False, 'facts': {'inside': True}, 'warnings': [],
        'twin': 'ok', 'recipe': {'bottom': -16.0, 'top': 192.0, 'storey': None, 'face': [12.0, 180.0], 'half': 8.0,
                                 'endInset': 8.0, 'sections': 4, 'section': [[8.0, -16.0, 0.5], [8.0, 192.0, 0.5]]}}
GROUND = {'mesh': 'Pkg.Meshes.Plane', 'material': 'Pkg.Materials.Grass', 'map': 'MapB', 'actor': 'XComLevelActor_9',
          'maps': {'MapB': 1}, 'name': 'Grass', 'setting': 'farm', 'lwrOnly': False, 'facts': {}, 'warnings': [],
          'twin': 'ok', 'recipe': {'thickness': 8.0, 'repeat': 256.0, 'sections': 1}}


class Looks(unittest.TestCase):
    def setUp(self):
        looks.forget()
        self.dir = tempfile.TemporaryDirectory()
        self.folder = Path(self.dir.name)
        for name, e in (('walls.json', WALL), ('ground.json', GROUND)):
            (self.folder / name).write_text(json.dumps({'about': 'test', 'measure': 1, 'looks': [e]}),
                                            encoding='utf-8', newline='\n')

    def tearDown(self):
        looks.forget()
        self.dir.cleanup()

    def test_a_catalogued_look_takes_its_recipe(self):
        out = looks.resolve('wall', {'mesh': WALL['mesh'], 'measure': 1}, folder=self.folder)
        self.assertEqual(out['recipe'], WALL['recipe'])
        self.assertEqual((out['mesh'], out['measure'], out['warnings']), (WALL['mesh'], 1, []))
        out['recipe']['top'] = 0        # (a copy: the catalogue is not changed)
        self.assertEqual(looks.entry('wall', WALL['mesh'], folder=self.folder)['recipe']['top'], 192.0)

    def test_a_ground_look_is_its_mesh_and_material(self):
        look = {'mesh': GROUND['mesh'], 'material': GROUND['material'], 'measure': 1}
        self.assertEqual(looks.resolve('ground', look, folder=self.folder)['recipe']['repeat'], 256.0)
        with self.assertRaises(looks.LookError):
            looks.resolve('ground', dict(look, material='Pkg.Materials.Mud'), folder=self.folder)
        with self.assertRaises(looks.LookError):
            looks.check_look('ground', {'mesh': GROUND['mesh'], 'measure': 1})

    def test_an_uncatalogued_look_is_measured_on_its_donor_once(self):
        calls = []

        def measure(package, actor):
            calls.append((package.path, actor))
            return {'recipe': {'top': 384.0, 'sections': 6}, 'warnings': ["its window frames and ledges aren't made"]}

        fake = types.SimpleNamespace(VERSION=1, measure=measure)
        package = types.SimpleNamespace(path='MapC.upk')
        look = {'mesh': 'Other.Meshes.WallB_FRACTURED', 'measure': 1}
        with mock.patch.object(looks, 'measurer', return_value=fake):
            with self.assertRaises(looks.LookError):
                looks.resolve('wall', look, folder=self.folder)          # nothing to measure
            for _ in range(2):
                out = looks.resolve('wall', look, package, 'XComFracLevelActor_7', folder=self.folder)
        self.assertEqual(calls, [('MapC.upk', 'XComFracLevelActor_7')])
        self.assertEqual(out['recipe']['top'], 384.0)
        self.assertEqual(out['warnings'], ["its window frames and ledges aren't made"])

    def test_an_uncatalogued_ground_look_is_measured_for_its_material(self):
        seen = []
        fake = types.SimpleNamespace(VERSION=1, measure=lambda p, a, material=None: seen.append(material) or {'recipe': {'thickness': 8.0}})
        look = {'mesh': 'Farm.Meshes.Plane', 'material': 'Farm.Materials.Mud', 'measure': 1}
        with mock.patch.object(looks, 'measurer', return_value=fake):
            looks.resolve('ground', look, types.SimpleNamespace(path='Farm.upk'), 'XComLevelActor_3', folder=self.folder)
        self.assertEqual(seen, ['Farm.Materials.Mud'])

    def test_a_look_of_another_measurer_version_is_refused(self):
        fake = types.SimpleNamespace(VERSION=2, measure=lambda p, a: {'recipe': {}})
        package = types.SimpleNamespace(path='MapC.upk')
        with mock.patch.object(looks, 'measurer', return_value=fake):
            with self.assertRaises(looks.LookError):
                looks.resolve('wall', {'mesh': 'Other.Meshes.WallB', 'measure': 1}, package, 'A_1', folder=self.folder)
            # the catalogue was built by version 1: a look read by version 2 is measured
            out = looks.resolve('wall', {'mesh': WALL['mesh'], 'measure': 2}, package, 'A_1', folder=self.folder)
        self.assertEqual(out['recipe'], {})

    def test_requests_with_a_look_id_are_left_alone(self):
        for generated in ({'kind': 'fracWall', 'version': 2, 'wall': {'x0': 0, 'x1': 192, 'look': 'bar-inside'}},
                          {'kind': 'fracSlab', 'version': 1, 'slab': {'x0': 0, 'x1': 96, 'y0': 0, 'y1': 96}},
                          {'kind': 'relit'}):
            self.assertIs(looks.resolved(generated, folder=self.folder), generated)
        done = looks.resolved({'kind': 'fracWall', 'version': 3,
                               'wall': {'x0': 0, 'x1': 192, 'look': {'mesh': WALL['mesh'], 'measure': 1}}},
                              folder=self.folder)
        self.assertEqual(done['wall']['look']['recipe']['sections'], 4)
        self.assertIs(looks.resolved(done, folder=self.folder), done)

    def test_the_listing_has_the_numbers_the_page_draws_by(self):
        rows = looks.listing('wall', folder=self.folder)
        self.assertEqual((rows['kind'], rows['measure'], len(rows['looks'])), ('wall', 1, 1))
        row = rows['looks'][0]
        self.assertEqual(row['recipe'], {k: WALL['recipe'][k] for k in looks.PAGE_RECIPE['wall']})
        self.assertNotIn('section', row['recipe'])
        self.assertEqual(row['name'], 'Wall A')
        self.assertEqual(row['surfaces'], {})       # (its recipe holds no maps: nothing said of its surfaces)
        self.assertEqual(looks.listing('slab', folder=self.folder)['looks'], [])     # no catalogue yet


def side(slot, fit):
    """A wall recipe's side: an outline whose middle segment is a face (12 to 180 up) in `slot`, textured by `fit`."""
    return dict(profile=[[8.0, -16.0], [8.0, 12.0], [8.0, 180.0], [8.0, 192.0]],
                strips=[dict(slot=1, face=False), dict(slot=None, face=True), dict(slot=1, face=False)], fit=fit, slot=slot)


class Surfaces(unittest.TestCase):
    """Whether a look's surfaces tile, from its recipe's maps over its donor's face (looks.surfaces: the module's
    rule), on made-up recipes and on the checked-in catalogues' looks named for an atlas or a tiling texture."""

    def test_the_rule_along_each_axis(self):
        # 384 by 168 of a 192 tile: two repeats along, 0.875 up inside one repeat, square: it tiles both ways
        self.assertEqual(looks.tiling([[1 / 192, 0, 0], [0, -1 / 192, 0.0625 + 180 / 192]], (0, 384), (12, 180)),
                         dict(repeat=[192.0, 192.0], share=[2.0, 0.875], tiles=[True, True]))
        # the subway car roof's top: 302 along, 584 across, the top half of its texture across it: a window across
        fit = [[0.0, 1 / 302.2, 0.1], [1 / 583.7, 0.0, 0.017 + 143 / 583.7]]
        self.assertEqual(looks.tiling(fit, (-143, 143), (0, 1776))['tiles'], [True, False])
        # across a repeat's edge, though under one repeat long: it tiles (a window never crosses its texture's edge)
        self.assertEqual(looks.tiling([[1 / 300, 0, 0.9], [0, 1 / 700, 0.2]], (0, 60), (0, 100))['tiles'], [True, False])
        # a coordinate that doesn't change: a strip of a texture, no repeat
        out = looks.tiling([[1 / 96, 0, 0], [0, 0, 0.2]], (0, 192), (0, 96))
        self.assertEqual((out['repeat'], out['tiles']), ([96.0, None], [True, False]))
        # not placed (a ground look's): its span alone
        self.assertEqual(looks.tiling([[1 / 300, 0, 0.9], [0, 1 / 700, 0.2]], (0, 60), (0, 100), placed=False)['tiles'],
                         [False, False])

    def test_a_wall_side_with_no_face_and_each_slot_over_its_band(self):
        a = side(0, [[1 / 192, 0, 0], [0, -1 / 192, 1.0]])
        b = side(2, [[1 / 288, 0, 0], [0, -1 / 916, 0.46]])
        R = dict(profile=dict(A=a['profile'], B=b['profile']), strips=dict(A=a['strips'], B=[dict(slot=1, face=False)] * 3),
                 slots=dict(sideA=[0], sideB=[]), splits=dict(A=[], B=[]), faceUV={'0A': a['fit']}, frame=dict(x=[0.0, 864.0]))
        found = looks.surfaces('wall', dict(recipe=R))['faces']
        self.assertIsNone(found['B'])
        self.assertEqual(found['A'], dict(slots=[0], repeat=[192.0, 192.0], share=[4.5, 0.875], tiles=[True, True]))
        # side B a face too, a band of a UFO texture: tiles along, a window up
        R = dict(R, strips=dict(A=a['strips'], B=b['strips']), slots=dict(sideA=[0], sideB=[2]), faceUV={'0A': a['fit'], '2B': b['fit']})
        self.assertEqual(looks.surfaces('wall', dict(recipe=R))['faces']['B']['tiles'], [True, False])
        # two slots up side A, split at 96: each read over its own band of the face (a part of its texture up each)
        two = dict(R, slots=dict(sideA=[0, 3], sideB=[2]), splits=dict(A=[96.0], B=[]),
                   faceUV={'0A': [[1 / 192, 0, 0], [0, -1 / 400, 0.5]], '3A': [[1 / 192, 0, 0], [0, -1 / 400, 0.6]], '2B': b['fit']})
        self.assertEqual(looks.surfaces('wall', dict(recipe=two))['faces']['A']['tiles'], [True, False])

    def test_the_catalogues_named_looks(self):
        # (the checked-in catalogues: atlases and plain tiling textures one can name)
        def faces(mesh):
            return looks.surfaces('wall', looks.entry('wall', mesh))['faces']
        roof = looks.surfaces('slab', looks.entry('slab', 'SubwayTrain.Meshes.SubwayCarRoof_FRACTURED'))
        self.assertEqual((roof['top']['tiles'], roof['underside']['tiles']), ([True, False], [True, False]))
        self.assertEqual(roof['top']['slots'], roof['underside']['slots'])        # (one texture: its two halves)
        for mesh in ('SubwayTrain.Meshes.SubwayEngineInnerWall_FRACTURED', 'SupplyShipBody.MeshesContainers.SupplyCrateWalls_FRACTURED',
                     'AbductorExtWall.Meshes.AbductorExtWallx9_FRACTURED', 'ExaltHoloGlobe.Meshes.ExaltHoloGlobeWall_A_FRC'):
            self.assertTrue(any(s and False in s['tiles'] for s in faces(mesh).values()), mesh)
        # tiling textures on donors narrower than a repeat: the core floors' 88 across a 192 tile, the facades' 168 up,
        # a joint strip 52 up, the police station's walls (a 176-long one under one repeat both ways)
        core = looks.surfaces('slab', looks.entry('slab', 'ComKit_Meshes.Cores.Core_320FloorC_FRACTURED'))
        self.assertEqual((core['top']['share'][1] < 0.5, core['top']['tiles']), (True, [True, True]))
        for mesh in ('ComKit_Meshes.Cores.Core_384FacadeB_FRACTURED', 'URB_PoliceStationBuilding.Meshes.PoliceStationWallB_FRACTURED',
                     'ComKit_WallsEXT_Meshes.Walls_ExtJOINT.Wall_ExtJOINT_320to256_FRACTURED'):
            self.assertTrue(all(s is None or s['tiles'] == [True, True] for s in faces(mesh).values()), mesh)
        # a doorway of the UFO, its outline all trims: no face either side
        self.assertEqual(faces('AbductorExtWall.Meshes.AbductorExtAltWallDoorwayx9_FRACTURED'), dict(A=None, B=None))

    def test_the_mapped_surfaces_a_look_draws_from_an_atlas(self):
        roof = dict(look=dict(mesh='SubwayTrain.Meshes.SubwayCarRoof_FRACTURED', measure=1))
        size = dict(mode='size', u=96.0, v=96.0)
        self.assertEqual(looks.mapped_windows('slab', roof), [])
        self.assertEqual(looks.mapped_windows('slab', dict(roof, mapping=dict(surfaces=dict(underside=size, top=size)))),
                         ['top', 'underside'])
        crate = dict(look=dict(mesh='SupplyShipBody.MeshesContainers.SupplyCrateWalls_FRACTURED', measure=1),
                     mapping=dict(surfaces=dict(faces=size)))
        self.assertEqual(looks.mapped_windows('wall', crate), ['faces'])
        self.assertEqual(looks.mapped_windows('wall', dict(crate, look='bar-inside')), [])
        self.assertEqual(looks.mapped_windows('wall', dict(crate, look=dict(mesh='Not.Catalogued', measure=1))), [])


class RequestVersions(unittest.TestCase):
    """frac_walls.check: a look named by its donor comes with walls' request version 3 and slabs' and ground shapes'
    version 2, which always name one, resolved; a look id with the older versions."""

    def test_a_donor_look_comes_with_its_request_version_resolved(self):
        import frac_walls
        donor = {'mesh': WALL['mesh'], 'measure': 1}
        wall = {'x0': 0, 'x1': 192, 'openings': []}
        slab = {'x0': 0, 'x1': 96, 'y0': 0, 'y1': 96}
        ground = {'shape': 'patch', 'x0': 0, 'x1': 96, 'y0': 0, 'y1': 96}
        for bad in ({'kind': 'fracWall', 'version': 3, 'wall': dict(wall, look=donor)},          # not resolved
                    {'kind': 'fracWall', 'version': 2, 'wall': dict(wall, look=dict(donor, recipe={}))},
                    {'kind': 'fracWall', 'version': 3, 'wall': dict(wall, look='bar-inside')},
                    {'kind': 'fracWall', 'version': 3, 'wall': wall},
                    {'kind': 'fracSlab', 'version': 2, 'slab': slab},
                    {'kind': 'fracSlab', 'version': 1, 'slab': dict(slab, look=dict(donor, recipe={}))},
                    {'kind': 'fracSlab', 'version': 3, 'slab': slab},
                    {'kind': 'ground', 'version': 2, 'ground': dict(ground, look=dict(donor, recipe={}))}):     # no material
            with self.assertRaises(ValueError, msg=bad):
                frac_walls.check(bad)


if __name__ == '__main__':
    unittest.main()

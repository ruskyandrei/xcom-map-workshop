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
        self.assertEqual(looks.listing('slab', folder=self.folder)['looks'], [])     # no catalogue yet


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

"""The slab and ground catalogues (tools/bake/looks/slabs.json, ground.json; slab_catalogue.py, ground_catalogue.py;
custom geometry plan, M4 work order B): the checked-in files are well formed (LF, sorted, every entry with the
contract's fields, no folder of one computer), they hold today's named looks' donors, every look's recipe builds;
on the install, a build gives the same bytes twice."""
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
for folder in ('viewer', 'upk', 'lab'):
    sys.path.insert(0, str(HERE.parents[1] / folder))
sys.path.insert(0, str(HERE.parent))
import frac_slab  # noqa: E402
import ground  # noqa: E402
import ground_catalogue  # noqa: E402
import ground_measure  # noqa: E402
import slab_catalogue  # noqa: E402
import slab_measure  # noqa: E402

FIELDS = {'mesh', 'map', 'actor', 'maps', 'name', 'setting', 'lwrOnly', 'facts', 'warnings', 'twin', 'recipe'}


def install():
    import settings
    try:
        game, _ = settings.game_install(settings.load_settings())
    except Exception:       # (no settings file: the tests that need the install skip)
        return None
    return game


class Files(unittest.TestCase):
    def check_file(self, path, version, key):
        raw = path.read_bytes()
        self.assertNotIn(b'\r', raw)
        self.assertTrue(raw.endswith(b'\n'))
        data = json.loads(raw.decode('utf-8'))
        self.assertEqual(raw.decode('utf-8'), slab_catalogue.dump(data))      # written the one way
        self.assertEqual(data['measure'], version)
        self.assertTrue(data['built'].startswith('<game>'))
        self.assertIn('lwrOnly', data['about'])
        self.assertEqual(data['looks'], sorted(data['looks'], key=key))
        for e in data['looks']:
            self.assertLessEqual(FIELDS, set(e), e.get('mesh'))
            self.assertIs(e['lwrOnly'], False)
            self.assertIsInstance(e['twin'], str)
            self.assertTrue(e['maps'] and e['map'] in e['maps'], e['mesh'])
            self.assertTrue(all(isinstance(w, str) and w for w in e['warnings']))
        return data

    def test_the_slab_catalogue(self):
        data = self.check_file(slab_catalogue.CATALOGUE, slab_measure.VERSION, lambda e: e['mesh'])
        meshes = [e['mesh'] for e in data['looks']]
        self.assertEqual(len(meshes), len(set(meshes)))
        for e in data['looks']:
            self.assertEqual({'role', 'kind', 'thickness', 'layout'} - set(e['facts']), set(), e['mesh'])
        # today's looks' donors are in it (D18: the named looks are shortcuts to them)
        for look in frac_slab.LOOKS.values():
            self.assertIn(look['donor'], meshes)

    def test_the_ground_catalogue(self):
        data = self.check_file(ground_catalogue.CATALOGUE, ground_measure.VERSION,
                               lambda e: (e['material'], e['mesh']))
        materials = [e['material'] for e in data['looks']]
        self.assertEqual(len(materials), len(set(materials)))       # one entry a material
        for e in data['looks']:
            self.assertEqual(e['recipe']['material'], e['material'])
            self.assertEqual({'thickness', 'painted', 'material'} - set(e['facts']), set(), e['material'])
            self.assertIsNone(e['facts']['leftOut'], e['material'])
        for look in ground.LOOKS.values():
            self.assertIn(look['material'], materials)

    def test_every_slab_look_builds(self):
        data = json.loads(slab_catalogue.CATALOGUE.read_text(encoding='utf-8'))
        for e in data['looks']:
            out = frac_slab.build(dict(x0=0.0, x1=192.0, y0=0.0, y1=192.0, seed=1,
                                       look=dict(mesh=e['mesh'], measure=data['measure'], recipe=e['recipe'])))
            self.assertEqual(len(out['mesh']['lods'][0]['sections']), e['recipe']['sections'], e['mesh'])

    def test_every_ground_look_builds(self):
        data = json.loads(ground_catalogue.CATALOGUE.read_text(encoding='utf-8'))
        for e in data['looks']:
            look = dict(mesh=e['mesh'], material=e['material'], measure=data['measure'], recipe=e['recipe'])
            for shape in (dict(shape='patch', x0=0.0, x1=192.0, y0=0.0, y1=96.0),
                          dict(shape='ramp', x0=0.0, x1=288.0, y0=0.0, y1=96.0, height=64.0)):
                out = ground.build(dict(shape, look=look))
                self.assertEqual(len(out['mesh']['lods'][0]['sections']), e['recipe']['sections'], e['material'])


def plain(v):
    """A value as the catalogue file holds it (tuples as lists)."""
    return json.loads(json.dumps(v))


class Fresh(unittest.TestCase):
    """A few looks of each catalogue, measured afresh on their donors, give their checked-in entries (review finding
    57): a measurer changed without its version raised fails here, as the walls' catalogue does in test_wall_measure."""
    COUNT = 3

    @classmethod
    def setUpClass(cls):
        game = install()
        if game is None:
            raise unittest.SkipTest('the game install is not configured (python tools/viewer/viewer.py settings)')
        cls.maps = {n: path for n, _, path in slab_catalogue.maps_of(game)}

    def sample(self, catalogue):
        """A few entries spread over the file, from maps the install lists, each with its donor's package open."""
        from package import Package
        looks = [e for e in json.loads(catalogue.read_text(encoding='utf-8'))['looks'] if e['map'] in self.maps]
        if not looks:
            self.skipTest('the install lists none of the donor maps')
        picked = looks[::max(1, len(looks) // self.COUNT)][:self.COUNT]
        return [(e, Package(self.maps[e['map']])) for e in picked]

    def test_slab_looks_measured_afresh_are_the_catalogues(self):
        import gen_mesh
        import measure_common as mc
        for e, p in self.sample(slab_catalogue.CATALOGUE):
            found = slab_measure.measure(p, e['actor'])
            _, _, mesh = mc.find_placing(p, e['actor'], slab_measure.FRACTURING, 'FracturedStaticMeshComponent')
            facts = plain({k: v for k, v in found['facts'].items() if k not in ('mesh', 'actor')})
            self.assertEqual(plain(found['recipe']), e['recipe'], e['mesh'])
            self.assertEqual(facts, {k: e['facts'].get(k) for k in facts}, e['mesh'])
            self.assertEqual(found['warnings'], e['warnings'], e['mesh'])
            self.assertEqual(slab_measure.verdict(slab_measure.twin(found['recipe'], gen_mesh.read(p, mesh))), e['twin'],
                             e['mesh'])

    def test_ground_looks_measured_afresh_are_the_catalogues(self):
        import gen_mesh
        import measure_common as mc
        for e, p in self.sample(ground_catalogue.CATALOGUE):
            found = ground_measure.measure(p, e['actor'], e['material'])
            _, _, mesh = mc.find_placing(p, e['actor'], ground_measure.PLAIN, 'StaticMeshComponent')
            # (the catalogue adds its placings' counts and paint signs to what the measure finds)
            facts = plain({k: v for k, v in found['facts'].items() if k not in ('mesh', 'actor', 'painted')})
            self.assertEqual(found['facts']['mesh'], e['mesh'])
            self.assertEqual(plain(found['recipe']), e['recipe'], e['material'])
            self.assertEqual(facts, {k: e['facts'].get(k) for k in facts}, e['material'])
            self.assertEqual(found['warnings'], e['warnings'][:len(found['warnings'])], e['material'])
            self.assertEqual(ground_measure.verdict(ground_measure.twin(found['recipe'], gen_mesh.read(p, mesh))),
                             e['twin'], e['material'])


class Rebuilt(unittest.TestCase):
    """A build over one map, twice: the same bytes."""

    def test_the_same_bytes_twice(self):
        game = install()
        if game is None:
            self.skipTest('the game install is not configured (python tools/viewer/viewer.py settings)')
        import library
        if 'URB_Bar' not in {n for n, _, _ in library.donors(game)}:
            self.skipTest('the install lists no URB_Bar')
        for builder in (slab_catalogue, ground_catalogue):
            first = builder.build(game, ['URB_Bar'])
            self.assertEqual(builder.build(game, ['URB_Bar']), first, builder.__name__)
            self.assertTrue(json.loads(first)['looks'], builder.__name__)


if __name__ == '__main__':
    unittest.main()

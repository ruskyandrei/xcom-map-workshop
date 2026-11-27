"""A baked Build's own light in the viewer's cache (build_light.py; the game-likeness plan's B4): the components it
holds, its export written once beside its place with the variant's older Builds pruned, and the route that joins it
with the manifest, on a made-up Build whose one added piece has a lightmap; its files served from /cache-builds/.
Reading a piece's baked light is B1's (export.Exporter.baked; test_baked_light.py on the install): a stand-in reads it
here. The textures a Build did not write are found in the folder a package is told its caches are in."""
from functools import partial
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_light  # noqa: E402
from builds import BuildRunner  # noqa: E402
import package  # noqa: E402
from projects import ProjectStore  # noqa: E402
from viewer_fixtures import ID, OTHER, document  # noqa: E402
from viewer import Handler, LocalServer  # noqa: E402

PL = 'TheWorld.PersistentLevel.'
VARIANT = 'URB_Bar_Remix_0f8b'
BUILD_ID = VARIANT + '-20261127-101500-0a1b2c3d'
ADDED = PL + 'XComLevelActor_44_copy3'          # the project's added piece, and the actor the Build made for it
BUILT = PL + 'XComLevelActor_412'
LIGHTMAP = dict(colour='build-901', directions='build-902', scale0=[1, 1, 1], scale1=[2, 2, 2], uvScale=[0.25, 0.25],
                uvBias=[0.5, 0.25], channel=1)


def manifest(**changes):
    """A baked Build's manifest (build.py) of the project ID: its one added piece made as BUILT."""
    m = dict(schema='xcom-map-workshop/package', buildId=BUILD_ID, builtAt='2026-11-27T10:15:00', quick=False,
             variant=VARIANT, project=dict(id=ID, revision=4), source=dict(map='URB_Bar'), files={},
             lightingUnchanged=False, builtActors={ADDED: BUILT}, relitComponents=[PL + 'XComLevelActor_8.StaticMeshComponent_2'],
             asBuilt=document(added=[dict(id='e', actor=ADDED, components=[PL + 'XComLevelActor_44.StaticMeshComponent_7'],
                                          location=[0, 0, 0], rotation=[0, 0, 0])]))
    m.update(changes)
    return m


class StandIn:
    """What components() asks of a package: its exports by name, their children and classes."""
    def __init__(self, exports):
        self.paths = list(exports)
        self.by_name = {name: k for k, name in enumerate(self.paths, 1)}
        self.classes = dict(enumerate(exports.values(), 1))
        self.children = {}
        for k, name in enumerate(self.paths, 1):
            outer = self.by_name.get(name.rsplit('.', 1)[0], 0)
            self.children.setdefault(outer, []).append(k)

    def cls(self, index):
        return self.classes[index]


def read_stand_in(package_path, m, out, caches=None):
    """build_light.read's stand-in: the added piece's built component with a lightmap in two atlases of the Build's,
    one of them the map's own texture written again (its name)."""
    (Path(out) / 'texture-build-901.dds').write_bytes(b'DDS colour')
    (Path(out) / 'texture-build-902.dds').write_bytes(b'DDS directions')
    return dict(format=build_light.FORMAT, buildId=m['buildId'], diagnostics=[],
                pieces={BUILT + '.StaticMeshComponent_7': dict(lightmap=LIGHTMAP, sunIrrelevant=True)},
                textures={'build-901': dict(name='NormalizedAverageColor1_91', format='PF_DXT1', url='texture-build-901.dds', container='dds'),
                          'build-902': dict(name='DirectionalMaxComponent0_1', format='PF_DXT1', url='texture-build-902.dds', container='dds')})


class TheBuildsLight(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache, self.output = self.root / 'cache', self.root / 'builds'
        self.cache.mkdir()
        self.store = ProjectStore(self.root / 'projects')
        self.store.save(ID, document(output=dict(shipAs=VARIANT, patch='patch_urb_bar_remix_0f8b')), 0)
        self.store.save(OTHER, document(OTHER, output=dict(shipAs='URB_Bar_Other_1a2b', patch='patch_urb_bar_other_1a2b')), 0)
        self.package(manifest())

    def package(self, m, variant=VARIANT):
        folder = self.output / variant / 'CookedPCConsole'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / ('%s.upk' % variant)).write_bytes(b'the built map')
        (self.output / variant / 'manifest.json').write_text(json.dumps(m), encoding='utf-8')

    def test_a_baked_build_that_relit_the_map_has_a_light_of_its_own(self):
        self.assertTrue(build_light.has_light(manifest()))
        for changes in (dict(quick=True), dict(lightingUnchanged=True), dict(builtActors=None), dict(asBuilt=None),
                        dict(buildId='../elsewhere')):
            with self.subTest(changes):
                self.assertFalse(build_light.has_light(manifest(**changes)))
        self.assertFalse(build_light.has_light(None))
        self.assertEqual(build_light.folder(self.cache, BUILD_ID), self.cache / 'builds' / BUILD_ID)
        self.assertIsNone(build_light.folder(self.cache, '..\\x'))

    def test_it_holds_each_built_actors_mesh_components_and_every_relit_one(self):
        p = StandIn({PL + 'XComLevelActor_412': 'XComLevelActor', BUILT + '.StaticMeshComponent_7': 'StaticMeshComponent',
                     BUILT + '.XComDestructibleActor_Action_0': 'XComDestructibleActor_Action',
                     PL + 'XComFracLevelActor_30': 'XComFracLevelActor',
                     PL + 'XComFracLevelActor_30.FracturedStaticMeshComponent_1': 'FracturedStaticMeshComponent',
                     PL + 'XComLevelActor_8': 'XComLevelActor', PL + 'XComLevelActor_8.StaticMeshComponent_2': 'StaticMeshComponent'})
        # (a made piece cut into parts is drawn whole by the page and lit live: its parts are not read)
        m = manifest(builtActors={ADDED: BUILT, PL + 'XComFracLevelActor_2_copy4': [PL + 'XComFracLevelActor_30'],
                                  PL + 'Missing_copy1': PL + 'Missing_1'},
                     relitComponents=[PL + 'XComLevelActor_8.StaticMeshComponent_2', PL + 'Gone.StaticMeshComponent_1'])
        self.assertEqual([p.paths[k - 1] for k in build_light.components(p, m)],
                         [BUILT + '.StaticMeshComponent_7', PL + 'XComLevelActor_8.StaticMeshComponent_2'])

    def test_the_export_is_written_once_and_the_variants_older_builds_go(self):
        older, other = self.cache / 'builds' / (VARIANT + '-20261126-090000'), self.cache / 'builds' / 'URB_Bar_Other_1a2b-20261126-090000'
        for folder in (older, other):
            folder.mkdir(parents=True)
            (folder / 'light.json').write_text('{}', encoding='utf-8')
        calls = []
        with mock.patch.object(build_light, 'read', lambda *a: calls.append(a) or read_stand_in(*a)):
            first = build_light.export(self.output / VARIANT / 'CookedPCConsole' / ('%s.upk' % VARIANT), manifest(), self.cache, 'maps')
            again = build_light.export(self.output / VARIANT / 'CookedPCConsole' / ('%s.upk' % VARIANT), manifest(), self.cache, 'maps')
        self.assertEqual((len(calls), calls[0][3]), (1, 'maps'))
        self.assertEqual(first, again)
        target = self.cache / 'builds' / BUILD_ID
        self.assertEqual(json.loads((target / 'light.json').read_text(encoding='utf-8')), first)
        self.assertEqual((target / 'texture-build-901.dds').read_bytes(), b'DDS colour')
        self.assertEqual(sorted(p.name for p in (self.cache / 'builds').iterdir()), sorted([BUILD_ID, other.name]))

    def test_a_package_reads_its_textures_caches_from_the_folder_it_is_told(self):
        maps = self.root / 'maps'
        maps.mkdir()
        (maps / 'Lighting.tfc').write_bytes(b'tfc')
        here = self.output / VARIANT / 'CookedPCConsole'
        self.assertEqual(package.cache_file(here, 'Lighting', maps), maps / 'Lighting.tfc')
        self.assertEqual(package.cache_file(here, 'Lighting'), here / 'Lighting.tfc')
        (here / 'Lighting.tfc').write_bytes(b'its own')
        self.assertEqual(package.cache_file(here, 'Lighting', maps), here / 'Lighting.tfc')

    def test_the_route_gives_the_added_pieces_lightmap_with_the_manifests_records(self):
        """A made-up Build whose one added piece has a lightmap: the page asks for its light and gets the piece's record
        by its built component, the actor each project piece became and the project as built, and the atlases' files."""
        runner = BuildRunner(self.store, self.cache, self.output)
        server = LocalServer(('127.0.0.1', 0), partial(Handler, catalogue=dict(defaultMap=None, maps={}), projects=self.store,
                                                       builds=runner))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = 'http://127.0.0.1:%d' % server.server_port

        def get(path):
            try:
                with urlopen(base + path, timeout=10) as r:
                    body = r.read()
                    return r.status, json.loads(body) if r.headers.get('Content-Type') == 'application/json' else body
            except HTTPError as error:
                return error.code, json.loads(error.read()) if error.headers.get('Content-Type') == 'application/json' else None

        self.assertTrue(get('/projects/%s/build.json' % ID)[1]['package']['light'])
        with mock.patch.object(build_light, 'read', read_stand_in):
            status, light = get('/projects/%s/build-light.json' % ID)
        self.assertEqual(status, 200, light)
        self.assertEqual((light['buildId'], light['builtAt'], light['revision'], light['map']), (BUILD_ID, '2026-11-27T10:15:00', 4, 'URB_Bar'))
        self.assertEqual(light['actors'], {ADDED: BUILT})
        self.assertEqual(light['project']['added'][0]['actor'], ADDED)
        self.assertEqual(light['pieces'], {BUILT + '.StaticMeshComponent_7': dict(lightmap=LIGHTMAP, sunIrrelevant=True)})
        self.assertEqual(light['base'], '/cache-builds/%s/' % BUILD_ID)
        self.assertEqual(get(light['base'] + light['textures']['build-901']['url']), (200, b'DDS colour'))
        # (only a Build's folder is served, and nothing outside it)
        self.assertEqual(get('/cache-builds/%s/../../builds/%s/manifest.json' % (BUILD_ID, VARIANT))[0], 404)
        self.assertEqual(get('/cache-builds/nothing/light.json')[0], 404)
        # a quick Build has no light of its own; a project never built has none either
        self.package(manifest(quick=True))
        self.assertNotIn('light', get('/projects/%s/build.json' % ID)[1]['package'])
        self.assertEqual(get('/projects/%s/build-light.json' % ID)[0], 404)
        self.assertEqual(get('/projects/%s/build-light.json' % OTHER)[0], 404)


if __name__ == '__main__':
    unittest.main()

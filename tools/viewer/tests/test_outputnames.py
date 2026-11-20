"""A project's output names (tools/viewer/outputnames.py; output names plan): the name conversion, the allocation of a
new project's map name, who holds which names, the server's preview and the store's check as it saves."""
from functools import partial
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'bake' / 'tests'))
import installs  # noqa: E402  (it puts tools/bake on the path)
import deploy_fixture as dep  # noqa: E402
import outputnames as names  # noqa: E402
from projects import ProjectError, ProjectStore  # noqa: E402
from fixtures import record  # noqa: E402
from viewer_fixtures import ID, OTHER, document  # noqa: E402
from viewer import Handler, LocalServer  # noqa: E402

THIRD = '2b3c4d5e-6f7a-4b2c-9d3e-4f5a6b7c8d9e'


def game(folder, packages=('URB_Bar.upk', 'CIN_DropshipIntros.upk', 'Lighting.tfc')):
    """A game install: its config and packages, URB_Bar's record streaming the landing intro."""
    (folder / 'XEW/XComGame/Config').mkdir(parents=True)
    (folder / 'XEW/XComGame/CookedPCConsole').mkdir(parents=True)
    (folder / 'XEW/XComGame/Config/DefaultMaps.ini').write_bytes(dep.EOL.join([b'[XComGame.XComMapManager]', record('bar'), b'']))
    for name in packages:
        (folder / 'XEW/XComGame/CookedPCConsole' / name).write_bytes(b'x')
    return folder


class Conversion(unittest.TestCase):
    def test_a_project_name_becomes_one_word(self):
        """Plan 3.1, steps 1-4: the same vectors whatever the name's form."""
        for typed, word in [
                ('Commercial restaurant fix', 'CommercialRestaurantFix'),
                ('URB_Bar fix', 'URB_BarFix'),                  # letters, digits and _ as typed
                ('bar remix', 'BarRemix'),
                ('x', 'X'),                                     # one letter
                ('2nd try', 'Map2ndTry'),                       # no letter first
                ('_under', 'Map_under'),
                ('', 'Map'), ('!!! ???', 'Map'),                # nothing left
                ('café', 'Cafe'), ('café', 'Cafe'),       # precomposed and decomposed accents alike
                ('Café au lait', 'CafeAuLait'),                 # an accent never splits a word
                ('Ελληνικά', 'Map'),                            # no promise to transliterate other alphabets
                ('patch_bar', 'MapPatch_bar'), ('PT_x', 'MapPT_x'), ('pp_y', 'MapPp_y'),     # kept prefixes
                ('CIN_DropshipIntros_bar', 'MapCIN_DropshipIntros_bar'),
                ('patch bar', 'PatchBar'),                      # no underscore: no kept prefix
        ]:
            with self.subTest(typed):
                self.assertEqual(names.convert(typed), word)

    def test_names_are_cut_to_24_and_numbered_within_it(self):
        stem = 'A' * 30
        tried = list(names.candidates(stem))
        self.assertEqual(tried[0], 'A' * 24)
        self.assertEqual((tried[1], tried[8], tried[9]), ('A' * 22 + '_2', 'A' * 22 + '_9', 'A' * 21 + '_10'))
        self.assertTrue(all(len(t) <= 24 for t in tried))
        self.assertEqual(len(tried), names.ATTEMPTS)
        self.assertEqual(names.patch_name('URB_BarFix'), 'patch_urb_barfix')
        self.assertEqual(names.cache_name('URB_BarFix'), 'URB_BarFix_Lighting')
        self.assertEqual(len(names.patch_name('A' * 24)), 30)       # a new map name leaves room for its patch

    def test_allocation_numbers_taken_and_device_names_and_says_why(self):
        free = lambda found: None  # noqa: E731
        self.assertEqual(names.allocate('Commercial restaurant fix', free),
                         dict(shipAs='CommercialRestaurantFix', patch='patch_commercialrestaurantfix', reason=None))
        taken = {'barfix', 'patch_barfix_2'}        # the second through its patch
        holds = lambda found: next((f'{n} is held' for n in found if n.lower() in taken), None)  # noqa: E731
        out = names.allocate('Bar fix', holds)
        self.assertEqual(out['shipAs'], 'BarFix_3')
        self.assertIn('BarFix is taken (BarFix is held)', out['reason'])
        self.assertEqual(names.allocate('con', free)['shipAs'], 'Con_2')
        self.assertIn('device', names.allocate('Nul', free)['reason'])
        self.assertIn('kept for other files', names.allocate('patch_x', free)['reason'])
        # an intro copy of the base map is one of the names checked
        intro = lambda found: 'held' if 'CIN_DropshipIntros_Foo' in found else None  # noqa: E731
        self.assertEqual(names.allocate('Foo', intro, ['CIN_DropshipIntros'])['shipAs'], 'Foo_2')
        # everything taken: a useful error, not a loop
        with self.assertRaisesRegex(names.NamesError, 'every name from Foo to Foo_999 is taken'):
            names.allocate('Foo', lambda found: 'held')

    def test_what_a_save_may_carry(self):
        free = lambda found: None  # noqa: E731
        self.assertIsNone(names.accepts('Bar fix', dict(shipAs='BarFix', patch='patch_barfix'), free))
        self.assertIsNone(names.accepts('Bar fix', dict(shipAs='BarFix_2', patch='patch_barfix_2'), free))
        self.assertIn('not a name the project name gives', names.accepts('Bar fix', dict(shipAs='Other', patch='patch_other'), free))
        self.assertIn('its patch must be', names.accepts('Bar fix', dict(shipAs='BarFix', patch='patch_x'), free))
        self.assertIn('package names', names.accepts('Bar fix', dict(shipAs='Bar Fix', patch='p'), free))


class ClaimsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.projects, self.builds = self.root / 'projects', self.root / 'builds'
        self.store = ProjectStore(self.projects)
        self.store.save(ID, document(output=dict(shipAs='BarRemix', patch='patch_barremix')), 0)

    def test_everything_that_holds_a_name_regardless_of_case(self):
        source, play = game(self.root / 'LWR'), game(self.root / 'Copy', packages=('Hand_Made.upk',))
        # a retained build whose project is gone, and a folder that is no build
        kept = self.builds / 'OldBuild'
        (kept / 'CookedPCConsole').mkdir(parents=True)
        (kept / 'manifest.json').write_text(json.dumps(dict(
            schema=names.BUILD_SCHEMA, variant='OldBuild', project=dict(id=OTHER, name='Gone'), patch='patch_oldbuild',
            cache='Lighting_1234', files={'CookedPCConsole/CIN_DropshipIntros_OldBuild.upk': 'x'})), encoding='utf-8')
        (self.builds / 'Junk').mkdir()
        (self.builds / '.work').mkdir()
        c = names.Claims(self.projects, self.builds, [source, play])
        for name in ('barremix', 'PATCH_BARREMIX', 'BarRemix_Lighting',                 # the project's
                     'oldbuild', 'Patch_OldBuild', 'lighting_1234', 'cin_dropshipintros_oldbuild',    # the build's
                     'junk', 'urb_bar', 'Lighting', 'hand_made',                          # a folder, both installs
                     'patch_bar', 'patch_hide_randomized_objects'):                       # streams a record loads
            with self.subTest(name):
                self.assertTrue(c.holders(name), name)
        self.assertFalse(c.holders('.work'))
        self.assertFalse(c.holders('Free'))
        self.assertIn('Gone', c.taken(['OldBuild']))
        # the project's own claims, proven by its id, don't count against it; a duplicate's do
        self.assertFalse(names.Claims(self.projects, self.builds, [], ID).holders('BarRemix'))
        self.store.save(OTHER, document(OTHER, name='Copy', output=dict(shipAs='BarRemix', patch='patch_barremix')), 0)
        self.assertTrue(names.Claims(self.projects, self.builds, [], ID).holders('barremix'))

    def test_what_the_editor_installed_and_whose_it_is(self):
        source = game(self.root / 'LWR', packages=('URB_Bar.upk', 'Mine.upk', 'Whose.upk'))
        installs.write_ledger(source, dict(playFiles={'Mine.upk': 'h', 'Whose.upk': 'h'}, owners={'Mine.upk': ID},
                                           rotation=[dict(variant='Campaign_X', base='URB_Bar', mode='additional', lines=[],
                                                          project=dict(id=OTHER))]))
        fresh, mine = names.Claims(None, None, [source]), names.Claims(None, None, [source], ID)
        self.assertTrue(fresh.holders('mine') and fresh.holders('whose') and fresh.holders('campaign_x'))
        # the project's own file is its own; one nothing says whose is left to the install step
        self.assertEqual((mine.holders('Mine'), mine.holders('Whose')), ([], []))
        self.assertTrue(mine.holders('Campaign_X'))

    def test_what_the_labs_deploys_put_in_the_lab_copy_is_soft(self):
        """A file the lab's deploy tools put in the lab copy before the editor could install (installs.lab_deploys) is
        a project's earlier test: it keeps a new project from taking its name, and doesn't stop a project's build (the
        install step checks its bytes). In an install that is not the lab copy the same file is anyone's."""
        source = game(self.root / 'LWR', packages=('URB_Bar.upk', 'URB_Bar_Exp17_7a1f.upk', 'patch_urb_bar_exp17_7a1f.upk'))
        lab = self.root / 'lab'
        (lab / 'bake-fixtures').mkdir(parents=True)
        (lab / 'patchtool').mkdir()
        fixture = source / 'XEW/XComGame/CookedPCConsole/URB_Bar_Exp17_7a1f.upk'
        (lab / 'bake-fixtures' / 'deployed.json').write_text(json.dumps({str(fixture): installs.sha256(fixture)}), encoding='utf-8')
        (lab / 'patchtool' / 'deployed.txt').write_text('patch_urb_bar_exp17_7a1f\n', encoding='utf-8')
        import settings
        from unittest import mock
        with mock.patch.object(settings, 'configured', side_effect=lambda key: lab if key == 'lab' else None):
            wanted = ['URB_Bar_Exp17_7a1f', 'patch_urb_bar_exp17_7a1f']
            self.assertEqual(len(names.Claims(None, None, [source], ID).conflicts(wanted)), 2)     # not the lab copy
            (source / 'XComLab-copy.txt').write_text('lab')
            self.assertEqual(names.Claims(None, None, [source], ID).conflicts(wanted), [])
            fresh = names.Claims(None, None, [source])
            self.assertIn('the lab\'s deploy tools', fresh.taken(['URB_Bar_Exp17_7a1f']))
            self.assertTrue(fresh.holders('patch_urb_bar_exp17_7a1f'))

    def test_a_source_that_is_set_but_unreadable_is_an_error(self):
        source = game(self.root / 'LWR')
        (source / installs.LEDGER_FOLDER).mkdir()
        (source / installs.LEDGER_FOLDER / 'installs.json').write_text('{not json')
        with self.assertRaisesRegex(names.NamesError, 'can\'t be read'):
            names.Claims(None, None, [source])


class Saving(unittest.TestCase):
    """The server's preview and the store's check as it saves (plan 3.3)."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, self.play = game(self.root / 'LWR'), None
        self.store = ProjectStore(self.root / 'projects')
        self.service = names.Service(self.store, self.root / 'builds', lambda: [(self.source, 'the game install'),
                                                                                (self.play, 'the install Play in game uses')])
        self.store.names = self.service

    def new(self, project_id, name, output=None):
        """A new project's first save with the names the preview gave (or `output`)."""
        output = output or self.service.preview(name, 'URB_Bar')['output']
        return self.store.save(project_id, document(project_id, name=name, output=output), 0)

    def test_a_new_project_saves_under_the_name_the_preview_gave(self):
        p = self.service.preview('Bar remix', 'URB_Bar')
        self.assertEqual((p['fresh'], p['output'], p['reason'], p['limit']),
                         (True, dict(shipAs='BarRemix', patch='patch_barremix'), None, 24))
        self.assertEqual(p['notes'], ['the install Play in game uses is not set, so the names are not checked against it yet'])
        self.new(ID, 'Bar remix')
        # a second project of that name is numbered, and says why
        p = self.service.preview('bar REMIX', 'URB_Bar')
        self.assertEqual(p['output']['shipAs'], 'BarREMIX_2')
        self.assertIn('BarREMIX is taken', p['reason'])
        # the map's own package and a package in another install the editor plays in are taken too
        self.assertEqual(self.service.preview('URB Bar', 'URB_Bar')['output']['shipAs'], 'URBBar')
        self.assertEqual(self.service.preview('URB_Bar', 'URB_Bar')['output']['shipAs'], 'URB_Bar_2')
        self.play = game(self.root / 'Copy', packages=('Elsewhere.upk',))
        self.assertEqual(self.service.preview('elsewhere', 'URB_Bar')['output']['shipAs'], 'Elsewhere_2')
        # an existing project's own names, fixed
        p = self.service.preview('Bar remix', 'URB_Bar', ID)
        self.assertEqual((p['fresh'], p['output']['shipAs'], p['conflicts']), (False, 'BarRemix', []))

    def test_names_are_fixed_once_saved(self):
        self.new(ID, 'Bar remix')
        doc = self.store.load(ID)
        # a case-only change of the name, and any other name: the output stays
        self.store.save(ID, dict(doc, name='BAR REMIX'), 1)
        self.assertEqual(self.store.load(ID)['output'], dict(shipAs='BarRemix', patch='patch_barremix'))
        for changed in (dict(shipAs='BARREMIX', patch='patch_barremix'), dict(shipAs='BarRemix', patch='patch_x'), None):
            with self.subTest(changed):
                with self.assertRaises(ProjectError) as e:
                    self.store.save(ID, {**dict(doc, name='Other'), **({'output': changed} if changed else {})}
                                    if changed else {k: v for k, v in doc.items() if k != 'output'}, 2)
                self.assertEqual(e.exception.status, 409)
                self.assertIn('fixed when it is', e.exception.message)
        # Save as: a new project, its own name
        self.new(OTHER, 'Bar remix')
        self.assertEqual(self.store.load(OTHER)['output']['shipAs'], 'BarRemix_2')
        # a store without the service (a tool's) checks only their form; a saved project's stay fixed all the same
        plain = ProjectStore(self.store.root)
        plain.save(THIRD, document(THIRD, name='Tool', output=dict(shipAs='Whatever', patch='patch_whatever')), 0)
        with self.assertRaises(ProjectError): plain.save(ID, dict(self.store.load(ID), output=dict(shipAs='X', patch='patch_x')), 2)
        with self.assertRaises(ProjectError) as e:
            plain.save(THIRD, document(THIRD, name='Tool', output=dict(shipAs='Bad name', patch='x')), 1)
        self.assertEqual(e.exception.status, 422)

    def test_a_name_taken_meanwhile_is_refused_with_the_one_it_would_get(self):
        shown = self.service.preview('Bar remix', 'URB_Bar')['output']
        self.new(ID, 'Bar remix', shown)
        with self.assertRaises(ProjectError) as e:
            self.new(OTHER, 'Bar remix', shown)
        self.assertEqual(e.exception.status, 409)
        self.assertEqual(e.exception.extra['proposal']['output'], dict(shipAs='BarRemix_2', patch='patch_barremix_2'))
        self.assertIn('BarRemix is taken', e.exception.extra['proposal']['reason'])
        self.assertIsNone(self.store._find(OTHER))         # nothing saved
        # names the project's name doesn't give, or none at all, are refused too
        with self.assertRaises(ProjectError) as e:
            self.new(OTHER, 'Bar remix', dict(shipAs='Unrelated', patch='patch_unrelated'))
        self.assertEqual(e.exception.status, 409)
        with self.assertRaises(ProjectError) as e:
            self.store.save(OTHER, document(OTHER, name='Bar remix'), 0)
        self.assertEqual(e.exception.status, 422)

    def test_two_first_saves_at_once_cannot_take_one_name(self):
        shown = self.service.preview('Same', 'URB_Bar')['output']
        results, start = {}, threading.Barrier(2)

        def save(project_id):
            start.wait()
            try: results[project_id] = self.new(project_id, 'Same', shown)
            except ProjectError as error: results[project_id] = error
        threads = [threading.Thread(target=save, args=(i,)) for i in (ID, OTHER)]
        for t in threads: t.start()
        for t in threads: t.join(timeout=30)
        refused = [r for r in results.values() if isinstance(r, ProjectError)]
        self.assertEqual((len(results), len(refused)), (2, 1))
        self.assertEqual(refused[0].extra['proposal']['output']['shipAs'], 'Same_2')

    def test_an_imported_project_with_anothers_names_is_diagnosed_not_renamed(self):
        self.new(ID, 'Bar remix')
        copy = dict(self.store.load(ID), id=OTHER, name='Imported')
        (self.store.root / 'Imported.json').write_text(json.dumps(copy), encoding='utf-8')
        self.store.list()
        # it opens and saves as it is (its names are its own, fixed), and the preview says they are taken elsewhere
        self.store.save(OTHER, self.store.load(OTHER), copy['revision'])
        p = self.service.preview('Imported', 'URB_Bar', OTHER)
        self.assertEqual(p['output']['shipAs'], 'BarRemix')
        self.assertTrue(any('Bar remix' in c for c in p['conflicts']))

    def test_the_route(self):
        server = LocalServer(('127.0.0.1', 0), partial(Handler, catalogue=dict(maps={}, defaultMap=None), projects=self.store))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(timeout=5)))

        def call(body, headers=None):
            request = Request(f'http://127.0.0.1:{server.server_port}/projects/output-names', data=json.dumps(body).encode(),
                              method='POST', headers={'Content-Type': 'application/json', **(headers or {})})
            try:
                with urlopen(request) as response: return response.status, json.load(response)
            except HTTPError as error: return error.code, json.load(error)
        status, p = call(dict(name='Bar remix', map='URB_Bar'))
        self.assertEqual((status, p['output']['shipAs']), (200, 'BarRemix'))
        self.assertEqual(call(dict(name='', map='URB_Bar'))[0], 422)
        self.assertEqual(call(dict(name='x', map='URB_Bar'), {'Origin': 'http://evil.example'})[0], 403)
        self.store.names = None
        self.assertEqual(call(dict(name='x', map='URB_Bar'))[0], 404)


if __name__ == '__main__':
    unittest.main()

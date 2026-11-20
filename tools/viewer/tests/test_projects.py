"""Project storage, its HTTP routes, and the settings/doctor (first-editor plan E1)."""
from functools import partial
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalogue import load_catalogue
from projects import SCHEMA_VERSION, ProjectError, ProjectStore, file_stem
import settings as settings_module
from viewer import Handler, LocalServer
from viewer_fixtures import ID, OTHER, document  # noqa: F401  (the records the viewer suite shares)

# page sessions (the id each page makes as it loads)
PAGE_A, PAGE_B, PAGE_C = ('aaaaaaaa-0000-4000-8000-00000000000a', 'bbbbbbbb-0000-4000-8000-00000000000b',
                          'cccccccc-0000-4000-8000-00000000000c')


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'projects'
        self.store = ProjectStore(self.root)

    def files(self):
        return sorted(p.name for p in self.root.iterdir() if p.is_file())

    def test_save_numbers_revisions_keeps_the_previous_and_lists(self):
        first = self.store.save(ID, document(), 0)
        self.assertEqual((first['revision'], first['file']), (1, 'Bar remix.json'))
        self.assertEqual(self.store.load(ID)['revision'], 1)
        # One file per project, named after it; nothing else beside it but the hidden state folder.
        self.assertEqual([p.name for p in self.root.iterdir()], ['Bar remix.json'])
        # The page carries a project's created time in what it saves (only a new project goes without one).
        second = self.store.save(ID, dict(document(name='Bar remix 2'), created=first['created']), 1)
        self.assertEqual(second['revision'], 2)
        self.assertEqual(second['created'], first['created'])
        # A new name renames the file; the revision before is kept in .workshop\<id>.
        self.assertEqual(self.files(), ['Bar remix 2.json'])
        previous = json.loads((self.root / '.workshop' / ID / 'project.prev.json').read_text(encoding='utf8'))
        self.assertEqual((previous['revision'], previous['name']), (1, 'Bar remix'))
        self.assertFalse(list(self.root.rglob('*.tmp')))
        self.assertEqual([(p['id'], p['name'], p['revision'], p['map'], p['file']) for p in self.store.list()],
                         [(ID, 'Bar remix 2', 2, 'URB_Bar', 'Bar remix 2.json')])
        self.assertEqual(self.store.path(ID), self.root / 'Bar remix 2.json')
        # Saved as written: LF line endings, UTF-8, readable JSON.
        self.assertNotIn(b'\r\n', (self.root / 'Bar remix 2.json').read_bytes())
        # Groups are optional, and kept as saved.
        group = dict(id='g1', locked=True, breakTogether=True, members=[dict(added='TheWorld.PersistentLevel.A_copy1'),
                                                                          dict(package='URB_Bar', level='base', actor='TheWorld.PersistentLevel.B')])
        self.store.save(ID, document(name='Bar remix 2', groups=[group]), 2)
        self.assertEqual(self.store.load(ID)['groups'], [group])

    def test_file_names_follow_the_name_safely_and_never_clash(self):
        self.assertEqual(file_stem('Bar: remix?/2*'), 'Bar_ remix__2_')
        self.assertEqual(file_stem('  .dots and spaces. '), 'dots and spaces')
        self.assertEqual(file_stem('con'), '_con')
        self.assertEqual(file_stem('NUL.backup'), '_NUL.backup')
        self.assertEqual(file_stem('...'), 'project')
        self.store.save(ID, document(name='Bar: remix'), 0)
        # Another project whose name gives the same file name gets " (2)", and keeps it while the first holds the name.
        saved = self.store.save(OTHER, document(OTHER, name='Bar_ remix'), 0)
        self.assertEqual(saved['file'], 'Bar_ remix (2).json')
        self.assertEqual(self.store.save(OTHER, document(OTHER, name='Bar_ remix'), 1)['file'], 'Bar_ remix (2).json')
        self.assertEqual(self.files(), ['Bar_ remix (2).json', 'Bar_ remix.json'])
        self.assertEqual(self.store.load(ID)['name'], 'Bar: remix')
        self.assertEqual(self.store.load(OTHER)['name'], 'Bar_ remix')
        # Only the case changes: the same file, showing the new case.
        self.assertEqual(self.store.save(ID, document(name='BAR: Remix'), 1)['file'], 'BAR_ Remix.json')
        self.assertEqual(self.files(), ['BAR_ Remix.json', 'Bar_ remix (2).json'])

    def test_a_file_renamed_moved_in_or_copied_beside(self):
        self.store.save(ID, document(), 0)
        self.store.save_recovery(ID, dict(baseRevision=1, overrides=[], added=[]))
        # Renamed outside the editor: still found by its id, with its recovery; the next save names it again.
        (self.root / 'Bar remix.json').rename(self.root / 'shared by me.json')
        self.assertEqual(self.store.load(ID)['revision'], 1)
        self.assertTrue(self.store.list()[0]['recovery'])
        self.assertEqual(self.store.save(ID, document(), 1)['file'], 'Bar remix.json')
        self.assertEqual(self.files(), ['Bar remix.json'])
        # A file someone shared, dropped in under any name, is listed and opens.
        (self.root / 'from a friend.json').write_text(json.dumps(document(OTHER, name='Their remix', revision=4)), encoding='utf8')
        self.assertEqual(self.store.load(OTHER)['name'], 'Their remix')
        # A copy beside a project (one id in two files): the newest revision is the project, the copy is listed greyed.
        (self.root / 'Bar remix - Copy.json').write_bytes((self.root / 'Bar remix.json').read_bytes())
        self.store.save(ID, document(), 2)
        listed = {p['file']: p for p in self.store.list()}
        self.assertEqual(listed['Bar remix.json']['revision'], 3)
        self.assertIn('A copy of the project in “Bar remix.json”', listed['Bar remix - Copy.json']['error'])
        # Files that are not projects are listed as unreadable; other files and folders are left alone.
        (self.root / 'notes.json').write_text('{"hello": 1}', encoding='utf8')
        (self.root / 'readme.txt').write_text('hi', encoding='utf8')
        self.assertIn('not an XCOM Map Workshop project', {p['file']: p for p in self.store.list()}['notes.json']['error'])
        self.assertEqual(len(self.store.list()), 4)

    def test_a_malformed_shared_project_is_listed_with_its_reason_and_the_rest_open(self):
        """Review finding 9: a file of the project schema whose shape the editor can't read (its base map a string,
        its edits not lists, its revision not a number) is a row of its own with the reason; the others list, open
        and capture as before, schema 1 among them."""
        self.store.save(ID, document(), 0)
        old = dict(document(OTHER, name='Old one', revision=3), schemaVersion=1)
        (self.root / 'old.json').write_text(json.dumps(old), encoding='utf8', newline='\n')
        bad = {'source string.json': dict(source='URB_Bar'), 'edits object.json': dict(overrides={'a': 1}),
               'added numbers.json': dict(added=[1, 2]), 'revision text.json': dict(revision='3'),
               'no hash.json': dict(source=dict(map='URB_Bar')), 'name list.json': dict(name=['x'])}
        ids = {}
        for k, (file, change) in enumerate(bad.items()):
            ids[file] = f'00000000-0000-4000-8000-0000000000{k:02d}'
            (self.root / file).write_text(json.dumps(document(ids[file], **change)), encoding='utf8', newline='\n')
        listed = {p['file']: p for p in self.store.list()}
        self.assertEqual((listed['Bar remix.json']['revision'], listed['old.json']['revision']), (1, 3))
        for file in bad:
            self.assertIn('can\'t be read', listed[file]['error'], file)
            with self.assertRaises(ProjectError) as error: self.store.load(ids[file])
            self.assertEqual(error.exception.status, 422)
            with self.assertRaises(ProjectError): self.store.capture(ids[file])
        self.assertIn('base map', listed['source string.json']['error'])
        self.assertIn('"overrides"', listed['edits object.json']['error'])
        self.assertEqual(self.store.load(OTHER)['schemaVersion'], 1)
        self.assertEqual(self.store.capture(ID)[0]['revision'], 1)
        # a copy that can be read is the project before a newer one that can't
        (self.root / 'Bar remix - broken.json').write_text(json.dumps(document(revision=9, overrides='x')), encoding='utf8', newline='\n')
        self.assertEqual(self.store.load(ID)['revision'], 1)
        self.assertIn('copy', {p['file']: p for p in self.store.list()}['Bar remix - broken.json']['error'])

    def test_each_project_file_is_read_once_until_it_changes(self):
        """Review finding 20: a listing reads each project file once; the next reads only what changed; the polled
        lookups (the build status, the queue view, the map names) read nothing new; the project manager's listing
        reads each project once, its summary from the document it gives; a file renamed or changed outside the
        editor is seen at the next listing."""
        ids = [ID, OTHER, '2b3c4d5e-6f7a-4b8c-9d0e-1f2a3b4c5d6e']
        for k, project_id in enumerate(ids):
            self.store.save(project_id, document(project_id, name=f'Project {k}', output=dict(shipAs=f'Ship{k}', patch=f'patch_ship{k}')), 0)
        store = ProjectStore(self.root)
        store.list()
        self.assertEqual(store.reads, 3)
        store.list()
        self.assertEqual(store.reads, 3)
        for project_id in ids:
            self.assertEqual(store.cached(project_id)['output']['shipAs'], f'Ship{ids.index(project_id)}')
            store.path(project_id)
        self.assertEqual(len(store.claimed()), 3)
        self.assertEqual(store.reads, 3)
        rows = store.listing()
        self.assertEqual(store.reads, 6)
        self.assertEqual({s['id']: (s['revision'], d['revision']) for s, d in rows}, {i: (1, 1) for i in ids})
        store.load(ID)
        self.assertEqual(store.reads, 7)
        # renamed outside the editor: found under its new name at the next listing
        (self.root / 'Project 1.json').rename(self.root / 'renamed by hand.json')
        self.assertIn('renamed by hand.json', [p['file'] for p in store.list()])
        self.assertEqual(store.path(OTHER).name, 'renamed by hand.json')
        # changed outside the editor: that one read again, and its summary is the new one
        path = self.root / 'Project 0.json'
        changed = dict(json.loads(path.read_text(encoding='utf8')), revision=5, name='Project 0 by hand')
        path.write_text(json.dumps(changed), encoding='utf8', newline='\n')
        before = store.reads
        listed = {p['id']: p for p in store.list()}
        self.assertEqual((listed[ID]['revision'], listed[ID]['name'], store.reads - before), (5, 'Project 0 by hand', 1))
        self.assertEqual(store.cached(ID)['revision'], 5)

    def test_a_save_that_cant_be_written_says_why(self):
        """Review finding 46: a full disk, a locked file or a read-only folder is a ProjectError with the reason, and
        the revision before stays the project."""
        import errno
        self.store.save(ID, document(), 0)
        full = OSError(errno.ENOSPC, 'No space left on device')
        with mock.patch('projects.os.fsync', side_effect=full):
            with self.assertRaises(ProjectError) as error: self.store.save(ID, document(name='Bar remix'), 1)
        self.assertEqual(error.exception.status, 500)
        self.assertIn('the disk is full', error.exception.message)
        self.assertFalse(list(self.root.glob('*.tmp')))
        locked = PermissionError(errno.EACCES, 'Access is denied')
        with mock.patch('projects.shutil.copyfile', side_effect=locked):
            with self.assertRaises(ProjectError) as error: self.store.save(ID, document(), 1)
        self.assertIn('access was refused', error.exception.message)
        self.assertEqual(self.store.load(ID)['revision'], 1)
        with mock.patch('projects.os.replace', side_effect=locked):
            with self.assertRaises(ProjectError) as error: self.store.save_recovery(ID, dict(owner=PAGE_A, baseRevision=1))
        self.assertIn('could not be written', error.exception.message)
        self.assertEqual(self.store.save(ID, document(), 1)['revision'], 2)

    def test_a_save_based_on_an_older_revision_is_a_conflict(self):
        self.store.save(ID, document(), 0)
        self.store.save(ID, document(), 1)
        with self.assertRaises(ProjectError) as error: self.store.save(ID, document(name='stale'), 1)
        self.assertEqual((error.exception.status, error.exception.extra), (409, dict(revision=2)))
        with self.assertRaises(ProjectError) as error: self.store.save(OTHER, document(OTHER), 3)
        self.assertEqual(error.exception.status, 409)
        self.assertEqual(self.store.load(ID)['name'], 'Bar remix')

    def test_schema_1_is_read_and_a_stale_page_cant_save_it(self):
        # schema 2 adds pieces' flags (piece flags plan): a schema 1 project opens; a page that still saves schema 1
        # (older than the server: it would drop the flags) is refused, so it can't write over a newer document
        self.store.save(ID, document(), 0)
        old = dict(self.store.load(ID), schemaVersion=1)
        path = next(self.root.glob('*.json'))
        path.write_text(json.dumps(old), encoding='utf8', newline='\n')
        self.assertEqual(self.store.load(ID)['schemaVersion'], 1)
        with self.assertRaises(ProjectError) as error: self.store.save(ID, dict(old), old['revision'])
        self.assertEqual(error.exception.status, 409)
        self.assertIn('older than the editor', error.exception.message)
        self.assertTrue(error.exception.extra.get('stale'))
        self.store.save(ID, dict(old, schemaVersion=SCHEMA_VERSION), old['revision'])
        self.assertEqual(self.store.load(ID)['schemaVersion'], 4)
        # schema 3 adds effects' and sounds' records (the effects and sounds plan): a schema 2 project opens, and a
        # page that saves schema 2 is as stale
        with self.assertRaises(ProjectError) as error:
            self.store.save(ID, dict(old, schemaVersion=2), self.store.load(ID)['revision'])
        self.assertTrue(error.exception.extra.get('stale'))
        # schema 4 adds the spawns plan's records (spawnRules, SP8): a schema 3 project opens, and a page that saves
        # schema 3 is as stale
        with self.assertRaises(ProjectError) as error:
            self.store.save(ID, dict(old, schemaVersion=3), self.store.load(ID)['revision'])
        self.assertTrue(error.exception.extra.get('stale'))
        self.store.save(ID, dict(old, schemaVersion=SCHEMA_VERSION, spawnRules=dict(dropIns='placed')), self.store.load(ID)['revision'])
        self.assertEqual(self.store.load(ID)['spawnRules'], dict(dropIns='placed'))
        # a flags-only override and an added piece's flags are carried as the document has them
        flags = dict(overrides=[dict(target=dict(package='URB_Bar', level='base', actor='TheWorld.PersistentLevel.XComLevelActor_1'),
                                     flags=dict(walking=False, cover=False))])
        self.store.save(ID, document(**flags), self.store.load(ID)['revision'])
        self.assertEqual(self.store.load(ID)['overrides'], flags['overrides'])

    def test_other_schema_versions_and_bad_documents_are_refused(self):
        with self.assertRaises(ProjectError) as error: self.store.save(ID, document(schemaVersion=5), 0)
        self.assertEqual(error.exception.status, 409)
        self.assertIn('schema 5', error.exception.message)
        self.root.mkdir(parents=True)
        (self.root / 'Bar remix.json').write_text(json.dumps(document(schemaVersion=0)), encoding='utf8', newline='\n')
        with self.assertRaises(ProjectError) as error: self.store.load(ID)
        self.assertIn('schema 0', error.exception.message)
        self.assertIn('schema 0', self.store.list()[0]['error'])
        with self.assertRaises(ProjectError) as error: self.store.save(ID, document(), 0)
        self.assertEqual(error.exception.status, 409)          # never written over
        (self.root / 'Bar remix.json').unlink()
        with self.assertRaises(ProjectError) as error: self.store.save(OTHER, document(), 0)
        self.assertIn('another project', error.exception.message)
        for bad in (document(name=''), document(mode='blank'), document(source=dict(map='URB_Bar', sha256='x')),
                    document(overrides='none'), document(added=[1]), document(groups='none'), document(groups=[1]),
                    document(cleared='yes'), document(clearKeepsOutside=1), document(landingZones='none'), document(landingZones=[1]), [], None):
            with self.assertRaises(ProjectError) as error: self.store.save(ID, bad, 0)
            self.assertEqual(error.exception.status, 422)
        # a cleared map with its landing zones is saved as it is (the compiler checks the zones)
        zones = [dict(id='a', location=[719, -1681, 64], direction='north', kind='normal')]
        self.store.save(ID, document(cleared=True, clearKeepsOutside=True, landingZones=zones), 0)
        self.assertEqual(self.store.load(ID)['landingZones'], zones)
        self.assertIs(self.store.load(ID)['cleared'], True)
        self.assertIs(self.store.load(ID)['clearKeepsOutside'], True)
        for project_id in ('../escape', 'ABC', '', ID.upper()):
            with self.assertRaises(ProjectError) as error: self.store.load(project_id)
            self.assertEqual(error.exception.status, 404)

    def test_a_capture_is_the_saved_file_whole_and_later_saves_change_nothing_of_it(self):
        """Build queue plan, 9.1: what a queued build reads is captured under the store's lock, bytes and digest; a
        save or a rename after it leaves the captured bytes as they were."""
        import hashlib
        self.store.save(ID, document(), 0)
        doc, data, digest, path = self.store.capture(ID)
        self.assertEqual((doc['revision'], digest, path.name), (1, hashlib.sha256(data).hexdigest(), 'Bar remix.json'))
        self.assertEqual(json.loads(data), doc)
        self.store.save(ID, document(name='Renamed'), 1)        # renames the file
        self.assertEqual(json.loads(data)['revision'], 1)
        self.assertFalse(path.exists())
        self.assertEqual(self.store.capture(ID)[0]['revision'], 2)
        with self.assertRaises(ProjectError) as error: self.store.capture(OTHER)
        self.assertEqual(error.exception.status, 404)
        (self.root / 'Renamed.json').write_text('{', encoding='utf8')            # torn by hand
        with self.assertRaises(ProjectError): self.store.capture(ID)

    def test_recovery_is_kept_until_the_next_save(self):
        with self.assertRaises(ProjectError): self.store.save_recovery(ID, dict(baseRevision=0))
        self.store.save(ID, document(), 0)
        self.assertEqual(self.store.save_recovery(ID, dict(owner=PAGE_A, baseRevision=1, overrides=[], added=[])),
                         dict(ok=True, revision=1, stale=False))
        self.assertEqual(self.store.recovery(ID)['baseRevision'], 1)
        self.assertTrue(self.store.list()[0]['recovery'])
        self.store.save(ID, document(), 1, owner=PAGE_A)
        self.assertIsNone(self.store.recovery(ID))
        self.store.save_recovery(ID, dict(owner=PAGE_A, baseRevision=2))
        self.store.drop_recovery(ID, PAGE_A)
        self.assertIsNone(self.store.recovery(ID))

    def test_each_page_session_keeps_its_own_draft(self):
        """Review finding 3: two pages editing one project keep a draft each; a save, a discard or a clean page's
        leaving deletes its own draft only, and a draft the user was shown goes only while it is still that one."""
        self.store.save(ID, document(), 0)
        self.store.save_recovery(ID, dict(owner=PAGE_A, baseRevision=1, note='a'))
        self.store.save_recovery(ID, dict(owner=PAGE_B, baseRevision=1, note='b'))
        newest = self.store.recovery(ID)
        self.assertEqual((newest['others'], newest['owner'] in (PAGE_A, PAGE_B)), (1, True))
        # a third page, clean, leaves: nothing of the two goes
        self.assertEqual(self.store.drop_recovery(ID, PAGE_C), dict(dropped=False))
        self.assertEqual(len(self.store._drafts(ID)), 2)
        # A saves: its draft goes, B's stays (and is stale now: based on revision 1, the project at 2)
        self.store.save(ID, document(), 1, owner=PAGE_A)
        kept = self.store.recovery(ID)
        self.assertEqual((kept['owner'], kept['note'], kept['others']), (PAGE_B, 'b', 0))
        self.assertEqual(self.store.save_recovery(ID, dict(owner=PAGE_B, baseRevision=1, note='b2')),
                         dict(ok=True, revision=2, stale=True))
        # a draft based on a revision the project never had is refused
        with self.assertRaises(ProjectError) as error: self.store.save_recovery(ID, dict(owner=PAGE_B, baseRevision=7))
        self.assertEqual((error.exception.status, error.exception.extra), (409, dict(revision=2)))
        # the user discards B's draft from another page, as it was shown: refused once B kept it again since
        shown = self.store.recovery(ID)
        self.store.save_recovery(ID, dict(owner=PAGE_B, baseRevision=1, note='b3'))
        with mock.patch('projects.now', lambda: 'later'):
            self.store.save_recovery(ID, dict(owner=PAGE_B, baseRevision=1, note='b4'))
        self.assertEqual(self.store.drop_recovery(ID, PAGE_B, shown['savedAt']), dict(dropped=False))
        self.assertEqual(self.store.drop_recovery(ID, PAGE_B, 'later'), dict(dropped=True))
        self.assertIsNone(self.store.recovery(ID))
        # an older editor's owner-less draft is listed, and goes by its own name only
        self.store.save_recovery(ID, dict(baseRevision=2, note='old'))
        self.assertEqual(self.store.recovery(ID)['owner'], None)
        self.assertEqual(self.store.drop_recovery(ID, PAGE_A), dict(dropped=False))
        self.assertEqual(self.store.drop_recovery(ID, None), dict(dropped=True))
        # owners are page session ids: nothing else names a file
        for bad in ('../x', 'ABC', 3):
            with self.assertRaises(ProjectError): self.store.save_recovery(ID, dict(owner=bad, baseRevision=2))
            with self.assertRaises(ProjectError): self.store.drop_recovery(ID, bad)
        with self.assertRaises(ProjectError): self.store.save(ID, document(), 2, owner='../x')
        self.assertEqual(self.store.load(ID)['revision'], 2)


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        scene = root / 'cache' / 'URB_Bar' / 'current'; scene.mkdir(parents=True)
        (scene / 'scene.json').write_text(json.dumps(dict(schemaVersion=1, exporterVersion=12, name='URB_Bar', scope='map')), encoding='utf8', newline='\n')
        self.store = ProjectStore(root / 'projects')
        self.server = LocalServer(('127.0.0.1', 0), partial(Handler, catalogue=load_catalogue(root / 'cache'), projects=self.store))
        thread = threading.Thread(target=self.server.serve_forever, daemon=True); thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'
        self.addCleanup(lambda: (self.server.shutdown(), self.server.server_close(), thread.join(timeout=5)))

    def call(self, method, path, body=None, headers=None):
        data = None if body is None else json.dumps(body).encode()
        request = Request(self.base + path, data=data, method=method,
                          headers={'Content-Type': 'application/json', **(headers or {})})
        try:
            with urlopen(request) as response: return response.status, json.load(response)
        except HTTPError as error: return error.code, json.load(error)

    def test_save_open_list_and_recovery_over_http(self):
        self.assertEqual(self.call('GET', '/projects.json'), (200, dict(folder=str(self.store.root), projects=[])))
        status, saved = self.call('PUT', f'/projects/{ID}/project.json', dict(expectedRevision=0, document=document()))
        self.assertEqual((status, saved['revision']), (200, 1))
        status, opened = self.call('GET', f'/projects/{ID}/project.json')
        self.assertEqual((status, opened['name'], opened['revision']), (200, 'Bar remix', 1))
        status, conflict = self.call('PUT', f'/projects/{ID}/project.json', dict(expectedRevision=0, document=document()))
        self.assertEqual((status, conflict['revision']), (409, 1))
        self.assertEqual(self.call('GET', f'/projects/{ID}/recovery.json'), (200, None))
        self.assertEqual(self.call('PUT', f'/projects/{ID}/recovery.json', dict(owner=PAGE_A, baseRevision=1)),
                         (200, dict(ok=True, revision=1, stale=False)))
        self.assertEqual(self.call('GET', f'/projects/{ID}/recovery.json')[1]['baseRevision'], 1)
        # a DELETE names whose draft (and, for one shown, its time): another page's goes with nothing of it
        self.assertEqual(self.call('DELETE', f'/projects/{ID}/recovery.json')[0], 400)
        self.assertEqual(self.call('DELETE', f'/projects/{ID}/recovery.json?owner={PAGE_B}'), (200, dict(dropped=False)))
        self.assertEqual(self.call('DELETE', f'/projects/{ID}/recovery.json?owner={PAGE_A}&savedAt=2000-01-01T00:00:00Z'),
                         (200, dict(dropped=False)))
        self.assertEqual(self.call('DELETE', f'/projects/{ID}/recovery.json?owner={PAGE_A}'), (200, dict(dropped=True)))
        self.assertEqual(self.call('GET', f'/projects/{ID}/recovery.json'), (200, None))
        # a save names the page saving: its draft goes, another page's stays
        self.call('PUT', f'/projects/{ID}/recovery.json', dict(owner=PAGE_A, baseRevision=1))
        self.call('PUT', f'/projects/{ID}/recovery.json', dict(owner=PAGE_B, baseRevision=1))
        self.assertEqual(self.call('PUT', f'/projects/{ID}/project.json', dict(expectedRevision=1, document=document(), owner=PAGE_A))[0], 200)
        self.assertEqual(self.call('GET', f'/projects/{ID}/recovery.json')[1]['owner'], PAGE_B)
        self.assertEqual(self.call('DELETE', f'/projects/{ID}/recovery.json?owner={PAGE_B}'), (200, dict(dropped=True)))
        self.assertEqual(self.call('GET', f'/projects/{OTHER}/recovery.json')[0], 404)
        self.assertEqual(self.call('GET', '/projects.json')[1]['projects'][0]['id'], ID)

    def test_changes_from_other_pages_or_hosts_and_non_json_are_refused(self):
        body = dict(expectedRevision=0, document=document())
        self.assertEqual(self.call('PUT', f'/projects/{ID}/project.json', body, {'Origin': 'http://evil.example'})[0], 403)
        self.assertEqual(self.call('PUT', f'/projects/{ID}/project.json', body, {'Host': 'evil.example'})[0], 403)
        self.assertEqual(self.call('PUT', f'/projects/{ID}/project.json', body, {'Content-Type': 'text/plain'})[0], 415)
        self.assertEqual(self.call('PUT', '/projects/../project.json', body)[0], 404)
        self.assertEqual(self.call('GET', '/projects/not-an-id/project.json')[0], 404)
        self.assertFalse(self.store.root.exists())
        same = {'Origin': f'http://127.0.0.1:{self.server.server_port}'}
        self.assertEqual(self.call('PUT', f'/projects/{ID}/project.json', body, same)[0], 200)


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'settings.json'
        patcher = mock.patch.dict(os.environ, {'XCOM_MAP_WORKSHOP_SETTINGS': str(self.path)})
        patcher.start(); self.addCleanup(patcher.stop)

    def test_defaults_set_and_clear(self):
        loaded = settings_module.load_settings()
        self.assertEqual(loaded['projects'].parts[-2:], (settings_module.APP, 'projects'))
        self.assertIsNone(loaded['lwr'])
        updated = settings_module.save_settings({'lwr': self.root, 'projects': self.root / 'p'})
        self.assertEqual((updated['lwr'], updated['projects']), (self.root.resolve(), (self.root / 'p').resolve()))
        self.assertEqual(settings_module.save_settings({'lwr': None})['lwr'], None)
        with self.assertRaises(ValueError): settings_module.save_settings({'nope': self.root})
        self.path.write_text('{"lwr": 3}', encoding='utf8', newline='\n')
        with self.assertRaises(ValueError): settings_module.load_settings()

    def test_a_release_keeps_projects_and_builds_in_its_own_folder(self):
        home, app = self.root / 'Documents' / settings_module.APP, self.root / 'Programs' / 'XCOM Map Workshop'
        app.mkdir(parents=True)
        d = settings_module.default_folders(root=app, home=home)
        self.assertEqual((d['projects'], d['output'], d['cache']), (app / 'projects', app / 'builds', home / 'cache'))
        # run from the repository (no release folder): all under Documents, as before
        self.assertIsNone(settings_module.editor_folder())
        d = settings_module.default_folders(home=home)
        self.assertEqual((d['projects'], d['output']), (home / 'projects', home / 'builds'))
        # an earlier release's projects in Documents stay in sight there; builds, with none there, go to the editor's
        (home / 'projects').mkdir(parents=True)
        (home / 'projects' / 'Bar remix.json').write_text('{}', encoding='utf8')
        d = settings_module.default_folders(root=app, home=home)
        self.assertEqual((d['projects'], d['output']), (home / 'projects', app / 'builds'))
        # an editor folder that can't be written (installed for all users): Documents
        with mock.patch.object(settings_module, '_writable', lambda folder: False):
            self.assertEqual(settings_module.default_folders(root=app, home=home)['output'], home / 'builds')
        # a setting wins over either
        with mock.patch.object(settings_module, 'editor_folder', lambda: app):
            self.path.write_text(json.dumps({'output': str(self.root / 'mine')}), encoding='utf8', newline='\n')
            loaded = settings_module.load_settings()
            self.assertEqual(loaded['output'], self.root / 'mine')

    def test_the_game_setting_reads_and_replaces_the_older_lwr(self):
        self.path.write_text(json.dumps({'lwr': str(self.root)}), encoding='utf8', newline='\n')
        loaded = settings_module.load_settings()
        self.assertEqual((loaded['game'], loaded['lwr']), (self.root, self.root))
        settings_module.save_settings({'game': self.root / 'g'})
        stored = json.loads(self.path.read_text(encoding='utf8'))
        self.assertEqual((stored.get('game'), 'lwr' in stored), (str((self.root / 'g').resolve()), False))
        self.assertEqual(settings_module.save_settings({'lwr': self.root})['game'], self.root.resolve())

    def test_the_kind_of_game_install(self):
        def game(name, *config):
            folder = self.root / name; (folder / 'XEW' / 'XComGame' / 'CookedPCConsole').mkdir(parents=True)
            (folder / 'XEW' / 'XComGame' / 'Config').mkdir()
            for f in config: (folder / 'XEW' / 'XComGame' / 'Config' / f).write_text('', encoding='utf8')
            return folder
        self.assertEqual(settings_module.game_kind(game('lwr', 'DefaultLZMutator.ini', 'DefaultLWRebalance.ini')), 'lwr')
        self.assertEqual(settings_module.game_kind(game('lw', 'DefaultLZMutator.ini')), 'longwar')
        plain = game('ew', 'DefaultMaps.ini')
        self.assertEqual(settings_module.game_kind(plain), 'ew')
        self.assertIsNone(settings_module.game_kind(self.root / 'nothing'))
        self.assertIn('Enemy Within', settings_module.resolve_game(plain)[1])
        checks = {c['name']: c for c in settings_module.doctor(dict(projects=self.root / 'p', output=self.root / 'o',
                                                                   cache=self.root / 'c', game=plain, install=None, udk=None, lab=None))}
        self.assertEqual(checks['game']['status'], 'ok')
        checks = {c['name']: c for c in settings_module.doctor(dict(projects=self.root / 'p', output=self.root / 'o',
                                                                   cache=self.root / 'c', game=self.root / 'lw', install=None, udk=None, lab=None))}
        self.assertEqual(checks['game']['status'], 'ok')        # (no "not tried" warning since 16 November 2026)

    def test_doctor_reports_missing_wrong_and_matching_maps(self):
        game = self.root / 'game'; cooked = game / 'XEW' / 'XComGame' / 'CookedPCConsole'; cooked.mkdir(parents=True)
        (cooked / 'URB_Bar.upk').write_bytes(b'bar')
        import hashlib
        bar = dict(name='URB_Bar', sha256=hashlib.sha256(b'bar').hexdigest())
        temple = dict(name='TempleShip', sha256='0' * 64)
        udk = self.root / 'udk'; (udk / 'Binaries' / 'Win32').mkdir(parents=True); (udk / 'Binaries' / 'Win32' / 'UDK.com').write_bytes(b'')
        conf = dict(projects=self.root / 'p', output=self.root / 'o', cache=self.root / 'c', lwr=game, install=self.root,
                    udk=udk, lab=self.root / 'no-lab')
        checks = {c['name']: c for c in settings_module.doctor(conf, [bar, temple])}
        self.assertEqual(checks['cache']['status'], 'ok')
        self.assertEqual(checks['install']['status'], 'wrong')            # not a game folder
        conf['install'] = game
        self.assertEqual({c['name']: c for c in settings_module.doctor(conf)}['install']['status'], 'ok')
        self.assertEqual(checks['game']['status'], 'ok')
        self.assertEqual(checks['map URB_Bar']['status'], 'ok')
        self.assertEqual(checks['map TempleShip']['status'], 'missing')
        self.assertEqual(checks['udk']['status'], 'warn')                # optional: only a patch needs it
        self.assertIn('XComGame stubs', checks['udk']['detail'])
        conf['udk'] = None
        self.assertEqual({c['name']: c for c in settings_module.doctor(conf)}['udk']['status'], 'ok')
        self.assertEqual(checks['lab']['status'], 'wrong')
        (game / 'XComLab-copy.txt').write_text('', encoding='utf8')
        self.assertEqual({c['name']: c for c in settings_module.doctor(conf)}['game']['status'], 'wrong')
        conf['lwr'] = None
        self.assertEqual({c['name']: c for c in settings_module.doctor(conf)}['game']['status'], 'missing')

    def test_lwr_is_the_game_folder_or_found_beside_the_lab_copy(self):
        def game(name, lab=False):
            folder = self.root / 'common' / name; (folder / 'XEW' / 'XComGame' / 'CookedPCConsole').mkdir(parents=True)
            if lab: (folder / 'XComLab-copy.txt').write_text('', encoding='utf8')
            return folder
        resolve = settings_module.resolve_lwr
        common = self.root / 'common'
        lab = game('XCom-Enemy-Unknown', lab=True)
        self.assertEqual(resolve(common)[0], None)
        self.assertIn('only the lab copy', resolve(common)[1])
        parked = game('XCom-Enemy-Unknown.LWR')
        self.assertEqual(resolve(common)[0], parked)
        # switch_install lwr: LWR becomes the active folder, the lab copy is parked as .Lab.
        lab.rename(common / 'XCom-Enemy-Unknown.Lab'); parked.rename(common / 'XCom-Enemy-Unknown')
        self.assertEqual(resolve(common)[0], common / 'XCom-Enemy-Unknown')
        # Set directly: the install itself anywhere, never the lab copy.
        self.assertEqual(resolve(common / 'XCom-Enemy-Unknown')[0], common / 'XCom-Enemy-Unknown')
        self.assertEqual(resolve(common / 'XCom-Enemy-Unknown.Lab')[0], None)
        elsewhere = game('../My LWR')
        self.assertEqual(resolve(elsewhere)[0], elsewhere)
        # Two installs under names that are not Steam's: ambiguous, so it must be set directly.
        other = self.root / 'games'; (other / 'A' / 'XEW' / 'XComGame' / 'CookedPCConsole').mkdir(parents=True)
        (other / 'B' / 'XEW' / 'XComGame' / 'CookedPCConsole').mkdir(parents=True)
        self.assertEqual(resolve(other)[0], None)
        self.assertIn('several', resolve(other)[1])
        self.assertEqual(resolve(self.root / 'nowhere')[0], None)
        checks = {c['name']: c for c in settings_module.doctor(dict(projects=self.root / 'p', output=self.root / 'o', cache=self.root / 'c', lwr=common,
                                                                  install=None, udk=None, lab=None))}
        self.assertEqual(checks['game']['status'], 'ok')
        self.assertIn('XCom-Enemy-Unknown', checks['game']['detail'])


if __name__ == '__main__': unittest.main()

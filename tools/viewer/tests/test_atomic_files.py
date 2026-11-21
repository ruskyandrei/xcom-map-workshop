"""One writer for a file replaced whole (atomic_files.py; KB-10): a replace that Windows refuses for a moment (another
program holding the file: a virus scanner, an indexer) is tried again, a write that fails leaves no temporary file,
each writer of the server's files completes through such refusals, and no module of tools/viewer replaces or renames
a file itself but those listed with their reasons."""
import ast
import collections
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
VIEWER = HERE.parent
sys.path.insert(0, str(VIEWER))
import atomic_files  # noqa: E402
import buildqueue  # noqa: E402
import builds  # noqa: E402
from catalogue import PackageDigests  # noqa: E402
import installs  # noqa: E402  (it puts tools/bake on the path)
import library  # noqa: E402
import mapsini  # noqa: E402
import packs  # noqa: E402
import pictures  # noqa: E402
import playsaves  # noqa: E402
import prefab_tests  # noqa: E402
from prefabs import PrefabStore  # noqa: E402
from projects import ProjectStore  # noqa: E402
import publication  # noqa: E402
import settings  # noqa: E402
import squads  # noqa: E402
from viewer_fixtures import ID, document, png, prefab  # noqa: E402

# what Windows says when another program holds the file
HELD = (13, 'The process cannot access the file because it is being used by another process')


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Refusing:
    """os.replace as Windows answers while another program holds a file for a moment: each target refused `times`
    times with a PermissionError, then replaced. A path's replace calls os.replace, so it is refused too."""

    def __init__(self, times=2):
        self.real, self.times, self.refused = os.replace, times, collections.Counter()

    @staticmethod
    def key(path):
        return os.path.normcase(os.path.abspath(path))

    def __call__(self, src, dst, *args, **kwargs):
        if self.refused[self.key(dst)] < self.times:
            self.refused[self.key(dst)] += 1
            raise PermissionError(*HELD, str(dst))
        return self.real(src, dst, *args, **kwargs)

    def count(self, path):
        return self.refused[self.key(path)]

    def __enter__(self):
        self.patch = mock.patch('os.replace', self)
        self.patch.start()
        return self

    def __exit__(self, *exc):
        self.patch.stop()
        return False


class Replace(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path, self.new = self.root / 'kept.json', self.root / 'kept.json.tmp'
        self.path.write_bytes(b'old')
        self.new.write_bytes(b'new')

    def files(self):
        return sorted(p.name for p in self.root.iterdir())

    def test_a_refused_replace_is_tried_again(self):
        with Refusing(2) as refusing:
            atomic_files.replace(self.new, self.path)
        self.assertEqual((self.path.read_bytes(), self.files(), refusing.count(self.path)), (b'new', ['kept.json'], 2))

    def test_the_last_refusal_is_raised_and_the_file_moved_stays(self):
        with mock.patch.object(atomic_files, 'PAUSE', 0), Refusing(atomic_files.TRIES) as refusing:
            with self.assertRaises(PermissionError):
                atomic_files.replace(self.new, self.path)
        self.assertEqual(refusing.count(self.path), atomic_files.TRIES)
        # (it may be a file moved aside, not a temporary one: replace never deletes it)
        self.assertEqual((self.path.read_bytes(), self.new.read_bytes()), (b'old', b'new'))

    def test_another_error_is_raised_at_once(self):
        with mock.patch('os.replace', side_effect=FileNotFoundError(2, 'gone')) as called:
            with self.assertRaises(FileNotFoundError):
                atomic_files.replace(self.root / 'missing', self.path)
        self.assertEqual(called.call_count, 1)

    def test_bytes_and_text_written_whole_through_refusals(self):
        self.new.unlink()
        text = self.root / 'notes.txt'
        with Refusing(2) as refusing:
            atomic_files.write_bytes(self.path, b'\x00bytes', sync=True)
            atomic_files.write_text(text, 'a line\nanother é\n')
        self.assertEqual((self.path.read_bytes(), text.read_bytes()), (b'\x00bytes', 'a line\nanother é\n'.encode()))
        self.assertEqual((refusing.count(self.path), refusing.count(text), self.files()), (2, 2, ['kept.json', 'notes.txt']))

    def test_a_write_that_fails_leaves_no_temporary_file(self):
        self.new.unlink()
        own = self.root / 'kept.json.mine.part'
        with mock.patch.object(atomic_files, 'PAUSE', 0), Refusing(atomic_files.TRIES * 2):
            with self.assertRaises(PermissionError):
                atomic_files.write_bytes(self.path, b'new')
            with self.assertRaises(PermissionError):
                atomic_files.write_text(self.path, 'new', temp=own)
        with self.assertRaises(TypeError):
            atomic_files.write_bytes(self.path, 'not bytes')
        with self.assertRaises(FileNotFoundError):      # its folder is not there: nothing is made
            atomic_files.write_bytes(self.root / 'gone' / 'kept.json', b'new')
        self.assertEqual((self.path.read_bytes(), self.files()), (b'old', ['kept.json']))


class Writers(unittest.TestCase):
    """Each writer of a file the server replaces whole completes when Windows refuses each of its replaces twice
    (KB-10: before atomic_files only the install's ledger and config files did), and leaves no temporary file. A
    writer returns the files it replaced; each must have been refused twice and tried again. The writers of the
    piece, effect and drawn effect records, the build's writer record, the reports' and packs' zips and the queue's
    reset write as these do and are held by Scan below."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_every_writer_completes_through_refusals(self):
        for name in sorted(n for n in dir(self) if n.startswith('write_')):
            with self.subTest(name[len('write_'):]):
                root = self.root / name
                root.mkdir()
                with Refusing(2) as refusing:
                    targets = getattr(self, name)(root)
                self.assertTrue(targets)
                for path in targets:
                    self.assertEqual(refusing.count(path), 2, f'{path} was not replaced through a refusal')
                self.assertEqual([p for p in root.rglob('*') if p.is_file() and p.suffix in ('.tmp', '.part')], [])

    # ------------------------------------------------------------------ the projects and their pictures
    def write_project(self, root):
        store = ProjectStore(root / 'projects')
        store.save(ID, document(), 0)
        store.save(ID, document(), 1)       # the revision before kept beside it
        self.assertEqual(store.load(ID)['revision'], 2)
        return [store.path(ID), store.state(ID) / store.prev]

    def write_picture(self, root):
        store = ProjectStore(root / 'projects')
        first = pictures.save_picture(store, ID, png())['sha256']
        pictures.save_picture(store, ID, png(colour=(90, 20, 20)))      # the first becomes the one before
        folder = store.root / '.workshop' / ID
        self.assertEqual(sha((folder / pictures.PREVIOUS).read_bytes()), first)
        return [folder / pictures.NAME, folder / pictures.PREVIOUS]

    def write_build_snapshot(self, root):
        store = ProjectStore(root / 'projects')
        digest = pictures.save_picture(store, ID, png())['sha256']
        store.save(ID, document(picture=dict(sha256=digest)), 0)
        _, _, _, snapshot, picture = builds.capture(store, ID, root / 'work')
        self.assertEqual(picture, digest)
        return [snapshot, pictures.beside(snapshot)]

    def write_prefab(self, root):
        store = PrefabStore(root / 'prefabs')
        store.save(ID, prefab(), 0)
        path = store.path(ID)
        store.save_picture(ID, png())
        picture = store.picture_path(ID)
        kept = Path(store.delete(ID)['kept'])           # moved aside into .workshop\deleted
        self.assertEqual(json.loads(kept.read_text(encoding='utf8'))['name'], 'Corner shop')
        return [path, picture, kept]

    # ------------------------------------------------------------------ the builds
    def write_publication(self, root):
        output, variant = root / 'builds', 'URB_Bar_Remix_0f8b'
        staging = output / '.work' / f'{variant}-new' / 'package'
        (staging / 'CookedPCConsole').mkdir(parents=True)
        (staging / 'CookedPCConsole' / f'{variant}.upk').write_bytes(b'new map')
        (staging / 'manifest.json').write_text(json.dumps(dict(
            schema=installs.PACKAGE_SCHEMA, schemaVersion=1, buildId='new', project=dict(id='p1', revision=1),
            variant=variant, attempt='a1', files={f'CookedPCConsole/{variant}.upk': sha(b'new map')})), encoding='utf-8')
        with publication.guard(output, variant):
            self.assertEqual(publication.publish(output, variant, staging, None, dict(buildId='new', attempt='a1', project='p1')), [])
        self.assertTrue((output / variant / 'manifest.json').is_file())
        return [publication.journal_path(output, variant)]

    def write_build_queue(self, root):
        class Runner:
            output, queue, listeners = root / 'builds', None, []
        queue = buildqueue.BuildQueue(None, Runner(), dict)
        queue.q = buildqueue.empty()
        queue._save()
        queue._save()       # the first becomes the last good copy
        self.assertEqual(json.loads(queue.backup.read_text(encoding='utf-8'))['schema'], buildqueue.SCHEMA)
        return [queue.file, queue.backup]

    # ------------------------------------------------------------------ the cache and the library
    def write_catalogue_digests(self, root):
        package = root / 'URB_Bar.upk'
        package.write_bytes(b'a map')
        digests = PackageDigests(root)
        digests.digest(package)
        digests.save()          # (a write that fails is let go: the file then is not there)
        self.assertEqual([v[2] for v in json.loads(digests.path.read_text(encoding='utf-8')).values()], [sha(b'a map')])
        return [digests.path]

    def write_library_index(self, root):
        cache = root / 'cache'
        with mock.patch.object(library, 'donors', return_value=[('URB_Bar', 'map', root / 'URB_Bar.upk')]), \
                mock.patch.object(library, 'scan_donor', return_value=dict(package='URB_Bar')), \
                mock.patch.object(library, 'build_index', return_value=dict(version=1)):
            library.scan(root / 'game', cache, jobs=1)
        self.assertEqual(json.loads(library.index_path(cache).read_text(encoding='utf-8')), dict(version=1))
        return [library.index_path(cache)]

    def write_library_area_lights(self, root):
        import area_light_bindings
        scene = dict(lightMetadata=dict(areaMatcher=area_light_bindings.MATCHER_VERSION), lights=[])
        with mock.patch('compiler.find_export', return_value=(None, scene)):
            self.assertEqual(library.donor_area_lights(root, root, root / 'URB_Bar.upk', 'a' * 64), {})
        return [root / f'area-lights-v{area_light_bindings.MATCHER_VERSION}.json']

    def write_library_favourites(self, root):
        path = root / 'library.json'
        self.assertEqual(library.save_state(dict(favourites=[], recent=[]), 0, path)['revision'], 1)
        return [path]

    def write_library_thumbnail(self, root):
        runner = library.LibraryRunner(root / 'cache', None)
        runner.save_thumb('0123456789abcdef', png((64, 64)))
        return [runner.thumb('0123456789abcdef')]

    # ------------------------------------------------------------------ the settings, the squad, the packs
    def write_settings(self, root):
        path = root / 'settings.json'
        settings.save_settings({'projects': root / 'mine'}, path)
        self.assertEqual(Path(json.loads(path.read_text(encoding='utf8'))['projects']), (root / 'mine').resolve())
        return [path]

    def write_squad(self, root):
        unit = dict(id='unit-1', kind='soldier', first='Tom', last='Alpha', **{'class': 'eSC_Assault'}, rank=1,
                    look='man-a', country='eCountry_Canada', armour='eItem_ArmorKevlar', sidearm='eItem_Pistol',
                    weapons=['eItem_Shotgun'], items=['eItem_FragGrenade'], perks=[], stats={})
        store = squads.SquadStore(root / squads.FILE)
        revision = store.save(dict(schema=squads.SCHEMA, version=1, name='First', units=[unit]), 'none')
        store.save(dict(schema=squads.SCHEMA, version=1, name='Second', units=[unit]), revision)     # the first kept
        return [store.path, root / squads.PREVIOUS]

    def write_pack(self, root):
        record = dict(schema=packs.SCHEMA, schemaVersion=1, name='Other', folder='Other', card=7, version=3, maps=[])
        packs.save(root, record)
        self.assertEqual(packs.load(root, 'Other'), record)
        return [packs.root(root) / 'Other.json']

    # ------------------------------------------------------------------ the game install and its saves
    def write_play_saves(self, root):
        folder, kept = root / 'SaveData', root / 'copy'
        folder.mkdir()
        kept.write_bytes(b'a campaign save')
        self.assertIsNone(playsaves._put_back(dict(copy=str(kept), sha256=sha(b'a campaign save')), folder / 'save3'))
        (folder / 'save1').write_bytes(b'a play save')
        self.assertEqual(playsaves._move_to_next_slot(folder, folder / 'save1', {1, 3}, []), folder / 'save4')
        return [folder / 'save3', folder / 'save4']

    def write_prefab_test(self, root):
        folder = root / '.prefab-tests' / '0f8b2c4e1d2a'
        folder.mkdir(parents=True)
        prefab_tests.write(folder / 'test.json', dict(id=ID, state='preparing'))
        prefab_tests.write(folder / 'test.json', dict(id=ID, state='building'))
        self.assertEqual((folder / 'test.json').read_bytes(),
                         ('{\n "id": "%s",\n "state": "building"\n}\n' % ID).encode())
        return [folder / 'test.json']

    def write_install_ledger(self, root):
        installs.write_ledger(root, dict(history=[dict(at='now')]))
        return [installs.ledger_path(root)]

    def write_install_files(self, root):
        cooked = installs.cooked(root)
        cooked.mkdir(parents=True)
        (cooked / 'URB_Bar_Remix.upk').write_bytes(b'the last build')
        (root / 'new.upk').write_bytes(b'this build')
        with installs._Change(root, 'a check') as change:       # what it replaces moved aside, then the copy put in
            change.copy_in(root / 'new.upk', cooked / 'URB_Bar_Remix.upk', sha(b'this build'))
            aside = installs._aside(cooked / 'URB_Bar_Remix.upk')
        self.assertEqual((cooked / 'URB_Bar_Remix.upk').read_bytes(), b'this build')
        return [installs.change_path(root), aside, cooked / 'URB_Bar_Remix.upk']

    def write_install_config(self, root):
        maps, lz, spawns = root / 'DefaultMaps.ini', root / 'DefaultLZ.ini', root / 'XComLZMutator.ini'
        mapsini.write_checked(maps, [b'[Maps]', b'MapName="URB_Bar"'])
        installs.replace_bytes(lz, b'a prefab test\'s config', '0f8b2c4e-1d2a-4b6c-8e9f-123456789abc')
        installs.replace_bytes(spawns, b'its bytes from before the change')      # (a change's roll-back)
        self.assertEqual([p.read_bytes() for p in (maps, lz, spawns)],
                         [b'[Maps]\r\nMapName="URB_Bar"', b'a prefab test\'s config', b'its bytes from before the change'])
        return [maps, lz, spawns]


# a call that replaces or renames a file (os.replace, os.rename, a path's one-argument replace or rename) allowed in a
# module of tools/viewer, and why; every other module goes through atomic_files
ALLOWED = {
    'atomic_files.py': 'the one writer',
    'export.py': 'the export\'s staging folder published under its name: a folder moved, which Path.rename refuses '
                 'onto one that is there (a new generation is named then)',
    'publication.py': 'a package\'s folders swapped (the old one aside, the new one in, back on a failure): folders '
                      'moved, and the journal\'s states rest on Path.rename refusing a folder that is there',
}


def moves(path):
    """The lines of `path` that replace or rename a file: os.replace(a, b) or os.rename(a, b), or a.replace(b) or
    a.rename(b) with one argument (a path's; a string's replace takes two)."""
    found = []
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in ('replace', 'rename')):
            continue
        by_os = isinstance(node.func.value, ast.Name) and node.func.value.id == 'os'
        if by_os or (len(node.args) == 1 and not node.keywords):
            found.append(node.lineno)
    return found


class Scan(unittest.TestCase):
    def test_no_module_replaces_a_file_itself(self):
        found = {p.name: moves(p) for p in sorted(VIEWER.glob('*.py'))}
        left = {name: lines for name, lines in found.items() if lines and name not in ALLOWED}
        self.assertEqual(left, {}, 'these replace or rename a file without atomic_files (KB-10): use '
                                   'atomic_files.replace, write_bytes or write_text, or list the module with its reason')
        self.assertEqual([name for name in ALLOWED if not found.get(name)], [], 'listed, and no longer moving a file')

    def test_the_scan_sees_each_form(self):
        sample = self.sample_file('import os\nos.replace(a, b)\nos.rename(a, b)\np.replace(q)\np.rename(q)\n'
                              's.replace("a", "b")\nd.replace(microsecond=0)\n')
        self.assertEqual(moves(sample), [2, 3, 4, 5])

    def sample_file(self, text):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        path = Path(temp.name) / 'sample.py'
        path.write_text(text, encoding='utf-8', newline='\n')
        return path


if __name__ == '__main__':
    unittest.main()

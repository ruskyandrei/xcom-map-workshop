"""A map pack's zip (manager.pack) on the temporary game installs of test_play.py:
- review finding 13: a project left out (a file of another build's name with other bytes, the conflict last in its
  manifest) leaves nothing in the pack: no file, card line, picture or README line;
- review finding 14: no text in the zip names a folder of this computer, with the editor projects in it or not;
- review finding 44: a card line the card can't hold leaves its project out, with why;
- review finding 46: a zip that fails part-way answers why and leaves no .zip.tmp; Game maps refuses records that
  are no ids."""
import hashlib
import json
from pathlib import Path
import re
import sys
import unittest
from unittest import mock
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'bake' / 'tests'))
import installs  # noqa: E402  (it puts tools/bake on the path)
import deploy_fixture as dep  # noqa: E402
import gamemaps  # noqa: E402
import manager  # noqa: E402
sys.path.insert(0, str(HERE.parents[1] / 'upk'))
import pack_card  # noqa: E402
from projects import ProjectError  # noqa: E402
import test_manager  # noqa: E402  (its Manager is used by name, so that its tests don't run here again)
from test_manager import OTHER, OTHER_ID  # noqa: E402
import test_play  # noqa: E402
from test_projects import ID  # noqa: E402

VARIANT = test_play.VARIANT
TEXT = ('.txt', '.json', '.cmd', '.ps1')


class PackExport(unittest.TestCase):
    setUp = test_play.Play.setUp
    M = test_manager.Manager
    player, package, second, more_missions = M.player, M.package, M.second, M.more_missions
    del M

    def manifest(self, variant):
        path = self.output / variant / 'manifest.json'
        return path, json.loads(path.read_text(encoding='utf-8'))

    def entries(self, zip_path):
        with zipfile.ZipFile(zip_path) as z: return {n: z.read(n) for n in z.namelist()}

    def test_a_project_left_out_leaves_nothing_in_the_pack(self):
        self.package()
        self.second()
        # the second build also has a cache of the first's name with other bytes, last in its manifest: its own map
        # was read before the conflict was found
        path, m = self.manifest(OTHER)
        (self.output / OTHER / 'CookedPCConsole' / 'Lighting_4242.tfc').write_bytes(b'other lightmaps')
        m['files']['CookedPCConsole/Lighting_4242.tfc'] = hashlib.sha256(b'other lightmaps').hexdigest()
        self.assertEqual(list(m['files'])[-1], 'CookedPCConsole/Lighting_4242.tfc')
        path.write_text(json.dumps(m), encoding='utf-8')
        r = manager.pack(self.store, self.builds, self.player(), dict(projects=[ID, OTHER_ID], mode='additional', name='Left out'))
        self.assertEqual(([p['variant'] for p in r['packed']], [s['id'] for s in r['skipped']]), ([VARIANT], [OTHER_ID]))
        self.assertIn('two of the builds', r['skipped'][0]['error'])
        entries = self.entries(r['zip'])
        self.assertFalse([n for n in entries if OTHER in n])
        described = json.loads(entries['pack.json'])
        self.assertEqual([m['variant'] for m in described['maps']], [VARIANT])
        self.assertEqual(set(described['files']), {f'{VARIANT}.upk', 'Lighting_4242.tfc', f'CIN_DropshipIntros_{VARIANT}.upk'})
        for name, digest in described['files'].items():
            member = next(n for n in entries if n.endswith('/' + name))
            self.assertEqual(hashlib.sha256(entries[member]).hexdigest(), digest)
        card = pack_card.read(entries[f'CookedPCConsole/{r["folder"]}/{described["card"]["file"]}'])
        self.assertEqual({m['Name'] for m in card['Maps']}, {VARIANT})
        self.assertEqual({z['MapName'] for z in card['LZArray']}, {VARIANT})
        self.assertNotIn(OTHER, entries['README.txt'].decode('latin-1'))
        self.assertEqual(entries['CookedPCConsole/Lighting_4242.tfc'], b'lightmaps')     # the accepted build's

    def test_a_card_line_the_card_cant_hold_leaves_its_project_out(self):
        self.package()
        self.second()
        path, m = self.manifest(OTHER)
        line = dep.set_field(test_play.record('bar'), 'Name', OTHER).decode('latin-1')
        line = re.sub(r'InitialChance=[^,)]*', 'InitialChance=abc', line)
        m['config'] = dict(maps=[line], recordMissions=[[0]], missions=['Abduction'])
        path.write_text(json.dumps(m), encoding='utf-8')
        r = manager.pack(self.store, self.builds, self.player(), dict(projects=[ID, OTHER_ID], mode='additional', name='Bad line'))
        self.assertEqual(([p['variant'] for p in r['packed']], [s['id'] for s in r['skipped']]), ([VARIANT], [OTHER_ID]))
        self.assertIn('abc', r['skipped'][0]['error'])
        # alone, it is no pack, with why
        with self.assertRaises(ProjectError) as error:
            manager.pack(self.store, self.builds, self.player(), dict(projects=[OTHER_ID], mode='additional', name='Bad alone'))
        self.assertEqual(error.exception.status, 409)
        self.assertIn('abc', error.exception.message)

    def test_no_text_of_the_pack_names_a_folder_of_this_computer(self):
        """The build's manifest holds absolute paths (project.file, source.file, work, the stages' and a donor's file)
        and its README one too: none reaches the zip, with the editor projects in it or not, and what a recipient
        checks (names, hashes, the project's id and revision) is still there."""
        self.package()
        path, m = self.manifest(VARIANT)
        root = Path(self.temp.name)
        m['project'].update(file=str(root / 'projects' / 'Bar remix.json'), savedAt='2026-11-20T10:00:00')
        m['source'].update(file='C:\\Games\\SentinelGame\\XEW\\XComGame\\CookedPCConsole\\URB_Bar.upk', exporterVersion=36)
        m.update(work=str(self.output / '.work' / VARIANT), attempt='a' * 32,
                 stages=[dict(stage='snapshot', base='C:\\Games\\SentinelStage\\URB_Bar.upk', export=str(Path.home() / 'cache'))],
                 donors=[dict(map='URB_Other', sha256='d' * 64, file='D:\\Games\\SentinelDonor\\URB_Other.upk', pieces=2)],
                 tools={'tools/editor/build.py': 'e' * 64})
        path.write_text(json.dumps(m), encoding='utf-8')
        readme = self.output / VARIANT / 'README.txt'
        readme.write_bytes(b'A variant.\r\nKept in ' + str(self.output / VARIANT).encode('latin-1') + b'\r\n')
        local = [str(root), str(Path.home()), 'Sentinel']
        for with_projects in (False, True):
            with self.subTest(projectFiles=with_projects):
                r = manager.pack(self.store, self.builds, self.player(),
                                 dict(projects=[ID], mode='additional', name=f'Clean {with_projects}', projectFiles=with_projects))
                entries = self.entries(r['zip'])
                self.assertEqual(any(n.startswith('projects/') for n in entries), with_projects)
                for name, data in entries.items():
                    if not name.lower().endswith(TEXT): continue
                    text = data.decode('utf-8', 'replace').replace('\\\\', '\\').replace('/', '\\').lower()
                    for folder in local:
                        self.assertNotIn(folder.replace('/', '\\').lower(), text, f'{name} names {folder}')
                public = json.loads(entries[f'packages/{VARIANT}/manifest.json'])
                self.assertEqual(public['project'], dict(id=ID, name='Bar remix', revision=1, savedAt='2026-11-20T10:00:00'))
                self.assertEqual(public['source'], dict(map='URB_Bar', sha256='s' * 64, exporterVersion=36))
                self.assertEqual(public['files'], m['files'])
                self.assertEqual(public['donors'], [dict(map='URB_Other', sha256='d' * 64, pieces=2)])
                self.assertNotIn('stages', public)
                self.assertNotIn('work', public)
                self.assertIn('<builds>', entries[f'packages/{VARIANT}/README.txt'].decode('latin-1'))
        # the build's own manifest is as it was
        self.assertEqual(self.manifest(VARIANT)[1]['work'], str(self.output / '.work' / VARIANT))

    def test_a_zip_that_fails_answers_why_and_leaves_nothing(self):
        self.package()
        with mock.patch('zipfile.ZipFile.write', side_effect=OSError('the disk is full')):
            with self.assertRaises(ProjectError) as error:
                manager.pack(self.store, self.builds, self.player(), dict(projects=[ID], mode='additional', name='Full disk'))
        self.assertEqual(error.exception.status, 500)
        self.assertIn('the disk is full', error.exception.message)
        self.assertEqual([p.name for p in (self.output / manager.PACKS).iterdir() if p.is_file()], [])

    def test_game_maps_refuses_records_that_are_no_ids(self):
        for records in ([['a']], [{'id': 'a'}], [1]):
            with self.subTest(records=records), self.assertRaises(ProjectError) as error:
                gamemaps.use(None, dict(records=records, use=False))
            self.assertEqual(error.exception.status, 400)


if __name__ == '__main__':
    unittest.main()

"""The exporter and the server's readers on damaged input, and the reads they keep (review findings 50 and 31): one
unreadable record ends nothing but itself, Package.cls names an import's own class, a level's actor list has one
answer when it can't be read, a missing area-light matcher says why (and the compiler says what helps), a failed
read of the script defaults is not kept, PowerShell starts once for the setup dialog, and a pack's zip is opened once
as it is."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import zipfile
import zlib

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'upk'))
sys.path.insert(0, str(HERE.parents[1] / 'editor'))
import pack_card  # noqa: E402
import export  # noqa: E402
from package import FormatError, Package  # noqa: E402
import effects_metadata  # noqa: E402
import packs  # noqa: E402
import piece_flags  # noqa: E402
import scene_metadata  # noqa: E402
import settings  # noqa: E402


class Damaged(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / 'Card.upk'
        self.path.write_bytes(pack_card.card('Card'))

    def test_package_cls_of_an_import_is_its_own_class(self):
        p = Package(self.path)
        self.assertEqual(p.cls(-1), p.imports[0]['cls'])
        self.assertEqual(p.cls(-2), p.imports[1]['cls'])
        self.assertEqual(p.cls(0), 'None')
        self.assertEqual(p.cls(1), p.imports[1]['name'])            # the card's export is of its second import's class
        for wrong in (len(p.exports) + 1, -len(p.imports) - 1):
            with self.assertRaises(FormatError):
                p.cls(wrong)

    def test_one_unreadable_record_ends_only_itself(self):
        def broken(error):
            def read(*args, **kwargs): raise error
            return read
        stage = self.root / 'stage'
        stage.mkdir()
        with mock.patch.object(export, 'building_metadata', broken(IndexError('list index out of range'))), \
                mock.patch.object(export, 'cursor_volumes', broken(zlib.error('invalid stored block lengths'))), \
                mock.patch.object(export, 'content_records', broken(KeyError('Floors'))), \
                mock.patch.object(export, 'landing_metadata', broken(ValueError('LZO block cut short (3 bytes)'))), \
                mock.patch.dict(sys.modules, {'area_light_bindings': None}):
            scene = export.Exporter(Package(self.path), stage).run('map')
        said = {d['source']: d['message'] for d in scene['diagnostics']}
        self.assertIn('list index out of range', said['buildings'])
        self.assertIn('invalid stored block lengths', said['cursor volumes'])
        self.assertIn('cut short', said['landings'])
        self.assertEqual((scene['buildings'], scene['cursorVolumes'], scene['landings']), ([], [], []))
        # (export 37: the map writes no level records; a streamed package's layer reads its own, guarded the same)
        self.assertNotIn('content', scene)
        with mock.patch.object(export, 'content_records', broken(KeyError('Floors'))):
            layer = export.Exporter(Package(self.path), stage, namespace='stream-Damaged').run('map')
        self.assertIn('Floors', {d['source']: d['message'] for d in layer['diagnostics']}['level records'])
        self.assertEqual(layer['content'], [])
        # the matcher missing: the export says why, and the compiler says exporting again alone won't help
        self.assertIn('area-light matcher', said['area lights'])
        self.assertIsNone(scene['lightMetadata']['areaMatcher'])
        import compiler
        problem = compiler.light_metadata_problem(dict(scene, exporterVersion=compiler.EXPORT_MINIMUM))
        self.assertIn('area-light matcher', problem)
        self.assertIn('Exporting it again gives the same until', problem)

    def test_a_level_list_that_cant_be_read_has_one_answer(self):
        p = Package(self.path)
        self.assertIsNone(scene_metadata.level_list(p))                 # no persistent level
        self.assertIsNone(effects_metadata.level_list(p, 1))             # not a level: the same reader, the same answer
        with mock.patch.object(scene_metadata, 'level_list', return_value=None) as asked:
            self.assertIsNone(effects_metadata.level_list(p, 7))
        asked.assert_called_once_with(p, 7)
        self.assertIn(12345, scene_metadata._Everything())

    def test_a_failed_read_of_the_script_defaults_is_not_kept(self):
        folder = self.root / 'cooked'
        found = iter([None, dict(Core='core')])
        with mock.patch.object(piece_flags.ScriptDefaults, '_read', staticmethod(lambda f: next(found))):
            self.assertIsNone(piece_flags.ScriptDefaults.of(folder))
            self.assertEqual(piece_flags.ScriptDefaults.of(folder), dict(Core='core'))
            self.assertEqual(piece_flags.ScriptDefaults.of(folder), dict(Core='core'))     # kept once read
        piece_flags.ScriptDefaults._done.pop(folder, None)

    def test_powershell_starts_once_for_the_setup_dialog(self):
        pwsh = self.root / 'pwsh.exe'
        pwsh.write_bytes(b'x')
        runs = []
        def run(argv, **kwargs):
            runs.append(argv)
            return mock.Mock(stdout='7\n')
        settings._POWERSHELL.clear()
        with mock.patch.object(settings.subprocess, 'run', run):
            first = settings._powershell_check(str(pwsh))
            self.assertEqual(settings._powershell_check(str(pwsh)), first)
            self.assertEqual((first['status'], len(runs)), ('ok', 1))
            pwsh.write_bytes(b'a newer pwsh')                              # another file: asked again
            settings._powershell_check(str(pwsh))
            self.assertEqual(len(runs), 2)
        with mock.patch.object(settings.subprocess, 'run', side_effect=OSError('no')):
            pwsh.write_bytes(b'broken')
            self.assertEqual(settings._powershell_check(str(pwsh))['status'], 'warn')
        with mock.patch.object(settings.subprocess, 'run', run):
            self.assertEqual(settings._powershell_check(str(pwsh))['status'], 'ok')        # a failure is not kept

    def test_a_packs_zip_is_opened_once_as_it_is(self):
        path = self.root / 'Night.zip'
        real = zipfile.ZipFile
        def write(name):
            with real(path, 'w') as z:
                z.writestr('pack.json', json.dumps(dict(name=name, maps=[dict(id='x', name='Bar', variant='URB_Bar_N')])))
        write('Night maps')
        opened = []
        with mock.patch.object(packs.zipfile, 'ZipFile', lambda *a, **k: opened.append(a) or real(*a, **k)):
            first = packs.from_zip(path)
            first['name'] = 'changed by a caller'
            self.assertEqual(packs.from_zip(path)['name'], 'Night maps')    # a copy each time
            self.assertEqual(len(opened), 1)
            import os
            write('Night maps 2')
            os.utime(path, (2_000_000_000, 2_000_000_000))
            self.assertEqual(packs.from_zip(path)['name'], 'Night maps 2')
            self.assertEqual(len(opened), 2)


if __name__ == '__main__':
    unittest.main()

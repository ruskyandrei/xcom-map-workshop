"""The release tooling (tools/release): what the zip takes of ours, its launcher and installer files, and the README
hand install's reading of a build's README.txt."""
from pathlib import Path
import re
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
RELEASE = HERE.parent
sys.path.insert(0, str(RELEASE))
sys.path.insert(0, str(RELEASE.parent / 'editor'))
import build  # noqa: E402
import make_release  # noqa: E402
from make_release import guide  # noqa: E402
import readme_install_check  # noqa: E402


class ReleaseTests(unittest.TestCase):
    def test_the_zip_takes_the_editors_modules_and_no_lab_or_patch_tools(self):
        names = {p.relative_to(make_release.TOOLS).as_posix() for p in make_release.modules()}
        for needed in ('viewer/viewer.py', 'viewer/gamesetup.py', 'editor/build.py', 'editor/compiler.py',
                       'bake/native_copy.py', 'bake/relight.py', 'upk/package_grow.py', 'viewer/version.py',
                       # the modules named for what they do (review finding 53): the config lines, the lighting
                       # records, the lightmap writer and textures
                       'viewer/mapsini.py', 'upk/lighting_records.py', 'bake/lightmap_writer.py', 'bake/lightmap_textures.py',
                       # pieces from other maps: the library, the transplanter and what it reads objects by
                       'viewer/library.py', 'bake/transplant.py', 'upk/schema.py', 'upk/typed_props.py',
                       'upk/native_fields.py', 'bake/shadowmaps.py', 'viewer/prefabs.py', 'viewer/prefab_bounds.py',
                       'viewer/prefab_tests.py', 'viewer/area_light_bindings.py', 'editor/prefab_stage.py',
                       # what the modules reach the other folders by (review finding 54)
                       'paths.py'):
            self.assertIn(needed, names)
        # nothing shipped imports the lab's tools since the config lines left deploy_fixture (review finding 53)
        self.assertFalse([n for n in names if n.startswith(('patch/', 'udk/', 're/', 'lab/')) or '/tests/' in n])
        # one module per name: the embedded Python's path finds each by name alone
        self.assertEqual(len({Path(n).name for n in names}), len(names))
        for extra in make_release.EXTRAS:
            self.assertTrue((make_release.TOOLS / extra).is_file(), extra)

    def test_the_launcher_and_installer_files(self):
        for name in make_release.TEMPLATES.values():
            data = (RELEASE / name).read_bytes()
            if name.endswith(('.cmd', '.ps1')):
                data.decode('ascii')    # Windows PowerShell 5.1 reads a BOM-less script as the ANSI code page
            if name.endswith('.cmd'):
                self.assertEqual(data.count(b'\n'), data.count(b'\r\n'), name)
        self.assertIn(b'serve --reuse', (RELEASE / 'XCOM Map Workshop.cmd').read_bytes())
        self.assertTrue((make_release.REPO / 'LICENSE').read_text(encoding='utf-8').startswith('MIT License'))
        self.assertRegex(make_release.PYTHON_SHA256 or '', r'^[0-9a-f]{64}$')

    def test_the_installer_script(self):
        text = make_release.INSTALLER.read_bytes().decode('ascii')
        # the game folder page, the settings written by the bundled Python as the user who ran Setup, per-user by default
        for needed in ('CreateInputDirPage', 'tools\\viewer\\gamesetup.py', '" set "', 'ExecAsOriginalUser', 'PrivilegesRequired=lowest',
                       'PrivilegesRequiredOverridesAllowed=dialog', 'DefaultDirName={autopf}', '{param:GAMEDIR|}',
                       'XEW\\XComGame\\CookedPCConsole', 'LicenseFile={#Stage}\\LICENSE.txt',
                       'OutputBaseFilename=XCOM-Map-Workshop-{#Version}-Setup', '[InstallDelete]'):
            self.assertIn(needed, text)
        # an upgrade while the editor runs: Setup asks for it to be closed by the mutex its server holds
        import appmutex
        self.assertIn('AppMutex=%s,Global\\%s' % (appmutex.NAME, appmutex.NAME), text)
        # the user guide: a Start menu shortcut to it, and offered on the last page (the file make_release stages)
        entries = [line for line in text.splitlines() if '{app}\\%s"' % guide.KIT_NAME in line]
        self.assertEqual(len(entries), 2, entries)
        self.assertTrue(entries[0].startswith('Name: "{autoprograms}\\'))
        self.assertTrue(all(flag in entries[1] for flag in ('postinstall', 'shellexec', 'skipifsilent', 'runasoriginaluser')))
        # the file make_release looks for is the one the script names
        self.assertEqual(make_release.installer.__doc__.split()[0], 'XCOM-Map-Workshop-<version>-Setup.exe')
        # a compiler given that doesn't exist is passed over for the usual places (none here, or Inno Setup's)
        found = make_release.find_iscc(make_release.REPO / 'no-such' / 'ISCC.exe')
        self.assertTrue(found is None or found.name.lower() == 'iscc.exe')

    def test_the_installers_game_kind_is_the_editors(self):
        """(review finding 55) The installer's GameKind tells what a game folder holds by the same folder and config
        files, in the same order, as settings.game_kind, and passes over the lab copy by settings' marker, as
        resolve_game does. Its labels are settings.KINDS', plain Enemy Within's said "(plain)" beside the two Long Wars."""
        import settings
        text = make_release.INSTALLER.read_bytes().decode('ascii')
        body = text[text.index('function GameKind('):]
        body = body[:body.index('\nend;')]
        self.assertEqual(re.findall(r"DirExists\(Root \+ '([^']+)'\)", body), ['XEW\\XComGame\\CookedPCConsole'])
        marker, *configs = re.findall(r"FileExists\(Root \+ '([^']+)'\)", body)
        self.assertEqual(marker, settings.LAB_MARKER)
        labels = re.findall(r"Result := '([^']+)'", body)
        self.assertEqual(labels, [settings.KINDS['lwr'], settings.KINDS['longwar'], settings.KINDS['ew'] + ' (plain)'])
        # a folder holding the installer's first config file and the ones after it, then its second..., then none: the
        # kinds settings tells in that order are the ones the installer's labels name in its order
        told = []
        for first in range(len(configs) + 1):
            with tempfile.TemporaryDirectory() as tmp:
                game = Path(tmp)
                Path(game, *'XEW\\XComGame\\CookedPCConsole'.split('\\')).mkdir(parents=True)
                for name in configs[first:]:
                    path = Path(game, *name.split('\\'))
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b'')
                told.append(settings.game_kind(game))
        self.assertEqual(told, ['lwr', 'longwar', 'ew'])

    def test_a_download_is_checked_before_it_is_kept(self):
        import hashlib
        import tempfile
        good = b'the pinned bytes'
        digest = hashlib.sha256(good).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            with self.assertRaises(SystemExit):
                make_release.download('https://example.invalid/x.zip', cache, digest, fetch=lambda u: b'tampered')
            self.assertEqual(list(cache.iterdir()), [])         # nothing bad stays behind
            self.assertEqual(make_release.download('https://example.invalid/x.zip', cache, digest, fetch=lambda u: good), good)
            (cache / 'x.zip').write_bytes(b'damaged since')      # a damaged cache file is fetched again
            self.assertEqual(make_release.download('https://example.invalid/x.zip', cache, digest, fetch=lambda u: good), good)
            self.assertEqual((cache / 'x.zip').read_bytes(), good)

    def test_the_page_ships_what_git_tracks_and_the_pinned_vendor_files(self):
        web = make_release.TOOLS / 'viewer' / 'web'
        probe = web / 'untracked-probe.tmp'
        probe.write_bytes(b'x')
        try:
            files = make_release.page_files()
        finally:
            probe.unlink()
        names = {p.relative_to(web).as_posix() for p in files}
        self.assertNotIn('untracked-probe.tmp', names)
        self.assertTrue({'index.html', 'app.js', 'style.css'} <= names)
        vendored = {'vendor/three/' + k for k in make_release.setup_vendor.CHECKSUMS}
        present = {n for n in vendored if (web / n).is_file()}
        self.assertEqual(present, vendored & names)
        self.assertNotIn('upk/map_inventory.py', make_release.EXTRAS)   # nothing shipped runs it

    def test_the_user_guide_is_one_page_with_its_pictures_and_sections(self):
        source = guide.SOURCE
        text = source.read_text(encoding='utf-8')
        # every picture it names is there, and none is left over
        named = set(re.findall(r'src="(shots/[^"]+)"', text))
        self.assertEqual(named, {'shots/' + p.name for p in (source.parent / 'shots').iterdir()})
        # as one page: the pictures inside it, the version in, nothing loaded from beside it or from the net
        page = guide.inline(source, '9.8.7').decode('utf-8')
        self.assertEqual(re.findall(r'(?:src|href)="(?!data:image/webp;base64,|#)[^"]*"', page), [])
        self.assertNotRegex(page, r'url\(|@import|<link\b')
        self.assertIn('<span id="guideVersion">9.8.7</span>', page)
        self.assertEqual(page.count('data:image/webp;base64,'), len(re.findall(r'src="shots/', text)))
        # the contents list and the links name sections that are there, each once
        ids = re.findall(r'\bid="([\w-]+)"', text)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertFalse(set(re.findall(r'href="#([\w-]+)"', text)) - set(ids))
        # the controls the pictures mark are the page's own: one renamed there means the guide needs a look
        shots = (source.parent / 'take_shots.py').read_text(encoding='utf-8')
        web = (make_release.TOOLS / 'viewer' / 'web' / 'index.html').read_text(encoding='utf-8')
        marked = {m for m in re.findall(r"'#([A-Za-z]\w*)", shots) if not re.fullmatch(r'[0-9a-f]{6}', m)}
        self.assertGreater(len(marked), 60)
        self.assertFalse(marked - set(re.findall(r'\bid="(\w+)"', web)))
        # the editor's ? menu links to where the server serves it
        self.assertIn('href="guide.html"', web)
        self.assertEqual(guide.KIT_NAME, 'User Guide.html')

    def test_a_build_readme_reads_as_the_hand_install_follows_it(self):
        m = dict(variant='URB_Bar_X_1', patch=None, cache='Lighting_1001', editorVersion='0.1.0', builtAt='now',
                 files={'CookedPCConsole/URB_Bar_X_1.upk': 'a', 'CookedPCConsole/Lighting_1001.tfc': 'b'},
                 project=dict(id='p', name='X', revision=1), source=dict(map='URB_Bar', sha256='s'),
                 intros=[], config=dict(maps=['Maps=( Name="URB_Bar_X_1", bInRotation=False )'], missions=['Abduction'],
                                        streamSlots=[None], landingZones=['LZArray=(MapName="URB_Bar_X_1")'],
                                        miniMods=['Rule=(Map="URB_Bar_X_1")']))
        s = readme_install_check.sections(build.readme(m))
        self.assertEqual(sorted(s['files']), ['Lighting_1001.tfc', 'URB_Bar_X_1.upk'])
        self.assertEqual(s['DefaultMaps.ini'], m['config']['maps'])
        self.assertEqual(s['DefaultLZMutator.ini'], m['config']['landingZones'])
        self.assertEqual(s['DefaultMiniMods.ini'], m['config']['miniMods'])
        # plain EW: no landing-zone or mini-mod lines at all
        m['config'].update(landingZones=None, miniMods=None)
        s = readme_install_check.sections(build.readme(m))
        self.assertEqual(sorted(s), ['DefaultMaps.ini', 'files'])

    def test_the_smoke_tests_read_a_zip_back_against_the_repository(self):
        import tempfile
        import zipfile
        import smoke_release
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'
            (repo / 'tools/release').mkdir(parents=True)
            (repo / 'tools/viewer').mkdir(parents=True)
            (repo / 'tools/release/GETTING-STARTED.md').write_bytes(b'readme\n')
            (repo / 'tools/viewer/viewer.py').write_bytes(b'print(1)\n')
            (repo / 'tools/viewer/a.py').write_bytes(b'a\n')

            def make(v, files):
                path = Path(tmp) / ('%s.zip' % len(list(Path(tmp).glob('*.zip'))))
                with zipfile.ZipFile(path, 'w') as z:
                    for name, data in files.items():
                        z.writestr('XCOM-Map-Workshop-%s/%s' % (v, name), data)
                return path
            good = {'VERSION.txt': '%s 9.9.9\r\n' % smoke_release.NAME, 'README.md': b'readme\n',
                    'User Guide.html': b'<th>New in 9.9.9</th>', 'XCOM Map Workshop.cmd': b'', 'LICENSE.txt': b'',
                    'THIRD-PARTY-NOTICES.txt': b'', 'python/python.exe': b'', 'tools/viewer/viewer.py': b'print(1)\n',
                    'tools/viewer/a.py': b'a\n', 'tools/viewer/__pycache__/a.cpython-312.pyc': b'compiled'}
            self.assertEqual(smoke_release.check_zip(make('9.9.9', good), '9.9.9', repo), ([], 2))
            bad = dict(good, **{'tools/viewer/a.py': b'changed\n', 'tools/viewer/extra.py': b'',
                                'User Guide.html': b'<th>New in 9.9.8</th>', 'VERSION.txt': 'XCOM Map Workshop 9.9.8'})
            del bad['python/python.exe']
            problems, _ = smoke_release.check_zip(make('9.9.9', bad), '9.9.9', repo)
            self.assertEqual(sorted(problems), sorted([
                'missing: python/python.exe', "VERSION.txt says 'XCOM Map Workshop 9.9.8'",
                'the user guide has no "New in 9.9.9" table', 'differs from the repository: tools/viewer/a.py',
                'not in the repository: tools/viewer/extra.py']))
            # a zip made for another version: its folder isn't the version's
            self.assertIn('missing: VERSION.txt', smoke_release.check_zip(make('9.9.8', good), '9.9.9', repo)[0])


if __name__ == '__main__': unittest.main()

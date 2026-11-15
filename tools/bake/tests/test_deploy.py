"""Deploying a lighting fixture to a test slot and restoring it, on a temporary copy of the lab's layout."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import deploy_fixture as dep  # noqa: E402

RECORDS = HERE.parents[1] / 'patch' / 'tests' / 'defaultmaps-records.txt'


def record(name):
    for line in RECORDS.read_bytes().split(b'\n'):
        if line.startswith(name.encode() + b'\t'):
            return line.split(b'\t', 1)[1]
    raise KeyError(name)


class DeployRestore(unittest.TestCase):
    def setUp(self):
        # the tests work on a temporary layout, so whether the real game is open does not matter
        running = dep.game_running
        self.addCleanup(setattr, dep, 'game_running', running)
        dep.game_running = lambda: False
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.game, self.work = root / 'game', root / 'work'
        (self.game / 'XEW/XComGame/Config').mkdir(parents=True)
        (self.game / 'XEW/XComGame/CookedPCConsole').mkdir(parents=True)
        (self.game / 'XComLab-copy.txt').write_text('lab')
        bar = record('bar')
        slot = dep.set_field(record('templeship'), 'DisplayName', dep.TEST_SLOT)
        self.maps = dep.EOL.join([b'[XComGame.XComMapManager]', bar, b';comment', slot, b''])
        self.lz = dep.EOL.join([b'[XComLZMutator.XComLZMutator]', b';URB_Bar locations - tested',
                                b'LZArray=(MapName="URB_Bar",StartLoc=(X=1,Y=2,Z=3))',
                                b'LZArray=(MapName="URB_Bar",StartLoc=(X=4,Y=5,Z=6))',
                                b';Other', b'LZArray=(MapName="Other",StartLoc=(X=0,Y=0,Z=0))', b''])
        self.cfg = self.game / 'XEW/XComGame/Config'
        (self.cfg / 'DefaultMaps.ini').write_bytes(self.maps)
        (self.cfg / 'DefaultLZMutator.ini').write_bytes(self.lz)
        out = root / 'fixture'
        out.mkdir()
        files = {}
        for name, data in [('URB_BarLight.upk', b'map'), ('Lighting_7000.tfc', b'cache')]:
            (out / name).write_bytes(data)
            files[str(out / name)] = hashlib.sha256(data).hexdigest()
        self.manifest = out / 'URB_BarLight.fixture.json'
        self.manifest.write_text(json.dumps(dict(variant='URB_BarLight', source=r'C:\x\URB_Bar.upk', outputs=files)))

    def tearDown(self):
        self.tmp.cleanup()

    def test_dry_run_changes_nothing(self):
        plan = dep.deploy(self.manifest, self.game, self.work, dry=True)
        self.assertEqual(plan['testSlotLine'], 4)
        self.assertEqual((self.cfg / 'DefaultMaps.ini').read_bytes(), self.maps)
        self.assertFalse(self.work.exists())

    def test_deploy_then_restore(self):
        plan = dep.deploy(self.manifest, self.game, self.work)
        lines = (self.cfg / 'DefaultMaps.ini').read_bytes().split(dep.EOL)
        slot = lines[3]
        self.assertEqual(dep.field(slot, 'Name'), 'URB_BarLight')
        self.assertEqual(dep.field(slot, 'DisplayName'), dep.TEST_SLOT)
        self.assertIn(b'MapName="patch_bar"', slot)
        self.assertNotIn(b'TempleShip_Stream', slot)
        self.assertEqual(dep.unquoted(slot, 'eRegion'), 'eMissionRegion_None')
        self.assertEqual(dep.unquoted(slot, 'TimeOfDay'), dep.unquoted(record('bar'), 'TimeOfDay'))
        self.assertEqual(lines[1], record('bar'))
        lz = (self.cfg / 'DefaultLZMutator.ini').read_bytes().split(dep.EOL)
        self.assertTrue(lz[4].startswith(b';URB_BarLight locations = copy of URB_Bar'))
        self.assertEqual(lz[5:7], [b'LZArray=(MapName="URB_BarLight",StartLoc=(X=1,Y=2,Z=3))',
                                   b'LZArray=(MapName="URB_BarLight",StartLoc=(X=4,Y=5,Z=6))'])
        self.assertEqual((self.game / 'XEW/XComGame/CookedPCConsole/Lighting_7000.tfc').read_bytes(), b'cache')
        self.assertEqual(len(list((self.work / 'backups').iterdir())), 2)
        dep.restore(plan['record'], self.game)
        self.assertEqual((self.cfg / 'DefaultMaps.ini').read_bytes(), self.maps)
        self.assertEqual((self.cfg / 'DefaultLZMutator.ini').read_bytes(), self.lz)

    def test_second_deploy_chains_back_to_the_original_slot(self):
        first = dep.deploy(self.manifest, self.game, self.work, now=__import__('datetime').datetime(2026, 11, 6, 21))
        m = json.loads(self.manifest.read_text())
        m['variant'] = 'URB_BarLight2'
        second_manifest = self.manifest.with_name('URB_BarLight2.fixture.json')
        second_manifest.write_text(json.dumps(m))
        second = dep.deploy(second_manifest, self.game, self.work, now=__import__('datetime').datetime(2026, 11, 6, 22))
        self.assertEqual(second['previous'], first['record'])
        slot = (self.cfg / 'DefaultMaps.ini').read_bytes().split(dep.EOL)[3]
        self.assertEqual(dep.field(slot, 'Name'), 'URB_BarLight2')
        lz = (self.cfg / 'DefaultLZMutator.ini').read_bytes()
        self.assertIn(b'MapName="URB_BarLight2"', lz)
        self.assertIn(b'MapName="URB_BarLight"', lz)
        dep.restore(second['record'], self.game)
        self.assertEqual((self.cfg / 'DefaultMaps.ini').read_bytes(), self.maps)
        self.assertEqual((self.cfg / 'DefaultLZMutator.ini').read_bytes(), self.lz)

    def test_reset_writes_lwrs_own_first_mission_back_and_restore_undoes_it(self):
        lwr = Path(self.tmp.name) / 'lwr'
        (lwr / 'XEW/XComGame/Config').mkdir(parents=True)
        default = dep.set_field(record('liquorstore'), 'DisplayName', dep.TEST_SLOT)
        (lwr / 'XEW/XComGame/Config/DefaultMaps.ini').write_bytes(dep.EOL.join([b'[XComGame.XComMapManager]', default, b'']))
        deployed = dep.deploy(self.manifest, self.game, self.work, now=__import__('datetime').datetime(2026, 11, 8, 10))
        after_deploy = (self.cfg / 'DefaultMaps.ini').read_bytes()
        self.assertEqual(dep.reset(lwr, self.game, self.work, dry=True)['testSlotNew'], default.decode('latin1'))
        self.assertEqual((self.cfg / 'DefaultMaps.ini').read_bytes(), after_deploy)        # the dry run wrote nothing
        plan = dep.reset(lwr, self.game, self.work, now=__import__('datetime').datetime(2026, 11, 8, 11))
        lines = (self.cfg / 'DefaultMaps.ini').read_bytes().split(dep.EOL)
        self.assertEqual(lines[3], default)
        self.assertEqual(lines[:3] + lines[4:], after_deploy.split(dep.EOL)[:3] + after_deploy.split(dep.EOL)[4:])
        self.assertEqual(plan['previous'], deployed['record'])
        self.assertIn(b'MapName="URB_BarLight"', (self.cfg / 'DefaultLZMutator.ini').read_bytes())   # left, harmless
        self.assertIsNone(dep.reset(lwr, self.game, self.work))                           # LWR's own already
        dep.restore(plan['record'], self.game, chain=False)
        self.assertEqual((self.cfg / 'DefaultMaps.ini').read_bytes(), after_deploy)
        (self.game / 'XComLab-copy.txt').unlink()
        with self.assertRaises(SystemExit):
            dep.reset(lwr, self.game, self.work)

    def test_streams_a_patch_in_the_first_free_slot(self):
        with self.assertRaises(ValueError):           # the patch must be in the lab first
            dep.deploy(self.manifest, self.game, self.work, dry=True, streams=['patch_pooldel'])
        (self.game / 'XEW/XComGame/CookedPCConsole/patch_pooldel.upk').write_bytes(b'patch')
        plan = dep.deploy(self.manifest, self.game, self.work, streams=['patch_pooldel'])
        self.assertEqual(plan['streams'], ['patch_pooldel'])
        slot = (self.cfg / 'DefaultMaps.ini').read_bytes().split(dep.EOL)[3]
        # URB_Bar's record streams slots 0, 1 and 5: the patch takes 2, and the base streams stay
        self.assertEqual(dep.stream_slots(slot), [0, 1, 5, 2])
        self.assertIn(b', StreamingMaps[2]=( MapName="patch_pooldel", Loc=( X=0, Y=0, Z=0 ), '
                      b'Rot=( Pitch=0, Yaw=0, Roll=0 ) ) )', slot)
        self.assertIn(b'MapName="patch_bar"', slot)
        self.assertEqual(dep.field(slot, 'Name'), 'URB_BarLight')
        dep.restore(plan['record'], self.game)
        self.assertEqual((self.cfg / 'DefaultMaps.ini').read_bytes(), self.maps)

    def test_seed_plan_deploys_a_seeded_copy_of_the_variant(self):
        plan_file = Path(self.tmp.name) / 'seed-plan-built.tsv'
        with self.assertRaises(ValueError):           # the plan must exist
            dep.deploy(self.manifest, self.game, self.work, dry=True, seed_plans=[plan_file])
        plan_file.write_text('object\n')
        calls = []

        def fake_seed(src, dst, plans):               # the test layout's map is not a real package
            calls.append((Path(src).name, [str(p) for p in plans]))
            Path(dst).parent.mkdir(parents=True, exist_ok=True)
            Path(dst).write_bytes(Path(src).read_bytes() + b'+seeds')
            return 'seeded 3 of 3 planned tiles'
        real = dep.seed_variant
        self.addCleanup(setattr, dep, 'seed_variant', real)
        dep.seed_variant = fake_seed
        plan = dep.deploy(self.manifest, self.game, self.work, seed_plans=[plan_file])
        self.assertEqual(calls, [('URB_BarLight.upk', [str(plan_file)])])
        deployed = self.game / 'XEW/XComGame/CookedPCConsole/URB_BarLight.upk'
        self.assertEqual(deployed.read_bytes(), b'map+seeds')
        self.assertEqual(plan['seeded']['report'], 'seeded 3 of 3 planned tiles')
        ledger = json.loads((self.work / 'deployed.json').read_text())
        self.assertEqual(ledger[str(deployed)], hashlib.sha256(b'map+seeds').hexdigest())
        # the cache is copied as built, and a redeploy over the seeded map is allowed
        self.assertEqual((self.game / 'XEW/XComGame/CookedPCConsole/Lighting_7000.tfc').read_bytes(), b'cache')
        dep.deploy(self.manifest, self.game, self.work, dry=True)

    def test_a_base_map_without_landing_zones_gets_none(self):
        self.assertEqual(dep.plan_lz([b'LZArray=(MapName="Other")'], 'TempleShip', 'TempleShip_X_1', 'note'), (None, []))

    def test_a_base_map_of_another_kind_plays_as_the_first_missions_abduction(self):
        slot = dep.set_field(record('bar'), 'DisplayName', dep.TEST_SLOT)
        at, old, new = dep.plan_maps([record('templeship'), slot], 'TempleShip', 'TempleShip_X_1')
        self.assertEqual((at, old), (1, slot))
        self.assertEqual(dep.field(new, 'Name'), 'TempleShip_X_1')
        self.assertEqual(dep.unquoted(new, 'MissionType'), 'eMission_Abduction')
        self.assertEqual(dep.field(new, 'MapFamily'), 'URB_Bar')
        self.assertEqual(dep.unquoted(new, 'TimeOfDay'), dep.unquoted(record('templeship'), 'TimeOfDay'))
        self.assertIn(b'TempleShip_Stream', new)
        # an abduction map keeps its own family
        at, old, new = dep.plan_maps([record('liquorstore'), slot], 'URB_LiquorStore', 'URB_LiquorStore_X_1')
        self.assertEqual(dep.field(new, 'MapFamily'), 'URB_LiquorStore')

    def test_a_variants_own_intro_is_streamed_in_place_of_the_original(self):
        slot = dep.set_field(record('bar'), 'DisplayName', dep.TEST_SLOT)
        at, old, new = dep.plan_maps([record('bar'), slot], 'URB_Bar', 'URB_Bar_X_1', streams=['patch_x'],
                                     replace={'CIN_DropshipIntros': 'CIN_DropshipIntros_URB_Bar_X_1'})
        self.assertIn(b'StreamingMaps[0]=( MapName="CIN_DropshipIntros_URB_Bar_X_1"', new)
        self.assertNotIn(b'MapName="CIN_DropshipIntros"', new)
        self.assertIn(b'MapName="patch_x"', new)
        with self.assertRaises(ValueError):         # a record that streams no such intro
            dep.plan_maps([record('templeship'), slot], 'TempleShip', 'TempleShip_X_1',
                          replace={'CIN_DropshipIntros': 'CIN_DropshipIntros_TempleShip_X_1'})

    def test_a_map_with_several_records_plays_its_abduction(self):
        slot = dep.set_field(record('bar'), 'DisplayName', dep.TEST_SLOT)
        bar = record('bar')
        bomb = dep.set_field(dep.set_field(bar, 'MissionType', 'eMission_Special', quoted=False), 'CouncilType',
                             'eFCMType_Bomb', quoted=False)
        terror = dep.set_field(bar.replace(b'CIN_DropshipIntros', b'CIN_FastropeIntros'), 'MissionType',
                               'eMission_TerrorSite', quoted=False)
        both = {'CIN_DropshipIntros': 'CIN_DropshipIntros_URB_Bar_X_1', 'CIN_FastropeIntros': 'CIN_FastropeIntros_URB_Bar_X_1'}
        at, old, new = dep.plan_maps([bomb, terror, bar, slot], 'URB_Bar', 'URB_Bar_X_1', replace=both)
        self.assertEqual((at, dep.unquoted(new, 'MissionType'), dep.unquoted(new, 'CouncilType')),
                         (3, 'eMission_Abduction', 'eFCMType_None'))
        self.assertIn(b'MapName="CIN_DropshipIntros_URB_Bar_X_1"', new)     # the fast-rope copy is another record's
        # without an abduction record: the first that is no council mission, played as the abduction
        other = dep.set_field(record('liquorstore'), 'DisplayName', dep.TEST_SLOT)   # a slot that isn't a bar record
        at, old, new = dep.plan_maps([bomb, terror, other], 'URB_Bar', 'URB_Bar_X_1', replace=both)
        self.assertEqual((dep.unquoted(new, 'MissionType'), dep.unquoted(new, 'CouncilType')),
                         ('eMission_Abduction', 'eFCMType_None'))
        self.assertIn(b'MapName="CIN_FastropeIntros_URB_Bar_X_1"', new)

    def test_add_stream_refuses_a_patch_streamed_already(self):
        with self.assertRaises(ValueError):
            dep.add_stream(record('bar'), 'patch_bar')

    def test_redeploy_over_own_files_but_not_others(self):
        dep.deploy(self.manifest, self.game, self.work)
        foreign = self.game / 'XEW/XComGame/CookedPCConsole/URB_BarLight.upk'
        foreign.write_bytes(b'someone else')
        with self.assertRaises(ValueError):
            dep.deploy(self.manifest, self.game, self.work, dry=True)

    def test_replaces_patchtool_files_with_a_backup_but_no_others(self):
        cooked = self.game / 'XEW/XComGame/CookedPCConsole'
        pt = Path(self.tmp.name) / 'patchtool'
        pt.mkdir()
        (cooked / 'URB_BarLight.upk').write_bytes(b'patchtool seeded map')
        (cooked / 'Lighting_7000.tfc').write_bytes(b'someone else')
        digest = hashlib.sha256(b'patchtool seeded map').hexdigest().upper()
        (pt / 'seeded.txt').write_text(f'2026-11-06 19:42:59\tURB_BarLight\tpatch_x\t9\t{digest}\n')
        with self.assertRaisesRegex(ValueError, 'Lighting_7000.tfc exists'):
            dep.deploy(self.manifest, self.game, self.work, patchtool=pt)
        (pt / 'deployed.txt').write_text('patch_exp04b\nLighting_7000\n')
        plan = dep.deploy(self.manifest, self.game, self.work, patchtool=pt)
        self.assertEqual(sorted(Path(d).name for d in plan['replaced']), ['Lighting_7000.tfc', 'URB_BarLight.upk'])
        self.assertEqual(Path(plan['replaced'][str(cooked / 'URB_BarLight.upk')]).read_bytes(), b'patchtool seeded map')
        self.assertEqual((cooked / 'URB_BarLight.upk').read_bytes(), b'map')
        # a map patchtool seeded, changed since: not its file any more
        (cooked / 'URB_BarLight.upk').write_bytes(b'changed')
        self.assertFalse(dep.patchtool_owns(cooked / 'URB_BarLight.upk', pt))

    def test_refuses_without_lab_marker(self):
        (self.game / 'XComLab-copy.txt').unlink()
        with self.assertRaises(SystemExit):
            dep.deploy(self.manifest, self.game, self.work)
        self.assertEqual((self.cfg / 'DefaultMaps.ini').read_bytes(), self.maps)

    def test_refuses_while_the_game_runs(self):
        dep.game_running = lambda: True
        with self.assertRaises(SystemExit):
            dep.deploy(self.manifest, self.game, self.work)
        self.assertEqual((self.cfg / 'DefaultMaps.ini').read_bytes(), self.maps)

    def test_restore_refuses_a_slot_changed_since(self):
        plan = dep.deploy(self.manifest, self.game, self.work)
        lines = (self.cfg / 'DefaultMaps.ini').read_bytes().split(dep.EOL)
        lines[3] = lines[3].replace(b'URB_BarLight', b'Something')
        (self.cfg / 'DefaultMaps.ini').write_bytes(dep.EOL.join(lines))
        with self.assertRaises(ValueError):
            dep.restore(plan['record'], self.game)


if __name__ == '__main__':
    unittest.main()

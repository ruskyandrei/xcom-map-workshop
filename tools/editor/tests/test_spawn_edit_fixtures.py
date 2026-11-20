"""The base map's spawn points edited (the compiler's spawn family: spawn_edits.py) against recorded fixtures.

spawn_edit_cases.json holds, for each case of the compiler tests' spawn scene (test_compiler.CompilerTests.spawn_scene),
its inputs (the scene: the base scene with the keys the case changes, the project document, the families switched on
or off) and what the compiler gave for them
when the family was moved out of the Compiler class (review finding 23): whether the report is ok, the native edit's
`spawns` lane (the records the Build writes), the report's spawn entities and spawn counts, and every error, warning,
note and piece left out, in order. A change that alters any of them fails here, so a refactor of the family keeps
actor identity, record ordering, diagnostics and partial builds as they were.

  python -B tools/editor/tests/test_spawn_edit_fixtures.py --write      records the cases again (after a deliberate change)
"""
import contextlib
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import compiler  # noqa: E402

CASES = HERE / 'spawn_edit_cases.json'


def scene_of(recorded, key):
    """A case's scene: the recorded base scene with the keys its scene changes."""
    return dict(recorded['base'], **recorded['scenes'][key])


def outcome(doc, scene, enable=(), family_off=False):
    """What a case gives: the report's verdict, the spawns lane, spawn entities and counts, and its diagnostics."""
    with mock.patch.dict(compiler.FAMILIES['spawn'], builds=False) if family_off else contextlib.nullcontext():
        spec, report = compiler.compile_project(copy.deepcopy(doc), copy.deepcopy(scene), list(enable))
    lane = compiler.native_split(spec)[1].get('spawns') if spec is not None else None
    return dict(ok=report['ok'], spawns=lane, entities=[e for e in report['entities'] if e['kind'] == 'spawn'],
                counts=report['counts']['spawns'], errors=report['errors'], warnings=report['warnings'],
                notes=report['notes'], leftOut=report['leftOut'])


def record():
    """The cases, built from the compiler tests' spawn scene and records (test_compiler.py's four spawn tests)."""
    import test_compiler as t
    PL, document, target = t.PL, t.document, t.target
    s, at = t.CompilerTests('test_base_spawn_points_copied_and_deleted').spawn_scene()
    scenes, cases = {}, []

    def case(name, scene, doc, enable=(), family_off=False):
        changed = {k: copy.deepcopy(v) for k, v in scene.items() if s.get(k) != v}
        key = next((k for k, v in scenes.items() if v == changed), None)
        if key is None:
            key = 'scene%d' % len(scenes)
            scenes[key] = changed
        cases.append(dict(name=name, scene=key, doc=doc, enable=list(enable), familyOff=family_off))

    # moved and given values (SP6), with the family off and on, and each refusal
    moved = copy.deepcopy(s)
    moved['spawns'][0]['links'] = [dict(property='PathNode', actor=PL + 'XComAlienPathNode_4')]
    moved['spawns'].append(dict(actor=PL + 'XComSpawnPoint_Alien_3', actorClass='XComSpawnPoint_Alien', kind='dropIn',
                                location=at(5, 5), rotation=[0, 0, 0], values={}))
    moved['spawns'].append(dict(actor=PL + 'XComSpawnPoint_18', actorClass='XComSpawnPoint', kind='soldier',
                                location=at(6, 6), rotation=[0, 0, 0], values={}))
    pod = moved['spawns'][0]
    edits = [dict(target=target('XComAlienPod_0'), location=[pod['location'][0] + 96, *pod['location'][1:]], rotation=[0, 16384, 0]),
             dict(target=target('XComAlienPod_1'), spawn=dict(commander=True)),
             dict(target=target('XComMeldContainerSpawnPoint_1'), spawn=dict(difficulty='Hard', destroyedOnTurn=6, spawnGroup=0)),
             dict(target=target('XComSpawnPoint_Alien_3'), location=at(7, 5), rotation=[0, -16384, 0])]
    case('moved, family off', moved, document(edits), family_off=True)
    case('moved and given values', moved, document(edits))
    refusing = copy.deepcopy(moved)
    refusing['spawns'][2]['listed'] = False
    refusing['spawns'][3]['unread'] = 'bad bytes'
    for k, rec in enumerate([dict(target=target('XComAlienPod_1'), spawn=dict(difficulty='Hard')),
                             dict(target=target('XComMeldContainerSpawnPoint_1'), spawn=dict(destroyedOnTurn=100)),
                             dict(target=target('XComMeldContainerSpawnPoint_1'), spawn=dict(difficulty='Medium')),
                             dict(target=target('XComAlienPod_0'), spawn=dict(use=1)),
                             dict(target=target('XComSpawnPoint_18'), location=at(9, 9), rotation=[0, 0, 0]),
                             dict(target=target('XComAlienPod_2'), spawn=dict(commander=True)),
                             dict(target=target('XComMeldContainerSpawnPoint_0'), spawn=dict(spawnGroup=1)),
                             dict(target=target('XComAlienPod_0'), spawn=dict(colour='red')),
                             dict(target=target('XComAlienPod_0'), spawn='commander'),
                             dict(target=target('XComAlienPod_0'), spawn=dict(commander=False), extra=1)]):
        case('override refused or noted %d' % k, refusing, document([rec]), enable=['spawn'])
    # copied and deleted (SP7), with the family off and on, and each refusal
    copied = copy.deepcopy(s)
    copied['spawns'][1]['uses'] = [dict(how='event', by='Main_Sequence.SeqEvent_OnRevealPod_0', podId=7, staticOnly=False)]
    copied['spawns'][1]['values']['commander'] = {'value': True, 'from': 'saved'}
    copied['spawns'].append(dict(actor=PL + 'XComSpawnPoint_Alien_3', actorClass='XComSpawnPoint_Alien', kind='dropIn',
                                 location=at(5, 5), rotation=[0, 0, 0], values={},
                                 uses=[dict(how='direct', by='Main_Sequence.SeqAct_SpawnAlien_1', byClass='SeqAct_SpawnAlien')]))
    copied['streams']['URB_Bar_CNH']['missionObjects'].append(dict(actor=PL + 'XComAlienPod_9', actorClass='XComAlienPod', kind='pod',
                                                                   location=at(1, 1), values={'podIndex': {'value': 9, 'from': 'saved'}}))

    def a_copy(n, src, kind, where, **extra):
        return dict(id='c%d' % n, kind=kind, actor=PL + '%s_copy%d' % (src, n), **{'from': target(src)}, location=where,
                    rotation=[0, 0, 0], **extra)
    added = [a_copy(1, 'XComAlienPod_0', 'pod', at(12, 12, 17.0)), a_copy(2, 'XComAlienPod_2', 'pod', at(31, 31, 17.0), spawn=dict(use=False)),
             a_copy(3, 'XComMeldContainerSpawnPoint_1', 'meld', at(26, 6, 17.0), spawn=dict(difficulty='Hard', spawnGroup=0))]
    gone = [dict(target=target('XComAlienPod_2'), deleted=True), dict(target=target('XComAlienPod_1'), deleted=True),
            dict(target=target('XComSpawnPoint_Alien_3'), deleted=True)]
    case('copied and deleted, family off', copied, document(gone, added=added), family_off=True)
    case('copied and deleted', copied, document(gone, added=added))
    for k, rec in enumerate([a_copy(4, 'XComAlienPod_1', 'pod', at(12, 12, 17.0)),
                             a_copy(5, 'XComAlienPod_0', 'meld', at(12, 12, 17.0)),
                             a_copy(6, 'XComMeldContainerSpawnPoint_0', 'meld', at(12, 12, 17.0), spawn=dict(commander=True)),
                             a_copy(7, 'XComAlienPod_77', 'pod', at(12, 12, 17.0)),
                             dict(a_copy(8, 'XComAlienPod_0', 'pod', at(12, 12, 17.0)), id=''),
                             a_copy(9, 'XComSpawnPoint_Alien_3', 'dropIn', at(12, 12, 17.0)),
                             a_copy(10, 'XComAlienPod_0', 'pod', at(12, 12, 17.0), light=dict(radius=1)),
                             a_copy(11, 'XComAlienPod_0', 'pod', at(12, 12, 17.0), colour='red')]):
        case('copy refused or noted %d' % k, copied, document(added=[rec]), enable=['spawn'])
    unread = copy.deepcopy(copied)
    unread['spawns'][0]['unread'] = 'bad bytes'
    case('a delete of a point whose uses were not read', unread, document([dict(target=target('XComAlienPod_0'), deleted=True,
                                                                                 location=at(1, 1))]), enable=['spawn'])
    # no-spawn volumes sized, given values, copied, made and deleted, with the family off and on, and each refusal
    volumes = copy.deepcopy(s)
    volumes['spawns'].append(dict(actor=PL + 'XComNoSpawnVolume_0', actorClass='XComNoSpawnVolume', kind='noSpawn',
                                  location=[-384.0, -480.0, 96.0], rotation=[0, 0, 0], listed=True,
                                  box=dict(min=[-864.0, -576.0, 0.0], max=[-384.0, -384.0, 256.0]),
                                  values={'aliens': {'value': True, 'from': 'class'}, 'civilians': {'value': True, 'from': 'class'}}))
    volumes['spawns'].append(dict(actor=PL + 'XComNoSpawnVolume_2', actorClass='XComNoSpawnVolume', kind='noSpawn',
                                  location=[0.0, 0.0, 96.0], rotation=[0, 0, 0], listed=True,
                                  box=dict(min=[0.0, 0.0, 0.0], max=[192.0, 192.0, 256.0]), values={}))
    box = [-864.0, -576.0, 0.0, -192.0, -384.0, 320.0]
    edits = [dict(target=target('XComNoSpawnVolume_0'), box=box, spawn=dict(civilians=False, aliens=True)),
             dict(target=target('XComNoSpawnVolume_2'), deleted=True)]
    added = [dict(id='v1', kind='noSpawn', actor=PL + 'XComNoSpawnVolume_0_copy1', **{'from': target('XComNoSpawnVolume_0')},
                  box=[96.0, 96.0, 0.0, 288.0, 288.0, 256.0]),
             dict(id='v2', kind='noSpawn', actor=PL + 'XComNoSpawnVolume_copy2', box=[384.0, 384.0, 0.0, 672.0, 672.0, 256.0],
                  spawn=dict(aliens=False))]
    case('volumes, family off', volumes, document(edits, added=added), family_off=True)
    case('volumes', volumes, document(edits, added=added))
    for k, rec in enumerate([dict(target=target('XComNoSpawnVolume_0'), location=[0, 0, 0], rotation=[0, 0, 0]),
                             dict(target=target('XComAlienPod_0'), box=box),
                             dict(target=target('XComNoSpawnVolume_0'), box=[0, 0, 0, 0, 96, 64]),
                             dict(target=target('XComNoSpawnVolume_0'), box=[0, 0, 0, 96, 96]),
                             dict(target=target('XComNoSpawnVolume_0'), spawn=dict(use=True)),
                             dict(target=target('XComNoSpawnVolume_0'), spawn=dict(aliens='yes')),
                             dict(target=target('XComNoSpawnVolume_0'), box=[-864.0, -576.0, 0.0, -384.0, -384.0, 256.0])]):
        case('volume override refused or noted %d' % k, volumes, document([rec]), enable=['spawn'])
    for k, rec in enumerate([dict(added[1], location=[0, 0, 0], rotation=[0, 0, 0]),
                             dict(added[0], **{'from': target('XComAlienPod_0')}),
                             dict(added[1], box=[0, 0, 0, 96, 96]),
                             dict(added[1], colour='red'),
                             dict(added[1], id=None)]):
        case('volume copy refused or noted %d' % k, volumes, document(added=[rec]), enable=['spawn'])
    # a pod's place taken by a delete of the piece under it (SP5 reads the points as the edit leaves them)
    case('pod places against a delete', copied, document([dict(target=target('XComLevelActor_1'), deleted=True)],
                                                         added=[a_copy(1, 'XComAlienPod_0', 'pod', at(12, 12, 17.0))]))
    recorded = dict(base=s, scenes=scenes, cases=cases)
    for c in cases:
        c['expected'] = outcome(c['doc'], scene_of(recorded, c['scene']), c['enable'], c['familyOff'])
    return recorded


class SpawnEditFixtures(unittest.TestCase):
    def test_each_case_gives_what_was_recorded(self):
        recorded = json.loads(CASES.read_text(encoding='utf-8'))
        self.assertGreater(len(recorded['cases']), 30)
        for c in recorded['cases']:
            with self.subTest(c['name']):
                got = json.loads(json.dumps(outcome(c['doc'], scene_of(recorded, c['scene']), c['enable'], c['familyOff'])))
                self.assertEqual(got, c['expected'])


if __name__ == '__main__':
    if sys.argv[1:] == ['--write']:
        recorded = record()
        # (one line for the base scene, one for the scenes' changes, one for each case)
        compact = lambda v: json.dumps(v, separators=(',', ':'), sort_keys=True)  # noqa: E731
        lines = ['{"base": %s,' % compact(recorded['base']), ' "scenes": %s,' % compact(recorded['scenes']), ' "cases": [']
        lines += ['  %s%s' % (compact(c), ',' if k < len(recorded['cases']) - 1 else '') for k, c in enumerate(recorded['cases'])]
        with open(CASES, 'w', encoding='utf-8', newline='\n') as f:
            f.write('\n'.join(lines + [' ]}']) + '\n')
        print('%d cases written to %s' % (len(recorded['cases']), CASES.name))
    else:
        unittest.main()

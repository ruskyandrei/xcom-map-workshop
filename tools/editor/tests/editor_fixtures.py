"""The records and helpers the editor suite's tests share (review finding 58: a fixtures module per suite, rather than
tests that import other tests). Named for its suite, as file names are unique across the repository (the bake
suite's is fixtures.py). The records more than one suite shares come from their one home,
tools/tests/shared_fixtures.py.

- the compiler tests' small scene of Bar's pieces, with assemblies (scene, assembly_scene, part), a project
  document and its edits (document, target, add), and a compile's codes (refused, codes, left_out, warned, noted);
- the scene with a mission's stream and the base map's spawns (MissionScenes), which spawn_edit_cases.json was
  recorded from;
- a made wall's copy and its compile (made, compiled)."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'viewer'))
sys.path.insert(0, str(HERE.parents[1] / 'tests'))
from compiler import compile_project  # noqa: E402
from export_math import transform  # noqa: E402
from resolver import place  # noqa: E402
from shared_fixtures import record  # noqa: E402,F401  (the records every suite shares)

SHA = 'a' * 64
PL = 'TheWorld.PersistentLevel.'
# a donor map's SHA-256, for pieces of another map
DONOR_SHA = 'd' * 64


def part(name, cls='XComLevelActor', at=(0, 0, 0), rot=(0, 0, 0), layer='base', package='URB_Bar', **extra):
    obj = dict(id=name, actor=PL + name, component=PL + name + '.StaticMeshComponent_0', sourcePackage=package,
               layer=layer, actorClass=cls, mesh='m', materials=[], location=list(at), rotation=list(rot),
               scale=[1, 1, 1], hidden=False, floors=[], prefab=None, partner=None,
               componentTransform=transform([0, 0, 0], [0, 0, 0], [1, 1, 1]))
    obj.update(extra)
    place(obj, obj['location'], obj['rotation'], obj['scale'])
    return obj


def scene():
    objs = [part('XComLevelActor_1'), part('XComLevelActor_2', at=(96, 0, 0)),
            part('StaticMeshActor_3', cls='StaticMeshActor', at=(0, 96, 0), floors=[dict(building='7', floor=0, cutdownFloor=0)]),
            part('XComDestructibleActor_4', cls='XComDestructibleActor', at=(0, -96, 0)),
            part('XComLevelActor_5', at=(192, 0, 0), componentTransform=transform([0, 0, 16], [0, 0, 0], [1, 1, 1])),
            part('XComDestructibleActor_6', cls='XComDestructibleActor', at=(0, -300, 0), partner=PL + 'XComFracLevelActor_7'),
            part('XComFracLevelActor_7', cls='XComFracLevelActor', at=(0, -300, 0)),
            part('XComInteractiveLevelActor_8', cls='XComInteractiveLevelActor', at=(300, 0, 0)),
            part('XComCollectible_10', cls='XComCollectible', at=(0, -600, 0)),
            part('XComFracLevelActor_11', cls='XComFracLevelActor', at=(0, -900, 0)),
            part('XComLevelActor_1', layer='inherited', package='patch_bar', at=(500, 0, 0))]
    return dict(name='URB_Bar', source=dict(sha256=SHA), tileGrid=dict(origin=[-2783.9998, -1920.0, 0.0]),
                objects=objs, meshes={'m': dict(bounds=[0, 0, 50, 48, 48, 50, 100])}, materials={}, textures={},
                buildings=[], diagnostics=[], exporterVersion=18, lightMetadata=dict(version=1, areaMatcher=1), lights=[])


def assembly_scene():
    """The small scene with a ladder, a framed door, a frameless door, a car with a light bar, and a van (its own
    building lists its parts and a skid mark under it). Pieces stand on Bar's grid as Bar's do."""
    s = scene()
    s['meshes'].update({'ladder': dict(name='LadderMetal.Meshes.LadderMetalA_448',
                                       bounds=[33.1, 0, 237.4286, 14.9, 30.8, 237.4286, 239.7]),
                        'leaf': dict(name='Doors.Meshes.DoorSwingSingleD', bounds=[0, 0, 50, 48, 4, 50, 70]),
                        'frame': dict(name='Doors.Meshes.DoorSwingSingleD_Frame', bounds=[0, 0, 50, 48, 4, 50, 70]),
                        'ufo': dict(name='UFO.Meshes.UFODoor', bounds=[0, 0, 50, 48, 4, 50, 70])})
    s['objects'] += [
        part('XComLadder_20', cls='XComLadder', at=(432, 1296, 16), rot=(0, -16384, 0), mesh='ladder'),
        part('XComInteractiveLevelActor_21', cls='XComInteractiveLevelActor', at=(480, 144, 16), rot=(0, 16384, 0), mesh='leaf'),
        part('XComDestructibleActor_22', cls='XComDestructibleActor', at=(480, 144.4, 16), rot=(0, 16384, 0), mesh='frame'),
        part('XComInteractiveLevelActor_23', cls='XComInteractiveLevelActor', at=(-480, 144, 16), mesh='ufo'),
        part('XComDestructibleActor_24', cls='XComDestructibleActor', at=(-1240.36, -482.16, 0), rot=(0, -728, 0),
             prefab='PrefabInstance_41', partner=PL + 'XComFracLevelActor_25'),
        part('XComFracLevelActor_25', cls='XComFracLevelActor', at=(-1238.36, -482.3, 0), rot=(0, -728, 0), prefab='PrefabInstance_41'),
        part('XComDestructibleActor_26', cls='XComDestructibleActor', at=(-1241.79, -482.06, 0), rot=(0, -728, 0), prefab='PrefabInstance_41'),
        part('XComDestructibleActor_30', cls='XComDestructibleActor', at=(-1911.5, -1245.7, 0), rot=(0, 32768, 0),
             prefab='PrefabInstance_1', partner=PL + 'XComFracLevelActor_31'),
        part('XComFracLevelActor_31', cls='XComFracLevelActor', at=(-1911.5, -1245.7, 0), rot=(0, 32768, 0), prefab='PrefabInstance_1'),
        part('XComLevelActor_32', at=(-1916, -1248, 0), rot=(0, 32768, 0), prefab='PrefabInstance_1'),
        part('XComLevelActor_33', at=(-1916, -1248, 0), rot=(0, 32768, 0), prefab='PrefabInstance_1'),
        part('XComLevelActor_34', at=(-1900, -1240, 0)),
    ]
    floor = lambda *names: dict(members=[dict(actor=PL + n, cutdownFloor=0) for n in names])
    s['buildings'] = [dict(id='1', name=PL + 'XComBuildingVolume_1',
                           floors=[floor('XComLevelActor_32', 'XComLevelActor_34'), floor('XComLevelActor_33')]),
                      dict(id='2', name=PL + 'XComBuildingVolume_0', floors=[floor('XComLevelActor_1', 'XComLevelActor_2')])]
    # Bar's grid: floor on every tile of the ground, and roofs (level 6) up to x tile 40, as Bar's ladders climb to
    s['tileGrid'].update(dimensions=[52, 39, 12], size=[96, 96, 64])
    s['tactical'] = dict(floorTiles=[dict(tile=[x, y, z]) for z in (0, 6) for x in range(52 if z == 0 else 41) for y in range(39)])
    return s


def target(name, level='base', package='URB_Bar'):
    return dict(package=package, level=level, actor=PL + name)


def document(overrides=(), added=(), **changes):
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=1, id='5005037f-f7ac-4287-97f6-d1cab95360f9',
               name='Bar remix', mode='edit', revision=3,
               source=dict(map='URB_Bar', package='URB_Bar.upk', sha256=SHA, exporterVersion=12),
               output=dict(shipAs='URB_Bar_BarRemix_5005', patch='patch_urb_bar_barremix_5005'),
               overrides=list(overrides), added=list(added), nextSerial=len(added))
    doc.update(changes)
    return doc


def add(name, serial, at, rot=(0, 0, 0)):
    return {'id': '00000000-0000-4000-8000-%012d' % serial, 'actor': PL + '%s_copy%d' % (name, serial),
            'from': target(name), 'components': [PL + name + '.StaticMeshComponent_0'], 'location': list(at),
            'rotation': list(rot)}


def refused(report):
    """What a compile did not take: the document's errors (which stop the build) and the pieces left out of it."""
    return report['errors'] + report['leftOut']


def codes(report):
    return [d['code'] for d in refused(report)]


def left_out(report):
    """The codes of the pieces a compile left out, the build itself going on (no error of the document's)."""
    assert report['ok'] and not report['errors'], report['errors']
    assert report['counts']['leftOut'] == len(report['leftOut'])
    return [d['code'] for d in report['leftOut']]


def warned(report, prefix=''):
    return sorted(d['code'] for d in report['warnings'] if d['code'].startswith(prefix))


def noted(report, prefix=''):
    """The codes of a compile's notes: what can cause no problem in the game (compiler.note)."""
    return sorted(d['code'] for d in report['notes'] if d['code'].startswith(prefix))


class MissionScenes:
    """The compiler tests' scene with a data recovery stream's mission objects (mission_scene) and with the base map's
    pods and Meld points as well (spawn_scene): a base before unittest.TestCase, or made alone (MissionScenes())."""

    def mission_scene(self):
        """Bar's grid with a data recovery stream (export 24): the operative's point and a capture volume over the floor
        of XComLevelActor_1, a VIP's point where a copy will stand, a drop-in point, and a radar array elsewhere."""
        s = assembly_scene()
        ox, oy = s['tileGrid']['origin'][:2]
        at = lambda tx, ty, z=40.0: [ox + (tx + 0.5) * 96, oy + (ty + 0.5) * 96, z]  # noqa: E731
        s['tactical']['floorTiles'] = [dict(tile=[x, y, 0], **({'actor': PL + 'XComLevelActor_1'} if (x, y) == (10, 10) else {}))
                                       for x in range(52) for y in range(39)]
        obj = lambda actor, cls, kind, where, **more: dict(dict(actor=PL + actor, actorClass=cls, kind=kind, location=where, rotation=[0, 0, 0],  # noqa: E731
                                                           archetype=None, tag=None, unitType=None, box=None, referencedBy=[],
                                                           group=None, role=None), **more)
        c = at(10, 10, 0.0)
        s['missions'] = [dict(type='Abduction', label='Abduction', group='abduction', display='', streams=[]),
                         dict(type='CaptureAndHold', label='Data recovery', group='exalt', display='', streams=['URB_Bar_CNH'])]
        s['streams'] = {'URB_Bar_CNH': dict(kind='mission', objects=[], lights=[], missionObjects=[
            obj('XComSpawnPoint_0', 'XComSpawnPoint', 'operative', at(10, 10), unitType=10),
            obj('XComSpawnPoint_1', 'XComSpawnPoint', 'vip', at(20, 20), unitType=6),
            obj('XComSpawnPoint_Alien_0', 'XComSpawnPoint_Alien', 'dropIn', at(10, 10)),
            obj('XComRadarArrayActor_0', 'XComRadarArrayActor', 'radar', at(30, 30)),
            obj('XComCapturePointVolume_0', 'XComCapturePointVolume', 'capturePoint', c, group='capture:XComCapturePointVolume_0',
                role='volume', box=dict(min=[c[0] - 40, c[1] - 40, 0], max=[c[0] + 40, c[1] + 40, 128]))])}
        return s, at

    def spawn_scene(self):
        """mission_scene with the base map's pods and Meld points (export 33's `spawns`): three pods and a Meld group of
        a hard and an easy point; the first pod and the hard point stand on XComLevelActor_1's floor tile."""
        s, at = self.mission_scene()
        rec = lambda actor, cls, kind, where, **values: dict(  # noqa: E731
            actor=PL + actor, actorClass=cls, kind=kind, location=where, rotation=[0, 0, 0],
            values={k: {'value': v, 'from': 'saved'} for k, v in values.items()})
        s['spawns'] = [rec('XComAlienPod_0', 'XComAlienPod', 'pod', at(10, 10, 17.0), podIndex=0),
                       rec('XComAlienPod_1', 'XComAlienPod', 'pod', at(15, 15, 17.0), podIndex=1),
                       rec('XComAlienPod_2', 'XComAlienPod', 'pod', at(30, 30, 17.0), podIndex=2),
                       rec('XComMeldContainerSpawnPoint_0', 'XComMeldContainerSpawnPoint', 'meld', at(10, 10, 17.0),
                           difficulty='Hard', spawnGroup=0),
                       rec('XComMeldContainerSpawnPoint_1', 'XComMeldContainerSpawnPoint', 'meld', at(25, 5, 17.0),
                           difficulty='Easy', spawnGroup=0)]
        return s, at


def made(generated, name='XComFracLevelActor_11', serial=1, at=(0, 600, 0)):
    return dict(add(name, serial, at), generated=generated)


def compiled(added):
    spec, report = compile_project(document((), added, schemaVersion=2), scene())
    return spec, report

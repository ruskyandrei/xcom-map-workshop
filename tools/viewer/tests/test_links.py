"""Linked pieces: prefab instance members, and how previews keep copies apart from their originals."""
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from package import Package, Reader
from scene_metadata import fragment_breaks, kismet_references, prefab_members
from resolver import resolve_scene
from viewer_fixtures import scene
import settings

# URB_Bar from the LWR install (the lwr setting); without it the Kismet test skips
COOKED = settings.lwr_cooked()
BAR = COOKED / 'URB_Bar.upk' if COOKED else None
POLICE = COOKED / 'URB_PoliceStation.upk' if COOKED else None


class PrefabPackage:
    """Export 3 is a PrefabInstance whose archetype map names actors 1 and 2 (and an empty slot)."""
    def __init__(self,tail=b''):
        self.paths=['TheWorld.PersistentLevel.Body','TheWorld.PersistentLevel.Glass','TheWorld.PersistentLevel.PrefabInstance_7']
        self.blob=struct.pack('<i6i',3,-1,1,-2,2,-3,0)+struct.pack('<i',0)+tail
    def cls(self,index): return 'PrefabInstance' if index==3 else 'XComLevelActor'
    def native(self,index): return Reader(self.blob)
    def name(self,index): return self.paths[index-1] if index>0 else f'Import{-index}'


class LinkTests(unittest.TestCase):
    def test_prefab_instance_lists_its_actors(self):
        self.assertEqual(prefab_members(PrefabPackage()),{1:'PrefabInstance_7',2:'PrefabInstance_7'})

    def test_trailing_bytes_are_reported_not_guessed(self):
        notes=[]
        self.assertEqual(prefab_members(PrefabPackage(b'\0'),lambda *a:notes.append(a)),{})
        self.assertEqual(len(notes),1)

    def test_copies_link_only_to_copies_of_the_same_operation(self):
        base=scene();body=base['objects'][0]
        glass=dict(body,id='1:3',actor='TheWorld.PersistentLevel.Glass',partner=None,prefab='PrefabInstance_7')
        body.update(prefab='PrefabInstance_7',partner='TheWorld.PersistentLevel.Glass')
        base['objects'].append(glass)
        out=resolve_scene(base,dict(objects=[dict(type='copy',**{'from':['Piece','Glass']},location=[0,0,0]),
                                             dict(type='copy',**{'from':['Piece']},location=[500,0,0])]))
        first=[o for o in out['objects'] if o.get('provenance',{}).get('operation')==0]
        second=[o for o in out['objects'] if o.get('provenance',{}).get('operation')==1]
        self.assertEqual({o['prefab'] for o in first},{'copy0:PrefabInstance_7'})
        self.assertEqual(first[0]['partner'],'Preview.Glass_copy0')
        self.assertIsNone(second[0]['partner'])   # its glass was not copied
        self.assertEqual(out['objects'][0]['prefab'],'PrefabInstance_7')   # the original is untouched


@unittest.skipUnless(BAR and BAR.exists(), 'URB_Bar.upk of the LWR install (the lwr setting) not found')
class KismetTests(unittest.TestCase):
    def test_bars_kismet_names_its_grounded_skyranger_and_drop_zone(self):
        # export 15's referencedBy: the landing's SeqAct_ToggleHidden hides both, through its Target variables; no
        # ladder, door or car is named (plan section 2.4)
        p = Package(BAR)
        found = kismet_references(p)
        named = {p.name(a).rsplit('.', 1)[-1]: v for a, v in found.items()}
        self.assertEqual(named['XComLevelActor_138'], ['SeqAct_ToggleHidden_1 Target'])
        self.assertEqual(named['XComLevelActor_6'], ['SeqAct_ToggleHidden_1 Target'])
        self.assertFalse({p.cls(a) for a in found} & {'XComLadder', 'XComInteractiveLevelActor', 'XComFracLevelActor'})


@unittest.skipUnless(POLICE and POLICE.exists(), 'URB_PoliceStation.upk of the LWR install (the lwr setting) not found')
class BreaksTests(unittest.TestCase):
    def test_police_stations_car_glass_names_its_car_and_its_standalone_light_bar(self):
        # export 16's breaks (plan sections 2.3 and 3.3): the glass's fragment columns name the body and its parts; a
        # sedan's standalone police light bar, which no prefab places with it, only there; and on car 1054 a fence
        p = Package(POLICE)
        PL = 'TheWorld.PersistentLevel.'
        glass = {n: p.by_name[PL + n] for n in ('XComFracLevelActor_192', 'XComFracLevelActor_191', 'XComFracLevelActor_198')}
        found = fragment_breaks(p, glass.values())
        named = {n: [p.name(v).rsplit('.', 1)[-1] for v in found[i]] for n, i in glass.items()}
        self.assertEqual(named['XComFracLevelActor_192'], ['XComDestructibleActor_1056', 'XComDestructibleActor_1057',
                                                           'XComDestructibleActor_1058', 'XComDestructibleActor_468'])
        self.assertIn('XComDestructibleActor_72', named['XComFracLevelActor_191'])
        self.assertEqual(named['XComFracLevelActor_198'], ['XComDestructibleActor_1070', 'XComDestructibleActor_1071'])


if __name__=='__main__':unittest.main()

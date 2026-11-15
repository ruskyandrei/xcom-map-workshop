from pathlib import Path
import copy
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from export_math import transform,view_matrix
from resolver import resolve_scene,snap,place


def scene():
    obj=dict(id='1:2',actor='TheWorld.PersistentLevel.Piece',actorClass='XComLevelActor',mesh='m',
             materials=[],location=[10,0,0],rotation=[0,0,0],scale=[1,1,1],hidden=False,floors=[],
             componentTransform=transform([0,0,0],[0,0,0],[1,1,1]))
    place(obj,obj['location'],obj['rotation'],obj['scale'])
    return dict(objects=[obj],meshes={'m':dict(bounds=[0,0,0,1,1,1,2])},materials={},textures={},
                buildings=[],diagnostics=[])


class ResolverTests(unittest.TestCase):
    def test_copy_scale_changes_size_not_spacing(self):
        base=scene();before=copy.deepcopy(base)
        out=resolve_scene(base,dict(objects=[dict(type='copy',**{'from':['Piece']},pivot=[0,0,0],
            location=[100,0,0],yaw=90,extra=['CopyScale=(X=2,Y=3,Z=1)'])]))
        obj=out['objects'][-1]
        self.assertAlmostEqual(obj['location'][0],100)
        self.assertAlmostEqual(obj['location'][1],10)
        self.assertEqual(obj['scale'],[2,3,1])
        self.assertEqual(base,before)

    def test_hider_skips_new_copies(self):
        out=resolve_scene(scene(),dict(objects=[dict(type='copy',**{'from':['Piece']},pivot=[0,0,0],location=[0,0,0]),
            dict(type='hide',location=[10,0,0],half=[20,20,20],extra=['KeepGroundHeight=0'])]))
        self.assertTrue(out['objects'][0]['hidden'])
        self.assertFalse(out['objects'][1]['hidden'])

    def test_keep_precedes_explicit_hide(self):
        out=resolve_scene(scene(),dict(objects=[dict(type='hide',location=[10,0,0],half=[20,20,20],
            keep=['Piece'],alsoHide=['Piece'])]))
        self.assertFalse(out['objects'][0]['hidden'])

    def test_missing_sources_and_inherited_patch_are_reported(self):
        out=resolve_scene(scene(),dict(base='patch_bar',objects=[dict(type='copy',**{'from':['Missing']})]))
        self.assertEqual(len(out['preview']['notes']),2)
        self.assertFalse(out['preview']['gameVerified'])

    # The preview follows the builder (first-editor plan, section 6, item 8; editor contracts, "What E0 still lacks").
    def test_defaults_are_patchtools(self):
        base=scene()
        far=copy.deepcopy(base['objects'][0]);far['actor']='TheWorld.PersistentLevel.Far'
        place(far,[400,0,10],[0,0,0],[1,1,1]);base['objects'].append(far)
        # A hide's half-size is 512 by default, as patchtool's, not 128.
        out=resolve_scene(base,dict(objects=[dict(type='hide',location=[0,0,0],extra=['KeepGroundHeight=0'])]))
        self.assertTrue(all(o['hidden'] for o in out['objects']))
        # A location without z stands at patchtool's groundZ, not 0.
        out=resolve_scene(scene(),dict(objects=[dict(type='copy',**{'from':['Piece']},pivot=[10,0,0],location=[50,0])]))
        self.assertAlmostEqual(out['objects'][-1]['location'][2],3.999993)

    def test_copies_the_builder_refuses_are_reported_not_drawn(self):
        out=resolve_scene(scene(),dict(objects=[dict(type='copy',**{'from':['Piece']},pivot=[0,0,0],location=[0,0,0],yaw=45)]))
        self.assertEqual(len(out['objects']),1)
        self.assertIn('multiples of 90',out['preview']['notes'][0]['message'])
        base=scene();base['objects'][0]['actorClass']='KAsset'
        out=resolve_scene(base,dict(objects=[dict(type='copy',**{'from':['Piece']},pivot=[0,0,0],location=[0,0,0])]))
        self.assertEqual(len(out['objects']),1)
        self.assertIn("can't copy",out['preview']['notes'][0]['message'])

    def test_a_moved_door_keeps_its_scale_and_building_floor_minus_one_keeps_the_sources(self):
        base=scene();base['objects'][0]['actorClass']='XComInteractiveLevelActor'
        base['objects'][0]['floors']=[dict(building='7',floor=1,cutdownFloor=1)]
        out=resolve_scene(base,dict(objects=[dict(type='copy',**{'from':['Piece']},pivot=[0,0,0],location=[0,0,0],
            building=dict(floors=[['V']]),extra=['CopyScale=(X=2,Y=2,Z=2)','BuildingFloor=-1'])]))
        door=out['objects'][0]
        self.assertTrue(door['moved'])
        self.assertEqual(door['scale'],[1,1,1])
        self.assertEqual(door['floors'],[dict(building='copy-0',floor=1,cutdownFloor=1)])

    def test_absolute_poses_and_exact_hides(self):
        base=scene()
        out=resolve_scene(base,dict(objects=[
            dict(type='copy',**{'from':['Piece','Piece']},location=[0,0,0],labels=['a','b'],
                 poses=[dict(location=[1,2,3],rotation=[16384,0,0]),dict(location=[4,5,6],rotation=[0,0,8192])]),
            dict(type='hide',exact=True,location=[0,0,0],alsoHide=['Piece','Gone'])]))
        a,b=out['objects'][1:]
        self.assertEqual((a['actor'],a['location'],a['rotation']),('Preview.a',[1,2,3],[16384,0,0]))
        self.assertEqual(b['matrix'],view_matrix(transform([4,5,6],[0,0,8192],[1,1,1])))
        self.assertTrue(out['objects'][0]['hidden']);self.assertFalse(a['hidden'])
        self.assertEqual([n['message'] for n in out['preview']['notes']],['No base-map actor Gone to hide'])
        base['objects'][0]['actorClass']='XComLadder'
        out=resolve_scene(base,dict(objects=[dict(type='copy',**{'from':['Piece']},location=[0,0,0],
            poses=[dict(location=[0,0,0],rotation=[0,0,0])])]))
        self.assertEqual(len(out['objects']),1)
        self.assertIn('absolute pose',out['preview']['notes'][0]['message'])

    def test_snap_uses_footprint_parity(self):
        base=scene();obj=base['objects'][0];base['meshes']['m']['bounds']=[0,0,0,144,96,1,200]
        place(obj,[10,13,0],[0,0,0],[1,1,1])
        self.assertEqual(snap([obj],base['meshes'],[0,0],0),[38,-13,0])
        self.assertIsNone(snap([obj],base['meshes'],[0,0],45))


if __name__=='__main__':unittest.main()

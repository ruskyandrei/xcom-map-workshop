import copy
import unittest
from viewer_fixtures import scene
from composition import compose_scene
from resolver import resolve_scene


class CompositionTests(unittest.TestCase):
    def layer(self):
        layer=scene();layer['name']='patch_bar';layer['source']={'file':'patch_bar.upk','sha256':'test'}
        obj=layer['objects'][0];obj['id']='patch-1:2';obj['hidden']=True;obj['sourcePackage']='patch_bar'
        layer['content']=[dict(actorClass='XComRebuildWorldDataVolume',path='Rebuild')]
        return layer

    def test_hidden_layer_and_records_preserved(self):
        base=scene();before=copy.deepcopy(base);out=compose_scene(base,[self.layer()])
        self.assertEqual(len(out['objects']),2);self.assertTrue(out['objects'][1]['hidden'])
        self.assertEqual(out['inheritedPatches'][0]['hiddenComponents'],1)
        self.assertEqual(out['inheritedPatches'][0]['records'][0]['actorClass'],'XComRebuildWorldDataVolume')
        self.assertEqual(base,before)

    def test_source_name_collision_does_not_copy_patch_actor(self):
        base=compose_scene(scene(),[self.layer()])
        out=resolve_scene(base,dict(base='patch_bar',objects=[dict(type='copy',**{'from':['Piece']},location=[0,0,0])]))
        copies=[o for o in out['objects'] if o.get('provenance')]
        self.assertEqual(len(copies),1)
        self.assertEqual(out['preview']['notes'],[])

    def test_duplicate_identity_is_rejected(self):
        layer=self.layer();layer['objects'][0]['id']='1:2'
        with self.assertRaisesRegex(ValueError,'Duplicate'):compose_scene(scene(),[layer])

    def test_explicit_hider_name_matches_both_level_namespaces(self):
        base=compose_scene(scene(),[self.layer()])
        out=resolve_scene(base,dict(objects=[dict(type='hide',alsoHide=['Piece'])]))
        self.assertTrue(all(o['hidden'] for o in out['objects']))
        self.assertEqual([o['hiddenBy'] for o in out['objects']],[0,0])


if __name__=='__main__':unittest.main()

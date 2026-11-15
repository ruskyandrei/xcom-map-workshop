from pathlib import Path
import copy
import struct
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from package import Reader
from export_math import transform,view_matrix
from scene_metadata import tactical_metadata


def store(kind, height=0):
    data=struct.pack('<6i',1,1,0,1,1,1)+struct.pack('<6i',0,1 if kind=='floor' else 0,0,0,0,18)
    for i in range(18):
        if kind=='floor':
            data+=struct.pack('<6fIBiiB',47,47,height,0,0,1,0,253,3,0,int(i==0))
        else:data+=struct.pack('<IB',0,0)
    return data


class TacticalTests(unittest.TestCase):
    def package(self,height=0):
        blob=store('flags')+store('flags')+store('floor',height)
        class P:
            exports=[{}]
            def cls(self,i):return 'XComWorldDataContainer'
            def native(self,i):return Reader(blob)
            def name(self,i):return 'Floor' if i==3 else 'Container'
        return P(),blob

    def test_source_layers_and_floor_bounds_are_reversible_view_metadata(self):
        p,_=self.package()
        grid=dict(origin=[0,0,-32],dimensions=[1,1,1],size=[96,96,64])
        def obj(layer,x=0):return dict(mesh='m',editorLayers=layer,matrix=view_matrix(transform([x,0,0],[0,0,0],[1,1,1])))
        objects=[obj([]),obj(['Periphery']),obj(['hallway roofs']),obj(['HiddenWalls']),obj([],1000)]
        before=copy.deepcopy(objects);notes=[]
        result=tactical_metadata(p,objects,{'m':dict(bounds=[0,0,0,1,1,1,2])},grid,lambda *v:notes.append(v))
        self.assertEqual(result['floorTiles'][0]['location'],[47,47,0])
        self.assertEqual(result['floorTiles'][0]['actor'],'Floor')
        self.assertEqual(result['focusBounds'],dict(min=[-1,-32,-1],max=[95,192,95]))
        self.assertEqual(result['recommendedView'],'interior')
        self.assertEqual([o['sceneryRole'] for o in objects],['interior','backdrop','roof','helper','backdrop'])
        for old,new in zip(before,objects):self.assertEqual(new,{**old,'sceneryRole':new['sceneryRole']})
        self.assertEqual(notes,[])

    def test_invalid_floor_data_is_diagnosed(self):
        p,blob=self.package();p.native=lambda i:Reader(blob[:-1]);notes=[]
        grid=dict(origin=[0,0,0],dimensions=[1,1,1],size=[96,96,64])
        self.assertIsNone(tactical_metadata(p,[],{},grid,lambda *v:notes.append(v)))
        self.assertEqual(len(notes),1)
        p,_=self.package(float('nan'));notes=[]
        self.assertIsNone(tactical_metadata(p,[],{},grid,lambda *v:notes.append(v)))
        self.assertIn('Nonfinite',notes[0][1])


if __name__=='__main__':unittest.main()

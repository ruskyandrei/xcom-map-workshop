from pathlib import Path
import sys
import unittest
import struct
import tempfile
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from materials import profile, static_switches, constant_color
from scene_metadata import building_metadata, cursor_volumes, tile_grid
from package import Reader, FormatError
from export import Exporter
from PIL import Image


class MaterialTests(unittest.TestCase):
    def test_roof_destruction_does_not_cut_diffuse_alpha(self):
        out = profile(['GEN_MaterialParents.Master_Materials.BLDG_Floors'],
                      'BLEND_Masked',{'Diffuse_Base':7},{},{})
        self.assertEqual(out['opacitySource'],'intact-destruction')

    def test_foliage_keeps_diffuse_cutout(self):
        out = profile(['FoliageLeaf'],'BLEND_Masked',{'Diffuse':5},{},{})
        self.assertEqual(out['opacitySource'],'diffuse-alpha')

    def test_obsolete_sidewalk_family_uses_actual_parameter_name(self):
        out=profile(['RoadAndSidewalk_Material'],'BLEND_Opaque',{'DiffuseMap':19},{},{})
        self.assertEqual(out['diffuseParameter'],'DiffuseMap')

    def test_building_uv_channel_and_tiling(self):
        out = profile(['BLDG_Enterable'],'BLEND_Opaque',{'Diffuse_Base':7},
                      {'TileXY':1.25},{'Diffuse_Base':{'channel':1,'scale':[2,3]}})
        self.assertEqual(out['uv'],{'channel':1,'scale':[2.5,3.75]})

    def test_alien_opacity_uses_own_switch_and_packed_texture(self):
        args = (['GEN.ALIEN_Base'], 'BLEND_Masked', {'Diffuse':1,'Spc_Ems_Ref_Opc':2}, {}, {})
        self.assertEqual(profile(*args, {'OpacityMasked':False})['opacitySource'], 'opaque')
        masked = profile(*args, {'OpacityMasked':True})
        self.assertEqual(masked['opacitySource'], 'packed-alpha')
        self.assertEqual(masked['opacityParameter'], 'Spc_Ems_Ref_Opc')
        self.assertEqual(masked['emissiveParameter'], 'Spc_Ems_Ref_Opc')
        self.assertEqual(profile(['GEN.ALIEN_DoorEnergy_Opaque'],'BLEND_Masked',{}, {}, {})['opacitySource'], 'opaque')

    def test_channel_images_are_linear_and_keep_source_provenance(self):
        with tempfile.TemporaryDirectory() as folder:
            exporter=Exporter(None,Path(folder))
            Image.new('RGBA',(1,1),(19,71,139,203)).save(Path(folder)/'source.png')
            exporter.textures['7']=dict(url='source.png',srgb=True,sourceRangeSha256='source-hash')
            key=exporter.texture_channel(7,'G')
            self.assertEqual(Image.open(Path(folder)/exporter.textures[key]['url']).getpixel((0,0)),(71,71,71))
            self.assertFalse(exporter.textures[key]['srgb'])
            self.assertEqual(exporter.textures[key]['derivedFrom'],'7')
            self.assertEqual(exporter.textures[key]['sourceRangeSha256'],'source-hash')
            alpha=exporter.texture_channel(7,'A')
            self.assertEqual(Image.open(Path(folder)/exporter.textures[alpha]['url']).getpixel((0,0)),(203,203,203))
            rgb=exporter.texture_channel(7,'RGB')
            self.assertEqual(Image.open(Path(folder)/exporter.textures[rgb]['url']).convert('RGBA').getpixel((0,0)),(19,71,139,255))

    def test_constant_families_do_not_override_unrelated_materials(self):
        class P:
            def name(self,i):return self.material
        p=P();p.material='HQ_FundingCouncil.Materials.UnlitBlack'
        self.assertEqual(constant_color(p,1),([0,0,0],True))
        p.material='jeremy_dev.M_SimpleGrey'
        self.assertAlmostEqual(constant_color(p,1)[0][0],(128/255)**2.2)
        p.material='AnotherPackage.Materials.UnlitBlack'
        self.assertEqual(constant_color(p,1),(None,False))


class StaticSwitchTests(unittest.TestCase):
    def package(self, switches, licensee=64):
        # Empty FMaterial arrays, then EW extra data and a parameter set.
        raw=struct.pack('<3i',0,0,0)+bytes(16)+struct.pack('<8i',0,0,0,0,0,0,0,0)+struct.pack('<2i',0,0)
        if licensee == 64: raw+=bytes(16)+struct.pack('<2i',0,0)
        raw+=bytes(16)+struct.pack('<i',len(switches))
        for i,(value,override) in enumerate(switches):raw+=struct.pack('<4i',i,0,value,override)+bytes(16)
        class P:
            header={'lic':licensee}
            def own(self,*args):return True
            def native(self,*args):return Reader(raw)
            def fname(self,r):
                i,number=r.unpack('2i');return f'Switch{i}'
        return P(),raw

    def test_only_own_overrides_replace_inherited_values(self):
        for licensee in (0,64):
            p,_=self.package([(1,0),(0,1),(1,1)],licensee)
            self.assertEqual(static_switches(p,1),{'Switch1':False,'Switch2':True})

    def test_truncated_and_invalid_switches_are_rejected(self):
        p,raw=self.package([(1,1)]);p.native=lambda _:Reader(raw[:-1])
        with self.assertRaises(FormatError):static_switches(p,1)
        p,_=self.package([(2,1)])
        with self.assertRaises(FormatError):static_switches(p,1)


def item(value): return {'value':value}


class FloorTests(unittest.TestCase):
    def test_cursor_volumes_by_floor_with_their_boxes(self):
        class P:
            paths=['TheWorld.PersistentLevel.XComCursorVolume_1','TheWorld.PersistentLevel.XComCursorVolume_0',
                   'TheWorld.PersistentLevel.XComLevelActor_0','Other.XComCursorVolume_9']
            def cls(self,i): return 'XComLevelActor' if i==3 else 'XComCursorVolume'
            def effective(self,i,key,default=None):
                return {'m_iFloorNumber':{1:2,2:1,4:5},'m_bTreatAsStair':{1:True}}[key].get(i,default)
        boxes={1:{'min':[0,0,210],'max':[9,9,402]},2:{'min':[0,0,0],'max':[9,9,210]}}
        with patch('scene_metadata.volume_bounds',side_effect=lambda p,i:boxes[i]):
            result=cursor_volumes(P())
        self.assertEqual(result,[dict(name=P.paths[1],floor=1,box=boxes[2],stair=False),
                                 dict(name=P.paths[0],floor=2,box=boxes[1],stair=True)])

    def test_display_grid_uses_map_dimensions_and_validates_extent(self):
        class P:
            exports=[{}]
            def cls(self,i):return 'XComWorldDataContainer'
            def native(self,i):return Reader(struct.pack('<5i',0,0,45,203,15))
            def name(self,i):return 'WorldData'
        bounds=dict(min=[100,-384,-9408],max=[4420,576,10080])
        notes=[]
        grid=tile_grid(P(),bounds,lambda *v:notes.append(v))
        self.assertEqual(grid['dimensions'],[45,203,15])
        self.assertEqual(grid['origin'],[100,-9408,-384])
        # a box a unit or so short on the far side keeps its grid (CSmallScout_Roadhouse: 5471 wide for 57 tiles)
        bounds['max'][0]-=1.004
        self.assertEqual(tile_grid(P(),bounds,lambda *v:notes.append(v))['origin'],[100,-9408,-384])
        self.assertEqual(notes,[])
        bounds['max'][0]+=1.004+96
        self.assertIsNone(tile_grid(P(),bounds,lambda *v:notes.append(v)))
        self.assertEqual(len(notes),1)

    def test_only_source_cache_membership_is_used(self):
        class P:
            paths=['TheWorld.PersistentLevel.Building','TheWorld.PersistentLevel.Roof','TheWorld.PersistentLevel.Other']
            def cls(self,i): return 'XComBuildingVolume' if i==1 else 'XComLevelActor'
            def name(self,i): return self.paths[i-1] if i<=len(self.paths) else f'FloorVolume_{i}'
            def effective(self,i,key,default=None):
                if key=='IsUfo': return True
                return [{('FloorVolumes',0):item([10]),('m_aCachedActors',0):item([])},
                        {('FloorVolumes',0):item([11]),('m_aCachedActors',0):item([
                            {('ResidentActor',0):item(2),('CutdownFloor',0):item(2)}])}]
            def refs(self,value): return value
            def structs(self,value): return value
        objects=[{'actor':P.paths[1]},{'actor':P.paths[2]}]
        with patch('scene_metadata.volume_bounds',return_value={'min':[0,0,210],'max':[1,1,402]}), \
             patch('scene_metadata.plain_box',side_effect=lambda p,r: r==10):
            result=building_metadata(P(),objects,{11:['SeqAct_Toggle_0 Target']})
        # export 21: the building's actor, level, flags, the Kismet naming it or its floor volumes, plain boxes
        self.assertEqual((result[0]['actor'],result[0]['level'],result[0]['isUfo']),('Building','PersistentLevel',True))
        self.assertEqual(result[0]['referencedBy'],['SeqAct_Toggle_0 Target'])
        self.assertEqual([f['plain'] for f in result[0]['floors']],[[True],[False]])
        self.assertEqual(objects[0]['floors'],[{'building':'1','floor':1,'cutdownFloor':2}])
        self.assertEqual(objects[1]['floors'],[])
        self.assertEqual(result[0]['floors'][1]['top'],402)
        # export 15: each floor's volume boxes, for a copy's floor
        self.assertEqual(result[0]['floors'][1]['boxes'],[{'min':[0,0,210],'max':[1,1,402]}])


if __name__=='__main__': unittest.main()

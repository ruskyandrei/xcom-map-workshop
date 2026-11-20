"""Light records, the dominant-light component layout and the resolver's light rules."""
import json
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from package import Package
from lights import effective_cone, effective_cone_degrees, light_metadata, light_record, light_records, storable_cone, sun_records
from resolver import resolve_scene
from scene_metadata import kismet_references
from test_resolver import scene
import settings

# URB_Bar from the game install (the game setting); without it the package tests skip
COOKED=settings.lwr_cooked()
BAR=COOKED/'URB_Bar.upk' if COOKED else None


class LightPackage:
    """Exports 1 (actor) and 2 (its component) with the given own properties."""
    def __init__(self,actor_class,component_class,actor=None,component=None):
        self.path=Path('Synthetic.upk');self.classes={1:actor_class,2:component_class}
        self.values={1:{'LightComponent':2,**(actor or {})},2:component or {}}
    def own(self,index,key,default=None): return self.values[index].get(key,default)
    effective=own
    def cls(self,index): return self.classes[index]
    def name(self,index): return f'TheWorld.PersistentLevel.{self.classes[index]}_0'


def light(name,location,kind='point',**extra):
    return dict(id=name,actor=f'TheWorld.PersistentLevel.{name}',layer='base',kind=kind,location=location,
                enabled=True,**extra)


class LightRecordTests(unittest.TestCase):
    def test_unset_values_take_engine_defaults(self):
        record=light_record(LightPackage('SpotLight','SpotLightComponent',dict(Location=[1,2,3])),1)
        self.assertEqual((record['kind'],record['role']),('spot','static'))
        self.assertEqual((record['radius'],record['falloffExponent']),(1024.0,2.0))
        self.assertEqual((record['innerConeAngle'],record['outerConeAngle']),(0.0,44.0))
        self.assertEqual((record['brightness'],record['color']),(1.0,[1.0,1.0,1.0]))
        # SpotLight's class default rotation points straight down.
        for got,want in zip(record['direction'],[0,0,-1]):self.assertAlmostEqual(got,want)

    def test_own_values_and_sky_hemisphere(self):
        p=LightPackage('SkyLight','SkyLightComponent',component=dict(Brightness=0.75,LightColor=[0.3,0.4,0.6,0],
                       LowerBrightness=0.01,LowerColor=[1,0.8,0.6,0]))
        record=light_record(p,1)
        self.assertEqual((record['kind'],record['brightness'],record['color']),('sky',0.75,[0.3,0.4,0.6]))
        self.assertEqual((record['lowerBrightness'],record['lowerColor']),(0.01,[1,0.8,0.6]))
        self.assertFalse(record['castShadows'])

    def test_area_lights_keep_their_role(self):
        record=light_record(LightPackage('GeneratedMeshAreaLight','SpotLightComponent',dict(Rotation=[0,16384,0])),1)
        self.assertEqual(record['role'],'area')
        for got,want in zip(record['direction'],[0,1,0]):self.assertAlmostEqual(got,want)

    def test_unsupported_component_offset_is_rejected(self):
        p=LightPackage('PointLight','PointLightComponent',component=dict(Translation=[0,0,10]))
        with self.assertRaisesRegex(ValueError,'Translation'):light_record(p,1)


class DominantComponentTests(unittest.TestCase):
    def test_properties_follow_the_leading_shadow_map(self):
        names=['None','Brightness','FloatProperty','DominantDirectionalLightComponent']
        words=[7,8,9]
        # Shadow map, then NetIndex and TemplateOwnerClass (an import), then the tagged properties.
        body=(struct.pack('<i',len(words))+struct.pack(f'<{len(words)}H',*words)+struct.pack('<2i',0,-1)+
              struct.pack('<4i',1,0,2,0)+struct.pack('<ii',4,0)+struct.pack('<f',1.1)+struct.pack('<2i',0,0))
        p=Package.__new__(Package)
        p.data,p.names=body,names
        p.imports=[dict(name='DominantDirectionalLightComponent',outer=0)]
        p.exports=[dict(name='Sun',outer=0,cls=-1,arch=0,off=0,size=len(body),flags=0)]
        values,_=p.properties(1)
        self.assertAlmostEqual(values[('Brightness',0)]['value'],1.1,places=5)


class ResolverLightTests(unittest.TestCase):
    def lit(self):
        base=scene()
        base['lights']=[light('PointLight_0',[10,0,0]),light('PointLight_1',[500,0,0]),
                        light('SkyLight_0',[0,0,0],kind='sky')]
        return base

    def test_hider_takes_lights_only_with_bhidelights(self):
        hide=dict(type='hide',location=[0,0,0],half=[100,100,100])
        out=resolve_scene(self.lit(),dict(objects=[hide]))
        self.assertTrue(all(l['enabled'] for l in out['lights']))
        out=resolve_scene(self.lit(),dict(objects=[dict(hide,extra=['bHideLights=True'],alsoHide=['PointLight_1'])]))
        self.assertEqual([l['enabled'] for l in out['lights']],[False,False,False])
        self.assertEqual(out['lights'][0]['hiddenBy'],0)

    def test_keep_protects_a_light(self):
        out=resolve_scene(self.lit(),dict(objects=[dict(type='hide',location=[0,0,0],half=[100,100,100],
                                                    keep=['PointLight_0'],extra=['bHideLights=True'])]))
        self.assertTrue(out['lights'][0]['enabled'])

    def test_sun_object_survives_a_later_hider(self):
        out=resolve_scene(self.lit(),dict(objects=[dict(type='sun',sun=1.2,sky=0.5,yaw=138,pitch=50),
            dict(type='hide',location=[0,0,0],half=[5000,5000,5000],extra=['bHideLights=True'])]))
        patch=[l for l in out['lights'] if l['layer']=='patch']
        self.assertEqual([(l['kind'],l['brightness'],l['enabled']) for l in patch],
                         [('directional',1.2,True),('sky',0.5,True)])
        self.assertTrue(all(not l['enabled'] for l in out['lights'] if l['layer']=='base'))
        self.assertEqual(out['preview']['notes'],[])

    def test_photo_defaults_match_the_sun_object(self):
        photo=sun_records('photo',1.2,0.5,138,50)
        out=resolve_scene(scene(),dict(objects=[dict(type='photo')]))
        self.assertEqual([l['direction'] for l in out['lights']],[l['direction'] for l in photo])
        self.assertLess(photo[0]['direction'][2],0)   # pitch 50 degrees down


CONES=json.loads((Path(__file__).with_name('cone_cases.json')).read_text(encoding='utf-8'))['cases']


class EffectiveConeTests(unittest.TestCase):
    """lights.effective_cone and its twin light_rules.js effectiveCone, against the shared cases (plan 9.2)."""
    def test_python_matches_the_cases(self):
        for case in CONES:
            got=effective_cone(case['inner'],case['outer'])
            for g,want in zip(got,case['effective']):self.assertAlmostEqual(g,want,places=10,msg=case['why'])

    def test_stored_wide_cones_bake_as_clamped(self):
        # the codec's spot term uses the effective cone: a stored 580 lights as 89.99
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'bake'))
        import numpy as np
        import lightmap_encode as codec
        frames=np.tile(np.eye(3),(1,1,1))
        light=dict(kind='spot',location=[0,0,100],direction=[0,0,-1],radius=1000,falloffExponent=2,brightness=1,
                   color=[1,1,1],innerConeAngle=0,outerConeAngle=580)
        clamped=dict(light,outerConeAngle=89.99)
        world=np.array([[50.0,0,0]])
        self.assertTrue(np.allclose(codec.light_contribution(light,world,frames),codec.light_contribution(clamped,world,frames)))

    def test_javascript_matches_the_cases(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest('Playwright is not installed')
        source=(Path(__file__).resolve().parents[1]/'web'/'light_rules.js').read_text(encoding='utf-8').replace('export function','function').replace('export const','const')
        # the module's functions, evaluated in a page with the cases as the argument
        script='cases => {%s; return cases.map(c => effectiveCone(c.inner, c.outer)); }' % source
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel="msedge",headless=True)
            try:
                got=browser.new_page().evaluate(script,CONES)
            finally:
                browser.close()
        for case,pair in zip(CONES,got):
            for g,want in zip(pair,case['effective']):self.assertAlmostEqual(g,want,places=10,msg=case['why'])


# (stored inner, stored outer) -> the cone a made light holds: in range kept as stored, else the effective cone
STORABLE=[((0,44),(0,44)),((40,54.96),(40,54.96)),((30,30),(30,30)),((0,89.99),(0,89.99)),
          ((0,100),(0,89.99)),((0,580),(0,89.99)),((39.9995,189.999),(39.9995,89.99)),((95,100),(89,89.99)),
          ((50,30),(50,50.0573)),((-5,20),(0,20))]


class StorableConeTests(unittest.TestCase):
    """lights.storable_cone and its twin light_rules.js storableCone: a prefab's light copied from a map light with a
    stored cone wider than the editor's ranges (the Small Landed UFO's blue spots: 100) holds the cone it lights as."""
    def check(self,got):
        for ((inner,outer),want),cone in zip(STORABLE,got):
            for g,w in zip(cone,want):self.assertAlmostEqual(g,w,places=4,msg=(inner,outer))
            i,o=cone
            self.assertTrue(0<=i<=89 and i<=o<=89.99,(inner,outer,cone))     # what the compiler takes
            for g,w in zip(effective_cone_degrees(i,o),effective_cone_degrees(inner,outer)):
                self.assertAlmostEqual(g,w,delta=0.01,msg=(inner,outer))      # and it lights as before

    def test_python(self):
        self.check([storable_cone(i,o) for (i,o),_ in STORABLE])
        self.assertEqual(storable_cone(0,80),(0,80))                          # in range: the very values

    def test_javascript_matches(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest('Playwright is not installed')
        source=(Path(__file__).resolve().parents[1]/'web'/'light_rules.js').read_text(encoding='utf-8').replace('export function','function').replace('export const','const')
        script='cases => {%s; return cases.map(([i, o]) => storableCone(i, o)); }' % source
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel="msedge",headless=True)
            try:
                got=browser.new_page().evaluate(script,[list(c) for c,_ in STORABLE])
            finally:
                browser.close()
        self.check(got)


@unittest.skipUnless(BAR and BAR.exists(),'URB_Bar.upk of the game install (the game setting) not found')
class LightMetadataTests(unittest.TestCase):
    """Export 18's light fields on the bar (editor lights plan 4.1, 9.3)."""
    @classmethod
    def setUpClass(cls):
        p=cls.p=Package(BAR)
        level='TheWorld.PersistentLevel.'
        actors=[i for i,n in enumerate(p.paths,1) if n.startswith(level) and n.count('.')==2 and '.Default__' not in n]
        objects=[]
        for a in actors:
            for c in p.children.get(a,[]):
                if 'StaticMeshComponent' in p.cls(c):
                    objects.append(dict(id=f'{a}:{c}',actor=p.name(a),component=p.name(c)))
        cls.lights=light_metadata(p,light_records(p,actors),objects,kismet_references(p))
        cls.by_actor={l['actor'].rsplit('.',1)[-1]:l for l in cls.lights}

    def test_every_placed_light_is_in_a_lightmap(self):
        placed=[l for l in self.lights if l['role']=='static' and l['kind'] in ('point','spot')]
        self.assertEqual(len(placed),116)
        self.assertTrue(all(l['bakedInto'] for l in placed))
        # area lights are in no lightmap (Lightmass bakes the glow onto the surfaces directly)
        self.assertFalse(any(l['bakedInto'] for l in self.lights if l['role']=='area'))

    def test_guids_read_back(self):
        lamp=self.by_actor['SpotLight_53']
        c=self.p.by_name[lamp['component']]
        self.assertEqual(lamp['lightmapGuid'],bytes(self.p.own(c,'LightmapGuid')).hex())
        self.assertEqual(lamp['lightGuid'],bytes(self.p.own(c,'LightGuid')).hex())
        self.assertRegex(lamp['lightmapGuid'],'^[0-9a-f]{32}$')
        self.assertIn('Brightness',lamp['saved'])
        self.assertFalse(lamp['channels'])

    def test_the_toggleable_spot_names_its_destructible(self):
        spot=self.by_actor['SpotLightToggleable_2']
        self.assertEqual(spot['referencedBy'],['XComDestructibleActor_14 ToggleLight (XComDestructibleActor_Action_ToggleLight_0)'])
        self.assertTrue(spot['shadowMapped'])
        self.assertTrue(self.by_actor['DominantDirectionalLight_1']['shadowMapped'])


if __name__=='__main__':unittest.main()

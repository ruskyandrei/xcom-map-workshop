"""No diagnostic pink (export 14): where a material's colour comes from when it has no texture parameter the profile
knows. The rules on their own, then on LWR's own maps where the install is here: burning trees and alien wreck
debris (Forest Trench), a patch package's stub materials (Supply Ship Overlook) and a fractured mesh's interior."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import export  # noqa: E402
from materials import approximate_colour, opacity_input, GREY, WATER  # noqa: E402
from PIL import Image  # noqa: E402
from package import Package  # noqa: E402
from settings import lwr_cooked  # noqa: E402

# the LWR install's packages (the lwr setting), or the folder XCOM_COOKED names; without either, those tests skip
COOKED = Path(os.environ.get('XCOM_COOKED') or lwr_cooked() or 'no-lwr-install-configured')


class Rules(unittest.TestCase):
    def test_names_that_hold_no_colour(self):
        for name in ('T_Smoke_Cloud_Scrolling_NML', 'NoiseHighFreq', 'T_FireSmoke_Scrolling', 'DiffuseDev_Grad',
                     'groundLight_NRM', 'T_Ragged_Edge', 'SpermWhale_SPC', 'RandomLights'):
            self.assertFalse(export.colour_like(name), name)
        for name in ('T_Alien_Destroyed', 'pineBranchSplit', 'pineTree_LOD3_Burnt', 'Rough_Debris', 'grassMulti',
                     'StaticScreenTexture', 'HQscreens_test'):
            self.assertTrue(export.colour_like(name), name)

    def test_a_diffuse_under_another_parameter_name(self):
        dev = 'GEN_MaterialParents.Textures.DiffuseDev'
        # by its texture's name, Firaxis's misspelling included
        self.assertEqual(export.diffuse_parameter({'Specular_Map': 'a.Spec', 'Diffsue_Map': 'a.Pipes_DIFF'}), 'Diffsue_Map')
        # by its own name: the obsolete tiling material's packed A layer, not the placeholder B layer or the mask
        tiling = {'Diffuse Map A | CMod Mask': 'ENB.TL_RoofTarA_CMOD', 'Normal Map A': 'ENB.TL_RoofTarA_NORM',
                  'Diffuse Map B': dev, 'Diffuse Mask': 'GEN_MaterialParents.Textures.GrayDev'}
        self.assertEqual(export.diffuse_parameter(tiling), 'Diffuse Map A | CMod Mask')
        self.assertEqual(export.diffuse_parameter({'Diffuse_Map': 'RurUS.treeBark'}), 'Diffuse_Map')
        self.assertEqual(export.diffuse_parameter({'Diffuse_GlassMask': 'W.WINBP_GlassParaA', 'Normal': 'W.N_NORM'}),
                         'Diffuse_GlassMask')
        # the only parameter that reads as colour
        self.assertEqual(export.diffuse_parameter({'StaticScreenTexture': 'HQ.HQscreens_test'}), 'StaticScreenTexture')
        self.assertIsNone(export.diffuse_parameter({'Noise_NML': 'FX.Cloud_NML', 'reflection': 'FX.T_Water_Reflection'}))
        self.assertIsNone(export.diffuse_parameter({'Mask': 'FX.T_Pipe_Hole_Square'}))
        self.assertIsNone(export.diffuse_parameter({'Diffuse_Mod': 'a.Mod_DIFF', 'Diffuse Map B': dev}))

    def test_the_colour_among_a_compiled_shaders_textures(self):
        self.assertEqual(export.compiled_colour({1: 'T_Smoke_Cloud_Scrolling_NML', 2: 'pineBranchSplit',
                                                 3: 'T_FireSmoke_Scrolling'}), 2)
        self.assertEqual(export.compiled_colour({1: 'Asphalt_Patch_DIFF', 2: 'Asphalt_Patch_MASK'}), 1)
        self.assertEqual(export.compiled_colour({1: 'T_Ragged_Edge', 2: 'T_Alien_Destroyed'}), 2)
        self.assertIsNone(export.compiled_colour({1: 'NormalDev', 2: 'DiffuseDev', 3: 'SpecularDev'}))
        self.assertIsNone(export.compiled_colour({1: 'T_Roiling_Smoke_Scrolling'}))

    def test_what_an_opacity_mask_input_samples(self):
        """opacity_input: a texture parameter with one channel masked; anything else says nothing."""
        class P:
            def __init__(self, struct, nodes): self.struct, self.nodes = struct, nodes
            def own(self, index, key, default=None):
                if index == 1 and key == 'OpacityMask': return self.struct and b'raw'
                return self.nodes.get(index, {}).get(key, default)
            def cls(self, index): return self.nodes[index]['class']
            def tagged(self, reader): return {(k, 0): dict(value=v) for k, v in self.struct.items()}
        sample = {2: {'class': 'MaterialExpressionTextureSampleParameter2D', 'ParameterName': 'Spc_Ems_Mpc_Opc'},
                  3: {'class': 'MaterialExpressionMultiply'}}
        self.assertEqual(opacity_input(P(dict(Expression=2, Mask=1, MaskA=1), sample), 1), ('Spc_Ems_Mpc_Opc', 'A'))
        self.assertEqual(opacity_input(P(dict(Expression=2, Mask=1, MaskG=1), sample), 1), ('Spc_Ems_Mpc_Opc', 'G'))
        self.assertIsNone(opacity_input(P(dict(Expression=2, Mask=0), sample), 1))           # the RGB output
        self.assertIsNone(opacity_input(P(dict(Expression=2, Mask=1, MaskR=1, MaskA=1), sample), 1))
        self.assertIsNone(opacity_input(P(dict(Expression=3, Mask=1, MaskA=1), sample), 1))  # through another node
        self.assertIsNone(opacity_input(P(dict(Expression=0), sample), 1))                   # stripped or unwired
        self.assertIsNone(opacity_input(P(None, sample), 1))

    def test_colours_by_kind(self):
        colour, why = approximate_colour(['FX_Water.Marshlands.MI_Quagmire_Bottom_Layer',
                                          'FX_Water.Marshlands.M_Quagmire_Bottom_Layer'], {'Color': [0.5, 0.5, 0.5, 1]})
        self.assertEqual(colour, [0.015, 0.0175, 0.01])
        self.assertIn('marsh', why)
        self.assertEqual(approximate_colour(['W.Pie_A_WaterGroundColor_INST', 'W.Pie_A_WaterGroundColor'],
                                            {'Pier_A_WaterGroundColor': [0.06, 0.07, 0.08, 1]})[0], [0.06, 0.07, 0.08])
        self.assertEqual(approximate_colour(['FX_Water.Rain_Runoff.M_Water_Opaque_Cheap'], {})[0], WATER)
        self.assertEqual(approximate_colour(['HQ_S_Engineering.Materials.Eng_TempGrey'], {}), (GREY, 'neutral grey'))


def package(name):
    path = COOKED / f'{name}.upk'
    if not path.exists(): raise unittest.SkipTest(f'{name} not available')
    return Package(path)


class OnLwrMaps(unittest.TestCase):
    def material(self, exporter, full):
        return exporter.materials[exporter.material(exporter.p.by_name[full])]

    def test_burning_trees_and_alien_wreck_debris(self):
        p = package('CLrgScout_ForestTrench')
        with tempfile.TemporaryDirectory() as d:
            exporter = export.Exporter(p, Path(d))
            # masked branches keep the colour texture's alpha as their cut-out
            fade = self.material(exporter, 'FX_Fire_Trees.Singles.M_Pine_Tree_Single_Burning_Fade_LOD0')
            self.assertFalse(fade['diffuse'].endswith('-RGB'))
            self.assertEqual(exporter.textures[fade['diffuse']]['name'].rsplit('.', 1)[-1], 'pineBranchSplit')
            self.assertEqual(fade['render']['opacitySource'], 'diffuse-alpha')
            # the wreck debris's only colour-like texture is a packed mask: charred metal by kind instead
            debris = self.material(exporter, 'GenericDestructionLibrary.Materials.M_Alien_Machinery')
            self.assertFalse([d for d in exporter.diagnostics if d['source'] == debris['name'] and 'compiled shader' in d['message']])
            self.assertEqual((debris['render']['family'], debris['render']['constantColor']),
                             ('approximate', [0.025, 0.026, 0.03]))
            bark = self.material(exporter, 'RurUS_RevFoliage.Materials.BurntTreeBark')
            self.assertEqual(bark['render']['diffuseParameter'], 'Diffuse_Map')
            self.assertIsNotNone(bark['diffuse'])
            charcoal = self.material(exporter, 'FX_Fire_B.M_Burnt_Debris_Cluster')
            self.assertEqual(charcoal['render']['family'], 'approximate')
            self.assertEqual(charcoal['render']['constantColor'], [0.02, 0.018, 0.016])
            self.assertFalse(any('diagnostic' in d['message'] for d in exporter.diagnostics))

    def test_a_patch_packages_stub_materials_are_the_maps(self):
        base = export.Exporter(package('CSupplyship_OverlookA'), None)
        stream = export.Exporter(package('patch_clean_overlook'), None, namespace='stream-patch_clean_overlook', base=base)
        crate = stream.p.by_name['AlienCrate.Materials.AlienCrate_GREEN']
        self.assertTrue(stream.stub(crate))
        self.assertFalse(base.stub(base.p.by_name['AlienCrate.Materials.AlienCrate_GREEN']))
        with tempfile.TemporaryDirectory() as d:
            base.folder = stream.folder = Path(d)
            key = stream.section_material(crate, stream.p.by_name['AlienCrate.Meshes.UDK_AlienCrate'])
            self.assertNotIn(key, stream.materials)
            info = base.materials[key]
            self.assertEqual(info['name'], 'AlienCrate.Materials.AlienCrate_GREEN')
            self.assertEqual(info['render']['diffuseParameter'], 'Diffuse')
            self.assertIsNotNone(info['diffuse'])

    def test_a_masked_cut_out_follows_the_opacity_mask_input(self):
        """T-29: PROP_Objects cuts by Spc_Ems_Mpc_Opc's alpha (its OpacityMask input's wiring), PROP_Objects_Old by
        nothing while its OpacityMask switch is off (the farm's tractor), and with the switch on as before."""
        p = package('CsmallScout_Farm')
        self.assertEqual(export.opacity_input(p, p.by_name['GEN_MaterialParents.Master_Materials.PROP_Objects']),
                         ('Spc_Ems_Mpc_Opc', 'A'))
        self.assertIsNone(export.opacity_input(p, p.by_name['GEN_MaterialParents.Obsolete_Materials.PROP_Objects_Old']))
        with tempfile.TemporaryDirectory() as d:
            exporter = export.Exporter(p, Path(d))
            tractor = self.material(exporter, 'VEH_commercial.Materials.MINST_Tractor')
            self.assertEqual(tractor['render']['opacitySource'], 'opaque')
            lamp = self.material(exporter, 'MetalLamp.Materials.MInst_MetalLamp_A')
            self.assertEqual((lamp['render']['opacitySource'], lamp['render']['opacityParameter'],
                              lamp['render']['opacityChannel']), ('packed-alpha', 'Spc_Ems_Mpc_Opc', 'A'))
            self.assertTrue(lamp['diffuse'].endswith('-RGB') and lamp['opacity'].endswith('-A'))
            # the lamp's own mask cuts none of it, where its colour's alpha cut 98%
            with Image.open(Path(d) / exporter.textures[lamp['opacity']]['url']) as mask:
                low = sum(mask.convert('L').histogram()[:int(255 * lamp['alphaTest'])])
                self.assertLess(low / (mask.width * mask.height), 0.01)
        p = package('URB_TruckStop_EWI')
        with tempfile.TemporaryDirectory() as d:
            lift = self.material(export.Exporter(p, Path(d)), 'CarLift.Materials.CarLiftBase_MIC')
            self.assertTrue(lift['staticSwitches']['OpacityMask'])
            self.assertEqual(lift['render']['opacitySource'], 'diffuse-alpha')

    def test_a_fractured_meshs_interior_is_hidden_and_a_missing_material_grey(self):
        p = package('CSmallScout_Roadhouse')
        exporter = export.Exporter(p, None)
        glass = exporter.section_material(0, p.by_name['VEH_MovingVan.Meshes.MovingVanGlass_FRACTURED'])
        self.assertEqual(exporter.materials[glass]['render']['family'], 'hidden')
        p = package('URB_HighwayBridge')
        exporter = export.Exporter(p, None)
        powerline = next(-i for i in range(1, len(p.imports) + 1)
                         if p.name(-i) == 'EXT_PROP_Powerlines.Materials.M_PowerLine')
        key = exporter.section_material(powerline, p.by_name['BridgeSupport.Meshes.bridgeCableA'])
        self.assertEqual(exporter.materials[key]['render']['constantColor'], export.NEUTRAL)
        self.assertEqual(exporter.diagnostics[-1]['source'], 'EXT_PROP_Powerlines.Materials.M_PowerLine')


if __name__ == '__main__':
    unittest.main()

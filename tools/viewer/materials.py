"""Explicit first-pass rules for the source material families we can identify.

UE destruction masks are independent of colour-texture alpha. A material being
BLEND_Masked does not establish that diffuse alpha is an opacity mask.
"""
import re

from package import Reader, FormatError


def _resource(p, r, textures=None):
    """Reads a native FMaterialResource (and EW's material data after it) from `r`; its material ID. The textures
    its uniform expressions sample by index (object references) are appended to `textures` when given."""
    for _ in range(r.count()):
        n = r.i32()  # FString compile error, possibly UTF-16
        r.take(n if n >= 0 else -2*n)
    r.take(r.count()*8)  # texture dependency map
    r.i32()  # max dependency
    material_id = r.take(16)
    r.u32()  # UV count
    refs = [r.i32() for _ in range(r.count())]  # uniform expression texture references
    if textures is not None: textures.extend(refs)
    r.take(24)  # five flags and coordinate-transform usage
    r.take(r.count()*16); r.u32()  # texture lookups and fallback flags
    if p.header['lic'] == 64:
        r.take(16); r.take(r.count()*16); r.i32()  # FXComMaterialData
    return bytes(material_id)


def resource_id(p, material):
    """The material ID in a material's (or a permutation instance's) native resource: a base material's shader maps
    are keyed by it (shader_cache.py)."""
    return _resource(p, p.native(material))


def resource_textures(p, material):
    """The textures (object references) a material's (or a permutation instance's) resource lists for its uniform
    expressions: a shader map's `Texture` and `TextureParameter` expressions name them by index."""
    out = []
    _resource(p, p.native(material), out)
    return out


def static_parameters(p, material):
    """A material instance's own static permutation, None without one: dict(id (its resource's ID), base (the static
    parameter set's base material ID), switches [(name, value, override)], masks [(name, (r, g, b, a), override)],
    normals [(name, compression, override)]), each in the order the record keeps them. Counted, bounded reads."""
    if not p.own(material, 'bHasStaticPermutationResource', False): return None
    r = p.native(material)
    material_id = _resource(p, r)
    base = bytes(r.take(16))  # FStaticParameterSet.BaseMaterialId
    switches, masks, normals = [], [], []
    for _ in range(r.count()):
        name = p.fname(r)
        value, override = r.unpack('2i')
        if value not in (0, 1) or override not in (0, 1):
            raise FormatError('Invalid static switch boolean')
        r.take(16)  # expression GUID
        switches.append((name, bool(value), bool(override)))
    for _ in range(r.count()):
        name = p.fname(r)
        flags = r.unpack('5i')
        r.take(16)
        masks.append((name, tuple(bool(f) for f in flags[:4]), bool(flags[4])))
    for _ in range(r.count()):
        name = p.fname(r)
        compression = r.take(1)[0]
        override = r.i32()
        r.take(16)
        normals.append((name, compression, bool(override)))
    for _ in range(r.count()):  # terrain layer weights: never seen with entries
        p.fname(r)
        r.take(4 + 4 + 16)
    return dict(id=material_id, base=base, switches=switches, masks=masks, normals=normals)


def static_switches(p, material):
    """Own overridden switches in an EW/UDK material instance's native SM3 record ({name: value})."""
    parameters = static_parameters(p, material)
    if parameters is None: return {}
    return {name: value for name, value, override in parameters['switches'] if override}


def constant_color(p, material):
    """Source constants for the three textureless families exercised by Temple Ship."""
    name = p.name(material)
    if name == 'HQ_FundingCouncil.Materials.UnlitBlack': return [0, 0, 0], True
    if name == 'jeremy_dev.M_SimpleGrey': return [(128/255)**2.2]*3, False
    if name == 'Level_Design_Construction_Kit.Materials.Flat':
        raw = p.own(material, 'DiffuseColor')
        if raw:
            expression = p.tagged(Reader(raw)).get(('Expression', 0), {}).get('value', 0)
            if expression > 0 and p.cls(expression) == 'MaterialExpressionVectorParameter':
                return p.own(expression, 'DefaultValue', [0, 0, 0, 0])[:3], False
    return None, False


# Linear colours by kind for materials with no colour texture to read (their colour is computed in shaders the
# cook stripped): the root material, its base colour, and the vector parameter that scales it. These come before
# the compiled shaders' textures: the alien wreck debris samples T_Alien_Destroyed, a packed mask (green and red
# channels), which drawn as colour is bright green blotches.
BY_KIND = {
    'GenericDestructionLibrary.Materials.M_Alien_Machinery': ([0.025, 0.026, 0.03], None,
                                                               'alien wreck debris: charred metal'),
    'GenericDestructionLibrary.Materials.M_Alien_Machinery_Frac': ([0.025, 0.026, 0.03], None,
                                                                    'alien wreck debris: charred metal'),
    'FX_Water.Marshlands.M_Quagmire_Bottom_Layer': ([0.03, 0.035, 0.02], 'Color', 'marsh bottom: murky green'),
    'FX_Fire_B.M_Burnt_Debris_Cluster': ([0.02, 0.018, 0.016], None, 'burnt debris: charcoal'),
    'CityscapePlates.Materials.Citiscape_Buildings': ([0.03, 0.033, 0.04], None, 'distant city blocks: dark grey'),
}
WATER = [0.012, 0.02, 0.022]
GREY = [(128/255)**2.2]*3
COLOUR_VECTOR = re.compile(r'(?i)(water|ground)_?colou?r$')


def approximate_colour(parents, vectors):
    """A linear colour for a material with no colour texture, and why: by kind (BY_KIND), from a vector parameter
    naming a water or ground colour (the water planes' WaterColor, Pier_A_WaterGroundColor), dark water for a water
    material, else neutral grey."""
    root = parents[-1] if parents else ''
    if root in BY_KIND:
        base, scale, why = BY_KIND[root]
        factor = vectors.get(scale) if scale else None
        if isinstance(factor, list) and len(factor) >= 3:
            base = [min(1.0, b * f) for b, f in zip(base, factor[:3])]
        return base, why
    for name, value in vectors.items():
        if COLOUR_VECTOR.search(name) and isinstance(value, list) and len(value) >= 3:
            return [min(1.0, max(0.0, v)) for v in value[:3]], f'its {name}'
    if any('water' in n.lower() for n in parents):
        return WATER, 'water: dark blue-green'
    return GREY, 'neutral grey'


def coordinates(p, expression):
    raw = p.own(expression, "Coordinates")
    ref = 0
    if raw:
        ref = p.tagged(Reader(raw)).get(("Expression", 0), {}).get("value", 0)
    if ref > 0 and p.cls(ref) == "MaterialExpressionTextureCoordinate":
        return dict(channel=p.own(ref,"CoordinateIndex",0),
                    scale=[p.own(ref,"UTiling",1.0),p.own(ref,"VTiling",1.0)])
    # An empty expression uses the texture sample's constant coordinate index.
    return dict(channel=p.own(expression,"ConstCoordinate",0),scale=[1.0,1.0],
                approximate=bool(ref))


def opacity_input(p, material):
    """What a cooked Material's OpacityMask input samples: (texture parameter, channel) when it is wired straight to
    a texture sample parameter with one channel masked, as PROP_Objects' Spc_Ems_Mpc_Opc alpha. None when nothing is
    connected or it goes through a node the cooker stripped (cooking keeps parameter nodes and blanks links to the
    rest), which says nothing about where the mask comes from."""
    raw = p.own(material, 'OpacityMask')
    if not raw: return None
    tag = p.tagged(Reader(raw))
    ref = tag.get(('Expression', 0), {}).get('value', 0)
    if not isinstance(ref, int) or ref <= 0 or p.cls(ref) != 'MaterialExpressionTextureSampleParameter2D': return None
    name = p.own(ref, 'ParameterName')
    channels = [c for c in 'RGBA' if tag.get((f'Mask{c}', 0), {}).get('value', 0)]
    if not name or not tag.get(('Mask', 0), {}).get('value', 0) or len(channels) != 1: return None
    return name, channels[0]


def profile(parents, blend, parameters, scalars, sampling, switches=None):
    families = {name.rsplit(".",1)[-1] for name in parents}
    destruction = bool(families & {"BLDG_Floors","BLDG_Enterable","Building_Fracturable_DecoFrac",
                                   "Building_Fracturable_InteriorFaces"})
    # Intact building destruction is driven by component/vertex state, not by
    # the source diffuse image's alpha. No damage simulation is active here.
    opacity = "intact-destruction" if destruction else "diffuse-alpha" if blend == "BLEND_Masked" else "opaque"
    preferred = ("Diffuse_Base","Diffuse","DiffuseMap","Diffuse Map","Diffuse_BaseA") if destruction else ("Diffuse","Diffuse_Base","DiffuseMap","Diffuse Map","Diffuse_BaseA")
    diffuse = next((n for n in preferred if parameters.get(n)),None)
    uv = dict(sampling.get(diffuse,{"channel":0,"scale":[1,1]}))
    if "BLDG_Enterable" in families:
        tile = scalars.get("TileXY",1.0)
        uv["scale"] = [s*tile for s in uv["scale"]]
    family="building" if destruction else "vehicle" if "VEH_Objects" in families else "generic"
    alien = bool(families & {'ALIEN_Base', 'ALIEN_Base_NoLMSPC'})
    if alien:
        family = 'alien'
        # The source switch selects packed SPC alpha; diffuse alpha is unrelated.
        opacity = 'packed-alpha' if (switches or {}).get('OpacityMasked', False) else 'opaque'
    if 'ALIEN_DoorEnergy_Opaque' in families:
        family, opacity = 'alien-energy', 'opaque'
    if any(name.startswith('CivFogged_') for name in families):family='fogged-civilian'
    result = dict(family=family, opacitySource=opacity,diffuseParameter=diffuse,uv=uv)
    if alien and parameters.get('Spc_Ems_Ref_Opc'):
        result['emissiveParameter'] = 'Spc_Ems_Ref_Opc'
        if opacity == 'packed-alpha': result['opacityParameter'] = 'Spc_Ems_Ref_Opc'
    return result

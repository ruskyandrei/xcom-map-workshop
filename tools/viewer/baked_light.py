"""A piece's baked light as the game stores it, for the export (game-likeness plan, stage B1; F-180, F-181).

The game lights a lightmapped piece from its directional lightmap: two DXT1 atlases read through sRGB, a colour and
three direction values, each with its scale, at the piece's lightmap UVs (its mesh's LightMapCoordinateIndex channel,
scaled and biased into its rectangle of the atlas). The page weights the three direction values by the squared
cosines of the material's normal with UE3's basis (section 0 of the implementation plan; the baker's flat_light is
three times that, F-181). The sun's shadow on a piece is its shadow map of the dominant directional light: a distance
field (or a plain factor) in an atlas of its own, at the same lightmap UVs with its own scale and bias. A piece wholly
in the sun's shadow has none: the light is on its IrrelevantLights, and the game draws no sun on it (F-184).

  lightmap(p, component, mesh) -> dict | None        the piece's lightmap: its two atlases (export indices), scales,
                                                     UV scale and bias and channel
  sun_shadow(p, component, guid) -> dict | None      its shadow map of the light with that LightGuid (hex)
  sun_irrelevant(p, component, guid) -> bool         whether that light is on its IrrelevantLights
  dominant_guid(p) -> str | None                     the map's dominant directional light's LightGuid (hex)
"""
from pathlib import Path
import struct
import sys
if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.append(str(Path(__file__).resolve().parents[1]))     # tools/paths.py (review finding 54)
import paths  # noqa: E402
paths.use('upk')
import lighting_records  # noqa: E402
from package import FormatError  # noqa: E402

# what reading one piece's lighting of a damaged package can raise (the export's other readers' guard)
UNREADABLE = (FormatError, ValueError, IndexError, KeyError, struct.error, OSError)
DOMINANT = ('DominantDirectionalLightComponent',)


def lightmap(p, component, mesh):
    """The piece's LOD 0 directional lightmap: dict(colour, directions: the atlases' export indices, scale0, scale1:
    the slots' [r, g, b] scales, uvScale, uvBias, channel: the mesh's lightmap UV channel), or None when it has none (a
    vertex lightmap, none at all)."""
    record = lighting_records.component_record(p, component)
    lod = record['lods'][0] if record['lods'] else None
    lm = lod['lightmap'] if lod else None
    if not lm or lm.get('type') != 2 or len(lm.get('slots') or []) < 2 or not all(s['index'] > 0 for s in lm['slots'][:2]):
        return None
    channel = p.effective(mesh, 'LightMapCoordinateIndex', 0) if mesh > 0 else 0
    return dict(colour=lm['slots'][0]['index'], directions=lm['slots'][1]['index'],
                scale0=[round(float(v), 6) for v in lm['slots'][0]['scale'][:3]],
                scale1=[round(float(v), 6) for v in lm['slots'][1]['scale'][:3]],
                uvScale=[round(float(v), 7) for v in lm['coordinateScale']],
                uvBias=[round(float(v), 7) for v in lm['coordinateBias']], channel=int(channel))


def sun_shadow(p, component, guid):
    """The piece's LOD 0 shadow map of the light whose LightGuid is `guid` (hex): dict(texture: its export index,
    uvScale, uvBias, factor: a plain shadow factor rather than a distance field), or None."""
    if not guid:
        return None
    record = lighting_records.component_record(p, component)
    lod = record['lods'][0] if record['lods'] else None
    for ref in (lod['shadowMaps'] if lod else []):
        if ref <= 0:
            continue
        own = p.own(ref, 'LightGuid')
        if not isinstance(own, (bytes, bytearray)) or own.hex() != guid:
            continue
        texture = p.own(ref, 'Texture', 0)
        if not texture or texture <= 0:
            return None
        return dict(texture=texture, uvScale=[round(v, 7) for v in struct.unpack('<2f', p.own(ref, 'CoordinateScale'))],
                    uvBias=[round(v, 7) for v in struct.unpack('<2f', p.own(ref, 'CoordinateBias'))],
                    factor=bool(p.own(ref, 'bIsShadowFactorTexture', False)))
    return None


def sun_irrelevant(p, component, guid):
    """Whether the light whose LightGuid is `guid` (hex) is on the piece's IrrelevantLights: Lightmass found it lights
    none of the piece (wholly in its shadow), and the game draws none of it there (F-184)."""
    if not guid:
        return False
    raw = p.own(component, 'IrrelevantLights', b'')
    if not isinstance(raw, (bytes, bytearray)) or len(raw) < 4:
        return False
    n = struct.unpack_from('<i', raw)[0]
    return any(raw[4 + 16 * k:20 + 16 * k].hex() == guid for k in range(max(0, min(n, (len(raw) - 4) // 16))))


def dominant_guid(p):
    """The LightGuid (hex) of the persistent level's first dominant directional light, or None."""
    for i in range(1, len(p.exports) + 1):
        if p.cls(i) in DOMINANT and p.name(i).startswith('TheWorld.PersistentLevel.'):
            own = p.own(i, 'LightGuid')
            return own.hex() if isinstance(own, (bytes, bytearray)) else None
    return None

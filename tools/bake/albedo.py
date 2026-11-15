"""Surface albedo for bounce light: each material's mean diffuse colour, linear (baker design, section 4.7).

Lightmass reflects light with the material's diffuse colour (times the WorldInfo's DiffuseBoost, 1 in EW's maps).
This resolves a material's diffuse texture the way the viewer's exporter does (`tools/viewer/export.py`: parent
chain, parameters, render profile), without writing any files, and averages a small mip of that texture (inline mips
are enough for a mean). sRGB textures are decoded to linear. Materials with a constant colour use it; translucent,
additive and modulated materials reflect nothing; anything unresolved gets FALLBACK.
"""
import io
from pathlib import Path
import sys

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'viewer'))
from export import Exporter  # noqa: E402
from mesh import bulk  # noqa: E402
from package import cache_file  # noqa: E402
from texture import dds_header, decompress_payload  # noqa: E402

FALLBACK = (0.3, 0.3, 0.3)
NON_REFLECTING = ('BLEND_Translucent', 'BLEND_Additive', 'BLEND_Modulate')


class _Resolver(Exporter):
    """The viewer's material resolution, with texture keys replaced by export indices and nothing written."""

    def __init__(self, p):
        super().__init__(p, Path('.'))

    def texture(self, index):
        return index if index and index > 0 else None

    def texture_channel(self, index, channel):
        return index if index and index > 0 else None


def texture_mean(p, index, max_size=64):
    """Mean RGB (0-1, as stored) of a texture's smallest live mip of at least 4 texels, preferring one no larger than
    max_size."""
    r = p.native(index)
    bulk(r)
    mips = []
    for _ in range(r.count()):
        item = bulk(r)
        item['width'], item['height'] = r.unpack('2i')
        if item['size'] > 0 and item['count'] > 0 and not item['flags'] & 32 and item['width'] >= 4:
            mips.append(item)
    if not mips:
        raise ValueError(f'{p.name(index)}: no live mip')
    small = [m for m in mips if m['width'] <= max_size and not m['flags'] & 1]
    mip = max(small, key=lambda m: m['width']) if small else min(mips, key=lambda m: m['width'])
    data = mip['data']
    if mip['flags'] & 1:
        cache = p.effective(index, 'TextureFileCacheName')
        with cache_file(p.path.parent, cache).open('rb') as f:
            f.seek(mip['offset'])
            data = f.read(mip['size'])
    data = decompress_payload(data, mip['flags'])
    w, h = mip['width'], mip['height']
    fmt = p.effective(index, 'Format')
    if fmt in ('PF_DXT1', 'PF_DXT3', 'PF_DXT5'):
        fourcc = {'PF_DXT1': 'DXT1', 'PF_DXT3': 'DXT3', 'PF_DXT5': 'DXT5'}[fmt]
        image = Image.open(io.BytesIO(dds_header(w, h, fourcc, len(data)) + data)).convert('RGB')
    elif fmt == 'PF_A8R8G8B8':
        image = Image.frombytes('RGBA', (w, h), data, 'raw', 'BGRA').convert('RGB')
    elif fmt == 'PF_G8':
        image = Image.frombytes('L', (w, h), data).convert('RGB')
    else:
        raise ValueError(f'{p.name(index)}: unsupported format {fmt}')
    rgb = np.asarray(image, float) / 255.0
    if p.effective(index, 'SRGB', True):
        rgb = rgb ** 2.2
    return rgb.reshape(-1, 3).mean(0)


class Albedo:
    """Linear albedo per material export index (cached)."""

    def __init__(self, p):
        self.p = p
        self.resolver = _Resolver(p)
        self.cache = {}
        self.notes = {}

    def blend(self, material):
        """The material's blend mode (BLEND_Opaque when it cannot be resolved)."""
        try:
            return self.resolver.materials[self.resolver.material(material)]['blend'] if material > 0 else 'BLEND_Opaque'
        except Exception:
            return 'BLEND_Opaque'

    def transmits(self, material):
        """Whether light passes through the material (translucent, additive or modulated, like window glass)."""
        return self.blend(material) in NON_REFLECTING

    def __call__(self, material):
        if material in self.cache:
            return self.cache[material]
        value, note = np.array(FALLBACK), 'fallback'
        if material and material > 0:
            try:
                key = self.resolver.material(material)
                info = self.resolver.materials[key]
                if info['blend'] in NON_REFLECTING:
                    value, note = np.zeros(3), info['blend']
                elif info.get('diffuse'):
                    value, note = texture_mean(self.p, info['diffuse']), 'diffuse texture'
                elif info['render'].get('constantColor'):
                    value, note = np.asarray(info['render']['constantColor'][:3], float), 'constant colour'
            except Exception as error:   # unresolvable materials keep the fallback
                note = f'fallback ({type(error).__name__})'
        value = np.clip(value, 0.0, 0.95)
        self.cache[material] = value
        self.notes[material] = note
        return value

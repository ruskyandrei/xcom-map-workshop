"""Makes the base map for UDK Lightmass calibration bakes: a copy of a UDK map whose WorldInfo has no Lightmass
environment light and no ambient occlusion (baker design, section 4.7).

UDK's editor starts on its template map, whose WorldInfo keeps a sky-blue environment colour (R 176, G 218, B 255)
and ambient occlusion, and it refuses SET commands, so `udk_bake.ps1` cannot switch them off. This copies a map that
already holds that WorldInfo (for example the first calibration bake) and overwrites the two values in place, both
fixed-size: `LightmassSettings.EnvironmentColor` becomes black (or `--environment R,G,B`, the bytes the editor
stores, for a bake of the environment light itself) and `bUseAmbientOcclusion` False. Members the map does not store
keep their defaults. The bake opens the copy (`udk_bake.ps1 -Map <name>`) and deletes its actors.

  python -B tools/bake/udk_calib_base.py <src.udk> <udk>\\UDKGame\\Content\\Maps\\calib\\CalibBase.udk
      [--environment 64,69,97]

Only uncompressed licensee-0 packages (as the editor saves them). Refuses to overwrite unless --force.
"""
import argparse
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'upk'))
sys.path.insert(0, str(ROOT / 'viewer'))
sys.path.insert(0, str(ROOT / 'bake'))
import audit_lighting as lighting  # noqa: E402
from lightmap_fields import property_offsets  # noqa: E402
from udk_calib_read import lightmass_settings  # noqa: E402


def struct_members(p, offset, size):
    """{member: (value offset, size, kind)} of a tagged struct value at a logical offset."""
    out, pos, end = {}, offset, offset + size
    while pos + 8 <= end:
        name = p.names[struct.unpack_from('<i', p.data, pos)[0]]
        if name == 'None':
            return out
        if pos + 24 > end:
            break
        kind = p.names[struct.unpack_from('<i', p.data, pos + 8)[0]]
        n = struct.unpack_from('<i', p.data, pos + 16)[0]
        pos += 24
        if kind in ('StructProperty', 'ByteProperty'):
            pos += 8
        n = 1 if kind == 'BoolProperty' else n
        out[name] = (pos, n, kind)
        pos += n
    raise ValueError('LightmassSettings has no terminator')


def edits_for(p, environment=(0, 0, 0)):
    wi = [i for i in range(1, len(p.exports) + 1) if p.cls(i) == 'WorldInfo']
    if len(wi) != 1:
        raise ValueError(f'expected one WorldInfo, found {len(wi)}')
    props = property_offsets(p, wi[0])
    if ('LightmassSettings', 0) not in props:
        raise ValueError('this WorldInfo stores no LightmassSettings (already the defaults)')
    off, size, _ = props[('LightmassSettings', 0)]
    members = struct_members(p, off, size)
    edits = []
    if 'EnvironmentColor' in members:
        o, n, _ = members['EnvironmentColor']
        if n != 4:
            raise ValueError('EnvironmentColor is not a 4-byte colour')
        r, g, b = environment
        edits.append((o, bytes([b, g, r, p.data[o + 3]])))   # stored B, G, R, A; alpha kept
    if 'bUseAmbientOcclusion' in members:
        o, _, _ = members['bUseAmbientOcclusion']
        edits.append((o, b'\0'))
    return edits


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('src', type=Path)
    a.add_argument('dst', type=Path)
    a.add_argument('--force', action='store_true')
    a.add_argument('--environment', default='0,0,0', help='EnvironmentColor R,G,B (0-255)')
    args = a.parse_args()
    environment = tuple(int(v) for v in args.environment.split(','))
    if len(environment) != 3 or not all(0 <= v <= 255 for v in environment):
        a.error('--environment takes three values 0-255')
    if args.dst.exists() and not args.force:
        sys.exit(f'{args.dst} exists; pass --force to replace it')
    p = lighting.Package(args.src)
    raw = bytearray(args.src.read_bytes())
    if p.header['lic'] != 0 or bytes(raw) != bytes(p.data):
        sys.exit('expected an uncompressed UDK (licensee 0) package')
    edits = edits_for(p, environment)
    for o, data in edits:
        raw[o:o + len(data)] = data
    args.dst.parent.mkdir(parents=True, exist_ok=True)
    args.dst.write_bytes(raw)
    q = lighting.Package(args.dst)
    after = lightmass_settings(q)
    color = after.get('EnvironmentColor', dict(R=0, G=0, B=0))
    if (color['R'], color['G'], color['B']) != environment or after.get('bUseAmbientOcclusion', False):
        sys.exit(f'the copy does not read back as intended: {after}')
    print(f'{len(edits)} edits; {args.dst} LightmassSettings now {after}')


if __name__ == '__main__':
    main()

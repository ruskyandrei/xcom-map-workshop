"""Read-only evidence for custom building and terrain feasibility (EXP-66).

Uses the configured game's cooked folder, or --cooked <CookedPCConsole>. Prints
counts and asset names only; --output saves the same JSON. No game data is written.
The private native-field helpers are used here to measure existing serialization,
not to claim that the editor can author new fractured meshes.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
for folder in ('viewer', 'upk', 'lab'):
    sys.path.insert(0, str(ROOT / 'tools' / folder))
import collision
import labpaths
import mesh
import native_fields
from package import Package


def mesh_record(p, index):
    decoded = mesh.read_mesh(p, index)
    start = p.native(index).pos - p.exports[index - 1]['off']
    fields = native_fields.fields(p, index, start)
    result = dict(
        name=p.name(index), kind=p.cls(index),
        vertices=len(decoded['positions']) // 3,
        triangles=len(decoded['indices']) // 3,
        lods=decoded['lods'], uvChannels=len(decoded['uvs']),
        vertexColours=bool(decoded['colors']),
        lightmapCoordinateIndex=p.own(index, 'LightMapCoordinateIndex'),
        boundsSize=[round(v * 2, 3) for v in decoded['bounds'][3:6]],
        materialSlots=len(decoded['sections']),
        nativeReferenceFields=len(fields), nativeLayoutValidated=True,
    )
    if p.cls(index) == 'StaticMesh':
        col = collision.line_collision(p, index)
        result['collision'] = dict(
            bodySetup=p.name(collision.body_setup(p, index)),
            simpleLine=col['simple'],
            convexAndBoxElements=len(col.get('elements', [])),
            skippedSpheresAndCapsules=col.get('skipped', 0),
        )
    else:
        out = native_fields._Out(p, index, start)
        native_fields._static_mesh_tail(out, native_fields._static_mesh_head(out))
        out.obj()
        result['fragments'] = out.r.count()
    return result


def audit(cooked):
    records = []
    for name in ('CSmallScout_Farm', 'URB_Bar'):
        path = cooked / (name + '.upk')
        p = Package(path)
        classes = Counter(p.cls(i) for i in range(1, len(p.exports) + 1))
        samples = []
        if name == 'CSmallScout_Farm':
            samples.append(mesh_record(p, p.by_name['TornEarth.Meshes.SmallscoutRamps']))
        else:
            # The five alphabetically first wall meshes, not a claim about all walls.
            walls = sorted((p.name(i), i) for i in range(1, len(p.exports) + 1)
                           if p.cls(i) == 'FracturedStaticMesh' and 'wall' in p.name(i).lower())
            samples.extend(mesh_record(p, i) for _, i in walls[:5])
        columns, actors = 0, 0
        for i in range(1, len(p.exports) + 1):
            if p.cls(i) in ('XComFracLevelActor', 'XComDecoFracLevelActor'):
                actors += 1
                columns += len(p.structs(p.own(i, 'FragmentColumns')))
        records.append(dict(
            package=name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            version=p.header['ver'], licensee=p.header['lic'],
            terrainExports=classes['Terrain'], landscapeExports=classes['Landscape'],
            staticMeshes=classes['StaticMesh'], fracturedMeshes=classes['FracturedStaticMesh'],
            fracturingActors=actors, fragmentColumns=columns, samples=samples,
        ))
    return dict(scope='Read-only inspection of two installed maps; no new geometry or game run', maps=records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cooked', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    cooked = args.cooked or labpaths.lwr_cooked()
    if cooked is None:
        parser.error('configure the game setting or supply --cooked')
    result = json.dumps(audit(cooked), indent=2) + '\n'
    if args.output:
        args.output.write_text(result, encoding='utf-8', newline='\n')
    else:
        print(result, end='')


if __name__ == '__main__':
    main()

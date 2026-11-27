"""The case file both sides of a material's program read (material_program_cases.json): four of the game's
materials' programs as the slice makes them, each with an input sample and flat textures, and the outputs
shader_eval.py gives. test_shader_slice.py holds shader_eval to it (and, with the install, the slice), and
material_program_test.mjs holds material_program.js's runProgram to the same numbers.

  python -B tools/viewer/tests/material_program_cases.py --write      (the install's shader cache: made again)
"""
from pathlib import Path
import json
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'upk'))
FILE = HERE / 'material_program_cases.json'
# (name, base material ID, its values)
MATERIALS = [
    ('ENV_ForestGround', '172d031942d928ea4848ee82989329c6', {}),
    ('a one-texture prop with a cut-out', 'acad640d49963317188f94ad316e49b8', {}),
    ('Building_Tiling_Material, tinted', '5a00b6cc443836f8d993a1bfaec71815', {'vectors': {'CMod Color': [1, 0.2, 0.1, 1]}}),
    ('a midground building of two UV channels', '210096484b8aa84db07faa8a4e2ba95b', {}),
]
INPUTS = {'uv0': [0.3, 0.7], 'uv1': [0.6, 0.2], 'uv2': [0.1, 0.1], 'color': [0.8, 0.4, 0.2, 1.0],
          'cameraVector': [0.2, -0.3, 0.9], 'worldPosition': [120.0, -40.0, -600.0, 1.0],
          'worldTangent': [1.0, 0.0, 0.0], 'worldBinormal': [0.0, 1.0, 0.0], 'worldNormal': [0.0, 0.0, 1.0]}


def flat_colours(program):
    """A flat colour a texture key, the same each time: a texture's colour from its position in the list."""
    out = {}
    for k, key in enumerate(sorted(program['textures'])):
        out[key] = [round(0.15 + 0.2 * ((k * 3 + c) % 4), 3) for c in range(4)]
    return out


def evaluate(program, colours, inputs=INPUTS):
    import numpy as np
    import shader_eval
    arrays = {k: np.array([v], dtype=np.float64) for k, v in inputs.items()}
    textures = {k: (lambda uv, c=c: np.tile(c, (len(uv), 1))) for k, c in colours.items()}
    return {k: [round(float(x), 6) for x in v[0]] for k, v in shader_eval.run(program, arrays, textures, n=1).items()}


def make(cache_path):
    import shader_cache
    import shader_slice
    cache = shader_cache.open_cache(cache_path)
    cases = []
    for name, base, values in MATERIALS:
        smap = next(m for m in cache.find_maps(base) if not m.switches)
        program = shader_slice.slice_material(cache, smap, values)
        colours = flat_colours(program)
        cases.append(dict(name=name, base=base, values=values, program=program, inputs=INPUTS, textures=colours,
                          expected=evaluate(program, colours)))
    return cases


def main():
    sys.path.insert(0, str(HERE.parents[1] / 'lab'))
    import labpaths
    path = labpaths.lwr_cooked('RefShaderCache-PC-D3D-SM3.upk')
    cases = make(path)
    if '--write' in sys.argv:
        FILE.write_text(json.dumps(cases, indent=1) + '\n', encoding='utf-8', newline='\n')
        print('written', FILE, len(cases), 'cases')
    else:
        print(json.dumps([dict(name=c['name'], expected=c['expected']) for c in cases], indent=1))


if __name__ == '__main__':
    main()

"""A light's light function (light_functions.py, shader_slice.slice_light_function; game-likeness plan, F1): the case
file both sides read (light_function_cases.json: its programs and their factors at given times, which the page's
material_program.js lightFunctionAt holds too) worked out by shader_eval.py; and on the install, DLC2_3_Furies' four
pulsing lights sliced to the case file's program, a light function with no material giving none (skipped without the
install).

  python -B tools/viewer/tests/test_light_functions.py --write    the case file written again from the install
"""
import json
import math
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'upk'))
sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402
import light_functions  # noqa: E402
import material_programs  # noqa: E402
import shader_eval  # noqa: E402

CASES = HERE / 'light_function_cases.json'
FURIES, NO_FURIES = labpaths.install_map('DLC2_3_Furies')
PULSE = 'FX_Gameplay_DLC_090.M_LightFunction_RedSlow'
TIMES = [0.0, 0.25, 0.5, 1.0, 1.5, 1.75, 3.1]


def factors(program, times):
    return [[round(float(v), 6) for v in shader_eval.run(program, {}, {}, time=t, n=1)['light'][0]] for t in times]


class Cases(unittest.TestCase):
    def test_each_case_gives_its_factors(self):
        cases = json.loads(CASES.read_text(encoding='utf-8'))['cases']
        self.assertTrue(cases)
        for case in cases:
            for got, want in zip(factors(case['program'], case['times']), case['expected']):
                for g, w in zip(got, want):
                    self.assertAlmostEqual(g, w, places=5, msg=case['name'])

    def test_the_pulse_is_half_of_one_plus_a_sine_of_pi_t(self):
        case = next(c for c in json.loads(CASES.read_text(encoding='utf-8'))['cases'] if c['material'] == PULSE)
        for t, (r, g, b) in zip(case['times'], case['expected']):
            want = 0.999 * 0.5 * (1 + math.sin(math.pi * t))        # (the greyscale's 0.333 a channel, the shader's own)
            self.assertAlmostEqual(r, want, places=5)
            self.assertEqual(r, g)
            self.assertEqual(g, b)


def furies_records():
    from package import Package
    p = Package(FURIES)
    programs = material_programs.Programs(None)
    lights = [dict(component=p.paths[i - 1]) for i in range(1, len(p.exports) + 1)
              if p.cls(i).endswith('LightComponent') and p.paths[i - 1].startswith('TheWorld.PersistentLevel.')]
    said = []
    light_functions.add(p, lights, programs, lambda source, message: said.append((source, message)))
    return lights, said


@unittest.skipUnless(FURIES and FURIES.exists(), NO_FURIES)
class Install(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lights, cls.said = furies_records()

    def test_four_lights_pulse_by_the_case_files_program(self):
        found = [r for r in self.lights if 'lightFunction' in r]
        self.assertEqual(len(found), 4)
        case = next(c for c in json.loads(CASES.read_text(encoding='utf-8'))['cases'] if c['material'] == PULSE)
        for r in found:
            self.assertEqual(r['lightFunction']['material'], PULSE)
            self.assertTrue(r['lightFunction']['moves'])
            self.assertEqual(r['lightFunction']['program'], case['program'])
        self.assertEqual(self.said, [])

    def test_a_light_function_with_no_material_gives_none(self):
        # the map's dominant light names a light function with no material: the game draws it steady
        sun = [r for r in self.lights if 'DominantDirectionalLight' in r['component']]
        self.assertTrue(sun)
        self.assertTrue(all('lightFunction' not in r for r in sun))


def write():
    lights, said = furies_records()
    found = next(r for r in lights if 'lightFunction' in r)['lightFunction']
    cases = [dict(name='pulse', material=found['material'], program=found['program'], times=TIMES,
                  expected=factors(found['program'], TIMES))]
    CASES.write_text(json.dumps(dict(about='A light function\'s program (light_functions.py, export 46) and the factor it '
                                     'gives the light at each time (shader_eval.py); material_program.js lightFunctionAt '
                                     'is held to the same numbers. Written by test_light_functions.py --write.',
                                     cases=cases), indent=1) + '\n', encoding='utf-8', newline='\n')
    print('wrote', CASES, said)


if __name__ == '__main__':
    if sys.argv[1:] == ['--write']:
        write()
    else:
        unittest.main()

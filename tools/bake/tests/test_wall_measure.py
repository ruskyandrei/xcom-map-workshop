"""Walls in the look of any of the game's walls (custom geometry plan, M4; work order A): the general path of
frac_wall.py on a recipe written here (no install needed), wall_measure.py on donors of the configured install (the
Bar's, the old --check; a wall with one face slot a side, one with no trim slot, one whose trim carries its faces, one
whose sides differ, a one-storey donor, a modelled one) with the twin check on each, and the walls' catalogue
(tools/bake/looks/walls.json: its form, and that a fresh build of some of its walls gives their lines byte for byte
twice over)."""
from collections import Counter
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(TOOLS / 'upk'))
sys.path.insert(0, str(TOOLS / 'viewer'))
sys.path.insert(0, str(TOOLS / 'lab'))
import frac_wall  # noqa: E402
import labpaths  # noqa: E402
import wall_catalogue  # noqa: E402
import wall_measure  # noqa: E402

# a measured look written out (wall_measure's recipe form): side A the Bar's skirting, a chair rail stepping out and
# back at 52 and 64 (two ledges), its face split at 192 and a cornice; side B plain with a sloping foot; seven slots,
# slot 3 and slot 6 used by nothing (empty sections)
UV = [[0.0104, 0.0, 0.25], [0.0, -0.05, 0.6]]
RECIPE = dict(
    measure=1, donor='Made.Here.Wall', bottom=-16.0, top=384.0, half=8.0, endInset=8.0,
    profile=dict(A=[[11.0, -16.0], [11.0, 0.0], [10.0, 9.0], [8.0, 12.0], [8.0, 52.0], [9.0, 52.0], [10.0, 53.0],
                    [10.0, 63.0], [9.0, 64.0], [8.0, 64.0], [8.0, 372.0], [12.0, 374.0], [12.0, 384.0]],
                 B=[[9.0, -16.0], [8.0, 0.0], [8.0, 384.0]]),
    strips=dict(A=[dict(slot=4, face=False, uv=UV)] * 3 + [dict(slot=None, face=True, uv=None)]
                + [dict(slot=4, face=False, uv=UV)] * 5 + [dict(slot=None, face=True, uv=None)]
                + [dict(slot=4, face=False, uv=UV)] * 2,
                B=[dict(slot=4, face=False, uv=None), dict(slot=None, face=True, uv=None)]),
    slots=dict(sideA=[0, 1], sideB=[2], interior=5), splits=dict(A=[192.0], B=[]),
    faceUV={'0A': [[0.0052, 0.0, 0.5], [0.0, -0.0052, 4.0]], '1A': [[0.0052, 0.0, 0.5], [0.0, -0.0052, 4.0]],
            '2B': [[-0.0052, 0.0, 0.5], [0.0, -0.0052, 7.0]]},
    caps=dict(top=dict(slot=4, uv=[[-0.0104, 0.0, 0.0], [0.0, -0.005, 0.17]]), bottom=None),
    colours=dict(outside='fffffeff', interior='ffffffff'), cell=[96.0, 80.0], jitter=0.3, collisionHalf=8.0,
    collisionY=[-8.0, 8.0], lightmap=dict(density=0.196, interiorDensity=0.5, margin=2, block=4), sections=7,
    storeys=2, storey=192.0, donorLength=560.0, frame=dict(turned=False, centre=0.0, x=[-376.0, 184.0]))
LOOK = dict(mesh=RECIPE['donor'], measure=1, recipe=RECIPE)


def triangles(mesh):
    """[(slot, fragment, (a, b, c) positions, vertex index of a)] of LOD 0."""
    lod = mesh['lods'][0]
    pos, idx = lod['positions'], lod['indices'][1]
    out = []
    for s in lod['sections']:
        for f, (first, n) in enumerate(s['fragments']):
            for t in range(first // 3, first // 3 + n):
                out.append((s['slot'], f, [pos[i] for i in idx[3 * t:3 * t + 3]], idx[3 * t]))
    return out


def open_edges(mesh):
    """How many of the triangles' edges have no edge running back along them in the same fragment."""
    edges = {}
    for _, f, tri, _ in triangles(mesh):
        tri = [tuple(round(c, 3) for c in p) for p in tri]
        e = edges.setdefault(f, Counter())
        for a, b in ((0, 1), (1, 2), (2, 0)):
            e[tri[a], tri[b]] += 1
    return sum(1 for e in edges.values() for k, c in e.items() if e.get((k[1], k[0]), 0) != c)


def facing_in(mesh):
    """How many triangles face against their vertices' normal (UE3's front faces: clockwise seen from outside)."""
    vertices = mesh['lods'][0]['vertices']
    count = 0
    for _, _, (a, b, c), first in triangles(mesh):
        n = [(x - 127.5) / 127.5 for x in vertices[first][1][:3]]
        u, v = [q - p for p, q in zip(a, b)], [q - p for p, q in zip(a, c)]
        cross = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        count += sum(x * y for x, y in zip(cross, n)) > 1e-6
    return count


class GeneralPath(unittest.TestCase):
    """A measured look's wall (frac_wall's block "any look"), from the recipe above."""
    WALLS = dict(
        twin=dict(x0=0.0, x1=576.0, openings=[], seed=1),
        # a doorway, and a window whose sill is the chair rail's ledges' height and whose lintel is the face's split
        doorway=dict(x0=0.0, x1=480.0, openings=[dict(x0=96.0, x1=192.0, z0=-16.0, z1=160.0),
                                                 dict(x0=288.0, x1=384.0, z0=64.0, z1=192.0)], seed=2),
        joined=dict(x0=0.0, x1=1536.0, openings=[dict(x0=192.0, x1=480.0, z0=40.0, z1=300.0)], seed=3,
                    ends=['through', 'line']),
        storey=dict(x0=0.0, x1=288.0, openings=[], seed=4, storeys=1))
    built = {}

    @classmethod
    def setUpClass(cls):
        for name, wall in cls.WALLS.items():
            cls.built[name] = frac_wall.build(dict(wall, look=LOOK))

    def test_every_fragment_is_closed_and_every_triangle_faces_out(self):
        for name, out in self.built.items():
            self.assertEqual(open_edges(out['mesh']), 0, name)
            self.assertEqual(facing_in(out['mesh']), 0, name)
            uv = [v[2][1] for v in out['mesh']['lods'][0]['vertices']]
            self.assertTrue(all(0.0 <= u <= 1.0 and 0.0 <= v <= 1.0 for u, v in uv), name)

    def test_the_mesh_has_the_donors_slots_in_order_the_unused_ones_empty(self):
        for name, out in self.built.items():
            sections = out['mesh']['lods'][0]['sections']
            self.assertEqual([s['slot'] for s in sections], list(range(7)), name)
            counts = {s['slot']: s['triangles'] for s in sections}
            self.assertEqual((counts[3], counts[6]), (0, 0), name)
            self.assertTrue(all(counts[k] > 0 for k in (0, 2, 4, 5)), name)
            self.assertEqual(out['mesh']['fractured']['interior'], 5)
        self.assertEqual(frac_wall.sections_of(RECIPE), 7)
        self.assertEqual(frac_wall.sections_of(frac_wall.RECIPE), 6)

    def test_each_side_stands_on_its_own_outline(self):
        pos = self.built['twin']['mesh']['lods'][0]['positions']
        self.assertEqual((min(p[1] for p in pos), max(p[1] for p in pos)), (-9.0, 12.0))
        self.assertEqual(frac_wall.extent(RECIPE), (-9.0, 12.0))
        self.assertEqual(frac_wall.extent(frac_wall.RECIPE), (-12.0, 12.0))
        # the chair rail stands 10 proud on side A between 53 and 63, side B is flat at 8 there
        at = [p for p in pos if 54 < p[2] < 62]
        self.assertEqual(sorted({p[1] for p in at if p[1] > 0}), [10.0])
        self.assertEqual(sorted({p[1] for p in at if p[1] < 0}), [-8.0])

    def test_faces_take_their_slot_by_height_and_its_texture(self):
        lod = self.built['twin']['mesh']['lods'][0]
        pos, idx, vertices = lod['positions'], lod['indices'][1], lod['vertices']
        checked = Counter()
        for s in lod['sections']:
            if s['slot'] not in (0, 1):
                continue
            for t in range(s['first'] // 3, s['first'] // 3 + s['triangles']):
                corners = idx[3 * t:3 * t + 3]
                if not all(abs(pos[k][1] - 8.0) < 1e-6 for k in corners):
                    continue        # (the wall's ends in the face's slot)
                zs = [pos[k][2] for k in corners]
                self.assertTrue(max(zs) <= 192 + 1e-6 if s['slot'] == 0 else min(zs) >= 192 - 1e-6, (s['slot'], zs))
                (a, b, c), (d, e, f) = RECIPE['faceUV']['%dA' % s['slot']]
                for k in corners:
                    u, v = vertices[k][2][0]
                    self.assertAlmostEqual(u, a * pos[k][0] + b * pos[k][2] + c, 5)
                    self.assertAlmostEqual(v, d * pos[k][0] + e * pos[k][2] + f, 5)
                checked[s['slot']] += 1
        self.assertTrue(checked[0] and checked[1])

    def test_one_storey_takes_a_storey_out_of_the_face(self):
        self.assertEqual(frac_wall.storeys_of(RECIPE), (1, 2))
        R = frac_wall.shaped(dict(self.WALLS['storey'], look=LOOK))
        self.assertEqual(R['top'], 192.0)
        # the face's run is cut short (372 -> 180), the cornice kept above it, the chair rail where it was
        self.assertEqual([z for _, z in R['profile']['A']][-3:], [180.0, 182.0, 192.0])
        self.assertEqual(R['profile']['A'][:10], RECIPE['profile']['A'][:10])
        zs = [p[2] for p in self.built['storey']['mesh']['lods'][0]['positions']]
        self.assertEqual((min(zs), max(zs)), (-16.0, 192.0))
        self.assertIs(frac_wall.shaped(dict(self.WALLS['twin'], look=LOOK)), RECIPE)
        with self.assertRaises(ValueError):
            frac_wall.shaped(dict(self.WALLS['storey'], storeys=3, look=LOOK))

    def test_the_collision_and_the_box_follow_the_look(self):
        import frac_walls
        out = self.built['doorway']
        # beside, over the doorway; beside, under and over the window; beside
        self.assertEqual(len(out['solids']), 6)
        self.assertTrue(all(lo[1] == -8.0 and hi[1] == 8.0 for lo, hi in out['solids']))
        wall = dict(self.WALLS['doorway'], look=LOOK)
        self.assertEqual(frac_walls.local_box(wall), [8.0, 472.0, -9.0, 12.0, -16.0, 384.0])
        frac_walls.check(dict(kind='fracWall', version=2, wall=wall))
        with self.assertRaises(ValueError):
            frac_walls.check(dict(kind='fracWall', version=2, wall=dict(wall, storeys=3)))

    def test_a_look_by_its_donor_needs_its_recipe_and_names_its_own_mesh(self):
        with self.assertRaises(ValueError):
            frac_wall.look_of(dict(look=dict(mesh=RECIPE['donor'], measure=1)))
        with self.assertRaises(ValueError):
            frac_wall.look_of(dict(look=dict(mesh=RECIPE['donor'], measure=1, recipe=frac_wall.RECIPE)))
        self.assertIs(frac_wall.look_of(dict(look=LOOK)), RECIPE)
        wall = dict(self.WALLS['twin'], look=LOOK)
        self.assertNotEqual(frac_wall.mesh_name(wall), frac_wall.mesh_name(self.WALLS['twin']))
        self.assertEqual(frac_wall.mesh_name(wall), frac_wall.mesh_name(dict(wall)))

    def test_a_donor_over_its_pivot_is_moved_down_by_whole_levels(self):
        # its bottom ends in (-64, 0]: 64 -> 0, 192 -> 0, 48 -> -16, 320 -> 0; at or under its pivot, not moved
        self.assertEqual([wall_measure.lift_of(b) for b in (64.0, 192.0, 48.0, 320.0, 0.0, -16.0)],
                         [64.0, 192.0, 64.0, 320.0, 0.0, 0.0])
        high, made = wall_measure.lowered_by(dict(RECIPE, frame=dict(RECIPE['frame'])), {'A': [[100.0, 120.0]]}, 64.0)
        self.assertEqual((high['bottom'], high['top'], high['frame']['lowered'], made), (-80.0, 320.0, 64.0, {'A': [[36.0, 56.0]]}))
        self.assertEqual(high['profile']['A'][0], [11.0, -80.0])
        self.assertEqual(high['splits'], dict(A=[128.0], B=[]))
        # each face keeps its texture where it was on the wall
        (a, b, c), (d, e, f) = RECIPE['faceUV']['0A']
        (a2, b2, c2), (d2, e2, f2) = high['faceUV']['0A']
        self.assertAlmostEqual(d * 10 + e * 100 + f, d2 * 10 + e2 * 36 + f2, 6)
        self.assertNotIn('lowered', RECIPE['frame'])

    def test_painting_puts_the_donor_in_the_walls_frame(self):
        import numpy as np
        import frac_walls
        # a donor along y (turned: its mesh's x is the wall's -y), its centre line at the mesh's x 4 (the turned
        # frame's y -4), 560 long, the points of one face; a made wall twice as long
        donor = np.array([[4.0 + 8.0, -376.0 + x, 0.0] for x in range(0, 561, 40)])
        made = np.array([[x, 8.0, 0.0] for x in range(8, 1129, 40)])
        d, p = frac_walls.in_frame(donor, made, dict(turned=True, centre=-4.0, x=[-376.0, 184.0]))
        self.assertEqual(sorted({round(v, 3) for v in d[:, 1]}), [-8.0])
        self.assertTrue(np.all(p[:, 0] >= -376.0 - 1e-6) and np.all(p[:, 0] <= 184.0 + 1e-6))
        self.assertAlmostEqual(p[0, 0], -376.0)
        self.assertAlmostEqual(p[-1, 0], 184.0)


GAME = labpaths.install_map('URB_Bar')[0]
NO_GAME = labpaths.install_map('URB_Bar')[1]
# the donors: (map, actor), each a variant of the recipe
DONORS = dict(
    bar=('URB_Bar', 'XComDecoFracLevelActor_17'),
    one_slot=('URB_CommercialStreet', 'XComDecoFracLevelActor_26'),        # HighRise_384BackA: one face slot a side
    no_trim=('URB_PierA', 'URB_Pier_A_Building.Meshes.URBPierAWH_WallMainSouth_FRACTURED'),
    trim_faces=('LSupplyShip_ForestGrove', 'SupplyShipBody.MeshesWall.SupplyWallAx6_FRACTURED'),
    sides_differ=('URB_Bar', 'ComKit_Meshes.Cores.Core_384FacadeA_FRACTURED'),
    modelled=('CSmallScout_Roadhouse', 'XComFracLevelActor_15'),            # RHWallEast
)


def have(*maps):
    return all((labpaths.install_map(m)[0] or Path('-none-')).exists() for m in maps)


@unittest.skipUnless(GAME is not None and GAME.exists(), NO_GAME)
class Measurer(unittest.TestCase):
    """wall_measure on the install's donors: the Bar's against RECIPE (the research script's --check), and a look's
    entry and twin for each variant."""
    entries = {}

    @classmethod
    def setUpClass(cls):
        from package import Package
        cls.packages = {}
        for key, (name, what) in DONORS.items():
            path = labpaths.install_map(name)[0]
            if path is None or not path.exists():
                continue
            if name not in cls.packages:
                cls.packages[name] = Package(path)
            entry = wall_measure.measure(cls.packages[name], what)
            cls.entries[key] = dict(entry, twin=wall_measure.twin(entry['recipe']))

    def entry(self, key):
        if key not in self.entries:
            self.skipTest('%s.upk is not in the install' % DONORS[key][0])
        return self.entries[key]

    def test_the_bars_donor_measures_as_its_recipe(self):
        rows = wall_measure.check(wall_measure.measure_raw(self.packages['URB_Bar'], DONORS['bar'][1]), frac_wall.RECIPE)
        self.assertEqual([r['key'] for r in rows if not r['ok']], [])
        self.assertEqual(len(rows), 22)

    def test_every_twin_matches_its_donors_recipe(self):
        for key in DONORS:
            e = self.entry(key)
            self.assertTrue(e['twin']['ok'], (key, [r for r in e['twin']['rows'] if not r['ok']]))

    def test_the_bars_look(self):
        e = self.entry('bar')
        r = e['recipe']
        self.assertEqual((r['sections'], r['storeys'], e['facts']['storeys']), (6, 2, [1, 2]))
        self.assertEqual((r['slots'], r['splits']), (dict(sideA=[0, 1], sideB=[2, 3], interior=5), dict(A=[192.0], B=[192.0])))
        self.assertEqual(r['profile']['A'], [[11.0, -16.0], [11.0, 0.0], [10.0, 9.0], [8.0, 12.0], [8.0, 372.0],
                                             [12.0, 374.0], [12.0, 384.0]])
        self.assertEqual((r['half'], r['endInset'], r['colours']['outside']), (8.0, 8.0, 'fffffeff'))
        self.assertEqual((e['facts']['verdict'], e['facts']['inside'], e['warnings']), ('swept', True, []))

    def test_a_wall_with_one_face_slot_a_side(self):
        r = self.entry('one_slot')['recipe']
        self.assertEqual((r['slots']['sideA'], r['slots']['sideB'], r['splits']), ([1], [0], dict(A=[], B=[])))
        self.assertTrue(any(s['face'] for s in r['strips']['A']) and any(s['face'] for s in r['strips']['B']))

    def test_a_wall_with_no_trim_slot(self):
        # the pier warehouse: one material on both faces split at 64, its sloping top in a face slot
        r = self.entry('no_trim')['recipe']
        faces = set(r['slots']['sideA']) | set(r['slots']['sideB'])
        self.assertEqual(faces, {0, 1})
        self.assertTrue(all(s['face'] or s['slot'] in faces for X in 'AB' for s in r['strips'][X]))
        self.assertEqual(r['sections'], 3)

    def test_a_wall_whose_trim_carries_its_faces(self):
        # the supply ship's: no face slot, the whole outline in one slot and one unwrap, a storey tall
        e = self.entry('trim_faces')
        r = e['recipe']
        self.assertEqual((r['slots']['sideA'], r['slots']['sideB']), ([], []))
        self.assertTrue(all(not s['face'] and s['slot'] == 0 and s['uv'] for X in 'AB' for s in r['strips'][X]))
        self.assertEqual((r['storeys'], e['facts']['storeys'], r['sections']), (1, [1], 2))

    def test_a_one_storey_donor_is_made_at_its_own_height(self):
        # the supply ship's wall stands 192: one storey, the only height it is made at ("storeys": 1 or left out)
        e = self.entry('trim_faces')
        r = e['recipe']
        look = dict(mesh=r['donor'], measure=1, recipe=r)
        self.assertEqual((frac_wall.storeys_of(r), e['facts']['storeys']), ((1,), [1]))
        self.assertIs(frac_wall.shaped(dict(x0=0.0, x1=384.0, storeys=1, look=look)), r)
        with self.assertRaises(ValueError):
            frac_wall.shaped(dict(x0=0.0, x1=384.0, storeys=2, look=look))
        # a two-storey donor made one storey: its storey (192) off its top
        bar = self.entry('bar')['recipe']
        low = frac_wall.shaped(dict(x0=0.0, x1=384.0, storeys=1, look=dict(mesh=bar['donor'], measure=1, recipe=bar)))
        self.assertEqual((bar['storey'], low['top']), (192.0, bar['top'] - 192.0))

    def test_walls_whose_sides_differ(self):
        # the Bar's facade: its two sides' trims in other textures; the pier's: its top slopes over from one side
        r = self.entry('sides_differ')['recipe']
        self.assertEqual(r['profile']['A'], r['profile']['B'])
        self.assertNotEqual(r['strips']['A'][0]['uv'], r['strips']['B'][0]['uv'])
        p = self.entry('no_trim')['recipe']['profile']
        self.assertNotEqual(p['A'], p['B'])
        self.assertEqual(p['A'][-1], [-8.0, 395.0])

    def test_a_modelled_wall_says_what_isnt_made(self):
        e = self.entry('modelled')
        self.assertEqual(e['facts']['verdict'], 'modelled')
        self.assertIn(wall_measure.MODELLED, e['warnings'])

    def test_the_same_donor_gives_the_same_entry(self):
        name, what = DONORS['no_trim']
        if name not in self.packages:
            self.skipTest('%s.upk is not in the install' % name)
        e = wall_measure.measure(self.packages[name], what)
        self.assertEqual(json.dumps(e, sort_keys=True), json.dumps({k: v for k, v in self.entry('no_trim').items()
                                                                     if k != 'twin'}, sort_keys=True))


class CatalogueFile(unittest.TestCase):
    """The checked-in catalogue's form (no install needed)."""

    @classmethod
    def setUpClass(cls):
        cls.raw = wall_catalogue.OUT.read_bytes()
        cls.catalogue = json.loads(cls.raw)

    def test_it_is_lf_sorted_and_one_look_a_line(self):
        self.assertNotIn(b'\r', self.raw)
        looks = self.catalogue['looks']
        self.assertEqual([e['mesh'] for e in looks], sorted(e['mesh'] for e in looks))
        self.assertEqual(self.raw.decode('utf-8'), wall_catalogue.text(self.catalogue))
        self.assertEqual((self.catalogue['measure'], self.catalogue['built']), (wall_measure.VERSION, '<game>'))

    def test_it_holds_every_wall_of_the_audit_each_with_its_twin_and_warnings(self):
        audit = json.loads(wall_catalogue.AUDIT.read_text(encoding='utf-8'))['walls']
        looks = {e['mesh']: e for e in self.catalogue['looks']}
        self.assertEqual(sorted(looks), sorted(audit))
        self.assertEqual(len(looks), 344)
        keys = ['mesh', 'map', 'actor', 'maps', 'name', 'setting', 'lwrOnly', 'facts', 'warnings', 'twin', 'recipe']
        for mesh, e in looks.items():
            self.assertEqual(list(e), keys, mesh)
            self.assertEqual(e['recipe']['donor'], mesh)
            self.assertEqual(e['maps'], dict(sorted(audit[mesh]['placed'].items())))
            self.assertTrue(e['twin'] == 'ok' or e['twin'], mesh)
            self.assertIn(max(e['facts']['storeys']), (1, 2, 3, 4))
            self.assertEqual(e['facts']['verdict'], audit[mesh]['sweep']['verdict'])
            if e['facts']['verdict'] == 'modelled':
                self.assertIn(wall_measure.MODELLED, e['warnings'], mesh)
            # its heights are over the piece's location: a donor over its pivot moved down to stand on the floor
            lift = e['recipe']['frame'].get('lowered', 0.0)
            self.assertEqual(e['facts'].get('lowered', 0.0), lift, mesh)
            self.assertEqual((e['facts']['bottom'], e['facts']['top']), (e['recipe']['bottom'], e['recipe']['top']))
            if lift:
                self.assertTrue(-64.0 < e['recipe']['bottom'] <= 0.0 and lift % 64 == 0, mesh)
        x9 = looks['AbductorExtWall.Meshes.AbductorExtWallx9_FRACTURED']['recipe']
        self.assertEqual((x9['bottom'], x9['top'], x9['frame']['lowered']), (0.0, 189.945, 192.0))
        self.assertNotIn('lowered', looks['URB_Bar_FRAC.Meshes.URB_BarIntWallB_FRACTURED']['recipe']['frame'])
        self.assertIn('licensee', self.catalogue['about'])

    def test_every_look_builds(self):
        e = next(x for x in self.catalogue['looks'] if x['facts']['verdict'] == 'modelled')
        r = e['recipe']
        out = frac_wall.build(dict(x0=0.0, x1=384.0, openings=[dict(x0=96.0, x1=192.0, z0=r['bottom'], z1=r['bottom'] + 176)],
                                   seed=1, look=dict(mesh=e['mesh'], measure=1, recipe=r)))
        self.assertEqual(open_edges(out['mesh']), 0)
        self.assertEqual(len(out['mesh']['lods'][0]['sections']), r['sections'])


SAMPLE = ['URB_Bar_FRAC.Meshes.URB_BarIntWallB_FRACTURED', 'URB_Pier_A_Building.Meshes.URBPierAWH_WallMainSouth_FRACTURED',
          'ComKit_Meshes.Cores.Core_384FacadeA_FRACTURED']


@unittest.skipUnless(have('URB_Bar', 'URB_PierA'), NO_GAME)
class CatalogueBuild(unittest.TestCase):
    """A fresh build of some of the catalogue's walls gives their lines of the checked-in file, the same bytes twice."""

    def test_a_fresh_build_gives_the_same_bytes(self):
        first = wall_catalogue.text(wall_catalogue.build(only=set(SAMPLE)))
        again = wall_catalogue.text(wall_catalogue.build(only=set(SAMPLE)))
        self.assertEqual(first, again)
        lines = {json.loads(line.rstrip(','))['mesh']: line.rstrip(',') for line in
                 wall_catalogue.OUT.read_text(encoding='utf-8').splitlines() if line.startswith('  {')}
        for line in first.splitlines():
            if line.startswith('  {'):
                line = line.rstrip(',')
                self.assertEqual(line, lines[json.loads(line)['mesh']])


if __name__ == '__main__':
    unittest.main()

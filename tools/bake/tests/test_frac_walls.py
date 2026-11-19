"""Fracturing walls made from numbers in the variant map (frac_walls.py; custom geometry plan, section 0, stage F3).

The columns rule and the request's checks on their own; then, with the configured install (tools/viewer/settings.py),
the proof of concept's build on the bar (no bake): three copies of URB_BarIntWallB_FRACTURED on the pavement, the
reference ('relit', its mesh the donor's), the twin (the donor's size) and the custom wall (four tiles with a doorway),
read back with a fresh reader: the new meshes written whole under XComMapEdGeo, each component's numbers as the
game's walls save them (F0), one painted colour for each new vertex, the columns by F0's rule, the tiles seeded over
the wall's own box."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(TOOLS / 'upk'))
sys.path.insert(0, str(TOOLS / 'viewer'))
sys.path.insert(0, str(TOOLS / 'lab'))
import frac_wall  # noqa: E402
import frac_walls  # noqa: E402
import gen_mesh  # noqa: E402
import labpaths  # noqa: E402
import lightmap_texels  # noqa: E402

BAR, NO_BAR = labpaths.test_file('XCOM_BAR_UPK', labpaths.lwr_cooked('URB_Bar.upk'), 'URB_Bar.upk')
POLICE, NO_POLICE = labpaths.install_map('URB_PoliceStation')
DEMOLITION, NO_DEMOLITION = labpaths.install_map('URB_Demolition_EWI')
ALLEY, NO_ALLEY = labpaths.install_map('URB_CommercialAlley')
PL = 'TheWorld.PersistentLevel.'
DONOR = 'XComDecoFracLevelActor_17'
DOOR = dict(x0=96.0, x1=192.0, z0=-16.0, z1=160.0)
COPIES = [
    dict(actor=DONOR, location=[-1344.0, -192.0, 16.0], rotation=[0, 0, 0], label='Reference',
         generated=dict(kind='relit', version=1)),
    dict(actor=DONOR, location=[-576.0, -192.0, 16.0], rotation=[0, 0, 0], label='Twin',
         generated=dict(kind='fracWall', version=1, wall=dict(x0=-384.0, x1=192.0, openings=[], seed=1))),
    dict(actor=DONOR, location=[-192.0, -192.0, 16.0], rotation=[0, 0, 0], label='Custom',
         generated=dict(kind='fracWall', version=1, wall=dict(x0=0.0, x1=384.0, openings=[DOOR], seed=2))),
]


def overlap(a, b):
    return all(min(a[2 * k + 1], b[2 * k + 1]) - max(a[2 * k], b[2 * k]) > 0 for k in range(3))


class Columns(unittest.TestCase):
    GRID = dict(tx=-1.0, ty=-1.0, tz=-1.0)

    def test_a_column_for_each_tile_and_storey_listing_the_fragments_over_it(self):
        # four fragments a tile wide each, the first two a storey tall, the others two storeys
        boxes = [[96.0 * k - 1, 96.0 * k + 95, -12.0, 12.0, -1.0, 191.0 if k < 2 else 383.0] for k in range(4)]
        cols = frac_walls.columns(boxes, self.GRID)
        self.assertEqual(len(cols), 6)
        for c in cols:
            listed = [f for f, _ in c['frags']]
            self.assertEqual(listed, [f for f, b in enumerate(boxes) if overlap(b, c['box'])])
            self.assertEqual([z for _, z in c['frags']], sorted(z for _, z in c['frags']))
            self.assertAlmostEqual(c['box'][5] - c['box'][4], frac_walls.STOREY)
            self.assertEqual(c['box'][2:4], [-12.0, 12.0])
        # cut to the wall's ends: the last column stops at the last fragment's end
        self.assertAlmostEqual(max(c['box'][1] for c in cols), boxes[-1][1])

    def test_a_wall_along_y_is_cut_along_y(self):
        boxes = [[-8.0, 8.0, 96.0 * k - 1, 96.0 * k + 95, -1.0, 191.0] for k in range(3)]
        cols = frac_walls.columns(boxes, self.GRID)
        self.assertEqual(len(cols), 3)
        self.assertTrue(all(c['box'][:2] == [-8.0, 8.0] for c in cols))

    def test_requests_are_checked(self):
        ok = dict(kind='fracWall', version=1, wall=dict(x0=0, x1=96, openings=[]))
        self.assertIs(frac_walls.check(ok), ok)
        self.assertEqual(frac_walls.check(dict(kind='relit', version=1))['kind'], 'relit')
        for bad in (None, dict(kind='wall'), dict(kind='fracWall', version=3, wall=ok['wall']),
                    dict(kind='fracWall', version=1, wall=dict(x0=0, x1=12)),
                    dict(kind='fracWall', version=1, wall=dict(x0=0, x1=39)),
                    dict(kind='fracWall', version=1, wall=dict(x0=0, x1=96, openings=[dict(x0=90, x1=120, z0=0, z1=10)]))):
            with self.assertRaises(ValueError):
                frac_walls.check(bad)

    def test_a_walls_local_box_is_its_solid_and_the_recipes_section(self):
        self.assertEqual(frac_walls.local_box(dict(x0=0.0, x1=384.0)), [8.0, 376.0, -12.0, 12.0, -16.0, 384.0])

    def test_the_compiler_knows_the_same_inset_and_shortest_wall(self):
        sys.path.insert(0, str(TOOLS / 'editor'))
        import compiler
        self.assertEqual(compiler.FRAC_WALL_END_INSET, frac_wall.RECIPE['endInset'])
        self.assertEqual(compiler.FRAC_WALL_MIN_LENGTH, frac_walls.MIN_LENGTH)


@unittest.skipUnless(BAR.exists(), NO_BAR)
class Built(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import native_copy
        from package import Package
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name)
        cls.m = native_copy.build(BAR, out, 'FracPoc', [dict(c) for c in COPIES])
        cls.q = Package(out / 'FracPoc.upk')
        cls.p = Package(BAR)
        cls.walls = cls.m['nativeCopies']['generatedWalls']
        # (the manifest lists the copies in the order asked)
        cls.copies = dict(zip((c['label'] for c in COPIES), cls.m['nativeCopies']['copies']))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def made(self):
        return [w for w in self.walls if w['kind'] == 'fracWall']

    def test_the_manifest_names_each_wall(self):
        self.assertEqual([(w['kind'], w['label']) for w in self.walls],
                         [('relit', 'Reference'), ('fracWall', 'Twin'), ('fracWall', 'Custom')])
        twin, custom = self.made()
        self.assertEqual((twin['fragments'], twin['solids'], custom['fragments'], custom['solids']), (30, 1, 27, 3))
        self.assertTrue(twin['painted'] and custom['painted'])
        self.assertEqual([c.get('generated') for c in self.m['nativeCopies']['copies']], ['relit', 'fracWall', 'fracWall'])

    def test_the_reference_keeps_the_donors_mesh(self):
        q = self.q
        actor = q.by_name[PL + self.walls[0]['copy']]
        comp = q.own(actor, 'FracturedStaticMeshComponent')
        self.assertEqual(q.name(q.own(comp, 'StaticMesh')), frac_wall.RECIPE['donor'])

    def test_the_new_meshes_are_written_whole_under_our_package(self):
        q = self.q
        for w in self.made():
            mesh = q.by_name[w['mesh']]
            self.assertEqual(q.cls(mesh), 'FracturedStaticMesh')
            self.assertTrue(w['mesh'].startswith(frac_walls.PACKAGE + '.FracWall_'))
            m = gen_mesh.read(q, mesh)
            e = q.exports[mesh - 1]
            self.assertEqual(gen_mesh.write(m, m['at']), bytes(q.data[m['at']:e['off'] + e['size']]))
            self.assertEqual(q.cls(m['bodySetup']), 'RB_BodySetup')
            self.assertEqual(len(m['fractured']['fragments']), w['fragments'])

    def test_each_component_saves_its_numbers_as_the_games_walls_do(self):
        q = self.q
        for w in self.made():
            actor = q.by_name[PL + w['copy']]
            comp = q.own(actor, 'FracturedStaticMeshComponent')
            mesh = q.own(comp, 'StaticMesh')
            self.assertEqual(q.name(mesh), w['mesh'])
            m = gen_mesh.read(q, mesh)
            lod = m['lods'][0]
            self.assertEqual(q.own(comp, 'NumResourceIndices'), len(lod['indices'][1]))
            world = lightmap_texels.world_matrix(q, comp)
            pos = np.array(lod['positions'], float)
            z = (np.c_[pos, np.ones(len(pos))] @ world.T)[:, 2]
            self.assertAlmostEqual(q.own(comp, 'FragmentBoundsMinZ'), z.min(), 3)
            self.assertAlmostEqual(q.own(comp, 'FragmentBoundsMaxZ'), z.max(), 3)
            # one painted colour for each new vertex
            flag, _ = frac_walls._lod_colours(q.data, q.properties(comp)[1])
            self.assertEqual(q.data[flag], 1)
            self.assertEqual(struct.unpack_from('<2I', q.data, flag + 1), (4, len(pos)))

    def test_a_build_without_baking_gives_each_wall_one_even_light_from_a_piece_near_it(self):
        # (M2, D9) every vertex at one texel (a coordinate scale of 0) of a lit piece of the map near the wall
        q = self.q
        for w in self.made():
            self.assertEqual(w['light']['kind'], 'even')
            comp = q.own(q.by_name[PL + w['copy']], 'FracturedStaticMeshComponent')
            lm = frac_walls.lightmap_offsets(q.data, q.properties(comp)[1])
            self.assertEqual(struct.unpack_from('<2f', q.data, lm['scale']), (0.0, 0.0))
            bias = struct.unpack_from('<2f', q.data, lm['bias'])
            self.assertTrue(all(0.0 < b < 1.0 for b in bias))
            for tex, _ in lm['slots'][:2]:
                index = struct.unpack_from('<i', q.data, tex)[0]
                self.assertEqual(q.cls(index), 'LightMapTexture2D')
            self.assertGreater(w['light']['light'], 0.0)
            self.assertIn(w['light']['piece'], q.by_name)

    def test_without_baking_the_dominant_light_is_the_even_light_pieces(self):
        # (M2 item 2) the shadow map of the piece the even light comes from, at a texel of its rectangle; or, where it
        # has none, the light listed irrelevant
        import shadowmaps
        q = self.q
        moon = frac_walls.dominant_shadow(q)['guid']
        for w in self.made():
            comp = q.own(q.by_name[PL + w['copy']], 'FracturedStaticMeshComponent')
            maps = shadowmaps.shadow_maps(q, comp)
            listed = q.own(comp, 'IrrelevantLights', b'')
            piece = q.by_name[w['light']['piece']]
            theirs = [sm for sm in shadowmaps.shadow_maps(q, piece) if sm['guid'] == moon.hex()]
            if theirs:
                self.assertEqual(len(maps), 1)
                self.assertEqual((maps[0]['guid'], maps[0]['texture'], maps[0]['scale']),
                                 (moon.hex(), theirs[0]['texture'], [0.0, 0.0]))
                self.assertEqual(q.exports[maps[0]['export'] - 1]['outer'], comp)
                self.assertNotIn(moon, listed)
                self.assertFalse(w['shadowMap']['irrelevant'])
            else:
                self.assertEqual(maps, [])
                self.assertIn(moon, listed)
                self.assertTrue(w['shadowMap']['irrelevant'])

    def test_a_baked_build_gives_each_wall_its_own_rectangle_of_its_size(self):
        # (M2) set_light on the donor's own record: the rectangle the wall's mesh asks for, at the donor's corner
        # (texel 193, down to the block at 192) or the atlas's where it doesn't fit
        p, q = self.p, self.q
        comp = p.own(p.by_name[PL + DONOR], 'FracturedStaticMeshComponent')
        e = p.exports[comp - 1]
        data = bytes(p.data[e['off']:e['off'] + e['size']])
        at = p.properties(comp)[1] - e['off']
        self.assertEqual(frac_walls.atlas_size(p, comp), (1024, 1024))
        for rect, corner in (((80, 208), (192, 192)), ((900, 200), (0, 192))):
            out = frac_walls.set_light(data, at, dict(kind='rect', rect=rect, atlas=(1024, 1024)))
            self.assertEqual(len(out), len(data))
            lm = frac_walls.lightmap_offsets(out, at)
            self.assertEqual(struct.unpack_from('<2f', out, lm['scale']), (rect[0] / 1024, rect[1] / 1024))
            self.assertEqual(struct.unpack_from('<2f', out, lm['bias']), (corner[0] / 1024, corner[1] / 1024))
            self.assertEqual(out[:lm['scale']], data[:lm['scale']])

    def test_the_columns_list_the_fragments_over_them(self):
        q = self.q
        for w in self.made():
            actor = q.by_name[PL + w['copy']]
            comp = q.own(actor, 'FracturedStaticMeshComponent')
            m = gen_mesh.read(q, q.own(comp, 'StaticMesh'))
            world = lightmap_texels.world_matrix(q, comp)
            lod = m['lods'][0]
            pos = np.array(lod['positions'], float)
            wpos = (np.c_[pos, np.ones(len(pos))] @ world.T)[:, :3]
            idx = lod['indices'][1]
            points = {}
            for s in lod['sections']:
                for f, (first, n) in enumerate(s['fragments']):
                    points.setdefault(f, set()).update(idx[first:first + 3 * n])
            fbox = {f: [v for k in range(3) for v in (wpos[sorted(vs), k].min(), wpos[sorted(vs), k].max())]
                    for f, vs in points.items() if vs}
            cols = q.structs(q.own(actor, 'FragmentColumns'))
            self.assertEqual(len(cols), w['columns'])
            for c in cols:
                b = struct.unpack('<6fB', c[('Bounds', 0)]['value'])
                box = [b[0], b[3], b[1], b[4], b[2], b[5]]
                saved = [(it.get(('FragIndex', 0), {}).get('value', 0), it.get(('MinZ', 0), {}).get('value', 0.0))
                         for it in q.structs(c.get(('FragCache', 0), {}).get('value'))]
                self.assertEqual({f for f, _ in saved}, {f for f, fb in fbox.items() if overlap(fb, box)})
                self.assertEqual([z for _, z in saved], sorted(z for _, z in saved))
                for f, z in saved:
                    self.assertAlmostEqual(z, fbox[f][4], 3)
                self.assertEqual(q.structs(c.get(('DestructibleCache', 0), {}).get('value')), [])

    def test_the_tiles_are_seeded_over_each_walls_own_box(self):
        ref, twin, custom = (self.copies[k]['tiles']['tiles'] for k in ('Reference', 'Twin', 'Custom'))
        self.assertEqual(twin[0] - ref[0], 8)               # the twin is the reference's box, eight tiles east
        self.assertEqual(twin[1] - twin[0], ref[1] - ref[0])
        self.assertLess(custom[1] - custom[0], twin[1] - twin[0])   # the custom wall is shorter than the donor


@unittest.skipUnless(BAR.exists() and POLICE.exists(), NO_POLICE)
class BakedLayout(unittest.TestCase):
    """(M2) A baked Build's made walls before the relight fills them (it is left out here): each wall's lightmap its
    own rectangle of its cloned atlas, the wall's size at the donor's density, and a shadow map of the moon of its own
    (a cloned ShadowMap2D and texture, the same rectangle), the moon off its IrrelevantLights; a 2-tile and a 16-tile
    wall on the Bar."""
    WALLS = [dict(actor=DONOR, location=[-576.0, -192.0, 16.0], rotation=[0, 0, 0], label='Two',
                  generated=dict(kind='fracWall', version=1, wall=dict(x0=0.0, x1=192.0, openings=[], seed=1))),
             dict(actor=DONOR, location=[-1536.0, 384.0, 16.0], rotation=[0, 0, 0], label='Sixteen',
                  generated=dict(kind='fracWall', version=1, wall=dict(x0=0.0, x1=1536.0, openings=[], seed=2)))]

    @classmethod
    def setUpClass(cls):
        from unittest import mock
        import native_copy
        from package import Package
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name)

        def no_relight(cmd, check):
            (out / 'Baked.fixture.json').write_text('{}', encoding='utf-8')
        with mock.patch.object(native_copy.subprocess, 'run', no_relight):
            cls.m = native_copy.build(BAR, out, 'Baked', [dict(c) for c in cls.WALLS], bake=True, cache='Baked_Lighting')
        cls.q = Package(out / 'grown' / BAR.name)
        cls.walls = cls.m['nativeCopies']['generatedWalls']

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_each_wall_has_a_lightmap_rectangle_of_its_size_in_its_own_atlas(self):
        import lightmap_fields
        p = __import__('package').Package(BAR)
        donor = lightmap_fields.component_fields(p, p.own(p.by_name[PL + DONOR], 'FracturedStaticMeshComponent'))
        donor_slots = {s['index'] for s in donor['lods'][0]['lightmap']['slots']}
        q = self.q
        rects = []
        for w in self.walls:
            comp = q.own(q.by_name[PL + w['copy']], 'FracturedStaticMeshComponent')
            lm = lightmap_fields.component_fields(q, comp)['lods'][0]['lightmap']
            rw, rh = w['lightmapRect']
            self.assertEqual(w['light'], dict(kind='rect', rect=w['lightmapRect']))
            self.assertEqual(lm['coordinateScale'], [rw / 1024, rh / 1024])
            self.assertEqual(lm['coordinateBias'], [192 / 1024, 192 / 1024])
            self.assertFalse({s['index'] for s in lm['slots'] if s['index'] > 0} & donor_slots)
            rects.append(rw * rh)
        # sixteen tiles of wall take about eight times the texels of two (the ends and trims are the same)
        self.assertGreater(rects[1], 5 * rects[0])

    def test_each_wall_has_a_shadow_map_of_the_moon_of_its_own(self):
        import shadowmaps
        q = self.q
        moon = frac_walls.dominant_shadow(q)['guid']
        textures = set()
        for w in self.walls:
            comp = q.own(q.by_name[PL + w['copy']], 'FracturedStaticMeshComponent')
            maps = shadowmaps.shadow_maps(q, comp)
            self.assertEqual(len(maps), 1)
            sm = maps[0]
            self.assertEqual(sm['guid'], moon.hex())
            self.assertFalse(sm['factor'])
            self.assertEqual(q.exports[sm['export'] - 1]['outer'], comp)
            self.assertEqual(q.cls(sm['texture']), 'ShadowMapTexture2D')
            size = (q.own(sm['texture'], 'SizeX'), q.own(sm['texture'], 'SizeY'))
            rw, rh = w['lightmapRect']
            self.assertEqual(sm['scale'], [rw / size[0], rh / size[1]])
            self.assertEqual(sm['bias'], [0.0, 0.0])
            textures.add(sm['texture'])
            self.assertTrue(w['shadowMap']['own'])
            # the donor lists the moon irrelevant (an inside wall): the made wall doesn't
            self.assertNotIn(moon, q.own(comp, 'IrrelevantLights', b''))
            # the relight finds it: a receiver of the moon
            self.assertIn(comp, [ci for _, ci, _, _ in shadowmaps.dominant_receivers(q, shadowmaps.dominant_lights(q))])
        self.assertEqual(len(textures), 2)


class DoorInMadeWall(unittest.TestCase):
    """(M3 item 4) A door standing in a made wall's doorway is listed in the wall's columns, so the two break together:
    URB_Bar's door 7 and its frame (XComInteractiveLevelActor_7, XComDestructibleActor_65, listed in the inner wall
    XComDecoFracLevelActor_16's columns where they stand) copied into the doorway of a made wall on the pavement (a
    half turn, as the wall's yaw is the door's wall's turned), as one door: native_copy.edit_columns lists them where
    their original's listing lands, now in the made wall's columns."""
    DOOR = ['XComInteractiveLevelActor_7', 'XComDestructibleActor_65']
    WALL = dict(actor=DONOR, location=[-1728.0, -192.0, 16.0], rotation=[0, 0, 0], label='Made',
                generated=dict(kind='fracWall', version=1, wall=dict(
                    x0=0.0, x1=384.0, openings=[dict(x0=96.0, x1=192.0, z0=-16.0, z1=160.0)], seed=5)))

    @classmethod
    def setUpClass(cls):
        import native_copy
        from package import Package
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name)
        copies = [dict(cls.WALL)]
        for n in cls.DOOR:
            # the doorway's tile centre (x -1584) and the wall's line; the door's yaw a half turn from its own
            copies.append(dict(actor=n, location=[-1584.0, -192.0, 16.0], rotation=[0, 0, 0],
                               assembly='add:XComInteractiveLevelActor_7_copy', family='door'))
        cls.m = native_copy.build(BAR, out, 'FracDoor', copies)
        cls.q = Package(out / 'FracDoor.upk')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_door_and_its_frame_are_in_the_made_walls_columns_at_its_doorway(self):
        q = self.q
        nc = self.m['nativeCopies']
        sec = {c['actor']: c for c in nc['copies']}
        wall = sec[DONOR]['export']
        doors = [sec[n]['export'] for n in self.DOOR]
        cols = []
        for c in q.structs(q.own(wall, 'FragmentColumns')):
            b = struct.unpack('<6f', c[('Bounds', 0)]['value'][:24])
            names = [e[('DestructibleActor', 0)]['value'] for e in q.structs(c.get(('DestructibleCache', 0), {}).get('value'))]
            cols.append(([b[0], b[3]], names))
        for d in doors:
            at = [x for x, names in cols if d in names]
            # in the columns round the doorway (its tile and the tiles beside it, both storeys), each once
            self.assertGreaterEqual(len(at), 4, q.name(d))
            self.assertTrue(all(-1728 - 1 <= x[0] and x[1] <= -1440 + 1 for x in at), at)
            self.assertTrue(all(names.count(d) <= 1 for _, names in cols))


class GroupWithMadeWall(unittest.TestCase):
    """(M3 item 4, F-101's limit) A group that breaks together with a made wall: its prop (a copy of URB_Bar's
    XComDestructibleActor_4, standing against the wall's face) and a map's own prop left in place are listed in the
    wall's columns they stand by (frac_walls.group_columns), and a group of one prop with a wall links no children."""
    PROP = 'XComDestructibleActor_4'

    @classmethod
    def setUpClass(cls):
        import native_copy
        from package import Package
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name)
        p = Package(BAR)
        cls.prop_box = native_copy.piece_box(p, p.by_name[PL + cls.PROP], [-1490.0, -170.0, 16.0], [0, 0, 0])
        copies = [dict(actor=DONOR, location=[-1728.0, -192.0, 16.0], rotation=[0, 0, 0], label='Made', wallGroup=1,
                       generated=dict(kind='fracWall', version=1, wall=dict(x0=0.0, x1=384.0, openings=[], seed=7))),
                  dict(actor=cls.PROP, location=[-1490.0, -170.0, 16.0], rotation=[0, 0, 0], label='Prop', breakGroup=1)]
        cls.m = native_copy.build(BAR, out, 'FracGroup', copies)
        cls.q = Package(out / 'FracGroup.upk')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_prop_is_listed_in_the_columns_it_stands_by(self):
        q = self.q
        nc = self.m['nativeCopies']
        sec = {c['label']: c for c in nc['copies']}
        wall, prop = sec['Made']['export'], sec['Prop']['export']
        at = []
        for c in q.structs(q.own(wall, 'FragmentColumns')):
            b = struct.unpack('<6f', c[('Bounds', 0)]['value'][:24])
            names = [e[('DestructibleActor', 0)]['value'] for e in q.structs(c.get(('DestructibleCache', 0), {}).get('value'))]
            if prop in names:
                at.append([b[0], b[3], b[2], b[5]])
        self.assertTrue(at)
        box = self.prop_box
        for x0, x1, z0, z1 in at:
            # each column it is in meets its box grown by 24
            self.assertTrue(x0 < box[1] + 24 and x1 > box[0] - 24 and z0 < box[5] + 24 and z1 > box[4] - 24, (at, box))
        self.assertEqual([len(d['columns']) for d in nc['groupListings']], [len(at)])


class NeighbourRule(unittest.TestCase):
    """(M3 item 3) The game's rule for the neighbour lists (research/native/frac-neighbours.md): a column lists another
    piece's column when its box touches or overlaps that column's box cut to that piece's bounds grown by one."""

    def test_touching_counts_and_the_cut_is_the_other_pieces(self):
        import frac_walls
        a = [0, 96, -8, 8, 0, 192]
        self.assertTrue(frac_walls.lists_column(a, [96, 192, -8, 8, 0, 192], [None] * 6))          # touching
        self.assertFalse(frac_walls.lists_column(a, [97, 192, -8, 8, 0, 192], [None] * 6))
        # a top-storey column reaching over its piece: cut to the piece's top (100) grown by one, a column over it
        # isn't listed by it, but it lists that column (the one-way listings of F-69)
        tall = [0, 96, 8, 30, 192, 384]
        self.assertFalse(frac_walls.lists_column(tall, [0, 96, -8, 8, 0, 192], [None, None, None, None, 0, 100]))
        self.assertTrue(frac_walls.lists_column([0, 96, -8, 8, 0, 192], tall, [None] * 6))


@unittest.skipUnless(BAR.exists(), NO_BAR)
class JoinedMadeWalls(unittest.TestCase):
    """(M3 items 2 and 3) Made walls that meet, built in URB_Bar: an L (M1 along x, running through; M2 a quarter turn
    from its far end, butting) and a T's stem (M3) on the Bar's own inside wall XComDecoFracLevelActor_16 (along x at
    y 672). Their columns and the walls they touch list each other's by the game's rule, at the joint only."""
    MAP_WALL = 'XComDecoFracLevelActor_16'

    @classmethod
    def setUpClass(cls):
        import native_copy
        from package import Package
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name)

        def wall(label, at, yaw, ends=None):
            w = dict(x0=0.0, x1=384.0, openings=[], seed=3)
            gen = dict(kind='fracWall', version=1, wall=w)
            if ends:
                gen = dict(kind='fracWall', version=2, wall=dict(w, ends=ends))
            return dict(actor=DONOR, location=at, rotation=[0, yaw, 0], label=label, generated=gen)
        copies = [wall('M1', [-1536.0, 1440.0, 16.0], 0, ['free', 'through']),
                  wall('M2', [-1152.0, 1440.0, 16.0], 16384),
                  wall('M3', [-1440.0, 672.0, 16.0], 16384)]
        cls.m = native_copy.build(BAR, out, 'FracJoined', copies)
        cls.q = Package(out / 'FracJoined.upk')
        nc = cls.m['nativeCopies']
        cls.export = {c['label']: c['export'] for c in nc['copies']}
        cls.export[cls.MAP_WALL] = cls.q.by_name[PL + cls.MAP_WALL]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def columns(self, name):
        import native_copy
        q = self.q
        i = self.export[name]
        out = []
        for c in q.structs(q.own(i, 'FragmentColumns')):
            b = struct.unpack('<6f', c[('Bounds', 0)]['value'][:24])
            lists = [(e[('FracActor', 0)]['value'], e.get(('ColumnIndex', 0), {'value': 0})['value'])
                     for e in q.structs(c.get(('FracActorCache', 0), {}).get('value'))]
            out.append(dict(box=[b[0], b[3], b[1], b[4], b[2], b[5]], lists=lists))
        return out

    def test_the_through_wall_reaches_the_far_face(self):
        sec = {r['label']: r for r in self.m['nativeCopies']['generatedWalls']}
        self.assertAlmostEqual(sec['M1']['box'][1], -1152.0 + 8.0, 3)
        self.assertAlmostEqual(sec['M2']['box'][2], 1440.0 + 8.0, 3)        # butting on M1's face

    def test_the_l_and_the_t_list_each_other_at_the_joint_only(self):
        e = self.export
        listings = {(d['wall'], d['other']) for d in self.m['nativeCopies']['neighbourListings']}
        name = lambda i: self.q.name(i).split('.')[-1]  # noqa: E731
        self.assertIn((name(e['M1']), name(e['M2'])), listings)
        self.assertIn((name(e['M3']), self.MAP_WALL), listings)
        for a, b in (('M1', 'M2'), ('M2', 'M1'), ('M3', self.MAP_WALL), (self.MAP_WALL, 'M3')):
            cols = self.columns(a)
            hits = [k for k, c in enumerate(cols) if any(x == e[b] for x, _ in c['lists'])]
            self.assertTrue(hits, (a, b))
            # only the columns at the joint: reaching it or within the corner square's half of it
            joint = {'M1': -1152.0, 'M2': 1440.0, 'M3': 672.0, self.MAP_WALL: -1440.0}[a]
            axis = 1 if a in ('M2', 'M3') else 0
            for k in hits:
                box = cols[k]['box']
                self.assertLessEqual(max(box[2 * axis] - joint, joint - box[2 * axis + 1]), 8.0, (a, b, box))
        # M2 and M3 are far apart: nothing between them
        self.assertFalse(any(x == e['M3'] for c in self.columns('M2') for x, _ in c['lists']))

    def test_every_listing_follows_the_rule(self):
        import frac_walls
        e = self.export
        cols = {n: self.columns(n) for n in ('M1', 'M2', 'M3', self.MAP_WALL)}
        boxes = {r['label']: r['box'] for r in self.m['nativeCopies']['generatedWalls']}
        comp = self.q.own(e[self.MAP_WALL], 'FracturedStaticMeshComponent')
        bounds = {n: boxes[n] for n in ('M1', 'M2', 'M3')}
        bounds[self.MAP_WALL] = [None] * 4 + [self.q.own(comp, 'FragmentBoundsMinZ'), self.q.own(comp, 'FragmentBoundsMaxZ')]
        by_export = {e[n]: n for n in cols}
        for a, rows in cols.items():
            for c in rows:
                for actor, index in c['lists']:
                    b = by_export.get(actor)
                    if b is None or (a == self.MAP_WALL and b == self.MAP_WALL):
                        continue
                    self.assertTrue(frac_walls.lists_column(c['box'], cols[b][index]['box'], bounds[b]), (a, b, index))


@unittest.skipUnless(BAR.exists(), NO_BAR)
class MadeWallInBuilding(unittest.TestCase):
    """(M3 item 7) A made wall standing in one of the map's buildings is in that building's cutaway by the game
    editor's rule for its own box: the twin of URB_Bar's inside wall at the donor's own place lands in the floors the
    Bar lists the donor in, with the same CutdownFloor; a one-storey wall there in the ground floor only."""

    @classmethod
    def setUpClass(cls):
        import native_copy
        from package import Package
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name)
        pose = dict(location=[-1056.0, 864.0, 16.0], rotation=[0, 49152, 0])
        copies = [dict(actor=DONOR, label='Twin', generated=dict(kind='fracWall', version=1,
                                                                 wall=dict(x0=-384.0, x1=192.0, openings=[], seed=1)), **pose),
                  dict(actor=DONOR, label='Low', location=[-1152.0, 864.0, 16.0], rotation=[0, 49152, 0],
                       generated=dict(kind='fracWall', version=1, wall=dict(x0=-384.0, x1=192.0, openings=[], seed=2,
                                                                            storeys=1)))]
        cls.m = native_copy.build(BAR, out, 'FracInBuilding', copies)
        cls.p = Package(BAR)
        cls.q = Package(out / 'FracInBuilding.upk')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @staticmethod
    def listings(p, actor):
        out = {}
        level = p.by_name[PL[:-1]]
        for i in range(1, len(p.exports) + 1):
            if p.cls(i) != 'XComBuildingVolume' or p.exports[i - 1]['outer'] != level:
                continue
            for k, floor in enumerate(p.structs(p.own(i, 'Floors'))):
                for e in p.structs(floor.get(('m_aCachedActors', 0), {}).get('value')):
                    if e[('ResidentActor', 0)]['value'] == actor:
                        out.setdefault(p.name(i).split('.')[-1], []).append(
                            [k, e.get(('CutdownFloor', 0), {'value': 0})['value']])
        return out

    def test_the_twin_is_listed_where_the_donor_is(self):
        donor = self.listings(self.p, self.p.by_name[PL + DONOR])
        self.assertTrue(donor)
        sec = {c['label']: c['export'] for c in self.m['nativeCopies']['copies']}
        self.assertEqual(self.listings(self.q, sec['Twin']), donor)
        found = {d['wall']: d for d in self.m['nativeCopies']['madeWallFloors']}
        twin = found[self.q.name(sec['Twin']).split('.')[-1]]
        self.assertEqual({twin['building']: twin['floors']}, donor)

    def test_a_building_made_in_the_editor_takes_a_made_walls_own_box(self):
        import buildings
        box = [0.0, 96.0, -12.0, 12.0, 0.0, 208.0]
        self.assertEqual(buildings.piece_box(self.p, dict(source=self.p.by_name[PL + DONOR], box=box), {}), box)

    def test_a_one_storey_wall_is_in_the_ground_floor_only(self):
        sec = {c['label']: c['export'] for c in self.m['nativeCopies']['copies']}
        low = self.listings(self.q, sec['Low'])
        self.assertEqual([[k for k, _ in floors] for floors in low.values()], [[0]])


@unittest.skipUnless(BAR.exists(), NO_BAR)
class MadeSlabs(unittest.TestCase):
    """(M5) Slabs made from numbers in URB_Bar: a roof on a copy of the bar's roof (XComFracLevelActor_3) over a made wall, and an upper floor on a copy of the bar's upstairs strip
    (XComFracLevelActor_17, turned a half turn)."""
    ROOF, FLOOR = 'XComFracLevelActor_3', 'XComFracLevelActor_17'

    @classmethod
    def setUpClass(cls):
        import native_copy
        from package import Package
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name)
        copies = [dict(actor=cls.ROOF, label='Roof', location=[-1728.0, -1056.0, 400.0], rotation=[0, 0, 0],
                       generated=dict(kind='fracSlab', version=1,
                                      slab=dict(x0=0.0, x1=384.0, y0=0.0, y1=288.0, seed=4,
                                                holes=[dict(x0=96.0, x1=192.0, y0=96.0, y1=192.0)]))),
                  dict(actor=cls.FLOOR, label='Floor', location=[-1056.0, -768.0, 0.0], rotation=[0, 32768, 0],
                       generated=dict(kind='fracSlab', version=1,
                                      slab=dict(x0=0.0, x1=288.0, y0=480.0, y1=672.0, seed=5, look='floor'))),
                  dict(actor=DONOR, label='Under', location=[-1728.0, -960.0, 16.0], rotation=[0, 0, 0],
                       generated=dict(kind='fracWall', version=1, wall=dict(x0=0.0, x1=384.0, openings=[], seed=6)))]
        cls.m = native_copy.build(BAR, out, 'FracSlabs', copies)
        cls.p = Package(BAR)
        cls.q = Package(out / 'FracSlabs.upk')
        cls.sec = {c['label']: c['export'] for c in cls.m['nativeCopies']['copies']}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_slabs_are_made_with_their_own_mesh_and_keep_their_floor_flags(self):
        q = self.q
        for label in ('Roof', 'Floor'):
            actor = self.sec[label]
            comp = q.own(actor, 'FracturedStaticMeshComponent')
            self.assertTrue(q.name(q.own(comp, 'StaticMesh')).split('.')[-1].startswith('FracSlab_'), label)
            self.assertIsNone(q.own(comp, 'EditorPaintedVisibleFragments'))
            self.assertTrue(q.effective(actor, 'bPathColliding', False), label)
            self.assertTrue(q.effective(actor, 'bCanStepUpOn', False), label)
        rec = {r['label']: r for r in self.m['nativeCopies']['generatedWalls']}
        self.assertEqual(rec['Roof']['kind'], 'fracSlab')
        # the roof's box: x -1728 to -1344, y -1056 to -768, its plate 398 to 402
        for got, want in zip(rec['Roof']['box'], [-1728.0, -1344.0, -1056.0, -768.0, 398.0, 402.0]):
            self.assertAlmostEqual(got, want, 2)
        # the floor turned a half turn: its mesh's y 480 to 672 lies at y -1440 to -1248, its top at 194
        for got, want in zip(rec['Floor']['box'], [-1344.0, -1056.0, -1440.0, -1248.0, 192.0, 194.0]):
            self.assertAlmostEqual(got, want, 2)

    def test_a_slabs_columns_follow_the_slabs_rule(self):
        q = self.q
        cols = list(q.structs(q.own(self.sec['Roof'], 'FragmentColumns')))
        self.assertEqual(len(cols), 5 * 4)            # 4 by 3 tiles: a column a cell, the last row and column 1 wide
        boxes = [struct.unpack('<6f', c[('Bounds', 0)]['value'][:24]) for c in cols]
        # cells from the slab's corner less one unit, cut across to the fragments they list
        self.assertAlmostEqual(min(b[0] for b in boxes), -1728.0, 2)
        self.assertAlmostEqual(min(b[1] for b in boxes), -1056.0, 2)
        self.assertAlmostEqual(max(b[3] for b in boxes), -1344.0, 2)
        self.assertAlmostEqual(min(b[2] for b in boxes), 398.0 - 1.0, 2)

    def test_the_slabs_bring_cursor_floors_breaking_under_them(self):
        # (M5b, F-128) the bar's four map-wide cursor volumes are taken out and stand again round the slabs; over the
        # floor (192 to 194) the floors break at 190 and over the roof (398 to 402) at 396, 2 under each underside
        # (EXP-80 run G), the map's floor numbers kept
        import shell
        rec = self.m['nativeCopies']['madeCursors']
        self.assertEqual(len(rec['hidden']), 4)
        over = [a for a in rec['added'] if a['over']]

        def bands(foot):
            return sorted((round(a['box'][2]), round(a['box'][5]), a['floor']) for a in over
                          if all(abs(a['box'][k] - v) < 0.01 for k, v in zip((0, 1, 3, 4), foot)))
        self.assertEqual(bands([-1344.0, -1440.0, -1056.0, -1248.0]),
                         [(0, 190, 1), (190, 402, 2), (402, 594, 3), (594, 768, 4)])
        self.assertEqual(bands([-1728.0, -1056.0, -1344.0, -768.0]),
                         [(0, 210, 1), (210, 396, 2), (396, 594, 3), (594, 768, 4)])
        self.assertEqual(len(over), 8)
        # what the bar's volumes covered outside the slabs stands again at the same heights and floors
        for a in rec['added']:
            if not a['over']:
                self.assertIn((round(a['box'][2]), round(a['box'][5]), a['floor']),
                              [(0, 210, 1), (210, 402, 2), (402, 594, 3), (594, 768, 4)])
        # read back: the clones listed, the bar's own not
        q, live = self.q, shell.listed(self.q)
        listed = [i for i in shell.actors(q, 'XComCursorVolume') if i in live]
        self.assertEqual(sorted(q.name(i).split('.')[-1] for i in listed), sorted(a['copy'] for a in rec['added']))
        self.assertFalse(set(rec['hidden']) & {q.name(i).split('.')[-1] for i in listed})

    def test_the_wall_under_the_roof_and_the_roof_list_each_other(self):
        listings = {(d['wall'], d['other']) for d in self.m['nativeCopies']['neighbourListings']}
        name = lambda i: self.q.name(i).split('.')[-1]  # noqa: E731
        self.assertTrue((name(self.sec['Roof']), name(self.sec['Under'])) in listings
                        or (name(self.sec['Under']), name(self.sec['Roof'])) in listings, listings)


@unittest.skipUnless(DEMOLITION.exists(), NO_DEMOLITION)
class GroundOnBackdrop(unittest.TestCase):
    """(EXP-79 run D) A block made on URB_Demolition_EWI's grass plane (XComLevelActor_13), which saves its collision,
    its cover and bWorldGeometry off: the game walked a soldier into a block made from it and never put the cursor on
    its top. The copy collides, takes cover and is world geometry."""
    DONOR = 'XComLevelActor_13'

    def test_the_block_is_world_geometry_and_collides(self):
        import native_copy
        from package import Package
        p = Package(DEMOLITION)
        donor = p.by_name[PL + self.DONOR]
        self.assertIs(p.effective(donor, 'bWorldGeometry', None), False)
        with tempfile.TemporaryDirectory() as d:
            m = native_copy.build(DEMOLITION, Path(d), 'GroundOnBackdrop', [dict(
                actor=self.DONOR, label='Block', location=list(p.own(donor, 'Location', [0.0, 0.0, 0.0])),
                rotation=[0, 0, 0], generated=dict(kind='ground', version=1, ground=dict(
                    shape='block', x0=0.0, x1=192.0, y0=0.0, y1=192.0, height=64.0)))], bake=False)
            q = Package(Path(d) / 'GroundOnBackdrop.upk')
            (actor,) = [c['export'] for c in m['nativeCopies']['copies'] if c['label'] == 'Block']
            for name, want in (('bWorldGeometry', True), ('bCollideActors', True), ('bPathColliding', True),
                               ('bIgnoreForCover', False), ('bCanClimbOnto', True)):
                self.assertIs(q.effective(actor, name, None), want, name)
            comp = q.own(actor, 'StaticMeshComponent')
            self.assertIs(q.effective(comp, 'CollideActors', None), True)
            self.assertIs(q.effective(comp, 'BlockRigidBody', None), True)


@unittest.skipUnless(ALLEY.exists(), NO_ALLEY)
class GroundOnStaticMeshActor(unittest.TestCase):
    """(EXP-79 run D) A block made on URB_CommercialAlley's asphalt (StaticMeshActor_50), which saves bCanStepUpOn and
    its collision off: no soldier climbed onto a block made from it. The copy is an XComLevelActor (F-130) that can be
    stepped up on."""
    DONOR = 'StaticMeshActor_50'

    def test_the_block_can_be_stepped_up_on(self):
        import native_copy
        from package import Package
        p = Package(ALLEY)
        donor = p.by_name[PL + self.DONOR]
        self.assertIs(p.effective(donor, 'bCanStepUpOn', None), False)
        with tempfile.TemporaryDirectory() as d:
            m = native_copy.build(ALLEY, Path(d), 'GroundOnStaticMeshActor', [dict(
                actor=self.DONOR, label='Block', location=list(p.own(donor, 'Location', [0.0, 0.0, 0.0])),
                rotation=[0, 0, 0], generated=dict(kind='ground', version=1, ground=dict(
                    shape='block', x0=0.0, x1=192.0, y0=0.0, y1=192.0, height=64.0)))], bake=False)
            q = Package(Path(d) / 'GroundOnStaticMeshActor.upk')
            (actor,) = [c['export'] for c in m['nativeCopies']['copies'] if c['label'] == 'Block']
            self.assertEqual(q.cls(actor), 'XComLevelActor')
            self.assertIs(q.effective(actor, 'bCanStepUpOn', None), True)
            self.assertIs(q.effective(actor, 'bCollideActors', None), True)


@unittest.skipUnless(BAR.exists(), NO_BAR)
class GroundShapes(unittest.TestCase):
    """(M6) Ground shapes made from numbers in URB_Bar, baked: a block and a ramp on copies of the bar's asphalt plane
    (XComLevelActor_131, an XComLevelActor whose component has its archetype's mesh and saves none)."""
    DONOR = 'XComLevelActor_131'
    SMALL_ATLAS = 'StaticMeshActor_117'

    @classmethod
    def setUpClass(cls):
        import native_copy
        from package import Package
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name)
        copies = [dict(actor=cls.DONOR, label='Block', location=[-1728.0, -1440.0, 0.0], rotation=[0, 0, 0],
                       generated=dict(kind='ground', version=1,
                                      ground=dict(shape='block', x0=0.0, x1=192.0, y0=0.0, y1=96.0, height=64.0))),
                  dict(actor=cls.DONOR, label='Ramp', location=[-1440.0, -1440.0, 0.0], rotation=[0, 0, 0],
                       generated=dict(kind='ground', version=1,
                                      ground=dict(shape='ramp', x0=0.0, x1=288.0, y0=0.0, y1=96.0, height=64.0))),
                  # the plain asphalt look's donor: a street block beyond the play area, whose atlas (32 texels) is
                  # smaller than a block's rectangle at the recipe's density
                  dict(actor=cls.SMALL_ATLAS, label='Plain', location=[-1152.0, -1440.0, 0.0], rotation=[0, 0, 0],
                       generated=dict(kind='ground', version=1,
                                      ground=dict(shape='block', x0=0.0, x1=96.0, y0=0.0, y1=96.0, height=96.0,
                                                  look='plain-asphalt'))),
                  # (M6 item 6) a rock, its collision its own hull
                  dict(actor=cls.DONOR, label='Rock', location=[-960.0, -1440.0, 0.0], rotation=[0, 0, 0],
                       generated=dict(kind='ground', version=1,
                                      ground=dict(shape='rock', x0=0.0, x1=192.0, y0=0.0, y1=96.0, height=96.0, seed=7)))]
        cls.m = native_copy.build(BAR, out, 'Ground', copies, bake=True, cache='Ground_Lighting')
        cls.p = Package(BAR)
        cls.q = Package(out / 'Ground.upk')
        cls.sec = {c['label']: c['export'] for c in cls.m['nativeCopies']['copies']}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_each_is_a_plain_mesh_of_its_own_with_one_collision_element(self):
        q = self.q
        for label, prefix in (('Block', 'Ground_block_2x1_'), ('Ramp', 'Ground_ramp_3x1_')):
            comp = q.own(self.sec[label], 'StaticMeshComponent')
            mesh = q.own(comp, 'StaticMesh')
            self.assertEqual(q.cls(mesh), 'StaticMesh')
            self.assertTrue(q.name(mesh).split('.')[-1].startswith(prefix), q.name(mesh))
            # one convex element (test_cover_blocks.hull reads it): a box's six planes, a ramp's wedge's five
            import test_cover_blocks
            *_, fields = test_cover_blocks.hull(q, q.own(mesh, 'BodySetup'))
            self.assertEqual(len(fields['FacePlaneData']), 6 if label == 'Block' else 5)
            # the donor's material stays bound by the component
            self.assertEqual(q.effective(comp, 'Materials', None), self.p.effective(self.p.own(self.p.by_name[PL + self.DONOR],
                                                                                              'StaticMeshComponent'), 'Materials', None))

    def test_its_box_light_and_shadow(self):
        rec = {r['label']: r for r in self.m['nativeCopies']['generatedWalls']}
        self.assertEqual(rec['Block']['kind'], 'ground')
        self.assertEqual([round(v, 2) for v in rec['Block']['box']], [-1728.0, -1536.0, -1440.0, -1344.0, 0.0, 64.0])
        self.assertEqual([round(v, 2) for v in rec['Ramp']['box']], [-1440.0, -1152.0, -1440.0, -1344.0, 0.0, 64.0])
        for r in rec.values():
            self.assertEqual(r['light']['kind'], 'rect')
            self.assertTrue(r['shadowMap']['own'])
            self.assertEqual(r['columns'], 0)

    def test_a_rock_collides_as_its_hull(self):
        import ground
        import test_cover_blocks
        q = self.q
        mesh = q.own(q.own(self.sec['Rock'], 'StaticMeshComponent'), 'StaticMesh')
        self.assertTrue(q.name(mesh).split('.')[-1].startswith('Ground_rock_2x1_'), q.name(mesh))
        *_, fields = test_cover_blocks.hull(q, q.own(mesh, 'BodySetup'))
        rock = dict(shape='rock', x0=0.0, x1=192.0, y0=0.0, y1=96.0, height=96.0, seed=7)
        self.assertEqual(len(fields['FacePlaneData']), len(ground.corners_and_faces(rock)[1]))
        rec = {r['label']: r for r in self.m['nativeCopies']['generatedWalls']}
        lo, hi = rec['Rock']['box'][0::2], rec['Rock']['box'][1::2]
        self.assertTrue(lo[0] >= -960.0 and hi[0] <= -768.0 and lo[1] >= -1440.0 and hi[1] <= -1344.0, rec['Rock']['box'])
        self.assertAlmostEqual(hi[2], 96.0, 2)

    def test_its_lightmap_rectangle_fits_its_atlas(self):
        # a rectangle bigger than the donor's atlas is scaled down to fit (the relight skipped it before)
        rec = {r['label']: r for r in self.m['nativeCopies']['generatedWalls']}
        comp = self.q.own(self.sec['Plain'], 'StaticMeshComponent')
        aw, ah = frac_walls.atlas_size(self.q, comp)
        w, h = rec['Plain']['light']['rect']
        self.assertLessEqual(w, aw)
        self.assertLessEqual(h, ah)
        self.assertEqual(tuple(rec['Plain']['lightmapRect']), (w, h))
        self.assertEqual(frac_walls.fit_rect((16, 56), (32, 32)), (9, 32))
        self.assertEqual(frac_walls.fit_rect((16, 24), (32, 32)), (16, 24))

    def test_it_collides_whatever_its_donor_saves(self):
        # (many ground donors are backdrop planes saved with their collision off: native_copy.ground_collision)
        q = self.q
        for label in ('Block', 'Ramp'):
            actor = self.sec[label]
            self.assertIs(q.effective(actor, 'bCollideActors', None), True)
            self.assertIs(q.effective(actor, 'bPathColliding', None), True)
            comp = q.own(actor, 'StaticMeshComponent')
            self.assertIs(q.effective(comp, 'CollideActors', None), True)
            self.assertIs(q.effective(comp, 'BlockRigidBody', None), True)

    def test_its_vertices_take_the_donors_main_painted_colour(self):
        import gen_mesh
        q = self.q
        mesh = q.own(q.own(self.sec['Block'], 'StaticMeshComponent'), 'StaticMesh')
        colours = {bytes(c) for c in gen_mesh.read(q, mesh)['lods'][0]['colours']}
        self.assertEqual(colours, {bytes.fromhex('ecf4f8f6')})      # the asphalt's main painted colour (ground_measure's too)


class StagedDoorInMadeWall(unittest.TestCase):
    """(M3 item 4) A door of another map in a made wall's doorway: URB_Bar's door 7 and its frame brought to
    URB_PoliceStation with the wall's donor (transplant.stage_edit), nothing there listing them, are listed by
    frac_walls.door_columns in the made wall's columns within a tile of the door, on every storey."""
    DOOR = ['XComInteractiveLevelActor_7', 'XComDestructibleActor_65']

    @classmethod
    def setUpClass(cls):
        import native_copy
        import transplant
        sys.path.insert(0, str(TOOLS / 'editor'))
        import schema as schema_module
        from package import Package
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name)
        schema = schema_module.Schema(schema_module.build(BAR.parent))
        donor = dict(package='URB_Bar', sha256=transplant.sha256(BAR))
        copies = [dict(actor=DONOR, donor=donor, location=[0.0, 0.0, 16.0], rotation=[0, 0, 0], label='Made',
                       generated=dict(kind='fracWall', version=1, wall=dict(
                           x0=0.0, x1=384.0, openings=[dict(x0=96.0, x1=192.0, z0=-16.0, z1=160.0)], seed=6)))]
        for n in cls.DOOR:
            copies.append(dict(actor=n, donor=donor, location=[144.0, 0.0, 16.0], rotation=[0, 0, 0],
                               assembly='add:XComInteractiveLevelActor_7_copy', family='door'))
        cls.staged, cls.edit, _ = transplant.stage_edit(POLICE, out, dict(copies=copies), schema=schema)
        cls.m = native_copy.build(cls.staged, out / 'build', 'FracStagedDoor', cls.edit['copies'])
        cls.q = Package(out / 'build' / 'FracStagedDoor.upk')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_door_and_its_frame_are_listed_by_the_doorway(self):
        q = self.q
        nc = self.m['nativeCopies']
        wall = next(c['export'] for c in nc['copies'] if c.get('generated') == 'fracWall')
        doors = [c['export'] for c in nc['copies'] if c.get('family') == 'door' or c['actor'] in self.DOOR]
        self.assertEqual(len(doors), 2, nc['copies'])
        listed, near = {}, []
        for c in q.structs(q.own(wall, 'FragmentColumns')):
            b = struct.unpack('<6f', c[('Bounds', 0)]['value'][:24])
            box = (round(b[0]), round(b[3]), round(b[2]), round(b[5]))
            if b[0] < 287:
                near.append(box)            # the doorway's tile (96 to 192) and one tile each side
            for e in q.structs(c.get(('DestructibleCache', 0), {}).get('value')):
                listed.setdefault(e[('DestructibleActor', 0)]['value'], []).append(box)
        # every storey of the station's grid the wall reaches (three: it stands 400 tall)
        self.assertEqual(len(near), 9)
        for d in doors:
            self.assertEqual(sorted(listed.get(d, [])), sorted(near), q.name(d))
        self.assertEqual(sorted(len(d['columns']) for d in nc.get('doorListings', [])), [9, 9])


class StagedDonor(unittest.TestCase):
    """A made wall on a map without the Bar's wall (custom geometry plan, M1 item 1): the donor brought from URB_Bar
    as any piece of another map is (transplant.stage_edit), then the copy made from numbers through the staged actor:
    the custom wall, and a second one along y (a quarter turn from the donor's yaw, its columns along y), on
    URB_PoliceStation."""
    WALLS = [dict(location=[0.0, 0.0, 16.0], rotation=[0, 0, 0], label='Along x',
                  generated=COPIES[2]['generated']),
             dict(location=[384.0, 0.0, 16.0], rotation=[0, 16384, 0], label='Along y',
                  generated=dict(kind='fracWall', version=1, wall=dict(x0=0.0, x1=288.0, openings=[
                      dict(x0=96.0, x1=192.0, z0=72.0, z1=168.0)], seed=3)))]

    @classmethod
    def setUpClass(cls):
        import native_copy
        import transplant
        sys.path.insert(0, str(TOOLS / 'editor'))
        import schema as schema_module
        from package import Package
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name)
        schema = schema_module.Schema(schema_module.build(BAR.parent))
        edit = dict(copies=[dict(w, actor=DONOR, donor=dict(package='URB_Bar', sha256=transplant.sha256(BAR)))
                            for w in cls.WALLS])
        cls.staged, cls.edit, cls.report = transplant.stage_edit(POLICE, out, edit, schema=schema)
        cls.m = native_copy.build(cls.staged, out / 'build', 'FracStaged', cls.edit['copies'])
        cls.q = Package(out / 'build' / 'FracStaged.upk')
        cls.grid = native_copy.level_grid(cls.q)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_donor_is_staged_and_both_walls_are_made_from_numbers(self):
        self.assertEqual(self.report['donors'][0]['map'], 'URB_Bar')
        self.assertTrue(all(c['staged'] for c in self.edit['copies']))
        walls = self.m['nativeCopies']['generatedWalls']
        self.assertEqual([(w['kind'], w['label']) for w in walls], [('fracWall', 'Along x'), ('fracWall', 'Along y')])
        for w in walls:
            mesh = self.q.by_name[w['mesh']]
            self.assertEqual(self.q.cls(mesh), 'FracturedStaticMesh')
            self.assertTrue(w['painted'])

    def test_each_wall_stands_where_it_was_put_with_its_columns_along_it(self):
        q = self.q
        for w, spec in zip(self.m['nativeCopies']['generatedWalls'], self.WALLS):
            actor = q.by_name[PL + w['copy']]
            self.assertEqual([round(v, 1) for v in q.own(actor, 'Location')], spec['location'])
            box = w['box']
            along = 0 if spec['rotation'][1] == 0 else 1
            length = spec['generated']['wall']['x1']
            # the solid, 8 in from each tile edge, along the wall's axis from its start
            self.assertAlmostEqual(box[2 * along], spec['location'][along] + 8, 3)
            self.assertAlmostEqual(box[2 * along + 1], spec['location'][along] + length - 8, 3)
            cols = q.structs(q.own(actor, 'FragmentColumns'))
            self.assertEqual(len(cols), w['columns'])
            for c in cols:
                b = struct.unpack('<6fB', c[('Bounds', 0)]['value'])
                lo, hi = (b[0], b[1]), (b[3], b[4])
                self.assertLessEqual(hi[along] - lo[along], frac_walls.TILE + 1e-3)     # a tile along the wall
                self.assertLess(hi[1 - along] - lo[1 - along], 30)                   # the wall's thickness across



@unittest.skipUnless(BAR.exists(), NO_BAR)
class Broken(unittest.TestCase):
    """(custom geometry editing plan, B5) A made wall and roof built broken by their blasts in URB_Bar: their components
    save EditorPaintedVisibleFragments (one int a fragment, 0 for those the blasts knock out) and DestroyedChunks (the
    hidden fragments' boxes), as the game's maps save painted-out pieces; a whole copy of the bar's roof, which saves
    its own array (all 81 shown), saves neither (the donor's say nothing of the made mesh's)."""
    ROOF = 'XComFracLevelActor_3'
    WALL = dict(x0=0.0, x1=384.0, openings=[], seed=6)
    SLAB = dict(x0=0.0, x1=384.0, y0=0.0, y1=288.0, seed=4, holes=[])
    BLAST = [dict(at=[192.0, 12.0, 100.0], radius=96.0)]
    ROOF_BLAST = [dict(at=[192.0, 144.0, 0.0], radius=96.0)]

    @classmethod
    def setUpClass(cls):
        import native_copy
        from package import Package
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name)
        copies = [dict(actor=DONOR, label='Wall', location=[-1728.0, -960.0, 16.0], rotation=[0, 0, 0],
                       generated=dict(kind='fracWall', version=1, wall=cls.WALL, blasts=cls.BLAST)),
                  dict(actor=cls.ROOF, label='Roof', location=[-1728.0, -1056.0, 400.0], rotation=[0, 0, 0],
                       generated=dict(kind='fracSlab', version=1, slab=cls.SLAB, blasts=cls.ROOF_BLAST)),
                  dict(actor=cls.ROOF, label='Whole', location=[-1344.0, -1056.0, 400.0], rotation=[0, 0, 0],
                       generated=dict(kind='fracSlab', version=1, slab=dict(cls.SLAB, seed=5)))]
        cls.m = native_copy.build(BAR, out, 'FracBroken', copies)
        cls.q = Package(out / 'FracBroken.upk')
        cls.sec = {c['label']: c['export'] for c in cls.m['nativeCopies']['copies']}
        cls.rec = {r['label']: r for r in cls.m['nativeCopies']['generatedWalls']}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def arrays(self, label):
        q = self.q
        comp = q.own(self.sec[label], 'FracturedStaticMeshComponent')
        return q.own(comp, 'EditorPaintedVisibleFragments'), q.own(comp, 'DestroyedChunks')

    def test_the_broken_pieces_save_their_painted_fragments(self):
        import made_blasts
        for label, built, blasts in (('Wall', frac_wall.build(self.WALL), self.BLAST),
                                     ('Roof', __import__('frac_slab').build(self.SLAB), self.ROOF_BLAST)):
            visible, chunks = self.arrays(label)
            n = self.rec[label]['fragments']
            count, *values = struct.unpack('<%di' % (n + 1), visible)
            gone = [k for k, v in enumerate(values) if v == 0]
            self.assertEqual(count, n, label)
            self.assertEqual(gone, made_blasts.hidden(built, blasts), label)
            self.assertEqual(self.rec[label]['broken'], len(gone))
            self.assertTrue(0 < len(gone) < n, label)
            self.assertEqual(struct.unpack_from('<i', chunks)[0], len(gone))
            self.assertEqual(len(chunks), 4 + 25 * len(gone))
            for k, i in enumerate(gone):
                box = struct.unpack_from('<6f', chunks, 4 + 25 * k)
                want = built['fragments'][i]['box']
                for got, w in zip((box[0], box[3], box[1], box[4], box[2], box[5]), want):
                    self.assertAlmostEqual(got, w, places=2)

    def test_a_whole_copy_saves_neither(self):
        self.assertEqual(self.arrays('Whole'), (None, None))
        self.assertFalse(self.rec['Whole'].get('broken'))

    def test_the_export_reads_the_mask(self):
        # the viewer's export (export.py component) draws a component with the array saved: its count the mesh's
        q = self.q
        comp = q.own(self.sec['Wall'], 'FracturedStaticMeshComponent')
        mesh = gen_mesh.read(q, q.own(comp, 'StaticMesh'))
        visible = q.effective(comp, 'EditorPaintedVisibleFragments')
        self.assertEqual(struct.unpack_from('<i', visible)[0], len(mesh['fractured']['fragments']))
        self.assertEqual(len(visible), 4 + 4 * len(mesh['fractured']['fragments']))


class MapBroken(unittest.TestCase):
    """(custom geometry editing plan, E6) URB_Bar's XComFracLevelActor_5 (which paints one of its 29 fragments out)
    broken by a blast where it stands and on a moved copy: each component saves the fragments the blast reaches
    painted out with that one, and DestroyedChunks the hidden fragments' bounds; the piece's tiles are rebuilt; a
    piece that doesn't break, or that the map hasn't, is an error."""
    ROOF = 'XComFracLevelActor_5'

    @classmethod
    def setUpClass(cls):
        import made_blasts
        import native_copy
        from package import Package
        p = Package(BAR)
        roof = p.by_name[native_copy.PL + cls.ROOF]
        comp = p.own(roof, 'FracturedStaticMeshComponent')
        mesh = gen_mesh.read(p, p.effective(comp, 'StaticMesh'))
        cls.frags = mesh['fractured']['fragments']
        shown = made_blasts.shown_of(p.effective(comp, 'EditorPaintedVisibleFragments'), len(cls.frags))
        cls.before = {i for i, s in enumerate(shown) if not s}
        centres = made_blasts.fragment_centres(mesh['lods'][0], len(cls.frags))
        # a blast on the middle of the first fragment the map shows
        first = next(i for i, s in enumerate(shown) if s and centres[i] is not None)
        cls.blasts = [dict(at=[round(v, 3) for v in centres[first]], radius=64.0)]
        cls.knocked = set(made_blasts.hidden_at(centres, cls.blasts)) - cls.before
        cls.want = sorted(cls.before | cls.knocked)
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name)
        copies = [dict(actor=cls.ROOF, label='Moved', location=[-1344.0, -1056.0, 400.0], rotation=[0, 0, 0],
                       blasts=cls.blasts)]
        cls.m = native_copy.build(BAR, out, 'FracMapBroken', copies,
                                  piece_blasts=[dict(name=cls.ROOF, blasts=cls.blasts)])
        cls.q = Package(out / 'FracMapBroken.upk')
        cls.moved = {c['label']: c['export'] for c in cls.m['nativeCopies']['copies']}['Moved']
        cls.roof = cls.q.by_name[native_copy.PL + cls.ROOF]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def check(self, actor):
        q = self.q
        comp = q.own(actor, 'FracturedStaticMeshComponent')
        visible, chunks = q.own(comp, 'EditorPaintedVisibleFragments'), q.own(comp, 'DestroyedChunks')
        n = len(self.frags)
        count, *values = struct.unpack('<%di' % (n + 1), visible)
        self.assertEqual(count, n)
        self.assertEqual([k for k, v in enumerate(values) if v == 0], self.want)
        self.assertEqual(struct.unpack_from('<i', chunks)[0], len(self.want))
        self.assertEqual(len(chunks), 4 + 25 * len(self.want))
        for k, i in enumerate(self.want):
            got = struct.unpack_from('<6f', chunks, 4 + 25 * k)
            b = self.frags[i]['bounds']
            for j in range(3):
                self.assertAlmostEqual(got[j], b[j] - b[j + 3], places=2)
                self.assertAlmostEqual(got[j + 3], b[j] + b[j + 3], places=2)

    def test_the_blast_knocks_out_fragments_the_map_shows(self):
        self.assertEqual(len(self.before), 1)
        self.assertTrue(self.knocked)

    def test_the_roof_is_broken_where_it_stands(self):
        self.check(self.roof)
        rec = self.m['nativeCopies']['pieceBlasts']
        (piece,) = rec['inPlace']
        self.assertEqual((piece['label'], piece['knocked'], piece['hidden']), (self.ROOF, len(self.knocked), len(self.want)))
        self.assertTrue(rec['tiles'])

    def test_the_moved_copy_is_broken(self):
        self.check(self.moved)
        (piece,) = self.m['nativeCopies']['pieceBlasts']['onCopies']
        self.assertEqual((piece['label'], piece['knocked']), ('Moved', len(self.knocked)))

    def test_a_piece_that_does_not_break_is_an_error(self):
        import native_copy
        from package import Package
        p = Package(BAR)
        plain = next(p.name(i).split('.')[-1] for i in range(1, len(p.exports) + 1)
                     if p.cls(i) == 'StaticMeshActor' and p.name(i).startswith(native_copy.PL))
        with tempfile.TemporaryDirectory() as tmp:
            for name in (plain, 'XComFracLevelActor_99999'):
                with self.assertRaises(ValueError, msg=name):
                    native_copy.build(BAR, Path(tmp), 'FracMapBad', [], piece_blasts=[dict(name=name, blasts=self.blasts)])


if __name__ == '__main__':
    unittest.main()

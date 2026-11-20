"""Cover blocks made from a recipe (cover_blocks.py): a hidden XComLevelActor on a box mesh of the block's size.

The recipe and geometry checks run anywhere. The map-backed checks read the configured install (tools/viewer/settings.py)
and skip without it: URB_Bar, where blocks are built, and LWR's patch_policestation.upk, whose hidden cover helpers
(XComLevelActor_0 on CoverPatch.highcover, high cover; XComLevelActor_2 on CoverPatch.Cover2x4, low cover) the recipe
was checked against. Nothing is read from LWR's patch to build a block; the patch is only the reference here."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(TOOLS / 'upk'))
sys.path.insert(0, str(TOOLS / 'viewer'))
import cover_blocks  # noqa: E402
import native_copy  # noqa: E402
import audit_lighting as lighting  # noqa: E402
import mesh as viewer_mesh  # noqa: E402
import package_grow  # noqa: E402
import props as legacy_props  # noqa: E402

sys.path.insert(0, str(TOOLS / 'lab'))
import labpaths  # noqa: E402

BAR, NO_BAR = labpaths.test_file('XCOM_BAR_UPK', labpaths.lwr_cooked('URB_Bar.upk'), 'URB_Bar.upk')
POLICE, NO_POLICE = labpaths.test_file('XCOM_POLICE_UPK', labpaths.lwr_cooked('URB_PoliceStation.upk'),
                                       'URB_PoliceStation.upk')
PATCH, NO_PATCH = labpaths.test_file('XCOM_POLICE_PATCH_UPK', labpaths.lwr_cooked('patch_policestation.upk'),
                                     'patch_policestation.upk')
# recipe version 1 as checked; a change to it is a new version
DIGEST_1 = 'e5d998b0361d4cd7e28eb2efcd4efb6450d34629e7cfad26c7a26b7c776ac50e'
# the block that breaks with its group (cover_blocks.BREAKING), version 1
BREAKING_DIGEST_1 = '4818e1ccd5f27e3a983be9550ff00162947d64d78c81ac5eebed122576eff59b'
# version 2, with the blocker (15 November 2026, Discord feedback S6), and its breaking block
DIGEST_2 = 'c123918f9ff0c42cc66014d69bf11dac0d7d60e2aae2314b60338002531da63c'
BREAKING_DIGEST_2 = '0ae8de32bf9c537c933aa9f6dfffcf1ecc0db397899e22be367ba1d969e7b861'
PL = 'TheWorld.PersistentLevel.'
HIGH = dict(name='CoverBlock_copy1', kind='high', location=[-1824.0, -960.0, 0.0], rotation=[0, 0, 0], size=[96.0, 96.0],
            heights=[-12.0, 96.0], box=[-1824.0, -1728.0, -960.0, -864.0, -12.0, 96.0])
LOW = dict(name='CoverBlock_copy2', kind='low', location=[-1536.0, -960.0, 0.0], rotation=[0, 16384, 0],
           size=[192.0, 96.0], heights=[-12.0, 84.0], box=[-1632.0, -1536.0, -960.0, -768.0, -12.0, 84.0])
# an invisible floor, 3 x 2 tiles, turned a quarter, its top at 40; a high block two tiles tall
FLOOR = dict(name='InvisibleFloor_copy4', kind='floor', location=[-1248.0, -960.0, 40.0], rotation=[0, 16384, 0],
             size=[288.0, 192.0], heights=[-2.0, 0.0], box=[-1440.0, -1248.0, -960.0, -672.0, 38.0, 40.0])
TALL = dict(name='CoverBlock_copy5', kind='high', location=[-1824.0, -768.0, 0.0], rotation=[0, 0, 0], size=[96.0, 96.0],
            heights=[-12.0, 192.0], box=[-1824.0, -1728.0, -768.0, -672.0, -12.0, 192.0])
HIGH2 = dict(HIGH, name='CoverBlock_copy3', location=[-1824.0, -576.0, 0.0], box=[-1824.0, -1728.0, -576.0, -480.0, -12.0, 96.0])
# a blocker (recipe version 2, Discord feedback S6): the high block's box with no cover; and one that breaks with a group
BLOCK = dict(name='Blocker_copy6', kind='block', version=2, location=[-1632.0, -576.0, 0.0], rotation=[0, 0, 0],
             size=[96.0, 96.0], heights=[-12.0, 96.0], box=[-1632.0, -1536.0, -576.0, -480.0, -12.0, 96.0])
BLOCK2 = dict(BLOCK, name='Blocker_copy7', location=[-1440.0, -576.0, 0.0], box=[-1440.0, -1344.0, -576.0, -480.0, -12.0, 96.0])


def faces(positions, indices):
    """{(axis, plane, facing): triangle count}: the box face each triangle lies on and which way its winding faces
    (the sign of cross(b - a, c - a) along that axis). Two boxes split a face along either diagonal alike."""
    out = {}
    for k in range(0, len(indices), 3):
        a, b, c = [positions[i] for i in indices[k:k + 3]]
        axis = next(x for x in range(3) if a[x] == b[x] == c[x])
        cross = cover_blocks._cross(cover_blocks._sub(b, a), cover_blocks._sub(c, a))
        key = (axis, round(a[axis], 3), cross[axis] > 0)
        out[key] = out.get(key, 0) + 1
    return out


def native_layout(b, at):
    """The parts of a cooked box mesh's native data from `at`: (fields by name, the offset after LOD 0)."""
    r = lighting.Reader(b, at)
    f = dict(bounds=r.unpack('7f'), bodySetup=r.i32(), root=r.unpack('6f'))
    f['nodes'] = r.array_bytes()
    f['tris'] = r.array_bytes()
    f['version'] = r.unpack('2i')
    f['optimisation'] = r.take(r.count() * 7)
    f['simplified'] = r.i32()
    f['lods'] = r.count()
    f['bulk'] = r.unpack('4i')
    f['bulkEnd'] = r.pos
    f['sections'] = []
    for _ in range(r.count()):
        f['sections'].append((r.unpack('4i4Ii'), [r.unpack('2i') for _ in range(r.count())], r.take(1)))
    f['positionsHead'] = r.unpack('2I')
    stride, count, pos = r.array_bytes()
    f['positions'] = [struct.unpack_from('<3f', pos, 12 * k) for k in range(count)]
    f['vertexHead'] = r.unpack('4I')
    stride, count, verts = r.array_bytes()
    f['vertices'] = [verts[stride * k:stride * (k + 1)] for k in range(count)]
    f['colours'] = r.unpack('2I')
    f['count'] = r.u32()
    stride, count, idx = r.array_bytes()
    f['indices'] = list(struct.unpack(f'<{count}H', idx))
    f['rest'] = b[r.pos:]
    return f


RAW = {'Vector': '3f', 'Plane': '4f', 'Box': '6fB'}


def tagged(p, b, at=0):
    """[(name, kind, value)] of tagged properties in b from `at` up to None: a struct of plain fields as a list, of
    tagged fields as tagged(); an array as (count, raw elements)."""
    out = []
    while True:
        name = p.names[struct.unpack_from('<i', b, at)[0]]
        if name == 'None':
            return out
        kind = p.names[struct.unpack_from('<i', b, at + 8)[0]]
        size = struct.unpack_from('<i', b, at + 16)[0]
        at += 24
        if kind == 'StructProperty':
            sname = p.names[struct.unpack_from('<i', b, at)[0]]
            at += 8
            body = b[at:at + size]
            out.append((name, sname, list(struct.unpack('<' + RAW[sname], body)) if sname in RAW else tagged(p, body)))
        elif kind == 'ArrayProperty':
            out.append((name, kind, (struct.unpack_from('<i', b, at)[0], b[at + 4:at + size])))
        elif kind == 'BoolProperty':
            out.append((name, kind, b[at]))
            at += 1
            continue
        else:
            out.append((name, kind, b[at:at + size]))
        at += size


def hull(p, body_setup):
    """An RB_BodySetup's (version, [its tagged property names], its one convex element's fields as convex_hull gives
    them)."""
    props = tagged(p, export_bytes(p, body_setup), legacy_props.props_start(p.data, p.exports[body_setup - 1], p.names)
                   - p.exports[body_setup - 1]['off'])
    named = {n: v for n, _, v in props}
    version = struct.unpack('<i', named['PreCachedPhysDataVersion'])[0]
    [(top, _, (count, elems))] = named['AggGeom']
    assert top == 'ConvexElems' and count == 1
    fmts = dict(VertexData='3f', PermutedVertexData='4f', FaceTriData='i', EdgeDirections='3f',
                FaceNormalDirections='3f', FacePlaneData='4f')
    out = {}
    for name, kind, value in tagged(p, elems):
        if name == 'ElemBox':
            out[name] = [value[:3], value[3:6], value[6]]
        else:
            n, raw = value
            size = struct.calcsize('<' + fmts[name])
            rows = [list(struct.unpack_from('<' + fmts[name], raw, size * k)) for k in range(n)]
            out[name] = [r[0] for r in rows] if fmts[name] == 'i' else rows
    return version, [n for n, _, _ in props], out


def export_bytes(p, i):
    e = p.exports[i - 1]
    return bytes(p.data[e['off']:e['off'] + e['size']])


def props_list(p, i):
    """[(name, kind, struct or enum name, raw value)] of an export's tagged properties, in order."""
    e = p.exports[i - 1]
    b = export_bytes(p, i)
    start = legacy_props.props_start(p.data, e, p.names) - e['off']
    w = native_copy.Walker(p)
    return [(prop, kind, sub, b[v:v + size]) for prop, kind, sub, v, size in w.walk(b, start, len(b))]


class Recipe(unittest.TestCase):
    def test_the_body_setup_template_uses_a_static_mesh_parent(self):
        classes = ['SkeletalMesh', 'RB_BodySetup', 'StaticMesh', 'RB_BodySetup']
        package = SimpleNamespace(exports=[dict(outer=i) for i in (0, 1, 0, 3)],
                                  cls=lambda i: classes[i - 1] if i else '')
        self.assertEqual(cover_blocks._template(None, package, 'RB_BodySetup', outer_class='StaticMesh'), 4)

    def test_versions(self):
        self.assertEqual(sorted(cover_blocks.RECIPES), [1, 2])
        with self.assertRaises(ValueError):
            cover_blocks.recipe(3)
        self.assertEqual(cover_blocks.recipe_digest(1), DIGEST_1)
        self.assertEqual(cover_blocks.recipe_digest(2), DIGEST_2)

    def test_version_2_is_version_1_and_the_blocker(self):
        """Version 2 adds one kind and changes nothing else: a blocker forces no cover, is ignored for cover (so the
        cover trace skips it, F-82), is neither climbed onto nor a destination, and lets units see past it."""
        one, two = cover_blocks.recipe(1), cover_blocks.recipe(2)
        self.assertEqual({k: v for k, v in two.items() if k != 'kinds'}, {k: v for k, v in one.items() if k != 'kinds'})
        self.assertEqual({k: v for k, v in two['kinds'].items() if k != 'block'}, one['kinds'])
        self.assertEqual(two['kinds']['block'], {'force': None, 'visibility': [['bBlockUnitVisibility', 'bool', False]],
                                                 'climb': False, 'destination': False, 'ignore': True, 'cell': None})

    def test_the_box_has_four_vertices_a_face_and_front_faces_outward(self):
        lo, hi = [0.0, 0.0, -12.0], [192.0, 96.0, 84.0]
        verts, tris = cover_blocks.box_geometry(lo, hi)
        self.assertEqual((len(verts), len(tris)), (24, 12))
        for a, b, c in tris:
            n = verts[a][1]
            self.assertEqual(n, verts[b][1])
            cross = cover_blocks._cross(cover_blocks._sub(verts[b][0], verts[a][0]), cover_blocks._sub(verts[c][0], verts[a][0]))
            self.assertLess(sum(x * y for x, y in zip(cross, n)), 0)     # UE3's front faces, as the cooked boxes
        for p, *_ in verts:
            self.assertTrue(all(v in (l, h) for v, l, h in zip(p, lo, hi)))

    def test_mesh_names_carry_the_size(self):
        self.assertEqual(cover_blocks.mesh_name([0, 0, -12], [192, 96, 84]), 'Box_192x96_m12_84')
        self.assertEqual(cover_blocks.mesh_name([0, 0, -12], [96, 96, 96.5]), 'Box_96x96_m12_96p5')


@unittest.skipUnless(PATCH and PATCH.exists(), NO_PATCH)
class MatchesLwrHelpers(unittest.TestCase):
    """The recipe against LWR's own hidden cover helpers, the reference it was checked against."""

    @classmethod
    def setUpClass(cls):
        cls.q = lighting.Package(PATCH)
        cls.ref = {k: cls.q.by_name[PL + a] for k, a in (('high', 'XComLevelActor_0'), ('low', 'XComLevelActor_2'))}

    def reference_mesh(self, kind):
        q = self.q
        comp = q.own(self.ref[kind], 'StaticMeshComponent')
        return q.own(comp, 'StaticMesh')

    def test_a_box_of_the_helpers_size_is_their_mesh(self):
        for kind in ('high', 'low'):
            m = self.reference_mesh(kind)
            b = export_bytes(self.q, m)
            at = self.q.properties(m)[1] - self.q.exports[m - 1]['off']
            ref = native_layout(b, at)
            centre, half = ref['bounds'][:3], ref['bounds'][3:6]
            lo, hi = [c - h for c, h in zip(centre, half)], [c + h for c, h in zip(centre, half)]
            ours = native_layout(cover_blocks.box_mesh_native(lo, hi, bytes(16), 1000, body_setup=4321), 0)
            with self.subTest(kind=kind):
                for key in ('bounds', 'root', 'nodes', 'version', 'optimisation', 'simplified', 'lods', 'sections',
                            'positionsHead', 'vertexHead', 'colours', 'count'):
                    self.assertEqual(ours[key], ref[key], key)
                self.assertEqual(ours['bodySetup'], 4321)
                self.assertEqual(ours['tris'][:2], ref['tris'][:2])
                self.assertEqual(faces(ours['positions'], ours['indices']), faces(ref['positions'], ref['indices']))
                # the collision tree's triangles: the same faces as the index buffer's
                t = ours['tris'][2]
                self.assertEqual(faces(ours['positions'], [x for k in range(12) for x in struct.unpack_from('<3H', t, 8 * k)]),
                                 faces(ours['positions'], ours['indices']))
                # each vertex's normal (bytes 4 to 8) as the reference's at the same corner of the same face
                def normals(f):
                    return {(tuple(round(v) for v in p), bytes(v[4:7])) for p, v in zip(f['positions'], f['vertices'])}
                self.assertEqual(normals(ours), normals(ref))
                # what follows LOD 0: the same fields but the lighting GUID, the texture factor and the positions version
                self.assertEqual(len(ours['rest']), len(ref['rest']))
                self.assertEqual(ours['rest'][:44], ref['rest'][:44])
                self.assertEqual(ours['rest'][64:68], ref['rest'][64:68])
                self.assertEqual(ours['rest'][72:], ref['rest'][72:])
                self.assertEqual(ours['bulk'][:3], (0, 0, 0))
                self.assertEqual(ours['bulk'][3], 1000 + ours['bulkEnd'])     # just after its own record
                self.assertEqual(ref['bulk'][3], self.q.exports[m - 1]['off'] + ref['bulkEnd'])     # as the helpers'

    def test_the_helpers_boxes_have_a_hull_saved_as_ours(self):
        """LWR's boxes' RB_BodySetups save what ours save: the same version, properties and convex element fields,
        their hull the box's eight corners (their corners and triangles in another order: UDK's hull builder's)."""
        spec = cover_blocks.recipe(1)['bodySetup']
        for kind in ('high', 'low'):
            m = self.reference_mesh(kind)
            version, names, theirs = hull(self.q, self.q.own(m, 'BodySetup'))
            lo, hi = theirs['ElemBox'][0], theirs['ElemBox'][1]
            ours = cover_blocks.convex_hull(lo, hi, spec)
            with self.subTest(kind=kind):
                self.assertEqual((version, names), (spec['version'], ['PreCachedPhysDataVersion', 'AggGeom']))
                self.assertEqual(list(theirs), list(ours))
                self.assertEqual(sorted(map(tuple, theirs['VertexData'])), sorted(map(tuple, ours['VertexData'])))
                self.assertEqual(sorted(map(tuple, theirs['FacePlaneData'])), sorted(map(tuple, ours['FacePlaneData'])))
                self.assertEqual(theirs['ElemBox'], ours['ElemBox'])

    @unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
    def test_the_built_actors_save_what_the_helpers_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'cover.upk'
            p = lighting.Package(BAR)
            g = package_grow.Grower(str(BAR))
            actors, records = cover_blocks.add_blocks(g, p, [HIGH, LOW])
            native_copy.add_to_level(g, p, actors)
            g.write(str(out))
            q2 = lighting.Package(out)
            q = self.q
            for rec in records:
                kind = rec['kind']
                ref_actor = self.ref[kind]
                with self.subTest(kind=kind):
                    pairs = [(rec['actor'], ref_actor), (rec['component'], q.own(ref_actor, 'StaticMeshComponent')),
                             (rec['floor'], q.own(ref_actor, 'FloorComponent'))]
                    for ours, ref in pairs:
                        self.assertEqual(q2.cls(ours), q.cls(ref))
                        oa, ra = q2.exports[ours - 1]['arch'], q.exports[ref - 1]['arch']
                        self.assertEqual(q2.name(oa) if oa else None, q.name(ra) if ra else None)
                        self.assertEqual(q2.exports[ours - 1]['flags'], q.exports[ref - 1]['flags'])
                        mine, theirs = props_list(q2, ours), props_list(q, ref)
                        self.assertEqual([x[:3] for x in mine], [x[:3] for x in theirs])
                        refs = ('FloorComponent[0]', 'StaticMeshComponent[0]', 'CollisionComponent[0]', 'StaticMesh[0]',
                                'OwnerMeshComponents[0]', 'Location[0]', 'Rotation[0]')
                        for (name, kind_, sub, a), (_, _, _, b) in zip(mine, theirs):
                            if name in refs:
                                continue
                            if kind_ in ('NameProperty', 'ByteProperty', 'StructProperty'):
                                continue        # names: indices of each package's own table (compared by name below)
                            self.assertEqual(a, b, name)
                        e = q2.exports[ours - 1]
                        b2 = export_bytes(q2, ours)
                        start = legacy_props.props_start(q2.data, e, q2.names) - e['off']
                        tail = b2[q2.properties(ours)[1] - e['off']:]
                        rb = export_bytes(q, ref)
                        rtail = rb[q.properties(ref)[1] - q.exports[ref - 1]['off']:]
                        if q2.cls(ours) == 'StaticMeshComponent':
                            # the patch (licensee 0) ends after the LODData; EW's maps save their mesh-swap LOD
                            # records after it (BuiltInTheMap.test_the_mesh_components_native_data_is_the_maps_own)
                            self.assertEqual(tail[:len(rtail)], rtail)
                        else:
                            self.assertEqual(tail, rtail)
                        rstart = legacy_props.props_start(q.data, q.exports[ref - 1], q.names) - q.exports[ref - 1]['off']
                        self.assertEqual(start, rstart)
                        if start == 26:     # the state frame, but its class references, net index and the
                            self.assertEqual(b2[8:12], rb[8:12])     # cooker's noise word (12 to 14)
                            self.assertEqual(b2[14:22], rb[14:22])
                    self.assertEqual(q2.own(rec['actor'], 'CoverForceFlag'), q.own(ref_actor, 'CoverForceFlag'))
                    self.assertEqual(q2.own(rec['actor'], 'Tag'), q.own(ref_actor, 'Tag'))
                    self.assertTrue(q2.own(rec['actor'], 'bHidden'))
                    if kind == 'low':
                        vis, rvis = q2.own(rec['actor'], 'VisibilityBlockingData'), q.own(ref_actor, 'VisibilityBlockingData')
                        self.assertEqual(len(vis), len(rvis))


@unittest.skipUnless(POLICE and POLICE.exists(), NO_POLICE)
class GameBoxHull(unittest.TestCase):
    def test_a_box_of_the_fx_boxs_size_has_its_hull_exactly(self):
        """The recipe's hull of a 96-unit box is the game's FX_Utilities.Box_96x96x96's (URB_PoliceStation), field
        for field, float for float."""
        p = lighting.Package(POLICE)
        version, names, theirs = hull(p, p.own(p.by_name['FX_Utilities.Box_96x96x96'], 'BodySetup'))
        spec = cover_blocks.recipe(1)['bodySetup']
        ours = cover_blocks.convex_hull([-48.0] * 3, [48.0] * 3, spec)
        self.assertEqual((version, names), (spec['version'], ['PreCachedPhysDataVersion', 'AggGeom']))
        self.assertEqual(list(theirs), list(ours))
        for key in ours:
            self.assertEqual(theirs[key], ours[key], key)


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class BuiltInTheMap(unittest.TestCase):
    """Blocks built in URB_Bar read back: their meshes, actors, the Level's list and their tiles."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name) / 'cover.upk'
        p = lighting.Package(BAR)
        g = package_grow.Grower(str(BAR))
        cls.actors, cls.records = cover_blocks.add_blocks(g, p, [HIGH, LOW, HIGH2])
        cls.level = native_copy.add_to_level(g, p, cls.actors)
        g.write(str(out))
        cls.p, cls.q = p, lighting.Package(out)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_meshes_read_back_and_blocks_of_one_size_share_one(self):
        q = self.q
        high, low, high2 = self.records
        self.assertEqual(high['mesh'], high2['mesh'])
        self.assertNotEqual(high['mesh'], low['mesh'])
        for rec, size in ((high, (96, 96, 108)), (low, (192, 96, 96))):
            m = viewer_mesh.read_mesh(q, rec['mesh'])
            self.assertEqual(q.name(rec['mesh']).split('.')[0], cover_blocks.PACKAGE)
            self.assertEqual(q.cls(rec['mesh']), 'StaticMesh')
            self.assertEqual([round(2 * v) for v in m['bounds'][3:6]], list(size))
            self.assertEqual(len(m['positions']), 72)
        pkg = q.exports[high['mesh'] - 1]['outer']
        self.assertEqual(q.cls(pkg), 'Package')
        self.assertEqual(q.exports[pkg - 1]['outer'], 0)

    def test_actors_are_in_the_level_hidden_with_their_cover_and_pose(self):
        q = self.q
        level = q.by_name['TheWorld.PersistentLevel']
        _, end = q.properties(level)
        owner, count = struct.unpack_from('<ii', q.data, end)
        listed = set(struct.unpack_from(f'<{count}i', q.data, end + 8))
        for rec, force in zip(self.records, ('CoverForce_High', 'CoverForce_Low', 'CoverForce_High')):
            a = rec['actor']
            self.assertIn(a, listed)
            self.assertIn(rec['tiles']['volume']['export'], listed)
            self.assertEqual(q.cls(a), 'XComLevelActor')
            self.assertTrue(q.own(a, 'bHidden'))
            self.assertFalse(q.own(a, 'bIsValidDestination'))
            self.assertEqual(q.own(a, 'CoverForceFlag'), force)
            self.assertEqual(q.own(a, 'Location'), rec['location'])
            self.assertEqual(q.own(a, 'Rotation', [0, 0, 0]), rec['rotation'])
            comp = q.own(a, 'StaticMeshComponent')
            self.assertEqual(q.own(a, 'CollisionComponent'), comp)
            self.assertEqual(q.own(comp, 'StaticMesh'), rec['mesh'])
            self.assertEqual(q.exports[comp - 1]['outer'], a)
            self.assertEqual(q.name(q.exports[comp - 1]['arch']), 'XComGame.Default__XComLevelActor.StaticMeshComponent0')
            floor = q.own(a, 'FloorComponent')
            self.assertEqual(q.name(q.exports[floor - 1]['arch']), 'XComGame.Default__XComLevelActor.FloorComponent0')
            self.assertEqual(q.refs(q.own(floor, 'OwnerMeshComponents')), [comp])
            self.assertTrue(rec['tiles']['seeded'] + rec['tiles']['alreadyMarked'] > 0)

    def test_the_mesh_components_native_data_is_the_maps_own(self):
        """After its properties, a component saves what URB_Bar's own components with no LOD save (EW, licensee 64: an
        empty LODData, two empty mesh-swap LOD records and two null meshes), and the audit reader takes it whole. Built
        with the patch's (licensee 0) LODData alone, the game read past it and stopped as the map loaded (F-79)."""
        p, q = self.p, self.q
        self.assertEqual(p.header['lic'], 64)
        lodless = set()
        for i in range(1, len(p.exports) + 1):
            if p.cls(i) == 'StaticMeshComponent':
                e = p.exports[i - 1]
                tail = p.data[p.properties(i)[1]:e['off'] + e['size']]
                if tail[:4] == bytes(4) and tail[-8:] == bytes(8):
                    lodless.add(tail)
        self.assertEqual(lodless, {bytes(46)})
        for rec in self.records:
            comp = rec['component']
            e = q.exports[comp - 1]
            self.assertEqual(q.data[q.properties(comp)[1]:e['off'] + e['size']], bytes(46))
            native = lighting.component_record(q, comp)
            self.assertEqual((native['lods'], len(native['swaps']), native['unparsedSubclassBytes']), ([], 2, 0))
            self.assertTrue(all(not s['shadowMaps'] and s['lightmap']['type'] == 0 for s in native['swaps']))

    def test_each_box_has_a_body_setup_as_the_maps_own(self):
        """Each box mesh's simple collision: an RB_BodySetup under it, named in its BodySetup property and in its native
        data, with the map's own RB_BodySetups' entry flags, version, properties and empty pre-cooked data; its hull the
        mesh's box. The mesh saves nothing else (its simple-collision flags at their defaults). With no BodySetup the
        game's checks found nothing (F-80)."""
        p, q = self.p, self.q
        theirs = [i for i in range(1, len(p.exports) + 1) if p.cls(i) == 'RB_BodySetup'
                  and p.cls(p.exports[i - 1]['outer']) == 'StaticMesh']
        flags = {p.exports[i - 1]['flags'] for i in theirs}
        tails = {bytes(p.data[p.properties(i)[1]:p.exports[i - 1]['off'] + p.exports[i - 1]['size']]) for i in theirs}
        self.assertEqual(tails, {bytes(4)})
        for m in {rec['mesh'] for rec in self.records}:
            body = q.own(m, 'BodySetup')
            self.assertEqual([k[0] for k in q.properties(m)[0]], ['BodySetup'])
            self.assertEqual(struct.unpack_from('<i', q.data, q.native(m).pos + 28)[0], body)
            self.assertEqual((q.cls(body), q.exports[body - 1]['outer']), ('RB_BodySetup', m))
            self.assertIn(q.exports[body - 1]['flags'], flags)
            self.assertEqual(bytes(q.data[q.properties(body)[1]:q.exports[body - 1]['off'] + q.exports[body - 1]['size']]),
                             bytes(4))
            version, names, h = hull(q, body)
            self.assertEqual(names, ['PreCachedPhysDataVersion', 'AggGeom'])
            self.assertIn(version, {q.own(i, 'PreCachedPhysDataVersion') for i in theirs[:20]})
            bounds = viewer_mesh.read_mesh(q, m)['bounds']
            lo = [c - e for c, e in zip(bounds[:3], bounds[3:6])]
            hi = [c + e for c, e in zip(bounds[:3], bounds[3:6])]
            self.assertEqual([[round(v, 3) for v in h['ElemBox'][0]], [round(v, 3) for v in h['ElemBox'][1]]],
                             [[round(v, 3) for v in lo], [round(v, 3) for v in hi]])
            # every corner on or inside every face plane (w, normal), four on each
            for w, *n in h['FacePlaneData']:
                d = [sum(a * b for a, b in zip(n, v)) - w for v in h['VertexData']]
                self.assertTrue(all(x < 1e-3 for x in d))
                self.assertEqual(sum(abs(x) < 1e-3 for x in d), 4)

    def test_the_actor_and_floor_component_save_no_native_data_as_the_maps_own(self):
        p, q = self.p, self.q
        for cls in ('XComLevelActor', 'XComFloorComponent'):
            theirs = {p.exports[i - 1]['off'] + p.exports[i - 1]['size'] - p.properties(i)[1]
                      for i in range(1, len(p.exports) + 1) if p.cls(i) == cls}
            self.assertEqual(theirs, {0}, cls)
        for rec in self.records:
            for i in (rec['actor'], rec['floor']):
                e = q.exports[i - 1]
                self.assertEqual(e['off'] + e['size'], q.properties(i)[1], q.name(i))

    def test_the_state_frame_is_the_maps_own_level_actors(self):
        """The preamble as the map's placed XComLevelActors save it (their class references and net index aside)."""
        p, q = self.p, self.q
        def frame(b):           # bytes 12 to 14 are cooker noise (cover_blocks.RECIPES)
            return b[8:12] + b[14:22]
        theirs = {frame(export_bytes(p, i)) for i in range(1, len(p.exports) + 1)
                  if p.cls(i) == 'XComLevelActor' and p.exports[i - 1]['outer'] == p.by_name['TheWorld.PersistentLevel']}
        self.assertEqual(len(theirs), 1)
        for rec in self.records:
            self.assertEqual(frame(export_bytes(q, rec['actor'])), next(iter(theirs)))
            self.assertEqual(export_bytes(q, rec['actor'])[12:14], bytes(2))

    def test_net_indices_are_fresh(self):
        q = self.q
        seen = {}
        for i in range(1, len(q.exports) + 1):
            e = q.exports[i - 1]
            start = legacy_props.props_start(q.data, e, q.names)
            net = struct.unpack_from('<i', q.data, start - 4)[0] if start >= e['off'] + 4 else 0
            top = i
            while q.exports[top - 1]['outer'] > 0:
                top = q.exports[top - 1]['outer']
            if net > 0 and q.name(top).startswith('TheWorld'):
                self.assertNotIn(net, seen, f'{q.name(i)} shares net index {net} with {seen.get(net)}')
                seen[net] = q.name(i)



@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class FloorsAndTallBlocks(unittest.TestCase):
    """An invisible floor (EXP-32) and a block two tiles tall, built in URB_Bar."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name) / 'floor.upk'
        p = lighting.Package(BAR)
        g = package_grow.Grower(str(BAR))
        cls.actors, cls.records = cover_blocks.add_blocks(g, p, [FLOOR, TALL])
        native_copy.add_to_level(g, p, cls.actors)
        g.write(str(out))
        cls.p, cls.q = p, lighting.Package(out)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_a_floor_is_a_thin_plate_per_tile_cell(self):
        """One actor per tile cell, at the cell's centre a unit under the floor's top, on a 96 x 96 x 2 plate: under 4
        units thick and 384 across, so the tile rebuild's occupancy test skips it (research/native-code-notes.md)."""
        q = self.q
        floor = self.records[0]
        self.assertEqual(len(floor['cells']), 6)
        m = viewer_mesh.read_mesh(q, floor['mesh'])
        half = m['bounds'][3:6]
        self.assertEqual([round(v, 3) for v in half], [48.0, 48.0, 1.0])
        self.assertTrue(half[2] < 2 and max(half[:2]) < 192)
        self.assertEqual([round(v, 3) for v in m['bounds'][:3]], [0.0, 0.0, 0.0])
        self.assertEqual(q.cls(q.own(floor['mesh'], 'BodySetup')), 'RB_BodySetup')
        axes = cover_blocks._axes(FLOOR['rotation'])
        want = []
        for v in range(2):
            for u in range(3):
                c = [96 * u + 48, 96 * v + 48, -1.0]
                want.append([round(FLOOR['location'][k] + sum(c[a] * axes[a][k] for a in range(3)), 2) for k in range(3)])
        got = [[round(x, 2) for x in q.own(cell['actor'], 'Location')] for cell in floor['cells']]
        self.assertEqual(got, want)
        # every cell's plate together: the floor's box
        pts = [[at[k] + sx * half[0] * axes[0][k] + sy * half[1] * axes[1][k] + sz * half[2] * axes[2][k] for k in range(3)]
               for at in got for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
        self.assertEqual([round(f(p[k] for p in pts), 2) for k in range(3) for f in (min, max)], FLOOR['box'])

    def test_a_floor_is_hidden_walkable_and_forces_no_cover(self):
        """A floor's actors save the blocks' properties but the cover and the climbing and destination ones, and are
        ignored for cover: a hidden level actor a unit can stand on that gives no tile cover (EXP-32 run 1)."""
        q = self.q
        for cell in self.records[0]['cells']:
            a = cell['actor']
            names = [k[0] for k in q.properties(a)[0]]
            self.assertEqual(names, ['FloorComponent', 'bIgnoreForCover', 'StaticMeshComponent', 'Location', 'Rotation',
                                     'bHidden', 'Tag', 'CollisionComponent'])
            self.assertTrue(q.own(a, 'bHidden'))
            self.assertTrue(q.own(a, 'bIgnoreForCover'))
            self.assertIsNone(q.own(a, 'CoverForceFlag'))
            comp = q.own(a, 'StaticMeshComponent')
            self.assertEqual(q.own(comp, 'StaticMesh'), self.records[0]['mesh'])
            self.assertEqual(q.refs(q.own(q.own(a, 'FloorComponent'), 'OwnerMeshComponents')), [comp])
            self.assertEqual(lighting.component_record(q, comp)['unparsedSubclassBytes'], 0)

    def test_a_tall_block_is_one_actor_at_its_corner(self):
        q = self.q
        tall = self.records[1]
        self.assertEqual(len(tall['cells']), 1)
        self.assertEqual(q.own(tall['actor'], 'Location'), TALL['location'])
        m = viewer_mesh.read_mesh(q, tall['mesh'])
        self.assertEqual([round(2 * v) for v in m['bounds'][3:6]], [96, 96, 204])
        self.assertEqual(q.own(tall['actor'], 'CoverForceFlag'), 'CoverForce_High')
        self.assertFalse(q.own(tall['actor'], 'bIsValidDestination'))
        self.assertIsNone(q.own(tall['actor'], 'bIgnoreForCover'))       # a block gives cover

    def test_their_actors_and_volumes_are_in_the_level(self):
        q = self.q
        level = q.by_name['TheWorld.PersistentLevel']
        _, end = q.properties(level)
        owner, count = struct.unpack_from('<ii', q.data, end)
        listed = set(struct.unpack_from(f'<{count}i', q.data, end + 8))
        for rec in self.records:
            self.assertTrue({c['actor'] for c in rec['cells']} <= listed)
            self.assertIn(rec['tiles']['volume']['export'], listed)


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class BlocksSmallerThanATile(unittest.TestCase):
    """Blocks sized by the editor's handles in units (private/plans/done/cover-block-handles-plan.md), built in
    URB_Bar: half a tile across, a wall 8 units thick a tile long, one off the floor from 40 to 80, a blocker 48 x 96
    turned a quarter, and a floor 150 x 96 (cells of about a tile: two of 75)."""
    HALF = dict(name='CoverBlock_copy11', kind='high', location=[-1824.0, -384.0, 0.0], rotation=[0, 0, 0],
                size=[48.0, 48.0], heights=[-12.0, 96.0], box=[-1824.0, -1776.0, -384.0, -336.0, -12.0, 96.0])
    WALL = dict(name='CoverBlock_copy12', kind='low', location=[-1632.0, -384.0, 0.0], rotation=[0, 0, 0],
                size=[8.0, 96.0], heights=[-12.0, 84.0], box=[-1632.0, -1624.0, -384.0, -288.0, -12.0, 84.0])
    FLOAT = dict(name='CoverBlock_copy13', kind='high', location=[-1440.0, -384.0, 0.0], rotation=[0, 0, 0],
                 size=[96.0, 96.0], heights=[40.0, 80.0], box=[-1440.0, -1344.0, -384.0, -288.0, 40.0, 80.0])
    BLOCK = dict(name='Blocker_copy14', kind='block', version=2, location=[-1152.0, -384.0, 0.0], rotation=[0, 16384, 0],
                 size=[48.0, 96.0], heights=[-12.0, 96.0], box=[-1248.0, -1152.0, -384.0, -336.0, -12.0, 96.0])
    FLOOR = dict(name='InvisibleFloor_copy15', kind='floor', location=[-1824.0, -192.0, 40.0], rotation=[0, 0, 0],
                 size=[150.0, 96.0], heights=[-2.0, 0.0], box=[-1824.0, -1674.0, -192.0, -96.0, 38.0, 40.0])

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name) / 'small.upk'
        p = lighting.Package(BAR)
        g = package_grow.Grower(str(BAR))
        cls.blocks = [cls.HALF, cls.WALL, cls.FLOAT, cls.BLOCK, cls.FLOOR]
        cls.actors, cls.records = cover_blocks.add_blocks(g, p, cls.blocks, version=1)
        native_copy.add_to_level(g, p, cls.actors)
        g.write(str(out))
        cls.q = lighting.Package(out)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_each_block_is_its_box_at_its_corner(self):
        """Each block one actor at its corner, its mesh its size and heights, its cover as a whole tile's, and its
        box its rebuild volume's."""
        q = self.q
        for b, rec, force in zip(self.blocks[:4], self.records, ('CoverForce_High', 'CoverForce_Low', 'CoverForce_High',
                                                                 None)):      # a blocker saves none
            self.assertEqual(len(rec['cells']), 1, b['name'])
            self.assertEqual(q.own(rec['actor'], 'Location'), b['location'])
            self.assertEqual(q.own(rec['actor'], 'Rotation', [0, 0, 0]), b['rotation'])
            self.assertEqual(q.own(rec['actor'], 'CoverForceFlag'), force)
            m = viewer_mesh.read_mesh(q, rec['mesh'])
            lo = [round(c - e, 3) for c, e in zip(m['bounds'][:3], m['bounds'][3:6])]
            hi = [round(c + e, 3) for c, e in zip(m['bounds'][:3], m['bounds'][3:6])]
            self.assertEqual((lo, hi), ([0.0, 0.0, b['heights'][0]], [*b['size'], b['heights'][1]]), b['name'])
            version, names, h = hull(q, q.own(rec['mesh'], 'BodySetup'))
            self.assertEqual([[round(v, 3) for v in h['ElemBox'][k]] for k in range(2)], [lo, hi])
            self.assertEqual(rec['box'], b['box'])
        self.assertEqual(len({rec['mesh'] for rec in self.records}), 5)        # every size its own mesh

    def test_a_floor_off_whole_tiles_splits_into_cells_of_about_a_tile(self):
        q = self.q
        floor = self.records[4]
        self.assertEqual(len(floor['cells']), 2)
        m = viewer_mesh.read_mesh(q, floor['mesh'])
        self.assertEqual([round(v, 3) for v in m['bounds'][3:6]], [37.5, 48.0, 1.0])
        got = [[round(x, 2) for x in q.own(cell['actor'], 'Location')] for cell in floor['cells']]
        self.assertEqual(got, [[-1786.5, -144.0, 39.0], [-1711.5, -144.0, 39.0]])



def breaking_digest(version):
    """SHA-256 of a breaking block's recipe, pinned as recipe_digest's is."""
    text = json.dumps(cover_blocks.breaking_recipe(version), sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


class BreakingRecipe(unittest.TestCase):
    def test_versions_and_kinds(self):
        self.assertEqual(sorted(cover_blocks.BREAKING), [1, 2])
        self.assertEqual(breaking_digest(1), BREAKING_DIGEST_1)
        self.assertEqual(breaking_digest(2), BREAKING_DIGEST_2)
        self.assertEqual(sorted(cover_blocks.BREAKING[1]['kinds']), ['high', 'low'])
        self.assertEqual(sorted(cover_blocks.BREAKING[2]['kinds']), ['block', 'high', 'low'])
        with self.assertRaises(ValueError):
            cover_blocks.breaking_recipe(3)
        # version 2's prop saves bIgnoreForCover where the level actor does, for the blocker alone (high and low have none)
        names = [p[0] for p in cover_blocks.BREAKING[2]['actor']['properties']]
        one = [p[0] for p in cover_blocks.BREAKING[1]['actor']['properties']]
        self.assertEqual(names, one[:5] + ['bIgnoreForCover'] + one[5:])
        self.assertEqual(names.index('bIgnoreForCover') + 1, names.index('CoverForceFlag'))
        self.assertNotIn('ignore', cover_blocks.BREAKING[2]['kinds']['high'])

    def test_recipe_1_is_untouched(self):
        self.assertEqual(cover_blocks.recipe_digest(1), DIGEST_1)


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class BreakingBlocksInTheMap(unittest.TestCase):
    """Blocks that break with a group, built in URB_Bar next to a plain one: hidden props with the game's Hide action,
    laid out as the map's own placed props, and listed by their group's pieces."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name) / 'cover.upk'
        p = lighting.Package(BAR)
        g = package_grow.Grower(str(BAR))
        blocks = [HIGH, dict(LOW, breakGroup=1), dict(HIGH2, breakGroup=1)]
        cls.actors, cls.records = cover_blocks.add_blocks(g, p, blocks)
        cls.prop = 'XComDestructibleActor_223'       # a ketchup bottle: one Hide event, like the block's
        cls.groups, _ = native_copy.link_children(
            g, p, [], [dict(name=cls.prop, group=1)], [(r['breakGroup'], r['actor']) for r in cls.records if r.get('breakGroup')])
        native_copy.add_to_level(g, p, cls.actors)
        g.write(str(out))
        cls.p, cls.q = p, lighting.Package(out)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_a_block_outside_a_group_is_the_level_actor_it_was(self):
        q, plain = self.q, self.records[0]
        self.assertEqual(q.cls(plain['actor']), 'XComLevelActor')
        self.assertNotIn('breakGroup', plain)
        self.assertIsNotNone(plain['floor'])

    def test_a_breaking_block_is_a_hidden_prop_with_its_cover(self):
        q = self.q
        for rec, force in zip(self.records[1:], ('CoverForce_Low', 'CoverForce_High')):
            a = rec['actor']
            self.assertEqual(rec['breakGroup'], 1)
            self.assertEqual(q.cls(a), 'XComDestructibleActor')
            self.assertEqual(q.exports[a - 1]['arch'], 0)
            self.assertTrue(q.own(a, 'bHidden'))
            self.assertFalse(q.own(a, 'bIsValidDestination'))
            self.assertFalse(q.own(a, 'bDestroysSurroundingArea'))
            self.assertEqual(q.own(a, 'CoverForceFlag'), force)
            self.assertEqual(q.own(a, 'Location'), rec['location'])
            self.assertEqual(q.own(a, 'Rotation', [0, 0, 0]), rec['rotation'])
            self.assertIsNone(q.own(a, 'FloorComponent'))
            self.assertIsNone(rec['floor'])
            comp = q.own(a, 'StaticMeshComponent')
            self.assertEqual(comp, rec['component'])
            self.assertEqual(q.own(a, 'CollisionComponent'), comp)
            self.assertEqual(q.own(comp, 'StaticMesh'), rec['mesh'])
            self.assertEqual(q.name(q.exports[comp - 1]['arch']),
                             'XComGame.Default__XComDestructibleActor.StaticMeshComponent0')
            self.assertEqual(lighting.component_record(q, comp)['unparsedSubclassBytes'], 0)
            self.assertTrue(rec['tiles']['seeded'] + rec['tiles']['alreadyMarked'] > 0)
        # low cover lets units see over it, as recipe 1's
        low = dict((n, v) for n, _, _, v in props_list(q, self.records[1]['actor']))
        self.assertIn('VisibilityBlockingData[0]', low)
        self.assertNotIn('VisibilityBlockingData[0]', dict((n, v) for n, _, _, v in props_list(q, self.records[2]['actor'])))

    def test_its_one_destroyed_event_is_a_hide_action_saved_as_the_maps_props_save_theirs(self):
        p, q = self.p, self.q
        theirs = p.by_name[PL + self.prop]
        [their_events] = [v for n, _, _, v in props_list(p, theirs) if n == 'DestroyedEvents[0]']
        their_action = struct.unpack_from('<i', their_events, 28)[0]
        self.assertEqual(p.cls(their_action), 'XComDestructibleActor_Action_Hide')
        for rec in self.records[1:]:
            a, action = rec['actor'], rec['cells'][0]['action']
            [events] = [v for n, _, _, v in props_list(q, a) if n == 'DestroyedEvents[0]']
            # the same bytes but for the action named and the name indices of this package (the names are the same)
            self.assertEqual(len(events), len(their_events))
            self.assertEqual(struct.unpack_from('<i', events, 0)[0], 1)
            self.assertEqual(struct.unpack_from('<i', events, 28)[0], action)
            self.assertEqual([q.names[struct.unpack_from('<i', events, at)[0]] for at in (4, 12, 32)],
                             [p.names[struct.unpack_from('<i', their_events, at)[0]] for at in (4, 12, 32)])
            self.assertEqual(q.cls(action), 'XComDestructibleActor_Action_Hide')
            self.assertEqual(q.exports[action - 1]['outer'], a)
            # the action's data: a net index and no properties, as the map's own
            self.assertEqual(len(export_bytes(q, action)), len(export_bytes(p, their_action)))
            self.assertEqual(export_bytes(q, action)[4:], export_bytes(p, their_action)[4:].replace(
                struct.pack('<i', p.names.index('None')), struct.pack('<i', q.names.index('None'))))

    def test_its_toughness_takes_no_damage(self):
        p, q = self.p, self.q
        metal = p.by_name['GameData_Toughness.Toughness_METAL']
        for rec in self.records[1:]:
            t = q.own(rec['actor'], 'Toughness')
            self.assertEqual(t, rec['cells'][0]['toughness'])
            self.assertEqual(q.cls(t), 'XComDestructibleActor_Toughness')
            self.assertEqual(q.exports[t - 1]['outer'], rec['actor'])
            self.assertTrue(q.own(t, 'bInvincible'))
            self.assertIsNone(q.own(t, 'bSuccumbsToDamage'))
            # a net index, then the properties, as the map's toughnesses
            e, m = q.exports[t - 1], p.exports[metal - 1]
            self.assertEqual(legacy_props.props_start(q.data, e, q.names) - e['off'],
                             legacy_props.props_start(p.data, m, p.names) - m['off'])

    def test_the_state_frame_is_the_maps_own_props(self):
        p, q = self.p, self.q
        def frame(b):           # bytes 12 to 14 are cooker noise (cover_blocks.RECIPES)
            return b[8:12] + b[14:22]
        theirs = {frame(export_bytes(p, i)) for i in range(1, len(p.exports) + 1)
                  if p.cls(i) == 'XComDestructibleActor' and p.exports[i - 1]['outer'] == p.by_name['TheWorld.PersistentLevel']}
        self.assertEqual(len(theirs), 1)
        for rec in self.records[1:]:
            b = export_bytes(q, rec['actor'])
            self.assertEqual(frame(b), next(iter(theirs)))
            cls = struct.unpack_from('<i', b, 0)[0]
            self.assertEqual(struct.unpack_from('<i', b, 4)[0], cls)
            self.assertEqual(q.name(cls), 'XComGame.XComDestructibleActor')

    def test_the_groups_prop_lists_the_blocks_and_they_list_nothing(self):
        p, q = self.p, self.q
        prop = p.by_name[PL + self.prop]
        blocks = [r['actor'] for r in self.records[1:]]
        self.assertEqual(self.groups, {1: [prop] + blocks})
        qw = native_copy.Walker(q)

        def children(i):
            e = q.exports[i - 1]
            start = legacy_props.props_start(q.data, e, q.names) - e['off']
            return native_copy.object_array(qw, q.data[e['off']:e['off'] + e['size']], start, 'AffectedChildren')
        self.assertEqual(children(prop)[-2:], blocks)
        for b in blocks:
            self.assertEqual(children(b), [])

    def test_net_indices_are_fresh(self):
        q = self.q
        seen = {}
        for rec in self.records[1:]:
            cell = rec['cells'][0]
            for i in (cell['actor'], cell['component'], cell['action'], cell['toughness']):
                e = q.exports[i - 1]
                net = struct.unpack_from('<i', q.data, legacy_props.props_start(q.data, e, q.names) - 4)[0]
                self.assertGreater(net, 0)
                self.assertNotIn(net, seen)
                seen[net] = i

    def test_a_group_needs_a_breakable_piece_and_a_floor_cant_break(self):
        p = self.p
        g = package_grow.Grower(str(BAR))
        with self.assertRaises(ValueError):
            native_copy.link_children(g, p, [], [], [(1, 5)])
        with self.assertRaises(ValueError):
            cover_blocks.add_blocks(g, p, [dict(FLOOR, breakGroup=1)])


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class BlockersInTheMap(unittest.TestCase):
    """Blockers (recipe version 2, Discord feedback S6) built in URB_Bar beside a version 1 high block: one plain, one
    breaking with a group. A blocker is the high block's hidden box with no cover; a version 1 block is made the same
    whichever version builds it."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name) / 'blockers.upk'
        p = lighting.Package(BAR)
        g = package_grow.Grower(str(BAR))
        cls.actors, cls.records = cover_blocks.add_blocks(g, p, [HIGH, BLOCK, dict(BLOCK2, breakGroup=1), dict(HIGH2, breakGroup=1)])
        native_copy.add_to_level(g, p, cls.actors)
        g.write(str(out))
        cls.p, cls.q = p, lighting.Package(out)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_a_blocker_is_hidden_occupies_its_tiles_and_gives_no_cover(self):
        """The high block's properties but the cover: no CoverForceFlag, ignored for cover, low cover's sight data; and
        its box, which it shares with the high block of its size."""
        q = self.q
        high, block = self.records[0], self.records[1]
        a = block['actor']
        self.assertEqual(q.cls(a), 'XComLevelActor')
        self.assertEqual([k[0] for k in q.properties(a)[0]],
                         ['FloorComponent', 'VisibilityBlockingData', 'bCanClimbOnto', 'bIsValidDestination', 'bIgnoreForCover',
                          'StaticMeshComponent', 'Location', 'bHidden', 'Tag', 'CollisionComponent'])
        self.assertTrue(q.own(a, 'bHidden'))
        self.assertTrue(q.own(a, 'bIgnoreForCover'))
        self.assertIsNone(q.own(a, 'CoverForceFlag'))
        self.assertFalse(q.own(a, 'bIsValidDestination'))
        self.assertFalse(q.own(a, 'bCanClimbOnto'))
        self.assertIn('VisibilityBlockingData[0]', dict((n, v) for n, _, _, v in props_list(q, a)))
        self.assertEqual(block['mesh'], high['mesh'])
        self.assertEqual(q.cls(q.own(block['mesh'], 'BodySetup')), 'RB_BodySetup')
        self.assertEqual(q.own(a, 'Location'), BLOCK['location'])
        self.assertTrue(block['tiles']['seeded'] + block['tiles']['alreadyMarked'] > 0)
        # the high block beside it keeps its cover
        self.assertEqual(q.own(high['actor'], 'CoverForceFlag'), 'CoverForce_High')
        self.assertIsNone(q.own(high['actor'], 'bIgnoreForCover'))

    def test_a_breaking_blocker_is_a_hidden_prop_ignored_for_cover(self):
        q = self.q
        blocker, high = self.records[2], self.records[3]
        a = blocker['actor']
        self.assertEqual(q.cls(a), 'XComDestructibleActor')
        self.assertTrue(q.own(a, 'bIgnoreForCover'))
        self.assertIsNone(q.own(a, 'CoverForceFlag'))
        self.assertFalse(q.own(a, 'bIsValidDestination'))
        self.assertIn('VisibilityBlockingData[0]', dict((n, v) for n, _, _, v in props_list(q, a)))
        # a version 1 high block breaking beside it saves what version 1 saves: no bIgnoreForCover
        self.assertEqual(q.cls(high['actor']), 'XComDestructibleActor')
        self.assertEqual(q.own(high['actor'], 'CoverForceFlag'), 'CoverForce_High')
        self.assertIsNone(q.own(high['actor'], 'bIgnoreForCover'))

    def test_a_version_1_block_is_the_same_by_either_version(self):
        """The whole map built with a high and a low block (one breaking) is the same file by version 1 and by version 2."""
        built = []
        for version in (1, 2):
            p = lighting.Package(BAR)
            g = package_grow.Grower(str(BAR))
            blocks = [dict(HIGH, version=version), dict(LOW, version=version, breakGroup=1)]
            actors, _ = cover_blocks.add_blocks(g, p, blocks)
            native_copy.add_to_level(g, p, actors)
            out = Path(self.tmp.name) / f'v{version}.upk'
            g.write(str(out))
            built.append(out.read_bytes())
        self.assertEqual(built[0], built[1])

    def test_version_1_makes_no_blocker(self):
        p = self.p
        g = package_grow.Grower(str(BAR))
        with self.assertRaises(ValueError):
            cover_blocks.add_blocks(g, p, [dict(BLOCK, version=1)])


if __name__ == '__main__':
    unittest.main()

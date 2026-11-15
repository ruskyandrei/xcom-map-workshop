"""Growing edits by appending (package_grow.py; UDK-removal U2, baker L4 gate C6), on the bar."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'viewer'))
sys.path.insert(0, str(HERE.parents[1] / 'bake'))
import decomp  # noqa: E402
import package_grow  # noqa: E402
import upkinfo  # noqa: E402

sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402

# URB_Bar as shipped: XCOM_BAR_UPK, else the LWR install's (tools/viewer/settings.py); without it the tests skip
BAR, NO_BAR = labpaths.test_file('XCOM_BAR_UPK', labpaths.lwr_cooked('URB_Bar.upk'), 'URB_Bar.upk')
FLOOR = 'TheWorld.PersistentLevel.XComLevelActor_302.StaticMeshComponent_7'


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class GrowBar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.full, cls.h = decomp.decompress_pkg(str(BAR))
        cls.names, cls.imps, cls.exps = upkinfo.tables(cls.full, cls.h)

    def test_a_growing_write_without_changes_moves_only_the_tables(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'URB_Bar.upk'
            report = package_grow.Grower(str(BAR)).write(str(out))
            full, h = decomp.decompress_pkg(str(out))
            names, imps, exps = upkinfo.tables(full, h)
            end = self.h['chunks'][-1][0] + self.h['chunks'][-1][1]
            # every export's data is where it was, and the old bytes are all still there (from the first chunk: the
            # logical image's first bytes are the physical summary's)
            lo = self.h['chunks'][0][0]
            self.assertEqual(full[lo:end], self.full[lo:end])
            self.assertEqual([(e['off'], e['size'], e['name']) for e in exps],
                             [(e['off'], e['size'], e['name']) for e in self.exps])
            self.assertEqual((names, len(imps)), (self.names, len(self.imps)))
            # the table keeps its size (some entries carry net object counts, so not all are 68 bytes)
            self.assertEqual((h['expoff'], h['dependsoff']), (end, end + self.h['dependsoff'] - self.h['expoff']))
            self.assertEqual(h['gens'][0][:2], (len(exps), len(names)))
            self.assertEqual(len(h['chunks']), len(self.h['chunks']) + 1)
            self.assertEqual(report['added'], 0)

    def test_a_new_name_and_a_relocated_export(self):
        g = package_grow.Grower(str(BAR))
        index = g.name('XComMapWorkshopTestName')
        self.assertEqual(index, len(self.names))
        self.assertEqual(g.name('XComMapWorkshopTestName'), index)
        victim = 5
        data = g.export_data(victim) + b'grown'
        g.relocate(victim, data)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'URB_Bar.upk'
            report = g.write(str(out))
            full, h = decomp.decompress_pkg(str(out))
            names, imps, exps = upkinfo.tables(full, h)
            self.assertEqual(names[-1], 'XComMapWorkshopTestName')
            self.assertEqual(report['newNames'], ['XComMapWorkshopTestName'])
            e = exps[victim - 1]
            self.assertEqual(full[e['off']:e['off'] + e['size']], data)
            self.assertGreaterEqual(e['off'], self.h['chunks'][-1][0] + self.h['chunks'][-1][1])

    def test_chunks_are_cut_only_where_an_item_starts(self):
        cut = package_grow.Grower.chunk_cuts
        self.assertEqual(cut([0, 300, 700], 1000, limit=500), [(0, 300), (300, 700), (700, 1000)])
        self.assertEqual(cut([0, 100, 200, 450], 1000, limit=500), [(0, 450), (450, 1000)])
        # an item bigger than the limit gets a chunk to itself
        self.assertEqual(cut([0, 100, 900], 1000, limit=500), [(0, 100), (100, 900), (900, 1000)])
        self.assertEqual(cut([], 1000, limit=500), [(0, 1000)])

    def test_new_imports_go_after_the_old_and_existing_ones_are_found(self):
        g = package_grow.Grower(str(BAR))
        engine = g.find_import('Package', 'Engine', 0)
        self.assertIsNotNone(engine)
        self.assertEqual(g.add_import('Core', 'Class', engine, 'TriggerVolume'),
                         g.find_import('Class', 'TriggerVolume', engine))
        new = g.add_import('Core', 'Class', engine, 'XComMapWorkshopTestClass')
        self.assertEqual(new, -(len(self.imps) + 1))
        self.assertEqual(g.add_import('Core', 'Class', engine, 'XComMapWorkshopTestClass'), new)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'URB_Bar.upk'
            report = g.write(str(out))
            full, h = decomp.decompress_pkg(str(out))
            names, imps, exps = upkinfo.tables(full, h)
            self.assertEqual(len(imps), len(self.imps) + 1)
            self.assertEqual(imps[:-1], self.imps)
            self.assertEqual(imps[-1], dict(cpkg='Core', cls='Class', outer=engine, name='XComMapWorkshopTestClass'))
            self.assertEqual((report['addedImports'], report['newNames']), (1, ['XComMapWorkshopTestClass']))
            self.assertGreaterEqual(h['impoff'], self.h['chunks'][-1][0] + self.h['chunks'][-1][1])

    def test_a_new_export_with_no_template(self):
        # an entry made from its class, outer, name, archetype and flags alone (new_export), with the package's next net
        # index; nothing of another export's entry is copied
        g = package_grow.Grower(str(BAR))
        level = next(k + 1 for k in range(len(self.exps)) if upkinfo.objname(k + 1, self.imps, self.exps)
                     == 'TheWorld.PersistentLevel')
        engine = g.find_import('Package', 'Engine', 0)
        cls = g.add_import('Core', 'Class', engine, 'XComMapWorkshopTestClass')
        net = g.next_net_index(level)
        self.assertEqual((net, g.net_objects), (self.h['gens'][0][2], self.h['gens'][0][2] + 1))
        data = struct.pack('<ii', 0, net) + struct.pack('<ii', g.name('None'), 0)
        new = g.new_export(cls, level, 'XComMapWorkshopTestObject', data, flags=0x0007000100000000)
        self.assertEqual(new, len(self.exps) + 1)
        self.assertEqual(g.entries[new - 1].name_number, 1)
        self.assertEqual(g.new_export(cls, new, 'XComMapWorkshopTestObject', data), new + 1)
        self.assertEqual(g.entries[new].name_number, 2)
        # refused: no class, a class or archetype outside the package, an import as outer, a bad name or flags
        for bad in (dict(cls=0), dict(cls=-len(g.imports) - 1), dict(cls=len(g.entries) + 1), dict(archetype=10 ** 7),
                    dict(outer=engine), dict(name='None'), dict(name=''), dict(flags=-1), dict(flags=1 << 64),
                    dict(number=-1)):
            args = {**dict(cls=cls, outer=level, name='X', data=data), **bad}
            with self.assertRaises(ValueError, msg=str(bad)):
                g.new_export(args.pop('cls'), args.pop('outer'), args.pop('name'), args.pop('data'), **args)
        self.assertEqual(len(g.entries), new + 1)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'URB_Bar.upk'
            report = g.write(str(out))
            full, h = decomp.decompress_pkg(str(out))
            names, imps, exps = upkinfo.tables(full, h)
            self.assertEqual(report['added'], 2)
            self.assertEqual(h['gens'][0][2], self.h['gens'][0][2] + 1)
            e = exps[new - 1]
            self.assertEqual((e['cls'], e['sup'], e['outer'], e['arch'], e['flags']), (cls, 0, level, 0, 0x0007000100000000))
            self.assertEqual(upkinfo.objname(new, imps, exps), 'TheWorld.PersistentLevel.XComMapWorkshopTestObject_0')
            self.assertEqual(upkinfo.objname(new + 1, imps, exps),
                             'TheWorld.PersistentLevel.XComMapWorkshopTestObject_0.XComMapWorkshopTestObject_1')
            self.assertEqual(full[e['off']:e['off'] + e['size']], data)
            # the entry is a plain one: 68 bytes, no net object counts, zero GUID and package flags
            raw = bytes(g.entries[new - 1].data)
            self.assertEqual((len(raw), raw[40:68]), (68, bytes(28)))

    def test_an_adopted_entry_keeps_everything_but_its_size_and_place(self):
        # an entry made elsewhere (transplant.py: another package's, renumbered): here a forced-export package's own
        # entry, with its net object count and GUID, under a new name
        g = package_grow.Grower(str(BAR))
        k = next(k for k, e in enumerate(g.entries) if e.outer == 0 and e.get('<I', 40) & package_grow.FORCED_EXPORT
                 and e.get('<I', 44) == 1)
        entry = package_grow.Entry(g.entries[k].data)
        entry.put('<i', 12, g.name('XComMapWorkshopTestPackage'))
        data = struct.pack('<i', -1) + struct.pack('<ii', g.name('None'), 0)
        new = g.adopt_export(entry.data, data)
        self.assertEqual(new, len(self.exps) + 1)
        mine, theirs = bytes(g.entries[new - 1].data), bytes(g.entries[k].data)
        self.assertEqual((mine[:12], mine[16:32], mine[40:]), (theirs[:12], theirs[16:32], theirs[40:]))
        self.assertEqual((g.entries[new - 1].size, g.entries[new - 1].offset), (12, g.end))
        # refused: a short or long entry, a name or an import outside the tables, an import as outer
        for bad in (entry.data[:60], bytes(entry.data) + bytes(4)):
            with self.assertRaises(ValueError):
                g.adopt_export(bad, data)
        for at, value in ((12, len(g.names)), (0, -len(g.imports) - 1), (8, -1)):
            wrong = package_grow.Entry(entry.data)
            wrong.put('<i', at, value)
            with self.assertRaises(ValueError, msg=str(at)):
                g.adopt_export(wrong.data, data)
        self.assertEqual(len(g.entries), new)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'URB_Bar.upk'
            report = g.write(str(out))
            full, h = decomp.decompress_pkg(str(out))
            names, imps, exps = upkinfo.tables(full, h)
            self.assertEqual(report['added'], 1)
            self.assertEqual(upkinfo.objname(new, imps, exps), 'XComMapWorkshopTestPackage')
            self.assertEqual(upkinfo.clsname(exps[new - 1]['cls'], imps, exps), 'Package')
            self.assertEqual(h['gens'][0][2], self.h['gens'][0][2])        # no net object of the map's own

    def test_cloned_lightmap_textures_read_back_with_their_payloads(self):
        import audit_lighting as lighting
        import grow_fixture
        import lightmap_fields
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'URB_Bar.upk'
            info = grow_fixture.grow(BAR, out, FLOOR)
            lighting.link_caches(d, BAR.parent)      # the grown map reads the map's own texture cache, where it is
            q = lighting.Package(out)
            p = lighting.Package(BAR)
            lm = lightmap_fields.component_fields(q, q.by_name[FLOOR])['lods'][0]['lightmap']
            for slot in (0, 1):
                original, clone, name = info['clones'][slot]
                self.assertEqual(lm['slots'][slot]['index'], clone)
                self.assertEqual(q.name(clone), name)
                self.assertEqual(q.cls(clone), q.cls(original))
                a = lightmap_fields.texture_fields(q, clone)
                b = lightmap_fields.texture_fields(p, original)
                for ma, mb in zip(a['mips'], b['mips']):
                    self.assertEqual((ma['flags'], ma['width'], ma['bytes']), (mb['flags'], mb['width'], mb['bytes']))
                    if ma['inline']:
                        # the copy's own payload, at its new absolute offset
                        self.assertEqual(q.data[ma['payloadOffset']:ma['payloadOffset'] + ma['bytes']],
                                         p.data[mb['payloadOffset']:mb['payloadOffset'] + mb['bytes']])
                        self.assertEqual(struct.unpack_from('<i', q.data, ma['metaOffset'] + 12)[0],
                                         ma['payloadOffset'])
                    else:
                        self.assertEqual(ma['offset'], mb['offset'])


if __name__ == '__main__':
    unittest.main()

from pathlib import Path
from functools import partial
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request,urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalogue import load_catalogue,public_catalogue,with_install
from exports import ExportRunner
from unittest.mock import patch
from viewer import Handler,LocalServer

# Stands in for `viewer.py export`: writes a generation of the map into the cache and prints the export's JSON result,
# or fails as an export that can't read the package does.
FAKE_EXPORT='''import json,sys,pathlib
cache,name=pathlib.Path(sys.argv[1]),sys.argv[2]
if name=='Broken': print('reading the package'); print('ValueError: unsupported export'); sys.exit(1)
again=(cache/name/'g1').exists()   # exported before: a Prepare (export 18)
if name=='Flaky' and again: print('ValueError: the second export fails'); sys.exit(1)
root=cache/name/('g2' if again else 'g1'); root.mkdir(parents=True)
(root/'scene.json').write_text(json.dumps(dict(schemaVersion=1,exporterVersion=18 if again else 11,name=name,scope='map')))
(root/'mesh-1.glb').write_bytes(name.encode())
print('exporting', name)
print('progress: reading the map 1/2'); print('progress: reading the map 2/2'); print('progress: reading patch_x 1/1')
print(json.dumps(dict(folder=str(root),counts={},diagnostics=0),indent=2))
'''


class CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def export(self,name,folder,version=11,scope='map'):
        root=self.root/name/folder;root.mkdir(parents=True)
        data=dict(schemaVersion=1,exporterVersion=version,name=name,scope=scope)
        (root/'scene.json').write_text(json.dumps(data),encoding='utf8',newline='\n')
        (root/'mesh-1.glb').write_bytes(name.encode())
        return root

    def test_latest_full_generation_per_map_and_checked_labels(self):
        self.export('URB_Bar','old',version=9)
        latest=self.export('URB_Bar','current')
        self.export('URB_Bar','newer-study',version=99,scope='sample')
        self.export('URB_Bar','.export-unfinished',version=100)
        self.export('TempleShip','current')
        broken=self.root/'OtherMap'/'broken';broken.mkdir(parents=True)
        (broken/'scene.json').write_text('[]',encoding='utf8',newline='\n')
        catalogue=load_catalogue(self.root)
        self.assertEqual(catalogue['maps']['URB_Bar']['root'],latest)
        listed=lambda name,label:dict(id=name,name=name,label=label,ready=True,checked=True,groups=['other'],missions=[])
        self.assertEqual(public_catalogue(catalogue),dict(defaultMap='URB_Bar',maps=[
            listed('URB_Bar','Bar'),listed('TempleShip','Temple Ship')]))
        self.assertEqual(len(load_catalogue(self.root/'URB_Bar')['maps']),1)
        # outdated needs a newer exporter and a map of the install
        installed=with_install(catalogue,dict(URB_Bar=dict(label='Bar',groups=['abduction'],missions=[])))
        self.assertTrue(public_catalogue(installed,12)['maps'][0]['outdated'])
        self.assertNotIn('outdated',public_catalogue(installed,11)['maps'][0])
        self.assertNotIn('outdated',public_catalogue(installed)['maps'][0])
        self.assertFalse(any('outdated' in m for m in public_catalogue(catalogue,12)['maps']))

    def test_exact_generation_is_pinned_and_unknown_maps_are_unchecked(self):
        old=self.export('URB_Bar','old',version=9)
        self.export('URB_Bar','new')
        self.assertEqual(load_catalogue(old)['maps']['URB_Bar']['root'],old)
        other=self.export('OtherMap','current')
        self.assertEqual(public_catalogue(load_catalogue(other))['maps'][0],dict(
            id='OtherMap',name='OtherMap',label='OtherMap',ready=True,checked=False,groups=['other'],missions=[]))

    def test_install_lists_every_map_and_exported_ones_take_its_labels(self):
        self.export('URB_Bar','current')
        mission=lambda kind:[dict(type=kind,label=kind,display='')]
        installed=dict(URB_Bar=dict(label='Urban Bar',groups=['abduction'],missions=mission('Abduction')),
                       Alpha=dict(label='Alpha Base',groups=['story'],missions=mission('AlienBase')))
        catalogue=with_install(load_catalogue(self.root),installed)
        self.assertEqual(catalogue['defaultMap'],'URB_Bar')
        self.assertEqual([(m['id'],m['label'],m['ready'],m['groups']) for m in public_catalogue(catalogue)['maps']],
                         [('Alpha','Alpha Base',False,['story']),('URB_Bar','Urban Bar',True,['abduction'])])
        self.assertIsNone(catalogue['maps']['Alpha']['root'])
        # an export whose package's case differs from its record's takes the record's name
        farm=self.export('CsmallScout_Farm','current')
        installed['CSmallScout_Farm']=dict(label='Crashed Small Scout Farm',groups=['ufo'],missions=mission('Crash'))
        catalogue=with_install(load_catalogue(self.root),installed)
        self.assertEqual(catalogue['maps']['CSmallScout_Farm']['root'],farm)
        self.assertNotIn('CsmallScout_Farm',catalogue['maps'])

    def test_maps_are_chosen_by_the_install_package(self):
        """Review finding 18: two installs' copies of one map (distinct SHA-256): each install's map list serves the
        export of its own file, a file with no export of its own is unprepared, switching back takes the first again,
        and a file changed in place is seen at the next listing."""
        import hashlib
        from catalogue import PackageDigests
        installs = {}
        for name, data in (('lwr', b'LWR copy of the bar'), ('plain', b'plain EW copy of the bar!'), ('other', b'third')):
            cooked = self.root / name / 'XEW' / 'XComGame' / 'CookedPCConsole'
            cooked.mkdir(parents=True)
            (cooked / 'URB_Bar.upk').write_bytes(data)
            installs[name] = cooked / 'URB_Bar.upk'
        sha = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in installs.items()}
        cache = self.root / 'cache'
        for name, version in (('lwr', 30), ('plain', 31)):
            folder = cache / 'URB_Bar' / f'{sha[name][:16]}-v{version}-map'
            folder.mkdir(parents=True)
            (folder / 'scene.json').write_text(json.dumps(dict(schemaVersion=1, exporterVersion=version, name='URB_Bar',
                                                               scope='map', source=dict(sha256=sha[name]))), encoding='utf8')
        installed = dict(URB_Bar=dict(label='Bar', groups=['abduction'], missions=[]))
        digests = PackageDigests(cache)
        def choose(install):
            return with_install(load_catalogue(cache), installed, lambda name: digests.digest(installs[install]))
        lwr, plain, other = choose('lwr'), choose('plain'), choose('other')
        self.assertEqual(lwr['maps']['URB_Bar']['root'].name, f'{sha["lwr"][:16]}-v30-map')
        self.assertEqual(plain['maps']['URB_Bar']['root'].name, f'{sha["plain"][:16]}-v31-map')
        self.assertEqual((other['maps']['URB_Bar']['root'], other['maps']['URB_Bar']['ready'], other['defaultMap']),
                         (None, False, None))
        self.assertEqual(public_catalogue(other)['maps'][0]['ready'], False)
        self.assertEqual(choose('lwr')['maps']['URB_Bar']['root'], lwr['maps']['URB_Bar']['root'])   # switching back
        self.assertEqual(with_install(load_catalogue(cache), installed)['maps']['URB_Bar']['root'].name,
                         f'{sha["plain"][:16]}-v31-map')                                     # file unknown: the newest
        digests.save()
        self.assertEqual(PackageDigests(cache).digest(installs['lwr'])[0], sha['lwr'])        # kept in the cache root
        # the LWR file changed in place (now the plain copy's bytes): the next listing serves the plain export
        catalogue = choose('lwr')
        exports = ExportRunner(catalogue, cache, None, digests=digests)
        installs['lwr'].write_bytes(installs['plain'].read_bytes())
        os.utime(installs['lwr'], (2_000_000_000, 2_000_000_000))
        exports.recheck()
        self.assertEqual(catalogue['maps']['URB_Bar']['root'].name, f'{sha["plain"][:16]}-v31-map')
        installs['lwr'].write_bytes(b'something new')
        exports.recheck()
        self.assertEqual((catalogue['maps']['URB_Bar']['root'], catalogue['maps']['URB_Bar']['ready']), (None, False))

    def test_empty_cache_and_invalid_exact_generation_are_clear_errors(self):
        with self.assertRaisesRegex(ValueError,'No prepared maps'):load_catalogue(self.root)
        root=self.export('Wrong','invalid')
        (root/'scene.json').write_text('{"name":"../escape"}',encoding='utf8',newline='\n')
        with self.assertRaises(ValueError):load_catalogue(root)

    def test_http_assets_are_namespaced_and_cannot_escape_map_roots(self):
        self.export('URB_Bar','current');self.export('TempleShip','current')
        catalogue=load_catalogue(self.root)
        server=LocalServer(('127.0.0.1',0),partial(Handler,catalogue=catalogue))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with urlopen(base+'/maps.json') as response:
                self.assertEqual(json.load(response),public_catalogue(catalogue))
            for name in ('URB_Bar','TempleShip'):
                with urlopen(base+f'/cache/{name}/mesh-1.glb') as response:self.assertEqual(response.read(),name.encode())
            with urlopen(base+'/cache/scene.json') as response:self.assertEqual(json.load(response)['name'],'URB_Bar')
            for path in ('/cache/TempleShip/%2e%2e/%2e%2e/URB_Bar/current/mesh-1.glb',
                         '/cache/TempleShip/%2e%2e%5c%2e%2e%5cURB_Bar/current/mesh-1.glb',
                         '/cache/NotListed/mesh-1.glb'):
                with self.assertRaises(HTTPError) as error:urlopen(base+path)
                self.assertEqual(error.exception.code,404)
        finally:
            server.shutdown();server.server_close();thread.join(timeout=5)

    def test_export_on_first_open(self):
        self.export('URB_Bar','current')
        game=self.root/'install'/'game';cooked=game/'XEW'/'XComGame'/'CookedPCConsole';cooked.mkdir(parents=True)
        for name in ('Alpha','Broken'):(cooked/f'{name}.upk').write_bytes(b'')
        installed={name:dict(label=name,groups=['story'],missions=[]) for name in ('Alpha','Broken','Missing')}
        cache=self.root/'cache';cache.mkdir()
        catalogue=with_install(load_catalogue(self.root),installed)
        script=self.root/'fake_export.py';script.write_text(FAKE_EXPORT,encoding='utf8',newline='\n')
        exports=ExportRunner(catalogue,cache,game,command=lambda package:[sys.executable,'-B',str(script),str(cache),package.stem])
        server=LocalServer(('127.0.0.1',0),partial(Handler,catalogue=catalogue,exports=exports))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        def call(path,post=False):
            try:
                with urlopen(Request(base+path,data=b'' if post else None,method='POST' if post else 'GET')) as response:
                    return response.status,json.load(response)
            except HTTPError as error: return error.code,json.load(error)
        def settle(name):
            for _ in range(100):
                status,state=call(f'/maps/{name}/export.json')
                if state['state']!='running':return state
                time.sleep(0.1)
            self.fail(f'{name} never finished')
        try:
            with self.assertRaises(HTTPError) as denied:urlopen(base+'/cache/Alpha/scene.json')
            self.assertEqual(denied.exception.code,404)
            self.assertEqual(call('/maps/Alpha/export.json')[1]['state'],'idle')
            status,state=call('/maps/Alpha/export',post=True)
            self.assertEqual((status,state['state']),(202,'running'))
            state=settle('Alpha')
            self.assertEqual((state['state'],state['ready'],state['error']),('ready',True,None))
            # progress lines set the bar (the map is 90% of it, its streams the rest) and stay out of the log
            self.assertEqual(state['progress'],dict(what='reading patch_x',done=1,total=1,fraction=1.0))
            self.assertFalse(any(l.startswith('progress:') for l in state['lines']))
            with urlopen(base+'/cache/Alpha/mesh-1.glb') as response:self.assertEqual(response.read(),b'Alpha')
            with urlopen(base+'/maps.json') as response:
                self.assertTrue(next(m for m in json.load(response)['maps'] if m['id']=='Alpha')['ready'])
            self.assertEqual(call('/maps/Alpha/export',post=True)[1]['state'],'ready')   # exported: nothing to do
            call('/maps/Broken/export',post=True)
            state=settle('Broken')
            self.assertEqual((state['state'],state['ready'],state['error']),('failed',False,'ValueError: unsupported export'))
            self.assertEqual(call('/maps/Missing/export',post=True)[0],404)                 # no package in the install
            self.assertEqual(call('/maps/Nowhere/export.json')[0],404)                      # not listed
        finally:
            server.shutdown();server.server_close();thread.join(timeout=5)

    def test_prepare_exports_an_exported_map_again(self):
        """The page's Prepare (editor lights plan: an export older than 18): POST {"prepare": true} exports a ready map
        again, and its entry takes the new generation; a failed one leaves the older generation served."""
        self.export('URB_Bar','current')
        game=self.root/'install'/'game';cooked=game/'XEW'/'XComGame'/'CookedPCConsole';cooked.mkdir(parents=True)
        for name in ('Alpha','Flaky'):(cooked/f'{name}.upk').write_bytes(b'')
        installed={name:dict(label=name,groups=['story'],missions=[]) for name in ('Alpha','Flaky')}
        cache=self.root/'cache';cache.mkdir()
        catalogue=with_install(load_catalogue(self.root),installed)
        script=self.root/'fake_export.py';script.write_text(FAKE_EXPORT,encoding='utf8',newline='\n')
        exports=ExportRunner(catalogue,cache,game,command=lambda package:[sys.executable,'-B',str(script),str(cache),package.stem])
        server=LocalServer(('127.0.0.1',0),partial(Handler,catalogue=catalogue,exports=exports))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        def call(path,body=None,post=False):
            data=json.dumps(body).encode() if body is not None else (b'' if post else None)
            headers={'Content-Type':'application/json'} if body is not None else {}
            try:
                with urlopen(Request(base+path,data=data,headers=headers,method='POST' if post or body is not None else 'GET')) as response:
                    return response.status,json.load(response)
            except HTTPError as error: return error.code,json.load(error)
        def settle(name):
            for _ in range(100):
                status,state=call(f'/maps/{name}/export.json')
                if state['state']!='running':return state
                time.sleep(0.1)
            self.fail(f'{name} never finished')
        version=lambda name:json.load(urlopen(base+f'/cache/{name}/scene.json'))['exporterVersion']
        # an exported map of the install whose export is older than the server's exporter is outdated (the page
        # prepares it again when it opens); the fake's re-export writes 18, so the server's exporter is 18 here
        outdated=lambda:{m['id'] for m in json.load(urlopen(base+'/maps.json'))['maps'] if m.get('outdated')}
        exporter=patch('viewer.EXPORT_VERSION',18);exporter.start();self.addCleanup(exporter.stop)
        try:
            self.assertEqual(outdated(),set())                       # nothing of the install exported yet
            for name in ('Alpha','Flaky'):
                call(f'/maps/{name}/export',post=True)
                self.assertEqual(settle(name)['state'],'ready')
                self.assertEqual(version(name),11)
            self.assertEqual(outdated(),{'Alpha','Flaky'})           # URB_Bar's export isn't of the install
            self.assertEqual(call('/maps/Alpha/export',post=True)[1]['state'],'ready')    # plain: nothing to do
            self.assertEqual(version('Alpha'),11)
            status,state=call('/maps/Alpha/export',body=dict(prepare=True))
            self.assertEqual((status,state['state']),(202,'running'))
            self.assertEqual(settle('Alpha')['state'],'ready')
            self.assertEqual(version('Alpha'),18)
            self.assertEqual(outdated(),{'Flaky'})
            call('/maps/Flaky/export',body=dict(prepare=True))
            state=settle('Flaky')
            self.assertEqual((state['state'],state['ready'],state['error']),('failed',True,'ValueError: the second export fails'))
            self.assertEqual(version('Flaky'),11)                                            # the older one still served
            self.assertEqual(outdated(),{'Flaky'})
        finally:
            server.shutdown();server.server_close();thread.join(timeout=5)


if __name__=='__main__':unittest.main()

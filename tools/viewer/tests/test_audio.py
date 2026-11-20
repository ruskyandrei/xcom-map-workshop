"""A sound's wave for the Effects view's Wave preview (tools/viewer/audio.py; the effects and sounds plan, Part D's
audio route, stage FX2). Made-up Ogg streams for what the check accepts and each thing it refuses; the cache's
refusals; the byte ranges the route answers; and, on the configured install, Bar's Skyranger idle wave read from its
package and served over the route (GET, HEAD, ranges, ETag)."""
from functools import partial
import hashlib
import json
import struct
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import audio  # noqa: E402

IDENT = b'\x01vorbis' + struct.pack('<IBIiiiBB', 0, 2, 44100, 0, 128000, 0, 0xB8, 1)
COMMENT = b'\x03vorbis' + b'\0' * 8 + b'\x01'
SETUP = b'\x05vorbis' + b'\x07' * 300      # longer than one segment: laced 255 + 52


def lacing(packet, finished=True):
    return [255] * (len(packet) // 255) + ([len(packet) % 255] if finished else [])


def page(packets, seq, granule, flags=0, serial=7, lace=None):
    """One Ogg page holding `packets` whole (or the lacing `lace`), its checksum filled in."""
    body = b''.join(packets)
    lace = lace if lace is not None else [n for p in packets for n in lacing(p)]
    head = struct.pack('<4sBBqIIIB', b'OggS', 0, flags, granule, serial, seq, 0, len(lace)) + bytes(lace)
    raw = bytearray(head + body)
    struct.pack_into('<I', raw, 22, audio.crc(bytes(raw)))
    return bytes(raw)


def stream(**change):
    """A good stream: the identification header alone, then the comment and setup headers, then two audio pages, the
    last ending the stream at one second; `change` replaces one page (0-3) by bytes or drops it (None)."""
    pages = [page([IDENT], 0, 0, flags=2), page([COMMENT, SETUP], 1, 0),
             page([b'\0' * 40, b'\0' * 50], 2, 22050), page([b'\0' * 30], 3, 44100, flags=4)]
    for n, value in change.items():
        pages[int(n[1:])] = value
    return b''.join(p for p in pages if p is not None)


class Check(unittest.TestCase):
    def test_the_checksum_is_oggs(self):
        # the CRC-32 of Ogg (polynomial 0x04C11DB7, unreflected, from 0): the check value of '123456789'
        self.assertEqual(audio.crc(b'123456789'), 0x89A1897F)

    def test_a_good_stream(self):
        self.assertEqual(audio.validate(stream()), dict(channels=2, rate=44100, frames=44100, seconds=1.0, pages=4, serial=7))
        # a packet carried over a page boundary, the continued flag set on the next page
        audio_packet = b'\1' * 300
        split = stream(p2=page([audio_packet[:255]], 2, -1, lace=[255]),
                       p3=page([audio_packet[255:]], 3, 44100, flags=4 | 1, lace=[45]))
        self.assertEqual(audio.validate(split)['frames'], 44100)

    def test_what_is_refused(self):
        good = stream()
        flipped = bytearray(good)
        flipped[-1] ^= 1
        cases = [
            (bytes(flipped), 'checksum'),
            (good[:-5], 'ends inside page 3'),
            (good[:len(good) - 40], 'ends inside'),
            (good + b'junk', 'ends inside a page header'),
            (good + b'x' * 30, 'capture pattern'),
            (b'', 'empty'),
            (stream(p3=page([b'\0' * 30], 3, 44100, flags=4, serial=8)), 'another logical stream'),
            (stream(p3=page([b'\0' * 30], 4, 44100, flags=4)), 'numbered 4'),
            (stream(p0=page([IDENT], 0, 0)), 'does not begin'),
            (stream(p2=page([b'\0' * 40], 2, 22050, flags=2)), 'page 2 begins'),       # a chained stream's start
            (stream(p3=page([b'\0' * 30], 3, 44100)), 'page 3 does not end'),
            (stream(p2=page([b'\0' * 40], 2, 22050, flags=4)), 'page 2 ends'),
            (stream(p2=page([b'\0' * 40], 2, 22050, flags=1)), 'continued-packet flag'),
            (stream(p3=page([b'\0' * 30], 3, 100, flags=4)), 'goes back'),
            (stream(p3=page([b'\0' * 255], 3, 44100, flags=4, lace=[255])), 'not finished'),
            (stream(p0=page([IDENT, COMMENT], 0, 0, flags=2), p1=page([SETUP], 1, 0)), 'not alone'),
            (stream(p1=page([COMMENT, SETUP, b'\0' * 9], 1, 0)), 'fresh page'),
            (stream(p0=page([b'\x01opus__' + IDENT[7:]], 0, 0, flags=2)), 'not Vorbis'),
            (stream(p0=page([IDENT[:12] + bytes(4) + IDENT[16:]], 0, 0, flags=2)), 'not valid'),   # a sample rate of 0
            (stream(p1=page([COMMENT, b'\x07vorbis' + b'\0' * 9], 1, 0)), 'comment or setup header'),
            (page([IDENT], 0, 0, flags=2) + page([COMMENT], 1, 0, flags=4), 'fewer than the three'),
            (page([IDENT], 0, 0, flags=2) + page([COMMENT, SETUP], 1, 0, flags=4), 'no audio'),
            (page([b'\0' * 7], 0, 0, flags=2 | 8), 'flags Ogg does not define'),
        ]
        for data, words in cases:
            with self.assertRaises(audio.OggError, msg=words) as caught:
                audio.validate(data)
            self.assertIn(words, str(caught.exception))
        with self.assertRaisesRegex(audio.OggError, 'larger than'):
            audio.validate(good, max_bytes=len(good) - 1)
        version = bytearray(page([IDENT], 0, 0, flags=2))
        version[4] = 1
        with self.assertRaisesRegex(audio.OggError, 'version 1'):
            audio.validate(bytes(version))

    def test_byte_ranges(self):
        for header, want in (('bytes=0-99', (0, 99)), ('bytes=100-', (100, 999)), ('bytes=-10', (990, 999)),
                             ('bytes=900-5000', (900, 999)), ('bytes=-5000', (0, 999)), (None, None), ('', None),
                             ('bytes=0-1,5-6', None), ('items=0-1', None), ('bytes=a-b', None),
                             ('bytes=1000-', False), ('bytes=5-2', False), ('bytes=-0', False)):
            self.assertEqual(audio.byte_range(header, 1000), want, header)


class Refusals(unittest.TestCase):
    SCENE = dict(name='URB_Bar', source=dict(file='URB_Bar.upk', sha256='0' * 64), streams={'patch_bar': {}},
                 soundWaves={'URB_Bar|A.Hum': dict(playable=False, why='its PC sound data is compressed'),
                             'Elsewhere|A.Hum': dict(playable=True)})

    def get(self, wave_id, scene=None):
        return audio.WaveCache().get('root', scene or self.SCENE, wave_id, lambda: 1 / 0, lambda name: 1 / 0)

    def test_ids_the_export_does_not_list(self):
        for wave_id in ('URB_Bar|A.Other', '', 'C:\\Windows\\win.ini', '../URB_Bar|A.Hum'):
            with self.assertRaises(KeyError, msg=wave_id):
                self.get(wave_id)
        # listed, but of a package that is neither the map's nor one of its streams
        with self.assertRaises(KeyError):
            self.get('Elsewhere|A.Hum')

    def test_a_wave_the_export_says_is_not_playable(self):
        with self.assertRaisesRegex(audio.OggError, 'compressed'):
            self.get('URB_Bar|A.Hum')

    def test_a_stream_not_in_the_install(self):
        scene = dict(self.SCENE, soundWaves={'patch_bar|A.Hum': dict(playable=True)})
        with self.assertRaisesRegex(audio.OggError, 'not in the install'):
            audio.WaveCache().get('root', scene, 'patch_bar|A.Hum', None, lambda name: None)

    def test_an_exports_scene_is_read_once_for_each_version_of_it(self):
        """(review finding 50) The wave route reads what it needs of scene.json once, not on every wave played: the
        name, source, stream names and soundWaves, again only when the file changes."""
        import os
        from unittest import mock
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / 'scene.json'
            path.write_text(json.dumps(dict(self.SCENE, objects=[dict(name='XComLevelActor_1')] * 50)), encoding='utf-8')
            cache = audio.WaveCache()
            with mock.patch.object(audio.json, 'loads', wraps=json.loads) as loads:
                first, again = cache.scene(root), cache.scene(root)
                self.assertEqual(loads.call_count, 1)
                self.assertIs(first, again)
                self.assertEqual(first, dict(name='URB_Bar', source=self.SCENE['source'], streams=['patch_bar'],
                                             soundWaves=self.SCENE['soundWaves']))
                # what it keeps answers as the whole scene does
                with self.assertRaisesRegex(audio.OggError, 'compressed'):
                    cache.get(root, first, 'URB_Bar|A.Hum', lambda: 1 / 0, lambda name: 1 / 0)
                with self.assertRaisesRegex(audio.OggError, 'not in the install'):
                    cache.get(root, dict(first, soundWaves={'patch_bar|A.Hum': dict(playable=True)}), 'patch_bar|A.Hum',
                              None, lambda name: None)
                # a re-export writes a new file: read again
                path.write_text(json.dumps(dict(self.SCENE, name='URB_Bar2')), encoding='utf-8')
                st = path.stat()
                os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 10 ** 9))
                self.assertEqual(cache.scene(root)['name'], 'URB_Bar2')
                self.assertEqual(loads.call_count, 2)


# ---------------------------------------------------------------- the configured install

INSTALL, WHY = None, 'no install configured'
try:
    sys.path.insert(0, str(HERE.parents[1] / 'lab'))
    sys.path.insert(0, str(HERE.parents[1] / 'upk'))
    import labpaths  # noqa: E402
    INSTALL, WHY = labpaths.install_map('URB_Bar')
except Exception as error:      # noqa: BLE001
    WHY = str(error)
WAVE = 'URB_Bar|SoundParticleObjects.DropshipIdle'


@unittest.skipUnless(INSTALL and INSTALL.exists(), WHY)
class Install(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sha = hashlib.sha256(INSTALL.read_bytes()).hexdigest()
        cls.scene = dict(name='URB_Bar', source=dict(file=str(INSTALL), sha256=cls.sha), streams={},
                         soundWaves={WAVE: dict(playable=True), 'URB_Bar|SoundParticleObjects.Nothing': dict(playable=True)})

    def test_the_skyrangers_idle_wave(self):
        cache = audio.WaveCache()
        data, etag, record = cache.get('root', self.scene, WAVE, lambda: INSTALL, None)
        self.assertEqual(data[:4], b'OggS')
        # the stream says what the wave's own properties say
        from effects_metadata import wave_record
        from package import Package
        p = Package(INSTALL)
        saved = wave_record(p, p.by_name[WAVE.split('|')[1]])
        self.assertEqual((record['channels'], record['rate']), (saved['channels'], saved['rate']))
        self.assertAlmostEqual(record['seconds'], saved['seconds'], delta=0.05)
        self.assertEqual(len(data), saved['ogg'])
        # kept: the second play takes the same bytes, the package read once
        self.assertIs(cache.get('root', self.scene, WAVE, lambda: INSTALL, None)[0], data)
        self.assertEqual(len(cache.packages), 1)
        # a wave the export lists that isn't in the package
        with self.assertRaisesRegex(audio.OggError, 'is not in URB_Bar.upk'):
            cache.get('root', self.scene, 'URB_Bar|SoundParticleObjects.Nothing', lambda: INSTALL, None)

    def test_a_package_that_is_not_the_exported_one(self):
        scene = dict(self.scene, source=dict(file=str(INSTALL), sha256='0' * 64))
        with self.assertRaisesRegex(audio.OggError, 'not the file this map was exported from'):
            audio.WaveCache().get('root', scene, WAVE, lambda: INSTALL, None)

    def test_the_bound(self):
        cache = audio.WaveCache(budget=1)
        data = cache.get('a', self.scene, WAVE, lambda: INSTALL, None)[0]
        cache.get('b', self.scene, WAVE, lambda: INSTALL, None)
        self.assertEqual([k[0] for k in cache.waves], ['b'])
        self.assertGreater(len(data), 1)

    def test_the_route(self):
        from viewer import Handler, LocalServer
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'scene.json').write_text(json.dumps(dict(self.scene, soundWaves=dict(
                self.scene['soundWaves'], **{'URB_Bar|A.Packed': dict(playable=False, why='its PC sound data is compressed')}))),
                encoding='utf-8', newline='\n')
            catalogue = dict(defaultMap='URB_Bar', maps=dict(URB_Bar=dict(root=root), Alpha=dict(root=None)))
            kept = Handler.wave_cache
            Handler.wave_cache = audio.WaveCache()
            self.addCleanup(setattr, Handler, 'wave_cache', kept)
            server = LocalServer(('127.0.0.1', 0), partial(Handler, catalogue=catalogue))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f'http://127.0.0.1:{server.server_port}/maps/URB_Bar/wave.ogg?id='
            url = base + quote(WAVE)
            try:
                with urlopen(url) as r:
                    whole = r.read()
                    self.assertEqual((r.status, r.headers['Content-Type'], r.headers['Accept-Ranges']), (200, 'audio/ogg', 'bytes'))
                    self.assertEqual(int(r.headers['Content-Length']), len(whole))
                    etag = r.headers['ETag']
                self.assertEqual(audio.validate(whole)['channels'], 1)
                with urlopen(Request(url, method='HEAD')) as r:
                    self.assertEqual((r.status, int(r.headers['Content-Length']), r.read()), (200, len(whole), b''))
                with urlopen(Request(url, headers={'Range': 'bytes=10-109'})) as r:
                    self.assertEqual((r.status, r.headers['Content-Range'], r.read()), (206, f'bytes 10-109/{len(whole)}', whole[10:110]))
                with urlopen(Request(url, headers={'Range': 'bytes=-16'})) as r:
                    self.assertEqual(r.read(), whole[-16:])
                for headers, code in (({'Range': f'bytes={len(whole)}-'}, 416), ({'If-None-Match': etag}, 304)):
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(Request(url, headers=headers))
                    self.assertEqual(caught.exception.code, code)
                for wave_id, code, words in ((WAVE + 'x', 404, 'not one of this map'), ('', 404, 'not one of this map'),
                                             ('URB_Bar|A.Packed', 422, 'compressed')):
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(base + quote(wave_id))
                    self.assertEqual(caught.exception.code, code)
                    self.assertIn(words, json.load(caught.exception)['error'])
                for path, code in (('/maps/Alpha/wave.ogg?id=x', 404), ('/maps/Nowhere/wave.ogg?id=x', 404)):
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(f'http://127.0.0.1:{server.server_port}' + path)
                    self.assertEqual(caught.exception.code, code)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == '__main__':
    unittest.main()

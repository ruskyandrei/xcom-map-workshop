"""A project's map picture (pictures.py and its routes; LWR map packs plan, 4.3): the endpoint takes an opaque
512 x 256 PNG and nothing else, keeps it clean with the project and answers its SHA-256; the project names it through
an ordinary save; a picture sent beside a project's file is taken in; the manager says whose picture a map shows."""
from functools import partial
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from PIL import Image, PngImagePlugin

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalogue import load_catalogue  # noqa: E402
import pictures  # noqa: E402
from projects import ProjectError, ProjectStore  # noqa: E402
from test_projects import ID, OTHER, document  # noqa: E402
from viewer import Handler, LocalServer  # noqa: E402


def png(size=(512, 256), mode='RGB', colour=(40, 90, 160), text=None, alpha=None):
    """A PNG's bytes: one colour with a lighter block, of any size and mode; `text` adds a text chunk, `alpha` (0 to
    255) makes it RGBA with that alpha everywhere."""
    image = Image.new('RGB', size, colour)
    image.paste((200, 180, 60), (size[0] // 4, size[1] // 4, size[0] // 2, size[1] // 2))
    if alpha is not None:
        image = image.convert('RGBA')
        image.putalpha(alpha)
    elif mode != 'RGB':
        image = image.convert(mode)
    info = None
    if text:
        info = PngImagePlugin.PngInfo()
        info.add_text('Comment', text)
    out = io.BytesIO()
    image.save(out, 'PNG', pnginfo=info)
    return out.getvalue()


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Kept(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'projects'
        self.store = ProjectStore(self.root)
        self.folder = self.root / '.workshop' / ID

    def refused(self, data, status=422):
        with self.assertRaises(ProjectError) as caught:
            pictures.save_picture(self.root, ID, data)
        self.assertEqual(caught.exception.status, status)
        self.assertFalse((self.folder / 'picture.png').exists())

    def test_only_an_opaque_512_x_256_png_is_taken(self):
        self.refused(png(size=(256, 256)))
        self.refused(png(size=(1024, 512)))
        self.refused(png(size=(256, 512)))
        self.refused(b'not a picture at all')
        self.refused(b'')
        jpeg = io.BytesIO(); Image.new('RGB', (512, 256)).save(jpeg, 'JPEG')
        self.refused(jpeg.getvalue())
        self.refused(png()[:200])                                   # cut short
        self.refused(png(alpha=128))                                # see-through
        self.refused(png() + bytes(pictures.MAX_BYTES), 413)        # too big
        with self.assertRaises(ProjectError):
            pictures.save_picture(self.root, '../elsewhere', png())
        self.assertFalse(self.root.exists())

    def test_it_is_written_again_clean_and_named_by_its_sha256(self):
        sent = png(text='made on a computer with a name')
        result = pictures.save_picture(self.store, ID, sent)
        kept = (self.folder / 'picture.png').read_bytes()
        self.assertEqual(result, dict(sha256=sha(kept)))
        self.assertNotEqual(kept, sent)
        self.assertNotIn(b'made on a computer', kept)
        self.assertNotIn(b'tEXt', kept)
        with Image.open(io.BytesIO(kept)) as image, Image.open(io.BytesIO(sent)) as original:
            self.assertEqual((image.size, image.mode), ((512, 256), 'RGB'))
            self.assertEqual(image.tobytes(), original.convert('RGB').tobytes())
        # the same pixels sent another way are the same file: an opaque RGBA, a palette picture
        self.assertEqual(pictures.save_picture(self.root, OTHER, png(alpha=255)), result)
        self.assertEqual(pictures.clean(kept), kept)
        self.assertEqual(pictures.picture_file(self.root, ID), self.folder / 'picture.png')
        self.assertEqual(pictures.picture_file(self.store, ID, result['sha256']), self.folder / 'picture.png')
        self.assertIsNone(pictures.picture_file(self.root, ID, 'f' * 64))
        self.assertIsNone(pictures.picture_file(self.root, 'not-an-id'))
        self.assertFalse(list(self.root.rglob('*.tmp')))

    def test_the_saved_revision_keeps_its_picture_through_unsaved_changes(self):
        first = pictures.save_picture(self.root, ID, png())['sha256']
        doc = document(picture=dict(sha256=first))
        self.assertEqual(pictures.named(doc), first)
        self.assertEqual(pictures.project_picture(self.root, doc), self.folder / 'picture.png')
        # a second and a third picture chosen and never saved: the saved one is still found
        second = pictures.save_picture(self.root, ID, png(colour=(90, 20, 20)), saved=first)['sha256']
        self.assertEqual(pictures.project_picture(self.root, doc), self.folder / 'picture.prev.png')
        third = pictures.save_picture(self.root, ID, png(colour=(20, 90, 20)), saved=first)['sha256']
        self.assertEqual(len({first, second, third}), 3)
        self.assertEqual(pictures.project_picture(self.root, doc), self.folder / 'picture.prev.png')
        self.assertEqual(pictures.picture_file(self.root, ID), self.folder / 'picture.png')
        self.assertEqual(sha((self.folder / 'picture.png').read_bytes()), third)
        # removed without a save: still the saved revision's
        self.assertEqual(pictures.remove_picture(self.root, ID, saved=first), dict(removed=True))
        self.assertIsNone(pictures.picture_file(self.root, ID))
        self.assertEqual(pictures.project_picture(self.root, doc), self.folder / 'picture.prev.png')
        self.assertEqual(pictures.remove_picture(self.root, ID, saved=first), dict(removed=False))
        # a project that names a picture this computer does not have, and one that names none
        self.assertIsNone(pictures.project_picture(self.root, document(picture=dict(sha256='e' * 64))))
        self.assertIsNone(pictures.project_picture(self.root, document()))
        self.assertIsNone(pictures.named(document(picture=dict(sha256='nope'))))

    def test_a_picture_beside_a_project_file_is_taken_in_when_its_hash_matches(self):
        data = pictures.clean(png())
        self.store.save(ID, document(picture=dict(sha256=sha(data))), 0)
        path = self.store.path(ID)
        beside = pictures.beside(path)
        self.assertEqual(beside.name, 'Bar remix.picture.png')
        doc = self.store.load(ID)
        # none beside it: nothing happens
        self.assertFalse(pictures.adopt_beside(self.store, path, doc))
        # another picture beside it: left alone
        beside.write_bytes(pictures.clean(png(colour=(1, 2, 3))))
        self.assertFalse(pictures.adopt_beside(self.store, path, doc))
        self.assertTrue(beside.is_file())
        self.assertIsNone(pictures.project_picture(self.store, doc))
        # the project's own: taken in byte for byte, and the file beside it is gone
        beside.write_bytes(data)
        self.assertTrue(pictures.adopt_beside(self.store, path, doc))
        self.assertFalse(beside.exists())
        self.assertEqual(pictures.project_picture(self.store, doc).read_bytes(), data)
        # once kept, a second file beside it is not looked at
        beside.write_bytes(data)
        self.assertFalse(pictures.adopt_beside(self.store, path, doc))
        self.assertTrue(beside.is_file())
        # the projects folder still lists one project: the picture is no project file
        self.assertEqual([p['id'] for p in self.store.list()], [ID])
        # by hand: any map picture for a project, checked against the hash given; not a picture, not taken
        self.assertFalse(pictures.adopt_picture(self.root, OTHER, beside, 'a' * 64))
        (self.root / 'junk.picture.png').write_bytes(b'junk')
        self.assertFalse(pictures.adopt_picture(self.root, OTHER, self.root / 'junk.picture.png'))
        self.assertTrue(pictures.adopt_picture(self.root, OTHER, beside, sha(data), remove=False))
        self.assertTrue(beside.is_file())
        self.assertEqual(pictures.picture_file(self.root, OTHER, sha(data)).read_bytes(), data)

    def test_a_project_s_document_takes_a_picture_record_and_nothing_else_there(self):
        self.store.save(ID, document(picture=dict(sha256='a' * 64)), 0)
        self.assertEqual(self.store.load(ID)['picture'], dict(sha256='a' * 64))
        for bad in (dict(), dict(sha256='A' * 64), dict(sha256='a' * 64, file='somewhere.png'), 'a' * 64, []):
            with self.assertRaises(ProjectError) as caught:
                self.store.save(ID, document(picture=bad), 1)
            self.assertEqual(caught.exception.status, 422)
        # and a save without it takes the picture out of the project
        self.store.save(ID, document(), 1)
        self.assertNotIn('picture', self.store.load(ID))

    def test_whose_picture_a_map_shows(self):
        self.assertEqual(pictures.status(self.root, document()), 'none')
        digest = pictures.save_picture(self.root, ID, png())['sha256']
        self.assertEqual(pictures.status(self.root, document()), 'none')         # kept, but the project names none
        self.assertEqual(pictures.status(self.root, document(picture=dict(sha256=digest))), 'own')
        self.assertEqual(pictures.status(self.root, document(picture=dict(sha256='b' * 64))), 'none')
        # a folder with no map-image packages has no base picture
        self.assertEqual(pictures.status(self.root, document(), self.root), 'none')
        self.assertIsNone(pictures.base_library(self.root, 'URB_Bar'))
        self.assertIsNone(pictures.base_png(self.root, 'URB_Bar'))

    def test_the_preview_is_the_picture_after_dxt1(self):
        data = pictures.clean(png())
        pictures.save_picture(self.root, ID, data)
        shown = pictures.game_png(pictures.picture_file(self.root, ID))
        self.assertEqual(shown, pictures.shown_png(data))
        with Image.open(io.BytesIO(shown)) as a, Image.open(io.BytesIO(data)) as b:
            self.assertEqual((a.size, a.mode), ((512, 256), 'RGB'))
            worst = max(abs(x - y) for x, y in zip(a.tobytes(), b.tobytes()))
        self.assertLess(worst, 12)          # two flat colours: DXT1 keeps them to its 5:6:5 steps
        with self.assertRaises(ProjectError):
            pictures.shown_png(png(size=(100, 50)))


class GamePictures(unittest.TestCase):
    """The base map's picture, from the configured install's map-image packages (skipped without the game)."""
    def test_the_game_s_picture_of_a_map_is_found_by_the_map_s_name(self):
        import settings
        cooked = settings.lwr_cooked()
        if cooked is None or not (cooked / 'UILibrary_MapImages_SF.upk').is_file():
            self.skipTest('no game install with UILibrary_MapImages_SF.upk configured')
        self.assertEqual(pictures.base_library(cooked, 'URB_Bar'), 'UILibrary_MapImages')
        self.assertEqual(pictures.base_library(cooked, 'urb_bar'), 'UILibrary_MapImages')
        self.assertEqual(pictures.base_library(cooked, 'DLC1_1_LowFriends'), 'UILibrary_MapImages_DLC1')
        self.assertEqual(pictures.base_library(cooked, 'EWI_HQAssault'), 'UILibrary_MapImages_HQAssault')
        self.assertIsNone(pictures.base_library(cooked, 'CB2_MP_Blank'))
        with Image.open(io.BytesIO(pictures.base_png(cooked, 'URB_Bar'))) as image:
            self.assertEqual(image.size, (512, 256))
        self.assertIsNone(pictures.base_png(cooked, 'No_Such_Map'))
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(pictures.status(folder, document(), cooked), 'base')


class Routes(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        scene = root / 'cache' / 'URB_Bar' / 'current'; scene.mkdir(parents=True)
        (scene / 'scene.json').write_text(json.dumps(dict(schemaVersion=1, exporterVersion=12, name='URB_Bar', scope='map')), encoding='utf8', newline='\n')
        self.store = ProjectStore(root / 'projects')
        self.server = LocalServer(('127.0.0.1', 0), partial(Handler, catalogue=load_catalogue(root / 'cache'), projects=self.store))
        thread = threading.Thread(target=self.server.serve_forever, daemon=True); thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'
        self.addCleanup(lambda: (self.server.shutdown(), self.server.server_close(), thread.join(timeout=5)))
        self.url = f'/projects/{ID}/picture.png'

    def call(self, method, path, data=None, headers=None):
        """(status, the answer: JSON read, or a picture's bytes)."""
        request = Request(self.base + path, data=data, method=method, headers={'Content-Type': 'image/png', **(headers or {})})
        try:
            with urlopen(request) as response:
                body = response.read()
                return response.status, json.loads(body) if response.headers['Content-Type'] == 'application/json' else body
        except HTTPError as error:
            return error.code, json.load(error)

    def save(self, expected=0, **changes):
        body = json.dumps(dict(expectedRevision=expected, document=document(**changes))).encode()
        return self.call('PUT', f'/projects/{ID}/project.json', body, {'Content-Type': 'application/json'})

    def test_the_picture_is_put_served_previewed_and_removed(self):
        # a project that does not exist keeps no picture
        self.assertEqual(self.call('PUT', self.url, png())[0], 404)
        self.assertEqual(self.save()[0], 200)
        self.assertEqual(self.call('GET', self.url)[0], 404)
        status, kept = self.call('PUT', self.url, png(text='who made it'))
        self.assertEqual(status, 200)
        file = self.store.root / '.workshop' / ID / 'picture.png'
        self.assertEqual(kept, dict(sha256=sha(file.read_bytes())))
        self.assertEqual(self.call('GET', self.url), (200, file.read_bytes()))
        self.assertEqual(self.call('GET', f'{self.url}?sha256={kept["sha256"]}'), (200, file.read_bytes()))
        self.assertEqual(self.call('GET', f'{self.url}?sha256={"0" * 64}')[0], 404)
        status, shown = self.call('GET', f'{self.url}?as=game')
        self.assertEqual((status, shown), (200, pictures.game_png(file)))
        self.assertNotEqual(shown, file.read_bytes())
        # the dialog's preview of a crop not kept yet: the same round trip, and nothing kept by it
        other = png(colour=(120, 30, 30))
        status, previewed = self.call('POST', '/projects/picture-preview', other)
        self.assertEqual((status, previewed), (200, pictures.shown_png(other)))
        self.assertEqual(sha(file.read_bytes()), kept['sha256'])
        self.assertEqual(self.call('POST', '/projects/picture-preview', png(size=(64, 32)))[0], 422)
        # removed
        self.assertEqual(self.call('DELETE', self.url), (200, dict(removed=True)))
        self.assertEqual(self.call('GET', self.url)[0], 404)
        self.assertEqual(self.call('DELETE', self.url), (200, dict(removed=False)))
        self.assertEqual(self.call('GET', f'/projects/not-an-id/picture.png')[0], 404)

    def test_nothing_but_an_opaque_512_x_256_png_from_the_page_itself_is_taken(self):
        self.assertEqual(self.save()[0], 200)
        file = self.store.root / '.workshop' / ID / 'picture.png'
        for body, status in ((png(size=(512, 512)), 422), (png(size=(256, 128)), 422), (b'GIF89a not a png', 422),
                             (png(alpha=10), 422), (png() + bytes(pictures.MAX_BYTES), 413), (b'', 400)):
            self.assertEqual(self.call('PUT', self.url, body)[0], status)
            self.assertFalse(file.exists())
        self.assertEqual(self.call('PUT', self.url, png(), {'Origin': 'http://evil.example'})[0], 403)
        self.assertEqual(self.call('PUT', self.url, png(), {'Host': 'evil.example'})[0], 403)
        self.assertEqual(self.call('DELETE', self.url, headers={'Origin': 'http://evil.example'})[0], 403)
        self.assertEqual(self.call('POST', '/projects/picture-preview', png(), {'Origin': 'http://evil.example'})[0], 403)
        self.assertFalse(file.exists())
        same = {'Origin': f'http://127.0.0.1:{self.server.server_port}'}
        self.assertEqual(self.call('PUT', self.url, png(), same)[0], 200)
        self.assertTrue(file.is_file())
        # the connection is still good after a refused body (the next request is read whole)
        self.assertEqual(self.call('GET', '/projects.json')[0], 200)

    def test_the_project_names_its_picture_through_an_ordinary_save(self):
        self.assertEqual(self.save()[1]['revision'], 1)
        digest = self.call('PUT', self.url, png())[1]['sha256']
        # keeping the picture changes nothing of the project: its revision is the save's
        self.assertEqual(self.store.load(ID)['revision'], 1)
        self.assertNotIn('picture', self.store.load(ID))
        self.assertEqual(self.save(1, picture=dict(sha256=digest))[1]['revision'], 2)
        opened = self.call('GET', f'/projects/{ID}/project.json')[1]
        self.assertEqual((opened['revision'], opened['picture']), (2, dict(sha256=digest)))
        self.assertEqual(self.save(2, picture=dict(sha256='zz'))[0], 422)
        # another picture chosen twice without saving: the saved revision's is still served by its hash
        self.call('PUT', self.url, png(colour=(9, 9, 9)))
        newest = self.call('PUT', self.url, png(colour=(99, 9, 9)))[1]['sha256']
        self.assertEqual(sha(self.call('GET', f'{self.url}?sha256={digest}')[1]), digest)
        self.assertEqual(sha(self.call('GET', self.url)[1]), newest)
        # removed without saving: the same
        self.call('DELETE', self.url)
        self.assertEqual(sha(self.call('GET', f'{self.url}?sha256={digest}')[1]), digest)

    def test_opening_a_project_takes_in_the_picture_sent_beside_its_file(self):
        data = pictures.clean(png())
        self.assertEqual(self.save(picture=dict(sha256=sha(data)))[0], 200)
        beside = pictures.beside(self.store.path(ID))
        beside.write_bytes(data)
        self.assertEqual(self.call('GET', f'{self.url}?sha256={sha(data)}')[0], 404)
        self.assertEqual(self.call('GET', f'/projects/{ID}/project.json')[0], 200)
        self.assertFalse(beside.exists())
        self.assertEqual(self.call('GET', f'{self.url}?sha256={sha(data)}'), (200, data))

    def test_the_game_s_picture_of_a_map_is_served_or_missing(self):
        # this server reads no game install: no map has a picture
        self.assertEqual(self.call('GET', '/map-pictures/URB_Bar.png')[0], 404)
        self.assertEqual(self.call('GET', '/map-pictures/..%2F..%2Fsecret.png')[0], 404)


if __name__ == '__main__':
    unittest.main()

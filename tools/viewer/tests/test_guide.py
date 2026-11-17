"""The user guide as one page (guide.py) and the server's /guide.html."""
from functools import partial
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalogue import load_catalogue
import guide
from viewer import Handler, LocalServer

PICTURE = b'RIFF\x1a\x00\x00\x00WEBPVP8 not a real picture'


class GuideTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'shots').mkdir()
        (self.root / 'shots' / 'one.webp').write_bytes(PICTURE)
        self.source = self.root / 'guide.html'
        self.source.write_text('<p>%s</p><img src="shots/one.webp" width="2"><img src="shots/one.webp">' % guide.VERSION_SLOT,
                               encoding='utf-8', newline='\n')

    def test_the_pictures_go_inside_the_page_and_the_version_in_its_slot(self):
        import base64
        page = guide.inline(self.source, '1.2.3').decode('utf-8')
        data = 'src="data:image/webp;base64,%s"' % base64.b64encode(PICTURE).decode('ascii')
        self.assertEqual(page, '<p><span id="guideVersion">1.2.3</span></p><img %s width="2"><img %s>' % (data, data))
        # a picture that is missing, or a page with no slot for the version, is an error, not a page with a hole
        (self.root / 'shots' / 'one.webp').unlink()
        self.assertRaises(OSError, guide.inline, self.source, '1.2.3')
        self.source.write_text('<p>no slot</p>', encoding='utf-8')
        self.assertRaises(ValueError, guide.inline, self.source, '1.2.3')

    def test_a_release_serves_its_own_file_and_the_repository_its_source(self):
        # the repository: the source made one page, with the editor's version
        page = guide.page()
        self.assertIn(b'<span id="guideVersion">%s</span>' % guide.VERSION.encode(), page)
        self.assertNotIn(b'src="shots/', page)
        # a release: "User Guide.html" two folders up from the module (tools/viewer there), as it is
        kit = self.root / 'kit' / 'tools' / 'viewer'; kit.mkdir(parents=True)
        (self.root / 'kit' / guide.KIT_NAME).write_bytes(b'the release guide')
        with mock.patch.object(guide, 'HERE', kit):
            self.assertEqual(guide.page(), b'the release guide')
        # neither: no guide
        with mock.patch.object(guide, 'HERE', kit / 'none'), mock.patch.object(guide, 'SOURCE', self.root / 'none.html'):
            self.assertTrue(guide.page() is None)

    def test_every_link_inside_the_guide_has_its_place_and_the_contents_lists_clear_map(self):
        import re
        text = guide.SOURCE.read_text(encoding='utf-8')
        ids = set(re.findall(r'\bid="([^"]+)"', text))
        self.assertEqual(sorted({h for h in re.findall(r'href="#([^"]+)"', text)} - ids), [])
        # Clear map, the ground grid and landing zones (private/plans/done/clear-map-plan.md, C8)
        self.assertIn('<li><a href="#clearmap">Clear map and landing zones</a></li>', text)
        for words in ('Clear map…', 'Map grid', 'Ground grid', 'Landing zones', 'Land here', 'Plain EW', 'Used by'):
            self.assertIn(words, text)

    def test_each_picture_shows_at_half_its_pixels_and_every_picture_is_used(self):
        # take_shots.py takes the pictures at device scale 2, and the page shows them at half their pixels; a picture
        # taken again at another size must have its width and height changed in the page (the update-guide skill)
        import re
        from PIL import Image
        text = guide.SOURCE.read_text(encoding='utf-8')
        shots = guide.SOURCE.parent / 'shots'
        tags = re.findall(r'<img src="shots/([^"]+)"([^>]*)>', text)
        self.assertTrue(tags)
        wrong = []
        for name, rest in tags:
            size = re.search(r'width="(\d+)" height="(\d+)"', rest)
            with Image.open(shots / name) as picture: want = tuple(round(v / 2) for v in picture.size)
            if not size or tuple(map(int, size.groups())) != want: wrong.append((name, size and size.groups(), want))
        self.assertEqual(wrong, [])
        self.assertEqual(sorted(p.name for p in shots.glob('*.webp') if p.name not in {n for n, _ in tags}), [])

    def test_the_guide_never_calls_a_thing_untried(self):
        # what ships is usable, tried or not (the user, 16 November 2026): the guide says what happens, never that a
        # thing is untried, not played or how far it is known to work
        import re
        text = guide.SOURCE.read_text(encoding='utf-8')
        # ("not tested" alone stays: the guide uses it of the game's own checks, a prop's pathing sweep)
        words = re.compile(r'untried|untested|not (?:yet )?been (?:tried|played|tested)|not (?:yet )?(?:played|tried)\b'
                           r'|known to work|best guess|been played this way|has been tried', re.I)
        self.assertEqual([m.group(0) for m in words.finditer(re.sub(r'\s+', ' ', text))], [])

    def test_the_server_sends_it_at_guide_html(self):
        scene = self.root / 'cache' / 'URB_Bar' / 'current'; scene.mkdir(parents=True)
        (scene / 'scene.json').write_text(json.dumps(dict(schemaVersion=1, exporterVersion=12, name='URB_Bar', scope='map')), encoding='utf8', newline='\n')
        server = LocalServer(('127.0.0.1', 0), partial(Handler, catalogue=load_catalogue(self.root / 'cache')))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(timeout=5)))
        url = 'http://127.0.0.1:%d/guide.html' % server.server_port
        with urlopen(url) as response:
            body = response.read()
            self.assertEqual((response.status, response.headers['Content-Type']), (200, 'text/html; charset=utf-8'))
        self.assertEqual(body, guide.page())
        with urlopen(Request(url, method='HEAD')) as response:
            self.assertEqual((response.status, int(response.headers['Content-Length']), response.read()), (200, len(body), b''))
        with mock.patch.object(guide, 'page', return_value=None):
            with self.assertRaises(HTTPError) as refused: urlopen(url)
            self.assertEqual(refused.exception.code, 404)


if __name__ == '__main__': unittest.main()

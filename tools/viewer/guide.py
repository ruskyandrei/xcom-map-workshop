"""The user guide as one page. Its source is tools/release/guide/guide.html with its pictures beside it in shots/
(tools/release/guide/take_shots.py makes those). inline() puts the pictures into the page as data URIs and fills in
the version, so the result is a single file that can be copied anywhere: a release carries it as "User Guide.html"
(tools/release/make_release.py), the installer makes a shortcut to it and offers to open it, and the editor serves
it at /guide.html (the ? menu links there): a release's own file, else the repository's source made one page.
"""
import base64
import re
from pathlib import Path

from version import VERSION

HERE = Path(__file__).resolve().parent
KIT_NAME = 'User Guide.html'
SOURCE = HERE.parent / 'release' / 'guide' / 'guide.html'
PICTURE = re.compile(r'src="(shots/[\w.-]+\.webp)"')
VERSION_SLOT = '<span id="guideVersion"></span>'


def inline(source=None, version=VERSION):
    """The guide as one page's bytes: each picture inside it, the version in its slot."""
    source = Path(source or SOURCE)
    text = source.read_text(encoding='utf-8')

    def picture(match):
        data = (source.parent / match.group(1)).read_bytes()
        return 'src="data:image/webp;base64,%s"' % base64.b64encode(data).decode('ascii')
    text = PICTURE.sub(picture, text)
    if VERSION_SLOT not in text:
        raise ValueError('%s has no version slot (%s)' % (source, VERSION_SLOT))
    return text.replace(VERSION_SLOT, VERSION_SLOT.replace('></', '>%s</' % version)).encode('utf-8')


def page():
    """What the server sends for /guide.html, or None when there is no guide: the release's file (two folders up
    from this module there), else the repository's source made one page."""
    kit = HERE.parents[1] / KIT_NAME
    if kit.is_file(): return kit.read_bytes()
    try: return inline()
    except (OSError, ValueError): return None

"""Helpers for updating the user guide (the update-guide skill, .claude/skills/update-guide/SKILL.md):

  compare <folder>                    each picture take_shots.py made in <folder> against the guide's own in shots/:
                                      NEW, SIZE (another size) or how far it differs (a mean over a small copy, 0-255)
  sheet <png> <folder> <name>...      the guide's picture and the new one side by side for each name, in one image,
                                      to look at with an image viewer (a small difference can be only what stands
                                      behind a see-through panel; a large one can be a new button)
  look <folder> <picture or #id>...   the guide made one page (tools/viewer/guide.py, as a release and the guide page
                                      carry it), opened in headless Edge, and a screenshot of the page where each
                                      picture (the start of its alt text) or anchor (#id) is, as <folder>/look-<n>.png

  python tools/release/guide/guide_tools.py compare <scratch>/shots
  python tools/release/guide/guide_tools.py sheet <scratch>/sheet.png <scratch>/shots window.webp rail.webp
  python tools/release/guide/guide_tools.py look <scratch>/look "The project manager" "#flags"

Nothing here changes the guide or its pictures. look needs Playwright, as take_shots.py does; all of it needs Pillow.
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHOTS = HERE / 'shots'


def compare(folder):
    from PIL import Image, ImageChops, ImageStat
    rows = []
    for new in sorted(Path(folder).glob('*.webp')):
        old = SHOTS / new.name
        a = Image.open(new).convert('RGB')
        if not old.is_file():
            rows.append((new.name, 'NEW', '%d x %d' % a.size)); continue
        b = Image.open(old).convert('RGB')
        if a.size != b.size:
            rows.append((new.name, 'SIZE', '%d x %d -> %d x %d' % (b.size + a.size))); continue
        small = (200, max(1, round(200 * a.height / a.width)))
        diff = ImageStat.Stat(ImageChops.difference(a.resize(small), b.resize(small))).mean
        rows.append((new.name, 'diff', '%.2f' % (sum(diff) / 3)))
    for name, kind, what in rows: print('%-22s %-5s %s' % (name, kind, what))
    return rows


def sheet(out, folder, names, scale=0.5):
    from PIL import Image
    pictures = []
    for name in names:
        for path in (SHOTS / name, Path(folder) / name):
            if path.is_file():
                p = Image.open(path).convert('RGB')
                pictures.append(p.resize((max(1, round(p.width * scale)), max(1, round(p.height * scale)))))
    if not pictures: raise SystemExit('none of %s is in %s or %s' % (', '.join(names), SHOTS, folder))
    gap = 10
    out_image = Image.new('RGB', (sum(p.width for p in pictures) + gap * (len(pictures) - 1), max(p.height for p in pictures)), (255, 0, 255))
    x = 0
    for p in pictures:
        out_image.paste(p, (x, 0)); x += p.width + gap
    out_image.save(out)
    print('%s: the guide\'s picture, then the new one, for %s' % (out, ', '.join(names)))


def look(folder, targets):
    sys.path.insert(0, str(HERE.parents[1] / 'viewer'))
    import guide
    from playwright.sync_api import sync_playwright
    folder = Path(folder).resolve(); folder.mkdir(parents=True, exist_ok=True)
    page_file = folder / 'guide.html'
    page_file.write_bytes(guide.inline())
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge', headless=True)
        page = browser.new_page(viewport=dict(width=1440, height=1000))
        page.goto(page_file.as_uri())
        page.wait_for_timeout(1000)
        for n, target in enumerate(targets):
            found = page.locator('[id="%s"]' % target[1:]) if target.startswith('#') else page.locator('img[alt^="%s"]' % target.replace('"', '\\"'))
            if not found.count(): raise SystemExit('the guide has no %s' % (target if target.startswith('#') else 'picture whose alt starts "%s"' % target))
            top = found.first.evaluate('e => e.getBoundingClientRect().top + window.scrollY')
            page.evaluate('y => window.scrollTo(0, y - 60)', top)
            page.wait_for_timeout(300)
            out = folder / ('look-%d.png' % n)
            page.screenshot(path=str(out))
            print('%s  %s' % (out, target))
        browser.close()


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = a.add_subparsers(dest='action', required=True)
    c = sub.add_parser('compare'); c.add_argument('folder', type=Path)
    s = sub.add_parser('sheet'); s.add_argument('out', type=Path); s.add_argument('folder', type=Path); s.add_argument('names', nargs='+')
    s.add_argument('--scale', type=float, default=0.5)
    lk = sub.add_parser('look'); lk.add_argument('folder', type=Path); lk.add_argument('targets', nargs='+')
    args = a.parse_args()
    if args.action == 'compare': compare(args.folder)
    elif args.action == 'sheet': sheet(args.out, args.folder, args.names, args.scale)
    else: look(args.folder, args.targets)


if __name__ == '__main__':
    main()

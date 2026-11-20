# Top-down picture of a cooked XCOM map's play area from a map_inventory.py table, optionally with a remix plan.
#
#   python tools/upk/map_picture.py <inventory.tsv> <out.png> [--plan plan.json ...] [--title "..."]
#
# Draws each actor's box at ground-storey height (boxes reaching below z 250), coloured by kind: ground pieces
# (lying wholly below z 40), buildings (fractured actors and tall meshes), vehicles (VEH_ meshes or archetypes),
# props (other destructibles) and other level meshes. Landing zones from the plan are red rings. Lights, effects,
# decals and volumes are left out. Tile grid every 10 tiles; north (low y) is up.
#
# With --plan it draws a before panel and one after panel per plan (the first plan's origin, size and landing zones
# are used for the before panel). A plan (JSON) gives:
#   origin [x, y], tiles [nx, ny]          the play area (tile 0,0 at origin; 96-unit tiles)
#   landingZones [[x, y], ...]             world units
#   hide [{"min": [tx, ty], "max": [tx, ty]}]             tile boxes cleared like XComMapEdHider (ground kept)
#   building [{"min": [tx, ty], "max": [tx, ty]}]         tile rectangles of the new building (union = footprint)
#   cars [{"tile": [tx, ty], "size": [w, h]}]             new cars, tile rectangles
#   labels [{"tile": [tx, ty], "text": "..."}]
#   blank true                             the after panel starts from nothing (EXP-08): none of the map's pieces,
#                                          only what the plan lays: ground, holes, sidewalks, props (tile rectangles)
#   ground / holes / sidewalks / props [{"min": [tx, ty], "max": [tx, ty]}]   inclusive tile rectangles
import csv, json, argparse

ap = argparse.ArgumentParser()
ap.add_argument('tsv'); ap.add_argument('out')
ap.add_argument('--plan', action='append', default=[], help='a plan JSON; repeat for one after-panel each')
ap.add_argument('--title', default='')
ap.add_argument('--px', type=int, default=16, help='pixels per tile')
a = ap.parse_args()
from PIL import Image, ImageDraw, ImageFont

plans = [json.load(open(p)) for p in a.plan]
plan = plans[0] if plans else {}
OX, OY = plan.get('origin', [-2784, -1920])
NX, NY = plan.get('tiles', [52, 39])
T = 96.0
PX = a.px

COL = {
    'bg': (236, 236, 232), 'ground': (206, 203, 194), 'floor': (196, 160, 116), 'building': (70, 72, 84),
    'vehicle': (70, 118, 194), 'prop': (190, 128, 66), 'other': (140, 140, 140), 'grid': (215, 120, 120),
    'lz': (220, 30, 30), 'hide': (220, 40, 40), 'newwall': (25, 25, 30), 'newfloor': (226, 190, 140),
    'newcar': (40, 170, 220), 'text': (20, 20, 20), 'hole': (30, 30, 34), 'sidewalk': (172, 168, 160),
    'newprop': (226, 120, 40),
}
WALL = ('XComFracLevelActor', 'XComDecoFracLevelActor')
SKIP = ('Light', 'Emitter', 'Decal', 'Volume', 'Note', 'Spawn', 'PointInSpace', 'Prefab', 'VisGroup', 'Sound',
        'LensFlare', 'Pod', 'CoverSeed', 'PlayerStart', 'Interactive', 'KAsset')


def rng(s):
    lo, hi = s.split('..')
    return float(lo), float(hi)


items = []
for r in csv.DictReader(open(a.tsv), delimiter='\t'):
    c = r['class']
    if any(k in c for k in SKIP) or not r['box x']:
        continue
    x0, x1 = rng(r['box x']); y0, y1 = rng(r['box y']); z0, z1 = rng(r['box z'])
    if z0 > 250:
        continue
    if (x1 - x0) * (y1 - y0) > 2500 * T * T:
        continue
    src = r['mesh'] + ' ' + r['archetype']
    if z1 < 40:
        kind = 'floor' if 'Floor' in r['mesh'] or 'Rug' in r['mesh'] else 'ground'
    elif 'VEH_' in src:
        kind = 'vehicle'
    elif c in WALL or (c == 'StaticMeshActor' and z1 - z0 > 150):
        kind = 'building'
    elif c == 'XComDestructibleActor':
        kind = 'prop'
    else:
        kind = 'other'
    items.append(dict(name=r['name'], kind=kind, box=((x0 - OX) / T, (y0 - OY) / T, (x1 - OX) / T, (y1 - OY) / T)))

order = ['ground', 'floor', 'other', 'prop', 'building', 'vehicle']
items.sort(key=lambda i: order.index(i['kind']))


def in_rects(cx, cy, rects):
    return any(r['min'][0] <= cx <= r['max'][0] + 1 and r['min'][1] <= cy <= r['max'][1] + 1 for r in rects)


try:
    font = ImageFont.truetype('arial.ttf', 13); big = ImageFont.truetype('arialbd.ttf', 18)
except OSError:
    font = big = ImageFont.load_default()

M = 30  # margin for labels
W, H = NX * PX + 2 * M, NY * PX + 2 * M + 24


def panel(after, plan=plan):
    im = Image.new('RGB', (W, H), (255, 255, 255)); d = ImageDraw.Draw(im)
    ox, oy = M, M + 24
    d.rectangle([ox, oy, ox + NX * PX, oy + NY * PX], fill=COL['bg'])

    def rect(b, **kw):
        x0, y0, x1, y1 = [max(0, min(v, lim)) for v, lim in zip(b, (NX, NY, NX, NY))]
        if x1 <= x0 or y1 <= y0:
            return
        d.rectangle([ox + x0 * PX, oy + y0 * PX, max(ox + x0 * PX, ox + x1 * PX - 1), max(oy + y0 * PX, oy + y1 * PX - 1)], **kw)

    hide = plan.get('hide', []) if after else []
    blank = after and plan.get('blank')
    if blank:
        for key, col in (('ground', 'ground'), ('sidewalks', 'sidewalk'), ('holes', 'hole')):
            for r in plan.get(key, []):
                rect((r['min'][0], r['min'][1], r['max'][0] + 1, r['max'][1] + 1), fill=COL[col])
    for it in ([] if blank else items):
        x0, y0, x1, y1 = it['box']
        if after and it['kind'] not in ('ground', 'floor') and in_rects((x0 + x1) / 2, (y0 + y1) / 2, hide):
            continue
        rect(it['box'], fill=COL[it['kind']])
    if after:
        bld = plan.get('building', [])
        cells = {(tx, ty) for r in bld for tx in range(r['min'][0], r['max'][0] + 1) for ty in range(r['min'][1], r['max'][1] + 1)}
        for (tx, ty) in cells:
            rect((tx, ty, tx + 1, ty + 1), fill=COL['newfloor'])
        for (tx, ty) in cells:   # walls on the footprint's outline
            for (dx, dy) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if (tx + dx, ty + dy) not in cells:
                    if dx: rect((tx + (1 if dx > 0 else 0) - 0.18, ty, tx + (1 if dx > 0 else 0) + 0.18, ty + 1), fill=COL['newwall'])
                    else: rect((tx, ty + (1 if dy > 0 else 0) - 0.18, tx + 1, ty + (1 if dy > 0 else 0) + 0.18), fill=COL['newwall'])
        if blank:
            for r in plan.get('props', []):
                rect((r['min'][0] + 0.1, r['min'][1] + 0.1, r['max'][0] + 0.9, r['max'][1] + 0.9), fill=COL['newprop'], outline=(110, 50, 10))
        for c in plan.get('cars', []):
            tx, ty = c['tile']; w, h = c['size']
            rect((tx + 0.1, ty + 0.1, tx + w - 0.1, ty + h - 0.1), fill=COL['newcar'], outline=(10, 60, 110))
        for r in hide:
            x0, y0 = r['min']; x1, y1 = r['max']
            for k in range(0, int((x1 + 1 - x0) * PX), 10):
                d.line([ox + x0 * PX + k, oy + y0 * PX, ox + x0 * PX + min(k + 5, (x1 + 1 - x0) * PX), oy + y0 * PX], fill=COL['hide'], width=2)
                d.line([ox + x0 * PX + k, oy + (y1 + 1) * PX, ox + x0 * PX + min(k + 5, (x1 + 1 - x0) * PX), oy + (y1 + 1) * PX], fill=COL['hide'], width=2)
            for k in range(0, int((y1 + 1 - y0) * PX), 10):
                d.line([ox + x0 * PX, oy + y0 * PX + k, ox + x0 * PX, oy + y0 * PX + min(k + 5, (y1 + 1 - y0) * PX)], fill=COL['hide'], width=2)
                d.line([ox + (x1 + 1) * PX, oy + y0 * PX + k, ox + (x1 + 1) * PX, oy + y0 * PX + min(k + 5, (y1 + 1 - y0) * PX)], fill=COL['hide'], width=2)
        for l in plan.get('labels', []):
            tx, ty = l['tile']
            d.text((ox + tx * PX, oy + ty * PX), l['text'], fill=COL['text'], font=font)
    for tx in range(0, NX + 1, 10):
        d.line([ox + tx * PX, oy, ox + tx * PX, oy + NY * PX], fill=COL['grid'], width=1)
        d.text((ox + tx * PX - 6, oy - 16), str(tx), fill=COL['grid'], font=font)
    for ty in range(0, NY + 1, 10):
        d.line([ox, oy + ty * PX, ox + NX * PX, oy + ty * PX], fill=COL['grid'], width=1)
        d.text((ox - 24, oy + ty * PX - 7), str(ty), fill=COL['grid'], font=font)
    for (x, y) in plan.get('landingZones', []):
        cx, cy = ox + (x - OX) / T * PX, oy + (y - OY) / T * PX
        d.ellipse([cx - 1.6 * PX, cy - 1.6 * PX, cx + 1.6 * PX, cy + 1.6 * PX], outline=COL['lz'], width=3)
        d.text((cx - 5, cy - 8), 'LZ', fill=COL['lz'], font=font)
    d.rectangle([ox, oy, ox + NX * PX, oy + NY * PX], outline=(60, 60, 60), width=2)
    return im, d


title = a.title or 'URB_Bar'
panels = [('Before: ' + title, panel(False))]
for pl in plans:
    panels.append(('After: ' + pl.get('name', 'plan'), panel(True, pl)))
LEG = 44
out = Image.new('RGB', (W * len(panels), H + LEG), (255, 255, 255)); d = ImageDraw.Draw(out)
for i, (t, (im, _)) in enumerate(panels):
    out.paste(im, (i * W, 0))
    d.text((i * W + M, 6), t, fill=COL['text'], font=big)
legend = [('ground / pavement', 'ground'), ('floor slab, rug', 'floor'), ('building walls', 'building'),
          ('props', 'prop'), ('vehicles', 'vehicle'), ('other meshes', 'other')]
if plan:
    legend += [('new building', 'newwall'), ('new floor', 'newfloor'), ('new cars', 'newcar'), ('cleared (hider box)', 'hide'), ('landing zone', 'lz')]
    if any(p.get('blank') for p in plans):
        legend += [('new sidewalk', 'sidewalk'), ('new props', 'newprop'), ('no ground', 'hole')]
x = M
for text, k in legend:
    d.rectangle([x, H + 14, x + 16, H + 30], fill=COL[k], outline=(80, 80, 80))
    d.text((x + 22, H + 15), text, fill=COL['text'], font=font)
    x += 30 + int(d.textlength(text, font=font))
out.save(a.out)
print('wrote', a.out, out.size, len(items), 'boxes')

"""A prefab's dimensions, and what the editor says of one larger than a map can hold.

Geometry comes from the same library GLBs the page draws, including component transforms.
Unavailable sources are reported, never treated as zero-size geometry. The limits warn and refuse nothing (plan
"sturdier prefabs", R7): a prefab over them is saved and placed, with what it means said. Only the prefab test
has a real limit, its stage's (tools/editor/prefab_stage.py).
"""
from functools import lru_cache
import itertools
import json
import math
from pathlib import Path
import struct

import numpy as np

from export_math import transform, view_matrix
from projects import ProjectError

TILE, MAX_TILES, SLACK = 96, 128, 0.5
# Heights (prefab plan 5.6b; 30 levels since 14 November 2026): the grid is 30 levels of 64 from the prefab's ground
# (the game's own maps go to 18, PLAYED_LEVELS: over that it has not been played), and anything may stick out 192 units
# (three levels) under or over it: a hull or a crater, a roof, floor boxes, lights.
LEVEL, GRID_LEVELS, PLAYED_LEVELS, ALLOWANCE = 64, 30, 18, 192
GRID_TOP = LEVEL * GRID_LEVELS
PLAYED_TOP = LEVEL * PLAYED_LEVELS
MIN_Z, MAX_Z = -ALLOWANCE, GRID_TOP + ALLOWANCE


def footprint(bounds):
    low = [math.floor((bounds[k] + SLACK) / TILE) * TILE for k in range(2)]
    tiles = [max(1, math.ceil((bounds[k + 3] - low[k] - SLACK) / TILE)) for k in range(2)]
    return low, tiles


def policy(boxes, unknown=()):
    """The size verdict: dict(bounds, tiles, unknown, warnings, verified, outside: the names of what reaches out of
    the grid's 0 to GRID_TOP into the allowance, where it has no tiles; tall: it reaches over the 18 levels the game's
    own maps have). `warnings` say what is over the limits; nothing is refused, so `errors` is empty and `supported`
    true, kept for the callers that read them."""
    bounds = None
    offenders, outside = [], []
    for name, box in boxes:
        if bounds is None: bounds = list(box)
        else: bounds = [min(bounds[k], box[k]) if k < 3 else max(bounds[k], box[k]) for k in range(6)]
        if box[2] < MIN_Z - SLACK or box[5] > MAX_Z + SLACK: offenders.append(name)
        elif (box[2] < -SLACK or box[5] > GRID_TOP + SLACK) and name not in outside: outside.append(name)
    bounds = bounds or [0, 0, 0, 0, 0, 0]
    _, tiles = footprint(bounds)
    warnings = []
    if max(tiles) > MAX_TILES:
        warnings.append(f'{tiles[0]} by {tiles[1]} tiles is over 128 by 128 tiles, the largest map the editor makes: '
                        'no map holds it whole, and it can\'t be tested on the stage')
    if offenders:
        warnings.append(f'height {bounds[2]:g} to {bounds[5]:g} reaches past {MIN_Z} to {MAX_Z} units, where a map has '
                        'no tiles: ' + ', '.join(offenders[:8]))
    return dict(bounds=bounds, tiles=tiles, unknown=list(unknown), errors=[], warnings=warnings, supported=True,
                verified=not unknown, outside=outside, tall=bounds[5] > PLAYED_TOP + SLACK)


@lru_cache(maxsize=256)
def vertices(path, stamp):
    """Read POSITION from our geometry-only GLB, in the viewer basis, as homogeneous rows."""
    raw = Path(path).read_bytes()
    size = struct.unpack_from('<I', raw, 12)[0]
    doc = json.loads(raw[20:20 + size])
    start = 28 + size
    attributes = {p['attributes']['POSITION'] for m in doc['meshes'] for p in m['primitives']}
    parts = []
    for index in attributes:
        a = doc['accessors'][index]; v = doc['bufferViews'][a['bufferView']]
        if a['componentType'] != 5126 or a['type'] != 'VEC3': raise ValueError('Unsupported POSITION format')
        pts = np.ndarray((a['count'], 3), dtype='<f4', buffer=raw,
                         offset=start + v.get('byteOffset', 0) + a.get('byteOffset', 0),
                         strides=(v.get('byteStride', 12), 4))
        parts.append(np.column_stack((pts, np.ones(len(pts)))))
    return np.concatenate(parts) if parts else np.empty((0, 4))


def matrix(location, rotation):
    return np.array(view_matrix(transform(location, rotation, [1, 1, 1]))).reshape((4, 4), order='F')


def extent(points, placement):
    posed = points @ placement.T
    return [*posed[:, [0, 2, 1]].min(axis=0).tolist(), *posed[:, [0, 2, 1]].max(axis=0).tolist()]


def measure(document, library=None, *, resolved=None, recipes=None):
    from compiler import COVER_RECIPES, cover_shape
    from library import pieces_root
    boxes, unknown, records = [], [], {}
    hashes = {d['package'].casefold(): d.get('sha256') for d in document.get('donors', [])} if recipes is not None else {}
    sources = {(p['from']['package'], p['from']['actor']): dict(p['from'], actor=p['from']['actor'].split('.')[-1])
               for p in document['pieces'] if p.get('from')}
    # Every record read in one batch (the server's library: the install found and its maps listed once, each donor
    # opened once, a piece not exported yet exported then): asked one by one, each piece looked the install up and
    # listed its cooked folder again, about 13 s for an 800-piece selection with every piece already exported. A
    # piece the batch could not give is unknown, as one that fails below is.
    if resolved is None and library is not None and sources and hasattr(library, 'records'):
        keys = list(sources)
        answers = library.records([sources[key] for key in keys])
        resolved = {key: answer['record'] for key, answer in zip(keys, answers) if answer.get('record')}
    for piece in document['pieces']:
        name = piece['actor']; template = piece.get('template', {})
        if template.get('kind') in ('point', 'spot'):
            boxes.append((name, piece['location'] * 2))
        elif template.get('kind') == 'cover':
            recipe = COVER_RECIPES.get(template['version'])
            c = piece['cover']
            if isinstance(c, dict) and set(c) == {'width', 'length', 'height'} and isinstance(c['height'], str):
                c = dict(width=c['width'], length=c['length'], type=c['height'], height=1)     # a first record
            shape = cover_shape(c, recipe) if recipe is not None else None
            if shape is None:
                unknown.append(name); continue
            _, (sx, sy), (z0, z1) = shape     # whole tiles or units (compiler.cover_shape)
            pts = np.array([[x, z, y, 1] for x, y, z in itertools.product((0, sx), (0, sy), (z0, z1))])
            boxes.append((name, extent(pts, matrix(piece['location'], piece['rotation']))))
        else:
            source = piece['from']; key = (source['package'], source['actor'])
            try:
                if library is None: raise ValueError('No source library')
                if resolved is not None:
                    record = resolved[key]
                else:
                    if key not in records:
                        records[key] = library.piece(sources[key])
                    record = records[key]
                base = record['base'].removeprefix('/cache-library/')
                folder = pieces_root(library.cache) / base
                objects = {o['component']: o for o in record['objects'] if o['actor'] == source['actor'] or o['actor'].split('.')[-1] == source['actor']}
                pending = []
                for component in piece['components']:
                    o = objects[component]; mesh = record['meshes'][o['mesh']]
                    path = folder / mesh['url']
                    pts = vertices(str(path), path.stat().st_mtime_ns)
                    if not len(pts): raise ValueError('No geometry')
                    placement = matrix(piece['location'], piece['rotation']) @ np.linalg.inv(matrix(o['location'], o['rotation'])) @ np.array(o['matrix']).reshape((4, 4), order='F')
                    box = extent(pts, placement)
                    if not all(math.isfinite(v) for v in box): raise ValueError('Nonfinite geometry')
                    pending.append((name, box))
                boxes.extend(pending)
                if recipes is not None:
                    actor = next(iter(objects.values()))['actor']
                    recipe = (record.get('recipes') or {}).get(actor)
                    expected = hashes.get(source['package'].casefold())
                    if recipe and (expected is None or expected == record['source']['sha256']):
                        old = piece.get('recipe')
                        if not old or (old['key'] == recipe['key'] and not old.get('member') and recipe.get('member')):
                            recipes[name] = recipe
            except (ProjectError, OSError, ValueError, KeyError, struct.error, np.linalg.LinAlgError):
                unknown.append(name)
    for b in document.get('buildings', []):
        for f in b['floors']:
            boxes.extend((b.get('name') or b['id'], box) for box in f['boxes'])
    # An unknown mesh's actor pivot is not its physical bound (it may be far outside
    # the geometry). Preserve its prior envelope; do not invent a height from its pivot.
    if unknown:
        nx, ny = document['floor']['tiles']
        boxes.append(('Unresolved footprint', [0, 0, 0, nx * TILE, ny * TILE, 0]))
    return policy(boxes, unknown)


def require_supported(document, library=None, *, recipes=None):
    """The prefab measured for a save. It refused a prefab over the limits once; they warn now (R7), so this is
    measure() under the name its callers know."""
    return measure(document, library, recipes=recipes)

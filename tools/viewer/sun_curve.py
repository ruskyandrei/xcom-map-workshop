"""The time of day's curve (the game-likeness plan's track T): sun_curve.json, the one home the page (sun_rules.js, by
the server's /sun-curve.json) and the compiler both read, and the shape of the project's `sun` (schema 10) by its
limits.

Each row of the curve is a light one of the game's own maps has (research/evidence/sun-audit-2026-11-27.json, F-175):
the sun or moon's height and side rule, its colour and brightness, the sky light's, and the fog's two colours and the
grade's tint and shadows beside it. The page blends them at the bar's time; the record a project saves holds the
values it ended with (sun_rules.js `timeSet`), so a later change to the curve never changes a saved project.
"""
import json
import math
from pathlib import Path

CURVE_FILE = Path(__file__).resolve().with_name('sun_curve.json')
KEYS = ('time', 'heading', 'timeOfDay', 'light', 'sky', 'custom', 'atmosphere')
TIMES_OF_DAY = ('auto', 'day', 'night')
DAY = 24


def load(path=CURVE_FILE):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _colour(v):
    return isinstance(v, list) and len(v) == 3 and all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 255
                                                       for c in v)


def _within(v, limits):
    return _number(v) and limits[0] <= v <= limits[1]


def problem(record, curve=None):
    """None for a `sun` record the page and the compiler read, else what is wrong with it, in words (the page's
    sun_rules.js validSun holds the same; tools/viewer/tests/sun_record_cases.json holds both)."""
    curve = curve or load()
    limits = curve['limits']
    if not isinstance(record, dict):
        return 'it is not a record'
    extra = sorted(set(record) - set(KEYS))
    if extra:
        return 'it has %s, which the record has not' % ', '.join(extra)
    if not (_number(record.get('time')) and 0 <= record['time'] < DAY):
        return 'its time is not an hour from 0 to 24'
    if not _number(record.get('heading')):
        return 'its heading is not a number'
    if record.get('timeOfDay') not in TIMES_OF_DAY:
        return 'its time of day is not auto, day or night'
    light = record.get('light')
    if not (isinstance(light, dict) and isinstance(light.get('rotation'), list) and len(light['rotation']) == 3
            and all(isinstance(v, int) and not isinstance(v, bool) for v in light['rotation'])):
        return 'its light has no rotation of three whole numbers'
    if not (_colour(light.get('color')) and _within(light.get('brightness'), limits['brightness'])):
        return 'its light\'s colour or brightness is not one the game takes'
    sky = record.get('sky')
    if sky is not None and not (isinstance(sky, dict) and _colour(sky.get('color')) and _colour(sky.get('lowerColor'))
                                and _within(sky.get('brightness'), limits['skyBrightness'])
                                and _within(sky.get('lowerBrightness'), limits['skyBrightness'])):
        return 'its sky light is not a colour, a brightness, a lower colour and a lower brightness'
    custom = record.get('custom')
    if custom is not None and not (isinstance(custom, list) and all(k in curve['custom'] for k in custom)):
        return 'it says a value is set by hand that the bar does not set'
    marks = record.get('atmosphere')
    if marks is not None and not (isinstance(marks, dict) and set(marks) <= {'fog', 'postProcess'}
                                  and all(isinstance(v, dict) and all(map(_value, v.values())) for v in marks.values())):
        return 'its fog and grade of the hour are not {fog, postProcess} of plain values'
    return None


def _value(v):
    # a member's value as the atmosphere's records have it (the page's atmosphere_rules.js isValue)
    return _number(v) or isinstance(v, (bool, str)) or (isinstance(v, list) and 3 <= len(v) <= 4 and all(map(_number, v)))

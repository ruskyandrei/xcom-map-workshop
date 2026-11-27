"""The map's atmosphere a project changes (game-likeness plan, stage C5), for the compiler.

The project's `atmosphere`: {"fog": {member: value}, "postProcess": {member: value}}, only the members it changes of
the map's height fog (an XComHeightFogParameters) and its post-process settings (a PostProcessSettings), in the
export's form (tools/viewer/atmosphere.py): a number, true or false, a colour as four numbers from 0 to 1, a vector as
three numbers, an enum member's name.

Each value is held to its member's kind (tools/viewer/atmosphere_defaults.json `kinds`, the script packages'
declarations). A member the struct lacks, one a project does not set (an object, the LUT blender's state, an array) or
a value of another kind is left out (atmosphere-value), and the rest builds. A changed post-process member that a
post-process volume of the map overrides is warned of (atmosphere-volume): where the camera is inside that volume, the
game shows the volume's value.

An AtmosphereEdits works for one Compiler, as the other families do. `lane` is the spec's `atmosphere`, or None:
compiler.native_split hands it to the Build, which writes it on the map's WorldInfo (tools/bake/native_world.py).
"""
import math

SECTIONS = ('fog', 'postProcess')
NOT_SET = {'ColorGradingLUT', 'ColorGrading_LookupTable', 'DOF_BokehTexture', 'DisabledMaterialEffects'}
WORDS = {'fog': 'height fog', 'postProcess': 'post-process settings'}


def _kinds():
    import atmosphere
    return atmosphere.load_defaults()['kinds']


def tidy(kind, value):
    """The value in the lane's form for a member of `kind` ([property kind, struct name]), or None when it isn't one."""
    prop, sub = kind

    def number(v):
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None

    def numbers(n, lo=None, hi=None):
        if not isinstance(value, list) or len(value) != n:
            return None
        out = [number(v) for v in value]
        if any(v is None or (lo is not None and not lo <= v <= hi) for v in out):
            return None
        return out
    if prop == 'BoolProperty':
        return value if isinstance(value, bool) else None
    if prop == 'FloatProperty':
        return number(value)
    if prop == 'ByteProperty':
        return value if isinstance(value, str) and value.isidentifier() else None
    if prop == 'StructProperty' and sub == 'Color':
        return numbers(4, 0.0, 1.0)
    if prop == 'StructProperty' and sub == 'LinearColor':
        return numbers(4)
    if prop == 'StructProperty' and sub == 'Vector':
        return numbers(3)
    return None


class AtmosphereEdits:
    def __init__(self, compiler):
        self.c = compiler
        self.lane = None                # the spec's `atmosphere`, or None
        self.counts = dict(fog=0, postProcess=0)

    def check(self):
        """The project's `atmosphere` checked into the lane: each value held to its member's kind (left out where it
        can't be had), each changed post-process member a volume of the map overrides warned of."""
        self.lane = None
        rec = self.c.doc.get('atmosphere')
        if rec is None:
            return
        where = dict(record='atmosphere')
        if not isinstance(rec, dict) or not set(rec) <= set(SECTIONS) or not all(isinstance(rec[k], dict) for k in rec):
            self.c.leave_out('atmosphere-shape', 'The project\'s fog and colour must be {"fog": {member: value}, '
                             '"postProcess": {member: value}}: it is left out, and the map keeps its own.', **where)
            return
        kinds = _kinds()
        lane = {}
        for key in SECTIONS:
            for name, value in sorted((rec.get(key) or {}).items()):
                kind = kinds[key].get(name)
                tidied = tidy(kind, value) if kind and name not in NOT_SET else None
                if tidied is None:
                    self.c.leave_out('atmosphere-value', 'The %s have no member %s a project sets, or %r is not its kind of '
                                     'value: it is left out, and the map keeps its own.' % (WORDS[key], name, value),
                                     record='atmosphere', member='%s.%s' % (key, name))
                    continue
                lane.setdefault(key, {})[name] = tidied
        self.counts = {key: len(lane.get(key) or {}) for key in SECTIONS}
        self.lane = lane or None
        if lane.get('postProcess'):
            self.volumes(lane['postProcess'])

    def volumes(self, changed):
        """A warning for each of the map's post-process volumes that overrides a member the project changes."""
        import atmosphere
        for volume in ((self.c.scene.get('atmosphere') or {}).get('volumes') or []):
            if not volume.get('enabled', True):
                continue
            settings = volume.get('settings') or {}
            over = sorted(name for name in changed if settings.get(atmosphere.override_flag(name)))
            if over:
                self.c.warn('atmosphere-volume', 'The map\'s post-process volume %s sets %s itself: where the camera is '
                            'inside it, the game shows the volume\'s value, not the project\'s.'
                            % (volume.get('name'), ', '.join(over)), record='atmosphere', volume=volume.get('name'))

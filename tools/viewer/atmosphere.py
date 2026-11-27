"""A map's atmosphere: its height fog, colour grade, bloom and fog-of-war colours as the game applies them, read
from its WorldInfo and its post-process volumes (the game-likeness plan, stage C1; F-168). The user sees "Fog and
colour"; in code it is the atmosphere, because "looks" names the made pieces' looks.

A map saves only the members of a struct that differ from its class's defaults (Dirt Road's fog saves four), so each
value here is the map's saved member over the class default object's (Default__WorldInfo, Default__PostProcessVolume)
over the struct's own defaults. Those two layers of defaults are read once from the script packages into
atmosphere_defaults.json beside this (`python -B tools/viewer/atmosphere.py defaults <CookedPCConsole> --write`),
and its test reads the install again and compares.

  read(p, defaults=None) -> dict | None         a map package's atmosphere (export 43's scene.json `atmosphere`)
  make_defaults(cooked) -> dict                 the defaults, from the script packages
"""
import argparse
import json
from pathlib import Path
import struct
import sys
if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.append(str(Path(__file__).resolve().parents[1]))     # tools/paths.py (review finding 54)
import paths  # noqa: E402

from package import Package, Reader, FormatError  # noqa: E402

HERE = Path(__file__).resolve().parent
DEFAULTS_FILE = HERE / 'atmosphere_defaults.json'
# where each struct is declared, and the default objects that set it
STRUCTS = {'fog': ('Engine', 'WorldInfo.XComHeightFogParameters'),
           'postProcess': ('Engine', 'PostProcessVolume.PostProcessSettings')}
OWNERS = {'world': ('Engine', 'Default__WorldInfo', {'fog': 'XComHeightFog', 'postProcess': 'DefaultPostProcessSettings'}),
          'volume': ('Engine', 'Default__PostProcessVolume', {'postProcess': 'Settings'})}
# members that are no value of the look (an array of effects turned off, the LUT blender's state, a bokeh texture)
SKIPPED = {'DisabledMaterialEffects', 'ColorGradingLUT', 'DOF_BokehTexture'}


def plain(p, item):
    """A tagged property's value as JSON: numbers, bools, lists (colours 0 to 1, vectors), names; an object as its
    name (None when none); None for what it can't say."""
    value = item['value']
    if item['kind'] == 'ObjectProperty':
        return p.name(value) if isinstance(value, int) and value else None
    if isinstance(value, (bytes, bytearray, memoryview)):
        return None
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, list):
        return [round(v, 6) if isinstance(v, float) else v for v in value]
    return value


def members(p, raw):
    """{member: value} of a tagged struct's saved bytes."""
    out = {}
    for (name, slot), item in p.tagged(Reader(bytes(raw))).items():
        if slot == 0 and name not in SKIPPED:
            value = plain(p, item)
            if value is not None or item['kind'] == 'ObjectProperty':
                out[name] = value
    return out


def struct_defaults(p, path):
    """{member: value} of a ScriptStruct's own defaults in a script package: the tagged properties after its script
    and flags (tools/upk/schema.py reads the same layout)."""
    index = p.by_name.get(path)
    if index is None or p.cls(index) != 'ScriptStruct':
        raise FormatError('no struct %s in %s' % (path, p.path.name))
    e = p.exports[index - 1]
    d = p.data[e['off']:e['off'] + e['size']]
    sizes = struct.unpack_from('<ii', d, 12 + 28)
    start = e['off'] + 12 + 40 + sizes[1]
    out = {}
    for (name, slot), item in p.tagged(Reader(p.data, start, e['off'] + e['size'])).items():
        if slot == 0 and name not in SKIPPED:
            out[name] = plain(p, item)
    return out


# the override flag of a post-process member whose flag is not bOverride_<member> (bOverride_<member less its b> for a
# bEnable member): XCOM's own members, and the LUT
OWN_FLAGS = {'XComFogOfWarColor': 'bOverrideXComFOWColor', 'XComFOWColor': 'bOverrideXComFOWColor',
             'HaveSeenTintColor': 'bOverrideXComHaveSeenTint', 'RimShader_Color': 'bOverrideRimShaderColor',
             'XComFOWBorderFadeOutColor': 'bOverrideXComFOWBorderSettings',
             'XComFOWBorderFadeOutRate': 'bOverrideXComFOWBorderSettings',
             'XComFOWBorderFadeInRate': 'bOverrideXComFOWBorderSettings',
             'ColorGrading_LookupTable': 'bOverride_Scene_ColorGradingLUT'}


def override_flag(name, members=None):
    """The flag that says a post-process member is set (the game's editor saves it on with the member; a volume's
    member counts only where it is on), or None for a flag itself, or one `members` (a struct's names) lacks."""
    if name.startswith('bOverride'):
        return None
    flag = OWN_FLAGS.get(name) or ('bOverride_' + name[1:] if name.startswith('bEnable') else 'bOverride_' + name)
    return flag if members is None or flag in members else None


def member_kinds(cooked):
    """{'fog' | 'postProcess': {member: [property kind, its struct's short name or None]}} of the two structs, from the
    script packages' declarations (tools/upk/schema.py over Core and Engine): what a Build writes a changed member as
    (tools/bake/native_world.py) and what the compiler holds a project's value to (tools/editor/atmosphere_edits.py)."""
    paths.use('upk')
    import schema
    s = schema.Schema(schema.build(Path(cooked), packages=('Core', 'Engine')))
    out = {}
    for key, (pkg, path) in STRUCTS.items():
        out[key] = {name: [prop['kind'], prop['struct'].rsplit('.', 1)[-1] if isinstance(prop.get('struct'), str) else None]
                    for name, prop in s.members('%s.%s' % (pkg, path)) if name not in SKIPPED}
    return out


def make_defaults(cooked):
    """The defaults of each owner's structs: the struct's own with its default object's saved members over them."""
    cooked = Path(cooked)
    packages = {}

    def package(name):
        if name not in packages:
            packages[name] = Package(cooked / (name + '.upk'))
        return packages[name]
    structs = {key: struct_defaults(package(pkg), path) for key, (pkg, path) in STRUCTS.items()}
    out = {'version': 2, 'structs': structs, 'kinds': member_kinds(cooked)}
    for owner, (pkg, name, props) in OWNERS.items():
        p = package(pkg)
        index = p.by_name.get(name)
        if index is None:
            raise FormatError('no %s in %s' % (name, pkg))
        entry = {}
        for key, prop in props.items():
            raw = p.own(index, prop)
            entry[key] = dict(structs[key], **(members(p, raw) if raw else {}))
        out[owner] = entry
    return out


def load_defaults(path=DEFAULTS_FILE):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def read(p, defaults=None):
    """The map's atmosphere: {'world': {'fog', 'postProcess' (every member, the map's over the defaults), 'saved':
    {'fog', 'postProcess': the members the map itself saves}, 'environmentColor'}, 'volumes': [{'name', 'box'
    (min, max: game units), 'priority', 'enabled', 'unbound', 'settings' (the members it saves, its bOverride_
    flags among them)}]}; None for a package with no WorldInfo (a streamed level)."""
    defaults = defaults or load_defaults()
    world = next((i for i in range(1, len(p.exports) + 1) if p.cls(i) in ('WorldInfo', 'XComWorldInfo')
                  and p.paths[i - 1].startswith('TheWorld.PersistentLevel.')), None)
    if world is None:
        return None
    saved = {}
    out = {'class': p.cls(world)}
    for key, prop in (('fog', 'XComHeightFog'), ('postProcess', 'DefaultPostProcessSettings')):
        raw = p.own(world, prop)
        saved[key] = members(p, raw) if raw else {}
        out[key] = dict(defaults['world'][key], **saved[key])
    out['saved'] = {k: sorted(v) for k, v in saved.items()}
    material = p.own(world, 'XComMaterialParameters')
    env = members(p, material).get('EnvironmentColorAndEmissiveFade') if material else None
    out['environmentColor'] = env
    volumes = []
    from scene_metadata import volume_bounds
    for index, name in enumerate(p.paths, 1):
        if p.cls(index) != 'PostProcessVolume' or not name.startswith('TheWorld.PersistentLevel.'):
            continue
        raw = p.own(index, 'Settings')
        try:
            box = volume_bounds(p, index)
        except (FormatError, ValueError, struct.error):
            box = None
        volumes.append(dict(name=name.rsplit('.', 1)[-1], box=box, priority=p.effective(index, 'Priority', 0.0),
                            enabled=bool(p.effective(index, 'bEnabled', True)),
                            unbound=bool(p.effective(index, 'bUnbound', False)),
                            settings=members(p, raw) if raw else {}))
    return {'world': out, 'volumes': volumes}


CATALOGUE_FILE = HERE / 'atmospheres.json'
# the post-process members a look carries (the Game look's bloom and grade: tools/viewer/web/post_grade.js)
LOOK_POST = ('bEnableBloom', 'Bloom_Scale', 'Bloom_Threshold', 'Bloom_Tint', 'Bloom_ScreenBlendThreshold',
             'DOF_BlurBloomKernelSize', 'bEnableSceneEffect', 'Scene_Shadows', 'Scene_HighLights', 'Scene_MidTones',
             'Scene_Desaturation', 'Scene_Colorize')


def make_catalogue(game):
    """The game's maps' looks (the Map settings window's "Take the look of"): {'version', 'looks': [{'fog', 'postProcess'
    (LOOK_POST's members), 'maps': [{'map', 'label', 'time'}]}]}, a look for each set of values one or more maps share,
    the commonest first; each map's `time` its records' TimeOfDay words (Day, Night). `game` is the install's folder."""
    import installs
    import maplist
    import mapsini
    times = {}
    for line in maplist.records(installs.maps_text(game)):
        name, time = mapsini.field(line, 'Name'), mapsini.unquoted(line, 'TimeOfDay')
        if name and time and time.startswith('eMissionTime_'):
            times.setdefault(name, set()).add(time[len('eMissionTime_'):])
    defaults = load_defaults()
    looks = {}
    for name, entry in maplist.lwr_maps(game).items():
        if not entry.get('package'):
            continue
        found = read(Package(entry['package']), defaults)
        if not found:
            continue
        look = dict(fog=found['world']['fog'], postProcess={k: found['world']['postProcess'][k] for k in LOOK_POST})
        key = json.dumps(look, sort_keys=True)
        looks.setdefault(key, dict(look, maps=[]))['maps'].append(
            dict(map=name, label=entry['label'], time=sorted(times.get(name, ()))))
    out = sorted(looks.values(), key=lambda l: (-len(l['maps']), min(m['label'].casefold() for m in l['maps'])))
    for look in out:
        look['maps'].sort(key=lambda m: m['label'].casefold())
    return {'version': 1, 'looks': out}


def load_catalogue(path=CATALOGUE_FILE):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='command', required=True)
    d = sub.add_parser('defaults', help='the structs\' defaults from the script packages')
    d.add_argument('cooked', type=Path, help='a CookedPCConsole with Engine.upk')
    d.add_argument('--write', action='store_true', help='write %s' % DEFAULTS_FILE.name)
    m = sub.add_parser('map', help='a map\'s atmosphere')
    m.add_argument('package', type=Path)
    c = sub.add_parser('catalogue', help='the game\'s maps\' looks (%s)' % CATALOGUE_FILE.name)
    c.add_argument('game', type=Path, help='the install\'s folder (<LWR install>)')
    c.add_argument('--write', action='store_true', help='write %s' % CATALOGUE_FILE.name)
    args = ap.parse_args(argv)
    if args.command == 'catalogue':
        text = json.dumps(make_catalogue(args.game), indent=1, sort_keys=True) + '\n'
        if args.write:
            CATALOGUE_FILE.write_text(text, encoding='utf-8', newline='\n')
            print('written', CATALOGUE_FILE)
        else:
            print(text)
        return
    if args.command == 'defaults':
        made = make_defaults(args.cooked)
        text = json.dumps(made, indent=1, sort_keys=True) + '\n'
        if args.write:
            DEFAULTS_FILE.write_text(text, encoding='utf-8', newline='\n')
            print('written', DEFAULTS_FILE)
        else:
            print(text)
    else:
        print(json.dumps(read(Package(args.package)), indent=1))


if __name__ == '__main__':
    main()

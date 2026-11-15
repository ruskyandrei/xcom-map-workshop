"""Read-only mission-editor evidence collection for an EW installation.

Uses the existing experimental v845 package readers. This is an inventory,
not a cooker, complete native-object decoder, or in-game compatibility test.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import upkinfo
import props
import lzo1x


def digest(path):
    with path.open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def read_header(path):
    with path.open('rb') as file:
        data = file.read(65536)
        # Some core/startup files wrap the entire package in an LZO stream.
        # Decode the first block only: the package summary is at its start.
        if struct.unpack_from('<II', data) == (0x9E2A83C1, 131072):
            block_size = struct.unpack_from('<I', data, 4)[0]
            total_raw = struct.unpack_from('<I', data, 12)[0]
            blocks = (total_raw + block_size - 1) // block_size
            packed, unpacked = struct.unpack_from('<II', data, 16)
            file.seek(16 + 8 * blocks)
            data = lzo1x.decompress(file.read(packed), unpacked)
            return upkinfo.summary(data), True
    return upkinfo.summary(data), False


def tagged_properties(data, entry, names, imports, exports):
    offset = entry['off']
    if (entry['flags'] >> 32) & 0x02000000:
        node = struct.unpack_from('<i', data, offset)[0]
        offset += 18 + (4 if node else 0)
    offset += 4  # NetIndex
    values, end = props.read_props(
        data, offset, entry['off'] + entry['size'], names, imports, exports)
    return {'properties': values, 'native_tail_bytes': entry['off'] + entry['size'] - end}


def inspect_package(path, detailed=False):
    data, header = upkinfo.load(str(path))
    names, imports, exports = upkinfo.tables(data, header)
    counts = collections.Counter(upkinfo.clsname(e['cls'], imports, exports) for e in exports)
    result = {'sha256': digest(path), 'header': header, 'class_counts': dict(counts)}
    classes = {}
    selected = []
    for index, entry in enumerate(exports, 1):
        cls = upkinfo.clsname(entry['cls'], imports, exports)
        name = upkinfo.objname(index, imports, exports)
        if cls == 'Class':
            classes[name] = upkinfo.objname(entry['sup'], imports, exports)
        if detailed and (cls in {
                'XComLevelVolume', 'XComWorldData', 'XComWorldDataContainer',
                'SeqAct_SetLOSBlocking', 'SeqAct_BuildWorldData',
                'XComRebuildWorldDataVolume', 'Texture2D', 'MaterialInstanceConstant',
                'XComSpawnPoint', 'XComAlienPod_Abduction'}):
            record = {'class': cls, 'object': name, 'serialized_bytes': entry['size']}
            try:
                record.update(tagged_properties(data, entry, names, imports, exports))
            except Exception as exc:
                record['parse_error'] = str(exc)
            selected.append(record)
    result['classes'] = classes
    result['world_data_functions'] = [upkinfo.objname(i, imports, exports)
                                     for i, e in enumerate(exports, 1)
                                     if upkinfo.clsname(e['cls'], imports, exports) == 'Function'
                                     and upkinfo.objname(i, imports, exports).startswith('XComWorldData.')]
    if detailed:
        result['selected_exports'] = selected
        result['meshes'] = [upkinfo.objname(i, imports, exports) for i, e in enumerate(exports, 1)
                            if upkinfo.clsname(e['cls'], imports, exports) in ('StaticMesh', 'SkeletalMesh')]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('game_root', type=Path, help='XCom-Enemy-Unknown directory')
    parser.add_argument('output', type=Path, help='JSON evidence file outside the game')
    args = parser.parse_args()
    game = args.game_root.resolve()
    output = args.output.resolve()
    if output.is_relative_to(game):
        parser.error('Output must be outside the game installation.')
    cooked = game / 'XEW/XComGame/CookedPCConsole'
    config = game / 'XEW/XComGame/Config'
    result = {'research_date': '2026-11-03', 'game_root': str(game),
              'scope': 'Top-level XEW CookedPCConsole .upk/.u headers; all patch_*.upk export tables; selected properties. No gameplay tests.'}
    header_groups = collections.Counter()
    files = sorted(p for p in cooked.iterdir() if p.suffix.lower() in ('.upk', '.u'))
    licensee_zero = []
    wrapped_packages = []
    errors = []
    for path in files:
        try:
            header, wrapped = read_header(path)
            if wrapped:
                wrapped_packages.append(path.name)
            group = (header['ver'], header['lic'], header['engine'], header['cooker'])
            header_groups[group] += 1
            if header['lic'] == 0:
                licensee_zero.append(path.name)
        except Exception as exc:
            errors.append({'file': path.name, 'error': str(exc)})
    result['package_inventory'] = {
        'total': len(files), 'header_groups': [dict(zip(('version', 'licensee', 'engine', 'cooker', 'count'), (*g, count)))
                                             for g, count in sorted(header_groups.items())],
        'licensee_zero': licensee_zero, 'fully_compressed_headers': wrapped_packages, 'errors': errors}
    map_path = config / 'DefaultMaps.ini'
    maps = []
    for number, line in enumerate(map_path.read_text(encoding='utf-8-sig').splitlines(), 1):
        if not re.match(r'^\s*\+?Maps\s*=', line):
            continue
        values = {}
        for field in ('MapFamily', 'Name', 'DisplayName', 'MissionType', 'bInRotation', 'TimeOfDay', 'ShipType', 'CouncilType'):
            match = re.search(r'\b' + field + r'\s*=\s*("[^"]*"|[^,\s)]+)', line)
            values[field] = match.group(1).strip('"') if match else None
        values['line'] = number
        values['streams'] = re.findall(r'MapName\s*=\s*"([^"]+)"', line)
        maps.append(values)
    references = [stream for entry in maps for stream in entry['streams'] if stream.lower().startswith('patch_')]
    installed_patches = sorted(cooked.glob('patch_*.upk'))
    present = {p.stem.lower() for p in installed_patches}
    referenced = {x.lower() for x in references}
    result['map_config'] = {
        'path': str(map_path), 'sha256': digest(map_path), 'active_entries': len(maps),
        'in_rotation': sum(m['bInRotation'].lower() == 'true' for m in maps),
        'mission_counts': dict(collections.Counter(m['MissionType'] for m in maps)),
        'patch_reference_occurrences': len(references), 'unique_patch_references': len(referenced),
        'unreferenced_patch_files': sorted(present - referenced),
        'missing_patch_files': sorted(referenced - present), 'maps': maps}
    result['config_hashes'] = {p.name: digest(p) for p in sorted(config.glob('*.ini'))
                               if p.name in ('DefaultLZMutator.ini', 'DefaultMutatorLoader.ini', 'DefaultLWRebalance.ini')}
    result['texture_caches'] = [{'name': p.name, 'bytes': p.stat().st_size} for p in sorted(cooked.glob('*.tfc'))]
    executable = game / 'XEW/Binaries/Win32/XComEW.exe'
    exe_data = executable.read_bytes()
    patterns = {
        'custom_material_patch_3': ('A9 CE 07 00 00 0F 84 CC 01 00 00', 'A9 CE 07 00 00 0F 89 CC 01 00 00'),
        'custom_material_patch_4': ('8D 44 24 38 8B CF 50 74 7A', '8D 44 24 38 8B CF 50 EB 7A')}
    result['executable_material_patterns'] = {'path': str(executable), 'sha256': digest(executable),
        'source': 'https://github.com/chrishayesmu/XCOM-LW-CommunityEdition/blob/71d2164ca8d76883ff5afa24ee5062596c880088/Notes/exe_patches.md',
        'patterns': {key: {'original_count': exe_data.count(bytes.fromhex(before)),
                           'modified_count': exe_data.count(bytes.fromhex(after)),
                           'original_offset': exe_data.find(bytes.fromhex(before))}
                     for key, (before, after) in patterns.items()}}
    result['patches'] = {}
    aggregate = collections.Counter()
    for path in installed_patches:
        try:
            info = inspect_package(path, detailed=path.stem.lower() == 'patch_bar')
            result['patches'][path.name] = info
            aggregate.update(info['class_counts'])
        except Exception as exc:
            errors.append({'file': path.name, 'error': str(exc)})
    result['patch_class_totals'] = dict(aggregate)
    result['representative_packages'] = {}
    for name in ('CB2_MP_Blank.upk', 'URB_Bar.upk', 'XComGame.upk', 'XComLZMutator.u', 'LWRebalance.u', 'LWRFX.upk', 'LWRPictures.upk'):
        path = cooked / name
        if not path.exists():
            errors.append({'file': name, 'error': 'not present'})
            continue
        print('Inspecting', name, flush=True)
        try:
            result['representative_packages'][name] = inspect_package(path, detailed=name in ('CB2_MP_Blank.upk', 'URB_Bar.upk', 'LWRFX.upk'))
        except Exception as exc:
            errors.append({'file': name, 'error': str(exc)})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'packages': len(files), 'header_groups': result['package_inventory']['header_groups'],
                      'maps': len(maps), 'rotation': result['map_config']['in_rotation'],
                      'patch_files': len(installed_patches), 'patch_references': len(references),
                      'unique_patch_references': len(referenced), 'errors': errors}, indent=2))


if __name__ == '__main__':
    main()

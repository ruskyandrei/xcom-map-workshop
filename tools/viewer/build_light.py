"""A baked Build's own light in the viewer's cache (game-likeness plan, stage B4).

A baked Build relights the map: the pieces it makes as new actors (a moved original's copy, an added piece) get
lightmaps of their own, and the map's pieces near its changes get new ones. Its manifest says which built actor each
project piece became (`builtActors`: the project's name for the piece to the built actor; a list for a made piece cut
into parts), which components it relit (`relitComponents`) and what the project was as built (`asBuilt`; build.py
built_actors). `export` reads those components' baked light from the built package with the export's own code
(export.Exporter.baked, stage B1: baked_light.py): every mesh component of each built actor named alone, and every
relit component. It writes the records and the atlases they name into the cache under the Build's ID:

  <cache>/builds/<buildId>/light.json         {format, buildId, pieces: {built component: its baked light, as export
                                              45 gives a piece's: lightmap, sunShadow or sunIrrelevant}, textures:
                                              {key: the texture's record, as the export's}, diagnostics}
  <cache>/builds/<buildId>/texture-build-<n>.dds|.png      the atlases as stored (texture.export_texture)

A relit atlas is the map's own texture written again (lightmap_writer.py keeps its object and name), so its record
here carries the map's texture's name, and the page reads it in place of the map's (baked_light.js). The page asks
through GET /projects/<id>/build-light.json (viewer.py, builds.BuildRunner.light): `light` exports the project's last
Build's light the first time it is asked for, then serves it, joined with what the manifest says (the built actors and
the project as built), and the files from /cache-builds/<buildId>/. Another Build of the same variant's folder goes
once a newer one is exported (the package it was read from is gone).

  python -B tools/viewer/build_light.py <package folder> --cache <cache> [--maps <game maps>]    export one package's
      light (the textures it did not write read from the game install's folder of maps), and print what it holds
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys
import threading
from uuid import uuid4

import atomic_files
from export import Exporter, UNREADABLE
from package import Package
import publication
import settings

FORMAT = 1
FOLDER = 'builds'               # <cache>/builds/<buildId>/
URL = '/cache-builds/'          # where the page reads a Build's files (viewer.py translate_path)
BUILD_ID = re.compile(r'([A-Za-z][A-Za-z0-9_]*)-\d{8}-\d{6}(?:-[0-9a-f]{8})?')     # build.py: <variant>-<stamp>[-<attempt>]
MESHES = ('StaticMesh', 'FracturedStaticMesh')
_EXPORTING = threading.Lock()   # one export at a time: two pages asking at once get the one export


class LightError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status, self.message = status, message


def has_light(m):
    """Whether a package's manifest names a Build's own light: a baked Build that relit the map (build.py)."""
    return (isinstance(m, dict) and not m.get('quick') and not m.get('lightingUnchanged')
            and isinstance(m.get('builtActors'), dict) and isinstance(m.get('asBuilt'), dict)
            and isinstance(m.get('buildId'), str) and bool(BUILD_ID.fullmatch(m['buildId'])))


def folder(cache, build_id):
    """The cache folder of a Build's light, or None for an id that is no Build's."""
    return Path(cache) / FOLDER / build_id if isinstance(build_id, str) and BUILD_ID.fullmatch(build_id) else None


def components(p, m):
    """The export indices of the components whose light a Build's light holds: each mesh component of every built
    actor `builtActors` names alone (a made piece cut into parts is drawn whole by the page, and lit live), and every
    relit component (`relitComponents`), in the package's order."""
    out = set()
    for actor in (m.get('builtActors') or {}).values():
        index = p.by_name.get(actor) if isinstance(actor, str) else None
        if index:
            out.update(c for c in p.children.get(index, []) if 'MeshComponent' in p.cls(c))
    for name in m.get('relitComponents') or []:
        index = p.by_name.get(name) if isinstance(name, str) else None
        if index and 'MeshComponent' in p.cls(index):
            out.add(index)
    return sorted(out)


def read(package_path, m, out, caches=None):
    """The Build's light read from its package into the folder `out` (its atlases' files): the record light.json
    holds. `caches`: the game install's folder of maps, where the textures the Build did not write are (in the base
    map's texture caches; package.cache_file)."""
    p = Package(package_path, caches=caches)
    exporter = Exporter(p, Path(out), namespace='build', lightmaps=True)
    pieces = {}
    for ci in components(p, m):
        try:
            mesh = p.effective(ci, 'StaticMesh', 0)
            if mesh <= 0 or p.cls(mesh) not in MESHES:
                continue
        except UNREADABLE as error:
            exporter.warn(p.name(ci), f'its mesh was not read: {error}')
            continue
        baked = exporter.baked(ci, mesh)
        if baked:
            pieces[p.name(ci)] = baked
    return dict(format=FORMAT, buildId=m['buildId'], pieces=dict(sorted(pieces.items())),
                textures={k: v for k, v in sorted(exporter.textures.items()) if v}, diagnostics=exporter.diagnostics)


def export(package_path, m, cache, caches=None):
    """The Build's light (`m` its manifest, has_light) exported into the cache, unless it is there: its record. The
    folder is written beside its place and moved in whole, so a page never reads half of one."""
    target = folder(cache, m['buildId'])
    with _EXPORTING:
        if (target / 'light.json').is_file():
            return json.loads((target / 'light.json').read_text(encoding='utf-8'))
        temp = target.parent / ('.export-%s' % uuid4().hex[:8])
        temp.mkdir(parents=True)
        try:
            record = read(package_path, m, temp, caches)
            atomic_files.write_text(temp / 'light.json', json.dumps(record, indent=1) + '\n')
            if target.exists():
                shutil.rmtree(target)       # (a folder without its record: an export cut short)
            atomic_files.replace(temp, target)
        finally:
            shutil.rmtree(temp, ignore_errors=True)
        prune(cache, m['buildId'])
        return record


def prune(cache, keep):
    """The other Builds' lights of the variant `keep` names (a Build's ID) out of the cache: their packages are gone."""
    variant = BUILD_ID.fullmatch(keep).group(1)
    root = Path(cache) / FOLDER
    for old in root.iterdir() if root.is_dir() else ():
        found = BUILD_ID.fullmatch(old.name)
        if old.is_dir() and old.name != keep and found and found.group(1) == variant:
            shutil.rmtree(old, ignore_errors=True)


def light(cache, output, project_id, variant, caches=None):
    """The project's last Build's light for the page: what the cache holds of it (exported the first time), with what
    its manifest says: {buildId, builtAt, revision, map, actors (builtActors), project (asBuilt), pieces, textures,
    base (where its files are served)}. LightError(404) where the project's last package has none."""
    if not (isinstance(variant, str) and publication.VARIANT.fullmatch(variant)):
        raise LightError(404, 'The project has not been built yet.')
    package = Path(output) / variant
    try:
        with publication.guard(output, variant, wait=publication.READ_WAIT):
            try:
                m = json.loads((package / 'manifest.json').read_text(encoding='utf-8'))
            except (OSError, ValueError):
                raise LightError(404, 'The project has not been built yet.')
            if not isinstance(m, dict) or (m.get('project') or {}).get('id') != project_id:
                raise LightError(404, 'The project has not been built yet.')
            if not has_light(m):
                raise LightError(404, 'The project\'s last Build has no light of its own: it was a quick Build, or it '
                                      'relit nothing.')
            try:
                record = export(package / settings.COOKED / ('%s.upk' % variant), m, cache, caches)
            except (OSError,) + UNREADABLE as error:
                raise LightError(500, f'The light of the project\'s last Build could not be read: {error}')
    except publication.Busy as error:
        raise LightError(409, str(error))
    return dict(buildId=m['buildId'], builtAt=m.get('builtAt'), revision=(m.get('project') or {}).get('revision'),
                map=(m.get('source') or {}).get('map'), actors=m['builtActors'], project=m['asBuilt'],
                pieces=record['pieces'], textures=record['textures'], base='%s%s/' % (URL, m['buildId']))


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('package', type=Path, help='a Build\'s package folder (<builds>/<Variant>)')
    a.add_argument('--cache', type=Path, required=True, help='the viewer cache to export into')
    a.add_argument('--maps', type=Path, help='the game install\'s folder of maps, where the textures '
                   'the Build did not write are')
    args = a.parse_args(argv)
    m = json.loads((args.package / 'manifest.json').read_text(encoding='utf-8'))
    if not has_light(m):
        sys.exit('%s names no light of its own (a quick Build, one that relit nothing, or one from before 27 November 2026)'
                 % args.package)
    record = export(args.package / settings.COOKED / ('%s.upk' % m['variant']), m, args.cache, args.maps)
    lit = sum(1 for r in record['pieces'].values() if r.get('lightmap'))
    print(json.dumps(dict(folder=str(folder(args.cache, m['buildId'])), pieces=len(record['pieces']), lightmaps=lit,
                          textures=len(record['textures']), diagnostics=len(record['diagnostics'])), indent=1))


if __name__ == '__main__':
    main()

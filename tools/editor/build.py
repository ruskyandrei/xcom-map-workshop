"""The editor's Build (first-editor plan, section 7; slice E4): a saved project to a finished variant package, with
its lighting baked. It never touches a game install: the game install (LWR, or plain Enemy Within) is only read, for
the pristine base map and its config lines. Installing a package somewhere is a separate step (the editor's Install
in game, installs.py, or a modder's own, from the package's README). The install's DefaultMaps.ini is read as it
has it: what the editor installed into it is taken out (installs.maps_text).

  python -B tools/editor/build.py <project file | project id or name> [--cache <viewer cache>] [--output <builds folder>]
      [--radius 1024] [--lwr <install>] [--udk <UDK 2011-09>] [--family other ...] [--quick] [--work <folder>]

--quick is the editor's Build with Bake the lighting off (its default): the edit made in the map exactly as a full
build makes it, but its lighting not baked (stage 4 without the relight), in seconds instead of minutes. Pathing, cover
and line of sight in the game are a full build's; the lighting is not right (the copies keep their originals' lighting
and cast no shadows, and deleted or moved pieces leave their shadows behind). Its package replaces the project's last
one, as any build's does, and its manifest says `quick`.

--family builds a family the compiler doesn't build for every project (compiler.FAMILIES), for an experiment's build;
its choices are the families still switched off, which today is only `other` (the classes with no family of their
own). EXP-22 built ladders with --family ladder, EXP-23 doors with --family door, EXP-24 cars and vans with --family car
and --family van and EXP-26 run 1 lights with --family light, before each family was switched on for every project.
Fracturing pieces and physics props were switched on without one (9 November 2026; EXP-28 has their game runs).

Folders default to the editor's settings (tools/viewer/settings.py: projects, output, lwr, and udk, which only a
patch needs) and the main viewer cache. Where Windows' long paths are off (the usual), a build whose files would
pass its 260 characters stops before its first stage, saying by how many (Build.check_paths, error code
path-too-long). Stages, each logged in the build's work folder (<output>/.work/<Variant>-<stamp>/logs;
--work gives another, and a prefab test's Build works in the test's own folder: Build.work_folder):
1. Snapshot: the project (its saved revision, read once; the manifest's project.sha256 names its bytes), the viewer
   export of its source map (by the project's SHA-256), and the base map from the game install, which must have that
   SHA-256. The server's builds read a snapshot it captured (--saved-file names the project's own file), with the map
   picture the project names beside it (project.picture.png): Build.find_picture.
2. Compile: tools/editor/compiler.py with --stream-only, split (compiler.native_split): copies of every class the
   compiler builds (compiler.NATIVE_CLASSES: scenery, props, destructibles, collectibles, fracturing pieces and
   physics props; and every assembly's parts) are
   made in the variant map itself (native-copies.json), and so are their groups that break together, linked in the
   map; hidden pieces are taken out of it. So a project the compiler accepts leaves the patch nothing. What would be
   left for it (copies of a class built only by the copier, and the groups they break with) waits for later
   milestones. Refused when there is nothing to build from (the document's schema, its source map, its names, an
   export without the light data or the tile grid the edit needs), or when the project changes nothing (has_work: its
   own missions list or a map picture is a change); a piece, or a part of the document, that can't be built is left
   out and named (the compile stage's leftOutPieces, the manifest's leftOut: a malformed group, building, landing
   zone, map size, spawn rule or missions entry among them), and the rest builds.
3. Patch: tools/patch/patchtool.ps1 build (-Force, so a rebuild replaces the project's last authoring package, which
   patchtool backs up) and cook, in UDK from the settings, with patchtool's work folder in the builds folder
   (<output>/.work/patchtool) and the original maps read from the game install (-Lwr). Skipped when the patch has
   nothing to do, which is every project the compiler accepts today: then the variant streams no patch, and UDK isn't
   run. The udk setting is optional: a build that would need a patch without it is refused with what to set.
4. Light: with copies, hides or light edits made in the map, tools/bake/native_copy.py --bake on the pristine base
   map: each copy a new actor (its own lighting textures, a fresh name and net indices), in the tiles (seeds and a
   rebuild volume), the cover blocks made (tools/bake/cover_blocks.py: hidden level actors on box meshes, from a
   recipe), the light edits made (tools/bake/native_lights.py: lights deleted, changed, added, generated glow
   lights following their pieces; private/plans/done/editor-lights-plan.md, 4.3), then tools/bake/relight.py with the copies,
   the light edits' before and after lights and the patch's spec (--edit-spec). Without, relight.py alone with the spec.
   A calculation that changes no texel (a disabled light added, say) is a valid build: the map keeps the original's
   lightmaps, the stage and the manifest say lightingUnchanged, and there is no texture cache.
   Hidden pieces stop casting shadows, copies cast them at their poses, a copy made in the map is lit for where it
   stands, and every texture-lightmapped component within --radius of the edit is relit as a change on the original
   bake (--receivers-near). Writes, in the work folder, the variant map and its texture cache, <Variant>_Lighting.tfc (cache_name: the
   name added to the map's name table first, by native_copy.py's growing write, or for the relight alone by a named
   copy of the map in the work folder: Build.named_base; until 16 November 2026 it was Lighting_<n>, n from the
   variant's name). A quick build runs native_copy.py without --bake (Build.edit_unbaked): the same edit, no relight,
   no texture cache.
5. Seeds: the patch's seed plan (patchtool's seed-plan-built.tsv) is applied to the relit map
   (tools/upk/seed_map.py apply), so the copier's copies block and give cover on tiles the map left empty (F-29).
   Then the project's map picture, if it has one (tools/viewer/pictures.py keeps the file, 512 x 256), is written
   into the map as its top-level Texture2D `MapPicture` (tools/bake/map_frame.py: DXT1, as the game's own map
   pictures), in quick and full builds alike. Long War Rebalance 3 shows it on the
   mission screens; plain Enemy Within and earlier Long War versions look for no such object. A project that names
   a picture whose file is not on this computer builds without one and says so (a note: the stage, the manifest's
   pictureNote and the README). A changed picture is a change of the project like any other: the build is an
   ordinary one, with no shortcut that redoes the picture alone (which inputs of the last build still hold is not
   recorded, so "only the picture changed" can't be told safely).
   Last, the relight's lightmaps go inside the map (tools/bake/inline_lighting.py, Build.lighting_inside; EXP-86):
   every texture that names the build's cache holds all its mips inline, NeverStream, and the package ships no
   texture cache. The game finds a .tfc only in CookedPCConsole itself (F-140), so a map that carries its own lighting
   goes anywhere a map can, a map pack's folder included; its lightmaps stay in memory while the map is loaded.
   Since 19 November 2026; a package built before has its <Variant>_Lighting.tfc (or Lighting_<n>.tfc) beside the
   map until it is built again, and a map that can't take its lightmaps in still ships it, the stage saying why.
6. Package: <output>/<Variant>/, as the plan's variant package:
     CookedPCConsole/<Variant>.upk          the base map with the edit's copies, relit and seeded, under the
                                            variant's name, with the project's map picture and its baked lightmaps
                                            inside it (manifest: lightingInside; cache None)
     CookedPCConsole/<EditPatch>.upk        the cooked edit patch (hides, the copier's copies), if there is one
     CookedPCConsole/<Intro>_<Variant>.upk  the base map's intro (CIN_DropshipIntros, CIN_FastropeIntros, or the
                                            alien bases' CIN_TP05A_EnteringAlienBase) with its scene under the
                                            variant's name (tools/bake/intro_copy.py, F-45, F-76), one for each intro
                                            its records stream
     CookedPCConsole/<Patch>_<Variant>.upk  a streamed patch of the base map without the pieces the edit takes out of
                                            it (tools/bake/stream_copy.py: a moved or deleted ladder's hidden helper
                                            in patch_bar), one for each such patch; and a mission's stream with the
                                            objects the project moves moved in place (mission types plan, Part E),
                                            streamed by that mission's records alone
     README.txt                             what it is, where the files go, the config lines to add
     manifest.json                          project and revision, source map hash, names, files and hashes, streams,
                                            config lines, each stage's result, tool hashes, whether it is a quick
                                            build, and how long the project's last full and quick builds took
   The package is written beside the old one and swapped in last, so a failed build leaves the last good package as
   it was. No zip is made (until 10 November 2026 one was, <output>/<Variant>.zip: a build takes an earlier one away).

The config lines are the game install's own, renamed: each of the base map's DefaultMaps.ini records (one per mission
it serves: most maps have several) under the variant's name, out of rotation, with the patch (if any) streamed in
its lowest free slot and the intro and stream copies in place of the originals (the manifest's replaceStreams); its
landing zones (DefaultLZMutator.ini); its DefaultMiniMods.ini rules. A record's own mission streams (a bomb's,
say) stay as they are, placed for the original map, unless the project moves their objects: then the record streams
the variant's copy (<Stream>_<Variant>.upk), and the base map's tiles under a moved solid piece are rebuilt where it
stood and seeded and rebuilt where it stands (the native edit's streamTiles). The last two files are Long War's: an install without them (plain
Enemy Within) gets neither, and its variant lands as the map's own landing zones say. The records' display names end
in " |0" where the install's do (LWR's do; plain EW's don't).
"""
import argparse
import ast
import contextlib
import dataclasses
import datetime
import functools
import hashlib
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(TOOLS / 'viewer'))
sys.path.insert(0, str(TOOLS / 'upk'))
if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.append(str(Path(__file__).resolve().parents[1]))     # tools/paths.py (review finding 54)
import paths  # noqa: E402
import builds as build_runs  # noqa: E402
import compiler  # noqa: E402
import decomp  # noqa: E402
import installs  # noqa: E402
import maplist  # noqa: E402
import mapsini  # noqa: E402
import missions as mission_kinds  # noqa: E402
import outputnames  # noqa: E402
import pictures  # noqa: E402
import procs  # noqa: E402
import publication  # noqa: E402
import spawnrules  # noqa: E402
import spawns  # noqa: E402
import settings as settings_module  # noqa: E402
from game_files import lwr_file  # noqa: E402
from projects import ID as PROJECT_ID, ProjectError, ProjectStore  # noqa: E402
from version import VERSION  # noqa: E402
# The modules one stage of a Build needs (the shell, the relight's lightmap writer, the map picture's writer, the
# streams' copier...) are imported in that stage's function, not here: none is loaded once the imports above have run,
# so an import here would load it earlier, in every process that imports the Build, and many Builds never reach the
# stage (a quick Build has no relight; most projects move no landing and no mission object).

SCHEMA ='xcom-map-workshop/variant-package'
SCHEMA_VERSION = 1
PATCHTOOL = TOOLS / 'patch' / 'patchtool.ps1'
RELIGHT = TOOLS / 'bake' / 'relight.py'
NATIVE_COPY = TOOLS / 'bake' / 'native_copy.py'
TRANSPLANT = TOOLS / 'bake' / 'transplant.py'
SHELL = TOOLS / 'bake' / 'shell.py'
# the export generation a Build needs: one with the light and generated-light metadata (editor lights plan, 4.1 and
# 9.3), the compiler's own minimum
EXPORT_MINIMUM = compiler.EXPORT_MINIMUM
# the native edit's lanes of effects, ambient sounds and lens flares (compiler.native_split; native_copy.py makes them)
EFFECT_LANES = ('effects', 'sounds', 'flares')
LEFT_OUT_SHOWN = 100        # how many left-out pieces the compile stage names (the report file has them all)
OTHER_SHOWN = 20            # how many pieces the light stage names whose lightmaps the relight's writes reached
# what a quick build does with light edits (editor lights plan, 4.3): made in the map, not baked; the editor's build
# panel can show the same text beside Bake the lighting
QUICK_LIGHTS = ('Its light edits are made in the map but not baked: a deleted light\'s pool stays on the baked '
                'surfaces; a changed or moved light leaves its old pool baked where it was, and only what the game '
                'lights live (soldiers, aliens and other moving things) takes the edited light; an added light has no '
                'baked light of its own, so the surfaces it reaches show only what the game lights live; glow lights '
                'that follow their glowing pieces light soldiers and aliens at the new place, but the old glow stays '
                'baked where it was and the new place gets none.')
INTRO_COPY = TOOLS / 'bake' / 'intro_copy.py'
PICTURE_FORMAT = 'DXT1'
PICTURE_MISSING = ('the project names a map picture whose file is not on this computer (%s): the map is built '
                   'without a picture of its own. Choose the picture again in Map picture, save and build again')
PICTURE_FAILED = ('the map picture could not be written into %s (%s): the map is built without a picture of its own. '
                  'Choose the picture again in Map picture, save and build again')
STREAM_COPY = TOOLS / 'bake' / 'stream_copy.py'
# the tools the Build runs, each as a process of its own (the modules it imports itself are found from build.py's
# imports: tool_modules)
RUN_TOOLS = (NATIVE_COPY, RELIGHT, INTRO_COPY, STREAM_COPY, TRANSPLANT, SHELL)
# the streamed intros whose Kismet picks its scene by the map's exact name (intro_copy.py): the Skyranger and fast-rope
# landings (F-45) and the alien bases' entrance (F-76; Temple Ship's arrival names no map). A variant gets its own copy.
INTROS = outputnames.INTROS
LANDINGS = ('CIN_DropshipIntros', 'CIN_FastropeIntros')   # the Skyranger's landings among them (the README's words)
RADIUS = 1024.0
LOG_TAIL = 40       # the lines of a failing tool's log read for the pieces it names (Build.untried_named)
PREFAB_TEST_WORK = 'w'      # a prefab test's work folder, in the test's own folder (Build.work_folder)
# Windows' path limit (MAX_PATH, 260 with the closing nul) for a file, and for a folder, which is made only when an 8.3
# name (12 characters) still fits after it: what the Build's files must keep to where long paths are off (long_paths;
# Build.check_paths, KB-12)
PATH_LIMIT, FOLDER_LIMIT = 259, 247
PREVIEW_ACTOR = 32          # the longest actor name a relight preview is named by (28 in the game's maps)
# a decoded map the Build keeps in its work folder (decomp.py: <SHA-256>.unpacked, written as <name>.<pid>.tmp)
UNPACKED_NAME = '%s.unpacked.%s.tmp' % ('0' * 64, '0' * 6)
EOL = '\r\n'


class BuildError(Exception):
    """Why a build failed. `code`, when given, says which failure it is to the editor's build runner (main prints it
    on a "build failed code:" line before the reason; tools/viewer/builds.py keeps it as the job's errorCode)."""
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def imported_names(path):
    """The modules the Python file `path` imports by absolute name (`import x.y` gives x, `from x import y` gives x),
    wherever the statement stands (a stage's late import in a function too): its syntax tree's statements, read
    without walking every expression."""
    def statements(body):
        for s in body:
            yield s
            for field in ('body', 'orelse', 'finalbody'):
                yield from statements(getattr(s, field, None) or [])
            for part in (getattr(s, 'handlers', None) or []) + (getattr(s, 'cases', None) or []):
                yield from statements(part.body)
    for s in statements(ast.parse(Path(path).read_text(encoding='utf-8')).body):
        if isinstance(s, ast.Import):
            yield from (a.name.split('.')[0] for a in s.names)
        elif isinstance(s, ast.ImportFrom) and s.level == 0 and s.module:
            yield s.module.split('.')[0]


@functools.lru_cache(maxsize=None)
def imported_modules(roots, folders):
    """The files of `folders` (a tuple) that the files `roots` (a tuple) import, and theirs, found from their import
    statements (imported_names; a module is the first of `folders` holding <name>.py), as the release finds its
    modules: a sorted tuple, the roots that lie in `folders` among them. Worked out once a process (a Build is a
    process of its own; the tests run a hundred Builds in one)."""
    seen, todo = set(), list(roots)
    while todo:
        path = todo.pop()
        if path in seen:
            continue
        seen.add(path)
        for name in imported_names(path):
            todo += [p for p in (f / ('%s.py' % name) for f in folders) if p.is_file()][:1]
    return tuple(sorted(p for p in seen if p.parent in folders))


def editor_modules():
    """build.py and the modules of tools/editor it imports, and theirs: the compiler, the modules split off it and
    game_files (imported_modules). The manifest's `tools` names each (with its SHA-256), so a module split off the
    compiler later is named with no list to keep. build.py first, the rest by name."""
    own = HERE / 'build.py'
    return [own] + [p for p in imported_modules((own,), (HERE,)) if p != own]


def tool_modules():
    """The modules of tools/bake and tools/upk that make a package: the tools the Build runs (RUN_TOOLS), what
    build.py imports of the two folders itself (the seeder, the named copy's growing writer, the map picture's writer,
    the inline lighting...), and everything they import of the two (imported_modules), sorted. The manifest's
    `tools` names each with its SHA-256, so a module a tool takes on later is named with no list to keep (a hand list
    did until 21 November 2026, and left out the shell, the copy tool's makers and the relight's own modules)."""
    return imported_modules((HERE / 'build.py',) + RUN_TOOLS, (TOOLS / 'bake', TOOLS / 'upk'))


def long_paths():
    """Whether this process can open paths past Windows' 260 characters (Windows 10's LongPathsEnabled, which this
    Python honours; the Build's tools run on the same Python): then the Build has no path limit to keep to. True off
    Windows."""
    if sys.platform != 'win32':
        return True
    try:
        import ctypes
        enabled = ctypes.windll.ntdll.RtlAreLongPathsEnabled
        enabled.restype = ctypes.c_ubyte
        return bool(enabled())
    except (AttributeError, OSError):
        return False


def cache_name(variant):
    """The variant's texture cache: <Variant>_Lighting (outputnames.cache_name), its own as its map name is, so a
    rebuild replaces its own. The name is added to the map's name table before the relight writes it (native_copy.py,
    Build.named_base). Until 16 November 2026 it was Lighting numbered from a hash of the variant's name (Lighting_<n>):
    a package built then keeps it until it is built again."""
    return outputnames.cache_name(variant)


def inline_map(src, dst, cache, tfc):
    """dst: the map `src` with the lightmaps of its cache `cache` (the file `tfc`) inside it (inline_lighting.inline):
    {cache, textures, mips, bytes, sha256}. An error when it can't be done (the map is then left as it is)."""
    paths.use('bake')
    import inline_lighting
    return inline_lighting.inline(src, dst, cache, tfc, echo=lambda *_: None)


def owned_folder(output, variant, project_id):
    """The builds folder's entry for `variant` (its name in any case), or None when there is none. A BuildError when
    it is there and is not a build of this project: a build replaces only its own project's last package (its
    manifest names the same project id), never another project's or a folder that is no build."""
    found = outputnames.find_ci(output, variant)
    if found is None:
        return None
    m = outputnames.read_manifest(found) if found.is_dir() else None
    owner = (m.get('project') or {}).get('id') if m else None
    if project_id and owner == project_id:
        return found
    what = ('the build of another project (%s)' % ((m.get('project') or {}).get('name') or owner) if owner
            else 'no build of this project (it has no readable manifest naming it)')
    raise BuildError('%s in the builds folder is %s; the build leaves it as it is. Save the project under a new name '
                     '(Save as) to build it under another, or move that folder away' % (found, what))


@contextlib.contextmanager
def publish_lock(output, variant, wait=publication.PUBLISH_WAIT):
    """One build at a time puts a variant's package in place, and no reader copies it meanwhile (the server's builds,
    its readers and a command line's build): the variant's guard, a lock the operating system holds for its holder
    (publication.guard; until 16 November 2026 a lock file taken over by its age)."""
    try:
        with publication.guard(output, variant, wait):
            yield
    except publication.Busy as error:
        raise BuildError(str(error))


def last_times(manifest, project_id):
    """How long the project's last full build and last quick build took ({'full': s, 'quick': s}, either or both), from
    the package a build replaces, so the editor's estimate for each kind survives a build of the other. A package of
    another project (the same variant name: never, but its manifest says) gives nothing; one from before quick builds
    gives its `seconds` as the full build's."""
    try:
        m = json.loads(Path(manifest).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    if (m.get('project') or {}).get('id') != project_id:
        return {}
    times = m.get('times')
    if isinstance(times, dict):
        return {k: v for k, v in times.items() if k in ('full', 'quick') and isinstance(v, (int, float))}
    return {} if m.get('quick') or not isinstance(m.get('seconds'), (int, float)) else {'full': m['seconds']}


def find_project(arg, projects):
    """A project file given as a path, or the file of the project with this id or name in the projects folder."""
    path = Path(arg)
    if path.suffix.lower() == '.json' or path.is_file():
        return path
    store = ProjectStore(projects)
    try:
        if PROJECT_ID.fullmatch(arg):
            return store.path(arg)
        named = [p for p in store.list() if not p.get('error') and (p.get('name') or '').casefold() == arg.casefold()]
        if len(named) == 1:
            return store.path(named[0]['id'])
    except ProjectError as error:
        raise BuildError('no project %s in %s (%s)' % (arg, projects, error.message))
    if named:
        raise BuildError('%d projects are called %s in %s; give the file or the id' % (len(named), arg, projects))
    raise BuildError('no project %s in %s' % (arg, projects))


def has_light_edits(native):
    """Whether the native edit makes light edits (its `lights`, editor lights plan 9.5): any light deleted, changed or
    added, or any generated area light moved, copied or deleted. A disabled added light is still a map edit."""
    lights = (native or {}).get('lights') or {}
    return any(lights.get(k) for k in ('deletes', 'changes', 'adds', 'area'))


def light_counts(native):
    """The native edit's light edits counted for the build window and the record: placed lights moved, changed (values
    set), added (and how many by the built-in spot recipe) and deleted, and the generated area lights following their
    pieces, counted apart with the pieces they follow. None without light edits."""
    if not has_light_edits(native):
        return None
    lights = native['lights']
    changes, adds, area = lights.get('changes') or [], lights.get('adds') or [], lights.get('area') or []

    def posed(c):
        before = c.get('before') or {}
        loc = c.get('location') is not None and before.get('location') is not None and any(
            abs(float(a) - float(b)) > 1e-3 for a, b in zip(c['location'], before['location']))
        rot = c.get('rotation') is not None and before.get('rotation') is not None and \
            [int(v) for v in c['rotation']] != [int(v) for v in before['rotation']]
        return loc or rot
    return dict(moved=sum(1 for c in changes if posed(c)), changed=sum(1 for c in changes if c.get('set')),
                added=len(adds), recipeSpots=sum(1 for a in adds if a.get('template')),
                deleted=len(lights.get('deletes') or []),
                area=dict(moved=sum(1 for a in area if a.get('op') == 'move'),
                          copied=sum(1 for a in area if a.get('op') == 'copy'),
                          deleted=sum(1 for a in area if a.get('op') == 'delete'),
                          pieces=sorted({str(a.get('ownerEntity') or a.get('owner')) for a in area
                                         if a.get('ownerEntity') or a.get('owner')})))


def other_pieces_changed(record):
    """The relight record's otherPiecesChanged (lightmap_writer.Fixture.others_changed: the texels its writes changed in the
    lightmaps of pieces it was not relighting, a write re-encoding whole 4-texel blocks) as the light stage carries
    it: {texels, largest (the largest change, 0 to 1), count (pieces), pieces (the first OTHER_SHOWN), textures}, or
    None when it changed none."""
    if not isinstance(record, dict) or not record.get('texels'):
        return None
    pieces = [str(p) for p in record.get('pieces') or []]
    return dict(texels=record['texels'], largest=record.get('largest'), count=len(pieces), pieces=pieces[:OTHER_SHOWN],
                textures=record.get('textures'))


def light_summary(counts):
    """The light edits in words, as the README and the stage lines say them, or '' without any."""
    if not counts:
        return ''

    def n(k, word):
        return '%d %s' % (k, word) if k else ''
    placed = [x for x in (n(counts['moved'], 'moved'), n(counts['changed'], 'changed'),
                          n(counts['added'], 'added'), n(counts['deleted'], 'deleted')) if x]
    area = counts['area']
    glow = [x for x in (n(area['moved'], 'moved'), n(area['copied'], 'copied'), n(area['deleted'], 'deleted')) if x]
    parts = []
    if placed:
        parts.append('lights %s' % ', '.join(placed))
    if glow:
        parts.append('glow lights following their pieces %s (%s)' % (', '.join(glow), ', '.join(area['pieces'])))
    return '; '.join(parts)


# ---------------------------------------------------------------- config lines

def drop_in_exclusion(lwr, variant):
    """The manifest's config.dropInExclusion for a project that leaves scripted drop-ins where placed (spawnRules;
    the editor spawns plan, SP8): {file, section, line}, the line written as the install's own ExcludeMaps lines are
    (spawnrules.exclusion_entry). Planned against the build's install as it is now, with `why` where that install
    can't take it (plain Enemy Within, which plays them where placed already; a Long War whose loader has no drop-in
    mutator, or whose file has no drop-in section); Play in game and the campaign install plan it again there."""
    out = dict(file=spawnrules.RANDOM_SPAWNS, section=spawnrules.DROP_IN_SECTION, line=spawnrules.exclusion_entry(variant))
    path = lwr_file(lwr, 'Config', spawnrules.RANDOM_SPAWNS)
    if not path.is_file():
        return dict(out, why='the install has no %s: plain Enemy Within lands scripted drop-ins where placed already'
                    % spawnrules.RANDOM_SPAWNS)
    if spawnrules.rules(lwr).get('dropIns') == 'absent':
        return dict(out, why='the install\'s Long War loads no drop-in mutator: its scripted drop-ins land where placed already')
    _, _, why = spawnrules.plan_exclusion(path.read_bytes().split(b'\n'), variant, 'planned')
    return dict(out, why=why) if why else out


def config_text(path):
    data = Path(path).read_bytes()
    if data.startswith(b'\xef\xbb\xbf'):
        data = data[3:]
    return data.decode('latin-1').replace('\r\n', '\n').split('\n')


@contextlib.contextmanager
def record_edits():
    """Records written by mapsini's writers (set_field, add_stream: the one writer of a DefaultMaps.ini record, which
    takes the Build's lines of text), a refusal of theirs the Build's error in their words: a record without the field
    to set ('record has no DisplayName'), a patch name it can't write or a stream the record has already (neither of
    which a Build makes)."""
    try:
        yield
    except ValueError as error:
        raise BuildError('a DefaultMaps.ini record can\'t be written: %s' % error) from None


def base_records(maps, base):
    """The base map's DefaultMaps.ini records, one per mission it serves (most maps have several: an abduction,
    a terror site, a council mission...), in file order: its live records, or the commented-out ones the editor takes
    for a switched-off map (maplist.records: Act1_IntroLevel's abduction). The name matches whatever its case, as the game's
    does: the farm's file is CsmallScout_Farm.upk, its records name CSmallScout_Farm (installs.same_map, the record's
    Name read by mapsini.field, as the install finds the same records: installs.base_records)."""
    records = [l for l in maplist.records('\n'.join(maps)) if installs.same_map(mapsini.field(l, 'Name'), base)]
    if not records:
        raise BuildError('the game install has no DefaultMaps.ini record for %s' % base)
    return records


def intro_stream(record):
    """The intro a map record streams (one of INTROS: a landing, or the alien bases' entrance), or None."""
    return next((n for n in mapsini.slot_streams(record) if n in INTROS), None)


def intro_streams(records):
    """The distinct landing intros the records stream, in order: a map's missions can land differently (13 LWR maps
    have records with the Skyranger intro and records with the fast-rope one, or none)."""
    return list(dict.fromkeys(s for s in map(intro_stream, records) if s))


def mission_label(record):
    """A record's mission, readable (maplist.mission_of): Abduction, Terror, Council bomb..."""
    return maplist.mission_of(record)[2]


def template_record(records):
    """The base map's record an added kind of mission is made from (mission types plan, D4): its abduction, else its
    first that is no council mission (whose streams a bomb or rescue needs), else its first."""
    council = lambda r: mapsini.unquoted(r, 'CouncilType') not in (None, 'eFCMType_None')  # noqa: E731
    return next((r for r in records if 'MissionType=eMission_Abduction' in re.sub(r'\s', '', r) and not council(r)),
                next((r for r in records if not council(r)), records[0]))


def mission_entries(records, listed):
    """The missions the variant serves, as `missions` entries: every base map record ({record: i}) when the project
    lists none, else the project's valid entries, its base records in file order and then its added kinds."""
    if not isinstance(listed, list):
        return [dict(record=i) for i in range(len(records))]
    valid = [e for e in listed if mission_kinds.valid_entry(e, len(records))]
    kinds = list(mission_kinds.ADDED_KINDS)
    picked = sorted({e['record'] for e in valid if 'record' in e})
    added = sorted({e['kind']: e for e in valid if 'kind' in e}.values(), key=lambda e: kinds.index(e['kind']))
    return [dict(record=i) for i in picked] + added


def config_lines(maps, lz, minimods, base, variant, patch, display, intros=None, zones=None, missions_list=None):
    """The variant's config lines from the game install's (lists of lines): one DefaultMaps.ini record per record of
    the base map (its missions), each under the variant's name and out of rotation, streaming `patch` unless it is
    None and the variant's own intro copies in place of the originals (`intros`, {original: copy}); landing zones and
    MiniMods rules (`lz` and `minimods` None where the install has no such file: plain EW; then they are None too).
    `display` None or {'tail': ' |0'}: each record's display name is '<variant> (<its base record's own words>) |n'
    (missions.variant_display; tail: the ending for a base record without one), a second record that would get the
    same name saying its mission too. Else `display` is the records' display name, or display(mission label) for
    each record's (the tests'); either keeps, after the
    variant's name, the text the game's script matches in the base record's display name (missions.markers: '_Bomb',
    so Long War still throttles a bomb mission's reinforcements; mission types plan, Part B), and `matchedNames` lists
    the records that carry some ({record, marker, why}). `zones` (the project's
    landingZones; Clear map plan, section 4): the variant's landing-zone lines are those zones, every one without
    `lwr: false`, in order (spawns.write_line), in place of the base map's copied; the result then says
    landingZonesFromProject. recordMissions: for each record, the missions it stands for (the indices of base map
    records in file order, the export's `missions` order, or an added kind), which Play in game picks a mission by
    (installs.build_record). missions_list: the project's `missions` (mission types plan, D1): records for those
    alone, an added kind's made from the base map's abduction record (missions.added_record); then the result says
    missionsFromProject."""
    records, missions, slots, stands, matched = [], [], [], [], []
    found = base_records(maps, base)
    template = template_record(found)
    seen = {}
    with record_edits():
        for entry in mission_entries(found, missions_list):
            if 'record' in entry:
                index, base_line = entry['record'], found[entry['record']]
                mission = mission_label(base_line)
                base_display = mapsini.field(base_line, 'DisplayName') or ''
            else:
                index, base_line = entry['kind'], mission_kinds.added_record(template, entry)
                mission = mission_kinds.label(entry['kind'])
                base_display = '_Bomb' if entry['kind'] == 'Special/Bomb' else ''     # what the game matches for the kind
            marks = mission_kinds.markers(base_display, variant)
            # the record's own words (LWR map packs plan, section 3): the base record's, an added kind's after its
            # template's; the same at every build, whatever the project is called
            own = None
            if display is None or isinstance(display, dict):
                tail = (display or {}).get('tail', '')
                if 'record' in entry: own = mission_kinds.variant_display(base_display, variant, tail=tail)
                else:
                    shown = mapsini.field(template, 'DisplayName') or ''
                    words, ending = mission_kinds.record_words(shown)
                    own = '%s%s (%s)%s' % (variant, marks, ', '.join(w for w in (words, mission_kinds.added_words(entry)) if w),
                                           ending or tail)

            def named(label, again=False):
                if own is not None:       # a second record that would get the same name says its mission too
                    return own if not again else re.sub(r'\)( \|\d+)?$', lambda m: ', %s)%s' % (label, m.group(1) or ''), own, count=1)
                text = display(label) if callable(display) else display
                return variant + marks + text[len(variant):] if marks and text.startswith(variant) and not text.startswith(variant + marks) else text
            text = named(mission)
            record = mapsini.set_field(mapsini.set_field(base_line, 'Name', variant), 'DisplayName', text)
            if mapsini.unquoted(record, 'bInRotation') is not None:
                record = mapsini.set_field(record, 'bInRotation', 'False', quoted=False)
            for original, copy in (intros or {}).items():
                record = record.replace('MapName="%s"' % original, 'MapName="%s"' % copy)
            record, slot = mapsini.add_stream(record, patch) if patch else (record, None)
            if record in records:
                stands[records.index(record)].append(index)
                continue    # two records the renaming makes the same
            # two records of one mission that differ (a landed transport and a landed terror ship) get display names of
            # their own: the game streams by display name (mission types plan 2.1)
            seen[mission] = seen.get(mission, 0) + 1
            again = seen[mission] > 1
            if again: mission = '%s %d' % (mission, seen[mission])
            if again and own is None:
                text = named(mission)
                record = mapsini.set_field(record, 'DisplayName', text)
            elif own is not None and any(mapsini.field(r, 'DisplayName') == text for r in records):
                text = named(mission, again=True)
                record = mapsini.set_field(record, 'DisplayName', text)
            records.append(record)
            missions.append(mission)
            slots.append(slot)
            stands.append([index])
            matched += [dict(record=len(records) - 1, marker=marker, why=why) for marker, why in mission_kinds.matched(text)]
    # (the base map's name in the landing-zone and mini-mod lines matches whatever its case, as in base_records)
    tag = re.compile(re.escape('MapName="%s"' % base), re.IGNORECASE)
    # a map that lands no Skyranger (TempleShip) has no landing zones, and its variant needs none
    own = zones
    zones = None if lz is None else [tag.sub(lambda _: 'MapName="%s"' % variant, l, count=1) for l in lz
                                     if tag.search(l) and not l.lstrip().startswith(';')]
    ids = None
    if own is not None and lz is not None:
        zones = [spawns.write_line(variant, z) for z in own if z.get('lwr', True) is not False]
        ids = [z['id'] for z in own if z.get('lwr', True) is not False]
    rule = re.compile(r'(?<![A-Za-z])' + re.escape('Map="%s")' % base), re.IGNORECASE)
    rules = None if minimods is None else [rule.sub(lambda _: 'Map="%s")' % variant, l) for l in minimods
                                           if rule.search(l) and not l.lstrip().startswith(';')]
    return dict(maps=records, missions=missions, recordMissions=stands, matchedNames=matched, streamSlots=slots,
                landingZones=zones, miniMods=rules, **({'missionsFromProject': True} if isinstance(missions_list, list) else {}),
                **({'landingZonesFromProject': True, 'landingZoneIds': ids} if own is not None and lz is not None else {}))


def readme(m):
    c = m['config']
    lines = [
        '%s: %s, a variant of %s%s' % (m['variant'], m['project']['name'], m['source']['map'],
                                     ' (QUICK BUILD: its lighting is not baked)' if m.get('quick') else ''),
        '',
        'Built by the XCOM Map Workshop %s from project %s, revision %s, on %s.' % (m.get('editorVersion', ''), m['project']['id'],
                                                                                 m['project']['revision'], m['builtAt']),
        'Base map: %s with SHA-256 %s (the game release it was built from).' % (m['source']['map'], m['source']['sha256']),
        '',
        'Files: copy the contents of CookedPCConsole into XEW\\XComGame\\CookedPCConsole of the game:',
    ]
    lines += ['  %s' % Path(f).name for f in sorted(m['files'])]
    lit = light_summary(m.get('lights'))
    made = (('its copies made as pieces of the map, in its tiles; ' if m.get('nativeCopies') else '')
            + ('the pieces it deletes or moves taken out; ' if m.get('nativeHides') else '')
            + ('its cover blocks and invisible floors made as hidden pieces, in their tiles; '
               if m.get('coverBlocks') else '')
            + ('its light edits made in the map (%s); ' % lit if lit else ''))
    if m.get('quick'):
        lines += [
            '',
            '%s.upk is %s with the edit made in it: %sits lighting NOT baked. This is a quick build, to check pathing, '
            'cover and line of sight in the game, which are as a full build makes them. Its lighting is not right: the '
            'copies keep the lighting their originals have where they stand and cast no shadows, and the pieces it '
            'deletes or moves leave their shadows behind.%s Build the project with Bake the lighting ticked for its '
            'proper lighting.'
            % (m['variant'], m['source']['map'], made, ' ' + QUICK_LIGHTS if lit else ''),
        ]
    elif m.get('lightingUnchanged'):
        lines += [
            '',
            '%s.upk is %s with the edit made in it: %sits lighting calculated, and the edit changes no baked light '
            '(lighting unchanged), so it reads %s\'s own lightmaps and has no texture cache of its own.'
            % (m['variant'], m['source']['map'], made, m['source']['map']),
        ]
    elif m.get('lightingInside'):
        lines += [
            '',
            '%s.upk is %s with the edit made in it: %sits lighting baked, its lightmaps inside the map (no texture '
            'cache goes with it).' % (m['variant'], m['source']['map'], made),
        ]
    else:
        lines += [
            '',
            '%s.upk is %s with the edit made in it: %sits lighting baked; its lightmaps are in %s.tfc, which goes in '
            'CookedPCConsole itself.' % (m['variant'], m['source']['map'], made, m['cache']),
        ]
    if m.get('picture'):
        lines += ['%s.upk holds the project\'s map picture (MapPicture, 512 x 256, %s): Long War Rebalance 3 shows it '
                  'on the mission screens; plain Enemy Within and earlier Long War versions don\'t look for it.'
                  % (m['variant'], m['picture'].get('format'))]
    elif m.get('pictureNote'):
        lines += ['No map picture: %s.' % m['pictureNote']]
    counts = m.get('lights') or {}
    if lit and not m.get('quick') and (counts.get('added') or counts.get('changed') or counts.get('moved')):
        lines += ['Each added, moved or changed light is baked into the lightmaps of the pieces it reaches and listed '
                  'in them, so the game doesn\'t light those pieces with it a second time.']
    if m['patch']:
        lines += ['%s.upk is the rest of the edit, which the game makes at load, streamed into the variant.' % m['patch']]
    intros = m.get('intros') or []
    for intro in intros:
        if intro['stream'] in LANDINGS:
            lines += ['%s.upk is the landing intro (%s) with %s\'s landing under the variant\'s name, so the Skyranger '
                      'lands as it does in %s.' % (intro['copy'], intro['stream'], m['source']['map'], m['source']['map'])]
        else:
            lines += ['%s.upk is the intro (%s) with %s\'s scene under the variant\'s name, so the intro plays as it '
                      'does in %s.' % (intro['copy'], intro['stream'], m['source']['map'], m['source']['map'])]
    several = len(c['maps']) > 1
    slots = sorted(set(s for s in c['streamSlots'] if s is not None))
    lines += [
        '',
        'Config: add these lines to XEW\\XComGame\\Config.',
        '',
        'DefaultMaps.ini, in the [XComGame.XComMapManager] list (out of rotation%s%s)%s:'
        % ('; streams %s in slot %s' % (m['patch'], ' or '.join(map(str, slots))) if m['patch'] else '',
           ''.join('; streams %s in place of %s' % (i['copy'], i['stream']) for i in intros),
           ('; one record for each mission the project is for (%s): keep the ones you want' % ', '.join(c['missions'])
            if c.get('missionsFromProject') else
            '; one record for each mission %s serves (%s): keep the ones you want' % (m['source']['map'], ', '.join(c['missions'])))
           if several else ''),
    ] + c['maps'] + ['']
    for m_ in c.get('matchedNames') or []:
        lines += ['The %s record\'s display name keeps "%s": %s.' % (c['missions'][m_['record']], m_['marker'], m_['why'])]
    if c.get('matchedNames'): lines += ['']
    if c['landingZones'] is None:
        pass    # the install has no DefaultLZMutator.ini (plain EW): the variant lands as the map itself says
    elif c.get('landingZonesFromProject'):
        lines += ['DefaultLZMutator.ini, the project\'s landing zones (beside %s\'s, or at the end):' % m['source']['map']]
        lines += c['landingZones'] or ['(none: the project has no landing zone with a line)']
    elif c['landingZones']:
        lines += ['DefaultLZMutator.ini, beside %s\'s landing zones:' % m['source']['map']] + c['landingZones']
    else:
        lines += ['DefaultLZMutator.ini: nothing to add; %s has no landing zones there, so its variant needs none.'
                  % m['source']['map']]
    ex = c.get('dropInExclusion')
    if ex and ex.get('why'):
        lines += ['', 'The project leaves scripted drop-ins where placed (Long War\'s %s, [%s]), but %s.'
                  % (ex['file'], ex['section'], ex['why'])]
    elif ex:
        lines += ['', '%s, in its [%s] section after its ExcludeMaps lines (the project leaves scripted drop-ins where '
                  'placed: Long War\'s drop-in mutator leaves the variant alone):' % (ex['file'], ex['section']), ex['line']]
    if c['miniMods']:
        lines += ['', 'DefaultMiniMods.ini, beside %s\'s rules (optional):' % m['source']['map']] + c['miniMods']
    base = m['source']['map']
    lines += [
        '',
        'Playing it (with XCOM closed):',
        '- The editor\'s Play in game (Project menu) installs this build under its own name and starts the game in a '
        'battle on it, and Remove from game takes it back out; the editor keeps a backup of each file it changes.',
        '- By hand: copy the files and add the lines above. The records are out of rotation (bInRotation=False), so no '
        'mission picks the variant yet. For missions to pick it like any other map, set bInRotation=True on the records '
        'you want. To play it instead of %s, also set bInRotation=False on %s\'s own records for the same missions '
        '(the lines with Name="%s" in DefaultMaps.ini).' % (base, base, base),
        '- Start a fresh mission afterwards: a tactical save from before ignores the new pieces\' cover.',
        '- To take it out again: remove the lines you added and the files listed above.',
        '',
    ]
    return EOL.join(lines)


# ---------------------------------------------------------------- stages

@dataclasses.dataclass(frozen=True)
class BuildInputs:
    """What a Build is given, as one record (Build.__init__ took 22 parameters: review finding 23). main makes it from
    the command line, which is how the server's builds give it (tools/viewer/builds.py and buildqueue.py start this
    file as a process); the tests, build_outputs.py and the examples make it themselves. The first five are the
    project and its folders; the rest have the defaults a command line's build has. Build.__init__ reads it once and
    keeps each value as the stages read it (folders as paths)."""
    project: object         # the project file, or the server's snapshot of it (saved_file names the project's own)
    cache: object           # the viewer cache: the map's export and the library of other maps' pieces
    output: object          # the builds folder
    lwr: object             # the game install (LWR or plain Enemy Within), only read
    udk: object             # UDK 2011-09, or None: only a patch needs UDK, and no project the compiler accepts has one
    radius: float = RADIUS  # the relight's receivers are those within this many units of the edit
    patch_work: object = None   # patchtool's work folder (None: the builds folder's own)
    now: object = None      # the build's clock (None: now), for its id, its stamp and builtAt
    run: object = None      # runs a tool (None: Build._run; tests and build_outputs.py give a recorder)
    seed: object = None     # the seeder (None: Build._seed; tests give a stand-in)
    echo: object = print    # where the build's lines go
    enable: tuple = ()      # families built although the compiler doesn't build them yet (--family)
    quick: bool = False     # the edit made in the map without baking its lighting (edit_unbaked)
    foreign: tuple = ()     # families whose pieces from other maps build before their switch (--foreign-family)
    projects: object = None     # the projects folder the build's names are checked against (None: the project file's)
    games: tuple = ()       # other game installs whose names the build's are checked against (the one Play in game uses)
    named: object = None    # named_base's growing write (None: Build._name_copy; tests give a stand-in)
    # the server's launch this build is (builds.py: a UUID), carried into the manifest so the server knows its own
    # package, and into the build's id so two builds in one second are told apart
    attempt: object = None
    saved_file: object = None   # the project's own file when the build reads a snapshot of it (the build queue's)
    boundary: object = None     # publication.publish's step hook (tests)
    picture: object = None  # the map picture's writer (None: Build._picture; tests give a stand-in)
    # the build's work folder (--work; None: a prefab test's is `w` beside its project file, any other build's
    # <output>/.work/<Variant>-<stamp>: Build.work_folder)
    work: object = None


class Build:
    def __init__(self, inputs):
        """The Build of `inputs` (BuildInputs). The state its stages fill is named here too, each with the stage that
        fills it, so none is made by first use."""
        self.project_path = Path(inputs.project)
        self.attempt = inputs.attempt
        self.saved_file = Path(inputs.saved_file) if inputs.saved_file else None
        self.boundary = inputs.boundary
        # whose names the build checks its own against (outputnames.Claims): the projects folder (the project file's
        # own, unless given), the builds folder, the game install it reads and `games` (the one Play in game uses)
        self.projects = Path(inputs.projects) if inputs.projects else self.project_path.parent
        self.games = tuple(Path(g) for g in inputs.games if g)
        self.quick = bool(inputs.quick)
        self.enable = tuple(inputs.enable)
        self.foreign = tuple(inputs.foreign)
        self.cache, self.output, self.lwr = Path(inputs.cache), Path(inputs.output), Path(inputs.lwr)
        self.udk = Path(inputs.udk) if inputs.udk else None
        self.radius = inputs.radius
        # patchtool's work folder: the builds folder's own, so a build needs nothing from our lab's layout
        self.patch_work = Path(inputs.patch_work) if inputs.patch_work else self.output / '.work' / 'patchtool'
        self.now = inputs.now or datetime.datetime.now()
        self.stamp = (self.now.strftime('%Y%m%d-%H%M%S')
                      + ('-%s' % self.attempt.replace('-', '')[:8] if self.attempt else ''))
        self.run_tool = inputs.run or self._run
        self.seed_tool = inputs.seed or self._seed
        self.name_tool = inputs.named or self._name_copy
        self.picture_tool = inputs.picture or self._picture
        self.work_given = Path(inputs.work) if inputs.work else None
        self.echo = inputs.echo
        self.stages = []
        self.started = self.stage_started = time.monotonic()
        # The state the stages fill, in run's order; none of it is read before its stage has run.
        # snapshot: the project's document (its bytes read once), its picture file, its names and source map, the
        # export, the install's base map (`base`, which the shell stage may replace with the equipped map), the work
        # folder and the decoded packages kept in it (unpacked)
        self.doc = self.project_sha = self.picture_png = None
        self.variant = self.patch = self.map = self.sha = self.export = self.scene = None
        self.base = self.install_base = self.install_cooked = self.work = self.unpacked_work = None
        # compile: the compiler's report (compile-report.json) and what it left out, whether the map's size and the
        # missions list are read, and the native edit with what the stages after it read of it; `copies` is the edit's
        # file (transplant names the staged one). drop_untried changes some of them, and lists the untried pieces the
        # Build itself left out
        self.compile_report = self.left_out = self.missions_listed = self.native = self.natives = None
        self.stage_kept = True
        self.covers = self.buildings = self.building_edits = self.any_buildings = None
        self.piece_flags = self.piece_blasts = self.flags_edit = self.spawn_edits = self.effects_edit = None
        self.has_patch = self.resizes = self.cleared = self.landing_zones = self.spawn_rules = None
        self.has_lights, self.lights, self.moves_landings = False, None, False
        self.stream_moves = self.stream_tiles = self.spec = self.copies = None
        self.untried_dropped = []
        # patch_and_cook: the cooked patch and its seed plan; shell: what the equipped map brought
        self.cooked = self.seed_plan = self.shelled = None
        # transplant: the map the copy tool reads (the base map, or the one staged with pieces of other maps) and the
        # maps those came from
        self.source = self.donors = None
        # light: the folder of the edited map, its texture cache's name, whether its lighting is unchanged, and the
        # relight's record
        self.lit = self.cache_name = self.relit = None
        self.unchanged = False
        # the map's own landings the project moves, read once, when the intro copies (package) first ask (landing_moves)
        self._landing_moves = None
        # package: the seeds' report, the map picture written (or the note why not), the lightmaps put inside the map,
        # and the manifest and folder of the finished package
        self.seeded = self.pictured = self.picture_note = self.inside = self.manifest = self.folder = None

    def _run(self, args, log):
        """Run a tool, its output to the log file and the console; raise on a failure. The tool writes its output in
        UTF-8 (procs.utf8_env), so a path whose characters the system's code page lacks is printed, not fatal."""
        self.echo('  $ %s' % subprocess.list2cmdline([str(a) for a in args]))
        with open(log, 'w', encoding='utf-8', newline='\n') as f:
            proc = subprocess.Popen([str(a) for a in args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, encoding='utf-8', errors='replace', cwd=str(TOOLS.parent),
                                    env=procs.utf8_env())
            for line in proc.stdout:
                f.write(line)
                self.echo('    ' + line.rstrip())
            code = proc.wait()
        if code:
            tool = next((Path(str(x)).name for x in args if str(x).endswith(('.py', '.ps1'))), str(args[0]))
            raise BuildError('%s failed (exit %d); see %s' % (tool, code, log))

    @staticmethod
    def _seed(src, dst, plan):
        import seed_map
        import seed_tiles
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            seed_map.apply(str(src), str(dst), [str(plan)], seed_tiles.SEED_DEFAULT)
        return out.getvalue().strip()

    def stage(self, name, **result):
        # how long the stage took: since the stage before it ended (faster-bake plan, 6.2)
        now = time.monotonic()
        result = dict(result, seconds=round(now - self.stage_started, 1))
        self.stage_started = now
        self.stages.append(dict(stage=name, **result))
        self.echo('%s: %s' % (name, json.dumps(result)))

    def unpacked(self):
        """Decoded packages are kept for this build's tools (decomp.py): what a tool decodes, in the work folder,
        for the tools after it and the relight's workers; the pristine base map's image in the viewer cache, for
        the next build of the map too (faster-bake plan, 3.1). The work folder's go when the build ends."""
        self.unpacked_work = self.work / 'unpacked'
        if not long_paths() and len(os.path.abspath(self.unpacked_work / UNPACKED_NAME)) > PATH_LIMIT:
            self.echo('note: the decoded maps can\'t be kept in the work folder (%s): its path is too long for their '
                      'names, so each tool decodes the maps it reads again, which is slower. A builds folder on a '
                      'shorter path avoids it' % self.unpacked_work)
        os.environ[decomp.WORK_ENV] = str(self.unpacked_work)
        keep = self.cache / '.unpacked'
        os.environ[decomp.KEEP_ENV] = str(keep)
        try:
            decomp.keep(str(self.base), str(keep))
        except (OSError, ValueError, KeyError, struct.error):
            pass        # not a package this can read: the stages after it say so

    def snapshot(self):
        # the bytes read once: the manifest names them by their SHA-256, as the server's job and bug report do
        data = self.project_path.read_bytes()
        self.doc = json.loads(data.decode('utf-8'))
        self.project_sha = hashlib.sha256(data).hexdigest()
        self.picture_png = self.find_picture()
        out = self.doc.get('output') or {}
        self.variant, self.patch = out.get('shipAs'), out.get('patch')
        src = self.doc.get('source') or {}
        self.map, self.sha = src.get('map'), src.get('sha256')
        if not (self.variant and self.patch and self.map and self.sha):
            raise BuildError('the project has no output names or source binding')
        # the files it writes must fit Windows' path limit, checked before anything else (and again with the names
        # the compile adds: preflight)
        self.work = self.work_folder()
        self.check_paths([self.variant] + self.intro_names())
        # the builds folder's package of this name must be this project's, checked before any costly work (and again
        # as the new one goes in: package)
        owned_folder(self.output, self.variant, self.doc.get('id'))
        # a generation with the light metadata (export 18)
        try:
            self.export, self.scene = compiler.find_export(self.cache, self.doc, minimum=EXPORT_MINIMUM)
        except compiler.ExportMissing as error:
            raise BuildError(str(error), code=compiler.ExportMissing.code)
        self.base = lwr_file(self.lwr, 'CookedPCConsole', '%s.upk' % self.map)
        if not self.base.is_file():
            raise BuildError('the game install has no %s' % self.base)
        if sha256(self.base) != self.sha:
            raise BuildError('%s is not the map the project was made on (SHA-256 %s)' % (self.base, self.sha))
        # the install's own file and folder: `base` becomes the equipped map where the shell stage makes one
        self.install_base, self.install_cooked = self.base, self.base.parent
        (self.work / 'logs').mkdir(parents=True, exist_ok=True)
        self.unpacked()
        self.stage('snapshot', project=self.doc.get('id'), revision=self.doc.get('revision'), base=str(self.base),
                   export=str(self.export))

    def work_folder(self):
        """Where the build works (its logs, records, the lit map, the package before it goes in place): the folder
        it is given (BuildInputs.work), else a prefab test's own folder's `w` (PREFAB_TEST_WORK, beside the test's
        project file, which the test writes in its folder: prefab_tests.py), else <output>/.work/<Variant>-<stamp>. A
        prefab test's builds folder is <builds>/.prefab-tests/<test>/artifacts: a work folder under it as any build's
        added about 60 characters to each path, which with a long builds folder passed Windows' 260 (KB-12)."""
        if self.work_given:
            return self.work_given
        if 'prefabTest' in self.doc:
            return self.project_path.parent / PREFAB_TEST_WORK
        return self.output / '.work' / ('%s-%s' % (self.variant, self.stamp))

    def intro_names(self):
        """The variant's copies of the intros its base map's records stream (as output_names names them), read from
        the install before the snapshot stage for check_paths; [] where the records can't be read (the stages after
        say why)."""
        try:
            maps = installs.maps_text(self.lwr).replace('\r\n', '\n').split('\n')
            return ['%s_%s' % (s, self.variant) for s in intro_streams(base_records(maps, self.map))]
        except (BuildError, OSError, ValueError, installs.InstallError):
            return []

    def deepest_files(self, names):
        """The files of the build that lie deepest, each (path, what it is): in the work folder, its compile report,
        the edited map's temporary file (package_grow.py writes <map>.grow-tmp beside the map it writes), the map
        with the pieces of other maps staged in it (transplant.py), and in a full build the relight's previews
        (<variant>-<actor>-shadow.png, the actor's name up to PREVIEW_ACTOR characters); and each of `names` (the
        package's maps: the variant, its patch, its intro and stream copies) in the package as it is made in the work
        folder and where it goes."""
        w, v = self.work, self.variant
        files = [(w / 'compile-report.json', 'the compile report'),
                 (w / 'lit' / ('%s.upk.grow-tmp' % v), 'the edited map\'s temporary file'),
                 (w / 'transplant' / 'staged' / ('%s.upk.grow-tmp' % self.map), 'the staged map\'s temporary file')]
        if not self.quick:
            files.append((w / 'lit' / ('%s-%s-shadow.png' % (v, 'X' * PREVIEW_ACTOR)), 'a preview of the relight'))
        for name in names:
            files += [(w / 'package' / 'CookedPCConsole' / ('%s.upk' % name), 'the package\'s %s.upk' % name),
                      (self.output / v / 'CookedPCConsole' / ('%s.upk' % name), 'the package\'s %s.upk' % name)]
        return files

    def check_paths(self, names):
        """Before the costly stages (the snapshot's first step, and preflight with the names the compile adds): a
        BuildError with the code path-too-long when a file the build writes (deepest_files, `names` its package's
        maps) would pass Windows' path limit (PATH_LIMIT, FOLDER_LIMIT for its folder), saying by how many characters,
        on a system where long paths are off (long_paths). It replaces a FileNotFoundError in the middle of the build
        (KB-12); it is no limit of the editor's own. The decoded maps the build keeps in its work folder (decomp.py)
        are not counted: one that can't be written is decoded again by each tool that reads it, which is slower and
        stops nothing (the snapshot stage says so: unpacked)."""
        if long_paths():
            return
        worst = None
        for path, what in self.deepest_files(names):
            full = os.path.abspath(path)
            over = max(len(full) - PATH_LIMIT, len(os.path.dirname(full)) - FOLDER_LIMIT)
            if over > 0 and (worst is None or over > worst[0]):
                worst = (over, full, what)
        if worst:
            over, full, what = worst
            raise BuildError('the builds folder\'s path is too long for this build by %d character%s: %s would be '
                             'written at %s (%d characters), and Windows takes paths of at most %d characters (%d for a '
                             'folder). Put the builds folder on a path at least %d characters shorter: install the editor '
                             'in a shorter folder (Setup), or set the output folder (viewer.py settings --output <folder>)'
                             % (over, '' if over == 1 else 's', what, full, len(full), PATH_LIMIT, FOLDER_LIMIT, over),
                             code='path-too-long')

    def find_picture(self):
        """The picture file the project names (pictures.named), or None, looked up once as the build starts. A build
        of a snapshot (the server's: --saved-file) takes the copy the server captured beside it
        (pictures.beside: <snapshot>.picture.png) when its SHA-256 is the one named, and nothing else, so its picture
        is the one saved with the bytes it was handed, whatever was chosen since; any other build takes the one kept
        with the project (pictures.picture_file)."""
        named = pictures.named(self.doc)
        if not named:
            return None
        if self.saved_file:
            beside = pictures.beside(self.project_path)
            try:
                return beside if beside.is_file() and pictures.sha256(beside.read_bytes()) == named else None
            except OSError:
                return None
        return pictures.picture_file(self.projects, self.doc.get('id'), named)

    def compile(self):
        # pieces of other maps come from the library in the cache, read from this install
        spec, report = compiler.compile_project(self.doc, self.scene, self.enable,
                                                compiler.Library(self.cache, self.lwr), self.foreign)
        report['export'] = str(self.export)
        self.compile_report = report
        compiler.write_json(self.work / 'compile-report.json', report)
        if spec is None:
            raise BuildError('the project does not compile: %s' % '; '.join(e['message'] for e in report['errors']))
        # the pieces the compiler left out (plan "sturdier prefabs", R4): the build goes on without them, and the
        # Build's window and the manifest name them (the first LEFT_OUT_SHOWN; compile-report.json has them all)
        self.left_out = [dict(actor=e.get('entity') or e.get('target') or '', code=e['code'], message=e['message'])
                         for e in report.get('leftOut') or []]
        # the parts of the document the compiler left out are not read here either: the map size (shell), and the
        # missions list, whose entries the Build can write are the compiler's (report `missions`; None: every record)
        self.stage_kept = not any(e.get('record') == 'stage' for e in report.get('leftOut') or [])
        listed = self.doc.get('missions')
        self.missions_listed = report['missions'] if 'missions' in report else listed if isinstance(listed, list) else None
        patch_spec, self.native = compiler.native_split(compiler.stream_only(spec))
        self.natives = self.native['copies']
        self.covers = self.native.get('covers') or []
        # buildings made from nothing (tools/bake/buildings.py): made in the map by native_copy.py, as cover blocks are
        self.buildings = self.native.get('buildings') or []
        # the map's own buildings changed or deleted (buildings.edit): edited in place by native_copy.py too
        self.building_edits = self.native.get('buildingEdits') or []
        self.any_buildings = bool(self.buildings or self.building_edits)
        # pieces' flags (piece flags plan): the map's own pieces whose flags change where they stand, written in the map
        # by native_copy.py (a copy's flags go with the copy); flags alone change no light
        self.piece_flags = self.native.get('pieceFlags') or []
        # (the map's own pieces broken where they stand go with the flags' step: E6)
        self.piece_blasts = self.native.get('pieceBlasts') or []
        self.flags_edit = bool(self.piece_flags or self.piece_blasts)
        # effects and ambient sounds moved, copied or deleted (the effects and sounds plan, Part D): made in the map by
        # native_copy.py in both kinds of build; on their own they change no baked light (an effect and a sound are
        # dynamic), so a full build makes them as cover blocks are made, with the map's lighting kept. Lens flares
        # (stage FX6b) are the same: a glare drawn over the picture, no baked light
        # the base map's spawn points moved or given values (the editor spawns plan, SP6) are the same: settings and
        # places the game reads, no light, so they go with the effects (made by native_copy.py, lighting kept)
        self.spawn_edits = {op: len((self.native.get('spawns') or {}).get(op) or []) for op in ('moves', 'values', 'copies', 'deletes')}
        self.effects_edit = any((self.native.get(k) or {}).get(op) for k in EFFECT_LANES + ('spawns',)
                                for op in ('moves', 'deletes', 'copies', 'values'))
        self.has_patch = bool(patch_spec['objects'])
        # light edits (editor lights plan, 4.5): made in the map by native_copy.py, in both kinds of build
        self.has_lights = has_light_edits(self.native)
        self.lights = light_counts(self.native)
        self.resizes = bool(report.get('stageGrid'))
        # a cleared map (Clear map plan, section 7): native_copy.py's clear_level, and the shell stage's cursor storeys
        self.cleared = self.native.get('cleared')
        # the project's landing zones (Clear map plan, section 4): its own lines, and the map's own landings moved in
        # the map (native_spawns.py, run by native_copy.py) where a zone that is also theirs moves them
        self.landing_zones = self.native.get('landingZones')
        # the project's spawn rule (spawns plan, SP8): the variant's ExcludeMaps line, a change of its own
        self.spawn_rules = self.native.get('spawnRules')
        self.moves_landings = bool(self.landing_zones and self.landing_zones.get('own'))
        # a mission's objects moved in their streams (mission types plan, Part E): moved in place in the variant's
        # copies of the streams (stream_copies), and the base map's tiles under a moved solid piece rebuilt
        self.stream_moves = self.native.get('streamMoves') or {}
        if self.stream_moves:
            self.native['streamTiles'] = self.stream_tile_boxes()
        self.stream_tiles = bool(self.native.get('streamTiles'))
        if not self.has_work():
            if self.left_out:
                raise BuildError('nothing of the project can be built: %s left out (%s)' % (
                    'its one edit is' if len(self.left_out) == 1 else 'its %d edits are' % len(self.left_out),
                    '; '.join(row['message'] for row in self.left_out[:3]) + ('; ...' if len(self.left_out) > 3 else '')))
            raise BuildError('the project changes nothing in the map: no piece, effect, sound, lens flare or spawn point is moved, deleted or '
                             'added, no light or flag is changed, no building is made, the map keeps its size, no '
                             'spawn rule is set, the missions are the map\'s and it has no map picture')
        self.spec = self.work / ('%s.json' % self.patch)
        compiler.write_json(self.spec, patch_spec)
        self.copies = self.work / 'native-edit.json'
        compiler.write_json(self.copies, self.native)
        # pieces, effects and sounds of other maps (the effects and sounds plan, FX4): the transplant stage's step
        foreign = sum(1 for c in self.natives if c.get('donor')) + sum(
            1 for k in EFFECT_LANES for c in (self.native.get(k) or {}).get('copies') or [] if c.get('donor'))
        for row in self.left_out[:LEFT_OUT_SHOWN]:
            self.echo('left out: %s' % row['message'])
        # what the edit does to the missions the variant keeps (mission types plan, C3): the build window lists them by
        # mission; the build goes on
        mission_rows = [dict(mission=w.get('mission'), message=w['message'], **({'actor': w['actor']} if w.get('actor') else {}))
                        for w in report.get('warnings') or [] if str(w.get('code', '')).startswith(('mission-', 'spawn-'))]
        for row in mission_rows[:LEFT_OUT_SHOWN]:
            self.echo('mission: %s' % row['message'])
        self.stage('compile', spec=str(self.spec), nativeCopies=len(self.natives), families=list(self.enable),
                   **({'leftOutPieces': self.left_out[:LEFT_OUT_SHOWN]} if self.left_out else {}),
                   **({'missionWarnings': mission_rows[:LEFT_OUT_SHOWN], 'missionWarningCount': len(mission_rows)}
                      if mission_rows else {}),
                   **({'foreignCopies': foreign} if foreign else {}),
                   **({'coverBlocks': len(self.covers)} if self.covers else {}),
                   **({'pieceFlags': len(self.piece_flags)} if self.piece_flags else {}),
                   **({'flagCopies': n} if (n := sum(1 for c in self.natives if c.get('flags'))) else {}),
                   **({'buildings': len(self.buildings)} if self.buildings else {}),
                   **({'buildingEdits': len(self.building_edits)} if self.building_edits else {}),
                   **({'cleared': self.cleared} if self.cleared else {}),
                   streamHides=self.native.get('streamHides') or {},
                   nativeBreakGroups=len({c['breakGroup'] for c in self.natives + self.covers if c.get('breakGroup')}),
                   copierCopies=sum(len(o['from']) for o in patch_spec['objects'] if o['type'] == 'copy'),
                   hides=len(self.native['hides']),
                   patchHides=sum(len(o['alsoHide']) for o in patch_spec['objects'] if o['type'] == 'hide'),
                   # the compiler's own light counts give way to the native edit's (light_counts)
                   **({'lights': self.lights} if self.lights else {}),
                   **{k: v for k, v in report['counts'].items() if k != 'lights'})

    def has_work(self):
        """Whether the edit leaves the Build something to make: a piece, light, flag, effect, sound, flare or spawn
        point changed, a building, a size, a clear, landing zones, a mission's objects moved, a spawn rule, the
        project's own list of missions (the records the variant gets are a change of their own) or a map picture (a
        project that only gives its map a picture builds: LWR map packs plan). The compile step's test, and the one
        drop_untried asks again after it drops copies."""
        return bool(self.natives or self.native['hides'] or self.covers or self.has_patch or self.has_lights
                    or self.resizes or self.any_buildings or self.cleared or self.landing_zones is not None
                    or self.stream_moves or self.native.get('streamHides') or self.flags_edit or self.effects_edit
                    or self.spawn_rules or self.missions_listed is not None or pictures.named(self.doc))

    def claims(self):
        """Who holds which names now (outputnames.Claims), this project's own left out."""
        games = [self.lwr] + [g for g in self.games if not outputnames.same(g, self.lwr)]
        try:
            return outputnames.Claims(self.projects, self.output, games, self.doc.get('id'))
        except outputnames.NamesError as error:
            raise BuildError('the names the build writes can\'t be checked: %s' % error)

    def output_names(self):
        """Every name this build may write: the map, its patch (only when the edit makes one, which the compile has
        said by now: a file of the patch's name that the build never writes doesn't stop it), its texture cache (not
        in a quick build), and its copies of the intros its base map's records stream and of the streams the edit
        changes."""
        names = ([self.variant] + ([self.patch] if self.has_patch else [])
                 + ([] if self.quick else [outputnames.cache_name(self.variant)]))
        maps = installs.maps_text(self.lwr).replace('\r\n', '\n').split('\n')
        names += ['%s_%s' % (s, self.variant) for s in intro_streams(base_records(maps, self.map))]
        streams = set(self.native.get('streamHides') or {}) | set(self.native.get('streamMoves') or {})
        names += ['%s_%s' % (s, self.variant) for s in sorted(streams)]
        return names

    def check_names(self, names):
        """A BuildError naming what holds each of `names` that anything but this project holds (another project's
        output names, another build, a package of the game install...): a build never writes over them."""
        clash = self.claims().conflicts(names)
        if clash:
            raise BuildError('the build would write names that are taken: %s. Save the project under a new name '
                             '(Save as) to give it names of its own, or take away what holds them'
                             % '; '.join('%s (%s)' % (n, what) for n, what in clash))

    def preflight(self):
        """Before the costly stages: every name the build may write is free for this project (check_names), and its
        files with those names fit Windows' path limit (check_paths: the stream copies are known from the compile)."""
        names = self.output_names()
        self.check_names(names)
        self.check_paths(names)

    def patch_and_cook(self):
        if not self.has_patch:
            self.cooked = self.seed_plan = None
            self.stage('patch', skipped='nothing for a patch: the edit is made in the map itself')
            return
        if self.udk is None or not PATCHTOOL.is_file():
            raise BuildError('this edit needs a patch cooked in UDK, %s: set the udk setting to UDK 2011-09 with the '
                             'XComGame stubs (viewer.py settings --udk <folder>), or leave out the pieces the compile '
                             'report lists for the patch' % ('which this copy of the editor does not ship' if self.udk
                                                            else 'and the udk setting is not set'))
        common = ['-Udk', self.udk, '-Work', self.patch_work, '-Lwr', self.lwr]
        ps = ['pwsh', '-NoProfile', '-File', PATCHTOOL]
        self.run_tool(ps + ['build', self.spec, '-Force'] + common, self.work / 'logs' / 'patchtool-build.log')
        self.run_tool(ps + ['cook', self.spec] + common, self.work / 'logs' / 'patchtool-cook.log')
        self.cooked = self.udk / 'UDKGame' / 'CookedPC' / 'Maps' / 'patches' / ('%s.udk' % self.patch)
        if not self.cooked.is_file():
            raise BuildError('no cooked patch %s' % self.cooked)
        plan = self.patch_work / self.patch / 'seed-plan-built.tsv'
        self.seed_plan = plan if plan.is_file() and plan.stat().st_size else None
        self.stage('patch', cooked=str(self.cooked), bytes=self.cooked.stat().st_size,
                   seedPlan=str(self.seed_plan) if self.seed_plan else None)

    def shell(self):
        """A base map that is little more than a level and a tile grid (the game's blank map) gets what a battle and
        the later stages need of it, from another map of the install (tools/bake/shell.py): soldier spawn points,
        cursor volumes, a volume to clone rebuild volumes from. The equipped map is the base from here on. A map that
        lacks none of them, which is every other map, is left alone and the stage says nothing.
        A project can also ask for a larger tile grid (`stage: {grid: [nx, ny]}`, tiles, from the map's own corner,
        or [nx, ny, nz] with the levels, from its own bottom): the same tool lays ground over the new area and writes
        the map's tile data for it (prefab plan 5.11, 5.6b)."""
        # (a size the compiler left out is not read: the map keeps its own)
        stage = (self.doc.get('stage') if self.stage_kept else None) or {}
        grid = stage.get('grid')    # the compiler has checked it against the map's own
        cleared = bool(self.cleared)
        ambient = self.doc.get('prefabTest') and self.map in compiler.STAGE_MAPS
        paths.use('bake')
        import shell
        from package import Package
        try:
            lacking = shell.needs(Package(self.base), building=self.needs_templates())
        except (OSError, ValueError, KeyError, struct.error):
            return      # not a package this stage can read: the stages after it say so
        if not (lacking or grid or stage.get('lines') or stage.get('hideGround') or ambient or cleared):
            return
        out = self.work / 'shell'
        self.run_tool([sys.executable, '-B', '-u', SHELL, self.base, out, '--cooked', self.install_cooked]
                      + (['--grid', grid[0], grid[1]] if grid else [])
                      + (['--levels', grid[2]] if grid and len(grid) == 3 else [])
                      + (['--grid-lines'] if stage.get('lines') else ['--hide-ground'] if stage.get('hideGround') else [])
                      + (['--ambient-light'] if ambient else [])
                      # a cleared map lays no ground: the user lays floor pieces (Clear map plan, section 7)
                      + (['--no-ground'] if grid and (stage.get('ground') is False or cleared) else [])
                      + (['--clear'] if cleared else [])
                      + [x for e in self.piece_flags if e['flags'].get('floor') is False for x in ('--floor-off', e['name'])]
                      + (['--building'] if self.needs_templates() else []),
                      self.work / 'logs' / 'shell.log')
        try:
            report = json.loads((out / 'shell.json').read_text(encoding='utf-8'))
            if not report.get('shelled'):
                return      # it lacks nothing and has that grid already
            self.base = Path(report['shelled'])
            if not self.base.is_file():
                raise ValueError('no equipped map')
        except (OSError, ValueError, KeyError) as error:
            raise BuildError('shell.py equipped no map (%s); see %s' % (error, self.work / 'logs' / 'shell.log'))
        donor = report.get('donor') or {}
        self.shelled = dict(lacked=lacking, donor=donor.get('map'), sha256=donor.get('sha256'),
                            brought=report['brought'])
        if report.get('resized'):
            r = report['resized']
            self.shelled['grid'] = dict(before=r['before'], now=r['grid'], ground=r['ground'], planesLaid=r['planesLaid'],
                                        # the map's own low scenery in the new area: made walkable, or a floor
                                        # already, and the tiles they give floor on queued (F-100)
                                        walkableScenery=len(r.get('walkableScenery') or []),
                                        sceneryFloors=len(r.get('sceneryFloors') or []),
                                        sceneryTilesQueued=r.get('sceneryTilesSeeded', 0),
                                        blocksUnderScenery=len(r.get('blocksUnderScenery') or []),
                                        # the pieces whose Floor the project's flags turn off: left as they are
                                        **({'floorKeptOff': r['floorKeptOff']} if r.get('floorKeptOff') else {}))
        if report.get('gridLines'):
            self.shelled['gridLines'] = report['gridLines']
        if report.get('hiddenGround'):
            self.shelled['hiddenGround'] = report['hiddenGround']
        if report.get('ambientLight'):
            self.shelled['ambientLight'] = report['ambientLight']
        if 'clearedCursors' in report:
            self.shelled['clearedCursors'] = report['clearedCursors']
        self.stage('shell', equipped=str(self.base), **self.shelled)

    def drop_untried(self, error):
        """After a failed transplant or copy stage: the copies marked untried (compiler.Compiler.untried: a class the
        Build has not made before, an assembly's part on its own, a piece the library held back) that the failure names
        (untried_named) are taken out of the native edit with what depends on them: the hide of a moved one (it stays
        where the map has it), the glow lights that would follow them (area-light ops owned by them), an assembly left
        with no part, and a group they broke with that no longer can (unlinked_groups). They are named as left out,
        and the caller runs the stages again. False when the failure names none: it is the build's own, and nothing
        is run again."""
        gone = self.untried_named(error)
        if not gone:
            return False
        labels = {c['label'] for c in gone}
        names = {c['label'].split(':', 1)[-1] for c in gone}
        why = str(error).splitlines()[0][:300]
        self.echo('the Build could not make the edit with %d piece%s of kinds it has not made before (%s): building '
                  'without them' % (len(gone), '' if len(gone) == 1 else 's', why))
        self.native['copies'] = self.natives = [c for c in self.natives if c['label'] not in labels]
        self.native['hides'] = [h for h in self.native['hides'] if h['label'] not in labels]
        made = {c.get('assembly') for c in self.natives}
        if self.native.get('assemblies'):
            self.native['assemblies'] = [m for m in self.native['assemblies'] if m['id'] in made]
        # a dropped copy's copied glow light, a dropped move's moved one: the piece isn't made, or stays where it is
        lights = self.native.get('lights')
        if lights and lights.get('area'):
            lights['area'] = [a for a in lights['area']
                              if not (a.get('op') in ('copy', 'move') and str(a.get('ownerEntity')) in names)]
            self.has_lights, self.lights = has_light_edits(self.native), light_counts(self.native)
        unlinked = self.unlinked_groups(gone)
        dropped = [dict(actor=c['label'].split(':', 1)[-1], code='untried-failed',
                        message='making %s failed: left out%s'
                        % (c['label'].split(':', 1)[-1], ' (it stays where the map has it)' if c['label'].startswith('move:') else ''))
                   for c in gone]
        self.left_out += dropped
        self.untried_dropped = self.untried_dropped + dropped
        # compile-report.json has every piece left out, the Build's own too (its stage and the window show the first
        # LEFT_OUT_SHOWN), each marked by the stage that left it out
        if self.compile_report is not None:
            rows = self.compile_report.setdefault('leftOut', [])
            rows += [dict(record='build', entity=row['actor'], code=row['code'], message=row['message'], stage='leftout')
                     for row in dropped]
            if isinstance(self.compile_report.get('counts'), dict):
                self.compile_report['counts'] = dict(self.compile_report['counts'], leftOut=len(rows))
            compiler.write_json(self.work / 'compile-report.json', self.compile_report)
        for g in unlinked:
            self.echo('break group %d no longer breaks together: a piece of it could not be made' % g)
        self.copies = self.work / 'native-edit.json'
        compiler.write_json(self.copies, self.native)
        for folder in (self.work / 'transplant', self.work / 'lit'):
            if folder.exists():
                shutil.rmtree(folder)
        # (cumulative: a second failure that names another untried piece drops it too, and the stage lists both)
        self.stage('leftout', pieces=self.untried_dropped[:LEFT_OUT_SHOWN], count=len(self.untried_dropped), reason=why,
                   **({'groupsUnlinked': unlinked} if unlinked else {}))
        if not self.has_work():
            raise BuildError('nothing of the project can be built: its %d piece%s could not be made (%s)'
                             % (len(self.untried_dropped), '' if len(self.untried_dropped) == 1 else 's', why))
        return True

    def untried_named(self, error):
        """The untried copies a failure is about: those whose name (the copy's, or the moved piece's) or whose source
        actor its message names, or the last LOG_TAIL lines of the failing tool's log (the "see <log>" of _run's
        error, where a tool's traceback ends). [] when it names none."""
        untried = [c for c in self.natives if c.get('untried')]
        if not untried:
            return []
        text = str(error)
        log = re.search(r'; see (.+?)\s*$', text)
        if log:
            try:
                text += '\n' + '\n'.join(Path(log.group(1)).read_text(encoding='utf-8', errors='replace').splitlines()[-LOG_TAIL:])
            except OSError:
                pass

        def named(c):
            return any(n and re.search(r'(?<!\w)%s(?!\w)' % re.escape(n), text)
                       for n in (c['label'].split(':', 1)[-1], str(c.get('actor') or '')))
        return [c for c in untried if named(c)]

    def unlinked_groups(self, gone):
        """The break groups a dropped copy broke with that can't break together without it, by the compiler's rule
        (Compiler.groups): two breakable pieces, or one and a cover block, with one of them made in the map, or a made
        wall with a prop or a block. Their numbers are taken off the copies, cover blocks and made walls left, and their
        map pieces out of breakOriginals, so the edit links no group short of its pieces (native_copy.py refuses one).
        Returns those numbers."""
        touched = sorted({g for c in gone for g in (c.get('breakGroup'), c.get('wallGroup')) if g})
        undone = []
        for g in touched:
            copies = [c for c in self.natives if c.get('breakGroup') == g]
            originals = [o for o in self.native.get('breakOriginals') or [] if o.get('group') == g]
            blocks = [c for c in self.covers if c.get('breakGroup') == g]
            walls = [c for c in self.natives if c.get('wallGroup') == g]
            links = len(copies) + len(originals)
            if (walls and (links or blocks)) or (links >= (1 if blocks else 2) and (blocks or copies)):
                continue
            undone.append(g)
            for c in copies + blocks:
                c.pop('breakGroup', None)
            for c in walls:
                c.pop('wallGroup', None)
            if 'breakOriginals' in self.native:
                self.native['breakOriginals'] = [o for o in self.native['breakOriginals'] if o.get('group') != g]
        return undone

    def transplant(self):
        """Pieces of other maps (the native edit's copies with a donor), and effects and sounds of other maps (its
        `effects`, `sounds` and `flares` lanes' copies with a donor: the effects and sounds plan, stage FX4): each staged in a
        copy of the base map, with what it depends on (tools/bake/transplant.py). The copier then reads the staged map
        and the edit naming the staged actors. Without such a piece nothing is done."""
        self.source, self.donors = self.base, []
        foreign_effects = any(c.get('donor') for k in EFFECT_LANES
                              for c in (self.native.get(k) or {}).get('copies') or [])
        if not (any(c.get('donor') for c in self.natives) or foreign_effects):
            return
        out = self.work / 'transplant'
        self.run_tool([sys.executable, '-B', '-u', TRANSPLANT, self.base, out, '--edit', self.copies, '--cooked',
                       self.install_cooked], self.work / 'logs' / 'transplant.log')
        try:
            report = json.loads((out / 'transplant.json').read_text(encoding='utf-8'))
            self.source, self.copies = Path(report['staged']), out / 'native-edit.staged.json'
            if not (self.source.is_file() and self.copies.is_file()):
                raise ValueError('no staged map')
        except (OSError, ValueError, KeyError) as error:
            raise BuildError('transplant.py staged no map (%s); see %s' % (error, self.work / 'logs' / 'transplant.log'))
        self.donors = [dict(map=d['map'], sha256=d['sha256'], file=d['file'], pieces=d['pieces'],
                            effects=d.get('effects', 0), flares=d.get('flares', 0), objectsBrought=d['objectsBrought'],
                            objectsReused=d['objectsReused'], cut=d['cut'], sizes=d.get('sizes', []),
                            bytes=d['bytes']) for d in report['donors']]
        self.stage('transplant', staged=str(self.source), foreignPieces=report['foreignPieces'],
                   donors=[dict(map=d['map'], pieces=d['pieces'], effects=d['effects'], flares=d['flares'],
                                objectsBrought=d['objectsBrought'],
                                bytes=d['bytes'], cut=len(d['cut']), otherSizes=len(d['sizes'])) for d in self.donors])

    def light(self):
        self.lit = self.work / 'lit'
        if self.quick:
            return self.edit_unbaked()
        if not (self.natives or self.native['hides'] or self.covers or self.has_lights or self.any_buildings or self.cleared
                or self.moves_landings or self.has_patch or self.resizes or self.flags_edit or self.effects_edit):
            # landing-zone lines alone (Clear map plan, section 4), or a spawn rule (spawns plan, SP8): nothing in the
            # map changes, so nothing is relit, and the variant reads the map's own lightmaps (lighting unchanged; the
            # stage says so as cover blocks alone do, not as a quick build's)
            return self.edit_unbaked(unchanged=True)
        if (self.covers or self.any_buildings or self.cleared or self.flags_edit or self.effects_edit) and not (
                self.natives or self.native['hides'] or self.has_lights or self.has_patch or self.moves_landings):
            # cover blocks alone: hidden pieces change no baked light (a hidden actor casts no baked shadow,
            # shadows.py), so there is nothing to relight. The map is made as a quick build makes it and keeps the
            # original's lightmaps: lighting unchanged, no texture cache. The same for buildings made from nothing:
            # volumes and lists, no light. A landing moved in place is relit: its grounded Skyranger casts a shadow,
            # which goes with it (F-98). Pieces' flags alone are settings the game reads, not light: the same. So are
            # effects and sounds moved, copied or deleted (the effects and sounds plan). The map is the base map, or
            # the staged one with the effects and sounds of other maps in it (transplant)
            self.cache_name, self.unchanged = None, True
            self.run_tool([sys.executable, '-B', '-u', NATIVE_COPY, self.source, self.lit, self.variant, '--copies',
                           self.copies], self.work / 'logs' / 'native-copy.log')
            self.relit = dict(written=0, unchanged=0, skipped=0, shadowMaps=0, copies=[], nativeCopies=[], hidden=0,
                              lightingUnchanged=True, coverBlocks=len(self.covers), **self.building_record(),
                              **self.flag_record())
            self.stage('light', cache=None, baked=True, **self.relit)
            return
        self.cache_name = cache_name(self.variant)
        # the relit pieces of this project's last baked build are kept, and taken again where the new edit leaves a
        # piece's lights and reaching edits as they were (relight.py PieceCache; faster-bake plan, 3.7)
        pieces = ['--piece-cache', self.output / '.work' / 'pieces' / self.variant, '--base', sha256(self.base)]
        if (self.natives or self.native['hides'] or self.covers or self.has_lights or self.any_buildings or self.moves_landings
                or self.stream_tiles or self.flags_edit):
            # the edit made in the map (copies, hides, light edits), lit there; anything left in the patch modelled
            # as an edit
            # (the map is the base map, or the staged one with the pieces of other maps in it: those are lit from
            # nothing where they stand)
            self.run_tool([sys.executable, '-B', '-u', NATIVE_COPY, self.source, self.lit, self.variant, '--copies',
                           self.copies, '--bake', '--cache', self.cache_name, '--receivers-near', '%g' % self.radius]
                          + pieces + (['--edit-spec', self.spec] if self.has_patch else []),
                          self.work / 'logs' / 'native-copy.log')
        else:
            # the relight alone, on a copy of the map whose name table holds the cache's name (named_base)
            self.run_tool([sys.executable, '-B', '-u', RELIGHT, self.named_base(), self.lit, self.variant, '--cache',
                           self.cache_name, '--edit-spec', self.spec, '--receivers-near', '%g' % self.radius]
                          + pieces,
                          self.work / 'logs' / 'relight.log')
        rec = json.loads((self.lit / ('%s.relight.json' % self.variant)).read_text(encoding='utf-8'))
        # a completed calculation that changes no texel (plan 4.4): the map keeps the original's lightmaps, and there
        # is no texture cache to ship
        self.unchanged = bool(rec.get('lightingUnchanged'))
        if self.unchanged:
            self.cache_name = None
        self.relit = dict(written=len(rec['components']), unchanged=len(rec.get('unchanged') or []),
                          skipped=len(rec.get('skipped') or []),
                          shadowMaps=sum(1 for s in rec.get('shadowMaps') or [] if 'skipped' not in s),
                          copies=[(c['source'], c['triangles']) for c in rec.get('copies') or []],
                          nativeCopies=[(c['copy'], c['source']) for c in rec.get('nativeCopies') or []],
                          # pieces of other maps, lit from nothing where they stand (relight.py --foreign-copy)
                          **({'foreignCopies': [c['copy'] for c in rec['foreignCopies']]} if rec.get('foreignCopies') else {}),
                          hidden=len(self.native['hides']), lightingUnchanged=self.unchanged)
        # texels the relight's writes changed in the lightmaps of pieces it was not relighting (relight.py's warning):
        # carried as a record of its own, so the build window says it once the log has scrolled past
        other = other_pieces_changed(rec.get('otherPiecesChanged'))
        if other:
            self.relit['otherPiecesChanged'] = other
        if self.lights:
            self.relit['lights'] = dict(self.lights, **self.light_record())
        self.relit.update(self.building_record())
        self.relit.update(self.flag_record())
        self.stage('light', cache=self.cache_name, baked=True, **self.relit)

    def named_base(self):
        """The map the relight alone reads (an edit only the patch makes): a copy of it in the work folder, written by
        the growing writer (package_grow.py) with the variant cache's name added to its name table, so the relight can
        write that name into the textures it moves there (lightmap_writer.cache_fname). The game install's file is
        never written; the copy reads the texture caches where the map does (tfc-folder.txt)."""
        paths.use('bake')
        import lightmap_writer
        from package import link_caches
        folder = self.work / 'named'
        folder.mkdir(parents=True, exist_ok=True)
        named = folder / Path(self.base).name
        self.name_tool(self.base, named, lightmap_writer.cache_table_name(self.cache_name))
        link_caches(folder, Path(self.base).parent)
        return named

    @staticmethod
    def _name_copy(src, dst, text):
        """`src` written to `dst` by the growing writer with `text` added to its name table (nothing else changes:
        the tables move to the end, test_package_grow)."""
        import package_grow
        g = package_grow.Grower(str(src))
        g.name(text)
        g.write(str(dst))

    def needs_templates(self):
        """Whether the map must have a building and a plain floor volume to clone: a building made from nothing, or a
        new box in one of the map's own buildings."""
        return bool(self.buildings) or any(v is None for e in self.building_edits if not e.get('deleted')
                                           for f in e['floors'] for v in f['volumes'])

    def building_record(self):
        """What the writer's record says of the buildings made from nothing and of the map's own edited in place (the
        fixture manifest's nativeCopies `buildings` and `buildingEdits`): each one's volumes and how many pieces each
        floor lists. {} without any."""
        if not self.any_buildings:
            return {}
        try:
            m = json.loads((self.lit / ('%s.fixture.json' % self.variant)).read_text(encoding='utf-8'))
            made = m['nativeCopies']['buildings']
            edited = m['nativeCopies'].get('buildingEdits') or []
        except (OSError, ValueError, KeyError):
            return {}
        return dict(**({'buildingEdits': [dict(id=e['id'], actor=e['actor'], deleted=e['deleted'],
                                               **({} if e['deleted'] else dict(moved=e['moved'], volumes=e['volumes'],
                                                                               pieces=e['pieces']))) for e in edited]}
                       if edited else {}),
                    buildings=[dict(id=b['id'], name=b['name'], kind=b['kind'], volume=b['copy'],
                                    floors=[dict(volumes=f['volumes'], pieces=len(f['members']),
                                                 cutDown=sum(1 for x in f['members'] if x['cutdown']))
                                            for f in b['floors']], unread=b['unread']) for b in made])

    def flag_record(self):
        """What the writer's record says of the pieces' flags (the fixture manifest's nativeCopies `pieceFlags`): how
        many pieces had flags written in place and on copies, the properties written, the tile regions worked out
        again, and the pieces whose request the writer refused (named in the log too). {} without any."""
        if not (self.flags_edit or any(c.get('flags') for c in self.natives)):
            return {}
        try:
            m = json.loads((self.lit / ('%s.fixture.json' % self.variant)).read_text(encoding='utf-8'))
            f = m['nativeCopies']['pieceFlags']
        except (OSError, ValueError, KeyError):
            return {}
        for name in f.get('refused') or []:
            self.echo('flags not written: %s (the writer found its settings ambiguous; see native-copy.log)' % name)
        tiles = f.get('tiles') or {}
        return dict(pieceFlags=dict(inPlace=len(f.get('inPlace') or []), onCopies=len(f.get('onCopies') or []),
                                    written=f.get('written', 0), refused=f.get('refused') or [],
                                    regions=len(tiles.get('regions') or []), seeded=tiles.get('seeded', 0),
                                    ladders=sum(1 for l in m['nativeCopies'].get('ladders') or [] if l.get('inPlace'))))

    def light_record(self):
        """What the writer's record says of the light edits (the fixture manifest's `lights`): the receivers each
        light was listed in, those in reach without a texture lightmap, and the imports recipe spots made."""
        try:
            m = json.loads((self.lit / ('%s.fixture.json' % self.variant)).read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {}
        lights = m.get('lights') or {}
        return dict(policy=lights.get('policy'), registered=len(lights.get('registered') or {}),
                    unregistered=len(lights.get('unregistered') or []),
                    createdImports=sorted({str(i) for e in lights.get('edits') or [] for i in e.get('created') or []}))

    def edit_unbaked(self, unchanged=False):
        """A quick build's light stage: the edit made in the map as a full build makes it (the copies as new actors
        in their tiles, the hidden pieces taken out, ladders, doors, columns, floors and vans), by the same
        native_copy.py without --bake. Nothing is relit: the copies read their originals' lightmaps and shadow maps
        (EXP-20 run 2), and there is no texture cache. Only the lighting differs from a full build's map.
        `unchanged`: a full build whose edit changes no light (light's first case): the same map, the stage recorded
        as baked with the lighting unchanged, as a full build of cover blocks alone records it."""
        self.cache_name = None
        self.unchanged = unchanged
        if (self.natives or self.native['hides'] or self.covers or self.has_lights or self.any_buildings or self.cleared
                or self.moves_landings or self.stream_tiles or self.flags_edit or self.effects_edit):
            # light edits too: the same actor and component changes as a full build's, receivers' lightmap lists left
            # as they are (editor lights plan, 4.3). The map is the base map, or the staged one with the pieces of
            # other maps in it (transplant)
            self.run_tool([sys.executable, '-B', '-u', NATIVE_COPY, self.source, self.lit, self.variant, '--copies',
                           self.copies], self.work / 'logs' / 'native-copy.log')
            if not (self.lit / ('%s.upk' % self.variant)).is_file():
                raise BuildError('native_copy.py made no %s.upk' % self.variant)
        else:
            # an edit only a patch makes: the variant is the base map under its name
            self.lit.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.base, self.lit / ('%s.upk' % self.variant))
        self.stage('light', cache=None, baked=unchanged, nativeCopies=len(self.natives), hidden=len(self.native['hides']),
                   **({'lightingUnchanged': True} if unchanged else {}),
                   **({'coverBlocks': len(self.covers)} if self.covers else {}), **self.building_record(),
                   **self.flag_record(),
                   **({'lights': dict(self.lights, **self.light_record())} if self.lights else {}))

    def seed(self, cooked_dir):
        lit_map = self.lit / ('%s.upk' % self.variant)
        dst = cooked_dir / ('%s.upk' % self.variant)
        if self.seed_plan:
            shutil.copyfile(self.seed_plan, self.work / 'seed-plan.tsv')
            self.seeded = self.seed_tool(lit_map, dst, self.seed_plan)
            # the seeder's own notes beside the map (<map>.seeded.txt) belong with the build's work, not the package
            for note in cooked_dir.glob(dst.name + '.*'):
                shutil.move(str(note), str(self.work / note.name))
        else:
            shutil.copyfile(lit_map, dst)
            self.seeded = ('no seed plan from the patch: the copies made in the map seeded their own tiles'
                           if self.natives or self.covers else 'no seed plan: the edit puts nothing on new tiles')
        self.stage('seeds', report=self.seeded)

    @staticmethod
    def _picture(src, dst, png):
        """The map `src` written to `dst` with the picture file `png` (512 x 256) as its MapPicture
        (tools/bake/map_frame.py): dict(export, how)."""
        paths.use('bake')
        import map_frame
        return map_frame.write_picture(src, dst, map_frame.encode_file(png))

    def picture(self, cooked_dir):
        """The project's map picture written into the variant map, after the seeds (which want nothing written after
        the world data before them; the picture's writer appends, as the edit's own writer does) and before the
        lightmaps go inside it (lighting_inside, which appends too). The picture is the file the project's document
        names by its SHA-256 (find_picture, looked up as the build starts); one that is missing, or that can't be
        written into the map, is a note, and the map is built without a picture of its own: a picture is no reason to
        lose a finished bake."""
        self.pictured = self.picture_note = None
        if self.doc.get('picture') is None:
            return
        named = pictures.named(self.doc)
        png = self.picture_png if named else None
        if png is None:
            self.picture_note = PICTURE_MISSING % (named[:12] if named else 'its record is malformed')
            self.echo('note: %s' % self.picture_note)
            self.stage('picture', written=False, note=self.picture_note)
            return
        built = cooked_dir / ('%s.upk' % self.variant)
        out = self.work / 'pictured' / built.name
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            report = self.picture_tool(built, out, png) or {}
        except (OSError, ValueError, KeyError, struct.error) as error:
            self.picture_note = PICTURE_FAILED % (built.name, error)
            self.echo('note: %s' % self.picture_note)
            self.stage('picture', written=False, note=self.picture_note)
            return
        os.replace(out, built)
        self.pictured = dict(sha256=named, format=PICTURE_FORMAT)
        self.stage('picture', written=True, export=report.get('export'), how=report.get('how'), **self.pictured)

    def intro_copies(self, cooked_dir, records):
        """The variant's own intros (F-45, F-76), one per intro its base records stream: {stream: copy}."""
        copies = {}
        for stream in intro_streams(records):
            copy = self.intro_copy(cooked_dir, stream)
            if copy:
                copies[stream] = copy
        return copies

    def intro_copy(self, cooked_dir, stream):
        """An intro stream copied with the base map's landing under the variant's name (tools/bake/intro_copy.py):
        the copy's name, or None when the intro has no landing of its own for the base map (then the variant streams
        it unchanged)."""
        src = lwr_file(self.lwr, 'CookedPCConsole', '%s.upk' % stream)
        if not src.is_file():
            raise BuildError('the game install has no %s' % src)
        copy = '%s_%s' % (stream, self.variant)
        moves = self.landing_moves()
        extra = []
        if moves:
            path = self.work / 'landing-moves.json'
            path.write_text(json.dumps(moves, indent=1) + '\n', encoding='utf-8', newline='\n')
            extra = ['--landing-moves', path]
        report = self.work / ('intro-copy-%s.json' % stream)
        # the base map, whose grounded Skyrangers give a place to an entry of the intro that saves none (F-106)
        if Path(self.install_base).is_file():
            extra += ['--map', self.install_base]
        self.run_tool([sys.executable, '-B', '-u', INTRO_COPY, src, cooked_dir / ('%s.upk' % copy), self.map,
                       self.variant, '--report', report] + extra,
                      self.work / 'logs' / ('intro-copy-%s.log' % stream))
        r = json.loads(report.read_text(encoding='utf-8')) if report.is_file() else {}
        if r.get('moved') or r.get('notFound') or r.get('filled'):
            self.stage('intro', stream=stream, moved=r.get('moved') or [],
                       **({'filled': r['filled']} if r.get('filled') else {}),
                       **({'warning': 'no flight place found for landing %s: the intro flies to the old place'
                           % ', '.join(map(str, r['notFound']))} if r.get('notFound') else {}))
        return copy if (cooked_dir / ('%s.upk' % copy)).is_file() else None

    def own_landing_groups(self):
        """[{zone, index, group}] for the zones that are the map's own landings: the spawn group the game knows each
        by (`?SpawnGroup=Group<N>`: its points' tag where it is Group<N>, else Group<index>; F-96)."""
        paths.use('bake')
        import scene_metadata
        from package import Package
        try:
            landings = scene_metadata.landing_metadata(Package(self.install_base))
        except (OSError, ValueError, struct.error):
            landings = []
        out = []
        for k, slot in enumerate(self.landing_zones['own']):
            tag = landings[k].get('group') if k < len(landings) else None
            group = tag if tag and re.fullmatch(r'Group\d+', tag) else 'Group%d' % k
            out.append(dict(zone=self.landing_zones['zones'][slot]['id'], index=k, group=group))
        return out

    def landing_moves(self):
        """The map's own landings the project moves (native_spawns.plan on the base map): [{index, frame}], or []."""
        if not self.moves_landings:
            return []
        if self._landing_moves is None:
            paths.use('bake')
            import native_spawns
            import scene_metadata
            from package import Package
            moves = native_spawns.plan(scene_metadata.landing_metadata(Package(self.install_base)), self.landing_zones)
            self._landing_moves = [dict(index=m['index'], frame=m['frame']) for m in moves]
        return self._landing_moves

    def stream_tile_boxes(self):
        """The moved mission objects that touch the game's tiles (stream_copy.tile_boxes on the install's streams):
        [{stream, actor, old, new}], for native_copy.py to rebuild the base map's tiles at both places."""
        paths.use('bake')
        import stream_copy
        out = []
        for stream, moves in sorted(self.stream_moves.items()):
            src = lwr_file(self.lwr, 'CookedPCConsole', '%s.upk' % stream)
            if not src.is_file():
                raise BuildError('the game install has no %s' % src)
            try:
                out += [dict(stream=stream, **b) for b in stream_copy.tile_boxes(src, moves)]
            except ValueError as error:
                raise BuildError('%s: %s' % (stream, error))
        return out

    def stream_copies(self, cooked_dir):
        """The streamed patches with pieces taken out (the compiler's streamHides: a moved or deleted ladder's
        helpers), and the mission streams whose objects the project moves (streamMoves, Part E: moved in place, the
        map switches naming the variant), each copied under the variant's name (tools/bake/stream_copy.py):
        {stream: copy}."""
        copies = {}
        hides, moves = self.native.get('streamHides') or {}, self.native.get('streamMoves') or {}
        for stream in sorted(set(hides) | set(moves)):
            src = lwr_file(self.lwr, 'CookedPCConsole', '%s.upk' % stream)
            if not src.is_file():
                raise BuildError('the game install has no %s' % src)
            copy = '%s_%s' % (stream, self.variant)
            extra = []
            if moves.get(stream):
                listed = self.work / ('stream-moves-%s.json' % stream)
                listed.write_text(json.dumps([dict(actor=m['actor'], location=m['location'], rotation=m['rotation'])
                                              for m in moves[stream]], indent=1) + '\n', encoding='utf-8', newline='\n')
                extra = ['--moves', listed, '--base', self.map, '--variant', self.variant]
            self.run_tool([sys.executable, '-B', '-u', STREAM_COPY, src, cooked_dir / ('%s.upk' % copy)]
                          + [x for n in hides.get(stream) or [] for x in ('--hide', n)] + extra
                          + ['--report', self.work / ('stream-copy-%s.json' % stream)],
                          self.work / 'logs' / ('stream-copy-%s.log' % stream))
            if not (cooked_dir / ('%s.upk' % copy)).is_file():
                raise BuildError('stream_copy.py made no %s' % copy)
            copies[stream] = copy
        if copies:
            self.stage('streams', copies=copies, hidden=hides, **({'moved': {s: len(v) for s, v in moves.items()}} if moves else {}),
                       **({'tiles': len(self.native.get('streamTiles') or [])} if moves else {}))
        return copies

    def lighting_inside(self, cooked_dir):
        """The relight's lightmaps put inside the variant's map, its last change (tools/bake/inline_lighting.py; EXP-86,
        F-140): every texture that names the build's cache holds all its mips inline, NeverStream, so the package has no
        texture cache to go beside the map, in CookedPCConsole or in a map pack's folder. A map that can't take them in
        ships its cache beside it, as builds did before, and the stage says why. Sets self.inside ({cache, textures,
        mips, bytes}) or None."""
        self.inside = None
        if not self.cache_name:     # a quick build, or the lighting unchanged: no cache
            return
        tfc = self.lit / ('%s.tfc' % self.cache_name)
        if not tfc.is_file():
            return
        target = cooked_dir / ('%s.upk' % self.variant)
        out = self.work / 'inside' / target.name
        try:
            done = inline_map(target, out, self.cache_name, tfc)
        except Exception as error:      # any failure: the map as it is, its cache beside it
            shutil.copyfile(tfc, cooked_dir / tfc.name)
            note = ('its lightmaps could not be put inside the map (%s): they are in %s, which goes in CookedPCConsole '
                    'itself beside the map' % (error, tfc.name))
            self.echo('note: %s' % note)
            self.stage('inside', cache=self.cache_name, note=note)
            return
        os.replace(out, target)
        self.inside = {k: done[k] for k in ('cache', 'textures', 'mips', 'bytes')}
        self.stage('inside', **self.inside)

    def package(self):
        staging = self.work / 'package'
        if staging.exists():
            shutil.rmtree(staging)
        cooked_dir = staging / 'CookedPCConsole'
        cooked_dir.mkdir(parents=True)
        self.seed(cooked_dir)
        self.picture(cooked_dir)
        self.lighting_inside(cooked_dir)
        if self.cooked:
            shutil.copyfile(self.cooked, cooked_dir / ('%s.upk' % self.patch))
        patch = self.patch if self.cooked else None
        # the install's own config: what the editor installed (installs.py) taken out
        cfg = lambda name: (installs.maps_text(self.lwr).replace('\r\n', '\n').split('\n') if name == 'DefaultMaps.ini'  # noqa: E731
                            else config_text(lwr_file(self.lwr, 'Config', name))
                            # Long War's files (DefaultLZMutator.ini, DefaultMiniMods.ini): None where the install has none
                            if lwr_file(self.lwr, 'Config', name).is_file() else None)
        maps = cfg('DefaultMaps.ini')
        records = base_records(maps, self.map)
        intros = self.intro_copies(cooked_dir, records)
        streams = self.stream_copies(cooked_dir)
        replace = dict(intros, **streams)
        files = {'CookedPCConsole/%s' % f.name: sha256(f) for f in sorted(cooked_dir.iterdir())}
        name = re.sub(r'[^\x20-\x7E]|"|\|', '', self.doc.get('name') or '').strip() or 'variant'
        # LWR's display names end in " |<n>", plain EW's don't: a record without an ending follows the install's
        tail = ' |0' if any(re.search(r'\|\d+$', mapsini.field(r, 'DisplayName') or '') for r in records) else ''
        listed = self.missions_listed     # the compiler's: the entries it can write, or None (every record)
        display = dict(tail=tail)       # each record keeps its base record's own words (config_lines)
        lines = config_lines(maps, cfg('DefaultLZMutator.ini'), cfg('DefaultMiniMods.ini'), self.map, self.variant,
                             patch, display, intros=replace, missions_list=listed,
                             zones=(self.native.get('landingZones') or {}).get('zones') if 'landingZones' in self.native else None)
        if self.spawn_rules:
            lines['dropInExclusion'] = drop_in_exclusion(self.lwr, self.variant)
            if lines['dropInExclusion'].get('why'):
                self.echo('spawn rule: nothing to write on this install: %s' % lines['dropInExclusion']['why'])
        if self.landing_zones and self.landing_zones.get('own'):
            # Land here on a plain install (Play in game with one zone): the spawn group each own zone's landing is
            lines['ownLandingGroups'] = self.own_landing_groups()
        # the code that made the package: tools/editor's modules, patchtool, and tools/bake's and tools/upk's
        tools = {str(p.relative_to(TOOLS.parent)).replace('\\', '/'): sha256(p)
                 for p in (*editor_modules(), PATCHTOOL, *tool_modules()) if p.is_file()}
        final = self.output / self.variant
        seconds = round(time.monotonic() - self.started)
        times = dict(last_times(final / 'manifest.json', self.doc.get('id')), **{'quick' if self.quick else 'full': seconds})
        m = dict(schema=SCHEMA, schemaVersion=SCHEMA_VERSION, editorVersion=VERSION, buildId='%s-%s' % (self.variant, self.stamp),
                 builtAt=self.now.isoformat(timespec='seconds'), quick=self.quick,
                 **({'attempt': self.attempt} if self.attempt else {}),
                 project=dict(id=self.doc.get('id'), name=self.doc.get('name'), revision=self.doc.get('revision'),
                              savedAt=self.doc.get('savedAt'), file=str(self.saved_file or self.project_path),
                              sha256=self.project_sha),
                 source=dict(map=self.map, sha256=self.sha, file=str(self.install_base),
                             exporterVersion=self.scene.get('exporterVersion')), variant=self.variant,
                 **({'prefabTest': self.doc['prefabTest']} if 'prefabTest' in self.doc else {}),
                 **({'leftOut': self.left_out} if self.left_out else {}),
                 **({'shell': self.shelled} if self.shelled else {}),
                 # cache: the texture cache the package ships (none once its lightmaps are inside the map)
                 patch=patch, cache=None if self.inside else self.cache_name,
                 **({'lightingInside': self.inside} if self.inside else {}),
                 files=files, streams=[patch] if patch else [], config=lines,
                 intros=[dict(stream=s, copy=c) for s, c in intros.items()], replaceStreams=replace,
                 streamCopies=[dict(stream=s, copy=c, hidden=(self.native.get('streamHides') or {}).get(s) or [],
                                    **({'moved': [m['actor'] for m in self.stream_moves[s]]} if self.stream_moves.get(s) else {}))
                               for s, c in streams.items()],
                 families=list(self.enable),
                 nativeCopies=len(self.natives), nativeHides=len(self.native['hides']), coverBlocks=len(self.covers),
                 **({'pieceFlags': len(self.piece_flags)} if self.piece_flags else {}),
                 **({'spawnEdits': dict(moved=self.spawn_edits['moves'], valued=self.spawn_edits['values'],
                                        added=self.spawn_edits['copies'], deleted=self.spawn_edits['deletes'])}
                    if any(self.spawn_edits.values()) else {}),
                 buildings=len(self.buildings), buildingEdits=len(self.building_edits),
                 donors=self.donors, foreignPieces=sum(d['pieces'] for d in self.donors),
                 foreignEffects=sum(d.get('effects', 0) for d in self.donors),
                 lights=self.lights,
                 lightingUnchanged=self.unchanged,
                 # the map's own picture (its file's SHA-256, as the project names it); absent: the map has none
                 **({'picture': self.pictured} if self.pictured else {}),
                 **({'pictureNote': self.picture_note} if self.picture_note else {}),
                 stages=self.stages, seconds=seconds, times=times, work=str(self.work), tools=tools)
        (staging / 'manifest.json').write_text(json.dumps(m, indent=1) + '\n', encoding='utf-8', newline='\n')
        (staging / 'README.txt').write_bytes(readme(m).encode('latin-1', 'replace'))
        with publish_lock(self.output, self.variant):
            # checked again as the package goes in: the folder is this project's, and no name it holds is taken now
            existing = owned_folder(self.output, self.variant, self.doc.get('id'))
            self.check_names(outputnames.build_names(m, self.variant))
            # the swap keeps a journal, so a build killed between its renames leaves the last package or this one
            # after reconciliation (publication.py)
            try:
                warnings = publication.publish(self.output, self.variant, staging, existing,
                                               dict(buildId=m['buildId'], attempt=self.attempt, project=self.doc.get('id')),
                                               boundary=self.boundary)
            except publication.PublishError as error:
                raise BuildError(str(error))
        for warning in warnings:
            self.echo('warning: %s' % warning)
        # an earlier build's zip of the folder (builds made one until 10 November 2026): out of date now
        stale = self.output / ('%s.zip' % self.variant)
        if stale.is_file():
            stale.unlink()
        self.manifest, self.folder = m, final
        return m

    def prune_work(self):
        """Old work out of the builds folder after every build, built or failed (builds.prune_work; faster-bake plan
        6.1, review finding 49): of every variant the KEEP_WORK newest work folders stay whole (a bug report reads the
        newest) and older ones keep their logs and small records; kept pieces unused for PIECE_DAYS are deleted. This
        build's own work folder and kept pieces are left. Variants no project ships as are left to the server's prune
        as it starts (BuildRunner.prune), which knows the projects of its builds folder."""
        variant = self.variant
        spare = [self.work, self.output / '.work' / 'pieces' / variant if variant else None]
        try:
            result = build_runs.prune_work(self.output, spare=spare)
        except Exception as error:      # never the build's own outcome
            self.echo('old build work was not pruned (%s)' % error)
            return
        if result['freed']:
            self.echo('old build work pruned: %.0f MB freed (%d work folders, %d sets of kept pieces)'
                      % (result['freed'] / 2 ** 20, result['folders'], result['pieces']))

    def run(self):
        try:
            self.snapshot()
            self.compile()
            self.preflight()
            self.patch_and_cook()
            self.shell()
            while True:
                try:
                    self.transplant()
                    self.light()
                    break
                except BuildError as error:
                    # a copy the Build has not been tried on (the compiler's `untried`) may be one it can't make: those
                    # the failure names are left out, named, and the rest is built (each try drops at least one)
                    if not self.drop_untried(error):
                        raise
            m = self.package()
        finally:
            if self.unpacked_work:
                shutil.rmtree(self.unpacked_work, ignore_errors=True)
            self.prune_work()
        self.echo('built %s: %s (%s)' % (m['buildId'], self.folder, ', '.join('%s %s' % (Path(f).name, h[:12]) for f, h in m['files'].items())))
        return m


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('project', help='a project file (.json), or a project\'s id or name in the settings\' projects folder')
    a.add_argument('--cache', type=Path, help='the viewer cache (default: the settings\' cache)')
    a.add_argument('--output', type=Path, help='the builds folder (default: the settings\' output folder)')
    a.add_argument('--game', '--lwr', dest='lwr', type=Path,
                   help='the game install (LWR or plain EW), read only (default: the settings\' game)')
    a.add_argument('--udk', type=Path, help='UDK 2011-09, only for an edit that needs a patch (default: the settings\' udk)')
    a.add_argument('--radius', type=float, default=RADIUS,
                   help='relight receivers within this many units of the edit (default %(default)g)')
    a.add_argument('--family', action='append', default=[], choices=sorted(f for f in compiler.FAMILIES if not compiler.FAMILIES[f]['builds']),
                   help='build this family although the compiler doesn\'t for every project: an experiment\'s build '
                        '(repeatable; the choices are the families still switched off)')
    a.add_argument('--foreign-family', action='append', default=[], choices=sorted(compiler.FAMILIES) + ['check'],
                   help='build this family\'s pieces from other maps although that isn\'t switched on yet: an '
                        'experiment\'s build (repeatable)')
    a.add_argument('--quick', action='store_true',
                   help='make the edit in the map without baking its lighting: seconds instead of minutes, to check '
                        'pathing and cover in the game; the lighting is not right')
    # the server's launches (tools/viewer/builds.py, buildqueue.py)
    a.add_argument('--attempt', help='the server\'s id for this launch (a UUID): carried into the manifest and the '
                                     'build\'s id')
    a.add_argument('--projects', type=Path, help='the projects folder whose names the build\'s are checked against '
                                                  '(default: the project file\'s folder)')
    a.add_argument('--check-game', action='append', default=[], type=Path,
                   help='another game install whose names the build\'s are checked against (repeatable; default: the '
                        'install Play in game uses, from the settings)')
    a.add_argument('--saved-file', type=Path, help='the project\'s own file, written in the manifest, when the build '
                                                    'reads a snapshot of it (its map picture is then the one captured '
                                                    'beside the snapshot)')
    a.add_argument('--pinned', action='store_true',
                   help='take nothing from the settings: every folder comes from the arguments (no --udk: no UDK)')
    a.add_argument('--work', type=Path, help='the build\'s work folder (default: <output>/.work/<Variant>-<stamp>; a '
                                              'prefab test\'s, w beside its project file)')
    args = a.parse_args(argv)
    if args.attempt and not PROJECT_ID.fullmatch(args.attempt):
        a.error('--attempt takes a UUID')
    if args.pinned:
        if not (args.lwr and args.cache and args.output and Path(args.project).suffix.lower() == '.json'):
            a.error('--pinned needs the project file, --game, --cache and --output')
        s = dict(projects=None, cache=None, output=None, udk=None)
        lwr, udk = args.lwr, args.udk
    else:
        s = settings_module.load_settings()
        lwr = args.lwr or (settings_module.resolve_game(s['game'])[0] if s['game'] else None)
        udk = args.udk or s['udk']
    if not lwr:
        a.error('set the game install (viewer.py settings, or --lwr)')
    try:
        project = find_project(args.project, args.projects or s['projects'])
        # the install Play in game uses, where it is another: the build's names are checked against it too
        if args.check_game or args.pinned:
            games = list(args.check_game)
        else:
            try:
                play = settings_module.install_game(s)[0]
            except (OSError, ValueError):
                play = None
            games = [play] if play else []
        Build(BuildInputs(project, args.cache or s['cache'], args.output or s['output'], lwr, udk, radius=args.radius,
                          enable=args.family, quick=args.quick, foreign=args.foreign_family, games=games,
                          projects=args.projects, attempt=args.attempt, saved_file=args.saved_file,
                          work=args.work)).run()
    except BuildError as error:
        if error.code:
            print('build failed code: %s' % error.code)
        print('build failed: %s' % error)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())

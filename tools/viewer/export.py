"""Export an original EW map into an external, disposable viewer cache."""
import hashlib
import json
from pathlib import Path
import sys
if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.append(str(Path(__file__).resolve().parents[1]))     # tools/paths.py (review finding 54)
import paths  # noqa: E402
import re
import shutil
import struct
import tempfile
import zlib
from package import Package, FormatError
from mesh import read_mesh, write_glb
import material_programs
import atmosphere as atmosphere_records
import baked_light
import decals as decal_export
import light_functions
from skeletal import read_skeletal
from texture import export_texture
from materials import coordinates, profile, static_switches, constant_color, approximate_colour, opacity_input, BY_KIND
from PIL import Image
from export_math import multiply, transform, view_matrix
import background_sound
from scene_metadata import (building_metadata, cursor_volumes, effect_metadata, landing_metadata, destruction, fragment_breaks, kismet_references, prefab_members, tile_grid,
                            tactical_metadata, spawn_metadata, donor_objects, BOMB_DONOR, trigger_counts)
from resolver import resolve_scene
from composition import compose_scene,content_records
from lights import light_metadata, light_records
import collision
import effects_draw
import effects_metadata
import piece_flags
import settings

# 13: the map's missions and the packages they stream (`missions`, `streams`); textures from compiled shaders
# 14: no diagnostic pink: more diffuse rules (parameter names, compiled shaders' colour textures, colours by kind,
#     else neutral grey), streamed packages' stub materials from the map, fractured interiors hidden
# 17: what the game's damage does to each piece (`destruction`: its toughness and health; scene_metadata.destruction)
# 18: what the editor needs to edit lights (private/plans/done/editor-lights-plan.md 4.1, 9.3): each light's GUIDs, the pieces
#     its bake lists it in (`bakedInto`, `shadowMapped`), `channels`, `saved`, `referencedBy`; area lights' glowing
#     pieces (`emitterAttachment`, objects' `areaLights`) and the scene's `lightMetadata`
# 19: a masked material's cut-out follows its OpacityMask input (T-29)
# 20: the map's cursor volumes (`cursorVolumes`: the cursor's floors; prefab plan B1.2)
# 21: what the editor needs to edit the map's own buildings (private/plans/done/map-buildings-editable-plan.md, E0b):
#     each building's actor, level, isUfo, referencedBy, van, and its floor volumes' plain
# 22: the map's own landings (`landings`: each landing prefab's ten actors, its group and the grounded Skyranger's
#     prefab; private/plans/done/clear-map-plan.md, section 4)
# 23: the level's effects (`effects`: its Emitter actors, each with its particle system and the piece that carries it;
#     scene_metadata.effect_metadata), and a landing with no drop zone frame matched to its Skyranger from where its
#     fitted zone's frame would stand (spawns.fit_zone)
# 24: each mission stream's objects (`streams[<name>].missionObjects`: drop-in points, pods, points, landings, capture
#     points, radar arrays, the bomb and power nodes with their parts, waves, triggers, each with what lists it and the
#     group it moves with; scene_metadata.mission_objects, private/plans/done/mission-types-plan.md C1)
# 25: the tile grid of a map whose level volume falls a unit or so short of its whole tiles (2 units of slack, which
#     export 26 replaced; CSmallScout_Roadhouse had none, so its vans could not be moved)
# 26: every map's tile grid from the game's own record (scene_metadata.game_grid; private/plans/done/game-grid-plan.md):
#     the world data's tile counts, and `tileGrid.tiles`, the corner the game counts its tiles from (WorldBounds' low
#     corner, a unit under `origin`, the level volume's, which placing keeps); CBattleship_01, DLC2_2_Deluge and
#     DLC2_3_Furies get a grid; `source` world-data, or level-volume where a map saves no record
# 27: each piece's flags (piece flags plan, P2; piece_flags.describe): `pieceFlags` on every component of an actor of a
#     class the flags apply to (its family, its settings with where each came from, its roles, whether it collides and
#     whether its static meshes have simple collision), and each mesh's `collision` (its BodySetup, whether line and
#     box checks use its simple collision; a skeletal mesh's kind)
# 28: the map's effects, sounds and lens flares for the Effects view (effects and sounds plan, Part A, stage FX1;
#     effects_metadata.describe): `effects` gains its identity, starting state, saved particle parameters, floors,
#     script users, attachment and what the editor may do with it; `sounds` and `flares` are new; `effectSystems`
#     and `soundWaves` describe each particle system and wave once; a mission stream's own are in its layer
# 29: what the page draws an effect's likeness from (effects and sounds plan, Part J1, stage FXV1; effects_draw.py):
#     each emitter of `effectSystems` gains `draw` (sprites or meshes, its textures and blend, its spawn rate, bursts
#     and followed modules' tables or particle parameters) or `draw: null` with `why`; the particle textures and
#     meshes are written with the map's others
# 30: an effect placed by a prefab instance at whose own place one mesh piece stands is carried by that piece
#     (`carriedBy`, `carriedHow: prefab`; scene_metadata.effect_metadata): the fog pod's smoke follows its pod (F-50)
# 31: draw version 4 (effects_draw.texture_traits): each particle texture's traits from its pixels, and an emitter's
#     colour and shape taken from different textures (`maskFrom`, `opacity: none`): the fires drawn as flames; the
#     material's own colour parameters (`colours`): the night smoke drawn dark, not pink
# 32: draw version 5: an added particle's grey texture is its picture, and a picture whose alpha holds its shape
#     takes only a named mask (the police lights round again, not squares); an emitter that only sends events says so
# 33: the map's spawn points and who uses them (editor spawns implementation plan, SP1; scene_metadata.spawn_metadata):
#     `spawns` (pods, Meld points, drop-in and other points, starts, path nodes, no-spawn volumes, each with its values
#     and where each comes from, its links and uses); an LWR patch's `spawns`; a mission object's values, links, uses
#     and listed, and the bomb's PointInSpace helper in its group (F-124); `donors` (the bomb donor's objects)
# 34: a no-spawn volume's values (`aliens`, `civilians`: AlienNoSpawnZone, CivilianNoSpawnZone), for the Spawns view's
#     volume edits
# 35: a landing's Skyranger lists its dust (the ARC_Skyranger_Ground_Periphery emitter beside its prefab, role `dust`),
#     so the view carries it with a moved zone as the Build does
# 36: a fracturing piece whose component keeps its fragments (bPreventChunkRemoval: most roofs and floors) says so
#     (`keepsPieces`), so the editor offers Breaks further in battle on it and on copies made from it (F-139)
# 37: what nothing read is no longer written (review finding 63): the map's own `content` (every level actor and
#     Kismet record; a streamed or previewed layer still reads its own), `effectsMetadata`, a material's
#     `render.compiledTextures` and scenes.json; a streamed package's buildings, tile grid and tactical data are no
#     longer worked out only to be dropped. Each mission says its kind (`missions[].kind`, missions.kind_key: a
#     council mission's `Special/<council type>`), which the page and the server took from its label before.
# 38: the map's diagonal cover tiles (`tactical.diagonalCover`: each tile its seeds marked, its floor's height, its
#     cover location and the diagonals it gives cover toward; scene_metadata.saved_diagonal_tiles), for View options'
#     Diagonal cover (findings register F-149)
# 39: the map's background sound (`backgroundSound`: the sound its script starts when the level loads, for the player;
#     background_sound.py) and its triggers counted (`triggerCounts`: the trigger volumes, water volumes and sight
#     points a clear takes out unless kept; scene_metadata.trigger_counts, F-159)
# 40: each diagonal cover tile's directions name their `wall` (scene_metadata.diagonal_walls, tools/bake/mark_walls.py:
#     the piece the game's cover rule meets along that diagonal), so a mark follows its piece in the editor (diagonal
#     cover by hand, stage M5)
# 41: each streamed package's rebuild volumes as the battle reads them (`streams[<name>].rebuildSpheres`: centre and
#     sphere radius, scene_metadata.rebuild_spheres, F-150), so the Diagonal cover view and the Build warn of a mark
#     whose tile a patch level reworks at the battle's start (KNOWN-BUGS.md KB-22)
# 42: the bomb donor's too (`donors[<kind>].rebuildSpheres`), which an added bomb mission streams; the view and the
#     Build move a mission object's volume with the project's move of it
# 43: materials as their compiled shaders draw them (game-likeness plan, A-S3): a material's `program` (its slice of the
#     game's shaders, research/editor-contracts.md section 9, material_programs.py) with every texture it samples
#     exported; a placed piece's own painted vertex colours (`paint`: paint-<object>.bin, RGBA bytes a vertex); block-
#     compressed textures as DDS files with their mips (texture.py `container`, A-S3b); the map's atmosphere
#     (`atmosphere`: fog, grade, bloom and fog-of-war colours over the classes' defaults, its post-process volumes:
#     atmosphere.py, C1)
# 44: each lightmapped piece's baked light as the game stores it (game-likeness plan, B1: baked_light.py): its
#     `lightmap` (the colour and direction atlases, as DDS files, their scales, the UV scale and bias and channel) and
#     its `sunShadow` (its shadow map of the dominant light: atlas, UV scale and bias), the map's and its streamed
#     levels' own pieces only (a piece of another map is lit live where it is put)
# 45: `sunIrrelevant` in place of `sunShadow` on a lightmapped piece whose IrrelevantLights hold the dominant light
#     (wholly in its shadow: the game draws none of the sun on it; B3, F-184)
# 46: a light's `lightFunction` (game-likeness plan, F1: light_functions.py): the program of the material the game
#     draws on the light (its light function shader sliced, output `light`: the factor it multiplies the light by,
#     which may move with time), its material and whether it moves; only where the export makes programs
# 47: the map's placed decals (game-likeness plan, D1; decals.py, decal_records.py; F-210, F-211): `decals`, each with
#     its actor, place, rotation, frame, size, material and the piece it lies on, and a mesh (decal-<actor>.glb) of
#     the triangles the game stored for it, grouped by the piece each part lies on; a stream's in its layer
# The library's pieces are not kept by this version (since 24 November 2026: library.piece_folder): a change here to
# what a piece of another map carries (its meshes, materials or textures as written, or a field of its record) raises
# library.PIECE_VERSION as well, and tests/test_piece_version.py's fingerprints are written again.
EXPORT_VERSION = 47
LIGHT_METADATA_VERSION = 1
# What reading one piece, texture, record or streamed package of a damaged or modded package can raise, caught alike by
# every per-piece guard of the export so one unreadable actor never ends the whole map's (review finding 50): the
# readers' FormatError and other ValueErrors (lzo1x's block cut short among them), a struct cut short, an index or key
# a damaged table names, a zlib stream that won't decode, a texture format the image library lacks, a file error.
UNREADABLE = (ValueError, OSError, struct.error, IndexError, KeyError, zlib.error, NotImplementedError)


def sha256(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


collides = piece_flags.collides        # one rule with the flags and the Build (review finding 55)


def compiled_textures(p, material):
    """The textures a cooked Material's compiled shaders sample: its first material resource's
    UniformExpressionTextures, after CompileErrors, TextureDependencyLengthMap, MaxTextureDependencyLength, Id and
    NumUserTexCoords. EW's cooked materials keep this list even where their expressions are stripped (StreetSet's
    Asphalt_Patch: no texture parameter, only Asphalt_Patch_DIFF and _MASK here). [] where it doesn't parse."""
    try:
        reader = p.native(material)     # bounded by the material's export: nothing is read from the next one
        at, stop = reader.pos, reader.end

        def word(o):
            reader.pos = o
            return reader.i32()
        for _ in range(word(at) if 0 <= word(at) < 64 else 0):      # CompileErrors: FStrings
            at += 4
            n = word(at)
            at += 4 + (n if n >= 0 else -2 * n)
        at += 4
        pairs = word(at)                                           # TMap<expression, int>
        if not 0 <= pairs < 4096: return []
        at += 4 + 8 * pairs + 4 + 16 + 4
        count = word(at)
        if not 0 <= count <= 64 or at + 4 + 4 * count > stop: return []
        refs = [word(at + 4 + 4 * k) for k in range(count)]
        return [r for r in refs if r and 'Texture' in p.cls(r)]
    except (FormatError, struct.error, IndexError, KeyError, ValueError):
        return []


DIFFUSE_NAME = re.compile(r'_(DIFF|DIF|DIFFUSE|D|COL|COLOR|COLOUR|ALB|ALBEDO|BASE)$', re.I)
MASK_NAME = re.compile(r'_(MASK|MSK|M)$', re.I)
# Words in a texture's or parameter's name that say it holds no surface colour: normals, specular, masks, FX
# (scrolling smoke and fire, noise, gradients) and Firaxis's placeholders (DiffuseDev, NormalDev...)
NOT_COLOUR = frozenset('NML NRM NORM NOR NORMAL NORMALS SPC SPEC SPECULAR REF REFL REFLECTION MASK MSK NOISE GRADIENT GRAD '
                       'SMOKE FIRE SCROLLING RAGGED EDGE DEV WIPE VOMIT FROTH EMS EMISSIVE OPA OPC OPACITY ALPHA LIGHTS '
                       'HOLE DISTORTION CLOUD EMBERS BLURRED HEIGHT AO CUBE CUBEMAP FRESNEL GLOW DISSOLVE'.split())
# The neutral grey drawn where nothing says what colour a surface is (linear: sRGB 128)
NEUTRAL = [(128/255)**2.2]*3
STUB_PROPERTIES = {'ReferencedTextureGuids', 'LightingGuid'}


def name_words(name):
    """A name's words, upper case: T_Smoke_Cloud_Scrolling_NML -> T SMOKE CLOUD SCROLLING NML, NoiseHighFreq -> NOISE
    HIGH FREQ."""
    return {w.upper() for w in re.findall(r'[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+', name)}


def colour_like(name):
    """Whether a texture or parameter name could hold a surface colour (no NOT_COLOUR word in it)."""
    return not name_words(name) & NOT_COLOUR


def placeholder(full):
    """Firaxis's default textures in the parent materials (GEN_MaterialParents.Textures.DiffuseDev, GrayDev...),
    which a material instance that doesn't set the parameter keeps."""
    return full.startswith('GEN_MaterialParents.Textures.') and 'DEV' in name_words(full.rsplit('.', 1)[-1])


def diffuse_parameter(names):
    """The diffuse among texture parameters the profile doesn't know ({parameter: texture path}), or None:
    1. the one whose texture is named _DIFF (Firaxis's own "Diffsue_Map" on PROP_Objects_Old);
    2. one named Diffuse..., Dif... ("Diffuse_Map" on Burning_Tree, "Diffuse Map A | CMod Mask" on the obsolete
       Building_Tiling_Material, "Diffuse_GlassMask" on the window parallax), not a mask or a layered material's
       Diffuse_Mod, nor a placeholder;
    3. the only parameter whose name and texture both read as colour ("StaticScreenTexture" on HQ_ConsoleScreen,
       "Rope_Tex", "Car_Tex")."""
    usable = {k: v for k, v in names.items() if k != 'Diffuse_Mod' and not placeholder(v)}
    named = [k for k, v in usable.items() if DIFFUSE_NAME.search(v.rsplit('.', 1)[-1])]
    if named: return next((k for k in named if k.lower().startswith('diff')), named[0])
    called = [k for k in usable if re.match(r'(?i)dif', k) and not re.fullmatch(r'(?i)diffuse[ _]?mask', k)]
    if called: return called[0]
    loose = [k for k, v in usable.items() if colour_like(k) and colour_like(v.rsplit('.', 1)[-1])]
    return loose[0] if len(loose) == 1 else None


def compiled_colour(names):
    """The colour among the textures a material's compiled shaders sample ({ref: short name}): one named _DIFF,
    else the first whose name reads as colour (pineBranchSplit beside the fire and smoke on burning trees). A name
    can mislead: materials.BY_KIND takes the roots where it does, before this."""
    return (next((r for r, n in names.items() if DIFFUSE_NAME.search(n)), None)
            or next((r for r, n in names.items() if colour_like(n)), None))


def area_lights(p, objects, lights, meshes, materials, warn):
    """Each area light's glowing piece (area_light_bindings.associate, editor lights plan 4.8): `emitterAttachment` on
    the area lights, `areaLights` on every object (the area lights it may have emitted). Returns the matcher's version,
    or None where the matcher isn't there (the export then can't build edits: compiler.light_metadata_problem)."""
    for obj in objects: obj['areaLights'] = []
    try:
        import area_light_bindings
    except ImportError as error:
        # said in the export's diagnostics, which the compiler's refusal quotes (review finding 31)
        warn('area lights', f'The area-light matcher (area_light_bindings) could not be loaded: {error}')
        return None
    found = area_light_bindings.associate(p, objects, lights, meshes, materials, warn)
    for light in lights:
        if light['id'] in found['attachments']: light['emitterAttachment'] = found['attachments'][light['id']]
    for obj in objects: obj['areaLights'] = sorted(found['owners'].get(obj['id'], []))
    return found['version']


class Exporter:
    def __init__(self, package, folder,namespace='',progress=None,base=None,digest=None,programs=None,lightmaps=None):
        """progress(done, total): called as the pieces are read (the export's slow part). base: the map's own
        Exporter, for a package streamed into it (its stub and imported materials are the map's). lightmaps: whether
        each piece's baked light is written (export 44: the map's export and its streams; never a piece of another
        map's, which is lit where it is put); a stream follows its map."""
        self.p, self.folder = package, folder
        self.base = base
        self.lightmaps = lightmaps if lightmaps is not None else bool(getattr(base, 'lightmaps', False))
        self._dominant = ...        # the dominant light's LightGuid (baked_light.dominant_guid), read once
        # the materials' programs are made only where the exporter is told to (material_programs.Programs): the
        # bake's albedo resolves materials through a subclass of this and must not open the shader cache; a stream
        # or a patch layer follows its map
        self.programs = programs if programs is not None else getattr(base, 'programs', None)
        self.digest = digest        # the package's SHA-256 when the caller has it (export_map: worked out once)
        self.prefix=namespace+'-' if namespace else ''
        self.prefabs = {}
        self.kismet = {}
        self.breaks = {}
        self.meshes, self.materials, self.textures = {}, {}, {}
        # block-compressed textures as DDS files with their mips, as the game stores them (texture.export_texture)
        self.texture_container = 'auto'
        self.diagnostics = []
        self.progress = progress
        self.flags = {}     # actor -> its piece flags (piece_flags.describe), worked out once for its components
        self.landings = []          # the map's own landings (export 22): effects() reads them, run() writes them
        self.area_matcher = None    # what matches area lights to their glowing pieces: run() works it out and writes it

    def piece_flags(self, actor):
        """The actor's flags as the export carries them, or None (a class they don't apply to, a streamed or inherited
        package's piece: the editor doesn't edit those). A piece of another map's (the library's `lib-` export) carries
        them: an added piece, a made wall's or ground's donor, takes them from its record."""
        if self.prefix.startswith(('stream-', 'inherited-')):
            return None
        if actor not in self.flags:
            try:
                self.flags[actor] = piece_flags.describe(self.p, actor)
            except UNREADABLE as error:
                self.warn(self.p.name(actor), f'Piece flags not read: {error}')
                self.flags[actor] = None
        return self.flags[actor]

    def effects(self):
        """The package's effects, sounds and flares (export 28; effects_metadata.describe): the map's own, each effect
        with the piece that carries it (export 23's rule), and a mission stream's, read only; none for the patch a
        preview builds on. Sets self.landings (export 22), which they are matched against."""
        p = self.p
        self.landings = [] if self.prefix else self.guarded('landings', lambda: landing_metadata(p, self.warn), [])
        stream = self.prefix[len('stream-'):-1] if self.prefix.startswith('stream-') else None
        nothing = dict(effects=[], sounds=[], flares=[], systems={}, waves={})
        if self.prefix and stream is None:
            return nothing
        carried = {} if stream else self.guarded('effect carriers', lambda: {
            e['actor']: dict(by=e['carriedBy'], how=e['carriedHow']) for e in effect_metadata(p) if e['carriedBy']}, {})
        defaults = self.guarded('script defaults', lambda: effects_metadata.Defaults(p), None)
        if defaults is None:
            return nothing
        found = self.guarded('effects', lambda: effects_metadata.describe(
            p, kismet=self.kismet, prefabs=self.prefabs, landings=self.landings, carried=carried, prefix=self.prefix,
            layer='stream' if stream else 'base', stream=stream, defaults=defaults, warn=self.warn), None)
        if found is None:
            return nothing
        # export 29: what the page draws each system's likeness from (effects_draw.py; plan Part J1)
        self.guarded('effect drawings', lambda: effects_draw.attach(p, defaults, found['systems'], self, compiled_textures,
                                                                    effects_draw.RULES, self.warn), None)
        return found

    def particle_mesh(self, mi, override=0):
        """A mesh particle's mesh as the export keeps a piece's: (mesh key, a material key for each drawn section, each
        section's own material export), or (None, [], []) where it doesn't read. `override`: the emitter's own material, drawn on every section."""
        p = self.p
        mesh_key = self.prefix + str(mi)
        if mesh_key not in self.meshes:
            try:
                mesh = read_mesh(p, mi)
                write_glb(mesh, self.folder / f"mesh-{mesh_key}.glb")
            except UNREADABLE as error:
                self.warn(p.name(mi), f'Particle mesh not read: {error}')
                return None, [], []
            self.meshes[mesh_key] = dict(name=p.name(mi), url=f"mesh-{mesh_key}.glb",
                vertices=len(mesh["positions"])//3, triangles=len(mesh["indices"])//3,
                sections=mesh["sections"], bounds=mesh["bounds"], fragmentMask=None, kind='static', bones=[],
                pose=None, origin=mesh.get('origin'), rotOrigin=mesh.get('rotOrigin'),
                collision=self.mesh_collision(mi))
        drawn = [s for s in self.meshes[mesh_key]["sections"] if s["count"]]
        mats = [self.section_material(override if override > 0 else s["material"], mi) for s in drawn]
        return mesh_key, mats, [s["material"] for s in drawn]

    def mesh_collision(self, mesh):
        """What the game's traces meet of a mesh: dict(bodySetup, simpleLine, simpleBox) for a static one (bodySetup
        False: its simple collision is empty, so a check that uses it passes through), dict(kind='skeletal')."""
        p = self.p
        if p.cls(mesh) == 'SkeletalMesh':
            return dict(kind='skeletal')
        try:
            has = bool(collision.body_setup(p, mesh))
        except (FormatError, ValueError, IndexError, struct.error):
            has = None
        return dict(bodySetup=has, simpleLine=p.own(mesh, 'UseSimpleLineCollision', True) is not False,
                    simpleBox=p.own(mesh, 'UseSimpleBoxCollision', True) is not False)

    def warn(self, source, message):
        self.diagnostics.append(dict(source=source, message=str(message)))

    def guarded(self, what, read, fallback):
        """read(), or `fallback` with a diagnostic when the package's records for `what` can't be read: one unreadable
        record never ends the whole map's export (review finding 50)."""
        try:
            return read()
        except UNREADABLE as error:
            self.warn(what, f'{what[:1].upper() + what[1:]} not read: {error}')
            return fallback

    def texture(self, index):
        if index <= 0: return None
        key = self.prefix+str(index)
        if key not in self.textures:
            self.textures[key] = None
            try:
                info = export_texture(self.p, index, self.folder / f"texture-{key}.png", self.texture_container)
                info["url"] = info.pop("output")
                self.textures[key] = info
            except UNREADABLE as error:
                self.warn(self.p.name(index), error)
        return key if self.textures[key] else None

    def baked(self, component, mesh):
        """The piece's `lightmap` and `sunShadow` (export 44), their atlases exported once as stored, or
        `sunIrrelevant` in place of `sunShadow` where the dominant light is on its IrrelevantLights (export 45, F-184);
        {} where it has none of them or they can't be read (a warning)."""
        p, out = self.p, {}
        try:
            lm = baked_light.lightmap(p, component, mesh)
            if lm:
                colour, directions = self.texture(lm['colour']), self.texture(lm['directions'])
                if colour and directions:
                    out['lightmap'] = dict(lm, colour=colour, directions=directions)
            if self._dominant is ...:
                self._dominant = baked_light.dominant_guid(p) if not self.base else self.base.dominant_light()
            if baked_light.sun_irrelevant(p, component, self._dominant):
                out['sunIrrelevant'] = True
            elif (sm := baked_light.sun_shadow(p, component, self._dominant)) and (atlas := self.texture(sm['texture'])):
                out['sunShadow'] = dict(sm, texture=atlas)
        except baked_light.UNREADABLE as error:
            self.warn(p.name(component), f'its baked light was not read: {error}')
        return out

    def dominant_light(self):
        """The map's dominant light's LightGuid (hex), read once: a streamed level's pieces keep shadow maps of it."""
        if self._dominant is ...:
            self._dominant = baked_light.dominant_guid(self.p)
        return self._dominant

    def material(self, index):
        key = self.prefix+str(index)
        if key in self.materials: return key
        p = self.p
        chain, seen = [], set()
        current = index
        while current > 0:
            if current in seen: raise FormatError("Material parent cycle")
            seen.add(current); chain.append(current)
            current = p.own(current, "Parent", 0)
        textures, scalars, vectors, sampling, switches = {}, {}, {}, {}, {}
        blend, two_sided = "BLEND_Opaque", False
        for mat in reversed(chain):
            for c in p.children.get(mat, []):
                parameter, tex = p.own(c, "ParameterName"), p.own(c, "Texture", 0)
                if parameter and tex:
                    textures[parameter] = tex
                    sampling[parameter] = coordinates(p,c)
                if parameter and p.cls(c) == "MaterialExpressionScalarParameter":
                    scalars[parameter] = p.own(c,"DefaultValue",0.0)
                if parameter and p.cls(c) == "MaterialExpressionVectorParameter":
                    vectors[parameter] = p.own(c,"DefaultValue",[0,0,0,0])
                if parameter and p.cls(c) == 'MaterialExpressionStaticSwitchParameter':
                    switches[parameter] = p.own(c, 'DefaultValue', False)
            for field, target in [("TextureParameterValues", textures), ("ScalarParameterValues", scalars),
                                  ("VectorParameterValues", vectors)]:
                for row in p.structs(p.own(mat, field)):
                    name = row.get(("ParameterName", 0), {}).get("value")
                    fallback = [0,0,0,0] if field == "VectorParameterValues" else 0
                    value = row.get(("ParameterValue", 0), {}).get("value", fallback)
                    if name is not None: target[name] = value
            blend = p.own(mat, "BlendMode", blend)
            two_sided = p.own(mat, "TwoSided", two_sided)
            try: switches.update(static_switches(p, mat))
            except (ValueError, struct.error) as error:
                self.warn(p.name(mat), f'Static switch overrides unavailable: {error}')
        def binding(names):
            for name in names:
                if name in textures: return self.texture(textures[name])
            return None
        render_profile = profile([p.name(i) for i in chain],blend,textures,scalars,sampling,switches)
        if not render_profile['diffuseParameter']:
            # A diffuse under another parameter name (diffuse_parameter has the rules)
            pick = diffuse_parameter({k: p.name(v) for k, v in textures.items() if isinstance(v, int) and v > 0})
            if pick:
                render_profile.update(diffuseParameter=pick,
                                      uv=dict(sampling.get(pick, {"channel": 0, "scale": [1, 1]})))
                if '|' in pick and blend == 'BLEND_Masked':
                    # "Diffuse Map A | CMod Mask": the alpha is where CMod Color tints, not a cut-out
                    render_profile['opacitySource'] = 'opaque'
        if render_profile['opacitySource'] == 'diffuse-alpha' and chain:
            # A masked material's cut-out is what its OpacityMask input samples, not always the colour's alpha.
            # Wired straight to a texture parameter (PROP_Objects: Spc_Ems_Mpc_Opc's alpha), that texture's channel;
            # an OpacityMask switch that is off (PROP_Objects_Old: a tractor, dairy tanks, pipes, whose colour alpha
            # is near black) cuts nothing. Otherwise the colour's alpha, as before.
            wired = opacity_input(p, chain[-1])
            if switches.get('OpacityMask') is False:
                render_profile['opacitySource'] = 'opaque'
            elif wired and wired[0] in textures and wired[0] != render_profile['diffuseParameter']:
                render_profile.update(opacitySource='packed-alpha', opacityParameter=wired[0], opacityChannel=wired[1])
        program = material_programs.program(self, index, chain, dict(vectors=vectors, scalars=scalars, blend=blend),
                                            textures)
        say = (lambda *a: None) if program else self.warn       # a material drawn by its program: no guesses to own
        constant, unlit = constant_color(p, chain[-1]) if chain else (None, False)
        if constant is not None:
            render_profile.update(family='constant', constantColor=constant, unlit=unlit, opacitySource='opaque')
        if render_profile['family']=='fogged-civilian':
            interior=p.by_name.get(p.name(index).rsplit('.',1)[0]+'.CivFogged_Int',index)
            colours=[p.own(c,'DefaultValue') for c in p.children.get(interior,[])
                     if p.cls(c)=='MaterialExpressionVectorParameter']
            render_profile['constantColor']=next((c[:3] for c in colours if isinstance(c,list) and len(c)>=3),None)
            say(p.name(index),'Fogged civilian procedural material: source constant-colour approximation')
        diffuse = self.texture(textures[render_profile["diffuseParameter"]]) if render_profile["diffuseParameter"] else None
        normal = binding(("Normal", "Normal_Base", "NormalMap", "Normal Map"))
        opacity = emissive = None
        if render_profile.get('opacityParameter'):
            opacity = self.texture_channel(textures[render_profile['opacityParameter']], render_profile.get('opacityChannel', 'A'))
            if diffuse: diffuse = self.texture_channel(textures[render_profile['diffuseParameter']], 'RGB')
            render_profile['opacityUv'] = sampling.get(render_profile['opacityParameter'], dict(channel=0,scale=[1,1]))
        if render_profile.get('emissiveParameter'):
            emissive = self.texture_channel(textures[render_profile['emissiveParameter']], 'G')
            render_profile['emissiveUv'] = sampling.get(render_profile['emissiveParameter'], dict(channel=0,scale=[1,1]))
        if render_profile['family'] == 'alien-energy':
            # The cooked energy graph is stripped. Tint one pattern channel with
            # DoorColor, rather than displaying its packed RGB as surface colour.
            if render_profile['diffuseParameter']:
                emissive = self.texture_channel(textures[render_profile['diffuseParameter']], 'R')
            say(p.name(index), 'Alien energy door: stationary colour/pattern approximation; animation is not evaluated')
        compiled = None
        if (not diffuse and not render_profile.get('constantColor') and chain and p.name(chain[-1]) not in BY_KIND
                and blend not in ("BLEND_Translucent", "BLEND_Additive", "BLEND_Modulate")):
            # No texture parameter to read: the textures its compiled shaders sample, by name (a colour texture,
            # and for a masked one a mask whose channel a 0/1 vector parameter picks, as Asphalt_Patch's PatchSet,
            # else the colour texture's own alpha, as a burning pine's branches)
            refs = compiled_textures(p, chain[-1])
            names = {r: p.name(r).rsplit('.', 1)[-1] for r in refs}
            colour = compiled_colour(names)
            if colour:
                compiled = dict(diffuse=names[colour], textures=[p.name(r) for r in refs])
                mask = next((r for r in refs if MASK_NAME.search(names[r])), None)
                selector = next((v for v in vectors.values() if isinstance(v, list) and len(v) >= 3
                                 and all(x in (0, 1, 0.0, 1.0) for x in v[:3]) and sum(v[:3]) == 1), None)
                if blend == 'BLEND_Masked' and mask and selector:
                    diffuse = self.texture_channel(colour, 'RGB')
                    channel = 'RGB'[list(v for v in selector[:3]).index(1)]
                    opacity = self.texture_channel(mask, channel)
                    render_profile.update(opacitySource='packed-alpha', opacityUv=dict(channel=0, scale=[1, 1]))
                    compiled.update(mask=names[mask], channel=channel)
                else:
                    diffuse = self.texture(colour) if blend == 'BLEND_Masked' else self.texture_channel(colour, 'RGB')
                say(p.name(index), f"No texture parameter: colour from the compiled shader's {names[colour]}"
                          + (f", cut out by {names[mask]}'s {compiled['channel']} channel" if 'channel' in compiled else '')
                          + ' (approximation)')
        if not diffuse and not render_profile.get('constantColor') and chain and blend not in (
                "BLEND_Translucent", "BLEND_Additive", "BLEND_Modulate"):
            # Nothing to read a colour from: a colour by kind (approximate_colour), or neutral grey
            colour, why = approximate_colour([p.name(i) for i in chain], vectors)
            render_profile.update(family='approximate', constantColor=colour, opacitySource='opaque')
            say(p.name(index), f'No colour texture found: {why} (approximation)')
        info = dict(name=p.name(index), parents=[p.name(i) for i in chain], diffuse=diffuse,
                    normal=normal, opacity=opacity, emissive=emissive, blend=blend, twoSided=two_sided,
                    alphaTest=p.own(chain[-1], 'OpacityMaskClipValue', 0.3333) if chain else 0.3333,
                    vectors=vectors, scalars=scalars, staticSwitches=switches,
                    render=render_profile,
                    textureParameters={k: p.name(v) for k,v in textures.items()}, approximation=True)
        if program:
            info['program'] = program
        if blend == "BLEND_Modulate":
            say(p.name(index), "Modulate overlay: colour-only approximation")
        if any(k in textures for k in ("Diffuse_Mod", "Normal_Mod", "Mask")):
            say(p.name(index), "Layered/vertex-painted material: drawn in one of its textures, not mixed as the game "
                               "mixes them")
        self.materials[key] = info
        return key

    def stand_in(self, kind, name=None, source=None):
        """A material for a mesh section with none to draw: 'interior', a fractured mesh's inside faces with no
        material (the game draws them only where a fragment has broken off; the page hides them), or 'missing', a
        material the package only names (it lives in another package: neutral grey)."""
        key = f'{self.prefix}{kind}' + (f'-{name}' if name else '')
        if key in self.materials: return key
        hidden = kind == 'interior'
        self.materials[key] = dict(name=name or kind, parents=[], diffuse=None, normal=None, opacity=None,
                                   emissive=None, blend='BLEND_Opaque', twoSided=False, alphaTest=0.3333, vectors={},
                                   scalars={}, staticSwitches={}, textureParameters={}, approximation=True,
                                   render=dict(family='hidden' if hidden else 'approximate', opacitySource='opaque',
                                               diffuseParameter=None, uv=dict(channel=0, scale=[1, 1]),
                                               **({} if hidden else dict(constantColor=NEUTRAL))))
        if name:
            self.warn(name, 'Material not in this package (the game loads it from another): drawn neutral grey')
        elif not hidden:
            self.warn(source or kind, 'Mesh section with no material (this and any others): drawn neutral grey')
        return key

    def stub(self, index):
        """A material export with nothing in it but its texture GUIDs (LWR's patch packages carry the materials of
        their pieces like this: the game has the real ones from the map already loaded)."""
        try:
            props, _ = self.p.properties(index)
        except (FormatError, ValueError, struct.error):
            return False
        return 'Material' in self.p.cls(index) and {k[0] for k in props} <= STUB_PROPERTIES

    def section_material(self, mat, mesh):
        """The material key for a mesh section's material reference: an export of this package; a stub or import
        found in the base map (a streamed package's, as the game finds it); a fractured mesh's interior with none;
        otherwise a neutral grey stand-in."""
        if mat > 0 and (self.prefix + str(mat) in self.materials or not self.stub(mat)): return self.material(mat)
        if mat and self.base is not None:
            index = self.base.p.by_name.get(self.p.name(mat), 0)
            if index > 0 and not self.base.stub(index): return self.base.material(index)
        if not mat:
            fractured = self.p.cls(mesh) == 'FracturedStaticMesh'
            return self.stand_in('interior' if fractured else 'missing', source=self.p.name(mesh))
        return self.stand_in('missing', self.p.name(mat))

    def texture_channel(self, index, channel):
        """Portable linear masks retain the packed source texture's provenance."""
        source = self.texture(index)
        if not source: return None
        key = f'{source}-{channel}'
        if key not in self.textures:
            filename = f'texture-{key}.png'
            with Image.open(self.folder / self.textures[source]['url']) as image:
                pixels = image.convert('RGB') if channel == 'RGB' else image.getchannel(channel).convert('RGB')
                pixels.save(self.folder / filename)
            kept = {k: v for k, v in self.textures[source].items() if k not in ('container', 'levels')}   # a PNG
            self.textures[key] = dict(kept, url=filename, derivedFrom=source,
                                      channel=channel, srgb=self.textures[source]['srgb'] if channel == 'RGB' else False)
        return key

    def component(self, actor, component):
        p = self.p
        mi = p.effective(component, "StaticMesh", 0)
        if mi <= 0:
            if mi < 0: self.warn(p.name(component), f"Unresolved external mesh {p.name(mi)}")
            skeletal = p.effective(component, "SkeletalMesh", 0)
            if skeletal>0:mi=skeletal
            else:
                if skeletal<0:self.warn(p.name(component),f'Unresolved external skeletal mesh {p.name(skeletal)}')
                return None
        if p.cls(mi) not in ("StaticMesh", "FracturedStaticMesh", "SkeletalMesh"):
            self.warn(p.name(component), f"Unsupported mesh class {p.cls(mi)}")
            return None
        visible = p.effective(component, "EditorPaintedVisibleFragments")
        mask = None
        if visible:
            n = struct.unpack_from("<i", visible)[0]
            if len(visible) == 4 + n * 4: mask = [bool(x) for x in struct.unpack_from(f"<{n}i", visible, 4)]
            elif len(visible) == 4 + n: mask = [bool(x) for x in visible[4:]]
            else: raise FormatError("Invalid visible-fragment mask")
        mesh_key = self.prefix+str(mi) + ("-" + hashlib.sha256(visible).hexdigest()[:12] if visible else "")
        if mesh_key not in self.meshes:
            mesh = read_skeletal(p,mi) if p.cls(mi)=='SkeletalMesh' else read_mesh(p, mi)
            if mask is not None:
                indices, sections = [], []
                for s in mesh["sections"]:
                    start = len(indices)
                    if len(s["fragments"]) != len(mask):
                        raise FormatError("Fragment range count disagrees with visibility mask")
                    for enabled, (first, triangles) in zip(mask, s["fragments"]):
                        if enabled: indices.extend(mesh["indices"][first:first+triangles*3])
                    sections.append({**s, "first": start, "count": len(indices)-start})
                mesh["indices"], mesh["sections"] = indices, sections
            write_glb(mesh, self.folder / f"mesh-{mesh_key}.glb")
            self.meshes[mesh_key] = dict(name=p.name(mi), url=f"mesh-{mesh_key}.glb",
                vertices=len(mesh["positions"])//3, triangles=len(mesh["indices"])//3,
                sections=mesh["sections"], bounds=mesh["bounds"], fragmentMask=mask,
                kind='skeletal' if mesh.get('bones') else 'static',bones=mesh.get('bones',[]),
                pose='reference' if mesh.get('bones') else None,
                origin=mesh.get('origin'),rotOrigin=mesh.get('rotOrigin'),
                collision=self.mesh_collision(mi))
        mesh = self.meshes[mesh_key]
        # its own painted vertex colours (LOD 0's), in the mesh's vertex order: a file beside the mesh (export 43)
        paint = None
        if mesh['kind'] == 'static' and self.programs is not None:
            colours = material_programs.painted_colours(p, component, mesh['vertices'])
            if colours:
                paint = f"paint-{self.prefix}{actor}-{component}.bin"
                (self.folder / paint).write_bytes(colours)
        material_refs = p.refs(p.effective(component, "Materials"))
        mats = []
        for s in mesh["sections"]:
            if not s["count"]: continue
            slot = s["slot"]
            override = material_refs[slot] if 0 <= slot < len(material_refs) else 0
            # the component's own material, else the mesh's; an import of either is looked for in the base map
            mats.append(self.section_material(override if override > 0 else s["material"] or override, mi))
        location = p.effective(actor, "Location", [0,0,0])
        rotation = p.effective(actor, "Rotation", [0,0,0])
        scale = [v * p.effective(actor, "DrawScale", 1) for v in p.effective(actor, "DrawScale3D", [1,1,1])]
        component_scale = [v * p.effective(component, "Scale", 1) for v in p.effective(component, "Scale3D", [1,1,1])]
        for flag in ("AbsoluteTranslation", "AbsoluteRotation", "AbsoluteScale"):
            if p.effective(component, flag, False): raise FormatError(f"Unsupported {flag}")
        am = transform(location, rotation, scale)
        cm = transform(p.effective(component,"Translation",[0,0,0]),
                       p.effective(component,"Rotation",[0,0,0]), component_scale)
        return dict(id=f"{self.prefix}{actor}:{component}", actor=p.name(actor), component=p.name(component),
                    sourcePackage=p.path.stem,layer='inherited' if self.prefix else 'base',
                    editorLayers=[v.strip() for v in p.effective(actor,'Layer','').split(',') if v.strip()],
                    actorClass=p.cls(actor), archetype=p.name(p.exports[actor-1]["arch"]),
                    mesh=mesh_key, materials=mats, location=location, rotation=rotation, scale=scale,
                    matrix=view_matrix(multiply(am,cm)), tint=p.effective(actor,"TintColor",[1,1,1,1]),
                    componentTransform=cm,
                    # Pieces placed together: the prefab instance that placed the actor, and the
                    # partner it names (a car body's glass). The viewer moves linked pieces together.
                    prefab=self.prefabs.get(actor),
                    partner=p.name(partner) if (partner:=p.effective(actor,"HidingPartner",0)) > 0 else None,
                    # what of the package's Kismet names the actor (export 15): moving or deleting it is refused
                    referencedBy=self.kismet.get(actor, []),
                    # what its fragment columns break (export 16): a car's glass names its body and parts
                    breaks=[p.name(v) for v in self.breaks.get(actor, [])],
                    # its toughness and health, None when it has none (export 17)
                    destruction=destruction(p, actor),
                    environment=p.name(mi).startswith("Skybox."),
                    cutout=bool(p.effective(component,"bCutoutMask",False)),
                    # a fracturing piece the game keeps whole (export 36)
                    **({'keepsPieces': True} if p.cls(component) == "FracturedStaticMeshComponent"
                       and p.effective(component, "bPreventChunkRemoval", False) else {}),
                    hidden=bool(p.effective(actor,"bHidden",False) or p.effective(component,"HiddenGame",False)),
                    **({'paint': paint} if paint else {}),
                    # its baked light as the game stores it (export 44): its lightmap, and its shadow map of the sun
                    **(self.baked(component, mi) if self.lightmaps and mesh['kind'] == 'static' else {}),
                    # false when the actor collides with nothing, so touches no floor volume and no building lists it
                    # (F-87; the Build's native_copy.collides): left out otherwise, and in exports made before it
                    **({} if collides(p, actor) else {'collides': False}),
                    # its flags (export 27): how the game's tiles and mouse use it, the same on each of its components
                    **({'pieceFlags': flags} if (flags := self.piece_flags(actor)) else {}))

    def run(self, scope='map'):
        """The package's scene: the whole level (`scope` is always "map": the scene says so, as catalogue.py checks). A
        streamed package's (stream_layers) keeps only its pieces, lights, effects and level records, so its buildings,
        tile grid and tactical data are not worked out (review finding 63); the map itself writes no level records
        (`content`), which a layer keeps for stream_layers' and compose_scene's counts."""
        p = self.p
        stream = self.prefix.startswith('stream-')
        actors = [i for i,n in enumerate(p.paths,1) if n.startswith("TheWorld.PersistentLevel.") and n.count(".")==2
                  and not n.rsplit(".",1)[-1].startswith("Default__")]
        selected = set(actors)
        self.prefabs = prefab_members(p, self.warn)
        self.kismet = kismet_references(p, self.warn)
        self.breaks = fragment_breaks(p, selected, self.warn)
        objects = []
        work = [(actor, [c for c in p.children.get(actor,[]) if "MeshComponent" in p.cls(c)]) for actor in sorted(selected)]
        total, done, step = sum(len(c) for _, c in work), 0, 0
        if self.progress: self.progress(0, total)
        for actor, components in work:
            for c in components:
                try:
                    obj = self.component(actor,c)
                    if obj: objects.append(obj)
                except UNREADABLE as error:
                    self.warn(p.name(c), error)
                done += 1
                if self.progress and (done == total or done * 100 // max(total, 1) > step):
                    step = done * 100 // max(total, 1)
                    self.progress(done, total)
        buildings = [] if stream else self.guarded('buildings', lambda: building_metadata(p,objects,self.kismet), [])
        lights = self.guarded('lights', lambda: light_records(p,actors,self.prefix,
                                                              'inherited' if self.prefix else 'base',self.warn), [])
        self.guarded('light metadata', lambda: light_metadata(p, lights, objects, self.kismet, self.warn), None)
        # what a light's light function does to it (export 46): a program the page runs each frame in the Game look
        if self.programs is not None:
            self.guarded('light functions', lambda: light_functions.add(p, lights, self.programs, self.warn), None)
        self.area_matcher = self.guarded('area lights', lambda: area_lights(p, objects, lights, self.meshes, self.materials,
                                                                            self.warn), None)
        # a van's own building goes with the van (compiler.van_buildings: the editor keeps it fixed)
        if not stream:
            paths.use('editor')
            import compiler
            vans = compiler.van_buildings(dict(objects=objects, buildings=buildings, meshes=self.meshes), p.path.stem)
            for building in buildings: building['van'] = building['id'] in vans
        if self.prefix and not stream:
            for building in buildings:building['id']=self.prefix+building['id']
            for obj in objects:
                for entry in obj['floors']:entry['building']=self.prefix+entry['building']
        bounds = None
        # (a stream's playable bounds, grid and tactical data are dropped: none is worked out)
        for obj in (objects if not stream else []):
            if obj["actorClass"] != "XComLevelVolume": continue
            b = self.meshes[obj["mesh"]]["bounds"]
            m = obj["matrix"]
            corners = []
            for sx in (-1,1):
                for sy in (-1,1):
                    for sz in (-1,1):
                        v = [b[0]+sx*b[3],b[2]+sz*b[5],b[1]+sy*b[4]]
                        corners.append([sum(m[k*4+j]*v[k] for k in range(3))+m[12+j] for j in range(3)])
            candidate = dict(min=[min(v[j] for v in corners) for j in range(3)],
                             max=[max(v[j] for v in corners) for j in range(3)])
            area = (candidate["max"][0]-candidate["min"][0])*(candidate["max"][2]-candidate["min"][2])
            if bounds is None or area > bounds[0]: bounds = (area,candidate)
        grid=tile_grid(p,bounds[1],self.warn) if bounds else None
        tactical=tactical_metadata(p,objects,self.meshes,grid,self.warn) if grid else None
        effects = self.effects()
        # the map's spawn points (export 33): [] for a map with none, absent for a streamed or previewed package
        spawns = {} if self.prefix else dict(spawns=spawn_metadata(p, self.landings, self.warn))
        # its background sound and its triggers counted (export 39), absent for a streamed or previewed package
        sound = {} if self.prefix else dict(
            backgroundSound=self.guarded('background sound', lambda: background_sound.background_sound(p), None),
            triggerCounts=self.guarded('trigger counts', lambda: trigger_counts(p), None))
        # its fog, grade, bloom and post-process volumes (export 43), absent for a streamed or previewed package
        air = {} if self.prefix else dict(atmosphere=self.guarded('atmosphere', lambda: atmosphere_records.read(p), None))
        # its placed decals (export 47): the map's and a stream's, none for the patch a preview builds on
        decals = ([] if self.prefix and not stream
                  else self.guarded('decals', lambda: decal_export.records(self, objects), []))
        return dict(schemaVersion=1, exporterVersion=EXPORT_VERSION, name=p.path.stem, scope=scope, **air,
                    playableBounds=bounds[1] if bounds else None,
                    tileGrid=grid, tactical=tactical,
                    buildings=buildings,
                    cursorVolumes=[] if self.prefix else self.guarded('cursor volumes', lambda: cursor_volumes(p), []),
                    landings=self.landings, **spawns, **sound,
                    effects=effects['effects'], sounds=effects['sounds'], flares=effects['flares'],
                    effectSystems=effects['systems'], soundWaves=effects['waves'], decals=decals,
                    lighting="dynamic", lightMetadata=dict(version=LIGHT_METADATA_VERSION, areaMatcher=self.area_matcher),
                    source=dict(file=str(p.path),sha256=self.digest or sha256(p.path),
                    version=p.header["ver"],licensee=p.header["lic"]),
                    counts=dict(exports=len(p.exports),selectedActors=len(selected),components=len(objects),lights=len(lights),
                                decals=len(decals),
                                meshes=len(self.meshes),materials=len(self.materials),textures=sum(bool(v) for v in self.textures.values())),
                    objects=objects, lights=lights, meshes=self.meshes,
                    materials=self.materials,textures=self.textures,diagnostics=self.diagnostics,
                    **({'content': self.guarded('level records', lambda: content_records(p), [])} if self.prefix else {}))


def map_records(package_path):
    """The DefaultMaps.ini records that play this map (maplist.records: the live ones, or a switched-off map's), from
    the install its package is in
    (<game>/XEW/XComGame/CookedPCConsole/<map>.upk, so <game>/XEW/XComGame/Config/DefaultMaps.ini): each record's
    mission (maplist.mission_of) and the packages it streams, landing intros and other cinematics (CIN_) left out.
    [] for a package outside an install."""
    import maplist
    import mapsini
    import installs
    import missions
    path = Path(package_path).resolve()
    ini = path.parent.parent / 'Config' / 'DefaultMaps.ini'
    if not ini.is_file(): return []
    # LWR's own records: what the editor installed (installs.py) taken out
    game = ini.parents[3] if len(ini.parents) > 3 else None
    text = installs.maps_text(game) if game and installs.config(game, 'DefaultMaps.ini') == ini else ini.read_text(encoding='latin-1')
    out = []
    for line in maplist.records(text):
        if (mapsini.field(line, 'Name') or '').casefold() != path.stem.casefold(): continue
        group, mission, label = maplist.mission_of(line)
        if mission in maplist.LEFT_OUT: continue
        streams = [s for s in mapsini.slot_streams(line) if not s.upper().startswith('CIN_')]
        out.append(dict(type=mission, label=label, group=group, kind=missions.kind_key(line),
                        display=mapsini.field(line, 'DisplayName') or '', streams=list(dict.fromkeys(streams))))
    return out


def stream_package(package_path, name):
    """A streamed package beside the map's (the EW folder), else in the base game's CookedPCConsole, or None."""
    cooked = Path(package_path).resolve().parent
    for folder in (cooked, settings.cooked_folders(cooked.parents[2])[-1]):
        if (folder / f'{name}.upk').is_file(): return folder / f'{name}.upk'
    return None


def stream_layers(p, result, stage, records, progress=None, base=None):
    """Each package the map's records stream, exported as a layer the page overlays (`streams` in scene.json): its
    pieces and lights (layer "stream", `stream` its name), their assets added to the scene's. kind "lwr" for LWR's
    patches (patch_*), "mission" for the rest (a mission's own objects: _CNH, _Bomb, ...). Stream pieces carry no
    floors or scenery role: the page shows them whatever the cutaway, and never edits them. base: the map's
    Exporter (whose assets are the result's), where a stream's stub and imported materials are found. A mission's
    stream also gets `missionObjects` (export 24: scene_metadata.mission_objects), its objects that have no mesh to show
    as pieces among them."""
    streams = {}
    for name in dict.fromkeys(s for r in records for s in r['streams']):
        kind = 'lwr' if name.lower().startswith('patch_') else 'mission'
        path = stream_package(p.path, name)
        entry = streams[name] = dict(kind=kind, package=path.name if path else None, objects=[], lights=[],
                                     error=None if path else 'not in the install')
        if not path: continue
        try:
            report = (lambda done, total, name=name: progress(f'reading {name}', done, total)) if progress else None
            package = Package(path)
            layer = Exporter(package, stage, namespace='stream-'+name, progress=report, base=base).run('map')
        except UNREADABLE as error:
            entry['error'] = str(error)
            continue
        report_to = lambda source, error, name=name: result['diagnostics'].append(  # noqa: E731
            dict(source=f'{name}: {source}', message=str(error)))
        if kind == 'mission':
            from scene_metadata import mission_objects
            entry['missionObjects'] = mission_objects(package, report_to)
        else:
            # an LWR patch's spawn points (export 33), shown read only with the layer named
            entry['spawns'] = spawn_metadata(package, [], report_to)
        for key in ('meshes','materials','textures'):
            if set(result[key]) & set(layer[key]): raise ValueError(f'Asset identity collision in {name}')
            result[key].update(layer[key])
        # its effects, sounds and flares (export 28), read only; their systems and waves are keyed by package
        for key, into in (('effectSystems', 'effectSystems'), ('soundWaves', 'soundWaves')):
            result.setdefault(into, {}).update(layer.get(key) or {})
        for record in layer['objects'] + layer.get('lights', []) + layer.get('decals', []):
            record.update(layer='stream', stream=name)
        for obj in layer['objects']:
            obj.update(floors=[], sceneryRole=None)
        entry.update(effects=layer.get('effects', []), sounds=layer.get('sounds', []), flares=layer.get('flares', []),
                     decals=layer.get('decals', []))
        entry.update(objects=layer['objects'], lights=layer.get('lights', []),
                     hiddenComponents=sum(bool(o['hidden']) for o in layer['objects']),
                     rebuildVolumes=sum(r.get('actorClass') == 'XComRebuildWorldDataVolume'
                                        for r in layer.get('content', [])))
        # where the battle reworks the tiles as the level streams in (export 41, KB-22): a diagonal cover mark there
        # gets none in the game, which the Diagonal cover view and the Build warn of
        from scene_metadata import rebuild_spheres
        entry['rebuildSpheres'] = rebuild_spheres(package, report_to)
        result['diagnostics'].extend(dict(d, source=f'{name}: {d["source"]}') for d in layer['diagnostics'])
    return streams


def export_map(source, cache_root, scope, specs=(), progress=None):
    """progress(what, done, total), as each package's pieces are read."""
    p = Package(source)
    digest = sha256(p.path)       # once: the folder's name and the scene's source both take it
    fingerprint = digest[:16]
    parent = Path(cache_root).resolve() / p.path.stem
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / f"{fingerprint}-v{EXPORT_VERSION}-{scope}"
    stage = Path(tempfile.mkdtemp(prefix=".export-",dir=parent))
    try:
        exporter = Exporter(p,stage,progress=(lambda done, total: progress('reading the map', done, total)) if progress else None,
                            digest=digest, programs=material_programs.Programs(Path(cache_root).resolve()), lightmaps=True)
        result = exporter.run(scope)
        previews=[]
        inherited={}
        def inherited_scene(name):
            import re
            if not re.fullmatch(r'[A-Za-z_]\w*',name):raise ValueError(f'Invalid inherited package name {name}')
            if name not in inherited:
                path=p.path.parent/(name+'.upk')
                if not path.is_file():raise ValueError(f'Missing inherited patch: {path}')
                package=Package(path)
                layer=Exporter(package,stage,namespace='inherited-'+name,base=exporter).run('map')
                for key in ('meshes','materials','textures'):
                    collision=set(result[key])&set(layer[key])
                    if collision:raise ValueError(f'Asset identity collision in {name}')
                    result[key].update(layer[key])
                inherited[name]=layer
            return inherited[name]
        def template(name):
            index=p.by_name.get(name,0)
            if not index:return []
            output=[]
            for c in p.children.get(index,[]):
                if 'MeshComponent' not in p.cls(c):continue
                obj=exporter.component(index,c)
                if obj:output.append(obj)
            return output
        for i,path in enumerate(specs):
            spec=json.loads(Path(path).read_text(encoding='utf-8'))
            if spec.get('map',{}).get('name')!=p.path.stem:
                raise ValueError(f'Spec {path} does not target {p.path.stem}')
            composed=compose_scene(result,[inherited_scene(spec['base'])]) if spec.get('base') else result
            scene=resolve_scene(composed,spec,template)
            scene['preview']['source']=str(Path(path).resolve())
            scene['preview']['sha256']=sha256(path)
            scene.pop('spawns',None)     # (export 33: a preview reads no spawn points)
            previews.append((f'preview-{i}.json',scene))
        if scope == 'map':
            # what the game streams into the map with each mission (LWR's patches, mission objects); the original
            # layout's only: a preview carries the patch it builds on itself
            result['missions'] = map_records(p.path)
            result['streams'] = stream_layers(p, result, stage, result['missions'], progress, base=exporter)
            # the bomb donor's objects (export 33): an added bomb mission's markers, without its pieces
            result['donors'] = donor_objects(stream_package(p.path, BOMB_DONOR), lambda source, error: result['diagnostics'].append(
                dict(source=f'{BOMB_DONOR}: {source}', message=str(error))))
        for scene in [result]+[s for _,s in previews]:
            for key in ('meshes','materials','textures'):scene[key]=result[key]
            scene['counts'].update(components=len(scene['objects']),lights=len(scene.get('lights',[])),meshes=len(exporter.meshes),
                                   materials=len(exporter.materials),textures=sum(bool(v) for v in exporter.textures.values()))
        for filename,scene in previews:
            (stage/filename).write_text(json.dumps(scene,separators=(',',':')),encoding='utf-8')
        # compact (review finding 50: indented, the largest was 15.6 MB against 8.3)
        (stage/"scene.json").write_text(json.dumps(result,separators=(',',':')),encoding="utf-8")
        if target.exists():
            # Publish to a new generation instead of deleting an existing export.
            target = parent / (target.name + "-" + stage.name.removeprefix(".export-"))
        stage.rename(target)
        return target, result
    except BaseException:
        # Remove only the verified staging folder created by this invocation.
        if stage.parent == parent and stage.name.startswith(".export-"): shutil.rmtree(stage)
        raise

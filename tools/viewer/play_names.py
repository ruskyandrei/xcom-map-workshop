"""A play's own names: Play in game installs a project's build under names that nothing else in the game install has,
so a map pack that carries the same map never meets the play.

The game finds a package by its file name anywhere under CookedPCConsole, a map pack's folder included, and Long War
Rebalance 3 merges a pack's map lines into the game's map list by DisplayName, a pack line taking the place of an
entry of the same display name. A build played under its project's own names, beside a pack made from the same
project, met both: two packages of each name, and the pack's line in place of the play's record. A pack installed the
classic way (Install.cmd) has a record of the map's name in DefaultMaps.ini and its files in CookedPCConsole itself,
which the install step refused to replace.

So a play installs every package of the build under its name with a play suffix (SUFFIX, numbered from 2 when that
gives a name the install has): the map <Map>_Play, its intro copies CIN_DropshipIntros_<Map>_Play (the name keeps
the intro's own at its start, as the exe recognises it), its edit patch and stream copies <name>_Play. The record is
the Build's own line for the mission played under the map's play name, its display name starting with the play name
where it started with the map's (the words the game matches after it stay), streaming the play's names; the
landing-zone lines and the drop-in exclusion name the play's map. An intro copy's Switch Strings, which pick the
landing by the map's exact name, are made to name the play's map (tools/bake/intro_copy.py, the map's name as the
base and the play's as the variant's). A package's own name is its file's: the map, its patch and its copies hold
no name of each other's (their name tables name none), so each is copied as it is under its new name. A file other
than a package (a texture cache, which textures find by its name) keeps its name.

A play's things come out once the game has closed (installs.clear_play), so the names never stay in the game.
"""
import copy
from pathlib import Path
import sys

import mapsini
from outputnames import INTROS
if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.append(str(Path(__file__).resolve().parents[1]))     # tools/paths.py (review finding 54)
import paths  # noqa: E402

paths.use('bake')

SUFFIX = '_Play'
TRIES = 99          # numbered suffixes tried (_Play2 ... _Play99) before giving up


class PlayNameError(Exception):
    pass


def suffix(stems, taken):
    """The play's suffix: SUFFIX, else SUFFIX numbered from 2, the first that gives none of the package names `stems`
    a name in `taken` (lower case)."""
    for n in range(1, TRIES + 1):
        end = SUFFIX + (str(n) if n > 1 else '')
        if not any((stem + end).lower() in taken for stem in stems):
            return end
    raise PlayNameError(f'every play name of {", ".join(stems)} up to {SUFFIX}{TRIES} is taken in the install')


def display(text, variant, play):
    """A record's display name for the play: the play's map name where it starts with the map's, else in front."""
    if text.lower().startswith(variant.lower()):
        return play + text[len(variant):]
    return f'{play} {text}' if text else play


def is_intro(stem):
    """Whether a package of the build is a copy of a streamed intro, whose Switch Strings name the map."""
    return any(stem.lower().startswith(intro.lower() + '_') for intro in INTROS)


def manifest(m, names):
    """The package's manifest as the play installs it: `names` ({package name: its play name}, the map's among them)
    in place of the build's, in the variant, the streams and copies it streams, the Build's records and the project's
    landing-zone lines; `playOf` the map's own name."""
    variant = m['variant']
    lower = {k.lower(): v for k, v in names.items()}        # (names match whatever their case, as Windows's do)
    play = lower[variant.lower()]
    out = copy.deepcopy(m)
    out['variant'], out['playOf'] = play, variant
    out['streams'] = [lower.get(s.lower(), s) for s in m.get('streams') or []]
    out['replaceStreams'] = {k: lower.get(v.lower(), v) for k, v in (m.get('replaceStreams') or {}).items()}
    c = out.get('config') or {}

    def record(line):
        line = mapsini.set_field(mapsini.renamed_maps(line, names), 'Name', play)
        shown = mapsini.field(line, 'DisplayName')
        return line if shown is None else mapsini.set_field(line, 'DisplayName', display(shown, variant, play))
    if c.get('maps'):
        c['maps'] = [record(line) for line in c['maps']]
    if c.get('landingZones'):
        c['landingZones'] = [mapsini.renamed_maps(line, {variant: play}) for line in c['landingZones']]
    return out


def renamed_intro(src, dst, variant, play):
    """The build's intro copy `src` written to `dst` with each Switch String entry naming `variant` naming `play`;
    False when no entry names it (the copy's bytes never do), and nothing is written."""
    if variant.lower().encode('ascii') not in Path(src).read_bytes().lower():
        return False
    import intro_copy
    try:
        return intro_copy.make(src, dst, variant, play)['copy'] is not None
    except (OSError, ValueError, KeyError, IndexError) as error:
        raise PlayNameError(f'{Path(src).name} could not be given the play\'s map name ({error})') from None


def for_play(m, files, taken, scratch, digest):
    """(the manifest, the files) of a package (installs.read_package's) as a play installs them: each package under
    its play name (suffix against `taken`, the install's names in lower case), an intro copy renamed inside written
    into the folder `scratch` first and hashed by `digest` (installs.sha256)."""
    variant = m['variant']
    stems = [dst.stem for _, dst, _ in files if dst.suffix.lower() == '.upk']
    if variant.lower() not in {stem.lower() for stem in stems}:
        raise PlayNameError(f'the package has no {variant}.upk')
    end = suffix(stems, taken)
    # (the map's play name spelt as the manifest spells the map: the record, the open line and the intro's switches)
    names = {stem: (variant if stem.lower() == variant.lower() else stem) + end for stem in stems}
    play = variant + end
    out = []
    for src, dst, sha in files:
        new = names.get(dst.stem) if dst.suffix.lower() == '.upk' else None
        if new is None:
            out.append((src, dst, sha))
            continue
        target = dst.with_name(new + dst.suffix)
        made = Path(scratch) / target.name
        if is_intro(dst.stem) and renamed_intro(src, made, variant, play):
            out.append((made, target, digest(made)))
        else:
            out.append((src, target, sha))
    return manifest(m, names), out

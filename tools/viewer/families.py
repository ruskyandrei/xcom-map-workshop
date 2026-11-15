"""The families of pieces and a map's assemblies, for the editor page (private/plans/done/cars-doors-ladders-plan.md, sections
3.3 and 3.4): GET /maps/<id>/families.json. The page always moves an assembly's pieces together (a car's body, glass
and light bar; a door's leaf and frame), poses the grid families by the recipe snap, and names the milestone of a
family that doesn't build yet. All of it comes from the compiler (tools/editor/compiler.py), so the page and the Build
agree."""
import json
from pathlib import Path
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'editor'))
import compiler  # noqa: E402
import ladders  # noqa: E402


def table():
    """What the page needs of the compiler's tables: each family (builds, milestone, grid, what), each class's family,
    the families that are assemblies, and the pose rule's steps."""
    return dict(families=compiler.FAMILIES, classFamily=compiler.CLASS_FAMILY,
                assemblyFamilies=list(compiler.ASSEMBLY_FAMILIES),
                grid=dict(tile=compiler.TILE, storey=compiler.STOREY, quarter=compiler.QUARTER, slack=compiler.POSE_SLACK),
                # cover blocks' recipe (compiler.COVER_RECIPES): the latest version's heights (below and above the
                # floor, by cover) and the most tiles across, and the types each version makes (a block keeps its own
                # version while that version makes its type)
                coverRecipes=dict(versions=sorted(compiler.COVER_RECIPES), latest=max(compiler.COVER_RECIPES),
                                  types={str(v): sorted(r['heights']) for v, r in compiler.COVER_RECIPES.items()},
                                  **compiler.COVER_RECIPES[max(compiler.COVER_RECIPES)]))


def light_table(scene):
    """What the page needs to edit lights (private/plans/done/editor-lights-plan.md, 3.4 and 4.2): each light's verdict by id
    (compiler.light_rule: None when an edit may change it, else why it is view only), the built-in recipes for lights a
    map has no template for (`lightRecipes`: kind -> its versions and their starting values), and why this export can't
    build edits (`exportProblem`, compiler.light_metadata_problem: an older export needs preparing), or None."""
    return dict(lightRules={l['id']: compiler.light_rule(l) for l in scene.get('lights') or [] if l.get('id')},
                lightRecipes={kind: dict(versions=sorted(v), latest=max(v), values=v[max(v)])
                              for kind, v in compiler.LIGHT_RECIPES.items()},
                exportProblem=compiler.light_metadata_problem(scene), exportMinimum=compiler.EXPORT_MINIMUM)


def families(scene):
    """table(), the map's assemblies (compiler.assemblies), each once: dict(family, pivot, members, leaves), actor
    paths of the base level of the map's own package; its ladders' helpers in streamed patches (ladders.helpers); its
    landing-zone pieces (compiler.landing_actors: moved or deleted with a warning, F-45); and light_table()."""
    found, seen = [], set()
    for assembly in compiler.assemblies(scene, scene.get('name')).values():
        if assembly['pivot'] in seen: continue
        seen.add(assembly['pivot'])
        found.append(dict(family=assembly['family'], pivot=assembly['pivot'], members=assembly['members'],
                          leaves=assembly.get('leaves') or []))
    return dict(table(), map=scene.get('name'), assemblies=sorted(found, key=lambda a: a['pivot']),
                helpers=ladders.helpers(scene), landing=compiler.landing_actors(scene), **light_table(scene))


class FamilyCache:
    """families() of each exported map's scene.json, worked out the first time the page asks (a map's export doesn't
    change under a running server: a re-export is served after a restart)."""

    def __init__(self):
        self.lock = threading.Lock()
        self.done = {}

    def get(self, root):
        root = Path(root)
        with self.lock:
            if root not in self.done:
                self.done[root] = families(json.loads((root / 'scene.json').read_text(encoding='utf-8')))
            return self.done[root]

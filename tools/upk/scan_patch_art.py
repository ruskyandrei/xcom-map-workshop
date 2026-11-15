# Lists the art in a folder of patch packages: exported static meshes, material instances and textures, imported
# art objects, and Kismet mesh-swap actions with the paths they load.
#   python tools/upk/scan_patch_art.py [CookedPCConsole folder] [glob, default patch_*.upk]
# The folder defaults to the CookedPCConsole of the game Steam runs (tools/lab/labpaths.py: the lab copy when active).
import sys, os, glob, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import upkinfo as U

if len(sys.argv) > 1:
    folder = sys.argv[1]
else:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lab'))
    import labpaths
    folder = str(labpaths.active_game() / 'XEW' / 'XComGame' / 'CookedPCConsole')
pattern = sys.argv[2] if len(sys.argv) > 2 else 'patch_*.upk'
ART = ('StaticMesh', 'SkeletalMesh', 'Material', 'MaterialInstanceConstant', 'Texture2D', 'PhysicalMaterial')
SWAPS = ('SeqAct_ReplaceActorMesh', 'SeqAct_LoadContent', 'SeqAct_SetMesh')
exported = collections.defaultdict(set); imported = collections.defaultdict(set); swaps = collections.defaultdict(set)
for p in sorted(glob.glob(os.path.join(folder, pattern))):
    pn = os.path.basename(p)[:-4]
    try:
        b, h = U.load(p); names, imps, exps = U.tables(b, h)
    except Exception as e:
        print('FAIL', pn, e); continue
    for n, e in enumerate(exps):
        c = U.clsname(e['cls'], imps, exps)
        if c in ART:
            exported[c + ' ' + U.objname(n + 1, imps, exps)].add(pn)
        elif c in SWAPS:
            data = b[e['off']:e['off'] + e['size']]
            paths = [s.decode() for s in re.findall(rb'[A-Za-z0-9_]+\.[A-Za-z0-9_.]+', data) if len(s) > 8]
            swaps[c + ' ' + (', '.join(paths) or '-')].add(pn)
    for n, i in enumerate(imps):
        if i['cls'] in ART:
            imported[i['cls'] + ' ' + U.objname(-(n + 1), imps, exps)].add(pn)

for title, d in (('exported art', exported), ('imported art', imported), ('mesh-swap actions', swaps)):
    print('== %s: %d' % (title, len(d)))
    for k, v in sorted(d.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        print('  %3d  %s   (e.g. %s)' % (len(v), k, sorted(v)[0]))

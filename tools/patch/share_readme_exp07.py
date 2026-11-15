"""Writes the README of the EXP-07 share package (dist/URB_Bar_L_Remix/README.txt).
It takes URB_Bar's map record, landing zones and MiniMods rule from the lab's config and renames them to
URB_BarRemix (F-42). The package itself: the seeded URB_Bar.upk copied as URB_BarRemix.upk, patch_exp07wing.upk,
preview.webp; see research/experiments/EXP-07-remix-layout.md, "Sharing".

  python tools/patch/share_readme_exp07.py [<the lab copy's XEW\\XComGame\\Config>]

The folder defaults to the Config of the game Steam runs, the lab copy while it is active (tools/lab/labpaths.py)."""
import os, re, sys

if len(sys.argv) > 1:
    G = sys.argv[1]
else:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lab'))
    import labpaths
    G = str(labpaths.active_game() / 'XEW' / 'XComGame' / 'Config')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'dist', 'URB_Bar_L_Remix', 'README.txt')

lines = open(G + '/DefaultMaps.ini', encoding='latin-1').read().split('\n')
src = [l for l in lines if 'Name="URB_Bar",' in l and 'Beta/Functionality Complete Urban Bar' in l]
assert len(src) == 1
rec = src[0].rstrip('\r')
rec = re.sub(r'(\bName=)"URB_Bar",', r'\1"URB_BarRemix",', rec, count=1)
rec = re.sub(r'DisplayName="[^"]*"', 'DisplayName="URB_BarRemix (Bar and Grill, L remix) |0"', rec)
assert rec.count('MapName="patch_bar"') == 1
rec = rec.replace('MapName="patch_bar"', 'MapName="patch_exp07wing"')
rec = re.sub(r'\s+', ' ', rec).strip()
assert 'MapFamily="URB_Bar"' in rec and 'Name="URB_BarRemix"' in rec

lz = [x.rstrip('\r').replace('MapName="URB_Bar"', 'MapName="URB_BarRemix"')
      for x in open(G + '/DefaultLZMutator.ini', encoding='latin-1').read().split('\n') if 'MapName="URB_Bar",' in x]
mm = [x.rstrip('\r').strip().replace('Map="URB_Bar"', 'Map="URB_BarRemix"')
      for x in open(G + '/DefaultMiniMods.ini', encoding='latin-1').read().split('\n') if 'Map="URB_Bar")' in x]
assert len(lz) == 7 and len(mm) == 1, (len(lz), len(mm))

readme = r'''URB_BarRemix: the Bar & Grill as an L
=====================================

XCOM: Enemy Within with Long War Rebalance (made on LWR v2.06.03, Windows/Steam).

URB_Bar's Bar & Grill with a second building north of it, so the two form an L. The wing has rooms with tables,
arcade machines and a pool table, working doors and windows, a wood floor, a ladder to its roof, and three new cars
(one on the roof). Everything else is the original map, and the original URB_Bar is left untouched: this is a map
of its own.

Files
-----
CookedPCConsole\URB_BarRemix.upk     the base map: a copy of the game's URB_Bar.upk whose tile data is marked
                                     where the wing stands. Without the marks the wing's walls don't block line of
                                     sight; the patch rebuilds those tiles at load.
CookedPCConsole\patch_exp07wing.upk  the streaming patch. It builds the wing at load from the bar's own pieces
                                     (script package XComMapEd, cooked in) and already holds patch_bar's content.
preview.webp                         an overview of the map.

Hints
-----
- Put both .upk files in XEW\XComGame\CookedPCConsole.
- Add a map record to DefaultMaps.ini: URB_Bar's abduction record with the new Name, and patch_exp07wing streamed
  in place of patch_bar (not as well as it):

@RECORD@

- Optional, for LWR's landing zones (DefaultLZMutator.ini), URB_Bar's seven lines under the new name. Without them
  the squad lands at the map's own spawn points:

@LZ@

- Optional, LW's difficulty rule for the map (DefaultMiniMods.ini):

@MM@

- Stream patch_exp07wing only on URB_BarRemix: it copies URB_Bar's pieces by their names.

Limits
------
- Saving and loading in a mission on this map is only lightly tested.

Credits: patch_bar is LiQuiD911's, from LWR's map patches. URB_Bar is Firaxis's; you need the game to use this.
'''
readme = readme.replace('@RECORD@', rec).replace('@LZ@', '\n'.join(lz)).replace('@MM@', '\n'.join(mm))
open(OUT, 'w', encoding='utf-8', newline='\r\n').write(readme)
print(rec)

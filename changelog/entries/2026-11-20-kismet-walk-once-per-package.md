### The Kismet walk runs once per package (editor refactor, stage B7)

[scene_metadata.py](../../tools/viewer/scene_metadata.py) `kismet_walk`, the one walk of a map's Kismet that
`kismet_references` and `kismet_uses` read, ran again each time either was asked: an export asked three times per
package (the scene's references, then the spawn points' reader's references and uses), and two or three times again
for each stream and the bomb donor (eleven walks for URB_Bar's export, 23 for URB_PierA's). Its result is now kept on
the package itself, as `Package.properties` keeps its reads, so each package is walked once (four and eight walks).
The walk no longer warns: it lists the sequence objects it could not read, and each reader warns of them in its own
words ("Kismet references not read", "Kismet uses not read"), each time it is asked, as before (review finding 55).

Checked:
- [test_links.py](../../tools/viewer/tests/test_links.py) `KismetWalkTests`, on a made-up package (no install): the
  three asks of an export read each sequence object's properties once (three times each before: the test fails on
  the code before), give the same references and uses, and warn of an unreadable object in each reader's words once
  per ask; another package walks its own.
- Fresh exports of URB_Bar, TempleShip, URB_PoliceStation, the blank map (CB2_MP_Blank) and URB_PierA (two mission
  streams and three patches read as layers, and the bomb donor) into scratch caches, three runs each with the code
  before and after, interleaved: `scene.json` the same bytes in all six runs of each map (references, uses and
  diagnostics; none of the five has an unreadable Kismet object), and every other file of the export too.
- The export's time is the same within the noise (seconds, before / after, mean of three, other work loading the
  computer at 13% to 83% of its processors meanwhile): the Bar 32.0 / 31.9, TempleShip 21.2 / 24.8, the police
  station 40.2 / 37.3, the blank map 3.31 / 3.30, the pier 27.1 / 29.4. The walks took about 0.19 s of an export
  before and 0.09 to 0.14 s after (the Bar and the pier, one run each): the property reads they lean on were already
  kept on the package.
- The viewer suite (640 tests; 10 skipped because a game was running on the computer: the play scripts refuse then).

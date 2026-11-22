### Play in game installs a build under play names of its own, so a map pack of the same map no longer stops it (F-161)

A player reported that a project could not be played from the editor while the same map was installed in the game
through a map pack. Play in game installed the build under the project's own names, which the pack's copy holds too:
a drop-in pack put a second package of each name under CookedPCConsole and, under Long War Rebalance 3, its line
(merged by display name) took the place of the play's record; a pack installed with Install.cmd left a record and
files of the map's name that the install step refused to replace.
[F-161](../../research/findings-register.md) has the details.

A play now installs every package of the build under its name with a play suffix,
[play_names.py](../../tools/viewer/play_names.py): `<Map>_Play`, or `_Play2` and on when one of the names is in the
install (a file anywhere under CookedPCConsole, a pack's folder included; a map name of DefaultMaps.ini; the editor's
ledgers, [installs.play_taken](../../tools/viewer/installs.py)). What the project's own earlier play holds is replaced,
as before. The map, its patch and its stream copies are copied as they are under their new names; each intro copy is
written again with its Switch Strings naming the play's map (`intro_copy.make` with the map's name as the base), so
the landing plays. The record is the Build's line for the mission under the play's name, its display name starting
with it (the words Long War matches after the name stay), streaming the play's copies; landing zones and the drop-in
exclusion name the play's map ([mapsini.renamed_maps](../../tools/viewer/mapsini.py) renames a line's map names). A
texture cache keeps its name, since textures find it by name: a play refuses one that differs from a campaign
install's of that name, which the campaign's map reads.

Because a play no longer shares names with the project's campaign install, a play of a newer build leaves the
campaign's files as they are (before, it replaced them), the project manager reads a play's `variant` to show it in
the game ([manager.py](../../tools/viewer/manager.py)), and the Game maps window's Undo of a build takes its play out
with it (`installs.remove_rotation`). A play no longer takes the place of a record the lab's patchtool deploy wrote
for the map; it goes beside it. Play's dialog, the Installs line and the [guide](../../tools/release/guide/guide.html)
say the play name.

Checked: [test_play_names.py](../../tools/viewer/tests/test_play_names.py) (a play beside a drop-in pack and beside a
pack installed the classic way, each left byte for byte; a name the pack holds takes the play to `_Play2`; the game's
own intro copied by the Build and renamed for a play reads back with the play's name in its switches), the play,
recovery and manager tests brought to the play names, and the viewer, repo and node suites.

Known gaps: not played in the game yet. A build whose lightmaps could not go inside the map ships a texture cache under
its own name: a pack that carries a different build's cache of that name beside its folder still stops a play, with
the install step's message.

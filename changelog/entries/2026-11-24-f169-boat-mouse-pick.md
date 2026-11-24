### F-169 recorded: over a boat, the mouse puts the cursor in the hold under the deck's stop

A user's report on a boat project (a building over water, a walkable hold under its deck), written into the
[findings register](../../research/findings-register.md) as F-169. The game's mouse pick, read from the decompiled
scripts, skips walls and keeps a first hit lower than the wheel's stop. With water round the hull nothing catches the
ray, so a pointer just off the deck's edge, or on the cabin roof near its edge, lands in the hold. The finding names
two ways out, neither tried. No tool changed.

Checked: the decompiled `GetMousePickActor` and the cursor-volume cursor classes read; the project's last build read
offline (the building's listings by the game editor's rule, the live cursor volumes over the boat, the deck pieces'
flags); the `repo` suite. Not played.

### A room's walls name a look the catalogue does not hold by its donor's mesh, as a wall's own section does

Editor follow-ups, stage P4, item 3.16, decision D6. A change of what the editor says.

The Room section (a drawn room picked whole) said "Walls: made from numbers" for walls whose look neither the editor's
own looks nor the walls' catalogue holds (a catalogue not read, or a donor it does not list), where each of those
walls' own Wall section names the look by the last part of its donor's mesh name. Now both say the same: one helper in
[made_panel.js](../../tools/viewer/web/made_panel.js), `wallLookName`, gives the Wall section and the room's walls
their look name through [looks.js](../../tools/viewer/web/looks.js)' `madeLookName`, with the donor's mesh name. The
Floor, Roof and Ground sections and a room's roof still say "made from numbers" for such a look: they give no mesh
name, as before (D6 names only the Room section's walls).

[browser_walls.py](../../tools/viewer/tests/browser_walls.py)' `room-buttons` check gives a room's walls the look of
one of the police station's walls, forgets the walls' catalogue and refuses its read, and compares the Room section's
look line with the Wall section of one of the walls once the room is ungrouped. It failed before this change ("Walls:
made from numbers" against "Wall · Core_384SBack_FRACTURED").

Checked: `room-buttons`, `walls` and `looks` pass on the police station; the node suite and `web_names` clean; the
twenty-edit recording the same as on the stage's start commit (52 steps: no room of it has such a look).

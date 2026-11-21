### A made piece's look name worked out in one place: looks.js' madeLookName

Editor follow-ups, stage P4, item 3.16, its first part. Nothing the editor says changes here; the next change (decision
D6) is the one that does.

- [looks.js](../../tools/viewer/web/looks.js) has `madeLookName(look, entry, meshName)`: the look's own name, else the
  catalogue entry's, else the last part of the donor's mesh name when the section knows it, else "made from numbers".
  [looks_test.mjs](../../tools/viewer/tests/looks_test.mjs) has its cases (it failed before: no such export).
- [made_panel.js](../../tools/viewer/web/made_panel.js)' Wall, Floor, Roof and Ground sections call it in place of the
  three wordings they had, each giving what it gave before (the Wall section its catalogue entry and its donor's mesh
  name; the Floor, Roof and Ground sections their look alone). The Room section's helper, which had the same name, is
  `rootLookName` and calls it too, giving a wall's catalogue entry but not yet its mesh name.

Checked: the node suite (with the new cases) and `web_names` clean; the twenty-edit recording the same as on the
stage's start commit (52 steps); browser checks `walls`, `looks` and `room-buttons` pass on the police station.

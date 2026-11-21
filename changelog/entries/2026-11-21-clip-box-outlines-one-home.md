### A clip's floor-box outlines built in one place

Editor follow-ups, stage P4, item 3.17 (the part left: `sentence` already lives in `dom_words.js`). Nothing the editor
does changes.

[clipboard.js](../../tools/viewer/web/clipboard.js)' `startPlacing` (the preview a click places) and `copyDragBegin`
(a copy's stand-in dragged off with Shift) each built the outlines of the floor boxes that come with a clip, line for
line the same. One function, `addBoxOutlines(group, clip)`, builds them for both. (A snapshot always has its
`volumes`, so the stand-in's taking a clip without them as none changes nothing.)

Checked: `web_names` clean; the node suite; the twenty-edit recording the same as on the stage's start commit (52
steps); browser checks `groups`, `copy-drag`, `box-select`, `floor-boxes`, `map-buildings`, `library`, `prefabs`,
`builder` and `paste-buildings` pass on the Bar.

### The Map grid's panel stands beside the Selected piece panel (KB-8 fixed)

With a piece selected, the rail's **Map grid** opened its panel at the same place as the Selected piece panel, which
covered it, so the grid panel's **Done** could not be clicked. Now, while the Selected piece panel is shown, the grid
panel stands to its left (a rule in [the stylesheet](../../tools/viewer/web/style.css), with its twin for windows up
to 800 pixels wide, where the Selected piece panel is narrower). The tool keeps the selection as before, and a piece picked while the
tool is on opens its panel beside the grid's. At 1024 pixels wide the two panels and the rail still fit side by side
(the grid panel from x 400 to 700, the Selected piece panel from 712), so the plan's fallback (hiding the Selected
piece panel while the tool is on) is not needed.

KB-8 leaves [KNOWN-BUGS.md](../../KNOWN-BUGS.md).

Checked: a new browser check, `grid-panel`
([browser_editing.py](../../tools/viewer/tests/browser_editing.py), in `--all`'s editing run): at 1280 and at 1024
pixels wide, with the piece picked before the tool is opened and with one picked while it is on, the panels' boxes
do not meet and miss the rail, a click at the middle of **Done** lands on it, puts the tool away and keeps the
selection. It failed before the change (the two panels at the same box, x 968 to 1268 at 1280 wide). The `clear-map`
check no longer clears the selection first (it did so only to get round this bug): run after `typed-pose`, which
leaves a piece selected, it clicks **Done** with that piece's panel shown; before the change that click timed out.
`--only grid-panel,typed-pose,clear-map` pass.

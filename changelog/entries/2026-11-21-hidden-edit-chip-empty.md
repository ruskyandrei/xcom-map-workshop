### The hidden edit chip keeps no words

The exploratory test after the refactor reported that the header said "not saved" after Reset all with no project
open and nothing changed. It did not show: the edit chip was hidden, as it is before any edit. But a hidden chip kept
its last words, "not saved", and the test read the chip's text with Playwright's `inner_text`, which gives a hidden
element's text too. Now the chip holds no words, and no title, while it is hidden
([piece_status.js](../../tools/viewer/web/piece_status.js)), so the page's text says only what is shown. What a user
sees is unchanged.

Checked: the `reset-all` browser check ([browser_editing.py](../../tools/viewer/tests/browser_editing.py)) asserts that
after a Reset all that leaves nothing changed, with no project open, the chip is hidden with no words and no title. It
failed before the change (hidden, with "not saved"). Tried on a test server, and the chip never showed with nothing
changed: a group alone, a move, a clear and a landing zone copy, each reset with no project open (the group and the
move undone and redone after), and a project closed with changes. `--only reset-all,typed-pose` pass.

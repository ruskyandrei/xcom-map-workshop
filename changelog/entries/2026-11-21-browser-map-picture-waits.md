### The Map picture check's fixed waits: the wheel's turns counted and the server's answer drawn

Editor refactor, stage P10. In [browser_map_picture.py](../../tools/viewer/tests/browser_map_picture.py), its four
fixed waits went:

- **The wheel:** each run of turns now waits until the frame canvas has had every turn (a counting listener the check
  adds after the dialog's own), instead of 300 ms after the frame first came under 800 pixels; the frame's own waits
  (1,600 wide, 32 wide, under 800) stay.
- **The result as the game shows it** (three waits of 900 ms): the dialog draws the crop at once on each change of the
  frame and the server's answer for it a moment later, dropping an answer for an earlier frame. The check wraps the
  result canvas's `drawImage` to note which it drew last, and waits for the server's answer before reading the pixels.

Checked on a test server: the check run five times in a row, all passing; `browser_smoke.py --all` twice (its
`map-picture` run).

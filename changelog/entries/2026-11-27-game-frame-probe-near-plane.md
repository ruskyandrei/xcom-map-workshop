### The Game look's frame check works on maps framed from far away

browser_smoke.py's `map-lights` check put its test square 10 units in front of the camera. On a map whose view frames
from far away (DLC2_3_Furies: the camera's near plane at 42 units) the square fell behind the near plane and the check
failed before reaching its own questions. The square now stands at four times the near plane (10 units at least), sized
to look the same.

- Where: [browser_smoke.py](../../tools/viewer/tests/browser_smoke.py) (`GAME_FRAME`).
- Checked: `map-lights` and `lights` pass on URB_Bar of export 45 on a test server.
- Known gaps: not run on Furies here (its export is in the agent's scratch cache, gone with its worktree).

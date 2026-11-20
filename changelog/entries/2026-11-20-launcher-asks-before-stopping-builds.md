### The launcher asks before it stops an editor that is building, and knows when the editor it started is up

Review finding 47. [xcom_editor.cmd](../../xcom_editor.cmd) with no argument (a double-click) restarts the editor,
and that was a `taskkill /F`: a running bake or a queue of builds died without a question.

- **Before it stops a running editor** (restart, stop), it asks the editor whether it is building:
  [launch_check.py](../../tools/viewer/launch_check.py) `busy` reads `GET /manager.json` (each project's `building`:
  a build from the build window or the queue's) and `GET /manager/queue.json` (a queue running, between its builds
  too). When something is building, or the editor does not answer, it says what and asks "Stop the editor anyway?
  [y/N]". It stops the editor only on a yes. Declined, a restart opens the running editor in the browser instead.
- **After the stop**, the launcher checks the editor actually stopped. It failed if `taskkill` failed, and it fails
  when the port is still held after ten seconds, instead of saying "Stopped" and starting a server that can't bind.
- **After a start** it waits until the editor answers on its port (`launch_check.py wait`, up to 5 minutes, saying
  every 15 s that it waits). It no longer looked for a listening port for 15 s, which said "did not start" of a main
  server still preparing its cache. A server whose process ended (a port in use, a bad argument) is said so at once:
  the server and the helper are both children of the launcher's cmd.
- **A `VIEWER_CACHE` ending in `\`** gets it doubled, where it escaped the closing quote.
- **`VIEWER_ARGS`** adds arguments to `serve` for tests: scratch `--projects`, `--builds`, `--squad`, `--dry-play`,
  `--install`.

Checked:
- [test_launch_check.py](../../tools/viewer/tests/test_launch_check.py) runs `busy` against stand-in servers: idle,
  building, a queue between builds, no queue, an error, and nothing listening. It runs `wait` against a server that
  listens late, against nothing, and against a server whose process ended.
- By hand on port 8792 with scratch folders and a `VIEWER_CACHE` ending in `\`:
  - `start`, `status`, `restart` and `stop` of an idle editor;
  - a stand-in "viewer.py serve" that is building, with no answer, "n" (to stop and to restart) and "y";
  - a server that refuses its arguments, which was reported in about a second.

Not checked: the port still being held after a stop, which can't be made to happen on purpose.

### Follow-ups to the Build fixes: a test server never takes real builds for abandoned, the server starts with any folder name

Three things the Build fixes' report left (review findings 49 and 35), and a test made steady.

- **The prune at start.** It treats a variant no project ships as as abandoned and strips its work folders after
  14 days. A server given scratch projects beside the settings' builds folder (`viewer.py serve --projects` alone)
  would have taken every real variant for abandoned. Such a server now prunes with no projects known: each variant
  keeps its newest work folders whole. See [builds.py](../../tools/viewer/builds.py) (`orphans`) and
  [viewer.py](../../tools/viewer/viewer.py).
- **Start-up output.** The server's start-up lines name the projects folder. When its output is redirected, a
  folder name the system's code page lacks now shows with a stand-in instead of stopping the server with a
  `UnicodeEncodeError` ([viewer.py](../../tools/viewer/viewer.py) `main`).
- **A manifest note.** The unbaked lights' note in [native_lights.py](../../tools/bake/native_lights.py) no longer
  points at an open experiment run. It says what the manifest records.
- **A steadier test.** [test_buildqueue.py](../../tools/viewer/tests/test_buildqueue.py)'s second Resume could meet
  the queue moved on between its view and its request, which is a stale request. The test now reads the view again,
  as the page does; the product was right.
- Checked:
  - a new test in [test_builds.py](../../tools/viewer/tests/test_builds.py), which fails without the switch;
  - `viewer.py settings` run with a cp1252 output;
  - the queue test passed three runs in a row;
  - the native_lights and server spot tests pass.

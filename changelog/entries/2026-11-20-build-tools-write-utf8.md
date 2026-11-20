### A build runs from a folder whose name the system's code page lacks

Review finding 35. The server reads a build's output as UTF-8, and the Build reads each tool's the same way, but
nothing told those Python children to write it: a piped Python child writes in the system's ANSI code page. The Build
echoes each tool's command line, which holds the builds and work folders under Documents, so a user name the code page
lacks (Cyrillic or Chinese on a Western system) stopped a build at its first tool with `UnicodeEncodeError`, and an
accented one gave garbled logs.

- [procs.py](../../tools/viewer/procs.py): `utf8_env()` gives a child's environment `PYTHONUTF8=1` and
  `PYTHONIOENCODING=utf-8`, and `launch`, which starts every build, prefab-test build and queued build, uses it. Every
  process below a build inherits it.
- [build.py](../../tools/editor/build.py): `_run` starts each tool with it.
- Checked: [test_procs.py](../../tools/viewer/tests/test_procs.py) launches a child from a folder with a Cyrillic name
  and [test_build.py](../../tools/editor/tests/test_build.py) runs a tool through `Build._run` from one, each with the
  test's own environment stripped of both variables. Both failed before the change (`cp1252`, `UnicodeEncodeError`).
- Not changed here: exports, library scans and the cache job still start with a plain `Popen` (finding 48).

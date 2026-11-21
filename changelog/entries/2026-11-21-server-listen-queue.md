### The editor's server lets connections that come at once wait instead of refusing them

The server's listen queue was Python's default of 5 (follow-ups item 3.26): a page or a script that opened many
connections at once, fetching the page's modules, had Windows refuse the sixth and those after it while the server was
still taking the first. [viewer.py](../../tools/viewer/viewer.py)'s `LocalServer` now queues 64.

Checked: the new test in [test_server_guard.py](../../tools/viewer/tests/test_server_guard.py) opens 40 connections
to a server that has not yet taken one (failed before: the sixth was refused); the viewer's server guard tests pass.

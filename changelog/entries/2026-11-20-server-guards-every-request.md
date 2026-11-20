### The server checks every request's Host, refuses network paths in its static routes and answers every failure

Review findings 45 and 46, in [viewer.py](../../tools/viewer/viewer.py).

- **Static routes** (the page's files, `/cache/<map>/`, `/cache-library/`): `contained` refuses a part that is
  absolute, names a drive or a network share, starts with a slash or backslash, or holds a colon or a NUL, before
  anything is joined, and compares the joined path with the root without resolving it. Before, `GET
  /%5C%5Chost%5Cshare%5Cf`, `/C:/Windows/win.ini` and `/cache/<map>///host/share/f` were resolved (so opened) before the
  containment test refused them. Only the one slash a request path starts with is taken off.
- **Host and Origin on every request**: `parse_request` checks them once, before any route, for reads as well as
  writes. A page elsewhere, or one that rebinds its name to 127.0.0.1, now reads nothing (the projects, the settings,
  `/play.json`) and gets a 403 with the reason. 127.0.0.1 and localhost with the server's port both pass, as the
  release launcher, the browser tests and the guide's shots use them. A refused request's body is read, so a kept-alive
  connection's next request starts clean.
- **Every failure answered**: one wrapper (`answer`) around every route turns an exception a route does not answer into
  a JSON 500 with its text (the traceback still goes to the server's window). Before, anything but a `ProjectError` on
  five route groups (a Save on a full disk, a failed export start, a game folder that fails to load) dropped the
  connection with no reason.
- **Content-Length**: `body_length` checks a raw body's length on every route that reads one (400 for a value that is
  not a whole number of 0 or more, 413 over the route's limit). A bad value raised with no answer, and a negative one
  made `rfile.read(-1)` hold the handler's thread until the client closed.
- Checked: [test_server_guard.py](../../tools/viewer/tests/test_server_guard.py) (new) replays the three paths and three
  more over HTTP (404), checks `contained` touches nothing on disk for twelve refused forms, checks Host and Origin on
  reads of every kind of route, a route that raises (500 with its text, and the server goes on), and bad and negative
  lengths on two raw-body routes. The viewer suite passes.

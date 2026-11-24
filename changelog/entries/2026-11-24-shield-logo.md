### The editor's logo: a shield over the grid

Stage M1 of the prefab menus plan. The header's boxed X and MAP WORKSHOP give way to a single logo the user chose
from four mock designs on 24 November: a shield, the sign of cover, over four tiles of the map's grid, two of them lit.
It is original line art in the editor's colours.

- [logo.svg](../../tools/viewer/web/logo.svg) (new): the logo, 32 units square, its colours written in it.
- [index.html](../../tools/viewer/web/index.html): the header's brand is the logo, 30 pixels high, titled "XCOM Map
  Workshop"; the page's tab icon, empty until now, is the same file.
- [style.css](../../tools/viewer/web/style.css): `.mark` and the wordmark's rule under 1100 wide go; the brand stays
  hidden under 800 wide, as it was.
- [viewer.py](../../tools/viewer/viewer.py): the server's own table of file types gains `.svg` (the Windows registry
  can map a type wrongly; it is why the table exists). The main server needs a restart for it.

Checked: the browser check `project-menu` ([browser_smoke.py](../../tools/viewer/tests/browser_smoke.py)) now also
finds the logo drawn on the bar, the tab icon naming logo.svg and the file served as `image/svg+xml`; `header` and
`text-select`. Looked at on a test server 1280, 1024 and 800 wide on Bar: the bar overflows at none, no page error.
Not done: the guide's pictures of the header, which the update-guide skill retakes after the build.

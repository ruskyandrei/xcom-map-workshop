### No gap in a group's section from the hidden prefab button

The placed prefab's **Open … in the builder** button (stage M4 of the prefab menus plan) stood in a row of its own that
stayed in the page when the button was hidden: an empty row, 0 pixels high with its 6-pixel margin, so every other
group's section had a small blank gap. Found by the guide pass.

- [index.html](../../tools/viewer/web/index.html) `groupPrefabRow` and [groups.js](../../tools/viewer/web/groups.js):
  the row itself is hidden when the group is no placed prefab the library still has, not the button alone.

Checked: in a plain group of two of Bar's pieces the row is not drawn (`display: none`); the browser checks `groups`
and `prefabs` (the placed prefab's group still shows Open Smoke prefab in the builder), on a test server with fresh
stores.

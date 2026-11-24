### The Build menu no longer shows over the open Add panel

With the rail drawn over the other panels (so the Views list shows over the dock), the Build menu that opens on Add's
hover stood over the open Add panel's list. The user: "when the add panel opens the side panel should not be shown
anymore".

- While the Add panel is open the Build menu doesn't show ([style.css](../../tools/viewer/web/style.css): hidden while
  the Add button is lit, as it is with the panel open); with the panel shut it shows on Add's hover as before. The Add
  button's tip ([index.html](../../tools/viewer/web/index.html)) and the
  [guide](../../tools/release/guide/guide.html) say the Build menu shows while the Add panel is shut.

Checked: the browser check `rail-lists` ([browser_controls.py](../../tools/viewer/tests/browser_controls.py)) now also
hovers Add with the panel shut (the menu visible) and open (hidden); the browser checks `builder`, `walls`, `adding` and
`library`; the repo, node and viewer suites.

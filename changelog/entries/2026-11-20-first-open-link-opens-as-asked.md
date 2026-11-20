### A project link to a map not prepared yet opens the project once the map is

Review finding 7. An address naming a project and a mission on a map not exported yet prepared the map and then
landed on the map alone. The browser's "ready" used the callback of a switch of map, which drops the project, the
mission and the layout.

- [app.js](../../tools/viewer/web/app.js) keeps the map the address asked for when it isn't prepared. Once the map
  browser has prepared that map, the page opens the address as it was: its project, mission and layout too. Nothing
  is open meanwhile, so nothing is left behind.
- Another map chosen by hand while it prepares is a switch of map, as before, and opens alone. An export that fails
  and is tried again opens the address as asked too.
- Checked: [browser_documents.py](../../tools/viewer/tests/browser_documents.py) `first-open` on two test servers:
  - warm, with the map list answered as if URB_Bar were not prepared and its export stood in for: the project and its
    mission open, with the edits as saved;
  - an export that fails, then Prepare and open again;
  - another map chosen while it prepares;
  - cold, a server on the same projects folder and an empty scratch cache: URB_Bar really exported (26 s), then the
    project opened with the same edits.

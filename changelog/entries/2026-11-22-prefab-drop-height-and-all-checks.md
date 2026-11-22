### A prefab placed under a snap steps its height from its grid base too; every browser check in the full run

Since 21 November 2026 a prefab of pieces with a pose rule (a car, a door) is no longer held to whole tiles whatever
the snap: it follows the snap setting, smoothly with snap off. Under a snap its place across stepped from its pivot,
but its height was taken from wherever the click landed, so a car placed under tile snap stood a little off its pose
rule. Now a prefab from the library also steps up and down in the snap's steps from its pivot, which stands on the
tile grid's base, as its place across does.

- [clipboard.js](../../tools/viewer/web/clipboard.js) `dropTarget`: a library prefab's height in the snap's up steps.
- [browser_smoke.py](../../tools/viewer/tests/browser_smoke.py): the `prefabs` check expects a prefab of cars not to be
  held to whole tiles, and places its car prefab in another map under tile snap, where its pieces keep their pose
  rule; the `--all` run's police run takes the `free-handles` and `texture-mapping` checks, which it refused to start
  without.

Checked: the browser checks `prefabs`, `prefab-effects`, `adding`, `copy-drag` and `floor-placing` on a fresh test
server; `browser_smoke.py --all` before the change: every run but `whole` (its `prefabs` check, fixed here) and `play`
(it refuses while a game is open) passed.

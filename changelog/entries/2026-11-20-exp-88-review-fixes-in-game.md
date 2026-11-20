### EXP-88: the review fixes played in the game; a cover block grouped with a made wall keeps its cover (F-143)

The review fixes that change what reaches the game, played unattended in the lab copy (LWR) on branch
`editor-review-fixes`: [EXP-88](../../research/experiments/EXP-88-review-fixes-in-game.md). No product code changed.

- [exp88_projects.py](../../tools/editor/examples/exp88_projects.py) makes the three projects (URB_Bar's made walls
  in break groups, URB_HighwayFallen's copy with "Mouse picks it" off, CsmallScout_Farm's changed lights and moved
  tractor); the prefab of check 5 was made in the page.
- Passed: a made wall's group with one prop and with two props (review finding 36), a copy with the mouse flag off
  builds and loads (finding 37), changed lights build and show (finding 37, built baked: a quick build would not show
  them), a moved piece's shadow after a baked Build (finding 44), a prefab with a made wall and a broken copy through
  Test in game (finding 6).
- Failed: a cover block grouped with a made wall builds and loads, but keeps its cover when the wall goes: the block
  is built invincible and the wall's columns reach it only by damage. Recorded as
  [F-143](../../research/findings-register.md), open; not fixed here.
- Unclear: whether the game's cursor passes through the copy with the mouse flag off; the hidden run's cursor snaps to
  tile floors and never rose onto either car.
- Checked: `run_tests.py repo` and `gather_changelog.py --check`.

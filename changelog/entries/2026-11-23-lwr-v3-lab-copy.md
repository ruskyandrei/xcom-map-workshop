### A lab copy for Long War Rebalance v3: XCom-Enemy-Unknown.Lab3

Checks of LWR v3 features (such as the map info a map pack's card now carries) had only the user's own LWR v3 copy
to run in, which holds their campaign. A fourth copy of the game now sits beside the others: the LWR v3 lab copy,
`<Steam common>\XCom-Enemy-Unknown.Lab3`, with LW Rebalance v3.00.00 beta 17.

- It was copied from the user's LWR v3 copy without its saves, logs, screenshots or map packs, but with its settings
  (video, resolution, LWR Settings). Its marker `XComLab-copy.txt` has the line `copy=lab3`, so the launch wrapper
  keeps its settings, saves and logs inside it, as for the other copies.
- [switch_install.ps1](../../tools/lab/switch_install.ps1) knows it: `status` lists it, and `lab3` makes it the copy
  Steam runs. Hidden runs need no switch: `hidden_game.py --game <the .Lab3 folder>`
  ([hidden_game.py](../../tools/lab/hidden_game.py)'s note says so).
- The game-test skill ([SKILL.md](../../.claude/skills/game-test/SKILL.md),
  [SETUP.md](../../.claude/skills/game-test/SETUP.md)) says which copy a check runs in: the LWR 2.x lab copy, or this
  one for LWR v3. It also says the user's own LWR v3 copy (`copy=lwr3`) is never run, staged into or changed unless
  the user asks.

Checked: all 163 files of the beta 17 zip's Config, CookedPCConsole and Localization match the copy. The one
exception is `Engine.upk`, which is the zip's console version, as in the user's copy. A checksum list of the whole copy compared
with the user's copy's differs only by the files left out and the marker. `switch_install.ps1 status` reports
`parked.Lab3=lab3`. A hidden run on URB_Bar reached the battle: the game showed "LWR v3.00.00 Beta 17", and
`Mutate LWRMapTest Info URB_Bar` answered `AlienDensity = Moderate (DefaultMaps.ini)`.

Known gap: the copy is not updated by itself when a new beta comes out. The new beta has to be laid over it as over
the user's copy.

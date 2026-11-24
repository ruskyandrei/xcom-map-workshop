### F-165 recorded: eleven base maps' scripts act at moments of the battle, and a clear leaves them

Asked which of a map's scripts a Clear map leaves, the install's 99 base maps were read for script events that
neither a place nor a name starts (every sequence event of a class other than a touch, a remote event, the level's
load and the after-a-load event).

- **Recorded as [F-165](../../research/findings-register.md)**: 88 maps have none; the eleven that do, with their
  event classes (the alien bases' closing narration when the mission is won, the Chryssalid Hive's and the Temple
  Ship's turn-by-turn mission scripts, single events on a battleship, Gangplank and Highway Construction, the HQ's
  own). The pod-reveal event on CSmallScout_DirtRoad is a hook that fires a remote event nothing in the map listens
  for; the pod reveal itself is the game's, on every map.
- **Left as it is**, at the user's word: a clear takes out the triggers and sight points (F-159) and leaves these
  events on. No tool or editor behaviour changes.

Checked: read offline with the viewer's package reader and [kismet_links.py](../../tools/upk/kismet_links.py)
(AlienBase01's victory event and DirtRoad's pod-reveal event followed to what they lead to); the `repo` suite.

Known gaps: none of it was played. What five of the maps' single events lead to was not read (CBattleship_02, Act1_IntroLevel,
DLC1_3_Gangplank, the two Highway Construction maps).

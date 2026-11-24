### F-170 and KB-26 recorded: a made building's volumes are stretched copies of brushes that need not be boxes

A user's boat on EWI_ChryssalidHive cut away to its hold with the cursor on some deck tiles, whatever the wheel's
stop. A hidden run's readbacks put it down to the cut-out box: there the cursor and its visibility point counted as
in no building, so the boat was hidden as a building standing between the camera and the cursor. The Build had made
the boat's floor volumes and building volume by stretching the map's own `XComFloorVolume_71` (a five-sided prism)
and `XComBuildingVolume_0` (a notched brush), as `buildings.floor_template` and `building_template` never ask for a
box brush. Written into the [findings register](../../research/findings-register.md) as F-170, with how far it goes
(25 of 78 maps for the floor volume, 5 for the building volume), and into [KNOWN-BUGS.md](../../KNOWN-BUGS.md) as
KB-26 until it is fixed. F-169, the mouse's pick into the boat's hold, now says it is to be looked at again after the
fix. No tool changed.

Checked: a hidden run in the LWR v3 lab copy (the cursor's, the visibility point's and the cut-out box's values on
cut and whole tiles; shots); the build's volumes and their brush polygons read offline; every installed map's
templates surveyed with the Build's own pickers; the `repo` suite.

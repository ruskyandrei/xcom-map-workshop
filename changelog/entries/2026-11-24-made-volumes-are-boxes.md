### A building made in the editor is a box in the game too: its floor and building volumes take box brushes

The Build made a building's floor volumes and building volume by stretching one of the map's own over each box, and
took the largest without asking for a box brush. On 25 of the 78 maps that can take a made building the floor volume
it took is not a box (URB_Bar, URB_PoliceStation, URB_TruckStop, the Abductor maps), and on 5 the building volume is
not (EWI_ChryssalidHive, URB_Trainyard, URB_IndustrialOffice, URB_GasStation_EWI, CSmallScout_Roadhouse). The game
tests what is inside a volume by its brush, so part of such a building was outside it: with the cursor there, the
game's cut-out box took the building for one standing between the camera and the cursor and cut it down to its first
floor ([F-170](../../research/findings-register.md)). KB-26 is fixed and taken out of
[KNOWN-BUGS.md](../../KNOWN-BUGS.md).

- [buildings.py](../../tools/bake/buildings.py): `floor_template` and `building_template` take a volume whose brush
  is a plain box first (`box_brush`, `scene_metadata.plain_box`). Where a map has none of the class (DLC2_1_Portent,
  URB_CemeteryGrand and URB_Trainyard for floor volumes), `box_source` finds another of its volumes with a box brush,
  and `clone_volume` gives the clone that volume's model and its brush component's saved collision (`BrushAggGeom`,
  `shaped_component`), placed by that model's bounds; the model is shared, as the rebuild volumes share theirs. A map
  building's own volume stretched by an edit takes a box the same way when its brush is not one (the report's
  `boxBrushFrom`), and so does the plain volume put in for a stretched notched floor volume.
- [test_buildings.py](../../tools/bake/tests/test_buildings.py): the bar's templates are boxes; a boat's three
  floors made on EWI_ChryssalidHive and two floors on URB_Trainyard (the borrowed box) read back as boxes over the
  boxes asked for, each brush component with the box's collision.
- [test_building_edits.py](../../tools/bake/tests/test_building_edits.py): the plain volume that replaces a
  stretched notched one on the bar is a box; the hive's notched `XComBuildingVolume_0`, stretched, is a box over its
  floors' union with a box's collision.

Checked: the `bake` and `repo` suites; the BoatAbduction project built quick with the fix (its four floor volumes and
its building volume boxes over its boxes, read offline); a hidden run of that build in the LWR v3 lab copy (see
F-170). A map built before this keeps the old volumes until it is built again.

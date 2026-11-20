### The copier's guess at object references against the typed walk: listed, and kept (editor refactor, stage B2)

The copy tool's `Walker.refs` ([native_copy.py](../../tools/bake/native_copy.py)) takes every array of 4-byte values
for object references unless its name is on a list (`NOT_REFERENCES`); the typed walk
([typed_props.py](../../tools/upk/typed_props.py)) names a reference only where the game's property types say one is.
The stage would have switched the copier to the typed walk if every place where the two differ were a wrong guess and
no copy of the ten Builds changed. Over every export of URB_Bar, TempleShip, URB_PoliceStation and CB2_MP_Blank:

- the typed walk names no reference the guess lacks (30,810, 23,807, 31,671 and 2,990 references named by both);
- the guess names more: 19,439, 13,772, 20,292 and 4,914 places, in 72, 51, 47 and 35 arrays. Nearly all are the
  float tables of the particle modules' curves (`LookupTable`: 19,186 places on the Bar), then other arrays of floats
  (`SoundNodeRandom.Weights`, `ParticleSystem.LODDistances`, `AnimNodeBlendList.TargetWeight`,
  `SoundNodeMixer.InputVolume`) and arrays of whole numbers (`AnimSequence.CompressedTrackOffsets`,
  `PhysicsAsset.BoundsBodies`, `XComVisGroupData`'s `ChildGroups`, `XComBuildingVolume`'s floors'
  `ExternalMeshGroupIndices`): wrong guesses. A few of those numbers fall in the range of object indices, but none of
  their classes is cloned by a copy (an anim sequence, a physics asset, the world's vis group data), and a building's
  mesh group indices are 0 or 1;
- one array the guess has right: `VisGroupActor.DependentOn` (13 places on the Bar, 4 on TempleShip, 18 on the police
  station). Its class is UnrealEd's, an editor's, which no cooked script package holds, so the typed walk can't type
  it; every value of it names a VisGroupActor of the map;
- the dominant light's component, whose properties stand after its leading shadow map, is refused by the guess (it
  walks from where an export's properties usually start) and read by the typed walk.

So the switch stops: the typed walk alone would lose `DependentOn`'s references. Whether the copier should take the
typed walk where it types a property and its guess only where it can't is left as a decision. Nothing of the product
changed; [test_schema.py](../../tools/upk/tests/test_schema.py)'s comparison of the two on the Bar now says so and
checks that every `DependentOn` value names a VisGroupActor and that the schema does not know the property.

Checked: the upk suite.

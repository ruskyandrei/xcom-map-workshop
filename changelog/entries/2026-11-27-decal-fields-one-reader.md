### A decal's receivers have one reader

The copier's list of the references in a decal component's native data ([native_fields.py](../../tools/upk/native_fields.py)
`_decal_component`, which a piece of another map's closure goes through) now takes them from the decal reader of
export 46 ([decal_records.py](../../tools/upk/decal_records.py) `receivers`, which gives each receiver's component and
shadow maps with their places) in place of a walk of its own, as ARCHITECTURE.md's "one home" asks.

- Checked: on all 3,351 decal components of the install's 153 map packages, the fields the old walk and the new give
  are the same; [test_native_fields.py](../../tools/upk/tests/test_native_fields.py) (the upk suite) and the bake
  suite's transplant tests pass.

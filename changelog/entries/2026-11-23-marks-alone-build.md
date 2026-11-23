### A project whose only change is a diagonal cover mark builds

The user's first try of the Diagonal cover view on the tutorial map stopped at "Make the edit in the map":
[native_copy.py](../../tools/bake/native_copy.py) refused to run with "give --copy, --copies (or --actor with
--at)", since the lanes it counts as an edit did not include the project's marks. A native edit with marks or removed
marks now counts.

Checked: [test_native_copy.py](../../tools/bake/tests/test_native_copy.py) (an edit of marks alone, and of a removed
mark alone, reaches the build); the user's tutorial map project built quick into a scratch folder (its mark written at
tile (44, 8, 0), its corner warned of as having no wall).

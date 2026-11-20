### The modules split off the compiler are held to the families' rule

[structure.json](../../tools/repo/structure.json)'s `compiler families` now also lists `compiler_tables.py`,
`native_edit.py` and `piece_lookup.py`, so the structure test fails if any of them imports the compiler, as it does
for the edit families; [ARCHITECTURE.md](../../ARCHITECTURE.md) section 4 says so. None imports it today.

Checked: the repo suite passes (the family rule over the twelve modules listed).

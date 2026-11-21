### A texture's or lightmap's compressed bulk payload is read by the one chunk-header reader

[texture.py](../../tools/viewer/texture.py)' `decompress_payload` (every texture the exporter reads, and the bake's
lightmap, shadow-map and albedo modules) read a compressed bulk payload's header and block table its own way, beside
[decomp.py](../../tools/upk/decomp.py)' `read_chunk`, which says it is the one reader of a chunk header. It now takes
the header and the block table from `read_chunk` (the tag, the block size, the table's two sums checked against the
header's before anything is decoded) and keeps what is its own: zlib or LZO by the flags, LZX refused, at most 512 MB
(`BULK_LIMIT`), the payload ending where its blocks end, each block decoded to its table's size. `read_chunk`'s
`ValueError` becomes the reader's `FormatError`, as its own refusals were. [ARCHITECTURE.md](../../ARCHITECTURE.md)'s
rule for readers of package bytes now names the readers V1 put the package's header, an export's native data and a
chunk header through (`upkinfo`, `Package.native`, `decomp.read_chunk`).

Checked: new tests in [test_damaged_packages.py](../../tools/viewer/tests/test_damaged_packages.py): an LZO and a zlib
payload decode; a block table whose packed or unpacked sizes do not add up, another tag, a block size of 0, a header,
a table or the blocks cut short, bytes after the blocks, a total past the limit and LZX are each a `FormatError`; a
block that decodes to another size than its entry is lzo1x's `ValueError`, as before. Every case gave the same kind of
answer before the change (only the words differ): it changes no answer. The three maps' exports (their textures go
through it) are byte for byte the same as before V1; the bake suite passes.

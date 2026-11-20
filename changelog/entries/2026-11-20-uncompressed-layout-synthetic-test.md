### The uncompressed-map layout tested on a made-up package

Review finding 62, its tools/upk item: the layout a map stored uncompressed is put in before it is written
(package_edit.compressed_layout) was tested only on URB_Bar of the install. [test_package_edit.py](../../tools/upk/tests/test_package_edit.py)
`SyntheticUncompressed` builds a small uncompressed v845 package (a summary with no chunks, a name and an export
table, five exports of 40 bytes to 1.3 MB) and checks, with no game file: every summary field kept but the flags
and the chunk table, PKG_StoreCompressed and LZO set, the header's tables as the first chunk, the export data cut
only where an export starts and in chunks of up to 1 MB (the export bigger than that alone in its own), 128 KB
blocks, the whole decoding to the package's bytes, an edit of it written compressed, and a package not laid out as
a cooked map refused.

The finding's other missing tests in these folders were there already: lzo1x and upkinfo.load on bad input
(test_bad_input.py), the copier's command line (test_native_copy.py) and a name new to the map
(test_native_lights.py).

Checked: the package-edit tests.

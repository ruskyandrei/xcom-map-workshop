"""The helpers the upk suite's tests share (review finding 58: a fixtures module per suite, rather than tests that
import other tests). Named for its suite, as file names are unique across the repository (the bake suite's is
fixtures.py)."""
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import decomp  # noqa: E402
import package_edit  # noqa: E402
import upkinfo  # noqa: E402


def uncompressed(path):
    """The package at `path` as it would be stored uncompressed (DLC2_3_Furies.upk as LWR ships it): the summary with
    no chunks, PKG_StoreCompressed and the compression flags cleared, then the logical bytes."""
    raw = Path(path).read_bytes()
    h = upkinfo.summary(raw)
    full, _ = decomp.decompress_pkg(str(path))
    table = package_edit.chunk_table_offset(raw, h['chunks'])
    r = upkinfo.R(raw)
    r.u32(); r.u16(); r.u16(); r.u32(); r.fstr()
    head = bytearray(raw[:table])
    struct.pack_into('<I', head, r.o, int(h['flags'], 16) & ~package_edit.STORE_COMPRESSED)
    struct.pack_into('<I', head, table - 4, 0)
    lo = h['chunks'][0][0]
    out = bytes(head) + struct.pack('<I', 0) + raw[table + 4 + 16 * len(h['chunks']):h['chunks'][0][2]]
    if len(out) != lo:
        raise ValueError('the summary is not where the first chunk starts')
    return out + full[lo:]

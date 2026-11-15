"""Extract the largest available texture mip; decode to a browser PNG.

PNG is the portable first-slice path. Source pixel format/mip/cache provenance is
retained so GPU-compressed textures can be added without changing scene identity.
"""
import io
import hashlib
import struct
import zlib
from PIL import Image
from package import FormatError, Reader, cache_file
from mesh import bulk
import lzo1x


def decompress_payload(data, flags):
    if not flags & (2 | 16 | 128): return data
    if flags & 128: raise FormatError("LZX bulk compression is not supported")
    r = Reader(data)
    tag, block_size, compressed_total, total = r.unpack("4I")
    if tag != 0x9E2A83C1 or block_size == 0 or total > 512 * 1024 * 1024:
        raise FormatError("Invalid compressed bulk header")
    blocks = [r.unpack("2I") for _ in range((total + block_size - 1)//block_size)]
    out = bytearray()
    for compressed, expanded in blocks:
        raw = r.take(compressed)
        part = lzo1x.decompress(raw, expanded) if flags & 16 else zlib.decompress(raw)
        if len(part) != expanded: raise FormatError("Bulk block size mismatch")
        out.extend(part)
    if len(out) != total or r.pos != r.end or sum(c for c, _ in blocks) != compressed_total:
        raise FormatError("Bulk total size mismatch")
    return bytes(out)


def dds_header(width, height, fourcc, size):
    words = [124, 0x81007, height, width, size, 0, 1] + [0]*11
    words += [32, 4, int.from_bytes(fourcc.encode(), "little"), 0, 0, 0, 0, 0]
    words += [0x1000, 0, 0, 0, 0]
    return b"DDS " + struct.pack("<31I", *words)


def export_texture(p, index, out):
    r = p.native(index)
    bulk(r)  # source art
    mips = []
    for _ in range(r.count()):
        item = bulk(r)
        item["width"], item["height"] = r.unpack("2i")
        if item["size"] > 0 and item["count"] > 0 and not item["flags"] & 32:
            mips.append(item)
    if not mips: raise FormatError("No live texture mips")
    cache_guid = r.take(16).hex()
    mip = max(mips, key=lambda m: m["width"] * m["height"])
    w, h = mip["width"], mip["height"]
    if not 0 < w <= 16384 or not 0 < h <= 16384: raise FormatError("Invalid texture dimensions")
    cache_name = p.effective(index, "TextureFileCacheName")
    data = mip["data"]
    cache_path = None
    if mip["flags"] & 1:
        if not cache_name or cache_name == "None": raise FormatError("External texture has no cache name")
        if not cache_name.replace("_", "").isalnum(): raise FormatError("Invalid texture cache name")
        cache_path = cache_file(p.path.parent, cache_name)
        if mip["offset"] < 0 or mip["offset"] + mip["size"] > cache_path.stat().st_size:
            raise FormatError("Mip outside texture cache")
        with cache_path.open("rb") as f:
            f.seek(mip["offset"])
            data = f.read(mip["size"])
    source_hash = hashlib.sha256(data).hexdigest()
    data = decompress_payload(data, mip["flags"])
    fmt = p.effective(index, "Format")
    if fmt in ("PF_DXT1", "PF_DXT3", "PF_DXT5", "PF_BC5"):
        block = 8 if fmt == "PF_DXT1" else 16
        expected = max(1, (w+3)//4) * max(1, (h+3)//4) * block
        if len(data) != expected: raise FormatError(f"Mip byte count {len(data)} != {expected}")
        fourcc = {"PF_DXT1": "DXT1", "PF_DXT3": "DXT3", "PF_DXT5": "DXT5", "PF_BC5": "ATI2"}[fmt]
        image = Image.open(io.BytesIO(dds_header(w, h, fourcc, len(data)) + data)).convert("RGBA")
    elif fmt == "PF_A8R8G8B8": image = Image.frombytes("RGBA", (w, h), data, "raw", "BGRA")
    elif fmt == "PF_G8": image = Image.frombytes("L", (w, h), data).convert("RGBA")
    else: raise FormatError(f"Unsupported pixel format {fmt}")
    image.save(out)
    return dict(name=p.name(index), format=fmt, width=w, height=h,
                srgb=p.effective(index, "SRGB", True), compression=p.effective(index, "CompressionSettings"),
                cache=cache_path.name if cache_path else None, offset=mip["offset"], bytes=mip["size"],
                cacheGuid=cache_guid, sourceRangeSha256=source_hash,
                mipCount=len(mips), output=out.name)

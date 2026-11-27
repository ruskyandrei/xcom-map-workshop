"""A map's texture written for the page: a block-compressed one (DXT1, DXT3, DXT5, BC5) as a DDS file holding every
live mip as the game stores it (the page hands the blocks to the GPU as they are: game-likeness plan, A-S3b), any
other as a PNG of its largest mip. A caller that wants a picture (the map picture) asks for a PNG of any texture.

The record keeps the source's pixel format, mips and cache provenance, and says which file it wrote (`container`).
"""
import io
from pathlib import Path
import hashlib
import struct
import zlib
from PIL import Image
from package import FormatError, cache_file      # package puts tools/upk on the path: decomp, lzo1x
from mesh import bulk
import decomp
import lzo1x

BULK_LIMIT = 512 * 1024 * 1024      # the largest bulk payload decoded


def decompress_payload(data, flags):
    """A bulk payload's bytes, decoded when its flags say it is compressed (2 zlib, 16 LZO; 128 LZX is refused). Its
    header and block table are read by decomp.read_chunk, the one reader of a chunk header (its tag, block size and
    the table's two sums against the header's); what is the payload's own is checked here: a total of at most
    BULK_LIMIT, the payload ending where its blocks end, each block decoded to its table's size. A damaged payload is a
    FormatError."""
    if not flags & (2 | 16 | 128): return data
    if flags & 128: raise FormatError("LZX bulk compression is not supported")
    try:
        _, _, total, blocks, at = decomp.read_chunk(data, 0)
    except ValueError as error:
        raise FormatError(f"Invalid compressed bulk header: {error}") from None
    if total > BULK_LIMIT:
        raise FormatError(f"Invalid compressed bulk header: {total} bytes, more than {BULK_LIMIT}")
    if at + sum(c for c, _ in blocks) != len(data):
        raise FormatError("Bulk total size mismatch: the payload does not end where its blocks end")
    out = bytearray()
    for compressed, expanded in blocks:
        raw = data[at:at + compressed]
        at += compressed
        part = lzo1x.decompress(raw, expanded) if flags & 16 else zlib.decompress(raw)
        if len(part) != expanded: raise FormatError("Bulk block size mismatch")
        out.extend(part)
    return bytes(out)


BLOCK_FORMATS = {"PF_DXT1": "DXT1", "PF_DXT3": "DXT3", "PF_DXT5": "DXT5", "PF_BC5": "ATI2"}


def dds_header(width, height, fourcc, size, mips=1):
    """A DDS file's header for block-compressed data: the top level's size in bytes, and how many levels follow."""
    flags, caps = 0x81007, 0x1000                  # caps, height, width, pixel format, linear size; a texture
    if mips > 1:
        flags |= 0x20000                           # the mip count
        caps |= 0x400008                           # complex, mipmap
    words = [124, flags, height, width, size, 0, mips] + [0]*11
    words += [32, 4, int.from_bytes(fourcc.encode(), "little"), 0, 0, 0, 0, 0]
    words += [caps, 0, 0, 0, 0]
    return b"DDS " + struct.pack("<31I", *words)


def block_bytes(fmt, w, h):
    """The bytes of one level of a block format."""
    return max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * (8 if fmt == "PF_DXT1" else 16)


def _mip_data(p, index, mip, cache_name):
    """(a mip's bytes, decoded, the cache file it came from or None, the SHA-256 of what was read)."""
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
    return decompress_payload(data, mip["flags"]), cache_path, source_hash


def export_texture(p, index, out, container="png"):
    """Writes texture `index` beside `out` and gives its record. `container` "auto" writes a block-compressed
    texture as `out` with the suffix .dds (every live mip from the largest down, as long as each halves the one
    before), anything else as a PNG of the largest mip; "png" writes the PNG whatever the format."""
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
    data, cache_path, source_hash = _mip_data(p, index, mip, cache_name)
    fmt = p.effective(index, "Format")
    out = Path(out)
    levels = 1
    if fmt in BLOCK_FORMATS:
        expected = block_bytes(fmt, w, h)
        if len(data) != expected: raise FormatError(f"Mip byte count {len(data)} != {expected}")
        fourcc = BLOCK_FORMATS[fmt]
        if container == "auto":
            chain = [data]
            pw, ph = w, h
            for m in sorted(mips, key=lambda m: -m["width"] * m["height"])[1:]:
                if (m["width"], m["height"]) != (max(1, pw // 2), max(1, ph // 2)):
                    break
                level, _, _ = _mip_data(p, index, m, cache_name)
                if len(level) != block_bytes(fmt, m["width"], m["height"]):
                    break
                chain.append(level)
                pw, ph = m["width"], m["height"]
            levels = len(chain)
            out = out.with_suffix(".dds")
            out.write_bytes(dds_header(w, h, fourcc, len(data), levels) + b"".join(chain))
        else:
            image = Image.open(io.BytesIO(dds_header(w, h, fourcc, len(data)) + data)).convert("RGBA")
            image.save(out)
    else:
        if fmt == "PF_A8R8G8B8": image = Image.frombytes("RGBA", (w, h), data, "raw", "BGRA")
        elif fmt == "PF_G8": image = Image.frombytes("L", (w, h), data).convert("RGBA")
        else: raise FormatError(f"Unsupported pixel format {fmt}")
        out = out.with_suffix(".png")
        image.save(out)
    info = dict(name=p.name(index), format=fmt, width=w, height=h,
                srgb=p.effective(index, "SRGB", True), compression=p.effective(index, "CompressionSettings"),
                cache=cache_path.name if cache_path else None, offset=mip["offset"], bytes=mip["size"],
                cacheGuid=cache_guid, sourceRangeSha256=source_hash,
                mipCount=len(mips), output=out.name)
    if out.suffix == ".dds":
        info.update(container="dds", levels=levels)     # (a PNG's record is as it was)
    return info


def dds_png(path):
    """A DDS file the export wrote as PNG bytes (its largest level), for a GPU without the block formats."""
    with Image.open(path) as image:
        rgba = image.convert("RGBA")
    buffer = io.BytesIO()
    rgba.save(buffer, "PNG")
    return buffer.getvalue()

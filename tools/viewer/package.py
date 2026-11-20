"""Checked, read-only helpers for EW v845 properties and native payloads.

The older research CLIs stay independent. Object references remain package-local
indices; names are for diagnostics, never implicit cross-package substitutions.
"""
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "upk"))
import upkinfo
import props as legacy_props


class FormatError(ValueError):
    pass


# A package written away from the map it came from (a grown map in a build's work folder) reads the game's texture
# caches where they are: this file beside it names their folder. Lighting.tfc is 1.4 GB, and a hard link can't cross
# drives.
CACHE_FOLDER_LINK = "tfc-folder.txt"


def cache_file(folder, cache):
    """The texture cache `cache` (a name, as Lighting) of a package in `folder`: <cache>.tfc beside it, else in the
    folder its CACHE_FOLDER_LINK names."""
    path = Path(folder) / (cache + ".tfc")
    link = Path(folder) / CACHE_FOLDER_LINK
    if not path.exists() and link.is_file():
        return Path(link.read_text(encoding="utf-8").strip()) / (cache + ".tfc")
    return path


def link_caches(folder, caches):
    """Points the packages in `folder` at the texture caches in the folder `caches` (cache_file)."""
    Path(folder).mkdir(parents=True, exist_ok=True)
    # a folder that is itself pointed elsewhere (a staged map's, transplant.py) gives the folder it names
    link = Path(caches) / CACHE_FOLDER_LINK
    if link.is_file() and not any(Path(caches).glob("*.tfc")):
        caches = link.read_text(encoding="utf-8").strip()
    (Path(folder) / CACHE_FOLDER_LINK).write_text(str(Path(caches).resolve()) + "\n", encoding="utf-8", newline="\n")


# Observed on URB_Bar; other dominant-light classes are unverified and parse normally.
LEADING_SHADOW_MAP = ("DominantDirectionalLightComponent",)


class Reader:
    def __init__(self, data, offset=0, end=None):
        self.data, self.pos = data, offset
        self.end = len(data) if end is None else end
        if not 0 <= offset <= self.end <= len(data):
            raise FormatError("Invalid reader bounds")

    def take(self, size):
        if size < 0 or self.pos + size > self.end:
            raise FormatError(f"Read of {size} bytes outside payload at {self.pos}")
        start = self.pos
        self.pos += size
        return self.data[start:self.pos]

    def unpack(self, fmt):
        return struct.unpack("<" + fmt, self.take(struct.calcsize("<" + fmt)))

    def i32(self): return self.unpack("i")[0]
    def u32(self): return self.unpack("I")[0]
    def count(self):
        n = self.i32()
        if not 0 <= n <= 10_000_000:
            raise FormatError(f"Invalid array count {n} at {self.pos - 4}")
        return n

    def array_bytes(self):
        stride = self.count()
        if not stride: return 0, 0, b""
        count = self.count()
        return stride, count, self.take(stride * count)


class Package:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.data, self.header = upkinfo.load(self.path)
        if self.header["ver"] != 845 or self.header["lic"] not in (0,64):
            raise FormatError("This importer supports v845 EW/licensee 64 and UDK/licensee 0 packages only")
        self.names, self.imports, self.exports = upkinfo.tables(self.data, self.header)
        self.paths = [self.name(i + 1) for i in range(len(self.exports))]
        self.by_name = {p: i + 1 for i, p in enumerate(self.paths)}
        self.children = {}
        for i, e in enumerate(self.exports, 1):
            if not 0 <= e["off"] <= e["off"] + e["size"] <= len(self.data):
                raise FormatError(f"Export {i} outside package")
            self.children.setdefault(e["outer"], []).append(i)

    def name(self, index):
        if index > len(self.exports) or index < -len(self.imports):
            raise FormatError(f"Invalid object reference {index}")
        return upkinfo.objname(index, self.imports, self.exports)

    def cls(self, index):
        return upkinfo.clsname(self.exports[index - 1]["cls"], self.imports, self.exports)

    def fname(self, r):
        i, number = r.unpack("ii")
        if not 0 <= i < len(self.names) or number < 0:
            raise FormatError(f"Invalid FName at {r.pos - 8}")
        return self.names[i] + (f"_{number - 1}" if number else "")

    def tagged(self, r):
        result = {}
        while r.pos < r.end:
            name = self.fname(r)
            if name == "None": return result
            kind = self.fname(r)
            size, slot = r.unpack("ii")
            subtype = None
            if kind == "BoolProperty":
                value = bool(r.take(1)[0])
            else:
                if kind in ("StructProperty", "ByteProperty"):
                    subtype = self.fname(r)
                raw = r.take(size)
                value = self.decode(kind, subtype, raw)
            result[(name, slot)] = {"kind": kind, "subtype": subtype, "value": value}
        raise FormatError("Missing property terminator")

    def decode(self, kind, subtype, raw):
        r = Reader(raw)
        if kind in ("ObjectProperty", "ComponentProperty", "ClassProperty", "IntProperty"):
            return r.i32()
        if kind == "FloatProperty": return r.unpack("f")[0]
        if kind == "NameProperty" or kind == "ByteProperty" and len(raw) == 8:
            return self.fname(r)
        if kind == "ByteProperty" and len(raw) == 1: return raw[0]
        if kind == "StructProperty":
            if subtype in ("Vector", "LinearColor", "Rotator"):
                fmt = {"Vector": "3f", "LinearColor": "4f", "Rotator": "3i"}[subtype]
                return list(r.unpack(fmt))
            if subtype == "Color":
                b, g, red, a = r.unpack("4B")
                return [red / 255, g / 255, b / 255, a / 255]
        return raw

    def properties(self, index):
        """(the export's tagged properties, where its native data starts), read once and kept on the package itself:
        a cache on the method would hold every package the server ever opened (review finding 19)."""
        kept = self.__dict__.setdefault('_properties', {})
        found = kept.get(index)
        if found is None:
            found = kept[index] = self._read_properties(index)
        return found

    def _read_properties(self, index):
        e = self.exports[index - 1]
        if self.cls(index) in LEADING_SHADOW_MAP:
            # The cooked component puts its DominantLightShadowMap (a counted WORD array)
            # ahead of the usual header; URB_Bar's sun holds 12,804 words.
            count = Reader(self.data, e["off"], e["off"] + e["size"]).count()
            skip = 4 + 2 * count
            if skip > e["size"]: raise FormatError("Dominant-light shadow map outside export")
            e = dict(e, off=e["off"] + skip, size=e["size"] - skip)
        start = legacy_props.props_start(self.data, e, self.names)
        r = Reader(self.data, start, e["off"] + e["size"])
        values = self.tagged(r)
        return values, r.pos

    def own(self, index, key, default=None):
        item = self.properties(index)[0].get((key, 0))
        return item["value"] if item is not None else default

    def effective(self, index, key, default=None):
        seen = set()
        while index > 0:
            if index in seen: raise FormatError("Archetype cycle")
            seen.add(index)
            item = self.properties(index)[0].get((key, 0))
            if item is not None: return item["value"]
            index = self.exports[index - 1]["arch"]
        return default

    def refs(self, raw):
        if raw is None: return []
        r = Reader(raw)
        count = r.count()
        values = list(r.unpack(f"{count}i"))
        if r.pos != r.end: raise FormatError("Object array size mismatch")
        for ref in values: self.name(ref)
        return values

    def structs(self, raw):
        if raw is None: return []
        r = Reader(raw)
        values = [self.tagged(r) for _ in range(r.count())]
        if r.pos != r.end: raise FormatError("Struct array size mismatch")
        return values

    def native(self, index):
        e = self.exports[index - 1]
        return Reader(self.data, self.properties(index)[1], e["off"] + e["size"])

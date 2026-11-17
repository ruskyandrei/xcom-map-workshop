"""A sound's wave for the page's Play button (private/plans/todo/effects-and-sounds-plan.md, Part D's audio route,
stage FX2): the Ogg Vorbis stream a SoundNodeWave keeps in its PC bulk record (effects_metadata.pc_sound), checked as
an Ogg stream before it is served, and kept in a bounded cache so a wave is read from its package once.

The check (validate) follows Xiph's Ogg framing (https://xiph.org/ogg/doc/framing.html) and the Vorbis I
specification (https://xiph.org/vorbis/doc/Vorbis_I_spec.html), as the subset this editor accepts: one logical
stream (no chained or multiplexed one), every page's capture pattern, version, checksum and sequence number, the
continued-packet flags agreeing with the lacing, the first page beginning the stream and holding the Vorbis
identification header alone, the comment and setup headers after it with the first audio packet on a fresh page, the
last page ending the stream, and the granule positions never going back. A wave that fails is answered with why, not
guessed at; nothing searches for `OggS` in a package.
"""
import hashlib
import struct
import threading
from collections import OrderedDict
from pathlib import Path

MAX_BYTES = 32 * 1024 * 1024        # the game's longest wave in use is 4.6 MB (plan 2.5)
MAX_SECONDS = 3600
CACHE_BYTES = 64 * 1024 * 1024      # the cache's bound: the 64 waves the census found in use are 17.2 MB together


class OggError(ValueError):
    """Why a stream isn't served."""


def _crc_table():
    table = []
    for i in range(256):
        r = i << 24
        for _ in range(8):
            r = ((r << 1) ^ 0x04C11DB7) if r & 0x80000000 else (r << 1)
        table.append(r & 0xFFFFFFFF)
    return table


CRC = _crc_table()


def crc(data):
    """Ogg's page checksum: CRC-32, polynomial 0x04C11DB7, not reflected, starting at 0."""
    r = 0
    for b in data:
        r = ((r << 8) & 0xFFFFFFFF) ^ CRC[((r >> 24) ^ b) & 0xFF]
    return r


def pages(data):
    """Each page of an Ogg stream: dict(at, flags, granule, serial, sequence, lacing, body (start, end), end), checked
    as a page (capture pattern, version 0, checksum, its lacing and body inside the data). Raises OggError."""
    at, out = 0, []
    while at < len(data):
        if len(data) - at < 27:
            raise OggError('the stream ends inside a page header')
        if data[at:at + 4] != b'OggS':
            raise OggError('page %d does not start with the Ogg capture pattern' % len(out))
        version, flags, granule, serial, sequence, checksum, count = struct.unpack_from('<BBqIIIB', data, at + 4)
        if version != 0:
            raise OggError('page %d is of Ogg version %d' % (len(out), version))
        if flags & ~0x07:
            raise OggError('page %d sets flags Ogg does not define' % len(out))
        lacing = data[at + 27:at + 27 + count]
        if len(lacing) != count:
            raise OggError('the stream ends inside page %d\'s lacing' % len(out))
        start = at + 27 + count
        end = start + sum(lacing)
        if end > len(data):
            raise OggError('the stream ends inside page %d' % len(out))
        page = bytearray(data[at:end])
        page[22:26] = b'\0\0\0\0'
        if crc(page) != checksum:
            raise OggError('page %d\'s checksum is wrong' % len(out))
        out.append(dict(at=at, flags=flags, granule=granule, serial=serial, sequence=sequence, lacing=bytes(lacing),
                        body=(start, end), end=end))
        at = end
    if not out:
        raise OggError('the stream is empty')
    return out


def validate(data, max_bytes=MAX_BYTES):
    """Check an Ogg Vorbis stream (the module's subset): dict(channels, rate, frames, seconds, pages, serial).
    Raises OggError with why it is refused."""
    if len(data) > max_bytes:
        raise OggError('the stream is larger than %d bytes' % max_bytes)
    found = pages(data)
    first, last = found[0], found[-1]
    serial = first['serial']
    packets, partial, open_packet, granule, audio_page_start = [], bytearray(), False, -1, None
    for n, page in enumerate(found):
        if page['serial'] != serial:
            raise OggError('page %d is of another logical stream (a multiplexed or chained stream)' % n)
        if page['sequence'] != n:
            raise OggError('page %d is numbered %d' % (n, page['sequence']))
        if bool(page['flags'] & 0x02) != (n == 0):
            raise OggError('page %d %s the stream' % (n, 'begins' if page['flags'] & 0x02 else 'does not begin'))
        if bool(page['flags'] & 0x04) != (n == len(found) - 1):
            raise OggError('page %d %s the stream' % (n, 'ends' if page['flags'] & 0x04 else 'does not end'))
        if bool(page['flags'] & 0x01) != open_packet:
            raise OggError('page %d\'s continued-packet flag disagrees with the page before' % n)
        if page['granule'] != -1:
            if page['granule'] < granule:
                raise OggError('page %d\'s granule position goes back' % n)
            granule = page['granule']
        # the first three packets (the Vorbis headers) are put together; the audio's are only counted
        at = page['body'][0]
        for size in page['lacing']:
            if len(packets) < 3:
                partial += data[at:at + size]
            at += size
            if size < 255:
                if len(packets) < 3:
                    packets.append(bytes(partial))
                    partial = bytearray()
                    if len(packets) == 1 and (n != 0 or at != page['end']):
                        raise OggError('the identification header is not alone on the first page')
                    if len(packets) == 3:
                        if at != page['end']:
                            raise OggError('the first audio packet does not begin on a fresh page')
                        audio_page_start = n + 1
        open_packet = bool(page['lacing']) and page['lacing'][-1] == 255
    if open_packet:
        raise OggError('the last packet is not finished')
    if len(packets) < 3:
        raise OggError('the stream holds fewer than the three Vorbis headers')
    ident, comment, setup = packets
    if len(ident) != 30 or ident[:7] != b'\x01vorbis':
        raise OggError('the stream is not Vorbis (no Vorbis identification header)')
    version, channels, rate = struct.unpack_from('<IBI', ident, 7)
    blocks, framing = ident[28], ident[29]
    small, large = blocks & 0x0F, blocks >> 4
    if version != 0 or not channels or not rate or not framing & 1 or not 6 <= small <= large <= 13:
        raise OggError('the Vorbis identification header is not valid')
    if comment[:7] != b'\x03vorbis' or setup[:7] != b'\x05vorbis':
        raise OggError('the Vorbis comment or setup header is missing')
    if audio_page_start is None or audio_page_start >= len(found) or last['granule'] < 0:
        raise OggError('the stream holds no audio')
    frames = last['granule']
    if frames / rate > MAX_SECONDS:
        raise OggError('the stream is longer than %d seconds' % MAX_SECONDS)
    return dict(channels=channels, rate=rate, frames=frames, seconds=frames / rate, pages=len(found), serial=serial)


def wave_stream(p, index):
    """(the Ogg Vorbis bytes of SoundNodeWave export `index`, validate()'s record). Raises OggError."""
    from effects_metadata import pc_sound
    if p.cls(index) != 'SoundNodeWave':
        raise OggError('%s is not a wave' % p.name(index))
    at, size, why = pc_sound(p, index)
    if why:
        raise OggError(why)
    data = bytes(p.data[at:at + size])
    return data, validate(data)


class WaveCache:
    """Each wave the page plays read from its package once and kept, up to CACHE_BYTES (the least recently played
    leave first). A package is read once per export it was found for: the map's own must be the file the map was
    exported from (its SHA-256); a stream's is taken by its size and time."""

    def __init__(self, budget=CACHE_BYTES):
        self.lock = threading.Lock()
        self.budget = budget
        self.waves = OrderedDict()      # (root, wave id, fingerprint) -> (bytes, etag, record)
        self.packages = {}              # (path, size, mtime) -> Package
        self.checked = {}               # (path, size, mtime) -> sha256 hex

    def package(self, path, want_sha=None):
        from package import Package
        path = Path(path)
        st = path.stat()
        key = (str(path), st.st_size, st.st_mtime_ns)
        if want_sha:
            if key not in self.checked:
                self.checked[key] = hashlib.sha256(path.read_bytes()).hexdigest()
            if self.checked[key] != want_sha:
                raise OggError('%s in the install is not the file this map was exported from' % path.name)
        if key not in self.packages:
            if len(self.packages) > 8:
                self.packages.pop(next(iter(self.packages)))
            self.packages[key] = Package(path)
        return self.packages[key], '%d-%d' % (st.st_size, st.st_mtime_ns)

    def get(self, root, scene, wave_id, find_map, find_stream):
        """(bytes, etag, record) of wave `wave_id` (a key of the export's soundWaves: '<package>|<path>') for the
        export at `root`. find_map() is the map's package in the install, find_stream(name) a stream's. Raises
        KeyError for an id the export doesn't list (a stale or made-up one) and OggError for a wave it can't serve."""
        waves = scene.get('soundWaves') or {}
        if wave_id not in waves:
            raise KeyError(wave_id)
        known = waves[wave_id]
        if not known.get('playable'):
            raise OggError(known.get('why') or 'the export says it can\'t be played')
        stem, _, path = wave_id.partition('|')
        # a package's file name and its map record's name can differ in case (CsmallScout_Farm)
        source = Path((scene.get('source') or {}).get('file') or '').stem
        streams = {name.casefold(): name for name in scene.get('streams') or {}}
        with self.lock:
            if stem.casefold() in ((scene.get('name') or '').casefold(), source.casefold()):
                p, fingerprint = self.package(find_map(), (scene.get('source') or {}).get('sha256'))
            else:
                if stem.casefold() not in streams:
                    raise KeyError(wave_id)
                found = find_stream(streams[stem.casefold()])
                if found is None:
                    raise OggError('%s is not in the install' % stem)
                p, fingerprint = self.package(found)
            key = (str(root), wave_id, fingerprint)
            if key in self.waves:
                self.waves.move_to_end(key)
                return self.waves[key]
            found = [i for i, name in enumerate(p.paths, 1) if name == path and p.cls(i) == 'SoundNodeWave']
            if not found:
                raise OggError('%s is not in %s' % (path, p.path.name))
            data, record = wave_stream(p, found[0])
            entry = (data, hashlib.sha256(data).hexdigest()[:20], record)
            self.waves[key] = entry
            total = sum(len(v[0]) for v in self.waves.values())
            while total > self.budget and len(self.waves) > 1:
                _, dropped = self.waves.popitem(last=False)
                total -= len(dropped[0])
            return entry


def byte_range(header, size):
    """(start, end) inclusive of a single-range Range header ('bytes=a-b', 'bytes=a-', 'bytes=-n') within `size`
    bytes; None for none or one this server doesn't answer (several ranges: the whole file is sent); False for one
    outside the file (416)."""
    if not header or not header.startswith('bytes=') or ',' in header:
        return None
    first, _, last = header[6:].strip().partition('-')
    try:
        if first == '':
            n = int(last)
            if n <= 0:
                return False
            return max(0, size - n), size - 1
        start = int(first)
        end = int(last) if last else size - 1
    except ValueError:
        return None
    if start >= size or start > end:
        return False
    return start, min(end, size - 1)

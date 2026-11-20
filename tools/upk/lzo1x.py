# Minimal pure-python LZO1X decompressor (safe variant semantics, enough for UE3 blocks)
def decompress(src, out_len=None):
    """The block `src` decoded. ValueError (never IndexError) for a block cut short or a match before its start, and,
    given `out_len`, for output of another length: a damaged package fails as the readers' guards expect (review
    finding 50)."""
    try:
        out = _decompress(src)
    except IndexError:
        raise ValueError('LZO block cut short (%d bytes)' % len(src)) from None
    if out_len is not None and len(out) != out_len:
        raise ValueError('LZO block gives %d bytes, not %d' % (len(out), out_len))
    return out


def _decompress(src):
    dst = bytearray()
    ip = 0
    n = len(src)
    def copy_match(dist, length):
        start = len(dst) - dist
        if start < 0: raise ValueError('lookbehind overrun')
        # slices, not a byte at a time (1.8 times faster on a map package); a match that overlaps what it writes
        # repeats its last `dist` bytes
        if dist >= length:
            dst.extend(dst[start:start + length])
        elif dist == 1:
            dst.extend(dst[start:] * length)
        else:
            dst.extend((bytes(dst[start:]) * (length // dist + 1))[:length])
    t = src[ip]
    state = 0
    if t > 17:
        ip += 1
        t -= 17
        dst += src[ip:ip+t]; ip += t
        state = 4 if t >= 4 else t
        # fall into main loop with the state set
    else:
        state = 0
    while True:
        t = src[ip]; ip += 1
        if t < 16:
            if state == 0:
                # literal run
                if t == 0:
                    while src[ip] == 0:
                        t += 255; ip += 1
                    t += 15 + src[ip]; ip += 1
                t += 3
                dst += src[ip:ip+t]; ip += t
                state = 4
                continue
            elif state < 4:
                # short match, 2 bytes
                dist = (t >> 2) + (src[ip] << 2) + 1; ip += 1
                copy_match(dist, 2)
                s = t & 3
            else:
                dist = (t >> 2) + (src[ip] << 2) + 2049; ip += 1
                copy_match(dist, 3)
                s = t & 3
        elif t >= 64:
            dist = ((t >> 2) & 7) + (src[ip] << 3) + 1; ip += 1
            length = (t >> 5) - 1 + 2
            copy_match(dist, length)
            s = t & 3
        elif t >= 32:
            length = t & 31
            if length == 0:
                while src[ip] == 0:
                    length += 255; ip += 1
                length += 31 + src[ip]; ip += 1
            length += 2
            v = src[ip] | (src[ip+1] << 8); ip += 2
            dist = (v >> 2) + 1
            copy_match(dist, length)
            s = v & 3
        else:  # 16..31
            length = t & 7
            if length == 0:
                while src[ip] == 0:
                    length += 255; ip += 1
                length += 7 + src[ip]; ip += 1
            length += 2
            v = src[ip] | (src[ip+1] << 8); ip += 2
            dist = ((t & 8) << 11) + (v >> 2)
            if dist == 0:
                break  # end of stream
            dist += 16384
            copy_match(dist, length)
            s = v & 3
        if s:
            dst += src[ip:ip+s]; ip += s
        state = s
    return bytes(dst)

"""DXT1 (BC1) blocks with numpy: decode, and encode in four-colour mode (baker design, section 4.7).

A block is 4 x 4 texels: two RGB565 endpoints and 2-bit indices. With c0 > c1 the palette is c0, c1, (2 c0 + c1) / 3
and (c0 + 2 c1) / 3; with c0 <= c1 it is c0, c1, their mean and black. The encoder fits the endpoints to the block's
principal axis, then refines them by least squares on the chosen indices, and always writes c0 > c1 (or a solid
block, c0 == c1 with every index 0), so it never produces black by accident.

Images here are float RGB in [0, 1], rows top to bottom, as `lightmap_stats.top_mip_rgb` returns them.
"""
import numpy as np


def _expand565(c):
    r, g, b = (c >> 11) & 31, (c >> 5) & 63, c & 31
    return np.stack([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)], -1).astype(np.float64) / 255.0


def _pack565(rgb):
    q = np.clip(np.rint(rgb * [31, 63, 31]), 0, [31, 63, 31]).astype(np.uint32)
    return (q[..., 0] << 11) | (q[..., 1] << 5) | q[..., 2]


def palettes(c0, c1):
    """(n, 4, 3) palettes of blocks with endpoints c0, c1 (uint RGB565 arrays)."""
    a, b = _expand565(c0), _expand565(c1)
    four = (c0 > c1)[:, None]
    p2 = np.where(four, (2 * a + b) / 3, (a + b) / 2)
    p3 = np.where(four, (a + 2 * b) / 3, 0.0)
    return np.stack([a, b, p2, p3], 1)


def decode_blocks(data):
    """(n, 16, 3) texels of n packed blocks (texel k = row k // 4, column k % 4)."""
    raw = np.frombuffer(bytes(data), dtype='<u4').reshape(-1, 2)
    c0, c1 = raw[:, 0] & 0xFFFF, raw[:, 0] >> 16
    idx = (raw[:, 1:2] >> (2 * np.arange(16, dtype=np.uint32))) & 3
    pal = palettes(c0, c1)
    return np.take_along_axis(pal, idx[..., None].astype(np.int64).repeat(3, -1), 1)


def encode_blocks(texels, refine=2):
    """Pack (n, 16, 3) texels in [0, 1] into n DXT1 blocks (bytes)."""
    x = np.clip(np.asarray(texels, np.float64), 0, 1)
    n = len(x)
    mean = x.mean(1)
    centred = x - mean[:, None]
    cov = np.einsum('nki,nkj->nij', centred, centred)
    _, vecs = np.linalg.eigh(cov)
    axis = vecs[:, :, -1]
    t = np.einsum('nki,ni->nk', centred, axis)
    lo = mean + t.min(1)[:, None] * axis
    hi = mean + t.max(1)[:, None] * axis
    c0, c1 = _endpoints(hi, lo)
    idx = _indices(x, c0, c1)
    for _ in range(refine):
        # least squares for the two endpoints given the indices (weights along c0 .. c1)
        w = np.choose(idx, [np.ones_like(idx, float), np.zeros_like(idx, float),
                            np.full(idx.shape, 2 / 3), np.full(idx.shape, 1 / 3)])
        aa, bb, ab = (w * w).sum(1), ((1 - w) ** 2).sum(1), (w * (1 - w)).sum(1)
        ax = np.einsum('nk,nki->ni', w, x)
        bx = np.einsum('nk,nki->ni', 1 - w, x)
        det = aa * bb - ab * ab
        ok = np.abs(det) > 1e-9
        safe = np.where(ok, det, 1.0)[:, None]
        new_hi = np.where(ok[:, None], (bb[:, None] * ax - ab[:, None] * bx) / safe, _expand565(c0))
        new_lo = np.where(ok[:, None], (aa[:, None] * bx - ab[:, None] * ax) / safe, _expand565(c1))
        n0, n1 = _endpoints(new_hi, new_lo)
        nidx = _indices(x, n0, n1)
        better = _error(x, n0, n1, nidx) < _error(x, c0, c1, idx)
        c0, c1 = np.where(better, n0, c0), np.where(better, n1, c1)
        idx = np.where(better[:, None], nidx, idx)
    solid = c0 == c1
    idx = np.where(solid[:, None], 0, idx)
    bits = (idx.astype(np.uint32) << (2 * np.arange(16, dtype=np.uint32))).sum(1, dtype=np.uint64).astype(np.uint32)
    out = np.empty((n, 2), '<u4')
    out[:, 0] = c0 | (c1 << 16)
    out[:, 1] = bits
    return out.tobytes()


def _endpoints(hi, lo):
    """RGB565 endpoints with c0 > c1 (or equal), swapping where needed."""
    c0, c1 = _pack565(np.clip(hi, 0, 1)), _pack565(np.clip(lo, 0, 1))
    swap = c0 < c1
    return np.where(swap, c1, c0), np.where(swap, c0, c1)


def _indices(x, c0, c1):
    pal = palettes(c0, c1)
    d = ((x[:, :, None, :] - pal[:, None, :, :]) ** 2).sum(-1)
    four = (c0 > c1)[:, None, None]
    d = np.where(four | (np.arange(4) < 2), d, np.inf)   # equal endpoints: keep to the two endpoints
    return d.argmin(-1)


def _error(x, c0, c1, idx):
    pal = palettes(c0, c1)
    return ((x - np.take_along_axis(pal, idx[..., None].repeat(3, -1), 1)) ** 2).sum((1, 2))


def image_blocks(image):
    """(rows, cols, 16, 3) blocks of an image whose sides are multiples of 4."""
    h, w, _ = image.shape
    return image.reshape(h // 4, 4, w // 4, 4, 3).transpose(0, 2, 1, 3, 4).reshape(h // 4, w // 4, 16, 3)


def blocks_image(blocks):
    """Inverse of image_blocks."""
    rows, cols = blocks.shape[:2]
    return blocks.reshape(rows, cols, 4, 4, 3).transpose(0, 2, 1, 3, 4).reshape(rows * 4, cols * 4, 3)


def decode_region(raw, width, height, bx0, by0, bx1, by1):
    """The blocks [bx0, bx1) x [by0, by1) of a DXT1 mip as a float image, 4 texels a block."""
    bw, bh = max(1, (width + 3) // 4), max(1, (height + 3) // 4)
    part = np.frombuffer(bytes(raw), np.uint8).reshape(bh, bw, 8)[by0:by1, bx0:bx1]
    rows, cols = part.shape[:2]
    return blocks_image(decode_blocks(part.tobytes()).reshape(rows, cols, 16, 3))


def decode_image(raw, width, height):
    """A whole DXT1 mip as a float image (sides padded up to whole blocks, then cut back)."""
    bw, bh = max(1, (width + 3) // 4), max(1, (height + 3) // 4)
    blocks = decode_blocks(raw).reshape(bh, bw, 16, 3)
    return blocks_image(blocks)[:height, :width]

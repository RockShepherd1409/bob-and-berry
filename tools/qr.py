"""Small dependency-free QR code encoder (byte mode) with SVG output.

Used by build.py to make the printable backup QR codes in nfc-kit/.
Follows ISO/IEC 18004; the structure mirrors Project Nayuki's
QR Code generator (MIT licence).

    from tools.qr import qr_matrix, qr_svg
    svg = qr_svg("https://example.com/bob/")
"""
from html import escape

_ORDER = {"L": 0, "M": 1, "Q": 2, "H": 3}
_FORMAT_BITS = {"L": 1, "M": 0, "Q": 3, "H": 2}
_ECC_PER_BLOCK = {
    "L": [-1, 7, 10, 15, 20, 26, 18, 20, 24, 30, 18, 20, 24, 26, 30, 22, 24, 28, 30, 28, 28, 28, 28, 30, 30, 26, 28, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30],
    "M": [-1, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26, 30, 22, 22, 24, 24, 28, 28, 26, 26, 26, 26, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28],
    "Q": [-1, 13, 22, 18, 26, 18, 24, 18, 22, 20, 24, 28, 26, 24, 20, 30, 24, 28, 28, 26, 30, 28, 30, 30, 30, 30, 28, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30],
    "H": [-1, 17, 28, 22, 16, 22, 28, 26, 26, 24, 28, 24, 28, 22, 24, 24, 30, 28, 28, 26, 28, 30, 24, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30],
}
_NUM_BLOCKS = {
    "L": [-1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 4, 4, 4, 4, 4, 6, 6, 6, 6, 7, 8, 8, 9, 9, 10, 12, 12, 12, 13, 14, 15, 16, 17, 18, 19, 19, 20, 21, 22, 24, 25],
    "M": [-1, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5, 5, 8, 9, 9, 10, 10, 11, 13, 14, 16, 17, 17, 18, 20, 21, 23, 25, 26, 28, 29, 31, 33, 35, 37, 38, 40, 43, 45, 47, 49],
    "Q": [-1, 1, 1, 2, 2, 4, 4, 6, 6, 8, 8, 8, 10, 12, 16, 12, 17, 16, 18, 21, 20, 23, 23, 25, 27, 29, 34, 34, 35, 38, 40, 43, 45, 48, 51, 53, 56, 59, 62, 65, 68],
    "H": [-1, 1, 1, 2, 4, 4, 4, 5, 6, 8, 8, 11, 11, 16, 16, 18, 16, 19, 21, 25, 25, 25, 34, 30, 32, 35, 37, 40, 42, 45, 48, 51, 54, 57, 60, 63, 66, 70, 74, 77, 81],
}


def _raw_modules(ver):
    r = (16 * ver + 128) * ver + 64
    if ver >= 2:
        n = ver // 7 + 2
        r -= (25 * n - 10) * n - 55
        if ver >= 7:
            r -= 36
    return r


def _data_codewords(ver, ecl):
    return _raw_modules(ver) // 8 - _ECC_PER_BLOCK[ecl][ver] * _NUM_BLOCKS[ecl][ver]


def _gf_mul(x, y):
    z = 0
    for i in reversed(range(8)):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z


def _rs_divisor(degree):
    result = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for j in range(degree):
            result[j] = _gf_mul(result[j], root)
            if j + 1 < degree:
                result[j] ^= result[j + 1]
        root = _gf_mul(root, 0x02)
    return result


def _rs_remainder(data, divisor):
    result = [0] * len(divisor)
    for b in data:
        factor = b ^ result.pop(0)
        result.append(0)
        for i, coef in enumerate(divisor):
            result[i] ^= _gf_mul(coef, factor)
    return result


def _alignment_positions(ver, size):
    if ver == 1:
        return []
    n = ver // 7 + 2
    step = (ver * 8 + n * 3 + 5) // (n * 4 - 4) * 2
    return [6] + sorted(size - 7 - i * step for i in range(n - 1))


def _count(s, pat):
    n, i = 0, s.find(pat)
    while i != -1:
        n += 1
        i = s.find(pat, i + 1)
    return n


def qr_matrix(text, min_ecl="M"):
    """Return the QR code for `text` as a list of rows of booleans (True = dark)."""
    data = text.encode("utf-8")
    ecl = min_ecl
    for ver in range(1, 41):
        cc_bits = 8 if ver <= 9 else 16
        needed = 4 + cc_bits + 8 * len(data)
        if needed <= _data_codewords(ver, ecl) * 8:
            break
    else:
        raise ValueError("Text is too long for a QR code")
    for better in ("Q", "H"):  # use stronger error correction when it fits for free
        if _ORDER[better] > _ORDER[ecl] and needed <= _data_codewords(ver, better) * 8:
            ecl = better

    # --- data bits
    bits = []

    def put(val, n):
        for i in reversed(range(n)):
            bits.append((val >> i) & 1)

    put(0b0100, 4)
    put(len(data), cc_bits)
    for b in data:
        put(b, 8)
    cap = _data_codewords(ver, ecl) * 8
    put(0, min(4, cap - len(bits)))
    put(0, (-len(bits)) % 8)
    pad = 0xEC
    while len(bits) < cap:
        put(pad, 8)
        pad ^= 0xEC ^ 0x11
    codewords = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]

    # --- error correction + interleaving
    nblocks = _NUM_BLOCKS[ecl][ver]
    ecclen = _ECC_PER_BLOCK[ecl][ver]
    raw = _raw_modules(ver) // 8
    nshort = nblocks - raw % nblocks
    shortlen = raw // nblocks
    div = _rs_divisor(ecclen)
    blocks, k = [], 0
    for i in range(nblocks):
        dlen = shortlen - ecclen + (0 if i < nshort else 1)
        dat = codewords[k:k + dlen]
        k += dlen
        ecc = _rs_remainder(dat, div)
        if i < nshort:
            dat = dat + [0]
        blocks.append(dat + ecc)
    final = []
    for i in range(len(blocks[0])):
        for j, blk in enumerate(blocks):
            if i != shortlen - ecclen or j >= nshort:
                final.append(blk[i])

    # --- function patterns
    size = ver * 4 + 17
    mod = [[False] * size for _ in range(size)]
    fn = [[False] * size for _ in range(size)]

    def setf(x, y, dark):
        mod[y][x] = dark
        fn[y][x] = True

    for i in range(size):
        setf(6, i, i % 2 == 0)
        setf(i, 6, i % 2 == 0)
    for cx, cy in ((3, 3), (size - 4, 3), (3, size - 4)):
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                x, y = cx + dx, cy + dy
                if 0 <= x < size and 0 <= y < size:
                    setf(x, y, max(abs(dx), abs(dy)) not in (2, 4))
    pos = _alignment_positions(ver, size)
    n = len(pos)
    for i in range(n):
        for j in range(n):
            if (i == 0 and j == 0) or (i == 0 and j == n - 1) or (i == n - 1 and j == 0):
                continue
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    setf(pos[i] + dx, pos[j] + dy, max(abs(dx), abs(dy)) != 1)

    def draw_format(mask):
        d = _FORMAT_BITS[ecl] << 3 | mask
        rem = d
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        fb = (d << 10 | rem) ^ 0x5412

        def g(i):
            return (fb >> i) & 1 == 1

        for i in range(6):
            setf(8, i, g(i))
        setf(8, 7, g(6))
        setf(8, 8, g(7))
        setf(7, 8, g(8))
        for i in range(9, 15):
            setf(14 - i, 8, g(i))
        for i in range(8):
            setf(size - 1 - i, 8, g(i))
        for i in range(8, 15):
            setf(8, size - 15 + i, g(i))
        setf(8, size - 8, True)

    draw_format(0)
    if ver >= 7:
        rem = ver
        for _ in range(12):
            rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
        vb = ver << 12 | rem
        for i in range(18):
            bit = (vb >> i) & 1 == 1
            a, b = size - 11 + i % 3, i // 3
            setf(a, b, bit)
            setf(b, a, bit)

    # --- place codewords in the zig-zag
    i, total, right = 0, len(final) * 8, size - 1
    while right >= 1:
        if right == 6:
            right = 5
        for vert in range(size):
            for j in range(2):
                x = right - j
                y = size - 1 - vert if ((right + 1) & 2) == 0 else vert
                if not fn[y][x] and i < total:
                    mod[y][x] = ((final[i >> 3] >> (7 - (i & 7))) & 1) == 1
                    i += 1
        right -= 2

    # --- masking: try all eight, keep the lowest penalty
    def apply_mask(m):
        for y in range(size):
            for x in range(size):
                if fn[y][x]:
                    continue
                if m == 0:
                    inv = (x + y) % 2 == 0
                elif m == 1:
                    inv = y % 2 == 0
                elif m == 2:
                    inv = x % 3 == 0
                elif m == 3:
                    inv = (x + y) % 3 == 0
                elif m == 4:
                    inv = (x // 3 + y // 2) % 2 == 0
                elif m == 5:
                    inv = x * y % 2 + x * y % 3 == 0
                elif m == 6:
                    inv = (x * y % 2 + x * y % 3) % 2 == 0
                else:
                    inv = ((x + y) % 2 + x * y % 3) % 2 == 0
                if inv:
                    mod[y][x] = not mod[y][x]

    def penalty():
        p = 0
        for lines in (mod, [list(c) for c in zip(*mod)]):
            for line in lines:
                run = 1
                for k2 in range(1, size):
                    if line[k2] == line[k2 - 1]:
                        run += 1
                    else:
                        if run >= 5:
                            p += 3 + run - 5
                        run = 1
                if run >= 5:
                    p += 3 + run - 5
                s = "".join("1" if v else "0" for v in line)
                p += 40 * (_count(s, "10111010000") + _count(s, "00001011101"))
        for y in range(size - 1):
            for x in range(size - 1):
                if mod[y][x] == mod[y][x + 1] == mod[y + 1][x] == mod[y + 1][x + 1]:
                    p += 3
        dark = sum(v for row in mod for v in row)
        tot = size * size
        p += ((abs(dark * 20 - tot * 10) + tot - 1) // tot - 1) * 10
        return p

    best, best_pen = 0, None
    for m in range(8):
        apply_mask(m)
        draw_format(m)
        pen = penalty()
        if best_pen is None or pen < best_pen:
            best, best_pen = m, pen
        apply_mask(m)
    apply_mask(best)
    draw_format(best)
    return mod


def qr_svg(text, border=4, dark="#111111", light="#ffffff", title=None):
    """Return a crisp, scalable SVG QR code (with the required quiet zone)."""
    m = qr_matrix(text)
    size = len(m)
    dim = size + border * 2
    parts = []
    for y, row in enumerate(m):
        x = 0
        while x < size:
            if row[x]:
                start = x
                while x < size and row[x]:
                    x += 1
                parts.append(f"M{start + border},{y + border}h{x - start}v1h{start - x}z")
            else:
                x += 1
    t = f"<title>{escape(title)}</title>" if title else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {dim} {dim}" '
            f'shape-rendering="crispEdges" role="img">{t}'
            f'<rect width="{dim}" height="{dim}" fill="{light}"/>'
            f'<path d="{"".join(parts)}" fill="{dark}"/></svg>')

"""_gfx (pico/modules/gfx/modgfx.c) in Python, so the PIL shim can be tried on CPython."""
WIDTH = HEIGHT = 240
canvas_bytes = bytearray(WIDTH * HEIGHT)
shows = 0


def _palette():
    out = []
    for i in range(256):
        if i < 216:
            out.append((i // 36 * 51, i // 6 % 6 * 51, i % 6 * 51))
        else:
            v = (i - 216) * 255 // 39
            out.append((v, v, v))
    return out


RGB = _palette()


def colour(r, g, b):
    if max(r, g, b) - min(r, g, b) <= 12:
        return 216 + ((r + g + b) * 39 + 382) // 765
    return 36 * ((r + 25) // 51) + 6 * ((g + 25) // 51) + (b + 25) // 51


def _blend(bg, fg, a):
    p, q = RGB[bg], RGB[fg]
    return colour(*[(p[k] * (15 - a) + q[k] * a + 7) // 15 for k in range(3)])


def fill(x0, y0, x1, y1, c):
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(WIDTH, x1), min(HEIGHT, y1)
    for y in range(y0, y1):
        if x1 > x0:
            canvas_bytes[y * WIDTH + x0:y * WIDTH + x1] = bytes([c]) * (x1 - x0)


def glyph(x, y, w, h, alpha, c, cx0, cy0, cx1, cy1):
    cx0, cy0, cx1, cy1 = max(0, cx0), max(0, cy0), min(WIDTH, cx1), min(HEIGHT, cy1)
    stride = (w + 1) // 2
    for j in range(h):
        py = y + j
        if py < cy0 or py >= cy1:
            continue
        for i in range(w):
            px = x + i
            if px < cx0 or px >= cx1:
                continue
            v = alpha[j * stride + i // 2]
            a = (v & 15) if (i & 1) else (v >> 4)
            if a:
                d = py * WIDTH + px
                canvas_bytes[d] = c if a == 15 else _blend(canvas_bytes[d], c, a)


def blit(src, w, h, x, y, cx0, cy0, cx1, cy1):
    cx0, cy0, cx1, cy1 = max(0, cx0), max(0, cy0), min(WIDTH, cx1), min(HEIGHT, cy1)
    for j in range(h):
        py = y + j
        if cy0 <= py < cy1:
            i0, i1 = max(0, cx0 - x), min(w, cx1 - x)
            if i1 > i0:
                canvas_bytes[py * WIDTH + x + i0:py * WIDTH + x + i1] = src[j * w + i0:j * w + i1]


def save(x0, y0, x1, y1):
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(WIDTH, x1), min(HEIGHT, y1)
    out = bytearray()
    for y in range(y0, y1):
        row = canvas_bytes[y * WIDTH:(y + 1) * WIDTH]
        x = x0
        while x < x1:
            run = 1
            while x + run < x1 and run < 255 and row[x + run] == row[x]:
                run += 1
            out += bytes((run, row[x]))
            x += run
    return bytes(out)


def restore(data, w, x, y, cx0, cy0, cx1, cy1):
    cx0, cy0, cx1, cy1 = max(0, cx0), max(0, cy0), min(WIDTH, cx1), min(HEIGHT, cy1)
    px = py = 0
    for k in range(0, len(data) - 1, 2):
        run, c = data[k], data[k + 1]
        yy = y + py
        if cy0 <= yy < cy1:
            a, b = max(cx0, x + px), min(cx1, x + px + run)
            if b > a:
                canvas_bytes[yy * WIDTH + a:yy * WIDTH + b] = bytes([c]) * (b - a)
        px += run
        if px >= w:
            px, py = 0, py + 1


def qr_encode(data):
    import pathlib
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "bitwasm-signer-pico/third_party/QR-Code-generator/python"))
    from qrcodegen import QrCode, QrSegment
    segs = QrSegment.make_segments(data) if isinstance(data, str) else [QrSegment.make_bytes(bytes(data))]
    q = QrCode.encode_segments(segs, QrCode.Ecc.LOW, boostecl=False)  # as modgfx.c
    n = q.get_size()
    bits = bytearray(1 + (n * n + 7) // 8)
    bits[0] = n
    for i in range(n * n):
        if q.get_module(i % n, i // n):
            bits[1 + (i >> 3)] |= 1 << (i & 7)
    return bytes(bits)


def _qr_square(n, r, c):
    if (r < 7 and c < 7) or (r < 7 and c >= n - 7) or (r >= n - 7 and c < 7):
        return True
    return n > 21 and n - 9 <= r < n - 4 and n - 9 <= c < n - 4


def qr(code, border, x, y, w, h, fg, bg, style, cx0, cy0, cx1, cy1):
    n, N = code[0], code[0] + 2 * border

    def module(r, c):
        if not (0 <= r < n and 0 <= c < n):
            return False
        i = r * n + c
        return (code[1 + (i >> 3)] >> (i & 7)) & 1

    cx0, cy0, cx1, cy1 = max(0, cx0, x), max(0, cy0, y), min(WIDTH, cx1, x + w), min(HEIGHT, cy1, y + h)
    for py in range(cy0, cy1):
        v = py - y
        mr = (2 * v + 1) * N // (2 * h)
        top = (2 * mr * h + N - 1) // (2 * N)
        cs_y, fy = (2 * (mr + 1) * h + N - 1) // (2 * N) - top, v - top
        for px in range(cx0, cx1):
            u = px - x
            mc = (2 * u + 1) * N // (2 * w)
            r, c = mr - border, mc - border
            dark = module(r, c)
            if dark and style != 1 and not _qr_square(n, r, c):
                left = (2 * mc * w + N - 1) // (2 * N)
                cs_x, fx = (2 * (mc + 1) * w + N - 1) // (2 * N) - left, u - left
                if style == 2:
                    ax, ay = 2 * fx + 1 - cs_x, 2 * fy + 1 - cs_y
                    dark = ax * ax + ay * ay <= cs_x * cs_y
                else:
                    dx, dy = (cs_x + 5) // 10, (cs_y + 5) // 10
                    dark = dx <= fx < cs_x - dx and dy <= fy < cs_y - dy
            canvas_bytes[py * WIDTH + px] = fg if dark else bg


def show(*args):
    global shows
    shows += 1


def canvas():
    return canvas_bytes


def to_rgb(buf=None):
    buf = buf or canvas_bytes
    out = bytearray()
    for v in buf:
        out += bytes(RGB[v])
    return bytes(out)

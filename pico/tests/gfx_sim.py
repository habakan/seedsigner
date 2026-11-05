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

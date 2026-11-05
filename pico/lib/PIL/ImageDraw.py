"""PIL's ImageDraw over pico/lib/PIL/Image.py: each call records an operation; replay() draws them."""
from PIL import Image as _Image

_gfx = _Image._gfx


def _clip(a, b):
    return (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))


def _fill(x0, y0, x1, y1, c, clip):
    """x1, y1 exclusive."""
    x0, y0, x1, y1 = max(x0, clip[0]), max(y0, clip[1]), min(x1, clip[2]), min(y1, clip[3])
    if x1 > x0 and y1 > y0:
        _gfx.fill(x0, y0, x1, y1, c)


def _inset(r, k):
    """How far row k of a corner of radius r starts in from the side."""
    d = r - k - 0.5
    return r - int((r * r - d * d) ** 0.5 + 0.5) if d * d < r * r else r


def _rrect_rows(x0, y0, x1, y1, r):
    """(y, left, right) spans of a rounded rectangle, both inclusive."""
    r = max(0, min(r, (x1 - x0 + 1) // 2, (y1 - y0 + 1) // 2))
    for y in range(y0, y1 + 1):
        k = min(y - y0, y1 - y)
        i = _inset(r, k) if k < r else 0
        yield y, x0 + i, x1 - i


def _ellipse_rows(x0, y0, x1, y1):
    cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0 + 1) / 2, (y1 - y0 + 1) / 2
    for y in range(y0, y1 + 1):
        t = (y + 0.5 - (cy + 0.5)) / ry if ry else 0
        if t * t > 1:
            continue
        half = rx * (1 - t * t) ** 0.5
        yield y, int(cx + 0.5 - half + 0.5), int(cx + 0.5 + half - 0.5)


def _spans(rows, c, dx, dy, clip):
    for y, a, b in rows:
        _fill(dx + a, dy + y, dx + b + 1, dy + y + 1, c, clip)


def _ring(outer, inner, c, dx, dy, clip):
    """An outline: each outer row less the inner row it has, if any."""
    inside = {y: (a, b) for y, a, b in inner}
    for y, a, b in outer:
        if y in inside and inside[y][0] <= inside[y][1]:
            ia, ib = inside[y]
            _fill(dx + a, dy + y, dx + ia, dy + y + 1, c, clip)
            _fill(dx + ib + 1, dy + y, dx + b + 1, dy + y + 1, c, clip)
        else:
            _fill(dx + a, dy + y, dx + b + 1, dy + y + 1, c, clip)


def replay(ops, dx, dy, clip):
    for op in ops:
        k = op[0]
        if k == "rect":
            _, x0, y0, x1, y1, fill, outline, width = op
            if fill is not None:
                _fill(dx + x0, dy + y0, dx + x1 + 1, dy + y1 + 1, fill, clip)
            if outline is not None and width > 0:
                for a in ((x0, y0, x1, y0 + width - 1), (x0, y1 - width + 1, x1, y1),
                          (x0, y0, x0 + width - 1, y1), (x1 - width + 1, y0, x1, y1)):
                    _fill(dx + a[0], dy + a[1], dx + a[2] + 1, dy + a[3] + 1, outline, clip)
        elif k == "rrect":
            _, x0, y0, x1, y1, r, fill, outline, width = op
            if outline is not None and width > 0:
                inner = list(_rrect_rows(x0 + width, y0 + width, x1 - width, y1 - width, max(0, r - width)))
                _ring(_rrect_rows(x0, y0, x1, y1, r), inner, outline, dx, dy, clip)
                if fill is not None:
                    _spans(inner, fill, dx, dy, clip)
            elif fill is not None:
                _spans(_rrect_rows(x0, y0, x1, y1, r), fill, dx, dy, clip)
        elif k == "ellipse":
            _, x0, y0, x1, y1, fill, outline, width = op
            if outline is not None and width > 0:
                inner = list(_ellipse_rows(x0 + width, y0 + width, x1 - width, y1 - width))
                _ring(_ellipse_rows(x0, y0, x1, y1), inner, outline, dx, dy, clip)
                if fill is not None:
                    _spans(inner, fill, dx, dy, clip)
            elif fill is not None:
                _spans(_ellipse_rows(x0, y0, x1, y1), fill, dx, dy, clip)
        elif k == "line":
            _, pts, c, width = op
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                _line(ax, ay, bx, by, c, width, dx, dy, clip)
        elif k == "arc":
            _, x0, y0, x1, y1, start, end, c, width = op
            _arc(x0, y0, x1, y1, start, end, c, width, dx, dy, clip)
        elif k == "text":
            _, x, y, text, font, c, anchor = op
            bits = memoryview(font.bitmaps)
            for gx, gy, w, h, off in font.glyphs(text, x, y, anchor):
                _gfx.glyph(dx + gx, dy + gy, w, h, bits[off:off + ((w + 1) // 2) * h], c,
                           clip[0], clip[1], clip[2], clip[3])
        elif k == "qr":
            _, code, border, x, y, w, h, fg, bg, style = op
            _gfx.qr(code, border, dx + x, dy + y, w, h, fg, bg, style, clip[0], clip[1], clip[2], clip[3])
        elif k == "rle":
            _, data, w = op
            _gfx.restore(data, w, dx, dy, clip[0], clip[1], clip[2], clip[3])
        elif k == "pix":
            _, pixels, w, h = op
            _gfx.blit(pixels, w, h, dx, dy, clip[0], clip[1], clip[2], clip[3])
        elif k == "img":
            _, sub, x, y, w, h = op
            replay(sub, dx + x, dy + y, _clip(clip, (dx + x, dy + y, dx + x + w, dy + y + h)))
        elif k == "scale":
            _, sub, sx, sy = op
            replay(_scaled(sub, sx, sy), dx, dy, clip)


def _scaled(ops, sx, sy):
    """Rectangles scale (a QR code's modules) and text takes the font at the scaled size, which is what a
    supersampled text area's resize comes to; anything else is drawn as it was."""
    from PIL import ImageFont
    out = []
    for op in ops:
        if op[0] == "rect":
            _, x0, y0, x1, y1, fill, outline, width = op
            out.append(("rect", int(x0 * sx), int(y0 * sy), int((x1 + 1) * sx) - 1, int((y1 + 1) * sy) - 1,
                        fill, outline, width))
        elif op[0] == "img":
            _, sub, x, y, w, h = op
            out.append(("img", _scaled(sub, sx, sy), int(x * sx), int(y * sy), int(w * sx), int(h * sy)))
        elif op[0] == "qr":
            _, code, border, x, y, w, h, fg, bg, style = op
            out.append(("qr", code, border, int(x * sx), int(y * sy), int(w * sx), int(h * sy), fg, bg, style))
        elif op[0] == "text":
            _, x, y, text, font, c, anchor = op
            out.append(("text", int(x * sx + 0.5), int(y * sy + 0.5), text,
                        ImageFont.truetype(font.path, int(font.size * sy + 0.5)), c, anchor))
        else:
            out.append(op)
    return out


def _line(ax, ay, bx, by, c, width, dx, dy, clip):
    lo, hi = -((width - 1) // 2), width // 2
    if ay == by or ax == bx:
        x0, x1 = min(ax, bx), max(ax, bx)
        y0, y1 = min(ay, by), max(ay, by)
        if ay == by:
            y0, y1 = y0 + lo, y1 + hi
        else:
            x0, x1 = x0 + lo, x1 + hi
        _fill(dx + x0, dy + y0, dx + x1 + 1, dy + y1 + 1, c, clip)
        return
    n = max(abs(bx - ax), abs(by - ay))
    for i in range(n + 1):
        x, y = ax + (bx - ax) * i // n, ay + (by - ay) * i // n
        _fill(dx + x + lo, dy + y + lo, dx + x + hi + 1, dy + y + hi + 1, c, clip)


def _arc(x0, y0, x1, y1, start, end, c, width, dx, dy, clip):
    import math
    cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
    while end < start:
        end += 360
    steps = max(8, int((end - start) / 360 * 2 * math.pi * max(rx, ry)))
    for i in range(steps + 1):
        a = math.radians(start + (end - start) * i / steps)
        for w in range(width):
            x, y = int(cx + (rx - w) * math.cos(a) + 0.5), int(cy + (ry - w) * math.sin(a) + 0.5)
            _fill(dx + x, dy + y, dx + x + 1, dy + y + 1, c, clip)


class ImageDraw:
    def __init__(self, im, mode=None):
        self.im = im
        self.mode = im.mode

    def _c(self, c):
        v = _Image.rgba(c, self.mode)
        return None if v is None or not v[3] else _Image.c332(v)

    def rectangle(self, xy, fill=None, outline=None, width=1):
        x0, y0, x1, y1 = _box(xy)
        self.im.add(("rect", x0, y0, x1, y1, self._c(fill), self._c(outline), width))

    def rounded_rectangle(self, xy, radius=0, fill=None, outline=None, width=1, corners=None):
        x0, y0, x1, y1 = _box(xy)
        self.im.add(("rrect", x0, y0, x1, y1, int(radius), self._c(fill), self._c(outline), width))

    def ellipse(self, xy, fill=None, outline=None, width=1):
        x0, y0, x1, y1 = _box(xy)
        self.im.add(("ellipse", x0, y0, x1, y1, self._c(fill), self._c(outline), width))

    def line(self, xy, fill=None, width=0, joint=None):
        pts = _points(xy)
        if self._c(fill) is not None:
            self.im.add(("line", pts, self._c(fill), max(1, width)))

    def arc(self, xy, start, end, fill=None, width=1):
        x0, y0, x1, y1 = _box(xy)
        self.im.add(("arc", x0, y0, x1, y1, start, end, self._c(fill), width))

    def polygon(self, xy, fill=None, outline=None, width=1):
        pts = _points(xy)
        if outline is not None or fill is not None:
            self.im.add(("line", pts + pts[:1], self._c(outline if outline is not None else fill), width))

    def text(self, xy, text, fill=None, font=None, anchor=None, spacing=4, align="left", *args, **kwargs):
        c = self._c(fill if fill is not None else "white")
        if c is None:
            return
        x, y = int(xy[0]), int(xy[1])
        if "\n" in text:
            # As PIL's multiline_text: lines a font's "A" height plus `spacing` apart
            step = font.getbbox("A")[3] + spacing
            for i, line in enumerate(text.split("\n")):
                self.im.add(("text", x, y + i * step, line, font, c, anchor or "la"))
            return
        self.im.add(("text", x, y, text, font, c, anchor))

    def textbbox(self, xy, text, font=None, anchor=None, *args, **kwargs):
        b = font.getbbox(text, anchor=anchor)
        return (xy[0] + b[0], xy[1] + b[1], xy[0] + b[2], xy[1] + b[3])

    def textlength(self, text, font=None, *args, **kwargs):
        return font.getlength(text)


def _box(xy):
    if len(xy) == 2:
        (x0, y0), (x1, y1) = xy
    else:
        x0, y0, x1, y1 = xy
    return int(x0), int(y0), int(x1), int(y1)


def _points(xy):
    if xy and not isinstance(xy[0], (tuple, list)):
        return [(int(xy[i]), int(xy[i + 1])) for i in range(0, len(xy), 2)]
    return [(int(p[0]), int(p[1])) for p in xy]


def Draw(im, mode=None):
    return ImageDraw(im, mode)

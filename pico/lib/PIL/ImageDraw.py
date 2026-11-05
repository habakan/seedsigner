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


def replay(ops, dx, dy, clip):
    """Draws `ops` offset by (dx, dy) inside `clip`, which is at most a band of rows: what lies wholly
    outside it is skipped here, before the per-row and per-glyph work in Python."""
    for op in ops:
        k = op[0]
        if k in ("rect", "rrect", "ellipse", "arc") and (dy + op[4] < clip[1] or dy + op[2] >= clip[3]):
            continue
        if k == "shade":
            _, x0, y0, x1, y1, c, a, holes = op
            for r in _less(x0, y0, x1, y1, holes):
                _gfx.shade(dx + r[0], dy + r[1], dx + r[2] + 1, dy + r[3] + 1, c, a, clip[0], clip[1], clip[2], clip[3])
            continue
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
            _gfx.shape(False, x0, y0, x1, y1, r, -1 if fill is None else fill, -1 if outline is None else outline,
                       width, dx, dy, clip[0], clip[1], clip[2], clip[3])
        elif k == "ellipse":
            _, x0, y0, x1, y1, fill, outline, width = op
            _gfx.shape(True, x0, y0, x1, y1, 0, -1 if fill is None else fill, -1 if outline is None else outline,
                       width, dx, dy, clip[0], clip[1], clip[2], clip[3])
        elif k == "line":
            _, pts, c, width = op
            ys = [p[1] for p in pts]
            if dy + max(ys) + width < clip[1] or dy + min(ys) - width >= clip[3]:
                continue
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                _line(ax, ay, bx, by, c, width, dx, dy, clip)
        elif k == "arc":
            _, x0, y0, x1, y1, start, end, c, width = op
            _arc(x0, y0, x1, y1, start, end, c, width, dx, dy, clip)
        elif k == "text":
            _, x, y, text, font, c, anchor, placed = op
            if dy + y + 2 * font.size < clip[1] or dy + y - 2 * font.size >= clip[3]:
                continue
            _gfx.glyphs(placed, font.bitmaps, c, dx, dy, clip[0], clip[1], clip[2], clip[3])
        elif k == "qr":
            _, code, border, x, y, w, h, fg, bg, style = op
            _gfx.qr(code, border, dx + x, dy + y, w, h, fg, bg, style, clip[0], clip[1], clip[2], clip[3])
        elif k == "pix":
            _, pixels, w, h = op
            _gfx.blit(pixels, w, h, dx, dy, clip[0], clip[1], clip[2], clip[3])
        elif k == "cam":
            _gfx.camera(dx, dy, clip[0], clip[1], clip[2], clip[3])
        elif k == "img":
            _, sub, x, y, w, h = op
            c = _clip(clip, (dx + x, dy + y, dx + x + w, dy + y + h))
            if c[0] < c[2] and c[1] < c[3]:
                replay(sub, dx + x, dy + y, c)
        elif k == "scale":
            _, sub, sx, sy = op
            replay(_scaled(sub, sx, sy), dx, dy, clip)


def _scaled(ops, sx, sy):
    """What a supersampled image's resize comes to: shapes and lines scale, text takes the font at the scaled
    size, and images and QR codes their scaled box."""
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
        elif op[0] == "line":
            _, pts, c, width = op
            out.append(("line", [(int(x * sx + 0.5), int(y * sy + 0.5)) for x, y in pts], c,
                        max(1, int(width * min(sx, sy) + 0.5))))
        elif op[0] in ("rrect", "ellipse", "arc"):
            # The box scales; a radius and an outline's width scale with it, to at least a pixel
            k, x0, y0, x1, y1 = op[:5]
            box = (int(x0 * sx), int(y0 * sy), int((x1 + 1) * sx) - 1, int((y1 + 1) * sy) - 1)
            w = max(1, int(op[-1] * min(sx, sy) + 0.5))
            if k == "rrect":
                out.append((k,) + box + (int(op[5] * min(sx, sy) + 0.5), op[6], op[7], w))
            elif k == "ellipse":
                out.append((k,) + box + (op[5], op[6], w))
            else:
                out.append((k,) + box + (op[5], op[6], op[7], w))
        elif op[0] == "text":
            _, x, y, text, font, c, anchor, placed = op
            out.append(text_op(int(x * sx + 0.5), int(y * sy + 0.5), text,
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
        if fill is not None and _Image.rgba(fill, self.mode)[3] == 0 and self.im.ops and self.im.ops[0][0] == "shade":
            self.im.ops[0][7].append((x0, y0, x1, y1))  # a hole in the image's translucent background
            fill = None
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
        # Angles a turn apart are one arc, kept as one so add() can drop it (the loading spinner's grow forever)
        s = start % 360
        self.im.add(("arc", x0, y0, x1, y1, s, s + end - start, self._c(fill), width))

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
                self.im.add(text_op(x, y + i * step, line, font, c, anchor or "la"))
            return
        self.im.add(text_op(x, y, text, font, c, anchor))

    def textbbox(self, xy, text, font=None, anchor=None, *args, **kwargs):
        b = font.getbbox(text, anchor=anchor)
        return (xy[0] + b[0], xy[1] + b[1], xy[0] + b[2], xy[1] + b[3])

    def textlength(self, text, font=None, *args, **kwargs):
        return font.getlength(text)


def _less(x0, y0, x1, y1, holes):
    """The box less the holes, as boxes, all inclusive."""
    boxes = [(x0, y0, x1, y1)]
    for hx0, hy0, hx1, hy1 in holes:
        out = []
        for a0, b0, a1, b1 in boxes:
            if hx0 > a1 or hx1 < a0 or hy0 > b1 or hy1 < b0:
                out.append((a0, b0, a1, b1))
                continue
            if b0 < hy0:
                out.append((a0, b0, a1, hy0 - 1))
            if hy1 < b1:
                out.append((a0, hy1 + 1, a1, b1))
            top, bottom = max(b0, hy0), min(b1, hy1)
            if a0 < hx0:
                out.append((a0, top, hx0 - 1, bottom))
            if hx1 < a1:
                out.append((hx1 + 1, top, a1, bottom))
        boxes = out
    return boxes


def text_op(x, y, text, font, c, anchor):
    """A text op, with its glyphs placed once here, `<hhBBI` each, for _gfx.glyphs to draw in every band."""
    import struct
    placed = bytearray()
    for gx, gy, w, h, off in font.glyphs(text, x, y, anchor):
        placed += struct.pack("<hhBBI", gx, gy, w, h, off)
    return ("text", x, y, text, font, c, anchor, bytes(placed))


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

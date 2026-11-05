"""
PIL's Image for SeedSigner on the Pico. An image is a list of drawing operations, not pixels: pasting
copies them and the display replays them, a band of rows at a time (pico/lib/seedsigner/hardware/displays/
ST7789.py), so no image costs a pixel buffer, the screen included.
"""
try:
    import _gfx
except ImportError:  # CPython, testing: pico/tests/gfx_sim.py stands in
    import gfx_sim as _gfx

W, H = _gfx.WIDTH, _gfx.HEIGHT

NAMES = {"black": (0, 0, 0), "white": (255, 255, 255), "red": (255, 0, 0), "green": (0, 128, 0),
         "blue": (0, 0, 255), "orange": (255, 165, 0), "darkorange": (255, 140, 0), "yellow": (255, 255, 0),
         "gray": (128, 128, 128), "grey": (128, 128, 128)}


class Resampling:
    NEAREST, BOX, BILINEAR, HAMMING, BICUBIC, LANCZOS = 0, 4, 2, 5, 3, 1


NEAREST, LANCZOS, BICUBIC, BILINEAR = 0, 1, 3, 2


def rgba(c, mode="RGB"):
    """(r, g, b, a) for any colour PIL takes, or None."""
    if c is None:
        return None
    if isinstance(c, int):
        if mode in ("L", "1"):
            v = 255 if (mode == "1" and c) else c
            return (v, v, v, 255)
        a = (c >> 24) & 255 if mode == "RGBA" else 255
        return (c & 255, (c >> 8) & 255, (c >> 16) & 255, a)
    if isinstance(c, str):
        if c.startswith("#"):
            h = c[1:]
            if len(h) in (3, 4):
                h = "".join(ch * 2 for ch in h)
            v = [int(h[i:i + 2], 16) for i in range(0, len(h), 2)]
            return tuple(v) if len(v) == 4 else (v[0], v[1], v[2], 255)
        return NAMES[c.lower()] + (255,)
    c = tuple(c)
    if len(c) == 1:
        c = (c[0],) * 3
    return c if len(c) == 4 else (c[0], c[1], c[2], 255)


def c332(c):
    """The framebuffer's palette index for a colour (pico/modules/gfx/modgfx.c)."""
    return _gfx.colour(c[0], c[1], c[2])


class Image:
    def __init__(self, mode, size, color=None):
        self.mode = mode
        self.size = (int(size[0]), int(size[1]))
        self.ops, self.boxes = [], []  # boxes: each op's extent, kept by add() for its pruning
        self.dirty = None  # what add() changed since the display last showed this image, inclusive
        bg = rgba(color, mode) if color is not None else (rgba(0, mode) if mode != "RGBA" else None)
        if bg is not None and 0 < bg[3] < 255 and mode == "RGBA":
            # Translucent: it dims what it is pasted over, less the holes fully transparent rectangles punch
            self.ops.append(("shade", 0, 0, self.size[0] - 1, self.size[1] - 1, c332(bg), bg[3] * 15 // 255, []))
        elif bg is not None and bg[3]:
            self.ops.append(("rect", 0, 0, self.size[0] - 1, self.size[1] - 1, c332(bg), None, 1))

    @property
    def width(self):
        return self.size[0]

    @property
    def height(self):
        return self.size[1]

    def add(self, op):
        # What an opaque op hides needn't be kept: the canvas is drawn over for every screen, and parts of
        # it (a keyboard's keys) for every button press, which would otherwise pile up until the heap ran out
        whole = (0, 0, self.size[0] - 1, self.size[1] - 1)
        if covers(op, self.size[0], self.size[1]):
            self.ops, self.boxes, self.dirty = [op], [box(op)], whole
            return
        b = box(op) or whole
        d = self.dirty
        self.dirty = b if d is None else (min(d[0], b[0]), min(d[1], b[1]), max(d[2], b[2]), max(d[3], b[3]))
        if len(self.boxes) != len(self.ops):
            self.boxes = [box(o) for o in self.ops]
        cover = opaque(op)
        if cover or op[0] == "rect" and op[6] is not None or op[0] in ("line", "arc"):
            keep = [i for i, (o, b) in enumerate(zip(self.ops, self.boxes)) if not hidden(o, b, op, cover)]
            if len(keep) < len(self.ops):
                self.ops, self.boxes = [self.ops[i] for i in keep], [self.boxes[i] for i in keep]
        self.ops.append(op)
        self.boxes.append(box(op))

    def paste(self, im, box=None, mask=None):
        if not isinstance(im, Image):  # a colour fills the box
            x0, y0 = (int(box[0]), int(box[1])) if box else (0, 0)
            x1, y1 = (int(box[2]), int(box[3])) if box and len(box) == 4 else (self.size[0], self.size[1])
            self.add(("rect", x0, y0, x1 - 1, y1 - 1, c332(rgba(im, self.mode)), None, 1))
            return
        x, y = (int(box[0]), int(box[1])) if box else (0, 0)
        self.add(("img", im.snapshot(), x, y, im.size[0], im.size[1]))

    def snapshot(self):
        """What this image is now, kept apart from what is drawn on it later."""
        return list(self.ops)

    def crop(self, box=None):
        x0, y0, x1, y1 = [int(v) for v in box] if box else (0, 0, self.size[0], self.size[1])  # PIL takes floats
        out = Image("RGBA", (x1 - x0, y1 - y0))
        out.mode = self.mode
        out.ops.append(("img", self.snapshot(), -x0, -y0, self.size[0], self.size[1]))
        return out

    def copy(self):
        return self.crop()

    def convert(self, mode=None, *args, **kwargs):
        out = self.copy()
        out.mode = mode or self.mode
        return out

    def resize(self, size, resample=None, box=None, reducing_gap=None):
        sx, sy = size[0] / self.size[0], size[1] / self.size[1]
        if sx == 1 and sy == 1:
            return self.copy()
        # Scaled once here, not at every replay: a supersampled text area is replayed in every band, and its
        # ops must stay plain for add() to see what a pasted copy covers (a scrolling label's frames)
        from PIL import ImageDraw
        out = Image("RGBA", size)
        out.mode = self.mode
        out.ops = ImageDraw._scaled(self.snapshot(), sx, sy)
        return out

    def rotate(self, angle, *args, **kwargs):
        if angle % 360:
            raise NotImplementedError("rotating a drawing")
        return self.copy()

    def filter(self, f):
        return self.copy()  # SHARPEN after a supersampled resize; the Pico draws at 1x

    def putalpha(self, alpha):
        pass  # the splash screen's fade-in; the Pico shows the logo at once

    def getbbox(self, *args, **kwargs):
        return (0, 0, self.size[0], self.size[1])

    def close(self):
        pass


def box(op):
    """The extent of `op`, inclusive, or None where it is not worked out (never pruned)."""
    k = op[0]
    if k in ("rect", "rrect", "ellipse", "arc", "shade"):
        return op[1], op[2], op[3], op[4]
    if k == "text":
        _, x, y, text, font, c, anchor, placed = op
        b = font.getbbox(text, anchor=anchor)
        return x + b[0], y + b[1], x + b[2], y + b[3]
    if k == "line":
        xs, ys, w = [p[0] for p in op[1]], [p[1] for p in op[1]], op[3]
        return min(xs) - w, min(ys) - w, max(xs) + w, max(ys) + w
    if k in ("pix", "cam"):
        return 0, 0, op[2] - 1, op[3] - 1
    if k == "qr":
        return op[3], op[4], op[3] + op[5] - 1, op[4] + op[6] - 1
    if k == "img":
        return op[2], op[3], op[2] + op[4] - 1, op[3] + op[5] - 1
    return None


def opaque(op):
    """Rectangles, inclusive, that `op` paints every pixel of."""
    k = op[0]
    if k == "rect" and op[5] is not None:
        return [op[1:5]]
    if k == "rrect" and op[6] is not None:
        x0, y0, x1, y1, r = op[1:6]
        return [(x0 + r, y0, x1 - r, y1), (x0, y0 + r, x1, y1 - r)]
    if k in ("pix", "cam", "qr") or (k == "img" and any(covers(o, op[4], op[5]) for o in op[1])):
        return [box(op)]
    return []


def hidden(old, b, new, cover):
    """Whether `new`, painting `cover`, hides all of `old`, whose extent is b."""
    if old[0] == "rrect" == new[0] and old[1:6] == new[1:6]:
        return True  # the same rounded rectangle again: a redrawn key
    if old[0] == "rect" == new[0] and old[1:5] == new[1:5] and old[5] is None and new[6] is not None and new[7] >= old[7]:
        return True  # an outline over one no wider: a warning screen's pulsing edges
    if old[0] == "line" == new[0] and old[1] == new[1] and new[3] >= old[3]:
        return True  # the same segments again, as wide or wider: a PSBT chart's animated pulses
    if old[0] == "arc" == new[0] and old[1:7] == new[1:7] and new[8] >= old[8]:
        return True  # the same arc again: the loading spinner erasing the arcs it drew two steps back
    return b is not None and any(c[0] <= b[0] and c[1] <= b[1] and b[2] <= c[2] and b[3] <= c[3] for c in cover)


def covers(op, w, h):
    """Whether `op` paints every pixel of a w x h image, opaquely."""
    k = op[0]
    if k == "rect":
        return op[5] is not None and op[1] <= 0 and op[2] <= 0 and op[3] >= w - 1 and op[4] >= h - 1
    if k in ("pix", "cam"):
        return op[2] >= w and op[3] >= h
    if k == "qr":
        return op[3] <= 0 and op[4] <= 0 and op[3] + op[5] >= w and op[4] + op[6] >= h
    if k == "img":
        _, sub, x, y, sw, sh = op
        return x <= 0 and y <= 0 and x + sw >= w and y + sh >= h and any(covers(o, sw, sh) for o in sub)
    return False


def new(mode, size, color=0):
    return Image(mode, size, color)


def alpha_composite(im1, im2):
    out = Image("RGBA", im1.size)
    out.mode = im1.mode
    out.ops = im1.snapshot() + im2.snapshot()
    return out


def open(fp, mode="r", formats=None):
    """One of SeedSigner's images, as pico/tools/make_images.py made it; the path names it."""
    import sys
    parts = str(fp).replace("\\", "/").split("/img/")[-1].rsplit(".", 1)[0].replace("-", "_").split("/")
    key = "pico_images.i_" + "_".join(parts)
    __import__(key)
    m = sys.modules[key]
    out = Image("RGB", (m.W, m.H), None)
    out.ops.append(("pix", m.PIXELS, m.W, m.H))
    return out

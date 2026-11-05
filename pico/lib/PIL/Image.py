"""
PIL's Image for SeedSigner on the Pico. An image is a list of drawing operations, not pixels: pasting
replays them, so a text area costs no buffer. The one image with pixels is the canvas, bound to _gfx's
framebuffer the first time the display shows it; what is drawn or pasted on it then lands at once.
"""
try:
    import _gfx
except ImportError:  # CPython, testing: pico/tests/gfx_sim.py stands in
    import gfx_sim as _gfx

W, H = _gfx.WIDTH, _gfx.HEIGHT

NAMES = {"black": (0, 0, 0), "white": (255, 255, 255), "red": (255, 0, 0), "green": (0, 128, 0),
         "blue": (0, 0, 255), "orange": (255, 165, 0), "yellow": (255, 255, 0), "gray": (128, 128, 128),
         "grey": (128, 128, 128)}


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
        self.ops = []
        self.bound = False  # the canvas, drawn straight into the framebuffer
        bg = rgba(color, mode) if color is not None else (rgba(0, mode) if mode != "RGBA" else None)
        if bg is not None and bg[3]:
            self.ops.append(("rect", 0, 0, self.size[0] - 1, self.size[1] - 1, c332(bg), None, 1))

    @property
    def width(self):
        return self.size[0]

    @property
    def height(self):
        return self.size[1]

    def add(self, op):
        if self.bound:
            from PIL import ImageDraw
            ImageDraw.replay([op], 0, 0, (0, 0, W, H))
        else:
            self.ops.append(op)

    def bind(self):
        """Becomes the framebuffer: what was recorded is drawn there, and from now on drawing is direct."""
        from PIL import ImageDraw
        ImageDraw.replay(self.ops, 0, 0, (0, 0, W, H))
        self.ops, self.bound = [], True

    def paste(self, im, box=None, mask=None):
        if not isinstance(im, Image):  # a colour fills the box
            x0, y0 = (box[0], box[1]) if box else (0, 0)
            x1, y1 = (box[2], box[3]) if box and len(box) == 4 else (self.size[0], self.size[1])
            self.add(("rect", x0, y0, x1 - 1, y1 - 1, c332(rgba(im, self.mode)), None, 1))
            return
        x, y = (box[0], box[1]) if box else (0, 0)
        self.add(("img", im.snapshot(), x, y, im.size[0], im.size[1]))

    def snapshot(self):
        """What this image is now, kept apart from what is drawn on it later."""
        if self.bound:
            raise NotImplementedError("the canvas cannot be pasted; it is the framebuffer")
        return list(self.ops)

    def crop(self, box=None):
        x0, y0, x1, y1 = box if box else (0, 0, self.size[0], self.size[1])
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
        out = Image("RGBA", size)
        out.mode = self.mode
        out.ops.append(("scale", self.snapshot(), sx, sy))
        return out

    def rotate(self, angle, *args, **kwargs):
        if angle % 360:
            raise NotImplementedError("rotating a drawing")
        return self.copy()

    def filter(self, f):
        return self.copy()  # SHARPEN after a supersampled resize; the Pico draws at 1x

    def getbbox(self, *args, **kwargs):
        return (0, 0, self.size[0], self.size[1])

    def close(self):
        pass


def new(mode, size, color=0):
    return Image(mode, size, color)


def alpha_composite(im1, im2):
    out = Image("RGBA", im1.size)
    out.mode = im1.mode
    out.ops = im1.snapshot() + im2.snapshot()
    return out


def open(fp, mode="r", formats=None):
    raise OSError("no image files on the Pico yet")

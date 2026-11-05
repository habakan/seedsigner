"""
ImageFont for the Pico: pico/tools/make_fonts.py's bitmaps behind PIL's basic layout, which puts glyphs
an advance apart with no kerning. getbbox answers as PIL's does; pico/tests/check_fonts.py compares them.
"""
import struct
import sys

_REC = 12  # <HhhBBI: advance, x0, y0, width, height, bitmap offset


class Layout:
    BASIC = 0


class FreeTypeFont:
    def __init__(self, path, size):
        self.path, self.size = path, size
        name = path.replace("\\", "/").rsplit("/", 1)[-1].rsplit(".", 1)[0].replace("-", "_")
        m = _load(name, size)
        self.ascent, self.descent = m.ASCENT, m.DESCENT
        self.chars, self.metrics, self.bitmaps = m.CHARS, m.METRICS, m.BITMAPS

    def getmetrics(self):
        return self.ascent, self.descent

    def glyph(self, ch):
        """(advance, x0, y0, w, h, offset), or None for a character the bitmaps lack."""
        i = self.chars.find(ch)
        return struct.unpack_from("<HhhBBI", self.metrics, i * _REC) if i >= 0 else None

    def getlength(self, text, *args, **kwargs):
        n = 0
        for ch in text:
            g = self.glyph(ch)
            n += g[0] if g else 0
        return float(n)

    def ink(self, text):
        """The union of the glyphs' boxes, at a baseline-left origin, or None for no ink."""
        pen, box = 0, None
        for ch in text:
            g = self.glyph(ch)
            if not g:
                continue
            if g[3] and g[4]:
                b = (pen + g[1], g[2], pen + g[1] + g[3], g[2] + g[4])
                box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
            pen += g[0]
        return box

    def offset(self, text, anchor):
        """Where `anchor` puts the baseline-left origin, relative to the point the text is drawn at."""
        anchor = anchor or "la"
        length = int(self.getlength(text))
        h, v = anchor[0], anchor[1]
        ox = 0 if h == "l" else -((length + 1) // 2) if h == "m" else -length
        if v == "s":
            oy = 0
        elif v == "a":
            oy = self.ascent
        elif v == "d":
            oy = -self.descent
        elif v == "m":
            oy = (self.ascent - self.descent + 1) // 2
        else:  # "t": the top of this text's ink
            box = self.ink(text)
            oy = -box[1] if box else 0
        return ox, oy

    def getbbox(self, text, mode="", direction=None, features=None, language=None, stroke_width=0, anchor=None):
        """PIL's: across from the origin to past the last advance or ink, whichever is further; down the ink."""
        if not text:
            return (0, 0, 0, 0)
        ox, oy = self.offset(text, anchor)
        length = int(self.getlength(text))
        box = self.ink(text) or (0, 0, 0, 0)
        return (min(0, box[0]) + ox, box[1] + oy, max(length, box[2]) + ox, box[3] + oy)

    def glyphs(self, text, x, y, anchor=None):
        """(x, y, w, h, offset) of each inked glyph of `text` drawn at (x, y) with `anchor`."""
        ox, oy = self.offset(text, anchor)
        pen = x + ox
        for ch in text:
            g = self.glyph(ch)
            if not g:
                continue
            if g[3] and g[4]:
                yield pen + g[1], y + oy + g[2], g[3], g[4], g[5]
            pen += g[0]


_cache = {}


def _load(name, size):
    """The bitmaps' module for this font at `size`, or at the nearest size made."""
    key = "pico_fonts.f_%s_%d" % (name, size)
    if key not in _cache:
        try:
            __import__(key)
            _cache[key] = sys.modules[key]
        except ImportError:
            import pico_fonts
            made = getattr(pico_fonts, "SIZES", {}).get(name)
            if not made:
                raise OSError("no bitmaps for %s at %d" % (name, size))
            nearest = min(made, key=lambda s: abs(s - size))
            _cache[key] = _load(name, nearest)
    return _cache[key]


def truetype(font=None, size=10, index=0, encoding="", layout_engine=None):
    return FreeTypeFont(font, size)

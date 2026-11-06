"""
SeedSigner's fonts as bitmaps, for MicroPython, which cannot render TrueType. One module per font and
size, of bytes only, so frozen it costs flash and no heap.

    python3 pico/tools/make_fonts.py OUT_DIR FONTS_DIR fonts_used.json de ja ...

fonts_used.json is {locale: {"Font-Name:size": chars}} from rendering every screen (pico/tools/record_fonts.py);
English and the locales named are made, from FONTS_DIR and the translations' fonts beside it.
Text fonts get all of printable ASCII besides; icon fonts every icon SeedSigner names. Each glyph is its
ink box at the baseline, as PIL's getbbox(ch, anchor="ls") gives it, with 4-bit alpha.
"""
import json
import pathlib
import struct
import sys

from PIL import Image, ImageDraw, ImageFont

ICON_FONTS = ("Font_Awesome_6_Free-Solid-900", "seedsigner-icons")


sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))


def icon_chars():
    from seedsigner.gui.components import FontAwesomeIconConstants, SeedSignerIconConstants
    chars = set()
    for cls in (FontAwesomeIconConstants, SeedSignerIconConstants):
        for k, v in vars(cls).items():
            if k.isupper() and isinstance(v, str) and len(v) == 1:
                chars.add(v)
    return chars


def glyph(font, ch):
    x0, y0, x1, y1 = font.getbbox(ch, anchor="ls")
    w, h = max(x1 - x0, 0), max(y1 - y0, 0)
    packed = bytearray()
    if w and h:
        img = Image.new("L", (w, h), 0)
        ImageDraw.Draw(img).text((-x0, -y0), ch, fill=255, font=font, anchor="ls")
        px = img.tobytes()
        for row in range(h):
            line = [(px[row * w + i] * 15 + 127) // 255 for i in range(w)] + [0]
            packed += bytes((line[i] << 4) | line[i + 1] for i in range(0, w, 2))
    return int(round(font.getlength(ch))), x0, y0, w, h, bytes(packed)


def main():
    from seedsigner.gui.components import GUIConstants
    out, fonts_dir, locales = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), ["en"] + sys.argv[4:]
    used = {}
    for locale, fonts in json.load(open(sys.argv[3])).items():
        for key, chars in fonts.items():
            if locale in locales:
                used[key] = "".join(sorted(set(used.get(key, "")) | set(chars)))
    paths = [p for d in (fonts_dir, fonts_dir.parent / "seedsigner-translations/fonts") for p in d.iterdir()]
    # The language picker names every language in its own font; a build keeps only its languages' fonts
    own = {f for loc, f in GUIConstants.BASE_LOCALE_FONTS.items() if loc in locales or loc == "default"}
    foreign = set(GUIConstants.BASE_LOCALE_FONTS.values()) - own
    out.mkdir(parents=True, exist_ok=True)
    icons = icon_chars()
    sizes = {}
    ascii_ = {chr(c) for c in range(32, 127)}
    total = 0
    for key, chars in sorted(used.items()):
        name, size = key.rsplit(":", 1)
        if name in foreign:
            continue
        path = next(p for p in paths if p.stem == name)
        font = ImageFont.truetype(str(path), int(size))
        # A newline is a glyph to PIL's single-line calls, .notdef's box and advance
        want = {c for c in chars if c >= " " or c == "\n"} | (icons if name in ICON_FONTS else ascii_ | {"\n"})
        chars_sorted = "".join(sorted(want))
        metrics, bitmaps = bytearray(), bytearray()
        for ch in chars_sorted:
            adv, x0, y0, w, h, bits = glyph(font, ch)
            metrics += struct.pack("<HhhBBI", adv, x0, y0, w, h, len(bitmaps))
            bitmaps += bits
        ascent, descent = font.getmetrics()
        mod = "f_%s_%s" % (name.replace("-", "_"), size)
        sizes.setdefault(name.replace("-", "_"), []).append(int(size))
        (out / (mod + ".py")).write_text(
            "# %s at %s, made by pico/tools/make_fonts.py\n" % (name, size) +
            "ASCENT = %d\nDESCENT = %d\nCHARS = %r\nMETRICS = %r\nBITMAPS = %r\n" % (
                ascent, descent, chars_sorted, bytes(metrics), bytes(bitmaps)))
        total += len(metrics) + len(bitmaps)
    # What ImageFont falls back on for a size not made: the nearest that was
    (out / "__init__.py").write_text("SIZES = %r\n" % {k: sorted(v) for k, v in sorted(sizes.items())})
    print("%d KB of glyphs" % (total // 1024))


main()

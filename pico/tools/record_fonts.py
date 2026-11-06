"""
Which fonts, sizes and characters SeedSigner's screens use: renders every screen with the screenshot
generator and records each getbbox and text call, in English and each locale named after the file, locale by
locale so a build takes only its own. Writes pico/fonts_used.json for make_fonts.py, and the getbbox calls with PIL's answers beside it for
pico/tests/check_fonts.py.

    .venv/bin/python pico/tools/record_fonts.py pico/fonts_used.json de es
"""
import json, os, sys
from PIL import ImageDraw, ImageFont
used, cur = {}, {}
calls = []
def note(font, text):
    key = "%s:%d" % (os.path.basename(font.path).rsplit(".", 1)[0], font.size)
    cur.setdefault(key, set()).update(text)
_text, _bbox, _len = ImageDraw.ImageDraw.text, ImageFont.FreeTypeFont.getbbox, ImageFont.FreeTypeFont.getlength
def text(self, xy, *a, **k):
    t = a[0] if a else k.get("text")
    f = k.get("font") or (a[2] if len(a) > 2 else None)
    if f is not None and isinstance(t, str): note(f, t)
    return _text(self, xy, *a, **k)
def getbbox(self, *a, **k):
    t = a[0] if a else k.get("text")
    r = _bbox(self, *a, **k)
    if isinstance(t, str):
        note(self, t)
        calls.append([os.path.basename(self.path).rsplit(".", 1)[0], self.size, t, k.get("anchor"), list(r)])
    return r
ImageDraw.ImageDraw.text = text
ImageFont.FreeTypeFont.getbbox = getbbox
import pytest
sys.path.insert(0, "src")
from seedsigner.models import psbt_parser
psbt_parser.PSBTParser._check_with_bitwasm = lambda self: None  # the generator's PSBTs predate the wasm cross-check
rc = 0
for locale in ["en"] + sys.argv[2:]:
    cur = used[locale] = {}
    rc |= pytest.main(["-q", "-p", "no:cacheprovider", "tests/screenshot_generator/generator.py", "--locale", locale])
json.dump({loc: {k: "".join(sorted(v)) for k, v in sorted(d.items())} for loc, d in used.items()},
          open(sys.argv[1], "w"), indent=1, ensure_ascii=False)
uniq = {json.dumps(c) for c in calls}
json.dump([json.loads(c) for c in sorted(uniq)], open(sys.argv[1].replace(".json", "_bbox.json"), "w"))
print("rc", rc, len(set().union(*used.values())), "font sizes", len(uniq), "getbbox calls")

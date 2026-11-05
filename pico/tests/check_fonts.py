"""
The bitmap fonts' getbbox and getlength against PIL's, on CPython: every getbbox call rendering all the
screens made (build/pico/fonts_used_bbox.json) and random ASCII strings in every font and anchor.

    python3 pico/tests/check_fonts.py build/pico/fonts build/pico/fonts_used_bbox.json
"""
import importlib.util, json, pathlib, random, sys

root = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, sys.argv[1])
spec = importlib.util.spec_from_file_location("pico_imagefont", root / "pico/lib/PIL/ImageFont.py")
ours = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ours)
from PIL import ImageFont

fonts_dir = root / "src/seedsigner/resources/fonts"
paths = {p.stem: str(p) for p in fonts_dir.iterdir()}
mine, theirs, bad, n = {}, {}, [], 0


def pair(name, size):
    k = (name, size)
    if k not in mine:
        mine[k] = ours.truetype(paths[name], size)
        theirs[k] = ImageFont.truetype(paths[name], size)
    return mine[k], theirs[k]


cases = [(c[0], c[1], c[2], c[3]) for c in json.load(open(sys.argv[2])) if c[0] in paths]
rnd = random.Random(1)
made = sorted({(c[0], c[1]) for c in cases})
for name, size in made:
    if name.startswith(("Font_Awesome", "seedsigner-icons")):
        continue
    for _ in range(200):
        t = "".join(chr(rnd.randint(32, 126)) for _ in range(rnd.randint(1, 20)))
        cases.append((name, size, t, rnd.choice(["ls", "la", "lt", "ms", "mt", "rm", "rs", None])))
for name, size, text, anchor in cases:
    a, b = pair(name, size)
    n += 1
    if a.getbbox(text, anchor=anchor) != b.getbbox(text, anchor=anchor) or a.getlength(text) != b.getlength(text):
        bad.append((name, size, text, anchor, a.getbbox(text, anchor=anchor), b.getbbox(text, anchor=anchor),
                    a.getlength(text), b.getlength(text)))
print("%d of %d agree" % (n - len(bad), n))
for b in bad[:15]:
    print(b)

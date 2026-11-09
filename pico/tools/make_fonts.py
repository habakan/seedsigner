"""
SeedSigner's fonts as bitmaps, through micropython-pil's tools/make_fonts.py: this picks what a build needs.

    python3 pico/tools/make_fonts.py OUT_DIR FONTS_DIR fonts_used.json de ja ...

fonts_used.json is {locale: {"Font-Name:size": chars}} from rendering every screen (pico/tools/record_fonts.py);
English and the locales named are made, from FONTS_DIR and the translations' fonts beside it. Text fonts get
all of printable ASCII besides; icon fonts every icon SeedSigner names.
"""
import json
import pathlib
import subprocess
import sys
import tempfile

ICON_FONTS = ("Font_Awesome_6_Free-Solid-900", "seedsigner-icons")
PICO = pathlib.Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PICO.parent / "src"))


def icon_chars():
    from seedsigner.gui.components import FontAwesomeIconConstants, SeedSignerIconConstants
    chars = set()
    for cls in (FontAwesomeIconConstants, SeedSignerIconConstants):
        for k, v in vars(cls).items():
            if k.isupper() and isinstance(v, str) and len(v) == 1:
                chars.add(v)
    return chars


def main():
    from seedsigner.gui.components import GUIConstants
    out, fonts_dir, locales = sys.argv[1], pathlib.Path(sys.argv[2]), ["en"] + sys.argv[4:]
    used = {}
    for locale, fonts in json.load(open(sys.argv[3])).items():
        for key, chars in fonts.items():
            if locale in locales:
                used[key] = "".join(sorted(set(used.get(key, "")) | set(chars)))
    # The language picker names every language in its own font; a build keeps only its languages' fonts
    own = {f for loc, f in GUIConstants.BASE_LOCALE_FONTS.items() if loc in locales or loc == "default"}
    foreign = set(GUIConstants.BASE_LOCALE_FONTS.values()) - own
    icons = "".join(sorted(icon_chars()))
    spec = {k: c + icons if k.rsplit(":", 1)[0] in ICON_FONTS else c
            for k, c in used.items() if k.rsplit(":", 1)[0] not in foreign}
    spec["_icons"] = list(ICON_FONTS)
    with tempfile.NamedTemporaryFile("w", suffix=".json") as f:
        json.dump(spec, f)
        f.flush()
        subprocess.run([sys.executable, str(PICO / "third_party/micropython-pil/tools/make_fonts.py"), out, f.name,
                        str(fonts_dir), str(fonts_dir.parent / "seedsigner-translations/fonts")], check=True)


main()

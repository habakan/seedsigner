"""
SeedSigner's .mo catalogs for the locales named, one module each: the catalog's bytes, which pico/lib/gettext.py
searches in place, and its Plural-Forms as Python, converted here since MicroPython cannot parse C.

    python3 pico/tools/make_l10n.py OUT_DIR L10N_DIR de es ...
"""
import gettext
import pathlib
import sys

out, src, locales = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3:]
out.mkdir(parents=True, exist_ok=True)
(out / "__init__.py").write_text("LOCALES = %r\n" % locales)
for locale in locales:
    mo = (src / locale / "LC_MESSAGES" / "messages.mo").read_bytes()
    with open(src / locale / "LC_MESSAGES" / "messages.mo", "rb") as f:
        info = gettext.GNUTranslations(f).info()
    plural = info.get("plural-forms", "plural=(n != 1);").split("plural=")[1].rstrip(";")
    expr, rest = gettext._parse(gettext._tokenize(plural))  # what gettext.c2py compiles, as source
    assert not rest
    (out / (locale + ".py")).write_text("MO = %r\n\n\ndef plural(n):\n    return int(%s)\n" % (mo, expr))
    print(locale, len(mo))

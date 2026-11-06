"""pico/lib/gettext.py over the catalogs pico/tools/make_l10n.py freezes, against CPython's gettext."""
import gettext
import importlib.util
import os
import pathlib
import struct
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
L10N = ROOT / "src/seedsigner/resources/seedsigner-translations/l10n"
LOCALES = ["ca", "cs", "de", "el", "es", "fr", "id", "it", "nl", "no", "pl", "pt_BR", "ru", "tr", "vi"]


def originals(mo: bytes) -> list:
    n, at = struct.unpack_from("<II", mo, 8)
    return [mo[o:o + ln].decode() for ln, o in (struct.unpack_from("<II", mo, at + 8 * i) for i in range(n))]


def test_every_message_as_cpython_translates_it(tmp_path, monkeypatch):
    subprocess.run([sys.executable, ROOT / "pico/tools/make_l10n.py", tmp_path / "pico_l10n", L10N, *LOCALES],
                   check=True, capture_output=True)
    monkeypatch.syspath_prepend(str(tmp_path))
    spec = importlib.util.spec_from_file_location("pico_gettext", ROOT / "pico/lib/gettext.py")
    pico = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pico)
    checked = 0
    for locale in LOCALES:
        mo = (L10N / locale / "LC_MESSAGES/messages.mo").read_bytes()
        with open(L10N / locale / "LC_MESSAGES/messages.mo", "rb") as f:
            want = gettext.GNUTranslations(f)
        monkeypatch.setitem(os.environ, "LANGUAGE", locale)
        for key in filter(None, originals(mo)):
            if "\0" in key:
                singular, plural = key.split("\0")
                for n in range(112):
                    assert pico.ngettext(singular, plural, n) == want.ngettext(singular, plural, n), (locale, n)
            else:
                assert pico.gettext(key) == want.gettext(key), (locale, key)
            checked += 1
        assert pico.gettext("not a message here") == "not a message here"
    monkeypatch.setitem(os.environ, "LANGUAGE", "en")
    assert pico.gettext("Settings") == "Settings" and pico.ngettext("input", "inputs", 2) == "inputs"
    assert checked > 1000


def test_the_language_menu_keeps_upstreams_order(tmp_path):
    subprocess.run([sys.executable, ROOT / "pico/tools/make_l10n.py", tmp_path, L10N, "vi", "de"],
                   check=True, capture_output=True)
    assert (tmp_path / "__init__.py").read_text() == "LOCALES = ['de', 'en', 'vi']\n"

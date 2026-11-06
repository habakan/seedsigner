# The catalogs pico/tools/make_l10n.py froze, as pico_l10n.<locale>: searched in place, in flash, rather than
# read into a dict on the heap. LANGUAGE is what Settings.load_locale sets
import os
import struct

_catalogs = {}


def _catalog():
    locale = os.environ.get("LANGUAGE", "en")
    if locale not in _catalogs:
        try:
            _catalogs[locale] = __import__("pico_l10n." + locale, None, None, ["MO"])
        except ImportError:
            _catalogs[locale] = None
    return _catalogs[locale]


def _find(mo, key):
    # msgfmt sorts the originals, so a binary search over their table
    n, originals, translations = struct.unpack_from("<III", mo, 8)
    lo, hi = 0, n
    while lo < hi:
        mid = (lo + hi) // 2
        length, at = struct.unpack_from("<II", mo, originals + 8 * mid)
        k = mo[at:at + length]
        if k == key:
            length, at = struct.unpack_from("<II", mo, translations + 8 * mid)
            return mo[at:at + length].decode()
        if k < key:
            lo = mid + 1
        else:
            hi = mid
    return None


def gettext(message):
    c = _catalog()
    return (c and message and _find(c.MO, message.encode())) or message


def ngettext(singular, plural, n):
    c = _catalog()
    found = c and _find(c.MO, singular.encode() + b"\0" + plural.encode())
    if not found:
        return singular if n == 1 else plural
    forms = found.split("\0")
    return forms[min(c.plural(n), len(forms) - 1)]


class NullTranslations:
    def gettext(self, message):
        return gettext(message)

    def ngettext(self, singular, plural, n):
        return ngettext(singular, plural, n)

    def install(self, names=None):
        pass


def translation(domain, localedir=None, languages=None, fallback=False):
    return NullTranslations()


def bindtextdomain(domain, localedir=None):
    pass


def textdomain(domain=None):
    pass

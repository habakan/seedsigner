# English only for now: the .mo catalogs are not on the device
class NullTranslations:
    def gettext(self, message):
        return message

    def ngettext(self, singular, plural, n):
        return singular if n == 1 else plural

    def install(self, names=None):
        pass


def translation(domain, localedir=None, languages=None, fallback=False):
    return NullTranslations()


def gettext(message):
    return message


def ngettext(singular, plural, n):
    return singular if n == 1 else plural


def bindtextdomain(domain, localedir=None):
    pass


def textdomain(domain=None):
    pass

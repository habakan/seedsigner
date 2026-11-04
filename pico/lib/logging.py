# What SeedSigner calls: getLogger and the level methods, which take logging's keyword arguments
# (exc_info=True above all). Only warnings and errors are printed: the device has a serial console at most
DEBUG, INFO, WARNING, ERROR, CRITICAL = 10, 20, 30, 40, 50
level = WARNING


class Logger:
    def __init__(self, name):
        self.name = name

    def _log(self, lvl, msg, args, kwargs):
        if lvl >= level:
            print("%s:%s:%s" % (("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")[lvl // 10 - 1], self.name, msg % args if args else msg))
            if kwargs.get("exc_info"):
                import sys
                e = sys.exc_info()[1] if hasattr(sys, "exc_info") else None
                if e is not None:
                    sys.print_exception(e)

    def debug(self, msg, *args, **kwargs):
        self._log(DEBUG, msg, args, kwargs)

    def info(self, msg, *args, **kwargs):
        self._log(INFO, msg, args, kwargs)

    def warning(self, msg, *args, **kwargs):
        self._log(WARNING, msg, args, kwargs)

    def error(self, msg, *args, **kwargs):
        self._log(ERROR, msg, args, kwargs)

    def exception(self, msg, *args, **kwargs):
        kwargs["exc_info"] = True
        self._log(ERROR, msg, args, kwargs)

    def setLevel(self, lvl):
        pass

    def isEnabledFor(self, lvl):
        return lvl >= level


_loggers = {}


def getLogger(name=None):
    if name not in _loggers:
        _loggers[name] = Logger(name or "root")
    return _loggers[name]


def basicConfig(**kwargs):
    global level
    level = kwargs.get("level", level)


def info(msg, *args, **kwargs):
    getLogger().info(msg, *args, **kwargs)

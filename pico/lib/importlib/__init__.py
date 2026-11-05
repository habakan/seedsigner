# import_module, as SeedSigner's controller preloads modules with it
import sys


def import_module(name, package=None):
    __import__(name)
    return sys.modules[name]

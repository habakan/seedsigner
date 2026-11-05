# traceback for SeedSigner on the rp2 port, which has no sys.exc_info: pico/tools/to_micropython.py hands
# print_exc and format_exc the exception of the except they are called in
import io
import sys


def format_exc(exc=None, *args, **kwargs):
    if exc is None:
        return ""
    import gc
    gc.collect()  # SeedSigner's error screen formats it right after whatever failed, often for want of memory
    buf = io.StringIO()
    sys.print_exception(exc, buf)
    return buf.getvalue()


def print_exc(exc=None, *args, **kwargs):
    if exc is not None:
        sys.print_exception(exc)


def format_exception(exc, *args, **kwargs):
    return [format_exc(exc if isinstance(exc, BaseException) else (args[0] if args else None))]

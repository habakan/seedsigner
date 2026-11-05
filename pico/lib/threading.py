# threading as SeedSigner uses it (Lock; Thread with start, is_alive, join, daemon) on MicroPython's
# _thread, which on the rp2 port runs one more thread, on the second core
import _thread
import time


def Lock():
    return _thread.allocate_lock()


class Thread:
    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None, daemon=None):
        self._target, self._args, self._kwargs = target, args, kwargs or {}
        self.name, self.daemon, self._alive = name, daemon, False

    def start(self):
        self._alive = True
        _thread.start_new_thread(self._bootstrap, ())

    def _bootstrap(self):
        try:
            self.run()
        finally:
            self._alive = False

    def run(self):
        if self._target:
            self._target(*self._args, **self._kwargs)

    def is_alive(self):
        return self._alive

    def join(self, timeout=None):
        start = time.ticks_ms()
        while self._alive and (timeout is None or time.ticks_diff(time.ticks_ms(), start) < timeout * 1000):
            time.sleep_ms(5)

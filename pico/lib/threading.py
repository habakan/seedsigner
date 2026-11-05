# threading as SeedSigner uses it (Lock; Thread with start, is_alive, join, daemon) on MicroPython's
# _thread, which on the rp2 port runs one more thread, on the second core
import _thread
import time


_core1 = None  # the Thread running on core1, if any


def Lock():
    return _thread.allocate_lock()


class Thread:
    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None, daemon=None):
        self._target, self._args, self._kwargs = target, args, kwargs or {}
        self.name, self.daemon, self._alive = name, daemon, False

    def start(self):
        # The rp2 port runs one thread besides the main one, on core1 (patches/: a GIL, a 16 KB static
        # stack). A second waits for a first that was told to stop, but not for one still running: a screen
        # with two (the PSBT overview's chart and its scrolling title) runs the first only
        deadline = time.ticks_add(time.ticks_ms(), 30000)
        while True:
            self._alive = True  # before core1 can run it and clear it; undone if it never starts
            try:
                _thread.start_new_thread(self._bootstrap, ())
                return
            except OSError:
                self._alive = False
                held = _core1
                if held is not None and getattr(held, "keep_running", True) and held._alive:
                    print("threading: core1 runs %s; %s does not run" % (type(held).__name__, type(self).__name__))
                    return
                if time.ticks_diff(deadline, time.ticks_ms()) < 0:
                    raise
                time.sleep_ms(50)

    def _bootstrap(self):
        global _core1
        _core1 = self
        try:
            self.run()
        finally:
            self._alive = False
            _core1 = None

    def run(self):
        if self._target:
            self._target(*self._args, **self._kwargs)

    def is_alive(self):
        return self._alive

    def join(self, timeout=None):
        start = time.ticks_ms()
        while self._alive and (timeout is None or time.ticks_diff(time.ticks_ms(), start) < timeout * 1000):
            time.sleep_ms(5)

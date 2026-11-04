# The part of pathlib SeedSigner uses: parent, resolve() and joining
import os


class Path:
    def __init__(self, *parts):
        self._p = "/".join(str(p) for p in parts) or "."

    def __str__(self):
        return self._p

    def __fspath__(self):
        return self._p

    def __truediv__(self, other):
        return Path(self._p.rstrip("/") + "/" + str(other))

    @property
    def parent(self):
        head = self._p.rstrip("/").rsplit("/", 1)
        return Path(head[0] if len(head) > 1 and head[0] else ("/" if self._p.startswith("/") else "."))

    @property
    def name(self):
        return self._p.rstrip("/").rsplit("/", 1)[-1]

    def resolve(self):
        return Path(os.path.abspath(self._p))

    def exists(self):
        return os.path.exists(self._p)

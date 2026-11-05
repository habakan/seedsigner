# super() for a mixin, a class with no bases of its own: MicroPython's looks only in the bases of the class it
# is called in, CPython's goes on to the class after the mixin in the instance's class's bases.
# pico/tools/to_micropython.py turns super() inside such a class into mixin_super(Mixin, self)


class mixin_super:
    def __init__(self, cls, obj):
        self.cls, self.obj = cls, obj

    def __getattr__(self, name):
        todo = [type(self.obj)]
        while todo:
            k = todo.pop(0)
            bases = k.__bases__
            if self.cls in bases:
                for b in bases[bases.index(self.cls) + 1:]:
                    f = getattr(b, name, None)
                    if f is not None:
                        obj = self.obj
                        return lambda *a, **kw: f(obj, *a, **kw)
            todo.extend(bases)
        raise AttributeError(name)

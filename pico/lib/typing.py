# Annotations are dropped at build time; these names only have to import
TYPE_CHECKING = False


class _Any:
    def __getitem__(self, item):
        return self

    def __call__(self, *args, **kwargs):
        return self


Any = List = Dict = Tuple = Optional = Union = Callable = Type = Set = Iterable = Sequence = ClassVar = _Any()


def __getattr__(name):
    return Any

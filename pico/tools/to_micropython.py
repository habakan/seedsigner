"""
Rewrites SeedSigner's Python for MicroPython, which keeps no annotations and so cannot run @dataclass:
each dataclass gets the __init__ the decorator would have made, and annotations are dropped.

    python3 pico/tools/to_micropython.py [--cpython] OUT_DIR SRC_DIR...

--cpython leaves traceback calls alone, which only pico/lib/traceback.py takes an exception in, so the
result can be checked against the test suite on CPython.

Fields are resolved across files by class name, bases first, as dataclasses orders them.
"""
import ast
import pathlib
import sys

MISSING = "_DC_MISSING"


def is_dataclass(node: ast.ClassDef) -> bool:
    return any(isinstance(d, ast.Name) and d.id == "dataclass" or
               isinstance(d, ast.Call) and getattr(d.func, "id", None) == "dataclass" for d in node.decorator_list)


def own_fields(node: ast.ClassDef) -> list:
    """(name, default expression or None, factory expression or None, init, owner) per annotated field."""
    out = []
    for st in node.body:
        if not isinstance(st, ast.AnnAssign) or not isinstance(st.target, ast.Name):
            continue
        if "ClassVar" in ast.unparse(st.annotation):
            continue
        default, factory, init = st.value, None, True
        if isinstance(st.value, ast.Call) and getattr(st.value.func, "id", None) == "field":
            default = None
            for kw in st.value.keywords:
                if kw.arg == "default":
                    default = kw.value
                elif kw.arg == "default_factory":
                    factory = kw.value
                elif kw.arg == "init":
                    init = ast.literal_eval(kw.value)
        out.append((st.target.id, default, factory, init, node))
    return out


class Registry:
    """Dataclasses by name. A base in the same file wins; one elsewhere must have a unique name."""
    def __init__(self):
        self.classes, self.file_of = {}, {}

    def add(self, path, tree):
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and is_dataclass(node):
                self.classes.setdefault(node.name, []).append(node)
                self.file_of[id(node)] = path

    def base(self, name, near):
        found = self.classes.get(name, [])
        same = [c for c in found if self.file_of[id(c)] == self.file_of[id(near)]]
        if same or len(found) == 1:
            return (same or found)[0]
        if found:
            sys.exit(f"base {name} of {near.name} is ambiguous: {len(found)} dataclasses have that name")
        return None

    def fields(self, node: ast.ClassDef) -> list:
        merged = {}
        for base in node.bases:
            name = base.id if isinstance(base, ast.Name) else getattr(base, "attr", None)
            found = self.base(name, node)
            if found is not None:
                for f in self.fields(found):
                    merged[f[0]] = f
        for f in own_fields(node):
            merged[f[0]] = f  # an override keeps its place, as in dataclasses
        return list(merged.values())


def make_init(node: ast.ClassDef, fields: list, base_of) -> ast.FunctionDef:
    """Defaults are read from the class that set them, never copied: a base's default may use names its
    own module imports and this one does not. Factories live on that class as staticmethods."""
    args, defaults, body = [], [], []
    for name, default, factory, init, owner in fields:
        where = ast.Name(name) if owner is node else ast.Attribute(base_of(name), name)
        if factory is not None:
            value = ast.parse(f"self._dc_factory_{name}()").body[0].value
        else:
            value = where if default is not None else ast.Constant(None)
        if not init:
            body.append(ast.parse(f"self.{name} = 0").body[0])
            body[-1].value = value
            continue
        args.append(ast.arg(name))
        if factory is not None:
            defaults.append(ast.Name(MISSING))
            st = ast.parse(f"self.{name} = _f if {name} is {MISSING} else {name}").body[0]
            st.value.body = value
            body.append(st)
            continue
        if default is not None:
            defaults.append(where)
        elif defaults:
            defaults.append(ast.Constant(None))  # dataclasses would refuse; keep the call working
        body.append(ast.parse(f"self.{name} = {name}").body[0])
    body += ast.parse("_p = getattr(self, '__post_init__', None)\nif _p:\n    _p()").body
    fn = ast.parse("def __init__(self): pass").body[0]
    fn.args.args = [ast.arg("self")] + args
    fn.args.defaults = defaults
    fn.body = body
    return fn


class Strip(ast.NodeTransformer):
    def __init__(self, fields, registry):
        self.fields, self.registry = fields, registry

    def visit_ClassDef(self, node):
        # list[Destination] as a base is list to CPython at runtime; MicroPython cannot subscript a type
        node.bases = [b.value if isinstance(b, ast.Subscript) else b for b in node.bases]
        if not node.bases and not CPYTHON:
            # A mixin's super() must reach the class after it in the instance's bases (pico/lib/pico_super.py)
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call) and getattr(sub.func, "id", None) == "super" and not sub.args:
                    sub.func.id = "mixin_super"
                    sub.args = [ast.Name(node.name), ast.Name("self")]
                    self.mixin_super = True
        if is_dataclass(node):
            fields = self.fields[id(node)]
            node.decorator_list = [d for d in node.decorator_list if not (
                isinstance(d, ast.Name) and d.id == "dataclass" or
                isinstance(d, ast.Call) and getattr(d.func, "id", None) == "dataclass")]
            for name, _, factory, _, owner in fields:
                if factory is not None and owner is node:
                    st = ast.parse(f"_dc_factory_{name} = staticmethod(_f)").body[0]
                    st.value.args[0] = factory
                    node.body.append(st)

            def base_of(name):
                for b in node.bases:
                    found = self.registry.base(b.id if isinstance(b, ast.Name) else getattr(b, "attr", None), node)
                    if found is not None and any(f[0] == name for f in self.fields[id(found)]):
                        return b
                raise SystemExit(f"{node.name}.{name}: no base has it")
            if not any(isinstance(s, ast.FunctionDef) and s.name == "__init__" for s in node.body):
                node.body.append(make_init(node, fields, base_of))
            if not any(isinstance(s, ast.FunctionDef) and s.name == "__eq__" for s in node.body):
                names = [f[0] for f in fields]
                mine = "(" + "".join(f"self.{n}, " for n in names) + ")"
                theirs = "(" + "".join(f"other.{n}, " for n in names) + ")"
                node.body += ast.parse(
                    "def __eq__(self, other):\n"
                    "    if other.__class__ is self.__class__:\n"
                    f"        return {mine} == {theirs}\n"
                    "    return NotImplemented").body
        self.generic_visit(node)
        return node

    def visit_AnnAssign(self, node):
        if node.value is None:
            return None
        if isinstance(node.value, ast.Call) and getattr(node.value.func, "id", None) == "field":
            dflt = [k.value for k in node.value.keywords if k.arg == "default"]
            node.value = dflt[0] if dflt else ast.Constant(None)
        return ast.Assign([node.target], node.value)

    def visit_arg(self, node):
        node.annotation = None
        return node

    def visit_FunctionDef(self, node):
        node.returns = None
        if not CPYTHON and any(a.arg == "e" for a in node.args.args):  # handle_exception formats e outside its except
            self.hand_exception(node.body, "e")
        self.generic_visit(node)
        return node

    @staticmethod
    def hand_exception(body, name):
        """traceback.print_exc() and format_exc() find the exception with sys.exc_info, which the rp2
        port lacks; they are handed it instead (pico/lib/traceback.py)."""
        for sub in ast.walk(ast.Module(body, [])):
            f = getattr(sub, "func", None)
            if (isinstance(sub, ast.Call) and isinstance(f, ast.Attribute) and f.attr in ("print_exc", "format_exc")
                    and isinstance(f.value, ast.Name) and f.value.id == "traceback" and not sub.args):
                sub.args = [ast.Name(name)]

    def visit_ExceptHandler(self, node):
        if CPYTHON:
            self.generic_visit(node)
            return node
        if node.name is None:
            if node.type is None:  # a bare except is BaseException's, which can take a name
                node.type = ast.Name("BaseException")
            node.name = "_exc"
        self.hand_exception(node.body, node.name)
        self.generic_visit(node)
        return node

    def visit_Expr(self, node):
        # logger.info / debug never print on the Pico (pico/lib/logging.py stops at WARNING), but their
        # f-strings are built anyway: the controller's renders the whole back stack on every screen
        f = getattr(node.value, "func", None)
        if (not CPYTHON and isinstance(f, ast.Attribute) and f.attr in ("info", "debug")
                and isinstance(f.value, ast.Name) and f.value.id == "logger"):
            return ast.Pass()
        self.generic_visit(node)
        return node

    def visit_FormattedValue(self, node):
        # MicroPython's format ignores __format__ (pico/lib/pico_format.py); only a constant spec is seen
        self.generic_visit(node)
        spec = node.format_spec
        if CPYTHON or spec is None or not all(isinstance(v, ast.Constant) for v in spec.values):
            return node
        text = "".join(v.value for v in spec.values)
        node.value = ast.Call(ast.Name("pico_fmt"), [node.value, ast.Constant(text)], [])
        node.format_spec = None
        return node

    def visit_Name(self, node):
        # MicroPython raises OSError, with an errno, where CPython raises these subclasses of it
        if node.id in ("FileNotFoundError", "PermissionError", "IsADirectoryError", "NotADirectoryError", "FileExistsError"):
            node.id = "OSError"
        return node

    def visit_Call(self, node):
        # cls.__new__(cls) for a class without its own __new__: MicroPython's classes only have
        # object's, reached as object.__new__ (no SeedSigner class defines one)
        self.generic_visit(node)
        f = node.func
        if (isinstance(f, ast.Attribute) and f.attr == "__new__" and isinstance(f.value, ast.Name)
                and len(node.args) == 1 and isinstance(node.args[0], ast.Name) and node.args[0].id == f.value.id):
            node.func = ast.Attribute(ast.Name("object"), "__new__")
        # MicroPython has no format() built-in: format(x, spec) is pico_fmt(x, spec), as f-strings are
        if not CPYTHON and isinstance(f, ast.Name) and f.id == "format" and len(node.args) == 2:
            node.func = ast.Name("pico_fmt")
        return node

    def visit_ImportFrom(self, node):
        if node.module in ("__future__", "dataclasses"):
            return None
        return node


CPYTHON = False


def main():
    global CPYTHON
    args = sys.argv[1:]
    if args and args[0] == "--cpython":
        CPYTHON, args = True, args[1:]
    out, srcs = pathlib.Path(args[0]), [pathlib.Path(p) for p in args[1:]]
    # resources/ holds the translations' own tooling, not anything SeedSigner runs
    files = [(s, p) for s in srcs for p in sorted(s.rglob("*.py")) if "resources" not in p.relative_to(s).parts]
    trees = {p: ast.parse(p.read_text(), str(p)) for _, p in files}
    registry = Registry()
    for p, t in trees.items():
        registry.add(p, t)
    # Every class's fields before any is rewritten: rewriting turns a base's annotations into plain assignments
    fields = {id(c): registry.fields(c) for cs in registry.classes.values() for c in cs}
    for src, p in files:
        tree = Strip(fields, registry).visit(trees[p])
        ast.fix_missing_locations(tree)
        text = ast.unparse(tree)
        if "pico_fmt(" in text:
            text = "from pico_format import fmt as pico_fmt\n" + text
        if "mixin_super(" in text:
            text = "from pico_super import mixin_super\n" + text
        if MISSING in text:
            text = f"{MISSING} = object()\n" + text
        dest = out / src.name / p.relative_to(src)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text + "\n")
    print(f"{len(files)} files, {len(registry.classes)} dataclasses")


main()

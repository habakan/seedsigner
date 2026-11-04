"""
Rewrites SeedSigner's Python for MicroPython, which keeps no annotations and so cannot run @dataclass:
each dataclass gets the __init__ the decorator would have made, and annotations are dropped.

    python3 pico/tools/to_micropython.py OUT_DIR SRC_DIR...

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
        self.generic_visit(node)
        return node

    def visit_ImportFrom(self, node):
        if node.module in ("__future__", "dataclasses"):
            return None
        return node


def main():
    out, srcs = pathlib.Path(sys.argv[1]), [pathlib.Path(p) for p in sys.argv[2:]]
    files = [(s, p) for s in srcs for p in sorted(s.rglob("*.py"))]
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
        if MISSING in text:
            text = f"{MISSING} = object()\n" + text
        dest = out / src.name / p.relative_to(src)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text + "\n")
    print(f"{len(files)} files, {len(registry.classes)} dataclasses")


main()

import fnmatch
from ast import literal_eval, parse, AST, FunctionDef, ClassDef
from itertools import zip_longest
import textwrap
from typing import Iterable, List, Optional, Tuple


def find_symbol_nodes(
    code: str, symbols: Iterable[str]
) -> List[Tuple[AST, Optional[str]]]:
    "Returns ast Nodes matching symbols"
    # list of (AST, None-or-class-name)
    matches = []
    module = parse(code)
    for node in module.body:
        if not isinstance(node, (ClassDef, FunctionDef)):
            continue
        name = getattr(node, "name", None)
        if match(name, symbols):
            matches.append((node, None))
        # If it's a class search its methods too
        if isinstance(node, ClassDef):
            for child in node.body:
                if isinstance(child, FunctionDef):
                    qualified_name = f"{name}.{child.name}"
                    if match(qualified_name, symbols):
                        matches.append((child, name))

    return matches


def code_for_node(
    code: str, node: AST, class_name: str, signatures: bool
) -> Tuple[str, int]:
    "Returns the code for a given node"
    lines = code.split("\n")
    start = None
    end = None
    if signatures:
        if isinstance(node, FunctionDef):
            definition, lineno = function_definition(node), node.lineno
            if class_name:
                definition = "    " + definition
            return definition, lineno
        elif isinstance(node, ClassDef):
            return class_definition(node), node.lineno
        else:
            # Not a function or class, fall back on just the line
            start = node.lineno - 1
            end = node.lineno
    else:
        # If the node has decorator_list, include those too
        if getattr(node, "decorator_list", None):
            start = node.decorator_list[0].lineno - 1
        else:
            start = node.lineno - 1
        end = node.end_lineno
    output = "\n".join(lines[start:end])
    # If it's in a class, indent it 4 spaces
    return output, start + 1


def match(name: str, symbols: Iterable[str]) -> bool:
    "Returns True if name matches any of the symbols, resolving wildcards"
    if name is None:
        return False
    for search in symbols:
        if "*" not in search:
            # Exact matches only
            if name == search:
                return True
        elif search.count(".") == 1:
            # wildcards are supported either side of the dot
            if "." in name:
                class_match, method_match = search.split(".")
                class_name, method_name = name.split(".")
                if fnmatch.fnmatch(class_name, class_match) and fnmatch.fnmatch(
                    method_name, method_match
                ):
                    return True
        else:
            if fnmatch.fnmatch(name, search) and "." not in name:
                return True

    return False


def function_definition(function_node: AST):
    function_name = function_node.name

    all_args = [
        *function_node.args.posonlyargs,
        *function_node.args.args,
        *function_node.args.kwonlyargs,
    ]

    # For position only args like "def foo(a, /, b, c)"
    # we can look at the length of args.posonlyargs to see
    # if any are set and, if so, at what index the `/` should go
    position_of_slash = len(function_node.args.posonlyargs)

    # For func_keyword_only_args(a, *, b, c) the length of
    # the kwonlyargs tells us how many spaces back from the
    # end the star should be displayed
    position_of_star = len(all_args) - len(function_node.args.kwonlyargs)

    # function_node.args.defaults may have defaults
    # corresponding to function_node.args.args - but
    # if defaults has 2 and args has 3 then those
    # defaults correspond to the last two args
    defaults = [None] * (len(all_args) - len(function_node.args.defaults))
    defaults.extend(literal_eval(default) for default in function_node.args.defaults)

    arguments = []

    for i, (arg, default) in enumerate(zip_longest(all_args, defaults)):
        if position_of_slash and i == position_of_slash:
            arguments.append("/")
        if position_of_star and i == position_of_star:
            arguments.append("*")
        if getattr(arg.annotation, "id", None):
            arg_str = f"{arg.arg}: {arg.annotation.id}"
        else:
            arg_str = arg.arg

        if default:
            arg_str = f"{arg_str}={default}"

        arguments.append(arg_str)

    if function_node.args.vararg:
        arguments.append(f"*{function_node.args.vararg.arg}")

    if function_node.args.kwarg:
        arguments.append(f"**{function_node.args.kwarg.arg}")

    arguments_str = ", ".join(arguments)

    return_annotation = ""
    if function_node.returns:
        if hasattr(function_node.returns, "id"):
            return_annotation = f" -> {function_node.returns.id}"
        elif function_node.returns.value is None:
            # None shows as returns.value is None
            return_annotation = " -> None"

    return f"def {function_name}({arguments_str}){return_annotation}"


def class_definition(class_def):
    # Base classes
    base_classes = []
    for base in class_def.bases:
        if getattr(base, "id", None):
            base_classes.append(base.id)
    base_classes_str = ", ".join(base_classes)

    # Keywords (including metaclass)
    keywords = {k.arg: getattr(k.value, "id", str(k.value)) for k in class_def.keywords}
    metaclass = keywords.pop("metaclass", None)
    keyword_str = ", ".join([f"{k}=..." for k in keywords])

    if base_classes_str and keyword_str:
        signature = f"{base_classes_str}, {keyword_str}"
    elif base_classes_str:
        signature = base_classes_str
    elif keyword_str:
        signature = keyword_str
    else:
        signature = ""

    if metaclass:
        sep = ", " if signature else ""
        signature = f"{signature}{sep}metaclass={metaclass}"

    if signature:
        signature = f"({signature})"

    class_definition = f"class {class_def.name}{signature}"

    return class_definition

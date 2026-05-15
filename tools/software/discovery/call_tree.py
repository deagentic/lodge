"""
Call Tree Builder
Traces function call relationships across the codebase.
Produces a directed graph of who-calls-whom, exported as both
a nested dict and DOT format (Graphviz) for visualization.
"""

from pathlib import Path
import ast
import re
from collections import defaultdict


def _process_file_edges(f: Path, rel: str, lang: str) -> list[dict]:
    if lang == "Python" and f.suffix == ".py":
        return _extract_calls_python(f, rel)
    if lang in ("C", "C++") and f.suffix in (".c", ".cpp", ".cc", ".cxx", ".h", ".hpp"):
        return _extract_calls_c(f, rel)
    if lang in ("JavaScript", "TypeScript") and f.suffix in (
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
    ):
        return _extract_calls_js(f, rel)
    if lang == "C#" and f.suffix == ".cs":
        return _extract_calls_csharp(f, rel)
    return _extract_calls_generic(f, rel)


def _trace_module_flows(mod: dict, ep: str, graph: dict) -> list[dict]:
    flows = []
    for fn in mod.get("functions", []):
        flow = _trace_flow(fn["name"], graph, depth=0, max_depth=6, visited=set())
        if flow:
            flows.append({"entry": fn["name"], "file": ep, "flow": flow})
    return flows


def _trace_entry_flows(entry_points: list, structure: dict, graph: dict) -> list[dict]:
    entry_flows = []
    for ep in entry_points[:5]:
        for mod in structure.get("modules", []):
            if mod["path"] == ep:
                entry_flows.extend(_trace_module_flows(mod, ep, graph))
    return entry_flows


def build_call_tree(path: Path, tech_stack: dict, structure: dict) -> dict:
    """
    Build a call tree for the codebase.

    Returns:
        {
          edges: [{caller, callee, location, line}],
          graph: {function_name: [called_functions]},
          dot: str,              # Graphviz DOT format
          entry_flows: [...],    # Traces from entry points
          external_calls: [...], # Calls to external/hardware APIs
        }
    """
    lang = tech_stack.get("primary_language", "")
    edges = []

    for rel in tech_stack.get("source_files", []):
        f = path / rel
        if f.exists():
            edges.extend(_process_file_edges(f, rel, lang))

    # Build adjacency graph
    graph: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        if e["callee"] not in graph[e["caller"]]:
            graph[e["caller"]].append(e["callee"])

    # Identify external/hardware API calls
    hw_patterns = {h["pattern"] for h in tech_stack.get("hardware_apis", [])}
    external_calls = [
        e for e in edges if e["callee"] in hw_patterns or _is_external(e["callee"])
    ]

    entry_flows = _trace_entry_flows(
        structure.get("entry_points", []), structure, graph
    )

    return {
        "edges": edges,
        "graph": dict(graph),
        "dot": _to_dot(graph, hw_patterns),
        "entry_flows": entry_flows,
        "external_calls": external_calls,
    }


# ─── Python (AST-based, most accurate) ───────────────────────────────────────


class _CallVisitor(ast.NodeVisitor):
    def __init__(self):
        self.current_func = None
        self.edges = []

    def visit_FunctionDef(self, node):
        prev = self.current_func
        self.current_func = node.name
        self.generic_visit(node)
        self.current_func = prev

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node):
        if self.current_func:
            callee = _py_call_name(node.func)
            if callee:
                self.edges.append(
                    {"caller": self.current_func, "callee": callee, "line": node.lineno}
                )
        self.generic_visit(node)


def _py_call_name(node) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr  # simplify obj.method → method
    return None


def _extract_calls_python(f: Path, rel: str) -> list[dict]:
    try:
        source = f.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source, filename=str(f))
        visitor = _CallVisitor()
        visitor.visit(tree)
        return [dict(e, location=rel) for e in visitor.edges]
    except Exception:
        return _extract_calls_generic(f, rel)


# ─── C/C++ (regex-based) ─────────────────────────────────────────────────────

_C_FUNC_DEF_RE = re.compile(
    r"^[\w\*\s]+\s+(\w+)\s*\([^)]*\)\s*(?:const\s*)?\{", re.MULTILINE
)
_C_CALL_RE = re.compile(r"\b(\w+)\s*\(")
_C_KEYWORDS = {
    "if",
    "while",
    "for",
    "switch",
    "return",
    "sizeof",
    "typeof",
    "alignof",
    "static_assert",
    "catch",
    "throw",
}


def _process_c_function(
    source: str, rel: str, fname: str, start: int, end: int, edges: list
) -> None:
    body = source[start:end]
    for cm in _C_CALL_RE.finditer(body):
        callee = cm.group(1)
        if callee not in _C_KEYWORDS and callee != fname:
            line = source[: start + cm.start()].count("\n") + 1
            edges.append(
                {"caller": fname, "callee": callee, "line": line, "location": rel}
            )


def _extract_calls_c(f: Path, rel: str) -> list[dict]:
    try:
        source = f.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    # Find function definition spans
    func_spans = [(m.group(1), m.end()) for m in _C_FUNC_DEF_RE.finditer(source)]

    edges = []
    for i, (fname, start) in enumerate(func_spans):
        end = func_spans[i + 1][1] if i + 1 < len(func_spans) else len(source)
        _process_c_function(source, rel, fname, start, end, edges)

    return edges


# ─── JavaScript/TypeScript (regex-based) ─────────────────────────────────────

_JS_FUNC_DEF_RE = re.compile(
    r"(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(?)\s*(?:[^)]*\))?\s*(?:=>)?\s*\{",
)
_JS_CALL_RE = re.compile(r"\b(\w+)\s*\(")
_JS_KEYWORDS = {
    "if",
    "while",
    "for",
    "switch",
    "return",
    "typeof",
    "instanceof",
    "new",
    "delete",
    "void",
    "throw",
    "catch",
    "import",
    "require",
}


def _process_js_line(
    line: str, i: int, rel: str, current_func: str, edges: list
) -> None:
    if current_func:
        for cm in _JS_CALL_RE.finditer(line):
            callee = cm.group(1)
            if callee not in _JS_KEYWORDS and callee != current_func:
                edges.append(
                    {
                        "caller": current_func,
                        "callee": callee,
                        "line": i,
                        "location": rel,
                    }
                )


def _extract_calls_js(f: Path, rel: str) -> list[dict]:
    try:
        source = f.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    lines = source.splitlines()
    edges = []
    current_func = None

    for i, line in enumerate(lines, 1):
        m = _JS_FUNC_DEF_RE.search(line)
        if m:
            current_func = m.group(1) or m.group(2)
        _process_js_line(line, i, rel, current_func, edges)

    return edges


# ─── C# (regex-based) ────────────────────────────────────────────────────────

_CS_METHOD_DEF_RE = re.compile(
    r"(?:public|private|protected|internal|static|override|virtual|async)\s+[\w<>\[\]]+\s+(\w+)\s*\("
)
_CS_CALL_RE = re.compile(r"\b(\w+)\s*\(")
_CS_KEYWORDS = {
    "if",
    "while",
    "for",
    "foreach",
    "switch",
    "return",
    "new",
    "throw",
    "catch",
    "typeof",
    "nameof",
    "sizeof",
}


def _process_cs_line(
    line: str, i: int, rel: str, current_method: str, edges: list
) -> None:
    if current_method:
        for cm in _CS_CALL_RE.finditer(line):
            callee = cm.group(1)
            if callee not in _CS_KEYWORDS and callee != current_method:
                edges.append(
                    {
                        "caller": current_method,
                        "callee": callee,
                        "line": i,
                        "location": rel,
                    }
                )


def _extract_calls_csharp(f: Path, rel: str) -> list[dict]:
    try:
        source = f.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    lines = source.splitlines()
    edges = []
    current_method = None

    for i, line in enumerate(lines, 1):
        m = _CS_METHOD_DEF_RE.search(line)
        if m:
            current_method = m.group(1)
        _process_cs_line(line, i, rel, current_method, edges)

    return edges


# ─── Generic fallback ────────────────────────────────────────────────────────

_GEN_FUNC_DEF_RE = re.compile(r"\b(\w+)\s*\([^)]*\)\s*(?:->[\w\s]+)?\s*[\{:]")
_GEN_CALL_RE = re.compile(r"\b(\w+)\s*\(")
_GEN_KEYWORDS = {
    "if",
    "while",
    "for",
    "switch",
    "return",
    "new",
    "throw",
    "import",
    "from",
    "class",
    "def",
    "function",
}


def _process_generic_line(
    line: str, i: int, rel: str, current: str, edges: list
) -> None:
    if current:
        for cm in _GEN_CALL_RE.finditer(line):
            callee = cm.group(1)
            if callee not in _GEN_KEYWORDS and callee != current:
                edges.append(
                    {"caller": current, "callee": callee, "line": i, "location": rel}
                )


def _extract_calls_generic(f: Path, rel: str) -> list[dict]:
    try:
        source = f.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    lines = source.splitlines()
    current = None
    edges = []

    for i, line in enumerate(lines, 1):
        m = _GEN_FUNC_DEF_RE.search(line)
        if m:
            current = m.group(1)
        _process_generic_line(line, i, rel, current, edges)

    return edges


# ─── Graph utilities ─────────────────────────────────────────────────────────


def _trace_flow(
    fn: str, graph: dict, depth: int, max_depth: int, visited: set
) -> dict | None:
    if depth > max_depth or fn in visited:
        return None
    visited.add(fn)
    children = {}
    for callee in graph.get(fn, []):
        sub = _trace_flow(callee, graph, depth + 1, max_depth, visited.copy())
        children[callee] = sub if sub else {}
    return children


def _add_dot_edges(
    caller: str, callees: list, highlight: set, seen_nodes: set, lines: list
):
    for callee in callees:
        for name in (caller, callee):
            if name not in seen_nodes:
                color = ' style=filled fillcolor="#ffaaaa"' if name in highlight else ""
                lines.append(f'  "{name}" [{color}];')
                seen_nodes.add(name)
        lines.append(f'  "{caller}" -> "{callee}";')


def _to_dot(graph: dict, highlight: set) -> str:
    lines = [
        "digraph CallTree {",
        "  rankdir=LR;",
        '  node [shape=box fontname="monospace"];',
    ]
    seen_nodes = set()

    for caller, callees in graph.items():
        _add_dot_edges(caller, callees, highlight, seen_nodes, lines)

    lines.append("}")
    return "\n".join(lines)


def _is_external(name: str) -> bool:
    """Heuristic: names with mixed case / all-caps often indicate external APIs."""
    return (name[0].isupper() and not name.isupper()) or name.startswith(
        ("Sc", "Win", "Nfc", "Usb")
    )

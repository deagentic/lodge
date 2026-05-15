"""
Structure Mapper
Builds a hierarchical map of a codebase: directories, modules, classes,
functions/methods, and their relationships.
"""

from pathlib import Path
import ast
import re
from typing import Optional


# ─── Language-specific parsers ────────────────────────────────────────────────

def _parse_file_by_language(lang: str, f: Path, rel: str) -> Optional[dict]:
    if lang == 'Python' and f.suffix == '.py':
        return _parse_python(f, rel)
    if lang in ('C', 'C++') and f.suffix in ('.c', '.cpp', '.cc', '.cxx', '.h', '.hpp'):
        return _parse_c(f, rel)
    if lang in ('JavaScript', 'TypeScript') and f.suffix in ('.js', '.ts', '.jsx', '.tsx'):
        return _parse_js(f, rel)
    if lang == 'C#' and f.suffix == '.cs':
        return _parse_csharp(f, rel)
    return _parse_generic(f, rel)


def _collect_public_api(modules: list) -> list[dict]:
    public_api = []
    for mod in modules:
        for cls in mod.get('classes', []):
            public_api.append({'name': cls['name'], 'kind': 'class', 'location': mod['path']})
        for fn in mod.get('functions', []):
            if not fn['name'].startswith('_'):
                public_api.append({'name': fn['name'], 'kind': 'function', 'location': mod['path']})
    return public_api


def map_structure(path: Path, tech_stack: dict) -> dict:
    """
    Build a structural map of the codebase.

    Returns:
        {
          tree: nested dict of dirs/files,
          modules: [{name, path, classes, functions, imports}],
          entry_points: [str],
          public_api: [{name, kind, location}],
        }
    """
    lang = tech_stack.get('primary_language', '')
    modules = []
    entry_points = []

    for rel in tech_stack.get('source_files', []):
        f = path / rel
        if not f.exists():
            continue

        mod = _parse_file_by_language(lang, f, rel)

        if mod:
            modules.append(mod)
            if mod.get('is_entry_point'):
                entry_points.append(rel)

    tree = _build_tree(path, tech_stack.get('source_files', []))
    public_api = _collect_public_api(modules)

    return {
        'tree': tree,
        'modules': modules,
        'entry_points': entry_points,
        'public_api': public_api,
    }


# ─── Python parser (AST-based) ────────────────────────────────────────────────

def _parse_python(f: Path, rel: str) -> Optional[dict]:
    try:
        source = f.read_text(encoding='utf-8', errors='ignore')
        tree = ast.parse(source, filename=str(f))
    except SyntaxError:
        return _parse_generic(f, rel)

    imports = []
    classes = []
    functions = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = getattr(node, 'module', None) or ''
            names = [alias.name for alias in node.names]
            imports.append({'module': module, 'names': names, 'line': node.lineno})

        elif isinstance(node, ast.ClassDef):
            methods = [
                {'name': n.name, 'line': n.lineno, 'args': _py_args(n),
                 'decorators': [_py_decorator(d) for d in n.decorator_list]}
                for n in node.body if isinstance(n, ast.FunctionDef)
            ]
            classes.append({
                'name': node.name,
                'line': node.lineno,
                'bases': [_py_name(b) for b in node.bases],
                'methods': methods,
            })

        elif isinstance(node, ast.FunctionDef) and not _is_method(node, tree):
            functions.append({
                'name': node.name,
                'line': node.lineno,
                'args': _py_args(node),
                'decorators': [_py_decorator(d) for d in node.decorator_list],
            })

    is_entry = (f.name == '__main__.py' or
                'if __name__' in source or
                f.name in ('main.py', 'app.py', 'run.py', 'cli.py'))

    return {
        'path': rel, 'language': 'Python',
        'imports': imports, 'classes': classes, 'functions': functions,
        'is_entry_point': is_entry,
        'line_count': source.count('\n'),
    }


def _py_args(node: ast.FunctionDef) -> list[str]:
    return [a.arg for a in node.args.args]


def _py_name(node) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f'{_py_name(node.value)}.{node.attr}'
    return '?'


def _py_decorator(node) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f'{_py_name(node.value)}.{node.attr}'
    if isinstance(node, ast.Call):
        return _py_decorator(node.func)
    return '?'


def _is_method(node: ast.FunctionDef, tree: ast.Module) -> bool:
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef):
            if node in n.body:
                return True
    return False


# ─── C/C++ parser (regex-based) ───────────────────────────────────────────────

_C_FUNC_RE = re.compile(
    r'^(?:(?:static|extern|inline|virtual|WINAPI|STDCALL|__cdecl)\s+)*'
    r'(?:[\w\*]+\s+)+(\w+)\s*\(([^)]*)\)\s*(?:const\s*)?(?:\{|;)',
    re.MULTILINE
)
_C_INCLUDE_RE = re.compile(r'#include\s*[<"]([^>"]+)[>"]')
_C_CLASS_RE = re.compile(r'(?:class|struct)\s+(\w+)\s*(?::\s*(?:public|private|protected)\s+\w+)?\s*\{')
_C_DEFINE_RE = re.compile(r'#define\s+(\w+)')


def _parse_c(f: Path, rel: str) -> Optional[dict]:
    try:
        source = f.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return None

    includes = [{'module': m, 'line': i + 1}
                for i, line in enumerate(source.splitlines())
                for m in _C_INCLUDE_RE.findall(line)]

    classes = [{'name': m, 'line': _line_of(source, m), 'methods': []}
               for m in _C_CLASS_RE.findall(source)]

    functions = []
    for m in _C_FUNC_RE.finditer(source):
        name = m.group(1)
        if name not in {'if', 'while', 'for', 'switch', 'return'}:
            functions.append({
                'name': name,
                'line': source[:m.start()].count('\n') + 1,
                'args': [a.strip() for a in m.group(2).split(',') if a.strip()],
            })

    defines = _C_DEFINE_RE.findall(source)

    return {
        'path': rel, 'language': 'C/C++',
        'imports': includes, 'classes': classes, 'functions': functions,
        'defines': defines,
        'is_entry_point': 'main(' in source or 'WinMain(' in source,
        'line_count': source.count('\n'),
    }


# ─── JavaScript/TypeScript parser (regex-based) ───────────────────────────────

_JS_IMPORT_RE = re.compile(r"(?:import|require)\s*\(?['\"]([^'\"]+)['\"]")
_JS_FUNC_RE = re.compile(
    r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)|'
    r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(?[^)]*\)?\s*=>'
)
_JS_CLASS_RE = re.compile(r'class\s+(\w+)(?:\s+extends\s+(\w+))?')


def _parse_js(f: Path, rel: str) -> Optional[dict]:
    try:
        source = f.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return None

    imports = [{'module': m} for m in _JS_IMPORT_RE.findall(source)]
    classes = [{'name': m[0], 'bases': [m[1]] if m[1] else [], 'methods': []}
               for m in _JS_CLASS_RE.findall(source)]
    functions = []
    for m in _JS_FUNC_RE.finditer(source):
        name = m.group(1) or m.group(3)
        if name:
            functions.append({
                'name': name,
                'line': source[:m.start()].count('\n') + 1,
                'args': [a.strip() for a in (m.group(2) or '').split(',') if a.strip()],
            })

    return {
        'path': rel, 'language': 'JavaScript/TypeScript',
        'imports': imports, 'classes': classes, 'functions': functions,
        'is_entry_point': f.name in ('index.js', 'index.ts', 'main.js', 'main.ts', 'app.js', 'app.ts'),
        'line_count': source.count('\n'),
    }


# ─── C# parser (regex-based) ─────────────────────────────────────────────────

_CS_CLASS_RE = re.compile(r'(?:public|private|internal|protected|static|sealed|abstract)\s+(?:partial\s+)?class\s+(\w+)')
_CS_METHOD_RE = re.compile(r'(?:public|private|protected|internal|static|override|virtual|async)\s+[\w<>\[\]]+\s+(\w+)\s*\(([^)]*)\)')
_CS_USING_RE = re.compile(r'using\s+([\w\.]+)\s*;')


def _parse_csharp(f: Path, rel: str) -> Optional[dict]:
    try:
        source = f.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return None

    usings = [{'module': m} for m in _CS_USING_RE.findall(source)]
    classes = [{'name': m, 'methods': []} for m in _CS_CLASS_RE.findall(source)]
    functions = [
        {'name': m[0], 'line': _line_of(source, m[0]),
         'args': [a.strip() for a in m[1].split(',') if a.strip()]}
        for m in _CS_METHOD_RE.findall(source)
    ]

    return {
        'path': rel, 'language': 'C#',
        'imports': usings, 'classes': classes, 'functions': functions,
        'is_entry_point': 'static void Main' in source or 'static async Task Main' in source,
        'line_count': source.count('\n'),
    }


# ─── Generic fallback ─────────────────────────────────────────────────────────

_GENERIC_FUNC_RE = re.compile(r'\b(\w+)\s*\([^)]*\)\s*(?:\{|:)')


def _parse_generic(f: Path, rel: str) -> Optional[dict]:
    try:
        source = f.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return None

    names = set()
    functions = []
    for m in _GENERIC_FUNC_RE.finditer(source):
        if m.group(1) not in names:
            names.add(m.group(1))
            functions.append({'name': m.group(1), 'line': source[:m.start()].count('\n') + 1, 'args': []})

    return {
        'path': rel, 'language': f.suffix or 'unknown',
        'imports': [], 'classes': [], 'functions': functions,
        'is_entry_point': False, 'line_count': source.count('\n'),
    }


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _line_of(source: str, token: str) -> int:
    idx = source.find(token)
    return source[:idx].count('\n') + 1 if idx >= 0 else 0


def _build_tree(root: Path, source_files: list[str]) -> dict:
    tree = {}
    for rel in source_files:
        parts = Path(rel).parts
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = None
    return tree

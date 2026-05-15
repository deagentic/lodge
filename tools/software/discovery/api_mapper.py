"""
API Mapper
Maps every external API call in the codebase: system APIs, hardware APIs,
library calls, network calls. Captures call sites, arguments, and usage patterns.
"""

from pathlib import Path
import ast
import re
from collections import defaultdict


# Known API groups to track — extend as needed
API_GROUPS = {
    'winscard': {
        'SCardEstablishContext', 'SCardReleaseContext',
        'SCardConnect', 'SCardDisconnect', 'SCardReconnect',
        'SCardBeginTransaction', 'SCardEndTransaction',
        'SCardTransmit', 'SCardControl',
        'SCardGetStatusChange', 'SCardListReaders',
        'SCardGetAttrib', 'SCardSetAttrib',
        'SCardStatus', 'SCardFreeMemory',
    },
    'libnfc': {
        'nfc_open', 'nfc_close', 'nfc_init', 'nfc_exit',
        'nfc_initiator_init', 'nfc_initiator_select_passive_target',
        'nfc_initiator_deselect_target', 'nfc_initiator_transceive_bytes',
        'nfc_device_set_property_bool', 'nfc_device_get_name',
        'nfc_list_devices',
    },
    'libusb': {
        'libusb_init', 'libusb_exit', 'libusb_open', 'libusb_close',
        'libusb_get_device_list', 'libusb_get_device_descriptor',
        'libusb_open_device_with_vid_pid', 'libusb_claim_interface',
        'libusb_bulk_transfer', 'libusb_control_transfer',
        'libusb_interrupt_transfer', 'libusb_release_interface',
    },
    'winapi': {
        'CreateFile', 'CloseHandle', 'ReadFile', 'WriteFile',
        'DeviceIoControl', 'SetupDiGetClassDevs',
        'SetupDiEnumDeviceInterfaces', 'SetupDiGetDeviceInterfaceDetail',
        'RegisterDeviceNotification', 'CM_Register_Notification',
    },
    'hidapi': {
        'hid_open', 'hid_close', 'hid_read', 'hid_write',
        'hid_send_feature_report', 'hid_get_feature_report',
        'hid_enumerate', 'hid_free_enumeration', 'hid_init', 'hid_exit',
    },
}

# Build reverse lookup: function → group
FUNC_TO_GROUP: dict[str, str] = {}
for _group, _funcs in API_GROUPS.items():
    for _fn in _funcs:
        FUNC_TO_GROUP[_fn] = _group


def map_api_calls(path: Path, tech_stack: dict) -> dict:
    """
    Map all external API calls found in the codebase.

    Returns:
        {
          by_group: {group: [{function, file, line, args_raw}]},
          by_file: {file: [{function, group, line}]},
          unknown_external: [...],
          summary: {group: count},
        }
    """
    lang = tech_stack.get('primary_language', '')
    all_calls = []

    for rel in tech_stack.get('source_files', []):
        f = path / rel
        if not f.exists():
            continue

        if lang == 'Python' and f.suffix == '.py':
            calls = _scan_python(f, rel)
        else:
            calls = _scan_regex(f, rel)

        all_calls.extend(calls)

    by_group: dict[str, list] = defaultdict(list)
    by_file: dict[str, list] = defaultdict(list)

    for c in all_calls:
        group = FUNC_TO_GROUP.get(c['function'], 'unknown')
        c['group'] = group
        by_group[group].append(c)
        by_file[c['file']].append(c)

    unknown_external = [c for c in by_group.get('unknown', []) if _looks_external(c['function'])]

    summary = {g: len(calls) for g, calls in by_group.items() if g != 'unknown'}

    return {
        'by_group': dict(by_group),
        'by_file': dict(by_file),
        'unknown_external': unknown_external,
        'summary': summary,
    }


# ─── Python scanner (AST) ────────────────────────────────────────────────────

class _ApiCallVisitor(ast.NodeVisitor):
    def __init__(self, rel: str):
        self.rel = rel
        self.calls = []

    def visit_Call(self, node):
        name = _extract_name(node.func)
        if name and name in FUNC_TO_GROUP:
            args_raw = [_ast_repr(a) for a in node.args]
            self.calls.append({
                'function': name,
                'file': self.rel,
                'line': node.lineno,
                'args_raw': args_raw,
            })
        self.generic_visit(node)


def _extract_name(node) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _ast_repr(node) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return '?'


def _scan_python(f: Path, rel: str) -> list[dict]:
    try:
        source = f.read_text(encoding='utf-8', errors='ignore')
        tree = ast.parse(source)
        v = _ApiCallVisitor(rel)
        v.visit(tree)
        return v.calls
    except Exception:
        return _scan_regex(f, rel)


# ─── Regex scanner (universal fallback) ──────────────────────────────────────

_CALL_RE = re.compile(r'\b(\w+)\s*\(([^)]*)\)')


def _scan_regex(f: Path, rel: str) -> list[dict]:
    try:
        source = f.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return []

    calls = []
    for i, line in enumerate(source.splitlines(), 1):
        for m in _CALL_RE.finditer(line):
            name = m.group(1)
            if name in FUNC_TO_GROUP:
                calls.append({
                    'function': name,
                    'file': rel,
                    'line': i,
                    'args_raw': [a.strip() for a in m.group(2).split(',') if a.strip()],
                })
    return calls


def _looks_external(name: str) -> bool:
    """Heuristic for external/system API calls."""
    return (
        (len(name) > 3 and name[0].isupper() and name[1].islower()) or
        name.startswith(('nfc_', 'hid_', 'usb_', 'scard', 'win32', 'ctypes'))
    )

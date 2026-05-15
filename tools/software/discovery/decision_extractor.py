"""
Decision Extractor
Scans source code for implicit and explicit software decisions:
  - Hardcoded constants (magic numbers, device IDs, timeouts)
  - Conditional branches that encode business/hardware logic
  - TODO/FIXME/HACK/NOTE comments that reveal intent
  - Protocol-specific byte sequences
  - Error handling patterns (what errors are swallowed/retried)
  - Threading/synchronization choices
"""

from pathlib import Path
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class Decision:
    kind: str          # constant | comment | branch | protocol | error | threading
    description: str
    file: str
    line: int
    snippet: str
    rationale: Optional[str] = None  # extracted from nearby comment


DECISIONS: list[Decision] = []


# ─── Pattern sets ─────────────────────────────────────────────────────────────

INTENT_COMMENT_RE = re.compile(
    r'(?://|#|/\*|\*)\s*(TODO|FIXME|HACK|NOTE|WORKAROUND|BUG|OPTIMIZE|REVIEW|XXX|IMPORTANT|WARNING)\s*:?\s*(.+)',
    re.IGNORECASE
)

MAGIC_NUMBER_RE = re.compile(
    r'\b(0x[0-9A-Fa-f]{2,8}|[0-9]{3,})\b'
)

TIMEOUT_RE = re.compile(
    r'(?:timeout|delay|sleep|wait|interval|period|ms|msec|millisec)\s*[=:]\s*(\d+)',
    re.IGNORECASE
)

RETRY_RE = re.compile(
    r'(?:retry|retries|attempts|max_attempts|max_retry)\s*[=:]\s*(\d+)',
    re.IGNORECASE
)

BYTE_SEQUENCE_RE = re.compile(
    r'(?:0x[0-9A-Fa-f]{2}\s*[,\s]+){2,}'
)

THREAD_RE = re.compile(
    r'\b(Thread|threading|mutex|semaphore|lock|async|await|concurrent|queue|event|signal)\b',
    re.IGNORECASE
)

ERROR_SWALLOW_RE = re.compile(
    r'(?:except\s*:|catch\s*\(|try\s*\{)[^}]*(?:pass|continue|return|//\s*ignore)',
    re.IGNORECASE | re.DOTALL
)

# WinSCard specific
SCARD_CONSTANT_RE = re.compile(r'\bSCARD_[A-Z_]+\b')
APDU_COMMAND_RE = re.compile(r'(?:0x[0-9A-Fa-f]{2},?\s*){4,}')  # 4+ bytes = likely APDU

# PC/SC Share mode / disposition decisions
SHARE_MODE_RE = re.compile(r'SCARD_SHARE_(SHARED|EXCLUSIVE|DIRECT)')
DISPOSITION_RE = re.compile(r'SCARD_(LEAVE_CARD|RESET_CARD|UNPOWER_CARD|EJECT_CARD)')


def extract_decisions(path: Path, tech_stack: dict) -> dict:
    """
    Scan codebase for implicit and explicit software decisions.

    Returns:
        {
          decisions: [Decision as dict],
          by_kind: {kind: [decisions]},
          critical: [high-impact decisions],
          summary: str,
        }
    """
    all_decisions: list[Decision] = []

    for rel in tech_stack.get('source_files', []):
        f = path / rel
        if not f.exists():
            continue
        try:
            source = f.read_text(encoding='utf-8', errors='ignore')
            lines = source.splitlines()
        except Exception:  # nosec B112  # best-effort: file read optional
            continue

        all_decisions.extend(_scan_intent_comments(lines, rel))
        all_decisions.extend(_scan_constants(lines, rel, tech_stack))
        all_decisions.extend(_scan_timeouts(lines, rel))
        all_decisions.extend(_scan_byte_sequences(lines, rel))
        all_decisions.extend(_scan_threading(lines, rel))
        all_decisions.extend(_scan_winscard_choices(lines, rel))

    by_kind: dict[str, list] = {}
    for d in all_decisions:
        by_kind.setdefault(d.kind, []).append(_to_dict(d))

    critical = [
        _to_dict(d) for d in all_decisions
        if d.kind in ('protocol', 'constant') or
        (d.kind == 'comment' and d.description.startswith(('HACK', 'WORKAROUND', 'BUG', 'FIXME')))
    ]

    return {
        'decisions': [_to_dict(d) for d in all_decisions],
        'by_kind': by_kind,
        'critical': critical,
        'summary': _summarize(all_decisions),
    }


# ─── Scanners ─────────────────────────────────────────────────────────────────

def _scan_intent_comments(lines: list[str], rel: str) -> list[Decision]:
    decisions = []
    for i, line in enumerate(lines, 1):
        m = INTENT_COMMENT_RE.search(line)
        if m:
            decisions.append(Decision(
                kind='comment',
                description=f"{m.group(1)}: {m.group(2).strip()}",
                file=rel, line=i, snippet=line.strip()
            ))
    return decisions


def _process_constant_line(line: str, stripped: str, rel: str, i: int, decisions: list[Decision]) -> None:
    if BYTE_SEQUENCE_RE.search(line):
        decisions.append(Decision(
            kind='protocol',
            description='Hardcoded byte sequence (possible APDU or device command)',
            file=rel, line=i, snippet=stripped[:120]
        ))
        return

    if APDU_COMMAND_RE.search(line) and ('0xFF' in line or '0x00' in line or 'FF' in line.upper()):
        decisions.append(Decision(
            kind='protocol',
            description='Possible APDU command bytes',
            file=rel, line=i, snippet=stripped[:120]
        ))

    for m in MAGIC_NUMBER_RE.finditer(line):
        val = m.group(1)
        if val in ('0', '1', '2', '0x00', '0xFF', '0x01'):
            continue
        if val.startswith('0x') and len(val) >= 6:
            decisions.append(Decision(
                kind='constant',
                description=f'Hardcoded hex constant: {val}',
                file=rel, line=i, snippet=stripped[:120]
            ))


def _scan_constants(lines: list[str], rel: str, tech_stack: dict) -> list[Decision]:
    """Find magic numbers and hardcoded device/protocol constants."""
    decisions = []

    for i, line in enumerate(lines, 1):
        # Skip comment lines and string assignments
        stripped = line.strip()
        if stripped.startswith(('//', '#', '*', '/*')):
            continue

        _process_constant_line(line, stripped, rel, i, decisions)

    return decisions


def _scan_timeouts(lines: list[str], rel: str) -> list[Decision]:
    decisions = []
    for i, line in enumerate(lines, 1):
        m = TIMEOUT_RE.search(line)
        if m:
            decisions.append(Decision(
                kind='constant',
                description=f'Timing decision: {line.strip()[:80]}',
                file=rel, line=i, snippet=line.strip()[:120]
            ))
        m2 = RETRY_RE.search(line)
        if m2:
            decisions.append(Decision(
                kind='constant',
                description=f'Retry/attempt limit: {line.strip()[:80]}',
                file=rel, line=i, snippet=line.strip()[:120]
            ))
    return decisions


def _process_byte_array_line(line: str, i: int, array_bytes: list, array_start: int, rel: str, decisions: list) -> bool:
    bytes_found = re.findall(r'0x[0-9A-Fa-f]{2}', line)
    array_bytes.extend(bytes_found)
    if ';' in line or '}' in line:
        if len(array_bytes) >= 4:
            decisions.append(Decision(
                kind='protocol',
                description=f'Byte array ({len(array_bytes)} bytes): {" ".join(array_bytes[:16])}{"..." if len(array_bytes) > 16 else ""}',
                file=rel, line=array_start, snippet=f'Array starting line {array_start}'
            ))
        return False
    return True


def _scan_byte_sequences(lines: list[str], rel: str) -> list[Decision]:
    # Already handled in _scan_constants for most cases
    # Here we catch multi-line byte arrays
    decisions = []
    in_array = False
    array_start = 0
    array_bytes: list[str] = []

    for i, line in enumerate(lines, 1):
        if re.search(r'(?:byte|uint8|BYTE|char)\s*\w*\s*\[', line):
            in_array = True
            array_start = i
            array_bytes = []
        if in_array:
            in_array = _process_byte_array_line(line, i, array_bytes, array_start, rel, decisions)

    return decisions


def _scan_threading(lines: list[str], rel: str) -> list[Decision]:
    decisions = []
    seen = set()
    for i, line in enumerate(lines, 1):
        m = THREAD_RE.search(line)
        if m:
            token = m.group(1).lower()
            if token not in seen:
                seen.add(token)
                decisions.append(Decision(
                    kind='threading',
                    description=f'Concurrency/threading: {token}',
                    file=rel, line=i, snippet=line.strip()[:120]
                ))
    return decisions


def _process_winscard_line(line: str, rel: str, i: int, decisions: list[Decision]) -> None:
    m = SHARE_MODE_RE.search(line)
    if m:
        decisions.append(Decision(
            kind='protocol',
            description=f'PC/SC share mode choice: {m.group(0)} — affects multi-app access',
            file=rel, line=i, snippet=line.strip()[:120]
        ))
    m2 = DISPOSITION_RE.search(line)
    if m2:
        decisions.append(Decision(
            kind='protocol',
            description=f'PC/SC card disposition on disconnect: {m2.group(0)} — affects card state',
            file=rel, line=i, snippet=line.strip()[:120]
        ))
    for m3 in SCARD_CONSTANT_RE.finditer(line):
        val = m3.group(0)
        if val not in {'SCARD_S_SUCCESS', 'SCARD_E_NO_SERVICE'}:
            decisions.append(Decision(
                kind='protocol',
                description=f'PC/SC constant usage: {val}',
                file=rel, line=i, snippet=line.strip()[:120]
            ))
            break  # one per line


def _scan_winscard_choices(lines: list[str], rel: str) -> list[Decision]:
    """Flag PC/SC-specific choices that affect behavior significantly."""
    decisions = []
    for i, line in enumerate(lines, 1):
        _process_winscard_line(line, rel, i, decisions)

    return decisions


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _to_dict(d: Decision) -> dict:
    return {
        'kind': d.kind,
        'description': d.description,
        'file': d.file,
        'line': d.line,
        'snippet': d.snippet,
        'rationale': d.rationale,
    }


def _summarize(decisions: list[Decision]) -> str:
    from collections import Counter
    counts = Counter(d.kind for d in decisions)
    parts = [f"{v} {k}" for k, v in counts.most_common()]
    return f"Found {len(decisions)} decisions: {', '.join(parts)}"

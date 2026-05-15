"""
Language & Technology Stack Detector
Scans a codebase and identifies: primary language, all languages present,
build systems, hardware APIs, platform targets, and frameworks.
"""

from pathlib import Path
from collections import Counter

EXTENSION_MAP = {
    '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript',
    '.tsx': 'TypeScript/React', '.jsx': 'JavaScript/React',
    '.c': 'C', '.h': 'C/C++ Header', '.cpp': 'C++', '.cc': 'C++',
    '.cxx': 'C++', '.hpp': 'C++ Header', '.cs': 'C#', '.java': 'Java',
    '.go': 'Go', '.rs': 'Rust', '.rb': 'Ruby', '.php': 'PHP',
    '.swift': 'Swift', '.kt': 'Kotlin', '.scala': 'Scala',
    '.lua': 'Lua', '.sh': 'Shell', '.ps1': 'PowerShell',
    '.bat': 'Batch', '.vbs': 'VBScript',
    '.asm': 'Assembly', '.s': 'Assembly',
}

BUILD_SYSTEM_FILES = {
    'package.json': 'npm/Node.js', 'pom.xml': 'Maven/Java',
    'build.gradle': 'Gradle/Java', 'Cargo.toml': 'Cargo/Rust',
    'CMakeLists.txt': 'CMake/C++', 'Makefile': 'Make',
    'setup.py': 'setuptools/Python', 'pyproject.toml': 'Python/pyproject',
    'requirements.txt': 'pip/Python', 'go.mod': 'Go modules',
    'Gemfile': 'Bundler/Ruby', 'composer.json': 'Composer/PHP',
}

BUILD_SYSTEM_EXTS = {
    '.csproj': 'MSBuild/C#', '.sln': 'Visual Studio',
    '.vcxproj': 'Visual Studio/C++',
}

# Pattern -> (description, category)
HARDWARE_API_PATTERNS = {
    # Windows Smart Card / PC/SC
    'SCardEstablishContext': ('PC/SC: Establish context', 'winscard'),
    'SCardConnect':          ('PC/SC: Connect to card', 'winscard'),
    'SCardTransmit':         ('PC/SC: Send APDU', 'winscard'),
    'SCardDisconnect':       ('PC/SC: Disconnect', 'winscard'),
    'SCardBeginTransaction': ('PC/SC: Begin transaction', 'winscard'),
    'SCardEndTransaction':   ('PC/SC: End transaction', 'winscard'),
    'SCardGetStatusChange':  ('PC/SC: Poll reader state change', 'winscard'),
    'SCardListReaders':      ('PC/SC: List available readers', 'winscard'),
    'SCardControl':          ('PC/SC: Send control/escape command', 'winscard'),
    'winscard':              ('WinSCard library import/link', 'winscard'),
    'pcsclite':              ('PC/SC Lite (Linux/macOS)', 'pcsc-linux'),
    # NFC / ISO protocols
    'ISO15693':              ('ISO 15693 Vicinity Card protocol', 'nfc'),
    'ISO14443':              ('ISO 14443 Proximity Card protocol', 'nfc'),
    'APDU':                  ('Application Protocol Data Unit', 'nfc'),
    'ACR122':                ('ACR122U NFC reader', 'nfc'),
    'libnfc':                ('libnfc library', 'nfc'),
    'nfc_open':              ('libnfc: open device', 'nfc'),
    'nfc_initiator':         ('libnfc: initiator mode', 'nfc'),
    'FF000000':              ('ACR122U escape command prefix', 'nfc'),
    # USB / HID
    'libusb':                ('LibUSB direct USB access', 'usb'),
    'hidapi':                ('HIDAPI (HID device access)', 'usb'),
    'WinUSB':                ('WinUSB driver', 'usb'),
    'DeviceIoControl':       ('Windows: DeviceIoControl', 'winapi'),
    'CreateFile':            ('Windows: CreateFile (device handle)', 'winapi'),
    'SetupDiGetClassDevs':   ('Windows: Device enumeration', 'winapi'),
    'RegisterDeviceNotification': ('Windows: Device hotplug events', 'winapi'),
    'CM_Register_Notification':   ('Windows: PnP notifications', 'winapi'),
}

IGNORE_DIRS = {
    '.git', 'node_modules', '__pycache__', '.venv', 'venv',
    'dist', 'build', 'target', '.idea', '.vs', '.vscode',
    'bin', 'obj', '.cache',
}


def _check_hardware_apis(content: str, rel: str, hardware_hits: dict):
    for pattern, (description, category) in HARDWARE_API_PATTERNS.items():
        if pattern in content:
            if pattern not in hardware_hits:
                hardware_hits[pattern] = {
                    'pattern': pattern,
                    'description': description,
                    'category': category,
                    'files': [],
                }
            hardware_hits[pattern]['files'].append(rel)


def _process_file_for_language(f: Path, rel: str, build_systems: list, ext_counter: Counter, source_files: list, hardware_hits: dict) -> int:
    lines = 0
    if f.name in BUILD_SYSTEM_FILES:
        bs = BUILD_SYSTEM_FILES[f.name]
        if bs not in build_systems:
            build_systems.append(bs)
    if f.suffix in BUILD_SYSTEM_EXTS:
        bs = BUILD_SYSTEM_EXTS[f.suffix]
        if bs not in build_systems:
            build_systems.append(bs)

    if f.suffix.lower() in EXTENSION_MAP:
        ext_counter[EXTENSION_MAP[f.suffix.lower()]] += 1
        source_files.append(rel)

    try:
        content = f.read_text(encoding='utf-8', errors='ignore')
        lines = content.count('\n')
        _check_hardware_apis(content, rel, hardware_hits)
    except Exception:  # nosec B110  # best-effort: file read optional
        pass
    return lines


def detect_language(path: Path) -> dict:
    """
    Analyze a codebase and return a technology stack descriptor.

    Returns:
        {
          primary_language: str,
          languages: {lang: file_count},
          build_systems: [str],
          hardware_apis: [{pattern, description, category, files: [str]}],
          platform: str,
          file_count: int,
          total_lines: int,
          source_files: [str],   # relative paths of code files
        }
    """
    ext_counter = Counter()
    source_files = []
    build_systems = []
    hardware_hits: dict[str, dict] = {}
    total_lines = 0

    for f in _walk(path):
        rel = str(f.relative_to(path))
        total_lines += _process_file_for_language(f, rel, build_systems, ext_counter, source_files, hardware_hits)

    languages = dict(ext_counter.most_common())
    primary = ext_counter.most_common(1)[0][0] if ext_counter else None

    # Infer platform
    categories = {h['category'] for h in hardware_hits.values()}
    if 'winscard' in categories or 'winapi' in categories:
        platform = 'Windows'
    elif 'pcsc-linux' in categories:
        platform = 'Linux/Unix'
    elif 'nfc' in categories:
        platform = 'Cross-platform NFC'
    else:
        platform = 'Unknown'

    return {
        'primary_language': primary,
        'languages': languages,
        'build_systems': build_systems,
        'hardware_apis': list(hardware_hits.values()),
        'platform': platform,
        'file_count': len(source_files),
        'total_lines': total_lines,
        'source_files': source_files,
    }


def _walk(path: Path):
    for f in path.rglob('*'):
        if f.is_file() and not any(p in IGNORE_DIRS for p in f.parts):
            yield f

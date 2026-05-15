import os
import sys
import subprocess  # nosec B404
from pathlib import Path


def main():
    base_sha = os.environ.get("BASE_SHA")
    head_sha = os.environ.get("HEAD_SHA")

    if not base_sha or not head_sha:
        print("BASE_SHA and HEAD_SHA environment variables required.")
        return 0

    print(f"Checking SemVer bump: {base_sha} -> {head_sha}")

    # Check commit messages for bypass
    try:
        log_out = subprocess.check_output(  # nosec B603, B607
            ["git", "log", f"{base_sha}..{head_sha}", "--pretty=%B"], text=True
        )
    except subprocess.CalledProcessError:
        print("Error reading git log.")
        return 1

    if "[skip-semver]" in log_out:
        print("Found [skip-semver] in commit messages. SemVer check passed.")
        return 0

    # Get version from base
    try:
        base_toml = subprocess.check_output(  # nosec B603, B607
            ["git", "show", f"{base_sha}:pyproject.toml"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        print("pyproject.toml not found in base branch, skipping SemVer check.")
        return 0

    import re

    VERSION_RE = re.compile(r'^version\s*=\s*"(\d+\.\d+\.\d+)"', re.MULTILINE)
    m_base = VERSION_RE.search(base_toml)
    base_version = m_base.group(1) if m_base else None

    # Get version from head
    head_toml = Path("pyproject.toml").read_text(encoding="utf-8")
    m_head = VERSION_RE.search(head_toml)
    head_version = m_head.group(1) if m_head else None

    if not base_version or not head_version:
        print("Could not parse versions. Assuming OK for now.")
        return 0

    if base_version == head_version:
        print(
            f"Error: Version in pyproject.toml ({head_version}) was not bumped compared to base."
        )
        print(
            "If this commit doesn't require a bump, add [skip-semver] to your commit message."
        )
        return 1

    print(f"SemVer bump detected: {base_version} -> {head_version}. Check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

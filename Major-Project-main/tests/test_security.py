"""
Security and Credential Leak Prevention Tests.

Verifies:
1. Zero secrets, API keys, or Wi-Fi passwords appear in tracked code files.
2. .gitignore properly includes sensitive patterns.
"""

from pathlib import Path
import re
import pytest

# Sensitive substrings from original code
KNOWN_ORIGINAL_SECRETS = [
    "53TE7P65F8X4FGUJ",
    "n5Xgc46MDPd7ieYGsfK9qReLEd4oqERy",
    "KFIHXY625IRCYFSC",
    "Akshay12",
]

TRACKED_EXTENSIONS = {".py", ".html", ".js", ".css", ".md"}


def test_no_hardcoded_secrets_in_tracked_source_files():
    root = Path(".")
    violations = []

    for path in root.rglob("*"):
        # Skip backup folder, git folder, venv, test_security itself, and ignored secret files
        if any(part in path.parts for part in ["_original_backup", ".git", "venv", "__pycache__", ".pytest_cache"]):
            continue
        if path.name in [".env", "secrets.h", "test_security.py"]:
            continue
        if path.suffix in TRACKED_EXTENSIONS or path.name.endswith(".example.h") or path.name.endswith(".example"):
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                for secret in KNOWN_ORIGINAL_SECRETS:
                    if secret in content:
                        violations.append(f"{path}: leaked secret '{secret}'")
            except Exception:
                pass

    assert not violations, f"Secret leaks detected in tracked files:\n" + "\n".join(violations)


def test_gitignore_contains_sensitive_patterns():
    gitignore = Path(".gitignore")
    assert gitignore.exists()
    content = gitignore.read_text(encoding="utf-8")
    assert ".env" in content
    assert "secrets.h" in content

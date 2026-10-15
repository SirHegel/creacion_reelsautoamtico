#!/usr/bin/env python3
"""Verify the tracked public inventory without reading ignored private data."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "PUBLIC_SOURCE_MANIFEST.json"
PRIVATE_PARTS = {
    ".estado", ".agents", ".git", "node_modules", "__pycache__", ".venv",
    "venv", "workspaces", "projects", "proyectos", "exports", "recursos",
    "credentials", "secrets", "accounts", "auth", "backups", "backup",
}
PRIVATE_SUFFIXES = {
    ".key", ".pem", ".p12", ".pfx", ".keystore", ".db", ".sqlite", ".sqlite3",
    ".log", ".bak", ".backup", ".old", ".orig", ".pyc", ".mp4", ".mov",
    ".mkv", ".webm", ".wav", ".mp3", ".zip", ".gz", ".tar",
}
TEXT_SUFFIXES = {
    ".py", ".js", ".mjs", ".jsx", ".ts", ".md", ".json", ".html", ".svg",
    ".css", ".txt", ".sh", ".toml", ".yaml", ".yml", ".csv",
}
PATTERNS = (
    ("github_token", r"\b(?:gh[pousr]_[A-Za-z0-9]{36,255}|github_pat_[A-Za-z0-9_]{50,255})\b"),
    ("provider_token", r"\bsk-(?:proj-|ant-api\d+-)?[A-Za-z0-9_-]{40,255}\b"),
    ("google_api_key", r"\bAIza[A-Za-z0-9_-]{35}\b"),
    ("aws_access_identifier", r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    ("slack_token", r"\bxox[baprs]-[A-Za-z0-9-]{25,255}\b"),
    ("private_key", r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----\s+[A-Za-z0-9+/=]{32,}"),
    ("private_drive_link", r"https?://(?:drive|docs)\.google\.com/(?:file|drive|document|spreadsheets|presentation|open)[/?]"),
    ("personal_home_path", r"/(?:home|Users)/(?!user(?:/|\b)|example(?:/|\b)|test(?:/|\b)|runner(?:/|\b)|username(?:/|\b))[^\s/\"'<>]+/"),
)


def tracked_names():
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"],
        check=True, capture_output=True,
    )
    return [name.decode("utf-8") for name in result.stdout.split(b"\0") if name]


def inspect():
    names = tracked_names()
    report = {"passed": False, "file_count": len(names), "total_bytes": 0, "findings": []}
    findings = report["findings"]
    inventory = {}
    font_notices = "IVAN/SOFTWARE/assets/fonts/licenses/"
    for name in names:
        pure = PurePosixPath(name)
        if pure.is_absolute() or str(pure) != name or any(p in {"", ".", ".."} for p in name.split("/")):
            findings.append({"path": "<invalid>", "category": "noncanonical_path"})
            continue
        lowered = [p.casefold() for p in pure.parts]
        if (any(p in PRIVATE_PARTS for p in lowered) or
                pure.name.casefold() == "estado.json" or
                pure.name.casefold().startswith((".env", "id_rsa", "id_ed25519")) or
                pure.suffix.casefold() in PRIVATE_SUFFIXES):
            findings.append({"path": name, "category": "private_path"})
            continue
        path = ROOT / name
        if path.resolve() != path:
            findings.append({"path": name, "category": "symlink_or_alias"})
            continue
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 16 * 1024 * 1024:
            findings.append({"path": name, "category": "unsafe_file"})
            continue
        data = path.read_bytes()
        report["total_bytes"] += len(data)
        if name != MANIFEST:
            inventory[name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        if pure.suffix.casefold() not in TEXT_SUFFIXES and pure.name != ".gitignore":
            continue
        if name.startswith(font_notices):
            continue  # The software checker verifies these required public notices by pinned SHA.
        source = data.decode("utf-8")
        for category, pattern in PATTERNS:
            for match in re.finditer(pattern, source):
                # An explicit low-entropy fake key is used by the provider unit test.
                if category == "provider_token" and len(set(match.group())) < 12:
                    continue
                findings.append({"path": name, "line": source.count("\n", 0, match.start()) + 1, "category": category})
    if report["total_bytes"] > 64 * 1024 * 1024:
        findings.append({"path": "<tree>", "category": "size_limit"})
    manifest = json.loads((ROOT / MANIFEST).read_text())
    if manifest.get("schema") != "reels.public-source/1" or manifest.get("files") != inventory:
        findings.append({"path": MANIFEST, "category": "inventory_mismatch"})
    software = ROOT / "IVAN/SOFTWARE"
    spec = importlib.util.spec_from_file_location("public_source_safety", software / "scripts/security_check.py")
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    prefix = "IVAN/SOFTWARE/"
    result = checker.inspect_files(software, [name[len(prefix):] for name in names if name.startswith(prefix)])
    for finding in result["findings"]:
        findings.append({**finding, "path": prefix + finding["path"]})
    report["passed"] = not findings
    report["sensitive_values_printed"] = False
    return report


def main():
    try:
        report = inspect()
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        print("Invalid publication input; no file contents printed.", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

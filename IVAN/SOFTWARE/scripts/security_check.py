#!/usr/bin/env python3
"""Check an explicit publication tree without displaying sensitive values.

This is a bounded preflight, not an exhaustive secret or vulnerability audit.
Run from a checkout with --git-tree, or supply --manifest with a JSON list of
relative file names. No files, credentials or installed application are loaded
outside that list. Private known values can be supplied by an in-process caller.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MAX_FILE = 16 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
PRIVATE_PARTS = {'.estado', 'workspaces', 'projects', 'proyectos', 'exports',
                 'privateassets', 'private_assets', 'raw', 'crudos', 'recursos',
                 'models', 'runtime', 'runtimes', 'node_modules', '__pycache__',
                 '.venv', 'venv', 'env', '.cache', '.pytest_cache', '.git',
                 'secrets', 'credentials', 'accounts', 'auth', '.ssh', '.aws', '.kube',
                 'backups', 'backup', 'logs', 'build', 'dist', '.npm', '.pnpm-store'}
PRIVATE_SUFFIXES = {'.key', '.pem', '.p12', '.pfx', '.jks', '.keystore', '.db',
                    '.sqlite', '.sqlite3', '.log', '.bak', '.pyc', '.mp4', '.mov',
                    '.mkv', '.webm', '.wav', '.mp3', '.zip', '.backup', '.old', '.orig'}
TEXT_SUFFIXES = {'.py', '.js', '.mjs', '.md', '.json', '.html', '.css', '.txt',
                 '.sh', '.toml', '.yml', '.yaml'}
EMAIL = re.compile(r'(?<![\w@])[\w.+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})(?![\w@])')
SYNTHETIC_DOMAINS = {'example.com', 'example.org', 'example.net', 'ejemplo.com'}
SECRETS = (
    ('github_token', re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{36,255}|github_pat_[A-Za-z0-9_]{50,255})\b')),
    ('aws_access_identifier', re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b')),
    ('google_api_key', re.compile(r'\bAIza[A-Za-z0-9_-]{35}\b')),
    ('slack_token', re.compile(r'\bxox[baprs]-[A-Za-z0-9-]{25,255}\b')),
    ('provider_token', re.compile(r'\bsk-(?:proj-|ant-api\d+-)?[A-Za-z0-9_-]{40,255}\b')),
    ('private_key_block', re.compile(r'-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----[\r\n]+[A-Za-z0-9+/=\r\n]{32,}', re.M)),
)


def _json(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError('Repeated manifest key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs)


def _bounded_regular(path, root, maximum):
    if path.resolve() != path or not path.is_relative_to(root):
        raise ValueError('Security input aliases a foreign path')
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not 1 <= before.st_size <= maximum:
        raise ValueError('Security input must be one bounded regular file')
    signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as source:
        if signature(os.fstat(source.fileno())) != signature(before):
            raise ValueError('Security input changed before read')
        data = source.read(maximum + 1)
    if len(data) != before.st_size or signature(path.lstat()) != signature(before):
        raise ValueError('Security input changed during read')
    return data


def _public_assets(root):
    """Exact hashes retain OFL notices, including required public attribution."""
    pack = _json(_bounded_regular(root / 'packs/public_fonts.json', root, 1024 * 1024))
    if (not isinstance(pack, dict) or pack.get('schema') != 'ascendia.public-fonts/1' or
            not isinstance(pack.get('fonts'), list) or len(pack['fonts']) != 6):
        raise ValueError('Public font manifest must contain six OFL faces')
    result = {}
    notices = set()
    for face in pack['fonts']:
        if not isinstance(face, dict) or face.get('license') != 'OFL-1.1':
            raise ValueError('Only declared public OFL faces are publishable')
        for name, key in ((face['path'], 'sha256'), (face['notice_path'], 'notice_sha256')):
            if (not isinstance(name, str) or not name.startswith('assets/fonts/') or
                    not isinstance(face[key], str) or not re.fullmatch(r'[a-f0-9]{64}', face[key])):
                raise ValueError('Noncanonical public font manifest')
            if name in result and result[name] != face[key]:
                raise ValueError('Conflicting public font hashes')
            result[name] = face[key]
        notices.add(face['notice_path'])
    if len(result) != 10 or len(notices) != 4:
        raise ValueError('Public font coverage must include four notices')
    # One policy source; parse its literal dictionary without executing code.
    try:
        policy = ast.parse(_bounded_regular(ROOT / 'scripts/package_release.py', ROOT, 1024 * 1024))
        assignments = [node for node in policy.body if isinstance(node, ast.Assign) and
                       any(isinstance(target, ast.Name) and target.id == 'PUBLIC_FILES' for target in node.targets)]
        if len(assignments) != 1:
            raise ValueError('One public asset policy is required')
        reviewed = ast.literal_eval(assignments[0].value)
    except (SyntaxError, TypeError) as error:
        raise ValueError('Public asset policy must be a literal dictionary') from error
    if result != reviewed:
        raise ValueError('Public font/notice pins differ from the reviewed source policy')
    return result


def _entropy(value):
    return -sum((value.count(c) / len(value)) * math.log2(value.count(c) / len(value)) for c in set(value))


def inspect_files(root, names, known_values=()):
    """Only findings' category/path/line are returned; never matched values."""
    root = Path(root).resolve()
    findings, files, total = [], {}, 0
    if not isinstance(names, (list, tuple)) or any(not isinstance(name, str) for name in names):
        raise ValueError('Publication manifest must contain only relative file-name strings')
    names = list(names)
    if len(names) != len(set(names)):
        findings.append({'path': '<manifest>', 'category': 'duplicate_paths'})
    pins = _public_assets(root)
    for name in sorted(set(names)):
        if not isinstance(name, str):
            findings.append({'path': '<invalid_path>', 'category': 'noncanonical_path'})
            continue
        pure = PurePosixPath(name)
        if (pure.is_absolute() or str(pure) != name or
                '\\' in name or any(part in {'', '.', '..'} for part in name.split('/'))):
            findings.append({'path': '<invalid_path>', 'category': 'noncanonical_path'})
            continue
        lowered = [part.casefold() for part in pure.parts]
        if (any(part in PRIVATE_PARTS for part in lowered) or pure.name.casefold() == 'estado.json' or
                pure.name.casefold().startswith(('.env', 'id_rsa', 'id_ed25519')) or
                re.search(r'\.(?:db|sqlite3?)-(?:wal|shm|journal)$', pure.name, re.I) or
                pure.suffix.casefold() in PRIVATE_SUFFIXES):
            findings.append({'path': name, 'category': 'private_path'})
            continue
        if name.startswith('assets/') and name not in pins:
            findings.append({'path': name, 'category': 'unreviewed_asset'})
            continue
        path = root / name
        try:
            data = _bounded_regular(path, root, MAX_FILE)
        except (OSError, ValueError):
            findings.append({'path': name, 'category': 'unsafe_or_changed_file'})
            continue
        digest = hashlib.sha256(data).hexdigest()
        total += len(data)
        files[name] = {'sha256': digest, 'bytes': len(data)}
        if total > MAX_TOTAL:
            findings.append({'path': '<manifest>', 'category': 'total_size_limit'})
            break
        if name in pins and digest != pins[name]:
            findings.append({'path': name, 'category': 'public_font_pin_mismatch'})
        for value in known_values:
            encoded = value.encode() if isinstance(value, str) else value
            if isinstance(encoded, bytes) and len(encoded) >= 8 and encoded in data:
                findings.append({'path': name, 'category': 'known_private_value'})
        if pure.suffix.casefold() not in TEXT_SUFFIXES and pure.name != '.gitignore':
            continue
        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError:
            findings.append({'path': name, 'category': 'invalid_text_encoding'})
            continue
        for category, pattern in SECRETS:
            for match in pattern.finditer(text):
                if category == 'provider_token' and _entropy(match.group()) < 4:
                    continue  # Low-entropy explicit fixtures are reported by the independent review.
                findings.append({'path': name, 'line': text.count('\n', 0, match.start()) + 1, 'category': category})
        if name not in pins:
            for match in EMAIL.finditer(text):
                domain = match.group(1).casefold()
                synthetic = domain in SYNTHETIC_DOMAINS or domain.endswith(('.test', '.invalid', '.example'))
                if not synthetic and not domain.endswith('users.noreply.github.com'):
                    findings.append({'path': name, 'line': text.count('\n', 0, match.start()) + 1, 'category': 'non_fixture_email'})
    if not pins.keys() <= files.keys():
        findings.append({'path': 'assets/fonts', 'category': 'missing_public_fonts_or_notices'})
    return {'passed': not findings, 'files': files, 'file_count': len(files),
            'total_bytes': total, 'findings': findings, 'sensitive_values_printed': False,
            'limitations': ['Pattern and known-value checks do not detect every secret or vulnerability.',
                            'Only the supplied current tree is checked, not commit history.',
                            'Public OFL attribution and synthetic email examples are retained.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--git-tree', action='store_true')
    mode.add_argument('--manifest', type=Path)
    args = parser.parse_args()
    if args.git_tree:
        top = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', '--show-toplevel'],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        repository = Path(top.stdout.decode().strip())
        if repository.resolve() != repository or not ROOT.is_relative_to(repository):
            raise ValueError('Git tree must contain this exact source directory')
        for command in (['git', '-C', str(ROOT), 'diff', '--quiet'],
                        ['git', '-C', str(ROOT), 'diff', '--cached', '--quiet']):
            if subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode:
                raise ValueError('Git index and checkout must match the committed tree')
        # A monorepo may contain other reviewed projects. Inspect only this
        # source directory, while requiring the entire Git checkout to remain
        # committed and unchanged before and after the inspection.
        result = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '-z', '--cached', '--', '.'],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        names = [value.decode('utf-8') for value in result.stdout.split(b'\0') if value]
    else:
        manifest = _json(_bounded_regular(args.manifest.absolute(), ROOT, 1024 * 1024))
        if isinstance(manifest, list):
            names = manifest
        elif isinstance(manifest, dict) and isinstance(manifest.get('files'), (dict, list)):
            names = list(manifest['files'])
        else:
            raise ValueError('Manifest must contain an explicit file list')
    report = inspect_files(ROOT, names)
    if args.git_tree:
        for command in (['git', '-C', str(ROOT), 'diff', '--quiet'],
                        ['git', '-C', str(ROOT), 'diff', '--cached', '--quiet']):
            if subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode:
                raise ValueError('Git tree changed during security inspection')
    # No file contents, credentials or matched strings are emitted.
    print(json.dumps({key: report[key] for key in ('passed', 'file_count', 'total_bytes', 'findings', 'sensitive_values_printed', 'limitations')}, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        print('Publication security input is invalid; no sensitive values printed.', file=sys.stderr)
        raise SystemExit(2)

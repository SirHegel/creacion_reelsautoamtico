"""Publication gates reject private data and aliases without leaking matches."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


SOFTWARE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('publication_security', SOFTWARE / 'scripts/security_check.py')
security = importlib.util.module_from_spec(spec)
spec.loader.exec_module(security)


@pytest.fixture
def source(tmp_path, monkeypatch):
    # Small synthetic files only, never a duplicate checkout or credential read.
    root = tmp_path / 'source'
    root.mkdir()
    monkeypatch.setattr(security, '_public_assets', lambda value: {})
    return root


@pytest.mark.parametrize('name', ['.estado/account.json', 'workspaces/person/data.json',
    'projects/raw.json', 'Crudos/input.txt', '.env.local', 'secret.key', 'accounts/user.json',
    'credentials/token.txt', '.ssh/id_ed25519', 'db.sqlite3-wal', 'exports/output.zip',
    'backups/account.json', 'cache.pyc', 'id_rsa.pub', 'raw/media.json'])
def test_private_names_are_rejected_without_opening(source, name, monkeypatch):
    monkeypatch.setattr(security, '_bounded_regular', lambda *args: pytest.fail('Private paths must not be opened'))
    report = security.inspect_files(source, [name])
    assert not report['passed'] and report['files'] == {}
    assert report['findings'] == [{'path': name, 'category': 'private_path'}]


@pytest.mark.parametrize('name', ['/etc/passwd', '../outside.txt', './readme.md', 'a//b.py', 'a\\b.py'])
def test_escaping_and_noncanonical_names_fail(source, name):
    report = security.inspect_files(source, [name])
    assert not report['passed'] and report['files'] == {}
    assert report['findings'][0]['category'] == 'noncanonical_path'


@pytest.mark.parametrize('names', [None, {}, [None], [False], ['README.md', {}]])
def test_manifest_types_fail_closed(source, names):
    with pytest.raises(ValueError):
        security.inspect_files(source, names)


def test_duplicate_paths_and_unreviewed_assets_fail(source):
    (source / 'README.md').write_text('Synthetic safe source')
    assert security.inspect_files(source, ['README.md'])['passed']
    report = security.inspect_files(source, ['README.md', 'README.md', 'assets/images/private.png'])
    assert not report['passed']
    assert {f['category'] for f in report['findings']} == {'duplicate_paths', 'unreviewed_asset'}


@pytest.mark.parametrize('alias', ['symlink', 'hardlink', 'directory'])
def test_foreign_file_aliases_and_nonfiles_are_not_read(source, alias):
    foreign = source.parent / 'foreign.txt'
    foreign.write_text('Opaque synthetic private value')
    target = source / 'README.md'
    if alias == 'symlink':
        target.symlink_to(foreign)
    elif alias == 'hardlink':
        os.link(foreign, target)
    else:
        target.mkdir()
    report = security.inspect_files(source, ['README.md'])
    assert not report['passed'] and report['files'] == {}
    assert report['findings'][0]['category'] == 'unsafe_or_changed_file'


@pytest.mark.parametrize('category,value', [
    ('github_token', 'ghp_' + '0123456789abcdefABCDEF' * 3),
    ('provider_token', 'sk-' + '0123456789abcdefABCDEFxyzXYZ_-uv' * 3),
    ('aws_access_identifier', 'AKIA' + 'ABCDEFGHIJKLMNOP'),
    ('google_api_key', 'AIza' + 'A' * 35),
    ('private_key_block', '-----BEGIN ' + 'PRIVATE KEY-----\n' + 'A' * 40 + '\n-----END PRIVATE KEY-----'),
    ('non_fixture_email', 'private-fixture' + '@' + 'generated-mail.net'),
])
def test_secret_patterns_report_category_without_matching_value(source, category, value):
    (source / 'README.md').write_text('Fixture before\n' + value + '\nFixture after')
    report = security.inspect_files(source, ['README.md'])
    assert not report['passed']
    assert {'path': 'README.md', 'line': 2, 'category': category} in report['findings']
    assert value not in json.dumps(report)
    assert report['sensitive_values_printed'] is False


def test_known_private_values_are_blocked_even_without_a_token_pattern(source):
    value = 'opaque-' + '12345678' * 3
    (source / 'README.md').write_text(value)
    report = security.inspect_files(source, ['README.md'], known_values=[value])
    assert not report['passed'] and report['findings'][0]['category'] == 'known_private_value'
    assert value not in json.dumps(report)


def test_synthetic_addresses_and_noreply_author_are_permitted(source):
    text = '\n'.join('fixture' + '@' + domain for domain in ('example.com', 'ejemplo.com',
                     'mail.test', 'unused.invalid', 'users.noreply.github.com'))
    (source / 'README.md').write_text(text)
    assert security.inspect_files(source, ['README.md'])['passed']


def test_single_file_and_total_budgets_fail(source, monkeypatch):
    (source / 'README.md').write_text('1234567890')
    monkeypatch.setattr(security, 'MAX_FILE', 9)
    assert not security.inspect_files(source, ['README.md'])['passed']
    monkeypatch.setattr(security, 'MAX_FILE', 20)
    monkeypatch.setattr(security, 'MAX_TOTAL', 9)
    report = security.inspect_files(source, ['README.md'])
    assert not report['passed'] and report['findings'][0]['category'] == 'total_size_limit'


@pytest.fixture
def pack_root(tmp_path):
    root = tmp_path / 'pack'
    (root / 'packs').mkdir(parents=True)
    pack = json.loads((SOFTWARE / 'packs/public_fonts.json').read_text())
    (root / 'packs/public_fonts.json').write_text(json.dumps(pack))
    return root, pack


def test_actual_ofl_policy_contains_all_fonts_and_required_notices():
    pins = security._public_assets(SOFTWARE)
    report = security.inspect_files(SOFTWARE, list(pins))
    assert len(pins) == 10 and report['passed']
    assert report['file_count'] == 10


@pytest.mark.parametrize('mutation', ['list_root', 'bad_faces', 'bad_face', 'bad_hash', 'changed_pin', 'duplicate_key'])
def test_malformed_public_font_packs_are_rejected(pack_root, mutation):
    root, pack = pack_root
    pack = copy.deepcopy(pack)
    if mutation == 'list_root':
        pack = []
    elif mutation == 'bad_faces':
        pack['fonts'] = None
    elif mutation == 'bad_face':
        pack['fonts'][0] = None
    elif mutation == 'bad_hash':
        pack['fonts'][0]['sha256'] = False
    elif mutation == 'changed_pin':
        pack['fonts'][0]['sha256'] = '0' * 64
    raw = json.dumps(pack)
    if mutation == 'duplicate_key':
        raw = '{"schema":"a","schema":"b"}'
    (root / 'packs/public_fonts.json').write_text(raw)
    with pytest.raises(ValueError):
        security._public_assets(root)


def test_public_manifest_alias_is_rejected_before_read(pack_root):
    root, _ = pack_root
    path = root / 'packs/public_fonts.json'
    foreign = root.parent / 'foreign_manifest.json'
    path.rename(foreign)
    path.symlink_to(foreign)
    with pytest.raises(ValueError):
        security._public_assets(root)


def test_missing_or_executable_public_policy_is_not_executed(pack_root, monkeypatch):
    root, _ = pack_root
    (root / 'scripts').mkdir()
    policy = root / 'scripts/package_release.py'
    marker = root / 'executed.txt'
    monkeypatch.setattr(security, 'ROOT', root)
    for raw in ('pass', 'PUBLIC_FILES = dict()', 'PUBLIC_FILES = [',
                'PUBLIC_FILES = __import__("pathlib").Path("executed.txt").touch()'):
        policy.write_text(raw)
        with pytest.raises(ValueError):
            security._public_assets(root)
    assert not marker.exists()


def test_cli_manifest_accepts_only_bounded_local_file_lists(source, monkeypatch, capsys):
    monkeypatch.setattr(security, 'ROOT', source)
    (source / 'README.md').write_text('Safe synthetic source')
    manifest = source / 'manifest.json'
    manifest.write_text(json.dumps({'files': ['README.md']}))
    monkeypatch.setattr(sys, 'argv', ['security_check', '--manifest', str(manifest)])
    assert security.main() == 0
    assert json.loads(capsys.readouterr().out)['passed']
    manifest.write_text(json.dumps({'files': None}))
    with pytest.raises(ValueError):
        security.main()
    foreign = source.parent / 'foreign.json'
    manifest.rename(foreign)
    manifest.symlink_to(foreign)
    with pytest.raises(ValueError):
        security.main()


def _git_commit(repository):
    subprocess.run(['git', '-C', str(repository), 'add', '--all'], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(repository), '-c', 'user.name=Publication Test',
                    '-c', 'user.email=publication@example.invalid',
                    'commit', '--quiet', '-m', 'Synthetic public sources'],
                   check=True, capture_output=True)


@pytest.mark.parametrize('nested', [False, True])
def test_cli_git_tree_accepts_committed_root_or_nested_sources(source, monkeypatch, capsys, nested):
    repository = source.parent if nested else source
    subprocess.run(['git', '-C', str(repository), 'init', '--quiet'], check=True, capture_output=True)
    (source / 'README.md').write_text('Safe synthetic source')
    if nested:
        (repository / 'other-project.txt').write_text('Separately reviewed project')
    _git_commit(repository)
    monkeypatch.setattr(security, 'ROOT', source)
    monkeypatch.setattr(sys, 'argv', ['security_check', '--git-tree'])
    assert security.main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report['passed'] and report['file_count'] == 1


@pytest.mark.parametrize('dirty', ['source', 'staged_source', 'outside_source'])
def test_cli_nested_git_tree_requires_entire_checkout_to_stay_committed(source, monkeypatch, dirty):
    repository = source.parent
    subprocess.run(['git', '-C', str(repository), 'init', '--quiet'], check=True, capture_output=True)
    (source / 'README.md').write_text('Safe synthetic source')
    (repository / 'other-project.txt').write_text('Separately reviewed project')
    _git_commit(repository)
    target = repository / 'other-project.txt' if dirty == 'outside_source' else source / 'README.md'
    target.write_text('Uncommitted change')
    if dirty == 'staged_source':
        subprocess.run(['git', '-C', str(repository), 'add', '--all'], check=True, capture_output=True)
    monkeypatch.setattr(security, 'ROOT', source)
    monkeypatch.setattr(sys, 'argv', ['security_check', '--git-tree'])
    with pytest.raises(ValueError, match='committed tree'):
        security.main()

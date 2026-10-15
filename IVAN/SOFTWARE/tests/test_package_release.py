"""Source-only packaging with real public font bytes and private canaries."""
import json
from pathlib import Path
import shutil
import zipfile

import pytest

from scripts import package_release as release


@pytest.fixture
def checkout(tmp_path):
    assert tmp_path.resolve().is_relative_to(release.SOFTWARE / ".estado/tmp")
    root = tmp_path / "checkout"
    root.mkdir()
    names = release.BASE + release.WEB + release.DOCS + release.WORKFLOWS + release.SCREENS
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if name == "packs/public_fonts.json":
            shutil.copyfile(release.SOFTWARE / name, path)
        else:
            path.write_bytes(("Public synthetic source fixture: " + name + "\n").encode())
    for name in release.PUBLIC_FILES:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(release.SOFTWARE / name, path)
    (root / "studio").mkdir()
    (root / "studio/__init__.py").write_text('__version__="fixture"\n')
    (root / "studio/core.py").write_text('"""Synthetic packaging fixture; never executed."""\n')
    return root


def test_package_exact_allowlist_crc_hash_and_no_private_canaries(checkout):
    forbidden = [".estado/accounts/credentials.json", ".estado/models/large.bin", "workspaces/w_user/private.mp4",
                 "projects/private/source.mp4", "exports/private.zip", "assets/video/source.mp4",
                 "assets/fonts/Sequel_Sans_Bold_Disp.ttf", "assets/fonts/Scholar_Italic.ttf",
                 "privateassets/private.png", "private_assets/private.png", "docs/segmentation-editor.png",
                 "docs/private.json", "web/private.mp4", "tests/private_harness.py", "scripts/private_helper.py"]
    for name in forbidden:
        path = checkout / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"PRIVATE_CANARY_ONLY_A_SYNTHETIC_TEST_NOT_A_REAL_KEY")
    plan = release.plan_release(checkout)
    assert not set(forbidden) & set(plan)
    result = release.build_release(checkout)
    assert result["verified_crc_and_sha256"] is True and result["deployed"] is False
    assert result["commercial_ready"] is False
    archive = checkout / result["path"]
    manifest = release.verify_zip(archive, plan)
    assert manifest["public_font_faces"] == 6 and manifest["public_font_notices"] == 4
    assert manifest["runtime_installed"] is False and manifest["private_data_included"] is False
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and set(z.namelist()) == set(plan) | {release.MANIFEST}
        assert {n for n in z.namelist() if n.startswith("docs/") and n.endswith(".png")} == {
            'docs/portal.png', 'docs/portal-mobile.png', 'docs/home-desktop.png',
            'docs/home-mobile.png', 'docs/shared-viewer.png', 'docs/typography-fonts.png',
            'docs/typography-editor.png', 'docs/typography-editor-mobile.png',
        }
        assert not any(b"PRIVATE_CANARY_ONLY" in z.read(n) for n in z.namelist())
    assert all((checkout / n).exists() for n in forbidden)


@pytest.mark.parametrize("name", ["README.md", "studio/core.py", "web/app.js", "docs/portal.png", "assets/fonts/7776ddb9f3eb58683e59.otf"])
def test_allowlisted_symlink_rejected_without_touching_target(checkout, name):
    path = checkout / name
    target = checkout.parent / "private_data"
    target.write_bytes(path.read_bytes())
    path.unlink();path.symlink_to(target)
    before = target.read_bytes()
    with pytest.raises(release.PackageError, match="enlaces"):
        release.build_release(checkout)
    assert target.read_bytes() == before
    assert not (checkout / release.OUTPUT).exists()


def test_ancestor_alias_and_root_alias_are_rejected(checkout):
    web = checkout / "web"
    moved = checkout.parent / "private_web"
    web.rename(moved);web.symlink_to(moved, target_is_directory=True)
    with pytest.raises(release.PackageError):
        release.plan_release(checkout)
    alias = checkout.parent / "checkout_alias"
    alias.symlink_to(checkout, target_is_directory=True)
    with pytest.raises(release.PackageError):
        release.plan_release(alias)


def test_hardlinked_public_source_is_rejected(checkout):
    path = checkout / "README.md"
    path.hardlink_to(checkout / "LICENSE") if not path.exists() else None
    target = checkout.parent / "private_hardlink"
    target.hardlink_to(path)
    with pytest.raises(release.PackageError, match="regulares"):
        release.plan_release(checkout)
    assert target.read_bytes() == path.read_bytes()


@pytest.mark.parametrize("mutation", ["font_bytes", "notice_bytes", "manifest_path", "manifest_sha", "manifest_id", "manifest_license", "missing_screen"])
def test_public_pins_and_required_screens_cannot_be_forged(checkout, mutation):
    font = checkout / "assets/fonts/7776ddb9f3eb58683e59.otf"
    notice = checkout / "assets/fonts/licenses/89ad2c4f66dd29127527493e.txt"
    if mutation in {"font_bytes", "notice_bytes"}:
        path = font if mutation == "font_bytes" else notice
        raw = path.read_bytes();path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
    elif mutation == "missing_screen":
        (checkout / release.SCREENS[0]).unlink()
    else:
        path = checkout / "packs/public_fonts.json"
        value = json.loads(path.read_text())
        face = value["fonts"][0]
        if mutation == "manifest_path":
            face["path"] = "assets/fonts/Sequel_Sans_Bold_Disp.ttf"
        elif mutation == "manifest_sha":
            face["sha256"] = "0" * 64
        elif mutation == "manifest_id":
            face["asset_id"] = "a_private"
        else:
            face["license"] = "owner_declared"
        path.write_text(json.dumps(value))
    with pytest.raises((release.PackageError, FileNotFoundError)):
        release.build_release(checkout)
    assert not (checkout / release.OUTPUT).exists()


def test_previous_package_preserved_if_source_changes_before_promotion(checkout, monkeypatch):
    first = release.build_release(checkout)
    output = checkout / first["path"]
    original_zip = output.read_bytes()
    original_verify = release.verify_zip
    def changed(path, expected):
        result = original_verify(path, expected)
        (checkout / "README.md").write_text("Changed after CRC, before source promotion.")
        return result
    monkeypatch.setattr(release, "verify_zip", changed)
    with pytest.raises(release.PackageError, match="SHA"):
        release.build_release(checkout)
    assert output.read_bytes() == original_zip
    assert not list((checkout / ".estado/tmp").glob("source_release_*"))


def test_new_module_during_packaging_invalidates_file_coverage(checkout, monkeypatch):
    original = release.verify_zip
    def added(path, expected):
        result = original(path, expected)
        (checkout / "studio/new_module.py").write_text("# New source requires a new snapshot.\n")
        return result
    monkeypatch.setattr(release, "verify_zip", added)
    with pytest.raises(release.PackageError, match="lista"):
        release.build_release(checkout)
    assert not (checkout / release.OUTPUT).exists()


def test_output_symlink_and_foreign_destination_are_rejected(checkout):
    target = checkout.parent / "private_existing.zip"
    target.write_bytes(b"private fixture must remain intact")
    output = checkout / release.OUTPUT
    output.parent.mkdir();output.symlink_to(target)
    with pytest.raises(release.PackageError):
        release.build_release(checkout)
    assert target.read_bytes() == b"private fixture must remain intact"
    output.unlink()
    with pytest.raises(release.PackageError):
        release.build_release(checkout, target)


def test_zip_verifier_rejects_extra_private_member_and_changed_member(checkout):
    plan = release.plan_release(checkout)
    packaged = checkout / release.build_release(checkout)["path"]
    for private in (True, False):
        changed = checkout / ".estado/tmp/changed.zip"
        with zipfile.ZipFile(packaged) as source, zipfile.ZipFile(changed, "w") as destination:
            for info in source.infolist():
                raw = source.read(info.filename)
                if not private and info.filename == "README.md":
                    raw = b"forged source"
                destination.writestr(info, raw)
            if private:
                destination.writestr(".estado/providers.key", b"PRIVATE_TEST_CANARY")
        with pytest.raises(release.PackageError):
            release.verify_zip(changed, plan)

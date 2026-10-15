"""Explicit skill attestations using an entirely self-owned canonical fixture."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from studio import core, skills, jobs
from test_core import sandbox

REAL_VALIDATE_APPLICATION = skills.validate_application

@pytest.fixture
def skill_workspace(sandbox, monkeypatch):
    # Generic core fixtures suppress this new gate for their unrelated tests;
    # these tests must exercise the actual validator.
    monkeypatch.setattr(skills, "validate_application", REAL_VALIDATE_APPLICATION)
    monkeypatch.setattr(skills, "MANUAL_ROOT", sandbox.parent)
    source = sandbox.parent / ".agents/skills"
    for name in skills.REQUIRED:
        directory = source / name
        directory.mkdir(parents=True)
        (directory / "SKILL.md").write_text("Fixture guide for " + name + ": read before applying.\n")
        (directory / "implementation.md").write_text("Fixture implementation instructions.\n")
    for reference in skills.REFERENCES:
        file = source / reference
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("Fixture required reference: " + reference + ".\n")
    project = core.create_project("Skill fixture")
    proof = sandbox / ".estado/tmp/evidence.txt"
    proof.write_text("Self-owned evidence from a fixture, never an approved client render.\n")
    return sandbox, source, project, {"path": ".estado/tmp/evidence.txt", "sha256": core.digest(proof)}


def completed_record(workspace):
    root, source, project, proof = workspace
    project = skills.prepare(project["id"])
    record = project["skills_applied"]
    record["status"] = "reviewed_applied"
    for entry in record["entries"]:
        entry.update(reading="read_by_agent", reviewer="Fixture reviewer", decision="Applied relevant fixture contract; no client approval.", evidence=[copy.deepcopy(proof)])
    for reference in record["references"]:
        reference.update(reading="read_by_agent", reviewer="Fixture reviewer")
    record["catalog_query"].update(query="connected elements transform along a visible path", language="en", decision="Fixture search considered reuse; chose its verified local implementation.", evidence=[copy.deepcopy(proof)])
    return project


def test_inventory_has_twelve_real_source_hashes_and_five_references(skill_workspace):
    root, source, project, proof = skill_workspace
    observed = skills.inventory()
    assert observed["required_count"] == 12 and len(observed["references"]) == 5
    assert all(item["available"] and len(item["sha256"]) == len(item["tree_sha256"]) == 64 for item in observed["skills"])
    assert all(item["available"] and len(item["sha256"]) == 64 for item in observed["references"])
    assert observed["reading_verified"] is False and observed["application_verified"] is False


def test_prepare_is_pending_and_preserves_existing_record_verbatim(skill_workspace):
    root, source, project, proof = skill_workspace
    prepared = skills.prepare(project["id"])
    assert prepared["skills_applied"]["status"] == "pending_reading_and_application"
    assert skills.validate_application(prepared)
    first_revision = prepared["revision"]
    first_bytes = core.project_path(project["id"]).read_bytes()
    again = skills.prepare(project["id"])
    assert again == prepared and again["revision"] == first_revision
    assert core.project_path(project["id"]).read_bytes() == first_bytes
    prepared["skills_applied"] = None
    saved = core.save_project(project["id"], prepared)
    assert skills.prepare(project["id"])["skills_applied"] is None


def test_complete_attestation_validates_without_mutation_or_approval(skill_workspace):
    root, source, project, proof = skill_workspace
    project = completed_record(skill_workspace)
    snapshot = copy.deepcopy(project)
    sources = {p: p.read_bytes() for p in source.rglob("*") if p.is_file()}
    assert skills.validate_application(project) == []
    assert project == snapshot and not project["review"]
    assert all(p.read_bytes() == value for p, value in sources.items())


def test_installation_and_hashes_never_substitute_for_reading(skill_workspace):
    root, source, project, proof = skill_workspace
    project = completed_record(skill_workspace)
    entry = project["skills_applied"]["entries"][0]
    entry["reading"] = "pending"
    entry["reviewer"] = None
    assert any("lectura real" in error for error in skills.validate_application(project))


def test_support_file_change_invalidates_tree_even_with_unchanged_skill_md(skill_workspace):
    root, source, project, proof = skill_workspace
    project = completed_record(skill_workspace)
    before = skills.inventory()["skills"][0]
    (source / skills.REQUIRED[0] / "implementation.md").write_text("Changed supporting requirement.\n")
    after = skills.inventory()["skills"][0]
    assert before["sha256"] == after["sha256"] and before["tree_sha256"] != after["tree_sha256"]
    assert any("Skill modificada" in error for error in skills.validate_application(project))


def test_reference_change_invalidates_its_read_attestation(skill_workspace):
    root, source, project, proof = skill_workspace
    project = completed_record(skill_workspace)
    (source / skills.REFERENCES[0]).write_text("New GSAP runtime contract.\n")
    assert any("Referencia de skill modificada" in error for error in skills.validate_application(project))


def test_missing_skill_is_unavailable_and_stably_reported(skill_workspace):
    root, source, project, proof = skill_workspace
    project = completed_record(skill_workspace)
    (source / skills.REQUIRED[0] / "SKILL.md").unlink()
    observed = skills.inventory()
    assert observed["skills"][0]["available"] is False
    first = skills.validate_application(project)
    assert any("no disponible" in error for error in first)
    assert skills.validate_application(project) == first


def test_modified_or_empty_evidence_is_rejected(skill_workspace):
    root, source, project, proof = skill_workspace
    project = completed_record(skill_workspace)
    (root / proof["path"]).write_text("Changed observation.\n")
    assert any("evidencia está vacía o cambió" in error for error in skills.validate_application(project))
    (root / proof["path"]).write_bytes(b"")
    empty_sha = core.digest(root / proof["path"])
    for entry in project["skills_applied"]["entries"]:
        entry["evidence"][0]["sha256"] = empty_sha
    assert any("evidencia está vacía" in error for error in skills.validate_application(project))


def test_evidence_path_escape_never_reads_canonical_parent(skill_workspace):
    root, source, project, proof = skill_workspace
    project = completed_record(skill_workspace)
    outside = root.parent / "private-fixture.txt"
    outside.write_text("Owned fixture outside its simulated SOFTWARE root.\n")
    (root / "escaped-proof").symlink_to(outside)
    project["skills_applied"]["entries"][0]["evidence"] = [{"path": "escaped-proof", "sha256": core.digest(outside)}]
    assert any("fuera de SOFTWARE" in error for error in skills.validate_application(project))
    assert outside.read_text().startswith("Owned fixture")


def test_source_symlink_escape_is_unavailable_not_executed(skill_workspace):
    root, source, project, proof = skill_workspace
    outside = root.parent / "private-guide.txt"
    outside.write_text("Do not read via a guide alias outside .agents.\n")
    guide = source / skills.REQUIRED[0] / "SKILL.md"
    guide.unlink()
    guide.symlink_to(outside)
    observed = skills.inventory()
    assert observed["skills"][0]["available"] is False
    assert "fuera" in observed["skills"][0]["error"]


def test_source_traversal_to_agents_sibling_is_rejected(skill_workspace):
    root, source, project, proof = skill_workspace
    sibling = source.parent / "private-fixture.md"
    sibling.write_text("Not a canonical skill guide.\n")
    with pytest.raises(core.StudioError) as error:
        skills._source(skills.SOURCE_PREFIX + "../private-fixture.md")
    assert error.value.status == 403
    alias = source / skills.REQUIRED[0] / "sibling.md"
    alias.symlink_to(sibling)
    assert skills.inventory()["skills"][0]["available"] is False


def test_change_to_earlier_support_file_during_tree_read_is_rejected(skill_workspace, monkeypatch):
    root, source, project, proof = skill_workspace
    directory = source / skills.REQUIRED[0]
    (directory / "aaa.md").write_text("First supporting guide.\n")
    (directory / "zzz.md").write_text("Last supporting guide.\n")
    read = skills._read_hash
    changed = []
    def changing_read(path, digest=None):
        if path == directory / "zzz.md" and digest is not None and not changed:
            (directory / "aaa.md").write_text("Changed after its bytes were already hashed.\n")
            changed.append(True)
        return read(path, digest)
    monkeypatch.setattr(skills, "_read_hash", changing_read)
    inventory = skills.inventory()
    assert changed and not inventory["skills"][0]["available"]
    assert "árbol" in inventory["skills"][0]["error"]


def test_guide_change_between_file_hash_and_tree_hash_is_rejected(skill_workspace, monkeypatch):
    root, source, project, proof = skill_workspace
    tree = skills._tree_hash
    def changing_tree(name):
        if name == skills.REQUIRED[0]:
            (source / name / "SKILL.md").write_text("Changed between guide and tree inventory.\n")
        return tree(name)
    monkeypatch.setattr(skills, "_tree_hash", changing_tree)
    assert not skills.inventory()["skills"][0]["available"]


def test_live_guide_bytes_invalidate_existing_editorial_digest(skill_workspace):
    root, source, project, proof = skill_workspace
    project = completed_record(skill_workspace)
    before = core.editorial_digest(project)
    old_record = copy.deepcopy(project["skills_applied"])
    (source / skills.REQUIRED[0] / "implementation.md").write_text("Updated support contract.\n")
    assert project["skills_applied"] == old_record
    assert core.editorial_digest(project) != before


@pytest.mark.parametrize("change", ["manual", "duplicate", "decision", "reference_read", "catalog_query", "catalog_language", "catalog_proof"])
def test_semantic_attestation_fields_are_required(skill_workspace, change):
    root, source, project, proof = skill_workspace
    project = completed_record(skill_workspace)
    record = project["skills_applied"]
    if change == "manual":
        (root.parent / "PROMPT_MAESTRO.md").write_text("Updated fixture manual.\n")
    elif change == "duplicate":
        record["entries"].append(copy.deepcopy(record["entries"][0]))
    elif change == "decision":
        record["entries"][0]["decision"] = "   "
    elif change == "reference_read":
        record["references"][0]["reading"] = "pending"
    elif change == "catalog_query":
        record["catalog_query"]["query"] = ""
    elif change == "catalog_language":
        record["catalog_query"]["language"] = "es"
    elif change == "catalog_proof":
        record["catalog_query"]["evidence"] = []
    assert skills.validate_application(project)


@pytest.mark.parametrize("record", [None, [], "invalid", {"entries": None, "references": None, "catalog_query": None},
                                   {"entries": [None, 3, [], {"name": []}], "references": [None, {"path": []}], "catalog_query": {"query": []}}])
def test_malformed_json_shapes_return_errors_instead_of_500(skill_workspace, record):
    root, source, project, proof = skill_workspace
    project["skills_applied"] = record
    assert isinstance(skills.validate_application(project), list)
    assert skills.validate_application(project)


def test_additional_references_require_current_canonical_hash_and_reading(skill_workspace):
    root, source, project, proof = skill_workspace
    project = completed_record(skill_workspace)
    reference = source / "hyperframes-registry/implementation.md"
    project["skills_applied"]["references"].append({"path": skills.SOURCE_PREFIX + "hyperframes-registry/implementation.md",
                                                    "sha256": core.digest(reference), "reading": "read_by_agent", "reviewer": "Fixture reviewer"})
    assert skills.validate_application(project) == []
    project["skills_applied"]["references"][-1]["path"] = "/etc/passwd"
    assert any("fuera de su fuente" in error for error in skills.validate_application(project))


def test_english_query_supports_unicode_names_and_punctuation(skill_workspace):
    project = completed_record(skill_workspace)
    project["skills_applied"]["catalog_query"]["query"] = "Animate O’Connor’s café headline with a reveal ✨"
    assert skills.validate_application(project) == []


def test_cyclic_proof_symlink_returns_validation_error(skill_workspace):
    root, source, project, proof = skill_workspace
    project = completed_record(skill_workspace)
    cyclic = root / "cycle-proof"
    cyclic.symlink_to(cyclic.name)
    project["skills_applied"]["entries"][0]["evidence"] = [{"path": "cycle-proof", "sha256": "0" * 64}]
    assert any("evidencia inexistente" in error for error in skills.validate_application(project))


def test_changed_guide_invalidates_an_already_claimed_agent_lease(skill_workspace):
    root, source, project, proof = skill_workspace
    project = completed_record(skill_workspace)
    project = core.save_project(project["id"], project)
    jobs.create_tasks(project["id"])
    task = jobs.claim_task("director", "Fixture reader")
    (source / skills.REQUIRED[0] / "implementation.md").write_text("Guide changed after claiming the task.\n")
    with pytest.raises(core.StudioError, match="cambió desde la asignación") as error:
        jobs.finish_task(task["id"], task["lease"], {"observations": "Fixture observations", "evidence": [proof["path"]]})
    assert error.value.status == 409
    assert next(t for t in jobs.tasks() if t["id"] == task["id"])["status"] == "claimed"


def test_changed_guide_invalidates_existing_render_receipt_before_review(skill_workspace):
    root, source, project, proof = skill_workspace
    project = completed_record(skill_workspace)
    output = root / "projects" / project["id"] / "fixture_render.mp4"
    output.write_bytes(b"Synthetic receipt fixture, not a real render")
    project["renders"] = [{"path": core.relative(output), "sha256": core.digest(output), "duration": 3,
                           "mode": "technical_library", "editorial_digest": core.editorial_digest(project)}]
    core.save_project(project["id"], project, action="rendered")
    (source / skills.REQUIRED[0] / "SKILL.md").write_text("Guide changed after producing the receipt.\n")
    with pytest.raises(core.StudioError, match="cronología vigente") as error:
        core.record_review(project["id"], {"approve_preview": False})
    assert error.value.status == 409

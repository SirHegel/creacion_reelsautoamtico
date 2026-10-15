"""Process-scoped workspaces; no global-root switching in HTTP requests."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

import pytest

from studio import runtime
from studio import core, jobs, branding, hyperframes


@pytest.fixture
def scopes(tmp_path):
    assert tmp_path.resolve().is_relative_to(runtime.CODE_ROOT / ".estado/tmp")
    runtime.WORKSPACES_ROOT.mkdir(exist_ok=True)
    roots = [runtime.WORKSPACES_ROOT / ("_runtime_test_" + uuid.uuid4().hex) for _ in range(2)]
    for root in roots:
        root.mkdir(mode=0o700)
    yield roots
    for root in roots:
        # Remove only the two known, uniquely owned test namespaces. Never
        # follow a link or clean the workspace base or an application tenant.
        if root.is_symlink():
            root.unlink()
        elif root.is_dir():
            assert root.parent == runtime.WORKSPACES_ROOT and root.name.startswith("_runtime_test_")
            shutil.rmtree(root)


def environment(tmp_path, workspace=None):
    value = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8",
             "TMPDIR": str(tmp_path), "PYTHONPATH": str(runtime.CODE_ROOT), "PYTHONDONTWRITEBYTECODE": "1"}
    if workspace is not None:
        value["ASCENDIA_WORKSPACE"] = str(workspace)
    return value


def process(tmp_path, code, workspace=None, *arguments):
    return subprocess.Popen([sys.executable, "-B", "-c", code, *map(str, arguments)],
        cwd=runtime.CODE_ROOT, env=environment(tmp_path, workspace), stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def result(child):
    stdout, stderr = child.communicate(timeout=30)
    assert child.returncode == 0, stderr.decode("utf-8", "replace")
    return json.loads(stdout)


ROOT_REPORT = """
import json
from studio import core,jobs,analysis,runtime,hyperframes,media_tools,skills
print(json.dumps({'code':str(runtime.CODE_ROOT),'manual':str(core.MANUAL_ROOT),
 'data':str(core.ROOT),'analysis':str(analysis.ROOT),'jobs':str(jobs.ROOT),
 'hf_limit':str(hyperframes.ROOT),'media_limit':str(media_tools.ROOT),
 'cpu':str(jobs.SHARED_CPU_LOCK),'dependencies':str(hyperframes._dependencies()['packages']),
 'skill_source':str(skills._source('../.agents/skills/hyperframes/SKILL.md')),
 'manual_sha':{k:v['sha256'] for k,v in core.manual_fingerprints().items()}}))
"""


def test_unconfigured_process_keeps_legacy_paths(tmp_path):
    value = result(process(tmp_path, ROOT_REPORT))
    assert value["data"] == value["analysis"] == value["jobs"] == str(runtime.CODE_ROOT)
    assert value["hf_limit"] == value["media_limit"] == str(runtime.CODE_ROOT)
    assert value["manual"] == str(runtime.MANUAL_ROOT)
    assert value["cpu"] == str(runtime.SHARED_CPU_LOCK)


def test_roots_are_selected_once_per_backend_and_code_stays_shared(tmp_path,scopes):
    children = [process(tmp_path, ROOT_REPORT, root) for root in scopes]
    values = [result(child) for child in children]
    for root, value in zip(scopes, values):
        assert value["data"] == value["analysis"] == value["jobs"] == str(root)
        assert value["code"] == value["hf_limit"] == value["media_limit"] == str(runtime.CODE_ROOT)
        assert value["cpu"] == str(runtime.SHARED_CPU_LOCK)
        assert value["manual"] == str(runtime.MANUAL_ROOT)
        assert value["dependencies"] == str(runtime.MANUAL_ROOT / ".estado/herramientas/node_modules")
        assert value["skill_source"] == str(runtime.MANUAL_ROOT / ".agents/skills/hyperframes/SKILL.md")
    assert values[0]["manual_sha"] == values[1]["manual_sha"]
    assert values[0]["data"] != values[1]["data"]
    assert list(scopes[0].iterdir()) == list(scopes[1].iterdir()) == []


@pytest.mark.parametrize("bad", ["", "/tmp/outside", "workspaces", "workspaces/../projects", "projects", "../IVAN", "."])
def test_invalid_workspace_fails_before_any_write(tmp_path,bad):
    child = process(tmp_path, "from studio import core;core.setup()", bad)
    stdout, stderr = child.communicate(timeout=20)
    assert child.returncode != 0 and not stdout
    assert b"WorkspaceConfigurationError" in stderr


def test_symlink_even_to_an_internal_workspace_is_not_a_namespace(tmp_path,scopes):
    alias = scopes[0] / "alias"
    alias.symlink_to(scopes[1], target_is_directory=True)
    child = process(tmp_path, "from studio import core;core.setup()", alias)
    stdout, stderr = child.communicate(timeout=20)
    assert child.returncode != 0 and b"WorkspaceConfigurationError" in stderr and not stdout
    assert list(scopes[1].iterdir()) == []


def test_post_start_directory_alias_cannot_open_another_workspace(tmp_path,scopes):
    code = """
import json,sys
from pathlib import Path
from studio import core
root=core.ROOT;backup=root.with_name(root.name+'_before_alias')
root.rename(backup)
try:
 root.symlink_to(Path(sys.argv[1]),target_is_directory=True)
 try:
  core.confined('.estado/private.json')
 except core.StudioError as error:
  print(json.dumps({'status':error.status}))
 else:raise RuntimeError('Workspace alias unexpectedly accepted')
finally:
 root.unlink();backup.rename(root)
"""
    value = result(process(tmp_path,code,scopes[0],scopes[1]))
    assert value["status"] == 403


def test_same_local_names_projects_and_caches_are_private(tmp_path,scopes):
    code = """
import json,sys,os,tempfile
from studio import core,hyperframes,branding
core.setup();core.atomic_json('.estado/private.json',{'owner':sys.argv[1]})
branding.bootstrap(core.ROOT,'Explicit public fixture '+sys.argv[1])
project=core.create_project('Private fixture '+sys.argv[1])
try:core.confined(sys.argv[2],must_exist=True)
except core.StudioError as error:denied=error.status
else:raise RuntimeError('Sibling resource unexpectedly accepted')
print(json.dumps({'owner':core.read_json('.estado/private.json')['owner'],'project':project['name'],
 'count':len(core.project_list()),'assets':core.assets(),'sibling_denied':denied,
 'temps':tempfile.gettempdir(),'caches':{key:os.environ[key] for key in ('XDG_CACHE_HOME','HF_HOME','TORCH_HOME')},
 'fonts':[p.name for p in (core.ROOT/'assets/fonts').iterdir()],'hf_verified':hyperframes.availability(core.ROOT)['verified_execution']}))
"""
    # Populate only an explicit fixture sentinel; never seed private fonts,
    # legacy projects or execution receipts into the new namespace.
    for root in scopes:
        (root / "sibling_sentinel.txt").write_text("Fixture-private, not a media asset")
    children = [process(tmp_path,code,root,label,other / "sibling_sentinel.txt")
                for root,label,other in ((scopes[0],"A",scopes[1]),(scopes[1],"B",scopes[0]))]
    values = [result(child) for child in children]
    for root,label,value in zip(scopes,("A","B"),values):
        assert value["owner"] == label and value["project"] == "Private fixture " + label
        assert value["count"] == 1 and len(value["assets"]) == 6
        assert all(a['kind']=='font' and a['id'] in branding.SEED_FONT_IDS for a in value['assets'])
        assert value["sibling_denied"] == 403 and value["hf_verified"] is False
        assert Path(value["temps"]).is_relative_to(root / ".estado")
        assert all(Path(path).is_relative_to(root / ".estado") for path in value["caches"].values())


def test_two_workspace_workers_share_the_existing_global_cpu_lock(tmp_path,scopes):
    log = tmp_path / "shared_cpu.jsonl"
    code = """
import json,sys,time
from pathlib import Path
from studio import core,jobs
core.setup();log=Path(sys.argv[1]);mode=sys.argv[2]
def operation(unused=None):
 assert jobs.CPU_ACTIVE.active is True
 with log.open('a') as output:
  output.write(json.dumps({'owner':str(core.ROOT),'event':'start','cpu':str(jobs.SHARED_CPU_LOCK)})+'\\n');output.flush()
  time.sleep(.15)
  output.write(json.dumps({'owner':str(core.ROOT),'event':'end'})+'\\n');output.flush()
if mode=='slot':
 with jobs.cpu_slot():operation()
else:
 core.atomic_json('.estado/jobs.json',[{'id':'j_fixture','status':'queued'}])
 jobs._execute=operation
 jobs.execute('j_fixture')
print(json.dumps({'workspace':str(core.ROOT),'completed':True}))
"""
    children = [process(tmp_path,code,root,log,mode) for root,mode in zip(scopes,("slot","execute"))]
    for child in children:
        assert result(child)["completed"] is True
    events = [json.loads(line) for line in log.read_text().splitlines()]
    assert [event["event"] for event in events] == ["start","end","start","end"]
    assert events[0]["owner"] == events[1]["owner"]
    assert events[2]["owner"] == events[3]["owner"] != events[0]["owner"]
    assert events[0]["cpu"] == events[2]["cpu"] == str(runtime.SHARED_CPU_LOCK)


@pytest.mark.parametrize("kind", ["file", "ancestor"])
@pytest.mark.parametrize("operation", ["slot", "execute"])
def test_cpu_lease_rejects_file_and_parent_alias_before_open(tmp_path,monkeypatch,kind,operation):
    original = tmp_path / "private_target"
    original.mkdir()
    sentinel = original / "cpu_worker.lock"
    sentinel.write_bytes(b"Preserve this fixture file; never acquire a lease through its alias.")
    if kind == "file":
        lease = tmp_path / "cpu_worker.lock"
        lease.symlink_to(sentinel)
    else:
        parent = tmp_path / "alias_state"
        parent.symlink_to(original, target_is_directory=True)
        lease = parent / "cpu_worker.lock"
    before = sentinel.read_bytes()
    monkeypatch.setattr(jobs, "SHARED_CPU_LOCK", lease)
    monkeypatch.setattr(jobs, "get_job", lambda unused: {"status": "queued"})
    monkeypatch.setattr(jobs, "_execute", lambda unused: pytest.fail("An alias cannot run a worker"))
    with pytest.raises(core.StudioError) as error:
        if operation == "slot":
            with jobs.cpu_slot():
                pytest.fail("An alias cannot acquire CPU")
        else:
            jobs.execute("j_test_alias")
    assert error.value.status == 403 and sentinel.read_bytes() == before
    assert lease.is_symlink() if kind == "file" else lease.parent.is_symlink()


def test_hyperframes_prefers_own_runtime_without_mixing_parent_gsap(tmp_path,monkeypatch):
    code=tmp_path/'software';manual=tmp_path/'parent';code.mkdir();manual.mkdir()
    monkeypatch.setattr(hyperframes,'CODE_ROOT',code);monkeypatch.setattr(hyperframes,'MANUAL_ROOT',manual)
    original=hyperframes._dependencies();assert original['packages']==manual/'.estado/herramientas/node_modules'
    cli=code/'.estado/herramientas/node_modules/hyperframes/bin/hyperframes.mjs';cli.parent.mkdir(parents=True);cli.write_text('Fixture readonly loader, never executed')
    own=hyperframes._dependencies()
    assert own['packages']==code/'.estado/herramientas/node_modules'
    assert own['gsap'].is_relative_to(own['packages']) and not own['gsap'].exists()


def test_hyperframes_rejects_package_alias_outside_selected_runtime(tmp_path,monkeypatch):
    code=tmp_path/'software';manual=tmp_path/'parent';code.mkdir();manual.mkdir()
    monkeypatch.setattr(hyperframes,'CODE_ROOT',code);monkeypatch.setattr(hyperframes,'MANUAL_ROOT',manual)
    packages=code/'.estado/herramientas/node_modules';loader=packages/'hyperframes/bin/hyperframes.mjs';loader.parent.mkdir(parents=True);loader.write_text('Never executed')
    outside=tmp_path/'other_gsap';outside.mkdir();(packages/'gsap').symlink_to(outside,target_is_directory=True)
    with pytest.raises(core.StudioError,match='dependencia'):hyperframes._dependencies()

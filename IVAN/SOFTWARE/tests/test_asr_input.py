"""A malformed opt-in must never enqueue ASR or download a model."""
import pytest

from studio import analysis, core, jobs
from test_api import api_workspace, http_server, request
from test_core import sandbox, valid_project


@pytest.mark.parametrize("action", ["analyze", "automate"])
@pytest.mark.parametrize("flag", [None, "false", "true", 0, 1, [], {}])
def test_http_rejects_nonboolean_asr_opt_in_before_queueing(http_server, action, flag):
    project = core.create_project("Isolated invalid ASR opt-in")
    response, unused, body = request(http_server, "POST", f"/api/projects/{project['id']}/{action}",
                                     {"transcribe": flag})
    assert response == 400 and "booleano" in body["error"]
    assert jobs.list_jobs() == []
    assert core.get_project(project["id"])["transcript"]["status"] == "pending"


def test_direct_analysis_rejects_string_false_before_media_io(sandbox, monkeypatch):
    project = valid_project(sandbox)
    monkeypatch.setattr(analysis, "probe", lambda *args: pytest.fail("Invalid opt-in must not start media/model work"))
    monkeypatch.setattr(analysis, "transcribe", lambda *args: pytest.fail("String false must never run ASR"))
    with pytest.raises(core.StudioError, match="booleano"):
        analysis.analyze_project(project, {"transcribe": "false"})
    assert "analysis" not in project


@pytest.mark.parametrize("options", [[], [True], "true", 0])
def test_nonobject_options_cannot_enqueue_or_invoke_analysis(sandbox, options):
    project = valid_project(sandbox)
    with pytest.raises(core.StudioError, match="objeto JSON"):
        jobs.submit(project["id"], "analyze", options)
    with pytest.raises(core.StudioError, match="objeto JSON"):
        analysis.analyze_project(project, options)
    assert jobs.list_jobs() == []

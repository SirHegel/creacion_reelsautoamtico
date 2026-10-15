"""Mobile orientation is retained without exposing arbitrary container tags."""
import copy
import json

import pytest

from studio import analysis
from test_api import api_workspace, fixture_media


@pytest.mark.parametrize("side,tag,expected", [(-90, "90", -90.), (None, "180", 180.), ("invalid", "270", 270.), (True, "45", 45.), (float("nan"), "invalid", None)])
def test_probe_keeps_only_finite_rotation_scalar(api_workspace, fixture_media, monkeypatch, side, tag, expected):
    data = {"streams": [{"codec_type": "video", "width": 160, "height": 284,
        "tags": {"rotate": tag, "private": "do not expose"},
        "side_data_list": [{"rotation": side, "displaymatrix": "omit matrix"}]}],
        "format": {"tags": {"private": "do not expose"}, "filename": "omit absolute path"}}
    monkeypatch.setattr(analysis, "run", lambda *a, **k: json.dumps(copy.deepcopy(data)))
    result = analysis.probe(fixture_media)
    assert result["streams"][0].get("rotation") == expected
    assert "tags" not in result["streams"][0] and "side_data_list" not in result["streams"][0]
    assert "tags" not in result["format"] and "filename" not in result["format"]


def test_real_display_matrix_survives_probe(api_workspace, fixture_media):
    target = api_workspace / ".estado/tmp/mobile_rotated.mp4"
    analysis.run(["ffmpeg", "-v", "error", "-y", "-display_rotation", "90", "-i", str(fixture_media),
                  "-c", "copy", str(target)])
    stream = next(s for s in analysis.probe(target)["streams"] if s["codec_type"] == "video")
    assert abs(stream["rotation"]) == 90
    assert "side_data_list" not in stream and "tags" not in stream

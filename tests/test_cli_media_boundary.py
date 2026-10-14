import json
import os
import subprocess
from pathlib import Path

import pytest

from logic2ableton.cli import main


@pytest.mark.parametrize("mode", ["logic2ableton", "logic2protools"])
@pytest.mark.parametrize("linked_metadata", ["Resources", "Alternatives", "ProjectInformation.plist"])
def test_cli_rejects_linked_metadata_before_following_it(tmp_path, monkeypatch, capsys, mode, linked_metadata):
    project = tmp_path / "Project.logicx"
    project.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    if linked_metadata == "ProjectInformation.plist":
        (project / "Resources").mkdir()
        target = outside / linked_metadata
        target.write_bytes(b"external metadata")
        link = project / "Resources" / linked_metadata
        try:
            link.symlink_to(target)
        except OSError as exc:
            pytest.skip(f"File symlinks unavailable: {exc}")
    else:
        link = project / linked_metadata
        if os.name == "nt":
            subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)],
                           check=True, capture_output=True)
        else:
            link.symlink_to(outside, target_is_directory=True)

    original_stat = Path.stat

    def guarded_stat(path, *args, **kwargs):
        if kwargs.get("follow_symlinks", True):
            assert not (path == link or path.is_relative_to(link) or path.is_relative_to(outside)), (
                f"CLI followed blocked metadata: {path}"
            )
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", guarded_stat)
    assert main([mode, str(project), "--output", str(tmp_path / "output"), "--json-progress"]) == 1
    terminal = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert terminal["stage"] == "error"
    assert terminal["failure_stage"] == "validation"
    assert "linked" in terminal["error"].lower()

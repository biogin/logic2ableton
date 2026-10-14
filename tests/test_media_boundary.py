"""Media links and compact header declarations cannot escape parser bounds."""

import builtins
import io
import os
import struct
import subprocess
from pathlib import Path

import pytest

from logic2ableton import logic_parser
from logic2ableton.protools_import import (
    protools_to_ableton_project, protools_to_logic_project, resolve_protools_media,
)
from logic2ableton.protools_parser import ProToolsRegion, ProToolsSession, ProToolsTrack
from scripts.fixture_builders import build_synthetic_logicx, write_test_wav


class _ExternalAccess(BaseException):
    pass


def _directory_link(link, target):
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                       check=True, capture_output=True)
    else:
        link.symlink_to(target, target_is_directory=True)


def _session(root):
    return ProToolsSession("Session", root / "Session.ptx", 12, 44100, [], [
        ProToolsTrack("Audio", 0, [ProToolsRegion("Clip", 0, 0, 0, 100, 0, "clip.wav")]),
    ], [])


def _forbid_link_access(monkeypatch, link, target):
    """lstat of a link itself is safe; following it or visiting a child is not."""
    original_open, original_io_open = builtins.open, io.open
    original_stat, original_resolve = Path.stat, Path.resolve
    original_iterdir = Path.iterdir

    def forbidden(path):
        path = Path(os.path.abspath(path))
        return path == link or path.is_relative_to(link) or path.is_relative_to(target)

    def guarded_open(path, *args, **kwargs):
        if not isinstance(path, int):
            if forbidden(path):
                raise _ExternalAccess(f"External media opened: {path}")
        return original_open(path, *args, **kwargs)

    def guarded_io_open(path, *args, **kwargs):
        if not isinstance(path, int) and forbidden(path):
            raise _ExternalAccess(f"External media opened: {path}")
        return original_io_open(path, *args, **kwargs)

    def guarded_stat(path, *args, **kwargs):
        if kwargs.get("follow_symlinks", True):
            assert not forbidden(path), f"External media stat: {path}"
        elif path != link:
            assert not forbidden(path), f"External media child inspected: {path}"
        return original_stat(path, *args, **kwargs)

    def guarded_resolve(path, *args, **kwargs):
        assert not forbidden(path), f"External media resolved: {path}"
        return original_resolve(path, *args, **kwargs)

    def guarded_iterdir(path):
        assert not forbidden(path), f"External directory enumerated: {path}"
        return original_iterdir(path)

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(io, "open", guarded_io_open)
    monkeypatch.setattr(Path, "stat", guarded_stat)
    monkeypatch.setattr(Path, "resolve", guarded_resolve)
    monkeypatch.setattr(Path, "iterdir", guarded_iterdir)


def test_protools_audio_directory_link_is_blocked_in_both_import_models(tmp_path, monkeypatch):
    root, outside = tmp_path / "session", tmp_path / "outside"
    root.mkdir()
    write_test_wav(outside / "clip.wav", frames=100)
    link = root / "Audio Files"
    _directory_link(link, outside)
    _forbid_link_access(monkeypatch, link, outside)
    session = _session(root)
    media = resolve_protools_media(session)
    assert media.referenced_files == ["clip.wav"]
    assert media.found_files == [] and media.resolved_files == {}
    for project in (protools_to_logic_project(session), protools_to_ableton_project(session)):
        assert not (project.audio_files if hasattr(project, "audio_files") else project.audio_tracks)
        assert any("Blocked source audio" in warning for warning in project.compatibility_warnings)


def test_protools_file_symlink_is_blocked_in_both_import_models(tmp_path, monkeypatch):
    root, outside = tmp_path / "session", tmp_path / "outside"
    (root / "Audio Files").mkdir(parents=True)
    write_test_wav(outside / "clip.wav", frames=100)
    link = root / "Audio Files" / "clip.wav"
    try:
        link.symlink_to(outside / "clip.wav")
    except OSError as exc:
        pytest.skip(f"File symlinks unavailable: {exc}")
    _forbid_link_access(monkeypatch, link, outside)
    session = _session(root)
    assert resolve_protools_media(session).found_files == []
    assert protools_to_logic_project(session).audio_files == []
    assert protools_to_ableton_project(session).audio_tracks == []


@pytest.mark.parametrize("layout", ["package", "folder", "folder-media"])
def test_logic_audio_directory_link_is_rejected_before_target_access(tmp_path, monkeypatch, layout):
    root = build_synthetic_logicx(tmp_path / "session", project_data=b"", used_audio_files=["clip.wav"])
    outside = tmp_path / "outside"
    write_test_wav(outside / "clip.wav", frames=100)
    link = ((root / "Media" / "Audio Files") if layout == "package" else
            (root.parent / "Audio Files") if layout == "folder" else
            (root.parent / "Media" / "Audio Files"))
    link.parent.mkdir(exist_ok=True)
    _directory_link(link, outside)
    _forbid_link_access(monkeypatch, link, outside)
    project = logic_parser.parse_logic_project(root, smpte_start_seconds=None)
    assert project.audio_files == []
    assert any("Blocked source audio" in warning for warning in project.compatibility_warnings)


def test_logic_file_symlink_is_rejected_before_timestamp_reads(tmp_path, monkeypatch):
    root = build_synthetic_logicx(tmp_path / "session", project_data=b"", used_audio_files=["clip.wav"])
    outside = tmp_path / "outside"
    write_test_wav(outside / "clip.wav", frames=100)
    link = root / "Media" / "Audio Files" / "clip.wav"
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(outside / "clip.wav")
    except OSError as exc:
        pytest.skip(f"File symlinks unavailable: {exc}")
    _forbid_link_access(monkeypatch, link, outside)
    project = logic_parser.parse_logic_project(root)
    assert project.audio_files == []
    assert any("Blocked source audio" in warning for warning in project.compatibility_warnings)


def test_timestamp_membership_is_checked_before_any_file_access(tmp_path, monkeypatch):
    write_test_wav(tmp_path / "excluded.wav", frames=1)

    def unexpected_read(path, *args, **kwargs):
        raise AssertionError(f"Excluded timestamp source read: {path}")

    monkeypatch.setattr(logic_parser, "_get_audio_time_reference", unexpected_read)
    assert logic_parser._resolve_timestamped_audio(tmp_path, contained_filenames=set()) == []


@pytest.mark.parametrize("relative,function", [
    ("Resources", "parse_project_info"),
    ("Resources/ProjectInformation.plist", "parse_project_info"),
    ("Alternatives", "discover_alternatives"),
    ("Alternatives/000", "discover_alternatives"),
    ("Alternatives/000/MetaData.plist", "discover_alternatives"),
    ("Alternatives/000/ProjectData", "discover_alternatives"),
    ("Alternatives/000/MetaData.plist", "parse_metadata"),
    ("Alternatives/000/ProjectData", "_read_project_data"),
    ("Alternatives/000/MetaData.plist", "extract_regions"),
])
def test_logic_metadata_links_are_blocked_before_any_target_access(tmp_path, monkeypatch, relative, function):
    root = build_synthetic_logicx(tmp_path / "session", project_data=b"LOCAL")
    write_test_wav(root / "Media" / "Audio Files" / "clip.wav", frames=1)
    link = root / relative
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / link.name
    is_directory = link.is_dir()
    link.rename(target)
    if is_directory:
        _directory_link(link, target)
    else:
        try:
            link.symlink_to(target)
        except OSError as exc:
            pytest.skip(f"File symlinks unavailable: {exc}")
    _forbid_link_access(monkeypatch, link, outside)
    with pytest.raises(ValueError, match="Blocked project metadata"):
        getattr(logic_parser, function)(root)


def test_metadata_readers_accept_an_explicitly_selected_package_alias(tmp_path):
    actual = build_synthetic_logicx(tmp_path / "actual", project_data=b"LOCAL")
    selected = tmp_path / "selected.logicx"
    _directory_link(selected, actual)
    assert logic_parser.parse_project_info(selected)["name"] == "Synth"
    assert logic_parser.discover_alternatives(selected) == [0]
    assert logic_parser.parse_metadata(selected)["sample_rate"] == 44100
    assert logic_parser._read_project_data(selected) == b"LOCAL"


@pytest.mark.parametrize("layout", ["package", "folder", "folder-media"])
@pytest.mark.parametrize("alias", [False, True])
def test_logic_supported_layouts_and_selected_root_aliases_keep_media(tmp_path, layout, alias):
    root = build_synthetic_logicx(tmp_path / "actual", project_data=b"", used_audio_files=["clip.wav"])
    audio = ((root / "Media" / "Audio Files") if layout == "package" else
             (root.parent / "Audio Files") if layout == "folder" else
             (root.parent / "Media" / "Audio Files"))
    clip = write_test_wav(audio / "clip.wav", frames=100)
    selected = root
    if alias:
        selected_parent = tmp_path / "selected"
        _directory_link(selected_parent, root.parent)
        selected = selected_parent / root.name
    project = logic_parser.parse_logic_project(selected)
    assert [ref.file_path for ref in project.audio_files] == [clip.resolve()]
    assert project.audio_layout == ("package" if layout == "package" else "folder")


@pytest.mark.parametrize("absolute_reference", [False, True])
def test_protools_selected_session_parent_alias_keeps_found_media(tmp_path, absolute_reference):
    root = tmp_path / "actual"
    clip = write_test_wav(root / "Audio Files" / "clip.wav", frames=100)
    alias = tmp_path / "selected"
    _directory_link(alias, root)
    session = _session(alias)
    if absolute_reference:
        session.tracks[0].regions[0].filename = str(clip.resolve())
    assert resolve_protools_media(session).found_files == [session.tracks[0].regions[0].filename]
    assert protools_to_logic_project(session).audio_files[0].file_path == clip.resolve()
    assert protools_to_ableton_project(session).audio_tracks[0].clips[0].source_path == clip.resolve()


class _BoundedRead(io.BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.requests = []

    def read(self, size=-1):
        self.requests.append(size)
        assert 0 <= size <= 256, f"Unbounded chunk read: {size}"
        return super().read(size)

    def close(self):
        pass


@pytest.mark.parametrize("kind", ["fmt", "COMM", "MARK"])
def test_timestamp_header_read_rejects_chunks_beyond_actual_container(monkeypatch, kind):
    if kind == "fmt":
        data = b"RIFF" + struct.pack("<I", 0xFFFFFF00) + b"WAVEfmt " + struct.pack("<I", 0xFFFFFE00) + b"\0" * 8
        function, suffix, expected = logic_parser._get_audio_sample_rate, ".wav", 44100
    else:
        data = b"FORM" + struct.pack(">I", 0xFFFFFF00) + b"AIFF" + kind.encode() + struct.pack(">I", 0xFFFFFE00) + b"\0" * 18
        function, suffix, expected = ((logic_parser._get_audio_sample_rate, ".aiff", 44100) if kind == "COMM"
                                      else (logic_parser._get_aiff_timestamp, ".aiff", (None, 0)))
    stream = _BoundedRead(data)
    monkeypatch.setattr(builtins, "open", lambda *args, **kwargs: stream)
    assert function(Path("source" + suffix)) == expected
    assert all(0 <= size <= 256 for size in stream.requests)
    assert stream.tell() <= len(data)


@pytest.mark.parametrize("kind", ["fmt", "COMM", "MARK"])
def test_large_valid_header_chunks_are_read_in_small_pieces(monkeypatch, kind):
    if kind == "fmt":
        payload = struct.pack("<HHIIHH", 1, 1, 48000, 96000, 2, 16) + b"\0" * 4096
        chunk = b"fmt " + struct.pack("<I", len(payload)) + payload
        data = b"RIFF" + struct.pack("<I", 4 + len(chunk)) + b"WAVE" + chunk
        function, suffix, expected = logic_parser._get_audio_sample_rate, ".wav", 48000
    else:
        if kind == "COMM":
            payload = struct.pack(">hIh", 1, 100, 16) + bytes.fromhex("400ebb80000000000000") + b"\0" * 4096
            function, expected = logic_parser._get_audio_sample_rate, 48000
        else:
            payload = struct.pack(">H", 2)
            for index, position, name in [(1, 0, b"Timestamp: 48000"), (2, 20, b"Start")]:
                payload += struct.pack(">HIB", index, position, len(name)) + name
                if len(name) % 2 == 0:
                    payload += b"\0"
            payload += b"\0" * 4096
            function, expected = logic_parser._get_aiff_timestamp, (48000, 20)
        chunk = kind.encode() + struct.pack(">I", len(payload)) + payload
        data = b"FORM" + struct.pack(">I", 4 + len(chunk)) + b"AIFF" + chunk
        suffix = ".aiff"
    stream = _BoundedRead(data)
    monkeypatch.setattr(builtins, "open", lambda *args, **kwargs: stream)
    assert function(Path("source" + suffix)) == expected
    assert all(0 <= size <= 256 for size in stream.requests)

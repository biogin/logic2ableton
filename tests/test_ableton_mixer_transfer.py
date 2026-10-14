import gzip
import copy
import json
import math
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from logic2ableton.ableton_parser import parse_ableton_project
from logic2ableton.audio import DecodedAudio, read_audio_info, write_pcm_wav
from logic2ableton.cli import main


def _live_set(tmp_path, *, mute=False, volume=1.0, pan=0.0, clip_gain=1.0,
              mixer=True, encoding="pcm", fallback=False, automation=False, midi=False, float_samples=None):
    source = tmp_path / ("source.mp3" if fallback else "source.wav")
    if fallback:
        source.write_bytes(b"undecodable source")
    else:
        frames = struct.pack("<4f", *(float_samples or (1.5, -2.0, 0.25, -0.5))) if encoding == "float" else struct.pack(
            "<4h", 24576, -16384, 8192, -4096
        )
        write_pcm_wav(source, sample_rate=8, channels=1, sample_width=4 if encoding == "float" else 2,
                      frames=frames, encoding=encoding, time_reference_samples=0)
    root = ET.Element("Ableton")
    live = ET.SubElement(root, "LiveSet")
    tracks = ET.SubElement(live, "Tracks")
    track = ET.SubElement(tracks, "MidiTrack" if midi else "AudioTrack")
    ET.SubElement(ET.SubElement(track, "Name"), "EffectiveName", Value="Mixer Track")
    chain = ET.SubElement(track, "DeviceChain")
    if mixer:
        mix = ET.SubElement(chain, "Mixer")
        for index, (name, value) in enumerate((
            ("Speaker", str(not mute).lower()), ("Volume", str(volume)), ("Pan", str(pan)),
        )):
            parameter = ET.SubElement(mix, name)
            ET.SubElement(parameter, "Manual", Value=value)
            ET.SubElement(parameter, "AutomationTarget", Id=str(index))
        if automation:
            envelopes = ET.SubElement(ET.SubElement(track, "AutomationEnvelopes"), "Envelopes")
            envelope = ET.SubElement(envelopes, "AutomationEnvelope")
            ET.SubElement(ET.SubElement(envelope, "EnvelopeTarget"), "PointeeId", Value="1")
            events = ET.SubElement(ET.SubElement(envelope, "Automation"), "Events")
            ET.SubElement(events, "FloatEvent", Time="-63072000", Value=str(volume))
            ET.SubElement(events, "FloatEvent", Time="0.5", Value="0.25")
    sequencer = ET.SubElement(chain, "MainSequencer")
    sample = ET.SubElement(sequencer, "ClipTimeable" if midi else "Sample")
    events = ET.SubElement(ET.SubElement(sample, "ArrangerAutomation"), "Events")
    clip = ET.SubElement(events, "MidiClip" if midi else "AudioClip", Time="0")
    ET.SubElement(clip, "Name", Value="Mixer Clip")
    ET.SubElement(clip, "CurrentStart", Value="0")
    ET.SubElement(clip, "CurrentEnd", Value="1")
    ET.SubElement(clip, "SampleVolume", Value=str(clip_gain))
    if midi:
        key = ET.SubElement(ET.SubElement(clip, "Notes"), "KeyTrack")
        ET.SubElement(key, "MidiKey", Value="60")
        ET.SubElement(key, "MidiNoteEvent", Time="0", Duration="0.5", Velocity="100")
    else:
        file_ref = ET.SubElement(ET.SubElement(clip, "SampleRef"), "FileRef")
        ET.SubElement(file_ref, "RelativePath", Value=source.name)
    path = tmp_path / "Mixer Set.als"
    path.write_bytes(gzip.compress(ET.tostring(root)))
    return path


def _convert(tmp_path, capsys, mode, *, als_path=None, **settings):
    path = als_path or _live_set(tmp_path, **settings)
    assert main([mode, str(path), "--output", str(tmp_path / "output"), "--json-progress"]) == 0
    complete = json.loads(capsys.readouterr().out.splitlines()[-1])
    package = Path(complete["package_path"])
    manifest = json.loads((package / ("timeline_manifest.json" if mode == "ableton2logic" else "manifest.json")).read_text())
    exports = list((package / "Audio Files").rglob("*.wav"))
    if mode == "ableton2logic":
        exports += list((package / "Track Stems").glob("*.wav"))
    return package, manifest, exports


def _samples(path):
    info = read_audio_info(path)
    frames = DecodedAudio(path, info).read_frames(0, info.frame_count)
    code = "f" if info.encoding == "float" else "h"
    return info, struct.unpack(f"<{len(frames) // info.sample_width}{code}", frames)


@pytest.mark.parametrize("mode", ["ableton2logic", "ableton2protools"])
@pytest.mark.parametrize("encoding", ["pcm", "float"])
def test_muted_audio_exports_are_silent(tmp_path, capsys, mode, encoding):
    _, manifest, exports = _convert(tmp_path, capsys, mode, mute=True, encoding=encoding)
    assert len(exports) == (2 if mode == "ableton2logic" else 1)
    for export in exports:
        _, samples = _samples(export)
        assert samples == (0.0, 0.0, 0.0, 0.0)
    assert manifest["tracks"][0]["mixer"]["is_muted"] is True
    assert any("Mixer Track" in warning and "muted" in warning.lower()
               for warning in manifest["compatibility_warnings"])


@pytest.mark.parametrize("mode", ["ableton2logic", "ableton2protools"])
@pytest.mark.parametrize("volume,clip_gain,expected", [
    (0.5, 0.25, (0.09375, -0.0625, 0.03125, -0.015625)),
    (2.0, 2.0, (3.0, -2.0, 1.0, -0.5)),
    (0.0, 1.0, (0.0, 0.0, 0.0, 0.0)),
])
def test_static_track_and_clip_gain_are_baked_without_clipping(tmp_path, capsys, mode, volume, clip_gain, expected):
    _, manifest, exports = _convert(tmp_path, capsys, mode, volume=volume, clip_gain=clip_gain)
    for export in exports:
        info, samples = _samples(export)
        assert info.encoding == "float"
        assert samples == expected
    assert manifest["tracks"][0]["mixer"]["volume_linear"] == volume
    assert manifest["tracks"][0]["clips"][0]["gain_linear"] == clip_gain


@pytest.mark.parametrize("mode", ["ableton2logic", "ableton2protools"])
def test_default_mixer_preserves_pcm_samples(tmp_path, capsys, mode):
    _, _, exports = _convert(tmp_path, capsys, mode, mixer=False)
    for export in exports:
        info, samples = _samples(export)
        assert info.encoding == "pcm"
        assert info.sample_width == 2
        assert samples == (24576, -16384, 8192, -4096)


@pytest.mark.parametrize("mode", ["ableton2logic", "ableton2protools"])
def test_default_mixer_preserves_float_headroom(tmp_path, capsys, mode):
    _, _, exports = _convert(tmp_path, capsys, mode, mixer=False, encoding="float")
    for export in exports:
        info, samples = _samples(export)
        assert info.encoding == "float"
        assert samples == (1.5, -2.0, 0.25, -0.5)


@pytest.mark.parametrize("mode", ["ableton2logic", "ableton2protools"])
def test_raw_source_reference_warns_gain_was_not_rendered(tmp_path, capsys, mode):
    package, manifest, _ = _convert(tmp_path, capsys, mode, volume=0.5, clip_gain=0.25, fallback=True)
    assert len(list((package / "Audio Files").rglob("*.mp3"))) == 1
    assert manifest["tracks"][0]["clips"][0]["export_mode"] == "copied-source"
    assert any("raw source reference" in warning and "gain" in warning for warning in manifest["compatibility_warnings"])


@pytest.mark.parametrize("mode", ["ableton2logic", "ableton2protools"])
def test_muted_undecodable_audio_is_not_copied_as_audible_source(tmp_path, capsys, mode):
    package, manifest, exports = _convert(tmp_path, capsys, mode, mute=True, fallback=True)
    assert not exports
    assert not list((package / "Audio Files").rglob("*.mp3"))
    assert manifest["tracks"][0]["clips"][0]["export_mode"] == "muted-reference-only"


@pytest.mark.parametrize("mode", ["ableton2logic", "ableton2protools"])
def test_pan_and_automation_are_retained_with_affected_track_warnings(tmp_path, capsys, mode):
    _, manifest, _ = _convert(tmp_path, capsys, mode, pan=0.75, automation=True)
    mixer = manifest["tracks"][0]["mixer"]
    assert mixer["pan"] == 0.75
    assert mixer["automation_parameters"] == ["Volume"]
    warnings = manifest["compatibility_warnings"]
    assert any("Mixer Track" in warning and "pan" in warning.lower() for warning in warnings)
    assert any("Mixer Track" in warning and "automation" in warning.lower() and "snapshot" in warning.lower()
               for warning in warnings)


@pytest.mark.parametrize("mode", ["ableton2logic", "ableton2protools"])
def test_muted_midi_retains_notes_and_warns_to_mute_after_import(tmp_path, capsys, mode):
    _, manifest, _ = _convert(tmp_path, capsys, mode, mute=True, midi=True)
    assert manifest["midi_tracks"][0]["note_count"] == 1
    assert manifest["midi_tracks"][0]["mixer"]["is_muted"] is True
    assert any("Mixer Track" in warning and "MIDI" in warning and "mute" in warning.lower()
               for warning in manifest["compatibility_warnings"])


@pytest.mark.parametrize("parameter,value", [("Volume", "nan"), ("Pan", "inf"), ("SampleVolume", "nan")])
def test_nonfinite_mixer_and_clip_gain_are_rejected(tmp_path, parameter, value):
    path = _live_set(tmp_path)
    root = ET.fromstring(gzip.decompress(path.read_bytes()))
    element = root.find(f".//{parameter}" if parameter == "SampleVolume" else f".//Mixer/{parameter}/Manual")
    element.set("Value", value)
    path.write_bytes(gzip.compress(ET.tostring(root)))
    with pytest.raises(ValueError, match="Non-finite"):
        parse_ableton_project(path)


@pytest.mark.parametrize("parameter", ["Volume", "SampleVolume"])
def test_negative_linear_gain_is_rejected(tmp_path, parameter):
    path = _live_set(tmp_path)
    root = ET.fromstring(gzip.decompress(path.read_bytes()))
    element = root.find(f".//{parameter}" if parameter == "SampleVolume" else f".//Mixer/{parameter}/Manual")
    element.set("Value", "-1")
    path.write_bytes(gzip.compress(ET.tostring(root)))
    with pytest.raises(ValueError, match="Negative"):
        parse_ableton_project(path)


@pytest.mark.parametrize("mode", ["ableton2logic", "ableton2protools"])
def test_combined_gain_overflow_fails_before_writing_audio(tmp_path, capsys, mode):
    path = _live_set(tmp_path, volume=1e308, clip_gain=1e308)
    output = tmp_path / "output"
    assert main([mode, str(path), "--output", str(output), "--json-progress"]) == 1
    failed = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert "Non-finite combined audio gain" in failed["error"]
    assert not list(output.rglob("*.wav"))


@pytest.mark.parametrize("mode", ["ableton2logic", "ableton2protools"])
def test_finite_sample_times_gain_overflow_clamps_to_float32_range(tmp_path, capsys, mode):
    _, _, exports = _convert(tmp_path, capsys, mode, volume=1e308, encoding="float")
    maximum = struct.unpack("<f", bytes.fromhex("ffff7f7f"))[0]
    for export in exports:
        info, samples = _samples(export)
        assert info.encoding == "float"
        assert all(math.isfinite(sample) for sample in samples)
        assert samples == (maximum, -maximum, maximum, -maximum)


@pytest.mark.parametrize("mode", ["ableton2logic", "ableton2protools"])
def test_gain_preserves_existing_nonfinite_source_sample_policy(tmp_path, capsys, mode):
    _, _, exports = _convert(tmp_path, capsys, mode, volume=2.0, encoding="float",
                             float_samples=(float("nan"), float("inf"), float("-inf"), 1.5))
    for export in exports:
        _, samples = _samples(export)
        assert math.isnan(samples[0])
        assert samples[1:] == (float("inf"), float("-inf"), 3.0)


def _group_set(tmp_path, groups, *, output="AudioOut/GroupTrack", solo=False):
    path = _live_set(tmp_path)
    root = ET.fromstring(gzip.decompress(path.read_bytes()))
    tracks = root.find("LiveSet/Tracks")
    child = tracks.find("AudioTrack")
    ET.SubElement(child, "TrackGroupId", Value=str(groups[0][0]))
    ET.SubElement(child.find("DeviceChain"), "AudioOutputRouting")
    ET.SubElement(child.find("DeviceChain/AudioOutputRouting"), "Target", Value=output)
    ET.SubElement(child.find("DeviceChain/Mixer"), "SoloSink", Value=str(solo).lower())
    for group_id, parent_id, mute in groups:
        group = ET.SubElement(tracks, "GroupTrack", Id=str(group_id))
        ET.SubElement(ET.SubElement(group, "Name"), "EffectiveName", Value=f"Group {group_id}")
        ET.SubElement(group, "TrackGroupId", Value=str(parent_id))
        chain = ET.SubElement(group, "DeviceChain")
        routing = ET.SubElement(chain, "AudioOutputRouting")
        ET.SubElement(routing, "Target", Value="AudioOut/GroupTrack" if parent_id != -1 else "AudioOut/Main")
        mixer = ET.SubElement(chain, "Mixer")
        ET.SubElement(ET.SubElement(mixer, "Speaker"), "Manual", Value=str(not mute).lower())
        ET.SubElement(ET.SubElement(mixer, "Volume"), "Manual", Value="0.5")
        ET.SubElement(ET.SubElement(mixer, "Pan"), "Manual", Value="0.25")
    path.write_bytes(gzip.compress(ET.tostring(root)))
    return path


@pytest.mark.parametrize("mode", ["ableton2logic", "ableton2protools"])
@pytest.mark.parametrize("groups", [[(42, -1, True)], [(42, 43, False), (43, -1, True)]])
def test_muted_group_ancestors_silence_routed_children(tmp_path, capsys, mode, groups):
    path = _group_set(tmp_path, groups)
    _, manifest, exports = _convert(tmp_path, capsys, mode, als_path=path)
    for export in exports:
        assert _samples(export)[1] == (0.0, 0.0, 0.0, 0.0)
    assert manifest["tracks"][0]["mixer"]["muted_by_groups"] == [str(groups[-1][0])]
    assert manifest["groups"][-1]["name"] == f"Group {groups[-1][0]}"
    assert any("Mixer Track" in warning and "group" in warning.lower() and "muted" in warning.lower()
               for warning in manifest["compatibility_warnings"])


@pytest.mark.parametrize("mode", ["ableton2logic", "ableton2protools"])
def test_unmuted_groups_keep_audio_and_warn_unrendered_group_mixer(tmp_path, capsys, mode):
    path = _group_set(tmp_path, [(42, 43, False), (43, -1, False)], solo=True)
    _, manifest, exports = _convert(tmp_path, capsys, mode, als_path=path)
    for export in exports:
        assert _samples(export)[1] == (24576, -16384, 8192, -4096)
    assert manifest["groups"][0]["mixer"]["volume_linear"] == 0.5
    assert manifest["groups"][0]["mixer"]["pan"] == 0.25
    assert manifest["tracks"][0]["mixer"]["is_soloed"] is True
    assert any("Group 42" in warning and "volume" in warning.lower()
               for warning in manifest["compatibility_warnings"])
    assert any("solo" in warning.lower() and "not applied" in warning.lower()
               for warning in manifest["compatibility_warnings"])


@pytest.mark.parametrize("mode", ["ableton2logic", "ableton2protools"])
@pytest.mark.parametrize("output", ["AudioOut/Main", "AudioOut/External/S0"])
def test_group_membership_with_explicit_bypass_does_not_inherit_mute(tmp_path, capsys, mode, output):
    path = _group_set(tmp_path, [(42, -1, True)], output=output)
    _, manifest, exports = _convert(tmp_path, capsys, mode, als_path=path)
    for export in exports:
        assert _samples(export)[1] == (24576, -16384, 8192, -4096)
    assert manifest["tracks"][0]["output_routing"] == output
    assert manifest["tracks"][0]["mixer"]["muted_by_groups"] == []
    assert any("Mixer Track" in warning and "routing" in warning.lower()
               for warning in manifest["compatibility_warnings"])


@pytest.mark.parametrize("mode", ["ableton2logic", "ableton2protools"])
def test_group_ancestry_cycles_fail_before_export(tmp_path, capsys, mode):
    path = _group_set(tmp_path, [(42, 43, False), (43, 42, True)])
    output = tmp_path / "output"
    assert main([mode, str(path), "--output", str(output), "--json-progress"]) == 1
    failed = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert "group ancestry cycle" in failed["error"].lower()
    assert not list(output.rglob("*.wav"))


@pytest.mark.parametrize("mode", ["ableton2logic", "ableton2protools"])
def test_default_group_routing_inherits_mute_with_inference_warning(tmp_path, capsys, mode):
    path = _group_set(tmp_path, [(42, -1, True)])
    root = ET.fromstring(gzip.decompress(path.read_bytes()))
    routing = root.find(".//AudioTrack/DeviceChain/AudioOutputRouting")
    routing.remove(routing.find("Target"))
    path.write_bytes(gzip.compress(ET.tostring(root)))
    _, manifest, exports = _convert(tmp_path, capsys, mode, als_path=path)
    for export in exports:
        assert _samples(export)[1] == (0.0, 0.0, 0.0, 0.0)
    assert any("Mixer Track" in warning and "inferred" in warning.lower()
               for warning in manifest["compatibility_warnings"])


@pytest.mark.parametrize("mode", ["ableton2logic", "ableton2protools"])
def test_inner_group_main_output_stops_outer_mute_inheritance(tmp_path, capsys, mode):
    path = _group_set(tmp_path, [(42, 43, False), (43, -1, True)])
    root = ET.fromstring(gzip.decompress(path.read_bytes()))
    root.find(".//GroupTrack/DeviceChain/AudioOutputRouting/Target").set("Value", "AudioOut/Main")
    path.write_bytes(gzip.compress(ET.tostring(root)))
    _, manifest, exports = _convert(tmp_path, capsys, mode, als_path=path)
    for export in exports:
        assert _samples(export)[1] == (24576, -16384, 8192, -4096)
    assert manifest["tracks"][0]["mixer"]["muted_by_groups"] == []
    assert any("Group 42" in warning and "bypasses" in warning.lower()
               for warning in manifest["compatibility_warnings"])


@pytest.mark.parametrize("mode", ["ableton2logic", "ableton2protools"])
def test_inherited_group_mute_references_obey_expansion_limit(tmp_path, capsys, monkeypatch, mode):
    import logic2ableton.limits as limits

    path = _group_set(tmp_path, [(42, -1, True)])
    root = ET.fromstring(gzip.decompress(path.read_bytes()))
    tracks = root.find("LiveSet/Tracks")
    child = tracks.find("AudioTrack")
    for _ in range(3):
        tracks.append(copy.deepcopy(child))
    path.write_bytes(gzip.compress(ET.tostring(root)))
    monkeypatch.setattr(limits, "MAX_EXPANDED_ITEMS", 3)
    output = tmp_path / "output"
    assert main([mode, str(path), "--output", str(output), "--json-progress"]) == 1
    failed = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert "Ableton group routing" in failed["error"]
    assert not list(output.rglob("*.wav"))

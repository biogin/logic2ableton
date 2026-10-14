"""Parse Ableton Live `.als` files into an audio-first project model."""

from __future__ import annotations

import gzip
import math
import xml.etree.ElementTree as ET
from pathlib import Path

from logic2ableton.audio import AUDIO_SUFFIXES
from logic2ableton.ableton_metadata import decode_meter, has_global_changes, parameter_events, read_global_parameter
from logic2ableton.limits import ExpansionBudget, read_session_bytes
from logic2ableton.paths import contained_source_path

from logic2ableton.models import (
    AbletonAudioClip,
    AbletonGroup,
    AbletonLocator,
    AbletonMidiClip,
    AbletonMidiNote,
    AbletonMidiTrack,
    AbletonMixerState,
    AbletonProject,
    AbletonTrack,
)


def _read_set_root(als_path: Path) -> ET.Element:
    with als_path.open("rb") as source:
        compressed = source.read(2) == b"\x1f\x8b"
        source.seek(0)
        if compressed:
            with gzip.GzipFile(fileobj=source) as handle:
                data = read_session_bytes(handle, "Decompressed Live Set")
        else:
            data = read_session_bytes(source, "Live Set")
    return ET.fromstring(data)


def _value(element: ET.Element | None, default: str = "") -> str:
    if element is None:
        return default
    if "Value" in element.attrib:
        return element.get("Value", default)
    if element.text:
        return element.text
    return default


def _float_value(element: ET.Element | None, default: float = 0.0) -> float:
    try:
        value = float(_value(element, str(default)))
    except (TypeError, ValueError):
        return default
    if not math.isfinite(value):
        raise ValueError("Non-finite number in Live Set")
    return value


def _float_attr(element: ET.Element | None, name: str, default: float = 0.0) -> float:
    if element is None:
        return default
    try:
        value = float(element.get(name, str(default)))
    except (TypeError, ValueError):
        return default
    if not math.isfinite(value):
        raise ValueError("Non-finite number in Live Set")
    return value


def _bool_value(element: ET.Element | None, default: bool = False) -> bool:
    raw = _value(element, "true" if default else "false").strip().lower()
    if raw in {"true", "1"}:
        return True
    if raw in {"false", "0"}:
        return False
    return default


def _live_set(root: ET.Element) -> ET.Element:
    if root.tag == "LiveSet":
        return root
    if root.tag == "Ableton":
        live_set = root.find("LiveSet")
        if live_set is not None:
            return live_set
    raise ValueError("The file does not contain an Ableton Live Set")


def _project_name(als_path: Path, live_set: ET.Element) -> str:
    candidates = [
        live_set.find("Name"),
        live_set.find(".//MetaData/Name"),
        live_set.find(".//ProjectName"),
    ]
    for candidate in candidates:
        value = _value(candidate)
        if value:
            return value
    return als_path.stem


def _is_within_project(project_root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(project_root)
        return True
    except ValueError:
        return False


def _resolve_source_path(als_path: Path, file_ref: ET.Element | None) -> tuple[Path | None, str | None, str | None]:
    if file_ref is None:
        return None, None, "missing-file-reference"

    absolute_path = _value(file_ref.find("Path"))
    relative_path = _value(file_ref.find("RelativePath"))
    project_root = als_path.parent
    absolute_candidate: Path | None = None
    relative_candidate: Path | None = None
    saw_blocked_candidate = False

    if absolute_path:
        absolute_candidate = contained_source_path(project_root, absolute_path)
        if absolute_candidate is None:
            saw_blocked_candidate = True
            absolute_candidate = None

    if relative_path:
        normalized = relative_path.replace("\\", "/")
        if normalized.startswith("./"):
            normalized = normalized[2:]
        relative_candidate = contained_source_path(project_root, normalized)
        if relative_candidate is None:
            saw_blocked_candidate = True
            relative_candidate = None

    for candidate in (relative_candidate, absolute_candidate):
        if candidate is not None and candidate.is_file():
            if candidate.suffix.lower() not in AUDIO_SUFFIXES:
                return None, relative_path or None, "unsupported-media-type"
            return candidate, relative_path or None, None

    for candidate in (relative_candidate, absolute_candidate):
        if candidate is not None:
            return candidate, relative_path or None, "missing-file-reference"

    if saw_blocked_candidate:
        return None, relative_path or None, "external-media-blocked"
    return None, relative_path or None, "missing-file-reference"


def _parse_locators(live_set: ET.Element) -> list[AbletonLocator]:
    locators: list[AbletonLocator] = []
    locator_groups = [
        live_set.find("Locators/Locators"),
        live_set.find("Locators"),
    ]
    seen: set[tuple[str, float]] = set()
    for group in locator_groups:
        if group is None:
            continue
        for locator in group.findall("Locator"):
            name = _value(locator.find("Name"), "Locator")
            time_beats = _float_value(locator.find("Time"), 0.0)
            key = (name, time_beats)
            if key in seen:
                continue
            seen.add(key)
            locators.append(AbletonLocator(name=name, time_beats=time_beats))
    return locators


def _parse_clip(
    clip: ET.Element, als_path: Path, track_name: str, tempo: float,
    source_cache: dict[tuple[str, str], tuple[Path | None, str | None, str | None]] | None = None,
) -> AbletonAudioClip | None:
    sample_ref = clip.find("SampleRef")
    file_ref = sample_ref.find("FileRef") if sample_ref is not None else None
    source_key = (_value(file_ref.find("Path")), _value(file_ref.find("RelativePath"))) if file_ref is not None else ("", "")
    if source_cache is None:
        source_path, relative_source_path, source_issue = _resolve_source_path(als_path, file_ref)
    else:
        if source_key not in source_cache:
            source_cache[source_key] = _resolve_source_path(als_path, file_ref)
        source_path, relative_source_path, source_issue = source_cache[source_key]

    start_beats = _float_value(clip.find("CurrentStart"), _float_attr(clip, "Time", 0.0))
    end_beats = _float_value(clip.find("CurrentEnd"), start_beats)
    if end_beats <= start_beats:
        duration_samples = _float_value(sample_ref.find("DefaultDuration") if sample_ref is not None else None, 0.0)
        sample_rate = _float_value(sample_ref.find("DefaultSampleRate") if sample_ref is not None else None, 0.0)
        if duration_samples > 0 and sample_rate > 0:
            duration_seconds = duration_samples / sample_rate
            end_beats = start_beats + (duration_seconds / 60.0) * tempo

    clip_name = _value(clip.find("Name"))
    if not clip_name and source_path is not None:
        clip_name = source_path.stem
    if not clip_name:
        clip_name = f"{track_name} clip"

    is_warped = _bool_value(clip.find("IsWarped"))
    source_start = _float_value(clip.find("Loop/LoopStart")) + _float_value(clip.find("Loop/StartRelative"))
    source_in_seconds = source_start
    if is_warped:
        # Warp markers map content beats to source-file seconds. Interpolate
        # the start marker even when subsequent time stretching is approximate.
        markers = sorted({
            (_float_attr(marker, "BeatTime"), _float_attr(marker, "SecTime"))
            for marker in clip.findall("WarpMarkers/WarpMarker")
        })
        source_in_seconds = source_start * 60 / tempo
        if markers:
            source_in_seconds = markers[0][1] + (source_start - markers[0][0]) * 60 / tempo
        for left, right in zip(markers, markers[1:]):
            if right[0] <= left[0]:
                continue
            source_in_seconds = left[1] + (source_start - left[0]) * (right[1] - left[1]) / (right[0] - left[0])
            if source_start <= right[0]:
                break
    source_in_beats = source_start if is_warped else source_in_seconds * tempo / 60
    gain_linear = _float_value(clip.find("SampleVolume"), 1.0)
    if gain_linear < 0:
        raise ValueError("Negative clip gain in Live Set")

    return AbletonAudioClip(
        clip_name=clip_name,
        track_name=track_name,
        source_path=source_path,
        relative_source_path=relative_source_path,
        start_beats=start_beats,
        end_beats=end_beats,
        source_in_beats=source_in_beats,
        source_in_seconds=max(0.0, source_in_seconds),
        is_warped=is_warped,
        is_disabled=_bool_value(clip.find("Disabled")),
        source_issue=source_issue,
        gain_linear=gain_linear,
    )


def _parse_mixer(track: ET.Element) -> AbletonMixerState:
    mixer = AbletonMixerState(
        volume_linear=_float_value(track.find("DeviceChain/Mixer/Volume/Manual"), 1.0),
        pan=_float_value(track.find("DeviceChain/Mixer/Pan/Manual"), 0.0),
        is_muted=not _bool_value(track.find("DeviceChain/Mixer/Speaker/Manual"), True),
        is_soloed=_bool_value(track.find("DeviceChain/Mixer/SoloSink")),
    )
    if mixer.volume_linear < 0:
        raise ValueError("Negative volume in Live Set")
    for name, manual in (("Speaker", float(not mixer.is_muted)), ("Volume", mixer.volume_linear), ("Pan", mixer.pan)):
        parameter = track.find(f"DeviceChain/Mixer/{name}")
        if parameter is None:
            continue
        events = parameter_events(track, parameter)
        if any((float(_bool_value(event)) if name == "Speaker" else _float_attr(event, "Value", manual)) != manual
               for event in events):
            mixer.automation_parameters.append(name)
    return mixer


def _group_id(track: ET.Element) -> str | None:
    value = _value(track.find("TrackGroupId"), "-1")
    return None if value == "-1" else value


def _parse_groups(live_set: ET.Element) -> list[AbletonGroup]:
    groups = [AbletonGroup(
        track_id=track.get("Id", ""),
        name=_value(track.find("Name/EffectiveName"), "Group Track"),
        parent_id=_group_id(track),
        output_routing=_value(track.find("DeviceChain/AudioOutputRouting/Target")),
        mixer=_parse_mixer(track),
    ) for track in live_set.findall(".//Tracks/GroupTrack")]
    by_id = {group.track_id: group for group in groups}
    if "" in by_id or len(by_id) != len(groups):
        raise ValueError("Missing or duplicate Live group track ID")
    checked: set[str] = set()
    for group in groups:
        chain: set[str] = set()
        parent = group.track_id
        while parent in by_id and parent not in checked:
            if parent in chain:
                raise ValueError("Live group ancestry cycle")
            chain.add(parent)
            parent = by_id[parent].parent_id
        checked.update(chain)
    return groups


def _inherit_group_mutes(project: AbletonProject) -> None:
    groups = {group.track_id: group for group in project.groups}
    budget = ExpansionBudget("Ableton group routing")
    budget.add_items(len(groups))
    for track in [*project.audio_tracks, *project.midi_tracks]:
        parent, routing = track.group_id, track.output_routing
        while parent in groups and routing in ("", "AudioOut/GroupTrack"):
            budget.reserve_work(1)
            group = groups[parent]
            if group.mixer.is_muted:
                budget.add_items()
                track.mixer.muted_by_groups.append(group.track_id)
            parent, routing = group.parent_id, group.output_routing


def _parse_audio_tracks(live_set: ET.Element, als_path: Path, tempo: float) -> list[AbletonTrack]:
    tracks: list[AbletonTrack] = []
    source_cache: dict[tuple[str, str], tuple[Path | None, str | None, str | None]] = {}
    for track in live_set.findall(".//Tracks/AudioTrack"):
        track_name = _value(track.find("Name/EffectiveName"), "Audio Track")
        clips: list[AbletonAudioClip] = []
        for clip in track.findall(".//MainSequencer/Sample/ArrangerAutomation/Events/AudioClip"):
            parsed = _parse_clip(clip, als_path, track_name, tempo, source_cache)
            if parsed is not None and not parsed.is_disabled:
                clips.append(parsed)
        tracks.append(AbletonTrack(
            name=track_name, clips=clips, mixer=_parse_mixer(track), group_id=_group_id(track),
            output_routing=_value(track.find("DeviceChain/AudioOutputRouting/Target")),
        ))
    return tracks


_BEAT_EPSILON = 1e-9


def _render_clip_notes(
    events: list[tuple[int, float, float, int]],
    *,
    clip_start: float,
    clip_end: float,
    loop_start: float,
    loop_end: float,
    start_relative: float,
    loop_on: bool,
    budget: ExpansionBudget | None = None,
) -> list[AbletonMidiNote]:
    """Place clip-content notes on the arrangement the way Live plays them.

    Verified against Live 12.4.3 by consolidating clips with known notes:
    playback starts at loop_start + start_relative and runs to loop_end, then
    wraps to loop_start until the clip's arrangement length is used up (Live
    wraps even when the loop switch is off). Notes are cut at the loop end and
    at the clip end. With the loop switch on, notes that start outside the loop
    brace never sound; otherwise a note already sounding at the start marker
    plays from the clip start for its remaining length.
    """
    if not events:
        return []
    budget = budget or ExpansionBudget("Ableton MIDI")
    clip_length = clip_end - clip_start
    loop_length = loop_end - loop_start
    if not math.isfinite(clip_length) or not math.isfinite(loop_length):
        raise ValueError("Non-finite MIDI clip or loop length in Live Set")
    if clip_length <= _BEAT_EPSILON or loop_length <= _BEAT_EPSILON:
        return []
    play_start = loop_start + start_relative
    if play_start < loop_start or play_start >= loop_end:
        play_start = loop_start
    if loop_on:
        events = [event for event in events if loop_start <= event[1] < loop_end]
    if not events:
        return []
    budget.reserve_work((clip_length / loop_length + 2) * len(events))

    notes: list[AbletonMidiNote] = []
    elapsed = 0.0
    window_start = play_start
    first_pass = True
    while elapsed < clip_length - _BEAT_EPSILON:
        window_length = min(loop_end - window_start, clip_length - elapsed)
        window_end = window_start + window_length
        for pitch, time, duration, velocity in events:
            note_end = time + duration
            if first_pass and time < window_start < note_end:
                onset = window_start
            elif window_start <= time < window_end - _BEAT_EPSILON:
                onset = time
            else:
                continue
            played = min(note_end, window_end) - onset
            if played <= _BEAT_EPSILON:
                continue
            budget.add_items()
            notes.append(
                AbletonMidiNote(
                    pitch=pitch,
                    start_beats=clip_start + elapsed + (onset - window_start),
                    duration_beats=played,
                    velocity=velocity,
                )
            )
        elapsed += window_length
        first_pass = False
        window_start = loop_start
    return notes


def _parse_midi_clip(
    clip: ET.Element, track_name: str, tempo: float, budget: ExpansionBudget | None = None,
) -> AbletonMidiClip | None:
    if _bool_value(clip.find("Disabled")):
        return None
    start_beats = _float_value(clip.find("CurrentStart"), _float_attr(clip, "Time", 0.0))
    end_beats = _float_value(clip.find("CurrentEnd"), start_beats)

    clip_name = _value(clip.find("Name")) or f"{track_name} clip"
    is_disabled = _bool_value(clip.find("Disabled"))
    is_looping = _bool_value(clip.find("Loop/LoopOn"))
    # Notes are timed relative to the clip's content origin (1.1.1 == 0 beats);
    # the loop brace and start marker decide which of them play and where.
    events: list[tuple[int, float, float, int]] = []
    for key_track in clip.findall(".//KeyTrack"):
        pitch = int(_float_value(key_track.find("MidiKey"), -1.0))
        if pitch < 0 or pitch > 127:
            continue
        for event in key_track.findall(".//MidiNoteEvent"):
            if event.get("IsEnabled", "true").strip().lower() in {"false", "0"}:
                continue
            note_time = _float_attr(event, "Time", 0.0)
            duration = _float_attr(event, "Duration", 0.0)
            velocity = int(round(_float_attr(event, "Velocity", 100.0)))
            if duration <= 0:
                continue
            events.append((pitch, note_time, duration, max(1, min(127, velocity))))

    notes = _render_clip_notes(
        events,
        clip_start=start_beats,
        clip_end=max(end_beats, start_beats),
        loop_start=_float_value(clip.find("Loop/LoopStart"), 0.0),
        loop_end=_float_value(clip.find("Loop/LoopEnd"), max(end_beats, start_beats) - start_beats),
        start_relative=_float_value(clip.find("Loop/StartRelative"), 0.0),
        loop_on=is_looping,
        budget=budget,
    )
    notes = [note for note in notes if note.start_beats >= 0]
    notes.sort(key=lambda note: (note.start_beats, note.pitch))
    return AbletonMidiClip(
        clip_name=clip_name,
        track_name=track_name,
        start_beats=start_beats,
        end_beats=end_beats if end_beats > start_beats else start_beats,
        notes=notes,
        is_disabled=is_disabled,
        is_looping=is_looping,
    )


def _parse_midi_tracks(live_set: ET.Element, tempo: float) -> list[AbletonMidiTrack]:
    tracks: list[AbletonMidiTrack] = []
    budget = ExpansionBudget("Ableton MIDI")
    for track in live_set.findall(".//Tracks/MidiTrack"):
        track_name = _value(track.find("Name/EffectiveName"), "MIDI Track")
        clips: list[AbletonMidiClip] = []
        for clip in track.findall(".//ArrangerAutomation/Events/MidiClip"):
            parsed = _parse_midi_clip(clip, track_name, tempo, budget)
            if parsed is not None and not parsed.is_disabled:
                clips.append(parsed)
        tracks.append(AbletonMidiTrack(
            name=track_name, clips=clips, mixer=_parse_mixer(track), group_id=_group_id(track),
            output_routing=_value(track.find("DeviceChain/AudioOutputRouting/Target")),
        ))
    return tracks


def _build_compatibility_warnings(project: AbletonProject) -> list[str]:
    warnings: list[str] = []
    clips = project.clips
    groups = {group.track_id: group for group in project.groups}
    for track in [*project.audio_tracks, *project.midi_tracks]:
        midi = isinstance(track, AbletonMidiTrack)
        if track.mixer.is_muted or track.mixer.muted_by_groups:
            group_names = ", ".join(groups[group_id].name for group_id in track.mixer.muted_by_groups)
            warnings.append(
                f"Track '{track.name}' is muted"
                + (f" by group(s) {group_names}. " if group_names else ". ")
                + ("Its MIDI file retains notes without mute; mute the destination track after import."
                   if midi else "Rendered audio is silent; undecodable source files are not copied.")
            )
        if track.group_id is not None:
            if track.group_id not in groups:
                warnings.append(f"Track '{track.name}' references missing group {track.group_id}; group mute could not be resolved.")
            elif track.output_routing not in ("", "AudioOut/GroupTrack"):
                warnings.append(
                    f"Track '{track.name}' routing '{track.output_routing}' bypasses its parent group mixer; recreate routing after import."
                )
            elif not track.output_routing:
                warnings.append(f"Track '{track.name}' has no saved output routing; group output is inferred from membership. Verify its routing in Live.")
        if track.output_routing not in ("", "AudioOut/Main", "AudioOut/Master", "AudioOut/GroupTrack"):
            warnings.append(f"Track '{track.name}' output routing '{track.output_routing}' is retained in the manifest but is not rebuilt.")
        if track.mixer.pan != 0:
            warnings.append(
                f"Track '{track.name}' has pan {track.mixer.pan:g}; pan is retained in the manifest "
                "and must be recreated in the destination DAW."
            )
        if midi and track.mixer.volume_linear != 1:
            warnings.append(
                f"MIDI track '{track.name}' has volume {track.mixer.volume_linear:g}; "
                "the MIDI file carries notes without audio gain. Recreate its volume after import."
            )
        if track.mixer.automation_parameters:
            warnings.append(
                f"Track '{track.name}' has mixer automation ({', '.join(track.mixer.automation_parameters)}). "
                "Only the saved Manual snapshot is used; recreate automation in the destination DAW."
            )
    for group in project.groups:
        if group.mixer.volume_linear != 1 or group.mixer.pan != 0 or group.mixer.automation_parameters:
            warnings.append(
                f"Group '{group.name}' volume, pan and mixer automation are retained in the manifest but not rendered; "
                "only its saved mute is applied to children routed through it. Recreate the group mixer in the destination DAW."
            )
        if group.parent_id is not None and group.output_routing not in ("", "AudioOut/GroupTrack"):
            warnings.append(f"Group '{group.name}' routing '{group.output_routing}' bypasses its parent group mixer; recreate routing after import.")
        elif group.parent_id is not None and not group.output_routing:
            warnings.append(f"Group '{group.name}' has no saved output routing; parent group output is inferred from membership. Verify its routing in Live.")
        if group.parent_id is not None and group.parent_id not in groups:
            warnings.append(f"Group '{group.name}' references missing parent group {group.parent_id}; ancestor mute could not be resolved.")
        if group.output_routing not in ("", "AudioOut/Main", "AudioOut/Master", "AudioOut/GroupTrack"):
            warnings.append(f"Group '{group.name}' output routing '{group.output_routing}' is retained in the manifest but is not rebuilt.")
    soloed = [track.name for track in [*project.audio_tracks, *project.midi_tracks, *project.groups] if track.mixer.is_soloed]
    if soloed:
        warnings.append(
            f"Solo state ({', '.join(soloed)}) is retained in the manifest but not applied; "
            "exports can include tracks silenced by solo in Live. Recreate solo state after import."
        )
    if not project.audio_tracks and not project.midi_tracks:
        warnings.append("No Ableton audio or MIDI tracks were found in the Live Set.")
        return warnings

    missing_files = [clip for clip in clips if clip.source_issue == "missing-file-reference"]
    if missing_files:
        examples = ", ".join(clip.clip_name for clip in missing_files[:5])
        if len(missing_files) > 5:
            examples += ", ..."
        warnings.append(
            f"{len(missing_files)} clip(s) referenced audio that could not be resolved from the Live Set: {examples}"
        )

    blocked_external = [clip for clip in clips if clip.source_issue == "external-media-blocked"]
    if blocked_external:
        examples = ", ".join(clip.clip_name for clip in blocked_external[:5])
        if len(blocked_external) > 5:
            examples += ", ..."
        warnings.append(
            f"{len(blocked_external)} clip(s) referenced audio outside the Ableton project folder and were blocked for safety: {examples}"
        )

    unsupported = [clip for clip in clips if clip.source_issue == "unsupported-media-type"]
    if unsupported:
        warnings.append(f"{len(unsupported)} clip(s) referenced unsupported media types and were not copied.")

    warped = [clip for clip in clips if clip.is_warped]
    if warped:
        examples = ", ".join(clip.clip_name for clip in warped[:5])
        if len(warped) > 5:
            examples += ", ..."
        warnings.append(
            f"{len(warped)} clip(s) use Ableton warping; source start offsets are preserved, but time stretching and loop playback require review in the destination DAW: {examples}"
        )

    if not clips and not project.midi_tracks:
        warnings.append("No arrangement audio clips were found in the Live Set.")

    return warnings


def parse_ableton_project(als_path: Path) -> AbletonProject:
    """Parse an Ableton Live Set into a transfer-friendly project model."""
    als_path = Path(als_path)
    root = _read_set_root(als_path)
    live_set = _live_set(root)

    tempo = read_global_parameter(live_set, "Tempo", 120.0)
    if not math.isfinite(tempo) or tempo <= 0:
        raise ValueError("The Live Set has an invalid tempo")
    time_sig = live_set.find(".//Transport//TimeSignatures/RemoteableTimeSignature")
    numerator, denominator = decode_meter(int(read_global_parameter(live_set, "TimeSignature", 201)))
    if time_sig is not None and live_set.find("MainTrack") is None and live_set.find("MasterTrack") is None:
        numerator = int(_float_value(time_sig.find("Numerator"), 4))
        denominator = int(_float_value(time_sig.find("Denominator"), 4))
    project = AbletonProject(
        name=_project_name(als_path, live_set),
        tempo=tempo,
        time_sig_numerator=numerator,
        time_sig_denominator=denominator,
        audio_tracks=_parse_audio_tracks(live_set, als_path, tempo),
        locators=_parse_locators(live_set),
        midi_tracks=_parse_midi_tracks(live_set, tempo),
        groups=_parse_groups(live_set),
    )
    _inherit_group_mutes(project)
    project.compatibility_warnings = _build_compatibility_warnings(project)
    for parameter in ("Tempo", "TimeSignature"):
        if has_global_changes(live_set, parameter):
            project.compatibility_warnings.append(
                f"Arrangement {parameter} changes are not transferred; only the value at project start is used."
            )
    return project

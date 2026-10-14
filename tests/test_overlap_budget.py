"""Overlap subtraction preserves precedence without quadratic tail scans."""

import random
from pathlib import Path

import pytest

from logic2ableton import limits, logic_parser
from logic2ableton.limits import ExpansionBudget
from logic2ableton.models import AudioFileRef
from logic2ableton.timeline import TempoMap
from scripts.fixture_builders import build_logic_arrangement_project_data, build_synthetic_logicx, write_test_wav


RATE = 48000
SAMPLES_PER_BEAT = RATE // 2


def _ref(index, start, end, track="Audio"):
    return AudioFileRef(f"{index}.wav", track, 0, False, "", Path(f"{index}.wav"),
                        content_offset_samples=100, content_duration_samples=round((end - start) * SAMPLES_PER_BEAT),
                        clip_name=str(index), start_beats=start)


@pytest.fixture(autouse=True)
def _sample_rate(monkeypatch):
    monkeypatch.setattr(logic_parser, "_get_audio_sample_rate", lambda path: RATE)


def _legacy_pieces(refs):
    """Small oracle for the former region-by-region subtraction semantics."""
    output = []
    for index, ref in enumerate(refs):
        start, end = ref.start_beats, ref.start_beats + ref.content_duration_samples / SAMPLES_PER_BEAT
        pieces = [(start, end)]
        ordered = sorted((i for i, r in enumerate(refs) if r.track_name == ref.track_name),
                         key=lambda i: (refs[i].start_beats, i))
        for later in ordered[ordered.index(index) + 1:]:
            other = refs[later]
            low, high = other.start_beats, other.start_beats + other.content_duration_samples / SAMPLES_PER_BEAT
            if high <= low or low >= end - 1e-9:
                continue
            remaining = []
            for left, right in pieces:
                if high <= left or low >= right:
                    remaining.append((left, right))
                    continue
                if low > left:
                    remaining.append((left, low))
                if high < right:
                    remaining.append((high, right))
            pieces = remaining
        unchanged = pieces == [(start, end)]
        for left, right in pieces:
            if unchanged or right - left >= logic_parser._OVERLAP_REPORT_BEATS:
                output.append((ref.filename, left, ref.content_offset_samples + round((left - start) * SAMPLES_PER_BEAT),
                               ref.content_duration_samples if unchanged else int((right - left) * SAMPLES_PER_BEAT + 1e-6)))
    return output


def test_overlap_precedence_and_fragments_match_existing_subtraction():
    rng = random.Random(913)
    cases = [
        [_ref(0, 0, 20), _ref(1, 2, 4), _ref(2, 6, 8)],
        [_ref(0, 0, 10), _ref(1, 0, 5), _ref(2, 1, 8)],
        [_ref(0, 0, 10), _ref(1, 10 - 5e-10, 11)],
        [_ref(0, 0, 0), _ref(1, 0, 2)],
    ]
    for _ in range(40):
        cases.append([_ref(i, start := rng.randrange(20) / 2, start + rng.randrange(20) / 2,
                           "Audio" if rng.randrange(2) else "Other") for i in range(30)])
    for refs in cases:
        result = logic_parser._cut_overlapping_audio(refs, tempo_map=TempoMap(120, []), warnings=[])
        assert [(ref.filename, ref.start_beats, ref.content_offset_samples, ref.content_duration_samples)
                for ref in result] == _legacy_pieces(refs)


@pytest.mark.parametrize("count", [2000, 4000, 8000, 44089])
def test_disjoint_loop_scan_has_linear_budgeted_work(count):
    refs = [_ref(i, i * 2, i * 2 + 2) for i in range(count)]
    budget = ExpansionBudget("Overlap test")
    result = logic_parser._cut_overlapping_audio(refs, tempo_map=TempoMap(120, []), warnings=[], budget=budget)
    assert result == refs
    assert count <= budget.work <= count * 4
    assert budget.items == count


def test_overlap_work_limit_fails_before_processing_unbounded_regions(monkeypatch):
    refs = [_ref(i, i, i + 100) for i in range(20)]
    monkeypatch.setattr(limits, "MAX_EXPANSION_WORK", 10)
    with pytest.raises(ValueError, match="loop expansion limit"):
        logic_parser._cut_overlapping_audio(refs, tempo_map=TempoMap(120, []), warnings=[])


def test_overlap_sort_comparisons_share_the_work_budget(monkeypatch):
    refs = [_ref(i, i, i + 1) for i in range(20)]
    monkeypatch.setattr(limits, "MAX_EXPANSION_WORK", 25)
    budget = ExpansionBudget("Overlap sorting")
    with pytest.raises(ValueError, match="loop expansion limit"):
        logic_parser._cut_overlapping_audio(refs, tempo_map=TempoMap(120, []), warnings=[], budget=budget)
    assert budget.work == 25 and budget.items == 0


def test_compact_single_sample_loop_parses_without_quadratic_overlap_work(tmp_path, monkeypatch):
    data = build_logic_arrangement_project_data(
        tracks={1: "Audio"}, sequences=[], midi_regions=[], audio_files={10: "clip.wav"},
        audio_regions=[{"file": 10, "index": 0, "name": "Short", "offset": 0, "length": 1}],
        audio_placements=[{"bar": 1, "track": 1, "file": 10, "loop_beats": 2}],
    )
    root = build_synthetic_logicx(tmp_path, project_data=data)
    write_test_wav(root / "Media" / "Audio Files" / "clip.wav", frames=1)
    original = logic_parser._cut_overlapping_audio
    measured = []

    def cut(refs, **kwargs):
        budget = ExpansionBudget("Compact loop overlap")
        result = original(refs, budget=budget, **kwargs)
        measured.append((len(refs), budget.work, budget.items))
        return result

    monkeypatch.setattr(logic_parser, "_cut_overlapping_audio", cut)
    # The fixture's actual rate controls repetition count, like the real parser.
    monkeypatch.setattr(logic_parser, "_get_audio_sample_rate", lambda path, **kwargs: 44100)
    project = logic_parser.parse_logic_project(root)
    assert len(project.audio_files) == 44089
    assert len(measured) == 1
    count, work, items = measured[0]
    assert count == items == 44089
    assert count <= work <= count * 4


def test_overlap_fragment_limit_is_checked_before_allocating_output(monkeypatch):
    refs = [_ref(0, 0, 10), _ref(1, 2, 3), _ref(2, 5, 6)]
    monkeypatch.setattr(limits, "MAX_EXPANDED_ITEMS", 4)
    allocated = []
    original = logic_parser.replace

    def replace(*args, **kwargs):
        allocated.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(logic_parser, "replace", replace)
    with pytest.raises(ValueError, match="loop expansion limit"):
        logic_parser._cut_overlapping_audio(refs, tempo_map=TempoMap(120, []), warnings=[])
    assert allocated == []


def test_overlap_warning_retains_first_later_region_and_track_order():
    refs = [_ref(0, 0, 10), _ref(1, 2, 8), _ref(2, 3, 4), _ref(3, 0, 10, "Other"), _ref(4, 1, 2, "Other")]
    warnings = []
    logic_parser._cut_overlapping_audio(refs, tempo_map=TempoMap(120, []), warnings=warnings)
    assert warnings == [
        "3 audio region(s) overlap a later region on the same track. A track plays one clip at a "
        "time, so the later region was kept whole and the earlier one cut around it; compare these with "
        "Logic: Audio: 0 under 1, Audio: 1 under 2, Other: 3 under 4"
    ]

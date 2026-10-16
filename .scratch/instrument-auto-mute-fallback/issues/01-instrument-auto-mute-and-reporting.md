# 01: Auto-mute a track when its instrument plugin can't transplant, with accurate fallback reporting

**What to build:** Converting a project where a channel strip's instrument plugin (`aumu` only, never `aumf`) can't transplant produces an Ableton track that's cleanly muted — MIDI preserved untouched — with the conversion report stating why, worded distinctly from a track already muted in the source Logic project. A channel strip with only a failing *effect* plugin (`aufx`/`aumf`) stays unmuted — it already does today, since a non-transplanted effect is simply never inserted — but the report must now name the dropped effect and confirm the rest of the chain is intact.

**Blocked by:** None (can start immediately)

**Status:** resolved

- [x] A channel strip whose instrument plugin's transplant outcome is anything other than "transplanted" results in its destination Ableton track being muted, via the same mute mechanism the existing mixer-state code already writes.
- [x] The MIDI clip/notes on an auto-muted track are completely unchanged — only the mute state differs from what would otherwise be generated.
- [x] A channel strip whose instrument plugin transplants successfully is never auto-muted.
- [x] A channel strip with no instrument slot, or whose only failing plugin is an effect (`aufx`/`aumf`), is never auto-muted — the track plays with that effect simply absent from the chain, same as today.
- [x] The conversion report states, per track, when it was auto-muted due to a missing instrument (naming the plugin), in wording distinct from a track that was already muted in the source Logic project with nothing missing.
- [x] The conversion report states, per dropped effect instance, that it was dropped and that the rest of the chain is intact — extending the existing per-instance transplant-outcome reporting, not a new mechanism.
- [x] Tests cover all four cases from the spec's Testing Decisions: instrument fails (mute + correct report wording), instrument succeeds (no mute), effect-only fails (no mute, report names the dropped effect), and a track already muted in Logic with nothing missing (report attributes the mute to the source project, not to auto-mute).

## Answer

**Implemented.** New shared decision function `missing_instrument()` in `au_transplant.py` (alongside `decide_transplant()`, same pattern from ticket 03 of the `au-plugin-state-transplant` spec): given a channel strip's plugin list, returns the `aumu`-typed instance if one exists and didn't transplant, else `None`. Both the writer (`ableton_generator.py`) and the report (`report.py`) call this same function independently, so they can never disagree about which tracks are auto-muted — same "single source of truth" discipline as the rest of this codebase's transplant-decision logic.

- **Writer**: a new `_force_mute()` helper (next to `_set_mixer_state`) sets the same `Speaker/Manual` field `_set_mixer_state` already writes, called after it so auto-mute is never overridden by a Logic mixer state that happened to read as unmuted. Wired into both the audio-track and MIDI-track generation loops, right after plugin transplant for that track.
- **Report**: a new `AUTO-MUTED TRACKS` section (only present when non-empty) lists each affected track and its missing instrument, with explicit wording that these are converter-muted, not Logic-muted. The existing per-instance `PLUGINS FOUND` line for any non-transplanted plugin now also states the consequence — "track auto-muted, see AUTO-MUTED TRACKS above" for a missing instrument, "rest of the chain plays without it" for a dropped effect — extending ticket 03's existing per-instance outcome reporting rather than introducing a new mechanism, exactly as scoped.

**Verified against real production data, not just synthetic fixtures**: ran the actual converter against a real multi-track Logic project with `installed_au_components` simulated as empty. Two real instrument-bearing tracks (`Analog s6 bass` using a Native Instruments instrument, ` - Init - ` using Xfer Serum) correctly auto-muted in the generated `.als` (`Speaker/Manual` = `"false"`), with the report's `AUTO-MUTED TRACKS` section correctly naming both. A normal run against the same project with real installed plugins produces no `AUTO-MUTED TRACKS` section at all — confirms no false positives when nothing is actually missing.

Tests: 4 new cases in `tests/test_au_transplant.py` (`missing_instrument`'s four branches: fails/succeeds/no-instrument/aumf-ignored), 4 new generator-level cases in `tests/test_ableton_generator.py` (auto-mute, no-mute-on-success, no-mute-on-effect-only-failure, MIDI performance preserved), and 3 new cases in `tests/test_report.py` (auto-muted section content, no section when nothing's missing, Logic-mute vs. auto-mute distinction) — covering all four of the spec's Testing Decisions fixtures. Full suite: 686 passed, 61 skipped, same 2 pre-existing unrelated VST3-scanner failures as before this work. `ruff check` clean.

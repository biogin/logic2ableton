# 02 - Wire existing automation data into the Ableton writer

Status: resolved
Type: task

## What

`logic2ableton` currently does not transfer fader/pan (or any other) automation — confirmed gap, per its own README.

The decoder already knows where this data lives: per-track automation is stored as MIDI placements of an `MSeq` named `*Automation` (see `logic_project_data.py`'s format notes). It's parsed as a location, just never read into the semantic model or written out.

## Scope

1. In `logic_parser.py`, read the `*Automation` MSeq placements per track into the `LogicProject` model (`models.py`) as a structured automation-curve representation (parameter id/name, time-value breakpoints).
2. In `ableton_generator.py`, write that model data into Ableton's native automation XML structure (per-device/per-parameter envelope, keyed to the matching Ableton track/device after instrument/plugin mapping from issues 03/04 has run).
3. Tempo is already handled (tempo-as-automation + warp markers per the existing code) — don't touch that path; this is specifically about track-level fader/pan/parameter automation.

## Out of scope here

- Automation on a plugin parameter that only exists post-mapping (e.g. a Logic stock plugin parameter mapped to a different Ableton stock plugin parameter) — that depends on issue 03's mapping table existing first for the parameter name/id correspondence. Wire the generic curve-transfer mechanism here; parameter-identity mapping across different plugins is issue 03/04's concern.

## Answer

**Implemented for track-level Volume and Pan.** The byte format wasn't actually known in advance despite the issue's framing ("just never read into the semantic model") — only the automation *container's location* was documented. The point/value/flag byte layout had to be reverse-engineered from scratch against a controlled ground-truth project (known dB/pan values, placed by hand in Logic, re-read and diffed) plus cross-checked against ~1,450 real automation containers across the project owner's own projects. See the conversation this issue was built in for the full process.

**What was found and implemented:**
- A 16-byte record (status 0x50) per breakpoint: value at +8 (same 24-bit-fraction fader-scale encoding as a channel strip's own fader — reuses the existing `_UNITY_FADER`/`volume_db` fader law, confirmed to match exactly), parameter id at +12 (7 volume, 10 pan), and a kind flag at +15 whose 0x40 bit marks a point Logic *baked* by resampling a ramp (a single hand-drawn two-node ramp produced over 1,000 interpolated samples) — never set on an authored node. Filtering on that bit means only the real authored breakpoints are kept; the dense resampling is discarded entirely, no curve-simplification algorithm needed.
- Decoder: `logic_project_data._automation_points()`, wired into `_sequences()` for `*Automation`-named MSeq containers.
- Parser: `logic_parser._arrangement_automation()` resolves each automation placement to its track, converts ticks to absolute beats, converts raw fader-scale values to dB (volume) and -1..1 (pan) using the same formulas as the existing mixer-fader code, and reports (not silently drops) any point using a parameter id it doesn't recognize.
- Writer: `ableton_metadata.set_track_automation()` (and `_events_element`'s create-if-missing logic) writes one `FloatEvent` per authored breakpoint onto the track's Volume/Pan `AutomationEnvelope` — these don't pre-exist on a freshly cloned track (Live only writes one once something is actually automated), so this builds the envelope from scratch rather than assuming `set_tempo_automation`'s "always already there" case holds for regular tracks too.
- Report: new `TRACK AUTOMATION` section lists point counts per track; the stale `NOT TRANSFERRED: Automation data (requires deeper binary parsing)` line is corrected.

**Where Logic's curve shape doesn't map exactly**: a ramp between two authored nodes interpolates *linearly in Logic's own fader-scale value* (confirmed: constant per-step delta in that space, verified at both ends of a real ramp). Live interpolates linearly between `FloatEvent`s in whatever scale that parameter's `Value` attribute uses — linear gain for Volume, not dB and not Logic's fader-scale. So a ramp's two endpoint values are exact, but the shape of the curve *between* them will not exactly match Logic's, even for an originally-linear ramp. Per the controlling spec, this was always an accepted limitation (see "Out of scope" below), not a defect to chase further here.

**Tests added**: decoder-level (`tests/test_logic_project_data.py`, using the same low-level fixture style as the rest of that file — ground-truth values inlined with a pointer to where they came from) and generator-level (`tests/test_ableton_generator.py`, including the empty-envelope and -∞ dB edge cases). Full suite: 640 passed, 2 pre-existing unrelated failures (VST3 scanner tests leaking the real machine's installed plugins into an isolation test — not touched by this work).

**Confirmed working against real production data**: ran the full CLI pipeline on a real, large project (not a synthetic fixture) and verified the generated `.als`'s `FloatEvent` values decode back to the exact same dB/pan values the parser extracted.

## Follow-up (not done here, not blocking)

- Curved (non-linear) automation segments, and whatever the `0x51`/`0x52` status-byte variants seen in real projects turn out to mean, are unexplored — current behavior degrades them to a straight line between whatever nodes get recognized, never a crash or silent wrong value beyond that approximation.
- Parameters beyond volume/pan (e.g. plugin-parameter automation) are out of scope here by the issue's own original framing — they depend on issues 03/04's plugin/device mapping existing first, and are correctly reported as unrecognized rather than dropped.

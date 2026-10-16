Status: ready-for-agent

# Auto-mute a track when its instrument plugin can't transplant

## Problem Statement

When a converted Ableton project is handed to a collaborator, a channel strip's instrument plugin that isn't installed on their machine leaves that track with nothing to generate sound at all — Ableton shows a "could not be found" warning and the device slot sits broken, but nothing in the converted project proactively handles this. The recipient is left staring at a silently-broken, confusing track state rather than a clear, intentional one.

## Solution

When a channel strip's instrument plugin can't be transplanted, the destination Ableton track is automatically muted rather than left in a broken device state — since without the instrument, nothing else on that channel strip has anything to process anyway. The MIDI performance itself is preserved untouched, so the recipient can load any instrument of their own into that track and unmute it, keeping the original performance. This requires no manual precondition (no export step, no extra flag) and no audio rendering — it's a pure decision made from information the converter already computes when deciding whether to transplant a plugin at all. A processing (effect) plugin that can't transplant needs no new handling: it was already never inserted, so the channel strip's dry signal already plays through unaffected — only the conversion report needs to say so explicitly, a direct extension of already-built per-instance outcome reporting. The conversion report distinguishes a track auto-muted this way from a track the user already muted themselves in Logic, so nobody mistakes one for the other.

## User Stories

1. As a Logic Pro user converting a project for a collaborator, I want a track whose instrument plugin can't be transplanted to come through as cleanly muted, so my collaborator sees an intentional, understandable state instead of Ableton's raw "could not be found" error.
2. As a Logic Pro user, I want this to require no manual step before conversion — no exporting audio from Logic first, no extra flag to remember — so the simple "Logic project in, Ableton project out" flow stays simple regardless of whether every plugin is available on the machine running the conversion.
3. As a Logic Pro user, I want the original MIDI performance on an auto-muted track preserved exactly as-is, not deleted or altered, so my collaborator can load their own instrument into that track and immediately hear the same performance.
4. As a Logic Pro user, I want this auto-mute to trigger only when the specific missing plugin is the channel strip's actual sound source (an AU "Music Device"), not any MIDI-aware processing plugin, so a plugin like an EQ that merely happens to respond to MIDI doesn't wrongly silence a track that has plenty to play without it.
5. As a Logic Pro user, I want a channel strip's processing (effect) plugins that can't transplant to simply be left out of the chain, with the rest of the chain — including the dry signal — still playing, so one missing effect never silences an otherwise-working track.
6. As a Logic Pro user, I want the conversion report to say explicitly when a processing plugin was dropped from a track's chain, even though the track still plays, so I know exactly what's different from the original mix before I send the project.
7. As a Logic Pro user, I want the conversion report to clearly distinguish a track I muted myself in Logic from a track the converter auto-muted because of a missing instrument, so I'm never confused about which tracks need my attention versus which ones I already decided to silence.
8. As a Logic Pro user's collaborator opening the converted project, I want to be able to tell at a glance (via the report, or an obvious marker) why a given track is silent, so a missing instrument doesn't read as a broken or buggy conversion.
9. As a Logic Pro user, I want this mechanism to coexist cleanly with everything else the converter already does (transplant, automation, mixer state), so auto-muting a track never touches its automation, its other mixer settings, or any other track in the project.

## Implementation Decisions

- Trigger condition: a channel strip's plugin instance with AU type `aumu` ("Music Device" — the only type that reliably means "this track's sole sound source") whose transplant outcome (already computed per-instance) is anything other than "transplanted." Specifically excludes `aumf` ("Music Effect") despite being MIDI-aware, since it processes a signal that exists independent of it (confirmed concretely: FabFilter Pro-Q 4, a pure EQ, is `aumf`).
- Mechanism: set the destination Ableton track's mute state, reusing the exact mechanism the mixer-state work already writes mute from — not a new field, not a new code path for "how to mute a track."
- The MIDI clip/notes on that track are left completely untouched — only the mute state changes.
- A channel strip can have at most one instrument slot in Logic, so at most one `aumu` instance can trigger this per channel strip — no need to handle multiple simultaneous instrument-plugin failures on one track.
- Effect plugins (`aufx`, `aumf`) that can't transplant require no new writer logic: they're already simply never inserted into the device chain (existing behavior from the core transplant mechanism), so the dry/unprocessed signal already plays through.
- Reporting: the conversion report states, per track, when it was auto-muted due to a missing instrument (naming the plugin), distinctly worded from a track that was already muted in the source Logic project. For effect-level drops, the report states which effect was dropped and that the rest of the chain is intact — a direct extension of the existing per-instance transplant-outcome reporting, not a new reporting mechanism.
- No CLI flag needed — this is not opt-in behavior like the deferred bounce approach; it's the converter's default, always-on handling of a plugin that can't transplant, since it requires no extra cost or precondition to apply.

## Testing Decisions

- Seam: the full conversion pipeline — a `.logicx` project with a channel strip whose instrument plugin isn't available (simulated via a mixer/registry test double, the same style already used for the core transplant tests), `.als` out — asserting on the destination Ableton track's mute state and on the conversion report's wording.
- What a good test asserts: only externally observable output — the generated track's mute flag, that the MIDI clip's notes are unchanged, and the report's stated reason. Not internal decision-function call counts.
- Fixtures needed: (a) a channel strip whose instrument plugin fails to transplant (asserts auto-mute + correct report wording), (b) a channel strip whose instrument plugin transplants successfully (asserts no auto-mute), (c) a channel strip with only a failing effect plugin, no instrument (asserts the track is NOT muted, and the report states the effect was dropped), (d) a track already muted in the source Logic project with no missing plugins at all (asserts the report attributes the mute to the source project, not to auto-mute).
- Prior art: matches the existing golden-file-style integration tests and one-test-file-per-module pattern already in the repo, and directly extends the existing `decide_transplant()`/outcome-reporting tests from the `au-plugin-state-transplant` spec's ticket 03.

## Out of Scope

- Any form of audio rendering, bouncing, or plugin hosting — deferred entirely to the bounce-fallback spec if ever pursued.
- Any fallback behavior for effect plugins beyond what already happens (nothing inserted, dry signal plays) plus accurate reporting — no attempt to substitute, approximate, or stock-map a missing effect here (that's the separate stock-instrument-mapping problem).
- Auto-muting a track for any reason other than a missing `aumu` instrument — e.g. a missing effect never triggers a mute, regardless of how central that effect was to the original mix.
- A CLI flag or opt-out for this behavior — it's considered safe, free, and always-correct to apply, so there's no scenario where a user would want the broken, un-reported Ableton default error state instead.

## Further Notes

- This emerged directly from grilling the deferred bounce-fallback spec: the original "fully working for a missing plugin" problem turned out to have a much cheaper, precondition-free answer for the one case that actually matters most (a missing instrument leaves nothing to play), while the other case (a missing effect) turns out to already be handled by the existing transplant mechanism's existing behavior.
- See `docs/adr/0001-auto-mute-over-bounce-for-missing-instrument-fallback.md` for the recorded trade-off against the bounce alternative.
- See `CONTEXT.md` for the sharpened vocabulary this spec relies on (Logic track vs. channel strip vs. Ableton track, instrument vs. effect plugin, transplant outcome, fallback, auto-mute) — written during the same session this spec came from.

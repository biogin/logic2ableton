Status: deferred — superseded for MVP by `.scratch/instrument-auto-mute-fallback/spec.md`; see `docs/adr/0001-auto-mute-over-bounce-for-missing-instrument-fallback.md` for why. Not discarded: a real option if a richer, edit-equivalent fallback is ever worth the manual-export precondition this spec requires.

# Bounce fallback for plugins missing on the recipient's machine

## Problem Statement

When a converted project is handed to a collaborator, any third-party plugin they don't have installed degrades to Ableton's own "could not be found" warning for that device — the project still opens, but that one track's processing is simply gone, with no sound and no way to recover it on the spot. For the mixing-handoff use case this doesn't matter (audio only, no plugins involved), but for the artist-collaboration use case — the whole point of transplanting plugin state instead of just bouncing stems — "fully working" currently depends on the recipient's plugin collection matching the sender's closely enough, which can't be known or guaranteed from the sending machine alone.

## Solution

When converting a project the sender expects to hand off, they can opt in to attaching a safety-net audio bounce to any track carrying a third-party plugin, so the track still sounds right even if the recipient is missing that plugin — as a muted alternate clip sitting on the same track, not a separate cluttering shadow track. The bounce itself comes from Logic's own existing "Export All Tracks as Audio Files" feature, run once by the sender before conversion — the converter's job is only to find those exported files, match each to its originating track, and bundle them in; it never renders audio or hosts a plugin itself. This is opt-in, not automatic, since most conversions don't need it, and it only applies to tracks that actually carry a third-party plugin. The live, editable version always remains what loads and plays by default; the bounce is pure insurance, ready if the live version turns out to be missing something on the other end.

## User Stories

1. As a Logic Pro user handing a project off to a collaborator, I want an option to attach a safety-net audio bounce to tracks with third-party plugins, so my collaborator's project still sounds right even if they're missing a plugin I have.
2. As a Logic Pro user, I want this fallback to be opt-in, not automatic, so ordinary conversions (same-machine use, or handoffs where I already know the collaborator has everything) aren't slowed down or bloated by rendering I don't need.
3. As a Logic Pro user, I want the converter to detect audio I've already exported via Logic's own "Export All Tracks as Audio Files" and match it to the right tracks automatically, so I don't have to organize files myself.
4. As a Logic Pro user, I want the fallback bounce attached only to tracks that actually carry a third-party plugin, so tracks that already load identically regardless of install base (pure audio, or stock-device-mapped) aren't bloated with a redundant duplicate.
5. As a Logic Pro user, I want the fallback bounce placed as a second, muted clip on the same track as the live version, not a separate visible shadow track, so the arrangement doesn't get cluttered or confusing for my collaborator.
6. As a Logic Pro user's collaborator opening the converted project, I want the live, editable version of each track to be what plays by default, so the project stays as editable as possible wherever the real plugin is actually available.
7. As a Logic Pro user's collaborator, when a plugin is genuinely missing, I want an easy, obvious way to switch that one track over to its bounced fallback, so a missing plugin never means silence or a broken-sounding mix.
8. As a Logic Pro user, I want the conversion report to state which tracks have a fallback bounce attached and which don't (and why), so I know exactly how complete my safety net is before I send the project.
9. As a Logic Pro user, when I pass the fallback flag but haven't actually exported any tracks from Logic first, I want the converter to tell me clearly, so I don't mistakenly believe I have a safety net that isn't there.
10. As a Logic Pro user, I want fallback matching to work even when I've only exported some of my third-party-plugin tracks, so a partial safety net is still useful rather than all-or-nothing.
11. As a Logic Pro user, I want this feature to never require the converter to host or render through actual plugins itself, so it doesn't depend on building a full offline audio-rendering engine — it only ever repackages audio Logic itself already rendered.
12. As a Logic Pro user, I want the fallback mechanism to coexist cleanly with everything the converter already does (automation, mixer state, plugin transplant), so turning on the flag never changes or breaks a track's live version, only adds an inert alternate next to it.
13. As the maintainer of this tool, I want the mechanism for detecting and matching Logic's exported bounce files grounded in how Logic's export actually behaves (investigated directly), not assumed, since this hasn't been verified yet.

## Implementation Decisions

- New opt-in CLI flag (e.g. `--bounce-fallback`) gating this entire feature — default behavior with the flag omitted is completely unchanged.
- Scope of which tracks are eligible: only tracks carrying at least one third-party plugin instance (using the existing `PluginInstance`/track attribution from the `au-plugin-state-transplant` spec's ticket 01) qualify. Tracks that are pure audio, map to a guaranteed stock device, or have no plugins at all are skipped — they already load identically regardless of install base.
- Source of the bounce audio: Logic's own "Export All Tracks as Audio Files" feature, run manually by the user before conversion. The converter does not drive Logic, does not render audio, and does not host any plugin itself — this boundary is deliberate; building an offline AU-hosting renderer was considered and rejected as a separate, much larger undertaking than anything else this tool has built, and unnecessary when Logic's own export already exists.
- File matching: the converter looks for exported audio matching each eligible track by name. The exact matching convention (Logic's default export location and filename pattern) is not yet verified and needs direct investigation as the first implementation step, not assumption. Matching is partial-tolerant: a track with no matching export simply has no fallback, reported as such — never an error that blocks the rest of the conversion.
- Placement in the generated `.als`: the bounce is a second clip on the *same* Ableton track as the live version, muted by default — not a separate parallel track. Keeps the arrangement visually clean and keeps the recipient's fallback action simple: mute the live clip, unmute the bounce.
- The live/transplanted version stays the default that plays; the fallback clip is inert unless the recipient deliberately switches it on.
- Reporting: the conversion report lists, per eligible track, whether a fallback bounce was attached or why not (no matching export found). When `--bounce-fallback` is passed but zero exported files are found anywhere, the report (and ideally a CLI-level warning) says so plainly — "flag passed" must never be mistaken for "safety net present."
- This feature must never alter a track's live/automation/mixer/transplant behavior — it only ever adds an inert second clip alongside what already gets generated.

## Testing Decisions

- Seam: the full conversion pipeline — a `.logicx` project with Logic-exported bounce audio present, `--bounce-fallback` passed, `.als` out — asserting on the generated fallback clip's XML (track, mute state, clip reference) and on the conversion report's per-track fallback-coverage listing. Matches the existing single-seam, full-pipeline test style already used for automation and transplant work in this codebase.
- What a good test asserts: only externally observable output — which tracks got a fallback clip, that it's muted by default, that the live clip/devices are unchanged, and that the report accurately states coverage. Not internal file-matching data structures.
- Fixtures needed: a project with (a) a third-party-plugin track with a matching exported bounce present, (b) a third-party-plugin track with no matching export (the partial-coverage case), and (c) a pure-audio or stock-mapped track (must never get a fallback — confirms the scoping rule).
- Also needs a test for `--bounce-fallback` passed with zero exported files found anywhere, asserting the clear "no safety net attached" signal.
- Prior art: matches the existing golden-file-style integration tests and one-test-file-per-module pattern already in the repo.

## Out of Scope

- Building any form of offline audio rendering or AU/VST plugin hosting inside the converter — this feature only ever repackages audio Logic itself has already rendered via its own export.
- Automating or driving Logic's own UI/export process (e.g. GUI scripting) — the user runs "Export All Tracks as Audio Files" themselves, once, manually.
- Any fallback for Logic's own stock instruments/effects (ES2, Alchemy, etc.) — that's the separate, already-tracked stock-instrument-mapping problem, not a missing-on-recipient's-machine problem (stock devices map to Ableton's own stock equivalents and have no "might not be installed" case).
- Automatic, always-on bouncing — this is opt-in only.
- The converter deciding on the recipient's behalf which track to switch to its fallback — the recipient always makes that choice themselves by unmuting the clip; the converter never guesses whether a transplant will actually work on a machine it can't see.

## Further Notes

- This directly answers a real workflow question: "if I convert a Logic project and hand it to a friend, and he doesn't have some of my plugins, what happens?" Today's honest answer is "Ableton disables that one device and shows a warning, but the project otherwise still opens" — survivable, but not "fully working." This feature is the closest realistic answer to that, short of either requiring an exact plugin-collection match (unrealistic) or building a full offline rendering engine (a large, separate undertaking, explicitly rejected above).
- The exact mechanism for finding Logic's exported bounce files (default location, filename convention) is a genuine unknown at spec time — direct investigation of real output from Logic's "Export All Tracks as Audio Files" is the first step of implementation, not an assumption baked into this spec.
- This sits alongside, not inside, the `au-plugin-state-transplant` spec — a complementary safety net for when that spec's live transplant can't work on the recipient's machine, not a replacement for it. The live transplant should always remain the primary, preferred path.

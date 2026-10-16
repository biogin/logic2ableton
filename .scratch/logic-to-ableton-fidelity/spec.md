# Logic Pro → Ableton Live: closing the fidelity gap

## Goal

A personal tool: take a Logic Pro `.logicx` project and produce a **fully working** Ableton Live `.als` project — one that sounds right when played back in Ableton, not just one that opens without crashing. Primary motivating case: sending a project to a friend/collaborator who works in Ableton and wants to keep contributing to it (not just a mixing-stems handoff, which is a separate, much simpler, explicitly out-of-scope problem — see Non-goals).

## Why this spec exists

Reached by a grilling session (see conversation). Starting point was "does a Logic→FL Studio/Ableton converter exist and why not" — landed here after establishing:
- Two unrelated real use cases exist (mixing handoff = audio-stems-only, no conversion needed; artist collaboration = full project fidelity). This spec is **only** about the second one.
- An existing open-source project, [`Evilander/logic2ableton`](https://github.com/Evilander/logic2ableton) (MIT, this repo), already solves audio region placement, MIDI note decoding, tempo/warp markers, locators, and mixer (level/pan/mute/bus grouping) — validated against 246 saved versions of 117 real projects. A fork-vs-reimplement audit (see Decisions below) confirmed its architecture (decoder → model → writer) is clean enough to build on, with one localized orchestration smell in `cli.py`.
- The gap between "already solved" and "fully working" is specifically: software instrument/plugin fidelity, automation, sends/inserts, and fades/crossfades/region gain.

## Decisions locked in

- **Scope**: full Logic → Ableton conversion (not the mixing-stems problem). Ableton first; FL Studio is an explicit phase-2, only if it turns out tractable — not designed for yet.
- **Direction**: one-way (Logic → Ableton) for v1. Round-trip (Ableton → Logic, for bringing a collaborator's edits back) is deferred — don't design the model to block it, but don't build it now.
- **Foundation**: fork and extend `logic2ableton`, don't reimplement from scratch. Confirmed via code audit — see "Audit findings" below.
- **Plugin/instrument scope**:
  1. A hand-built mapping table for Logic's own stock instruments/effects (ES2, Alchemy, Sampler, Drummer, Channel EQ, Compressor, etc.) → closest Ableton stock equivalents (Wavetable, Operator, Drum Rack, EQ Eight, Glue Compressor, ...). This is always lossy/approximate by nature — there's no way around that.
  2. For third-party AU plugins installed on both the source and target machine: attempt state-blob transplant (see spike, issue 01) rather than parameter remapping. This is a bet, not a guarantee — confirm feasibility before relying on it.
  3. Anything else (plugin missing on target machine, or blob transplant doesn't pan out): flag clearly in the conversion report. Never silently drop or fake a plugin's contribution.
- **Scoped to personal use, architected for general use**: the tool only needs to handle the plugins/instruments the project owner actually uses day to day — don't try to build a universal plugin database. But don't hardcode personal paths/assumptions that would block later generalization (e.g. if open-sourced).
- **Tech stack**: Python (matches the existing codebase; also the right call for continued reverse-engineering work — fast guess/inspect/retry loop beats Rust's edit-compile-run loop for that, and raw speed doesn't matter for single-project-file conversion).
- **Delivery**: CLI only for v1. No GUI work.
- **Legal/risk posture**: reverse-engineering Apple's undocumented `.logicx` format is accepted as standard practice for a personal tool reading one's own files — not redistributing Apple's format spec or code.

## Audit findings on `logic2ableton` (informs where to extend, not duplicate)

- Clean separation exists: `logic_project_data.py` (binary decoder + format spec in the module docstring) → `logic_parser.py` (builds `LogicProject` model, see `models.py`) → `ableton_generator.py` (`.als` XML writer, clones a template and correctly manages Ableton's `NextPointeeId` invariant).
- One real smell: `cli.py`'s `_run_forward()` (~lines 534–849) is a ~315-line monolithic function mixing arg validation, progress events, and pipeline orchestration. Localized refactor, not a reason to distrust the layers underneath.
- **Automation location is already known but unwired**: per-track automation is stored as MIDI placements of an `MSeq` named `*Automation` (documented in the decoder's own notes). Nothing currently reads this into the Ableton writer.
- **`PluginInstance.raw_plist` (`models.py`, populated in `logic_parser.py`) already captures the full parsed plist for every plugin instance** during decode. Unused today, marked "for future use" in the code — this is the most likely candidate for the AU state blob we need for the transplant spike. Don't re-derive this from raw bytes; it's already extracted.
- Current plugin handling (`plugin_matcher.py`, `plugin_database.py`) only does name/category similarity matching to suggest a VST3 replacement — no parameter translation. Confirms the gap; nothing to lift here beyond the matching-suggestion UX.
- Well-tested: ~9,700 test lines against ~10,900 source lines, one test file per module, plus `docs/reverse-engineering-logic-pro-midi.md` and `docs/reverse-engineering-pro-tools-sessions.md`.

**Second resource found mid-spike**: [`elixirbeats/abletoolz`](https://github.com/elixirbeats/abletoolz) (MIT) is a mature Python library for editing/grafting Ableton `.als` sets — not Logic-related, but it already solves the Ableton-side half of the hardest open question here. It documents (and its code implements) the exact `PluginDevice > PluginDesc > {VstPluginInfo|Vst3PluginInfo|AuPluginInfo}` structure, confirms the wrapper is format-agnostic (measured on Live 12.4.5), confirms `<Buffer>` is plain hex with no transformation, and already has pointee-id-safe device-chain grafting (`live_set/devices.py`) plus a from-scratch FabFilter `FFBS` state parser/encoder (`plugin_parsers/state/fabfilter.py`, including a Pro-Q1→Pro-Q3 translation). Treat this as a second foundation to build on for the Ableton-writer side, not just a reference.

## Open technical risk

**Does the AU ClassInfo blob transplant actually work?** Hypothesis: both Logic and Ableton host AU plugins on Mac via the standard `kAudioUnitProperty_ClassInfo` state mechanism (an opaque plist blob the plugin itself produces/consumes). If both DAWs store that same blob (just tagged with plugin identity) in their project files, copying it across hosts could restore a third-party plugin's exact state without understanding its internal parameters at all — near-lossless, for free, for any plugin installed on both machines.

This is **unverified** — no documentation confirms how either DAW embeds the blob in its file, or whether the two hosts' encodings are even compatible. It needs an empirical spike (issue 01), not more research. If it fails, third-party plugin fidelity falls back to the same manual-mapping-table approach as stock instruments, just with a much longer tail (unbounded third-party plugin list vs. a fixed stock-instrument list).

## Non-goals (explicitly out of scope for this spec)

- The mixing-handoff use case (audio stems only, no MIDI/instruments needed) — different problem, doesn't need any of this; Logic's own stem-export features already cover it.
- FL Studio as a target.
- Round-trip (Ableton → Logic).
- A GUI/desktop app (the repo has an Electron wrapper already; not in scope to extend it here).
- A general-purpose plugin database covering plugins the project owner doesn't personally use.

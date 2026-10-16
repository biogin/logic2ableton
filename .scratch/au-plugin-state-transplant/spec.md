Status: ready-for-agent

# Third-party AU plugin fidelity via ClassInfo state transplant

## Problem Statement

When converting a Logic Pro project to Ableton Live, every third-party plugin instance — EQs, compressors, saturators, reverbs, from vendors like FabFilter, oeksound, SoundToys, Xfer — currently loses its settings. The existing converter correctly identifies *which* plugin was used and suggests a replacement, but never restores the actual dialed-in parameters. A real session can carry a few dozen such instances. Re-dialing every one of them by ear after every handoff defeats the purpose of a project-level converter, and is the single biggest reason a Logic-to-Ableton handoff is currently a slow, manual, error-prone process for a user collaborating with an Ableton-based artist.

## Solution

When a Logic Pro project is converted to Ableton Live, any third-party Audio Unit plugin instance that is installed on both the source and target machine loads in Ableton with the exact same settings it had in Logic — no re-dialing, no guessing. This works because both DAWs store a plugin's state via the same standard macOS Audio Unit state-saving mechanism, not a Logic-specific or Ableton-specific format; moving that data across is enough to restore the plugin faithfully, without the converter needing to understand what any individual plugin's parameters mean. When a plugin can't be transplanted (not installed, not AU, platform mismatch), the conversion falls back cleanly to the existing suggestion-only behavior and says so in the report — it never fails the whole conversion and never silently produces a wrong-sounding result without flagging it.

## User Stories

1. As a Logic Pro user converting a project to Ableton, I want any third-party AU plugin instance that's installed on both machines to load in Ableton with its original Logic settings intact, so that I don't have to re-dial every plugin by ear after every handoff.
2. As a Logic Pro user, I want the converter to correctly identify which specific AU plugin (manufacturer, subtype, type) each instance is, so that the right plugin loads in Ableton rather than a wrong or generic one.
3. As a Logic Pro user, I want the converter to transplant a plugin's entire saved state, not just a partial or inner subset of it, so that the loaded plugin shows my actual dialed-in parameters rather than silently falling back to its factory default.
4. As a Logic Pro user, I want each plugin instance's transplanted state to land on the correct track and in the correct insert-chain position, so that a channel strip with multiple instances of the same plugin ends up with each instance's settings in the right slot, not mixed up or duplicated.
5. As a Logic Pro user whose channel strip has several different plugins in a chain, I want all of them transplanted in their original order, so that the processing chain behaves the same way in Ableton as it did in Logic.
6. As a Logic Pro user, when a plugin instance is a software instrument (an AU instrument/music-effect type) rather than an effect, I want the converter to still attempt the same state-transplant mechanism, so that instruments aren't arbitrarily excluded from a mechanism that works regardless of AU type.
7. As a Logic Pro user, when a third-party plugin used in my project is not installed on the machine running the conversion, I want the converter to fall back cleanly to its existing suggestion-only behavior for that instance, so that a missing plugin doesn't break the whole conversion.
8. As a Logic Pro user, when a third-party plugin is installed but is not an Audio Unit (only available as VST3, or the conversion runs on Windows where AU doesn't exist), I want the converter to fall back to the existing suggestion-only behavior for that instance, so that non-AU plugins don't cause errors or silent data loss.
9. As a Logic Pro user, I want the conversion report to clearly state which plugin instances were transplanted, which fell back to suggestion-only, and why, so that I know exactly what to manually check before sending a project to a collaborator.
10. As a Logic Pro user, I want the transplant to work regardless of which plugin vendor's internal state format is involved (FabFilter's own binary format, JUCE-based plugins' XML-wrapped state, Xfer's VST2-chunk format, etc.), so that the mechanism isn't limited to one plugin framework.
11. As a Logic Pro user, I want the converter to never silently produce a "looks loaded but is actually wrong" result for a plugin it could not transplant correctly, so that I'm not misled into sending a collaborator a project that sounds different from what I heard in Logic.
12. As the maintainer of this tool, I want plugin-state extraction to preserve the exact original bytes Logic stored for a plugin instance, not a re-serialized reconstruction, so byte-for-byte fidelity isn't put at risk by an intermediate parsing step.
13. As the maintainer of this tool, I want pointee IDs and chain-local device IDs allocated safely when a new plugin device is synthesized into a track's device chain, so the generated `.als` doesn't corrupt or collide with IDs already used elsewhere in the set.
14. As a Logic Pro user with a project containing several dozen third-party plugin instances, I want the transplant mechanism to run automatically across the whole project in one conversion pass, so I don't have to invoke it per-track or per-plugin.
15. As a Logic Pro user, I want this transplant mechanism to only ever add fidelity on top of what the converter already transfers (audio, MIDI, tempo, mixer), so existing working behavior isn't put at risk by this feature.
16. As a Logic Pro user, when the installed version of a plugin on the target machine differs from the version used in Logic, I want the converter to still attempt the transplant (most vendors keep state formats backward-compatible within a major version lineage) but flag the version difference in the report, so I know to double-check if something looks off.
17. As a Logic Pro user converting a large project, I want the transplant step to not meaningfully slow down the overall conversion, so project-level conversion stays fast enough for routine use.

## Implementation Decisions

- **Parser (`logic_parser.py`, `models.py`)**: `extract_plugins()`/`PluginInstance` is extended to retain the raw original plist byte range per plugin instance (the exact `<?xml version...?>...</plist>` bytes Logic embeds), not just the parsed dict it currently keeps. This raw byte range is the artifact that gets transplanted — a Python re-serialization of the parsed dict is not an acceptable substitute (confirmed by prototype: it silently produces a wrong result, not an error).
- **Parser: per-track/per-insert-slot association**. Each extracted plugin instance must be tied to the specific channel strip and insert position it belongs to. This is new — the parser currently has no such association. Likely shares groundwork with insert-chain transfer work tracked separately; check for overlap before implementing twice.
- **Writer (`ableton_generator.py`)**: new AU device-chain synthesis path. Given a plugin instance (identity + raw plist bytes + target track/insert position), construct a `PluginDevice > PluginDesc > AuPluginInfo > Preset > AuPreset > Buffer` XML fragment and insert it at the correct position in the track's `Devices` list.
- **AU identity encoding**: Logic's `au_type`/`au_subtype`/`au_manufacturer` four-character codes convert to Ableton's `ComponentType`/`ComponentSubType`/`ComponentManufacturer` int32 fields via the same big-endian packing already used by the parser's `_int_to_4cc` helper (`struct.pack`/`unpack(">I", ...)`), confirmed correct against a real Ableton-authored AU device example found in a third-party `.als` fixture.
- **`Buffer` content**: the complete original plist document Logic stored for the instance — identity fields, vendor payload key, and any other keys together, byte-identical — hex-encoded verbatim. Confirmed by prototype against real Ableton Live 12.4.6: a partial or reconstructed blob loads the correct plugin identity but silently resets to its factory default; only the complete original byte range restores the real state.
- **ID safety**: a synthesized device needs a chain-local `Device/@Id` unique within its target track's `Devices` list, plus any `AutomationTarget`/`Pointee` IDs allocated from the set's `NextPointeeId` counter, incrementing that counter accordingly, so the generated file never collides with IDs used elsewhere in the set.
- **Fallback behavior**: when a plugin isn't installed on the conversion machine, isn't an AU plugin, or the platform has no AU support (Windows), fall through to the existing suggestion-only plugin-matching path. This feature adds a new successful path; it does not replace or remove the existing fallback.
- **Reporting**: the existing conversion report gains a clear distinction between "transplanted" and "suggestion-only" plugin instances, with a stated reason for any fallback (not installed, not AU, platform mismatch, version mismatch flagged).
- **Scope boundary**: this covers only the transplant mechanism — identity resolution, full-state transplant, fallback, reporting. It explicitly excludes Logic's own stock instruments/effects (no AU-state equivalent exists in Ableton for those; they need a separate, hand-built mapping-table approach tracked elsewhere).

### Prototype findings (from a manual spike, encoded here precisely because prose alone would under-specify it)

Two real-Ableton-Live tests were run against a real Logic Pro project:

- **Attempt 1** (transplanting only the plugin's vendor-specific inner state value, e.g. just the JUCE `jucePluginState` field): the correct plugin loaded, but every parameter was wrong and Ableton's own preset-name field read "factory default preset" — a silent, wrong-but-undetectable-by-loading-alone failure.
- **Attempt 2** (transplanting the complete original plist byte range, unmodified): the plugin loaded with settings visually confirmed identical to the Logic original, verified against real Ableton Live 12.4.6.

Only one plugin vendor (a JUCE-based plugin) was verified end-to-end in real Ableton. The mechanism should generalize to other vendors' internal formats (FabFilter's own binary format, Xfer's VST2-chunk format) because the AU `ClassInfo` contract being transplanted is standard, not vendor-specific — but this is inference, not yet independently re-confirmed per vendor.

## Testing Decisions

- **Seam**: the full conversion pipeline — a `.logicx` fixture in, `.als` out — asserting on the generated AU device XML. No separate unit-level seam for the parser or writer in isolation; test through the same public interface the existing test suite already exercises for other conversion behavior.
- **What a good test asserts**: only externally observable output — the AU device's `ComponentType`/`ComponentSubType`/`ComponentManufacturer` match the source plugin's identity, the `Buffer` hex decodes back to content byte-identical to the source Logic plist, and the device appears in the correct track and insert-chain position. Not internal data structures or intermediate parser state.
- **Fixtures needed**: at least one fixture with a single, unambiguous third-party AU plugin instance, and at least one fixture with a channel strip carrying multiple instances of the same plugin in different insert positions (this is what exposed the slot-association gap during the manual spike — a channel strip with three Pro-Q 4 instances made an early test attempt impossible to validate).
- **Prior art**: matches the existing one-test-file-per-module pattern in the codebase, and its existing golden-file-style integration tests against real projects.
- **Not covered by automated testing**: an actual open-in-Ableton visual check (what the manual spike did) isn't automatable in CI. Automated tests validate the generated XML artifact, not real Ableton runtime behavior. The manual spike already provides one real-world confirmation; no further manual verification is required unless the automated assertions reveal a discrepancy from what the spike observed.

## Out of Scope

- Logic's own stock instruments/effects (ES2, Alchemy, Sampler, Drummer, Channel EQ, Compressor, etc.) — no AU state to transplant; needs a separate, hand-built mapping-table approach, tracked elsewhere.
- Sends, aux/return routing, and insert-chain-level mixer behavior beyond device state itself — tracked elsewhere.
- Automation data for any parameter, transplanted or not — tracked elsewhere.
- Round-trip (Ableton → Logic) transplant — one-way only.
- FL Studio as a conversion target.
- Any plugin format other than Audio Unit on the Logic side.
- A general-purpose plugin compatibility database — this only needs to work for plugins actually installed on the machine running the conversion, not a universal catalog.

## Further Notes

- This was the single highest-risk, highest-payoff open question identified during initial scoping of the larger "full Logic → Ableton project conversion" effort this feature sits inside. It is now empirically confirmed, which substantially de-risks that larger effort.
- `elixirbeats/abletoolz` (MIT-licensed, external project, not a dependency) was used as a reference during the spike for Ableton's `.als` AU plugin XML structure and device-chain ID-safety conventions — its author independently measured the `PluginDevice`/`PluginDesc` wrapper as format-agnostic across VST/VST3/AU on Live 12.4.5, which this spike's own fixture comparison corroborated.
- The per-track/per-insert-slot association gap (user story 4, and the corresponding implementation decision) only surfaced because the first real-world test attempt picked an ambiguous instance — a channel strip with three copies of the same plugin, with no way to know which one a given extracted blob came from. Treat slot association as a prerequisite for correctness, not an optional refinement.

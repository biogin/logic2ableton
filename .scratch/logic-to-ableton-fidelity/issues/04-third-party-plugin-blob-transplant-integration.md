# 04 - Integrate AU blob transplant for third-party plugins

Status: ready-for-agent
Type: task

## What

Issue 01 confirmed AU ClassInfo blob transplant works: transplanting the **entire original plist** Logic stores for a plugin instance (not just the vendor-specific inner value) into Ableton's `AuPluginInfo > Preset > AuPreset > Buffer` (hex-encoded, verbatim) correctly restores third-party AU plugin state, verified end-to-end with a real plugin (oeksound soothe2) in real Ableton Live 12.4.6. Wire this into the actual conversion pipeline instead of the current spike-script prototype.

## Scope

1. **Fix `PluginInstance`/`extract_plugins()` in `logic_parser.py`** to retain the raw original plist byte range (`data[start:end]`) per plugin instance, not just the parsed dict. This is the exact artifact that needs to be hex-encoded into `Buffer` — a Python re-serialization of the parsed dict is not safe to substitute (see issue 01's findings).
2. **Solve per-track/per-insert-slot association** — confirmed gap in issue 01's Test 1: `extract_plugins()` currently has no way to say which channel strip/insert slot a given plugin instance belongs to. Without this, the pipeline can't decide which Ableton device slot a transplanted blob goes into when a channel strip has multiple instances of the same (or different) plugins. This is likely shared groundwork with issue 05 (insert chains) — check whether solving it once here covers both.
3. **Build the `AuPluginInfo`/`PluginDevice` XML synthesis into `ableton_generator.py`** as real pipeline code: identity fields (`ComponentType`/`ComponentSubType`/`ComponentManufacturer`, from the same big-endian 4cc encoding `_int_to_4cc` already uses, inverted), the `Preset > AuPreset` wrapper (mirroring the structure confirmed against real Ableton skeleton fixtures — see issue 01), and correct pointee-id allocation from `NextPointeeId` (the spike script did this by hand; needs the same ID-safety discipline `abletoolz`'s `graft_chain` uses, see spec.md).
4. **Fallback path**: when the plugin isn't installed on the machine running the converter, or isn't an AU plugin at all (Windows users, or plugins only available as VST3) — fall through to the existing `plugin_matcher.py` suggestion-only behavior rather than fail the conversion.
5. **Spot-check at least one non-JUCE vendor** (FabFilter `FFBS` or Xfer's VST2-chunk format) with the full-plist-transplant approach before considering this generalized — issue 01 only verified one JUCE-based plugin; the mechanism should generalize (it's the AU contract, not JUCE-specific) but that's inference, not confirmed per-vendor.

## Answer

(fill in once implemented)

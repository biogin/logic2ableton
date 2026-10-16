# 01 - Spike: does AU ClassInfo blob transplant actually work?

Status: resolved
Type: research/prototype

## Question

Can a third-party Audio Unit plugin's saved state be carried from a Logic Pro project into an Ableton Live project by copying an opaque blob, without understanding the plugin's internal parameters?

## Why this matters

See spec.md "Open technical risk." If this works, third-party plugin fidelity for anything installed on both machines is close to free. If it doesn't, plugin fidelity requires the same bounded, hand-built mapping-table approach as Logic's stock instruments — except for an unbounded list of third-party plugins, which is a much bigger (likely out of scope) undertaking.

## How to test it

1. Pick one AU plugin installed and licensed on this machine (something with an obviously distinctive, non-default setting you can recognize by ear or by a visible parameter value — not an init patch).
2. Load it in a throwaway Logic Pro project, dial in the distinctive setting, save.
3. Load the *same plugin* in a throwaway Ableton Live project, dial in the *same* setting via Ableton's UI, save.
4. Decode the Logic project with `logic2ableton`'s existing parser and inspect `PluginInstance.raw_plist` (see `models.py`, populated in `logic_parser.py`) for that plugin instance.
5. Separately, inspect the Ableton `.als` (gunzip it, it's XML) for how it stores that same plugin's state — look for a base64 blob, a nested plist, or a `<PluginDesc>`/similar element with embedded binary data.
6. Compare: is the Logic-side blob (from `raw_plist`) byte-for-byte or structurally identical to the chunk of binary state Ableton embeds for the same plugin/setting? Does swapping one for the other (write Logic's blob into Ableton's XML in place of its own) produce a project that opens in Ableton with the plugin showing the Logic-dialed-in setting?

## Progress (Logic side confirmed; Ableton side pending)

Ran the existing `extract_plugins()` against a real project (`~/.../iCloud/Logic/simple beat.logicx`, 49 plugin instances). Every plugin's embedded plist carries its own **vendor-authored, host-agnostic** state blob, not an AU-wrapper-specific one:

- **FabFilter Pro-Q 4** (`FabF`/`FQ4p`): `raw_plist['FabFilterPluginState']` = bytes starting `FFBS\x01\x00\x00\x00...` — FabFilter's own documented cross-host binary preset format (the same mechanism that lets users copy-paste FabFilter settings between unrelated DAWs today).
- **A JUCE-based plugin** (Valhalla Vintage Verb, `oDin`/`vee3`): `raw_plist['jucePluginState']` = a thin JUCE wrapper (`VC2!...`) around the plugin's own XML preset (`<?xml version="1.0"...?><ValhallaVintageVerb pluginVersio...`). JUCE's state save/restore is produced by the plugin's own code, not host-specific.
- **An Xfer plugin** (`XFER`/`XfTT`, "Init 1"): `raw_plist['vstdata']` = a classic VST2 `CcnK`/`FxCk` preset chunk — Xfer's own legacy format, wrapped identically regardless of host/plugin-API.

This is strong evidence for the "plugin-authored, not host-authored" half of the hypothesis across three different plugin architectures. It does **not** yet confirm the other half: whether Ableton's `.als` embeds this *same* blob byte-for-byte for the same plugin, or re-encodes/wraps it differently.

## Next step (blocked on Ableton install, in progress — see conversation)

Once Ableton Live is available: load FabFilter Pro-Q 4 (already confirmed present in a real session, licensed, and the cleanest case — no host-wrapper framing at all, just `FFBS...` directly) in an Ableton project, dial a couple of EQ bands to distinctive values, save, gunzip the `.als`, and find how/where the plugin's state is embedded. Compare against the `FFBS` blobs already extracted above.

## Ableton-side structure, confirmed from source (no Ableton install needed for this part)

Found `elixirbeats/abletoolz` (MIT, mature Python lib for editing/grafting Ableton `.als` sets) and used it as ground truth instead of guessing:

- `abletoolz/plugin_parsers/format_translation.py` module docstring, measured by its author on Live 12.4.5: a device is `PluginDevice > PluginDesc > {VstPluginInfo | Vst3PluginInfo | AuPluginInfo}` — "the `PluginDevice` wrapper around `PluginDesc` is byte for byte the same whichever format is inside." I independently confirmed this by diffing a real `VstPluginInfo` block (FabFilter Pro-L 2, from `abletoolz`'s `test/version_fixtures/skeletons/12.2.6.als`) against a real `AuPluginInfo` block (Apple AUBandpass, from `skeletons/11.3.41.als`) — identical `Preset > {Vst,Au}Preset` shape: `OverwriteProtectionNumber, MpeEnabled, MpeSettings, ParameterSettings, IsOn, PowerMacroControlIndex, PowerMacroMappingRange, IsFolded, StoredAllParameters, DeviceLomId, DeviceViewLomId, IsOnLomId, ParametersListWrapperLomId, Buffer, ..., PresetRef`. Only the identity fields immediately above `Preset` differ (AU: `ComponentType`/`ComponentSubType`/`ComponentManufacturer` as three separate int32 fields; VST: a single packed `UniqueId`).
- `abletoolz/plugin_parsers/base.py:136-155` (`PluginData.decode_buffer`): the `<Buffer>` element's text is **plain hex** of the raw state bytes — `bytearray.fromhex(hex_str)`, no XOR/scrambling. Whitespace/tabs in the text are purely Ableton's own line-wrapping for readability and are stripped before decoding.
- AU identity ints use the same big-endian 4-char-code packing `logic2ableton` already uses for the Logic side (`_int_to_4cc` = `struct.pack(">I", n)`), so Logic's `au_type`/`au_subtype`/`au_manufacturer` strings convert to Ableton's `ComponentType`/`ComponentSubType`/`ComponentManufacturer` with the same encoding, just inverted (`struct.unpack(">I", cc.encode("ascii"))[0]`).

**Residual unknown**: every real `<Buffer>` I could find in `abletoolz`'s fixtures was empty (`<Buffer />` — untouched default plugins). I have no ground-truth example of a *populated* buffer, so I can't rule out a small Ableton-specific header/length-prefix wrapping the plugin's own blob before hex-encoding. `decode_buffer()`'s implementation suggests there isn't one (it hex-decodes the whole thing directly), but this is inferred, not observed.

## Test artifact built

Wrote `.scratch/logic-to-ableton-fidelity/spike-artifacts/simple_beat_PLUGIN-TRANSPLANT-SPIKE.als` — a real conversion of your `simple beat.logicx` (via `logic2ableton`'s existing pipeline), with one hand-synthesized `PluginDevice > PluginDesc > AuPluginInfo` inserted into the "Signal Pad with sketchcasette" track, carrying:
- Identity: FabFilter Pro-Q 4 (`ComponentType=1635085670, ComponentSubType=1179726960, ComponentManufacturer=1180787270`, decoded from Logic's `aumf`/`FQ4p`/`FabF`)
- `<Buffer>` = the exact 2733-byte `FFBS`-prefixed state blob extracted from the real Logic project's Pro-Q 4 instance, hex-encoded

The file is well-formed XML and gzips/parses cleanly. Built with a small one-off script, not checked into the pipeline yet (this is a spike artifact, not production code).

## Test 1 result: Pro-Q 4, ambiguous (invalid test, logged for the record)

First real-Ableton test used the first `FabF`/`FQ4p` instance found project-wide (13 exist), transplanted onto whatever track happened to have the first empty `<Devices />` in the template (landed on "Deluxe Classic_bip_1_bip," which has *three* separate Pro-Q 4 inserts — no way to know which one, if any, the extracted blob corresponded to). Ableton initially reported "The Audio Unit v2 plug-in could not be found" (turned out to be AU scanning not yet enabled on a fresh Ableton install, not a problem with the file). After enabling AU + rescanning, it loaded with a visible non-default curve (a real low-cut band), but the test was invalid — no unambiguous ground truth to compare against. Superseded by Test 2.

## Test 2 result: soothe2, unambiguous, NEGATIVE — identity correct, state did not restore

Re-ran targeting `OekS`/`SthB` (oeksound soothe2) specifically because it's the **only** instance of that plugin anywhere in the 49-plugin project (no ambiguity about which insert it came from), transplanting only the inner `jucePluginState` bytes value (2718 bytes, JUCE-wrapped XML preset) into `<Buffer>`.

Result: the plugin identity resolved correctly (soothe2 loaded, right version, no "not found" error) — but the state did not restore. Every parameter differed from the Logic original (attack 1.0 vs 0.1, release "fast" vs 4.2, depth 3.0 vs 2.3, mix 100% vs 77%, curve peak ~4kHz vs ~8kHz, different band-marker layout), and decisively: Ableton's own preset-name field read **"factory default preset"**, while Logic's read **"Harsh synth"** (a real, named, non-default preset). The plugin silently fell back to its factory default rather than erroring — meaning a malformed/incomplete `Buffer` doesn't visibly fail, it just produces a quiet wrong answer, which is itself an important thing to design around later (verification, not just "does it load").

**Diagnosis**: likely over-narrow extraction. I'd only taken the one inner `jucePluginState` dict value and discarded the plist's other keys (`data`, `element-name`, `manufacturer`, `name`, `subtype`, `type`, `version`). The AU v2 `kAudioUnitProperty_ClassInfo` contract is a *whole property-list dictionary*, not an isolated vendor field — `logic2ableton`'s `extract_plugins()` also only keeps the *parsed* dict (`PluginInstance.raw_plist`), not the original raw XML-plist byte range it was parsed from, so re-serializing from the parsed dict risks losing exact structure/ordering too.

## Test 3: full raw plist bytes, byte-identical to what Logic stored (awaiting result)

Rebuilt extraction to capture the **exact original byte range** (`data[start:end]`, the literal `<?xml version...?>...</plist>` document Logic embeds) for the same soothe2 instance — 5127 bytes, the complete dict including `data`, `element-name`, `jucePluginState`, and the identity fields — hex-encoded whole into `<Buffer>`, instead of a cherry-picked or re-serialized subset. Test file: `spike-artifacts/simple_beat_SOOTHE2-SPIKE-V3.als` (copied to `~/Desktop`). Same comparison as Test 2: open in Ableton, compare soothe2's UI (preset name, attack/release/depth/sharpness/selectivity/mix, curve shape) against the "Harsh synth" instance on "Deluxe Classic_bip_1_bip" in the original Logic project.

## Test 3 result: CONFIRMED — soothe2 loaded "looks identical" to the Logic original

User confirmation, visually comparing against the "Harsh synth" preset on "Deluxe Classic_bip_1_bip" in the original Logic project.

## Answer

**Confirmed. AU ClassInfo blob transplant works**, with one correction to the original hypothesis: you must transplant the **entire original plist document** Logic stores for a plugin instance (the full `<?xml version...?>...</plist>` byte range — identity fields, vendor payload key, and any other keys like `data`/`element-name` together, byte-identical), not just the vendor-specific inner value (e.g. `jucePluginState` alone). The outer plist *is* the AU v2 `kAudioUnitProperty_ClassInfo` contract; partial reconstruction loads the right plugin but silently falls back to its factory default rather than erroring, which only surfaces as a visual/behavioral mismatch, not a load failure.

**Implementation requirement this creates for issue 04**: `logic2ableton`'s `PluginInstance`/`extract_plugins()` (`logic_parser.py`) currently discards the raw byte range after parsing it into a dict (`raw_plist` is the *parsed* dict, not the original bytes). It needs to also retain `data[start:end]` — the exact original plist bytes — per plugin instance, since that's what actually gets hex-encoded into Ableton's `<Buffer>`, not a Python re-serialization of the parsed dict (re-serializing risks altering byte-exact structure/ordering that the plugin's own state-restore code may be sensitive to).

**Generalization**: tested on one JUCE-based plugin (soothe2). The mechanism being validated (transplant the whole outer ClassInfo plist, not an inner field) is generic to the AU contract itself, not JUCE-specific — every plugin instance `extract_plugins()` finds has the same outer-dict shape (identity fields + a vendor payload key, whether that's `jucePluginState`, `FabFilterPluginState`, or `vstdata`), so this should generalize to FabFilter and Xfer plugins too, but that's inference, not re-tested per vendor. Worth a quick spot-check on at least one FabFilter instance before treating issue 04 as fully de-risked across all vendors.

**Known gap, separate from this issue**: `extract_plugins()` has no per-track/per-insert-slot association — Test 1 (Pro-Q 4) failed to even produce a valid comparison because of this (3 ambiguous instances on one channel strip). Issue 04's real implementation needs this solved (tie each extracted plugin instance to its specific channel-strip/insert-slot) to know which Ableton device slot each blob belongs to — it's not enough to transplant correctly if the pipeline can't say *which* transplant goes *where*. The container-format half of the hypothesis is now confirmed from source, not guessed: Ableton has a structurally isomorphic slot (`AuPluginInfo > Preset > AuPreset > Buffer`, plain hex, no transformation) for exactly the kind of opaque state blob Logic already extracts. Whether Ableton *accepts and correctly loads* a buffer it never wrote itself is still unverified — needs opening the test artifact above in real Ableton once installed. Report back: (a) does the file open without a corruption warning, (b) does a FabFilter Pro-Q 4 device appear on "Signal Pad with sketchcasette", (c) does its EQ curve match the same track's Pro-Q 4 in the original Logic project.

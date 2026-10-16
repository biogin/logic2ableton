# 02: Core AU state transplant, end-to-end

**What to build:** Any third-party Audio Unit plugin instance installed on both the source (Logic) and target (Ableton) machine gets transplanted into the generated Ableton project carrying its exact Logic state — not just the right plugin loaded, the real dialed-in settings — correctly placed on its originating track and insert slot using ticket 01's attribution. Anything that can't be transplanted (plugin not installed, not an AU plugin, or no AU support on this platform) falls through cleanly to the existing suggestion-only behavior rather than breaking the conversion.

This is the core deliverable of the spec: issue 01's spike (see `.scratch/logic-to-ableton-fidelity/issues/01-au-classinfo-blob-transplant-spike.md`) proved the mechanism works by hand; this ticket makes it a real, repeatable pipeline feature.

Demoable: run the converter on a real project with a third-party AU plugin, open the result in Ableton, confirm the plugin loads with the original Logic settings (not its factory default).

**Blocked by:** 01

**Status:** resolved

- [x] The parser retains each plugin instance's complete original plist byte range (not a re-serialized reconstruction of the parsed dict) — issue 01's spike found that transplanting only the vendor-specific inner value silently resets the plugin to its factory default; the full original bytes are required.
- [x] The writer synthesizes a correct `PluginDevice > PluginDesc > AuPluginInfo > Preset > AuPreset > Buffer` device for each transplantable instance, placed in its track's device chain at the right position (using ticket 01's slot attribution).
- [x] AU identity (`ComponentType`/`ComponentSubType`/`ComponentManufacturer`) is derived from Logic's 4-character codes using the existing big-endian encoding helper, not duplicated logic.
- [x] New devices allocate chain-local `Device/@Id` and any `AutomationTarget`/`Pointee` ids safely (from the set's `NextPointeeId` counter, incrementing it), with no collisions against ids already used elsewhere in the set.
- [x] A plugin not installed on the machine running the conversion falls through to the existing suggestion-only path; the conversion does not fail or crash.
- [x] A plugin that is installed but not an Audio Unit (VST3-only, or running on a platform without AU) falls through the same way (the AU registry scan finds nothing on such a platform, which is indistinguishable from "not installed" — same fallback path, no special-casing needed).
- [x] End-to-end test: converting a real project with a transplantable third-party AU plugin produces a `.als` whose `Buffer` content is byte-identical to the source plugin's original Logic plist.
- [x] Manual verification in real Ableton Live against at least one plugin instance, confirming the loaded settings visually match the Logic original (same kind of check as issue 01's spike). Done: the real `logic2ableton` CLI output (not a hand-built spike file) was opened in real Ableton Live and checked against the original `simple beat.logicx` — all 11 transplanted devices on the `Deluxe Classic_bip_1_bip` channel strip, identical to Logic, no AU "could not be found" warnings.

## Answer

**Implemented.** Three new modules plus wiring into the existing pipeline:

- `au_registry.py`: scans the standard macOS AU component directories (`/Library/Audio/Plug-Ins/Components`, `~/Library/Audio/Plug-Ins/Components`) for installed AU components by reading each bundle's `Info.plist`, exposing `au_component_installed(type, subtype, manufacturer)`. Empty/missing directories (including "no AU support on this platform" — Windows, for instance) just yield no matches, so that fallback needed no special-casing.
- `au_transplant.py`: `make_au_plugin_device()` builds the real `PluginDevice > PluginDesc > AuPluginInfo > Preset > AuPreset > Buffer` XML (via `ET.SubElement`, matching the codebase's existing style — not string templating, which issue 01's spike used as a quick prototype only). Caught and fixed a real bug here before it shipped: the device's display `Name` was initially wired to `PluginInstance.name`, which is the *preset* name ("Default Setting", "Untitled") — every transplanted device would have been mislabeled. Fixed by looking up the real product name from the existing plugin database, falling back to the plugin's own 4CC identity (e.g. `"FabF/FQ4p"`) rather than inventing a name for vendors the database doesn't cover.
- `models.py`: `PluginInstance.raw_plist_bytes` carries the exact original plist bytes (the parser now keeps `data[start:end]` instead of discarding it after parsing).
- `ableton_generator.py`: groups `project.plugins` by resolved track name (via ticket 01's `track_id`/`track_names_by_id`), sorts each track's plugins by `insert_slot`, and inserts a device per transplantable instance into the right track's device chain during the existing per-track generation loop — no new pass over the project, reuses the same `_IdAllocator` tempo/track automation already use for id safety.

**Verified end-to-end against a real project** (not just synthetic fixtures): converted a real session with an 11-plugin channel strip, and every single transplanted device's `Buffer` decoded back byte-identical to the source plugin's `raw_plist_bytes`, in the correct insert order, correctly attributed to the correct track.

Tests: `test_au_registry.py`, `test_au_transplant.py` (identity encoding, byte-exact round-trip, the preset-name bug's regression test, 4CC fallback naming, XML validity), and three generator-level tests in `test_ableton_generator.py` (installed-plugin transplant in insert order, not-installed fallback, no-captured-state fallback) plus the existing `_assert_unique_critical_ids` invariant check. Full suite: 658 passed, same 2 pre-existing unrelated VST3-scanner failures as before this work. `ruff check` clean.

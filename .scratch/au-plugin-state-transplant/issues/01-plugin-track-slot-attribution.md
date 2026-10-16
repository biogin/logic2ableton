# 01: Plugin instance → track/insert-slot attribution

**What to build:** Each plugin instance the decoder extracts from a Logic project is correctly attributed to the specific channel strip and insert position it came from — not just "this plugin exists somewhere in the project." Today `extract_plugins()` is a flat scan with no track/slot association at all, which is exactly what made the first real transplant test (three FabFilter Pro-Q 4 instances on one channel strip) impossible to validate: there was no way to know which instance a given extracted blob belonged to.

Demoable via the conversion report: for a project with multiple instances of the same plugin on one channel strip (e.g. a channel strip with three separate EQ inserts), the report lists each instance against its track name and insert position, correctly distinguishing them.

**Blocked by:** None (can start immediately)

**Status:** resolved

- [x] Each extracted plugin instance carries its owning track and insert-slot position (ordinal position in the channel strip's insert chain).
- [x] A channel strip with multiple instances of the same plugin resolves each instance to a distinct, correctly-ordered slot (verified against a real project with this pattern — e.g. the `Deluxe Classic_bip_1_bip` channel strip's three Pro-Q 4 inserts).
- [x] A channel strip with several different plugins in its chain attributes each to the right slot, in the right order.
- [x] The conversion report surfaces this attribution (track + slot per instance) so it's independently verifiable via `--report-only` without needing the writer side built.
- [x] Decoder/parser-level tests cover: a channel strip with one plugin, a channel strip with multiple instances of the same plugin, and a channel strip with no plugins.

## Answer

**No existing field or object referenced a plugin's owning channel strip — had to find the mechanism from scratch.** There's no "insert slot" object type and no id/field on the AuCO (channel strip) object pointing at its plugins. The association turned out to be purely by **file position**: each inserted plugin's embedded XML plist sits somewhere between its own channel strip's AuCO object and the next AuCO object in the file, in insert-chain order. Confirmed against a real channel strip with eleven inserts (`Deluxe Classic_bip_1_bip` in a real project) — all eleven plists landed between that strip's AuCO object and the next, in exactly the right order, cross-checked against a screenshot of the actual insert chain (Pro-Q 4, ValhallaVi, Wider, Unfiltered, Pro-Q 4, soothe2, Kickstart, Ozone Imager, Kickstart, HalfTime, Pro-Q 4).

**Implementation:**
- `LogicChannelStrip` gained an `offset` field (the strip's own AuCO object's file offset) — `None` by default, not `0`; a real early bug here filtered out a strip that was genuinely at file offset 0 in a synthetic test because `0` is falsy in Python, caught and fixed before it could cause the same silent failure on a real project with a strip at a low file offset.
- `extract_plugins()` takes an optional `mixer` argument; when given, each plugin instance's `channel_index`, `track_id` (the same Envi-id space `track_names_by_id`/placements already use), and `insert_slot` are resolved via nearest-preceding-strip-by-offset. Without a mixer, these stay `None` — existing callers and tests are unaffected.
- `parse_logic_project()` now decodes the arrangement (and its mixer) before extracting plugins, so the mixer is available; this only reordered two already-unconditional calls, no new decode pass.
- `LogicProject` gained `track_names_by_id`, needed to resolve a plugin's `track_id` to a name in the report (and will be needed by ticket 02's writer for the same reason).
- The conversion report's `PLUGINS FOUND` section now shows `(<track name>, insert <N>)` per plugin, or `(unresolved track/slot)` when attribution wasn't available.

Tests: synthetic-byte unit tests in `test_logic_parser.py` (one strip/one plugin, one strip/multiple same-plugin instances plus an empty strip, no-mixer-given), and a report-level test in `test_report.py`. Full suite: 644 passed, same 2 pre-existing unrelated VST3-scanner failures as before this work.

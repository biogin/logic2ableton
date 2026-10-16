# 04: Cross-vendor verification

**What to build:** Confirm the transplant mechanism generalizes beyond the one JUCE-based plugin verified in issue 01's spike (oeksound soothe2), by spot-checking at least one FabFilter-format (`FFBS`-prefixed) and one VST2-chunk-format (`CcnK`/`FxCk`, e.g. an Xfer plugin) instance in real Ableton. Fix any vendor-specific quirks this surfaces. The spec treats the "transplant the whole original plist, not just the inner value" finding as generic to the AU contract rather than JUCE-specific, but that's inference from one data point, not confirmed.

Demoable the same way issue 01's spike was verified: convert a real project containing a FabFilter instance and an Xfer (or similar VST2-chunk-format) instance, open the result in Ableton, and visually compare each against the Logic original.

**Blocked by:** 02

**Status:** resolved

- [x] At least one FabFilter plugin instance transplants correctly, verified visually in real Ableton against the Logic original.
- [x] At least one VST2-chunk-format (e.g. Xfer) plugin instance transplants correctly, verified the same way.
- [x] Any vendor-specific bug found is fixed, or — if a vendor's format turns out not to transplant cleanly — documented here with what breaks and why, so ticket 02's "which vendors are supported" claim stays accurate.

## Answer

**Confirmed, no bugs found.** Verified against the real `simple beat.logicx` project's " - Init - " channel strip (five plugins: Xfer Serum — an instrument, `aumu` — plus Xfer OTT, FabFilter Saturn 2, SoundToys Decapitator, and FabFilter Pro-Q 4, all effects). All five transplanted and loaded in real Ableton Live with their real settings, not factory defaults — Serum in particular showed its actual oscillator/envelope/LFO state, not an init patch, matching the original. `decide_transplant()` reported `status=transplanted` for all five independently, matching what Ableton actually showed.

This also incidentally re-confirmed FabFilter (Pro-Q 4, now correctly slot-attributed per ticket 01, unlike the ambiguous first attempt during issue 01's spike) and extended coverage to a second FabFilter plugin (Saturn 2) and a second VST2-chunk-format vendor instance (Xfer OTT, an effect, alongside Serum, an instrument) — broader than the ticket's minimum bar of one each.

One apparent discrepancy during verification turned out to be a false alarm, not a bug: the user compared against a live-edited Logic session and initially flagged a plugin (LFOTool) as missing from the Ableton output. Checked the raw project data directly — the string `LFOTool` doesn't appear anywhere in it. The Logic project's `ProjectData` file had a modification timestamp ~2.5 hours *after* the test `.als` was generated (the project was being actively edited throughout this session's testing), so the Logic session being compared against had simply changed since conversion — not an extraction gap. Worth noting as a methodology reminder for future spot-checks: compare against a Logic save made at or after the moment of conversion, not a since-edited live session.

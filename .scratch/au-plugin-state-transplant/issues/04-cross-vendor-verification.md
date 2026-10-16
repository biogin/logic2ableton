# 04: Cross-vendor verification

**What to build:** Confirm the transplant mechanism generalizes beyond the one JUCE-based plugin verified in issue 01's spike (oeksound soothe2), by spot-checking at least one FabFilter-format (`FFBS`-prefixed) and one VST2-chunk-format (`CcnK`/`FxCk`, e.g. an Xfer plugin) instance in real Ableton. Fix any vendor-specific quirks this surfaces. The spec treats the "transplant the whole original plist, not just the inner value" finding as generic to the AU contract rather than JUCE-specific, but that's inference from one data point, not confirmed.

Demoable the same way issue 01's spike was verified: convert a real project containing a FabFilter instance and an Xfer (or similar VST2-chunk-format) instance, open the result in Ableton, and visually compare each against the Logic original.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] At least one FabFilter plugin instance transplants correctly, verified visually in real Ableton against the Logic original.
- [ ] At least one VST2-chunk-format (e.g. Xfer) plugin instance transplants correctly, verified the same way.
- [ ] Any vendor-specific bug found is fixed, or — if a vendor's format turns out not to transplant cleanly — documented here with what breaks and why, so ticket 02's "which vendors are supported" claim stays accurate.

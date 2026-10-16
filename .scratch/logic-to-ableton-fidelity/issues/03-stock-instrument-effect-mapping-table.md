# 03 - Stock instrument/effect mapping table: Logic → Ableton

Status: ready-for-agent
Type: task

## What

Logic's own stock instruments and effects (ES2, Alchemy, Sampler/Quick Sampler, EXS24, Drummer, Drum Machine Designer, Channel EQ, Compressor, etc.) have no equivalent component in Ableton — they can never be "the same plugin," only approximated by Ableton's closest stock device (Wavetable, Operator, Simpler, Drum Rack, EQ Eight, Glue Compressor, ...).

This is confirmed out of scope for `logic2ableton` today (`plugin_matcher.py` only does name/category similarity for VST3 suggestions in the report; it doesn't instantiate or configure a replacement).

## Scope

1. Enumerate the Logic stock instruments/effects actually used in the project owner's own sessions (per spec.md: scoped to personal use, not a universal catalog).
2. For each, build an explicit mapping to an Ableton stock device, including which Logic parameters carry over to which Ableton parameters (accept lossy/approximate — there is no 1:1 here by construction).
3. Wire this into the conversion pipeline: when `plugin_matcher.py`'s existing identification flags a Logic stock device, instantiate the mapped Ableton device and apply the translated parameter values, instead of just emitting a suggestion in the report.
4. Anything not in the mapping table: flag in the report per spec.md's "never silently drop or fake" rule — do not fall back to guessing.

## Answer

(fill in with the actual mapping table once built, and which Logic stock devices were covered vs. deliberately left unmapped)

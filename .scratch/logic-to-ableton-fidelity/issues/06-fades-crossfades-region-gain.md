# 06 - Preserve region fades, crossfades, and region gain

Status: ready-for-agent
Type: task

## What

Confirmed gap per README: region fades, crossfades, and region gain are dropped today, so edits become plain cuts in the Ableton output.

## Scope

1. In `logic_parser.py`, read per-region fade-in/fade-out curves, crossfade regions, and gain values from the Logic project data.
2. In `ableton_generator.py`, write Ableton's native per-clip fade and gain representation for the equivalent audio clips.
3. Related, lower-priority items from the same gap list in the README — only pull in if trivial once the above is done, otherwise split into a new ticket:
   - only the first time signature is carried over (multiple time signature changes not supported)
   - tempo changes are read as steps, not curves
   - solo state and output/master channel faders aren't applied

## Answer

(fill in once implemented)

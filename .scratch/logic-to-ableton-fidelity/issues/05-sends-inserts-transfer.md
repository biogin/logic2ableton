# 05 - Transfer sends, send-only returns, and insert effects

Status: ready-for-agent
Blocked by: 03
Type: task

## What

Confirmed gap per `logic2ableton`'s README: sends, send-only returns, and insert effects are not transferred today. Mixer level/pan/mute/bus grouping already works (per the existing `ableton_generator.py` channel-strip handling) — this extends the same mixer-reading path to also capture send routing and insert chains.

## Scope

1. In `logic_parser.py`, read each channel strip's insert-effect chain (ordered list of plugin instances, which overlaps with issues 03/04's instrument/plugin mapping for the actual device translation) and send levels/routing to return tracks.
2. In `ableton_generator.py`, write Ableton's native send/return and insert-chain XML structures, using the device mapping from 03/04 for each inserted effect.
3. This depends on 03 (stock effect mapping) existing for the insert chain to produce anything meaningful — an insert slot pointing at an unmapped device should flag per spec.md's rule rather than silently drop the slot.

## Answer

(fill in once implemented)

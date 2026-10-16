---
status: accepted
---

# Auto-mute, not bounce, as the MVP fallback for a missing instrument

A full spec (`.scratch/bounce-fallback-for-missing-plugins/`) already existed for attaching a pre-rendered audio bounce as a safety net when a recipient is missing a plugin, sourced from a manual "Export All Tracks as Audio Files" pass in Logic. We rejected it as the MVP mechanism: it requires a manual precondition step before every conversion, which breaks the tool's core promise of a simple `.logicx` in → `.als` out flow, and it only matters for the Instrument Plugin case in practice — a missing Effect Plugin already degrades gracefully today (the device is simply never inserted, so the dry signal plays through) and needs no new mechanism at all.

Instead, the MVP fallback mutes the whole destination Ableton track when its Instrument Plugin can't transplant, since nothing else on that channel strip has anything to process without it. This requires no audio rendering, no manual export step, and reuses the mute mechanism the mixer-state work already built. The bounce spec is deferred, not discarded — a real option if a richer, edit-equivalent-at-the-track-level fallback is ever worth the heavier precondition.

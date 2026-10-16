# 01: Auto-mute a track when its instrument plugin can't transplant, with accurate fallback reporting

**What to build:** Converting a project where a channel strip's instrument plugin (`aumu` only, never `aumf`) can't transplant produces an Ableton track that's cleanly muted — MIDI preserved untouched — with the conversion report stating why, worded distinctly from a track already muted in the source Logic project. A channel strip with only a failing *effect* plugin (`aufx`/`aumf`) stays unmuted — it already does today, since a non-transplanted effect is simply never inserted — but the report must now name the dropped effect and confirm the rest of the chain is intact.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] A channel strip whose instrument plugin's transplant outcome is anything other than "transplanted" results in its destination Ableton track being muted, via the same mute mechanism the existing mixer-state code already writes.
- [ ] The MIDI clip/notes on an auto-muted track are completely unchanged — only the mute state differs from what would otherwise be generated.
- [ ] A channel strip whose instrument plugin transplants successfully is never auto-muted.
- [ ] A channel strip with no instrument slot, or whose only failing plugin is an effect (`aufx`/`aumf`), is never auto-muted — the track plays with that effect simply absent from the chain, same as today.
- [ ] The conversion report states, per track, when it was auto-muted due to a missing instrument (naming the plugin), in wording distinct from a track that was already muted in the source Logic project with nothing missing.
- [ ] The conversion report states, per dropped effect instance, that it was dropped and that the rest of the chain is intact — extending the existing per-instance transplant-outcome reporting, not a new mechanism.
- [ ] Tests cover all four cases from the spec's Testing Decisions: instrument fails (mute + correct report wording), instrument succeeds (no mute), effect-only fails (no mute, report names the dropped effect), and a track already muted in Logic with nothing missing (report attributes the mute to the source project, not to auto-mute).

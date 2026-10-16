# logic2ableton

A converter that carries a Logic Pro project into Ableton Live with as much of its original state intact as possible — not just audio and MIDI, but mixer state, automation, and (where the plugin is actually available) a plugin instance's exact settings.

## Language

**Logic track**:
A track object in a Logic project, as the user sees it in Logic's Arrange/Track list. Plays through exactly one Channel Strip, which is where its plugins actually live — the track object itself holds none.
_Avoid_: Track (ambiguous on its own — see Channel Strip, Ableton Track)

**Channel strip**:
The mixer object a Logic track plays through: fader, pan, mute, and its entire insert chain of plugin instances. Plugin attribution resolves to a channel strip first, then to the Logic track that plays through it.
_Avoid_: Mixer strip, track (when specifically meaning where plugins live)

**Ableton track**:
The destination a Logic track's channel strip content lands on in the generated project.
_Avoid_: Track (ambiguous on its own)

**Instrument plugin**:
An AU plugin that is a channel strip's sole sound source (type `aumu`, "Music Device"). If it can't transplant, nothing else on that channel strip has anything to process.
_Avoid_: Synth plugin (too narrow — covers samplers etc. too)

**Effect plugin**:
An AU plugin that processes a signal which exists independent of it — both `aufx` and `aumf` type plugins. MIDI-awareness (`aumf`) does not make a plugin a sound source: FabFilter Pro-Q 4, a pure EQ, is `aumf`.
_Avoid_: Processing plugin, aumf plugin, aufx plugin

**Transplant**:
Carrying a plugin instance's exact Logic state into the generated project, rather than approximating its parameters.
_Avoid_: Migration (this project never alters the source), conversion (that's the whole-project operation, not a per-plugin one)

**Transplant outcome**:
Whether a plugin instance's transplant succeeded or fell back, and why. Drives both what's written into the generated project and what the conversion report says about it — the two may never disagree.
_Avoid_: Transplant status, transplant result

**Fallback**:
What happens to a track or plugin instance when live transplant isn't possible on the recipient's machine. Two strategies: Auto-mute (the instrument case) and Bounce (a deferred, manual-export-based strategy for a richer but heavier safety net).
_Avoid_: Safety net on its own (ambiguous between the two strategies)

**Auto-mute**:
The fallback strategy for a missing Instrument Plugin: the destination Ableton track is muted automatically, distinct from a track already muted in the source project. The MIDI performance is preserved, not deleted.
_Avoid_: Silencing, disabling (too generic — doesn't say why)

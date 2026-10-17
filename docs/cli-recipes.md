# CLI recipes

Less common flows, pulled out of the README's Quick Start so that one stays short. See [CLI Options](../README.md#cli-options) for every flag.

Logic to Ableton for a SMPTE-synced live show: infer the timecode hour, keep the sync and pilot tracks from stretching, and apply a tempo map with markers:

```bash
logic2live "Song.logicx" --output ./out --smpte-start auto --keep-unwarped "LTC*" --keep-unwarped "Pilot*" --timeline timeline.json
```

Write the mixer read from a Logic project to a JSON file you can edit, then convert with your edited values (tracks and fields you leave out keep what Logic has):

```bash
logic2live "MySong.logicx" --output ./output --generate-mixer-template --report-only
logic2live "MySong.logicx" --output ./output --mixer ./output/mixer_overrides.json
```

Keep the interface outputs of a playback rig, so a click on outputs 11-12 in Logic is on Ext. Out 11/12 in Live:

```bash
logic2live "MySong.logicx" --output ./output --keep-outputs
```

Emit JSON progress for app or automation integration:

```bash
logic2live "MySong.logicx" --output ./output --json-progress
ableton2logic "MySet.als" --output ./output --json-progress
```

Progress events report audio counts (`tracks`, `clips`, `audio_files`) separately from `midi_tracks` and `midi_notes`. Previews include recovered MIDI content. For Ableton output, the completion event's `midi_tracks` counts native tracks in the set; `midi_files` separately counts exported `.mid` sidecars.

A failed run ends with an `error` event whose `failure_stage` names the step that failed (for example `timeline`, `parsing` or `generating`) and whose `error` holds the reason. The saved report keeps any analysis already done and ends with the same stage and reason.

Pro Tools previews check referenced audio on disk. The report lists found, missing, and skipped sources, and `compatibility_warnings` names missing media before conversion begins. These notes also appear in the desktop preview.

## Timeline JSON

`--timeline` supplies your own tempo map and/or markers in place of the ones read from the Logic project. Tempo entries in the file replace the project's tempo changes; markers in the file replace the project's markers. Whatever the file leaves out is still taken from the project:

```json
{
  "tempo": [{"bar": 9, "bpm": 132}],
  "markers": [{"bar": 9, "name": "Chorus"}]
}
```

Each `tempo` or `markers` entry needs a position: either a 1-based `bar` with an optional 1-based `beat` (defaults to 1), or an absolute `beats` value counted in quarter notes from bar 1 (so bar 1 is `0`). Give one or the other, not both. Bar and beat positions are resolved against the Logic project's own base time signature. Tempo changes are steps, not ramps: each breakpoint holds its BPM until the next one, and the report's `TIMELINE` section, the Live tempo automation, and the clip warp markers all follow that same map.

## Reverse import strategy (Ableton to Logic)

For `ableton2logic`, the cleanest path is:

1. Import `Logic Timeline/Logic Timeline.mid` into a new empty Logic project at the project start.
2. Drag every file from `Track Stems/` into Logic starting at bar 1.
3. If you need clip-level editing, import `Audio Files/` and use Logic's `Edit > Move > To Recorded Position` command on timestamped WAV clips.
4. Use the transfer report and `timeline_manifest.csv` to review warped clips, copied-source files, and any manual cleanup.

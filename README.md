# logic2live

**Move a Logic Pro project into Ableton Live without re-dialing every plugin.** Your third-party plugins open in Live with the exact settings you left them at in Logic — not factory defaults — alongside your audio, MIDI, tempo, mixer, and volume/pan automation.

> logic2live is a fork of [logic2ableton](https://github.com/Evilander/logic2ableton) built around Logic → Ableton fidelity. The `logic2ableton` package on PyPI and its desktop app are the **original** tool: they don't include anything under [What this fork adds](#what-this-fork-adds).

## Install

Requires Python 3.11+. Plugin-state transplant needs macOS (see [below](#what-this-fork-adds)).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install git+https://github.com/biogin/logic2live.git
```

Don't install it into the same environment as the original `logic2ableton` package: both ship a Python module of the same name and would overwrite each other. A fresh virtualenv, as shown above, avoids that.

## Use

```bash
logic2live "MySong.logicx" --output ./output
```

Open `output/MySong Project/MySong.als` in Live, then read `output/MySong_conversion_report.txt`: it lists every plugin instance and whether its state carried over, and for each track it explains why it was muted, if it was.

Add `--report-only` to see the report without writing a project. Pass several `.logicx` paths to batch-convert.

## What this fork adds

Every paid cross-DAW converter we've found (AATranslator, Jukeblocks, WG DAW Converter) makes you reload and reconfigure every plugin by hand. This fork doesn't:

- **Plugin state transplant.** A third-party Audio Unit's saved state is copied into the Live set byte-for-byte and placed on the right track at the right position in the insert chain. Verified in Ableton Live 12 with FabFilter, iZotope, Xfer, and JUCE-based plugins (e.g. soothe2). This works for any plugin installed on the Mac you run the conversion on, and it will load wherever that same plugin is installed.
- **Volume and pan automation** carried over from Logic.
- **Fallbacks you can see.** If a track's instrument can't be transplanted, the track is muted in Live instead of failing silently, and its MIDI is kept untouched. Logic's own stock instruments (ES2, Alchemy, Sampler, ...) are detected the same way. If an effect can't be transplanted, it's dropped, and the report names it and confirms the rest of the chain is intact.
- **A per-plugin report.** For every plugin instance it says *transplanted* or *fell back*, plus the reason: plugin not installed / not an AU, or no Audio Unit support on this platform.

**Platform:** transplant needs macOS. On Windows the conversion still runs, but every third-party plugin falls back to the original tool's VST3 suggestions only.

## What carries over

**Carries over:** audio and note-accurate MIDI on the timeline, tempo and time-signature changes, track colors, markers, the mixer (level, pan, mute, bus groups), volume and pan automation, third-party AU plugin state.

**Doesn't yet:** Logic's stock instruments and effects aren't converted to Live equivalents. Tracks using a stock instrument are auto-muted, but the report can't name the instrument. Also not yet: sends and aux-only buses, fades/crossfades/region gain, plugin-parameter and mute automation, master/VCA faders.

Methodology and exact tolerances: [docs/conversion-fidelity-details.md](docs/conversion-fidelity-details.md). How Logic's undocumented format was decoded: [docs/reverse-engineering-logic-pro-midi.md](docs/reverse-engineering-logic-pro-midi.md).

## Useful options

| Option | What it does |
| --- | --- |
| `--output`, `-o` | Output directory |
| `--report-only` | Write the report only, no project |
| `--alternative`, `-a` | Which Logic project alternative to convert |
| `--no-copy` | Reference the original audio files instead of copying them |
| `--mixer` / `--no-mixer` | Override mixer values from a JSON file / reset every track to 0 dB, centred, unmuted |
| `--generate-mixer-template` | Write `mixer_overrides.json` with the values read from Logic |
| `--keep-outputs` | Keep tracks routed to other interface outputs on the same outputs in Live |
| `--smpte-start` | SMPTE time at bar 1 (default `01:00:00:00`, or `auto`) |
| `--keep-unwarped` | Track-name glob (repeatable) for tracks to leave unwarped, e.g. sync/timecode |
| `--timeline` | Supply your own tempo map and/or markers as JSON |
| `--template` | Use a specific `DefaultLiveSet.als` |

Run `logic2live --help` for everything. Less common flows (SMPTE-synced live shows, mixer JSON, JSON progress output) are in [docs/cli-recipes.md](docs/cli-recipes.md).

## Output

```text
output/
  MySong Project/
    MySong.als
    Samples/Imported/
    MIDI/01 - MIDI 1.mid
  MySong_conversion_report.txt
```

A name collision gets a `(2)` suffix — nothing is overwritten.

## Inherited from the original tool

The install also includes the original tool's other conversion directions, **unchanged by this fork**: `ableton2logic`, `protools2ableton`, `protools2logic`, `ableton2protools`, `logic2protools`. They move audio, MIDI and timeline data but no plugin state or devices. They're documented in the [upstream README](https://github.com/Evilander/logic2ableton#readme), and bugs in them belong [upstream](https://github.com/Evilander/logic2ableton/issues).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for running tests.

## License

MIT — see [LICENSE](LICENSE). Original work © 2025 evilander; fork changes by biogin.

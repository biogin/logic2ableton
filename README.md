# logic2ableton

[![PyPI version](https://img.shields.io/pypi/v/logic2ableton)](https://pypi.org/project/logic2ableton/)
[![Python 3.11+](https://img.shields.io/pypi/pyversions/logic2ableton)](https://pypi.org/project/logic2ableton/)
[![License: MIT](https://img.shields.io/pypi/l/logic2ableton)](https://github.com/Evilander/logic2ableton/blob/master/LICENSE)

**Convert a Logic Pro project into a real, working Ableton Live set.** Reads Logic's undocumented `.logicx` format and rebuilds your project in Live: audio on the timeline, note-accurate MIDI, tempo, mixer settings, and real third-party plugin state.

```bash
pip install logic2ableton
logic2ableton "MySong.logicx" --output ./output
```

No Logic or Ableton installation needed to run the converter. Prefer a GUI? Grab the [desktop app](https://github.com/Evilander/logic2ableton/releases/latest) — drag a session file in, pick a destination, go.

The same install also ships Ableton↔Logic↔Pro Tools conversion in the other directions, documented further down — but Logic → Ableton is the primary focus here.

> Logic's and Pro Tools' session formats are undocumented and had to be reverse-engineered: [how Logic's MIDI was decoded →](docs/reverse-engineering-logic-pro-midi.md) · [how Pro Tools' session container was decoded →](docs/reverse-engineering-pro-tools-sessions.md)

## What makes Logic → Ableton different

Every paid cross-DAW converter we could find (AATranslator, Jukeblocks, WG DAW Converter) explicitly does not carry plugin state across — you reload and reconfigure every plugin by hand. This one transplants a third-party Audio Unit's exact saved state, byte-for-byte, whenever that plugin is installed on the machine opening the set. Verified in real Ableton Live 12 with FabFilter, iZotope, Xfer, and JUCE-based plugins.

It's not everything — see [known gaps](#logic--ableton-what-works--known-gaps) below, especially Logic's own stock instruments.

## Logic → Ableton: what works / known gaps

Every run writes a report explaining exactly what transferred, what needs a manual check, and why — read it first if anything looks off.

**Works**: audio + MIDI on the timeline, tempo/time signature, track colors and markers, mixer (level/pan/mute/bus groups), volume & pan automation, third-party AU plugin state byte-for-byte, and honest fallbacks — a track is auto-muted rather than left silently broken when its instrument can't transplant.

**Known gaps**: Logic's own stock instruments (ES2, Alchemy, Drummer, ...) aren't identified yet — the track is auto-muted, but the report can't say which instrument is missing; sends and aux-only buses; fades/crossfades/region gain; plugin-parameter and mute automation; master/VCA faders.

**→ Full validation methodology and exact tolerances:** [docs/conversion-fidelity-details.md](docs/conversion-fidelity-details.md)

## Other directions (same install)

The package also ships five other conversion directions, each with its own report:

| Command | Input → Output |
| --- | --- |
| `ableton2logic` | Ableton `.als` → Logic import package (stems, MIDI, timeline) |
| `protools2ableton` | Pro Tools `.ptx` → Ableton `.als` + MIDI |
| `protools2logic` | Pro Tools `.ptx` → Logic import package |
| `ableton2protools` | Ableton `.als` → Pro Tools import package |
| `logic2protools` | Logic `.logicx` → Pro Tools import package |

`logic2ableton` also auto-detects `.als` and `.ptx` input. None of these recreate plugin state or devices — they move audio, MIDI, and timeline metadata, and Pro Tools' tempo is assumed (120 BPM default, pass `--tempo`) since `.ptx` doesn't expose it. Full detail: [docs/conversion-fidelity-details.md](docs/conversion-fidelity-details.md).

## Install

| Method | Command / Link | Description |
|--------|----------------|-------------|
| **PyPI** | `pip install logic2ableton` | CLI tool, any platform with Python 3.11+ |
| Windows | [Installer / Portable](https://github.com/Evilander/logic2ableton/releases/latest) | Desktop app |
| macOS (Apple Silicon) | [DMG](https://github.com/Evilander/logic2ableton/releases/latest) | Desktop app, macOS 12+ (separate DMG for macOS 11) |

Desktop app notes:

- macOS builds are ad-hoc signed, not notarized — Gatekeeper quarantines them on first download. Fix once: `xattr -dr com.apple.quarantine "/Applications/Logic Ableton Transfer.app"`, or right-click the app and choose **Open**.
- Intel macOS needs a source build; release DMGs are Apple Silicon only.
- The app bundles the converter binary, so end users don't need Python installed.

## Quick Start

**Desktop**: launch the app, drop a session file (`.logicx`, `.als`, `.ptx`) in, pick the destination DAW, run, check the report if anything looks off.

**CLI**:

```bash
logic2ableton "MySong.logicx" --output ./output
```

Batch convert: pass multiple paths — `logic2ableton "Song1.logicx" "Song2.logicx" --output ./output`.

The other five directions use the same pattern with their own command (`ableton2logic`, `protools2ableton`, `protools2logic`, `ableton2protools`, `logic2protools` — see [Other directions](#other-directions-same-install) above); `logic2ableton` itself also auto-detects `.als` and `.ptx` input.

Preview without writing output: add `--report-only`.

Less common flows (SMPTE-synced live shows, mixer override JSON, `--keep-outputs`, JSON progress for automation, the timeline JSON format) are in **[docs/cli-recipes.md](docs/cli-recipes.md)**.

## CLI Options

Every lane's input argument accepts one or more paths; pass several to convert each in turn.

### Shared

| Option | Description |
| --- | --- |
| `--version`, `-V` | Show version |
| `--mode` | Force any of the six lane names |
| `--output`, `-o` | Output directory |
| `--report-only` | Write the transfer report without generating output files |
| `--no-copy` | Don't copy audio; generated output references the original files |
| `--json-progress` | Emit JSON progress lines for GUI or automation use |

### Logic to Ableton only

| Option | Description |
| --- | --- |
| `--alternative`, `-a` | Logic alternative index (also on `logic2protools`) |
| `--template` | Use a specific `DefaultLiveSet.als` (also on `protools2ableton`) |
| `--vst3-path` | Override the VST3 scan directory |
| `--mixer` | JSON file of level/pan/mute/solo per track, overriding what Logic has |
| `--no-mixer` | Leave every track at 0 dB, centred and unmuted, with no groups |
| `--generate-mixer-template` | Write `mixer_overrides.json` with the values read from Logic |
| `--keep-outputs` | Route tracks that play to another interface output in Logic to the same output in Live |
| `--smpte-start` | SMPTE time bar 1 plays at (default `01:00:00:00`; `auto` infers one) |
| `--keep-unwarped` | Track-name glob (repeatable); matching tracks are written unwarped |
| `--timeline` | JSON file with a tempo map and/or markers, in place of the project's own (see [cli-recipes.md](docs/cli-recipes.md)) |

### Pro Tools imports only

| Option | Description |
| --- | --- |
| `--tempo` | Tempo (BPM) used to convert sample positions to beats; `.ptx` doesn't expose its tempo yet (default 120) |

## Output Layout

Each conversion creates a fresh project or transfer folder; a name collision gets a `(2)` suffix.

```text
output/
  MySong Project/
    MySong.als              <- Logic/Pro Tools -> Ableton
    Samples/Imported/
    MIDI/01 - MIDI 1.mid
  MySong_conversion_report.txt
```

```text
output/
  MySet Logic Transfer/      <- Ableton -> Logic
    Track Stems/
    Logic Timeline/Logic Timeline.mid
    MIDI Tracks/
    Audio Files/
    timeline_manifest.json / .csv
    locators.csv
    IMPORT_TO_LOGIC.md
```

```text
output/
  MySet Pro Tools Transfer/  <- Ableton/Logic -> Pro Tools
    Audio Files/             (BWF TimeReference stamped for Spot > Original Time Stamp)
    MIDI/
    manifest.json
    IMPORT GUIDE.txt
```

## Reading The Reports

Every Logic to Ableton report opens with the SMPTE start it used and whether it found the project's audio in a package or folder-style layout. Pay close attention to `COMPATIBILITY WARNINGS` — they mean either the converter needs an improvement, or the source session needs manual cleanup or a more deliberate export/import path.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for running tests, building the desktop app, and the release process.

## Bug Reports

Open issues at https://github.com/Evilander/logic2ableton/issues with: the Logic/Ableton version used to save the project, the exact generated report, and a minimal failing project if one can be shared.

## License

MIT

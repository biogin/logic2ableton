# Conversion fidelity: full details

The README keeps a short "what works / known gaps" summary per lane. This doc is the long version: exact validation methodology, tolerances, and edge cases, for anyone deciding whether a specific project will convert cleanly.

## Logic to Ableton

### What works

- Audio tracks into Ableton Arrangement View
- Region placement read from the Logic project itself: audio regions land where Logic had them, trimmed to the same slice of their file, on tracks named after the Logic tracks; older saves the decoder cannot read fall back to WAV BWF timestamps and Logic AIFF `MARK` chunks
- Tempo and time signature. Tempo changes are read from Logic's tempo track and become Live tempo automation; warped clips get a warp marker at each change, so the audio keeps its speed and its place (checked on a project with 85 tempo changes by opening the set in Live 12 and reading the tempo back)
- Overlap resolution for takes and comp bounces
- Audio membership follows the selected Logic alternative; unused and unreferenced takes are excluded
- Distinct per-track colors, with arrangement clips matching their track color
- MIDI regions decoded from Logic's binary project data land as native Ableton MIDI tracks inside the `.als` (and as Standard MIDI file exports): one clip per region at its arrangement position, and looped Logic regions become looping Live clips
- Logic markers become Live locators; muted regions are left out, as Logic would not play them
- `--smpte-start` sets the SMPTE time bar 1 plays at (or infers it with `auto`), for projects whose placement comes from audio timestamps
- `--timeline` supplies your own tempo map and/or markers in place of the ones read from the project; they become Live tempo automation, locators, and warp markers that follow the map (verified by opening the generated set in Live 12.4.3 and reading back its values)
- `--keep-unwarped` keeps matching tracks (sync tone, pilot tracks, timecode) as unwarped Live clips so they never stretch when the tempo changes
- Folder-saved Logic projects (a `.logicx` package next to a sibling `Audio Files` folder) are read the same as package-saved ones
- Multiple `.logicx` inputs in one run, converted and reported one after another
- The mixer: every track gets the level, pan and mute its channel strip has in the Logic project, audio and MIDI tracks alike. Where tracks play into a bus that an aux channel listens on (a drum bus, a summing stack), the aux becomes a Live group track with its level, pan and mute and those tracks inside it, so a bus fader still acts on the tracks that play through it. What the converter reads was compared with the pictures of its window that Logic saves inside each project: the mute buttons on the track headers and the levels, pans, bus and output assignments on the channel strips, more than 300 strips and headers in 23 project versions, after the six it was worked out on. They agree to within the 0.1 dB by which Logic rounds the levels it shows. Three converted sets opened in Live 12 showed the same level, pan, mute and group for all 76 of their tracks and groups. `--mixer` changes the values of the tracks named in a JSON file, and `--no-mixer` leaves every track at 0 dB, centred and unmuted
- `--keep-outputs` sends tracks that play to another output of the audio interface in Logic (3-4, 5-6, a mono output) to the same output in Live
- Plugin identification with VST3 suggestions in the report
- Volume and pan automation: a track's authored breakpoint curves for these two parameters become real Live automation envelopes, not a single static value frozen at save time (verified by opening the generated set in Live 12.4.3 and reading the curve back)
- Third-party Audio Unit plugin state transplant: when a plugin instance's saved state was captured in the Logic project and that plugin is installed as an AU on the machine opening the set, its exact state is written into the Live set byte-for-byte — the plugin opens already configured with its original settings, not Live's default. Verified in real Ableton against real third-party plugins (FabFilter, iZotope, Xfer Serum/OTT, several JUCE-based plugins) across multiple real projects
- Transplant outcome reporting: a report section names every plugin instance found and says plainly what happened to it — transplanted, not installed on this machine, no state was captured for it, or (Windows/Linux) this platform has no AU support
- Instrument auto-mute fallback: if a channel strip's one instrument plugin was identified but its state couldn't transplant (not installed, no captured state, unsupported platform), or if the strip is instrument-typed but no instrument plugin was extracted at all, the destination track is muted automatically instead of being left in Ableton's default broken-device silence, and the report names the track and the reason

### Known gaps

A session file over 1 GiB (a Live set counts at its decompressed size), or one whose loops would unroll into more than 2 million notes or clip repetitions, stops with a message instead of converting. Project metadata and media reached through a symlink or junction inside the project folder are blocked before reading; copy those files into the project folder first.

- MIDI notes transfer as native MIDI tracks (and `.mid` exports). A *third-party* AU instrument with captured state transplants as described above when it's installed on the machine opening the set; otherwise the report says so and the track is auto-muted rather than left silently broken. Logic's own stock instruments (ES2, Alchemy, Sampler, Drummer, and the rest) are a separate, currently open gap: they don't serialize their state the way third-party AU plugins do, so today they are **not identified** — the track is auto-muted (confirmed against real projects in this fork — every note-bearing stock-instrument track sampled showed this), but the report can't say which instrument is missing, only that one is. Reload those instruments manually in Ableton; MIDI effects are not recreated either way
- Region placement, loops, track names and markers come from the project's own arrangement data. That decoding was worked out on Logic 10.6 and Logic 11 saves and has since decoded all 246 saved versions of 117 projects without falling back (their latest saves come from Logic 10.2, 11.1, 11.2, 12.2 and 12.3; only the mixer part of those was compared with Logic). The report says "Region positions: read from the Logic arrangement" when it applies. Saves it cannot read fall back to audio timestamps, `MIDI 1`, `MIDI 2`, ... track names, and a warning
- Regions that start before bar 1 are moved to bar 1 (audio is trimmed by the same amount) because a Live arrangement cannot start earlier
- Looped audio regions are written as repeated clips; the report lists every region it unrolled
- Logic tracks that share a name are kept apart by numbering the later ones (`Guitar`, `Guitar (2)`), and the report says which were renamed
- A Live track plays one clip at a time. Where audio regions overlap on one Logic track, the later region is kept whole and the earlier one is cut around it; overlapping MIDI regions become one clip holding all their notes. The report lists each case. No real project with overlapping regions has been checked yet, so compare those spots with Logic
- Region fades, crossfades and region gain are not transferred, so edit points are plain cuts in Live. A take folder plays its comp, or its active take, read from the project where the folder sits; the report names those tracks so you can compare them with Logic. Flattening take folders in Logic first is the safer route
- Only the first time signature is carried over. Every project seen so far has one; if a project changes meter, regions, markers and tempo still land on the right beat, but Live's bar lines and the bar numbers in the report follow the first meter, and the report says so
- Tempo changes are read as steps, which is how the projects seen so far store them. Logic also stores the time each change falls on; if the steps do not add up to those times (a tempo curve, for example) the report says so. The Live set starts at bar 1, so a different tempo before bar 1 (a count-in, say) only decides how much of the audio that starts there is trimmed. Tempos outside Live's 20 to 999 BPM range are limited to it
- When the arrangement cannot be read and placement falls back to audio timestamps, Logic's tempo changes are reported but not applied; supply them with `--timeline`
- `--smpte-start` only matters for the timestamp fallback; it must then match the project's own synchronization setting (default `01:00:00:00`), and the report lists any files placed at bar 1 because their timestamp precedes it
- Volume and pan automation is read and recreated as real Live envelopes. Everything else is not: plugin-parameter automation, send-level automation, and mute automation are not read, so a track automated that way plays at whatever static value its parameter had when the project was saved
- Mixer values not covered by volume/pan automation are the ones the project was saved with. Solo is not carried over: when a project was saved with a solo on, the tracks that solo silenced play in Live, and the report names them and the soloed tracks. Levels were compared with what Logic shows between +2.9 and -27.1 dB. Below 0 dB Logic shows a level that sits between two of its 0.1 dB steps as the lower one, so such a fader reads 0.1 dB lower there than in the report (-6.0 in Logic, -5.9 here). Live shows pan as 50L to 50R where Logic counts -64 to +63
- Sends are not recreated, and neither are aux channels fed only by sends (reverb and delay returns). A bus that no aux channel listens on, or that several do, is left ungrouped and the report says so. The faders of Logic's output channels and its master fader are not applied, nor are the level and mute of a folder stack or a VCA fader, and a track muted in Logic's CPU-saving mute mode may not be seen as muted. A group is named after its aux channel, which is not always the name the stack shows in Logic
- Tracks play to Live's main output unless `--keep-outputs` is given. With it, a track whose output the current audio device does not have shows no output channel in Live and stays silent until you choose one
- Plugin state transplants for a *third-party* AU plugin instance when it was captured in the Logic project and is installed as an AU on the machine opening the set; the report names every other instance and why it didn't (not installed, no state captured, or an unsupported platform). An inserted-but-unconfigured plugin device still occupies the right slot in the chain, so insert order is correct even where state couldn't follow. VST3/AAX-only plugins, and plugins run through a wrapper Logic's AU scan doesn't see, are identified in the report but not transplanted
- In the timestamp fallback, imported audio without embedded timestamps defaults to bar 1
- Media outside `Media/Audio Files` is not copied automatically
- WAV duration detection includes IEEE float recordings. Sources whose duration cannot be read are skipped with a report warning

## Ableton to Logic

### What works

- Audio-track and clip discovery from `.als`
- MIDI-track and arrangement note extraction, exported as importable Standard MIDI files
- Tempo, locators, and a documented base time signature
- Logic-ready transfer package with `Track Stems/`, `Logic Timeline/Logic Timeline.mid`, `MIDI Tracks/`, `Audio Files/`, manifests, an import guide, and a saved transfer report

### Known gaps

- The reverse lane does not synthesize a native `.logicx` package
- MIDI note data transfers, but instruments, devices, racks, MIDI effects, and plugin state do not — reload those in Logic
- Looping MIDI clips are unrolled to their arrangement length, honoring the loop brace and start marker the way Live plays them (verified against Live 12.4's own Consolidate output); notes cut at a loop or clip boundary are shortened, not extended
- Ableton devices, racks, plugin state, and return-bus processing are not transferred
- Audio renders include saved track mute and volume plus clip gain. Muted tracks and children routed through muted groups render silence; undecodable muted sources are not copied. Keep destination track faders at unity. Recreate pan, group volume, mixer automation and solo state from the manifest and report. MIDI files retain notes and require destination mute and mixer settings after import
- Warped clips are exported with best-effort timing, but they still need review inside Logic before delivery
- The base tempo, meter, and markers are exported into the Logic Timeline MIDI file. Later tempo and meter changes are reported but are not reconstructed
- Non-PCM sources that cannot be rendered to timestamped WAV in-process are copied as references and flagged in the report/manifest
- Media references outside the Ableton project folder are blocked. Use Live's Collect All and Save before transferring a set that relies on external files
- PCM and float audio are rendered in chunks. Individual rendered WAVs are limited to the RIFF format's 4 GiB size limit
- Float audio stays float, written as 32-bit float WAV (64-bit sources too), so levels above full scale survive. A track stem whose clips overlap, or that mixes float and integer files, is also 32-bit float; 32-bit integer sources on such a stem keep 24 bits. Some older Logic versions do not import float WAV files
- The transfer package covers audio and MIDI; use the stems and MIDI files first, then clip exports and the manifest if you need finer reconstruction

## Pro Tools lanes

### What works

- Reads `.ptx` sessions directly (Pro Tools 10 through current `.ptx` saves, plus legacy `.pts`), including the XOR-obfuscated container
- Audio clips with their exact source trims (a clip that plays 8.6 s from the middle of a take stays that clip), placed at their session positions
- Stereo tracks reassembled from Pro Tools' per-channel lanes
- MIDI notes decoded from the session and created as native Ableton MIDI tracks or Logic-importable MIDI files
- Session sample rate and format version detection
- Crossfade render files are recognized and skipped so they don't appear as phantom clips
- Pro Tools import package with per-track folders of timestamped WAV clip exports, BWF `TimeReference` stamped for Spot > Original Time Stamp, one Standard MIDI file per MIDI track, a manifest, report, and import guide

### Known gaps

- **Session tempo is not recoverable from `.ptx` yet.** Audio positions are sample-exact regardless, but beat positions are computed at an assumed tempo (default 120 BPM, override with `--tempo`). Keep the destination set at that tempo, or pass the real session BPM
- Pro Tools source plugins, inserts, sends, automation, clip gain, and fades are not transferred; crossfade renders are skipped. Ableton audio exports include saved mute, track volume, and clip gain; their pan and mixer automation still need reconstruction
- Elastic Audio state is not reconstructed; clips reference their source audio directly
- The source session's `Audio Files/` folder must sit next to the `.ptx` for media to be copied
- Split-mono sources remain on separate left/right tracks. Live tracks are hard-panned; rendered transfer WAVs put each mono source in its original stereo channel. Interleaved stereo sources remain on one track
- MIDI regions anchor to their first note (a leading-silence offset inside a region is not preserved)

If a project lands imperfectly, the first thing to inspect is the generated report. It is the primary support artifact for this project.

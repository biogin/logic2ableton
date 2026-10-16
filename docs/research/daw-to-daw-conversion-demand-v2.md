# Research v2: Is DAW-to-DAW project conversion a real, recurring pain point? (deeper/broader pass)

> Produced by a second research pass, commissioned specifically to close v1's disclosed gaps: the inaccessible Reddit evidence, the unchecked DAW-survey PDF lead, and v1's narrow Logic↔Ableton-only scope. Run by a different agent/session than this repo's usual working session; pasted in and saved here verbatim in substance, lightly reformatted. See `daw-to-daw-conversion-demand.md` (v1) for the original pass this supersedes/extends, not replaces.

## 1. Reddit evidence (v1's biggest gap — now closed)

v1 could not surface any reddit.com results due to a tooling limitation, not absence of discussion. This pass found real threads in all five requested subreddits (r/Logic_Studio, r/ableton, r/edmproduction, r/musicproduction, r/WeAreTheMusicMakers).

| Community | Thread | Issue | Weight |
|---|---|---|---|
| r/Logic_Studio | [Transfer Logic project to Ableton, Mar 2023](https://www.reddit.com/r/Logic_Studio/comments/11mrsjg/) | Wants tempo/automation carried over | Direct ask, ambiguous willingness to pay |
| r/ableton | [Migrate full album Ableton→Logic, 2026](https://www.reddit.com/r/ableton/comments/1qxvsy6/) | Asks if MIDI carries instrument/VST settings; replies cite loss of effects/automation | Strong pain signal + a nonpurchase counterexample (issue got resolved another way) |
| r/ableton | [Cubase→Ableton, Mar 2024](https://www.reddit.com/r/ableton/comments/1b9kqcz/) | Unfinished old songs to complete in Live | Weak proof of full-fidelity need — audio/MIDI may suffice |
| r/edmproduction | [DAW file converter — does it exist? Is it needed?, Aug 2023](https://www.reddit.com/r/musicproduction/comments/165zg71/) | Community debates usefulness; dissenters say stems work | Market hypothesis asked publicly, not organic demand |
| r/WeAreTheMusicMakers | [Moving auxes/sends across DAWs, Sep 2021](https://www.reddit.com/r/WeAreTheMusicMakers/comments/pikyx7) | Logic→Pro Tools user wants sends/mixer behavior carried to mix stage | **Strongest single piece of evidence found**: specific need beyond stems |
| r/WeAreTheMusicMakers | [Collaborating across different DAWs, Apr 2020](https://www.reddit.com/r/WeAreTheMusicMakers/comments/g38sg1/) | Workaround is stems/audio export + new bounces per revision | Recurring friction, but also evidence stems are an accepted workaround |

**Caveat the research is explicit about**: this is purposive discovery, not systematic sampling. Vendor/demo-post threads and reposted conversations are flagged as not independent organic demand. Thread-level anecdotes still can't establish frequency, unique-user counts, or willingness to pay.

## 2. Broader than Logic↔Ableton — confirmed

Real threads found for Cubase↔Ableton, FL Studio↔Ableton (both directions, including a 2020 bandmate-collaboration case and a 2021 live-performance case), Logic→Pro Tools, REAPER↔Pro Tools, and Cubase legacy-format archival. One explicit counterexample included (Cubase→Ableton live playback via stems — ordinary stems sufficed).

**Medium-high confidence conclusion**: the underlying problem is cross-DAW generally, not a Logic/Ableton-specific quirk — but desired completeness varies sharply by persona (songwriter wants editable MIDI+synths; mix engineer wants automation+buses; archivist wants the project merely recoverable; live performer may need audio-only). The research explicitly warns against treating these as one monolithic market.

## 3. The University of Milan DAW survey (v1's other open lead) — checked, does not help

613 respondents, SMC 2025 poster, Italian/SMC-recruitment bias. Confirmed: it measures DAW *adoption* (which software people use), not project *migration* frequency. **Cannot** be used to estimate what fraction of producers need cross-DAW conversion per year — that variable isn't in the questionnaire. No other survey found (Production Expert ~2,500 respondents, Soundplate, PlaybackPilot, MIDiA, Grand View Research market sizing) fills this gap either — all measure adjacent things (DAW usage, remote collaboration rate, general production friction, market dollars), none measure migration incidence.

**No responsible TAM estimate exists.** The research proposes a denominator instead: "users with at least one project needing continued editing in another DAW in the last 12 months," then what fraction needed more than stems, what fraction could self-serve, what fraction would pay — none of which is answered yet.

## 4. Competitors — v1 undercounted these

New, not in v1:
- **AATranslator** — established paid session translator, $79 (Standard) / $249 (Pro Tools/AAF/OMF edition). **Its own documentation states it does not convert plugins/FX or MIDI.**
- **Jukeblocks Converter** — commercial FL Studio↔Ableton, €4.99 per conversion. Documents *selected* plugin translation, AU/VST limitations, and automation as "experimental." Logic/Pro Tools directions are waitlisted, not shipped.

Already known from v1, re-confirmed: DawVert (open source, broad format coverage, no independent fidelity benchmark), DAWproject (Steinberg's Cubase 15 manual now explicitly documents DAWproject interchange with VST3-dependent plugin handling), WG DAW Converter (KVR vendor thread, $49-99, real support exchange consistent with a paying customer, not audited sales data).

**The important implication for this repo specifically**: every competitor found either explicitly doesn't touch plugin state, or treats it as experimental/partial. None of them do what this session actually built — byte-identical AU `ClassInfo` state transplant, verified in real Ableton against real plugins. That's a real differentiator if it holds up outside this one evaluation machine, not yet validated against outside users.

## 5. A pointed caution about this project specifically

The research flagged something worth taking seriously: it evaluated this repo's **README**, which still describes the pre-this-session state ("Automation is not recreated," "Plugin parameters are not recreated"). It explicitly says: *"a demonstrable demand for plugin-state migration is not evidence that this repository already fulfills it... source-code behavior and uncommitted work were not independently benchmarked."*

That's a fair catch from the research's point of view — it had no way to know what's actually been built and tested in this session (real plugin transplant, automation transfer, instrument auto-mute, all verified against real projects in real Ableton). But it's also a concrete, actionable note: **the README is now stale relative to what the code does**, which matters both for anyone else evaluating this project from the outside and for an honest read of "is the value prop actually delivered yet."

## 6. Verdict (compared to v1)

**Strengthened**: real Reddit evidence (including the single strongest piece of evidence in either pass — the sends/auxes thread), cross-DAW breadth beyond Logic/Ableton, a verified academic survey checked and correctly ruled out as unhelpful (not just unexamined), several real competitors at real prices.

**Unchanged**: still no incidence/TAM/willingness-to-pay estimate. Still "niche-but-real," not survey-grade.

**Weakened**: v1 undercounted competition and overgeneralized "no good solution exists" — the more accurate claim is "no demonstrated universal, lossless translator between arbitrary DAWs, devices, and plugin state," not "nothing exists." Also flags that v1's "two separate threads" framing on some forum links needs double-checking (URLs with `viewtopic.php?p=...` are posts, not necessarily distinct threads) — treat as unverified, don't double-count.

**Recommended next step, if this gets taken further**: structured interviews (20-30, mixed DAW-pair/persona), not another round of search-based research — the research explicitly says aggregate adoption surveys, Reddit upvotes, and even 600+ survey responses about DAW *usage* cannot substitute for asking real people about a real recent migration and what they actually did/paid/lost.

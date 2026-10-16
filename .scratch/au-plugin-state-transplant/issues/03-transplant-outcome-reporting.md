# 03: Transplant outcome reporting

**What to build:** The conversion report clearly distinguishes which plugin instances were transplanted (real state carried over) from which fell back to suggestion-only, with a stated reason for every fallback (not installed, not an AU plugin, no AU support on this platform), plus a flag when the installed version differs from the version Logic used. This is what lets the project owner know what to manually double-check before sending a converted project to a collaborator, per the spec's core promise: never silently produce a "looks loaded but is actually wrong" result.

Demoable via `--report-only` on a project with a mix of transplantable and non-transplantable plugins: the report names each instance's outcome and, for fallbacks, why.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] The report lists, per plugin instance, whether it was transplanted or fell back to suggestion-only.
- [ ] Every fallback states its specific reason (not installed / not AU / platform has no AU support).
- [ ] A transplanted instance whose installed version differs from the version recorded in the Logic project is flagged in the report (not blocked — the transplant is still attempted — just flagged for the user to double-check).
- [ ] Report-generation tests cover at least one of each outcome (transplanted, each fallback reason, version-mismatch-but-transplanted).

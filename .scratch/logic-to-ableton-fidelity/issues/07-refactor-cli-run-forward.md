# 07 - Extract orchestration logic out of `cli.py`'s `_run_forward`

Status: ready-for-agent
Type: task

## What

`cli.py`'s `_run_forward()` (~lines 534-849, ~315 lines) mixes argument validation, JSON progress-event emission, mixer-override merging, and pipeline invocation in one function. This is the one real architecture smell found in the fork-vs-reimplement audit (see spec.md) — everything else in the codebase (decoder/model/writer separation) is clean.

## Why bother

Every other ticket in this feature (02 through 06) adds new steps to the same pipeline this function orchestrates. Extracting the orchestration into its own module before piling more logic into it keeps the growing feature set from calcifying into the same monolith.

## Scope

Pull the pipeline-invocation and progress-reporting logic out of `cli.py` into a dedicated module (e.g. `pipeline.py` or similar), leaving `cli.py` doing only argument parsing and calling into it. No behavior change — this is a pure refactor, verify with the existing test suite (should have ~9,700 lines of tests to lean on).

## Answer

(fill in once implemented)

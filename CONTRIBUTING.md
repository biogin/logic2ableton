# Contributing

The reverse-engineering write-ups in [docs/](docs/) explain how the Logic MIDI and Pro Tools session formats were decoded and what is still open.

## Running tests

```bash
python -m pytest tests -q
ruff check logic2ableton tests scripts
```

Tests against real sessions are optional and skipped by default. To run them, point `L2A_LOGIC_FIXTURE` at a local `.logicx` package and `L2A_PTX_FIXTURE` at a local `.ptx` file before invoking pytest.

Run the six-lane smoke check, which synthesizes a Logic project, a Live set, and a Pro Tools session and converts each through the CLI:

```bash
python -m scripts.smoke_standalone --source
python -m scripts.smoke_standalone dist/logic2ableton.exe   # against the packaged binary
```

No third-party Python dependencies. The Ableton template is bundled, so no Ableton installation is needed to generate Live sets.

## Building

Python package:

```bash
python -m build
```

Standalone converter:

```bash
pyinstaller logic2ableton.spec
dist/logic2ableton.exe --version
```

Desktop app, development:

```bash
cd app
npm ci
npm run dev
```

Desktop app, build + verify:

```bash
cd app
npm ci
npm run build
npm run typecheck
npm test
```

The desktop bundles Geist Sans directly; its font license is included in `app/src/renderer/public/Geist-LICENSE.txt` and copied into the built app.

Windows release artifacts, built locally:

```bash
pyinstaller logic2ableton.spec
copy dist\logic2ableton.exe app\resources\logic2ableton.exe
cd app
npm ci
npm run dist:win
```

## Release process

GitHub Actions validates: Ruff lint and the desktop app build, Python tests on Windows and macOS, Python package builds, a packaged-binary smoke run through all six conversion lanes, and tagged release packaging for Windows and macOS.

Publishing a release is done by pushing a `v*` tag. The workflow uploads the generated installers to GitHub Releases automatically. The same workflow publishes the Python package to PyPI through a trusted publisher (environment `pypi`) once the repository variable `PYPI_PUBLISH` is set to `true`.

The macOS build matrix produces two Apple Silicon DMGs: the regular one (macOS 12+) and a second built against Electron 37.10.3 for macOS 11 Big Sur. The installer job can also be run on demand with `workflow_dispatch`, which builds and uploads the same artifacts without cutting a GitHub Release.

## What "production ready" means here

- Repeated validation across parser tests, package builds, standalone converter builds, and desktop packaging
- Standalone converter smoke coverage for all six routes in CI before tagged release packaging
- Reports emitted on both success and failure paths so support starts with evidence instead of guesswork
- Desktop app safety rails around approved files, active jobs, and artifact opening
- The Pro Tools parser is validated against a real Pro Tools 2023 studio session (96 kHz, comped vocals, stereo lanes) and a synthetic obfuscated fixture that runs in CI
- All six conversion lanes ship from the same repo and version together

## Bug reports

Useful issues include:

- The Logic Pro or Ableton Live version used to save the project
- The exact generated report
- A minimal failing project if one can be shared
- Whether the issue is in the desktop app, CLI, or packaging

Open issues here: https://github.com/Evilander/logic2ableton/issues

"""Which Audio Unit plugins are actually installed on this machine.

Logic's AU type/subtype/manufacturer identity (see PluginInstance) says what
plugin an instance is, but says nothing about whether the machine running
the conversion can host it. An AU component declares its own identity in its
bundle's Info.plist (the AudioComponents array), so that is checked directly
rather than trusting a plugin-name database.
"""

import plistlib
import sys
from pathlib import Path


def _default_search_paths() -> list[Path]:
    return [
        Path("/Library/Audio/Plug-Ins/Components"),
        Path.home() / "Library/Audio/Plug-Ins/Components",
    ]


def _audio_components(bundle: Path) -> list[dict]:
    """Every AudioComponents entry a bundle's Info.plist declares, each with at
    least a usable (type, subtype, manufacturer) identity.

    Checked against real installed bundles (e.g. FabFilter Pro-Q 4 4.02): an
    entry also carries its own `version` -- an integer packed the same way
    Apple packs bundle versions generally, 0xMMMMmmbb (major, minor, bugfix).
    For Pro-Q 4 4.02 that's 262146 (0x00040002), matching its
    CFBundleShortVersionString "4.02". Not every entry sets `version`; those
    are kept (identity is still usable) but have no version to compare.
    """
    info_plist = bundle / "Contents/Info.plist"
    try:
        with info_plist.open("rb") as f:
            info = plistlib.load(f)
    except (OSError, ValueError):
        return []
    components = []
    for component in info.get("AudioComponents", []):
        type_ = component.get("type")
        subtype = component.get("subtype")
        manufacturer = component.get("manufacturer")
        if isinstance(type_, str) and isinstance(subtype, str) and isinstance(manufacturer, str):
            components.append(component)
    return components


def _all_components(search_paths: list[Path] | None) -> list[dict]:
    components: list[dict] = []
    for root in search_paths if search_paths is not None else _default_search_paths():
        try:
            entries = list(root.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.suffix.lower() == ".component":
                components.extend(_audio_components(entry))
    return components


def installed_au_components(search_paths: list[Path] | None = None) -> set[tuple[str, str, str]]:
    """Every (type, subtype, manufacturer) 4CC triple registered on this machine.

    Absent search directories (not macOS, or nothing installed) yield an
    empty set rather than an error -- the AU platform-support fallback and
    the not-installed fallback are both just "this triple isn't in here".
    """
    return {
        (component["type"], component["subtype"], component["manufacturer"])
        for component in _all_components(search_paths)
    }


def installed_au_component_versions(search_paths: list[Path] | None = None) -> dict[tuple[str, str, str], int]:
    """Each installed component's own declared version (its Info.plist
    AudioComponents `version` integer), keyed by the same identity triple
    `installed_au_components()` uses.

    Lets the report flag when the plugin installed here differs from the
    version Logic recorded (US16) -- the transplant is still attempted
    either way, this is only ever a "double-check" flag, never a block. A
    bundle whose entry has no `version` (or a non-int one) is left out, so
    no mismatch can be claimed for it rather than a false "version 0".
    """
    versions: dict[tuple[str, str, str], int] = {}
    for component in _all_components(search_paths):
        version = component.get("version")
        if isinstance(version, int):
            versions[(component["type"], component["subtype"], component["manufacturer"])] = version
    return versions


def format_au_version(version: int) -> str:
    """Decode an AU component's packed version int into a human "major.minor.bugfix"
    string -- 0xMMMMmmbb, e.g. 262146 -> "4.0.2" (FabFilter Pro-Q 4.02 on this machine)."""
    major = (version >> 16) & 0xFFFF
    minor = (version >> 8) & 0xFF
    bugfix = version & 0xFF
    return f"{major}.{minor}.{bugfix}"


def au_platform_supported() -> bool:
    """Whether this OS can host Audio Units at all -- only macOS can.

    On Windows (or any non-macOS platform), every third-party plugin falls
    back to suggestion-only purely because of the platform, not because any
    particular plugin "isn't installed" -- the report states that specific
    reason instead of the generic one (US8/US9).
    """
    return sys.platform == "darwin"


def au_component_installed(
    au_type: str, au_subtype: str, au_manufacturer: str, *, search_paths: list[Path] | None = None,
) -> bool:
    return (au_type, au_subtype, au_manufacturer) in installed_au_components(search_paths)

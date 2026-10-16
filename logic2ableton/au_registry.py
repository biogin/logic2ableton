"""Which Audio Unit plugins are actually installed on this machine.

Logic's AU type/subtype/manufacturer identity (see PluginInstance) says what
plugin an instance is, but says nothing about whether the machine running
the conversion can host it. An AU component declares its own identity in its
bundle's Info.plist (the AudioComponents array), so that is checked directly
rather than trusting a plugin-name database.
"""

import plistlib
from pathlib import Path


def _default_search_paths() -> list[Path]:
    return [
        Path("/Library/Audio/Plug-Ins/Components"),
        Path.home() / "Library/Audio/Plug-Ins/Components",
    ]


def _component_identities(bundle: Path) -> set[tuple[str, str, str]]:
    info_plist = bundle / "Contents/Info.plist"
    try:
        with info_plist.open("rb") as f:
            info = plistlib.load(f)
    except (OSError, ValueError):
        return set()
    identities = set()
    for component in info.get("AudioComponents", []):
        type_ = component.get("type")
        subtype = component.get("subtype")
        manufacturer = component.get("manufacturer")
        if isinstance(type_, str) and isinstance(subtype, str) and isinstance(manufacturer, str):
            identities.add((type_, subtype, manufacturer))
    return identities


def installed_au_components(search_paths: list[Path] | None = None) -> set[tuple[str, str, str]]:
    """Every (type, subtype, manufacturer) 4CC triple registered on this machine.

    Absent search directories (not macOS, or nothing installed) yield an
    empty set rather than an error -- the AU platform-support fallback and
    the not-installed fallback are both just "this triple isn't in here".
    """
    identities: set[tuple[str, str, str]] = set()
    for root in search_paths if search_paths is not None else _default_search_paths():
        try:
            entries = list(root.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.suffix.lower() == ".component":
                identities |= _component_identities(entry)
    return identities


def au_component_installed(
    au_type: str, au_subtype: str, au_manufacturer: str, *, search_paths: list[Path] | None = None,
) -> bool:
    return (au_type, au_subtype, au_manufacturer) in installed_au_components(search_paths)

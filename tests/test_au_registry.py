import plistlib
from pathlib import Path
from unittest.mock import patch

from logic2ableton.au_registry import (
    au_component_installed,
    au_platform_supported,
    format_au_version,
    installed_au_component_versions,
    installed_au_components,
)


def _make_component(
    root: Path, name: str, *, type_: str, subtype: str, manufacturer: str, version: int | None = None,
) -> Path:
    bundle = root / f"{name}.component"
    contents = bundle / "Contents"
    contents.mkdir(parents=True)
    entry = {"type": type_, "subtype": subtype, "manufacturer": manufacturer, "name": name}
    if version is not None:
        entry["version"] = version
    with (contents / "Info.plist").open("wb") as f:
        plistlib.dump({"AudioComponents": [entry]}, f)
    return bundle


def test_installed_au_components_reads_real_component_bundles(tmp_path):
    _make_component(tmp_path, "Test EQ", type_="aufx", subtype="TEQ1", manufacturer="Acme")
    assert installed_au_components([tmp_path]) == {("aufx", "TEQ1", "Acme")}


def test_au_component_installed_true_for_a_registered_triple(tmp_path):
    _make_component(tmp_path, "Test EQ", type_="aufx", subtype="TEQ1", manufacturer="Acme")
    assert au_component_installed("aufx", "TEQ1", "Acme", search_paths=[tmp_path]) is True


def test_au_component_installed_false_for_an_unregistered_triple(tmp_path):
    _make_component(tmp_path, "Test EQ", type_="aufx", subtype="TEQ1", manufacturer="Acme")
    assert au_component_installed("aufx", "ZZZZ", "Acme", search_paths=[tmp_path]) is False


def test_installed_au_components_on_an_empty_or_missing_directory(tmp_path):
    assert installed_au_components([tmp_path]) == set()
    assert installed_au_components([tmp_path / "does-not-exist"]) == set()


def test_installed_au_components_skips_a_bundle_with_no_readable_info_plist(tmp_path):
    bundle = tmp_path / "Broken.component" / "Contents"
    bundle.mkdir(parents=True)
    # No Info.plist at all: must not crash the scan.
    assert installed_au_components([tmp_path]) == set()


def test_installed_au_component_versions_reads_the_declared_version(tmp_path):
    # 262146 == 0x00040002 -- the real packed version FabFilter Pro-Q 4.02 declares
    # in its own Info.plist AudioComponents entry on this machine.
    _make_component(tmp_path, "Test EQ", type_="aufx", subtype="TEQ1", manufacturer="Acme", version=262146)
    assert installed_au_component_versions([tmp_path]) == {("aufx", "TEQ1", "Acme"): 262146}


def test_installed_au_component_versions_omits_a_bundle_with_no_version(tmp_path):
    # No `version` key declared -- the identity is still usable (installed_au_components
    # still finds it), but there is nothing to compare for a version-mismatch flag.
    _make_component(tmp_path, "Test EQ", type_="aufx", subtype="TEQ1", manufacturer="Acme")
    assert installed_au_components([tmp_path]) == {("aufx", "TEQ1", "Acme")}
    assert installed_au_component_versions([tmp_path]) == {}


def test_format_au_version_decodes_the_packed_major_minor_bugfix_int():
    # Matches FabFilter Pro-Q 4's real Info.plist: version 262146, CFBundleShortVersionString "4.02".
    assert format_au_version(262146) == "4.0.2"
    assert format_au_version(0) == "0.0.0"


def test_au_platform_supported_is_true_on_macos_false_elsewhere():
    with patch("logic2ableton.au_registry.sys.platform", "darwin"):
        assert au_platform_supported() is True
    with patch("logic2ableton.au_registry.sys.platform", "win32"):
        assert au_platform_supported() is False

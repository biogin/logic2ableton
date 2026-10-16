import plistlib
from pathlib import Path

from logic2ableton.au_registry import au_component_installed, installed_au_components


def _make_component(root: Path, name: str, *, type_: str, subtype: str, manufacturer: str) -> Path:
    bundle = root / f"{name}.component"
    contents = bundle / "Contents"
    contents.mkdir(parents=True)
    with (contents / "Info.plist").open("wb") as f:
        plistlib.dump(
            {"AudioComponents": [{"type": type_, "subtype": subtype, "manufacturer": manufacturer, "name": name}]},
            f,
        )
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

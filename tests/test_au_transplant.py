import struct
import xml.etree.ElementTree as ET

from logic2ableton.au_transplant import (
    au_identity_ints,
    decide_transplant,
    has_undetected_instrument,
    make_au_plugin_device,
    missing_instrument,
)
from logic2ableton.models import PluginInstance


def _plugin(**overrides) -> PluginInstance:
    fields = dict(
        name="Untitled",  # the preset name -- must never end up as the device's display Name
        au_type="aufx",
        au_subtype="SthB",
        au_manufacturer="OekS",
        is_waves=False,
        raw_plist={},
        raw_plist_bytes=b"the-exact-original-plist-bytes",
    )
    fields.update(overrides)
    return PluginInstance(**fields)


def test_au_identity_ints_match_the_big_endian_4cc_packing_logic_already_uses():
    plugin = _plugin(au_type="aufx", au_subtype="FQ4p", au_manufacturer="FabF")
    assert au_identity_ints(plugin) == (
        struct.unpack(">I", b"aufx")[0],
        struct.unpack(">I", b"FQ4p")[0],
        struct.unpack(">I", b"FabF")[0],
    )


def test_make_au_plugin_device_buffer_round_trips_the_exact_original_bytes():
    """The whole point of the transplant: Buffer must decode back to byte-identical
    content, not a re-serialization -- see the blob-transplant spike's findings."""
    original = b"FFBS\x01\x00\x00\x00some-real-plugin-state-bytes\x00\x01\x02"
    plugin = _plugin(raw_plist_bytes=original)

    device = make_au_plugin_device(plugin, device_id=0, automation_target_id=100, pointee_id=101)

    buffer = device.find(".//AuPluginInfo/Preset/AuPreset/Buffer")
    assert bytes.fromhex(buffer.text) == original


def test_make_au_plugin_device_identity_fields_and_ids():
    plugin = _plugin(au_type="aumf", au_subtype="FQ4p", au_manufacturer="FabF")
    device = make_au_plugin_device(plugin, device_id=3, automation_target_id=500, pointee_id=501)

    assert device.tag == "PluginDevice"
    assert device.get("Id") == "3"

    au_info = device.find("PluginDesc/AuPluginInfo")
    assert au_info.find("ComponentType").get("Value") == str(struct.unpack(">I", b"aumf")[0])
    assert au_info.find("ComponentSubType").get("Value") == str(struct.unpack(">I", b"FQ4p")[0])
    assert au_info.find("ComponentManufacturer").get("Value") == str(struct.unpack(">I", b"FabF")[0])

    assert device.find("On/AutomationTarget").get("Id") == "500"
    assert device.find("Pointee").get("Id") == "501"


def test_make_au_plugin_device_uses_the_plugin_database_name_not_the_preset_name():
    # Waves CLA-76 (ksWV/76CM) is in the static plugin database.
    plugin = _plugin(name="My Vocal Comp Preset", au_manufacturer="ksWV", au_subtype="76CM")
    device = make_au_plugin_device(plugin, device_id=0, automation_target_id=1, pointee_id=2)
    name = device.find("PluginDesc/AuPluginInfo/Name").get("Value")
    assert name != "My Vocal Comp Preset"
    assert "CLA-76" in name


def test_make_au_plugin_device_falls_back_to_4cc_identity_for_an_unknown_plugin():
    plugin = _plugin(name="Untitled", au_manufacturer="ZZZZ", au_subtype="ZZZZ")
    device = make_au_plugin_device(plugin, device_id=0, automation_target_id=1, pointee_id=2)
    name = device.find("PluginDesc/AuPluginInfo/Name").get("Value")
    assert name == "ZZZZ/ZZZZ"


def test_make_au_plugin_device_produces_valid_xml():
    plugin = _plugin()
    device = make_au_plugin_device(plugin, device_id=0, automation_target_id=1, pointee_id=2)
    # Round-trip through serialization to catch any malformed element.
    ET.fromstring(ET.tostring(device))


_INSTALLED = {("aufx", "SthB", "OekS")}


def test_decide_transplant_transplants_an_installed_plugin_with_captured_state():
    outcome = decide_transplant(_plugin(), _INSTALLED)
    assert outcome.status == "transplanted"
    assert outcome.version_mismatch is False


def test_decide_transplant_reports_no_captured_state_before_checking_anything_else():
    plugin = _plugin(raw_plist_bytes=b"")
    outcome = decide_transplant(plugin, _INSTALLED)
    assert outcome.status == "no_captured_state"
    assert outcome.reason == "no plugin state was captured from the Logic project for this instance"


def test_decide_transplant_reports_platform_unsupported_before_checking_the_registry():
    outcome = decide_transplant(_plugin(), _INSTALLED, platform_supported=False)
    assert outcome.status == "platform_unsupported"
    assert outcome.reason == "this platform has no Audio Unit support"


def test_decide_transplant_reports_not_installed_when_the_identity_is_missing():
    outcome = decide_transplant(_plugin(), set())
    assert outcome.status == "not_installed"
    assert outcome.reason == "not installed as an Audio Unit on this machine"


def test_decide_transplant_never_flags_a_mismatch_even_when_versions_clearly_differ():
    """US16 is currently unimplementable, not just suppressed for noisy cases: Logic's
    recorded 'version' is Apple's AU ClassInfo preset-format-version key
    (kAUPresetVersionKey), not the plugin's software version -- an earlier version of
    this logic only suppressed the comparison when Logic recorded 0 (~97% of real
    instances sampled), but still spuriously "mismatched" the rare non-zero case every
    time, since a preset-format version like 1 or 3 will essentially never equal a
    packed bundle version like 262146 by chance -- the two are unrelated number spaces
    regardless of whether Logic's value happens to be 0. No reliable software-version
    field was found anywhere in a Logic plugin instance's plist, so the comparison is
    disabled outright: version_mismatch is always False, even here where the two
    numbers plainly differ. logic_version/installed_version are still populated for a
    transplanted outcome in case a genuine version source turns up later."""
    plugin = _plugin(raw_plist={"version": 3})
    outcome = decide_transplant(
        plugin, _INSTALLED, installed_versions={("aufx", "SthB", "OekS"): 262146},
    )
    assert outcome.status == "transplanted"
    assert outcome.version_mismatch is False
    assert outcome.logic_version == 3
    assert outcome.installed_version == 262146


def test_decide_transplant_does_not_flag_a_mismatch_when_logic_recorded_no_version():
    plugin = _plugin(raw_plist={"version": 0})
    outcome = decide_transplant(
        plugin, _INSTALLED, installed_versions={("aufx", "SthB", "OekS"): 262146},
    )
    assert outcome.status == "transplanted"
    assert outcome.version_mismatch is False


def test_decide_transplant_does_not_flag_a_mismatch_when_installed_version_is_unknown():
    plugin = _plugin(raw_plist={"version": 3})
    outcome = decide_transplant(plugin, _INSTALLED, installed_versions={})
    assert outcome.status == "transplanted"
    assert outcome.version_mismatch is False


def test_decide_transplant_does_not_flag_a_mismatch_when_versions_agree():
    plugin = _plugin(raw_plist={"version": 1})
    outcome = decide_transplant(
        plugin, _INSTALLED, installed_versions={("aufx", "SthB", "OekS"): 1},
    )
    assert outcome.status == "transplanted"
    assert outcome.version_mismatch is False


def test_missing_instrument_returns_the_instance_when_its_transplant_failed():
    instrument = _plugin(au_type="aumu", au_subtype="XfsX", au_manufacturer="XFER")
    effect = _plugin(au_type="aufx", au_subtype="SthB", au_manufacturer="OekS")
    result = missing_instrument([effect, instrument], installed_components=set())
    assert result is instrument


def test_missing_instrument_returns_none_when_the_instrument_transplanted():
    instrument = _plugin(au_type="aumu", au_subtype="XfsX", au_manufacturer="XFER")
    installed = {("aumu", "XfsX", "XFER")}
    assert missing_instrument([instrument], installed) is None


def test_missing_instrument_returns_none_with_no_instrument_on_the_strip():
    effect = _plugin(au_type="aufx", au_subtype="SthB", au_manufacturer="OekS")
    assert missing_instrument([effect], installed_components=set()) is None


def test_missing_instrument_ignores_a_failed_aumf_even_though_it_is_midi_aware():
    """aumf ("Music Effect") processes a signal that exists independent of it --
    FabFilter Pro-Q 4, a pure EQ, is aumf -- so it must never trigger auto-mute."""
    midi_aware_effect = _plugin(au_type="aumf", au_subtype="FQ4p", au_manufacturer="FabF")
    assert missing_instrument([midi_aware_effect], installed_components=set()) is None


_INSTRUMENT_STRIP = 0x43
_AUDIO_STRIP = 0x40


def test_has_undetected_instrument_true_for_an_instrument_strip_with_no_aumu_at_all():
    """Real case: a note-bearing track whose channel strip yielded several extracted
    effect instances and zero instrument ones -- Logic's own stock instruments don't
    serialize as an embedded AU-state plist, so extract_plugins() never sees them."""
    effects_only = [_plugin(au_type="aufx"), _plugin(au_type="aumf", au_subtype="FQ4p", au_manufacturer="FabF")]
    assert has_undetected_instrument(_INSTRUMENT_STRIP, effects_only) is True


def test_has_undetected_instrument_false_when_an_aumu_was_actually_found():
    """Even a found-but-failed aumu means this isn't 'undetected' -- that's
    missing_instrument's case, with its own, more specific report wording."""
    found_instrument = [_plugin(au_type="aumu", au_subtype="XfsX", au_manufacturer="XFER")]
    assert has_undetected_instrument(_INSTRUMENT_STRIP, found_instrument) is False


def test_has_undetected_instrument_false_for_a_non_instrument_strip_kind():
    assert has_undetected_instrument(_AUDIO_STRIP, []) is False


def test_has_undetected_instrument_false_for_an_unknown_strip_kind():
    assert has_undetected_instrument(None, []) is False

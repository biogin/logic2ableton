import struct
import xml.etree.ElementTree as ET

from logic2ableton.au_transplant import au_identity_ints, make_au_plugin_device
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

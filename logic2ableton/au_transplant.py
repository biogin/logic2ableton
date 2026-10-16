"""Synthesize an Ableton AU plugin device that carries a Logic plugin instance's
exact state across, rather than approximating its parameters.

The mechanism (confirmed against real Ableton Live, not just inferred from the
file format): a device is PluginDevice > PluginDesc > AuPluginInfo, and its
Preset > AuPreset > Buffer element holds Logic's *entire* original plist for
that plugin instance, hex-encoded verbatim -- not a re-serialization, and not
just the plugin's own vendor-specific inner value. A partial or reconstructed
buffer loads the right plugin but silently resets it to its factory default
rather than erroring; the full original bytes are what actually restores the
real state. See .scratch/logic-to-ableton-fidelity/issues/01-au-classinfo-blob-transplant-spike.md
and .scratch/au-plugin-state-transplant/spec.md for how this was found.
"""

import struct
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from logic2ableton.models import PluginInstance
from logic2ableton.plugin_database import lookup_au_plugin

# Human-readable fallback reasons, kept as module constants so the decision
# logic here and the report's wording (report.py) can't drift apart.
NOT_INSTALLED_REASON = "not installed as an Audio Unit on this machine"
NO_CAPTURED_STATE_REASON = "no plugin state was captured from the Logic project for this instance"
PLATFORM_UNSUPPORTED_REASON = "this platform has no Audio Unit support"


@dataclass(frozen=True)
class TransplantOutcome:
    """Why a plugin instance did or didn't get its exact Logic state transplanted.

    ``status`` is one of "transplanted", "not_installed", "no_captured_state",
    or "platform_unsupported" -- tracked as distinct reasons (not a single
    generic "skipped") so the report can always say exactly why, per the
    spec's core promise: never leave the user guessing what to double-check.

    ``version_mismatch`` is currently always False -- see decide_transplant's
    docstring: no field was found in a Logic plugin instance's plist that
    reliably holds its software version, so there is nothing trustworthy to
    compare the installed version against yet. ``logic_version``/
    ``installed_version`` are still populated on a "transplanted" outcome in
    case a genuine version source turns up later.
    """
    status: str
    reason: str | None = None
    version_mismatch: bool = False
    logic_version: int | None = None
    installed_version: int | None = None


def decide_transplant(
    plugin: PluginInstance,
    installed_components: set[tuple[str, str, str]],
    *,
    installed_versions: dict[tuple[str, str, str], int] | None = None,
    platform_supported: bool = True,
) -> TransplantOutcome:
    """Single source of truth for whether ``plugin`` gets transplanted, and why
    not when it doesn't -- used both by the writer (ableton_generator.py, to
    decide what to actually insert) and the report (report.py, to describe
    the same decision) so the two can never disagree about a given instance.

    Checked in this order: a plugin with no captured state can never be
    transplanted regardless of what's installed; a platform with no AU
    support at all fails every instance for that one reason rather than the
    generic "not installed"; only then is the installed-component registry
    consulted.

    Version comparison (US16) is currently never flagged, by design, not
    oversight: Logic's own recorded `version` (inside ``plugin.raw_plist``)
    turned out, against real Logic projects, to almost always be 0 --
    sampling a real multi-plugin session found 686 of 704 instances at
    exactly 0, with the rare non-zero case still a tiny integer (1), nothing
    like a release version such as "4.02". That is consistent with Apple's
    own AU ClassInfo convention, where this key is a *preset dictionary
    format* version (kAUPresetVersionKey), not the plugin's software version
    -- it is not the same kind of number, in any case, as the installed
    component's own declared version (``installed_versions``, a real packed
    major/minor/bugfix int). The two are from unrelated number spaces
    regardless of whether Logic's value happens to be 0 or not: an early
    version of this logic only suppressed the comparison when it was 0,
    which fixed the 97% case but still spuriously "mismatched" the rare
    non-zero case every time, since a preset-format version like 1 will
    essentially never equal a packed bundle version like 262146 by chance.
    That reproduced exactly the noise this flag exists to avoid, just for a
    smaller slice. No field was found anywhere in a Logic plugin instance's
    plist that reliably holds its software version, so the comparison is
    disabled outright rather than narrowed further -- ``version_mismatch``
    is always False today. ``logic_version``/``installed_version`` are still
    populated on a transplanted outcome in case a genuine version source
    turns up later; nothing currently reads them for a true/false judgement.
    """
    if not plugin.raw_plist_bytes:
        return TransplantOutcome(status="no_captured_state", reason=NO_CAPTURED_STATE_REASON)
    if not platform_supported:
        return TransplantOutcome(status="platform_unsupported", reason=PLATFORM_UNSUPPORTED_REASON)

    identity = (plugin.au_type, plugin.au_subtype, plugin.au_manufacturer)
    if identity not in installed_components:
        return TransplantOutcome(status="not_installed", reason=NOT_INSTALLED_REASON)

    logic_version = plugin.raw_plist.get("version") if isinstance(plugin.raw_plist, dict) else None
    installed_version = (installed_versions or {}).get(identity)
    return TransplantOutcome(
        status="transplanted",
        version_mismatch=False,
        logic_version=logic_version,
        installed_version=installed_version,
    )


# The only AU type that reliably means "this channel strip's sole sound source" --
# aumf ("Music Effect") is MIDI-aware but still processes a signal that exists
# independent of it (FabFilter Pro-Q 4, a pure EQ, is aumf). See CONTEXT.md.
_INSTRUMENT_AU_TYPE = "aumu"


def missing_instrument(
    plugins: list[PluginInstance],
    installed_components: set[tuple[str, str, str]],
    *,
    installed_versions: dict[tuple[str, str, str], int] | None = None,
    platform_supported: bool = True,
) -> PluginInstance | None:
    """A channel strip's instrument plugin instance, if it has one and it didn't
    transplant -- the one case where nothing else on that strip has anything to
    process without it (see docs/adr/0001-auto-mute-over-bounce-for-missing-instrument-fallback.md).

    A channel strip has at most one instrument slot in Logic, so at most one
    instance in ``plugins`` can have this type; this is the shared decision
    both the writer (to mute the destination track) and the report (to say
    why) call, so they can never disagree -- same pattern as decide_transplant.
    """
    for plugin in plugins:
        if plugin.au_type != _INSTRUMENT_AU_TYPE:
            continue
        outcome = decide_transplant(
            plugin, installed_components, installed_versions=installed_versions, platform_supported=platform_supported,
        )
        if outcome.status != "transplanted":
            return plugin
    return None


def _display_name(plugin: PluginInstance) -> str:
    """The plugin's own product name, never its preset name.

    PluginInstance.name is the *preset* name ("Default Setting", "Untitled",
    ...) -- using it here would mislabel the device. The plugin database
    only covers some vendors, so an unrecognized one falls back to its 4CC
    identity rather than a name that's actively wrong.
    """
    info = lookup_au_plugin(plugin.au_manufacturer, plugin.au_subtype)
    return info.name if info else f"{plugin.au_manufacturer}/{plugin.au_subtype}"


def _fourcc_to_int(code: str) -> int:
    """Logic's and Ableton's AU identity fields share this same big-endian packing."""
    return struct.unpack(">I", code.encode("ascii"))[0]


def au_identity_ints(plugin: PluginInstance) -> tuple[int, int, int]:
    """(ComponentType, ComponentSubType, ComponentManufacturer), Ableton's own field names."""
    return (
        _fourcc_to_int(plugin.au_type),
        _fourcc_to_int(plugin.au_subtype),
        _fourcc_to_int(plugin.au_manufacturer),
    )


def make_au_plugin_device(
    plugin: PluginInstance,
    *,
    device_id: int,
    automation_target_id: int,
    pointee_id: int,
) -> ET.Element:
    """A PluginDevice element carrying ``plugin``'s exact Logic state.

    ``device_id`` is chain-local (unique within the target track's own
    Devices list); ``automation_target_id``/``pointee_id`` must be fresh,
    never-before-used ids from the set's NextPointeeId counter. The caller
    is responsible for all three and for appending the result into the
    right position of the target track's Devices list.
    """
    component_type, component_subtype, component_manufacturer = au_identity_ints(plugin)

    device = ET.Element("PluginDevice", Id=str(device_id))
    ET.SubElement(device, "LomId", Value="0")
    ET.SubElement(device, "LomIdView", Value="0")
    ET.SubElement(device, "IsExpanded", Value="true")
    ET.SubElement(device, "BreakoutIsExpanded", Value="false")

    on = ET.SubElement(device, "On")
    ET.SubElement(on, "LomId", Value="0")
    ET.SubElement(on, "Manual", Value="true")
    automation_target = ET.SubElement(on, "AutomationTarget", Id=str(automation_target_id))
    ET.SubElement(automation_target, "LockEnvelope", Value="0")
    thresholds = ET.SubElement(on, "MidiCCOnOffThresholds")
    ET.SubElement(thresholds, "Min", Value="64")
    ET.SubElement(thresholds, "Max", Value="127")

    ET.SubElement(device, "ModulationSourceCount", Value="0")
    ET.SubElement(device, "ParametersListWrapper", LomId="0")
    ET.SubElement(device, "Pointee", Id=str(pointee_id))
    ET.SubElement(device, "LastSelectedTimeableIndex", Value="0")
    ET.SubElement(device, "LastSelectedClipEnvelopeIndex", Value="0")
    last_preset_ref = ET.SubElement(device, "LastPresetRef")
    ET.SubElement(last_preset_ref, "Value")
    ET.SubElement(device, "LockedScripts")
    ET.SubElement(device, "IsFolded", Value="false")
    ET.SubElement(device, "ShouldShowPresetName", Value="true")
    ET.SubElement(device, "UserName", Value="")
    ET.SubElement(device, "Annotation", Value="")

    source_context = ET.SubElement(device, "SourceContext")
    value = ET.SubElement(source_context, "Value")
    branch = ET.SubElement(value, "BranchSourceContext", Id="0")
    ET.SubElement(branch, "OriginalFileRef")
    ET.SubElement(branch, "BrowserContentPath", Value="")
    ET.SubElement(branch, "LocalFiltersJson", Value="")
    ET.SubElement(branch, "PresetRef")
    ET.SubElement(
        branch, "BranchDeviceId",
        Value=f"device:au:audiofx:{component_manufacturer}:{component_subtype}:{component_type}",
    )

    ET.SubElement(device, "MpePitchBendUsesTuning", Value="true")

    plugin_desc = ET.SubElement(device, "PluginDesc")
    au_info = ET.SubElement(plugin_desc, "AuPluginInfo", Id="0")
    ET.SubElement(au_info, "WinPosX", Value="0")
    ET.SubElement(au_info, "WinPosY", Value="0")
    ET.SubElement(au_info, "NumAudioInputs", Value="2")
    ET.SubElement(au_info, "NumAudioOutputs", Value="2")
    ET.SubElement(au_info, "IsPlaceholderDevice", Value="false")
    ET.SubElement(au_info, "ComponentType", Value=str(component_type))
    ET.SubElement(au_info, "ComponentSubType", Value=str(component_subtype))
    ET.SubElement(au_info, "ComponentManufacturer", Value=str(component_manufacturer))
    ET.SubElement(au_info, "ComponentFlags", Value="2")
    ET.SubElement(au_info, "Name", Value=_display_name(plugin))
    ET.SubElement(au_info, "Manufacturer", Value=plugin.au_manufacturer)

    preset = ET.SubElement(au_info, "Preset")
    au_preset = ET.SubElement(preset, "AuPreset", Id="0")
    ET.SubElement(au_preset, "OverwriteProtectionNumber", Value="0")
    ET.SubElement(au_preset, "MpeEnabled", Value="0")
    mpe_settings = ET.SubElement(au_preset, "MpeSettings")
    ET.SubElement(mpe_settings, "ZoneType", Value="0")
    ET.SubElement(mpe_settings, "FirstNoteChannel", Value="1")
    ET.SubElement(mpe_settings, "LastNoteChannel", Value="15")
    ET.SubElement(au_preset, "ParameterSettings")
    ET.SubElement(au_preset, "IsOn", Value="true")
    ET.SubElement(au_preset, "PowerMacroControlIndex", Value="-1")
    power_range = ET.SubElement(au_preset, "PowerMacroMappingRange")
    ET.SubElement(power_range, "Min", Value="64")
    ET.SubElement(power_range, "Max", Value="127")
    ET.SubElement(au_preset, "IsFolded", Value="false")
    ET.SubElement(au_preset, "StoredAllParameters", Value="true")
    ET.SubElement(au_preset, "DeviceLomId", Value="0")
    ET.SubElement(au_preset, "DeviceViewLomId", Value="0")
    ET.SubElement(au_preset, "IsOnLomId", Value="0")
    ET.SubElement(au_preset, "ParametersListWrapperLomId", Value="0")
    ET.SubElement(au_preset, "Buffer").text = plugin.raw_plist_bytes.hex().upper()
    ET.SubElement(au_preset, "PresetRef")

    ET.SubElement(device, "MpeEnabled", Value="false")
    mpe_settings2 = ET.SubElement(device, "MpeSettings")
    ET.SubElement(mpe_settings2, "ZoneType", Value="0")
    ET.SubElement(mpe_settings2, "FirstNoteChannel", Value="1")
    ET.SubElement(mpe_settings2, "LastNoteChannel", Value="15")

    return device

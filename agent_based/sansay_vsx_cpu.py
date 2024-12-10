#!/usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-

# License: GNU General Public License v2

from cmk.agent_based.v2 import (
    AgentSection,
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    Result,
    Service,
    State,
)
from cmk_addons.plugins.sansay_vsx.lib import (
    SansayVSXAPIData,
    find_key_recursive,
    parse_sansay_vsx_multiple,
    sansay_vsx_health_state,
)

agent_section_sansay_vsx_cpu = AgentSection(
    name="sansay_vsx_cpu",
    parse_function=parse_sansay_vsx_multiple,
    parsed_section_name="sansay_vsx_cpu",
)


HPE_DIMM_STATE = {
    "Null": ("A value is temporarily unavailable", 1),
    "Unknown": ("The status of the DIMM is unknown.", 3),
    "Other": ("DIMM status that does not fit any of these definitions.", 3),
    "NotPresent": ("DIMM is not present.", 1),
    "PresentUnused": ("DIMM is present but unused.", 0),
    "GoodInUse": ("DIMM is functioning properly and currently in use.", 0),
    "AddedButUnused": ("DIMM is added but currently unused.", 0),
    "UpgradedButUnused": ("DIMM is upgraded but currently unused.", 0),
    "ExpectedButMissing": ("DIMM is expected but missing.", 1),
    "DoesNotMatch": ("DIMM type does not match.", 1),
    "NotSupported": ("DIMM is not supported.", 1),
    "ConfigurationError": ("Configuration error in DIMM.", 2),
    "Degraded": ("DIMM state is degraded.", 1),
    "PresentSpare": ("DIMM is present but used as spare.", 0),
    "GoodPartiallyInUse": ("DIMM is functioning properly but partially in use.", 0),
    "MapOutConfiguration": ("DIMM mapped out due to configuration error.", 1),
    "MapOutError": ("DIMM mapped out due to training failure.", 1),
}


def discovery_sansay_vsx_cpu(section: SansayVSXAPIData) -> DiscoveryResult:
    """Discover all non absent single modules"""
    for key in section.keys():
        if "Collection" in section[key].get("@odata.type"):
            continue
        if section[key].get("Status", {}).get("State") == "Absent":
            continue
        yield Service(item=section[key]["Id"])


def check_sansay_vsx_cpu(item: str, section: SansayVSXAPIData) -> CheckResult:
    """Check module state"""
    data = section.get(item, None)
    if data is None:
        return

    capacity = data.get("CapacityMiB")
    if not capacity:
        capacity = data.get("SizeMB", 0)
    memtype = data.get("MemoryDeviceType")
    if not memtype:
        memtype = data.get("DIMMType")
    opspeed = data.get("OperatingSpeedMhz")
    if not opspeed:
        opspeed = data.get("MaximumFrequencyMHz")
    errcor = data.get("ErrorCorrection")

    mem_msg = f"Size: {capacity / 1024:0.0f}GB, Type: {memtype}-{opspeed} {errcor}"
    yield Result(state=State(0), summary=mem_msg)

    if data.get("Status"):
        status, message = sansay_vsx_health_state(data.get("Status", {}))
    elif state := find_key_recursive(data, "DIMMStatus"):
        message, status = HPE_DIMM_STATE.get(state, ("Unknown state", 3))
    else:
        status = 0
        message = "No known status value found"

    yield Result(state=State(status), notice=message)


check_plugin_sansay_vsx_cpu = CheckPlugin(
    name="sansay_vsx_cpu",
    service_name="Memory %s",
    sections=["sansay_vsx_cpu"],
    discovery_function=discovery_sansay_vsx_cpu,
    check_function=check_sansay_vsx_cpu,
)
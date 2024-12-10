#!/usr/bin/env python3
'''check Sansay VSX API for trunk(s) information and state'''
# -*- encoding: utf-8; py-indent-offset: 4 -*-

# License: GNU General Public License v2

from collections.abc import Mapping
from typing import Any
from cmk.agent_based.v2 import AgentSection
from cmk_addons.plugins.sansay_vsx.lib import (
    parse_sansay_vsx_multiple,
)
from cmk.agent_based.v2 import (
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    Result,
    Service,
    State,
)
from cmk_addons.plugins.sansay_vsx.lib import (
    SansayVSXAPIData,
    sansay_vsx_health_state,
)
from cmk.plugins.lib.elphase import (
    check_elphase,
)


agent_section_sansay_vsx_trunks = AgentSection(
    name="sansay_vsx_trunks",
    parse_function=parse_sansay_vsx_multiple,
    parsed_section_name="sansay_vsx_trunks",
)


def discovery_sansay_vsx_trunks(section: SansayVSXAPIData) -> DiscoveryResult:
    """Discover single sensors"""
    for key in section.keys():
        if section[key].get("Status", {}).get("State") == "Absent":
            continue
        yield Service(item=section[key]["Id"])


def check_sansay_vsx_trunks(
    item: str, params: Mapping[str, Any], section: SansayVSXAPIData
) -> CheckResult:
    """Check single outlet state"""
    data = section.get(item, None)
    if data is None:
        return

    socket_data = {item: {
        "voltage": data.get('Voltage', {}).get('Reading', 0),
        "current": data.get('CurrentAmps', {}).get('Reading', 0),
        "power": data.get('PowerWatts', {}).get('Reading', 0),
        "frequency": data.get('FrequencyHz', {}).get('Reading', 0),
        "appower": data.get('PowerWatts', {}).get('ApparentVA', 0),
        "energy": data.get('EnergykWh', {}).get('Reading', 0) * 1000
    }}

    yield from check_elphase(
        item,
        params,
        socket_data
    )

    dev_state, dev_msg = sansay_vsx_health_state(data.get("Status", {}))
    yield Result(state=State(dev_state), notice=dev_msg)


check_plugin_sansay_vsx_trunks = CheckPlugin(
    name="sansay_vsx_trunks",
    service_name="Trunk %s",
    sections=["sansay_vsx_trunks"],
    discovery_function=discovery_sansay_vsx_trunks,
    check_function=check_sansay_vsx_trunks,
    check_default_parameters={},
    check_ruleset_name="ups_outphase",
)